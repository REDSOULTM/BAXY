"""Preregister the one-shot reserved MSWC gate for the calibrated selector."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


QUALITY_FLOOR = {
    "hard_candidate_top1_accuracy_minimum": 0.94,
    "pair_auc_minimum": 0.99,
    "equal_error_rate_maximum": 0.05,
    "zero_false_true_pair_recall_minimum": 0.20,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("mswc_reserved_preregistration_object_invalid")
    return value


def validate_tuning_report(report: dict[str, object]) -> None:
    metrics = report.get("metrics")
    contract = report.get("contract")
    if (
        report.get("schema")
        != "baxy.mswc-spanish-calibrated-selector-tuning.v10"
        or report.get("accepted") is not True
        or report.get("research_reserved_examples_scored") is not False
        or report.get("official_test_audio_accessed") is not False
        or report.get("blind_human_audio_accessed") is not False
        or report.get("effects_executed") != 0
        or not isinstance(metrics, dict)
        or not isinstance(contract, dict)
        or contract.get("quality_floor") != QUALITY_FLOOR
        or float(metrics.get("hard_candidate_top1_accuracy", 0.0))
        < QUALITY_FLOOR["hard_candidate_top1_accuracy_minimum"]
        or float(metrics.get("pair_auc", 0.0))
        < QUALITY_FLOOR["pair_auc_minimum"]
        or float(metrics.get("equal_error_rate", 1.0))
        > QUALITY_FLOOR["equal_error_rate_maximum"]
        or float(report.get("zero_false_true_pair_recall", 0.0))
        < QUALITY_FLOOR["zero_false_true_pair_recall_minimum"]
    ):
        raise ValueError("mswc_reserved_preregistration_tuning_gate_invalid")


def preregister(
    *,
    tuning_report_path: Path,
    hyper_ctc_cache_path: Path,
    whisper_cache_path: Path,
    forced_alignment_cache_path: Path,
    shortlist_cache_path: Path,
    silence_prior_cache_path: Path,
    corpus_manifest_path: Path,
    hyperspotter_checkpoint_path: Path,
    whisper_model_path: Path,
    output_path: Path,
) -> dict[str, object]:
    if output_path.exists():
        raise ValueError("mswc_reserved_preregistration_output_exists")
    paths = [
        tuning_report_path,
        hyper_ctc_cache_path,
        whisper_cache_path,
        forced_alignment_cache_path,
        shortlist_cache_path,
        silence_prior_cache_path,
        corpus_manifest_path,
        hyperspotter_checkpoint_path,
        whisper_model_path,
    ]
    (
        tuning_report_path,
        hyper_ctc_cache_path,
        whisper_cache_path,
        forced_alignment_cache_path,
        shortlist_cache_path,
        silence_prior_cache_path,
        corpus_manifest_path,
        hyperspotter_checkpoint_path,
        whisper_model_path,
    ) = [path.resolve(strict=True) for path in paths]
    output_path = output_path.resolve()
    tuning_report = read_object(tuning_report_path)
    validate_tuning_report(tuning_report)
    sources = tuning_report.get("sources")
    if not isinstance(sources, dict):
        raise ValueError("mswc_reserved_preregistration_sources_invalid")
    expected_cache_hashes = {
        "hyper_ctc_cache_sha256": sha256(hyper_ctc_cache_path),
        "whisper_cache_sha256": sha256(whisper_cache_path),
        "forced_alignment_cache_sha256": sha256(forced_alignment_cache_path),
        "shortlist_cache_sha256": sha256(shortlist_cache_path),
        "silence_prior_cache_sha256": sha256(silence_prior_cache_path),
    }
    if any(sources.get(name) != value for name, value in expected_cache_hashes.items()):
        raise ValueError("mswc_reserved_preregistration_cache_hash_invalid")
    repository_root = Path(__file__).resolve().parents[2]
    code_paths = [
        Path(__file__).resolve(),
        repository_root
        / "experiments/voice_latency/evaluate_mswc_spanish_calibrated_selector_tuning_v10.py",
        repository_root
        / "experiments/voice_latency/evaluate_mswc_spanish_whisper_forced_alignment_tuning_v9.py",
        repository_root
        / "experiments/voice_latency/build_mswc_spanish_forced_alignment_shortlist_v1.py",
        repository_root
        / "experiments/voice_latency/build_mswc_spanish_whisper_silence_prior_v1.py",
    ]
    report: dict[str, object] = {
        "schema": "baxy.mswc-spanish-calibrated-selector-reserved-preregistration.v1",
        "preregistered_at_utc": datetime.now(timezone.utc).isoformat(),
        "decision_locked": True,
        "sources": {
            "tuning_report_sha256": sha256(tuning_report_path),
            **expected_cache_hashes,
            "corpus_manifest_sha256": sha256(corpus_manifest_path),
            "hyperspotter_checkpoint_sha256": sha256(hyperspotter_checkpoint_path),
            "whisper_model_bin_sha256": sha256(whisper_model_path),
            "code_sha256": {
                str(path.relative_to(repository_root)).replace("\\", "/"): sha256(path)
                for path in code_paths
            },
        },
        "locked_protocol": {
            "split_seed": 6501,
            "tuning_word_classes": 400,
            "reserved_word_classes": 200,
            "reserved_query_examples_per_word": 6,
            "reserved_queries": 1200,
            "hard_negative_candidates_per_query": 40,
            "reserved_partition": "complement_of_tuning_words_in_research_v3",
            "hyperspotter_checkpoint": "listwise_train16_best_epoch_6",
            "phoneme_ctc_length_bonus": 0.05,
            "whisper_transcript": {
                "model": "faster_whisper_large_v3",
                "compute_type": "int8_float16",
                "language": "es",
                "beam_size": 1,
            },
            "forced_alignment": {
                "token_prefix": "leading_space",
                "include_eot": False,
                "length_power": 0.0,
                "shortlist_depth_per_signal": 3,
                "candidate_batch_size": 13,
            },
            "silence_prior": {"num_frames": 100, "weight": 0.63},
            "calibrated_fusion_weight": 0.60,
            "selector": {
                "type": "HistGradientBoostingClassifier",
                "training_population": "all_400_tuning_word_classes",
                "random_state": 13301,
                "learning_rate": 0.08,
                "max_iter": 220,
                "max_leaf_nodes": 7,
                "min_samples_leaf": 5,
                "l2_regularization": 2.0,
                "class_weight": "balanced",
                "candidate_alternatives": "union_of_eight_signal_top1_predictions",
            },
            "decision_scores": "calibrated_fusion_with_minimal_selector_top1_override",
            "quality_floor": QUALITY_FLOOR,
            "acceptance": "all_four_quality_floor_conditions_must_pass",
            "single_reserved_pass": True,
            "no_retuning_after_reserved": True,
            "individual_examples_exported": False,
        },
        "tuning_evidence": {
            "hard_candidate_top1_accuracy": tuning_report["metrics"][
                "hard_candidate_top1_accuracy"
            ],
            "pair_auc": tuning_report["metrics"]["pair_auc"],
            "equal_error_rate": tuning_report["metrics"]["equal_error_rate"],
            "zero_false_true_pair_recall": tuning_report[
                "zero_false_true_pair_recall"
            ],
        },
        "reserved_audio_accessed_before_preregistration": False,
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
    parser.add_argument("--tuning-report", type=Path, required=True)
    parser.add_argument("--hyper-ctc-cache", type=Path, required=True)
    parser.add_argument("--whisper-cache", type=Path, required=True)
    parser.add_argument("--forced-alignment-cache", type=Path, required=True)
    parser.add_argument("--shortlist-cache", type=Path, required=True)
    parser.add_argument("--silence-prior-cache", type=Path, required=True)
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--hyperspotter-checkpoint", type=Path, required=True)
    parser.add_argument("--whisper-model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = preregister(
        tuning_report_path=args.tuning_report,
        hyper_ctc_cache_path=args.hyper_ctc_cache,
        whisper_cache_path=args.whisper_cache,
        forced_alignment_cache_path=args.forced_alignment_cache,
        shortlist_cache_path=args.shortlist_cache,
        silence_prior_cache_path=args.silence_prior_cache,
        corpus_manifest_path=args.corpus_manifest,
        hyperspotter_checkpoint_path=args.hyperspotter_checkpoint,
        whisper_model_path=args.whisper_model,
        output_path=args.output,
    )
    print(
        json.dumps(
            {
                "decision_locked": report["decision_locked"],
                "reserved_audio_accessed_before_preregistration": report[
                    "reserved_audio_accessed_before_preregistration"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
