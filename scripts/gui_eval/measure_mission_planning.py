"""GATE 0a — ¿El 4B PLANIFICA bien misiones LARGAS/compuestas? (planificación pura)

SEGURO: solo inferencia contra el server. CERO SendInput, no toca GUI.
Mide el planner de PRODUCCIÓN (computer_use.plan_for) — con enable_thinking=False,
greedy, el modelo de texto del perfil — NO un HTTP a mano (que daba content vacío
por thinking, un artefacto de medición). Esto mide lo que el agente realmente usa.

Requisito: llama-server vram4 vivo en :8080.
GATE: parseable >=90%, sub-pasos núcleo presentes en orden >=70%.
Uso:  python scripts/gui_eval/measure_mission_planning.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from gemma4_agent.infra.config import AgentConfig
from gemma4_agent.infra.llm_client import LLMClient
from gemma4_agent.computer_use_pkg.computer_use import plan_for, PRIMITIVES


class _StubAgent:
    """Agente mínimo: solo necesita .client para plan_for."""
    def __init__(self):
        self.client = LLMClient(AgentConfig.from_env())


CASES = [
    ("entra a youtube", ["open_url"]),
    ("abrí la calculadora y escribí 2+2", ["focus_app", "type"]),
    ("mutea mi microfono en discord", ["focus_app", "discord_control"]),
    ("mandale hola a juan en discord", ["focus_app", "open_chat", "type", "send"]),
    ("entra al canal de voz musica en discord", ["focus_app", "open_voice"]),
    ("anda a instant gaming y busca resident evil requiem",
     ["open_url", "type", "send"]),
    ("activa las notificaciones", ["toggle"]),
    ("rellena el campo email con ana@example.com", ["fill_field"]),
    ("anda a instant gaming, busca resident evil requiem y abri el primer resultado",
     ["open_url", "type", "send", "click"]),
    ("abri el navegador, entra a gmail y escribi un correo nuevo",
     ["open_url", "click"]),
    ("entra a discord, anda al canal general y escribi buenas a todos",
     ["focus_app", "open_chat", "type", "send"]),
    ("busca un video de gatos en youtube y reproduci el primero",
     ["open_url", "type", "send", "click"]),
    ("abri la configuracion de windows y activa el modo oscuro",
     ["focus_app", "click", "toggle"]),
    ("anda a amazon, busca un teclado y agregalo al carrito",
     ["open_url", "type", "send", "click"]),
    ("abri spotify y reproduci mi lista de favoritos",
     ["focus_app", "type", "send"]),
]


def is_subseq(small, big):
    it = iter(big)
    return all(x in it for x in small)


def main() -> int:
    import urllib.request
    try:
        urllib.request.urlopen("http://127.0.0.1:8080/v1/models", timeout=5)
    except Exception as e:
        print(f"server DOWN en :8080 -> {type(e).__name__}.", flush=True)
        return 2

    agent = _StubAgent()
    print(f"=== GATE 0a — planificación de misiones (via plan_for) x{len(CASES)} ===",
          flush=True)
    results = []
    for goal, exp in CASES:
        try:
            plan = plan_for(agent, goal)  # producción: thinking off, greedy
        except Exception as e:
            plan = None
            err = f"{type(e).__name__}: {e}"
        else:
            err = ""
        ops = [s.get("op") for s in plan] if plan else None
        parseable = plan is not None
        valid = parseable and all(o in PRIMITIVES for o in ops)
        correct = bool(valid and is_subseq(exp, ops))
        results.append({"goal": goal, "parseable": parseable, "ops": ops,
                        "exp": exp, "correct": correct, "err": err})
        tag = "OK " if correct else ("PARSE-FAIL" if not parseable else "WRONG")
        print(f"  {tag:10} | {goal[:46]!r}\n        ops={ops} exp={exp}"
              + (f" err={err}" if err else ""), flush=True)

    npars = sum(1 for r in results if r["parseable"])
    ncorr = sum(1 for r in results if r["correct"])
    out = ROOT / "scripts" / "gui_eval" / "_mission_planning_results.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n>> parseable {npars}/{len(CASES)} | correcto {ncorr}/{len(CASES)} "
          f"= {ncorr/len(CASES)*100:.0f}%", flush=True)
    print(f">> GATE: parseable>=90% ({npars >= 0.9*len(CASES)}), "
          f"correcto>=70% ({ncorr >= 0.7*len(CASES)})", flush=True)
    print("WROTE", out, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
