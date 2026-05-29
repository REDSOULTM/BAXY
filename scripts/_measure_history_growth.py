"""¿El prompt CRECE sin techo en una conversación larga, o la compactación lo acota?
Corre 16 turnos MIXTOS (info/smalltalk/deícticos -> rutean a 'full' = mandan history)
acumulando, y captura el TOTAL del prompt de pass-1 (prompt_n + cache_n) + #mensajes
en self.history. Si el total se estabiliza -> compactación OK (no hay lever). Si
crece monótono hacia 16k -> leak.

  python scripts/_measure_history_growth.py
"""
import os
import sys
import time
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
from gemma4_agent.infra import llm_client

first_call = {"prompt_n": None, "cache_n": None, "seen": False}
orig = llm_client.LLMClient.chat


def wrapped(self, messages, **kw):
    resp = orig(self, messages, **kw)
    if not first_call["seen"]:
        first_call["seen"] = True
        t = (resp or {}).get("timings", {})
        first_call["prompt_n"] = t.get("prompt_n")
        first_call["cache_n"] = t.get("cache_n")
    return resp


llm_client.LLMClient.chat = wrapped
print("[boot] agente...", flush=True)
agent = Gemma4Agent()

# Turnos que tienden a rutear 'full' (info/ambiguo/deíctico) para forzar el envío
# de history -> estresa el crecimiento del prompt.
CMDS = [
    "qué es la fotosíntesis", "y eso para qué sirve", "explicame más",
    "cuál es la capital de Japón", "y la de Francia", "interesante, seguí",
    "qué es una API", "dame un ejemplo", "y otro más",
    "por qué el cielo es azul", "y de noche", "explicame el ADN",
    "qué más sabés de eso", "resumime todo lo anterior",
    "qué fue lo primero que te pregunté", "gracias por todo",
]
print("=" * 80, flush=True)
maxtot = 0
for i, cmd in enumerate(CMDS):
    first_call["seen"] = False
    first_call["prompt_n"] = None
    first_call["cache_n"] = None
    t0 = time.monotonic()
    try:
        agent.run_content(cmd)
    except Exception as e:  # noqa: BLE001
        print(f"  t{i:02d} EXC {type(e).__name__}: {e}", flush=True)
        continue
    dt = time.monotonic() - t0
    pn = first_call["prompt_n"] or 0
    cn = first_call["cache_n"] or 0
    tot = pn + cn
    maxtot = max(maxtot, tot)
    nhist = len(getattr(agent, "history", []) or [])
    print(f"  t{i:02d} {cmd[:28]!r:30} pass1_total={tot:5d} (prefill={pn} cache={cn}) hist_msgs={nhist} dt={dt:.2f}s", flush=True)
print("=" * 80, flush=True)
print(f"[lee] pass1_total max={maxtot}. Si se estabiliza (no crece monótono hacia ~16k) -> compactación OK.", flush=True)
