"""Test whether inherited messages can route Goal 03 without corpus training.

The fixed Goal 03 corpus is evaluation-only.  Training rows come from the
historical-message cutoff and its separately versioned acceptance mapping.
Labels are deliberately coarse catalogue domains; a later probe can measure
leaf selection only if this stage earns enough recall.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
for import_root in (REPO, REPO / "src"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from sklearn.feature_extraction.text import (  # noqa: E402
    TfidfVectorizer,
)
from sklearn.metrics import accuracy_score, balanced_accuracy_score  # noqa: E402
from sklearn.model_selection import train_test_split  # noqa: E402
from sklearn.pipeline import FeatureUnion  # noqa: E402
from sklearn.svm import LinearSVC  # noqa: E402

from scripts.measure_mind_budget import (  # noqa: E402
    current_core_catalog_snapshot,
    discover_core,
)

CORPUS = REPO / "artifacts/development/goal03_fresh_paraphrase_corpus.v1.jsonl"
MESSAGES = REPO / "tests/data/historical_messages.jsonl"
MAPPING = REPO / "tests/data/historical_message_mapping.jsonl"
OUTPUT = REPO / "artifacts/development/goal03_historical_family_classifier_v1.json"
NO_OPERATION = "no_operation"


def _jsonl(path: Path):
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _domain(operation: str) -> str:
    return operation.split(".", 1)[0]


def _load_training(current_domains: set[str]) -> tuple[list[str], list[str]]:
    accepted = {
        str(row["message_id"]): tuple(str(value) for value in row.get("operations") or [])
        for row in _jsonl(MAPPING)
    }
    texts: list[str] = []
    labels: list[str] = []
    for row in _jsonl(MESSAGES):
        if row.get("dedup_status") == "duplicate" or row.get("redacted"):
            continue
        operations = accepted.get(str(row.get("message_id")))
        if operations is None:
            continue
        domains = {_domain(operation) for operation in operations}
        if not operations:
            label = NO_OPERATION
        elif len(domains) == 1 and next(iter(domains)) in current_domains:
            label = next(iter(domains))
        else:
            continue
        text = str(row.get("text_literal") or row.get("paraphrase") or "").strip()
        if text:
            texts.append(text)
            labels.append(label)
    return texts, labels


def _features() -> FeatureUnion:
    return FeatureUnion(
        [
            (
                "word",
                TfidfVectorizer(
                    lowercase=True,
                    ngram_range=(1, 2),
                    min_df=2,
                    max_features=80_000,
                    strip_accents="unicode",
                    sublinear_tf=True,
                ),
            ),
            (
                "char",
                TfidfVectorizer(
                    analyzer="char_wb",
                    lowercase=True,
                    ngram_range=(3, 5),
                    min_df=2,
                    max_features=120_000,
                    strip_accents="unicode",
                    sublinear_tf=True,
                ),
            ),
        ]
    )


def _write_lf(path: Path, value: dict[str, Any]) -> None:
    serialized = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(serialized)


def main() -> int:
    catalog, _, _ = current_core_catalog_snapshot(discover_core(None))
    current_domains = {_domain(str(row["name"])) for row in catalog}
    texts, labels = _load_training(current_domains)
    train_x, valid_x, train_y, valid_y = train_test_split(
        texts,
        labels,
        test_size=0.2,
        random_state=20260820,
        stratify=labels,
    )
    feature_model = _features()
    started = time.perf_counter()
    train_vectors = feature_model.fit_transform(train_x)
    valid_vectors = feature_model.transform(valid_x)
    classifier = LinearSVC(C=1.0, class_weight="balanced", random_state=20260820)
    classifier.fit(train_vectors, train_y)
    validation_prediction = classifier.predict(valid_vectors)
    training_seconds = time.perf_counter() - started

    corpus = list(_jsonl(CORPUS))
    corpus_texts = [str(row["text"]) for row in corpus]
    started = time.perf_counter()
    corpus_prediction = classifier.predict(feature_model.transform(corpus_texts))
    inference_seconds = time.perf_counter() - started
    rows: list[dict[str, Any]] = []
    for row, predicted in zip(corpus, corpus_prediction, strict=True):
        expected_domains = sorted(
            {_domain(str(operation)) for operation in row.get("expected_operations") or []}
        )
        in_catalog = bool(row["in_catalog"])
        correct = (
            str(predicted) in expected_domains
            if in_catalog
            else str(predicted) == NO_OPERATION
        )
        rows.append(
            {
                "case_id": row["case_id"],
                "text": row["text"],
                "in_catalog": in_catalog,
                "expected_domains": expected_domains,
                "predicted_domain": str(predicted),
                "correct": correct,
            }
        )
    in_rows = [row for row in rows if row["in_catalog"]]
    out_rows = [row for row in rows if not row["in_catalog"]]
    result = {
        "schema": "baxy.goal03-historical-family-classifier.v1",
        "corpus": {"path": str(CORPUS.relative_to(REPO)), "sha256": _sha256(CORPUS)},
        "training_sources": {
            "messages": {"path": str(MESSAGES.relative_to(REPO)), "sha256": _sha256(MESSAGES)},
            "mapping": {"path": str(MAPPING.relative_to(REPO)), "sha256": _sha256(MAPPING)},
            "rows": len(texts),
            "train_rows": len(train_x),
            "validation_rows": len(valid_x),
        },
        "historical_validation": {
            "accuracy": accuracy_score(valid_y, validation_prediction),
            "balanced_accuracy": balanced_accuracy_score(valid_y, validation_prediction),
        },
        "fresh_corpus": {
            "in_catalog": {
                "rows": len(in_rows),
                "correct_family": sum(bool(row["correct"]) for row in in_rows),
            },
            "out_of_catalog": {
                "rows": len(out_rows),
                "honest_abstentions": sum(bool(row["correct"]) for row in out_rows),
            },
        },
        "timing_seconds": {
            "training": training_seconds,
            "fresh_total": inference_seconds,
            "fresh_per_row_mean": inference_seconds / len(rows),
        },
        "rows": rows,
    }
    _write_lf(OUTPUT, result)
    print(
        json.dumps(
            {
                "training_sources": result["training_sources"],
                "historical_validation": result["historical_validation"],
                "fresh_corpus": result["fresh_corpus"],
                "timing_seconds": result["timing_seconds"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
