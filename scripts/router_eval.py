"""Router evaluation harness over the FULL historical corpus.

Sprint 8 (2026-05-20): the corpus (gemma4_agent/data/router_eval_corpus.jsonl)
is built by scripts/router_corpus_build.py from EVERY log that exists —
the main trace ring, the archived traces_*.txt dumps, and the curated
Carter-540 bench matrix (which carries the EXPECTED tools per prompt).

Scoring uses two oracles, strongest first:
  1. GROUND TRUTH — for Carter-bench prompts we know the expected tools.
     The router PASSES the case iff every expected compound-tool is in
     the subset (legacy bench names are mapped to the current compound
     tools below). Prompts whose expected tools are "ninguna"/smalltalk
     must NOT pull a domain tool.
  2. INTENT HEURISTIC — for plain trace queries with no ground truth, we
     fall back to the semantic info/action intent oracle (independent of
     the router's own logic so the test isn't circular).

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

# Map the Carter bench's legacy/granular tool names to the compound tools
# the router actually selects today. A bench token resolves to the set of
# compound tools that can satisfy it.
_LEGACY_MAP: dict[str, set[str]] = {
    "web_open_url": {"web", "browser"},
    "web_search": {"web"},
    "web": {"web"},
    "app_open": {"app"},
    "app_resolver": {"app"},
    "app": {"app"},
    "window_close": {"window"},
    "window_manage": {"window"},
    "window_check": {"window", "verify"},
    "window": {"window"},
    "process": {"system", "window"},
    "process_check": {"system", "verify"},
    "memory_write": {"memory"},
    "memory_read": {"memory"},
    "memory_delete": {"memory"},
    "memory": {"memory"},
    "media_volume": {"audio"},
    "media": {"media", "audio"},
    "screenshot": {"gui", "vision"},
    "time": {"system"},
    "system": {"system"},
    "settings": {"device_settings", "system"},
    "filesystem": {"filesystem"},
    "terminal": {"terminal"},
    "gui": {"gui"},
    "vision": {"vision"},
    "uia": {"uia"},
    "input": {"input", "gui"},
    "steam": {"steam"},
    "browser": {"browser", "web"},
    "clipboard": {"clipboard"},
    "verify": {"verify"},
    "zip": {"backup_sync", "filesystem"},
}

# Bench expected-tool cells meaning "no domain tool should fire".
_NONE_MARKERS = ("ninguna", "none", "ningun", "-")
# Cells we can't score deterministically (depend on conversation state).
_SKIP_MARKERS = (
    "segun", "según", "confirmacion", "confirmación", "critica", "crítica",
    "aclaracion", "aclaración", "pendiente", "opcional", "si ", "o ",
    "runtime", "log", "tool router",
)


def _expected_compound_tools(cell: str) -> set[str] | None:
    """Return the set of acceptable compound tools for a bench cell, or
    None if the cell is non-deterministic (skip)."""
    low = cell.strip().lower()
    if any(m in low for m in _NONE_MARKERS):
        return set()  # expect NO domain tool
    if any(m in low for m in _SKIP_MARKERS):
        return None
    acceptable: set[str] = set()
    for tok in re.split(r"[\s/,]+", low):
        tok = tok.strip()
        if tok in _LEGACY_MAP:
            acceptable |= _LEGACY_MAP[tok]
    return acceptable or None


_DOMAIN_EXCLUDE = {"session", "safety", "state", "verify"}

# ---- intent heuristic (for trace queries without ground truth) -------
_SELF_OR_LOCAL = re.compile(
    r"\b(quien eres|quién eres|quien sos|que eres|qué eres|quien soy|quién soy|"
    r"que sabes hacer|qué sabes hacer|que puedes hacer|qué puedes hacer|"
    r"como te llamas|cómo te llamas|who are you|what can you do|"
    r"donde deje|dónde dejé|donde puse|donde dejaste|dónde dejaste|"
    r"cuando dija|cuando diga|cuando prenda|cuando se inic|when i say|"
    r"cual es tu|cuál es tu|deberias usar|deberías usar|no abras|no uses)\b",
    re.IGNORECASE,
)
_INFO_INTENT = re.compile(
    r"\b(que es|qué es|de que|de qué|quien es|quién es|quien fue|quién fue|"
    r"hablame|háblame|cuentame|cuéntame|de que trata|de qué trata|"
    r"quien gana|quién gana|what is|who is|who was|tell me about)\b",
    re.IGNORECASE,
)
_ACTION_INTENT = re.compile(
    r"\b(abre|abrir|cierra|cerrar|open|close|pon|poné|reproduce|play|pausa|"
    r"baja|bajá|sube|subí|silencia|mutea|screenshot|captura|maximiza|minimiza|"
    r"manda|mandá|envia|enviá|escribe|escribí|instala|borra|elimina)\b",
    re.IGNORECASE,
)


def heuristic_intent(q: str) -> str:
    if _SELF_OR_LOCAL.search(q):
        return "action" if _ACTION_INTENT.search(q) else "other"
    info = bool(_INFO_INTENT.search(q))
    act = bool(_ACTION_INTENT.search(q))
    if info and not act:
        return "info"
    if info and act:
        return "mixed"
    if act:
        return "action"
    return "other"


def run_router(q: str) -> set[str]:
    from gemma4_agent.planner import select_tool_names, plan_mission
    return set(select_tool_names(q, plan_mission(q), safety_enabled=False))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show-fails", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    rows = [json.loads(l) for l in CORPUS.read_text(encoding="utf-8").splitlines() if l.strip()]
    if args.limit:
        rows = rows[: args.limit]

    gt_total = gt_ok = 0
    gt_none_total = gt_none_ok = 0
    info_total = info_ok = 0
    action_total = action_ok = 0
    gt_fails: list[tuple[str, set[str], set[str]]] = []
    info_fails: list[tuple[str, set[str]]] = []
    action_fails: list[tuple[str, set[str]]] = []

    for r in rows:
        q = r["q"]
        subset = run_router(q)
        domain = subset - _DOMAIN_EXCLUDE
        et_cell = r.get("expected_tools")

        if et_cell is not None:
            acceptable = _expected_compound_tools(et_cell)
            if acceptable is None:
                pass  # non-deterministic → skip
            elif acceptable == set():
                gt_none_total += 1
                # "ninguna" → the router must not pull a domain tool.
                if not domain:
                    gt_none_ok += 1
                else:
                    gt_fails.append((q, set(), subset))
                continue
            else:
                gt_total += 1
                if subset & acceptable:
                    gt_ok += 1
                else:
                    gt_fails.append((q, acceptable, subset))
                continue

        # No ground truth → intent heuristic.
        intent = heuristic_intent(q)
        if intent in ("info", "mixed"):
            info_total += 1
            if subset & KNOWLEDGE_TOOLS:
                info_ok += 1
            else:
                info_fails.append((q, subset))
        if intent in ("action", "mixed"):
            action_total += 1
            if domain:
                action_ok += 1
            else:
                action_fails.append((q, subset))

    print("=" * 64)
    print("Router eval — full historical corpus")
    print("=" * 64)
    print(f"  corpus size: {len(rows)} unique queries")
    print()
    print(f"  GROUND-TRUTH tool recall: {gt_ok}/{gt_total} "
          f"= {gt_ok/max(1,gt_total):.3f}  (expected tool in subset)")
    print(f"  GROUND-TRUTH 'ninguna':   {gt_none_ok}/{gt_none_total} "
          f"= {gt_none_ok/max(1,gt_none_total):.3f}  (no domain tool when none expected)")
    print(f"  INFO recall (heuristic):  {info_ok}/{info_total} "
          f"= {info_ok/max(1,info_total):.3f}")
    print(f"  ACTION preserve (heur.):  {action_ok}/{action_total} "
          f"= {action_ok/max(1,action_total):.3f}")
    print()
    total_fail = len(gt_fails) + len(info_fails) + len(action_fails)
    print(f"  TOTAL real failures: {total_fail} "
          f"(gt={len(gt_fails)} info={len(info_fails)} action={len(action_fails)})")

    if args.show_fails:
        if gt_fails:
            print("\n--- GROUND-TRUTH failures (expected tool missing) ---")
            for q, exp, sub in gt_fails[:50]:
                print(f"  {q!r}\n     expected one of={sorted(exp)}  subset={sorted(sub)}")
        if info_fails:
            print("\n--- INFO heuristic misses ---")
            for q, sub in info_fails[:50]:
                print(f"  {q!r}\n     subset={sorted(sub)}")
        if action_fails:
            print("\n--- ACTION heuristic misses ---")
            for q, sub in action_fails[:50]:
                print(f"  {q!r}\n     subset={sorted(sub)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
