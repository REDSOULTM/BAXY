"""¿La PASS-1 reusa el prefijo (system + core tools) de turnos ANTERIORES
(cross-turn cache)? Es el lever que queda: la pass-1 prefilea ~1.2s. Con
--keep -1 + --swa-full el system estable debería cachearse cross-turn; las tools
varían por turno (router) -> el cache pega hasta donde divergen.

Corre comandos DISTINTOS en secuencia (history acumula = uso real) y captura, por
PASS-1, prompt_n (prefilados) + cache_n (reusados) + tools_n. Si cache_n es alto
(~system size) -> ya cachea; si ~0 -> hay variación que lo rompe (oportunidad).

  python scripts/_measure_crossturn_cache.py
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

turn_calls: list[dict] = []
orig = llm_client.LLMClient.chat


def wrapped(self, messages, **kw):
    resp = orig(self, messages, **kw)
    t = (resp or {}).get("timings", {})
    turn_calls.append({"prompt_n": t.get("prompt_n"), "cache_n": t.get("cache_n"),
                       "tools_n": len(kw.get("tools") or [])})
    return resp


llm_client.LLMClient.chat = wrapped
print("[boot] agente...", flush=True)
agent = Gemma4Agent()

# Comandos DISTINTOS, history ACUMULA (uso real). NO clear entre turnos.
CMDS = [
    "hola qué tal",
    "subí el volumen al 40 por ciento",
    "qué hora es",
    "bajá el volumen",
    "minimizá la ventana",
    "poné el volumen al 60 por ciento",
]
print("=" * 92, flush=True)
for i, cmd in enumerate(CMDS):
    turn_calls.clear()
    t0 = time.monotonic()
    agent.run_content(cmd)
    dt = time.monotonic() - t0
    p1 = turn_calls[0] if turn_calls else {}
    pn, cn = p1.get("prompt_n"), p1.get("cache_n")
    reuse = (f"{100*cn/(cn+pn):.0f}%" if isinstance(cn, int) and isinstance(pn, int) and (cn + pn) else "?")
    print(f"[turn {i}] {cmd!r:38} total={dt:.2f}s  PASS-1 prefill={pn} cache={cn} reuse={reuse} tools={p1.get('tools_n')}", flush=True)
print("=" * 92, flush=True)
print("[lee] PASS-1 cache alto (reuse>0) = cachea el system cross-turn; prefill chico = win ya capturado.", flush=True)
