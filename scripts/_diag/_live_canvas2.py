"""LIVE: navega a la URL REAL del portal UNIEJ Chile (portal2.uniej.cl, user logueado)
y lee las tareas por visión. 2 pasos por run_content (evita partir la URL en la cadena)."""
from __future__ import annotations
import os, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager
prof = get_active_profile(); apply_profile_to_env(prof)
get_shared_manager().start(prof, wait_health=True, timeout_s=120); print("[boot] OK", flush=True)
from PIL import ImageGrab
from gemma4_agent.agent_core.agent import Gemma4Agent

OUT = Path("scripts/_diag/_live"); OUT.mkdir(parents=True, exist_ok=True)
a = Gemma4Agent()

def live(tag, cmd, wait):
    print(f"\n[run:{tag}] {cmd!r}", flush=True)
    r = a.run_content(cmd)
    time.sleep(wait)
    ImageGrab.grab().convert("RGB").save(str((OUT / f"c2_{tag}.png").resolve()))
    ev = getattr(r, "tool_events", None) or []
    print(f"[{tag}] tools={[getattr(e,'name',None) for e in ev]}", flush=True)
    print(f"[{tag}] reply={(getattr(r,'content','') or '').strip()[:400]!r}", flush=True)

# 1) navegar a la URL REAL (browser usa tu sesión logueada)
live("nav", "abrí la página https://portal2.uniej.cl", 6.0)
# 2) leer las tareas por visión (lee lo que esté en pantalla)
live("read", "leeme las tareas que tengo que hacer en pantalla", 2.0)
print("\n[done]", flush=True)
