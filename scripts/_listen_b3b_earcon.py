"""PRUEBA DE ESCUCHA de B3b (earcon de progreso) — la corrés VOS y juzgás el SONIDO.

Activa GEMMA4_PROGRESS_EARCON=1 y corre 4 pedidos que rutean a tools LENTAS
(web/visión/browser/computer_use). El earcon (sonido corto no-verbal) debe sonar
cuando arranca cada tool lenta. Vos escuchás y juzgás:
  - ¿Se oye bien / agradable (no molesto)?
  - ¿El timing está bien (suena al arrancar la tool, no tarde)?
  - ¿El volumen es adecuado?

SEGURO: las _impls están mockeadas (NINGUNA tool se ejecuta de verdad — sin red,
sin visión, sin tocar el SO) + syscall user32 neutralizado. PERO el earcon SÍ suena
real (sounddevice). Solo reproduce AUDIO (output), no input sintético → no cierra VS Code.

Uso:  python scripts/_listen_b3b_earcon.py
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
os.environ["GEMMA4_PROGRESS_EARCON"] = "1"   # B3b bajo prueba
os.environ.pop("GEMMA4_STREAM_TTS", None)

# red de seguridad: neutralizar input físico (no toca teclado/mouse)
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
from gemma4_agent.voice import earcon

agent = Gemma4Agent()
reg = agent.tools
for _name in list(reg._impls.keys()):
    reg._impls[_name] = (lambda n: (lambda args: {"ok": True, "tool": n, "mocked": True,
                                                  "verified": True, "action": (args or {}).get("action")}))(_name)

# pedidos que rutean a tools LENTAS (donde dispara el earcon)
PROMPTS = [
    "buscá noticias de hoy",            # -> web
    "qué hay en mi pantalla",           # -> vision
    "andá a wikipedia",                 # -> browser/web
    "buscá recetas de pizza en internet",  # -> web
]

print("\n" + "=" * 60)
print("PRUEBA DE ESCUCHA B3b — vas a oír un earcon por cada tool lenta.")
print("Escuchá si suena agradable, con buen timing y volumen.")
print("=" * 60)
for i, p in enumerate(PROMPTS, 1):
    earcon.reset_throttle()  # que cada uno suene (no throttle entre pruebas)
    print(f"\n[{i}/{len(PROMPTS)}] ▶ {p!r}  —  🔊 (escuchá el earcon ahora)")
    try:
        r = agent.run_content(p)
        used = [getattr(e, "name", "?") for e in (getattr(r, "tool_events", []) or [])]
        print(f"            tool ruteada: {used}")
    except Exception as exc:
        print(f"            <EXC {type(exc).__name__}: {exc}>")
    time.sleep(2.5)  # gap para oír el earcon distinto

print("\n" + "=" * 60)
print("FIN. ¿Cómo sonó? (agradable/molesto, timing, volumen). Decime y lo flipeo o ajusto.")
print("=" * 60)
