"""Verificación EN VIVO del auto-inject de skills con el LLM/agente REAL (R3.2).

Mandamiento #3.5: un cambio que toca el comportamiento del agente NO está listo
hasta correrlo contra el LLM REAL con el mensaje que el usuario escribiría, viendo
la cadena completa. Los tests mockeados NO bastan.

Usa run_content (= la UI, seguro, SIN SendInput). NO ejecuta gui.{type,click,...}
físico. Captura el trace event `skill_autoinjected` para saber qué skill se inyectó
realmente en el prompt del 4B, y el reply final.

Casos:
  TP   -> debe auto-inyectar la skill esperada (la receta entra al prompt).
  HARD -> NO debe inyectar ninguna skill (hard-negative suprimido).

Uso: python scripts/_live_verify_skills_autoinject.py   (server ya levantado en 8080)
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# (mensaje, skill_esperada | None).  None = NO debe inyectar skill.
CASES = [
    # TP: workflows multi-paso reales
    ("sacá una captura y decime qué ves", "screenshot-and-analyze"),
    ("investigá sobre este tema en internet y resumime", "research-and-summarize"),
    ("grabá lo que voy a dictar y pasalo a texto", "voice-record-transcribe"),
    ("hacé un backup antes de borrar esta carpeta", "backup-then-clean"),
    ("descargá y guardá el instalador de python", "download-file"),
    # HARD-NEGATIVES: comparten sustantivo, otra intención -> NO skill (la cubre un tool)
    ("subí el brillo de la pantalla", None),
    ("desmuteá mi micrófono", None),
    ("poné el video en pantalla completa", None),
    ("resumime todo lo anterior", None),
    # CHARLA: nunca skill
    ("hola, cómo andás", None),
]


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    from gemma4_agent.agent_core.agent import Gemma4Agent
    from gemma4_agent.infra.config import AgentConfig

    ag = Gemma4Agent(AgentConfig.from_env())

    # Hook al trace para capturar qué skill se auto-inyectó por turno.
    injected = {"name": None}
    _orig_event = ag.trace.event

    def _capture(turn_id, kind, **kw):
        if kind == "skill_autoinjected":
            injected["name"] = kw.get("skill")
        return _orig_event(turn_id, kind, **kw)

    ag.trace.event = _capture  # type: ignore[assignment]

    ag.run_content("hola")  # warm-up
    print("=== LIVE skill auto-inject (4B real, run_content) ===\n", flush=True)

    ok = 0
    for msg, expected in CASES:
        injected["name"] = None
        try:
            r = ag.run_content(msg)
            reply = (getattr(r, "content", None) or "")[:60].replace("\n", " ")
            err = getattr(r, "error", None)
        except Exception as exc:
            reply, err = "", f"EXC {type(exc).__name__}: {exc}"
        got = injected["name"]
        passed = (got == expected)
        ok += passed
        tag = "PASS" if passed else "FAIL"
        exp_s = expected or "(ninguna)"
        got_s = got or "(ninguna)"
        print(f"  [{tag}] inj={got_s:24s} esp={exp_s:24s}  {msg!r}")
        if err:
            print(f"         err={err}")
        if not passed:
            print(f"         reply={reply!r}")

    print(f"\n  RESULTADO: {ok}/{len(CASES)} PASS")
    return 0 if ok == len(CASES) else 2


if __name__ == "__main__":
    raise SystemExit(main())
