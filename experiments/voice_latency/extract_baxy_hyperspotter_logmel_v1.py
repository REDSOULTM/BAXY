"""Extract the fixed BAXY synthetic corpus into HyperSpotter log-Mel frames.

The cache is a research asset outside the product runtime.  It preserves the
positive/adversarial labels and speaker-persona boundary needed for a
speaker-disjoint training campaign, while retaining no audio samples.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib
import json
from pathlib import Path
import subprocess
import sys
import time

import numpy as np


SAMPLE_RATE = 16_000
MEL_BINS = 80


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().lower()


def read_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("baxy_hyperspotter_logmel_json_invalid")
    return value


def upstream_commit(repository: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def selected_records(
    positive: dict[str, object], negative: dict[str, object]
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for expected_label, manifest in (
        ("positive", positive),
        ("adversarial_negative", negative),
    ):
        if (
            manifest.get("schema") != "baxy.voxcpm2-ipa-filtered-wake-corpus.v1"
            or manifest.get("class_label") != expected_label
            or not isinstance(manifest.get("records"), list)
        ):
            raise ValueError("baxy_hyperspotter_logmel_manifest_boundary_invalid")
        for source_index, raw in enumerate(manifest["records"]):
            if not isinstance(raw, dict) or raw.get("class_label") != expected_label:
                raise ValueError("baxy_hyperspotter_logmel_record_invalid")
            wav = raw.get("wav")
            if (
                not isinstance(wav, dict)
                or wav.get("sample_rate") != SAMPLE_RATE
                or wav.get("channels") != 1
                or not isinstance(wav.get("sha256"), str)
                or not isinstance(raw.get("output_file"), str)
                or not isinstance(raw.get("persona_id"), str)
                or not isinstance(raw.get("phrase_id"), str)
            ):
                raise ValueError("baxy_hyperspotter_logmel_audio_contract_invalid")
            result.append(
                {
                    "label": expected_label,
                    "source_index": source_index,
                    "relative_path": raw["output_file"],
                    "audio_sha256": str(wav["sha256"]).lower(),
                    "persona_id": raw["persona_id"],
                    "phrase_id": raw["phrase_id"],
                }
            )
    return result


def extract(
    *,
    positive_manifest_path: Path,
    negative_manifest_path: Path,
    hyperspotter_root: Path,
    hyperspotter_site_packages: Path,
    output_directory: Path,
) -> dict[str, object]:
    positive_manifest_path = positive_manifest_path.resolve(strict=True)
    negative_manifest_path = negative_manifest_path.resolve(strict=True)
    hyperspotter_root = hyperspotter_root.resolve(strict=True)
    hyperspotter_site_packages = hyperspotter_site_packages.resolve(strict=True)
    output_directory = output_directory.resolve()
    partial = output_directory.with_name(output_directory.name + ".partial")
    if output_directory.exists() or partial.exists():
        raise FileExistsError("baxy_hyperspotter_logmel_output_exists")

    manifests = {
        "positive": read_object(positive_manifest_path),
        "negative": read_object(negative_manifest_path),
    }
    records = selected_records(manifests["positive"], manifests["negative"])
    counts = {
        label: sum(record["label"] == label for record in records)
        for label in ("positive", "adversarial_negative")
    }
    if counts != {"positive": 2695, "adversarial_negative": 1975}:
        raise ValueError(f"baxy_hyperspotter_logmel_counts_invalid:{counts}")
    roots = {
        "positive": positive_manifest_path.parent,
        "adversarial_negative": negative_manifest_path.parent,
    }
    paths: list[Path] = []
    for record in records:
        path = (roots[str(record["label"])] / str(record["relative_path"])).resolve(
            strict=True
        )
        if sha256(path) != record["audio_sha256"]:
            raise ValueError("baxy_hyperspotter_logmel_audio_hash_mismatch")
        paths.append(path)

    # Import the CUDA-environment torch first.  The upstream environment is
    # then exposed only to obtain the exact OpenAI Whisper feature function.
    import torch
    import soundfile as sf

    while str(hyperspotter_site_packages) in sys.path:
        sys.path.remove(str(hyperspotter_site_packages))
    sys.path.insert(0, str(hyperspotter_site_packages))
    importlib.invalidate_caches()
    import whisper

    if not hasattr(whisper, "log_mel_spectrogram"):
        raise ValueError("baxy_hyperspotter_logmel_whisper_invalid")

    started = time.perf_counter()
    arrays: list[np.ndarray] = []
    lengths = np.empty(len(paths), dtype=np.int64)
    for index, path in enumerate(paths):
        waveform, sample_rate = sf.read(
            str(path), dtype="float32", always_2d=True
        )
        if sample_rate != SAMPLE_RATE or waveform.shape[1] != 1:
            raise ValueError("baxy_hyperspotter_logmel_wave_invalid")
        tensor = torch.from_numpy(waveform[:, 0])
        feature = (
            whisper.log_mel_spectrogram(tensor, n_mels=MEL_BINS)
            .transpose(0, 1)
            .contiguous()
            .cpu()
            .numpy()
            .astype(np.float32)
        )
        if feature.ndim != 2 or feature.shape[1] != MEL_BINS or len(feature) < 1:
            raise ValueError("baxy_hyperspotter_logmel_feature_invalid")
        arrays.append(feature)
        lengths[index] = len(feature)
        if (index + 1) % 400 == 0 or index + 1 == len(paths):
            print(f"BAXY_HYPER_LOGMEL|{index + 1}/{len(paths)}", flush=True)

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
    cursor = 0
    for value in arrays:
        features[cursor : cursor + len(value)] = value.astype(np.float16)
        cursor += len(value)
    features.flush()
    del features, arrays
    np.save(offset_path, offsets)

    manifest_records = [
        {
            **record,
            "feature_start": int(offsets[index]),
            "feature_end": int(offsets[index + 1]),
            "feature_frames": int(lengths[index]),
        }
        for index, record in enumerate(records)
    ]
    report: dict[str, object] = {
        "schema": "baxy.baxy-hyperspotter-logmel.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "positive_manifest_sha256": sha256(positive_manifest_path),
            "negative_manifest_sha256": sha256(negative_manifest_path),
            "hyperspotter_upstream_commit": upstream_commit(hyperspotter_root),
        },
        "contract": {
            "sample_rate": SAMPLE_RATE,
            "mel_bins": MEL_BINS,
            "extractor": "openai_whisper.log_mel_spectrogram",
            "labels": ["positive", "adversarial_negative"],
            "speaker_group": "persona_id",
        },
        "counts": {**counts, "records": len(records), "frames": int(offsets[-1])},
        "files": {
            "logmel": feature_path.name,
            "logmel_sha256": sha256(feature_path),
            "offsets": offset_path.name,
            "offsets_sha256": sha256(offset_path),
        },
        "records": manifest_records,
        "runtime_seconds": time.perf_counter() - started,
        "human_development_audio_accessed": False,
        "blind_human_audio_accessed": False,
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
    parser.add_argument("--positive-manifest", type=Path, required=True)
    parser.add_argument("--negative-manifest", type=Path, required=True)
    parser.add_argument("--hyperspotter-root", type=Path, required=True)
    parser.add_argument("--hyperspotter-site-packages", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = extract(
        positive_manifest_path=arguments.positive_manifest,
        negative_manifest_path=arguments.negative_manifest,
        hyperspotter_root=arguments.hyperspotter_root,
        hyperspotter_site_packages=arguments.hyperspotter_site_packages,
        output_directory=arguments.output_directory,
    )
    print(json.dumps(report["counts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
