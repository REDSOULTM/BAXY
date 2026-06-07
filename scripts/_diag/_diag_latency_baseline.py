"""Baseline de LATENCIA en vivo (regla 3.5) sobre los casos de uso reales del user.
Mide el camino OPTIMIZABLE (router → pasadas de LLM → finalización del reply) con
la ejecución de tools MOCKEADA (synthetic success) — seguro (cero SendInput) y
aísla la latencia que SÍ podemos recortar (la del LLM/agente), no la del SO
abriendo apps. Reporta por caso: total, #pasadas de LLM, tiempo de cada pasada.

Uso: python scripts/_diag/_diag_latency_baseline.py [N_runs]
"""
from __future__ import annotations
import os, sys, time, statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
os.environ.setdefault("GEMMA4_DIAG", "1")  # no contaminar la DB de Jarvis en pruebas

from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager

prof = get_active_profile(); apply_profile_to_env(prof)
mgr = get_shared_manager()
print(f"[boot] {prof.name}; server...", flush=True)
mgr.start(prof, wait_health=True, timeout_s=120)
print("[boot] OK", flush=True)

from gemma4_agent.tools_pkg.tools import ToolRegistry
from gemma4_agent.infra import llm_client

# --- SEGURIDAD: mock execute (synthetic, instantáneo) + primitivas físicas ---
_real_execute = ToolRegistry.execute
def _safe_execute(self, name, args):
    return {"ok": True, "status": "ok", "_eval_mock": True, "action": (args or {}).get("action")}
ToolRegistry.execute = _safe_execute
for _m in ["gui_type", "gui_keypress", "gui_click", "gui_type_into", "gui_click_button",
           "gui_hotkey", "gui_scroll", "gui_drag", "_send_text_via_sendinput"]:
    if hasattr(ToolRegistry, _m):
        setattr(ToolRegistry, _m, (lambda *a, **k: {"ok": True, "_eval_mock": "phys-noop"}))

# --- timing de cada pasada de LLM ---
_call_times: list[float] = []
_real_chat = llm_client.LLMClient.chat
def _timed_chat(self, messages, **kw):
    t0 = time.perf_counter()
    resp = _real_chat(self, messages, **kw)
    _call_times.append(time.perf_counter() - t0)
    return resp
llm_client.LLMClient.chat = _timed_chat
# también el streaming (algunos turnos van por chat_stream)
if hasattr(llm_client.LLMClient, "chat_stream"):
    _real_stream = llm_client.LLMClient.chat_stream
    def _timed_stream(self, *a, **kw):
        t0 = time.perf_counter()
        for ev in _real_stream(self, *a, **kw):
            yield ev
        _call_times.append(time.perf_counter() - t0)
    llm_client.LLMClient.chat_stream = _timed_stream

from gemma4_agent.agent_core.agent import Gemma4Agent
print("[boot] agente...", flush=True)
agent = Gemma4Agent()
agent.run_content("hola")  # warm prefix-cache

N = int(sys.argv[1]) if len(sys.argv) > 1 else 2

CASES = [
    ("system",     "qué hora es"),
    ("system",     "cuánta RAM tengo"),
    ("audio",      "subí el volumen"),
    ("audio",      "muteá"),
    ("brillo",     "bajá el brillo de la pantalla"),
    ("web/clima",  "qué clima hace hoy"),
    ("web/saber",  "quién es Lionel Messi"),
    ("web/saber",  "qué es pytest"),
    ("app",        "abrí Spotify"),
    ("app",        "cerrá Discord"),
    ("media",      "poné música"),
    ("navegar",    "andá a la página de YouTube"),
    ("mensajes",   "leeme los mensajes"),
    ("timer",      "contá 10 minutos"),
    ("filesystem", "qué hay en la carpeta Descargas"),
    ("chitchat",   "hola"),
    ("chitchat",   "gracias"),
]

print(f"\n{'CASO':<26} {'p50_total':>9} {'#LLM':>5} {'pasadas (s)':<22} reply", flush=True)
print("-" * 100, flush=True)
rows = []
for area, msg in CASES:
    totals, ncalls_list, breakdowns = [], [], []
    for _ in range(N):
        try:
            agent.history.clear()
        except Exception:
            pass
        _call_times.clear()
        t0 = time.perf_counter()
        reply = agent.run_content(msg)
        dt = time.perf_counter() - t0
        totals.append(dt)
        ncalls_list.append(len(_call_times))
        breakdowns.append(list(_call_times))
    p50 = statistics.median(totals)
    # tomar el breakdown de la corrida más cercana a la mediana
    best = min(range(len(totals)), key=lambda i: abs(totals[i] - p50))
    ncalls = ncalls_list[best]
    bd = "+".join(f"{x:.2f}" for x in breakdowns[best])
    content = (getattr(reply, "content", "") or "").replace("\n", " ")[:46]
    rows.append((area, msg, p50, ncalls, sum(breakdowns[best])))
    label = f"{area}:{msg}"
    print(f"{label:<26} {p50:>8.2f}s {ncalls:>5} {bd:<22} {content!r}", flush=True)

print("-" * 100, flush=True)
allp = sorted(r[2] for r in rows)
print(f"GLOBAL p50={statistics.median(allp):.2f}s  min={allp[0]:.2f}s  max={allp[-1]:.2f}s  "
      f"(presupuesto voz 4-5s)", flush=True)
print("LENTOS (>4s):", [f"{r[0]}:{r[1]} {r[2]:.1f}s" for r in rows if r[2] > 4.0], flush=True)
