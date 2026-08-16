"""Extract exact 16x96 LiveKit embeddings for MDTC hard negatives."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import wave

import numpy as np


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from scan_openslr_librispeech_livekit_development import (  # noqa: E402
    BatchedLiveKitPredictor,
    SAMPLE_RATE,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"json_root_is_not_object:{path}")
    return value


def read_window(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as source:
        contract = (
            source.getnchannels(),
            source.getsampwidth(),
            source.getframerate(),
            source.getnframes(),
        )
        if contract != (1, 2, SAMPLE_RATE, 2 * SAMPLE_RATE):
            raise ValueError(f"mdtc_hard_feature_wav_contract_mismatch:{path}")
        payload = source.readframes(source.getnframes())
    return np.frombuffer(payload, dtype="<i2").astype(np.float32) / 32768.0


def records_by_split(
    manifest: dict[str, object], split: str
) -> list[dict[str, object]]:
    if split not in {"train", "development"}:
        raise ValueError("mdtc_hard_feature_split_invalid")
    records = manifest.get("records")
    if not isinstance(records, list):
        raise ValueError("mdtc_hard_feature_records_missing")
    selected = [
        record
        for record in records
        if isinstance(record, dict) and record.get("split") == split
    ]
    if not selected:
        raise ValueError(f"mdtc_hard_feature_split_empty:{split}")
    return selected


def extract(
    *,
    hard_negative_manifest_path: Path,
    livekit_model_path: Path,
    batch_size: int,
) -> dict[str, object]:
    if batch_size <= 0:
        raise ValueError("mdtc_hard_feature_batch_size_invalid")
    hard_negative_manifest_path = hard_negative_manifest_path.resolve(strict=True)
    livekit_model_path = livekit_model_path.resolve(strict=True)
    manifest = read_json(hard_negative_manifest_path)
    if manifest.get("schema") != "baxy.mdtc-hard-negative-windows.v1":
        raise ValueError("unsupported_mdtc_hard_negative_schema")
    if manifest.get("blind_human_partition_accessed") is not False:
        raise ValueError("mdtc_hard_feature_blind_boundary_is_not_clean")
    root = Path(str(manifest["output_directory"])).resolve(strict=True)
    if hard_negative_manifest_path.parent != root:
        raise ValueError("mdtc_hard_feature_manifest_root_mismatch")
    predictor = BatchedLiveKitPredictor(livekit_model_path, batch_size=batch_size)
    outputs: dict[str, dict[str, object]] = {}
    for split in ("train", "development"):
        records = records_by_split(manifest, split)
        chunks: list[np.ndarray] = []
        for start in range(0, len(records), batch_size):
            batch = records[start : start + batch_size]
            audios = []
            for record in batch:
                path = root / str(record["output_relative_path"])
                if sha256(path) != record.get("output_sha256"):
                    raise ValueError(f"mdtc_hard_feature_audio_hash_mismatch:{path}")
                audios.append(read_window(path))
            chunks.append(predictor.extract_features(np.stack(audios)))
        features = np.concatenate(chunks).astype(np.float32)
        if features.shape != (len(records), 16, 96):
            raise ValueError(f"mdtc_hard_feature_shape_invalid:{features.shape}")
        output_path = root / f"livekit_features_{split}.npy"
        if output_path.exists():
            raise FileExistsError(f"mdtc_hard_feature_output_exists:{output_path}")
        np.save(output_path, features, allow_pickle=False)
        outputs[split] = {
            "path": output_path.as_posix(),
            "sha256": sha256(output_path),
            "shape": list(features.shape),
            "record_ids": [
                str(record["output_relative_path"]) for record in records
            ],
        }
    report: dict[str, object] = {
        "schema": "baxy.mdtc-hard-negative-livekit-features.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "candidate_development_hard_negative_mining",
        "hard_negative_manifest": hard_negative_manifest_path.as_posix(),
        "hard_negative_manifest_sha256": sha256(hard_negative_manifest_path),
        "livekit_classifier": livekit_model_path.as_posix(),
        "livekit_classifier_sha256": sha256(livekit_model_path),
        "frontend": {
            "mel_model": predictor.mel_path.as_posix(),
            "mel_model_sha256": sha256(predictor.mel_path),
            "embedding_model": predictor.embedding_path.as_posix(),
            "embedding_model_sha256": sha256(predictor.embedding_path),
            "feature_shape": [16, 96],
        },
        "outputs": outputs,
        "blind_human_partition_accessed": False,
        "effects_executed": 0,
    }
    output_manifest = root / "livekit_features.manifest.v1.json"
    if output_manifest.exists():
        raise FileExistsError(f"mdtc_hard_feature_output_exists:{output_manifest}")
    output_manifest.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hard-negative-manifest", type=Path, required=True)
    parser.add_argument("--livekit-model", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=64)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = extract(
        hard_negative_manifest_path=args.hard_negative_manifest,
        livekit_model_path=args.livekit_model,
        batch_size=args.batch_size,
    )
    print(json.dumps({"outputs": report["outputs"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
