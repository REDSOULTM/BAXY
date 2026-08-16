"""Evaluate the frozen V4 product wake cascade on new expanded development audio."""

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
    activity_verification_start,
    capture_audio,
    decode_flac,
    sha256,
)
from scan_openslr_librispeech_livekit_development import (  # noqa: E402
    BatchedLiveKitPredictor,
    streaming_scores,
)


def select_records(corpus: dict[str, object]) -> list[dict[str, object]]:
    if (
        corpus.get("schema") != "baxy.ccby-wake-v5-development-corpus.v1"
        or corpus.get("scope") != "development_only"
        or corpus.get("blind_human_audio_accessed") is not False
    ):
        raise ValueError("wake_expanded_cascade_boundary_invalid")
    records = [
        record
        for record in corpus.get("records", [])
        if isinstance(record, dict) and record.get("partition") == "development"
    ]
    if (
        len(records) != 12
        or sum(record.get("label") == "positive" for record in records) != 4
        or sum(record.get("label") == "matched_negative" for record in records) != 8
    ):
        raise ValueError("wake_expanded_cascade_records_invalid")
    return records


def summarize(records: list[dict[str, object]]) -> dict[str, object]:
    positives = [record for record in records if record["label"] == "positive"]
    negatives = [
        record for record in records if record["label"] == "matched_negative"
    ]
    accepted = sum(bool(record["detected"]) for record in positives)
    false = sum(bool(record["detected"]) for record in negatives)
    return {
        "positive_accepted": accepted,
        "positive_total": len(positives),
        "matched_negative_false_accepts": false,
        "matched_negative_total": len(negatives),
        "development_gate_passed": accepted == len(positives) and false == 0,
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
    if output_path.exists() or batch_size < 1:
        raise ValueError("wake_expanded_cascade_schedule_invalid")
    corpus_manifest_path = corpus_manifest_path.resolve(strict=True)
    stage1_model_path = stage1_model_path.resolve(strict=True)
    verifier_manifest_path = verifier_manifest_path.resolve(strict=True)
    stt_directory = stt_directory.resolve(strict=True)
    ffmpeg_path = ffmpeg_path.resolve(strict=True)
    output_path = output_path.resolve()
    corpus = json.loads(corpus_manifest_path.read_text(encoding="utf-8-sig"))
    if not isinstance(corpus, dict):
        raise ValueError("wake_expanded_cascade_manifest_invalid")
    source_records = select_records(corpus)
    verifier_config = load_wake_verifier_candidate_config(verifier_manifest_path)
    if sha256(stage1_model_path) != verifier_config.stage1_model_sha256:
        raise ValueError("wake_expanded_cascade_stage1_mismatch")
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
    proposals: list[dict[str, object]] = []
    started = time.perf_counter()
    for source in source_records:
        path = corpus_root / str(source["output_relative_path"])
        wav = source.get("wav")
        if not isinstance(wav, dict) or sha256(path) != wav.get("sha256"):
            raise ValueError(f"wake_expanded_cascade_audio_hash_mismatch:{path}")
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
                "source_id": source.get("source_id"),
                "speaker_group": source.get("speaker_group"),
                "label": source["label"],
                "stage1_hit": proposal["hit"],
                "transcript": transcript,
                "stage1_eligible": decision.stage1_eligible if decision else False,
                "method": decision.method if decision else "no_hit",
                "margin": decision.margin if decision else None,
                "detected": decision.accepted if decision else False,
            }
        )
    metrics = summarize(records)
    report: dict[str, object] = {
        "schema": "baxy.wake-verifier-expanded-development.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "new_expanded_development_only_frozen_v4_product_cascade",
        "sources": {
            "corpus_manifest_sha256": sha256(corpus_manifest_path),
            "stage1_model_sha256": sha256(stage1_model_path),
            "verifier_manifest_sha256": sha256(verifier_manifest_path),
            "stt_files_sha256": {
                name: sha256(stt_directory / name) for name in STT_FILES
            },
            "ffmpeg_sha256": sha256(ffmpeg_path),
        },
        "contract": {
            "candidate_was_frozen_before_expanded_corpus_existed": True,
            "first_causal_broad_hit": True,
            "stage1_hop_samples": verifier_config.stage1_hop_samples,
            "audio_frame_samples": 512,
            "verification_samples": verifier_config.maximum_samples,
            "maximum_turn_samples": verifier_config.maximum_turn_samples,
        },
        "metrics": metrics,
        "records": records,
        "runtime_seconds": time.perf_counter() - started,
        "candidate_frozen": False,
        "product_operating_point": False,
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
    print(json.dumps(report["metrics"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
