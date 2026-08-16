"""Score the frozen wake candidate once on the human blind partition.

This runner uses the same causal capture, single-stream STT schedule, VAD
alignment, and two-stage verifier as the product-capture development gate.  It
fails closed unless the preregistered positive development evidence and the
100-hour negative holdout gate are both intact.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE))
from baxy_mind.voice import SileroVad  # noqa: E402
from baxy_mind.wake_verifier import (  # noqa: E402
    OnnxWakeVerifier,
    load_wake_verifier_candidate_config,
)
from evaluate_wake_verifier_negative_holdout_v1 import (  # noqa: E402
    SAMPLE_RATE,
    STT_FILES,
    activity_verification_start,
    capture_audio,
    decode_flac,
    sha256,
)
from scan_openslr_librispeech_livekit_development import (  # noqa: E402
    BatchedLiveKitPredictor,
    streaming_scores,
)


EXPECTED_POSITIVE_COUNT = 4
EXPECTED_HARD_NEGATIVE_COUNT = 1


def read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"wake_blind_json_root_invalid:{path}")
    return value


def _hash_equals(actual: str, expected: object) -> bool:
    return actual.casefold() == str(expected or "").casefold()


def validate_release_evidence(
    *,
    preregistration: dict[str, object],
    preregistration_sha256: str,
    positive_development: dict[str, object],
    positive_development_sha256: str,
    negative_holdout: dict[str, object],
    negative_holdout_sha256: str,
    candidate_bundle_sha256: str,
    corpus_manifest_sha256: str,
    stage1_model_sha256: str,
    verifier_manifest_sha256: str,
    stt_files_sha256: dict[str, str],
    ffmpeg_sha256: str,
) -> None:
    """Reject any blind run that is not the exact frozen campaign."""

    if (
        preregistration.get("schema")
        != "baxy.wake-verifier-negative-holdout-preregistration.v1"
        or preregistration.get("candidate_frozen") is not True
        or preregistration.get("product_operating_point") is not True
        or preregistration.get("negative_holdout_scored") is not False
        or preregistration.get("blind_human_partition_accessed") is not False
        or preregistration.get("effects_executed") != 0
    ):
        raise ValueError("wake_blind_preregistration_invalid")
    bindings = {
        "candidate_bundle_sha256": candidate_bundle_sha256,
        "positive_development_report_sha256": positive_development_sha256,
        "stage1_model_sha256": stage1_model_sha256,
        "verifier_manifest_sha256": verifier_manifest_sha256,
        "ffmpeg_sha256": ffmpeg_sha256,
    }
    for key, actual in bindings.items():
        if not _hash_equals(actual, preregistration.get(key)):
            raise ValueError(f"wake_blind_binding_mismatch:{key}")
    expected_stt = preregistration.get("stt_files_sha256")
    if not isinstance(expected_stt, dict):
        raise ValueError("wake_blind_stt_binding_missing")
    for name in STT_FILES:
        if not _hash_equals(stt_files_sha256.get(name, ""), expected_stt.get(name)):
            raise ValueError(f"wake_blind_stt_binding_mismatch:{name}")

    positive_sources = positive_development.get("sources")
    positive_metrics = positive_development.get("metrics")
    if (
        positive_development.get("schema")
        != "baxy.wake-verifier-product-capture-development.v1"
        or not isinstance(positive_sources, dict)
        or not isinstance(positive_metrics, dict)
        or positive_metrics.get("gate_passed") is not True
        or positive_metrics.get("positive_accepted")
        != positive_metrics.get("positive_total")
        or positive_metrics.get("hard_negative_false_accepts") != 0
        or positive_development.get("product_operating_point") is not True
        or positive_development.get("blind_human_partition_accessed") is not False
        or positive_development.get("effects_executed") != 0
    ):
        raise ValueError("wake_blind_positive_development_gate_invalid")
    positive_bindings = {
        "corpus_manifest_sha256": corpus_manifest_sha256,
        "stage1_model_sha256": stage1_model_sha256,
        "verifier_manifest_sha256": verifier_manifest_sha256,
        "ffmpeg_sha256": ffmpeg_sha256,
    }
    for key, actual in positive_bindings.items():
        if not _hash_equals(actual, positive_sources.get(key)):
            raise ValueError(f"wake_blind_positive_binding_mismatch:{key}")
    positive_stt = positive_sources.get("stt_files_sha256")
    if not isinstance(positive_stt, dict):
        raise ValueError("wake_blind_positive_stt_binding_missing")
    for name in STT_FILES:
        if not _hash_equals(stt_files_sha256.get(name, ""), positive_stt.get(name)):
            raise ValueError(f"wake_blind_positive_stt_binding_mismatch:{name}")

    metrics = negative_holdout.get("metrics")
    gate = preregistration.get("gate")
    if not isinstance(metrics, dict) or not isinstance(gate, dict):
        raise ValueError("wake_blind_negative_metrics_missing")
    try:
        exposure = float(metrics["exposure_hours"])
        confidence = float(metrics["far_confidence"])
        upper = float(metrics["far_upper_confidence_per_hour"])
        minimum_exposure = float(gate["minimum_exposure_hours"])
        minimum_confidence = float(gate["far_confidence_gte"])
        maximum_upper = float(gate["far_upper_confidence_per_hour_lte"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("wake_blind_negative_metrics_invalid") from error
    if (
        negative_holdout.get("schema")
        != "baxy.wake-verifier-negative-holdout-gate.v1"
        or negative_holdout.get("negative_gate_passed") is not True
        or negative_holdout.get("candidate_frozen") is not True
        or negative_holdout.get("product_operating_point") is not True
        or negative_holdout.get("candidate_development_use") is not False
        or negative_holdout.get("blind_human_partition_accessed") is not False
        or negative_holdout.get("effects_executed") != 0
        or not _hash_equals(
            preregistration_sha256,
            negative_holdout.get("preregistration_sha256"),
        )
        or not _hash_equals(
            verifier_manifest_sha256,
            negative_holdout.get("verifier_manifest_sha256"),
        )
        or metrics.get("negative_false_activations") != 0
        or exposure < minimum_exposure
        or confidence < minimum_confidence
        or upper > maximum_upper
    ):
        raise ValueError("wake_blind_negative_holdout_gate_invalid")
    if not negative_holdout_sha256:
        raise ValueError("wake_blind_negative_holdout_hash_missing")


def select_blind_records(corpus: dict[str, object]) -> list[dict[str, object]]:
    if (
        corpus.get("schema") != "baxy.ccby-wake-holdout-corpus.v1"
        or corpus.get("blind_partition_was_not_scored") is not True
        or corpus.get("blind_human_partition_accessed") is True
    ):
        raise ValueError("wake_blind_corpus_boundary_invalid")
    records = [
        record
        for record in corpus.get("records", [])
        if isinstance(record, dict) and record.get("partition") == "blind"
    ]
    positives = [record for record in records if record.get("label") == "positive"]
    negatives = [
        record for record in records if record.get("label") == "hard_negative"
    ]
    if (
        len(records) != EXPECTED_POSITIVE_COUNT + EXPECTED_HARD_NEGATIVE_COUNT
        or len(positives) != EXPECTED_POSITIVE_COUNT
        or len(negatives) != EXPECTED_HARD_NEGATIVE_COUNT
    ):
        raise ValueError("wake_blind_partition_shape_invalid")
    return records


def summarize(records: list[dict[str, object]]) -> dict[str, object]:
    positives = [record for record in records if record["label"] == "positive"]
    negatives = [
        record for record in records if record["label"] == "hard_negative"
    ]
    accepted = sum(bool(record["detected"]) for record in positives)
    false = sum(bool(record["detected"]) for record in negatives)
    return {
        "positive_accepted": accepted,
        "positive_total": len(positives),
        "hard_negative_false_accepts": false,
        "hard_negative_total": len(negatives),
        "gate_passed": accepted == len(positives) and false == 0,
    }


def evaluate(
    *,
    corpus_manifest_path: Path,
    candidate_bundle_path: Path,
    preregistration_path: Path,
    positive_development_report_path: Path,
    negative_holdout_report_path: Path,
    stage1_model_path: Path,
    verifier_manifest_path: Path,
    stt_directory: Path,
    ffmpeg_path: Path,
    output_path: Path,
    batch_size: int,
) -> dict[str, object]:
    if output_path.exists() or batch_size <= 0:
        raise ValueError("wake_blind_schedule_invalid")
    paths = [
        corpus_manifest_path,
        candidate_bundle_path,
        preregistration_path,
        positive_development_report_path,
        negative_holdout_report_path,
        stage1_model_path,
        verifier_manifest_path,
        stt_directory,
        ffmpeg_path,
    ]
    (
        corpus_manifest_path,
        candidate_bundle_path,
        preregistration_path,
        positive_development_report_path,
        negative_holdout_report_path,
        stage1_model_path,
        verifier_manifest_path,
        stt_directory,
        ffmpeg_path,
    ) = [path.resolve(strict=True) for path in paths]
    output_path = output_path.resolve()
    stt_hashes = {
        name: sha256((stt_directory / name).resolve(strict=True)) for name in STT_FILES
    }
    corpus_hash = sha256(corpus_manifest_path)
    preregistration_hash = sha256(preregistration_path)
    positive_hash = sha256(positive_development_report_path)
    negative_hash = sha256(negative_holdout_report_path)
    validate_release_evidence(
        preregistration=read_json(preregistration_path),
        preregistration_sha256=preregistration_hash,
        positive_development=read_json(positive_development_report_path),
        positive_development_sha256=positive_hash,
        negative_holdout=read_json(negative_holdout_report_path),
        negative_holdout_sha256=negative_hash,
        candidate_bundle_sha256=sha256(candidate_bundle_path),
        corpus_manifest_sha256=corpus_hash,
        stage1_model_sha256=sha256(stage1_model_path),
        verifier_manifest_sha256=sha256(verifier_manifest_path),
        stt_files_sha256=stt_hashes,
        ffmpeg_sha256=sha256(ffmpeg_path),
    )
    source_records = select_blind_records(read_json(corpus_manifest_path))
    verifier_config = load_wake_verifier_candidate_config(verifier_manifest_path)
    if sha256(stage1_model_path) != verifier_config.stage1_model_sha256:
        raise ValueError("wake_blind_stage1_mismatch")

    import sherpa_onnx

    stage1 = BatchedLiveKitPredictor(stage1_model_path)
    recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=str(stt_directory / "encoder.int8.onnx"),
        decoder=str(stt_directory / "decoder.int8.onnx"),
        joiner=str(stt_directory / "joiner.int8.onnx"),
        tokens=str(stt_directory / "tokens.txt"),
        num_threads=6,
        model_type="nemo_transducer",
        decoding_method="modified_beam_search",
        max_active_paths=8,
    )
    warmup = recognizer.create_stream()
    warmup.accept_waveform(SAMPLE_RATE, np.zeros(SAMPLE_RATE // 2, np.float32))
    recognizer.decode_stream(warmup)
    verifier = OnnxWakeVerifier(verifier_config)
    vad = SileroVad()
    corpus_root = corpus_manifest_path.parent
    proposals: list[dict[str, object]] = []
    started = time.perf_counter()
    for source in source_records:
        path = corpus_root / str(source["output_relative_path"])
        wav = source.get("wav")
        if not isinstance(wav, dict) or sha256(path) != wav.get("sha256"):
            raise ValueError(f"wake_blind_audio_hash_mismatch:{path}")
        audio = decode_flac(ffmpeg_path, path)
        scan = streaming_scores(
            stage1,
            audio,
            retention_threshold=verifier_config.broad_threshold,
            hop_samples=verifier_config.stage1_hop_samples,
            frame_samples=512,
        )
        retained = scan["retained_windows"]
        if retained:
            hit = retained[0]
            capture, source_start = capture_audio(
                audio,
                hit_end_seconds=float(hit["window_end_seconds"]),
                pre_roll_seconds=verifier_config.stage1_pre_roll_seconds,
                maximum_turn_samples=verifier_config.maximum_turn_samples,
            )
            verification_start = activity_verification_start(
                capture,
                pre_roll_seconds=verifier_config.stage1_pre_roll_seconds,
                threshold=verifier_config.activity_vad_threshold,
                alignment_samples=verifier_config.activity_alignment_samples,
                default_start_sample=verifier_config.primary_view_start_samples,
                vad=vad,
            )
        else:
            hit = None
            capture = None
            source_start = None
            verification_start = None
        proposals.append(
            {
                "source": source,
                "scan": scan,
                "hit": hit,
                "capture": capture,
                "source_start": source_start,
                "verification_start": verification_start,
            }
        )

    selected = [proposal for proposal in proposals if proposal["hit"]]
    decisions: dict[str, tuple[str, object]] = {}
    for start in range(0, len(selected), batch_size):
        batch = selected[start : start + batch_size]
        streams = []
        for proposal in batch:
            stream = recognizer.create_stream()
            stream.accept_waveform(SAMPLE_RATE, proposal["capture"])
            streams.append(stream)
        for stream in streams:
            recognizer.decode_stream(stream)
        for proposal, stream in zip(batch, streams, strict=True):
            transcript = str(stream.result.text or "").strip()
            decision = verifier.verify(
                proposal["capture"],
                transcript,
                float(proposal["hit"]["score"]),
                verification_start_sample=int(proposal["verification_start"]),
            )
            relative = str(proposal["source"]["output_relative_path"])
            decisions[relative] = (transcript, decision)

    records: list[dict[str, object]] = []
    for proposal in proposals:
        source = proposal["source"]
        relative = str(source["output_relative_path"])
        transcript, decision = decisions.get(relative, ("", None))
        records.append(
            {
                "relative_path": relative,
                "label": source["label"],
                "stage1_hit": proposal["hit"],
                "capture_source_start_sample": proposal["source_start"],
                "capture_samples": (
                    len(proposal["capture"])
                    if proposal["capture"] is not None
                    else 0
                ),
                "verification_start_sample": proposal["verification_start"],
                "transcript": transcript,
                "stage1_eligible": (
                    decision.stage1_eligible if decision is not None else False
                ),
                "method": decision.method if decision is not None else "no_hit",
                "margin": decision.margin if decision is not None else None,
                "detected": decision.accepted if decision is not None else False,
            }
        )
    metrics = summarize(records)
    report: dict[str, object] = {
        "schema": "baxy.wake-verifier-product-capture-blind.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "corpus_manifest_sha256": corpus_hash,
            "candidate_bundle_sha256": sha256(candidate_bundle_path),
            "preregistration_sha256": preregistration_hash,
            "positive_development_report_sha256": positive_hash,
            "negative_holdout_report_sha256": negative_hash,
            "stage1_model_sha256": sha256(stage1_model_path),
            "verifier_manifest_sha256": sha256(verifier_manifest_path),
            "stt_files_sha256": stt_hashes,
            "ffmpeg_sha256": sha256(ffmpeg_path),
        },
        "contract": {
            "first_causal_broad_hit": True,
            "stt_decode_schedule": "single_stream_product_equivalent",
            "stage1_hop_samples": verifier_config.stage1_hop_samples,
            "audio_frame_samples": 512,
            "pre_roll_seconds": verifier_config.stage1_pre_roll_seconds,
            "pre_roll_samples": int(
                verifier_config.stage1_pre_roll_seconds * SAMPLE_RATE / 512
            )
            * 512,
            "trailing_silence_samples": int(0.7 * SAMPLE_RATE / 512) * 512,
            "verification_samples": verifier_config.maximum_samples,
            "primary_view_start_samples": verifier_config.primary_view_start_samples,
            "activity_lookback_samples": verifier_config.activity_lookback_samples,
            "activity_alignment_samples": verifier_config.activity_alignment_samples,
            "activity_vad_threshold": verifier_config.activity_vad_threshold,
            "maximum_turn_samples": verifier_config.maximum_turn_samples,
        },
        "metrics": metrics,
        "records": records,
        "runtime_seconds": time.perf_counter() - started,
        "candidate_frozen": True,
        "product_operating_point": True,
        "negative_holdout_gate_passed": True,
        "blind_human_partition_accessed": True,
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
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--candidate-bundle", type=Path, required=True)
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--positive-development-report", type=Path, required=True)
    parser.add_argument("--negative-holdout-report", type=Path, required=True)
    parser.add_argument("--stage1-model", type=Path, required=True)
    parser.add_argument("--verifier-manifest", type=Path, required=True)
    parser.add_argument("--stt-directory", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=8)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = evaluate(
        corpus_manifest_path=arguments.corpus_manifest,
        candidate_bundle_path=arguments.candidate_bundle,
        preregistration_path=arguments.preregistration,
        positive_development_report_path=arguments.positive_development_report,
        negative_holdout_report_path=arguments.negative_holdout_report,
        stage1_model_path=arguments.stage1_model,
        verifier_manifest_path=arguments.verifier_manifest,
        stt_directory=arguments.stt_directory,
        ffmpeg_path=arguments.ffmpeg,
        output_path=arguments.output,
        batch_size=arguments.batch_size,
    )
    print(json.dumps(report["metrics"], sort_keys=True))
    return 0 if report["metrics"]["gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
