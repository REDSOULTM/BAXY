"""Valida el fix B: un pedido de reproducir música SIEMPRE debe ofrecer `media`
en el subset del router (antes el exemplar/plan podía dejarlo afuera → el LLM caía
a `web` y abría una URL random). LLM real + tools mockeadas (seguro)."""
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

# (frase, repeticiones) — la exacta que falló se corre 3x (era intermitente)
CASES = [
    ("Pon una canción en Spotify", 3),
    ("pon una cancion en spotify", 1),
    ("pon música", 1),
    ("reproducí algo de rock", 1),
    ("pon una canción de michael jackson en spotify", 1),
]

print("=" * 76, flush=True)
fails = 0
for text, reps in CASES:
    for i in range(reps):
        try:
            agent.run_content(text)
            subset = getattr(agent, "_last_router_subset", []) or []
        except Exception as e:
            print(f"  <EXC {type(e).__name__}: {e}>", flush=True); fails += 1; continue
        has_media = "media" in subset
        if not has_media:
            fails += 1
        print(f"[{'OK  ' if has_media else 'FALLA'}] {text!r}  media_en_subset={has_media}  subset={subset}", flush=True)
print("=" * 76, flush=True)
print(f"[VEREDICTO B] {'OK (media SIEMPRE en el subset)' if fails == 0 else f'FALLA ({fails} sin media)'}", flush=True)
