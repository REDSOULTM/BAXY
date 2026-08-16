"""Probe a frozen operation ranker plus Qwen's explicit no-match selector.

This development diagnostic performs tool selection only.  It never sends a
plan to Core and cannot execute a provider effect.
"""

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

from benchmark_native_no_match_tool import _select  # noqa: E402
from probe_current_catalog_review import (  # noqa: E402
    _matches,
    _operation_sets,
)
from probe_operation_shortlist_current_review import (  # noqa: E402
    NO_ACTION,
    _resources,
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
from baxy_mind.llm import LlmRuntime  # noqa: E402


DEFAULT_ASSETS = ROOT / "artifacts/research/operation_shortlist_v3"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, int(percentile * len(ordered) + 0.999) - 1))
    return ordered[rank]


def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.output.exists():
        raise RuntimeError(f"refusing to overwrite result: {args.output}")
    source = _read_jsonl(args.corpus)
    cases = [row for row in source if row.get("owner") in {None, "mind_sidecar"}]
    product_rows: dict[str, dict[str, Any]] = {}
    if args.product is not None:
        product_rows = {
            str(row["case_id"]): row
            for row in json.loads(args.product.read_text(encoding="utf-8"))["rows"]
        }
    words, characters, classes, coefficients, intercept = _resources(args.assets)
    texts = [str(row["text"]) for row in cases]
    matrix = hstack(
        (words.transform(texts), characters.transform(texts)),
        format="csr",
    )
    scores = np.asarray(matrix @ coefficients.T + intercept)

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
        if not str(capability["name"]).startswith("memory.")
    }
    os.environ.update(
        sidecar_environment(
            runtime_config,
            gpu_layers=runtime_config.gpu_layers,
            llm_http_timeout=PROFILE_LIMITS["gpu"]["llm_http"],
        )
    )
    runtime = LlmRuntime()
    rows = []
    try:
        for index, case in enumerate(cases):
            ranking = [
                classes[int(position)]
                for position in np.argsort(-scores[index])
                if classes[int(position)] != NO_ACTION
                and classes[int(position)] in capability_by_name
            ][: args.ranker_count]
            product = product_rows.get(str(case["case_id"]), {})
            product_candidates = [
                str(value) for value in product.get("candidate_operations", [])
            ]
            candidate_names = list(
                dict.fromkeys([*ranking, *product_candidates])
            )[: args.max_candidates]
            candidates = [capability_by_name[name] for name in candidate_names]
            started = time.perf_counter()
            selector_error = None
            try:
                selected, no_match = _select(
                    runtime,
                    str(case["text"]),
                    candidates,
                    no_match_mode="sentinel",
                    tool_choice="required",
                    parallel_tool_calls=args.parallel_tool_calls,
                )
            except Exception as error:  # noqa: BLE001 - fail closed diagnostic
                selected, no_match = (), True
                selector_error = type(error).__name__
            seconds = time.perf_counter() - started
            action_expected = case["outcome"] in {"action", "clarify"}
            accepted = (
                _operation_sets(case, "compatible_terminal_operation_sets")
                if action_expected
                else ()
            )
            correct = (
                not no_match and _matches(selected, accepted)
                if action_expected
                else no_match and not selected
            )
            rows.append(
                {
                    "case_id": case["case_id"],
                    "outcome": case["outcome"],
                    "language": case["language"],
                    "ranker_candidates": ranking,
                    "candidate_operations": candidate_names,
                    "selected_operations": list(selected),
                    "selected_no_match": no_match,
                    "selector_error": selector_error,
                    "accepted_operation_sets": [list(value) for value in accepted],
                    "correct": correct,
                    "seconds": round(seconds, 6),
                }
            )
    finally:
        runtime.close()

    latencies = [float(row["seconds"]) for row in rows]
    action_rows = [row for row in rows if row["outcome"] in {"action", "clarify"}]
    no_action_rows = [row for row in rows if row not in action_rows]
    result = {
        "schema": "baxy.ranker-native-selector-development-probe.v1",
        "scope": "development_only_not_blind",
        "authority": "tool_selection_only_no_core_plan_or_provider",
        "effects_executed": 0,
        "contains_utterance_text": False,
        "runtime": public_runtime_identity(runtime_config),
        "source": {
            "corpus": str(args.corpus.relative_to(ROOT)),
            "assets": str(args.assets.relative_to(ROOT)),
            "product": (
                str(args.product.relative_to(ROOT)) if args.product is not None else None
            ),
            "cases": len(rows),
            "ranker_count": args.ranker_count,
            "max_candidates": args.max_candidates,
            "parallel_tool_calls": args.parallel_tool_calls,
        },
        "metrics": {
            "correct": sum(bool(row["correct"]) for row in rows),
            "accuracy": sum(bool(row["correct"]) for row in rows) / len(rows),
            "action_cases": len(action_rows),
            "action_correct": sum(bool(row["correct"]) for row in action_rows),
            "wrong_action_selection": sum(
                not row["correct"] and bool(row["selected_operations"])
                for row in action_rows
            ),
            "no_action_cases": len(no_action_rows),
            "false_actions": sum(
                bool(row["selected_operations"]) for row in no_action_rows
            ),
            "selector_errors": sum(
                row["selector_error"] is not None for row in rows
            ),
            "seconds_p50": statistics.median(latencies),
            "seconds_p95": _percentile(latencies, 0.95),
        },
        "rows": rows,
    }
    write_json_atomic(args.output, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--product", type=Path)
    parser.add_argument("--assets", type=Path, default=DEFAULT_ASSETS)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ranker-count", type=int, default=5)
    parser.add_argument("--max-candidates", type=int, default=12)
    parser.add_argument(
        "--parallel-tool-calls",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    parser.add_argument("--runtime-manifest", type=Path, default=DEFAULT_RUNTIME_MANIFEST)
    args = parser.parse_args()
    args.corpus = args.corpus.resolve(strict=True)
    args.product = args.product.resolve(strict=True) if args.product else None
    args.assets = args.assets.resolve(strict=True)
    args.output = args.output.resolve()
    result = run(args)
    print(json.dumps(result["metrics"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
