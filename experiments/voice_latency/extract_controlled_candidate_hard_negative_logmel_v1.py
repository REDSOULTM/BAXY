"""Freeze candidate-triggered controlled RAW windows as hard negatives."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path

import numpy as np


SCHEMA = "baxy.controlled-hard-negative-logmel.v1"
SOURCE_SCHEMAS = {
    "baxy.controlled-raw-runtime-logmel.v1",
    "baxy.baxy-hyperspotter-physical-runtime-logmel.v2",
}
FRAMES = 300
MEL_BINS = 80


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"controlled_hard_negative_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_TRAIN = load_component(
    "train_baxy_logmel_closed_set_verifier_v1.py",
    "_controlled_candidate_hard_negative_train_v1",
)
_BASE = _TRAIN._BASE._LOGMEL


def extract(
    *, source_manifest_path: Path, candidate_report_paths: list[Path], output: Path
) -> dict[str, object]:
    if not candidate_report_paths:
        raise ValueError("controlled_hard_negative_candidate_reports_empty")
    source_manifest_path = source_manifest_path.resolve(strict=True)
    candidate_report_paths = [path.resolve(strict=True) for path in candidate_report_paths]
    output = output.resolve()
    partial = output.with_name(output.name + ".partial")
    if output.exists() or partial.exists():
        raise FileExistsError("controlled_hard_negative_output_exists")

    source = _BASE.read_object(source_manifest_path)
    records = source.get("records")
    files = source.get("files")
    sources = source.get("sources")
    source_contract = source.get("contract")
    if (
        source.get("schema") not in SOURCE_SCHEMAS
        or source.get("development_only") is not True
        or source.get("blind_human_audio_accessed") is not False
        or not isinstance(records, list)
        or not isinstance(files, dict)
        or not isinstance(sources, dict)
        or not isinstance(source_contract, dict)
        or not isinstance(sources.get("physical_manifest_sha256"), str)
    ):
        raise ValueError("controlled_hard_negative_source_boundary_invalid")
    selected_hashes: set[str] = set()
    for report_path in candidate_report_paths:
        selected_hashes.update(
            _TRAIN.candidate_audio_hashes(
                _BASE.read_object(report_path),
                physical_manifest_sha256=str(sources["physical_manifest_sha256"]),
            )
        )
    selected = [
        (index, record)
        for index, record in enumerate(records)
        if isinstance(record, dict)
        and record.get("label") == "adversarial_negative"
        and str(record.get("audio_sha256", "")).lower() in selected_hashes
    ]
    if not selected:
        raise ValueError("controlled_hard_negative_selection_empty")

    feature_path = (source_manifest_path.parent / str(files.get("logmel"))).resolve(
        strict=True
    )
    offset_path = (source_manifest_path.parent / str(files.get("offsets"))).resolve(
        strict=True
    )
    if (
        _BASE.sha256(feature_path) != files.get("logmel_sha256")
        or _BASE.sha256(offset_path) != files.get("offsets_sha256")
    ):
        raise ValueError("controlled_hard_negative_source_hash_invalid")
    features = np.load(feature_path, mmap_mode="r", allow_pickle=False)
    offsets = np.load(offset_path, allow_pickle=False)

    partial.mkdir(parents=True)
    output_features = np.lib.format.open_memmap(
        partial / "logmel.f16.npy",
        mode="w+",
        dtype=np.float16,
        shape=(len(selected) * FRAMES, MEL_BINS),
    )
    output_records: list[dict[str, object]] = []
    for output_index, (source_index, record) in enumerate(selected):
        start = int(offsets[source_index])
        end = int(offsets[source_index + 1])
        if end - start != FRAMES:
            raise ValueError("controlled_hard_negative_feature_shape_invalid")
        output_start = output_index * FRAMES
        output_features[output_start : output_start + FRAMES] = features[start:end]
        output_records.append(
            {
                **record,
                "feature_start": output_start,
                "feature_end": output_start + FRAMES,
                "feature_frames": FRAMES,
            }
        )
    output_features.flush()
    del output_features
    output_offsets = np.arange(len(selected) + 1, dtype=np.int64) * FRAMES
    np.save(partial / "offsets.i64.npy", output_offsets)
    output_feature_path = partial / "logmel.f16.npy"
    output_offset_path = partial / "offsets.i64.npy"
    report: dict[str, object] = {
        "schema": SCHEMA,
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "opened_controlled_candidate_routes_hard_negative_logmel",
        "sources": {
            "feature_manifest_sha256": _BASE.sha256(source_manifest_path),
            "candidate_report_sha256": [
                _BASE.sha256(path) for path in candidate_report_paths
            ],
            "physical_manifest_sha256": sources["physical_manifest_sha256"],
        },
        "contract": {
            "frames": FRAMES,
            "mel_bins": MEL_BINS,
            "hop_samples": int(source_contract.get("hop_samples", 4_000)),
            "selection": "all_windows_from_candidate_triggered_negative_sources",
            "filenames_or_transcripts_retained": False,
        },
        "counts": {
            "source_records": len(
                {str(record["audio_sha256"]) for record in output_records}
            ),
            "records": len(output_records),
            "frames": len(output_records) * FRAMES,
        },
        "files": {
            "logmel": output_feature_path.name,
            "logmel_sha256": _BASE.sha256(output_feature_path),
            "offsets": output_offset_path.name,
            "offsets_sha256": _BASE.sha256(output_offset_path),
        },
        "records": output_records,
        "human_development_audio_accessed": bool(
            source.get("human_development_audio_accessed")
        ),
        "blind_human_audio_accessed": False,
        "development_only": True,
        "effects_executed": 0,
    }
    (partial / "features.manifest.v1.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    partial.rename(output)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--candidate-report", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    report = extract(
        source_manifest_path=arguments.source_manifest,
        candidate_report_paths=arguments.candidate_report,
        output=arguments.output,
    )
    print(json.dumps(report["counts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
