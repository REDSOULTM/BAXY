"""Merge verified selected VoxCPM2 corpora without changing audio bytes."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys


SCHEMA = "baxy.voxcpm2-ipa-filtered-wake-corpus.v1"


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


def merge_corpora(
    source_manifest_paths: list[Path], output_dir: Path
) -> dict[str, object]:
    if len(source_manifest_paths) < 2:
        raise ValueError("merge_requires_at_least_two_source_manifests")
    sources: list[tuple[Path, dict[str, object], list[dict[str, object]]]] = []
    for raw_path in source_manifest_paths:
        path = raw_path.resolve(strict=True)
        manifest = read_json(path)
        if manifest.get("schema") != SCHEMA:
            raise ValueError("unsupported_merge_source_schema")
        if manifest.get("class_label") != "positive":
            raise ValueError("merge_source_must_be_positive")
        if manifest.get("blind_human_partition_accessed") is not False:
            raise ValueError("merge_source_blind_boundary_invalid")
        raw_records = manifest.get("records")
        if not isinstance(raw_records, list) or not raw_records:
            raise ValueError("merge_source_records_missing")
        records = [record for record in raw_records if isinstance(record, dict)]
        if len(records) != len(raw_records):
            raise ValueError("merge_source_record_is_not_object")
        sources.append((path, manifest, records))

    root = output_dir.resolve()
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"merge_output_directory_not_empty:{root}")
    root.mkdir(parents=True, exist_ok=True)
    emitted: list[dict[str, object]] = []
    source_reports: list[dict[str, object]] = []
    for source_manifest_index, (path, manifest, records) in enumerate(sources):
        source_filter = manifest.get("filter")
        policy = (
            source_filter.get("positive_ipa_policy", "exact_target")
            if isinstance(source_filter, dict)
            else "exact_target"
        )
        source_reports.append(
            {
                "manifest": path.as_posix(),
                "manifest_sha256": sha256(path),
                "record_count": len(records),
                "positive_ipa_policy": policy,
            }
        )
        for record in records:
            source_wav = path.parent / str(record["output_file"])
            expected_hash = str(record.get("wav", {}).get("sha256", ""))
            if not source_wav.is_file() or sha256(source_wav) != expected_hash:
                raise ValueError(f"merge_source_wav_hash_mismatch:{source_wav}")
            output_index = len(emitted)
            output_path = root / f"clip_{output_index:06d}.wav"
            os.link(source_wav, output_path)
            merged = dict(record)
            merged.update(
                {
                    "output_index": output_index,
                    "output_file": output_path.name,
                    "merge_source_manifest_index": source_manifest_index,
                    "merge_source_output_index": record["output_index"],
                    "source_positive_ipa_policy": policy,
                }
            )
            emitted.append(merged)

    report = {
        "schema": SCHEMA,
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "class_label": "positive",
        "sources": source_reports,
        "filter": {
            "stage": "verified_selected_corpus_merge",
            "audio_transform": "none_hardlink_exact_bytes",
            "positive_ipa_policy": "per_record_source_policy",
            "source_policies": sorted(
                {str(source["positive_ipa_policy"]) for source in source_reports}
            ),
        },
        "counts": {
            "sources": len(sources),
            "records": len(emitted),
            "by_persona": dict(
                sorted(Counter(str(record["persona_id"]) for record in emitted).items())
            ),
            "by_phrase": dict(
                sorted(
                    Counter(str(record.get("phrase_id", "target")) for record in emitted).items()
                )
            ),
        },
        "records": emitted,
        "blind_human_partition_accessed": False,
        "candidate_model_training_started": False,
        "effects_executed": 0,
    }
    manifest_path = root / "manifest.v1.json"
    manifest_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = merge_corpora(args.source_manifest, args.output_dir)
    summary = {
        "manifest": (args.output_dir.resolve() / "manifest.v1.json").as_posix(),
        "source_count": report["counts"]["sources"],
        "record_count": report["counts"]["records"],
        "blind_human_partition_accessed": False,
    }
    sys.stdout.buffer.write(
        (json.dumps(summary, ensure_ascii=False) + "\n").encode("utf-8")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
