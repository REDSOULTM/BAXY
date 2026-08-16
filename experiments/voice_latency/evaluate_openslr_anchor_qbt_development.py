"""Evaluate broad LiveKit proposals with the locator-free anchored QbT verifier."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

import numpy as np


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from audit_openslr_librispeech_retained_parakeet import decode_flac  # noqa: E402
from evaluate_phoneme_teacher_category_oracle_v2 import (  # noqa: E402
    compress_category_logits,
    search_anchored_category_probabilities,
)
from phoneme_student_vocabulary_v2 import resolve_category_ids  # noqa: E402
from train_mdtc_livekit_verifier_student import read_json, sha256  # noqa: E402


SAMPLE_RATE = 16_000


def select_broad_records(
    corpus_records: list[dict[str, object]],
    scan_records: list[dict[str, object]],
    threshold: float,
) -> list[tuple[dict[str, object], dict[str, object]]]:
    if not 0.0 < threshold < 1.0:
        raise ValueError("openslr_anchor_threshold_invalid")
    corpus_by_id = {str(record.get("utterance_id")): record for record in corpus_records}
    if len(corpus_by_id) != len(corpus_records) or len(scan_records) != len(corpus_records):
        raise ValueError("openslr_anchor_record_count_invalid")
    selected = []
    for scan in scan_records:
        utterance_id = str(scan.get("utterance_id"))
        corpus = corpus_by_id.get(utterance_id)
        if (
            corpus is None
            or corpus.get("relative_path") != scan.get("relative_path")
            or corpus.get("sha256") != scan.get("wav_sha256")
        ):
            raise ValueError(f"openslr_anchor_identity_mismatch:{utterance_id}")
        if float(scan.get("max_score", -1.0)) >= threshold:
            selected.append((corpus, scan))
    return selected


def run(
    *,
    teacher_directory: Path,
    ffmpeg_path: Path,
    corpus_manifest_path: Path,
    scan_report_path: Path,
    output_path: Path,
    threshold: float,
    margin_threshold: float,
    batch_size: int,
    device: str,
) -> dict[str, object]:
    teacher_directory = teacher_directory.resolve(strict=True)
    ffmpeg_path = ffmpeg_path.resolve(strict=True)
    corpus_manifest_path = corpus_manifest_path.resolve(strict=True)
    scan_report_path = scan_report_path.resolve(strict=True)
    output_path = output_path.resolve()
    if (
        output_path.exists()
        or batch_size <= 0
        or device not in {"cpu", "cuda"}
        or not np.isfinite(margin_threshold)
    ):
        raise ValueError("openslr_anchor_schedule_invalid")
    corpus = read_json(corpus_manifest_path)
    scan = read_json(scan_report_path)
    if (
        corpus.get("schema") != "baxy.openslr-librispeech-negative-development.v1"
        or scan.get("schema")
        != "baxy.openslr-librispeech-livekit-development-scan.v1"
        or scan.get("corpus_manifest_sha256") != sha256(corpus_manifest_path)
        or corpus.get("blind_human_partition_accessed") is not False
        or scan.get("blind_human_partition_accessed") is not False
    ):
        raise ValueError("openslr_anchor_source_invalid")
    corpus_records = corpus.get("records")
    scan_records = scan.get("records")
    if not isinstance(corpus_records, list) or not isinstance(scan_records, list):
        raise ValueError("openslr_anchor_records_missing")
    selected = select_broad_records(corpus_records, scan_records, threshold)

    import torch
    import transformers
    from transformers import Wav2Vec2FeatureExtractor, Wav2Vec2ForCTC

    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("openslr_anchor_cuda_required")
    extractor = Wav2Vec2FeatureExtractor.from_pretrained(
        teacher_directory, local_files_only=True
    )
    model = Wav2Vec2ForCTC.from_pretrained(
        teacher_directory, local_files_only=True
    ).eval().to(device)
    vocabulary = read_json(teacher_directory / "vocab.json")
    model_config = read_json(teacher_directory / "config.json")
    category_ids = resolve_category_ids(vocabulary, int(model_config["pad_token_id"]))

    raw_corpus_root = corpus.get("corpus_root")
    if not isinstance(raw_corpus_root, str) or not raw_corpus_root:
        raise ValueError("openslr_anchor_corpus_root_missing")
    corpus_root = Path(raw_corpus_root).resolve(strict=True)
    records = []
    inference_seconds = 0.0
    decoded_seconds = 0.0
    started = time.perf_counter()
    for batch_start in range(0, len(selected), batch_size):
        batch = selected[batch_start : batch_start + batch_size]
        audios = []
        for corpus_record, _ in batch:
            path = corpus_root / str(corpus_record["relative_path"])
            if sha256(path) != corpus_record.get("sha256"):
                raise ValueError(f"openslr_anchor_audio_hash_mismatch:{path}")
            audio = decode_flac(ffmpeg_path, path)
            if len(audio) != int(corpus_record["frames"]):
                raise ValueError(f"openslr_anchor_audio_length_mismatch:{path}")
            audios.append(audio)
            decoded_seconds += len(audio) / SAMPLE_RATE
        prepared = extractor(
            audios,
            sampling_rate=SAMPLE_RATE,
            return_tensors="pt",
            padding=True,
        )
        input_lengths = torch.tensor(
            [len(audio) for audio in audios], dtype=torch.long, device=device
        )
        inference_started = time.perf_counter()
        with torch.inference_mode():
            logits = model(input_values=prepared.input_values.to(device)).logits
            categories = compress_category_logits(torch, logits, category_ids).cpu().numpy()
        if device == "cuda":
            torch.cuda.synchronize()
        inference_seconds += time.perf_counter() - inference_started
        output_lengths = model._get_feat_extract_output_lengths(input_lengths).cpu().tolist()
        for index, (corpus_record, scan_record) in enumerate(batch):
            probabilities = categories[index, : int(output_lengths[index])]
            scored = search_anchored_category_probabilities(probabilities)
            best = scored.get("best_verifier")
            margin = float(best["margin"]) if isinstance(best, dict) else None
            records.append(
                {
                    "utterance_id": corpus_record["utterance_id"],
                    "relative_path": corpus_record["relative_path"],
                    "wav_sha256": corpus_record["sha256"],
                    "duration_seconds": corpus_record["duration_seconds"],
                    "livekit_max_score": scan_record["max_score"],
                    "anchor_candidates": int(scored["candidate_count"]),
                    "margin": margin,
                    "detected": margin is not None and margin >= margin_threshold,
                }
            )

    false_activations = sum(bool(record["detected"]) for record in records)
    exposure_seconds = sum(float(record["duration_seconds"]) for record in corpus_records)
    report = {
        "schema": "baxy.openslr-anchor-qbt-development.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "development_only",
        "sources": {
            "corpus_manifest": corpus_manifest_path.as_posix(),
            "corpus_manifest_sha256": sha256(corpus_manifest_path),
            "livekit_scan": scan_report_path.as_posix(),
            "livekit_scan_sha256": sha256(scan_report_path),
            "teacher_directory": teacher_directory.as_posix(),
            "teacher_weights_sha256": sha256(teacher_directory / "pytorch_model.bin"),
            "ffmpeg": ffmpeg_path.as_posix(),
            "ffmpeg_sha256": sha256(ffmpeg_path),
        },
        "contract": {
            "livekit_broad_threshold": threshold,
            "locator": "category_qbt_greedy_boundary_anchors",
            "decision_margin_gte": margin_threshold,
        },
        "metrics": {
            "utterances": len(corpus_records),
            "exposure_seconds": exposure_seconds,
            "exposure_hours": exposure_seconds / 3600.0,
            "stage1_proposals": len(selected),
            "stage1_proposal_rate": len(selected) / len(corpus_records),
            "verifier_audio_seconds": decoded_seconds,
            "false_activations": false_activations,
            "point_false_activations_per_hour": false_activations
            / (exposure_seconds / 3600.0),
        },
        "runtime": {
            "device": device,
            "batch_size": batch_size,
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "inference_seconds": inference_seconds,
            "wall_seconds": time.perf_counter() - started,
        },
        "records": records,
        "candidate_frozen": False,
        "product_operating_point": False,
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
    parser.add_argument("--teacher-dir", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--scan-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threshold", type=float, default=0.02)
    parser.add_argument("--margin", type=float, default=0.5)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = run(
        teacher_directory=arguments.teacher_dir,
        ffmpeg_path=arguments.ffmpeg,
        corpus_manifest_path=arguments.corpus_manifest,
        scan_report_path=arguments.scan_report,
        output_path=arguments.output,
        threshold=arguments.threshold,
        margin_threshold=arguments.margin,
        batch_size=arguments.batch_size,
        device=arguments.device,
    )
    print(json.dumps(report["metrics"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
