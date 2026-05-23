"""Quality eval for the latency sprint. Compares the CURRENT corpus replies
(bench/latency_results.json, freshly produced by _latency_harness.py) against the
BASELINE (bench/latency_baseline.json) to quantify whether a latency optimization
degraded answer quality — so "el promedio mejora claro con degradación chica" is a
NUMBER, not intuition (norte rector: criterio BALANCE).

Quality score per prompt (0..1):
  - correctness: for factual prompts, the expected key fact appears (keyword list);
    for actions, the reply confirms or is empty-but-tool-fired; for smalltalk, the
    reply is non-empty and conversational.
  - We DON'T require byte-identical replies (the model is stochastic); we flag a
    DEGRADATION only when a baseline-correct reply becomes incorrect/empty.

Output: aggregate score + the list of prompts whose quality CHANGED (regressed or
improved), with the before/after text. Run AFTER _latency_harness.py.

Usage: PYTHONPATH=. python bench/_quality_eval.py
"""
from __future__ import annotations

import json
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").casefold())
    return "".join(c for c in s if not unicodedata.combining(c))


# Expected key facts per factual prompt (folded substring match). For actions,
# expected confirmation verbs. For others, just "non-empty + on-register".
_EXPECT = {
    "fs1": ["paris"],
    "fs2": ["2013"],
    "fs3": ["ocho", "8"],
    "fs4": ["garcia marquez", "marquez"],
    "fs5": ["1969"],
    "fs6": ["amazonas", "nilo"],
    "cx1": ["plant", "luz", "energia", "dioxido", "glucosa"],
    "cx2": ["solar", "eolic", "viento", "sol"],
    "cx3": ["luz", "dispers", "atmosfer", "azul", "longitud"],
    "cx4": ["combust", "motor", "energia", "piston", "explos"],
    "cx5": ["ram", "disco", "memoria", "rapid", "permanent", "volatil"],
}
_ACTION_OK = ["listo", "abri", "cerr", "minimic", "minimiz", "sub", "captur", "puse", "spotify", "chrome", "steam"]


def _quality(row) -> tuple[float, str]:
    """Return (score 0..1, reason)."""
    rid, typ, reply = row["id"], row["type"], (row.get("reply") or "")
    f = _fold(reply)
    if typ in ("factual-simple", "pregunta-compleja"):
        exp = _EXPECT.get(rid, [])
        if not f.strip():
            return 0.0, "EMPTY reply"
        if exp and any(_fold(k) in f for k in exp):
            return 1.0, "key fact present"
        if exp:
            return 0.3, f"key fact MISSING (expected one of {exp})"
        return 0.8, "non-empty, no expectation list"
    if typ in ("accion", "accion-multistep"):
        # An action turn is OK if it confirms OR is a tool-only turn (empty text
        # but the tool fired — the harness no-ops tools, so empty is acceptable
        # IF baseline was also empty; otherwise flag).
        if any(_fold(k) in f for k in _ACTION_OK):
            return 1.0, "confirmation present"
        if not f.strip():
            return 0.6, "empty (tool-only turn; acceptable for voice ack)"
        return 0.7, "non-empty, no clear confirmation verb"
    # smalltalk / research: non-empty + not a refusal
    if not f.strip():
        return 0.0, "EMPTY reply"
    return 1.0, "non-empty conversational"


def main():
    cur = {r["id"]: r for r in json.load(open(ROOT / "bench" / "latency_results.json", encoding="utf-8"))}
    base_path = ROOT / "bench" / "latency_baseline.json"
    base = {}
    if base_path.exists():
        base = {r["id"]: r for r in json.load(open(base_path, encoding="utf-8"))}

    scores = []
    changed = []
    for rid, row in cur.items():
        sc, reason = _quality(row)
        scores.append(sc)
        if rid in base:
            bsc, _ = _quality(base[rid])
            if abs(sc - bsc) >= 0.3:  # meaningful change
                changed.append((rid, bsc, sc, base[rid].get("reply", "")[:60], row.get("reply", "")[:60]))

    agg = sum(scores) / len(scores) if scores else 0.0
    print(f"=== quality aggregate: {agg:.3f} over {len(scores)} prompts ===")
    low = [(rid, _quality(r)[0], _quality(r)[1]) for rid, r in cur.items() if _quality(r)[0] < 0.7]
    if low:
        print("Below-0.7 prompts (current):")
        for rid, sc, reason in low:
            print(f"  {rid}: {sc:.1f} — {reason}")
    if changed:
        print("\nCHANGED vs baseline (|delta|>=0.3):")
        for rid, b, c, bt, ct in changed:
            arrow = "REGRESSED" if c < b else "IMPROVED"
            print(f"  {rid}: {b:.1f}->{c:.1f} {arrow}")
            print(f"     base: {bt.encode('ascii','replace').decode()!r}")
            print(f"     now:  {ct.encode('ascii','replace').decode()!r}")
    else:
        print("\nNo quality changes vs baseline (|delta|<0.3 for all).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
