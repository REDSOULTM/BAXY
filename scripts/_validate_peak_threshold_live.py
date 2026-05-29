"""Validación EN VIVO del fix _SEM_PEAK_KEEP 0.60->0.50 (planner.py).

Comandos cortos sin keyword (varias variantes de "cuál es mi ip") deben rutear a
network en vivo (antes se borraban a ['session']). Y el smalltalk debe SEGUIR sin
tool de acción (el 4B responde conversacional). ≥4 variantes por la regla del user.

SEGURIDAD: TODAS las _impls mockeadas + syscall user32 neutralizado.
Reporte -> scripts/_out_peak_threshold.txt
"""
import ctypes
import os
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
os.environ["GEMMA4_ACCESSIBILITY_MODE"] = "normal"
os.environ.pop("GEMMA4_STREAM_TTS", None)

try:
    _orig_windll = ctypes.WinDLL
    _BLOCKED = {"SendInput", "keybd_event", "mouse_event", "BlockInput", "SetCursorPos"}

    class _SafeDLL:
        def __init__(self, dll):
            object.__setattr__(self, "_dll", dll)

        def __getattr__(self, name):
            if name in _BLOCKED:
                return lambda *a, **k: 0
            return getattr(object.__getattribute__(self, "_dll"), name)

    def _safe_windll(name, *a, **k):
        dll = _orig_windll(name, *a, **k)
        if isinstance(name, str) and "user32" in name.lower():
            return _SafeDLL(dll)
        return dll

    ctypes.WinDLL = _safe_windll
except Exception:
    pass

from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager

prof = get_active_profile()
apply_profile_to_env(prof)
mgr = get_shared_manager()
mgr.start(prof, wait_health=True, timeout_s=120)

from gemma4_agent.agent_core.agent import Gemma4Agent

agent = Gemma4Agent()
reg = agent.tools
for _name in list(reg._impls.keys()):
    reg._impls[_name] = (lambda n: (lambda args: {"ok": True, "tool": n, "mocked": True,
                                                  "verified": True, "action": (args or {}).get("action")}))(_name)

_NET = {"network", "device_settings"}
_ACTION = {"network", "web", "browser", "app", "media", "audio", "filesystem",
           "system", "device_settings", "notification", "reminder", "gui", "input",
           "whatsapp", "email", "vision", "computer_use"}

# (prompt, modo): 'net' debe usar network; 'small' NO debe usar tool de acción
CASES = [
    ("cuál es mi ip", "net"),
    ("qué ip tengo", "net"),
    ("mostrame mi dirección ip pública", "net"),
    ("cuál es mi ip en esta red", "net"),
    ("hola, buenas", "small"),
    ("gracias por todo", "small"),
    ("qué tal todo", "small"),
]

report, hits = [], 0
t0 = time.monotonic()
for p, mode in CASES:
    try:
        agent.history.clear()
    except Exception:
        pass
    try:
        r = agent.run_content(p)
        used = [getattr(e, "name", "?") for e in (getattr(r, "tool_events", []) or [])]
        reply = (getattr(r, "content", "") or "").replace("\n", " ")
    except Exception as exc:
        used, reply = ["<EXC>"], f"{type(exc).__name__}: {exc}"
    if mode == "net":
        good = bool(set(used) & _NET)
    else:
        good = not (set(used) & _ACTION)
    if good:
        hits += 1
    report.append(f"  [{'OK  ' if good else 'MISS'}] ({mode}) {p[:34]!r} -> {used} | {reply[:46]!r}")

dt = time.monotonic() - t0
head = f"{'='*60}\nPEAK-KEEP 0.50 LIVE: {hits}/{len(CASES)} OK ({dt:.0f}s)\n{'='*60}"
Path("scripts/_out_peak_threshold.txt").write_text(head + "\n" + "\n".join(report), encoding="utf-8")
print(head)
for line in report:
    print(line)
