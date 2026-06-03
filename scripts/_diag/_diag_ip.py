from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from gemma4_agent.routing import planner as pl
from gemma4_agent.routing.semantic_router import suggest_tools_scored
from gemma4_agent.routing.intent_router import wants_knowledge, is_conversational
from gemma4_agent.safety_pkg.abstain_head import load_model, build_features
_PEAK_KEEP = pl._SEM_PEAK_KEEP
_PEAK_GAP = pl._SEM_PEAK_GAP
_VETO_P = getattr(pl, "_VETO_P", None)
print(f"_SEM_PEAK_KEEP={_PEAK_KEEP} _SEM_PEAK_GAP={_PEAK_GAP} _VETO_P={_VETO_P}")
_m = load_model()
for q in ["cuál es mi ip", "cual es mi ip", "cuál es mi IP", "mi ip cuál es"]:
    scored = suggest_tools_scored(q, k=12)
    sub_nosafe = pl.select_tool_names(q, pl.plan_mission(q))
    top = scored[0] if scored else (None, 0.0)
    gap = (scored[0][1] - scored[1][1]) if len(scored) >= 2 else top[1]
    confident_peak = top[1] >= _PEAK_KEEP and gap >= _PEAK_GAP
    try:
        from gemma4_agent.routing.intent_router import classify_intent
        si = classify_intent(q)
    except Exception:
        si = None
    feats = build_features(q, intent=si, scored=scored, keyword_fired=False)
    print(f"Q={q!r}")
    print(f"   sem top4: {[(t, round(s,3)) for t,s in scored[:4]]}  gap={gap:.3f} confident_peak={confident_peak}")
    print(f"   wants_knowledge={wants_knowledge(q)} is_conversational={is_conversational(q)}")
    print(f"   abstain: should_abstain={_m.should_abstain(feats)} p_no_tool={_m.p_no_tool(feats):.3f}")
    print(f"   subset(safety=False): {sub_nosafe}  -> network? {'network' in sub_nosafe}")
