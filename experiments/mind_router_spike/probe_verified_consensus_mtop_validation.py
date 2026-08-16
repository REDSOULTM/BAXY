"""Validate a conservative three-head consensus cascade outside MTOP R4.

The full-catalog and lexical heads may override the frozen MTOP specialist only
when they agree on one of its authenticated top-three nominations. Otherwise,
the native Qwen selector is called only on disagreements where the lexical
choice is already inside that top three, and it must independently agree.
No plan reaches Core and no provider can execute.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import statistics
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT, ROOT / "src", ROOT / "scripts", Path(__file__).parent):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import numpy as np  # noqa: E402
import torch  # noqa: E402
from scipy.sparse import hstack  # noqa: E402
from transformers import AutoModelForSequenceClassification, AutoTokenizer  # noqa: E402

import measure_turn_policy_v52_mtop_validation as mtop  # noqa: E402
import train_mtop_operation_classifier as trainer  # noqa: E402
from baxy_mind.llm import LlmRuntime  # noqa: E402
from benchmark_native_no_match_tool import _select  # noqa: E402
from probe_operation_shortlist_current_review import _resources  # noqa: E402
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


SPECIALIST = Path(r"D:\BAXYRuntime\experiments\mtop-operation-classifier-v8-mdeberta")
FULL = Path(r"D:\BAXYRuntime\experiments\full-catalog-operation-classifier-v2-mdeberta")
LEXICAL = ROOT / "artifacts/research/operation_shortlist_v3"
R4 = ROOT / "artifacts/fixes/mtop_product_validation_development_r4_current.json"
REPORT = ROOT / "artifacts/research/verified_consensus_mtop_validation_r2.json"
NO_ACTION = "__none__"
ALARM_CANCEL_ACTION = re.compile(
    r"\b(cancel|deactivate|turn off|cancela|desactiva|anula)\b"
)
ALARM_OBJECT = re.compile(r"\b(alarm|alarma)\b")
ALARM_ACTIVE = re.compile(
    r"\b(ringing|sounding|going off|went off|heard|hear you|awake|silence|"
    r"quiet|sonando|suena|sono|oi|despiert|silencia|calla)\b"
)
EXPLICIT_TIME = re.compile(
    r"\b([0-2]?\d[:.]\d\d|a las|at \d|am|pm|manana|tomorrow|monday|lunes)\b"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _score_checkpoint(
    checkpoint: Path,
    texts: list[str],
    batch_size: int,
) -> tuple[list[str], list[list[str]], float]:
    tokenizer = AutoTokenizer.from_pretrained(checkpoint, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        checkpoint,
        local_files_only=True,
    ).cuda().eval()
    labels = [
        str(model.config.id2label[index]) for index in range(model.config.num_labels)
    ]
    batches = []
    started = time.perf_counter()
    with torch.inference_mode():
        for offset in range(0, len(texts), batch_size):
            encoded = tokenizer(
                texts[offset : offset + batch_size],
                padding=True,
                truncation=True,
                max_length=96,
                return_tensors="pt",
            )
            encoded = {key: value.cuda(non_blocking=True) for key, value in encoded.items()}
            with torch.autocast(device_type="cuda", dtype=torch.float16):
                logits = model(**encoded).logits
            batches.append(logits.float().cpu().numpy())
    elapsed = time.perf_counter() - started
    scores = np.concatenate(batches, axis=0)
    order = np.argsort(-scores, axis=1)
    rankings = [
        [labels[int(index)] for index in row]
        for row in order
    ]
    del model
    torch.cuda.empty_cache()
    return labels, rankings, elapsed


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    latencies = [float(row["selector_seconds"]) for row in rows if row["selector_called"]]
    return {
        "cases": len(rows),
        "baseline_correct": sum(bool(row["baseline_correct"]) for row in rows),
        "baseline_accuracy": round(
            sum(bool(row["baseline_correct"]) for row in rows) / len(rows),
            6,
        ),
        "final_correct": sum(bool(row["final_correct"]) for row in rows),
        "final_accuracy": round(
            sum(bool(row["final_correct"]) for row in rows) / len(rows),
            6,
        ),
        "corrections": sum(
            not row["baseline_correct"] and row["final_correct"] for row in rows
        ),
        "regressions": sum(
            row["baseline_correct"] and not row["final_correct"] for row in rows
        ),
        "full_lexical_overrides": sum(
            row["gate"] == "full+lexical" for row in rows
        ),
        "native_lexical_overrides": sum(
            row["gate"] == "native+lexical" for row in rows
        ),
        "notification_contract_overrides": sum(
            row["gate"] == "notification-contract" for row in rows
        ),
        "native_selector_calls": len(latencies),
        "native_selector_call_rate": round(len(latencies) / len(rows), 6),
        "native_selector_seconds": (
            {
                "p50": round(statistics.median(latencies), 6),
                "p95": round(sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)], 6),
            }
            if latencies
            else None
        ),
    }


def _normal_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )


def _family(operation: str) -> str:
    return operation.split(".", 1)[0]


def _notification_cancel_contract(text: str) -> bool:
    normalized = _normal_text(text)
    return bool(
        ALARM_CANCEL_ACTION.search(normalized)
        and ALARM_OBJECT.search(normalized)
        and not ALARM_ACTIVE.search(normalized)
        and not EXPLICIT_TIME.search(normalized)
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.report.exists():
        raise RuntimeError(f"refusing to overwrite report: {args.report}")
    development, manifest, identity = mtop._load_development(
        mtop.DEVELOPMENT_CORPUS,
        mtop.MANIFEST,
    )
    rows = [
        (row, str(label))
        for row in development
        for label in [trainer.operation_label(row)]
        if row["split"] == "validation" and label is not None
    ]
    texts = [str(row["text"]) for row, _label in rows]
    specialist_labels, specialist_rankings, specialist_seconds = _score_checkpoint(
        args.specialist,
        texts,
        args.batch_size,
    )
    full_labels, full_rankings, full_seconds = _score_checkpoint(
        args.full,
        texts,
        args.batch_size,
    )
    words, characters, lexical_labels, coefficients, intercept = _resources(
        args.lexical
    )
    lexical_matrix = hstack(
        (words.transform(texts), characters.transform(texts)),
        format="csr",
    )
    lexical_scores = np.asarray(lexical_matrix @ coefficients.T + intercept)
    lexical_rankings = [
        [lexical_labels[int(index)] for index in np.argsort(-row)]
        for row in lexical_scores
    ]
    expected_labels = {label for _row, label in rows}
    if not expected_labels <= set(specialist_labels):
        raise RuntimeError("validation escaped specialist label space")
    if not (expected_labels - {NO_ACTION}) <= set(full_labels):
        raise RuntimeError("validation escaped full-catalog label space")

    r4_source = json.loads(R4.read_text(encoding="utf-8"))
    r4_ids = {str(row["source_id"]) for row in r4_source["samples"]}
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
    environment = sidecar_environment(
        runtime_config,
        gpu_layers=runtime_config.gpu_layers,
        llm_http_timeout=PROFILE_LIMITS["gpu"]["llm_http"],
    )
    os.environ.update(environment)
    runtime = LlmRuntime()
    results = []
    try:
        for index, (row, expected) in enumerate(rows):
            specialist = specialist_rankings[index]
            full = full_rankings[index]
            lexical = lexical_rankings[index]
            baseline = specialist[0]
            chosen = baseline
            gate = "specialist"
            selector_called = False
            selector_seconds = 0.0
            shortlist = [value for value in specialist[:3] if value != NO_ACTION]
            if (
                baseline != NO_ACTION
                and _family(baseline) == "notification"
                and "notification.cancel.latest" in shortlist
                and _notification_cancel_contract(str(row["text"]))
            ):
                chosen = "notification.cancel.latest"
                gate = "notification-contract"
            elif (
                baseline != NO_ACTION
                and full[0] == lexical[0]
                and full[0] != baseline
                and full[0] in shortlist
                and _family(full[0]) == _family(baseline)
            ):
                chosen = full[0]
                gate = "full+lexical"
            elif (
                baseline != NO_ACTION
                and lexical[0] != baseline
                and lexical[0] != NO_ACTION
                and lexical[0] in shortlist
                and _family(lexical[0]) == _family(baseline)
            ):
                selector_called = True
                started = time.perf_counter()
                selected, no_match = _select(
                    runtime,
                    str(row["text"]),
                    [capability_by_name[name] for name in shortlist],
                    no_match_mode="sentinel",
                    tool_choice="required",
                )
                selector_seconds = time.perf_counter() - started
                if not no_match and selected == (lexical[0],):
                    chosen = lexical[0]
                    gate = "native+lexical"
            results.append(
                {
                    "source_id": row["source_id"],
                    "in_r4": str(row["source_id"]) in r4_ids,
                    "expected": expected,
                    "specialist_top3": specialist[:3],
                    "full_top1": full[0],
                    "lexical_top1": lexical[0],
                    "chosen": chosen,
                    "gate": gate,
                    "selector_called": selector_called,
                    "selector_seconds": round(selector_seconds, 6),
                    "baseline_correct": baseline == expected,
                    "final_correct": chosen == expected,
                }
            )
    finally:
        runtime.close()

    r4_rows = [row for row in results if row["in_r4"]]
    non_r4_rows = [row for row in results if not row["in_r4"]]
    report = {
        "schema": "baxy.verified-consensus-mtop-validation.v2",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "opened_development_validation_only_test_and_blind_reserve_sealed",
        "authority": "candidate_selection_only_no_core_plan_or_provider",
        "effects_executed": 0,
        "contains_utterance_text": False,
        "sources": {
            "mtop_development_sha256": identity.corpus.sha256,
            "mtop_manifest_sha256": identity.manifest.sha256,
            "mtop_map_sha256": manifest["source"]["map_sha256"],
            "mtop_test_content_read": False,
            "baxy_blind_reserve_opened": False,
            "specialist_config_sha256": _sha256(args.specialist / "config.json"),
            "full_config_sha256": _sha256(args.full / "config.json"),
            "lexical_manifest_sha256": _sha256(
                args.lexical / "operation_shortlist.v1.manifest.json"
            ),
            "r4_selected_identity_sha256": r4_source["source"][
                "selected_identity_sha256"
            ],
            "runtime": public_runtime_identity(runtime_config),
        },
        "classifier_seconds": {
            "specialist_batch": round(specialist_seconds, 6),
            "full_batch": round(full_seconds, 6),
        },
        "configuration": {
            "no_action_override_allowed": False,
            "cross_family_override_allowed": False,
            "native_requires_lexical_top1_inside_specialist_top3": True,
            "full_requires_lexical_top1_and_specialist_top3": True,
            "notification_cancel_requires_no_active_or_explicit_time_cue": True,
        },
        "all_validation": _metrics(results),
        "r4_subset": _metrics(r4_rows),
        "non_r4_validation": _metrics(non_r4_rows),
        "records": results,
    }
    mtop._assert_input_identity_stable(identity)
    write_json_atomic(args.report, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--specialist", type=Path, default=SPECIALIST)
    parser.add_argument("--full", type=Path, default=FULL)
    parser.add_argument("--lexical", type=Path, default=LEXICAL)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--runtime-manifest", type=Path, default=DEFAULT_RUNTIME_MANIFEST)
    parser.add_argument("--batch-size", type=int, default=128)
    args = parser.parse_args()
    args.specialist = args.specialist.resolve(strict=True)
    args.full = args.full.resolve(strict=True)
    args.lexical = args.lexical.resolve(strict=True)
    args.report = args.report.resolve()
    result = run(args)
    print(
        json.dumps(
            {
                "all_validation": result["all_validation"],
                "r4_subset": result["r4_subset"],
                "non_r4_validation": result["non_r4_validation"],
                "classifier_seconds": result["classifier_seconds"],
                "report": str(args.report),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
