"""Verifica el fix de chain-context (nav in-app): "abrí <app> y andá al canal/destino X"
-> clause2 rutea a cu(open_chat/open_url) con el contexto de la app. + regresiones:
poné rock sigue a media, escribí sigue a type, nav standalone sigue a browser."""
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

cap = {"dispatch": [], "plans": []}
_real = ToolRegistry.execute
ToolRegistry.execute = lambda self, n, a: (cap["dispatch"].append((n, dict(a or {}))) or
    (_real(self, n, a) if n == "computer_use" else {"ok": True, "_mock": True}))
cu.PlanExecutor.execute = lambda self, plan, *a, **k: (cap["plans"].append(plan) or
    {"ok": True, "verified": True, "steps": [{"op": p.get("op"), "arg": p.get("arg")} for p in (plan or [])]})
_OPEN = {"discord", "spotify", "navegador", "chrome", "notepad", "bloc", "notas", "calculadora", "calc", "word"}
Gemma4Agent._window_title_in_text = lambda self, t: ("App - " + t) if (
    {w for w in re.findall(r"\w+", (t or "").lower()) if len(w) >= 4} & _OPEN) else None

def run(msg):
    a = Gemma4Agent(); cap["dispatch"].clear(); cap["plans"].clear()
    r = a.run_content(msg)
    return list(cap["dispatch"]), list(cap["plans"]), (getattr(r, "content", "") or "").strip()

def ops_of(plans):
    return [(p.get("op"), str(p.get("arg"))[:22]) for pl in plans for p in (pl or [])]

print("\n##### CHAIN-NAV (clause2 debe rutear a cu open_chat/open_url) #####")
CHAIN = [
    ("abrí Discord y andá al canal general", ("open_chat",)),
    ("abrí Discord y entrá al canal general", ("open_chat", "open_voice")),
    ("abrí el navegador y andá a youtube", ("open_url",)),
    ("abrí Spotify y andá a la playlist de rock", ("type", "open_url", "focus_app")),
]
for u, want in CHAIN:
    disp, plans, rep = run(u)
    ops = ops_of(plans)
    hit = any(o[0] in want for o in ops)
    print(f"  [{'OK' if hit else 'XX'}] {u!r:46} plan={ops}")
    if not ops: print(f"        tools={[n for n,_ in disp]} reply={rep[:60]!r}")

print("\n##### REGRESIÓN (no debe cambiar) #####")
REG = [
    ("abrí Spotify y poné rock", "media NO nav"),        # poné rock -> media
    ("abrí la calculadora y escribí 5+5", "type"),       # escribí -> type macro
    ("andá a la página de pivigames", "browser standalone"),  # sin chain -> browser
    ("abrí Discord y qué hora es", "no-nav clause2"),     # clause2 no es nav
]
for u, note in REG:
    disp, plans, rep = run(u)
    ops = ops_of(plans)
    tools = [n for n, _ in disp]
    print(f"  {u!r:42} [{note}] tools={tools} plan={ops}")
print("[done]")
