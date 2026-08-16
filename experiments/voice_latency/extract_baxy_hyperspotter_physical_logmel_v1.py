"""Extract attested RAW room captures into HyperSpotter log-Mel features.

The physical capture intentionally retains only hashes, labels and acoustic
measurements.  This extractor joins each captured source hash back to the
speaker/phrase metadata in the versioned synthetic manifests, then writes a
feature cache outside the product runtime.  No blind-human partition is read.
"""

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
MEL_BINS = 80
SOURCE_SCHEMA = "baxy.voxcpm2-ipa-filtered-wake-corpus.v1"
PHYSICAL_SCHEMA = "baxy.controlled-physical-wake-corpus.v1"


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"baxy_physical_logmel_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_BASE = load_component(
    "extract_baxy_hyperspotter_logmel_v1.py",
    "_baxy_hyperspotter_physical_logmel_base_v1",
)


def source_metadata(
    positive: dict[str, object], negative: dict[str, object]
) -> dict[str, dict[str, object]]:
    """Index the exact playback bytes without retaining source transcripts."""
    result: dict[str, dict[str, object]] = {}
    for expected_label, manifest in (
        ("positive", positive),
        ("adversarial_negative", negative),
    ):
        records = manifest.get("records")
        if (
            manifest.get("schema") != SOURCE_SCHEMA
            or manifest.get("class_label") != expected_label
            or not isinstance(records, list)
        ):
            raise ValueError("baxy_physical_logmel_source_boundary_invalid")
        for source_index, record in enumerate(records):
            if (
                not isinstance(record, dict)
                or record.get("class_label") != expected_label
                or not isinstance(record.get("persona_id"), str)
                or not isinstance(record.get("phrase_id"), str)
                or not isinstance(record.get("wav"), dict)
                or record["wav"].get("sample_rate") != SAMPLE_RATE
                or record["wav"].get("channels") != 1
                or not isinstance(record["wav"].get("sha256"), str)
            ):
                raise ValueError("baxy_physical_logmel_source_record_invalid")
            audio_sha256 = str(record["wav"]["sha256"]).lower()
            if audio_sha256 in result:
                raise ValueError("baxy_physical_logmel_source_hash_collision")
            result[audio_sha256] = {
                "label": expected_label,
                "source_index": source_index,
                "source_audio_sha256": audio_sha256,
                "persona_id": record["persona_id"],
                "phrase_id": record["phrase_id"],
            }
    return result


def physical_records(
    physical: dict[str, object],
    metadata: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    records = physical.get("records")
    counts = physical.get("counts")
    physical_path = physical.get("physicalPath")
    if (
        physical.get("schema") != PHYSICAL_SCHEMA
        or physical.get("blindHumanPartitionAccessed") is not False
        or physical.get("developmentOnly") is not True
        or not isinstance(records, list)
        or not isinstance(counts, dict)
        or not isinstance(physical_path, dict)
        or physical_path.get("captureTransport") != "wasapi_raw_iaudioclient2"
    ):
        raise ValueError("baxy_physical_logmel_capture_boundary_invalid")

    result: list[dict[str, object]] = []
    observed = {"positive": 0, "negative": 0}
    for record in records:
        if (
            not isinstance(record, dict)
            or not isinstance(record.get("recordId"), str)
            or not isinstance(record.get("sourceSha256"), str)
            or not isinstance(record.get("output"), str)
            or not isinstance(record.get("outputSha256"), str)
        ):
            raise ValueError("baxy_physical_logmel_capture_record_invalid")
        record_id = str(record["recordId"])
        capture_label = record_id.split("/", 1)[0]
        if capture_label not in observed:
            raise ValueError("baxy_physical_logmel_capture_label_invalid")
        expected_label = (
            "positive" if capture_label == "positive" else "adversarial_negative"
        )
        source_sha256 = str(record["sourceSha256"]).lower()
        source = metadata.get(source_sha256)
        if source is None:
            raise ValueError("baxy_physical_logmel_source_hash_unmapped")
        if source["label"] != expected_label:
            raise ValueError("baxy_physical_logmel_cross_label_invalid")
        observed[capture_label] += 1
        result.append(
            {
                **source,
                "record_id": record_id,
                "relative_path": record["output"],
                "audio_sha256": str(record["outputSha256"]).lower(),
                "captured_snr_db": record.get("capturedSnrDb"),
                "path_correlation": record.get("pathCorrelation"),
            }
        )
    expected_counts = {
        label: int(counts.get(label, -1)) for label in ("positive", "negative")
    }
    if observed != expected_counts or sum(observed.values()) != len(records):
        raise ValueError("baxy_physical_logmel_capture_counts_invalid")
    return result


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
        raise FileExistsError("baxy_physical_logmel_output_exists")

    physical = _BASE.read_object(physical_manifest_path)
    positive = _BASE.read_object(positive_manifest_path)
    negative = _BASE.read_object(negative_manifest_path)
    metadata = source_metadata(positive, negative)
    records = physical_records(physical, metadata)
    paths: list[Path] = []
    for record in records:
        path = (
            physical_manifest_path.parent / str(record["relative_path"])
        ).resolve(strict=True)
        if _BASE.sha256(path) != record["audio_sha256"]:
            raise ValueError("baxy_physical_logmel_audio_hash_mismatch")
        paths.append(path)

    import torch
    import soundfile as sf

    while str(hyperspotter_site_packages) in sys.path:
        sys.path.remove(str(hyperspotter_site_packages))
    sys.path.insert(0, str(hyperspotter_site_packages))
    importlib.invalidate_caches()
    import whisper

    if not hasattr(whisper, "log_mel_spectrogram"):
        raise ValueError("baxy_physical_logmel_whisper_invalid")

    started = time.perf_counter()
    arrays: list[np.ndarray] = []
    lengths = np.empty(len(paths), dtype=np.int64)
    for index, path in enumerate(paths):
        waveform, sample_rate = sf.read(str(path), dtype="float32", always_2d=True)
        if sample_rate != SAMPLE_RATE or waveform.shape[1] != 1:
            raise ValueError("baxy_physical_logmel_wave_invalid")
        feature = (
            whisper.log_mel_spectrogram(
                torch.from_numpy(waveform[:, 0]), n_mels=MEL_BINS
            )
            .transpose(0, 1)
            .contiguous()
            .cpu()
            .numpy()
            .astype(np.float32)
        )
        if feature.ndim != 2 or feature.shape[1] != MEL_BINS or len(feature) < 1:
            raise ValueError("baxy_physical_logmel_feature_invalid")
        arrays.append(feature)
        lengths[index] = len(feature)

    offsets = np.zeros(len(records) + 1, dtype=np.int64)
    offsets[1:] = np.cumsum(lengths)
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
            "feature_frames": int(lengths[index]),
        }
        for index, record in enumerate(records)
    ]
    label_counts = {
        label: sum(record["label"] == label for record in records)
        for label in ("positive", "adversarial_negative")
    }
    report: dict[str, object] = {
        "schema": "baxy.baxy-hyperspotter-physical-logmel.v1",
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
            "speaker_group": "persona_id",
            "capture_transport": "wasapi_raw_iaudioclient2",
            "filenames_or_transcripts_retained": False,
        },
        "counts": {
            **label_counts,
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
    (partial / "features.manifest.v1.json").write_text(
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
