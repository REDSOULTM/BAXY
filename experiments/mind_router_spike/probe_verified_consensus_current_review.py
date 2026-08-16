"""Validate the conservative consensus cascade on current reviewed cases."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT, ROOT / "src", ROOT / "scripts", Path(__file__).parent):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import numpy as np  # noqa: E402
from scipy.sparse import hstack  # noqa: E402

from baxy_mind.llm import LlmRuntime  # noqa: E402
from benchmark_native_no_match_tool import _select  # noqa: E402
from probe_operation_shortlist_current_review import _resources  # noqa: E402
from probe_verified_consensus_mtop_validation import (  # noqa: E402
    FULL,
    LEXICAL,
    NO_ACTION,
    SPECIALIST,
    _family,
    _notification_cancel_contract,
    _score_checkpoint,
    _sha256,
)
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


CORPUS = ROOT / "artifacts/development/current_catalog_review_development.v1.jsonl"
REPORT = ROOT / "artifacts/research/verified_consensus_current_review_r1.json"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _expected(row: dict[str, Any], labels: set[str]) -> frozenset[str] | None:
    accepted = {
        str(operations[0])
        for operations in row["compatible_terminal_operation_sets"]
        if len(operations) == 1 and str(operations[0]) in labels
    }
    if accepted:
        return frozenset(accepted)
    if row["outcome"] in {"conversation", "unsupported"}:
        return frozenset({NO_ACTION})
    return None


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
        "false_actions": sum(
            row["expected"] == [NO_ACTION] and row["chosen"] != NO_ACTION
            for row in rows
        ),
        "selector_calls": len(latencies),
        "selector_call_rate": round(len(latencies) / len(rows), 6),
        "selector_seconds": (
            {
                "p50": round(statistics.median(latencies), 6),
                "maximum": round(max(latencies), 6),
            }
            if latencies
            else None
        ),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    specialist_config = json.loads(
        (args.specialist / "config.json").read_text(encoding="utf-8")
    )
    specialist_labels = {
        str(value) for value in specialist_config["id2label"].values()
    }
    source = _read_jsonl(args.corpus)
    rows = [
        (row, expected)
        for row in source
        for expected in [_expected(row, specialist_labels)]
        if expected is not None
    ]
    texts = [str(row["text"]) for row, _expected_set in rows]
    _, specialist_rankings, specialist_seconds = _score_checkpoint(
        args.specialist,
        texts,
        args.batch_size,
    )
    _, full_rankings, full_seconds = _score_checkpoint(
        args.full,
        texts,
        args.batch_size,
    )
    words, characters, lexical_labels, coefficients, intercept = _resources(
        args.lexical
    )
    matrix = hstack(
        (words.transform(texts), characters.transform(texts)),
        format="csr",
    )
    lexical_scores = np.asarray(matrix @ coefficients.T + intercept)
    lexical_rankings = [
        [lexical_labels[int(index)] for index in np.argsort(-scores)]
        for scores in lexical_scores
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
    os.environ.update(
        sidecar_environment(
            runtime_config,
            gpu_layers=runtime_config.gpu_layers,
            llm_http_timeout=PROFILE_LIMITS["gpu"]["llm_http"],
        )
    )
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
                    "case_id": row["case_id"],
                    "outcome": row["outcome"],
                    "expected": sorted(expected),
                    "specialist_top3": specialist[:3],
                    "full_top1": full[0],
                    "lexical_top1": lexical[0],
                    "chosen": chosen,
                    "gate": gate,
                    "selector_called": selector_called,
                    "selector_seconds": round(selector_seconds, 6),
                    "baseline_correct": baseline in expected,
                    "final_correct": chosen in expected,
                }
            )
    finally:
        runtime.close()

    identity_rows = [row for row in results if row["expected"] != [NO_ACTION]]
    no_action_rows = [row for row in results if row["expected"] == [NO_ACTION]]
    report = {
        "schema": "baxy.verified-consensus-current-review.v1",
        "scope": "reviewed_development_conditional_labels_only_no_promotion",
        "authority": "candidate_selection_only_no_core_plan_or_provider",
        "effects_executed": 0,
        "contains_utterance_text": False,
        "sources": {
            "corpus_sha256": _sha256(args.corpus),
            "specialist_config_sha256": _sha256(args.specialist / "config.json"),
            "full_config_sha256": _sha256(args.full / "config.json"),
            "lexical_manifest_sha256": _sha256(
                args.lexical / "operation_shortlist.v1.manifest.json"
            ),
            "runtime": public_runtime_identity(runtime_config),
            "baxy_blind_reserve_opened": False,
        },
        "classifier_seconds": {
            "specialist_batch": round(specialist_seconds, 6),
            "full_batch": round(full_seconds, 6),
        },
        "all": _metrics(results),
        "identity": _metrics(identity_rows),
        "no_action": _metrics(no_action_rows),
        "records": results,
    }
    write_json_atomic(args.report, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--specialist", type=Path, default=SPECIALIST)
    parser.add_argument("--full", type=Path, default=FULL)
    parser.add_argument("--lexical", type=Path, default=LEXICAL)
    parser.add_argument("--corpus", type=Path, default=CORPUS)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--runtime-manifest", type=Path, default=DEFAULT_RUNTIME_MANIFEST)
    parser.add_argument("--batch-size", type=int, default=128)
    args = parser.parse_args()
    args.specialist = args.specialist.resolve(strict=True)
    args.full = args.full.resolve(strict=True)
    args.lexical = args.lexical.resolve(strict=True)
    args.corpus = args.corpus.resolve(strict=True)
    args.report = args.report.resolve()
    result = run(args)
    print(
        json.dumps(
            {
                "all": result["all"],
                "identity": result["identity"],
                "no_action": result["no_action"],
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
