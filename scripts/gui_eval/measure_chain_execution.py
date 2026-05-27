"""GATE — robustez del PlanExecutor en CADENAS (no del planner). Le damos un PLAN
FIJO y correcto y medimos cuántos PASOS completa/verifica. Aísla la EJECUCIÓN
(reintento/verificación), que es el techo medido — no la planificación.

SEGURO: cadenas WEB (open_url -> browser_real CDP / web_open_url). NO SendInput
físico. Reporta, por paso: ok, verified, method; y dónde se abortó.

Requisito: server vram4 vivo. Para navegación por CDP, idealmente un browser con
--remote-debugging-port (la red de CDP auto-lanza instancia dedicada si no).
Uso:  python scripts/gui_eval/measure_chain_execution.py
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("GEMMA4_ACCESSIBILITY_MODE", "movilidad")

from gemma4_agent.config import AgentConfig
from gemma4_agent.agent import Gemma4Agent
from gemma4_agent.computer_use import PlanExecutor

# Planes FIJOS correctos (aislamos el ejecutor). Cadenas web verificables.
CHAINS = [
    ("abrir youtube y buscar gatos", [
        {"op": "open_url", "arg": "youtube.com"},
        {"op": "wait", "arg": "2"},
        {"op": "type", "arg": "gatos"},
        {"op": "send", "arg": ""},
    ]),
    ("abrir github y buscar python", [
        {"op": "open_url", "arg": "github.com"},
        {"op": "wait", "arg": "2"},
        {"op": "type", "arg": "python"},
        {"op": "send", "arg": ""},
    ]),
    ("navegar a example.com (1 paso, control)", [
        {"op": "open_url", "arg": "example.com"},
    ]),
]


def main() -> int:
    import urllib.request
    try:
        urllib.request.urlopen("http://127.0.0.1:8080/v1/models", timeout=5)
    except Exception as e:
        print(f"server DOWN :8080 -> {type(e).__name__}", flush=True)
        return 2

    agent = Gemma4Agent(AgentConfig.from_env())
    ex = PlanExecutor(agent)
    results = []
    for name, plan in CHAINS:
        print(f"\n{'='*64}\n>> CADENA: {name} ({len(plan)} pasos)\n{'='*64}", flush=True)
        res = ex.execute(plan, "chain_eval")
        steps = res.get("steps", [])
        done = len(steps)
        verified_steps = sum(1 for s in steps if s.get("verified") is True)
        print(f"  ok={res.get('ok')} verified={res.get('verified')} "
              f"failed_at={res.get('failed_at')}", flush=True)
        for s in steps:
            print(f"    {s['op']:10} ok={s.get('ok')!s:5} verified={s.get('verified')!s:5} "
                  f"method={s.get('method')}", flush=True)
        results.append({"chain": name, "n_steps": len(plan), "steps_run": done,
                        "verified_steps": verified_steps, "ok": res.get("ok"),
                        "failed_at": res.get("failed_at")})

    out = ROOT / "scripts" / "gui_eval" / "_chain_execution_results.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWROTE {out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
