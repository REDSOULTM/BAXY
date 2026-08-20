"""Attach production-like current-operation candidates to inherited real rows."""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
from scipy.sparse import hstack

REPO = Path(__file__).resolve().parents[2]
for root in (REPO, REPO / "src", REPO / "experiments/functiongemma_selector"):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from baxy_mind.planner import PlannerCatalog  # noqa: E402
from baxy_mind.router import SemanticEncoder  # noqa: E402
from experiments.mind_router_spike.build_goal03_functiongemma_current_union_corpus import (  # noqa: E402
    EXPECTED_RANKER_WEIGHTS_SHA256,
    RANKER_ASSETS,
    _configure_tools,
    _e5_rankings,
    _read_jsonl,
    _resources,
    _sha256,
    _write_jsonl,
)
from scripts.measure_mind_budget import (  # noqa: E402
    current_core_catalog_snapshot,
    discover_core,
)
from selector_common import NO_ACTION_OPERATION, selection_tools  # noqa: E402

DEFAULT_DIR = Path(r"D:\BAXYRuntime\experiments\functiongemma-real-language-v1")
DEFAULT_REPORT = (
    REPO / "artifacts" / "development" / "goal03_inherited_real_union_corpus_v34.json"
)


def _counts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = collections.Counter(str(row["operation"]) for row in rows)
    return {
        "rows": len(rows),
        "operations": len(values),
        "by_operation": dict(sorted(values.items())),
    }


def build(source_dir: Path, report_path: Path, batch_size: int) -> dict[str, Any]:
    train_source = source_dir / "mapped_train.jsonl"
    validation_source = source_dir / "mapped_validation.jsonl"
    train_output = source_dir / "current_union_train.jsonl"
    validation_output = source_dir / "current_union_validation.jsonl"
    if train_output.exists() or validation_output.exists():
        raise FileExistsError("refusing to overwrite current-union real-language rows")
    if _sha256(RANKER_ASSETS / "operation_shortlist.v1.weights.npz") != (
        EXPECTED_RANKER_WEIGHTS_SHA256
    ):
        raise RuntimeError("inherited frozen ranker identity changed")

    train_rows = _read_jsonl(train_source)
    validation_rows = _read_jsonl(validation_source)
    rows = [*train_rows, *validation_rows]
    split = ["train"] * len(train_rows) + ["validation"] * len(validation_rows)
    capabilities, _, _ = current_core_catalog_snapshot(discover_core(None))
    catalog = {str(row["name"]): row for row in capabilities}
    unknown = sorted({str(row["operation"]) for row in rows} - set(catalog))
    if unknown:
        raise RuntimeError(f"mapped operations absent from current catalogue: {unknown}")

    texts = [str(row["text"]) for row in rows]
    words, characters, classes, coefficients, intercept = _resources(RANKER_ASSETS)
    features = hstack((words.transform(texts), characters.transform(texts)), format="csr")
    scores = np.asarray(features @ coefficients.T + intercept)
    ranker_rankings = [
        [classes[index] for index in np.argsort(-scores[row_index])]
        for row_index in range(len(rows))
    ]
    encoder = SemanticEncoder(device="cpu")
    planner = PlannerCatalog(_configure_tools(capabilities), encoder=encoder.encode)
    e5_rankings = _e5_rankings(texts, planner, encoder, batch_size)

    built: list[tuple[str, dict[str, Any]]] = []
    candidate_counts: list[int] = []
    for population, source, ranker, e5 in zip(
        split, rows, ranker_rankings, e5_rankings, strict=True
    ):
        candidates = [
            name
            for name in dict.fromkeys([*ranker[:14], *e5[:14]])
            if name in catalog
        ][:28]
        candidate_counts.append(len(candidates))
        operation = str(source["operation"])
        retrieved = operation in candidates
        built.append(
            (
                population,
                {
                    **source,
                    "schema": "baxy.functiongemma-current-union-row.v1",
                    "balance_key": operation,
                    "retrieved_before_force": retrieved,
                    "candidate_operations": candidates,
                    "tools": selection_tools(
                        catalog, [*candidates, NO_ACTION_OPERATION]
                    ),
                },
            )
        )

    # A target absent from the declared tools is not a train example. Validation
    # retains such rows so retrieval misses remain honest end-to-end failures.
    built_train = [
        row
        for population, row in built
        if population == "train" and row["retrieved_before_force"]
    ]
    built_validation = [
        row for population, row in built if population == "validation"
    ]
    _write_jsonl(train_output, built_train)
    _write_jsonl(validation_output, built_validation)

    train_retrieved = sum(
        population == "train" and bool(row["retrieved_before_force"])
        for population, row in built
    )
    validation_retrieved = sum(
        population == "validation" and bool(row["retrieved_before_force"])
        for population, row in built
    )
    report = {
        "schema": "baxy.goal03-inherited-real-current-union-corpus.v1",
        "sources": {
            "train": {"path": str(train_source), "sha256": _sha256(train_source)},
            "validation": {
                "path": str(validation_source),
                "sha256": _sha256(validation_source),
            },
            "ranker_weights_sha256": EXPECTED_RANKER_WEIGHTS_SHA256,
        },
        "catalog_operations": len(catalog),
        "retrieval": {
            "train": {"retrieved": train_retrieved, "rows": len(train_rows)},
            "validation": {
                "retrieved": validation_retrieved,
                "rows": len(validation_rows),
            },
        },
        "candidate_count": {
            "minimum": min(candidate_counts),
            "mean": round(sum(candidate_counts) / len(candidate_counts), 6),
            "maximum": max(candidate_counts),
        },
        "outputs": {
            "train": {
                "path": str(train_output),
                "sha256": _sha256(train_output),
                **_counts(built_train),
            },
            "validation": {
                "path": str(validation_output),
                "sha256": _sha256(validation_output),
                **_counts(built_validation),
            },
        },
        "policy": "symmetric frozen-ranker 14 + E5 14; no forced labels",
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
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--batch-size", type=int, default=128)
    args = parser.parse_args()
    report = build(args.source_dir.resolve(), args.report.resolve(), args.batch_size)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
