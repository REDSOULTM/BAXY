"""Validación EN VIVO de la CALIDAD de skills-autoinject (CLAUDE.md §3.5) para
decidir el flip a default-ON. Para cada pedido que matchea una skill:
  (a) DETERMINISTA: autoinject_skill confirma qué receta se inyecta.
  (b) LIVE: run_content contra el 4B real -> qué tools usa + reply (¿sigue la receta?).

SEGURIDAD: TODAS las _impls mockeadas + syscall user32 neutralizado. run_content
sin input físico = seguro (no cierra VS Code).

Reporte -> scripts/_out_skills_quality.txt
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
os.environ["GEMMA4_SKILLS_AUTOINJECT"] = "1"
os.environ["GEMMA4_SKILLS"] = "1"
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
from gemma4_agent.tools_pkg.skills_registry import autoinject_skill, scan_skills
from gemma4_agent.routing.semantic_router import embed

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

_skills = scan_skills()
# pedidos que DEBERÍAN matchear una skill (true positives)
QUERIES = [
    "se me cerró el juego de repente, ayudame a ver por qué se cae",
    "investigá sobre la fotosíntesis y resumime con las fuentes",
    "sacá una captura de pantalla y analizá qué hay en ella",
    "hacé un respaldo y después limpiá los archivos temporales",
    "programá una tarea que se repita todos los días a las 9",
]

report = []
t0 = time.monotonic()
for q in QUERIES:
    # (a) determinista: ¿qué skill matchea?
    sk_name, _ = autoinject_skill(q, _skills, embed_fn=embed)
    # (b) live
    try:
        agent.history.clear()
    except Exception:
        pass
    try:
        r = agent.run_content(q)
        used = [getattr(e, "name", "?") for e in (getattr(r, "tool_events", []) or [])]
        reply = (getattr(r, "content", "") or "").replace("\n", " ")
    except Exception as exc:
        used, reply = ["<EXC>"], f"{type(exc).__name__}: {exc}"
    report.append(f"\nQ: {q[:60]!r}")
    report.append(f"   skill inyectada (determinista): {sk_name or '(NINGUNA)'}")
    report.append(f"   live tools: {used}")
    report.append(f"   live reply: {reply[:90]!r}")

dt = time.monotonic() - t0
head = f"{'='*64}\nSKILLS QUALITY LIVE ({dt:.0f}s) — {len(_skills)} skills\n{'='*64}"
Path("scripts/_out_skills_quality.txt").write_text(head + "\n" + "\n".join(report), encoding="utf-8")
print(head)
for line in report:
    print(line)
