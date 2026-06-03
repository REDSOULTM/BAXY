"""LIVE (real, bypass): corre el flagship por run_content (el agente real, = la UI).
Browser navega + visión lee. NO mockea nada. Screenshots + reply para LEER."""
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
CMD = "andá al portal de la UNIEJ, entrá a Canvas y mostrame las tareas"
print(f"[run] {CMD!r}", flush=True)
t0 = time.time()
r = a.run_content(CMD)
dt = time.time() - t0
time.sleep(2.0)
ImageGrab.grab().convert("RGB").save(str((OUT / "canvas.png").resolve()))
rep = (getattr(r, "content", "") or "").strip()
ev = getattr(r, "tool_events", None) or []
print(f"[done] {dt:.1f}s  tools={[getattr(e,'name',None) for e in ev]}", flush=True)
print(f"[reply] {rep[:400]!r}", flush=True)
print("[screenshot] scripts/_diag/_live/canvas.png", flush=True)
