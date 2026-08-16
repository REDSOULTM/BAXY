"""Measure a family classifier without training on the frozen 147-case gate.

The real-paraphrase gate is the first six alphabetically sorted qualifying
texts per historical operation family.  This probe rebuilds the exact 1,002-row
population, removes every frozen gate text before fitting, chooses all
hyperparameters on a deterministic development split of the remaining rows,
and opens the frozen gate once with the selected configuration.

The output is advisory retrieval evidence only.  It neither selects a leaf
operation nor grants execution authority, executes no effect, and does not
touch the installed runtime or its manifest.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scripts.measure_mind_budget import (  # noqa: E402
    DEFAULT_CORE_CANDIDATES,
    current_core_capabilities,
    discover_core,
    write_json_atomic,
)

from experiments.mind_router_spike.probe_paraphrase_tool_quality import (  # noqa: E402
    _TECHNICAL,
    _oracle,
)

OUTPUT = (
    REPO
    / "artifacts"
    / "fixes"
    / "heldout_family_classifier_20260801.json"
)


def _normal_key(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(
        "".join(character if character.isalnum() else " " for character in normalized)
        .split()
    )


def _qualifying_pool(catalog_names: tuple[str, ...]) -> list[dict[str, Any]]:
    from baxy_mind.effect_intent import (
        resolve_explicit_clarification,
        resolve_explicit_effects,
    )

    families = {name.split(".", 1)[0] for name in catalog_names}
    source = REPO / "tests" / "data" / "historical_messages.jsonl"
    pool: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line in source.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("class") != "user_mission":
            continue
        if row.get("language") not in ("es", "en"):
            continue
        operations = row.get("operations") or []
        if len(operations) != 1:
            continue
        family = str(operations[0]).split(".", 1)[0]
        if family not in families or family == "memory":
            continue
        text = (row.get("text_literal") or "").strip().strip("«»\"”“").strip()
        if not text or not 8 <= len(text) <= 70 or text in seen:
            continue
        if _TECHNICAL.search(text):
            continue
        if resolve_explicit_effects(text, catalog_names, ()) is not None:
            continue
        if resolve_explicit_clarification(text, catalog_names) is not None:
            continue
        seen.add(text)
        pool.append(
            {
                "text": text,
                "family": family,
                "label": str(operations[0]),
                "language": str(row.get("language")),
            }
        )
    return sorted(pool, key=lambda item: item["text"])


def _historical_support_pool(
    catalog_names: tuple[str, ...],
    holdout_keys: set[str],
) -> list[dict[str, Any]]:
    """Return non-holdout single-family missions, including recogniser-owned rows."""

    families = {name.split(".", 1)[0] for name in catalog_names}
    source = REPO / "tests" / "data" / "historical_messages.jsonl"
    pool: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line in source.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("class") != "user_mission":
            continue
        if row.get("language") not in ("es", "en"):
            continue
        operations = row.get("operations") or []
        if len(operations) != 1:
            continue
        family = str(operations[0]).split(".", 1)[0]
        if family not in families or family == "memory":
            continue
        text = (row.get("text_literal") or "").strip().strip("«»\"”“").strip()
        key = _normal_key(text)
        if (
            not text
            or not 4 <= len(text) <= 160
            or not key
            or key in holdout_keys
            or key in seen
            or _TECHNICAL.search(text)
        ):
            continue
        seen.add(key)
        pool.append(
            {
                "text": text,
                "family": family,
                "label": str(operations[0]),
                "language": str(row.get("language")),
            }
        )
    return sorted(pool, key=lambda item: item["text"])


def _catalog_seed_pool(
    capabilities: list[dict[str, Any]],
    holdout_keys: set[str],
) -> list[dict[str, Any]]:
    """Represent every current family with authenticated catalogue prose."""

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for capability in capabilities:
        name = str(capability["name"])
        family = name.split(".", 1)[0]
        description = str(capability.get("description") or "").strip()
        for text in (
            description,
            f"{name.replace('.', ' ')}: {description}",
        ):
            key = _normal_key(text)
            if not key or key in holdout_keys or key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "text": text,
                    "family": family,
                    "label": name,
                    "language": "catalogue",
                }
            )
    return rows


def _development_split(
    training_pool: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Choose validation rows per family without looking at model output."""

    by_family: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in training_pool:
        by_family[row["family"]].append(row)
    fit: list[dict[str, Any]] = []
    validation: list[dict[str, Any]] = []
    for family in sorted(by_family):
        rows = sorted(
            by_family[family],
            key=lambda row: hashlib.sha256(
                row["text"].encode("utf-8")
            ).digest(),
        )
        if len(rows) < 2:
            fit.extend(rows)
            continue
        validation_count = max(1, min(len(rows) // 5, 8))
        validation.extend(rows[:validation_count])
        fit.extend(rows[validation_count:])
    return fit, validation


def _universal_holdout(
    rows: list[dict[str, Any]],
    *,
    cases: int = 20,
) -> list[dict[str, Any]]:
    """Freeze one unused long-tail paraphrase from each of twenty families."""

    by_family: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        by_family[row["family"]].append(row)
    selected: list[dict[str, Any]] = []
    for family in sorted(by_family):
        candidates = sorted(
            by_family[family],
            key=lambda row: hashlib.sha256(
                ("universal-v1\0" + row["text"]).encode("utf-8")
            ).digest(),
        )
        if candidates:
            selected.append(candidates[0])
        if len(selected) == cases:
            break
    if len(selected) != cases:
        raise RuntimeError("the universal holdout could not cover twenty families")
    return selected


def _row_normalize(scores):
    import numpy as np

    matrix = np.asarray(scores, dtype=np.float64)
    if matrix.ndim == 1:
        matrix = np.column_stack((-matrix, matrix))
    means = matrix.mean(axis=1, keepdims=True)
    std = matrix.std(axis=1, keepdims=True)
    return (matrix - means) / np.maximum(std, 1e-9)


def _accuracy(expected: list[str], predicted: list[str]) -> float:
    if not expected:
        return 0.0
    return sum(a == b for a, b in zip(expected, predicted, strict=True)) / len(
        expected
    )


def _fit_lexical(texts: list[str], labels: list[str], c_value: float):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.pipeline import FeatureUnion, Pipeline
    from sklearn.svm import LinearSVC

    features = FeatureUnion(
        [
            (
                "characters",
                TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=(2, 5),
                    min_df=1,
                    sublinear_tf=True,
                    strip_accents="unicode",
                    max_features=120_000,
                ),
            ),
            (
                "words",
                TfidfVectorizer(
                    analyzer="word",
                    ngram_range=(1, 2),
                    min_df=1,
                    sublinear_tf=True,
                    strip_accents="unicode",
                    max_features=60_000,
                ),
            ),
        ],
        transformer_weights={"characters": 1.0, "words": 1.5},
    )
    model = Pipeline(
        [
            ("features", features),
            (
                "classifier",
                LinearSVC(
                    C=c_value,
                    class_weight="balanced",
                    dual="auto",
                    max_iter=20_000,
                    random_state=0,
                ),
            ),
        ]
    )
    return model.fit(texts, labels)


def _fit_semantic(matrix, labels: list[str], c_value: float):
    from sklearn.svm import LinearSVC

    return LinearSVC(
        C=c_value,
        class_weight="balanced",
        dual="auto",
        max_iter=20_000,
        random_state=0,
    ).fit(matrix, labels)


def _aligned_scores(model: Any, values: Any, families: list[str]):
    import numpy as np

    scores = _row_normalize(model.decision_function(values))
    classes = [str(value) for value in model.classes_]
    aligned = np.full((scores.shape[0], len(families)), -10.0, dtype=np.float64)
    for source, family in enumerate(classes):
        aligned[:, families.index(family)] = scores[:, source]
    return aligned


def _predict_from_scores(scores, families: list[str]) -> tuple[list[str], list[float]]:
    import numpy as np

    order = np.argsort(scores, axis=1)
    winners = order[:, -1]
    margins = scores[np.arange(len(scores)), order[:, -1]] - scores[
        np.arange(len(scores)), order[:, -2]
    ]
    return [families[int(index)] for index in winners], [float(x) for x in margins]


def _encode(texts: list[str]):
    import numpy as np

    from baxy_mind.router import ProcessIntentRouter

    inherited = os.environ.get("PYTHONPATH", "")
    os.environ["PYTHONPATH"] = str(SRC) + (
        os.pathsep + inherited if inherited else ""
    )
    router = ProcessIntentRouter()
    try:
        if not router.try_ready(180.0):
            raise RuntimeError("the attested E5 worker did not become ready")
        batches = [
            router.encode(texts[start : start + 1_024], timeout=180.0)
            for start in range(0, len(texts), 1_024)
        ]
        return np.vstack(batches)
    finally:
        router.close()


def run(output: Path) -> dict[str, Any]:
    import numpy as np

    capabilities = current_core_capabilities(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES))
    )
    catalog_names = tuple(str(item["name"]) for item in capabilities)
    holdout = _oracle(catalog_names)
    pool = _qualifying_pool(catalog_names)
    holdout_keys = {_normal_key(row["text"]) for row in holdout}
    qualifying_training = [
        row for row in pool if _normal_key(row["text"]) not in holdout_keys
    ]
    universal_holdout = _universal_holdout(qualifying_training)
    universal_keys = {_normal_key(row["text"]) for row in universal_holdout}
    qualifying_training = [
        row
        for row in qualifying_training
        if _normal_key(row["text"]) not in universal_keys
    ]
    support_pool = _historical_support_pool(catalog_names, holdout_keys)
    catalog_seeds = _catalog_seed_pool(capabilities, holdout_keys)
    training_by_key: dict[str, dict[str, Any]] = {}
    for row in qualifying_training + support_pool + catalog_seeds:
        if _normal_key(row["text"]) in universal_keys:
            continue
        training_by_key.setdefault(_normal_key(row["text"]), row)
    training_pool = list(training_by_key.values())
    development_fit, development_validation = _development_split(training_pool)

    all_rows = development_fit + development_validation + holdout + universal_holdout
    all_embeddings = _encode([row["text"] for row in all_rows])
    fit_stop = len(development_fit)
    validation_stop = fit_stop + len(development_validation)
    dev_fit_embeddings = all_embeddings[:fit_stop]
    validation_embeddings = all_embeddings[fit_stop:validation_stop]
    holdout_stop = validation_stop + len(holdout)
    holdout_embeddings = all_embeddings[validation_stop:holdout_stop]
    universal_embeddings = all_embeddings[holdout_stop:]

    fit_texts = [row["text"] for row in development_fit]
    fit_labels = [row["family"] for row in development_fit]
    validation_texts = [row["text"] for row in development_validation]
    validation_labels = [row["family"] for row in development_validation]
    families = sorted({row["family"] for row in training_pool})
    missing = sorted({row["family"] for row in holdout} - set(families))
    if missing:
        raise RuntimeError(f"families have no training examples: {missing}")

    candidates: list[dict[str, Any]] = []
    for lexical_c in (0.1, 0.3, 1.0, 3.0):
        lexical = _fit_lexical(fit_texts, fit_labels, lexical_c)
        lexical_scores = _aligned_scores(
            lexical.named_steps["classifier"],
            lexical.named_steps["features"].transform(validation_texts),
            families,
        )
        for semantic_c in (0.1, 0.3, 1.0, 3.0):
            semantic = _fit_semantic(dev_fit_embeddings, fit_labels, semantic_c)
            semantic_scores = _aligned_scores(
                semantic, validation_embeddings, families
            )
            for semantic_weight in (0.0, 0.25, 0.5, 0.75, 1.0):
                scores = (
                    (1.0 - semantic_weight) * lexical_scores
                    + semantic_weight * semantic_scores
                )
                predicted, margins = _predict_from_scores(scores, families)
                candidates.append(
                    {
                        "lexical_c": lexical_c,
                        "semantic_c": semantic_c,
                        "semantic_weight": semantic_weight,
                        "accuracy": _accuracy(validation_labels, predicted),
                        "mean_margin": float(np.mean(margins)),
                    }
                )
    selected = max(
        candidates,
        key=lambda item: (
            item["accuracy"],
            item["mean_margin"],
            -abs(item["semantic_weight"] - 0.5),
            -item["lexical_c"],
            -item["semantic_c"],
        ),
    )

    training_texts = [row["text"] for row in training_pool]
    training_labels = [row["family"] for row in training_pool]
    training_embeddings = np.vstack(
        (dev_fit_embeddings, validation_embeddings)
    )
    lexical = _fit_lexical(
        training_texts, training_labels, float(selected["lexical_c"])
    )
    semantic = _fit_semantic(
        training_embeddings, training_labels, float(selected["semantic_c"])
    )
    lexical_scores = _aligned_scores(
        lexical.named_steps["classifier"],
        lexical.named_steps["features"].transform(
            [row["text"] for row in holdout]
        ),
        families,
    )
    semantic_scores = _aligned_scores(semantic, holdout_embeddings, families)
    lexical_predicted, _ = _predict_from_scores(lexical_scores, families)
    semantic_predicted, _ = _predict_from_scores(semantic_scores, families)
    holdout_scores = (
        (1.0 - float(selected["semantic_weight"])) * lexical_scores
        + float(selected["semantic_weight"]) * semantic_scores
    )
    holdout_predicted, holdout_margins = _predict_from_scores(
        holdout_scores, families
    )
    expected = [row["family"] for row in holdout]
    universal_lexical_scores = _aligned_scores(
        lexical.named_steps["classifier"],
        lexical.named_steps["features"].transform(
            [row["text"] for row in universal_holdout]
        ),
        families,
    )
    universal_semantic_scores = _aligned_scores(
        semantic,
        universal_embeddings,
        families,
    )
    universal_lexical_predicted, _ = _predict_from_scores(
        universal_lexical_scores,
        families,
    )
    universal_semantic_predicted, _ = _predict_from_scores(
        universal_semantic_scores,
        families,
    )
    universal_expected = [row["family"] for row in universal_holdout]
    right = sum(
        actual == predicted
        for actual, predicted in zip(expected, holdout_predicted, strict=True)
    )
    by_family: dict[str, dict[str, int]] = {}
    for family in sorted(set(expected)):
        indexes = [index for index, value in enumerate(expected) if value == family]
        by_family[family] = {
            "cases": len(indexes),
            "right": sum(
                expected[index] == holdout_predicted[index] for index in indexes
            ),
            "training_rows": sum(
                row["family"] == family for row in training_pool
            ),
        }

    report = {
        "schema": "baxy.heldout-family-classifier.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "effects_executed": 0,
        "installation_touched": False,
        "runtime_manifest_changed": False,
        "population": {
            "qualifying": len(pool),
            "frozen_holdout": len(holdout),
            "qualifying_training_after_holdout_removal": len(
                qualifying_training
            ),
            "broader_historical_support_before_deduplication": len(
                support_pool
            ),
            "authenticated_catalogue_seeds_before_deduplication": len(
                catalog_seeds
            ),
            "training_after_holdout_removal": len(training_pool),
            "development_fit": len(development_fit),
            "development_validation": len(development_validation),
            "text_overlap_between_training_and_holdout": len(
                holdout_keys & {_normal_key(row["text"]) for row in training_pool}
            ),
            "universal_holdout": len(universal_holdout),
            "text_overlap_between_training_and_universal_holdout": len(
                universal_keys
                & {_normal_key(row["text"]) for row in training_pool}
            ),
        },
        "selection": {
            **selected,
            "candidate_configurations": len(candidates),
            "chosen_only_from_development_validation": True,
        },
        "holdout": {
            "right": right,
            "cases": len(holdout),
            "accuracy": round(right / len(holdout), 4),
            "target_right": math.ceil(0.70 * len(holdout)),
            "target_met": right >= math.ceil(0.70 * len(holdout)),
            "component_accuracy": {
                "lexical": round(_accuracy(expected, lexical_predicted), 4),
                "semantic_e5": round(_accuracy(expected, semantic_predicted), 4),
                "selected_blend": round(right / len(holdout), 4),
            },
            "by_family": by_family,
            "predictions": [
                {
                    "case_id": row["case_id"],
                    "text": row["text"],
                    "expected_family": row["family"],
                    "predicted_family": predicted,
                    "lexical_predicted_family": lexical_prediction,
                    "semantic_predicted_family": semantic_prediction,
                    "right": row["family"] == predicted,
                    "margin": round(margin, 6),
                }
                for row, predicted, lexical_prediction, semantic_prediction, margin in zip(
                    holdout,
                    holdout_predicted,
                    lexical_predicted,
                    semantic_predicted,
                    holdout_margins,
                    strict=True,
                )
            ],
        },
        "universal_holdout": {
            "cases": len(universal_holdout),
            "families": len({row["family"] for row in universal_holdout}),
            "lexical_right": sum(
                expected_family == predicted_family
                for expected_family, predicted_family in zip(
                    universal_expected,
                    universal_lexical_predicted,
                    strict=True,
                )
            ),
            "lexical_accuracy": round(
                _accuracy(universal_expected, universal_lexical_predicted),
                4,
            ),
            "semantic_e5_accuracy": round(
                _accuracy(universal_expected, universal_semantic_predicted),
                4,
            ),
            "rows": [
                {
                    "text": row["text"],
                    "expected_family": row["family"],
                    "lexical_predicted_family": predicted,
                    "right": row["family"] == predicted,
                }
                for row, predicted in zip(
                    universal_holdout,
                    universal_lexical_predicted,
                    strict=True,
                )
            ],
        },
        "method": (
            "A class-balanced LinearSVC over word+character TF-IDF is blended "
            "with a class-balanced LinearSVC over the attested multilingual E5 "
            "embeddings. C values and blend weight are selected on a deterministic "
            "per-family development split. Training includes the other long-tail "
            "rows plus other historical single-family missions, including the "
            "recogniser-owned canonical phrasings needed to represent four absent "
            "classes, plus authenticated capability descriptions so every current "
            "family is represented. Normalised duplicates of all 147 frozen gate "
            "texts are removed before every fit and the gate is opened only after "
            "selection."
        ),
        "authority": (
            "The classifier produces a family hint only. It does not select a "
            "leaf, satisfy arguments, bypass grounding, or grant an effect."
        ),
    }
    write_json_atomic(output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    report = run(args.output)
    print(
        json.dumps(
            {
                "population": report["population"],
                "selection": report["selection"],
                "holdout": {
                    key: value
                    for key, value in report["holdout"].items()
                    if key not in ("predictions", "by_family")
                },
                "artifact": str(args.output),
            },
            ensure_ascii=False,
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
