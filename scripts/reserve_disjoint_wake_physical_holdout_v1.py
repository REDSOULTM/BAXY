"""Reserve source audio disjoint from an already opened physical wake corpus."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import tempfile
from typing import Iterable


SCHEMA = "baxy.disjoint-wake-physical-holdout-source.v1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _unique_sources(directory: Path) -> list[tuple[Path, str]]:
    records: list[tuple[Path, str]] = []
    seen: set[str] = set()
    for path in sorted(directory.glob("clip_*.wav")):
        digest = _sha256(path)
        if digest not in seen:
            records.append((path, digest))
            seen.add(digest)
    return records


def select_disjoint(
    records: Iterable[tuple[Path, str]],
    *,
    excluded_hashes: set[str],
    limit: int,
    seed: int,
) -> list[tuple[Path, str]]:
    available = [record for record in records if record[1] not in excluded_hashes]
    if limit < 1 or len(available) < limit:
        raise ValueError("disjoint_wake_holdout_population_insufficient")
    return sorted(random.Random(seed).sample(available, limit), key=lambda item: item[0])


def _opened_hashes(progress: Path) -> dict[str, set[str]]:
    result = {"positive": set(), "negative": set()}
    for line in progress.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        record_id = record.get("recordId")
        digest = record.get("sourceSha256")
        if not isinstance(record_id, str) or not isinstance(digest, str):
            raise ValueError("disjoint_wake_holdout_progress_invalid")
        label = record_id.split("/", maxsplit=1)[0]
        if label not in result or len(digest) != 64:
            raise ValueError("disjoint_wake_holdout_progress_invalid")
        result[label].add(digest)
    return result


def _merge_opened_hashes(corpora: Iterable[Path]) -> dict[str, set[str]]:
    merged = {"positive": set(), "negative": set()}
    for corpus in corpora:
        current = _opened_hashes(corpus / "progress.v1.jsonl")
        for label in merged:
            merged[label].update(current[label])
    return merged


def _materialize(
    records: list[tuple[Path, str]], destination: Path
) -> list[dict[str, object]]:
    destination.mkdir(parents=True)
    result: list[dict[str, object]] = []
    for index, (source, digest) in enumerate(records):
        output = destination / f"clip_{index:06d}.wav"
        try:
            os.link(source, output)
            transport = "hardlink"
        except OSError:
            shutil.copy2(source, output)
            transport = "copy"
        if _sha256(output) != digest:
            raise RuntimeError("disjoint_wake_holdout_materialization_mismatch")
        result.append(
            {
                "index": index,
                "audioSha256": digest,
                "materialization": transport,
            }
        )
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument(
        "--opened-corpus", type=Path, required=True, action="append"
    )
    parser.add_argument(
        "--opened-report", type=Path, required=True, action="append"
    )
    parser.add_argument("--candidate-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--positive-limit", type=int, default=48)
    parser.add_argument("--negative-limit", type=int, default=96)
    parser.add_argument("--seed", type=int, default=20260811)
    return parser


def main() -> int:
    args = _parser().parse_args()
    source = args.source_dir.resolve(strict=True)
    opened = [path.resolve(strict=True) for path in args.opened_corpus]
    opened_reports = [path.resolve(strict=True) for path in args.opened_report]
    candidate = args.candidate_manifest.resolve(strict=True)
    output = args.output_dir.resolve()
    if output.exists():
        raise SystemExit("Output directory already exists.")
    if len(opened) != len(opened_reports):
        raise SystemExit("Each opened corpus requires its report.")
    report_hashes: list[str] = []
    for corpus, report_path in zip(opened, opened_reports, strict=True):
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("corpusManifestSha256") != _sha256(
            corpus / "manifest.v1.json"
        ) or not isinstance(report.get("openedCorpusPassed"), bool):
            raise SystemExit("Opened report does not identify its corpus.")
        report_hashes.append(_sha256(report_path))
    excluded = _merge_opened_hashes(opened)
    selected = {
        "positive": select_disjoint(
            _unique_sources(source / "positive"),
            excluded_hashes=excluded["positive"],
            limit=args.positive_limit,
            seed=args.seed,
        ),
        "negative": select_disjoint(
            _unique_sources(source / "negative"),
            excluded_hashes=excluded["negative"],
            limit=args.negative_limit,
            seed=args.seed + 1,
        ),
    }
    temporary = Path(tempfile.mkdtemp(prefix=f"{output.name}.", dir=output.parent))
    try:
        materialized = {
            label: _materialize(records, temporary / label)
            for label, records in selected.items()
        }
        selected_hashes = {
            label: {digest for _, digest in records}
            for label, records in selected.items()
        }
        if any(selected_hashes[label] & excluded[label] for label in selected):
            raise RuntimeError("disjoint_wake_holdout_overlap")
        manifest = {
            "schema": SCHEMA,
            "createdAtUtc": datetime.now(timezone.utc).isoformat(),
            "candidateManifestSha256": _sha256(candidate),
            "candidateLoadedOrScored": False,
            "sourceManifestSha256": _sha256(source / "manifest.v1.json"),
            "openedCorpusManifestSha256": [
                _sha256(corpus / "manifest.v1.json") for corpus in opened
            ],
            "openedReportSha256": report_hashes,
            "seed": args.seed,
            "counts": {label: len(records) for label, records in selected.items()},
            "excludedCounts": {
                label: len(records) for label, records in excluded.items()
            },
            "selectedOverlapWithOpened": {"positive": 0, "negative": 0},
            "records": materialized,
            "blindHumanPartitionAccessed": False,
            "syntheticSpeech": True,
            "reservedForOneFuturePhysicalValidation": True,
            "developmentOnly": True,
            "effectsExecuted": 0,
        }
        (temporary / "manifest.v1.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        temporary.replace(output)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    print(
        json.dumps(
            {
                "negative": len(selected["negative"]),
                "overlap": 0,
                "positive": len(selected["positive"]),
                "reserved": True,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
