"""Sweep safe balancing strategies for the advisory operation shortlist.

All evaluation inputs are previously opened development data. The official
MTOP test and BAXY blind reserve remain sealed. No trained asset is promoted.
"""

from __future__ import annotations

import collections
import hashlib
import json
import math
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT, ROOT / "src", ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import numpy as np  # noqa: E402
from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: E402
from sklearn.pipeline import FeatureUnion  # noqa: E402
from sklearn.svm import LinearSVC  # noqa: E402

import build_operation_shortlist_classifier as shortlist  # noqa: E402
import measure_turn_policy_v52_mtop_validation as mtop  # noqa: E402
from scripts.measure_mind_budget import write_json_atomic  # noqa: E402


TRAINING = ROOT / "artifacts/research/functiongemma_training_corpus.v2.jsonl"
CURRENT = (
    ROOT / "artifacts/development/current_catalog_review_development.v1.jsonl"
)
EXACT = ROOT / "experiments/mind_router_spike/data/exact_operation_development.v1.jsonl"
PRODUCT = ROOT / "artifacts/fixes/current_catalog_review_product_probe_r20.json"
R4 = ROOT / "artifacts/fixes/mtop_product_validation_development_r4_current.json"
REPORT = ROOT / "artifacts/research/operation_shortlist_balancing_v1.json"
EXPECTED_TRAINING_SHA256 = (
    "6d9a9f6f2f8d23a92a30e36b5a1d880a7a36025ea6974ed4d24b155cde88f17f"
)
NO_ACTION = shortlist.NO_ACTION


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rank_metrics(
    scores: np.ndarray,
    classes: np.ndarray,
    expected: list[tuple[frozenset[str], ...]],
) -> dict[str, float]:
    order = np.argsort(-scores, axis=1)
    return {
        f"complete_top_{count}_accuracy": round(
            float(
                np.mean(
                    [
                        any(
                            option <= frozenset(classes[order[index, :count]])
                            for option in target
                        )
                        for index, target in enumerate(expected)
                    ]
                )
            ),
            6,
        )
        for count in (1, 2, 3, 5)
    }


def _score(classifier: LinearSVC, matrix: Any) -> np.ndarray:
    return np.asarray(classifier.decision_function(matrix), dtype=np.float32)


def _weights(labels: list[str], power: float) -> dict[str, float]:
    counts = collections.Counter(labels)
    total = len(labels)
    return {
        label: (total / (len(counts) * count)) ** power
        for label, count in counts.items()
    }


def _training_rows(
    mtop_rows: list[dict[str, Any]],
) -> list[tuple[str, str, str]]:
    excluded = {
        shortlist._normal_key(str(row["text"]))
        for path in (EXACT, CURRENT)
        for row in _read_jsonl(path)
    }
    raw: list[tuple[str, str, str]] = []
    for row in mtop_rows:
        label = shortlist._mtop_label(row)
        if row["split"] == "train" and label is not None:
            raw.append((str(row["text"]), label, "mtop"))
    for row in _read_jsonl(TRAINING):
        operation = str(row["operation"])
        raw.append(
            (
                str(row["text"]),
                NO_ACTION if operation == "__no_action__" else operation,
                "functiongemma",
            )
        )
    labels_by_key: dict[str, set[str]] = collections.defaultdict(set)
    first_by_key: dict[str, tuple[str, str, str]] = {}
    for text, label, source in raw:
        key = shortlist._normal_key(text)
        if not key or key in excluded:
            continue
        labels_by_key[key].add(label)
        first_by_key.setdefault(key, (text, label, source))
    return [
        first_by_key[key]
        for key in sorted(first_by_key)
        if len(labels_by_key[key]) == 1
    ]


def _strategy_indices(
    rows: list[tuple[str, str, str]], mtop_cap: int | None
) -> list[int]:
    if mtop_cap is None:
        return list(range(len(rows)))
    by_label: dict[str, list[int]] = collections.defaultdict(list)
    selected = []
    for index, (_text, label, source) in enumerate(rows):
        if source == "functiongemma":
            selected.append(index)
        else:
            by_label[label].append(index)
    for indices in by_label.values():
        indices.sort(
            key=lambda index: hashlib.sha256(
                rows[index][0].encode("utf-8")
            ).digest()
        )
        selected.extend(indices[:mtop_cap])
    return sorted(set(selected))


