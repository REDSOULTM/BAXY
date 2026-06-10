"""Reflexión por LLM para gustos FINOS — capa opt-in del Jarvis (R-Jarvis fase 1, 2026-05-30).

La reflexión DETERMINISTA de `taste_profile.py` da el perfil base ("usás Code de
mañana, Spotify de noche, escuchás Soda Stereo"). Esta capa OPCIONAL pasa esas
observaciones agregadas por el 4B LOCAL para inferir gustos de MÁS ALTO NIVEL
("preferís rock latino de los 90", "programás de noche con música") — el patrón
observación→reflexión→insight de Generative Agents (arXiv:2304.03442), ahora con el
paso de reflexión por LLM como reservaba el diseño.

POR QUÉ gateado + medido: el 4B es RUIDOSO clasificando gustos. Reglas
de diseño, todas verificables:
  - **Gate default OFF** (`GEMMA4_TASTE_LLM_REFLECTION`): opt-in. Sin él, el perfil
    determinista manda intacto. Esta capa AUMENTA, nunca reemplaza la base medida.
  - **Background, NO per-turn**: el pase LLM corre en un thread daemon cada
    `_REFRESH_TTL_S`; la inyección al prompt sólo LEE el caché en disco (barato). La
    latencia tier-Alexa del turno no se toca.
  - **Guard estructural anti-alucinación**: cada insight DEBE citar (campo
    `evidencia`) una observación REAL; si la evidencia no referencia ninguna
    app/artista/franja observada, se descarta. Mide la FORMA (grounding), no confía
    en el contenido. Precisión > recall (mejor 1 insight bueno que 3 dudosos).
  - **thinking OFF**: MEDIDO (2026-05-30) que con thinking el 4B gasta TODO el budget
    en `reasoning_content` y devuelve content vacío (finish_reason=length). Off → JSON
    limpio y grounded.
  - **Privacidad**: 4B LOCAL (no cloud), sobre observaciones AGREGADAS (metadata, no
    contenido). Inspectable y borrable como el resto del perfil.

Fuentes: Generative Agents arXiv:2304.03442 · Guided Profile Generation arXiv:2409.13093.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import unicodedata
from dataclasses import dataclass

from .behavior_log import BehaviorLog
from .taste_profile import _clean_app, _title_artist, build_profile

logger = logging.getLogger(__name__)

# Cada cuánto re-reflexiona el background (el gusto se mueve en escala de días).
_REFRESH_TTL_S = float(os.environ.get("GEMMA4_TASTE_REFLECTION_TTL_S", str(6 * 3600)))
_MAX_INSIGHTS = 3
_MAX_INSIGHT_CHARS = 160
_MIN_TOKEN_LEN = 3

_REFRESHING = False          # evita refrescos concurrentes
_REFRESH_LOCK = threading.Lock()

_SYSTEM = (
    "Sos un analista de preferencias. A partir de DATOS OBSERVADOS de uso de una "
    "persona, inferís preferencias de ALTO NIVEL (género/época musical, patrón de "
    "trabajo, combinaciones de hábitos). REGLAS ESTRICTAS:\n"
    "1) SOLO inferís de los datos dados. NUNCA inventes artistas, apps o géneros que "
    "no se derivan directamente de los datos.\n"
    "2) Cada inferencia DEBE citar textualmente el dato observado que la sostiene.\n"
    "3) Si no podés inferir con confianza, devolvé MENOS (mejor 1 buena que 3 dudosas). "
    "Máximo 3.\n"
    "Respondé SOLO un array JSON, sin texto extra ni explicación:\n"
    '[{"insight": "<inferencia en español, alto nivel, concisa>", "evidencia": "<dato observado citado>"}]'
)


def _enabled() -> bool:
    raw = (os.environ.get("GEMMA4_TASTE_LLM_REFLECTION") or "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Insight:
    text: str
    evidence: str


# --------------------------------------------------------------------- grounding

def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower()


def _observed_tokens(prof) -> set[str]:
    """Tokens (folded, >=3 chars) de TODO lo observado: apps, artistas, franjas.
    El grounding guard exige que la `evidencia` de un insight toque alguno."""
    toks: set[str] = set()
    def add(text: str) -> None:
        for w in _fold(text).replace(".", " ").replace("—", " ").split():
            w = w.strip("()[],:;")
            if len(w) >= _MIN_TOKEN_LEN:
                toks.add(w)
    for app, _ in getattr(prof, "top_apps", []) or []:
        add(app); add(app.rsplit(".", 1)[0] if "." in app else app)
    for art, _ in getattr(prof, "top_artists", []) or []:
        add(art)
    for slot, app in (getattr(prof, "apps_by_slot", {}) or {}).items():
        add(slot); add(app)
    for slot in getattr(prof, "music_slots", []) or []:
        add(slot)
    return toks


def _is_grounded(ins: Insight, observed: set[str]) -> bool:
    """El insight se acepta SOLO si su evidencia referencia una observación real."""
    ev = _fold(ins.evidence)
    if not ins.text or not ev:
        return False
    if len(ins.text) > _MAX_INSIGHT_CHARS:
        return False
    ev_tokens = {w.strip("()[],:;.") for w in ev.replace("—", " ").split()}
    return bool(ev_tokens & observed)


# --------------------------------------------------------------------- LLM call

def _observations_text(prof) -> str:
    """Mismo render que ve el analista LLM (compacto, sólo lo observado)."""
    lines: list[str] = []
    if prof.top_apps:
        lines.append("- Apps más usadas: " + ", ".join(
            f"{_clean_app(a)} ({h}h)" for a, h in prof.top_apps))
    if prof.apps_by_slot:
        lines.append("- Ritmo diario: " + ", ".join(
            f"a la {slot} {_clean_app(app)}" for slot, app in prof.apps_by_slot.items()))
    if prof.top_artists:
        lines.append("- Artistas más escuchados: " + ", ".join(
            f"{_title_artist(a)} ({n} plays)" for a, n in prof.top_artists))
    if prof.music_slots:
        lines.append("- Escucha música: a la " + ", a la ".join(prof.music_slots))
    return "\n".join(lines)


def _parse_json_insights(content: str) -> list[Insight]:
    """Extrae el array JSON (tolera fences ```json y narración alrededor)."""
    if not content:
        return []
    txt = content.strip()
    # quitar fences
    if "```" in txt:
        m = re.search(r"```(?:json)?\s*(.+?)```", txt, re.DOTALL)
        if m:
            txt = m.group(1).strip()
    # primer array JSON
    start, end = txt.find("["), txt.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return []
    try:
        arr = json.loads(txt[start:end + 1])
    except Exception:
        return []
    out: list[Insight] = []
    for item in arr if isinstance(arr, list) else []:
        if not isinstance(item, dict):
            continue
        text = str(item.get("insight") or "").strip()
        ev = str(item.get("evidencia") or item.get("evidence") or "").strip()
        if text:
            out.append(Insight(text=text, evidence=ev))
    return out


def reflect(prof, llm_client) -> list[Insight]:
    """Un pase de reflexión: LLM (thinking OFF) → parse → grounding guard → dedup.
    Devuelve [] si está sin datos, deshabilitado, o nada pasa el guard."""
    if prof is None or prof.is_empty():
        return []
    obs_text = _observations_text(prof)
    if not obs_text:
        return []
    # Modelo: resolución SERVER-DRIVEN (probe /v1/models) — el default del client
    # ("gemma-4") no existe; el server expone "vram4-text". Robusto en cualquier
    # proceso (background thread incluido). Sin server -> None -> best-effort.
    model = None
    try:
        from ..infra.llama_server import resolve_turn_model
        model = resolve_turn_model(has_image=False)
    except Exception:
        model = None
    try:
        resp = llm_client.chat(
            [{"role": "system", "content": _SYSTEM},
             {"role": "user", "content": f"Datos observados:\n{obs_text}\n\nInferí las preferencias."}],
            enable_thinking=False,   # MEDIDO: con thinking devuelve content vacío (length)
            max_tokens=300,
            model=model,
            sampling={"temperature": 0.3},  # baja entropía -> JSON estructurado limpio
            timeout_s=60.0,
        )
        content = (resp.get("choices") or [{}])[0].get("message", {}).get("content") or ""
    except Exception as exc:
        logger.debug("reflect LLM failed: %s", exc)
        return []
    insights = _parse_json_insights(content)
    observed = _observed_tokens(prof)
    grounded: list[Insight] = []
    seen: set[str] = set()
    for ins in insights:
        if not _is_grounded(ins, observed):
            continue
        key = _fold(ins.text)
        if key in seen:
            continue
        seen.add(key)
        grounded.append(ins)
        if len(grounded) >= _MAX_INSIGHTS:
            break
    return grounded


# --------------------------------------------------------------------- cache (disco)

def _cache_path(behavior_log):
    try:
        return behavior_log.path.with_name(behavior_log.path.stem + "_reflection.json")
    except Exception:
        return None


def _profile_signature(prof) -> str:
    """Firma de las observaciones: si no cambian, no re-reflexionamos."""
    parts = [a for a, _ in (prof.top_apps or [])] + [a for a, _ in (prof.top_artists or [])]
    parts += [f"{s}:{a}" for s, a in sorted((prof.apps_by_slot or {}).items())]
    return "|".join(parts)


def _save_cache(behavior_log, prof, insights: list[Insight]) -> None:
    p = _cache_path(behavior_log)
    if p is None:
        return
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({
            "ts": time.time(),
            "sig": _profile_signature(prof),
            "insights": [{"text": i.text, "evidence": i.evidence} for i in insights],
        }, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:
        logger.debug("save reflection cache failed: %s", exc)


def _load_cache(behavior_log) -> dict | None:
    p = _cache_path(behavior_log)
    if p is None or not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def cached_insights(behavior_log) -> list[Insight]:
    data = _load_cache(behavior_log)
    if not data:
        return []
    return [Insight(text=i.get("text", ""), evidence=i.get("evidence", ""))
            for i in data.get("insights", []) if i.get("text")]


def reflection_block(behavior_log) -> str:
    """Sub-bloque para el system prompt con los gustos finos inferidos (o '').
    Barato: sólo lee el caché. Gate OFF -> ''. Etiquetado INFERIDO (transparencia)."""
    if not _enabled():
        return ""
    insights = cached_insights(behavior_log)
    if not insights:
        return ""
    bullets = " ".join(f"{i.text}" for i in insights)
    return f" (inferido de tu uso: {bullets})"


def forget_reflection(behavior_log) -> None:
    """Borra el caché de insights inferidos (privacidad: borrable junto al perfil)."""
    p = _cache_path(behavior_log)
    try:
        if p is not None and p.exists():
            p.unlink()
    except Exception as exc:
        logger.debug("forget reflection failed: %s", exc)


# --------------------------------------------------------------------- background

def _cache_is_fresh(behavior_log) -> bool:
    """Chequeo BARATO de hot-path: ¿el caché existe y es más nuevo que el TTL?
    Sólo lee el JSON chico (NO escanea el behavior_log — eso es para el background)."""
    data = _load_cache(behavior_log)
    if not data:
        return False
    return (time.time() - float(data.get("ts", 0))) < _REFRESH_TTL_S


def refresh(behavior_log, llm_client) -> list[Insight]:
    """build_profile → reflect → guarda SIEMPRE (resetea el TTL aunque salga vacío,
    para no re-disparar el background cada turno). Pensado para el thread daemon."""
    prof = build_profile(behavior_log)
    insights = [] if prof.is_empty() else reflect(prof, llm_client)
    _save_cache(behavior_log, prof, insights)
    return insights


def maybe_refresh_async(behavior_log, llm_client) -> None:
    """Si el gate está ON y el caché venció (o falta), dispara UN refresh en un thread
    daemon. HOT-PATH BARATO: sólo mira la edad del caché (no escanea la DB); el trabajo
    pesado —build_profile + LLM— corre en background. Re-entrante-safe (un refresh a la
    vez). Diseño: no toca la latencia del turno (la reflexión NO es per-turn)."""
    global _REFRESHING
    if not _enabled() or behavior_log is None or llm_client is None:
        return
    if _cache_is_fresh(behavior_log):
        return
    with _REFRESH_LOCK:
        if _REFRESHING:
            return
        _REFRESHING = True

    def _run():
        global _REFRESHING
        try:
            # SQLite NO es cross-thread (una conexión sólo sirve en su thread). El
            # behavior_log compartido tiene su conexión en el main thread; acá
            # reconstruimos un BehaviorLog thread-local (mismo user+dir → abre su
            # propia conexión al MISMO DB en ESTE thread). El caché de salida es un
            # archivo JSON (cross-thread OK). Sin esto, build_profile rompía en el
            # thread y el refresh no guardaba nada (medido 2026-05-30).
            log = behavior_log
            try:
                if isinstance(behavior_log, BehaviorLog):
                    log = BehaviorLog(user=behavior_log.user, dir_path=behavior_log.dir_path)
            except Exception:
                log = behavior_log
            refresh(log, llm_client)
        except Exception as exc:
            logger.debug("background reflection failed: %s", exc)
        finally:
            with _REFRESH_LOCK:
                _REFRESHING = False

    t = threading.Thread(target=_run, name="taste-reflection", daemon=True)
    t.start()
