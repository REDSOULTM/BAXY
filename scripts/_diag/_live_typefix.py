"""LIVE: el fix de type-in-CLOSED-app. "escribí X en el bloc de notas" con Notepad
CERRADO debe abrir Notepad + tipear (cu), NO caer a notes_tasks."""
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
CMD = "escribí GEMMA TYPEFIX 999 en el bloc de notas"
print(f"[run] {CMD!r}", flush=True)
r = a.run_content(CMD)
time.sleep(3.5)
ImageGrab.grab().convert("RGB").save(str((OUT / "typefix.png").resolve()))
ev = getattr(r, "tool_events", None) or []
tools = [getattr(e, "name", None) for e in ev]
print(f"[result] tools={tools} (esperado: computer_use, NO notes_tasks)", flush=True)
print(f"[reply] {(getattr(r,'content','') or '').strip()[:120]!r}", flush=True)
print("[screenshot] scripts/_diag/_live/typefix.png", flush=True)
