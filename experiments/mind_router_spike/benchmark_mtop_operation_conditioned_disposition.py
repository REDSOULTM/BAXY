"""Benchmark operation-conditioned MTOP disposition classifiers.

Only hash-bound MTOP train and opened validation are read.  The operation is
the frozen catalog nomination available at runtime; it is input context, never
execution authority.  Official test and BAXY blind reserve remain sealed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts", Path(__file__).parent):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import measure_turn_policy_v52_mtop_validation as mtop  # noqa: E402
import train_mtop_operation_classifier as trainer  # noqa: E402
from scripts.measure_mind_budget import write_json_atomic  # noqa: E402


DEFAULT_R4 = (
    REPO
    / "artifacts/fixes/mtop_product_validation_development_r4_current.json"
)
DEFAULT_REPORT = (
    REPO
    / "artifacts/research/mtop_operation_conditioned_disposition_v1.json"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _disposition(row: dict[str, Any], operation: str) -> str:
    return trainer.training_label(row, operation, "disposition")


def _conditioned_text(row: dict[str, Any], operation: str) -> str:
    return f"operation={operation} request={row['text']}"


def _metrics(
    truth: list[str],
    predicted: list[str],
    ids: list[str],
    r4_ids: set[str],
) -> dict[str, Any]:
    def one(indices: list[int]) -> dict[str, Any]:
        exact = [truth[index] == predicted[index] for index in indices]
        by_disposition = {}
        for disposition in sorted(set(truth)):
            selected = [index for index in indices if truth[index] == disposition]
            if selected:
                correct = sum(truth[index] == predicted[index] for index in selected)
                by_disposition[disposition] = {
                    "cases": len(selected),
                    "correct": correct,
                    "accuracy": round(correct / len(selected), 6),
                }
        return {
            "cases": len(indices),
            "correct": sum(exact),
            "accuracy": round(sum(exact) / len(indices), 6),
            "by_disposition": by_disposition,
        }

    all_indices = list(range(len(truth)))
    r4_indices = [index for index, source_id in enumerate(ids) if source_id in r4_ids]
    return {
        "all_validation": one(all_indices),
        "r4": one(r4_indices),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    from scipy.sparse import hstack
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression

    if args.report.exists():
        raise RuntimeError(f"refusing to overwrite report: {args.report}")
    rows, manifest, identity = mtop._load_development(
        mtop.DEVELOPMENT_CORPUS,
        mtop.MANIFEST,
    )
    labelled = [
        (row, str(operation))
        for row in rows
        for operation in [trainer.operation_label(row)]
        if operation is not None
    ]
    train_rows = [item for item in labelled if item[0]["split"] == "train"]
    validation_rows = [
        item for item in labelled if item[0]["split"] == "validation"
    ]
    train_texts = [_conditioned_text(row, operation) for row, operation in train_rows]
    validation_texts = [
        _conditioned_text(row, operation) for row, operation in validation_rows
    ]
    train_labels = [_disposition(row, operation) for row, operation in train_rows]
    validation_labels = [
        _disposition(row, operation) for row, operation in validation_rows
    ]
    validation_ids = [str(row["source_id"]) for row, _operation in validation_rows]
    r4_source = json.loads(args.r4.read_text(encoding="utf-8"))
    r4_ids = {str(row["source_id"]) for row in r4_source["samples"]}
    if not r4_ids <= set(validation_ids):
        raise RuntimeError("R4 escaped the labelled validation population")

    words = TfidfVectorizer(
        analyzer="word",
        ngram_range=(1, 2),
        min_df=2,
        max_features=100_000,
        strip_accents="unicode",
        sublinear_tf=True,
    )
    characters = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(3, 5),
        min_df=2,
        max_features=150_000,
        strip_accents="unicode",
        sublinear_tf=True,
    )
    started = time.perf_counter()
    train_features = hstack(
        (words.fit_transform(train_texts), characters.fit_transform(train_texts)),
        format="csr",
    )
    validation_features = hstack(
        (words.transform(validation_texts), characters.transform(validation_texts)),
        format="csr",
    )
    feature_seconds = time.perf_counter() - started
    counts = Counter(train_labels)
    classes = sorted(counts)
    variants = []
    for power in args.class_weight_powers:
        class_weight = {
            label: (len(train_labels) / (len(classes) * counts[label])) ** power
            for label in classes
        }
        for regularization in args.c_values:
            fit_started = time.perf_counter()
            model = LogisticRegression(
                C=regularization,
                class_weight=class_weight,
                max_iter=500,
                n_jobs=1,
                random_state=trainer.SEED,
                solver="saga",
                tol=1e-3,
            )
            model.fit(train_features, train_labels)
            predicted = [str(value) for value in model.predict(validation_features)]
            metrics = _metrics(
                validation_labels,
                predicted,
                validation_ids,
                r4_ids,
            )
            variants.append(
                {
                    "class_weight_power": power,
                    "c": regularization,
                    "fit_seconds": round(time.perf_counter() - fit_started, 3),
                    **metrics,
                    "predictions": predicted,
                }
            )
    best = max(
        variants,
        key=lambda item: (
            item["all_validation"]["accuracy"],
            min(
                value["accuracy"]
                for value in item["all_validation"]["by_disposition"].values()
            ),
            item["r4"]["accuracy"],
        ),
    )
    records = [
        {
            "source_id": source_id,
            "in_r4": source_id in r4_ids,
            "expected": expected,
            "predicted": predicted,
            "correct": predicted == expected,
        }
        for source_id, expected, predicted in zip(
            validation_ids,
            validation_labels,
            best["predictions"],
            strict=True,
        )
    ]
    public_variants = [
        {key: value for key, value in variant.items() if key != "predictions"}
        for variant in variants
    ]
    report = {
        "schema": "baxy.mtop-operation-conditioned-disposition.v1",
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "scope": "development_only_mtop_test_and_baxy_blind_reserve_sealed",
        "authority": "classifier_evaluation_only_no_core_or_provider",
        "contains_utterance_text": False,
        "effects_executed": 0,
        "sources": {
            "mtop_development_sha256": identity.corpus.sha256,
            "mtop_manifest_sha256": identity.manifest.sha256,
            "mtop_map_sha256": manifest["source"]["map_sha256"],
            "r4_sha256": _sha256(args.r4),
            "mtop_test_content_read": False,
            "baxy_blind_reserve_opened": False,
        },
        "configuration": {
            "class_weight_powers": args.class_weight_powers,
            "c_values": args.c_values,
            "word_features": int(len(words.vocabulary_)),
            "character_features": int(len(characters.vocabulary_)),
            "feature_seconds": round(feature_seconds, 3),
        },
        "data": {
            "train_cases": len(train_rows),
            "validation_cases": len(validation_rows),
            "r4_cases": len(r4_ids),
            "train_class_counts": dict(sorted(counts.items())),
        },
        "variants": public_variants,
        "best": {
            key: value for key, value in best.items() if key != "predictions"
        },
        "records": records,
        "status": (
            "candidate"
            if best["all_validation"]["accuracy"] >= 0.99
            and best["r4"]["accuracy"] >= 0.99
            else "rejected_below_0_99"
        ),
    }
    mtop._assert_input_identity_stable(identity)
    write_json_atomic(args.report, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--r4", type=Path, default=DEFAULT_R4)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--class-weight-powers",
        type=float,
        nargs="+",
        default=(0.0, 0.25, 0.5, 0.75),
    )
    parser.add_argument(
        "--c-values",
        type=float,
        nargs="+",
        default=(0.5, 1.0, 2.0),
    )
    args = parser.parse_args()
    args.r4 = args.r4.resolve(strict=True)
    args.report = args.report.resolve()
    report = run(args)
    print(
        json.dumps(
            {
                "status": report["status"],
                "best": report["best"],
                "report": str(args.report),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
