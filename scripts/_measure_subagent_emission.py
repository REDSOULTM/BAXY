"""¿El 4B emite `subagent` cuando un pedido lo justifica? + latencia (medición).

Mandamiento #3.5: medir contra el 4B REAL. run_content (seguro, sin SendInput).
Mide si el modelo invoca la tool `subagent` cuando se le da un pedido que la
justifica (tarea acotada delegable), y cuánto tarda un subagente real.

Uso: python scripts/_measure_subagent_emission.py   (server en 8080)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Pedidos que JUSTIFICAN delegar a un subagente (tarea acotada, aislable).
CASES = [
    "buscá en mi biblioteca de Steam todos los juegos tipo metroidvania",
    "investigá en internet las 3 mejores laptops del 2026 y resumime",
    "revisá todos los archivos de mi carpeta Descargas y decime cuáles son grandes",
    "mientras tanto andá averiguando el clima de las próximas 3 ciudades que te diga",
]


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    from gemma4_agent.agent_core.agent import Gemma4Agent
    from gemma4_agent.infra.config import AgentConfig

    ag = Gemma4Agent(AgentConfig.from_env())

    emitted = {"tools": []}
    _orig = ag.trace.event

    def _cap(turn_id, kind, **kw):
        if kind == "tool_call":
            emitted["tools"].append(kw.get("name") or kw.get("tool"))
        return _orig(turn_id, kind, **kw)

    ag.trace.event = _cap  # type: ignore[assignment]

    ag.run_content("hola")  # warm
    print("=== ¿el 4B emite `subagent`? (4B real) ===\n", flush=True)

    emit_count = 0
    for msg in CASES:
        emitted["tools"] = []
        t = time.perf_counter()
        try:
            r = ag.run_content(msg)
            dt = time.perf_counter() - t
            reply = (getattr(r, "content", None) or "")[:50].replace("\n", " ")
        except Exception as exc:
            print(f"  EXC {type(exc).__name__}: {exc}  {msg!r}")
            continue
        tools = emitted["tools"]
        used_sub = "subagent" in tools
        emit_count += used_sub
        tag = "SUBAGENT" if used_sub else "no-sub"
        print(f"  [{tag:9s}] {dt:5.1f}s tools={tools}  {msg[:40]!r}")
        print(f"             reply={reply!r}")

    print(f"\n  El 4B emitió subagent en {emit_count}/{len(CASES)} pedidos que lo justifican.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
