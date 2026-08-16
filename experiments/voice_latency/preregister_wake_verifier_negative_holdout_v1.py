"""Freeze the complete two-stage wake candidate before opening FAR holdout."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path


STT_FILES = (
    "encoder.int8.onnx",
    "decoder.int8.onnx",
    "joiner.int8.onnx",
    "tokens.txt",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"json_root_is_not_object:{path}")
    return value


def preregister(
    *,
    candidate_directory: Path,
    negative_corpus_manifest: Path,
    positive_development_report: Path,
    negative_development_report: Path,
    mel_overlap_report: Path,
    stt_directory: Path,
    ffmpeg_path: Path,
    source_root: Path,
    output_path: Path,
) -> dict[str, object]:
    candidate_directory = candidate_directory.resolve(strict=True)
    negative_corpus_manifest = negative_corpus_manifest.resolve(strict=True)
    positive_development_report = positive_development_report.resolve(
        strict=True
    )
    negative_development_report = negative_development_report.resolve(
        strict=True
    )
    mel_overlap_report = mel_overlap_report.resolve(strict=True)
    stt_directory = stt_directory.resolve(strict=True)
    ffmpeg_path = ffmpeg_path.resolve(strict=True)
    source_root = source_root.resolve(strict=True)
    output_path = output_path.resolve()
    if output_path.exists():
        raise FileExistsError(f"wake_preregistration_exists:{output_path}")
    candidate_bundle_path = candidate_directory / "candidate.bundle.v1.json"
    wake_manifest_path = candidate_directory / "baxy-wakeword-v1.json"
    verifier_manifest_path = candidate_directory / "baxy-wake-verifier-v1.json"
    candidate = read_json(candidate_bundle_path)
    wake_manifest = read_json(wake_manifest_path)
    verifier_manifest = read_json(verifier_manifest_path)
    corpus = read_json(negative_corpus_manifest)
    positive_development = read_json(positive_development_report)
    negative_development = read_json(negative_development_report)
    mel_overlap = read_json(mel_overlap_report)
    contract = candidate.get("contract")
    if (
        candidate.get("schema") != "baxy.wake-verifier-candidate-bundle.v1"
        or candidate.get("candidate_frozen") is not False
        or candidate.get("blind_human_partition_accessed") is not False
        or candidate.get("negative_holdout_scored") is not False
        or corpus.get("schema")
        != "baxy.openslr-librispeech-negative-holdout.v1"
        or corpus.get("candidate_scored") is not False
        or wake_manifest.get("calibration") != {"approved": False}
        or verifier_manifest.get("calibration") != {"approved": False}
        or not isinstance(contract, dict)
    ):
        raise ValueError("wake_preregistration_boundary_invalid")
    positive_metrics = positive_development.get("metrics")
    positive_sources = positive_development.get("sources")
    positive_contract = positive_development.get("contract")
    negative_metrics = negative_development.get("metrics")
    negative_runtime = negative_development.get("runtime")
    expected_positive_contract = {
        "first_causal_broad_hit": True,
        "stt_decode_schedule": "single_stream_product_equivalent",
        "stage1_hop_samples": int(contract["hop_samples"]),
        "audio_frame_samples": int(contract["audio_frame_samples"]),
        "pre_roll_seconds": float(contract["pre_roll_seconds"]),
        "pre_roll_samples": int(
            float(contract["pre_roll_seconds"])
            * 16_000
            / int(contract["audio_frame_samples"])
        )
        * int(contract["audio_frame_samples"]),
        "trailing_silence_samples": int(
            0.7 * 16_000 / int(contract["audio_frame_samples"])
        )
        * int(contract["audio_frame_samples"]),
        "verification_samples": int(contract["verification_samples"]),
        "primary_view_start_samples": int(
            contract["primary_view_start_samples"]
        ),
        "activity_lookback_samples": int(
            contract["activity_lookback_samples"]
        ),
        "activity_alignment_samples": int(
            contract["activity_alignment_samples"]
        ),
        "activity_vad_threshold": float(contract["activity_vad_threshold"]),
        "maximum_turn_samples": int(contract["maximum_turn_samples"]),
    }
    if (
        positive_development.get("schema")
        != "baxy.wake-verifier-product-capture-development.v1"
        or not isinstance(positive_metrics, dict)
        or not isinstance(positive_sources, dict)
        or positive_contract != expected_positive_contract
        or positive_metrics.get("gate_passed") is not True
        or positive_metrics.get("positive_accepted")
        != positive_metrics.get("positive_total")
        or positive_metrics.get("hard_negative_false_accepts") != 0
        or positive_development.get("candidate_frozen") is not False
        or positive_development.get("product_operating_point") is not True
        or positive_development.get("blind_human_partition_accessed") is not False
        or positive_development.get("effects_executed") != 0
        or positive_sources.get("stage1_model_sha256")
        != wake_manifest.get("sha256")
        or positive_sources.get("verifier_manifest_sha256")
        != sha256(verifier_manifest_path)
    ):
        raise ValueError("wake_preregistration_positive_development_invalid")
    if (
        negative_development.get("schema")
        != "baxy.wake-verifier-negative-development.v1"
        or not isinstance(negative_metrics, dict)
        or not isinstance(negative_runtime, dict)
        or negative_metrics.get("negative_false_activations") != 0
        or negative_runtime.get("stt_decode_schedule")
        != "single_stream_product_equivalent"
        or negative_runtime.get("strong_stage1_transcript_elision") is not False
        or negative_development.get("development_gate_passed") is not True
        or negative_development.get("candidate_development_use") is not True
        or negative_development.get("candidate_frozen") is not False
        or negative_development.get("product_operating_point") is not False
        or negative_development.get("blind_human_partition_accessed") is not False
        or negative_development.get("effects_executed") != 0
        or negative_development.get("verifier_manifest_sha256")
        != sha256(verifier_manifest_path)
    ):
        raise ValueError("wake_preregistration_negative_development_invalid")
    overlap_assets = mel_overlap.get("assets")
    overlap_contract = mel_overlap.get("contract")
    overlap_equivalence = mel_overlap.get("equivalence")
    if (
        mel_overlap.get("schema") != "baxy.livekit-mel-overlap-models.v1"
        or not isinstance(overlap_assets, dict)
        or not isinstance(overlap_contract, dict)
        or not isinstance(overlap_equivalence, dict)
        or overlap_equivalence.get("bitwise_equal") is not True
        or float(overlap_equivalence.get("maximum_absolute_difference", -1.0))
        != 0.0
        or overlap_contract.get("exact_decisions_remain_owned_by_original_runtime")
        is not True
        or overlap_contract.get("audio_frame_samples")
        != int(contract["audio_frame_samples"])
        or overlap_contract.get("stage1_hop_samples")
        != int(contract["hop_samples"])
        or mel_overlap.get("candidate_frozen") is not False
        or mel_overlap.get("product_runtime_asset") is not False
        or mel_overlap.get("blind_human_partition_accessed") is not False
        or mel_overlap.get("effects_executed") != 0
    ):
        raise ValueError("wake_preregistration_mel_overlap_invalid")
    source_paths = {
        "wakeword_source_sha256": source_root / "src/baxy_mind/wakeword.py",
        "wake_verifier_source_sha256": (
            source_root / "src/baxy_mind/wake_verifier.py"
        ),
        "voice_source_sha256": source_root / "src/baxy_mind/voice.py",
        "scan_script_sha256": (
            source_root
            / "experiments/voice_latency/scan_openslr_librispeech_livekit_development.py"
        ),
        "evaluation_script_sha256": (
            source_root
            / "experiments/voice_latency/evaluate_wake_verifier_negative_holdout_v1.py"
        ),
        "positive_evaluation_script_sha256": (
            source_root
            / "experiments/voice_latency/evaluate_wake_verifier_product_capture_development_v1.py"
        ),
        "mel_overlap_build_script_sha256": (
            source_root
            / "experiments/voice_latency/build_livekit_mel_overlap_models_v1.py"
        ),
        "preregistration_script_sha256": Path(__file__).resolve(),
    }
    for path in source_paths.values():
        path.resolve(strict=True)
    stage1_model = candidate_directory / str(wake_manifest["model"])
    graph = candidate_directory / str(verifier_manifest["graph"])
    graph_data = candidate_directory / str(verifier_manifest["graphData"])
    vocabulary = candidate_directory / str(verifier_manifest["vocabulary"])
    identities = {
        "stage1_model_sha256": sha256(stage1_model),
        "verifier_graph_sha256": sha256(graph),
        "verifier_graph_data_sha256": sha256(graph_data),
        "verifier_vocabulary_sha256": sha256(vocabulary),
    }
    expected = {
        "stage1_model_sha256": wake_manifest["sha256"],
        "verifier_graph_sha256": verifier_manifest["graphSha256"],
        "verifier_graph_data_sha256": verifier_manifest[
            "graphDataSha256"
        ],
        "verifier_vocabulary_sha256": verifier_manifest[
            "vocabularySha256"
        ],
    }
    if identities != expected:
        raise ValueError("wake_preregistration_asset_hash_mismatch")
    mel_overlap_directory = mel_overlap_report.parent
    mel_overlap_raw = mel_overlap_directory / str(overlap_assets["raw"])
    mel_overlap_post = mel_overlap_directory / str(overlap_assets["post"])
    mel_overlap_identities = {
        "mel_overlap_raw_sha256": sha256(mel_overlap_raw),
        "mel_overlap_post_sha256": sha256(mel_overlap_post),
    }
    if mel_overlap_identities != {
        "mel_overlap_raw_sha256": overlap_assets.get("raw_sha256"),
        "mel_overlap_post_sha256": overlap_assets.get("post_sha256"),
    }:
        raise ValueError("wake_preregistration_mel_overlap_hash_mismatch")
    negative_scan_path = Path(
        str(negative_development.get("stage1_scan", ""))
    ).resolve(strict=True)
    negative_scan = read_json(negative_scan_path)
    negative_scan_runtime = negative_scan.get("runtime")
    if (
        negative_development.get("stage1_scan_sha256")
        != sha256(negative_scan_path)
        or negative_scan.get("schema")
        != "baxy.openslr-librispeech-livekit-development-scan.v1"
        or negative_scan.get("candidate_development_use") is not True
        or negative_scan.get("product_runtime_equivalent_schedule") is not True
        or negative_scan.get("model_sha256") != identities["stage1_model_sha256"]
        or negative_scan.get("retention_threshold")
        != float(contract["broad_threshold"])
        or negative_scan.get("proposal_threshold")
        != float(contract["strong_threshold"])
        or negative_scan.get("hop_samples") != int(contract["hop_samples"])
        or negative_scan.get("audio_frame_samples")
        != int(contract["audio_frame_samples"])
        or not isinstance(negative_scan_runtime, dict)
        or negative_scan_runtime.get("mel_overlap_raw_sha256")
        != mel_overlap_identities["mel_overlap_raw_sha256"]
        or negative_scan_runtime.get("mel_overlap_post_sha256")
        != mel_overlap_identities["mel_overlap_post_sha256"]
    ):
        raise ValueError("wake_preregistration_negative_scan_invalid")
    corpus_metrics = corpus.get("metrics")
    if not isinstance(corpus_metrics, dict):
        raise ValueError("wake_preregistration_corpus_metrics_missing")
    exposure_hours = float(corpus_metrics["audio_hours"])
    minimum_exposure = -math.log(0.05) / 0.1
    if exposure_hours < minimum_exposure:
        raise ValueError("wake_preregistration_exposure_insufficient")
    stt_hashes = {name: sha256(stt_directory / name) for name in STT_FILES}
    report: dict[str, object] = {
        "schema": "baxy.wake-verifier-negative-holdout-preregistration.v1",
        "preregistered_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_bundle_sha256": sha256(candidate_bundle_path),
        "wake_manifest_sha256": sha256(wake_manifest_path),
        "verifier_manifest_sha256": sha256(verifier_manifest_path),
        "negative_corpus_manifest_sha256": sha256(
            negative_corpus_manifest
        ),
        "positive_development_report_sha256": sha256(
            positive_development_report
        ),
        "negative_development_report_sha256": sha256(
            negative_development_report
        ),
        "negative_development_scan_sha256": sha256(negative_scan_path),
        "mel_overlap_report_sha256": sha256(mel_overlap_report),
        **identities,
        **mel_overlap_identities,
        **{name: sha256(path) for name, path in source_paths.items()},
        "stt_files_sha256": stt_hashes,
        "ffmpeg_sha256": sha256(ffmpeg_path),
        "broad_threshold": float(contract["broad_threshold"]),
        "strong_threshold": float(contract["strong_threshold"]),
        "stage1_hop_samples": int(contract["hop_samples"]),
        "audio_frame_samples": int(contract["audio_frame_samples"]),
        "stage1_debounce_seconds": float(contract["debounce_seconds"]),
        "stage1_pre_roll_seconds": float(contract["pre_roll_seconds"]),
        "stage1_pre_roll_samples": int(
            float(contract["pre_roll_seconds"])
            * 16_000
            / int(contract["audio_frame_samples"])
        )
        * int(contract["audio_frame_samples"]),
        "trailing_silence_samples": int(
            0.7 * 16_000 / int(contract["audio_frame_samples"])
        )
        * int(contract["audio_frame_samples"]),
        "verification_samples": int(contract["verification_samples"]),
        "primary_view_start_samples": int(
            contract["primary_view_start_samples"]
        ),
        "activity_lookback_samples": int(
            contract["activity_lookback_samples"]
        ),
        "activity_alignment_samples": int(
            contract["activity_alignment_samples"]
        ),
        "activity_vad_threshold": float(contract["activity_vad_threshold"]),
        "maximum_turn_samples": int(contract["maximum_turn_samples"]),
        "decision_margin": float(contract["decision_margin"]),
        "anchor_margin": float(contract["anchor_margin"]),
        "negative_exposure_hours": exposure_hours,
        "gate": {
            "negative_false_activations_eq": 0,
            "far_confidence_gte": 0.95,
            "far_upper_confidence_per_hour_lte": 0.1,
            "minimum_exposure_hours": minimum_exposure,
        },
        "candidate_frozen": True,
        "product_operating_point": True,
        "negative_holdout_scored": False,
        "blind_human_partition_accessed": False,
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
    parser.add_argument("--candidate-directory", type=Path, required=True)
    parser.add_argument("--negative-corpus-manifest", type=Path, required=True)
    parser.add_argument("--positive-development-report", type=Path, required=True)
    parser.add_argument("--negative-development-report", type=Path, required=True)
    parser.add_argument("--mel-overlap-report", type=Path, required=True)
    parser.add_argument("--stt-directory", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = preregister(
        candidate_directory=arguments.candidate_directory,
        negative_corpus_manifest=arguments.negative_corpus_manifest,
        positive_development_report=arguments.positive_development_report,
        negative_development_report=arguments.negative_development_report,
        mel_overlap_report=arguments.mel_overlap_report,
        stt_directory=arguments.stt_directory,
        ffmpeg_path=arguments.ffmpeg,
        source_root=arguments.source_root,
        output_path=arguments.output,
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
