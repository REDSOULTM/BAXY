"""BATERÍA COMPREHENSIVA EN VIVO (real, bypass): corre todo el computer-use por
run_content (el agente real). Captura tool-chain + reply + screenshot por comando."""
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

OUT = Path("scripts/_diag/_live/battery"); OUT.mkdir(parents=True, exist_ok=True)
a = Gemma4Agent()

TESTS = [
    ("open_calc",   "abrí la calculadora",                     2.5),
    ("type_np",     "escribí GEMMA TEST 555 en el bloc de notas", 4.0),
    ("screenshot",  "sacá una captura de pantalla",            2.0),
    ("volume",      "subí el volumen al 60",                   2.0),
    ("brightness",  "bajá el brillo",                          2.0),
    ("time",        "qué hora es",                             1.0),
    ("math",        "cuánto es 47 por 8",                      1.0),
    ("web",         "buscá el clima de Santiago hoy",          3.0),
    ("vision",      "mostrame qué hay en la pantalla",         2.0),
    ("chain_media", "abrí spotify y poné rock",                4.0),
]

for tag, cmd, wait in TESTS:
    try:
        t0 = time.time(); r = a.run_content(cmd); dt = time.time() - t0
    except Exception as e:
        print(f"[{tag}] EXC {type(e).__name__}: {str(e)[:80]}", flush=True); continue
    time.sleep(wait)
    try: ImageGrab.grab().convert("RGB").save(str((OUT / f"{tag}.png").resolve()))
    except Exception: pass
    ev = getattr(r, "tool_events", None) or []
    tools = [getattr(e, "name", None) for e in ev]
    rep = (getattr(r, "content", "") or "").strip()
    print(f"[{tag:12}] {dt:4.1f}s tools={tools} | {rep[:100]!r}", flush=True)
print("\n[done] screenshots en scripts/_diag/_live/battery/", flush=True)
