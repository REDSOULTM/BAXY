"""Validación EN VIVO del fix de routing reminder/notification (gap harness item4).

"recordame [acción] [tiempo]" debe rutear a notification/reminder (no a
session/cancel, memory ni calendar). Y los CONTROLES de memory ("recordame que
prefiero X") deben SEGUIR yendo a memory (no romper la desambiguación).

Fix = enriquecimiento multilingüe de TOOL_DESCRIPTIONS en semantic_router.py
(mecanismo aprobado CLAUDE.md §3; NO keyword-list). Las descripciones se
re-encodean al arrancar -> server fresco refleja el cambio.

SEGURIDAD: TODAS las _impls mockeadas + syscall user32 neutralizado.
Reporte -> scripts/_out_reminder_routing.txt
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

# (prompt, set aceptable, NO-debe-incluir)
CASES = [
    ("recordame comprar pan a las 5", {"notification", "reminder"}, {"memory", "session"}),
    ("recordame llamar a mamá en una hora", {"notification", "reminder"}, {"memory", "session"}),
    ("recordame sacar la basura mañana", {"notification", "reminder"}, {"memory", "session"}),
    ("recordame la reunión a las 9am", {"notification", "reminder", "local_calendar"}, {"memory", "session"}),
    # --- CONTROLES memory: deben SEGUIR yendo a memory (no romper) ---
    ("recordame que prefiero el café sin azúcar", {"memory"}, {"notification"}),
    ("recordame que soy alérgico al maní", {"memory"}, {"notification"}),
]

report, hits = [], 0
t0 = time.monotonic()
for p, accepted, forbidden in CASES:
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
    good = bool(set(used) & accepted) and not (set(used) & forbidden)
    if good:
        hits += 1
    report.append(f"  [{'OK  ' if good else 'MISS'}] {p[:40]!r} -> {used} | {reply[:50]!r}")

dt = time.monotonic() - t0
head = (f"{'='*60}\nREMINDER ROUTING: {hits}/{len(CASES)} OK ({dt:.0f}s)\n{'='*60}")
Path("scripts/_out_reminder_routing.txt").write_text(head + "\n" + "\n".join(report), encoding="utf-8")
print(head)
for line in report:
    print(line)
