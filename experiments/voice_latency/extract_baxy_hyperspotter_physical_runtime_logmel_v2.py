"""Extract exact three-second rolling runtime views from RAW room captures."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib
import importlib.util
import json
from pathlib import Path
import sys
import time

import numpy as np


SAMPLE_RATE = 16_000
WINDOW_SAMPLES = 48_000
SIDE_PADDING_SAMPLES = 16_000
HOP_SAMPLES = 4_000
MEL_BINS = 80


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"baxy_physical_runtime_logmel_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_PHYSICAL = load_component(
    "extract_baxy_hyperspotter_physical_logmel_v1.py",
    "_baxy_hyperspotter_physical_runtime_metadata_v2",
)
_BASE = _PHYSICAL._BASE


def continuous_runtime_windows(audio: np.ndarray) -> list[tuple[int, np.ndarray]]:
    values = np.asarray(audio, dtype=np.float32).reshape(-1)
    if values.size == 0 or not np.isfinite(values).all():
        raise ValueError("baxy_physical_runtime_logmel_audio_invalid")
    padded = np.pad(values, (SIDE_PADDING_SAMPLES, SIDE_PADDING_SAMPLES))
    if padded.size < WINDOW_SAMPLES:
        padded = np.pad(padded, (0, WINDOW_SAMPLES - padded.size))
    final_start = padded.size - WINDOW_SAMPLES
    starts = list(range(0, final_start + 1, HOP_SAMPLES))
    if starts[-1] != final_start:
        starts.append(final_start)
    return [
        (start, np.ascontiguousarray(padded[start : start + WINDOW_SAMPLES]))
        for start in starts
    ]


def extract(
    *,
    physical_manifest_path: Path,
    positive_manifest_path: Path,
    negative_manifest_path: Path,
    hyperspotter_site_packages: Path,
    output_directory: Path,
) -> dict[str, object]:
    physical_manifest_path = physical_manifest_path.resolve(strict=True)
    positive_manifest_path = positive_manifest_path.resolve(strict=True)
    negative_manifest_path = negative_manifest_path.resolve(strict=True)
    hyperspotter_site_packages = hyperspotter_site_packages.resolve(strict=True)
    output_directory = output_directory.resolve()
    partial = output_directory.with_name(output_directory.name + ".partial")
    if output_directory.exists() or partial.exists():
        raise FileExistsError("baxy_physical_runtime_logmel_output_exists")

    physical = _BASE.read_object(physical_manifest_path)
    positive = _BASE.read_object(positive_manifest_path)
    negative = _BASE.read_object(negative_manifest_path)
    metadata = _PHYSICAL.source_metadata(positive, negative)
    source_records = _PHYSICAL.physical_records(physical, metadata)

    import torch
    import soundfile as sf

    while str(hyperspotter_site_packages) in sys.path:
        sys.path.remove(str(hyperspotter_site_packages))
    sys.path.insert(0, str(hyperspotter_site_packages))
    importlib.invalidate_caches()
    import whisper

    started = time.perf_counter()
    arrays: list[np.ndarray] = []
    records: list[dict[str, object]] = []
    for source_record in source_records:
        path = (
            physical_manifest_path.parent / str(source_record["relative_path"])
        ).resolve(strict=True)
        if _BASE.sha256(path) != source_record["audio_sha256"]:
            raise ValueError("baxy_physical_runtime_logmel_audio_hash_mismatch")
        waveform, sample_rate = sf.read(str(path), dtype="float32", always_2d=True)
        if sample_rate != SAMPLE_RATE or waveform.shape[1] != 1:
            raise ValueError("baxy_physical_runtime_logmel_wave_invalid")
        windows = continuous_runtime_windows(waveform[:, 0])
        for window_index, (window_start, window) in enumerate(windows):
            feature = (
                whisper.log_mel_spectrogram(torch.from_numpy(window), n_mels=MEL_BINS)
                .transpose(0, 1)
                .contiguous()
                .cpu()
                .numpy()
                .astype(np.float32)
            )
            if feature.shape != (300, MEL_BINS):
                raise ValueError("baxy_physical_runtime_logmel_feature_invalid")
            arrays.append(feature)
            records.append(
                {
                    **source_record,
                    "runtime_window_index": window_index,
                    "runtime_window_start_samples": window_start,
                }
            )

    offsets = np.arange(len(records) + 1, dtype=np.int64) * 300
    partial.mkdir(parents=True)
    feature_path = partial / "logmel.f16.npy"
    offset_path = partial / "offsets.i64.npy"
    features = np.lib.format.open_memmap(
        feature_path,
        mode="w+",
        dtype=np.float16,
        shape=(int(offsets[-1]), MEL_BINS),
    )
    for index, value in enumerate(arrays):
        features[offsets[index] : offsets[index + 1]] = value.astype(np.float16)
    features.flush()
    del features, arrays
    np.save(offset_path, offsets)
    output_records = [
        {
            **record,
            "feature_start": int(offsets[index]),
            "feature_end": int(offsets[index + 1]),
            "feature_frames": 300,
        }
        for index, record in enumerate(records)
    ]
    label_counts = {
        label: sum(record["label"] == label for record in records)
        for label in ("positive", "adversarial_negative")
    }
    report: dict[str, object] = {
        "schema": "baxy.baxy-hyperspotter-physical-runtime-logmel.v2",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "physical_manifest_sha256": _BASE.sha256(physical_manifest_path),
            "positive_manifest_sha256": _BASE.sha256(positive_manifest_path),
            "negative_manifest_sha256": _BASE.sha256(negative_manifest_path),
        },
        "contract": {
            "sample_rate": SAMPLE_RATE,
            "mel_bins": MEL_BINS,
            "extractor": "openai_whisper.log_mel_spectrogram",
            "runtime_window_samples": WINDOW_SAMPLES,
            "side_padding_samples": SIDE_PADDING_SAMPLES,
            "hop_samples": HOP_SAMPLES,
            "speaker_group": "persona_id",
            "capture_transport": "wasapi_raw_iaudioclient2",
            "filenames_or_transcripts_retained": False,
        },
        "counts": {
            **label_counts,
            "source_records": len(source_records),
            "records": len(records),
            "frames": int(offsets[-1]),
        },
        "files": {
            "logmel": feature_path.name,
            "logmel_sha256": _BASE.sha256(feature_path),
            "offsets": offset_path.name,
            "offsets_sha256": _BASE.sha256(offset_path),
        },
        "records": output_records,
        "runtime_seconds": time.perf_counter() - started,
        "human_development_audio_accessed": False,
        "blind_human_audio_accessed": False,
        "development_only": True,
        "effects_executed": 0,
    }
    (partial / "features.manifest.v2.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    partial.rename(output_directory)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--physical-manifest", type=Path, required=True)
    parser.add_argument("--positive-manifest", type=Path, required=True)
    parser.add_argument("--negative-manifest", type=Path, required=True)
    parser.add_argument("--hyperspotter-site-packages", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = extract(
        physical_manifest_path=arguments.physical_manifest,
        positive_manifest_path=arguments.positive_manifest,
        negative_manifest_path=arguments.negative_manifest,
        hyperspotter_site_packages=arguments.hyperspotter_site_packages,
        output_directory=arguments.output_directory,
    )
    print(json.dumps(report["counts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
