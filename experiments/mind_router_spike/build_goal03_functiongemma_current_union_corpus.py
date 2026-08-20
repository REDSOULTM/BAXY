"""Build a query-disjoint FunctionGemma corpus with production-like distractors.

Positive labels come from the already reviewed FunctionGemma v3 corpus.  The
no-action population comes from the public MASSIVE/PRESTO rows that have no
mapped BAXY family.  Every row receives the same symmetric frozen-ranker + E5
candidate policy used by Goal 03; the sealed evaluation is used only as an
exact-text exclusion set and is never copied into either output.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
from scipy.sparse import hstack


REPO = Path(__file__).resolve().parents[2]
for root in (REPO, REPO / "src", REPO / "experiments/functiongemma_selector"):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from baxy_mind.planner import PlannerCatalog, _tokens, _tool_lexical_score  # noqa: E402
from baxy_mind.router import SemanticEncoder  # noqa: E402
from experiments.mind_router_spike.probe_operation_shortlist_current_review import (  # noqa: E402
    _resources,
)
from scripts.measure_mind_budget import (  # noqa: E402
    current_core_catalog_snapshot,
    discover_core,
)
from selector_common import (  # noqa: E402
    NO_ACTION_OPERATION,
    normalize_text,
    selection_tools,
)


POSITIVE_SOURCE = REPO / "artifacts/research/functiongemma_training_corpus.v3.jsonl"
OOS_SOURCE = REPO / "tests/data/turn_evidence_runtime.v1.jsonl"
SEALED = REPO / "artifacts/development/goal03_fresh_paraphrase_corpus.v1.jsonl"
RANKER_ASSETS = REPO.parent / "BAXY/artifacts/research/operation_shortlist_v3"
EXPECTED_RANKER_WEIGHTS_SHA256 = (
    "63de7aaeb52cf14e034828315656343b96b5125a33c48e6a5d6d1183bbc14d12"
)
DEFAULT_OUTPUT_DIR = Path(r"D:\BAXYRuntime\experiments\functiongemma-current-union-v1")
DEFAULT_REPORT = (
    REPO / "artifacts/development/goal03_functiongemma_current_union_corpus_v26.json"
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


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _configure_tools(capabilities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": str(row["name"]).replace(".", "_"),
                "canonical_name": str(row["name"]),
                "description": str(row["description"]),
                "parameters": row["argumentsSchema"],
                "risk": str(row["risk"]),
            },
        }
        for row in capabilities
    ]


def _public_oos_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            provenance = payload.get("provenance")
            if not isinstance(provenance, dict) or provenance.get("dataset") not in {
                "MASSIVE v1.1",
                "PRESTO v1",
            }:
                continue
            text = payload.get("text")
            families = payload.get("families")
            if not isinstance(text, str) or not isinstance(families, list):
                raise ValueError(f"invalid public row {line_number}")
            if families:
                continue
            rows.append(
                {
                    "case_id": f"public-oos-{payload.get('source_id') or line_number}",
                    "text": text,
                    "operation": NO_ACTION_OPERATION,
                    "language": "public-multilingual",
                    "source": f"public-oos:{provenance.get('dataset')}",
                }
            )
    return rows


def _stable_bucket(text: str, modulus: int = 10) -> int:
    return int(hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()[:8], 16) % modulus


def _split_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_operation: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        by_operation[str(row["operation"])].append(row)
    train: list[dict[str, Any]] = []
    validation: list[dict[str, Any]] = []
    for operation, group in sorted(by_operation.items()):
        ordered = sorted(
            group,
            key=lambda row: hashlib.sha256(
                normalize_text(str(row["text"])).encode("utf-8")
            ).hexdigest(),
        )
        if operation == NO_ACTION_OPERATION:
            held = [row for row in ordered if _stable_bucket(str(row["text"])) == 0]
            held_ids = {id(row) for row in held}
            validation.extend(held)
            train.extend(row for row in ordered if id(row) not in held_ids)
            continue
        holdout_count = max(1, min(len(ordered) - 1, round(len(ordered) * 0.1)))
        validation.extend(ordered[:holdout_count])
        train.extend(ordered[holdout_count:])
    return train, validation


def _e5_rankings(
    texts: list[str], planner: PlannerCatalog, encoder: SemanticEncoder, batch_size: int
) -> list[list[str]]:
    tools = planner.tools
    vectors = np.asarray(planner._tool_vectors, dtype=np.float32)  # type: ignore[attr-defined]
    rankings: list[list[str]] = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        queries = np.asarray(encoder.encode(batch, prefix="query"), dtype=np.float32)
        matrix = queries @ vectors.T
        for text, raw in zip(batch, matrix, strict=True):
            lowest = float(raw.min())
            span = float(raw.max()) - lowest
            scaled = (raw - lowest) / span if span > 0 else np.zeros_like(raw)
            lexical = _tokens(text)
            scored = sorted(
                zip(tools, scaled, strict=True),
                key=lambda item: (
                    float(item[1])
                    + min(_tool_lexical_score(lexical, item[0]), 1.0) * 0.12
                    + (
                        0.06
                        if lexical & _tokens(item[0].name.rsplit(".", 1)[-1])
                        else 0.0
                    ),
                    -len(item[0].required),
                    item[0].name,
                ),
                reverse=True,
            )
            rankings.append([item[0].name for item in scored])
    return rankings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--batch-size", type=int, default=128)
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty {output_dir}")
    if _sha256(SEALED) != EXPECTED_SEALED_SHA256:
        raise RuntimeError("sealed Goal 03 corpus identity changed")
    if _sha256(RANKER_ASSETS / "operation_shortlist.v1.weights.npz") != (
        EXPECTED_RANKER_WEIGHTS_SHA256
    ):
        raise RuntimeError("inherited frozen ranker identity changed")

    sealed_norm = {normalize_text(str(row["text"])) for row in _read_jsonl(SEALED)}
    capabilities, _, _ = current_core_catalog_snapshot(discover_core(None))
    catalog = {str(row["name"]): row for row in capabilities}

    positives: list[dict[str, Any]] = []
    skipped_retired = 0
    for source in _read_jsonl(POSITIVE_SOURCE):
        operation = str(source["operation"])
        if operation == NO_ACTION_OPERATION:
            continue
        if operation not in catalog:
            skipped_retired += 1
            continue
        if normalize_text(str(source["text"])) in sealed_norm:
            continue
        positives.append(
            {
                "case_id": source["case_id"],
                "text": source["text"],
                "operation": operation,
                "language": source.get("language") or "unknown",
                "source": source.get("source") or "functiongemma-v3",
            }
        )
    negatives = [
        row
        for row in _public_oos_rows(OOS_SOURCE)
        if normalize_text(str(row["text"])) not in sealed_norm
    ]

    # Positive labels win any normalized-text conflict.  This avoids teaching
    # no_action for a request that the reviewed current-catalog corpus serves.
    positive_norm = {normalize_text(str(row["text"])) for row in positives}
    dedup: dict[str, dict[str, Any]] = {
        normalize_text(str(row["text"])): row for row in positives
    }
    negative_conflicts = 0
    for row in negatives:
        key = normalize_text(str(row["text"]))
        if not key or key in dedup:
            negative_conflicts += int(key in positive_norm)
            continue
        dedup[key] = row
    rows = list(dedup.values())
    texts = [str(row["text"]) for row in rows]

    words, characters, classes, coefficients, intercept = _resources(RANKER_ASSETS)
    features = hstack((words.transform(texts), characters.transform(texts)), format="csr")
    ranker_scores = np.asarray(features @ coefficients.T + intercept)
    ranker_rankings = [
        [classes[index] for index in np.argsort(-ranker_scores[row_index])]
        for row_index in range(len(rows))
    ]

    encoder = SemanticEncoder(device="cpu")
    planner = PlannerCatalog(_configure_tools(capabilities), encoder=encoder.encode)
    e5_rankings = _e5_rankings(texts, planner, encoder, args.batch_size)

    built: list[dict[str, Any]] = []
    positive_retrieved = 0
    forced_positive = 0
    candidate_counts: list[int] = []
    for source, ranker, e5 in zip(rows, ranker_rankings, e5_rankings, strict=True):
        candidates = [
            name
            for name in dict.fromkeys([*ranker[:14], *e5[:14]])
            if name in catalog
        ]
        operation = str(source["operation"])
        retrieved = operation == NO_ACTION_OPERATION or operation in candidates
        if operation != NO_ACTION_OPERATION:
            positive_retrieved += int(retrieved)
            if not retrieved:
                forced_positive += 1
                candidates = [*candidates[:27], operation]
        candidates = list(dict.fromkeys(candidates))[:28]
        candidate_counts.append(len(candidates))
        built.append(
            {
                "schema": "baxy.functiongemma-current-union-row.v1",
                **source,
                "balance_key": operation,
                "retrieved_before_force": retrieved,
                "candidate_operations": candidates,
                "tools": selection_tools(catalog, [*candidates, NO_ACTION_OPERATION]),
            }
        )

    train, validation = _split_rows(built)
    output_dir.mkdir(parents=True, exist_ok=False)
    train_path = output_dir / "train.jsonl"
    validation_path = output_dir / "validation.jsonl"
    _write_jsonl(train_path, train)
    _write_jsonl(validation_path, validation)

    def counts(population: list[dict[str, Any]]) -> dict[str, int]:
        values = collections.Counter(str(row["operation"]) for row in population)
        return {
            "rows": len(population),
            "positive": len(population) - values[NO_ACTION_OPERATION],
            "no_action": values[NO_ACTION_OPERATION],
            "operations": len(values) - int(NO_ACTION_OPERATION in values),
        }

    result = {
        "schema": "baxy.goal03-functiongemma-current-union-corpus.v1",
        "sources": {
            "positive": {"path": str(POSITIVE_SOURCE), "sha256": _sha256(POSITIVE_SOURCE)},
            "public_oos": {"path": str(OOS_SOURCE), "sha256": _sha256(OOS_SOURCE)},
            "sealed_exclusion_only": {"path": str(SEALED), "sha256": _sha256(SEALED)},
            "ranker_manifest_sha256": _sha256(
                RANKER_ASSETS / "operation_shortlist.v1.manifest.json"
            ),
            "ranker_weights": {
                "path": str(RANKER_ASSETS / "operation_shortlist.v1.weights.npz"),
                "sha256": EXPECTED_RANKER_WEIGHTS_SHA256,
            },
        },
        "outputs": {
            "train": {"path": str(train_path), "sha256": _sha256(train_path), **counts(train)},
            "validation": {
                "path": str(validation_path),
                "sha256": _sha256(validation_path),
                **counts(validation),
            },
        },
        "catalog_operations": len(catalog),
        "skipped_retired_positive_rows": skipped_retired,
        "negative_conflicts_with_positive": negative_conflicts,
        "exact_normalized_overlap_with_sealed": sum(
            normalize_text(str(row["text"])) in sealed_norm for row in built
        ),
        "positive_retrieval": {
            "retrieved_before_force": positive_retrieved,
            "rows": len(positives),
            "forced_for_training": forced_positive,
        },
        "candidate_count": {
            "min": min(candidate_counts),
            "mean": sum(candidate_counts) / len(candidate_counts),
            "max": max(candidate_counts),
        },
        "split_policy": (
            "per-operation deterministic SHA holdout; public no_action hash bucket 0/10"
        ),
        "authority": {
            "development_only": True,
            "sealed_rows_copied": 0,
            "providers_enabled": False,
            "effects_executed": 0,
            "runtime_manifest_changed": False,
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
