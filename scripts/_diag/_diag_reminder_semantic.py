"""Diagnóstico CPU (sin LLM): ranking semántico crudo + subset final del planner
para los fraseos de reminder. Determinista, rápido, seguro. Diagnostica si el fix
de descripciones movió notification/memory arriba, y si el subset final los incluye.
"""
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent.parent  # scripts/_diag/ -> repo root
sys.path.insert(0, str(ROOT))
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")

from gemma4_agent.routing import semantic_router as sr

PHRASES = [
    "recordame comprar pan a las 5",
    "recordame llamar a mamá en una hora",
    "recordame sacar la basura mañana",
    "recordame la reunión a las 9am",
    "recordame que prefiero el café sin azúcar",
    "recordame que soy alérgico al maní",
]

print("=== RANKING SEMÁNTICO CRUDO (top-8, suggest_tools_scored) ===")
for p in PHRASES:
    try:
        scored = sr.suggest_tools_scored(p, k=8, min_score=0.0)
        pretty = ", ".join(f"{n}:{s:.2f}" for n, s in scored)
    except Exception as exc:
        pretty = f"<EXC {type(exc).__name__}: {exc}>"
    print(f"\n{p!r}\n   {pretty}")

# --- subset final del planner (si la firma lo permite) ---
print("\n\n=== SUBSET FINAL DEL PLANNER (select_tool_names) ===")
try:
    from gemma4_agent.routing import planner as pl
    fn = getattr(pl, "select_tool_names", None)
    if fn is None:
        print("  (no se encontró select_tool_names)")
    else:
        for p in PHRASES:
            try:
                plan = pl.plan_mission(p)
                out = fn(p, plan)
            except Exception as exc:
                out = f"<EXC {type(exc).__name__}: {exc}>"
            print(f"  {p[:40]!r} -> {out}")
except Exception as exc:
    print(f"  <EXC {type(exc).__name__}: {exc}>")
