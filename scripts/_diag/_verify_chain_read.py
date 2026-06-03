"""Verifica el chain-read (flagship): tras navegar a una página, "mostrame/ve las
tareas" -> vision.describe_screen (no notes_tasks local). + regresión."""
from __future__ import annotations
import os, sys, re
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
from gemma4_agent.tools_pkg.tools import ToolRegistry
from gemma4_agent.computer_use_pkg import computer_use as cu
from gemma4_agent.agent_core.agent import Gemma4Agent

cap = {"dispatch": []}
_real = ToolRegistry.execute
ToolRegistry.execute = lambda self, n, a: (cap["dispatch"].append(n) or
    (_real(self, n, a) if n == "computer_use" else {"ok": True, "_mock": True, "description": "(mock) tareas: T1, T2"}))
cu.PlanExecutor.execute = lambda self, plan, *a, **k: {"ok": True, "verified": True, "steps": []}
_OPEN = {"discord", "spotify", "navegador", "chrome", "canvas", "uniej"}
Gemma4Agent._window_title_in_text = lambda self, t: ("App - " + t) if (
    {w for w in re.findall(r"\w+", (t or "").lower()) if len(w) >= 4} & _OPEN) else None

def run(msg):
    a = Gemma4Agent(); cap["dispatch"].clear()
    r = a.run_content(msg)
    return list(cap["dispatch"]), (getattr(r, "content", "") or "").strip()

print("\n##### CHAIN-READ (clause final -> vision, NO notes_tasks) #####")
for u in ["andá al portal de la UNIEJ, entrá a Canvas y mostrame las tareas",
          "abrí el navegador y leeme lo que dice la página",
          "abrí youtube y mostrame los videos"]:
    disp, rep = run(u)
    hit = "vision" in disp and "notes_tasks" not in disp
    print(f"  [{'OK' if hit else 'XX'}] {u!r:60} tools={disp}")

print("\n##### REGRESIÓN #####")
for u, note in [("abrí Spotify y poné rock", "media (no vision)"),
                ("mostrame las tareas", "standalone -> notes_tasks (sin chain)"),
                ("abrí Discord y andá al canal general", "nav (no vision)")]:
    disp, rep = run(u)
    print(f"  {u!r:46} [{note}] tools={disp}")
print("[done]")
