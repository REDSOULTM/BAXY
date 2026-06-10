"""Perfil de gustos del usuario — la capa de REFLEXIÓN del Jarvis (R-Jarvis, 2026-05-30).

Convierte las observaciones crudas del ambient_observer (qué app usás, qué música
escuchás, en qué franja) en INSIGHTS de quién sos, y los inyecta al prompt de Gemma4
para que el modelo te conozca y dé una mejor experiencia.

Diseño respaldado por investigación verificada:
  - Generative Agents (arXiv:2304.03442): observación → reflexión → insight. Acá la
    reflexión es DETERMINISTA (agregación por conteo/tiempo) en vez de LLM, porque:
    (a) es barata y confiable (el 4B es ruidoso para esto), (b) las reglas del proyecto prohíbe
    depender del LLM para clasificar gustos sin necesidad. La síntesis del PÁRRAFO
    final sí puede pasar por el LLM (opt-in), pero los insights base son medidos.
  - Guided Profile Generation (arXiv:2409.13093, +37%): inyectar un PÁRRAFO en
    lenguaje natural, no el log crudo.
  - On-device (Google) + privacidad: local, inspectable (profile_text), borrable
    (forget), pausable (gate). Metadata, no contenido.

NO usa LLM para decidir gustos (determinista). NO inyecta el log crudo. NO guarda
títulos de ventana ni contenido. El perfil es un párrafo compacto (<~250 tokens).

Gate: GEMMA4_TASTE_PROFILE=0 desactiva la inyección del perfil.
"""
from __future__ import annotations

import logging
import os
import threading
import time as _time
from collections import Counter, defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Caché del bloque inyectado al prompt. build_profile_block() corre en CADA turno
# dentro de _system_message; sin caché re-lee TODO el behavior_log (medido: 15.7k
# eventos → ~18ms/turno, rompía el budget de 5ms de _system_message y el de
# latencia tier-Alexa). El perfil cambia en escala de minutos, no de segundos, así
# que un TTL corto es seguro. forget() invalida el caché para que un borrado se
# refleje YA (privacidad). inspect_text() NO usa el caché (siempre fresco). El
# caché se keyea por id(behavior_log) para no cruzar perfiles entre agentes (tests).
_BLOCK_CACHE: dict = {"log_id": None, "ts": 0.0, "text": ""}
_BLOCK_LOCK = threading.Lock()


def _block_ttl_s() -> float:
    try:
        return float(os.environ.get("GEMMA4_TASTE_PROFILE_TTL_S", "300"))
    except (TypeError, ValueError):
        return 300.0


def invalidate_block_cache() -> None:
    """Fuerza el rebuild del bloque en la próxima llamada (tras forget/cambios)."""
    with _BLOCK_LOCK:
        _BLOCK_CACHE.update(log_id=None, ts=0.0, text="")

# Cuántos días de comportamiento mirar y umbrales mínimos para afirmar un gusto
# (anti-ruido: no inventamos un perfil con 2 datos). Calibrables por env.
_WINDOW_DAYS = 30
_MIN_APP_DWELL_S = 600.0     # 10 min totales en una app para que cuente
_MIN_MEDIA_PLAYS = 3         # 3 reproducciones de un artista para "te gusta"
_MIN_MUSIC_SLOT_SESSIONS = 3  # 3 sesiones en una franja para llamarla "hábito"
_TOP_APPS = 4
_TOP_ARTISTS = 4


