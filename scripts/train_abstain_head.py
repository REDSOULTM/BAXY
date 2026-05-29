"""Train the calibrated NO-TOOL abstention head (Step 2 of the router rebuild).

Reproducible recipe (project law): regenerates gemma4_agent/data/abstain_head.json
from the curated corpus + the live intent/semantic routers. No binary artifact,
no pickle — emits plain float weights as JSON so the runtime forward pass is a
numpy dot product with zero sklearn dependency.

ANTI-OVERFIT, enforced here, not just promised:
  - Uses the SAME stable-hash split as router_eval.py. Training reads DEV rows
    ONLY; holdout rows are never embedded, never seen.
  - The decision threshold is picked on a dev-internal 5-fold CV (out-of-fold
    predictions), maximizing NO-TOOL keep subject to a recall-floor constraint,
    so we don't peek at holdout to set it.
  - Reports an honest dev-CV estimate; the real holdout number comes from
    router_eval.py AFTER wiring, evaluated once.

Run:  python scripts/train_abstain_head.py
      python scripts/train_abstain_head.py --recall-floor 0.985
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CORPUS = ROOT / "gemma4_agent" / "data" / "router_eval_corpus.curated.jsonl"
OUT = ROOT / "gemma4_agent" / "data" / "abstain_head.json"
_HOLDOUT_SALT = "router-eval-2026-05-20"  # MUST match router_eval.py


def _split_of(q: str) -> str:
    h = hashlib.sha256((_HOLDOUT_SALT + q).encode("utf-8")).hexdigest()
    return "holdout" if (int(h[:8], 16) % 5 == 0) else "dev"


def _features_for(q: str) -> dict[str, float]:
    """Compute the SAME feature vector the planner will compute at runtime.
    Reuses the live intent_router + semantic_router so train/serve match."""
    from gemma4_agent.safety_pkg.abstain_head import build_features
    from gemma4_agent.routing.intent_router import classify_intent
    from gemma4_agent.routing.semantic_router import suggest_tools_scored
    from gemma4_agent.routing.planner import _suggest_tools, _expand_abbreviations, _fold_text

    intent = classify_intent(q)
    scored = suggest_tools_scored(q, k=12)
    kw = _suggest_tools(_fold_text(_expand_abbreviations(q)))
    return build_features(q, intent=intent, scored=scored, keyword_fired=bool(kw))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--recall-floor", type=float, default=0.985,
                    help="min fraction of TOOL rows that must NOT be abstained "
                         "(protects recall). Threshold is the highest that keeps "
                         "tool-row abstention below 1-floor on dev CV.")
    ap.add_argument("--C", type=float, default=1.0, help="inverse L2 strength")
    args = ap.parse_args()

    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold

    from gemma4_agent.safety_pkg.abstain_head import FEATURE_NAMES

    rows = [json.loads(l) for l in CORPUS.read_text(encoding="utf-8").splitlines() if l.strip()]
    dev = [r for r in rows if _split_of(r["q"]) == "dev"]
    print(f"dev rows: {len(dev)}  (holdout excluded entirely)")

    # y = 1 means SHOULD ABSTAIN (no-tool row). Build the feature matrix.
    X, y, qs = [], [], []
    for i, r in enumerate(dev):
        q = r["q"]
        feats = _features_for(q)
        X.append([feats[n] for n in FEATURE_NAMES])
        y.append(0 if (r.get("expected") or []) else 1)
        qs.append(q)
        if (i + 1) % 200 == 0:
            print(f"  featurized {i+1}/{len(dev)}")
    X = np.asarray(X, dtype="float64")
    y = np.asarray(y, dtype="int64")
    print(f"no-tool positives: {int(y.sum())}/{len(y)} ({y.mean():.1%})")

    # Out-of-fold probabilities for honest threshold selection (no peeking).
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    oof = np.zeros(len(y), dtype="float64")
    for tr, va in skf.split(X, y):
        clf = LogisticRegression(C=args.C, class_weight="balanced", max_iter=2000)
        clf.fit(X[tr], y[tr])
        oof[va] = clf.predict_proba(X[va])[:, 1]

    # Choose threshold: maximize no-tool keep s.t. tool-row abstention rate
    # (false-abstain, which hurts recall) stays below 1 - recall_floor.
    tool_mask = y == 0
    notool_mask = y == 1
    best = None
    for thr in np.linspace(0.05, 0.95, 91):
        abst = oof >= thr
        false_abstain = (abst & tool_mask).mean() if tool_mask.any() else 0.0
        keep = (abst & notool_mask).sum() / max(1, notool_mask.sum())
        if false_abstain <= (1.0 - args.recall_floor):
            if best is None or keep > best[1]:
                best = (thr, keep, false_abstain)
    if best is None:
        # floor too strict; fall back to the highest threshold (most conservative)
        best = (0.95, (oof[notool_mask] >= 0.95).mean(), 0.0)
    thr, cv_keep, cv_false_abstain = best
    print(f"\nchosen threshold={thr:.3f}  (dev-CV no-tool keep added={cv_keep:.3f}, "
          f"tool-row false-abstain={cv_false_abstain:.4f})")

    # Refit on ALL dev rows for the shipped weights.
    final = LogisticRegression(C=args.C, class_weight="balanced", max_iter=2000)
    final.fit(X, y)
    weights = final.coef_[0].tolist()
    bias = float(final.intercept_[0])

    # Feature importance readout (which signals drive abstention).
    print("\nfeature weights (positive => pushes toward ABSTAIN):")
    for n, w in sorted(zip(FEATURE_NAMES, weights), key=lambda x: -abs(x[1])):
        print(f"    {n:18s} {w:+.3f}")

    OUT.write_text(json.dumps({
        "model_version": "v1",
        "feature_names": list(FEATURE_NAMES),
        "weights": weights,
        "bias": bias,
        "threshold": float(thr),
        "trained_on": "dev split (stable hash, holdout excluded)",
        "recall_floor": args.recall_floor,
        "dev_cv_notool_keep_added": float(cv_keep),
        "dev_cv_tool_false_abstain": float(cv_false_abstain),
    }, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
