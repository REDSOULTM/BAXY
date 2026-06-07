"""Verifica EN VIVO (server fresco, prompt Baxy) que el fix de identidad funciona:
el asistente se presenta como BAXY, no Gemma. + 2 fixes de honestidad de estado.
CLAUDE.md §3.5: probar contra el LLM real.

Uso: python scripts/_diag/_diag_verify_baxy_identity_live.py
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

from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager
prof = get_active_profile(); apply_profile_to_env(prof)
mgr = get_shared_manager(); mgr.start(prof, wait_health=True, timeout_s=120)
print("[boot] OK", flush=True)

from gemma4_agent.tools_pkg.tools import ToolRegistry
_real_t_steam = ToolRegistry.t_steam
def _exec(self, n, a):
    if n == "steam":
        try: return _real_t_steam(self, a or {})
        except Exception as e: return {"ok": False, "error": str(e)}
    return {"ok": True, "status": "done", "verified": True, "action": (a or {}).get("action"), "_eval_mock": True}
ToolRegistry.execute = _exec
for _m in ["gui_type","gui_keypress","gui_click","gui_type_into","gui_click_button","_send_text_via_sendinput"]:
    if hasattr(ToolRegistry, _m):
        setattr(ToolRegistry, _m, lambda *a, **k: {"ok": True})

from gemma4_agent.agent_core.agent import Gemma4Agent
agent = Gemma4Agent()
agent.run_content("hola")

CASES = [
    ("identidad ES", "¿quién sos?", lambda r: "baxy" in r.lower() and "soy gemma" not in r.lower()),
    ("identidad EN", "who are you?", lambda r: "baxy" in r.lower()),
    ("capacidades", "¿qué podés hacer?", lambda r: "soy gemma" not in r.lower()),
]
print("\n=== VERIFICACIÓN IDENTIDAD BAXY EN VIVO (server fresco) ===\n")
npass = 0
for label, msg, check in CASES:
    agent.history.clear()
    try:
        rep = agent.run_content(msg); reply = getattr(rep, "content", "") or ""
    except Exception as e:
        reply = f"<EXC {e}>"
    ok = False
    try: ok = check(reply)
    except Exception: ok = False
    npass += ok
    print(f"[{'PASS' if ok else 'CHECK'}] {label}: {msg!r}")
    print(f"   -> {reply[:120]!r}\n")
print(f"[done] {npass}/{len(CASES)} PASS", flush=True)
