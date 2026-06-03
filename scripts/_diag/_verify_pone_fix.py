"""Verifica end-to-end que el fix del profile-intent rutea los 'poné mi nombre en
app' a cu-tipeo (no al volcado de perfil), sin romper las queries reales de perfil."""
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
_OPEN = {"notepad", "bloc", "bloque", "notas", "word", "calculadora", "calc"}
Gemma4Agent._window_title_in_text = lambda self, t: ("App - " + t) if (
    {w for w in re.findall(r"\w+", (t or "").lower()) if len(w) >= 4} & _OPEN) else None

def run(msg):
    a = Gemma4Agent(); cap["dispatch"].clear(); cap["plans"].clear()
    r = a.run_content(msg)
    return list(cap["dispatch"]), list(cap["plans"]), (getattr(r, "content", "") or "").strip()

TYPE_CASES = [
    "en notepad poné mi nombre", "poné mi nombre en el bloc de notas",
    "poné mi nombre en el word", "en el bloc de notas poné hola",
    "abrí el bloc de notas y poné hola",
]
print("\n##### poné-tipeo (debe ir a cu plan type, NO al perfil) #####")
for u in TYPE_CASES:
    disp, plans, rep = run(u)
    ops = [(p.get("op"), str(p.get("arg"))[:20]) for pl in plans for p in (pl or [])]
    has_type = any(o[0] in ("type", "fill_field") for o in ops)
    is_profile = "observaciones" in rep.lower() or "aprendí observando" in rep.lower()
    tag = "OK-type" if has_type else ("PERFIL!" if is_profile else "?")
    tools = " -> ".join(n for n, _ in disp) or "(short-circuit)"
    print(f"  [{tag:8}] {u!r:46} | {tools} plan={ops}")
    if not has_type and not ops:
        print(f"            reply={rep[:70]!r}")

print("\n##### no-regresión: query REAL de perfil (debe volcar el perfil) #####")
for u in ["qué sabés de mí", "olvidate de lo que sabés de mí"]:
    disp, plans, rep = run(u)
    is_profile = "observaciones" in rep.lower() or "borré" in rep.lower() or "aprendí" in rep.lower()
    print(f"  [{'OK' if is_profile else 'XX'}] {u!r:40} reply={rep[:60]!r}")
print("[done]")
