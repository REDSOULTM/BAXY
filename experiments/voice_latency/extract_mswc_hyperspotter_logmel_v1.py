"""Extract official HyperSpotter log-mel features from bounded MSWC subsets."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import numpy as np


SAMPLE_RATE = 16_000
HOP_LENGTH = 160


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"mswc_hyperspotter_logmel_json_invalid:{path}")
    return value


def stable_digest(seed: int, *values: str) -> str:
    return hashlib.sha256(
        "\x1f".join((str(seed), *values)).encode("utf-8")
    ).hexdigest()


def select_records(
    records: list[dict[str, object]],
    *,
    partitions: set[str],
    examples_per_class: int,
    seed: int,
) -> list[dict[str, object]]:
    by_class: dict[str, list[dict[str, object]]] = {}
    for record in records:
        if str(record.get("partition")) in partitions:
            by_class.setdefault(str(record["class_name"]), []).append(record)
    selected = []
    for class_name in sorted(by_class):
        ordered = sorted(
            by_class[class_name],
            key=lambda record: (
                stable_digest(seed, class_name, str(record["source_link"])),
                str(record["source_link"]),
            ),
        )
        if len(ordered) < examples_per_class:
            raise ValueError(f"mswc_hyperspotter_logmel_examples_missing:{class_name}")
        selected.extend(dict(record) for record in ordered[:examples_per_class])
    if not selected:
        raise ValueError("mswc_hyperspotter_logmel_selection_empty")
    return sorted(
        selected,
        key=lambda record: (
            str(record["class_name"]),
            str(record["partition"]),
            str(record["source_link"]),
        ),
    )


def decode_opus(path: Path, av: object) -> np.ndarray:
    chunks = []
    with av.open(str(path)) as container:
        if not container.streams.audio:
            raise ValueError(f"mswc_hyperspotter_logmel_audio_stream_missing:{path}")
        resampler = av.AudioResampler(format="fltp", layout="mono", rate=SAMPLE_RATE)
        for frame in container.decode(container.streams.audio[0]):
            for output in resampler.resample(frame):
                chunks.append(output.to_ndarray().reshape(-1).astype(np.float32))
        for output in resampler.resample(None):
            chunks.append(output.to_ndarray().reshape(-1).astype(np.float32))
    if not chunks:
        raise ValueError(f"mswc_hyperspotter_logmel_audio_empty:{path}")
    audio = np.ascontiguousarray(np.concatenate(chunks), dtype=np.float32)
    if not np.isfinite(audio).all():
        raise ValueError(f"mswc_hyperspotter_logmel_audio_invalid:{path}")
    return audio


def extract(
    *,
    corpus_manifest_path: Path,
    corpus_root: Path,
    hyperspotter_root: Path,
    av_site_packages: Path,
    output_root: Path,
    partitions: set[str],
    examples_per_class: int,
    seed: int,
) -> dict[str, object]:
    if output_root.exists() or examples_per_class < 1 or not partitions:
        raise ValueError("mswc_hyperspotter_logmel_schedule_invalid")
    corpus_manifest_path = corpus_manifest_path.resolve(strict=True)
    corpus_root = corpus_root.resolve(strict=True)
    hyperspotter_root = hyperspotter_root.resolve(strict=True)
    av_site_packages = av_site_packages.resolve(strict=True)
    output_root = output_root.resolve()
    partial_root = output_root.with_name(output_root.name + ".partial")
    if partial_root.exists():
        raise FileExistsError(f"mswc_hyperspotter_logmel_partial_exists:{partial_root}")
    corpus = read_object(corpus_manifest_path)
    records_raw = corpus.get("records")
    if (
        corpus.get("schema")
        not in {
            "baxy.mswc-spanish-qbye-corpus.v1",
            "baxy.mswc-spanish-qbye-sequence-research-corpus.v3",
        }
        or corpus.get("official_test_audio_accessed") is not False
        or corpus.get("blind_human_audio_accessed") is not False
        or not isinstance(records_raw, list)
    ):
        raise ValueError("mswc_hyperspotter_logmel_corpus_boundary_invalid")
    records = []
    for raw_record in records_raw:
        if not isinstance(raw_record, dict):
            raise ValueError("mswc_hyperspotter_logmel_record_invalid")
        records.append(raw_record)
    selected = select_records(
        records,
        partitions=partitions,
        examples_per_class=examples_per_class,
        seed=seed,
    )
    paths = []
    for record in selected:
        relative = Path(str(record["relative_path"]))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("mswc_hyperspotter_logmel_relative_path_invalid")
        path = (corpus_root / relative).resolve(strict=True)
        path.relative_to(corpus_root)
        if (
            path.stat().st_size != int(record["audio_bytes"])
            or sha256(path) != record["audio_sha256"]
        ):
            raise ValueError(f"mswc_hyperspotter_logmel_audio_hash_mismatch:{path}")
        paths.append(path)
    sys.path.insert(0, str(av_site_packages))
    try:
        import av
    finally:
        sys.path.remove(str(av_site_packages))
    sys.path.insert(0, str(hyperspotter_root))
    import torch
    from src.processing import features_factory
    from src.utils import ConfigDict

    config = ConfigDict(
        {
            "features": {
                "stft_hop_length": 0.01,
                "stft_window_length": 0.025,
                "num_filterbank": 80,
                "sample_rate": SAMPLE_RATE,
                "n_fft": 400,
            },
            "augmentations": {"use_augmentations": False},
        }
    )
    extractor = features_factory(config, eval=True)
    started = time.perf_counter()
    sample_lengths = np.empty(len(paths), dtype=np.int64)
    for index, path in enumerate(paths):
        sample_lengths[index] = len(decode_opus(path, av))
    frame_lengths = sample_lengths // HOP_LENGTH
    if np.any(frame_lengths < 1):
        raise ValueError("mswc_hyperspotter_logmel_frame_length_invalid")
    offsets = np.zeros(len(selected) + 1, dtype=np.int64)
    offsets[1:] = np.cumsum(frame_lengths)
    partial_root.mkdir(parents=True)
    offset_path = partial_root / "offsets.i64.npy"
    feature_path = partial_root / "logmel.f16.npy"
    np.save(offset_path, offsets)
    output = np.lib.format.open_memmap(
        feature_path,
        mode="w+",
        dtype=np.float16,
        shape=(int(offsets[-1]), 80),
    )
    metadata_records = []
    with torch.inference_mode():
        for index, (record, path) in enumerate(zip(selected, paths, strict=True)):
            audio = decode_opus(path, av)
            features = extractor(torch.from_numpy(audio)[None, :], SAMPLE_RATE).cpu().numpy()
            if features.shape != (int(frame_lengths[index]), 80):
                raise ValueError(
                    f"mswc_hyperspotter_logmel_shape_mismatch:{features.shape}:{frame_lengths[index]}"
                )
            start = int(offsets[index])
            end = int(offsets[index + 1])
            output[start:end] = features.astype(np.float16)
            metadata_records.append(
                {
                    **record,
                    "feature_start": start,
                    "feature_end": end,
                    "feature_frames": end - start,
                }
            )
            if (index + 1) % 1000 == 0 or index + 1 == len(paths):
                print(f"HYPERSPOTTER_LOGMEL|{index + 1}/{len(paths)}", flush=True)
    output.flush()
    del output
    upstream_commit = subprocess.run(
        ["git", "-C", str(hyperspotter_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        encoding="utf-8",
    ).stdout.strip()
    report: dict[str, object] = {
        "schema": "baxy.mswc-hyperspotter-logmel.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "bounded_mswc_features_for_official_hyperspotter_adaptation",
        "sources": {
            "corpus_manifest_sha256": sha256(corpus_manifest_path),
            "hyperspotter_upstream_commit": upstream_commit,
        },
        "contract": {
            "seed": seed,
            "included_partitions": sorted(partitions),
            "examples_per_class": examples_per_class,
            "sample_rate": SAMPLE_RATE,
            "feature": "official_whisper_log_mel_spectrogram_80_bins",
            "feature_dtype": "float16",
            "audio_normalization": "none_beyond_official_feature_extractor",
            "memory_contract": "decode_length_pass_then_sequential_feature_memmap",
        },
        "counts": {
            "records": len(metadata_records),
            "classes": len({record["class_name"] for record in metadata_records}),
            "feature_frames": int(offsets[-1]),
            "partitions": {
                partition: sum(record["partition"] == partition for record in metadata_records)
                for partition in sorted(partitions)
            },
        },
        "files": {
            "logmel": feature_path.name,
            "logmel_sha256": sha256(feature_path),
            "offsets": offset_path.name,
            "offsets_sha256": sha256(offset_path),
        },
        "records": metadata_records,
        "runtime_seconds": time.perf_counter() - started,
        "official_test_audio_accessed": False,
        "blind_human_audio_accessed": False,
        "effects_executed": 0,
    }
    (partial_root / "features.manifest.v1.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(partial_root, output_root)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--corpus-root", type=Path, required=True)
    parser.add_argument("--hyperspotter-root", type=Path, required=True)
    parser.add_argument("--av-site-packages", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--partition", action="append", dest="partitions", required=True)
    parser.add_argument("--examples-per-class", type=int, default=8)
    parser.add_argument("--seed", type=int, default=8501)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = extract(
        corpus_manifest_path=args.corpus_manifest,
        corpus_root=args.corpus_root,
        hyperspotter_root=args.hyperspotter_root,
        av_site_packages=args.av_site_packages,
        output_root=args.output_root,
        partitions=set(args.partitions),
        examples_per_class=args.examples_per_class,
        seed=args.seed,
    )
    print(json.dumps(report["counts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
