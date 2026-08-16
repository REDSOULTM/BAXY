"""Benchmark low-memory per-operation compatibility verifiers on MTOP dev."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiments.mind_router_spike import (  # noqa: E402
    train_mtop_operation_classifier as trainer,
)
from experiments.mind_router_spike.calibrate_mtop_operation_compatibility import (  # noqa: E402
    _select_threshold,
)
from scripts.measure_mind_budget import write_json_atomic  # noqa: E402


DEFAULT_OUTPUT = (
    REPO / "artifacts/research/mtop_operation_compatibility_linear_v1.json"
)
SEED = 20260801


def _stable_sample(
    rows: list[dict[str, Any]],
    count: int,
    operation: str,
) -> list[dict[str, Any]]:
    ordered = sorted(
        rows,
        key=lambda row: hashlib.sha256(
            f"{operation}|{row.get('source_id', row['text'])}".encode("utf-8")
        ).hexdigest(),
    )
    return ordered[: min(count, len(ordered))]


def run(args: argparse.Namespace) -> dict[str, Any]:
    from scipy.sparse import hstack
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression

    random.seed(SEED)
    rows, manifest, identity = trainer.mtop._load_development(
        trainer.mtop.DEVELOPMENT_CORPUS,
        trainer.mtop.MANIFEST,
    )
    labelled = [
        (row, operation)
        for row in rows
        if (operation := trainer.operation_label(row))
        not in {None, trainer.NO_ACTION}
    ]
    operations = tuple(sorted({str(operation) for _row, operation in labelled}))
    train = [(row, str(operation)) for row, operation in labelled if row["split"] == "train"]
    validation = [
        (row, str(operation))
        for row, operation in labelled
        if row["split"] == "validation"
    ]
    wrong_validation = trainer._wrong_operation_pairs(
        [(row, "compatible") for row, _operation in validation],
        operations,
        count=1,
        negative_label="incompatible",
    )
    candidates = tuple(float(value) for value in args.c_values.split(","))
    measurements: list[dict[str, Any]] = []
    training_started = time.perf_counter()
    for c_value in candidates:
        compatible_scores = np.zeros(len(validation), dtype=np.float64)
        incompatible_scores = np.zeros(len(wrong_validation), dtype=np.float64)
        per_operation: dict[str, Any] = {}
        model_bytes_estimate = 0
        fit_seconds = 0.0
        score_seconds = 0.0
        for operation in operations:
            family = operation.split(".", 1)[0]
            positives = [row for row, actual in train if actual == operation]
            sibling_negatives = [
                row
                for row, actual in train
                if actual != operation and actual.split(".", 1)[0] == family
            ]
            other_negatives = [
                row
                for row, actual in train
                if actual.split(".", 1)[0] != family
            ]
            negatives = [
                *sibling_negatives,
                *_stable_sample(
                    other_negatives,
                    max(len(positives), len(sibling_negatives)),
                    operation,
                ),
            ]
            train_texts = [str(row["text"]) for row in [*positives, *negatives]]
            targets = np.asarray(
                [1] * len(positives) + [0] * len(negatives),
                dtype=np.int64,
            )
            word = TfidfVectorizer(
                analyzer="word",
                ngram_range=(1, 2),
                min_df=2,
                max_features=args.word_features,
                sublinear_tf=True,
                strip_accents="unicode",
            )
            char = TfidfVectorizer(
                analyzer="char_wb",
                ngram_range=(3, 5),
                min_df=2,
                max_features=args.char_features,
                sublinear_tf=True,
                strip_accents="unicode",
            )
            fit_started = time.perf_counter()
            features = hstack(
                (word.fit_transform(train_texts), char.fit_transform(train_texts)),
                format="csr",
            )
            model = LogisticRegression(
                C=c_value,
                class_weight="balanced",
                max_iter=2000,
                solver="liblinear",
                random_state=SEED,
            ).fit(features, targets)
            fit_seconds += time.perf_counter() - fit_started
            model_bytes_estimate += int(
                model.coef_.nbytes
                + model.intercept_.nbytes
                + sum(len(value.encode("utf-8")) + 8 for value in word.vocabulary_)
                + sum(len(value.encode("utf-8")) + 8 for value in char.vocabulary_)
            )

            correct_indices = [
                index
                for index, (_row, actual) in enumerate(validation)
                if actual == operation
            ]
            wrong_indices = [
                index
                for index, (row, _label) in enumerate(wrong_validation)
                if trainer._conditioned_operation(row) == operation
            ]

            def score(selected_rows: list[dict[str, Any]]) -> np.ndarray:
                nonlocal score_seconds
                if not selected_rows:
                    return np.asarray([], dtype=np.float64)
                started = time.perf_counter()
                texts = [str(row["text"]) for row in selected_rows]
                matrix = hstack(
                    (word.transform(texts), char.transform(texts)),
                    format="csr",
                )
                result = model.predict_proba(matrix)[:, 1]
                score_seconds += time.perf_counter() - started
                return result.astype(np.float64)

            compatible_scores[correct_indices] = score(
                [validation[index][0] for index in correct_indices]
            )
            incompatible_scores[wrong_indices] = score(
                [wrong_validation[index][0] for index in wrong_indices]
            )
            per_operation[operation] = {
                "train_compatible": len(positives),
                "train_incompatible": len(negatives),
                "validation_compatible": len(correct_indices),
                "validation_incompatible": len(wrong_indices),
                "features": int(features.shape[1]),
            }
        selected = _select_threshold(compatible_scores, incompatible_scores)
        if selected is None:
            raise RuntimeError("linear compatibility calibration failed")
        measurements.append(
            {
                "c": c_value,
                "argmax": {
                    "compatible_accuracy": round(
                        float(np.mean(compatible_scores >= 0.5)),
                        9,
                    ),
                    "incompatible_accuracy": round(
                        float(np.mean(incompatible_scores < 0.5)),
                        9,
                    ),
                },
                "selected": {
                    key: round(value, 9) for key, value in selected.items()
                },
                "fit_seconds": round(fit_seconds, 6),
                "score_seconds": round(score_seconds, 6),
                "estimated_model_bytes": model_bytes_estimate,
                "per_operation": per_operation,
            }
        )
    best = max(
        measurements,
        key=lambda item: (
            item["selected"]["minimum_accuracy"],
            item["selected"]["compatible_accuracy"],
        ),
    )
    report = {
        "schema": "baxy.mtop-operation-compatibility-linear-benchmark.v1",
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "scope": "development_validation_only_mtop_test_remains_sealed",
        "source": {
            "mtop_development_sha256": identity.corpus.sha256,
            "mtop_manifest_sha256": identity.manifest.sha256,
            "mtop_map_sha256": manifest["source"]["map_sha256"],
            "mtop_test_content_read": False,
        },
        "configuration": {
            "seed": SEED,
            "c_values": list(candidates),
            "word_features": args.word_features,
            "char_features": args.char_features,
            "negative_strategy": "all_same_family_plus_hash_sampled_cross_family",
        },
        "data": {
            "operations": len(operations),
            "train_compatible": len(train),
            "validation_compatible": len(validation),
            "validation_incompatible": len(wrong_validation),
            "utterance_text_persisted": False,
        },
        "measurements": measurements,
        "best": best,
        "training_seconds": round(time.perf_counter() - training_started, 6),
        "status": (
            "candidate"
            if best["selected"]["compatible_accuracy"] >= 0.99
            and best["selected"]["incompatible_accuracy"] >= 0.99
            else "rejected_below_0_99"
        ),
    }
    trainer.mtop._assert_input_identity_stable(identity)
    write_json_atomic(args.output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--c-values", default="1,3,10")
    parser.add_argument("--word-features", type=int, default=40_000)
    parser.add_argument("--char-features", type=int, default=60_000)
    args = parser.parse_args()
    args.output = args.output.resolve()
    report = run(args)
    print(
        json.dumps(
            {
                "status": report["status"],
                "best": report["best"],
                "training_seconds": report["training_seconds"],
                "report": str(args.output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
