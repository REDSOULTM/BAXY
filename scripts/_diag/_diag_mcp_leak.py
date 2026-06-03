from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from gemma4_agent.routing import semantic_router as SR
from gemma4_agent.routing import planner as pl
from gemma4_agent.routing.semantic_router import suggest_tools_scored
from gemma4_agent.routing.exemplar_router import match as ex_match

print(f"_MCP_PEAK_KEEP={getattr(pl, '_MCP_PEAK_KEEP', None)}")
SR.enroll_mcp_tools([
    {"id": "mcp__weather__weather_forecast", "description": "weather forecast temperature"},
])
RELEVANT = ["qué temperatura hace en Madrid", "qué clima hace hoy", "va a llover", "qué tiempo hace"]
IRRELEVANT = ["subí el volumen", "qué hora es", "abre steam", "mutea", "qué día es hoy", "cuánta RAM tengo"]
print("--- RELEVANT (MCP SHOULD promote) ---")
for q in RELEVANT:
    scored = suggest_tools_scored(q, k=14)
    s = next((sc for t, sc in scored if t.startswith("mcp__")), None)
    print(f"   {q!r}: mcp_score={s}")
print("--- IRRELEVANT (MCP should NOT leak) ---")
for q in IRRELEVANT:
    scored = suggest_tools_scored(q, k=14)
    s = next((sc for t, sc in scored if t.startswith("mcp__")), None)
    print(f"   {q!r}: mcp_score={s}")
print("--- detail for the 2 test queries ---")
for q in ["subí el volumen", "qué hora es"]:
    scored = suggest_tools_scored(q, k=14)
    mcp_score = next((s for t, s in scored if t.startswith("mcp__")), None)
    ex = ex_match(q)
    ex_desc = "None" if ex is None else f"abstain={ex.abstain} tools={list(ex.tools)}"
    sub = pl.select_tool_names(q, pl.plan_mission(q))
    leaked = [t for t in sub if t.startswith("mcp__")]
    print(f"Q={q!r}")
    print(f"   exemplar: {ex_desc}")
    print(f"   mcp_score={mcp_score}  subset={sub}")
    print(f"   LEAK? {leaked}")
SR.enroll_mcp_tools([])
