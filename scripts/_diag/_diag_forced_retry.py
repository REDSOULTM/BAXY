"""A/B disciplinado del forced-retry: cuando el 4B NARRA en pass-1 (no llama tool),
el forced-retry (tool_choice=required) debería FORZAR el tool-call. Hoy usa
enable_thinking=True y a veces vuelve VACÍO (forced_tool_retry_empty). Hipótesis:
el thinking interfiere con la grammar forzada. A/B: GEMMA4_FORCED_RETRY_NOTHINK
off (thinking on, actual) vs on (thinking off).

Por cada comando × condición captura: ¿disparó forced-retry? ¿ok o empty? eventos
finales. Agrega la tasa de rescate. Comandos benignos (app/settings opens) tendientes
a narrar (sufijos/qualifiers).

  python scripts/_diag_forced_retry.py
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")

from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager

prof = get_active_profile()
apply_profile_to_env(prof)
mgr = get_shared_manager()
print(f"[boot] {prof.name}; server...", flush=True)
mgr.start(prof, wait_health=True, timeout_s=120)

from gemma4_agent.agent_core.agent import Gemma4Agent

agent = None
flags = {"fired": False, "ok": False, "empty": False}


def reset_flags():
    flags["fired"] = flags["ok"] = flags["empty"] = False


print("[boot] agente...", flush=True)
agent = Gemma4Agent()
_orig_event = agent.trace.event


def wrapped_event(turn_id, _evname, **payload):
    if _evname == "forced_tool_retry":
        flags["fired"] = True
    elif _evname == "forced_tool_retry_ok":
        flags["ok"] = True
    elif _evname == "forced_tool_retry_empty":
        flags["empty"] = True
    return _orig_event(turn_id, _evname, **payload)


agent.trace.event = wrapped_event
agent.run_content("hola")  # warm

CMDS = [
    "abrí la calculadora de Windows",
    "abrí el administrador de tareas",
    "abrí la papelera de reciclaje",
    "abrí la configuración de Windows",
    "abrí el panel de control",
]
agg = {"off": {"fired": 0, "ok": 0, "empty": 0}, "on": {"fired": 0, "ok": 0, "empty": 0}}
print("=" * 90, flush=True)
for cmd in CMDS:
    print(f"\n{cmd!r}", flush=True)
    for nothink in (False, True):
        if nothink:
            os.environ["GEMMA4_FORCED_RETRY_NOTHINK"] = "1"
        else:
            os.environ.pop("GEMMA4_FORCED_RETRY_NOTHINK", None)
        try:
            agent.history.clear()
        except Exception:
            pass
        reset_flags()
        reply = agent.run_content(cmd)
        n_ev = len(getattr(reply, "tool_events", []) or [])
        cond = "on" if nothink else "off"
        if flags["fired"]:
            agg[cond]["fired"] += 1
            if flags["ok"]:
                agg[cond]["ok"] += 1
            if flags["empty"]:
                agg[cond]["empty"] += 1
        outcome = ("retry_OK" if flags["ok"] else ("retry_EMPTY" if flags["empty"]
                   else ("no_retry(called pass-1)" if n_ev else "no_retry")))
        print(f"  [NOTHINK={cond}] events={n_ev} forced_retry_fired={flags['fired']} -> {outcome}", flush=True)
        print(f"       reply={(getattr(reply,'content','') or '')[:70]!r}", flush=True)
print("=" * 90, flush=True)
for cond in ("off", "on"):
    a = agg[cond]
    rate = f"{a['ok']}/{a['fired']}" if a["fired"] else "0/0"
    print(f"[NOTHINK={cond}] forced-retry fired={a['fired']} OK={a['ok']} EMPTY={a['empty']}  rescue={rate}", flush=True)
print("[lee] si NOTHINK=on tiene más OK (menos EMPTY) cuando el retry dispara -> el thinking era el problema.", flush=True)
