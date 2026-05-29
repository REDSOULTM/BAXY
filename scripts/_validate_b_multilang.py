"""Valida que el fix B (media en el subset para play) sea MULTILINGÜE: pedidos de
reproducir música en FR/DE/PT/IT/ES deben ofrecer `media` (vía señal semántica,
embeddings 50+ idiomas — no regex ES+EN). Controles no-media NO deben sobre-incluir
media. Imprime el score semántico de media para calibrar el umbral."""
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
from gemma4_agent.routing.semantic_router import suggest_tools_scored

agent = Gemma4Agent()
for _n in list(agent.tools._impls.keys()):
    agent.tools._impls[_n] = (lambda n: (lambda a: {"ok": True, "tool": n, "mocked": True, "verified": True}))(_n)

# (frase, idioma, espera_media)
CASES = [
    ("Pon una canción en Spotify", "ES", True),
    ("Mets une chanson sur Spotify", "FR", True),
    ("Spiel ein Lied auf Spotify", "DE", True),
    ("Toca uma música no Spotify", "PT", True),
    ("Metti una canzone su Spotify", "IT", True),
    ("¿Qué hora es?", "ES-control", False),
    ("What time is it?", "EN-control", False),
]

print("=" * 80, flush=True)
fails = 0
for text, lang, want_media in CASES:
    try:
        _sc = suggest_tools_scored(text, k=12)
        media_score = next((s for t, s in _sc if t == "media"), 0.0)
        agent.run_content(text)
        subset = getattr(agent, "_last_router_subset", []) or []
    except Exception as e:
        print(f"  <EXC {type(e).__name__}: {e}>", flush=True); fails += 1; continue
    has_media = "media" in subset
    ok = (has_media == want_media)
    if not ok:
        fails += 1
    print(f"[{'OK  ' if ok else 'FALLA'}] {lang:10} {text!r}", flush=True)
    print(f"        media_score={media_score:.3f}  media_en_subset={has_media}  (esperado={want_media})  subset={subset}", flush=True)
print("=" * 80, flush=True)
print(f"[VEREDICTO B-multi] {'OK' if fails == 0 else f'FALLA ({fails})'}", flush=True)
