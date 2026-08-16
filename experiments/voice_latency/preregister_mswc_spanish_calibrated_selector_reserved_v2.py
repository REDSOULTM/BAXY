"""Seal code, assets, outputs, and thresholds before reserved MSWC access."""

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
CODE_FILES = [
    "experiments/voice_latency/evaluate_mswc_hyperspotter_ctc_fusion_tuning_v5.py",
    "experiments/voice_latency/evaluate_mswc_spanish_faster_whisper_tuning_v8.py",
    "experiments/voice_latency/evaluate_mswc_spanish_whisper_forced_alignment_tuning_v9.py",
    "experiments/voice_latency/build_mswc_spanish_forced_alignment_shortlist_v1.py",
    "experiments/voice_latency/build_mswc_spanish_whisper_silence_prior_v1.py",
    "experiments/voice_latency/evaluate_mswc_spanish_calibrated_selector_tuning_v10.py",
    "experiments/voice_latency/evaluate_mswc_spanish_calibrated_selector_reserved_v11.py",
    "experiments/voice_latency/preregister_mswc_spanish_calibrated_selector_reserved_v2.py",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("mswc_reserved_preregistration_v2_object_invalid")
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
        or contract.get("silence_prior_weight") != 0.63
        or contract.get("calibrated_fusion_weight") != 0.60
        or float(metrics.get("hard_candidate_top1_accuracy", 0.0))
        < QUALITY_FLOOR["hard_candidate_top1_accuracy_minimum"]
        or float(metrics.get("pair_auc", 0.0))
        < QUALITY_FLOOR["pair_auc_minimum"]
        or float(metrics.get("equal_error_rate", 1.0))
        > QUALITY_FLOOR["equal_error_rate_maximum"]
        or float(report.get("zero_false_true_pair_recall", 0.0))
        < QUALITY_FLOOR["zero_false_true_pair_recall_minimum"]
    ):
        raise ValueError("mswc_reserved_preregistration_v2_tuning_gate_invalid")


