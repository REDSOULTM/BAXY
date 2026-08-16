"""Combine compatible controlled RAW runtime log-Mel development stores."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np


SCHEMA = "baxy.controlled-raw-runtime-logmel.v1"
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
        raise ValueError("controlled_raw_logmel_combine_json_invalid")
    return value


def _contract_key(contract: dict[str, Any]) -> tuple[object, ...]:
    return (
        contract.get("sample_rate"),
        contract.get("mel_bins"),
        contract.get("runtime_window_samples"),
        contract.get("side_padding_samples"),
        contract.get("hop_samples"),
        contract.get("filenames_or_transcripts_retained"),
        contract.get("positive_window_selection"),
    )


def combine(inputs: list[Path], output: Path) -> dict[str, Any]:
    if len(inputs) < 2:
        raise ValueError("controlled_raw_logmel_combine_inputs_invalid")
    paths = [path.resolve(strict=True) for path in inputs]
    output = output.resolve()
    partial = output.with_name(output.name + ".partial")
    if output.exists() or partial.exists():
        raise FileExistsError("controlled_raw_logmel_combine_output_exists")

    manifests = [read_object(path) for path in paths]
    manifest_hashes = [sha256(path) for path in paths]
    contracts: list[dict[str, Any]] = []
    stores: list[tuple[np.ndarray, np.ndarray]] = []
    selected: list[tuple[int, int, dict[str, Any]]] = []
    seen: dict[tuple[str, int], str] = {}
    for store_index, (path, manifest) in enumerate(
        zip(paths, manifests, strict=True)
    ):
        contract = manifest.get("contract")
        files = manifest.get("files")
        records = manifest.get("records")
        if (
            manifest.get("schema") != SCHEMA
            or manifest.get("development_only") is not True
            or manifest.get("blind_human_audio_accessed") is not False
            or manifest.get("human_development_audio_accessed") is not False
            or not isinstance(contract, dict)
            or not isinstance(files, dict)
            or not isinstance(records, list)
        ):
            raise ValueError("controlled_raw_logmel_combine_manifest_invalid")
        contracts.append(contract)
        feature_path = (path.parent / str(files.get("logmel") or "")).resolve(
            strict=True
        )
        offset_path = (path.parent / str(files.get("offsets") or "")).resolve(
            strict=True
        )
        if (
            sha256(feature_path) != files.get("logmel_sha256")
            or sha256(offset_path) != files.get("offsets_sha256")
        ):
            raise ValueError("controlled_raw_logmel_combine_hash_invalid")
        features = np.load(feature_path, mmap_mode="r", allow_pickle=False)
        offsets = np.load(offset_path, allow_pickle=False)
        if (
            features.ndim != 2
            or features.shape[1] != MEL_BINS
            or len(offsets) != len(records) + 1
            or int(offsets[0]) != 0
            or int(offsets[-1]) != len(features)
        ):
            raise ValueError("controlled_raw_logmel_combine_feature_shape_invalid")
        stores.append((features, offsets))
        for record_index, record in enumerate(records):
            if (
                not isinstance(record, dict)
                or record.get("label") not in {"positive", "adversarial_negative"}
                or not isinstance(record.get("persona_id"), str)
                or not isinstance(record.get("audio_sha256"), str)
                or not isinstance(record.get("runtime_window_index"), int)
            ):
                raise ValueError("controlled_raw_logmel_combine_record_invalid")
            start = int(offsets[record_index])
            end = int(offsets[record_index + 1])
            if end - start != FRAMES:
                raise ValueError("controlled_raw_logmel_combine_feature_shape_invalid")
            identity = (
                str(record["audio_sha256"]),
                int(record["runtime_window_index"]),
            )
            label = str(record["label"])
            if identity in seen:
                if seen[identity] != label:
                    raise ValueError("controlled_raw_logmel_combine_label_conflict")
                continue
            seen[identity] = label
            selected.append((store_index, record_index, record))

    expected_contract = _contract_key(contracts[0])
    if (
        expected_contract
        != (16000, MEL_BINS, 48000, 16000, 4000, False, "all_runtime_windows")
        or any(_contract_key(contract) != expected_contract for contract in contracts[1:])
    ):
        raise ValueError("controlled_raw_logmel_combine_contract_invalid")

    partial.mkdir(parents=True)
    feature_path = partial / "logmel.f16.npy"
    combined = np.lib.format.open_memmap(
        feature_path,
        mode="w+",
        dtype=np.float16,
        shape=(len(selected) * FRAMES, MEL_BINS),
    )
    records: list[dict[str, Any]] = []
    for output_index, (store_index, record_index, record) in enumerate(selected):
        features, offsets = stores[store_index]
        start = int(offsets[record_index])
        end = int(offsets[record_index + 1])
        output_start = output_index * FRAMES
        combined[output_start : output_start + FRAMES] = features[start:end]
        copied = dict(record)
        original_record_id = copied.get("record_id")
        if not isinstance(original_record_id, str):
            raise ValueError("controlled_raw_logmel_combine_record_invalid")
        copied["source_record_id"] = original_record_id
        copied["record_id"] = (
            f"{manifest_hashes[store_index][:16]}:{original_record_id}"
        )
        copied["feature_start"] = output_start
        copied["feature_end"] = output_start + FRAMES
        copied["feature_frames"] = FRAMES
        records.append(copied)
    combined.flush()
    del combined

    offsets = np.arange(len(records) + 1, dtype=np.int64) * FRAMES
    offset_path = partial / "offsets.i64.npy"
    np.save(offset_path, offsets)
    positive = sum(record["label"] == "positive" for record in records)
    negative = len(records) - positive
    source_records = {
        str(record.get("source_audio_sha256") or record["audio_sha256"])
        for record in records
    }
    manifest = {
        "schema": SCHEMA,
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "feature_manifest_sha256": manifest_hashes,
            "physical_manifest_sha256": [
                manifest.get("sources", {}).get("physical_manifest_sha256")
                for manifest in manifests
            ],
        },
        "contract": dict(contracts[0]),
        "counts": {
            "positive": positive,
            "adversarial_negative": negative,
            "source_records": len(source_records),
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
        "runtime_seconds": sum(
            float(manifest.get("runtime_seconds") or 0.0) for manifest in manifests
        ),
        "human_development_audio_accessed": False,
        "blind_human_audio_accessed": False,
        "development_only": True,
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
    arguments = parser.parse_args()
    report = combine(arguments.input, arguments.output)
    print(json.dumps(report["counts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
