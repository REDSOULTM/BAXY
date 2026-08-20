"""Train an E5 linear head on inherited current-catalog FunctionGemma rows."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import accuracy_score, balanced_accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.svm import LinearSVC

REPO = Path(__file__).resolve().parents[2]
for import_root in (REPO, REPO / "src"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from baxy_mind.router import SemanticEncoder  # noqa: E402

CORPUS = REPO / "artifacts/development/goal03_fresh_paraphrase_corpus.v1.jsonl"
UNION = REPO / "artifacts/development/goal03_frozen_operation_ranker_v1.json"
DEFAULT_TRAINING = Path(
    r"C:\Users\usuario\Desktop\ETC\Programacion\BAXY\artifacts\research"
    r"\functiongemma_training_corpus.v3.jsonl"
)
DEFAULT_OUTPUT = REPO / "artifacts/development/goal03_semantic_operation_classifier_v1.json"
NO_ACTION = "__no_action__"


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalise(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text).casefold()
    return re.sub(r"[^a-z0-9]+", " ", folded).strip()


def _write_lf(path: Path, value: dict[str, Any]) -> None:
    serialized = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(serialized)


def _top_hits(
    scores: np.ndarray,
    classes: np.ndarray,
    expected: list[set[str]],
    indices: list[int],
    count: int,
) -> int:
    rankings = np.argsort(-scores[indices], axis=1)[:, :count]
    return sum(
        bool(expected[row_index] & {str(classes[value]) for value in ranking})
        for row_index, ranking in zip(indices, rankings, strict=True)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--training", type=Path, default=DEFAULT_TRAINING)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    args = parser.parse_args()
    training_path = args.training.resolve(strict=True)
    training = _jsonl(training_path)
    corpus = _jsonl(CORPUS)
    union_rows = {
        str(row["case_id"]): row
        for row in json.loads(UNION.read_text(encoding="utf-8"))["rows"]
    }
    training_texts = [str(row["text"]) for row in training]
    training_labels = [str(row["operation"]) for row in training]
    train_x, valid_x, train_y, valid_y = train_test_split(
        training_texts,
        training_labels,
        test_size=0.2,
        random_state=20260820,
        stratify=training_labels,
    )
    encoder = SemanticEncoder(device=args.device)
    encode_started = time.perf_counter()
    train_vectors = encoder.encode(train_x, prefix="query")
    valid_vectors = encoder.encode(valid_x, prefix="query")
    corpus_vectors = encoder.encode(
        [str(row["text"]) for row in corpus],
        prefix="query",
    )
    encode_seconds = time.perf_counter() - encode_started

    candidates: list[tuple[float, float, LinearSVC]] = []
    for c in (0.1, 0.3, 1.0, 3.0):
        classifier = LinearSVC(
            C=c,
            class_weight="balanced",
            random_state=20260820,
        )
        classifier.fit(train_vectors, train_y)
        prediction = classifier.predict(valid_vectors)
        candidates.append(
            (
                balanced_accuracy_score(valid_y, prediction),
                accuracy_score(valid_y, prediction),
                classifier,
            )
        )
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    validation_balanced, validation_accuracy, classifier = candidates[0]
    classes = classifier.classes_
    started = time.perf_counter()
    scores = np.asarray(classifier.decision_function(corpus_vectors))
    inference_seconds = time.perf_counter() - started
    class_index = {str(value): index for index, value in enumerate(classes)}
    expected = [
        set(str(value) for value in row.get("expected_operations") or [])
        for row in corpus
    ]
    in_indices = [index for index, row in enumerate(corpus) if row["in_catalog"]]
    out_indices = [index for index, row in enumerate(corpus) if not row["in_catalog"]]

    rows: list[dict[str, Any]] = []
    union_hits: dict[int, int] = {16: 0, 28: 0}
    union_abstentions: dict[int, int] = {16: 0, 28: 0}
    for index, source in enumerate(corpus):
        ranking_indices = np.argsort(-scores[index])
        ranking = [str(classes[value]) for value in ranking_indices]
        inherited = union_rows[str(source["case_id"])]
        selected_by_budget: dict[str, str] = {}
        for budget, per_ranker in ((16, 8), (28, 14)):
            offered = list(
                dict.fromkeys(
                    inherited["top_28"][:per_ranker]
                    + inherited["e5_top_28"][:per_ranker]
                    + [NO_ACTION]
                )
            )
            offered = [value for value in offered if value in class_index]
            selected = max(offered, key=lambda value: scores[index, class_index[value]])
            selected_by_budget[str(budget)] = selected
            if source["in_catalog"]:
                union_hits[budget] += selected in expected[index]
            else:
                union_abstentions[budget] += selected == NO_ACTION
        rows.append(
            {
                "case_id": source["case_id"],
                "in_catalog": bool(source["in_catalog"]),
                "expected_operations": sorted(expected[index]),
                "global_top_5": ranking[:5],
                "union_selection": selected_by_budget,
            }
        )

    training_normalised = {_normalise(text) for text in training_texts}
    corpus_normalised = {_normalise(str(row["text"])) for row in corpus}
    result = {
        "schema": "baxy.goal03-semantic-operation-classifier.v1",
        "corpus": {"path": str(CORPUS.relative_to(REPO)), "sha256": _sha256(CORPUS)},
        "training": {
            "path": str(training_path),
            "sha256": _sha256(training_path),
            "rows": len(training),
            "classes": len(set(training_labels)),
            "normalised_exact_overlap_with_fresh": len(
                training_normalised & corpus_normalised
            ),
        },
        "model_selection": {
            "selected_c": classifier.C,
            "validation_rows": len(valid_x),
            "validation_accuracy": validation_accuracy,
            "validation_balanced_accuracy": validation_balanced,
            "all_candidates": [
                {"c": item[2].C, "balanced_accuracy": item[0], "accuracy": item[1]}
                for item in candidates
            ],
        },
        "fresh_global": {
            "in_catalog_rows": len(in_indices),
            **{
                f"expected_top_{count}": _top_hits(
                    scores, classes, expected, in_indices, count
                )
                for count in (1, 2, 3, 5, 8, 12, 28)
            },
            "out_of_catalog_rows": len(out_indices),
            "honest_abstentions_top_1": sum(
                str(classes[int(np.argmax(scores[index]))]) == NO_ACTION
                for index in out_indices
            ),
        },
        "fresh_union_selection": {
            str(budget): {
                "selected_expected": union_hits[budget],
                "honest_abstentions": union_abstentions[budget],
            }
            for budget in (16, 28)
        },
        "timing_seconds": {
            "encode_training_validation_and_fresh": encode_seconds,
            "linear_head_fresh_total": inference_seconds,
            "linear_head_fresh_per_row_mean": inference_seconds / len(corpus),
        },
        "rows": rows,
    }
    _write_lf(args.output, result)
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "training",
                    "model_selection",
                    "fresh_global",
                    "fresh_union_selection",
                    "timing_seconds",
                )
            },
            indent=2,
            sort_keys=True,
        )
    )
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
