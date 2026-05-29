"""Verifica que el modo cache-hit (GEMMA4_SUMMARY_KEEP_TOOLS: keep tools + match
enable_thinking + budget=0 en el summary) produce REPLIES CORRECTOS (no vacíos ni
garbled por enable_thinking=True+budget=0) Y que la pass-2 hace cache-hit.

  python scripts/_verify_cache_hit.py
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
os.environ["GEMMA4_SUMMARY_KEEP_TOOLS"] = "1"  # soak the cache-hit mode

from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager

prof = get_active_profile()
apply_profile_to_env(prof)
mgr = get_shared_manager()
print(f"[boot] {prof.name}; server...", flush=True)
mgr.start(prof, wait_health=True, timeout_s=120)

from gemma4_agent.agent_core.agent import Gemma4Agent
from gemma4_agent.infra import llm_client

last = {"pass2_prefill": None, "calls": 0}
orig = llm_client.LLMClient.chat


def wrapped(self, messages, **kw):
    resp = orig(self, messages, **kw)
    last["calls"] += 1
    last["pass2_prefill"] = (resp or {}).get("timings", {}).get("prompt_n")
    return resp


llm_client.LLMClient.chat = wrapped
print("[boot] agente...", flush=True)
agent = Gemma4Agent()
agent.run_content("subí el volumen al 50 por ciento")  # warm

# SOAK: successful actions (audio + window) -> confirm consistent cache hits, no
# runaways, correct replies. Cache-hit mode is success-gated, so these should all
# hit (small pass2_prefill) and stay at 2 calls.
CMDS = ["subí el volumen al 45 por ciento", "bajá el volumen al 20 por ciento",
        "poné el volumen al 60 por ciento", "subí el volumen al 35 por ciento",
        "bajá el volumen", "poné el volumen al 50 por ciento",
        "minimizá la ventana", "poné el volumen al 30 por ciento"]
hits = runaways = bad = 0
print("=" * 92, flush=True)
for cmd in CMDS:
    try:
        agent.history.clear()
    except Exception:
        pass
    last["pass2_prefill"] = None
    last["calls"] = 0
    t0 = time.monotonic()
    reply = agent.run_content(cmd)
    dt = time.monotonic() - t0
    content = (getattr(reply, "content", "") or "").replace("\n", " ")
    n_ev = len(getattr(reply, "tool_events", []) or [])
    p2 = last["pass2_prefill"]
    runaway = last["calls"] > 2
    hit = isinstance(p2, int) and p2 < 500
    okrep = bool(content.strip()) and "think" not in content.lower()[:20]
    if runaway:
        runaways += 1
    if hit:
        hits += 1
    if not okrep or runaway:
        bad += 1
    flag = "OK " if (okrep and not runaway) else "CHK"
    print(f"[{flag}] {cmd!r:38} total={dt:.2f}s calls={last['calls']} ev={n_ev} pass2={p2} hit={hit}", flush=True)
    print(f"      {content[:90]!r}", flush=True)
print("=" * 92, flush=True)
print(f"[SOAK] cache-hits={hits}/{len(CMDS)}  runaways={runaways}  bad={bad}", flush=True)
print("=" * 92, flush=True)
print("[lee] reply NO vacío + sin '<think>' al inicio + pass2_prefill chico (cache hit) = OK.", flush=True)
