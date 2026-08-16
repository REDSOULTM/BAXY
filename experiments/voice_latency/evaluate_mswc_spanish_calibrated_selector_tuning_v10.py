"""Cross-validate a calibrated selector over cached Spanish keyword signals."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"mswc_calibrated_selector_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_FUSION = load_component(
    "evaluate_mswc_hyperspotter_ctc_fusion_tuning_v5.py",
    "_baxy_mswc_calibrated_selector_fusion_v10",
)


def word_group_folds(words: list[str], *, seed: int, fold_count: int) -> np.ndarray:
    if not words or fold_count < 2:
        raise ValueError("mswc_calibrated_selector_folds_invalid")
    fold_by_word = {
        word: int.from_bytes(
            hashlib.sha256(f"{seed}|{word}".encode("utf-8")).digest()[:4],
            "big",
        )
        % fold_count
        for word in set(words)
    }
    return np.asarray([fold_by_word[word] for word in words], dtype=np.int32)


def prepare_signal(
    scores: np.ndarray, *, selected_mask: np.ndarray | None = None
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    values = np.asarray(scores, dtype=np.float64)
    if values.ndim != 2 or not np.isfinite(values).all():
        raise ValueError("mswc_calibrated_selector_signal_invalid")
    rows, width = values.shape
    if selected_mask is not None:
        selected = np.asarray(selected_mask, dtype=bool)
        if selected.shape != values.shape or not selected.any(axis=1).all():
            raise ValueError("mswc_calibrated_selector_mask_invalid")
    else:
        selected = np.ones_like(values, dtype=bool)
    zscores = np.full_like(values, -4.0 if selected_mask is not None else 0.0)
    ranks = np.full_like(values, -1.0 if selected_mask is not None else 0.0)
    margins = np.full_like(values, -20.0 if selected_mask is not None else 0.0)
    top = np.zeros_like(values)
    top_margin = np.empty(rows, dtype=np.float64)
    row_deviation = np.empty(rows, dtype=np.float64)
    for row in range(rows):
        indexes = np.flatnonzero(selected[row])
        row_values = values[row, indexes]
        deviation = max(float(row_values.std()), 1e-8)
        zscores[row, indexes] = (row_values - float(row_values.mean())) / deviation
        order = np.argsort(row_values)
        row_ranks = np.empty_like(order)
        row_ranks[order] = np.arange(len(row_values))
        ranks[row, indexes] = row_ranks / max(1, len(row_values) - 1)
        best_local = int(np.argmax(row_values))
        best = int(indexes[best_local])
        sorted_values = np.sort(row_values)
        confidence = (
            float(sorted_values[-1] - sorted_values[-2])
            if len(sorted_values) > 1
            else 0.0
        )
        margins[row, indexes] = row_values - float(row_values.max())
        margins[row, best] = confidence
        top[row, best] = 1.0
        top_margin[row] = confidence
        row_deviation[row] = deviation
    return zscores, ranks, margins, top, top_margin, row_deviation


def apply_selector_choices(
    *, base_scores: np.ndarray, selected_candidates: np.ndarray
) -> np.ndarray:
    scores = np.asarray(base_scores, dtype=np.float64).copy()
    choices = np.asarray(selected_candidates, dtype=np.int64)
    if scores.ndim != 2 or choices.shape != (len(scores),):
        raise ValueError("mswc_calibrated_selector_choices_invalid")
    for row, candidate in enumerate(choices):
        if not 0 <= candidate < scores.shape[1]:
            raise ValueError("mswc_calibrated_selector_candidate_invalid")
        maximum = float(scores[row].max())
        if int(np.argmax(scores[row])) != candidate:
            scores[row, candidate] = np.nextafter(maximum, np.inf)
    return scores


def evaluate(
    *,
    hyper_ctc_cache_path: Path,
    whisper_cache_path: Path,
    forced_alignment_cache_path: Path,
    shortlist_cache_path: Path,
    silence_prior_cache_path: Path,
    output_path: Path,
    silence_prior_weight: float,
    calibrated_fusion_weight: float,
    fold_seed: int,
    fold_count: int,
) -> dict[str, object]:
    if (
        output_path.exists()
        or not 0.0 <= silence_prior_weight <= 2.0
        or not 0.0 <= calibrated_fusion_weight <= 1.0
        or fold_count < 2
    ):
        raise ValueError("mswc_calibrated_selector_schedule_invalid")
    hyper_ctc_cache_path = hyper_ctc_cache_path.resolve(strict=True)
    whisper_cache_path = whisper_cache_path.resolve(strict=True)
    forced_alignment_cache_path = forced_alignment_cache_path.resolve(strict=True)
    shortlist_cache_path = shortlist_cache_path.resolve(strict=True)
    silence_prior_cache_path = silence_prior_cache_path.resolve(strict=True)
    output_path = output_path.resolve()
    with np.load(hyper_ctc_cache_path, allow_pickle=False) as cache:
        if cache["schema"].tolist() != [
            "baxy.mswc-hyperspotter-ctc-score-cache.v1"
        ]:
            raise ValueError("mswc_calibrated_selector_hyper_schema_invalid")
        hyper_scores = cache["hyper_scores"].astype(np.float64)
        ctc_scores = cache["ctc_scores"].astype(np.float64)
        candidate_indexes = cache["candidate_indexes"].astype(np.int64)
        class_names = cache["class_names"].astype(str)
        candidate_words = class_names[candidate_indexes]
        query_hashes = cache["query_audio_sha256"].astype(str)
        query_words = cache["query_words"].astype(str)
    with np.load(whisper_cache_path, allow_pickle=False) as cache:
        if cache["schema"].tolist() != [
            "baxy.mswc-faster-whisper-score-cache.v1"
        ]:
            raise ValueError("mswc_calibrated_selector_whisper_schema_invalid")
        if (
            not np.array_equal(query_hashes, cache["query_audio_sha256"])
            or not np.array_equal(query_words, cache["query_words"])
            or not np.array_equal(candidate_words, cache["candidate_words"])
        ):
            raise ValueError("mswc_calibrated_selector_whisper_alignment_invalid")
        whisper_whole = cache["whole_transcript_edit"].astype(np.float64)
        whisper_token = cache["whole_or_token_edit"].astype(np.float64)
        exact_candidate_match = cache["exact_candidate_match"].astype(np.float64)
    with np.load(forced_alignment_cache_path, allow_pickle=False) as cache:
        if cache["schema"].tolist() != [
            "baxy.mswc-whisper-forced-alignment-score-cache.v1"
        ]:
            raise ValueError("mswc_calibrated_selector_forced_schema_invalid")
        if (
            not np.array_equal(query_hashes, cache["query_audio_sha256"])
            or not np.array_equal(query_words, cache["query_words"])
            or not np.array_equal(candidate_words, cache["candidate_words"])
        ):
            raise ValueError("mswc_calibrated_selector_forced_alignment_invalid")
        forced_scores = cache["scores_length_power_0_0"].astype(np.float64)
    with np.load(shortlist_cache_path, allow_pickle=False) as cache:
        if cache["schema"].tolist() != [
            "baxy.mswc-forced-alignment-shortlist.v1"
        ]:
            raise ValueError("mswc_calibrated_selector_shortlist_schema_invalid")
        if (
            not np.array_equal(query_hashes, cache["query_audio_sha256"])
            or not np.array_equal(query_words, cache["query_words"])
            or not np.array_equal(candidate_words, cache["candidate_words"])
        ):
            raise ValueError("mswc_calibrated_selector_shortlist_alignment_invalid")
        candidate_mask = cache["candidate_mask"].astype(bool)
    with np.load(silence_prior_cache_path, allow_pickle=False) as cache:
        if cache["schema"].tolist() != ["baxy.mswc-whisper-silence-prior.v1"]:
            raise ValueError("mswc_calibrated_selector_prior_schema_invalid")
        if not np.array_equal(class_names, cache["class_names"]):
            raise ValueError("mswc_calibrated_selector_prior_alignment_invalid")
        silence_prior = cache["log_probability_sum"].astype(np.float64)

    prior_matrix = silence_prior[candidate_indexes]
    calibrated_forced = forced_scores.copy()
    calibrated_forced[candidate_mask] = (
        forced_scores[candidate_mask]
        - silence_prior_weight * prior_matrix[candidate_mask]
    )
    baseline = 0.3 * _FUSION.global_standardize(
        hyper_scores
    ) + 0.7 * _FUSION.global_standardize(ctc_scores)
    calibrated_z = prepare_signal(
        calibrated_forced, selected_mask=candidate_mask
    )[0]
    calibrated_fusion = (
        (1.0 - calibrated_fusion_weight) * _FUSION.global_standardize(baseline)
        + calibrated_fusion_weight * calibrated_z
    )
    signals = [
        hyper_scores,
        ctc_scores,
        whisper_whole,
        whisper_token,
        forced_scores,
        calibrated_forced,
        baseline,
        calibrated_fusion,
    ]
    prepared = [prepare_signal(value) for value in signals[:4]]
    prepared.extend(
        [
            prepare_signal(forced_scores, selected_mask=candidate_mask),
            prepare_signal(calibrated_forced, selected_mask=candidate_mask),
            prepare_signal(baseline),
            prepare_signal(calibrated_fusion),
        ]
    )
    feature_rows = []
    labels = []
    query_ids = []
    candidate_ids = []
    for query in range(len(query_words)):
        alternatives = sorted(
            {int(np.argmax(signal[query])) for signal in signals}
        )
        top_count = sum(item[3][query] for item in prepared)
        query_context = [
            value
            for item in prepared
            for value in (item[4][query], item[5][query])
        ]
        for candidate in alternatives:
            features = [
                value
                for item in prepared
                for value in (
                    item[0][query, candidate],
                    item[1][query, candidate],
                    item[2][query, candidate],
                    item[3][query, candidate],
                )
            ]
            features.extend(query_context)
            features.extend(
                [
                    top_count[candidate],
                    float(candidate_mask[query, candidate]),
                    exact_candidate_match[query, candidate],
                    silence_prior[candidate_indexes[query, candidate]] / 30.0,
                    len(candidate_words[query, candidate]) / 16.0,
                ]
            )
            feature_rows.append(features)
            labels.append(int(candidate == 0))
            query_ids.append(query)
            candidate_ids.append(candidate)
    features = np.asarray(feature_rows, dtype=np.float64)
    labels_array = np.asarray(labels, dtype=np.uint8)
    query_ids_array = np.asarray(query_ids, dtype=np.int32)
    candidate_ids_array = np.asarray(candidate_ids, dtype=np.int32)
    folds = word_group_folds(
        query_words.tolist(), seed=fold_seed, fold_count=fold_count
    )
    from sklearn import __version__ as sklearn_version
    from sklearn.ensemble import HistGradientBoostingClassifier

    probabilities = np.empty(len(features), dtype=np.float64)
    fold_reports = []
    model_parameters = {
        "learning_rate": 0.08,
        "max_iter": 220,
        "max_leaf_nodes": 7,
        "min_samples_leaf": 5,
        "l2_regularization": 2.0,
        "class_weight": "balanced",
    }
    for fold in range(fold_count):
        training = folds[query_ids_array] != fold
        validation = folds[query_ids_array] == fold
        model = HistGradientBoostingClassifier(
            **model_parameters, random_state=fold_seed + fold
        )
        model.fit(features[training], labels_array[training])
        probabilities[validation] = model.predict_proba(features[validation])[:, 1]
        validation_queries = np.flatnonzero(folds == fold)
        correct = 0
        for query in validation_queries:
            rows = np.flatnonzero(query_ids_array == query)
            selected_row = int(rows[np.argmax(probabilities[rows])])
            correct += int(candidate_ids_array[selected_row] == 0)
        fold_reports.append(
            {
                "fold": fold,
                "word_classes": int(len(set(query_words[validation_queries]))),
                "queries": int(len(validation_queries)),
                "top1_accuracy": correct / len(validation_queries),
            }
        )
    selected_candidates = np.empty(len(query_words), dtype=np.int32)
    for query in range(len(query_words)):
        rows = np.flatnonzero(query_ids_array == query)
        selected_row = int(rows[np.argmax(probabilities[rows])])
        selected_candidates[query] = candidate_ids_array[selected_row]
    decision_scores = apply_selector_choices(
        base_scores=calibrated_fusion,
        selected_candidates=selected_candidates,
    )
    metrics = _FUSION._HYPER.hard_pair_metrics(
        scores=decision_scores, query_words=query_words.tolist()
    )
    zero_false_recall = (
        float(metrics["true_pairs_accepted_at_zero_false_pairs"])
        / float(metrics["true_pairs"])
    )
    quality_floor = {
        "hard_candidate_top1_accuracy_minimum": 0.94,
        "pair_auc_minimum": 0.99,
        "equal_error_rate_maximum": 0.05,
        "zero_false_true_pair_recall_minimum": 0.20,
    }
    accepted = (
        float(metrics["hard_candidate_top1_accuracy"])
        >= quality_floor["hard_candidate_top1_accuracy_minimum"]
        and float(metrics["pair_auc"]) >= quality_floor["pair_auc_minimum"]
        and float(metrics["equal_error_rate"])
        <= quality_floor["equal_error_rate_maximum"]
        and zero_false_recall
        >= quality_floor["zero_false_true_pair_recall_minimum"]
    )
    oracle_accuracy = float(
        np.logical_or.reduce([signal.argmax(axis=1) == 0 for signal in signals]).mean()
    )
    sha256 = _FUSION._HYPER._LOGMEL.sha256
    report: dict[str, object] = {
        "schema": "baxy.mswc-spanish-calibrated-selector-tuning.v10",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "five_fold_word_disjoint_oof_calibrated_candidate_selector",
        "sources": {
            "hyper_ctc_cache_sha256": sha256(hyper_ctc_cache_path),
            "whisper_cache_sha256": sha256(whisper_cache_path),
            "forced_alignment_cache_sha256": sha256(forced_alignment_cache_path),
            "shortlist_cache_sha256": sha256(shortlist_cache_path),
            "silence_prior_cache_sha256": sha256(silence_prior_cache_path),
        },
        "contract": {
            "fold_seed": fold_seed,
            "fold_count": fold_count,
            "fold_group": "query_word_class",
            "silence_prior_weight": silence_prior_weight,
            "calibrated_fusion_weight": calibrated_fusion_weight,
            "selector": "HistGradientBoostingClassifier",
            "selector_parameters": model_parameters,
            "candidate_alternatives": "union_of_eight_signal_top1_predictions",
            "quality_floor": quality_floor,
        },
        "folds": fold_reports,
        "aggregates": {
            "queries": len(query_words),
            "word_classes": len(set(query_words)),
            "selector_training_rows": len(features),
            "mean_alternatives_per_query": len(features) / len(query_words),
            "proposal_oracle_top1_accuracy": oracle_accuracy,
            "calibrated_fusion_top1_accuracy": float(
                np.mean(calibrated_fusion.argmax(axis=1) == 0)
            ),
        },
        "metrics": metrics,
        "zero_false_true_pair_recall": zero_false_recall,
        "accepted": accepted,
        "runtime": {"scikit_learn": sklearn_version},
        "individual_examples_exported": False,
        "research_tuning_examples_scored": True,
        "research_reserved_examples_scored": False,
        "official_test_audio_accessed": False,
        "blind_human_audio_accessed": False,
        "effects_executed": 0,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hyper-ctc-cache", type=Path, required=True)
    parser.add_argument("--whisper-cache", type=Path, required=True)
    parser.add_argument("--forced-alignment-cache", type=Path, required=True)
    parser.add_argument("--shortlist-cache", type=Path, required=True)
    parser.add_argument("--silence-prior-cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--silence-prior-weight", type=float, default=0.63)
    parser.add_argument("--calibrated-fusion-weight", type=float, default=0.60)
    parser.add_argument("--fold-seed", type=int, default=12301)
    parser.add_argument("--fold-count", type=int, default=5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = evaluate(
        hyper_ctc_cache_path=args.hyper_ctc_cache,
        whisper_cache_path=args.whisper_cache,
        forced_alignment_cache_path=args.forced_alignment_cache,
        shortlist_cache_path=args.shortlist_cache,
        silence_prior_cache_path=args.silence_prior_cache,
        output_path=args.output,
        silence_prior_weight=args.silence_prior_weight,
        calibrated_fusion_weight=args.calibrated_fusion_weight,
        fold_seed=args.fold_seed,
        fold_count=args.fold_count,
    )
    print(
        json.dumps(
            {
                "accepted": report["accepted"],
                "metrics": report["metrics"],
                "zero_false_true_pair_recall": report[
                    "zero_false_true_pair_recall"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
