"""Validación EN VIVO de que los 3 flips funcionan POR DEFECTO (sin env vars).

Tras flipear file-routing + error-recovery + skills-autoinject a default-ON, esto
confirma la conducta de PRODUCCIÓN real (no seteamos ningún GEMMA4_* — usamos los
nuevos defaults del código). Es la "validación en vivo de cada tool" pedida.

SEGURIDAD: TODAS las _impls mockeadas + syscall user32 neutralizado. NO env vars.
Reporte -> scripts/_out_flips_default.txt
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
# NO seteamos GEMMA4_FILE_TOOL_ROUTING / SKILLS_AUTOINJECT / ERROR_RECOVERY:
# queremos probar los DEFAULTS del código (ahora ON).
for _v in ("GEMMA4_FILE_TOOL_ROUTING", "GEMMA4_SKILLS_AUTOINJECT",
           "GEMMA4_ERROR_RECOVERY", "GEMMA4_STREAM_TTS"):
    os.environ.pop(_v, None)

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

from gemma4_agent.agent_core.agent import (
    Gemma4Agent, _file_tool_routing_enabled, _skills_autoinject_enabled,
    _error_recovery_enabled,
)

# sanity: confirmar que los defaults están ON (sin env vars)
gates = (f"file_routing={_file_tool_routing_enabled()} "
         f"skills_autoinject={_skills_autoinject_enabled()} "
         f"error_recovery={_error_recovery_enabled()}")

agent = Gemma4Agent()
reg = agent.tools
for _name in list(reg._impls.keys()):
    reg._impls[_name] = (lambda n: (lambda args: {"ok": True, "tool": n, "mocked": True,
                                                  "verified": True, "action": (args or {}).get("action")}))(_name)

# (prompt, set aceptable, NO-debe, etiqueta)
CASES = [
    ("buscá un word en mis documentos", {"filesystem", "document"}, {"web"}, "file-routing"),
    ("listá los archivos de descargas", {"filesystem"}, {"web"}, "file-routing"),
    ("buscá un pdf en el escritorio", {"filesystem", "document"}, {"web"}, "file-routing"),
    ("sacá una captura de pantalla y analizá qué hay", {"gui", "vision"}, set(), "skills"),
    ("qué hora es", {"system"}, set(), "control"),
    ("buscá noticias de hoy", {"web", "browser"}, {"filesystem"}, "control-web"),
    ("hola, buenas", set(), {"filesystem", "web", "system"}, "control-smalltalk"),
]

report, hits = [f"gates (sin env vars): {gates}"], 0
t0 = time.monotonic()
for p, accepted, forbidden, tag in CASES:
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
    if accepted:
        good = bool(set(used) & accepted) and not (set(used) & forbidden)
    else:  # smalltalk: NO debe usar tools de acción
        good = not (set(used) & forbidden)
    if good:
        hits += 1
    report.append(f"  [{'OK  ' if good else 'MISS'}] ({tag}) {p[:38]!r} -> {used} | {reply[:46]!r}")

dt = time.monotonic() - t0
head = f"{'='*62}\nFLIPS-BY-DEFAULT LIVE: {hits}/{len(CASES)} OK ({dt:.0f}s)\n{'='*62}"
Path("scripts/_out_flips_default.txt").write_text(head + "\n" + "\n".join(report), encoding="utf-8")
print(head)
for line in report:
    print(line)
