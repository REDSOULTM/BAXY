"""Merge current-catalogue training rows with inherited real-language rows."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
CURRENT = Path(r"D:\BAXYRuntime\experiments\functiongemma-current-union-v1\train.jsonl")
REAL = Path(
    r"D:\BAXYRuntime\experiments\functiongemma-real-language-v1\current_union_train.jsonl"
)
SEALED = REPO / "artifacts" / "development" / "goal03_fresh_paraphrase_corpus.v1.jsonl"
DEFAULT_OUTPUT = Path(
    r"D:\BAXYRuntime\experiments\functiongemma-current-union-real-mixed-v1\train.jsonl"
)
DEFAULT_REPORT = (
    REPO / "artifacts" / "development" / "goal03_functiongemma_real_mixed_corpus_v36.json"
)
EXPECTED_SEALED_SHA256 = (
    "761c1bc3b3facbf14a3aaafa09f24c0e5e0baaf8cebdd0edc7c2e648cb87413d"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _normalize(text: str) -> str:
    value = unicodedata.normalize("NFKD", text.casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(re.findall(r"[a-z0-9]+", value))


def build(output: Path, report_path: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    if _sha256(SEALED) != EXPECTED_SEALED_SHA256:
        raise RuntimeError("sealed Goal 03 corpus identity changed")
    current = _jsonl(CURRENT)
    real = _jsonl(REAL)
    sealed_norm = {_normalize(str(row["text"])) for row in _jsonl(SEALED)}

    merged = {_normalize(str(row["text"])): row for row in current}
    same_label_replaced = 0
    conflicting_real_removed = 0
    for row in real:
        key = _normalize(str(row["text"]))
        existing = merged.get(key)
        if existing is not None:
            if existing["operation"] != row["operation"]:
                conflicting_real_removed += 1
                continue
            same_label_replaced += 1
        merged[key] = row
    rows = sorted(
        merged.values(),
        key=lambda row: (
            str(row["operation"]),
            hashlib.sha256(_normalize(str(row["text"])).encode("utf-8")).hexdigest(),
        ),
    )
    overlap = sum(_normalize(str(row["text"])) in sealed_norm for row in rows)
    if overlap:
        raise RuntimeError("mixed corpus overlaps the sealed Goal 03 corpus")
    output.parent.mkdir(parents=True, exist_ok=False)
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    operations = {str(row["operation"]) for row in rows if row["operation"] != "__no_action__"}
    source_counts = collections.Counter(str(row.get("source")) for row in rows)
    real_source = "inherited-real-language-high-confidence-v1"
    real_by_operation = collections.Counter(
        str(row["operation"])
        for row in rows
        if row.get("source") == real_source
    )
    expected_preferred_rows = sum(min(8, count) for count in real_by_operation.values())
    report = {
        "schema": "baxy.goal03-functiongemma-real-mixed-corpus.v1",
        "sources": {
            "current": {"path": str(CURRENT), "sha256": _sha256(CURRENT), "rows": len(current)},
            "inherited_real": {"path": str(REAL), "sha256": _sha256(REAL), "rows": len(real)},
            "sealed_exclusion_only": {"path": str(SEALED.relative_to(REPO)), "sha256": _sha256(SEALED)},
        },
        "output": {
            "path": str(output),
            "sha256": _sha256(output),
            "rows": len(rows),
            "operations": len(operations),
            "real_rows": source_counts[real_source],
            "no_action_rows": sum(row["operation"] == "__no_action__" for row in rows),
        },
        "same_label_real_rows_replaced_current": same_label_replaced,
        "conflicting_real_rows_removed": conflicting_real_removed,
        "exact_normalized_overlap_with_sealed": overlap,
        "training_preregistration": {
            "epochs": 1,
            "per_operation": 8,
            "preferred_source": real_source,
            "preferred_per_operation": 8,
            "no_action_ratio": 0.5,
            "batch_size": 1,
            "gradient_accumulation": 8,
            "max_length": 1408,
            "attention_implementation": "sdpa",
            "learning_rate": 0.0002,
            "rank": 16,
            "alpha": 32,
            "seed": 5601,
            "expected_balanced_rows_per_epoch": 2028,
            "expected_preferred_real_rows_per_epoch": expected_preferred_rows,
        },
        "validation_gates": {
            "real_exact_minimum": "50/71",
            "synthetic_positive_exact_minimum": "430/477",
            "synthetic_negative_selected_actions_maximum": "0/307",
        },
        "authority": {
            "providers_enabled": False,
            "effects_executed": 0,
            "runtime_manifest_changed": False,
        },
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    report = build(args.output.resolve(), args.report.resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
