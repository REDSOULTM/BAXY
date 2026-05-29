"""¿Se puede sacar el thinking (32 tok) del pass-1 de quick_action SIN perder el
tool-calling? Si sí -> win ~0.4s GRATIS (sin la maquinaria riesgosa de prefill
`<|tool_call|>`). Si el tool-calling se cae -> el thinking es load-bearing y
prefill-token sería el rescate (riesgoso).

Mide, por comando de acción, en ambas condiciones (thinking ON=baseline 32 / OFF):
  - ¿pass-1 emitió tool_call?  (fiabilidad)
  - latencia de pass-1 (wall + prefill/decode ms).

History se RESETEA entre comandos (evita la contaminación que hacía "De nada").

  python scripts/_measure_thinking0.py
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

FORCE_THINK_OFF = {"on": False}
pass1 = {"tcs": [], "wall": 0.0, "prompt_ms": None, "predicted_ms": None, "predicted_n": None}
_seen = {"first": False}
orig = llm_client.LLMClient.chat


def wrapped(self, messages, **kw):
    # pass-1 de decisión = enable_thinking True + tools presentes (el summary va False).
    is_decision = bool(kw.get("enable_thinking")) and bool(kw.get("tools"))
    if FORCE_THINK_OFF["on"] and is_decision:
        kw["enable_thinking"] = False
        kw["thinking_budget"] = 0
    t0 = time.monotonic()
    resp = orig(self, messages, **kw)
    dt = time.monotonic() - t0
    if is_decision and not _seen["first"]:
        _seen["first"] = True
        tim = (resp or {}).get("timings") or {}
        tcs = []
        for ch in (resp or {}).get("choices") or []:
            for tc in ((ch.get("message") or {}).get("tool_calls") or []):
                tcs.append((tc.get("function") or {}).get("name"))
        pass1.update(tcs=tcs, wall=dt, prompt_ms=tim.get("prompt_ms"),
                     predicted_ms=tim.get("predicted_ms"), predicted_n=tim.get("predicted_n"))
    return resp


llm_client.LLMClient.chat = wrapped

print("[boot] agente...", flush=True)
agent = Gemma4Agent()
agent.run_content("abrí la calculadora")  # warm

CMDS = [
    "abrí la calculadora",
    "minimizá la ventana",
    "subí el volumen al 40 por ciento",
    "abrí el explorador de archivos",
    "bajá el volumen",
    "poné el volumen al 60 por ciento",
]


def run_suite(think_off: bool):
    FORCE_THINK_OFF["on"] = think_off
    rows = []
    for cmd in CMDS:
        try:
            agent.history.clear()
        except Exception:
            pass
        _seen["first"] = False
        pass1.update(tcs=[], wall=0.0, prompt_ms=None, predicted_ms=None, predicted_n=None)
        agent.run_content(cmd)
        rows.append((cmd, list(pass1["tcs"]), pass1["wall"], pass1["predicted_n"], pass1["predicted_ms"]))
    return rows


print("=" * 96, flush=True)
for label, off in [("THINKING ON (baseline 32)", False), ("THINKING OFF (0)", True)]:
    rows = run_suite(off)
    called = sum(1 for _, tcs, *_ in rows if tcs)
    avg_wall = sum(r[2] for r in rows) / len(rows)
    print(f"\n### {label}: tool_call en {called}/{len(rows)} | pass-1 wall avg={avg_wall:.2f}s", flush=True)
    for cmd, tcs, wall, pn, pm in rows:
        ok = "OK " if tcs else "MISS"
        print(f"  [{ok}] {cmd!r:45} tcs={tcs} wall={wall:.2f}s decode={pn}tok/{pm}ms", flush=True)
print("\n" + "=" * 96, flush=True)
print("[lee] si OFF mantiene tool_call ~igual que ON -> sacar thinking es win gratis.", flush=True)
print("      si OFF baja la tasa de tool_call -> thinking es load-bearing (prefill-token sería el rescate).", flush=True)
