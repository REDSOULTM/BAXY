"""Train the per-tool logit head — the research's core anti-bloat architecture.

All four reports converged on a multi-label router head: a per-tool logit with a
PER-TOOL CALIBRATED THRESHOLD. The subset is "tools whose logit clears their own
bar" — NOT top-k, NOT a band from the peak. This is what makes a flat-
distribution query like "pausa" yield ONLY {media} instead of the 7-tool cluster
{media,app,study,accessibility,...}: media's logit is high, the others' logits
sit below their own thresholds, so they're excluded BY CONSTRUCTION.

Architecture (compass_artifact_499...: "65 sigmoid tool logits + per-tool
calibrated thresholds"): one logistic regression PER tool (one-vs-rest) on the
fine-tuned encoder's 384-d embedding. Runtime is one embed + a 65x384 matmul +
a per-tool threshold compare (sub-ms, numpy). Reproducible JSON artifact.

Training data (labeled query -> tool):
  - the curated corpus DEV rows (q, expected[]) — real distribution
  - the Tool2Vec synthetic multilingual queries (q, tool) — coverage + balance
Holdout rows are excluded by the same stable hash as everything else.

Per-tool threshold: chosen on dev-CV out-of-fold probabilities to maximize F1
for that tool (so a tool with few/ambiguous examples gets a higher bar). A
global floor prevents degenerate thresholds.

Run:  python scripts/train_tool_head.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CORPUS = ROOT / "gemma4_agent" / "data" / "router_eval_corpus.curated.jsonl"
T2V = ROOT / "gemma4_agent" / "data" / "tool2vec_queries.jsonl"
OUT = ROOT / "gemma4_agent" / "data" / "tool_head.json"
_HOLDOUT_SALT = "router-eval-2026-05-20"


def _split_of(q: str) -> str:
    h = hashlib.sha256((_HOLDOUT_SALT + q).encode("utf-8")).hexdigest()
    return "holdout" if (int(h[:8], 16) % 5 == 0) else "dev"


def main() -> int:
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold

    from gemma4_agent.semantic_router import embed, TOOL_DESCRIPTIONS

    tools = sorted(TOOL_DESCRIPTIONS.keys())
    tool_idx = {t: i for i, t in enumerate(tools)}

    # Collect (query, set-of-tools). DEV corpus rows + synthetic queries.
    samples: list[tuple[str, set[str]]] = []
    for ln in CORPUS.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        r = json.loads(ln)
        if _split_of(r["q"]) != "dev":
            continue
        samples.append((r["q"], set(r.get("expected") or [])))
    n_real = len(samples)
    if T2V.exists():
        for ln in T2V.read_text(encoding="utf-8").splitlines():
            if not ln.strip():
                continue
            d = json.loads(ln)
            if d["tool"] in tool_idx:
                samples.append((d["q"], {d["tool"]}))
    print(f"samples: {len(samples)} ({n_real} real dev + "
          f"{len(samples)-n_real} synthetic)")

    # Embed once per unique query (cache).
    print("embedding queries with the fine-tuned encoder...")
    X = []
    Y = np.zeros((len(samples), len(tools)), dtype="int8")
    keep = []
    for i, (q, toolset) in enumerate(samples):
        v = embed(q)
        if v is None:
            continue
        X.append(np.asarray(v, dtype="float32"))
        for t in toolset:
            if t in tool_idx:
                Y[len(keep), tool_idx[t]] = 1
        keep.append(i)
        if (len(keep)) % 500 == 0:
            print(f"  embedded {len(keep)}")
    X = np.asarray(X, dtype="float32")
    Y = Y[: len(keep)]
    print(f"matrix: X{X.shape} Y{Y.shape}")

    # One-vs-rest logistic regression per tool, with per-tool threshold from
    # dev-CV out-of-fold probabilities (F1-max, with a global floor).
    weights = np.zeros((len(tools), X.shape[1]), dtype="float32")
    biases = np.zeros(len(tools), dtype="float32")
    thresholds = np.full(len(tools), 0.5, dtype="float32")
    GLOBAL_FLOOR = 0.35

    for ti, tool in enumerate(tools):
        y = Y[:, ti]
        pos = int(y.sum())
        if pos < 4:
            # Too few positives to calibrate — disable this tool's head (it
            # falls back to the keyword/semantic layer). High threshold.
            thresholds[ti] = 1.01
            continue
        clf = LogisticRegression(C=1.0, class_weight="balanced", max_iter=2000)
        # OOF probabilities for threshold selection.
        try:
            skf = StratifiedKFold(n_splits=min(5, pos), shuffle=True,
                                  random_state=42)
            oof = np.zeros(len(y), dtype="float64")
            for tr, va in skf.split(X, y):
                c = LogisticRegression(C=1.0, class_weight="balanced",
                                       max_iter=2000)
                c.fit(X[tr], y[tr])
                oof[va] = c.predict_proba(X[va])[:, 1]
            best_thr, best_f1 = GLOBAL_FLOOR, -1.0
            for thr in np.linspace(0.2, 0.9, 71):
                pred = oof >= thr
                tp = int((pred & (y == 1)).sum())
                fp = int((pred & (y == 0)).sum())
                fn = int((~pred & (y == 1)).sum())
                if tp == 0:
                    continue
                prec = tp / (tp + fp)
                rec = tp / (tp + fn)
                f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
                if f1 > best_f1:
                    best_f1, best_thr = f1, thr
            thresholds[ti] = max(GLOBAL_FLOOR, best_thr)
        except Exception:
            thresholds[ti] = 0.5
        clf.fit(X, y)
        weights[ti] = clf.coef_[0].astype("float32")
        biases[ti] = float(clf.intercept_[0])

    active = int((thresholds <= 1.0).sum())
    print(f"trained heads for {active}/{len(tools)} tools "
          f"(rest fall back to keyword/semantic)")

    OUT.write_text(json.dumps({
        "model_version": "v1",
        "tools": tools,
        "weights": weights.tolist(),
        "biases": biases.tolist(),
        "thresholds": thresholds.tolist(),
        "encoder": "router_encoder_ft (semantic_router default)",
        "trained_on": "dev corpus + Tool2Vec synthetic; holdout excluded",
    }), encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
