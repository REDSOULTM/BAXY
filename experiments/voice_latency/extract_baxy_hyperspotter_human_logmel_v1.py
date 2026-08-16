"""Extract fixed human-development BAXY clips into HyperSpotter log-Mel."""

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


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"baxy_human_logmel_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_SYNTHETIC = load_component(
    "extract_baxy_hyperspotter_logmel_v1.py",
    "_baxy_human_logmel_synthetic_v1",
)


def human_records(manifest: dict[str, object]) -> list[dict[str, object]]:
    if (
        manifest.get("schema") != "baxy.wav2vec2-hidden-wake-training-features.v1"
        or manifest.get("blind_human_audio_accessed") is not False
        or not isinstance(manifest.get("records"), list)
    ):
        raise ValueError("baxy_human_logmel_manifest_boundary_invalid")
    result = []
    for record in manifest["records"]:
        if not isinstance(record, dict) or record.get("corpus") not in {
            "human_legacy",
            "human_expanded",
        }:
            continue
        if (
            not isinstance(record.get("relative_path"), str)
            or not isinstance(record.get("audio_sha256"), str)
            or not isinstance(record.get("group"), str)
            or not isinstance(record.get("label"), str)
        ):
            raise ValueError("baxy_human_logmel_record_invalid")
        result.append(
            {
                "corpus": record["corpus"],
                "label": record["label"],
                "group": record["group"],
                "relative_path": record["relative_path"],
                "audio_sha256": str(record["audio_sha256"]).lower(),
            }
        )
    counts = {
        corpus: sum(record["corpus"] == corpus for record in result)
        for corpus in ("human_legacy", "human_expanded")
    }
    if counts != {"human_legacy": 18, "human_expanded": 12}:
        raise ValueError(f"baxy_human_logmel_counts_invalid:{counts}")
    return result


def extract(
    *,
    source_manifest_path: Path,
    legacy_root: Path,
    expanded_root: Path,
    hyperspotter_site_packages: Path,
    output_directory: Path,
) -> dict[str, object]:
    source_manifest_path = source_manifest_path.resolve(strict=True)
    legacy_root = legacy_root.resolve(strict=True)
    expanded_root = expanded_root.resolve(strict=True)
    hyperspotter_site_packages = hyperspotter_site_packages.resolve(strict=True)
    output_directory = output_directory.resolve()
    partial = output_directory.with_name(output_directory.name + ".partial")
    if output_directory.exists() or partial.exists():
        raise FileExistsError("baxy_human_logmel_output_exists")
    source = _SYNTHETIC.read_object(source_manifest_path)
    records = human_records(source)
    roots = {"human_legacy": legacy_root, "human_expanded": expanded_root}
    paths = []
    for record in records:
        path = (
            roots[str(record["corpus"])] / str(record["relative_path"])
        ).resolve(strict=True)
        if _SYNTHETIC.sha256(path) != record["audio_sha256"]:
            raise ValueError("baxy_human_logmel_audio_hash_mismatch")
        paths.append(path)

    import torch
    import soundfile as sf

    while str(hyperspotter_site_packages) in sys.path:
        sys.path.remove(str(hyperspotter_site_packages))
    sys.path.insert(0, str(hyperspotter_site_packages))
    importlib.invalidate_caches()
    import whisper

    started = time.perf_counter()
    arrays = []
    for path in paths:
        waveform, sample_rate = sf.read(str(path), dtype="float32", always_2d=True)
        if sample_rate != 16_000:
            raise ValueError("baxy_human_logmel_sample_rate_invalid")
        feature = (
            whisper.log_mel_spectrogram(
                torch.from_numpy(waveform.mean(axis=1)), n_mels=80
            )
            .transpose(0, 1)
            .contiguous()
            .cpu()
            .numpy()
            .astype(np.float32)
        )
        arrays.append(feature)
    offsets = np.zeros(len(records) + 1, dtype=np.int64)
    offsets[1:] = np.cumsum([len(value) for value in arrays])
    partial.mkdir(parents=True)
    feature_path = partial / "logmel.f16.npy"
    offset_path = partial / "offsets.i64.npy"
    features = np.lib.format.open_memmap(
        feature_path,
        mode="w+",
        dtype=np.float16,
        shape=(int(offsets[-1]), 80),
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
            "feature_frames": int(offsets[index + 1] - offsets[index]),
        }
        for index, record in enumerate(records)
    ]
    report: dict[str, object] = {
        "schema": "baxy.baxy-hyperspotter-human-logmel.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "source_manifest_sha256": _SYNTHETIC.sha256(source_manifest_path),
        },
        "contract": {
            "sample_rate": 16_000,
            "mel_bins": 80,
            "extractor": "openai_whisper.log_mel_spectrogram",
            "adaptation_partition": "human_legacy",
            "independent_development_partition": "human_expanded",
            "audio_or_filenames_retained_in_report": False,
        },
        "counts": {
            "records": len(records),
            "human_legacy": 18,
            "human_expanded": 12,
            "positive": sum(record["label"] == "positive" for record in records),
            "negative": sum(record["label"] != "positive" for record in records),
            "frames": int(offsets[-1]),
        },
        "files": {
            "logmel": feature_path.name,
            "logmel_sha256": _SYNTHETIC.sha256(feature_path),
            "offsets": offset_path.name,
            "offsets_sha256": _SYNTHETIC.sha256(offset_path),
        },
        "records": output_records,
        "runtime_seconds": time.perf_counter() - started,
        "human_development_audio_accessed": True,
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
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--legacy-root", type=Path, required=True)
    parser.add_argument("--expanded-root", type=Path, required=True)
    parser.add_argument("--hyperspotter-site-packages", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = extract(
        source_manifest_path=arguments.source_manifest,
        legacy_root=arguments.legacy_root,
        expanded_root=arguments.expanded_root,
        hyperspotter_site_packages=arguments.hyperspotter_site_packages,
        output_directory=arguments.output_directory,
    )
    print(json.dumps(report["counts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
