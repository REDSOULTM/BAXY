"""Re-mide SOLO los 2 casos C1 que aún loopeaban (602, 646) tras agregar el dedup
de batch degenerado. + 2 controles de research GENUINO (no debe romperse). MEDIR.

Uso: python scripts/_diag/_remeasure_c1_only.py
"""
from __future__ import annotations
import json, os, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
os.environ.setdefault("GEMMA4_DIAG", "1")  # no contaminar la DB de Jarvis en pruebas

# (label, user_text). Los 2 loopers + research genuino de control.
CASES = [
    ("C1-looper", "Investiga en internet que es el h2o"),
    ("C1-looper", "Investiga cuando salio gta 5"),
    ("ctrl-research", "buscame informacion actualizada sobre el clima en buenos aires"),
    ("ctrl-research", "investiga las ultimas noticias de inteligencia artificial"),
]

from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager
prof = get_active_profile(); apply_profile_to_env(prof)
get_shared_manager().start(prof, wait_health=True, timeout_s=120)
print("[boot] OK", flush=True)

from gemma4_agent.tools_pkg.tools import ToolRegistry
from gemma4_agent.infra import llm_client

executed: list = []
def _mock_execute(self, n, a):
    executed.append({"name": n, "args": a or {}})
    return {"ok": True, "status": "ok", "verified": True, "_eval_mock": True}
ToolRegistry.execute = _mock_execute
for _m in ["gui_type", "gui_keypress", "gui_click", "gui_type_into", "gui_click_button",
           "gui_hotkey", "gui_scroll", "gui_drag", "_send_text_via_sendinput"]:
    if hasattr(ToolRegistry, _m):
        setattr(ToolRegistry, _m, lambda *a, **k: {"ok": True})

ncalls = [0]
_real_chat = llm_client.LLMClient.chat
def _wrap(self, m, **kw):
    ncalls[0] += 1
    return _real_chat(self, m, **kw)
llm_client.LLMClient.chat = _wrap

from gemma4_agent.agent_core.agent import Gemma4Agent
agent = Gemma4Agent()
agent.run_content("hola")  # warm

for label, ut in CASES:
    try:
        agent.history.clear()
    except Exception:
        pass
    executed.clear(); ncalls[0] = 0
    t0 = time.perf_counter()
    try:
        rep = agent.run_content(ut)
        content = getattr(rep, "content", "") or ""
    except Exception as e:
        content = f"ERR {type(e).__name__}: {e}"
    dt = time.perf_counter() - t0
    loop = "LOOP" if len(executed) > 8 else "ok"
    print(f"  [{label}] dt={dt:.1f}s ntools={len(executed)} passes={ncalls[0]} {loop}  {ut[:48]!r}", flush=True)
    print(f"      reply: {content[:160]!r}", flush=True)
print("[done]", flush=True)
