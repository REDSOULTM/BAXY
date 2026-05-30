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
        rows.append({"q": q, "expected": tools, "source": "real_logs",
                     "turn_id": tid})

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
