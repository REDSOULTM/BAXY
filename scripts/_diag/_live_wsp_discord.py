"""LIVE (real, bypass): chain WhatsApp (envío real a Música, autorizado) + chain Discord,
por run_content (el agente real). Screenshots + reply por comando."""
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
    try:
        t0 = time.time(); r = a.run_content(cmd); dt = time.time() - t0
    except Exception as e:
        print(f"[{tag}] EXC {type(e).__name__}: {e}", flush=True); return
    time.sleep(wait)
    ImageGrab.grab().convert("RGB").save(str((OUT / f"{tag}.png").resolve()))
    ev = getattr(r, "tool_events", None) or []
    print(f"[{tag}] {dt:.1f}s tools={[getattr(e,'name',None) for e in ev]}", flush=True)
    print(f"[{tag}] reply={(getattr(r,'content','') or '').strip()[:220]!r}", flush=True)

# 1) WhatsApp chain — envío REAL a Música (autorizado)
live("wsp", "abrí WhatsApp y mandale a Música que el envío a grupos por voz ya funciona", 3.0)
# 2) Discord chain — abrir + navegar al canal
live("discord", "abrí Discord y andá al canal general", 3.0)
print("\n[done] screenshots en scripts/_diag/_live/", flush=True)
