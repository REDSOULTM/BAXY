"""Measure complementarity and safe calibration of lexical shortlist heads."""

from __future__ import annotations

import collections
import itertools
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT, ROOT / "src", ROOT / "scripts", Path(__file__).parent):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import numpy as np  # noqa: E402
from scipy.sparse import hstack  # noqa: E402
from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: E402
from sklearn.pipeline import FeatureUnion  # noqa: E402
from sklearn.svm import LinearSVC  # noqa: E402

import benchmark_operation_shortlist_balancing as source  # noqa: E402
from probe_operation_shortlist_current_review import _resources  # noqa: E402
from scripts.measure_mind_budget import write_json_atomic  # noqa: E402


REPORT = ROOT / "artifacts/research/operation_shortlist_balancing_ensemble_v1.json"
V1_ASSETS = ROOT / "artifacts/research/operation_shortlist_v1"
NO_ACTION = source.NO_ACTION


def _features() -> FeatureUnion:
    return FeatureUnion(
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


def _align(scores: np.ndarray, native: list[str], classes: list[str]) -> np.ndarray:
    aligned = np.full((len(scores), len(classes)), -20.0, dtype=np.float32)
    output_index = {label: index for index, label in enumerate(classes)}
    for native_index, label in enumerate(native):
        aligned[:, output_index[label]] = scores[:, native_index]
    return aligned


def _standardise(scores: np.ndarray) -> np.ndarray:
    mean = np.mean(scores, axis=1, keepdims=True)
    scale = np.std(scores, axis=1, keepdims=True)
    return (scores - mean) / np.maximum(scale, 1e-6)


def _top1(scores: np.ndarray, classes: list[str]) -> list[str]:
    return [classes[index] for index in np.argmax(scores, axis=1)]


def _accuracy(predictions: list[str], expected: list[tuple[frozenset[str], ...]]) -> float:
    return round(
        sum(any({prediction} == option for option in target) for prediction, target in zip(predictions, expected, strict=True))
        / len(expected),
        6,
    )


def probe() -> dict[str, Any]:
    mtop_rows, mtop_manifest, identity = source.mtop._load_development(
        source.mtop.DEVELOPMENT_CORPUS,
        source.mtop.MANIFEST,
    )
    training = source._training_rows(mtop_rows)
    features = _features()
    train_matrix = features.fit_transform([row[0] for row in training])
    labels = [row[1] for row in training]

    validation_rows = [
        row
        for row in mtop_rows
        if row["split"] == "validation"
        and source.shortlist._mtop_label(row) is not None
    ]
    current_rows = source._read_jsonl(source.CURRENT)
    r4_source = json.loads(source.R4.read_text(encoding="utf-8"))
    r4_rows = r4_source["samples"]
    evaluation = {
        "validation": (
            [str(row["text"]) for row in validation_rows],
            [
                (frozenset({str(source.shortlist._mtop_label(row))}),)
                for row in validation_rows
            ],
        ),
        "r4": (
            [str(row["text"]) for row in r4_rows],
            [
                (
                    frozenset(
                        str(value)
                        for value in row["expected"]["intent_operations"]
                    )
                    or frozenset({NO_ACTION}),
                )
                for row in r4_rows
            ],
        ),
        "current": (
            [str(row["text"]) for row in current_rows],
            [
                tuple(
                    frozenset(str(value) for value in operations)
                    for operations in row["compatible_terminal_operation_sets"]
                )
                or (frozenset({NO_ACTION}),)
                for row in current_rows
            ],
        ),
    }
    matrices = {
        name: features.transform(texts)
        for name, (texts, _expected) in evaluation.items()
    }
    models: dict[str, LinearSVC] = {}
    for name, power in (("v2_unweighted", 0.0), ("v2_sqrt", 0.5), ("v2_balanced", 1.0)):
        models[name] = LinearSVC(
            C=0.5,
            class_weight=None if power == 0.0 else source._weights(labels, power),
            dual="auto",
            max_iter=10_000,
            random_state=0,
        ).fit(train_matrix, labels)

    v1_words, v1_characters, v1_classes, v1_coefficients, v1_intercept = _resources(V1_ASSETS)
    classes = sorted(
        set(v1_classes)
        | {str(value) for model in models.values() for value in model.classes_}
    )
    scores: dict[str, dict[str, np.ndarray]] = collections.defaultdict(dict)
    for split, (texts, _expected) in evaluation.items():
        v1_matrix = hstack(
            (v1_words.transform(texts), v1_characters.transform(texts)),
            format="csr",
        )
        scores[split]["v1"] = _align(
            np.asarray(v1_matrix @ v1_coefficients.T + v1_intercept),
            list(v1_classes),
            classes,
        )
        for name, model in models.items():
            scores[split][name] = _align(
                np.asarray(model.decision_function(matrices[split]), dtype=np.float32),
                [str(value) for value in model.classes_],
                classes,
            )

    names = ["v1", *models]
    model_predictions = {
        split: {
            name: _top1(split_scores[name], classes)
            for name in names
        }
        for split, split_scores in scores.items()
    }
    current_expected = evaluation["current"][1]
    current_identity_indices = [
        index
        for index, target in enumerate(current_expected)
        if target != (frozenset({NO_ACTION}),)
    ]
    current_no_action_indices = [
        index
        for index, target in enumerate(current_expected)
        if target == (frozenset({NO_ACTION}),)
    ]
    individual = {
        name: {
            **{
                split: _accuracy(model_predictions[split][name], expected)
                for split, (_texts, expected) in evaluation.items()
            },
            "current_identity": _accuracy(
                [
                    model_predictions["current"][name][index]
                    for index in current_identity_indices
                ],
                [current_expected[index] for index in current_identity_indices],
            ),
            "current_no_action": _accuracy(
                [
                    model_predictions["current"][name][index]
                    for index in current_no_action_indices
                ],
                [current_expected[index] for index in current_no_action_indices],
            ),
        }
        for name in names
    }
    oracle = {
        split: round(
            sum(
                any(
                    any({model_predictions[split][name][index]} == option for option in target)
                    for name in names
                )
                for index, target in enumerate(expected)
            )
            / len(expected),
            6,
        )
        for split, (_texts, expected) in evaluation.items()
    }

    standard = {
        split: {name: _standardise(value) for name, value in split_scores.items()}
        for split, split_scores in scores.items()
    }
    no_action_index = classes.index(NO_ACTION)
    blends = []
    steps = 10
    for weights in itertools.product(range(steps + 1), repeat=len(names)):
        if sum(weights) != steps:
            continue
        for no_action_offset in (-0.5, -0.25, 0.0, 0.25, 0.5):
            metrics: dict[str, float] = {}
            for split, (_texts, expected) in evaluation.items():
                blended = sum(
                    standard[split][name] * (weights[index] / steps)
                    for index, name in enumerate(names)
                )
                blended = blended.copy()
                blended[:, no_action_index] += no_action_offset
                predictions = _top1(blended, classes)
                metrics[split] = _accuracy(predictions, expected)
                if split == "current":
                    identity_indices = [
                        index
                        for index, target in enumerate(expected)
                        if target != (frozenset({NO_ACTION}),)
                    ]
                    no_action = [
                        index
                        for index, target in enumerate(expected)
                        if target == (frozenset({NO_ACTION}),)
                    ]
                    metrics["current_identity"] = _accuracy(
                        [predictions[index] for index in identity_indices],
                        [expected[index] for index in identity_indices],
                    )
                    metrics["current_no_action"] = _accuracy(
                        [predictions[index] for index in no_action],
                        [expected[index] for index in no_action],
                    )
            blends.append(
                {
                    "weights": {
                        name: weights[index] / steps
                        for index, name in enumerate(names)
                    },
                    "no_action_offset": no_action_offset,
                    **metrics,
                }
            )
    best_r4_safe = max(
        (
            row
            for row in blends
            if row["current_no_action"] >= individual["v1"]["current_no_action"]
        ),
        key=lambda row: (row["r4"], row["current_identity"], row["validation"]),
    )
    best_joint = max(
        blends,
        key=lambda row: (
            min(row["r4"], row["validation"], row["current_no_action"]),
            row["r4"] + row["current_identity"] + row["current_no_action"],
        ),
    )
    report = {
        "schema": "baxy.operation-shortlist-balancing-ensemble.v1",
        "scope": "opened_development_only_no_promotion",
        "sources": {
            "training_sha256": source.EXPECTED_TRAINING_SHA256,
            "r4_selected_identity_sha256": r4_source["source"]["selected_identity_sha256"],
            "mtop_development_sha256": identity.corpus.sha256,
            "mtop_manifest_sha256": identity.manifest.sha256,
            "mtop_map_sha256": mtop_manifest["source"]["map_sha256"],
            "mtop_test_content_read": False,
        },
        "individual": individual,
        "top1_oracle": oracle,
        "best_r4_preserving_v1_current_accuracy": best_r4_safe,
        "best_joint": best_joint,
        "blend_count": len(blends),
    }
    source.mtop._assert_input_identity_stable(identity)
    write_json_atomic(REPORT, report)
    return report


def main() -> int:
    print(json.dumps(probe(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
