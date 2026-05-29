"""Valida el fix C: una negación/cancelación NO debe dar el genérico del grounding
gate "No alcancé a completar la acción. ¿La repetimos?" — debe ser un ack limpio.
LLM real; tools mockeadas + SendInput neutralizado (seguro; las negaciones no
ejecutan acciones de todos modos)."""
import ctypes
import os
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")

# red de seguridad: neutralizar input fisico
try:
    _o = ctypes.WinDLL
    _B = {"SendInput", "keybd_event", "mouse_event", "BlockInput", "SetCursorPos"}

    class _S:
        def __init__(s, d): object.__setattr__(s, "_d", d)
        def __getattr__(s, n):
            return (lambda *a, **k: 0) if n in _B else getattr(object.__getattribute__(s, "_d"), n)
    ctypes.WinDLL = lambda name, *a, **k: (_S(_o(name, *a, **k)) if isinstance(name, str) and "user32" in name.lower() else _o(name, *a, **k))
except Exception:
    pass

from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager

prof = get_active_profile()
apply_profile_to_env(prof)
print("[boot] llama-server...", flush=True)
get_shared_manager().start(prof, wait_health=True, timeout_s=120)

from gemma4_agent.agent_core.agent import Gemma4Agent

agent = Gemma4Agent()
for _n in list(agent.tools._impls.keys()):
    agent.tools._impls[_n] = (lambda n: (lambda a: {"ok": True, "tool": n, "mocked": True, "verified": True}))(_n)

BAD = "no alcancé a completar"
NEGS = ["No.", "No lo envíes", "no, dejá", "cancelá eso", "no, mejor no"]

print("=" * 76, flush=True)
fails = 0
for text in NEGS:
    try:
        r = agent.run_content(text)
        reply = (getattr(r, "content", "") or "").replace("\n", " ")
    except Exception as e:
        print(f"  <EXC {type(e).__name__}: {e}>", flush=True); fails += 1; continue
    bad = BAD in reply.lower()
    if bad:
        fails += 1
    subset = getattr(agent, "_last_router_subset", None)
    print(f"[{'FALLA' if bad else 'OK  '}] {text!r}  subset={subset}", flush=True)
    print(f"        reply={reply[:120]!r}", flush=True)
print("=" * 76, flush=True)
print(f"[VEREDICTO C] {'OK (0 dieron el generico)' if fails == 0 else f'FALLA ({fails} dieron No-alcancé)'}", flush=True)
