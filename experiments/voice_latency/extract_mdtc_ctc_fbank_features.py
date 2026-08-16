"""Extract deterministic 80-bin fbank features for a tiny phonetic CTC student."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import wave

import numpy as np


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from extract_human_ctc_aligned_livekit_features import (  # noqa: E402
    product_windows,
)
from train_mdtc_livekit_verifier_student import read_json, sha256  # noqa: E402


SAMPLE_RATE = 16_000
WINDOW_SAMPLES = 32_000
FEATURE_FRAMES = 198
FEATURE_DIMENSION = 80
AUGMENTATION_SUFFIXES = ("r0", "r1", "r2")


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as source:
        contract = (
            source.getnchannels(),
            source.getsampwidth(),
            source.getframerate(),
        )
        if contract != (1, 2, SAMPLE_RATE):
            raise ValueError(f"mdtc_ctc_wav_contract_mismatch:{path}:{contract}")
        audio = np.frombuffer(source.readframes(source.getnframes()), dtype="<i2")
    return audio.astype(np.float32) / 32768.0


def extract_fbank(audio: np.ndarray) -> np.ndarray:
    import torch
    from torchaudio.compliance import kaldi

    values = np.asarray(audio, dtype=np.float32).reshape(-1)
    if len(values) != WINDOW_SAMPLES or not np.isfinite(values).all():
        raise ValueError("mdtc_ctc_audio_window_invalid")
    features = kaldi.fbank(
        torch.from_numpy(values * 32768.0).unsqueeze(0),
        num_mel_bins=FEATURE_DIMENSION,
        frame_length=25,
        frame_shift=10,
        dither=0.0,
        energy_floor=0.0,
        sample_frequency=SAMPLE_RATE,
    ).numpy()
    if features.shape != (FEATURE_FRAMES, FEATURE_DIMENSION):
        raise ValueError(f"mdtc_ctc_fbank_shape_invalid:{features.shape}")
    return np.asarray(features, dtype=np.float32)


def augmented_synthetic_records(
    synthetic_directory: Path, assembly: dict[str, object], split: str
) -> list[dict[str, object]]:
    records = assembly.get("records")
    if not isinstance(records, dict):
        raise ValueError("mdtc_ctc_synthetic_records_missing")
    output = []
    for label_name, label in (("positive", 1), ("negative", 0)):
        key = f"{label_name}_{split}"
        values = records.get(key)
        if not isinstance(values, list):
            raise ValueError(f"mdtc_ctc_synthetic_split_missing:{key}")
        directory = synthetic_directory / key
        for record in values:
            if not isinstance(record, dict):
                raise ValueError("mdtc_ctc_synthetic_record_invalid")
            stem = Path(str(record.get("output_file"))).stem
            for suffix in AUGMENTATION_SUFFIXES:
                path = directory / f"{stem}_{suffix}.wav"
                if not path.is_file():
                    raise FileNotFoundError(f"mdtc_ctc_synthetic_audio_missing:{path}")
                output.append(
                    {
                        "source": "synthetic",
                        "split": split,
                        "label": label,
                        "path": path,
                        "record": {
                            "relative_path": path.relative_to(synthetic_directory).as_posix(),
                            "label": label,
                            "persona_id": record.get("persona_id"),
                            "phrase_id": record.get("phrase_id"),
                            "augmentation": suffix,
                        },
                    }
                )
    return output


def hard_negative_records(
    hard_directory: Path, manifest: dict[str, object], split: str
) -> list[dict[str, object]]:
    values = manifest.get("records")
    if not isinstance(values, list):
        raise ValueError("mdtc_ctc_hard_records_missing")
    output = []
    for record in values:
        if not isinstance(record, dict) or record.get("split") != split:
            continue
        relative_path = str(record.get("output_relative_path"))
        path = hard_directory / relative_path
        if sha256(path.resolve(strict=True)) != record.get("output_sha256"):
            raise ValueError(f"mdtc_ctc_hard_audio_hash_mismatch:{relative_path}")
        output.append(
            {
                "source": "openslr_hard_negative",
                "split": split,
                "label": 0,
                "path": path,
                "record": {
                    "relative_path": relative_path,
                    "label": 0,
                    "source_speaker_id": record.get("source_speaker_id"),
                    "source_utterance_id": record.get("source_utterance_id"),
                },
            }
        )
    return output


def human_records(
    human_manifest: dict[str, object], human_manifest_path: Path
) -> list[dict[str, object]]:
    values = human_manifest.get("records")
    corpus_path = Path(str(human_manifest.get("corpus_manifest"))).resolve(strict=True)
    if sha256(corpus_path) != human_manifest.get("corpus_manifest_sha256"):
        raise ValueError("mdtc_ctc_human_corpus_hash_mismatch")
    if not isinstance(values, list):
        raise ValueError("mdtc_ctc_human_records_missing")
    corpus_root = corpus_path.parent
    cached_windows: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    output = []
    for record in values:
        if not isinstance(record, dict):
            raise ValueError("mdtc_ctc_human_record_invalid")
        relative_path = str(record.get("output_relative_path"))
        if relative_path not in cached_windows:
            cached_windows[relative_path] = product_windows(
                read_wav(corpus_root / relative_path)
            )
        windows, ends = cached_windows[relative_path]
        target_end = float(record.get("window_end_seconds"))
        matches = np.flatnonzero(np.isclose(ends, target_end, atol=1e-9, rtol=0.0))
        if len(matches) != 1:
            raise ValueError(f"mdtc_ctc_human_window_missing:{relative_path}:{target_end}")
        index = int(matches[0])
        output.append(
            {
                "source": "human_development",
                "split": "human",
                "label": int(record.get("teacher_aligned_label", 0)),
                "audio": windows[index],
                "record": {
                    "relative_path": relative_path,
                    "label": int(record.get("teacher_aligned_label", 0)),
                    "speaker_group": record.get("speaker_group"),
                    "clip_label": record.get("clip_label"),
                    "window_end_seconds": target_end,
                },
            }
        )
    return output


def write_partition(
    output_directory: Path,
    name: str,
    records: list[dict[str, object]],
) -> dict[str, object]:
    feature_path = output_directory / f"{name}_features.npy"
    label_path = output_directory / f"{name}_labels.npy"
    features = np.lib.format.open_memmap(
        feature_path,
        mode="w+",
        dtype=np.float16,
        shape=(len(records), FEATURE_FRAMES, FEATURE_DIMENSION),
    )
    labels = np.empty(len(records), dtype=np.uint8)
    report_records = []
    for index, item in enumerate(records):
        audio_value = item.get("audio")
        audio = (
            np.asarray(audio_value, dtype=np.float32)
            if audio_value is not None
            else read_wav(Path(str(item["path"])))
        )
        features[index] = extract_fbank(audio).astype(np.float16)
        labels[index] = int(item["label"])
        report_records.append(item["record"])
        if (index + 1) % 1000 == 0 or index + 1 == len(records):
            print(f"FEATURES|{name}|{index + 1}/{len(records)}", flush=True)
    features.flush()
    del features
    np.save(label_path, labels, allow_pickle=False)
    return {
        "features": feature_path.as_posix(),
        "features_sha256": sha256(feature_path),
        "features_shape": [len(records), FEATURE_FRAMES, FEATURE_DIMENSION],
        "features_dtype": "float16",
        "labels": label_path.as_posix(),
        "labels_sha256": sha256(label_path),
        "positive": int(labels.sum()),
        "negative": int(len(labels) - labels.sum()),
        "records": report_records,
    }


def extract(
    *,
    synthetic_directory: Path,
    hard_manifest_path: Path,
    human_manifest_path: Path,
    output_directory: Path,
) -> dict[str, object]:
    synthetic_directory = synthetic_directory.resolve(strict=True)
    hard_manifest_path = hard_manifest_path.resolve(strict=True)
    human_manifest_path = human_manifest_path.resolve(strict=True)
    output_directory = output_directory.resolve()
    if output_directory.exists():
        raise FileExistsError(f"mdtc_ctc_feature_output_exists:{output_directory}")
    assembly_path = synthetic_directory / "assembly_manifest.v1.json"
    run_path = synthetic_directory / "development_run_manifest.v1.json"
    assembly = read_json(assembly_path)
    run = read_json(run_path)
    if run.get("assembly_manifest_sha256") != sha256(assembly_path):
        raise ValueError("mdtc_ctc_synthetic_assembly_hash_mismatch")
    if assembly.get("blind_human_partition_accessed") is not False:
        raise ValueError("mdtc_ctc_synthetic_blind_boundary_invalid")
    hard = read_json(hard_manifest_path)
    human = read_json(human_manifest_path)
    if hard.get("schema") != "baxy.mdtc-hard-negative-windows.v1":
        raise ValueError("unsupported_mdtc_ctc_hard_schema")
    if human.get("schema") != "baxy.human-ctc-aligned-livekit-features.v2":
        raise ValueError("unsupported_mdtc_ctc_human_schema")
    if (
        hard.get("blind_human_partition_accessed") is not False
        or human.get("blind_human_partition_accessed") is not False
    ):
        raise ValueError("mdtc_ctc_blind_boundary_invalid")
    hard_directory = Path(str(hard.get("output_directory"))).resolve(strict=True)
    partitions = {
        "base_train": augmented_synthetic_records(
            synthetic_directory, assembly, "train"
        )
        + hard_negative_records(hard_directory, hard, "train"),
        "base_development": augmented_synthetic_records(
            synthetic_directory, assembly, "test"
        )
        + hard_negative_records(hard_directory, hard, "development"),
        "human_development": human_records(human, human_manifest_path),
    }
    output_directory.mkdir(parents=True)
    outputs = {
        name: write_partition(output_directory, name, records)
        for name, records in partitions.items()
    }
    report: dict[str, object] = {
        "schema": "baxy.mdtc-phonetic-ctc-fbank-features.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "development_tiny_phonetic_ctc_student",
        "sources": {
            "synthetic_directory": synthetic_directory.as_posix(),
            "assembly_manifest_sha256": sha256(assembly_path),
            "development_run_manifest_sha256": sha256(run_path),
            "hard_manifest": hard_manifest_path.as_posix(),
            "hard_manifest_sha256": sha256(hard_manifest_path),
            "human_manifest": human_manifest_path.as_posix(),
            "human_manifest_sha256": sha256(human_manifest_path),
        },
        "frontend": {
            "sample_rate": SAMPLE_RATE,
            "window_samples": WINDOW_SAMPLES,
            "feature": "kaldi_fbank",
            "num_mel_bins": FEATURE_DIMENSION,
            "frame_length_ms": 25,
            "frame_shift_ms": 10,
            "dither": 0.0,
            "energy_floor": 0.0,
            "frames": FEATURE_FRAMES,
        },
        "outputs": outputs,
        "candidate_frozen": False,
        "product_operating_point": False,
        "blind_human_partition_accessed": False,
        "effects_executed": 0,
    }
    manifest_path = output_directory / "manifest.v1.json"
    manifest_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic-dir", type=Path, required=True)
    parser.add_argument("--hard-manifest", type=Path, required=True)
    parser.add_argument("--human-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = extract(
        synthetic_directory=args.synthetic_dir,
        hard_manifest_path=args.hard_manifest,
        human_manifest_path=args.human_manifest,
        output_directory=args.output_dir,
    )
    print(
        json.dumps(
            {
                name: {
                    "shape": value["features_shape"],
                    "positive": value["positive"],
                    "negative": value["negative"],
                }
                for name, value in report["outputs"].items()
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
