"""Extrae los TURNOS reales de una sesión de full.log (~/.gemma4/logs/<id>/).

Objetivo: reconstruir cada turno = (mensaje del usuario, cadena de tools
ejecutadas, reply) para auditar si el agente accionó MAL respecto a lo que el
usuario pidió. NO interpreta correctitud (eso lo hace el LLM/agentes del
workflow); solo estructura los datos crudos para que el juicio sea sobre
EVIDENCIA real, no especulación.

Formato de full.log: JSONL, un evento por línea. Tipos observados:
  _recorder (session_open/close), voice_wake, activity (src=YOU|BAXY...),
  tokens, state, ...

Uso:
  python scripts/_diag/_diag_audit_session_turns.py [session_dir]
Default: ~/.gemma4/logs/_pre_session
Salida: imprime los turnos legibles + vuelca JSON a
        scripts/_diag/_out_session_turns.json para el workflow.
"""
import json
import sys
from collections import Counter
from pathlib import Path

DEFAULT = Path.home() / ".gemma4" / "logs" / "_pre_session"


def load_events(log_path: Path) -> list[dict]:
    events = []
    with open(log_path, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                events.append(json.loads(ln))
            except Exception:
                pass
    return events


def main() -> None:
    session_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    log_path = session_dir / "full.log"
    if not log_path.exists():
        print(f"NO existe {log_path}")
        sys.exit(1)

    events = load_events(log_path)
    print(f"Total eventos: {len(events)}  ({log_path})")
    types = Counter(e.get("type", "?") for e in events)
    print("Tipos:")
    for k, v in types.most_common():
        print(f"  {v:5} {k}")

    # Inspeccionar la FORMA de cada tipo no-boot para entender los campos.
    print("\n=== EJEMPLO de cada tipo de evento (1 muestra c/u) ===")
    seen = set()
    for e in events:
        t = e.get("type", "?")
        if t in seen:
            continue
        seen.add(t)
        sample = {k: (str(v)[:120]) for k, v in e.items()}
        print(f"\n[{t}]")
        for k, v in sample.items():
            print(f"   {k}: {v}")

    # --- Reconstruir el HILO conversacional cronológico ---
    # Tomamos activity (entry.src/msg), voice_wake y tokens, en orden de ts,
    # filtrando el ruido de BOOT. Esto es la transcripción real del usuario y
    # las acciones/replies del agente, que es lo que hay que auditar.
    print("\n\n=== HILO CONVERSACIONAL (sin BOOT) ===")
    thread = []
    for e in events:
        t = e.get("type", "?")
        ts = e.get("_ts") or e.get("ts", "")
        if t == "voice_wake":
            thread.append({"kind": "WAKE", "ts": ts, "text": "(wake word fired)"})
        elif t == "activity":
            entry = e.get("entry", {}) or {}
            src = entry.get("src", "?")
            msg = entry.get("msg", "")
            if src == "BOOT":
                continue
            thread.append({"kind": src, "ts": entry.get("ts", ts), "text": msg})
        elif t == "voice_no_speech":
            thread.append({"kind": "NO_SPEECH", "ts": ts, "text": "(no speech detected)"})

    for item in thread:
        print(f"  [{item['ts']}] {item['kind']:9} | {item['text']}")

    out = Path(__file__).resolve().parent / "_out_session_turns.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(thread, f, ensure_ascii=False, indent=2)
    print(f"\n-> Hilo volcado a {out} ({len(thread)} items)")


if __name__ == "__main__":
    main()
