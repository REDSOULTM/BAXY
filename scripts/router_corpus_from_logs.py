"""Construye un corpus de eval del router desde los LOGS REALES del usuario.

Pedido del usuario (2026-05-29): "toma todos los logs del usuario, los mensajes
que ha mandado desde el inicio de los logs, debes lograr 100% de éxito en el router".

Los traces.jsonl tienen, por turn_id: el mensaje real del usuario (request_start
content.preview) + las tools que el agente REALMENTE ejecutó (tool_call). Eso es
ground truth REAL — en la forma de hablar del usuario (typos, "porfavor", "pls",
deícticos), no sintético. Mucho más valioso que el corpus generado.

Salida: data/router_corpus_real_logs.jsonl con {q, expected, source, turn_id}.
- expected = tools ejecutadas dedupeadas (lo que el usuario realmente consiguió).
- Filtramos: turnos sin tool (charla), confirmaciones cortas ("si"/"ok") cuya tool
  vino del turno previo (inherit, no del router de esa query), y duplicados exactos.

Uso: python scripts/router_corpus_from_logs.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRACES = ROOT / "gemma4_agent" / "data" / "traces.jsonl"
OUT = ROOT / "gemma4_agent" / "data" / "router_corpus_real_logs.jsonl"

# Tools "no-dominio" que no cuentan como intención de la query (siempre alcanzables).
_NON_DOMAIN = {"session", "safety", "state", "verify"}
# Confirmaciones cortas: su tool vino del turno previo (inherit), no del router de
# ESTA query — no son ground truth del router para esta query.
_CONFIRM_ONLY = {"si", "sí", "ok", "okay", "dale", "yes", "no", "bueno", "vale",
                 "claro", "hazlo", "hacelo", "y", "ya"}

# CURADO multi-label (S3, 2026-05-29): la tool que el agente EJECUTÓ no es la única
# correcta — varias tools del MISMO dominio funcional son igual de válidas para la
# misma intención. Ej: "reanuda el video" puede ser media O audio; "abre Spotify"
# puede ser app O media; "buscá en internet" puede ser web O browser. El corpus
# crudo etiqueta solo lo que corrió esa vez (ruidoso); acá expandimos `expected`
# con las tools de dominio-equivalente -> el recall medido refleja la VERDAD
# (un router que ofrece una tool del dominio correcto NO es un miss). Esto NO es
# circular: la equivalencia es estructural (qué tools comparten capacidad), no
# depende de lo que el router predice.
_DOMAIN_EQUIV: tuple[frozenset[str], ...] = (
    frozenset({"audio", "media", "audio_device"}),         # reproducir / volumen
    frozenset({"app", "media", "window", "steam"}),         # abrir cosas
    frozenset({"download", "filesystem"}),                  # archivos
    frozenset({"web", "browser", "browser_real", "knowledge"}),  # info / navegar
    frozenset({"gui", "uia", "window", "vision", "computer_use", "desktop_layout"}),  # pantalla
    frozenset({"system", "audio", "audio_device", "device_settings"}),  # ajustes PC
)


def _expand_equivalent(tools: list[str]) -> list[str]:
    """Multi-label: por cada tool, agrega las del mismo dominio funcional."""
    out = list(tools)
    for t in tools:
        for fam in _DOMAIN_EQUIV:
            if t in fam:
                for sib in fam:
                    if sib not in out:
                        out.append(sib)
    return out


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if not TRACES.exists():
        print(f"traces no encontrado: {TRACES}")
        return 1

    turns: dict[str, dict] = defaultdict(lambda: {"q": None, "tools": []})
    with TRACES.open(encoding="utf-8") as f:
        for line in f:
            try:
                d = json.loads(line)
            except Exception:
                continue
            tid = d.get("turn_id")
            if not tid:
                continue
            kind = d.get("kind")
            if kind == "request_start":
                c = d.get("content") or {}
                turns[tid]["q"] = c.get("preview") or c.get("text")
            elif kind == "tool_call":
                t = d.get("name") or d.get("tool")
                if t and t not in _NON_DOMAIN:
                    turns[tid]["tools"].append(t)

    rows: list[dict] = []
    seen_q: set[str] = set()
    for tid, t in turns.items():
        q = (t["q"] or "").strip()
        if not q:
            continue
        # tools ejecutadas, dedupeadas, en orden de primera aparición.
        tools: list[str] = []
        for x in t["tools"]:
            if x not in tools:
                tools.append(x)
        if not tools:
            continue  # turno sin tool de dominio (charla / no-tool)
        # confirmación corta: la tool vino del inherit del turno previo, no del
        # router de esta query -> no es ground truth del router.
        if q.casefold() in _CONFIRM_ONLY:
            continue
        # dedup por query exacta (normalizada) — quedarnos con la 1ª.
        key = q.casefold()
        if key in seen_q:
            continue
        seen_q.add(key)
        # expected = estricto (la tool exacta ejecutada — el norte de precisión).
        # expected_equiv = + las del mismo dominio (para descartar falsos misses
        # donde el router ofreció una tool igual de válida). El eval mide el
        # estricto por default; --equiv usa el permisivo para separar miss-real.
        rows.append({"q": q, "expected": tools,
                     "expected_equiv": _expand_equivalent(tools),
                     "source": "real_logs", "turn_id": tid})

    OUT.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8")
    print(f"Corpus de logs reales: {len(rows)} pares únicos (query -> tools)")
    print(f"Guardado en: {OUT}")
    # Distribución de tools esperadas (las más usadas por el usuario real).
    import collections as _c
    tool_freq = _c.Counter(tool for r in rows for tool in r["expected"])
    print("\nTools más usadas (logs reales):")
    for tool, n in tool_freq.most_common(15):
        print(f"  {n:4d}  {tool}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
