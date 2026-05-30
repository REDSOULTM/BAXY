"""Verificación EN VIVO del selector de microagents con el agente REAL (R3.3).

Mandamiento #3.5: corre contra el agente real con run_content (= la UI, seguro,
sin SendInput). Captura el trace event `microagent_matched` para ver qué
microagents se seleccionaron de verdad en la cadena completa.

Casos:
  TP   -> debe matchear el microagent esperado.
  HARD -> NO debe matchear ninguno (el bug "RAG en Dragon" / "que es" substring).

Uso: python scripts/_live_verify_microagents.py   (server ya en 8080)
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CASES = [
    # TP
    ("una app no responde, ayudame a arreglarla", "troubleshoot"),
    ("cómo ejecuto un comando en powershell", "windows-commands"),
    ("qué cosas podés hacer por mí", "tools-cheat-sheet"),
    ("qué es mmproj", "glossary"),
    # HARD-NEG (el bug de substring) -> ninguno
    ("House of Dragon", None),
    ("dile a Sebastián que es muy gordo", None),
    ("mutea el sonido", None),
    ("que es la fotosintesis", None),
]


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    from gemma4_agent.agent_core.agent import Gemma4Agent
    from gemma4_agent.infra.config import AgentConfig

    ag = Gemma4Agent(AgentConfig.from_env())

    matched = {"names": []}
    _orig = ag.trace.event

    def _cap(turn_id, kind, **kw):
        if kind == "microagent_matched":
            matched["names"] = kw.get("names") or []
        return _orig(turn_id, kind, **kw)

    ag.trace.event = _cap  # type: ignore[assignment]

    ag.run_content("hola")  # warm
    print("=== LIVE microagents (4B real, run_content) ===\n", flush=True)

    ok = 0
    for msg, expected in CASES:
        matched["names"] = []
        try:
            ag.run_content(msg)
        except Exception as exc:
            print(f"  [FAIL] EXC {type(exc).__name__}: {exc}  {msg!r}")
            continue
        got = matched["names"]
        if expected is None:
            passed = (len(got) == 0)
        else:
            passed = (expected in got)
        ok += passed
        tag = "PASS" if passed else "FAIL"
        exp_s = expected or "(ninguno)"
        got_s = ",".join(got) or "(ninguno)"
        print(f"  [{tag}] got={got_s:22s} esp={exp_s:18s}  {msg!r}")

    print(f"\n  RESULTADO: {ok}/{len(CASES)} PASS")
    return 0 if ok == len(CASES) else 2


if __name__ == "__main__":
    raise SystemExit(main())
