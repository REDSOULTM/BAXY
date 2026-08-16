"""Build disjoint positive/hard-negative data for candidate verification."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from benchmark_family_arbiter import DEFAULT_CACHE, _encode, _normal, _split
from selector_common import (
    NO_ACTION_OPERATION,
    REPO,
    catalog_by_name,
    read_jsonl,
    selection_tools,
    sha256,
    write_jsonl,
)

SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

DEFAULT_CORPUS = REPO / "artifacts" / "research" / "functiongemma_training_corpus.v1.jsonl"
DEFAULT_TRAIN = REPO / "artifacts" / "research" / "functiongemma_verifier_train.v1.jsonl"
DEFAULT_VALIDATION = REPO / "artifacts" / "research" / "functiongemma_verifier_validation.v1.jsonl"
DEFAULT_REPORT = REPO / "artifacts" / "research" / "functiongemma_verifier_corpus.v1.report.json"
DEFAULT_TOOL_CACHE = REPO / "artifacts" / "research" / "functiongemma_verifier_tool_e5.v1.npz"
EXACT_DEV = REPO / "experiments" / "mind_router_spike" / "data" / "exact_operation_development.v1.jsonl"


def _encode_tools(documents: list[str], cache: Path, catalog_hash: str) -> np.ndarray:
    if cache.is_file():
        with np.load(cache, allow_pickle=False) as saved:
            if str(saved["catalog_hash"].item()) == catalog_hash and int(saved["rows"].item()) == len(documents):
                return np.asarray(saved["embeddings"], dtype=np.float32)
    from baxy_mind.router import ProcessIntentRouter

    inherited = os.environ.get("PYTHONPATH", "")
    os.environ["PYTHONPATH"] = str(SRC) + (os.pathsep + inherited if inherited else "")
    router = ProcessIntentRouter()
    try:
        if not router.try_ready(180.0):
            raise RuntimeError("the attested E5 worker did not become ready")
        matrix = router.encode(documents, timeout=180.0).astype(np.float32, copy=False)
    finally:
        router.close()
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        cache,
        embeddings=matrix,
        catalog_hash=np.asarray(catalog_hash),
        rows=np.asarray(len(documents), dtype=np.int64),
    )
    return matrix


def _ordered_tools(catalog: dict[str, dict[str, Any]], candidate: str, identity: str) -> list[dict[str, Any]]:
    order = [candidate, NO_ACTION_OPERATION]
    if hashlib.sha256(identity.encode("utf-8")).digest()[0] & 1:
        order.reverse()
    return selection_tools(catalog, order)


def _pairs(
    rows: list[dict[str, Any]],
    indexes: list[int],
    catalog: dict[str, dict[str, Any]],
    operations: list[str],
    tool_matrix: np.ndarray,
    message_matrix: np.ndarray,
    split: str,
) -> list[dict[str, Any]]:
    operation_index = {operation: index for index, operation in enumerate(operations)}
    output: list[dict[str, Any]] = []
    for row_index in indexes:
        row = rows[row_index]
        expected = str(row["operation"])
        family = expected.split(".", 1)[0]
        similarities = tool_matrix @ message_matrix[row_index]
        same = [
            operation
            for operation in operations
            if operation != expected and operation.split(".", 1)[0] == family
        ]
        cross = [
            operation for operation in operations if operation.split(".", 1)[0] != family
        ]
        negatives: list[tuple[str, str]] = []
        if same:
            negatives.append((max(same, key=lambda value: float(similarities[operation_index[value]])), "hard-intra"))
        negatives.append((max(cross, key=lambda value: float(similarities[operation_index[value]])), "hard-cross"))
        candidates = [(expected, expected, "positive")] + [
            (candidate, NO_ACTION_OPERATION, kind) for candidate, kind in negatives
        ]
        for candidate, target, kind in candidates:
            identity = f"{row['case_id']}\0{candidate}\0{kind}"
            case_id = "verify-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]
            output.append(
                {
                    "schema": "baxy.functiongemma-verifier-row.v1",
                    "case_id": case_id,
                    "text": str(row["text"]),
                    "language": row.get("language"),
                    "operation": target,
                    "candidate_operation": candidate,
                    "balance_key": f"{candidate}|{'positive' if target == candidate else 'negative'}",
                    "verdict": "accept" if target == candidate else "reject",
                    "negative_kind": None if target == candidate else kind,
                    "base_operation": expected,
                    "base_case_id": row["case_id"],
                    "base_source": row.get("source"),
                    "source": f"candidate-verifier-v1:{split}",
                    "tools": _ordered_tools(catalog, candidate, identity),
                }
            )
    return output


def run(args: argparse.Namespace) -> dict[str, Any]:
    catalog = catalog_by_name()
    rows = [row for row in read_jsonl(args.corpus) if str(row.get("operation")) in catalog]
    fit, validation = _split(rows)
    texts = [str(row["text"]) for row in rows]
    message_matrix = _encode(texts, args.corpus, args.embedding_cache)
    operations = sorted(catalog)
    documents = [
        f"{operation}. {catalog[operation].get('description') or operation}"
        for operation in operations
    ]
    catalog_hash = hashlib.sha256(
        json.dumps(
            [(operation, catalog[operation].get("description")) for operation in operations],
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    tool_matrix = _encode_tools(documents, args.tool_embedding_cache, catalog_hash)
    train_rows = _pairs(rows, fit, catalog, operations, tool_matrix, message_matrix, "train")
    validation_rows = _pairs(rows, validation, catalog, operations, tool_matrix, message_matrix, "validation")
    train_texts = {_normal(str(row["text"])) for row in train_rows}
    validation_texts = {_normal(str(row["text"])) for row in validation_rows}
    dev_texts = {_normal(str(row["text"])) for row in read_jsonl(EXACT_DEV)}
    if train_texts & validation_texts or (train_texts | validation_texts) & dev_texts:
        raise RuntimeError("verifier corpus violates its text isolation contract")
    write_jsonl(args.train, train_rows)
    write_jsonl(args.validation, validation_rows)
    report = {
        "schema": "baxy.functiongemma-verifier-corpus.v1",
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": str(args.corpus),
        "source_sha256": sha256(args.corpus),
        "catalog_hash": catalog_hash,
        "base_rows": len(rows),
        "fit_base_rows": len(fit),
        "validation_base_rows": len(validation),
        "train_rows": len(train_rows),
        "validation_rows": len(validation_rows),
        "normalised_train_validation_overlap": 0,
        "normalised_exact_dev_overlap": 0,
        "train": {"path": str(args.train), "sha256": sha256(args.train)},
        "validation": {"path": str(args.validation), "sha256": sha256(args.validation)},
        "effects_executed": 0,
        "runtime_manifest_changed": False,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--embedding-cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--tool-embedding-cache", type=Path, default=DEFAULT_TOOL_CACHE)
    parser.add_argument("--train", type=Path, default=DEFAULT_TRAIN)
    parser.add_argument("--validation", type=Path, default=DEFAULT_VALIDATION)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    run(parser.parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
