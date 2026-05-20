"""Router evaluation harness — measures routing quality over the full
corpus of real historical queries, NOT a hand-picked test set.

Sprint 8 (2026-05-20): the operator reported the router sometimes leaves
the needed tool out of the subset. We extracted every unique real query
from the traces (gemma4_agent/data/router_eval_corpus.jsonl) and use them
as the evaluation set. The goal is a UNIVERSAL routing improvement, so we
score against intent categories — not the specific failing strings.

Two metrics:
  1. info_recall: of queries whose INTENT is informational ("what is X",
     "tell me about X", "how did X die"), how many get a knowledge tool
     (web/knowledge/fact_check/local_search) in the subset?
  2. action_preservation: of queries whose intent is a PC action
     ("open X", "close Y"), the action tool must still be present
     (guard against the info-fix stealing action slots → no regression).

Run:
    python scripts/router_eval.py
    python scripts/router_eval.py --show-fails
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CORPUS = ROOT / "gemma4_agent" / "data" / "router_eval_corpus.jsonl"

KNOWLEDGE_TOOLS = {"web", "knowledge", "fact_check", "local_search"}

# Intent oracles — deliberately BROADER than the planner's own keyword
# list, and independent of it, so they form a real test (if we just
# copied the planner's regex the test would be circular). These encode
# the *concept* of each intent, multilingual.
_INFO_INTENT = re.compile(
    r"\b("
    r"que es|qué es|que son|qué son|que era|qué era|"
    r"de que|de qué|"                       # "de qué trata", "de qué murió"
    r"quien es|quién es|quien era|quién era|quien fue|quién fue|quien|quién|"
    r"cual es|cuál es|cuales son|cuáles son|"
    r"cuando|cuándo|donde|dónde|por que|por qué|porque|como funciona|cómo funciona|"
    r"cuanto cuesta|cuánto cuesta|cuanto vale|cuánto vale|"
    r"hablame|háblame|cuentame|cuéntame|sabes de|sabes quien|sabes quién|"
    r"saber de|saber sobre|info de|informacion de|información de|informacion sobre|"
    r"que sabes de|qué sabes de|dime sobre|dime de|"
    r"what is|what are|who is|who was|tell me about|how does|why is|"
    r"when did|when was|where is|how did|search for|look up|google"
    r")\b",
    re.IGNORECASE,
)

# A PC action verb. If present AND no info intent, it's an action query.
_ACTION_INTENT = re.compile(
    r"\b("
    r"abre|abrir|abri|cierra|cerrar|open|close|click|clickea|"
    r"instala|instalar|install|borra|borrar|delete|elimina|copia|copiar|"
    r"pon|poné|reproduce|reproducir|play|pausa|pause|stop|detene|"
    r"screenshot|captura|capturá|"
    r"envia|enviá|manda|mandá|send|escribe|escribí|escribile|type|"
    r"maximiza|minimiza|mueve|cambia|sube|baja|silencia|mutea"
    r")\b",
    re.IGNORECASE,
)


# Things that look interrogative but are NOT web-knowledge queries:
#  - about the agent itself ("quién eres", "quién soy", "qué sabes hacer")
#  - about LOCAL state ("dónde dejé el archivo", "dónde puse")
#  - routine definitions ("cuando diga X haz Y") — config, not a question
_SELF_OR_LOCAL = re.compile(
    r"\b("
    r"quien eres|quién eres|quien sos|quién sos|que eres|qué eres|quien soy|quién soy|"
    r"que sabes hacer|qué sabes hacer|que puedes hacer|qué puedes hacer|"
    r"como te llamas|cómo te llamas|tu nombre|"
    r"who are you|what can you do|what are you|"
    r"donde deje|dónde dejé|donde puse|dónde puse|donde guarde|dónde guardé|"
    r"donde dejaste|dónde dejaste|donde posiste|dónde posiste|"
    r"cuando dija|cuando diga|cuando digo|cuando prenda|cuando se inic|cuando se prenda|"
    r"cuando inicie|al iniciar|al prender|when i say"
    r")\b",
    re.IGNORECASE,
)


def classify_intent(q: str) -> str:
    """Return 'info', 'action', 'mixed', or 'other'.

    'info' = a question about an EXTERNAL entity/fact (needs web/knowledge).
    We exclude self/local/routine interrogatives so the oracle reflects
    what genuinely needs a web lookup — otherwise we'd 'fix' the router
    into stuffing web everywhere, which is its own bug.
    """
    if _SELF_OR_LOCAL.search(q):
        # Self/local/routine — not a web-knowledge query even if interrogative.
        has_action = bool(_ACTION_INTENT.search(q))
        return "action" if has_action else "other"
    has_info = bool(_INFO_INTENT.search(q))
    has_action = bool(_ACTION_INTENT.search(q))
    if has_info and not has_action:
        return "info"
    if has_info and has_action:
        return "mixed"
    if has_action:
        return "action"
    return "other"


def run_router(q: str) -> list[str]:
    """Run the REAL planner.select_tool_names over a query."""
    from gemma4_agent.planner import select_tool_names, plan_mission
    plan = plan_mission(q)
    return select_tool_names(q, plan, safety_enabled=False)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show-fails", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    if not CORPUS.exists():
        print(f"corpus missing: {CORPUS}")
        return 1

    rows = [json.loads(l) for l in CORPUS.read_text(encoding="utf-8").splitlines() if l.strip()]
    if args.limit:
        rows = rows[: args.limit]

    info_total = info_ok = 0
    mixed_total = mixed_ok = 0
    action_total = action_ok = 0
    info_fails: list[tuple[str, list[str]]] = []
    action_fails: list[tuple[str, list[str]]] = []

    for r in rows:
        q = r["q"]
        intent = classify_intent(q)
        subset = set(run_router(q))
        if intent in ("info", "mixed"):
            has_knowledge = bool(subset & KNOWLEDGE_TOOLS)
            if intent == "info":
                info_total += 1
                if has_knowledge:
                    info_ok += 1
                else:
                    info_fails.append((q, sorted(subset)))
            else:
                mixed_total += 1
                if has_knowledge:
                    mixed_ok += 1
                else:
                    info_fails.append((q, sorted(subset)))
        if intent in ("action", "mixed"):
            # action_preservation: at least one action-domain tool present.
            # We can't know the exact tool without semantics, so we check
            # the subset is non-trivial (more than just session/safety).
            action_domain = subset - {"session", "safety", "state", "verify"}
            action_total += 1
            if action_domain:
                action_ok += 1
            else:
                action_fails.append((q, sorted(subset)))

    print("=" * 60)
    print("Router eval over real historical corpus")
    print("=" * 60)
    print(f"  corpus size: {len(rows)} unique queries")
    print()
    print(f"  INFO recall:   {info_ok}/{info_total} "
          f"= {info_ok/max(1,info_total):.3f}  (knowledge tool in subset)")
    print(f"  MIXED recall:  {mixed_ok}/{mixed_total} "
          f"= {mixed_ok/max(1,mixed_total):.3f}")
    print(f"  ACTION preserve: {action_ok}/{action_total} "
          f"= {action_ok/max(1,action_total):.3f}  (action tool present)")
    print()
    print(f"  info misses: {len(info_fails)}, action misses: {len(action_fails)}")

    if args.show_fails:
        print("\n--- INFO misses (no knowledge tool) ---")
        for q, sub in info_fails[:40]:
            print(f"  {q!r}\n     subset={sub}")
        if action_fails:
            print("\n--- ACTION misses (subset collapsed) ---")
            for q, sub in action_fails[:40]:
                print(f"  {q!r}\n     subset={sub}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