def preregister(
    *,
    tuning_report_path: Path,
    tuning_hyper_ctc_cache_path: Path,
    tuning_whisper_cache_path: Path,
    tuning_forced_alignment_cache_path: Path,
    tuning_shortlist_cache_path: Path,
    tuning_silence_prior_cache_path: Path,
    corpus_manifest_path: Path,
    hyperspotter_feature_manifest_path: Path,
    ctc_feature_manifest_path: Path,
    initial_checkpoint_path: Path,
    adapted_checkpoint_path: Path,
    ctc_tokenizer_vocabulary_path: Path,
    whisper_model_path: Path,
    reserved_hyper_ctc_cache_path: Path,
    reserved_whisper_cache_path: Path,
    reserved_forced_alignment_cache_path: Path,
    reserved_shortlist_cache_path: Path,
    reserved_silence_prior_cache_path: Path,
    reserved_gate_output_path: Path,
    output_path: Path,
) -> dict[str, object]:
    if output_path.exists():
        raise ValueError("mswc_reserved_preregistration_v2_output_exists")
    tuning_paths = {
        "tuning_report": tuning_report_path,
        "tuning_hyper_ctc_cache": tuning_hyper_ctc_cache_path,
        "tuning_whisper_cache": tuning_whisper_cache_path,
        "tuning_forced_alignment_cache": tuning_forced_alignment_cache_path,
        "tuning_shortlist_cache": tuning_shortlist_cache_path,
        "tuning_silence_prior_cache": tuning_silence_prior_cache_path,
    }
    asset_paths = {
        "corpus_manifest": corpus_manifest_path,
        "hyperspotter_feature_manifest": hyperspotter_feature_manifest_path,
        "ctc_feature_manifest": ctc_feature_manifest_path,
        "initial_hyperspotter_checkpoint": initial_checkpoint_path,
        "adapted_hyperspotter_checkpoint": adapted_checkpoint_path,
        "ctc_tokenizer_vocabulary": ctc_tokenizer_vocabulary_path,
        "whisper_model_bin": whisper_model_path,
    }
    tuning_paths = {
        name: path.resolve(strict=True) for name, path in tuning_paths.items()
    }
    asset_paths = {
        name: path.resolve(strict=True) for name, path in asset_paths.items()
    }
    reserved_paths = {
        "reserved_hyper_ctc_cache": reserved_hyper_ctc_cache_path.resolve(),
        "reserved_whisper_cache": reserved_whisper_cache_path.resolve(),
        "reserved_forced_alignment_cache": reserved_forced_alignment_cache_path.resolve(),
        "reserved_shortlist_cache": reserved_shortlist_cache_path.resolve(),
        "reserved_silence_prior_cache": reserved_silence_prior_cache_path.resolve(),
        "reserved_gate_output": reserved_gate_output_path.resolve(),
    }
    if any(path.exists() for path in reserved_paths.values()):
        raise ValueError("mswc_reserved_preregistration_v2_reserved_output_exists")
    tuning_report = read_object(tuning_paths["tuning_report"])
    validate_tuning_report(tuning_report)
    sources = tuning_report.get("sources")
    if not isinstance(sources, dict):
        raise ValueError("mswc_reserved_preregistration_v2_sources_invalid")
    expected_tuning_hashes = {
        f"{name}_sha256": sha256(path) for name, path in tuning_paths.items()
    }
    tuning_source_names = {
        "tuning_hyper_ctc_cache": "hyper_ctc_cache_sha256",
        "tuning_whisper_cache": "whisper_cache_sha256",
        "tuning_forced_alignment_cache": "forced_alignment_cache_sha256",
        "tuning_shortlist_cache": "shortlist_cache_sha256",
        "tuning_silence_prior_cache": "silence_prior_cache_sha256",
    }
    if any(
        sources.get(source_name)
        != expected_tuning_hashes[f"{path_name}_sha256"]
        for path_name, source_name in tuning_source_names.items()
    ):
        raise ValueError("mswc_reserved_preregistration_v2_cache_hash_invalid")
    repository_root = Path(__file__).resolve().parents[2]
    code_paths = {
        relative: (repository_root / relative).resolve(strict=True)
        for relative in CODE_FILES
    }
    report: dict[str, object] = {
        "schema": "baxy.mswc-spanish-calibrated-selector-reserved-preregistration.v2",
        "preregistered_at_utc": datetime.now(timezone.utc).isoformat(),
        "decision_locked": True,
        "sources": {
            **expected_tuning_hashes,
            **{
                f"{name}_sha256": sha256(path)
                for name, path in asset_paths.items()
            },
            "code_sha256": {
                relative: sha256(path) for relative, path in code_paths.items()
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
            "feature_cache_policy": "cache_only_without_label_metrics",
            "hyperspotter_checkpoint": "listwise_train16_best_epoch_6",
            "phoneme_ctc_length_bonus": 0.05,
            "whisper_transcript": {
                "model": "faster_whisper_large_v3",
                "compute_type": "int8_float16",
                "language": "es",
                "beam_size": 1,
                "inference_layout": "fixed_slot_batched",
                "inference_batch_size": 8,
                "slot_seconds": 2.0,
            },
            "forced_alignment": {
                "token_prefix": "leading_space",
                "include_eot": False,
                "length_power": 0.0,
                "shortlist_depth_per_signal": 3,
                "audio_batch_size": 2,
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
            "reserved_artifacts": {
                name: str(path) for name, path in reserved_paths.items()
            },
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
    output_path = output_path.resolve()
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
    parser.add_argument("--tuning-hyper-ctc-cache", type=Path, required=True)
    parser.add_argument("--tuning-whisper-cache", type=Path, required=True)
    parser.add_argument("--tuning-forced-alignment-cache", type=Path, required=True)
    parser.add_argument("--tuning-shortlist-cache", type=Path, required=True)
    parser.add_argument("--tuning-silence-prior-cache", type=Path, required=True)
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--hyperspotter-feature-manifest", type=Path, required=True)
    parser.add_argument("--ctc-feature-manifest", type=Path, required=True)
    parser.add_argument("--initial-checkpoint", type=Path, required=True)
    parser.add_argument("--adapted-checkpoint", type=Path, required=True)
    parser.add_argument("--ctc-tokenizer-vocabulary", type=Path, required=True)
    parser.add_argument("--whisper-model", type=Path, required=True)
    parser.add_argument("--reserved-hyper-ctc-cache", type=Path, required=True)
    parser.add_argument("--reserved-whisper-cache", type=Path, required=True)
    parser.add_argument("--reserved-forced-alignment-cache", type=Path, required=True)
    parser.add_argument("--reserved-shortlist-cache", type=Path, required=True)
    parser.add_argument("--reserved-silence-prior-cache", type=Path, required=True)
    parser.add_argument("--reserved-gate-output", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = preregister(
        tuning_report_path=args.tuning_report,
        tuning_hyper_ctc_cache_path=args.tuning_hyper_ctc_cache,
        tuning_whisper_cache_path=args.tuning_whisper_cache,
        tuning_forced_alignment_cache_path=args.tuning_forced_alignment_cache,
        tuning_shortlist_cache_path=args.tuning_shortlist_cache,
        tuning_silence_prior_cache_path=args.tuning_silence_prior_cache,
        corpus_manifest_path=args.corpus_manifest,
        hyperspotter_feature_manifest_path=args.hyperspotter_feature_manifest,
        ctc_feature_manifest_path=args.ctc_feature_manifest,
        initial_checkpoint_path=args.initial_checkpoint,
        adapted_checkpoint_path=args.adapted_checkpoint,
        ctc_tokenizer_vocabulary_path=args.ctc_tokenizer_vocabulary,
        whisper_model_path=args.whisper_model,
        reserved_hyper_ctc_cache_path=args.reserved_hyper_ctc_cache,
        reserved_whisper_cache_path=args.reserved_whisper_cache,
        reserved_forced_alignment_cache_path=args.reserved_forced_alignment_cache,
        reserved_shortlist_cache_path=args.reserved_shortlist_cache,
        reserved_silence_prior_cache_path=args.reserved_silence_prior_cache,
        reserved_gate_output_path=args.reserved_gate_output,
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
