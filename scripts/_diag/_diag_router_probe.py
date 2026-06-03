"""Diagnostic probe: route queries through the planner layers and print where
each tool subset decision is made. Throwaway — for diagnosing the FT-3ep state.
NOT a keyword map; it just instruments the existing planner/encoder/head.
"""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gemma4_agent.routing.planner import select_tool_names, plan_mission
from gemma4_agent.routing.semantic_router import suggest_tools_scored

def _exemplar(q):
    try:
        from gemma4_agent.routing.exemplar_router import match as m
        r = m(q)
        if r is None:
            return "None"
        return f"abstain={r.abstain} tools={list(r.tools)}"
    except Exception as e:
        return f"ERR {e}"

def _intent(q):
    try:
        from gemma4_agent.routing.intent_router import classify_intent, wants_knowledge, is_conversational
        si = classify_intent(q)
        fields = {}
        for f in ("chitchat", "info", "action", "selfref"):
            fields[f] = round(getattr(si, f, float("nan")), 3) if si is not None else None
        return f"{fields} wants_knowledge={wants_knowledge(q)} conversational={is_conversational(q)}"
    except Exception as e:
        return f"ERR {e}"

def _abstain(q, scored):
    try:
        from gemma4_agent.safety_pkg.abstain_head import load_model, build_features, is_enabled
        if not is_enabled():
            return "head DISABLED"
        m = load_model()
        if m is None:
            return "head None"
        try:
            from gemma4_agent.routing.intent_router import classify_intent
            si = classify_intent(q)
        except Exception:
            si = None
        feats = build_features(q, intent=si, scored=scored, keyword_fired=False)
        return f"should_abstain={m.should_abstain(feats)} p_no_tool={m.p_no_tool(feats):.3f}"
    except Exception as e:
        return f"ERR {e}"

QUERIES = [
    # --- failing in tests ---
    ("abre el navegador", "browser/app (S3c)"),
    ("Abri el navegador", "browser/app (S3c)"),
    ("abre el navegador predeterminado", "browser/app (S3c)"),
    ("que recuerdas de mi", "memory"),
    ("cual es mi ip", "network (peak-keep)"),
    ("que es pytest", "ABSTAIN []"),
    ("hola", "ABSTAIN []"),
    ("gracias", "ABSTAIN []"),
    # --- controls that should work ---
    ("abre steam", "steam/app"),
    ("mutea", "audio"),
    ("de que trata Dune", "web/knowledge"),
    ("quien es Batman", "web/knowledge"),
    # --- terse cluster (handoff live-verify) ---
    ("subi el volumen", "audio"),
    ("conta 10 minutos", "timer/reminder"),
    ("escribi 2+2", "gui/compute"),
]

for q, want in QUERIES:
    scored = suggest_tools_scored(q, k=8)
    sub = select_tool_names(q, plan_mission(q), safety_enabled=True)
    print("=" * 70)
    print(f"Q: {q!r}   (want: {want})")
    print(f"  SUBSET: {sub}")
    print(f"  exemplar: {_exemplar(q)}")
    print(f"  intent:   {_intent(q)}")
    print(f"  abstain:  {_abstain(q, scored)}")
    top = [(t, round(s, 3)) for t, s in scored[:6]]
    print(f"  sem top6: {top}")
