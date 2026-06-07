"""Extrae TODOS los turnos de traces.jsonl agrupados por turn_id, con el detalle
RICO (transcripción, short-circuits, llm_response, tool_calls, tool_results,
reply final, latencia). Mucho más profundo que full.log.

Objetivo: auditar cada turno REAL del usuario (sesión de voz) — reconstruir la
cadena completa de decisión del agente para detectar fallos sutiles que la vista
resumida de full.log oculta (reintentos, thinking, short-circuits, mismatches).

Separa los turnos REALES del usuario de los traces generados por mis tests
(heurística: los tests corren en ráfaga sub-segundo sin transcripción de voz;
los reales tienen un kind de entrada de usuario + gaps de segundos).

Uso: python scripts/_diag/_diag_traces_full_audit.py
Salida: imprime catálogo de kinds + cada turno con su cadena; vuelca JSON.
"""
import json
import sys
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TRACES = REPO / "gemma4_agent" / "data" / "traces.jsonl"


def load(path: Path) -> list[dict]:
    out = []
    for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except Exception:
            pass
    return out


def main() -> None:
    events = load(TRACES)
    print(f"Total eventos: {len(events)} ({TRACES})")

    kinds = Counter(e.get("kind", "?") for e in events)
    print("\n=== TODOS los kinds (catálogo) ===")
    for k, v in kinds.most_common():
        print(f"  {v:5} {k}")

    # Agrupar por turn_id preservando orden de aparición.
    turns: "OrderedDict[str, list[dict]]" = OrderedDict()
    for e in events:
        tid = e.get("turn_id", "?")
        turns.setdefault(tid, []).append(e)
    print(f"\n=== {len(turns)} turn_ids totales ===")

    # Identificar el kind que lleva el TEXTO del usuario.
    text_kinds = defaultdict(int)
    for e in events:
        for key in ("user_text", "text", "transcript", "content", "query", "message"):
            v = e.get(key)
            if isinstance(v, str) and v.strip() and len(v) < 200:
                text_kinds[e.get("kind", "?")] += 1
                break
    print("\n=== kinds que portan texto (candidatos a 'entrada del usuario') ===")
    for k, v in sorted(text_kinds.items(), key=lambda x: -x[1]):
        print(f"  {v:5} {k}")

    # Volcar el turn_id -> lista de (kind, resumen) para inspección humana.
    dump = []
    for tid, evs in turns.items():
        ts0 = evs[0].get("ts", "")
        row = {"turn_id": tid, "ts": ts0, "events": []}
        for e in evs:
            summ = {k: v for k, v in e.items() if k not in ("turn_id",)}
            # recortar valores largos
            summ = {k: (v if not isinstance(v, str) else v[:200]) for k, v in summ.items()}
            row["events"].append(summ)
        dump.append(row)

    out = Path(__file__).resolve().parent / "_out_traces_turns.json"
    out.write_text(json.dumps(dump, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n-> {len(dump)} turnos volcados a {out}")

    # Imprimir un ÍNDICE: turn_id, ts, kinds presentes, primer texto hallado.
    print("\n=== ÍNDICE de turnos (ts | kinds | texto) ===")
    for tid, evs in turns.items():
        ks = "/".join(dict.fromkeys(e.get("kind", "?") for e in evs))
        txt = ""
        for e in evs:
            for key in ("user_text", "text", "transcript", "content", "query"):
                v = e.get(key)
                if isinstance(v, str) and v.strip():
                    txt = v[:60]
                    break
            if txt:
                break
        ts = evs[0].get("ts", "")[:19]
        print(f"  {ts} | {tid[-8:]} | {txt!r:35} | {ks[:90]}")


if __name__ == "__main__":
    main()
