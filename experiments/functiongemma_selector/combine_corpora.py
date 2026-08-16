"""Combine audited selector corpora with normalized-text conflict checks."""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
from typing import Any

from selector_common import REPO, normalize_text, read_jsonl, sha256, write_jsonl

DEFAULT_INPUTS = [
    REPO / "artifacts" / "research" / "functiongemma_selection_corpus.v1.jsonl",
    REPO / "artifacts" / "research" / "functiongemma_targeted_seed.v1.jsonl",
    REPO / "artifacts" / "research" / "functiongemma_audio_seed.v1.jsonl",
    REPO / "artifacts" / "research" / "functiongemma_failure_seed.v2.jsonl",
    REPO / "artifacts" / "research" / "functiongemma_contrastive_seed.v3.jsonl",
]
DEFAULT_OUTPUT = REPO / "artifacts" / "research" / "functiongemma_training_corpus.v1.jsonl"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, action="append")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    inputs = [path.resolve(strict=True) for path in (args.input or DEFAULT_INPUTS)]
    output = args.output.resolve()
    by_key: dict[str, dict[str, Any]] = {}
    source_counts: collections.Counter[str] = collections.Counter()
    for path in inputs:
        for row in read_jsonl(path):
            key = f"{row['family']}:{normalize_text(str(row['text']))}"
            prior = by_key.get(key)
            if prior is not None and prior["operation"] != row["operation"]:
                raise ValueError(
                    f"conflicting corpus labels for {row['text']!r}: "
                    f"{prior['operation']} vs {row['operation']}"
                )
            by_key[key] = row
            source_counts[str(row.get("source") or path.name)] += 1
    rows = sorted(by_key.values(), key=lambda row: str(row["case_id"]))
    write_jsonl(output, rows)
    operations = collections.Counter(str(row["operation"]) for row in rows)
    report = {
        "schema": "baxy.functiongemma-combined-corpus.v1",
        "rows": len(rows),
        "operations": len(operations),
        "minimum_examples_per_operation": min(operations.values()),
        "maximum_examples_per_operation": max(operations.values()),
        "languages": dict(collections.Counter(str(row["language"]) for row in rows)),
        "sources": dict(source_counts),
        "inputs": [
            {"path": str(path), "sha256": sha256(path)} for path in inputs
        ],
        "output": str(output),
        "output_sha256": sha256(output),
    }
    report_path = output.with_suffix(".report.json")
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
