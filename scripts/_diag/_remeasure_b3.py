"""Verifica EN VIVO que el gate de ruido B3 hace que el agente PIDA ACLARACIÓN
ante un número/medición suelto, en vez de rutear a una tool arbitraria. + controles
que NO deben gatearse (comando con número, respuesta a pending).

Uso: python scripts/_diag/_remeasure_b3.py
"""
from __future__ import annotations
import os, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
os.environ.setdefault("GEMMA4_DIAG", "1")  # no contaminar la DB de Jarvis en pruebas

# (label, prev_text, user_text). prev sirve para el caso pending.
CASES = [
    ("B3-noise", "", "2.14s"),
    ("B3-noise", "", "7.63"),
    ("B3-noise", "", "12.66"),
    ("ctrl-cmd", "", "pon el volumen al 50"),   # número EN comando -> NO gatear
    ("ctrl-cmd", "", "abre steam"),             # comando normal
]

from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager
prof = get_active_profile(); apply_profile_to_env(prof)
get_shared_manager().start(prof, wait_health=True, timeout_s=120)
print("[boot] OK", flush=True)

from gemma4_agent.tools_pkg.tools import ToolRegistry
executed: list = []
def _mock_execute(self, n, a):
    executed.append({"name": n, "args": a or {}})
    return {"ok": True, "status": "ok", "verified": True, "_eval_mock": True}
ToolRegistry.execute = _mock_execute
for _m in ["gui_type", "gui_keypress", "gui_click", "gui_type_into", "gui_click_button",
           "gui_hotkey", "gui_scroll", "gui_drag", "_send_text_via_sendinput"]:
    if hasattr(ToolRegistry, _m):
        setattr(ToolRegistry, _m, lambda *a, **k: {"ok": True})

from gemma4_agent.agent_core.agent import Gemma4Agent
agent = Gemma4Agent()
agent.run_content("hola")  # warm

for label, prev, ut in CASES:
    try:
        agent.history.clear()
    except Exception:
        pass
    if prev:
        try:
            agent.run_content(prev)
        except Exception:
            pass
    executed.clear()
    t0 = time.perf_counter()
    try:
        rep = agent.run_content(ut)
        content = getattr(rep, "content", "") or ""
    except Exception as e:
        content = f"ERR {type(e).__name__}: {e}"
    dt = time.perf_counter() - t0
    tools = [e["name"] + "." + str((e["args"] or {}).get("action")) for e in executed]
    print(f"  [{label}] {ut!r:22} dt={dt:.1f}s tools={tools}", flush=True)
    print(f"      reply: {content[:150]!r}", flush=True)
print("[done]", flush=True)
