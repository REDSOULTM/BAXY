"""Run the preregistered one-shot reserved gate for the calibrated selector."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np


QUALITY_FLOOR = {
    "hard_candidate_top1_accuracy_minimum": 0.94,
    "pair_auc_minimum": 0.99,
    "equal_error_rate_maximum": 0.05,
    "zero_false_true_pair_recall_minimum": 0.20,
}
MODEL_PARAMETERS = {
    "learning_rate": 0.08,
    "max_iter": 220,
    "max_leaf_nodes": 7,
    "min_samples_leaf": 5,
    "l2_regularization": 2.0,
    "class_weight": "balanced",
}
MODEL_RANDOM_STATE = 13301
SILENCE_PRIOR_WEIGHT = 0.63
CALIBRATED_FUSION_WEIGHT = 0.60
REQUIRED_CODE_FILES = {
    "experiments/voice_latency/evaluate_mswc_hyperspotter_ctc_fusion_tuning_v5.py",
    "experiments/voice_latency/evaluate_mswc_spanish_faster_whisper_tuning_v8.py",
    "experiments/voice_latency/evaluate_mswc_spanish_whisper_forced_alignment_tuning_v9.py",
    "experiments/voice_latency/build_mswc_spanish_forced_alignment_shortlist_v1.py",
    "experiments/voice_latency/build_mswc_spanish_whisper_silence_prior_v1.py",
    "experiments/voice_latency/evaluate_mswc_spanish_calibrated_selector_tuning_v10.py",
    "experiments/voice_latency/evaluate_mswc_spanish_calibrated_selector_reserved_v11.py",
    "experiments/voice_latency/preregister_mswc_spanish_calibrated_selector_reserved_v2.py",
}


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"mswc_reserved_selector_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_TUNING = load_component(
    "evaluate_mswc_spanish_calibrated_selector_tuning_v10.py",
    "_baxy_mswc_calibrated_selector_tuning_v10_for_reserved",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("mswc_reserved_selector_object_invalid")
    return value


def load_signal_bundle(
    *,
    hyper_ctc_cache_path: Path,
    whisper_cache_path: Path,
    forced_alignment_cache_path: Path,
    shortlist_cache_path: Path,
    silence_prior_cache_path: Path,
) -> dict[str, np.ndarray]:
    with np.load(hyper_ctc_cache_path, allow_pickle=False) as cache:
        if cache["schema"].tolist() != [
            "baxy.mswc-hyperspotter-ctc-score-cache.v1"
        ]:
            raise ValueError("mswc_reserved_selector_hyper_schema_invalid")
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
            raise ValueError("mswc_reserved_selector_whisper_schema_invalid")
        if (
            not np.array_equal(query_hashes, cache["query_audio_sha256"])
            or not np.array_equal(query_words, cache["query_words"])
            or not np.array_equal(candidate_words, cache["candidate_words"])
        ):
            raise ValueError("mswc_reserved_selector_whisper_alignment_invalid")
        whisper_whole = cache["whole_transcript_edit"].astype(np.float64)
        whisper_token = cache["whole_or_token_edit"].astype(np.float64)
        exact_candidate_match = cache["exact_candidate_match"].astype(np.float64)
    with np.load(forced_alignment_cache_path, allow_pickle=False) as cache:
        if cache["schema"].tolist() != [
            "baxy.mswc-whisper-forced-alignment-score-cache.v1"
        ]:
            raise ValueError("mswc_reserved_selector_forced_schema_invalid")
        if (
            not np.array_equal(query_hashes, cache["query_audio_sha256"])
            or not np.array_equal(query_words, cache["query_words"])
            or not np.array_equal(candidate_words, cache["candidate_words"])
        ):
            raise ValueError("mswc_reserved_selector_forced_alignment_invalid")
        forced_scores = cache["scores_length_power_0_0"].astype(np.float64)
    with np.load(shortlist_cache_path, allow_pickle=False) as cache:
        if cache["schema"].tolist() != [
            "baxy.mswc-forced-alignment-shortlist.v1"
        ]:
            raise ValueError("mswc_reserved_selector_shortlist_schema_invalid")
        if (
            not np.array_equal(query_hashes, cache["query_audio_sha256"])
            or not np.array_equal(query_words, cache["query_words"])
            or not np.array_equal(candidate_words, cache["candidate_words"])
        ):
            raise ValueError("mswc_reserved_selector_shortlist_alignment_invalid")
        candidate_mask = cache["candidate_mask"].astype(bool)
        shortlist_hyper_hash = cache["hyper_ctc_cache_sha256"].astype(str)
        shortlist_whisper_hash = cache["whisper_cache_sha256"].astype(str)
    with np.load(silence_prior_cache_path, allow_pickle=False) as cache:
        if cache["schema"].tolist() != ["baxy.mswc-whisper-silence-prior.v1"]:
            raise ValueError("mswc_reserved_selector_prior_schema_invalid")
        if not np.array_equal(class_names, cache["class_names"]):
            raise ValueError("mswc_reserved_selector_prior_alignment_invalid")
        silence_prior = cache["log_probability_sum"].astype(np.float64)
    shapes = {
        hyper_scores.shape,
        ctc_scores.shape,
        whisper_whole.shape,
        whisper_token.shape,
        exact_candidate_match.shape,
        forced_scores.shape,
        candidate_mask.shape,
        candidate_indexes.shape,
        candidate_words.shape,
    }
    if (
        len(shapes) != 1
        or hyper_scores.ndim != 2
        or hyper_scores.shape[1] != 41
        or not candidate_mask.any(axis=1).all()
        or not np.array_equal(candidate_words[:, 0], query_words)
        or shortlist_hyper_hash.tolist() != [sha256(hyper_ctc_cache_path)]
        or shortlist_whisper_hash.tolist() != [sha256(whisper_cache_path)]
    ):
        raise ValueError("mswc_reserved_selector_bundle_invalid")
    return {
        "hyper_scores": hyper_scores,
        "ctc_scores": ctc_scores,
        "candidate_indexes": candidate_indexes,
        "class_names": class_names,
        "candidate_words": candidate_words,
        "query_hashes": query_hashes,
        "query_words": query_words,
        "whisper_whole": whisper_whole,
        "whisper_token": whisper_token,
        "exact_candidate_match": exact_candidate_match,
        "forced_scores": forced_scores,
        "candidate_mask": candidate_mask,
        "silence_prior": silence_prior,
    }


def build_selector_dataset(bundle: dict[str, np.ndarray]) -> dict[str, object]:
    hyper_scores = bundle["hyper_scores"]
    ctc_scores = bundle["ctc_scores"]
    whisper_whole = bundle["whisper_whole"]
    whisper_token = bundle["whisper_token"]
    forced_scores = bundle["forced_scores"]
    candidate_mask = bundle["candidate_mask"].astype(bool)
    candidate_indexes = bundle["candidate_indexes"].astype(np.int64)
    candidate_words = bundle["candidate_words"].astype(str)
    exact_candidate_match = bundle["exact_candidate_match"]
    silence_prior = bundle["silence_prior"]
    prior_matrix = silence_prior[candidate_indexes]
    calibrated_forced = forced_scores.copy()
    calibrated_forced[candidate_mask] = (
        forced_scores[candidate_mask]
        - SILENCE_PRIOR_WEIGHT * prior_matrix[candidate_mask]
    )
    baseline = 0.3 * _TUNING._FUSION.global_standardize(
        hyper_scores
    ) + 0.7 * _TUNING._FUSION.global_standardize(ctc_scores)
    calibrated_z = _TUNING.prepare_signal(
        calibrated_forced, selected_mask=candidate_mask
    )[0]
    calibrated_fusion = (
        (1.0 - CALIBRATED_FUSION_WEIGHT)
        * _TUNING._FUSION.global_standardize(baseline)
        + CALIBRATED_FUSION_WEIGHT * calibrated_z
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
    prepared = [_TUNING.prepare_signal(value) for value in signals[:4]]
    prepared.extend(
        [
            _TUNING.prepare_signal(forced_scores, selected_mask=candidate_mask),
            _TUNING.prepare_signal(calibrated_forced, selected_mask=candidate_mask),
            _TUNING.prepare_signal(baseline),
            _TUNING.prepare_signal(calibrated_fusion),
        ]
    )
    feature_rows: list[list[float]] = []
    labels: list[int] = []
    query_ids: list[int] = []
    candidate_ids: list[int] = []
    for query in range(len(bundle["query_words"])):
        alternatives = sorted({int(np.argmax(signal[query])) for signal in signals})
        top_count = sum(item[3][query] for item in prepared)
        query_context = [
            float(value)
            for item in prepared
            for value in (item[4][query], item[5][query])
        ]
        for candidate in alternatives:
            features = [
                float(value)
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
                    float(top_count[candidate]),
                    float(candidate_mask[query, candidate]),
                    float(exact_candidate_match[query, candidate]),
                    float(silence_prior[candidate_indexes[query, candidate]]) / 30.0,
                    len(candidate_words[query, candidate]) / 16.0,
                ]
            )
            feature_rows.append(features)
            labels.append(int(candidate == 0))
            query_ids.append(query)
            candidate_ids.append(candidate)
    return {
        "features": np.asarray(feature_rows, dtype=np.float64),
        "labels": np.asarray(labels, dtype=np.uint8),
        "query_ids": np.asarray(query_ids, dtype=np.int32),
        "candidate_ids": np.asarray(candidate_ids, dtype=np.int32),
        "calibrated_fusion": calibrated_fusion,
        "proposal_oracle_top1_accuracy": float(
            np.logical_or.reduce(
                [signal.argmax(axis=1) == 0 for signal in signals]
            ).mean()
        ),
    }


def select_candidates(
    *, probabilities: np.ndarray, query_ids: np.ndarray, candidate_ids: np.ndarray
) -> np.ndarray:
    query_count = int(query_ids.max()) + 1
    selected = np.empty(query_count, dtype=np.int32)
    for query in range(query_count):
        rows = np.flatnonzero(query_ids == query)
        if len(rows) == 0:
            raise ValueError("mswc_reserved_selector_query_missing")
        selected_row = int(rows[np.argmax(probabilities[rows])])
        selected[query] = candidate_ids[selected_row]
    return selected


def validate_preregistration(
    *,
    report: dict[str, object],
    repository_root: Path,
    tuning_paths: dict[str, Path],
    reserved_paths: dict[str, Path],
) -> None:
    sources = report.get("sources")
    locked = report.get("locked_protocol")
    if (
        report.get("schema")
        != "baxy.mswc-spanish-calibrated-selector-reserved-preregistration.v2"
        or report.get("decision_locked") is not True
        or report.get("reserved_audio_accessed_before_preregistration") is not False
        or report.get("effects_executed") != 0
        or not isinstance(sources, dict)
        or not isinstance(locked, dict)
        or locked.get("quality_floor") != QUALITY_FLOOR
        or locked.get("silence_prior")
        != {"num_frames": 100, "weight": SILENCE_PRIOR_WEIGHT}
        or locked.get("calibrated_fusion_weight") != CALIBRATED_FUSION_WEIGHT
    ):
        raise ValueError("mswc_reserved_selector_preregistration_invalid")
    selector = locked.get("selector")
    if (
        not isinstance(selector, dict)
        or selector.get("random_state") != MODEL_RANDOM_STATE
        or any(selector.get(key) != value for key, value in MODEL_PARAMETERS.items())
    ):
        raise ValueError("mswc_reserved_selector_preregistered_model_invalid")
    expected_tuning = {
        f"{name}_sha256": sha256(path) for name, path in tuning_paths.items()
    }
    if any(sources.get(name) != value for name, value in expected_tuning.items()):
        raise ValueError("mswc_reserved_selector_tuning_hash_invalid")
    locked_paths = locked.get("reserved_artifacts")
    expected_paths = {name: str(path.resolve()) for name, path in reserved_paths.items()}
    if locked_paths != expected_paths:
        raise ValueError("mswc_reserved_selector_reserved_paths_invalid")
    code_hashes = sources.get("code_sha256")
    if not isinstance(code_hashes, dict) or not REQUIRED_CODE_FILES.issubset(
        code_hashes
    ):
        raise ValueError("mswc_reserved_selector_code_contract_invalid")
    for relative_path, expected_hash in code_hashes.items():
        if (
            not isinstance(relative_path, str)
            or not isinstance(expected_hash, str)
            or sha256((repository_root / relative_path).resolve(strict=True))
            != expected_hash
        ):
            raise ValueError("mswc_reserved_selector_code_hash_invalid")


def evaluate(
    *,
    preregistration_path: Path,
    tuning_hyper_ctc_cache_path: Path,
    tuning_whisper_cache_path: Path,
    tuning_forced_alignment_cache_path: Path,
    tuning_shortlist_cache_path: Path,
    tuning_silence_prior_cache_path: Path,
    tuning_report_path: Path,
    reserved_hyper_ctc_cache_path: Path,
    reserved_whisper_cache_path: Path,
    reserved_forced_alignment_cache_path: Path,
    reserved_shortlist_cache_path: Path,
    reserved_silence_prior_cache_path: Path,
    output_path: Path,
) -> dict[str, object]:
    if output_path.exists():
        raise ValueError("mswc_reserved_selector_output_exists")
    repository_root = Path(__file__).resolve().parents[2]
    preregistration_path = preregistration_path.resolve(strict=True)
    tuning_paths = {
        "tuning_hyper_ctc_cache": tuning_hyper_ctc_cache_path.resolve(strict=True),
        "tuning_whisper_cache": tuning_whisper_cache_path.resolve(strict=True),
        "tuning_forced_alignment_cache": tuning_forced_alignment_cache_path.resolve(
            strict=True
        ),
        "tuning_shortlist_cache": tuning_shortlist_cache_path.resolve(strict=True),
        "tuning_silence_prior_cache": tuning_silence_prior_cache_path.resolve(
            strict=True
        ),
        "tuning_report": tuning_report_path.resolve(strict=True),
    }
    reserved_paths = {
        "reserved_hyper_ctc_cache": reserved_hyper_ctc_cache_path.resolve(
            strict=True
        ),
        "reserved_whisper_cache": reserved_whisper_cache_path.resolve(strict=True),
        "reserved_forced_alignment_cache": reserved_forced_alignment_cache_path.resolve(
            strict=True
        ),
        "reserved_shortlist_cache": reserved_shortlist_cache_path.resolve(strict=True),
        "reserved_silence_prior_cache": reserved_silence_prior_cache_path.resolve(
            strict=True
        ),
        "reserved_gate_output": output_path.resolve(),
    }
    preregistration = read_object(preregistration_path)
    validate_preregistration(
        report=preregistration,
        repository_root=repository_root,
        tuning_paths=tuning_paths,
        reserved_paths=reserved_paths,
    )
    tuning_bundle = load_signal_bundle(
        hyper_ctc_cache_path=tuning_paths["tuning_hyper_ctc_cache"],
        whisper_cache_path=tuning_paths["tuning_whisper_cache"],
        forced_alignment_cache_path=tuning_paths[
            "tuning_forced_alignment_cache"
        ],
        shortlist_cache_path=tuning_paths["tuning_shortlist_cache"],
        silence_prior_cache_path=tuning_paths["tuning_silence_prior_cache"],
    )
    reserved_bundle = load_signal_bundle(
        hyper_ctc_cache_path=reserved_paths["reserved_hyper_ctc_cache"],
        whisper_cache_path=reserved_paths["reserved_whisper_cache"],
        forced_alignment_cache_path=reserved_paths[
            "reserved_forced_alignment_cache"
        ],
        shortlist_cache_path=reserved_paths["reserved_shortlist_cache"],
        silence_prior_cache_path=reserved_paths["reserved_silence_prior_cache"],
    )
    tuning_words = tuning_bundle["query_words"].astype(str)
    reserved_words = reserved_bundle["query_words"].astype(str)
    if (
        len(tuning_words) != 2400
        or len(set(tuning_words)) != 400
        or len(reserved_words) != 1200
        or len(set(reserved_words)) != 200
        or set(tuning_words) & set(reserved_words)
    ):
        raise ValueError("mswc_reserved_selector_partition_invalid")
    tuning_dataset = build_selector_dataset(tuning_bundle)
    reserved_dataset = build_selector_dataset(reserved_bundle)
    tuning_features = tuning_dataset["features"]
    reserved_features = reserved_dataset["features"]
    if (
        not isinstance(tuning_features, np.ndarray)
        or not isinstance(reserved_features, np.ndarray)
        or tuning_features.shape[1] != reserved_features.shape[1]
    ):
        raise ValueError("mswc_reserved_selector_feature_contract_invalid")
    from sklearn import __version__ as sklearn_version
    from sklearn.ensemble import HistGradientBoostingClassifier

    model = HistGradientBoostingClassifier(
        **MODEL_PARAMETERS, random_state=MODEL_RANDOM_STATE
    )
    model.fit(tuning_features, tuning_dataset["labels"])
    reserved_probabilities = model.predict_proba(reserved_features)[:, 1]
    selected_candidates = select_candidates(
        probabilities=reserved_probabilities,
        query_ids=reserved_dataset["query_ids"],
        candidate_ids=reserved_dataset["candidate_ids"],
    )
    decision_scores = _TUNING.apply_selector_choices(
        base_scores=reserved_dataset["calibrated_fusion"],
        selected_candidates=selected_candidates,
    )
    metrics = _TUNING._FUSION._HYPER.hard_pair_metrics(
        scores=decision_scores, query_words=reserved_words.tolist()
    )
    zero_false_recall = (
        float(metrics["true_pairs_accepted_at_zero_false_pairs"])
        / float(metrics["true_pairs"])
    )
    accepted = (
        float(metrics["hard_candidate_top1_accuracy"])
        >= QUALITY_FLOOR["hard_candidate_top1_accuracy_minimum"]
        and float(metrics["pair_auc"]) >= QUALITY_FLOOR["pair_auc_minimum"]
        and float(metrics["equal_error_rate"])
        <= QUALITY_FLOOR["equal_error_rate_maximum"]
        and zero_false_recall
        >= QUALITY_FLOOR["zero_false_true_pair_recall_minimum"]
    )
    report: dict[str, object] = {
        "schema": "baxy.mswc-spanish-calibrated-selector-reserved.v11",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "preregistered_one_shot_reserved_word_class_gate",
        "sources": {
            "preregistration_sha256": sha256(preregistration_path),
            **{f"{name}_sha256": sha256(path) for name, path in tuning_paths.items()},
            **{
                f"{name}_sha256": sha256(path)
                for name, path in reserved_paths.items()
                if path.exists() and name != "reserved_gate_output"
            },
        },
        "contract": {
            "training_population": "all_400_tuning_word_classes",
            "evaluation_population": "200_disjoint_reserved_word_classes",
            "selector": "HistGradientBoostingClassifier",
            "selector_parameters": MODEL_PARAMETERS,
            "selector_random_state": MODEL_RANDOM_STATE,
            "silence_prior_weight": SILENCE_PRIOR_WEIGHT,
            "calibrated_fusion_weight": CALIBRATED_FUSION_WEIGHT,
            "candidate_alternatives": "union_of_eight_signal_top1_predictions",
            "quality_floor": QUALITY_FLOOR,
            "single_reserved_pass": True,
            "no_retuning_after_reserved": True,
        },
        "aggregates": {
            "training_queries": len(tuning_words),
            "training_word_classes": len(set(tuning_words)),
            "training_rows": len(tuning_features),
            "reserved_queries": len(reserved_words),
            "reserved_word_classes": len(set(reserved_words)),
            "reserved_selector_rows": len(reserved_features),
            "reserved_mean_alternatives_per_query": len(reserved_features)
            / len(reserved_words),
            "reserved_proposal_oracle_top1_accuracy": reserved_dataset[
                "proposal_oracle_top1_accuracy"
            ],
            "reserved_calibrated_fusion_top1_accuracy": float(
                np.mean(reserved_dataset["calibrated_fusion"].argmax(axis=1) == 0)
            ),
        },
        "metrics": metrics,
        "zero_false_true_pair_recall": zero_false_recall,
        "accepted": accepted,
        "runtime": {"scikit_learn": sklearn_version},
        "reserved_pass_number": 1,
        "individual_examples_exported": False,
        "research_tuning_examples_scored": True,
        "research_reserved_examples_scored": True,
        "official_test_audio_accessed": False,
        "blind_human_audio_accessed": False,
        "effects_executed": 0,
    }
    output_path = reserved_paths["reserved_gate_output"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--tuning-hyper-ctc-cache", type=Path, required=True)
    parser.add_argument("--tuning-whisper-cache", type=Path, required=True)
    parser.add_argument("--tuning-forced-alignment-cache", type=Path, required=True)
    parser.add_argument("--tuning-shortlist-cache", type=Path, required=True)
    parser.add_argument("--tuning-silence-prior-cache", type=Path, required=True)
    parser.add_argument("--tuning-report", type=Path, required=True)
    parser.add_argument("--reserved-hyper-ctc-cache", type=Path, required=True)
    parser.add_argument("--reserved-whisper-cache", type=Path, required=True)
    parser.add_argument("--reserved-forced-alignment-cache", type=Path, required=True)
    parser.add_argument("--reserved-shortlist-cache", type=Path, required=True)
    parser.add_argument("--reserved-silence-prior-cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = evaluate(
        preregistration_path=args.preregistration,
        tuning_hyper_ctc_cache_path=args.tuning_hyper_ctc_cache,
        tuning_whisper_cache_path=args.tuning_whisper_cache,
        tuning_forced_alignment_cache_path=args.tuning_forced_alignment_cache,
        tuning_shortlist_cache_path=args.tuning_shortlist_cache,
        tuning_silence_prior_cache_path=args.tuning_silence_prior_cache,
        tuning_report_path=args.tuning_report,
        reserved_hyper_ctc_cache_path=args.reserved_hyper_ctc_cache,
        reserved_whisper_cache_path=args.reserved_whisper_cache,
        reserved_forced_alignment_cache_path=args.reserved_forced_alignment_cache,
        reserved_shortlist_cache_path=args.reserved_shortlist_cache,
        reserved_silence_prior_cache_path=args.reserved_silence_prior_cache,
        output_path=args.output,
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
