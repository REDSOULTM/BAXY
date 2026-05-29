"""Validación EN VIVO dirigida del fix de routing filesystem (gap harness item4).

Confirma que con GEMMA4_FILE_TOOL_ROUTING=1, "buscá un word en documentos" rutea a
filesystem (local), NO a web (internet) — y que la búsqueda web genérica NO se rompe
(control). Solo 6 turnos -> no degrada la box (vs 60 del harness completo).

SEGURIDAD: TODAS las _impls mockeadas a no-op + syscall user32 (SendInput/keybd/mouse)
neutralizado. run_content sin input físico = seguro (no cierra VS Code).

Reporte -> scripts/_out_filesystem_routing.txt
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
os.environ["GEMMA4_FILE_TOOL_ROUTING"] = "1"  # el fix bajo prueba
os.environ.pop("GEMMA4_STREAM_TTS", None)

# --- RED DE SEGURIDAD: neutralizar el syscall de input físico (cualquier path) ---
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

# (prompt, set de tools aceptables, NO-debe-incluir)
CASES = [
    ("buscá un word en mis documentos", {"filesystem", "document"}, {"web"}),
    ("listá los archivos de descargas", {"filesystem"}, {"web"}),
    ("buscá un pdf en el escritorio", {"filesystem", "document"}, {"web"}),
    ("mostrame las fotos de mi carpeta", {"filesystem"}, {"web"}),
    # --- controles: búsqueda web genérica NO debe ir a filesystem ---
    ("buscá noticias de hoy", {"web", "browser"}, {"filesystem"}),
    ("qué es la fotosíntesis", {"web", "browser"}, {"filesystem"}),
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
head = (f"{'='*60}\nFILESYSTEM ROUTING (flag ON): {hits}/{len(CASES)} OK ({dt:.0f}s)\n{'='*60}")
Path("scripts/_out_filesystem_routing.txt").write_text(head + "\n" + "\n".join(report), encoding="utf-8")
print(head)
for line in report:
    print(line)
