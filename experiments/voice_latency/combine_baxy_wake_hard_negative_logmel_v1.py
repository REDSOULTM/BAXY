"""Combine hash-bound OpenSLR wake hard-negative log-Mel stores."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np


SCHEMA = "baxy.openslr-wake-hard-negative-logmel.v1"
CONTROLLED_SCHEMA = "baxy.controlled-hard-negative-logmel.v1"
ACCEPTED_SCHEMAS = {SCHEMA, CONTROLLED_SCHEMA}
FRAMES = 300
MEL_BINS = 80


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("wake_hard_negative_combine_json_invalid")
    return value


def selected_records(
    manifests: list[dict[str, Any]],
) -> list[tuple[int, int, dict[str, Any]]]:
    selected: list[tuple[int, int, dict[str, Any]]] = []
    seen: set[tuple[str, int]] = set()
    for store_index, manifest in enumerate(manifests):
        records = manifest.get("records")
        if manifest.get("schema") not in ACCEPTED_SCHEMAS or not isinstance(records, list):
            raise ValueError("wake_hard_negative_combine_manifest_invalid")
        for record_index, record in enumerate(records):
            if not isinstance(record, dict):
                raise ValueError("wake_hard_negative_combine_record_invalid")
            raw_window = record.get(
                "window_index", record.get("runtime_window_index", -1)
            )
            identity = (str(record.get("audio_sha256")), int(raw_window))
            if identity in seen:
                continue
            seen.add(identity)
            selected.append((store_index, record_index, record))
    return selected


def combine(inputs: list[Path], output: Path) -> dict[str, Any]:
    if len(inputs) < 2:
        raise ValueError("wake_hard_negative_combine_inputs_invalid")
    output = output.resolve()
    partial = output.with_name(output.name + ".partial")
    if output.exists() or partial.exists():
        raise FileExistsError("wake_hard_negative_combine_output_exists")
    paths = [path.resolve(strict=True) for path in inputs]
    manifests = [read_object(path) for path in paths]
    contracts = [manifest.get("contract") for manifest in manifests]
    if any(
        not isinstance(contract, dict)
        or contract.get("frames") != FRAMES
        or contract.get("mel_bins") != MEL_BINS
        for contract in contracts
    ) or len({int(contract["hop_samples"]) for contract in contracts}) != 1:
        raise ValueError("wake_hard_negative_combine_contract_invalid")
    stores = []
    for path, manifest in zip(paths, manifests, strict=True):
        files = manifest.get("files")
        if not isinstance(files, dict):
            raise ValueError("wake_hard_negative_combine_files_invalid")
        feature_path = (path.parent / str(files.get("logmel") or "")).resolve(strict=True)
        offset_path = (path.parent / str(files.get("offsets") or "")).resolve(strict=True)
        if (
            sha256(feature_path) != files.get("logmel_sha256")
            or sha256(offset_path) != files.get("offsets_sha256")
        ):
            raise ValueError("wake_hard_negative_combine_hash_invalid")
        stores.append(
            (
                np.load(feature_path, mmap_mode="r", allow_pickle=False),
                np.load(offset_path, allow_pickle=False),
            )
        )
    chosen = selected_records(manifests)
    partial.mkdir(parents=True)
    combined = np.lib.format.open_memmap(
        partial / "logmel.f16.npy",
        mode="w+",
        dtype=np.float16,
        shape=(len(chosen) * FRAMES, MEL_BINS),
    )
    records = []
    for output_index, (store_index, record_index, record) in enumerate(chosen):
        features, offsets = stores[store_index]
        start = int(offsets[record_index])
        end = int(offsets[record_index + 1])
        if end - start != FRAMES:
            raise ValueError("wake_hard_negative_combine_feature_shape_invalid")
        output_start = output_index * FRAMES
        combined[output_start : output_start + FRAMES] = features[start:end]
        copied = dict(record)
        copied["feature_start"] = output_start
        copied["feature_end"] = output_start + FRAMES
        copied["feature_frames"] = FRAMES
        records.append(copied)
    combined.flush()
    del combined
    offsets = np.arange(len(records) + 1, dtype=np.int64) * FRAMES
    np.save(partial / "offsets.i64.npy", offsets)
    feature_path = partial / "logmel.f16.npy"
    offset_path = partial / "offsets.i64.npy"
    unique_audio = {str(record["audio_sha256"]) for record in records}
    controlled = any(
        manifest.get("schema") == CONTROLLED_SCHEMA for manifest in manifests
    )
    manifest = {
        "schema": CONTROLLED_SCHEMA if controlled else SCHEMA,
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": (
            "opened_combined_controlled_hard_negative_logmel_development"
            if controlled
            else "opened_openslr_combined_hard_negative_logmel_development"
        ),
        "sources": {
            "feature_manifest_sha256": [sha256(path) for path in paths],
        },
        "contract": {
            "top_k_per_false_utterance": None,
            "hop_samples": int(contracts[0]["hop_samples"]),
            "frames": FRAMES,
            "mel_bins": MEL_BINS,
            "selection": "stable_unique_audio_hash_and_window_union",
            "speaker_identity": "pseudonymous_integer_only",
            "gpu": None,
        },
        "counts": {
            "source_records": len(unique_audio),
            "records": len(records),
            "frames": len(records) * FRAMES,
        },
        "files": {
            "logmel": feature_path.name,
            "logmel_sha256": sha256(feature_path),
            "offsets": offset_path.name,
            "offsets_sha256": sha256(offset_path),
        },
        "records": records,
        "candidate_development_use": True,
        "fresh_holdout_claim_supported": False,
        "development_only": True,
        "human_development_audio_accessed": any(
            source.get("human_development_audio_accessed") is True
            for source in manifests
        ),
        "blind_human_audio_accessed": False,
        "transcripts_or_filenames_retained": False,
        "effects_executed": 0,
    }
    (partial / "features.manifest.v1.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    partial.replace(output)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", action="append", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = combine(args.input, args.output)
    print(json.dumps(report["counts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
