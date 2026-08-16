"""Extract the highest-scoring log-Mel windows from known wake false alarms."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any

import numpy as np


SCHEMA = "baxy.openslr-wake-hard-negative-logmel.v1"
REPORT_SCHEMA = "baxy.wake-cascade-openslr-negative-regression.v1"
CORPUS_SCHEMA = "baxy.openslr-librispeech-negative-holdout.v1"
CASCADE_SCHEMAS = {"baxy-wake-cascade-v1", "baxy-wake-cascade-v2"}
SAMPLE_RATE = 16_000
WINDOW_SAMPLES = 48_000
FRAMES = 300
MEL_BINS = 80


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("baxy_wake_hard_negative_json_invalid")
    return value


def load_component(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("baxy_wake_hard_negative_component_invalid")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def decode_flac(ffmpeg: Path, path: Path) -> np.ndarray:
    result = subprocess.run(
        [
            str(ffmpeg),
            "-v",
            "error",
            "-i",
            str(path),
            "-f",
            "f32le",
            "-ac",
            "1",
            "-ar",
            str(SAMPLE_RATE),
            "pipe:1",
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    audio = np.frombuffer(result.stdout, dtype="<f4").copy()
    if not len(audio) or not np.isfinite(audio).all():
        raise ValueError("baxy_wake_hard_negative_audio_invalid")
    return audio


def stream_audio(audio: np.ndarray) -> np.ndarray:
    left = SAMPLE_RATE
    right = max(SAMPLE_RATE, WINDOW_SAMPLES - left - len(audio))
    return np.pad(np.asarray(audio, dtype=np.float32), (left, right))


def window_views(audio: np.ndarray, hop_samples: int) -> list[np.ndarray]:
    if not 1 <= hop_samples <= WINDOW_SAMPLES:
        raise ValueError("baxy_wake_hard_negative_hop_invalid")
    maximum = max(0, len(audio) - WINDOW_SAMPLES)
    return [
        audio[start : start + WINDOW_SAMPLES]
        for start in range(0, maximum + 1, hop_samples)
    ]


def gpu_logmel(torch: Any, audio: np.ndarray, filters: Any, window: Any) -> Any:
    values = torch.from_numpy(audio).cuda(non_blocking=True)
    spectrum = torch.stft(
        values,
        n_fft=400,
        hop_length=160,
        win_length=400,
        window=window,
        center=True,
        return_complex=True,
    )
    magnitudes = spectrum[..., :-1].abs().square()
    mel_spec = filters @ magnitudes
    log_spec = torch.clamp(mel_spec, min=1e-10).log10()
    log_spec = torch.maximum(
        log_spec, log_spec.amax(dim=(1, 2), keepdim=True) - 8.0
    )
    return ((log_spec + 4.0) / 4.0).transpose(1, 2).float()


def selected_records(
    corpus: dict[str, Any], report: dict[str, Any]
) -> list[dict[str, Any]]:
    false_hashes = report.get("falseActivationAudioSha256")
    records = corpus.get("records")
    if (
        report.get("schema") != REPORT_SCHEMA
        or not isinstance(false_hashes, list)
        or not false_hashes
        or len(false_hashes) != len(set(false_hashes))
        or corpus.get("schema") != CORPUS_SCHEMA
        or not isinstance(records, list)
    ):
        raise ValueError("baxy_wake_hard_negative_boundary_invalid")
    wanted = set(false_hashes)
    chosen = [
        record
        for record in records
        if isinstance(record, dict) and record.get("sha256") in wanted
    ]
    if len(chosen) != len(wanted):
        raise ValueError("baxy_wake_hard_negative_hash_coverage_invalid")
    return chosen


def extract(args: argparse.Namespace) -> dict[str, Any]:
    import torch

    if not torch.cuda.is_available():
        raise ValueError("baxy_wake_hard_negative_cuda_unavailable")
    if args.top_k < 1 or args.batch_size < 1 or args.group_size < 1:
        raise ValueError("baxy_wake_hard_negative_schedule_invalid")
    output = args.output.resolve()
    partial = output.with_name(output.name + ".partial")
    if output.exists() or partial.exists():
        raise ValueError("baxy_wake_hard_negative_output_exists")
    corpus_path = args.corpus_manifest.resolve(strict=True)
    report_path = args.false_report.resolve(strict=True)
    cascade_path = args.cascade_manifest.resolve(strict=True)
    checkpoint_path = args.verifier_checkpoint.resolve(strict=True)
    ffmpeg = args.ffmpeg.resolve(strict=True)
    corpus = read_object(corpus_path)
    report = read_object(report_path)
    cascade = read_object(cascade_path)
    if (
        report.get("sources", {}).get("corpusManifestSha256")
        != sha256(corpus_path)
        or report.get("sources", {}).get("cascadeManifestSha256")
        != sha256(cascade_path)
        or cascade.get("schema") not in CASCADE_SCHEMAS
    ):
        raise ValueError("baxy_wake_hard_negative_source_mismatch")
    records = selected_records(corpus, report)
    root = (corpus_path.parent / str(corpus.get("corpus_root") or "")).resolve(
        strict=True
    )
    mel_path = (cascade_path.parent / str(cascade.get("melFilters"))).resolve(
        strict=True
    )
    if sha256(mel_path) != cascade.get("melFiltersSha256"):
        raise ValueError("baxy_wake_hard_negative_mel_hash_mismatch")
    trainer = load_component(
        Path(__file__).with_name("train_baxy_logmel_closed_set_verifier_v1.py"),
        "_baxy_wake_hard_negative_verifier_v1",
    )
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    model = trainer.build_model(
        channels=int(checkpoint["channels"]),
        blocks=int(checkpoint["blocks"]),
        dropout=float(checkpoint["dropout"]),
    )
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    model.eval().cuda()
    filters = torch.from_numpy(np.load(mel_path).astype(np.float32)).cuda()
    window = torch.hann_window(400, device="cuda")
    hop_samples = int(cascade.get("hopSamples") or 0)
    partial.mkdir(parents=True)
    maximum_records = len(records) * args.top_k
    features = np.lib.format.open_memmap(
        partial / "logmel.f16.npy",
        mode="w+",
        dtype=np.float16,
        shape=(maximum_records * FRAMES, MEL_BINS),
    )
    output_records: list[dict[str, Any]] = []
    cursor = 0
    for group_start in range(0, len(records), args.group_size):
        group = records[group_start : group_start + args.group_size]
        decoded: list[list[np.ndarray]] = []
        for record in group:
            path = (root / str(record.get("relative_path") or "")).resolve(
                strict=True
            )
            if sha256(path) != record.get("sha256"):
                raise ValueError("baxy_wake_hard_negative_audio_hash_mismatch")
            audio = decode_flac(ffmpeg, path)
            if len(audio) != int(record.get("frames") or -1):
                raise ValueError("baxy_wake_hard_negative_frame_count_mismatch")
            decoded.append(window_views(stream_audio(audio), hop_samples))
        selections: list[list[tuple[float, int, np.ndarray]]] = [
            [] for _ in group
        ]
        locators = [
            (record_index, window_index, value)
            for record_index, windows in enumerate(decoded)
            for window_index, value in enumerate(windows)
        ]
        for start in range(0, len(locators), args.batch_size):
            batch = locators[start : start + args.batch_size]
            audio_batch = np.stack([value for _, _, value in batch])
            with torch.inference_mode():
                logmel = gpu_logmel(torch, audio_batch, filters, window)
                scores = model(logmel)[:, 0]
            cpu_features = logmel.half().cpu().numpy()
            cpu_scores = scores.float().cpu().numpy()
            for row, (record_index, window_index, _) in enumerate(batch):
                selections[record_index].append(
                    (
                        float(cpu_scores[row]),
                        window_index,
                        cpu_features[row],
                    )
                )
        for record, choices in zip(group, selections):
            if len(choices) < args.top_k:
                raise ValueError("baxy_wake_hard_negative_windows_insufficient")
            source_id = f"openslr:{record['utterance_id']}"
            persona_id = f"openslr_speaker_{int(record['speaker_id']):06d}"
            for rank, (score, window_index, value) in enumerate(
                sorted(choices, key=lambda item: item[0], reverse=True)[: args.top_k]
            ):
                start = cursor * FRAMES
                end = start + FRAMES
                features[start:end] = value
                output_records.append(
                    {
                        "label": "adversarial_negative",
                        "persona_id": persona_id,
                        "record_id": source_id,
                        "audio_sha256": record["sha256"],
                        "window_index": window_index,
                        "baseline_rank": rank,
                        "baseline_verifier_score": score,
                        "feature_start": start,
                        "feature_end": end,
                        "feature_frames": FRAMES,
                    }
                )
                cursor += 1
        completed = min(group_start + len(group), len(records))
        print(
            f"BAXY_WAKE_HARD_NEGATIVE|{completed}/{len(records)}|"
            f"windows={len(output_records)}",
            flush=True,
        )
    if cursor != maximum_records:
        raise ValueError("baxy_wake_hard_negative_record_count_invalid")
    features.flush()
    del features
    offsets = np.arange(cursor + 1, dtype=np.int64) * FRAMES
    np.save(partial / "offsets.i64.npy", offsets)
    feature_path = partial / "logmel.f16.npy"
    offset_path = partial / "offsets.i64.npy"
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "opened_openslr_false_alarm_topk_logmel_development",
        "sources": {
            "corpus_manifest_sha256": sha256(corpus_path),
            "false_report_sha256": sha256(report_path),
            "cascade_manifest_sha256": sha256(cascade_path),
            "verifier_checkpoint_sha256": sha256(checkpoint_path),
            "mel_filters_sha256": sha256(mel_path),
            "ffmpeg_sha256": sha256(ffmpeg),
        },
        "contract": {
            "top_k_per_false_utterance": args.top_k,
            "hop_samples": hop_samples,
            "frames": FRAMES,
            "mel_bins": MEL_BINS,
            "selection": "highest_baseline_verifier_logit",
            "speaker_identity": "pseudonymous_integer_only",
            "gpu": torch.cuda.get_device_name(0),
        },
        "counts": {
            "source_records": len(records),
            "records": len(output_records),
            "frames": cursor * FRAMES,
        },
        "files": {
            "logmel": feature_path.name,
            "logmel_sha256": sha256(feature_path),
            "offsets": offset_path.name,
            "offsets_sha256": sha256(offset_path),
        },
        "records": output_records,
        "candidate_development_use": True,
        "fresh_holdout_claim_supported": False,
        "development_only": True,
        "human_development_audio_accessed": False,
        "blind_human_audio_accessed": False,
        "transcripts_or_filenames_retained": False,
        "effects_executed": 0,
    }
    (partial / "features.manifest.v1.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    partial.replace(output)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--false-report", type=Path, required=True)
    parser.add_argument("--cascade-manifest", type=Path, required=True)
    parser.add_argument("--verifier-checkpoint", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--group-size", type=int, default=16)
    return parser.parse_args()


def main() -> int:
    report = extract(parse_args())
    print(
        json.dumps(
            {
                "sourceRecords": report["counts"]["source_records"],
                "records": report["counts"]["records"],
                "gpu": report["contract"]["gpu"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