def _profile_enabled() -> bool:
    raw = (os.environ.get("GEMMA4_TASTE_PROFILE") or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


@dataclass
class TasteProfile:
    """Insights agregados del comportamiento. Todo derivado, ninguno inventado."""
    top_apps: list[tuple[str, float]] = field(default_factory=list)        # (app, horas)
    apps_by_slot: dict[str, str] = field(default_factory=dict)             # slot -> app dominante
    top_artists: list[tuple[str, int]] = field(default_factory=list)       # (artista, plays)
    music_slots: list[str] = field(default_factory=list)                   # franjas donde escucha música
    total_observations: int = 0

    def is_empty(self) -> bool:
        return not (self.top_apps or self.top_artists)


def _artist_of(media_key: str) -> str:
    """'Soda Stereo — De Música Ligera' -> 'Soda Stereo'. Sin artista -> ''."""
    return media_key.split(" — ", 1)[0].strip() if " — " in media_key else ""


def build_profile(behavior_log, *, window_days: int = _WINDOW_DAYS) -> TasteProfile:
    """Lee el behavior_log y agrega los insights de gustos. Determinista, barato."""
    import time as _t
    since_ms = int((_t.time() - window_days * 86400) * 1000)
    try:
        events = behavior_log.events(since_ms=since_ms)
    except Exception:
        return TasteProfile()

    app_dwell: dict[str, float] = defaultdict(float)
    slot_app_dwell: dict[str, Counter] = defaultdict(Counter)
    artist_plays: Counter = Counter()
    music_slot_count: Counter = Counter()
    n = 0
    # Dedup de SESIÓN para media (F1): el ambient_observer poll-ea cada ~5s y, ante
    # micro-variaciones del título reportado por SMTC o gaps de playback, graba la
    # MISMA canción decenas/cientos de veces (medido: "Canserbero — Maquiavélico" 267
    # filas = 1 sola canción sonando un rato, NO 267 escuchas). `_last_media` en el
    # observer solo dedupea contra la fila INMEDIATAMENTE anterior y la PK incluye el
    # ts en ms, así que el INSERT OR IGNORE nunca colapsa. Contar filas hacía que
    # top_artists midiera TIEMPO-EN-PANTALLA, no preferencia. Acá colapsamos por
    # SESIÓN: filas consecutivas con la misma key (dentro de un gap razonable) =
    # una escucha. Una repetición real (misma canción tras otra distinta, o tras un
    # gap largo) sí cuenta como nueva sesión. Los eventos vienen ordenados por ts ASC.
    _last_media_key: str | None = None
    _last_media_ts: int = 0
    # Una pausa > este gap reabre la sesión (volviste a poner la misma canción).
    _SESSION_GAP_MS = int(float(os.environ.get(
        "GEMMA4_MEDIA_SESSION_GAP_S", "1800")) * 1000)  # 30 min default

    for e in events:
        ctx = e.get("context") or {}
        # Solo eventos AMBIENTE (lo que hace el user), no lo que abrió el agente.
        if ctx.get("source") != "ambient":
            continue
        kind = e.get("kind")
        key = e.get("key") or ""
        slot = ctx.get("slot") or ""
        if kind == "app_focus":
            n += 1
            d = float(ctx.get("dwell_s") or 0.0)
            app_dwell[key] += d
            if slot:
                slot_app_dwell[slot][key] += d
        elif kind == "media_play":
            ts = int(e.get("ts") or 0)
            # ¿Es la MISMA canción que la sesión en curso (poll repetido)? -> ignorar.
            same_session = (
                key == _last_media_key
                and 0 <= (ts - _last_media_ts) <= _SESSION_GAP_MS)
            _last_media_key = key
            _last_media_ts = ts
            if same_session:
                continue
            # F5: SMTC reporta CUALQUIER reproductor (Spotify, navegador, VLC,
            # PotPlayer...). Un título sin separador "artista — título" es casi
            # siempre un VIDEO/película (medido: "the.green.inferno.2015...mp4"),
            # no música. Solo lo que tiene artista cuenta como MÚSICA — así
            # "escucha música a la madrugada" no afirma que mirabas una peli.
            artist = _artist_of(key)
            if not artist:
                continue
            # Nueva sesión de escucha (canción distinta o re-play tras gap): cuenta 1.
            n += 1
            artist_plays[artist] += 1
            if slot:
                music_slot_count[slot] += 1

    prof = TasteProfile(total_observations=n)
    prof.top_apps = [(a, round(s / 3600.0, 1))
                     for a, s in app_dwell.most_common(_TOP_APPS)
                     if s >= _MIN_APP_DWELL_S] if hasattr(app_dwell, "most_common") else \
        [(a, round(s / 3600.0, 1))
         for a, s in Counter(app_dwell).most_common(_TOP_APPS) if s >= _MIN_APP_DWELL_S]
    # apps_by_slot: el dominante de cada franja DEBE superar el umbral anti-ruido
    # (auditoría 2026-06-07: una app abierta 1 vez por segundos declaraba un "ritmo
    # diario" falso que el LLM tomaba como verdad -> "a la tarde solés estar en X").
    prof.apps_by_slot = {slot: c.most_common(1)[0][0]
                         for slot, c in slot_app_dwell.items()
                         if c and c.most_common(1)[0][1] >= _MIN_APP_DWELL_S}
    prof.top_artists = [(a, p) for a, p in artist_plays.most_common(_TOP_ARTISTS)
                        if p >= _MIN_MEDIA_PLAYS]
    # music_slots: una franja es un HÁBITO solo con varias sesiones, no con una
    # sola (auditoría: 1 sesión declaraba "suele escuchar música a la <franja>").
    prof.music_slots = [s for s, c in music_slot_count.most_common(2)
                        if c >= _MIN_MUSIC_SLOT_SESSIONS]
    return prof


_EXE_SUFFIXES = (".exe", ".app", ".bin", ".com")


def _clean_app(name: str) -> str:
    """code.exe -> Code, spotify.exe -> Spotify, whatsapp.root.exe -> Whatsapp.

    Estructural (sin lista de apps por idioma): saca el sufijo de ejecutable y
    luego, si el resto AÚN tiene puntos (p.ej. 'whatsapp.root'), se queda con el
    PRIMER segmento (el nombre primario), no con el último. El bug previo usaba
    rsplit('.',1) que dejaba 'whatsapp.root' en el prompt.
    """
    base = (name or "").strip()
    low = base.lower()
    for suf in _EXE_SUFFIXES:
        if low.endswith(suf):
            base = base[: -len(suf)]
            break
    if "." in base:
        base = base.split(".", 1)[0]  # nombre primario, no el qualifier
    return base[:1].upper() + base[1:] if base else (name or "")


def _title_artist(name: str) -> str:
    """'soda stereo' -> 'Soda Stereo' (capitaliza cada palabra del artista)."""
    return " ".join(w[:1].upper() + w[1:] if w else w for w in name.split())


def profile_text(prof: TasteProfile) -> str:
    """Renderiza el perfil como PÁRRAFO en lenguaje natural (GPG arXiv:2409.13093).
    Compacto (<~250 tokens). Vacío si no hay señal suficiente."""
    if prof.is_empty():
        return ""
    parts: list[str] = []
    if prof.top_apps:
        apps = ", ".join(f"{_clean_app(a)}" for a, _ in prof.top_apps)
        parts.append(f"Las apps que más usa: {apps}.")
    if prof.apps_by_slot:
        # Agrupar franjas con la MISMA app dominante: "a la mañana y a la tarde
        # en Code; a la noche en Opera" (en vez de repetir Code dos veces).
        by_app: dict[str, list[str]] = defaultdict(list)
        for slot, app in prof.apps_by_slot.items():
            by_app[_clean_app(app)].append(slot)
        # F4: el "ritmo" solo informa si DISTINGUE franjas. Si una sola app domina
        # TODAS (Code en mañana/tarde/noche/madrugada), la frase "a la tarde y a la
        # noche y a la madrugada y a la mañana suele estar en Code" no aporta nada
        # (ya lo dice "las apps que más usa") y es ruido que daña a modelos chicos
        # (arXiv:2502.01609). Se emite solo si hay >1 app dominante distinta.
        if len(by_app) > 1:
            rhythm = "; ".join(
                f"a la {' y a la '.join(slots)} suele estar en {app}"
                for app, slots in by_app.items())
            parts.append(f"Ritmo diario: {rhythm}.")
    if prof.top_artists:
        arts = ", ".join(_title_artist(a) for a, _ in prof.top_artists)
        parts.append(f"Música que escucha: {arts}.")
    if prof.music_slots:
        parts.append(f"Suele escuchar música a la {', a la '.join(prof.music_slots)}.")
    return " ".join(parts)


def _render_block(behavior_log) -> str:
    """Construye el bloque desde cero (sin caché). Vacío si no hay señal."""
    try:
        prof = build_profile(behavior_log)
    except Exception:
        return ""
    txt = profile_text(prof)
    if not txt:
        return ""
    return (
        "\n\n# SOBRE EL USUARIO (contexto de fondo — NO lo menciones salvo que venga al caso)\n"
        f"{txt}\n"
        "Usá esto para personalizar tus respuestas y sugerencias, sin recitarlo.")


def build_profile_block(behavior_log) -> str:
    """Bloque listo para el system_prompt de Gemma4 (o '' si no aplica/sin datos).
    Etiquetado como BACKGROUND para que el 4B no lo recite (anti-parroting).
    CACHEADO con TTL: corre por turno, así que NO re-lee el behavior_log entero cada
    vez (ver _BLOCK_CACHE)."""
    if not _profile_enabled():
        return ""
    now = _time.time()
    log_id = id(behavior_log)
    with _BLOCK_LOCK:
        if (_BLOCK_CACHE["log_id"] == log_id
                and (now - _BLOCK_CACHE["ts"]) < _block_ttl_s()):
            return _BLOCK_CACHE["text"]
    # Rebuild FUERA del lock (build_profile hace I/O a SQLite) — peor caso, dos
    # turnos casi-simultáneos rebuildan; inocuo y raro (el runtime de voz es serial).
    block = _render_block(behavior_log)
    with _BLOCK_LOCK:
        _BLOCK_CACHE.update(log_id=log_id, ts=now, text=block)
    return block


# --------------------------------------------------------------------- privacidad

def inspect_text(behavior_log) -> str:
    """Lo que el sistema CREE saber del usuario, legible. Para un comando
    'qué sabés de mí'. Privacidad table-stakes: inspectable."""
    prof = build_profile(behavior_log)
    if prof.is_empty():
        return ("Todavía no aprendí lo suficiente sobre vos (necesito observar "
                "tu uso unos días). No tengo un perfil armado aún.")
    txt = profile_text(prof)
    return (f"Esto es lo que aprendí observando tu uso ({prof.total_observations} "
            f"observaciones, todo local):\n{txt}")


def forget(behavior_log) -> int:
    """Borra TODO el comportamiento observado del usuario (privacidad: ley).
    Devuelve cuántos eventos borró. NO toca el chat ni la experiencia.

    CRÍTICO (auditoría 2026-06-07): antes borraba SOLO app_focus/media_play y
    dejaba app_open/app_close/boot — el pattern_miner seguía minando rutinas del
    usuario ("cuando abrís X, abrís Y") tras un "olvidate de todo" confirmado.
    Eso viola la privacidad (es ley) y la honestidad (afirmaba olvidar sin
    hacerlo). Ahora borra TODO el behavior del usuario; el meta (schema) queda."""
    try:
        conn = behavior_log._open()
        if conn is None:
            return 0
        cur = conn.execute("SELECT COUNT(*) FROM behavior_events")
        n = cur.fetchone()[0]
        conn.execute("DELETE FROM behavior_events")
        conn.commit()
        invalidate_block_cache()  # el borrado debe reflejarse YA en el prompt (privacidad)
        return int(n)
    except Exception as exc:
        logger.debug("forget failed: %s", exc)
        return 0
