"""Evaluate the frozen semantic family arbiter on an external oracle once."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.svm import LinearSVC

from benchmark_family_arbiter import DEFAULT_CACHE, _encode
from selector_common import REPO, read_jsonl, sha256

SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

DEFAULT_CORPUS = REPO / "artifacts" / "research" / "functiongemma_training_corpus.v1.jsonl"
DEFAULT_ORACLE = REPO / "experiments" / "mind_router_spike" / "data" / "exact_operation_development.v1.jsonl"
DEFAULT_OUTPUT = REPO / "artifacts" / "research" / "family_arbiter_exact_dev_once.v1.json"


def _encode_external(texts: list[str]) -> tuple[np.ndarray, list[float]]:
    from baxy_mind.router import ProcessIntentRouter

    inherited = os.environ.get("PYTHONPATH", "")
    os.environ["PYTHONPATH"] = str(SRC) + (os.pathsep + inherited if inherited else "")
    router = ProcessIntentRouter()
    try:
        if not router.try_ready(180.0):
            raise RuntimeError("the attested E5 worker did not become ready")
        rows: list[np.ndarray] = []
        latencies: list[float] = []
        for text in texts:
            started = time.perf_counter()
            rows.append(router.encode([text], timeout=30.0)[0])
            latencies.append(time.perf_counter() - started)
        return np.vstack(rows).astype(np.float32, copy=False), latencies
    finally:
        router.close()


def _percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * probability)]


def run(args: argparse.Namespace) -> dict[str, Any]:
    training = [row for row in read_jsonl(args.corpus) if str(row.get("operation")) != "__no_action__"]
    training_texts = [str(row["text"]) for row in training]
    training_labels = [str(row["operation"]).split(".", 1)[0] for row in training]
    embeddings = _encode(training_texts, args.corpus, args.embedding_cache)
    model = LinearSVC(
        C=3.0,
        class_weight="balanced",
        dual="auto",
        max_iter=20_000,
        random_state=0,
    ).fit(embeddings, training_labels)

    cases = [row for row in read_jsonl(args.oracle) if row.get("category") == "single"]
    case_embeddings, latencies = _encode_external([str(row["text"]) for row in cases])
    scores = np.asarray(model.decision_function(case_embeddings), dtype=np.float64)
    order = np.argsort(scores, axis=1)[:, ::-1]
    classes = [str(value) for value in model.classes_]
    rows: list[dict[str, Any]] = []
    for index, case in enumerate(cases):
        expected = str(case["expected_operations"][0]).split(".", 1)[0]
        ranked = [classes[int(value)] for value in order[index, :5]]
        rows.append(
            {
                "case_id": case["case_id"],
                "language": case.get("language"),
                "text": case["text"],
                "expected_family": expected,
                "ranked_families": ranked,
                "right": ranked[0] == expected,
                "top2": expected in ranked[:2],
                "top3": expected in ranked[:3],
                "seconds": round(latencies[index], 6),
            }
        )
    right = sum(bool(row["right"]) for row in rows)
    report = {
        "schema": "baxy.family-arbiter-external-evaluation.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "one diagnostic opening after C=3.0 was frozen on disjoint internal validation",
        "configuration": "attested multilingual-e5-small embeddings + class-balanced LinearSVC C=3.0",
        "corpus": str(args.corpus),
        "corpus_sha256": sha256(args.corpus),
        "oracle": str(args.oracle),
        "oracle_sha256": sha256(args.oracle),
        "training_rows": len(training),
        "cases": len(rows),
        "right": right,
        "accuracy": round(right / len(rows), 6),
        "top2_recall": round(sum(bool(row["top2"]) for row in rows) / len(rows), 6),
        "top3_recall": round(sum(bool(row["top3"]) for row in rows) / len(rows), 6),
        "encoder_latency_seconds": {
            "mean": round(statistics.fmean(latencies), 6),
            "p50": round(_percentile(latencies, 0.5), 6),
            "p95": round(_percentile(latencies, 0.95), 6),
            "maximum": round(max(latencies), 6),
        },
        "incremental_classifier_coefficients": int(model.coef_.size + model.intercept_.size),
        "effects_executed": 0,
        "runtime_manifest_changed": False,
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "rows"}, ensure_ascii=False, indent=2, sort_keys=True))
    if right != len(rows):
        print(json.dumps([row for row in rows if not row["right"]], ensure_ascii=False, indent=2))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--oracle", type=Path, default=DEFAULT_ORACLE)
    parser.add_argument("--embedding-cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    run(parser.parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
