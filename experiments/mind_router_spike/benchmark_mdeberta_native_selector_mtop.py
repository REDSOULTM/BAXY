"""Benchmark an MTOP specialist shortlist followed by the native selector.

Development-only diagnostic.  The frozen mDeBERTa checkpoint runs on CPU and
may only nominate operations present in the authenticated Core catalogue.  The
native llama.cpp selector then chooses from at most three nominations or the
explicit no-match sentinel.  No plan is sent to Core and no provider can run.

The official MTOP test and BAXY blind reserve remain sealed.  The output keeps
source identities, labels, and timings, but never utterance text or model prose.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts", Path(__file__).parent):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import measure_turn_policy_v52_mtop_validation as mtop  # noqa: E402
import train_mtop_operation_classifier as trainer  # noqa: E402
from baxy_mind.llm import LlmRuntime  # noqa: E402
from benchmark_native_no_match_tool import _select  # noqa: E402
from scripts.baxy_runtime_config import (  # noqa: E402
    DEFAULT_RUNTIME_MANIFEST,
    public_runtime_identity,
    resolve_runtime,
)
from scripts.measure_mind_budget import (  # noqa: E402
    DEFAULT_CORE_CANDIDATES,
    PROFILE_LIMITS,
    current_core_catalog_snapshot,
    discover_core,
    sidecar_environment,
    write_json_atomic,
)


DEFAULT_CHECKPOINT = Path(
    r"D:\BAXYRuntime\experiments\mtop-operation-classifier-v8-mdeberta"
)
DEFAULT_SOURCE = (
    REPO / "artifacts/fixes/mtop_product_validation_development_r4_current.json"
)
DEFAULT_OUTPUT = (
    REPO / "artifacts/research/mdeberta_native_selector_mtop_r1.json"
)
NO_ACTION = "__none__"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, int(percentile * len(ordered) + 0.999) - 1))
    return ordered[rank]


def _checkpoint_identity(path: Path) -> dict[str, Any]:
    config = path / "config.json"
    weights = sorted(path.glob("*.safetensors"), key=lambda item: item.name)
    if not weights:
        raise ValueError("the specialist checkpoint has no safetensors weights")
    return {
        "path": str(path.resolve()),
        "config_sha256": _sha256(config),
        "weights": [
            {
                "name": item.name,
                "sha256": _sha256(item),
                "bytes": item.stat().st_size,
            }
            for item in weights
        ],
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    import numpy as np
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    if args.output.exists():
        raise RuntimeError(f"refusing to overwrite result: {args.output}")
    development_rows, manifest, identity = mtop._load_development(
        mtop.DEVELOPMENT_CORPUS,
        mtop.MANIFEST,
    )
    row_by_source = {
        str(row["source_id"]): row
        for row in development_rows
    }
    source = json.loads(args.source.read_text(encoding="utf-8"))
    samples = source.get("samples") if isinstance(source, dict) else None
    if not isinstance(samples, list) or not samples:
        raise ValueError("the product development source has no samples")
    selected_rows: list[tuple[dict[str, Any], dict[str, Any], str]] = []
    for sample in samples:
        source_id = str(sample.get("source_id", ""))
        row = row_by_source.get(source_id)
        if row is None:
            raise ValueError("the product sample escaped hash-bound MTOP development")
        label = trainer.operation_label(row)
        if label is None:
            raise ValueError("an unscorable MTOP projection entered the benchmark")
        if str(sample.get("text")) != str(row["text"]):
            raise ValueError("the product sample text differs from MTOP development")
        selected_rows.append((sample, row, str(label)))

    tokenizer = AutoTokenizer.from_pretrained(
        args.checkpoint,
        local_files_only=True,
    )
    model = AutoModelForSequenceClassification.from_pretrained(
        args.checkpoint,
        local_files_only=True,
    ).to("cpu").eval()
    labels = tuple(
        str(model.config.id2label[index])
        for index in range(model.config.num_labels)
    )
    classifier_started = time.perf_counter()
    score_batches: list[np.ndarray] = []
    with torch.inference_mode():
        for offset in range(0, len(selected_rows), args.batch_size):
            encoded = tokenizer(
                [
                    str(row["text"])
                    for _sample, row, _label in selected_rows[
                        offset : offset + args.batch_size
                    ]
                ],
                padding=True,
                truncation=True,
                max_length=96,
                return_tensors="pt",
            )
            score_batches.append(model(**encoded).logits.float().cpu().numpy())
    classifier_seconds = time.perf_counter() - classifier_started
    scores = np.concatenate(score_batches, axis=0)
    order = np.argsort(-scores, axis=1)
    nominations = [
        tuple(labels[int(index)] for index in row_order[: args.candidates])
        for row_order in order
    ]

    runtime_config = resolve_runtime(manifest_path=args.runtime_manifest)
    capabilities, _, _ = current_core_catalog_snapshot(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES))
    )
    capability_by_name = {
        str(capability["name"]): {
            "name": capability["name"],
            "description": capability["description"],
            "arguments_schema": capability["argumentsSchema"],
        }
        for capability in capabilities
    }
    specialist_operations = set(labels) - {NO_ACTION}
    absent = sorted(specialist_operations - set(capability_by_name))
    if absent:
        raise ValueError(f"specialist labels escaped the Core catalogue: {absent}")

    environment = sidecar_environment(
        runtime_config,
        gpu_layers=runtime_config.gpu_layers,
        llm_http_timeout=PROFILE_LIMITS["gpu"]["llm_http"],
    )
    os.environ.update(environment)
    runtime = LlmRuntime()
    records: list[dict[str, Any]] = []
    try:
        for (sample, row, expected), ranked in zip(
            selected_rows,
            nominations,
            strict=True,
        ):
            offered = tuple(label for label in ranked if label != NO_ACTION)
            candidates = [capability_by_name[label] for label in offered]
            started = time.perf_counter()
            chosen, no_match = _select(
                runtime,
                str(row["text"]),
                candidates,
                no_match_mode="sentinel",
                tool_choice="required",
            )
            selector_seconds = time.perf_counter() - started
            correct = (
                (expected == NO_ACTION and no_match and not chosen)
                or (
                    expected != NO_ACTION
                    and not no_match
                    and chosen == (expected,)
                )
            )
            records.append(
                {
                    "source_id": row["source_id"],
                    "mission_id": row["mission_id"],
                    "locale": row["locale"],
                    "disposition": row["projection"]["disposition"],
                    "expected_operation": expected,
                    "specialist_top": list(ranked),
                    "specialist_recall": expected in ranked,
                    "offered_operations": list(offered),
                    "selected_operations": list(chosen),
                    "selected_no_match": no_match,
                    "correct": correct,
                    "product_r4_exact": bool(sample["assessment"]["exact"]),
                    "selector_seconds": round(selector_seconds, 6),
                }
            )
    finally:
        runtime.close()

    latencies = [float(row["selector_seconds"]) for row in records]
    result = {
        "schema": "baxy.mdeberta-native-selector-mtop-development.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "development_only_mtop_test_and_baxy_blind_reserve_sealed",
        "authority": "raw_selection_only_no_core_plan_or_provider",
        "effects_executed": 0,
        "contains_utterance_text": False,
        "source": {
            "product_probe": str(args.source.relative_to(REPO)),
            "product_probe_sha256": _sha256(args.source),
            "mtop_development_sha256": identity.corpus.sha256,
            "mtop_manifest_sha256": identity.manifest.sha256,
            "mtop_map_sha256": manifest["source"]["map_sha256"],
            "mtop_test_content_read": False,
            "baxy_blind_reserve_opened": False,
            "checkpoint": _checkpoint_identity(args.checkpoint),
            "runtime": public_runtime_identity(runtime_config),
        },
        "configuration": {
            "classifier_device": "cpu",
            "classifier_batch_size": args.batch_size,
            "candidate_limit": args.candidates,
            "native_selector_tool_choice": "required",
            "explicit_no_match": True,
        },
        "metrics": {
            "cases": len(records),
            "product_r4_exact": sum(bool(row["product_r4_exact"]) for row in records),
            "specialist_recall": sum(bool(row["specialist_recall"]) for row in records),
            "specialist_recall_rate": sum(
                bool(row["specialist_recall"]) for row in records
            ) / len(records),
            "combined_correct": sum(bool(row["correct"]) for row in records),
            "combined_accuracy": sum(bool(row["correct"]) for row in records)
            / len(records),
            "fixed_product_errors": sum(
                not row["product_r4_exact"] and row["correct"]
                for row in records
            ),
            "regressed_product_successes": sum(
                row["product_r4_exact"] and not row["correct"]
                for row in records
            ),
            "classifier_batch_seconds": round(classifier_seconds, 6),
            "classifier_seconds_per_case": round(
                classifier_seconds / len(records),
                6,
            ),
            "selector_seconds_p50": statistics.median(latencies),
            "selector_seconds_p95": _percentile(latencies, 0.95),
            "selector_seconds_max": max(latencies),
        },
        "records": records,
    }
    mtop._assert_input_identity_stable(identity)
    write_json_atomic(args.output, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--runtime-manifest", type=Path, default=DEFAULT_RUNTIME_MANIFEST)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--candidates", type=int, default=3, choices=(2, 3, 5))
    args = parser.parse_args()
    result = run(args)
    print(json.dumps(result["metrics"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
