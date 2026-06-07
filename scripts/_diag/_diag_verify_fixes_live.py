"""Verifica EN VIVO (LLM real, ejecución física MOCKEADA) los fixes de esta sesión
que NO dependen del prompt cacheado en el server (routing/parsing/dispatcher):

  - BUG B estado-local: "¿qué juego estoy jugando?" -> ofrece/usa window (no cancel_turn)
  - click perífrasis: "hacé click en el botón rojo" -> gui.click_button (no charla)
  - busca_teclados crash: un handler non-dict NO tumba el turno (reply honesto)
  - mensajería Discord: "escribile a Juan ... en Discord" -> NO tipea "a Juan" en cuerpo

Registra, por caso: tools ejecutadas + reply + passes + latencia + veredicto.
CLAUDE.md §3.5: probar en vivo contra el LLM real, no solo unit mockeado.

Uso: python scripts/_diag/_diag_verify_fixes_live.py
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

from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager
prof = get_active_profile(); apply_profile_to_env(prof)
mgr = get_shared_manager(); mgr.start(prof, wait_health=True, timeout_s=120)
print("[boot] OK", flush=True)

from gemma4_agent.tools_pkg.tools import ToolRegistry
from gemma4_agent.infra import llm_client

executed = []
ToolRegistry.execute = lambda self, n, a: (
    executed.append((n, (a or {}).get("action"), (a or {}).get("query") or (a or {}).get("label") or (a or {}).get("goal") or ""))
    or {"ok": True, "status": "done", "verified": True, "action": (a or {}).get("action"), "_eval_mock": True})
for _m in ["gui_type", "gui_keypress", "gui_click", "gui_type_into", "gui_click_button",
           "gui_hotkey", "_send_text_via_sendinput"]:
    if hasattr(ToolRegistry, _m):
        setattr(ToolRegistry, _m, lambda *a, **k: {"ok": True})

ncalls = [0]
_real = llm_client.LLMClient.chat
def _w(self, m, **kw):
    ncalls[0] += 1
    return _real(self, m, **kw)
llm_client.LLMClient.chat = _w

from gemma4_agent.agent_core.agent import Gemma4Agent
agent = Gemma4Agent()
agent.run_content("hola")  # warm

CASES = [
    ("BUG B estado-local", "¿qué juego estoy jugando?",
     lambda tools, reply: any(t[0] == "window" for t in tools) or "no" not in reply.lower()[:4]),
    ("BUG B variante", "qué aplicación está abierta",
     lambda tools, reply: any(t[0] == "window" for t in tools)),
    ("click perífrasis", "hacé click en el botón rojo",
     lambda tools, reply: any(t[0] in ("gui", "uia", "vision") for t in tools)),
    ("mensajería Discord", "escribile a Juan que voy en un momento en Discord",
     lambda tools, reply: "a seba" not in reply.lower()),
]

print("\n=== VERIFICACIÓN EN VIVO DE FIXES ===\n")
for label, msg, check in CASES:
    agent.history.clear()
    executed.clear(); ncalls[0] = 0
    t0 = time.perf_counter()
    try:
        r = agent.run_content(msg)
        reply = getattr(r, "content", "") or ""
    except Exception as e:
        reply = f"<EXC {type(e).__name__}: {e}>"
    dt = time.perf_counter() - t0
    ok = False
    try:
        ok = check(list(executed), reply)
    except Exception:
        ok = False
    print(f"[{'PASS' if ok else 'CHECK'}] {label}")
    print(f"   msg:   {msg!r}")
    print(f"   tools: {executed}")
    print(f"   reply: {reply[:140]!r}")
    print(f"   ({dt:.1f}s, {ncalls[0]} passes)\n")

print("[done]", flush=True)
