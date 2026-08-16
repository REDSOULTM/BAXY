"""Verify the complete causal product capture on human development clips."""

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
from baxy_mind.wake_verifier import (  # noqa: E402
    OnnxWakeVerifier,
    load_wake_verifier_candidate_config,
)
from baxy_mind.voice import SileroVad  # noqa: E402
from evaluate_wake_verifier_negative_holdout_v1 import (  # noqa: E402
    SAMPLE_RATE,
    STT_FILES,
    capture_audio,
    decode_flac,
    sha256,
    activity_verification_start,
)
from scan_openslr_librispeech_livekit_development import (  # noqa: E402
    BatchedLiveKitPredictor,
    streaming_scores,
)


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
    stage1_model_path: Path,
    verifier_manifest_path: Path,
    stt_directory: Path,
    ffmpeg_path: Path,
    output_path: Path,
    batch_size: int,
) -> dict[str, object]:
    if output_path.exists() or batch_size <= 0:
        raise ValueError("wake_product_capture_schedule_invalid")
    corpus_manifest_path = corpus_manifest_path.resolve(strict=True)
    stage1_model_path = stage1_model_path.resolve(strict=True)
    verifier_manifest_path = verifier_manifest_path.resolve(strict=True)
    stt_directory = stt_directory.resolve(strict=True)
    ffmpeg_path = ffmpeg_path.resolve(strict=True)
    output_path = output_path.resolve()
    corpus = json.loads(corpus_manifest_path.read_text(encoding="utf-8"))
    if (
        corpus.get("blind_partition_was_not_scored") is not True
        or corpus.get("blind_human_partition_accessed") is True
    ):
        raise ValueError("wake_product_capture_blind_boundary_invalid")
    source_records = [
        record
        for record in corpus.get("records", [])
        if isinstance(record, dict) and record.get("partition") == "development"
    ]
    if len(source_records) != 18:
        raise ValueError("wake_product_capture_development_records_invalid")
    verifier_config = load_wake_verifier_candidate_config(
        verifier_manifest_path
    )
    if sha256(stage1_model_path) != verifier_config.stage1_model_sha256:
        raise ValueError("wake_product_capture_stage1_mismatch")
    for name in STT_FILES:
        (stt_directory / name).resolve(strict=True)

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
    proposals = []
    started = time.perf_counter()
    for source in source_records:
        path = corpus_root / str(source["output_relative_path"])
        wav = source.get("wav")
        if not isinstance(wav, dict) or sha256(path) != wav.get("sha256"):
            raise ValueError(f"wake_product_capture_audio_hash_mismatch:{path}")
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
                default_start_sample=(
                    verifier_config.primary_view_start_samples
                ),
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
    records: list[dict[str, object]] = []
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
                verification_start_sample=int(
                    proposal["verification_start"]
                ),
            )
            relative = str(proposal["source"]["output_relative_path"])
            decisions[relative] = (transcript, decision)
    for proposal in proposals:
        source = proposal["source"]
        relative = str(source["output_relative_path"])
        hit = proposal["hit"]
        transcript, decision = decisions.get(relative, ("", None))
        records.append(
            {
                "relative_path": relative,
                "label": source["label"],
                "stage1_hit": hit,
                "capture_source_start_sample": proposal["source_start"],
                "capture_samples": (
                    len(proposal["capture"])
                    if proposal["capture"] is not None
                    else 0
                ),
                "verification_start_sample": proposal[
                    "verification_start"
                ],
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
        "schema": "baxy.wake-verifier-product-capture-development.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "corpus_manifest": corpus_manifest_path.as_posix(),
            "corpus_manifest_sha256": sha256(corpus_manifest_path),
            "stage1_model_sha256": sha256(stage1_model_path),
            "verifier_manifest_sha256": sha256(verifier_manifest_path),
            "stt_files_sha256": {
                name: sha256(stt_directory / name) for name in STT_FILES
            },
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
            "primary_view_start_samples": (
                verifier_config.primary_view_start_samples
            ),
            "activity_lookback_samples": (
                verifier_config.activity_lookback_samples
            ),
            "activity_alignment_samples": (
                verifier_config.activity_alignment_samples
            ),
            "activity_vad_threshold": verifier_config.activity_vad_threshold,
            "maximum_turn_samples": verifier_config.maximum_turn_samples,
        },
        "metrics": metrics,
        "records": records,
        "runtime_seconds": time.perf_counter() - started,
        "candidate_frozen": False,
        "product_operating_point": True,
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
    parser.add_argument("--corpus-manifest", type=Path, required=True)
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
        stage1_model_path=arguments.stage1_model,
        verifier_manifest_path=arguments.verifier_manifest,
        stt_directory=arguments.stt_directory,
        ffmpeg_path=arguments.ffmpeg,
        output_path=arguments.output,
        batch_size=arguments.batch_size,
    )
    print(json.dumps(report["metrics"]))
    return 0 if report["metrics"]["gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
