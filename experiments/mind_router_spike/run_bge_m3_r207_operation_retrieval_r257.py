"""Run the sealed query-disjoint BGE-M3 operation-retrieval CUDA probe once."""

from __future__ import annotations

import gc
import hashlib
import json
import sys
import time
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from experiments.mind_router_spike import preregister_bge_m3_r207_operation_retrieval_r256 as r256


R207 = REPO / "artifacts/development/r207_cross_encoder_pairs.jsonl"
CATALOG = REPO / "artifacts/development/current_core_catalog_snapshot_r219.json"
OUTPUT = REPO / "artifacts/development/bge_m3_r207_operation_retrieval_r257.json"
BATCH_SIZE = 16
INSIDE_COUNT = 256
TOP_KS = (1, 2, 5, 8)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normal(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def catalogue_operations() -> list[str]:
    capabilities = json.loads(CATALOG.read_text(encoding="utf-8"))["catalogue"]["capabilities"]
    operations = sorted(str(row["name"]) for row in capabilities)
    if len(operations) != 174 or len(set(operations)) != len(operations):
        raise RuntimeError("R257 requires the 174-operation typed catalogue R219")
    return operations


def source_rows(operations: set[str]) -> tuple[dict[str, tuple[str, str]], set[str]]:
    by_query: dict[str, tuple[str, str]] = {}
    excluded_operations: set[str] = set()
    for line in R207.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["target"] != 1:
            continue
        operation = str(row["operation"])
        if operation not in operations:
            excluded_operations.add(operation)
            continue
        query = str(row["query"])
        normalized = normal(query)
        previous = by_query.setdefault(normalized, (query, operation))
        if previous[1] != operation:
            raise RuntimeError("R257 source contains one normalized query with conflicting typed operations")
    if not by_query:
        raise RuntimeError("R257 found no typed R207 positive rows")
    return by_query, excluded_operations


def split_rows(operations: list[str]) -> tuple[list[tuple[str, str]], list[tuple[str, str]], list[str], list[str]]:
    known, excluded = source_rows(set(operations))
    by_operation: dict[str, list[tuple[str, tuple[str, str]]]] = defaultdict(list)
    for normalized, row in known.items():
        by_operation[row[1]].append((normalized, row))
    represented = sorted(by_operation)
    missing = sorted(set(operations) - set(represented))
    selected = [
        sorted(by_operation[operation], key=lambda item: key(item[0] + "\0" + operation))[0]
        for operation in represented
    ]
    selected_normalized = {normalized for normalized, _ in selected}
    remainder = sorted(
        ((normalized, row) for normalized, row in known.items() if normalized not in selected_normalized),
        key=lambda item: key(item[0] + "\0" + item[1][1]),
    )
    evaluation = [*selected, *remainder[: INSIDE_COUNT - len(selected)]]
    if len(evaluation) != INSIDE_COUNT:
        raise RuntimeError("R257 requires at least 256 typed, normalized R207 positive queries")
    evaluation_normalized = {normalized for normalized, _ in evaluation}
    training = [row for normalized, row in known.items() if normalized not in evaluation_normalized]
    if evaluation_normalized & {normal(query) for query, _ in training}:
        raise RuntimeError("R257 query-disjoint split was violated")
    if set(operation for _, operation in training) != set(represented):
        raise RuntimeError("R257 training lacks an operation with an evaluation query")
    return (
        sorted(training, key=lambda row: key(normal(row[0]) + "\0" + row[1])),
        [row for _, row in evaluation],
        missing,
        sorted(excluded),
    )


def embed(model: Any, tokenizer: Any, texts: list[str], device: Any) -> np.ndarray:
    import torch

    chunks: list[np.ndarray] = []
    model.eval()
    with torch.inference_mode():
        for start in range(0, len(texts), BATCH_SIZE):
            encoded = tokenizer(
                texts[start : start + BATCH_SIZE],
                padding=True,
                truncation=True,
                max_length=128,
                return_tensors="pt",
            ).to(device)
            with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
                hidden = model(**encoded).last_hidden_state.float()
            mask = encoded["attention_mask"].unsqueeze(-1)
            vectors = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp_min(1)
            chunks.append(torch.nn.functional.normalize(vectors, p=2, dim=1).cpu().numpy())
    return np.concatenate(chunks, axis=0).astype(np.float32, copy=False)


def recall_summary(ranks: np.ndarray, expected: list[str], operations: list[str]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    operation_rows: dict[str, list[int]] = defaultdict(list)
    family_rows: dict[str, list[int]] = defaultdict(list)
    for index, operation in enumerate(expected):
        operation_rows[operation].append(index)
        family_rows[operation.split(".", 1)[0]].append(index)

    def coverage(groups: dict[str, list[int]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for name in sorted(groups):
            row_indexes = np.asarray(groups[name])
            result[name] = {
                "evaluation_queries": int(len(row_indexes)),
                **{
                    f"recall_top_{top_k}": float((ranks[row_indexes] <= top_k).mean())
                    for top_k in TOP_KS
                },
            }
        return result

    recalls = {f"recall_top_{top_k}": float((ranks <= top_k).mean()) for top_k in TOP_KS}
    operation_coverage = coverage(operation_rows)
    family_coverage = coverage(family_rows)
    if set(operation_coverage) - set(operations):
        raise RuntimeError("R257 evaluated an operation absent from the typed catalogue")
    return recalls, operation_coverage, family_coverage


def run() -> dict[str, Any]:
    preregistration = json.loads(r256.OUTPUT.read_text(encoding="utf-8"))
    if preregistration != r256.build() or OUTPUT.exists():
        raise RuntimeError("R257 preregistration identity changed or result already exists")
    import torch
    from transformers import AutoModel, AutoTokenizer

    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError("R257 requires CUDA BF16")
    torch.cuda.reset_peak_memory_stats()
    device = torch.device("cuda")
    operations = catalogue_operations()
    training, evaluation, missing_operations, excluded_operations = split_rows(operations)
    load_started = time.monotonic()
    tokenizer = AutoTokenizer.from_pretrained(str(r256.r232.r231.CANDIDATE_ROOT), local_files_only=True)
    model = AutoModel.from_pretrained(str(r256.r232.r231.CANDIDATE_ROOT), local_files_only=True).to(device)
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    model_load_seconds = time.monotonic() - load_started
    embed_training_started = time.monotonic()
    training_vectors = embed(model, tokenizer, [query for query, _ in training], device)
    embedding_training_seconds = time.monotonic() - embed_training_started
    embed_evaluation_started = time.monotonic()
    evaluation_vectors = embed(model, tokenizer, [query for query, _ in evaluation], device)
    embedding_evaluation_seconds = time.monotonic() - embed_evaluation_started
    if not np.isfinite(training_vectors).all() or not np.isfinite(evaluation_vectors).all():
        raise RuntimeError("R257 produced non-finite frozen embeddings")
    ranking_started = time.monotonic()
    scores_by_exemplar = evaluation_vectors @ training_vectors.T
    operation_indexes = {operation: index for index, operation in enumerate(operations)}
    scores_by_operation = np.full((len(evaluation), len(operations)), -np.inf, dtype=np.float32)
    for exemplar_index, (_, operation) in enumerate(training):
        operation_index = operation_indexes[operation]
        scores_by_operation[:, operation_index] = np.maximum(
            scores_by_operation[:, operation_index], scores_by_exemplar[:, exemplar_index]
        )
    ordered = np.argsort(-scores_by_operation, axis=1, kind="stable")
    expected_indexes = np.asarray([operation_indexes[operation] for _, operation in evaluation])
    ranks = (ordered == expected_indexes[:, None]).argmax(axis=1) + 1
    ranking_seconds = time.monotonic() - ranking_started
    recalls, per_operation, per_family = recall_summary(
        ranks, [operation for _, operation in evaluation], operations
    )
    peak_mib = float(torch.cuda.max_memory_allocated(device) / (1024 * 1024))
    del model
    gc.collect()
    torch.cuda.empty_cache()
    all_top_8 = recalls["recall_top_8"] == 1.0
    all_top_2 = recalls["recall_top_2"] == 1.0
    verdict = (
        "rejected_development_operation_retrieval_recall"
        if not all_top_8
        else "development_retrieval_signal_only_catalogue_coverage_incomplete"
    )
    return {
        "schema": "baxy.bge-m3-r207-operation-retrieval.r257-result.v1",
        "authority": "isolated_cuda_development_probe_not_runtime_oos_or_blind_holdout_measurement",
        "verdict": verdict,
        "candidate": {
            "base": "BAAI/bge-m3@5617a9f61b028005a4858fdac845db406aefb181",
            "device": "cuda_bf16",
            "ranking": "maximum cosine against query-disjoint positive R207 exemplars per typed operation",
            "threshold_or_domain_gate": None,
        },
        "development_population": {
            "source": "R207 typed positive rows only",
            "training_queries": len(training),
            "evaluation_queries": len(evaluation),
            "catalogue_operations": len(operations),
            "operations_with_r207_exemplars": len(operations) - len(missing_operations),
            "catalogue_operations_without_r207_exemplar": missing_operations,
            "source_positive_operations_excluded_as_not_typed_catalogue_operations": excluded_operations,
            "query_disjoint": True,
            "texts_retained": False,
            "source_ids_retained": False,
        },
        "observed": {
            **recalls,
            "per_operation_coverage": per_operation,
            "per_family_coverage": per_family,
            "operations_with_all_evaluation_queries_in_top_8": int(
                sum(row["recall_top_8"] == 1.0 for row in per_operation.values())
            ),
            "families_with_all_evaluation_queries_in_top_8": int(
                sum(row["recall_top_8"] == 1.0 for row in per_family.values())
            ),
            "minimum_useful_comparison": {
                "top_8_supports_no_loss_necessary_condition_on_covered_population": all_top_8,
                "top_2_supports_no_loss_necessary_condition_on_covered_population": all_top_2,
                "global_catalogue_shortlist_supported": False,
                "reason_global_catalogue_shortlist_not_supported": "R207 has no positive exemplar for every typed catalogue operation and this probe does not measure OOS, decision, vetoes, visible text or the blind path.",
            },
        },
        "latency_gpu": {
            "model_load_seconds": model_load_seconds,
            "embedding_training_seconds": embedding_training_seconds,
            "embedding_evaluation_seconds": embedding_evaluation_seconds,
            "ranking_seconds": ranking_seconds,
            "peak_allocated_mib": peak_mib,
            "batch_size": BATCH_SIZE,
        },
        "constraints": {
            "r228_opened": False,
            "clinc_opened": False,
            "public_holdout_opened": False,
            "registered_runtime_modified": False,
            "providers_enabled": False,
            "effects_executed": 0,
            "opened_v9": False,
            "voice_stt_wake_exercised": False,
        },
        "next_requirement": "A result cannot be integrated or used to shorten the runtime shortlist. A failure rejects this raw retrieval architecture; a covered-population pass still needs complete catalogue exemplars plus separately sealed OOS, raw-decision, veto, visible-text and blind full-path evidence.",
        "identities": {
            "preregistration_sha256": sha256(r256.OUTPUT),
            "r207_sha256": sha256(R207),
            "catalog_sha256": sha256(CATALOG),
            "program_sha256": sha256(Path(__file__)),
        },
    }


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing to overwrite result: {OUTPUT}")
    OUTPUT.write_bytes((json.dumps(run(), ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
