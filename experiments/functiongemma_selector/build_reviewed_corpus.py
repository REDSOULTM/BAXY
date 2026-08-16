"""Freeze committee-approved candidates into FunctionGemma selection rows."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path
from typing import Any

from selector_common import (
    NO_ACTION_OPERATION,
    REPO,
    catalog_by_name,
    family_operations,
    normalize_text,
    read_jsonl,
    selection_tools,
    sha256,
    write_jsonl,
)

DEFAULT_INPUT = (
    REPO / "artifacts" / "research" / "functiongemma_candidates.reviewed.v1.jsonl"
)
DEFAULT_HELDOUTS = [
    REPO
    / "experiments"
    / "mind_router_spike"
    / "data"
    / "exact_operation_development.v1.jsonl",
]
DEFAULT_OUTPUT = (
    REPO / "artifacts" / "research" / "functiongemma_selection_corpus.v1.jsonl"
)


def build(args: argparse.Namespace) -> dict[str, Any]:
    catalog = catalog_by_name()
    reviewed = read_jsonl(args.input)
    heldouts = args.heldout or DEFAULT_HELDOUTS
    heldout = {
        normalize_text(str(row["text"]))
        for path in heldouts
        for row in read_jsonl(path)
    }
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    overlap = 0
    reviewed_operations: set[str] = set()
    for operation_row in reviewed:
        operation = str(operation_row["operation"])
        if operation not in catalog:
            raise ValueError(f"reviewed operation is absent from catalog: {operation}")
        if operation in reviewed_operations:
            raise ValueError(f"reviewed operation is duplicated: {operation}")
        reviewed_operations.add(operation)
        family = operation.split(".", 1)[0]
        candidates = operation_row["candidates"]
        review = operation_row.get("review", {})
        decisions = review.get("decisions", [])
        accepted_indices = review.get("accepted_indices", [])
        expected_accepted = [
            decision["index"]
            for decision in decisions
            if decision.get("chosen_operation") == operation
            and decision.get("clear") is True
            and decision.get("natural") is True
            and decision.get("language_ok") is True
        ]
        if accepted_indices != expected_accepted:
            raise ValueError(f"accepted decision mismatch for {operation}")
        if sorted(review.get("reviewed_indices", [])) != list(range(len(candidates))):
            raise ValueError(f"not every generated candidate was reviewed for {operation}")
        tools = selection_tools(
            catalog,
            [*family_operations(catalog, family), NO_ACTION_OPERATION],
        )
        for index in accepted_indices:
            candidate = candidates[index]
            text = str(candidate["text"])
            normalized = normalize_text(text)
            if normalized in heldout:
                overlap += 1
                continue
            unique_key = f"{family}:{normalized}"
            if unique_key in seen:
                continue
            seen.add(unique_key)
            case_hash = hashlib.sha256(unique_key.encode("utf-8")).hexdigest()[:16]
            rows.append(
                {
                    "schema": "baxy.functiongemma-selection-row.v1",
                    "case_id": f"committee-{case_hash}",
                    "language": candidate["language"],
                    "text": text,
                    "operation": operation,
                    "family": family,
                    "source": "qwen-generator+gemma-reviewer",
                    "tools": tools,
                }
            )
    if overlap:
        raise ValueError(f"reviewed corpus overlaps heldout text in {overlap} rows")
    missing_reviews = sorted(set(catalog) - reviewed_operations)
    if missing_reviews:
        raise ValueError(f"catalog operations were not reviewed: {missing_reviews}")
    write_jsonl(args.output, rows)
    operation_counts = collections.Counter(row["operation"] for row in rows)
    report = {
        "schema": "baxy.functiongemma-reviewed-corpus-build.v1",
        "rows": len(rows),
        "operations": len(operation_counts),
        "catalog_operations": len(catalog),
        "missing_operations": sorted(set(catalog) - operation_counts.keys()),
        "operation_counts": dict(operation_counts),
        "languages": dict(collections.Counter(row["language"] for row in rows)),
        "families": dict(collections.Counter(row["family"] for row in rows)),
        "heldout_exact_overlap": overlap,
        "input_sha256": sha256(args.input),
        "heldouts": [
            {"path": str(path), "sha256": sha256(path)} for path in heldouts
        ],
        "output": str(args.output.resolve()),
        "output_sha256": sha256(args.output),
    }
    report_path = args.output.with_suffix(".report.json")
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--heldout", type=Path, action="append")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    args.input = args.input.resolve(strict=True)
    args.heldout = [
        path.resolve(strict=True) for path in (args.heldout or DEFAULT_HELDOUTS)
    ]
    args.output = args.output.resolve()
    build(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
