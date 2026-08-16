"""Measure complementarity of frozen MTOP operation selectors.

Development-only diagnostic: official MTOP test remains sealed and no product
runtime files are read or changed.  The script trains the lexical selector on
the hash-bound train partition and compares it with an external, frozen E5
checkpoint on the validation partition.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts", Path(__file__).parent):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import measure_turn_policy_v52_mtop_validation as mtop  # noqa: E402
import train_mtop_operation_classifier as trainer  # noqa: E402
from baxy_mind.router import QUERY_PREFIX  # noqa: E402
from scripts.measure_mind_budget import write_json_atomic  # noqa: E402


DEFAULT_CHECKPOINT = Path(
    "D:/BAXYRuntime/experiments/mtop-operation-classifier-v2-balanced"
)
DEFAULT_REPORT = (
    REPO / "artifacts/research/mtop_operation_selector_ensemble_probe_v1.json"
)
DEFAULT_E5_CACHE = (
    Path(os.environ["LOCALAPPDATA"])
    / "BAXYRuntime/datasets/mtop-v1/derived/mtop_development.v1.multilingual-e5-small.npy"
)
EXPECTED_E5_SHA256 = "4d3891ea2750760071962c16ec890387668a68cf9fa2eef74e9bb7084f0c3d00"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rank_metrics(scores: Any, truth: Any) -> dict[str, float]:
    import numpy as np

    order = np.argsort(-scores, axis=1)
    return {
        f"top_{count}_accuracy": round(
            float(np.mean([truth[i] in order[i, :count] for i in range(len(truth))])),
            6,
        )
        for count in (1, 2, 3, 5)
    }


def _row_standardise(scores: Any) -> Any:
    import numpy as np

    mean = np.mean(scores, axis=1, keepdims=True)
    scale = np.std(scores, axis=1, keepdims=True)
    return (scores - mean) / np.maximum(scale, 1e-6)


def probe(args: argparse.Namespace) -> dict[str, Any]:
    import numpy as np
    import torch
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.pipeline import FeatureUnion
    from sklearn.svm import LinearSVC
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    rows, manifest, identity = mtop._load_development(
        mtop.DEVELOPMENT_CORPUS,
        mtop.MANIFEST,
    )
    labelled = [(index, row, trainer.operation_label(row)) for index, row in enumerate(rows)]
    labelled = [
        (index, row, str(label))
        for index, row, label in labelled
        if label is not None
    ]
    train_rows = [
        (index, row, label)
        for index, row, label in labelled
        if row["split"] == "train"
    ]
    validation_rows = [
        (index, row, label)
        for index, row, label in labelled
        if row["split"] == "validation"
    ]
    train_texts = [str(row["text"]) for _index, row, _label in train_rows]
    train_labels = [label for _index, _row, label in train_rows]
    validation_texts = [str(row["text"]) for _index, row, _label in validation_rows]
    validation_labels = [label for _index, _row, label in validation_rows]

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
    train_matrix = features.fit_transform(train_texts)
    lexical = LinearSVC(
        C=0.5,
        dual="auto",
        max_iter=10_000,
        random_state=0,
    ).fit(train_matrix, train_labels)
    validation_matrix = features.transform(validation_texts)
    lexical_scores_native = np.asarray(
        lexical.decision_function(validation_matrix),
        dtype=np.float32,
    )
    lexical_balanced = LinearSVC(
        C=0.5,
        class_weight="balanced",
        dual="auto",
        max_iter=10_000,
        random_state=0,
    ).fit(train_matrix, train_labels)
    lexical_balanced_scores_native = np.asarray(
        lexical_balanced.decision_function(validation_matrix),
        dtype=np.float32,
    )

    if _sha256(args.e5_cache) != EXPECTED_E5_SHA256:
        raise RuntimeError("the frozen E5 development vector identity changed")
    e5_vectors = np.load(args.e5_cache, mmap_mode="r")
    if e5_vectors.shape != (len(rows), 384):
        raise RuntimeError(f"unexpected E5 cache shape: {e5_vectors.shape}")
    e5 = LinearSVC(
        C=10.0,
        dual="auto",
        max_iter=10_000,
        random_state=0,
    ).fit(
        np.asarray(e5_vectors[[index for index, _row, _label in train_rows]]),
        train_labels,
    )
    e5_scores_native = np.asarray(
        e5.decision_function(
            np.asarray(e5_vectors[[index for index, _row, _label in validation_rows]])
        ),
        dtype=np.float32,
    )

    tokenizer = AutoTokenizer.from_pretrained(args.checkpoint, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        args.checkpoint,
        local_files_only=True,
    ).cuda().eval()
    transformer_scores_native: list[np.ndarray] = []
    with torch.inference_mode():
        for offset in range(0, len(validation_texts), args.batch_size):
            encoded = tokenizer(
                [args.query_prefix + text for text in validation_texts[offset : offset + args.batch_size]],
                padding=True,
                truncation=True,
                max_length=96,
                return_tensors="pt",
            )
            encoded = {key: value.cuda(non_blocking=True) for key, value in encoded.items()}
            with torch.autocast(device_type="cuda", dtype=torch.float16):
                logits = model(**encoded).logits
            transformer_scores_native.append(logits.float().cpu().numpy())
    transformer_scores_native_array = np.concatenate(transformer_scores_native, axis=0)

    transformer_classes = [
        str(model.config.id2label[index]) for index in range(model.config.num_labels)
    ]
    lexical_classes = [str(value) for value in lexical.classes_]
    lexical_balanced_classes = [str(value) for value in lexical_balanced.classes_]
    e5_classes = [str(value) for value in e5.classes_]
    classes = sorted(
        set(transformer_classes)
        | set(lexical_classes)
        | set(lexical_balanced_classes)
        | set(e5_classes)
    )
    class_to_id = {label: index for index, label in enumerate(classes)}

    def align(scores: Any, native_classes: list[str]) -> Any:
        aligned = np.full((len(scores), len(classes)), -20.0, dtype=np.float32)
        for native_index, label in enumerate(native_classes):
            aligned[:, class_to_id[label]] = scores[:, native_index]
        return aligned

    lexical_scores = align(lexical_scores_native, lexical_classes)
    lexical_balanced_scores = align(
        lexical_balanced_scores_native,
        lexical_balanced_classes,
    )
    e5_scores = align(e5_scores_native, e5_classes)
    transformer_scores = align(transformer_scores_native_array, transformer_classes)
    truth = np.asarray([class_to_id[label] for label in validation_labels], dtype=np.int64)
    lexical_predictions = np.argmax(lexical_scores, axis=1)
    lexical_balanced_predictions = np.argmax(lexical_balanced_scores, axis=1)
    transformer_predictions = np.argmax(transformer_scores, axis=1)
    e5_predictions = np.argmax(e5_scores, axis=1)
    lexical_exact = lexical_predictions == truth
    lexical_balanced_exact = lexical_balanced_predictions == truth
    transformer_exact = transformer_predictions == truth
    e5_exact = e5_predictions == truth
    agreements = lexical_predictions == transformer_predictions

    lexical_normal = _row_standardise(lexical_scores)
    transformer_normal = _row_standardise(transformer_scores)
    e5_normal = _row_standardise(e5_scores)
    blends: list[dict[str, Any]] = []
    for step in range(101):
        transformer_weight = step / 100.0
        blended = (
            transformer_weight * transformer_normal
            + (1.0 - transformer_weight) * lexical_normal
        )
        blends.append(
            {
                "transformer_weight": transformer_weight,
                **_rank_metrics(blended, truth),
            }
        )
    best_blend = max(blends, key=lambda row: (row["top_1_accuracy"], row["top_3_accuracy"]))
    triple_blends: list[dict[str, Any]] = []
    for transformer_step in range(0, 21):
        transformer_weight = transformer_step / 20.0
        for lexical_step in range(0, 21 - transformer_step):
            lexical_weight = lexical_step / 20.0
            e5_weight = 1.0 - transformer_weight - lexical_weight
            blended = (
                transformer_weight * transformer_normal
                + lexical_weight * lexical_normal
                + e5_weight * e5_normal
            )
            triple_blends.append(
                {
                    "transformer_weight": transformer_weight,
                    "lexical_weight": lexical_weight,
                    "e5_weight": round(e5_weight, 10),
                    **_rank_metrics(blended, truth),
                }
            )
    best_triple_blend = max(
        triple_blends,
        key=lambda row: (row["top_1_accuracy"], row["top_3_accuracy"]),
    )

    transformer_order = np.argsort(-transformer_scores, axis=1)
    candidate_reranks: list[dict[str, Any]] = []
    for candidate_count in (2, 3, 5):
        candidates = transformer_order[:, :candidate_count]
        for name, selector_scores in (
            ("lexical", lexical_scores),
            ("lexical_balanced", lexical_balanced_scores),
            ("e5", e5_scores),
        ):
            selected = np.asarray(
                [
                    row_candidates[
                        int(np.argmax(selector_scores[index, row_candidates]))
                    ]
                    for index, row_candidates in enumerate(candidates)
                ],
                dtype=np.int64,
            )
            candidate_reranks.append(
                {
                    "transformer_candidates": candidate_count,
                    "selector": name,
                    "top_1_accuracy": round(float((selected == truth).mean()), 6),
                }
            )

    specialist_groups = {
        "alarm": {
            trainer.NO_ACTION,
            "notification.cancel.latest",
            "notification.dismiss",
            "notification.schedule",
        },
        "reminder": {
            trainer.NO_ACTION,
            "reminder.create",
            "reminder.delete",
            "reminder.list",
            "reminder.resolve.exact",
        },
        "media": {
            trainer.NO_ACTION,
            "media.control",
            "media.play.query",
            "media.seek.relative",
            "media.status",
        },
    }
    operation_to_group = {
        operation: group_name
        for group_name, operations in specialist_groups.items()
        for operation in operations
        if operation != trainer.NO_ACTION
    }
    specialist_results: list[dict[str, Any]] = []
    for c_value in (0.1, 0.5, 1.0, 5.0):
        specialist_scores: dict[str, Any] = {}
        for group_name, allowed in specialist_groups.items():
            indices = [
                index for index, label in enumerate(train_labels) if label in allowed
            ]
            specialist = LinearSVC(
                C=c_value,
                class_weight="balanced",
                dual="auto",
                max_iter=10_000,
                random_state=0,
            ).fit(train_matrix[indices], [train_labels[index] for index in indices])
            specialist_scores[group_name] = align(
                np.asarray(
                    specialist.decision_function(validation_matrix),
                    dtype=np.float32,
                ),
                [str(value) for value in specialist.classes_],
            )
        for candidate_count in (2, 3, 5):
            candidates = transformer_order[:, :candidate_count]
            selected: list[int] = []
            for index, row_candidates in enumerate(candidates):
                top_label = classes[int(row_candidates[0])]
                group_name = operation_to_group.get(top_label)
                if group_name is None and top_label == trainer.NO_ACTION:
                    group_name = next(
                        (
                            operation_to_group.get(classes[int(candidate)])
                            for candidate in row_candidates[1:]
                            if operation_to_group.get(classes[int(candidate)]) is not None
                        ),
                        None,
                    )
                if group_name is None:
                    selected.append(int(row_candidates[0]))
                    continue
                allowed = specialist_groups[group_name]
                local_candidates = np.asarray(
                    [
                        int(candidate)
                        for candidate in row_candidates
                        if classes[int(candidate)] in allowed
                    ],
                    dtype=np.int64,
                )
                if len(local_candidates) < 2:
                    selected.append(int(row_candidates[0]))
                    continue
                scores = specialist_scores[group_name][index, local_candidates]
                selected.append(int(local_candidates[int(np.argmax(scores))]))
            specialist_results.append(
                {
                    "c": c_value,
                    "transformer_candidates": candidate_count,
                    "top_1_accuracy": round(
                        float((np.asarray(selected, dtype=np.int64) == truth).mean()),
                        6,
                    ),
                }
            )

    all_wrong = ~transformer_exact & ~lexical_exact & ~e5_exact
    shared_error_confusions = collections.Counter(
        (
            classes[int(truth[index])],
            classes[int(transformer_predictions[index])],
            classes[int(lexical_predictions[index])],
            classes[int(e5_predictions[index])],
        )
        for index in np.flatnonzero(all_wrong)
    )

    report = {
        "schema": "baxy.mtop-operation-selector-ensemble-probe.v1",
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "scope": "development_only_mtop_test_remains_sealed",
        "source": {
            "mtop_development_sha256": identity.corpus.sha256,
            "mtop_manifest_sha256": identity.manifest.sha256,
            "mtop_map_sha256": manifest["source"]["map_sha256"],
            "mtop_test_content_read": False,
            "transformer_checkpoint": str(args.checkpoint.resolve()),
            "e5_cache": str(args.e5_cache.resolve()),
            "e5_cache_sha256": EXPECTED_E5_SHA256,
        },
        "data": {
            "train_rows": len(train_rows),
            "validation_rows": len(validation_rows),
            "classes": classes,
        },
        "lexical": _rank_metrics(lexical_scores, truth),
        "lexical_balanced": _rank_metrics(lexical_balanced_scores, truth),
        "e5": _rank_metrics(e5_scores, truth),
        "transformer": _rank_metrics(transformer_scores, truth),
        "complementarity": {
            "agreement_cases": int(agreements.sum()),
            "agreement_rate": round(float(agreements.mean()), 6),
            "agreement_accuracy": round(float(transformer_exact[agreements].mean()), 6),
            "disagreement_cases": int((~agreements).sum()),
            "transformer_only_correct": int((transformer_exact & ~lexical_exact).sum()),
            "lexical_only_correct": int((lexical_exact & ~transformer_exact).sum()),
            "both_wrong": int((~transformer_exact & ~lexical_exact).sum()),
            "either_top_1_oracle_accuracy": round(float((transformer_exact | lexical_exact).mean()), 6),
            "all_three_wrong": int(all_wrong.sum()),
            "three_model_top_1_oracle_accuracy": round(
                float((transformer_exact | lexical_exact | e5_exact).mean()),
                6,
            ),
            "four_model_top_1_oracle_accuracy": round(
                float(
                    (
                        transformer_exact
                        | lexical_exact
                        | lexical_balanced_exact
                        | e5_exact
                    ).mean()
                ),
                6,
            ),
            "all_three_wrong_confusions": [
                {
                    "expected": expected,
                    "transformer": transformer,
                    "lexical": lexical_label,
                    "e5": e5_label,
                    "cases": count,
                }
                for (expected, transformer, lexical_label, e5_label), count
                in shared_error_confusions.most_common()
            ],
        },
        "best_validation_blend": best_blend,
        "best_validation_triple_blend": best_triple_blend,
        "candidate_reranks": candidate_reranks,
        "specialist_reranks": specialist_results,
        "all_validation_blends": blends,
        "all_validation_triple_blends": triple_blends,
    }
    mtop._assert_input_identity_stable(identity)
    write_json_atomic(args.report, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--e5-cache", type=Path, default=DEFAULT_E5_CACHE)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--query-prefix", default=QUERY_PREFIX)
    args = parser.parse_args()
    result = probe(args)
    print(
        json.dumps(
            {
                "lexical": result["lexical"],
                "lexical_balanced": result["lexical_balanced"],
                "e5": result["e5"],
                "transformer": result["transformer"],
                "complementarity": result["complementarity"],
                "best_validation_blend": result["best_validation_blend"],
                "best_validation_triple_blend": result["best_validation_triple_blend"],
                "candidate_reranks": result["candidate_reranks"],
                "specialist_reranks": result["specialist_reranks"],
                "report": str(args.report.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
