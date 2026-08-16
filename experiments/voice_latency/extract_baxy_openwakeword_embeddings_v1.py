"""Extract closed-set openWakeWord embeddings for BAXY runtime windows.

This development-only extractor keeps speaker identity and hard-negative labels,
but never reads a blind-human partition.  Both clean synthetic clips and RAW
room captures are converted to the same exact three-second views used by the
rolling wake gate before the frozen openWakeWord feature backbone is applied.
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
WINDOW_SAMPLES = 48_000
SIDE_PADDING_SAMPLES = 16_000
HOP_SAMPLES = 4_000
EMBEDDING_FRAMES = 28
EMBEDDING_DIMENSION = 96
SOURCE_SCHEMA = "baxy.voxcpm2-ipa-filtered-wake-corpus.v1"
PHYSICAL_SCHEMA = "baxy.controlled-physical-wake-corpus.v1"
RUNTIME_SCHEMA = "baxy.baxy-hyperspotter-physical-runtime-logmel.v2"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().lower()


def read_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("baxy_openwakeword_json_invalid")
    return value


def git_commit(repository: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def continuous_runtime_windows(audio: np.ndarray) -> list[tuple[int, np.ndarray]]:
    values = np.asarray(audio, dtype=np.float32).reshape(-1)
    if values.size == 0 or not np.isfinite(values).all():
        raise ValueError("baxy_openwakeword_audio_invalid")
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


def pcm16(audio: np.ndarray) -> np.ndarray:
    values = np.asarray(audio, dtype=np.float32)
    if not np.isfinite(values).all():
        raise ValueError("baxy_openwakeword_pcm_invalid")
    return np.rint(np.clip(values, -1.0, 1.0) * 32767.0).astype(np.int16)


def synthetic_records(
    positive: dict[str, object], negative: dict[str, object]
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for label, manifest in (
        ("positive", positive),
        ("adversarial_negative", negative),
    ):
        records = manifest.get("records")
        if (
            manifest.get("schema") != SOURCE_SCHEMA
            or manifest.get("class_label") != label
            or not isinstance(records, list)
        ):
            raise ValueError("baxy_openwakeword_source_boundary_invalid")
        for source_index, record in enumerate(records):
            wav = record.get("wav") if isinstance(record, dict) else None
            if (
                not isinstance(record, dict)
                or record.get("class_label") != label
                or not isinstance(record.get("output_file"), str)
                or not isinstance(record.get("persona_id"), str)
                or not isinstance(record.get("phrase_id"), str)
                or not isinstance(wav, dict)
                or wav.get("sample_rate") != SAMPLE_RATE
                or wav.get("channels") != 1
                or not isinstance(wav.get("sha256"), str)
            ):
                raise ValueError("baxy_openwakeword_source_record_invalid")
            result.append(
                {
                    "domain": "synthetic_clean",
                    "label": label,
                    "source_index": source_index,
                    "persona_id": record["persona_id"],
                    "phrase_id": record["phrase_id"],
                    "relative_path": record["output_file"],
                    "audio_sha256": str(wav["sha256"]).lower(),
                }
            )
    return result


def physical_window_records(
    runtime: dict[str, object], *, physical_manifest_sha256: str
) -> list[dict[str, object]]:
    sources = runtime.get("sources")
    records = runtime.get("records")
    contract = runtime.get("contract")
    if (
        runtime.get("schema") != RUNTIME_SCHEMA
        or runtime.get("blind_human_audio_accessed") is not False
        or runtime.get("development_only") is not True
        or not isinstance(sources, dict)
        or sources.get("physical_manifest_sha256") != physical_manifest_sha256
        or not isinstance(contract, dict)
        or contract.get("runtime_window_samples") != WINDOW_SAMPLES
        or contract.get("side_padding_samples") != SIDE_PADDING_SAMPLES
        or contract.get("hop_samples") != HOP_SAMPLES
        or not isinstance(records, list)
    ):
        raise ValueError("baxy_openwakeword_runtime_boundary_invalid")
    result: list[dict[str, object]] = []
    for record in records:
        if (
            not isinstance(record, dict)
            or record.get("label") not in {"positive", "adversarial_negative"}
            or not isinstance(record.get("persona_id"), str)
            or not isinstance(record.get("phrase_id"), str)
            or not isinstance(record.get("relative_path"), str)
            or not isinstance(record.get("audio_sha256"), str)
            or not isinstance(record.get("runtime_window_index"), int)
            or not isinstance(record.get("runtime_window_start_samples"), int)
        ):
            raise ValueError("baxy_openwakeword_runtime_record_invalid")
        result.append(
            {
                "domain": "wasapi_raw_physical",
                "label": record["label"],
                "source_index": record.get("source_index"),
                "record_id": record.get("record_id"),
                "persona_id": record["persona_id"],
                "phrase_id": record["phrase_id"],
                "relative_path": record["relative_path"],
                "audio_sha256": str(record["audio_sha256"]).lower(),
                "runtime_window_index": record["runtime_window_index"],
                "runtime_window_start_samples": record[
                    "runtime_window_start_samples"
                ],
            }
        )
    return result


def validate_physical_manifest(manifest: dict[str, object]) -> None:
    path = manifest.get("physicalPath")
    if (
        manifest.get("schema") != PHYSICAL_SCHEMA
        or manifest.get("blindHumanPartitionAccessed") is not False
        or manifest.get("developmentOnly") is not True
        or not isinstance(path, dict)
        or path.get("captureTransport") != "wasapi_raw_iaudioclient2"
    ):
        raise ValueError("baxy_openwakeword_physical_boundary_invalid")


def extract(
    *,
    positive_manifest_path: Path,
    negative_manifest_path: Path,
    physical_manifest_path: Path,
    physical_runtime_manifest_path: Path,
    openwakeword_root: Path,
    melspectrogram_model_path: Path,
    embedding_model_path: Path,
    output_directory: Path,
    batch_size: int,
    ncpu: int,
) -> dict[str, object]:
    paths = [
        positive_manifest_path,
        negative_manifest_path,
        physical_manifest_path,
        physical_runtime_manifest_path,
        openwakeword_root,
        melspectrogram_model_path,
        embedding_model_path,
    ]
    (
        positive_manifest_path,
        negative_manifest_path,
        physical_manifest_path,
        physical_runtime_manifest_path,
        openwakeword_root,
        melspectrogram_model_path,
        embedding_model_path,
    ) = [path.resolve(strict=True) for path in paths]
    output_directory = output_directory.resolve()
    partial = output_directory.with_name(output_directory.name + ".partial")
    if output_directory.exists() or partial.exists():
        raise FileExistsError("baxy_openwakeword_output_exists")
    if batch_size < 1 or ncpu < 1:
        raise ValueError("baxy_openwakeword_batch_invalid")

    positive = read_object(positive_manifest_path)
    negative = read_object(negative_manifest_path)
    physical = read_object(physical_manifest_path)
    validate_physical_manifest(physical)
    runtime = read_object(physical_runtime_manifest_path)
    clean_records = synthetic_records(positive, negative)
    room_records = physical_window_records(
        runtime, physical_manifest_sha256=sha256(physical_manifest_path)
    )

    import soundfile as sf

    while str(openwakeword_root) in sys.path:
        sys.path.remove(str(openwakeword_root))
    sys.path.insert(0, str(openwakeword_root))
    importlib.invalidate_caches()
    from openwakeword.utils import AudioFeatures

    feature_backbone = AudioFeatures(
        melspec_model_path=str(melspectrogram_model_path),
        embedding_model_path=str(embedding_model_path),
        inference_framework="onnx",
        ncpu=ncpu,
        device="cpu",
    )
    if feature_backbone.get_embedding_shape(3.0) != (
        EMBEDDING_FRAMES,
        EMBEDDING_DIMENSION,
    ):
        raise ValueError("baxy_openwakeword_backbone_shape_invalid")

    started = time.perf_counter()
    windows: list[np.ndarray] = []
    records: list[dict[str, object]] = []
    roots = {
        "positive": positive_manifest_path.parent,
        "adversarial_negative": negative_manifest_path.parent,
    }
    for source in clean_records:
        path = (
            roots[str(source["label"])] / str(source["relative_path"])
        ).resolve(strict=True)
        if sha256(path) != source["audio_sha256"]:
            raise ValueError("baxy_openwakeword_synthetic_hash_mismatch")
        waveform, sample_rate = sf.read(str(path), dtype="float32", always_2d=True)
        if sample_rate != SAMPLE_RATE or waveform.shape[1] != 1:
            raise ValueError("baxy_openwakeword_synthetic_wave_invalid")
        for window_index, (window_start, window) in enumerate(
            continuous_runtime_windows(waveform[:, 0])
        ):
            windows.append(pcm16(window))
            records.append(
                {
                    **source,
                    "runtime_window_index": window_index,
                    "runtime_window_start_samples": window_start,
                }
            )

    physical_audio: dict[str, tuple[np.ndarray, list[tuple[int, np.ndarray]]]] = {}
    for source in room_records:
        relative_path = str(source["relative_path"])
        cached = physical_audio.get(relative_path)
        if cached is None:
            path = (physical_manifest_path.parent / relative_path).resolve(strict=True)
            if sha256(path) != source["audio_sha256"]:
                raise ValueError("baxy_openwakeword_physical_hash_mismatch")
            waveform, sample_rate = sf.read(
                str(path), dtype="float32", always_2d=True
            )
            if sample_rate != SAMPLE_RATE or waveform.shape[1] != 1:
                raise ValueError("baxy_openwakeword_physical_wave_invalid")
            cached = (waveform[:, 0], continuous_runtime_windows(waveform[:, 0]))
            physical_audio[relative_path] = cached
        selected_index = int(source["runtime_window_index"])
        if selected_index >= len(cached[1]):
            raise ValueError("baxy_openwakeword_physical_window_missing")
        selected_start, selected_window = cached[1][selected_index]
        if selected_start != source["runtime_window_start_samples"]:
            raise ValueError("baxy_openwakeword_physical_window_drift")
        windows.append(pcm16(selected_window))
        records.append(source)

    partial.mkdir(parents=True)
    feature_path = partial / "embeddings.f16.npy"
    embeddings = np.lib.format.open_memmap(
        feature_path,
        mode="w+",
        dtype=np.float16,
        shape=(len(windows), EMBEDDING_FRAMES, EMBEDDING_DIMENSION),
    )
    for start in range(0, len(windows), batch_size):
        end = min(start + batch_size, len(windows))
        batch = np.stack(windows[start:end])
        values = feature_backbone.embed_clips(
            batch, batch_size=batch_size * EMBEDDING_FRAMES, ncpu=ncpu
        )
        if values.shape != (
            end - start,
            EMBEDDING_FRAMES,
            EMBEDDING_DIMENSION,
        ) or not np.isfinite(values).all():
            raise ValueError("baxy_openwakeword_embedding_invalid")
        embeddings[start:end] = values.astype(np.float16)
        if end % 500 < batch_size or end == len(windows):
            print(f"BAXY_OWW_EMBED|{end}/{len(windows)}", flush=True)
    embeddings.flush()
    del embeddings, windows

    domain_counts = {
        domain: sum(record["domain"] == domain for record in records)
        for domain in ("synthetic_clean", "wasapi_raw_physical")
    }
    label_counts = {
        label: sum(record["label"] == label for record in records)
        for label in ("positive", "adversarial_negative")
    }
    report: dict[str, object] = {
        "schema": "baxy.openwakeword-runtime-embeddings.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "closed_set_wake_development_synthetic_plus_wasapi_raw",
        "sources": {
            "positive_manifest_sha256": sha256(positive_manifest_path),
            "negative_manifest_sha256": sha256(negative_manifest_path),
            "physical_manifest_sha256": sha256(physical_manifest_path),
            "physical_runtime_manifest_sha256": sha256(
                physical_runtime_manifest_path
            ),
            "openwakeword_commit": git_commit(openwakeword_root),
            "melspectrogram_model_sha256": sha256(melspectrogram_model_path),
            "embedding_model_sha256": sha256(embedding_model_path),
        },
        "contract": {
            "sample_rate": SAMPLE_RATE,
            "runtime_window_samples": WINDOW_SAMPLES,
            "side_padding_samples": SIDE_PADDING_SAMPLES,
            "hop_samples": HOP_SAMPLES,
            "embedding_frames": EMBEDDING_FRAMES,
            "embedding_dimension": EMBEDDING_DIMENSION,
            "feature_backbone": "openWakeWord_v0.5.1_onnx_speech_embedding",
            "feature_backbone_frozen": True,
            "inference_device": "cpu",
            "speaker_group": "persona_id",
        },
        "counts": {
            **domain_counts,
            **label_counts,
            "records": len(records),
        },
        "files": {
            "embeddings": feature_path.name,
            "embeddings_sha256": sha256(feature_path),
        },
        "records": records,
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
    parser.add_argument("--positive-manifest", type=Path, required=True)
    parser.add_argument("--negative-manifest", type=Path, required=True)
    parser.add_argument("--physical-manifest", type=Path, required=True)
    parser.add_argument("--physical-runtime-manifest", type=Path, required=True)
    parser.add_argument("--openwakeword-root", type=Path, required=True)
    parser.add_argument("--melspectrogram-model", type=Path, required=True)
    parser.add_argument("--embedding-model", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--ncpu", type=int, default=4)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = extract(
        positive_manifest_path=arguments.positive_manifest,
        negative_manifest_path=arguments.negative_manifest,
        physical_manifest_path=arguments.physical_manifest,
        physical_runtime_manifest_path=arguments.physical_runtime_manifest,
        openwakeword_root=arguments.openwakeword_root,
        melspectrogram_model_path=arguments.melspectrogram_model,
        embedding_model_path=arguments.embedding_model,
        output_directory=arguments.output_directory,
        batch_size=arguments.batch_size,
        ncpu=arguments.ncpu,
    )
    print(json.dumps(report["counts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