def benchmark() -> dict[str, Any]:
    if _sha256(TRAINING) != EXPECTED_TRAINING_SHA256:
        raise RuntimeError("the reviewed v2 training corpus identity changed")
    mtop_rows, mtop_manifest, identity = mtop._load_development(
        mtop.DEVELOPMENT_CORPUS,
        mtop.MANIFEST,
    )
    training = _training_rows(mtop_rows)
    features = FeatureUnion(
        [
            (
                "words",
                TfidfVectorizer(
                    ngram_range=(1, 2),
                    min_df=2,
                    max_features=150_000,
                    sublinear_tf=True,
                    strip_accents="unicode",
                    dtype=np.float32,
                ),
            ),
            (
                "characters",
                TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=(3, 5),
                    min_df=2,
                    max_features=220_000,
                    sublinear_tf=True,
                    strip_accents="unicode",
                    dtype=np.float32,
                ),
            ),
        ]
    )
    train_matrix = features.fit_transform([row[0] for row in training])

    validation_rows = [
        row
        for row in mtop_rows
        if row["split"] == "validation" and shortlist._mtop_label(row) is not None
    ]
    validation_matrix = features.transform([str(row["text"]) for row in validation_rows])
    validation_expected = [
        (frozenset({str(shortlist._mtop_label(row))}),)
        for row in validation_rows
    ]

    r4_source = json.loads(R4.read_text(encoding="utf-8"))
    r4_rows = r4_source["samples"]
    r4_matrix = features.transform([str(row["text"]) for row in r4_rows])
    r4_expected = [
        (
            frozenset(str(value) for value in row["expected"]["intent_operations"])
            or frozenset({NO_ACTION}),
        )
        for row in r4_rows
    ]
    r4_ood = [
        index
        for index, row in enumerate(r4_rows)
        if row["projection"]["disposition"] == "ood_no_effect"
    ]

    current_rows = _read_jsonl(CURRENT)
    current_matrix = features.transform([str(row["text"]) for row in current_rows])
    current_expected = [
        tuple(
            frozenset(str(value) for value in operations)
            for operations in row["compatible_terminal_operation_sets"]
        )
        or (frozenset({NO_ACTION}),)
        for row in current_rows
    ]
    current_identity = [
        index
        for index, target in enumerate(current_expected)
        if target != (frozenset({NO_ACTION}),)
    ]
    current_no_action = [
        index
        for index, target in enumerate(current_expected)
        if target == (frozenset({NO_ACTION}),)
    ]
    product_rows = {
        str(row["case_id"]): row
        for row in json.loads(PRODUCT.read_text(encoding="utf-8"))["rows"]
    }

    strategies = [
        ("full", None, power, c_value)
        for power, c_values in ((0.0, (0.25, 0.5, 1.0)), (0.5, (0.25, 0.5, 1.0)), (1.0, (0.25, 0.5)))
        for c_value in c_values
    ] + [
        (f"mtop_cap_{cap}", cap, 0.0, c_value)
        for cap, c_values in ((100, (0.25, 0.5, 1.0)), (250, (0.5,)), (500, (0.5,)), (1000, (0.5,)))
        for c_value in c_values
    ]
    results = []
    for name, cap, power, c_value in strategies:
        indices = _strategy_indices(training, cap)
        labels = [training[index][1] for index in indices]
        class_weight = None if power == 0.0 else _weights(labels, power)
        started = time.perf_counter()
        classifier = LinearSVC(
            C=c_value,
            class_weight=class_weight,
            dual="auto",
            max_iter=10_000,
            random_state=0,
        ).fit(train_matrix[indices], labels)
        classes = np.asarray(classifier.classes_, dtype=object)
        validation_scores = _score(classifier, validation_matrix)
        r4_scores = _score(classifier, r4_matrix)
        current_scores = _score(classifier, current_matrix)
        current_global = _rank_metrics(current_scores, classes, current_expected)
        current_identity_scores = current_scores[current_identity]
        current_identity_expected = [current_expected[index] for index in current_identity]
        current_no_action_scores = current_scores[current_no_action]
        current_no_action_expected = [current_expected[index] for index in current_no_action]
        class_index = {str(value): index for index, value in enumerate(classes)}
        candidate_scores = np.full_like(current_scores, -math.inf)
        for row_index, row in enumerate(current_rows):
            candidates = [
                NO_ACTION,
                *product_rows[str(row["case_id"])]["candidate_operations"],
            ]
            for operation in candidates:
                index = class_index.get(str(operation))
                if index is not None:
                    candidate_scores[row_index, index] = current_scores[row_index, index]
        result = {
            "name": name,
            "mtop_cap": cap,
            "class_weight_power": power,
            "c": c_value,
            "training_rows": len(indices),
            "fit_seconds": round(time.perf_counter() - started, 3),
            "mtop_validation": _rank_metrics(
                validation_scores,
                classes,
                validation_expected,
            ),
            "r4": _rank_metrics(r4_scores, classes, r4_expected),
            "r4_ood": _rank_metrics(
                r4_scores[r4_ood],
                classes,
                [r4_expected[index] for index in r4_ood],
            ),
            "current_all": current_global,
            "current_identity": _rank_metrics(
                current_identity_scores,
                classes,
                current_identity_expected,
            ),
            "current_no_action": _rank_metrics(
                current_no_action_scores,
                classes,
                current_no_action_expected,
            ),
            "current_after_product_retrieval": _rank_metrics(
                candidate_scores,
                classes,
                current_expected,
            ),
        }
        results.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)

    report = {
        "schema": "baxy.operation-shortlist-balancing-benchmark.v1",
        "scope": "opened_development_only_no_promotion",
        "source": {
            "training_sha256": EXPECTED_TRAINING_SHA256,
            "current_sha256": _sha256(CURRENT),
            "exact_sha256": _sha256(EXACT),
            "r4_selected_identity_sha256": r4_source["source"][
                "selected_identity_sha256"
            ],
            "mtop_development_sha256": identity.corpus.sha256,
            "mtop_manifest_sha256": identity.manifest.sha256,
            "mtop_map_sha256": mtop_manifest["source"]["map_sha256"],
            "mtop_test_content_read": False,
        },
        "training_rows": len(training),
        "results": results,
    }
    mtop._assert_input_identity_stable(identity)
    write_json_atomic(REPORT, report)
    return report


def main() -> int:
    report = benchmark()
    print(json.dumps({"report": str(REPORT), "runs": len(report["results"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
