"""¿Mantener las tools en el SUMMARY pass (GEMMA4_SUMMARY_KEEP_TOOLS) convierte el
re-prefill de ~5.3k tokens en un CACHE HIT? Mide, por comando de acción, en ambas
condiciones (flag OFF=dropea tools / ON=mantiene), el PREFILL de la pass-2 (call#1)
y el tiempo total del turno.

Hipótesis: con tools mantenidas, el prefijo de la pass-2 == prefijo de la pass-1 ->
prefix-cache hit -> pass-2 prefilea solo los ~50 tokens nuevos (no 5.3k) -> ~-1s.

History se resetea entre comandos. (Cambia el volumen; restaurable a mano.)

  python scripts/_measure_summary_cache.py
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
print(f"[boot] perfil={prof.name}; server...", flush=True)
mgr.start(prof, wait_health=True, timeout_s=120)

from gemma4_agent.agent_core.agent import Gemma4Agent
from gemma4_agent.infra import llm_client

calls: list[dict] = []
orig = llm_client.LLMClient.chat


def wrapped(self, messages, **kw):
    t0 = time.monotonic()
    resp = orig(self, messages, **kw)
    dt = time.monotonic() - t0
    tim = (resp or {}).get("timings") or {}
    tcs = []
    for ch in (resp or {}).get("choices") or []:
        for tc in ((ch.get("message") or {}).get("tool_calls") or []):
            tcs.append((tc.get("function") or {}).get("name"))
    calls.append({"dt": dt, "prompt_n": tim.get("prompt_n"), "prompt_ms": tim.get("prompt_ms"),
                  "predicted_n": tim.get("predicted_n"), "tcs": tcs})
    return resp


llm_client.LLMClient.chat = wrapped

print("[boot] agente...", flush=True)
agent = Gemma4Agent()
agent.run_content("subí el volumen al 50 por ciento")  # warm

CMDS = ["subí el volumen al 40 por ciento", "bajá el volumen", "minimizá la ventana"]


def run(cmd: str, keep: bool):
    if keep:
        os.environ["GEMMA4_SUMMARY_KEEP_TOOLS"] = "1"
    else:
        os.environ.pop("GEMMA4_SUMMARY_KEEP_TOOLS", None)
    try:
        agent.history.clear()
    except Exception:
        pass
    calls.clear()
    t0 = time.monotonic()
    agent.run_content(cmd)
    total = time.monotonic() - t0
    return total, [dict(c) for c in calls]


print("=" * 96, flush=True)
for cmd in CMDS:
    for keep in (False, True):
        total, cs = run(cmd, keep)
        tag = "KEEP " if keep else "DROP "
        # pass-2 = última call (la confirmación). pass-1 = primera con tool_call.
        line = f"[{tag}] {cmd!r:42} total={total:.2f}s calls={len(cs)}"
        print(line, flush=True)
        for i, c in enumerate(cs):
            role = "pass-1" if i == 0 else ("pass-2" if i == len(cs) - 1 else f"call#{i}")
            print(f"        {role}: prefill={c['prompt_n']}tok/{c['prompt_ms']}ms "
                  f"decode={c['predicted_n']}tok tcs={c['tcs']}", flush=True)
    print("-" * 96, flush=True)
print("=" * 96, flush=True)
print("[lee] si en KEEP el prefill de pass-2 << que en DROP -> cache hit confirmado (win).", flush=True)
