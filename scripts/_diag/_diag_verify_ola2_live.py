"""Verifica EN VIVO (LLM real, ejecución física MOCKEADA) los fixes de las olas 2-3:
  - terminal_as_app: "ejecuta pytest" -> terminal/developer, NO app (no "abrí pytest")
  - web_as_app: "abre esta búsqueda en Google: X" -> browser/web, NO computer_use sobre app basura
  - status_checks: "¿Steam está abierto?" -> system/window, NO steam (no "abrí Steam")
  - window_vs_fs: "mueve Notepad a la izquierda" -> window, NO filesystem (no renombra)
  - tepad: "open Notepad and type hello" -> NO falla con app="tepad"

Registra tools ejecutadas + reply + veredicto por caso. CLAUDE.md §3.5.
Uso: python scripts/_diag/_diag_verify_ola2_live.py
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
from gemma4_agent.infra import llm_client

executed = []
_real_t_steam = ToolRegistry.t_steam
def _exec(self, n, a):
    executed.append((n, (a or {}).get("action") or ""))
    # steam: dejar correr t_steam REAL (read-only ante pregunta-de-estado por el
    # fix B; NO ejecuta startfile si _current_user_text es pregunta de estado).
    if n == "steam":
        try:
            return _real_t_steam(self, a or {})
        except Exception as e:
            return {"ok": False, "error": str(e)}
    return {"ok": True, "status": "done", "verified": True, "action": (a or {}).get("action"), "_eval_mock": True}
ToolRegistry.execute = _exec
if hasattr(ToolRegistry, "t_computer_use"):
    ToolRegistry.t_computer_use = lambda self, a: (
        executed.append(("computer_use", "goal")) or
        {"ok": True, "status": "done", "verified": True, "completion_status": "simulated"})
for _m in ["gui_type", "gui_keypress", "gui_click", "gui_type_into", "gui_click_button",
           "gui_hotkey", "_send_text_via_sendinput"]:
    if hasattr(ToolRegistry, _m):
        setattr(ToolRegistry, _m, lambda *a, **k: {"ok": True})

from gemma4_agent.agent_core.agent import Gemma4Agent
agent = Gemma4Agent()
agent.run_content("hola")  # warm

CASES = [
    ("terminal_as_app", "ejecuta pytest",
     lambda tools, r: not any(t[0] == "app" for t in tools) and "abrí pytest" not in r.lower()),
    ("web_as_app", "abre esta búsqueda en Google: diodo zener para qué sirve",
     lambda tools, r: any(t[0] in ("browser", "browser_real", "web") for t in tools)),
    ("status_checks", "revisa si Steam está abierto",
     lambda tools, r: not any(t[0] == "steam" for t in tools) and "abrí steam" not in r.lower()),
    ("window_vs_fs", "mueve Notepad a la izquierda",
     lambda tools, r: not any(t[0] == "filesystem" for t in tools) and "renombr" not in r.lower()),
    ("tepad", "open Notepad and type hello",
     lambda tools, r: "tepad" not in r.lower()),
]

print("\n=== VERIFICACIÓN EN VIVO OLAS 2-3 ===\n")
npass = 0
for label, msg, check in CASES:
    agent.history.clear(); executed.clear()
    t0 = time.perf_counter()
    try:
        rep = agent.run_content(msg)
        reply = getattr(rep, "content", "") or ""
    except Exception as e:
        reply = f"<EXC {type(e).__name__}: {e}>"
    dt = time.perf_counter() - t0
    try:
        ok = check(list(executed), reply)
    except Exception:
        ok = False
    npass += ok
    print(f"[{'PASS' if ok else 'CHECK'}] {label}  ({dt:.1f}s)")
    print(f"   msg:   {msg!r}")
    print(f"   tools: {executed}")
    print(f"   reply: {reply[:130]!r}\n")

print(f"[done] {npass}/{len(CASES)} PASS", flush=True)
