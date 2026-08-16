"""Merge hash-bound physical-room LiveKit feature extensions."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np


SCHEMA = "baxy.controlled-physical-wake-livekit-features.v1"
SPLITS = (
    "positive_train",
    "positive_development",
    "negative_train",
    "negative_development",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def merge_arrays(paths: list[Path]) -> np.ndarray:
    arrays = [np.load(path, allow_pickle=False) for path in paths]
    if not arrays or any(
        array.dtype != np.float32
        or array.ndim != 3
        or array.shape[1:] != (16, 96)
        for array in arrays
    ):
        raise ValueError("physical_feature_merge_array_contract_invalid")
    return np.concatenate(arrays, axis=0).astype(np.float32, copy=False)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    manifests: list[tuple[Path, dict[str, object]]] = []
    for raw_path in args.manifest:
        path = raw_path.resolve(strict=True)
        report = json.loads(path.read_text(encoding="utf-8-sig"))
        if report.get("schema") != SCHEMA:
            raise ValueError("physical_feature_merge_schema_invalid")
        if report.get("blind_human_partition_accessed") is not False:
            raise ValueError("physical_feature_merge_blind_boundary_invalid")
        manifests.append((path, report))
    if len(manifests) < 2:
        raise ValueError("physical_feature_merge_requires_multiple_manifests")
    output_directory = args.output_dir.resolve()
    if output_directory.exists():
        raise SystemExit("Output directory already exists.")
    output_directory.mkdir(parents=True)
    outputs: dict[str, dict[str, object]] = {}
    for split in SPLITS:
        paths: list[Path] = []
        for _, manifest in manifests:
            raw_outputs = manifest.get("outputs")
            raw = raw_outputs.get(split) if isinstance(raw_outputs, dict) else None
            if not isinstance(raw, dict):
                raise ValueError(f"physical_feature_merge_output_missing:{split}")
            path_value = raw.get("path")
            digest_value = raw.get("sha256")
            if not isinstance(path_value, str) or not isinstance(digest_value, str):
                raise ValueError(f"physical_feature_merge_identity_invalid:{split}")
            path = Path(path_value).resolve(strict=True)
            if sha256(path) != digest_value:
                raise ValueError(f"physical_feature_merge_digest_mismatch:{split}")
            paths.append(path)
        merged = merge_arrays(paths)
        output_path = output_directory / f"{split}.npy"
        np.save(output_path, merged, allow_pickle=False)
        outputs[split] = {
            "path": output_path.as_posix(),
            "sha256": sha256(output_path),
            "shape": list(merged.shape),
            "sourceRecords": int(merged.shape[0]),
            "repeatWeight": None,
        }
    report = {
        "schema": SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "merged_controlled_physical_room_livekit_feature_extension",
        "sourceManifests": [
            {"path": path.as_posix(), "sha256": sha256(path)}
            for path, _ in manifests
        ],
        "outputs": outputs,
        "blind_human_partition_accessed": False,
        "developmentOnly": True,
        "effectsExecuted": 0,
    }
    manifest_path = output_directory / "livekit_features.manifest.v1.json"
    manifest_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({name: value["shape"] for name, value in outputs.items()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
