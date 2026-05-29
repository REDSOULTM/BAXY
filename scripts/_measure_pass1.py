"""Mide el DESGLOSE de latencia de pass-1 (decidir+tool-call) por LLM call:
prefill (prompt_ms, procesar el prompt) vs decode (predicted_ms, generar tokens).

Decide si prefill-`<|tool_call|>` vale la pena: si pass-1 está dominado por
PREFILL (prompt de ~5k tok, FA-off), sesgar el primer token / bajar thinking 32->0
ahorra solo el decode (~32 tok) -> casi nada. Si está dominado por DECODE (thinking),
sí ayuda. MEDIR antes de construir (lección del streaming TTS).

  python scripts/_measure_pass1.py
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

caps: list[dict] = []
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
    caps.append({"dt": dt, "timings": tim, "tcs": tcs})
    return resp


llm_client.LLMClient.chat = wrapped

print("[boot] agente...", flush=True)
agent = Gemma4Agent()
print("[warm] ...", flush=True)
agent.run_content("abrí la calculadora")

CMDS = ["abrí la calculadora", "minimizá la ventana", "subí el volumen al 40 por ciento"]
print("=" * 96, flush=True)
for cmd in CMDS:
    caps.clear()
    t0 = time.monotonic()
    reply = agent.run_content(cmd)
    total = time.monotonic() - t0
    content = (getattr(reply, "content", "") or "").replace("\n", " ")[:60]
    print(f"\n=== {cmd!r}  total_turn={total:.2f}s  calls={len(caps)}  reply={content!r}", flush=True)
    for i, c in enumerate(caps):
        t = c["timings"]
        pm = t.get("prompt_ms")
        dm = t.get("predicted_ms")
        pn = t.get("prompt_n")
        dn = t.get("predicted_n")
        tag = "PASS-1(decide)" if i == 0 else f"call#{i}"
        if pm is not None:
            print(f"  {tag}: wall={c['dt']:.2f}s  tcs={c['tcs']}  "
                  f"PREFILL {pn}tok/{pm:.0f}ms  DECODE {dn}tok/{dm:.0f}ms", flush=True)
        else:
            print(f"  {tag}: wall={c['dt']:.2f}s  tcs={c['tcs']}  (sin timings en la resp)", flush=True)
print("\n" + "=" * 96, flush=True)
print("[lee] si PREFILL_ms >> DECODE_ms en PASS-1 -> prefill-token NO ayuda (el costo es el prompt).", flush=True)
