"""Open one frozen negative holdout with the exact two-stage product policy."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import time

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from baxy_mind.wake_verifier import (  # noqa: E402
    OnnxWakeVerifier,
    load_wake_verifier_candidate_config,
    stage1_eligible,
)
from baxy_mind.voice import (  # noqa: E402
    VAD_WINDOW_SAMPLES,
    SileroVad,
    _wake_activity_onset_sample,
    _wake_frame_count,
)


SAMPLE_RATE = 16_000
STT_FILES = (
    "encoder.int8.onnx",
    "decoder.int8.onnx",
    "joiner.int8.onnx",
    "tokens.txt",
)


def opened_negative_regression_authority(
    corpus: dict[str, object],
    preregistration: dict[str, object],
    *,
    preregistration_supplied: bool,
) -> bool:
    """Identify an explicitly opened former holdout without granting FAR authority."""

    return (
        preregistration_supplied
        and corpus.get("schema")
        == "baxy.openslr-librispeech-negative-holdout.v1"
        and preregistration.get("schema")
        == "baxy.wake-verifier-negative-holdout-preregistration.v1"
        and preregistration.get("negative_corpus_previously_accessed") is True
        and preregistration.get("fresh_holdout_claim_supported") is False
        and preregistration.get("far_certification_supported") is False
        and preregistration.get("product_operating_point") is False
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def bytes_sha256(values: np.ndarray) -> str:
    return hashlib.sha256(
        np.ascontiguousarray(values, dtype="<f4").tobytes()
    ).hexdigest()


def read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"json_root_is_not_object:{path}")
    return value


def decode_flac(ffmpeg_path: Path, audio_path: Path) -> np.ndarray:
    completed = subprocess.run(
        [
            str(ffmpeg_path),
            "-v",
            "error",
            "-nostdin",
            "-i",
            str(audio_path),
            "-ac",
            "1",
            "-ar",
            str(SAMPLE_RATE),
            "-f",
            "f32le",
            "-acodec",
            "pcm_f32le",
            "pipe:1",
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    audio = np.frombuffer(completed.stdout, dtype="<f4").copy()
    if audio.size == 0 or not np.isfinite(audio).all():
        raise ValueError(f"wake_holdout_audio_decode_invalid:{audio_path}")
    return audio


def capture_audio(
    audio: np.ndarray,
    *,
    hit_end_seconds: float,
    pre_roll_seconds: float,
    maximum_turn_samples: int,
    trailing_silence_seconds: float = 0.7,
) -> tuple[np.ndarray, int]:
    values = np.asarray(audio, dtype=np.float32).reshape(-1)
    if (
        not np.isfinite(values).all()
        or not math.isfinite(hit_end_seconds)
        or hit_end_seconds < 0.0
        or pre_roll_seconds <= 0.0
        or maximum_turn_samples <= 0
        or trailing_silence_seconds < 0.0
    ):
        raise ValueError("wake_holdout_capture_invalid")
    pre_roll_samples = _wake_frame_count(pre_roll_seconds) * VAD_WINDOW_SAMPLES
    trailing_samples = (
        _wake_frame_count(trailing_silence_seconds) * VAD_WINDOW_SAMPLES
        if trailing_silence_seconds > 0.0
        else 0
    )
    start = round(hit_end_seconds * SAMPLE_RATE) - pre_roll_samples
    leading = max(0, -start)
    source_start = max(0, start)
    captured = np.concatenate(
        (
            np.zeros(leading, np.float32),
            values[source_start:],
            np.zeros(trailing_samples, np.float32),
        )
    )
    return (
        np.ascontiguousarray(captured[:maximum_turn_samples]),
        source_start,
    )


def activity_verification_start(
    capture: np.ndarray,
    *,
    pre_roll_seconds: float,
    threshold: float,
    alignment_samples: int,
    default_start_sample: int,
    vad: object,
) -> int:
    history_samples = min(
        len(capture),
        _wake_frame_count(pre_roll_seconds) * VAD_WINDOW_SAMPLES,
    )
    history = np.asarray(capture[:history_samples], dtype=np.float32)
    history = np.pad(
        history,
        (0, (-len(history)) % VAD_WINDOW_SAMPLES),
        mode="constant",
    )
    vad.reset()
    probabilities = [
        float(vad.process(history[start : start + VAD_WINDOW_SAMPLES]))
        for start in range(0, len(history), VAD_WINDOW_SAMPLES)
    ]
    vad.reset()
    return _wake_activity_onset_sample(
        probabilities,
        threshold=threshold,
        frame_samples=VAD_WINDOW_SAMPLES,
        alignment_samples=alignment_samples,
        default_start_sample=default_start_sample,
    )


def selected_records(
    corpus: dict[str, object], scan: dict[str, object]
) -> list[dict[str, object]]:
    corpus_records = corpus.get("records")
    scan_records = scan.get("records")
    if not isinstance(corpus_records, list) or not isinstance(scan_records, list):
        raise ValueError("wake_holdout_records_missing")
    corpus_by_id = {
        str(record.get("utterance_id")): record
        for record in corpus_records
        if isinstance(record, dict)
    }
    selected = []
    for scan_record in scan_records:
        if not isinstance(scan_record, dict):
            raise ValueError("wake_holdout_scan_record_invalid")
        retained = scan_record.get("retained_windows")
        if not isinstance(retained, list):
            raise ValueError("wake_holdout_retained_windows_invalid")
        if not retained:
            continue
        hit = retained[0]
        if not isinstance(hit, dict):
            raise ValueError("wake_holdout_hit_invalid")
        source = corpus_by_id.get(str(scan_record.get("utterance_id")))
        if source is None or source.get("relative_path") != scan_record.get(
            "relative_path"
        ):
            raise ValueError("wake_holdout_record_identity_mismatch")
        selected.append({"source": source, "scan": scan_record, "hit": hit})
    return selected


def _checkpoint(
    path: Path,
    *,
    preregistration_sha256: str,
    scan_sha256: str,
    evaluation_seconds: float,
    records: list[dict[str, object]],
) -> None:
    if not math.isfinite(evaluation_seconds) or evaluation_seconds < 0.0:
        raise ValueError("wake_holdout_checkpoint_runtime_invalid")
    path.write_text(
        json.dumps(
            {
                "schema": "baxy.wake-verifier-negative-holdout-checkpoint.v1",
                "preregistration_sha256": preregistration_sha256,
                "scan_sha256": scan_sha256,
                "evaluation_seconds": evaluation_seconds,
                "records": records,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _load_checkpoint(
    path: Path,
    *,
    preregistration_sha256: str,
    scan_sha256: str,
    selected: list[dict[str, object]],
) -> tuple[list[dict[str, object]], float]:
    if not path.is_file():
        return [], 0.0
    value = read_json(path)
    records = value.get("records")
    evaluation_seconds = value.get("evaluation_seconds")
    if (
        value.get("schema")
        != "baxy.wake-verifier-negative-holdout-checkpoint.v1"
        or value.get("preregistration_sha256") != preregistration_sha256
        or value.get("scan_sha256") != scan_sha256
        or isinstance(evaluation_seconds, bool)
        or not isinstance(evaluation_seconds, (int, float))
        or not math.isfinite(float(evaluation_seconds))
        or float(evaluation_seconds) < 0.0
        or not isinstance(records, list)
        or len(records) > len(selected)
    ):
        raise ValueError("wake_holdout_checkpoint_mismatch")
    for index, record in enumerate(records):
        source = selected[index]["source"]
        if not isinstance(record, dict) or record.get(
            "utterance_id"
        ) != source.get("utterance_id"):
            raise ValueError("wake_holdout_checkpoint_order_mismatch")
    return records, float(evaluation_seconds)


def evaluate(
    *,
    corpus_manifest_path: Path,
    scan_path: Path,
    preregistration_path: Path | None,
    verifier_manifest_path: Path,
    stt_directory: Path,
    ffmpeg_path: Path,
    output_path: Path,
    batch_size: int,
) -> dict[str, object]:
    if batch_size <= 0 or output_path.exists():
        raise ValueError("wake_holdout_schedule_invalid")
    corpus_manifest_path = corpus_manifest_path.resolve(strict=True)
    scan_path = scan_path.resolve(strict=True)
    verifier_manifest_path = verifier_manifest_path.resolve(strict=True)
    stt_directory = stt_directory.resolve(strict=True)
    ffmpeg_path = ffmpeg_path.resolve(strict=True)
    if preregistration_path is not None:
        preregistration_path = preregistration_path.resolve(strict=True)
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    corpus_hash = sha256(corpus_manifest_path)
    scan_hash = sha256(scan_path)
    preregistration_hash = (
        sha256(preregistration_path)
        if preregistration_path is not None
        else None
    )
    verifier_manifest_hash = sha256(verifier_manifest_path)
    corpus = read_json(corpus_manifest_path)
    scan = read_json(scan_path)
    preregistration = (
        read_json(preregistration_path)
        if preregistration_path is not None
        else {}
    )
    native_development = (
        corpus.get("schema")
        == "baxy.openslr-librispeech-negative-development.v1"
    )
    opened_regression = opened_negative_regression_authority(
        corpus,
        preregistration,
        preregistration_supplied=preregistration_path is not None,
    )
    development = native_development or opened_regression
    if native_development:
        if (
            preregistration_path is not None
            or scan.get("schema")
            != "baxy.openslr-librispeech-livekit-development-scan.v1"
            or scan.get("corpus_manifest_sha256") != corpus_hash
            or scan.get("candidate_development_use") is not True
            or scan.get("product_runtime_equivalent_schedule") is not True
        ):
            raise ValueError("wake_development_source_mismatch")
    elif opened_regression:
        if (
            scan.get("schema")
            != "baxy.openslr-librispeech-livekit-holdout-scan.v1"
            or scan.get("corpus_manifest_sha256") != corpus_hash
            or scan.get("preregistration_sha256") != preregistration_hash
            or scan.get("product_far_claim_supported") is not False
            or preregistration.get("candidate_frozen") is not True
            or preregistration.get("negative_corpus_manifest_sha256")
            != corpus_hash
            or preregistration.get("verifier_manifest_sha256")
            != verifier_manifest_hash
        ):
            raise ValueError("wake_opened_regression_source_mismatch")
    else:
        if preregistration_path is None:
            raise ValueError("wake_holdout_preregistration_required")
        if (
            corpus.get("schema")
            != "baxy.openslr-librispeech-negative-holdout.v1"
            or scan.get("schema")
            != "baxy.openslr-librispeech-livekit-holdout-scan.v1"
            or scan.get("corpus_manifest_sha256") != corpus_hash
            or scan.get("preregistration_sha256") != preregistration_hash
            or preregistration.get("candidate_frozen") is not True
            or preregistration.get("negative_corpus_manifest_sha256")
            != corpus_hash
            or preregistration.get("verifier_manifest_sha256")
            != verifier_manifest_hash
            or preregistration.get("evaluation_script_sha256")
            != sha256(Path(__file__).resolve())
        ):
            raise ValueError("wake_holdout_preregistration_mismatch")
        for name in STT_FILES:
            if sha256(stt_directory / name) != preregistration.get(
                "stt_files_sha256", {}
            ).get(name):
                raise ValueError("wake_holdout_stt_mismatch")
        if sha256(ffmpeg_path) != preregistration.get("ffmpeg_sha256"):
            raise ValueError("wake_holdout_ffmpeg_mismatch")
    verifier_config = load_wake_verifier_candidate_config(
        verifier_manifest_path
    )
    if development:
        if (
            scan.get("model_sha256")
            != verifier_config.stage1_model_sha256
            or scan.get("retention_threshold")
            != verifier_config.broad_threshold
            or scan.get("hop_samples")
            != verifier_config.stage1_hop_samples
        ):
            raise ValueError("wake_development_candidate_mismatch")
    elif (
        verifier_config.graph_sha256
        != preregistration.get("verifier_graph_sha256")
        or verifier_config.graph_data_sha256
        != preregistration.get("verifier_graph_data_sha256")
        or verifier_config.vocabulary_sha256
        != preregistration.get("verifier_vocabulary_sha256")
        or verifier_config.stage1_model_sha256
        != preregistration.get("stage1_model_sha256")
    ):
        raise ValueError("wake_holdout_candidate_mismatch")
    selected = selected_records(corpus, scan)
    corpus_root = Path(str(corpus["corpus_root"])).resolve(strict=True)
    checkpoint_path = output_path.with_suffix(output_path.suffix + ".partial.json")
    checkpoint_authority = preregistration_hash or verifier_manifest_hash
    records, completed_evaluation_seconds = _load_checkpoint(
        checkpoint_path,
        preregistration_sha256=checkpoint_authority,
        scan_sha256=scan_hash,
        selected=selected,
    )

    import onnxruntime
    import sherpa_onnx

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
    started = time.perf_counter()
    for start in range(len(records), len(selected), batch_size):
        batch = selected[start : start + batch_size]
        streams = []
        stream_indices = []
        captures = []
        starts = []
        transcripts = [""] * len(batch)
        for index, item in enumerate(batch):
            source = item["source"]
            path = corpus_root / str(source["relative_path"])
            if sha256(path) != source.get("sha256"):
                raise ValueError(f"wake_holdout_audio_hash_mismatch:{path}")
            audio = decode_flac(ffmpeg_path, path)
            capture, source_start = capture_audio(
                audio,
                hit_end_seconds=float(item["hit"]["window_end_seconds"]),
                pre_roll_seconds=verifier_config.stage1_pre_roll_seconds,
                maximum_turn_samples=verifier_config.maximum_turn_samples,
            )
            captures.append(capture)
            starts.append(source_start)
            stream = recognizer.create_stream()
            stream.accept_waveform(SAMPLE_RATE, capture)
            streams.append(stream)
            stream_indices.append(index)
        if streams:
            for stream in streams:
                recognizer.decode_stream(stream)
            for index, stream in zip(stream_indices, streams, strict=True):
                transcripts[index] = str(stream.result.text or "").strip()
        for index, (item, capture, source_start) in enumerate(
            zip(batch, captures, starts, strict=True)
        ):
            source = item["source"]
            hit = item["hit"]
            transcript = transcripts[index]
            eligible = stage1_eligible(
                float(hit["score"]),
                transcript,
                broad_threshold=verifier_config.broad_threshold,
                strong_threshold=verifier_config.strong_threshold,
            )
            verification_start = verifier_config.primary_view_start_samples
            if eligible:
                verification_start = activity_verification_start(
                    capture,
                    pre_roll_seconds=(
                        verifier_config.stage1_pre_roll_seconds
                    ),
                    threshold=verifier_config.activity_vad_threshold,
                    alignment_samples=(
                        verifier_config.activity_alignment_samples
                    ),
                    default_start_sample=(
                        verifier_config.primary_view_start_samples
                    ),
                    vad=vad,
                )
            decision = verifier.verify(
                capture,
                transcript,
                float(hit["score"]),
                verification_start_sample=verification_start,
            )
            records.append(
                {
                    "utterance_id": source["utterance_id"],
                    "relative_path": source["relative_path"],
                    "wav_sha256": source["sha256"],
                    "duration_seconds": source["duration_seconds"],
                    "hit_window_end_seconds": hit["window_end_seconds"],
                    "stage1_confidence": hit["score"],
                    "capture_source_start_sample": source_start,
                    "capture_samples": len(capture),
                    "capture_sha256": bytes_sha256(capture),
                    "verification_start_sample": verification_start,
                    "transcript": transcript,
                    "transcript_decoded": True,
                    "stage1_eligible": decision.stage1_eligible,
                    "verifier_method": decision.method,
                    "verifier_margin": decision.margin,
                    "detected": decision.accepted,
                }
            )
        _checkpoint(
            checkpoint_path,
            preregistration_sha256=checkpoint_authority,
            scan_sha256=scan_hash,
            evaluation_seconds=(
                completed_evaluation_seconds
                + time.perf_counter()
                - started
            ),
            records=records,
        )
        print(f"PROGRESS|{len(records)}/{len(selected)}", flush=True)
    evaluation_seconds = (
        completed_evaluation_seconds + time.perf_counter() - started
    )
    metrics = corpus.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError("wake_holdout_corpus_metrics_missing")
    exposure_hours = float(metrics["audio_hours"])
    false_activations = sum(bool(record["detected"]) for record in records)
    far_upper = (
        -math.log(0.05) / exposure_hours
        if false_activations == 0
        else None
    )
    negative_gate = (
        false_activations == 0
        and exposure_hours >= -math.log(0.05) / 0.1
        and far_upper is not None
        and far_upper <= 0.1
    )
    development_gate = development and false_activations == 0
    report: dict[str, object] = {
        "schema": (
            "baxy.wake-verifier-negative-development.v1"
            if native_development
            else (
                "baxy.wake-verifier-negative-opened-regression.v1"
                if opened_regression
                else "baxy.wake-verifier-negative-holdout-gate.v1"
            )
        ),
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "preregistration": (
            preregistration_path.as_posix()
            if preregistration_path is not None
            else None
        ),
        "preregistration_sha256": preregistration_hash,
        "corpus_manifest": corpus_manifest_path.as_posix(),
        "corpus_manifest_sha256": corpus_hash,
        "stage1_scan": scan_path.as_posix(),
        "stage1_scan_sha256": scan_hash,
        "verifier_manifest": verifier_manifest_path.as_posix(),
        "verifier_manifest_sha256": verifier_manifest_hash,
        "metrics": {
            "exposure_hours": exposure_hours,
            "stage1_proposals": len(selected),
            "stage1_eligible": sum(
                bool(record["stage1_eligible"]) for record in records
            ),
            "negative_false_activations": false_activations,
            "point_false_activations_per_hour": (
                false_activations / exposure_hours
            ),
            "far_confidence": 0.95,
            "far_upper_confidence_per_hour": far_upper,
        },
        "runtime": {
            "evaluation_seconds": evaluation_seconds,
            "onnxruntime": onnxruntime.__version__,
            "sherpa_onnx": getattr(sherpa_onnx, "__version__", None),
            "batch_size": batch_size,
            "stt_decode_schedule": "single_stream_product_equivalent",
            "strong_stage1_transcript_elision": False,
        },
        "records": records,
        "negative_gate_passed": negative_gate if not development else False,
        "development_gate_passed": development_gate,
        "candidate_frozen": not native_development,
        "product_operating_point": not development,
        "candidate_development_use": development,
        "negative_corpus_previously_accessed": opened_regression,
        "fresh_holdout_claim_supported": not development,
        "far_certification_supported": not development,
        "blind_human_partition_accessed": False,
        "effects_executed": 0,
    }
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    checkpoint_path.unlink(missing_ok=True)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--scan", type=Path, required=True)
    parser.add_argument("--preregistration", type=Path)
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
        scan_path=arguments.scan,
        preregistration_path=arguments.preregistration,
        verifier_manifest_path=arguments.verifier_manifest,
        stt_directory=arguments.stt_directory,
        ffmpeg_path=arguments.ffmpeg,
        output_path=arguments.output,
        batch_size=arguments.batch_size,
    )
    print(
        json.dumps(
            {
                "output": arguments.output.resolve().as_posix(),
                "metrics": report["metrics"],
                "negative_gate_passed": report["negative_gate_passed"],
                "development_gate_passed": report[
                    "development_gate_passed"
                ],
            }
        )
    )
    return 0 if (
        report["negative_gate_passed"]
        or report["development_gate_passed"]
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
