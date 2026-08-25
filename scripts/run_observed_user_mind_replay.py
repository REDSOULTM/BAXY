"""Replay every observed user occurrence through the current local mind.

This is the diagnostic half of Goal 10, not the integral acceptance result.  It
matches the desktop semantic sequence (turn decision followed by arguments or a
plan) and persists one private row per message_id.  Core/provider execution and
the final model review are deliberately separate gates, so this script never
claims that an operation was completed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DATA = ROOT / "tests" / "data"
DEFAULT_CASES = DATA / "historical_observed_product_turns.v1.jsonl"
DEFAULT_MAPPING = DATA / "historical_message_mapping.jsonl"
DEFAULT_OUTPUT = (
    Path(os.environ.get("LOCALAPPDATA", ROOT))
    / "BAXYRuntime"
    / "goal10"
    / "observed-user-mind-replay.v1.jsonl"
)
DEFAULT_SUMMARY = ROOT / "artifacts" / "goal10" / "observed-mind-replay-summary.v1.json"

from scripts.baxy_runtime_config import (  # noqa: E402
    RuntimeConfig,
    add_runtime_arguments,
    resolve_runtime_from_args_or_error,
)
from scripts.run_exhaustive_runtime_model_gate import (  # noqa: E402
    MindClient,
    core_capabilities,
)


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise RuntimeError(f"Expected object at {path}:{line_number}")
            yield value


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def runtime_fingerprint(
    runtime: RuntimeConfig,
    cases: Path,
    mapping: Path,
) -> str:
    digest = hashlib.sha256()
    for value in (
        runtime.manifest_sha256,
        file_sha256(runtime.gguf),
        file_sha256(runtime.llama_server),
        file_sha256(cases),
        file_sha256(mapping),
        file_sha256(Path(__file__)),
    ):
        digest.update(value.encode("ascii"))
        digest.update(b"\0")
    for path in sorted((ROOT / "src" / "baxy_mind").glob("*.py")):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_sha256(path).encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def expected_contract(mapping: dict[str, Any]) -> dict[str, Any]:
    return {
        key: mapping.get(key)
        for key in (
            "acceptance_scope",
            "outcome_type",
            "operations",
            "denied_operations",
            "plan",
            "risk",
            "provider_roles",
            "verification",
            "natural_response",
        )
    }


def visible_candidate(turn: dict[str, Any]) -> str:
    if turn.get("kind") == "conversation":
        return str(turn.get("reply") or "").strip()
    if turn.get("kind") == "clarify":
        return str(turn.get("question") or "").strip()
    return ""


def observed_operations(
    turn: dict[str, Any],
    plan: dict[str, Any] | None,
) -> list[str]:
    if turn.get("kind") == "action":
        operation = str(turn.get("operation") or "")
        return [operation] if operation else []
    if turn.get("kind") == "plan" and plan is not None:
        return [
            str(step.get("operation") or "")
            for step in plan.get("steps") or []
            if str(step.get("operation") or "")
        ]
    return []


def structural_verdict(
    mapping: dict[str, Any],
    turn: dict[str, Any],
    plan: dict[str, Any] | None,
    arguments: dict[str, Any] | None,
) -> tuple[str, str]:
    expected = [str(item) for item in mapping.get("operations") or []]
    denied = {str(item) for item in mapping.get("denied_operations") or []}
    actual = observed_operations(turn, plan)
    visible = visible_candidate(turn)

    if denied.intersection(actual):
        return "fail", "decision proposed an explicitly denied operation"
    if not expected:
        if actual:
            return "fail", "no-effect contract received operation authority"
        if turn.get("kind") not in {"conversation", "clarify"}:
            return "fail", "no-effect contract returned no usable response kind"
        if not visible:
            return "fail", "no-effect contract returned empty visible text"
        return "pass", "zero operation authority and non-empty model-authored text"

    if actual != expected:
        return "fail", "observed operation sequence differs from the contract"
    if turn.get("kind") == "action" and arguments is None:
        return "fail", "direct action did not produce grounded arguments"
    if turn.get("kind") == "plan" and (
        plan is None or plan.get("kind") != "plan" or not plan.get("steps")
    ):
        return "fail", "planned mission did not produce materialized steps"
    return "pass", "operation sequence and semantic materialization match"


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[int((len(ordered) - 1) * ratio)]


def run_case(
    mind: MindClient,
    case: dict[str, Any],
    mapping: dict[str, Any],
    fingerprint: str,
) -> dict[str, Any]:
    message_id = str(case["message_id"])
    text = str(case["text_literal"])
    started = time.monotonic()
    before_turn = time.monotonic()
    turn = mind.request(
        {"type": "turn.decide", "id": message_id, "text": text, "history": []},
        timeout=30,
        expected_type="turn.result",
    )
    turn_seconds = time.monotonic() - before_turn
    arguments: dict[str, Any] | None = None
    argument_result: dict[str, Any] | None = None
    plan: dict[str, Any] | None = None
    semantic_seconds = 0.0

    if turn.get("kind") == "action" and turn.get("operation"):
        before_semantic = time.monotonic()
        argument_result = mind.request(
            {
                "type": "arguments",
                "id": message_id + "_arguments",
                "operation": turn["operation"],
                "text": text,
            },
            timeout=30,
            expected_type="arguments.result",
        )
        semantic_seconds = time.monotonic() - before_semantic
        if argument_result.get("ok") is True:
            raw_arguments = argument_result.get("arguments")
            arguments = raw_arguments if isinstance(raw_arguments, dict) else None
    elif turn.get("kind") == "plan":
        before_semantic = time.monotonic()
        request: dict[str, Any] = {
            "type": "plan",
            "id": message_id + "_plan",
            "text": text,
            "history": [],
        }
        effects = [str(value) for value in turn.get("effectOperations") or []]
        if effects:
            request["expectedOperations"] = effects
        plan = mind.request(request, timeout=90, expected_type="plan.result")
        semantic_seconds = time.monotonic() - before_semantic

    verdict, reason = structural_verdict(mapping, turn, plan, arguments)
    return {
        "schema": "baxy.goal10-observed-mind-replay.v1",
        "message_id": message_id,
        "message": text,
        "text_sha256": case["text_sha256"],
        "source": case["source"],
        "source_location": case["source_location"],
        "class": case["class"],
        "language": case["language"],
        "contract": expected_contract(mapping),
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "facts": {
            "scope": "isolated semantic replay before Core/provider execution",
            "authority": "current registered local runtime and compiled catalog",
        },
        "turn": turn,
        "arguments_result": argument_result,
        "plan": plan,
        "observed_operations": observed_operations(turn, plan),
        "visible_candidate": visible_candidate(turn),
        "checks": {
            "pertinence": "requires_goal_model_review",
            "naturalness": "requires_goal_model_review",
            "language": "requires_goal_model_review",
            "honesty": "requires_goal_model_review",
            "requested_action": verdict,
            "risk": "requires_Core_replay",
            "confirmation": "requires_Core_replay",
            "verification": "requires_Core_replay",
            "terminal": "requires_Core_replay",
        },
        "structural_verdict": verdict,
        "structural_reason": reason,
        "timing_seconds": {
            "turn": round(turn_seconds, 6),
            "arguments_or_plan": round(semantic_seconds, 6),
            "total": round(time.monotonic() - started, 6),
        },
        "runtime_fingerprint": fingerprint,
    }


def build_summary(
    rows: list[dict[str, Any]],
    *,
    cases: Path,
    mapping: Path,
    output: Path,
    fingerprint: str,
    expected_count: int,
) -> dict[str, Any]:
    ids = [str(row["message_id"]) for row in rows]
    latencies = [float(row["timing_seconds"]["total"]) for row in rows]
    return {
        "schema": "baxy.goal10-observed-mind-replay-summary.v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "diagnostic semantic replay; not integral acceptance",
        "runtime_fingerprint": fingerprint,
        "source_cases_sha256": file_sha256(cases),
        "source_mapping_sha256": file_sha256(mapping),
        "private_output_sha256": file_sha256(output) if output.is_file() else "",
        "expected_occurrences": expected_count,
        "completed_occurrences": len(rows),
        "unique_message_ids": len(set(ids)),
        "duplicate_message_ids": len(ids) - len(set(ids)),
        "structural_verdict_counts": dict(
            sorted(Counter(row["structural_verdict"] for row in rows).items())
        ),
        "decision_kind_counts": dict(
            sorted(Counter(str(row["turn"].get("kind") or "") for row in rows).items())
        ),
        "latency_seconds": {
            "p50": percentile(latencies, 0.50),
            "p95": percentile(latencies, 0.95),
            "maximum": max(latencies, default=0.0),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--fresh", action="store_true")
    parser.add_argument("--llm-endpoint")
    add_runtime_arguments(parser)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runtime = resolve_runtime_from_args_or_error(argparse.ArgumentParser(), args)
    cases_path = args.cases.resolve()
    mapping_path = args.mapping.resolve()
    output_path = args.output.resolve()
    summary_path = args.summary_output.resolve()
    fingerprint = runtime_fingerprint(runtime, cases_path, mapping_path)
    cases = list(read_jsonl(cases_path))
    mappings = {str(row["message_id"]): row for row in read_jsonl(mapping_path)}
    case_ids = [str(case["message_id"]) for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise RuntimeError("Observed corpus contains duplicate message_id values")
    if missing := sorted(set(case_ids).difference(mappings)):
        raise RuntimeError(f"Observed corpus has {len(missing)} messages without mapping")

    if args.fresh and output_path.exists():
        output_path.unlink()
    completed_rows = list(read_jsonl(output_path)) if output_path.exists() else []
    if any(row.get("runtime_fingerprint") != fingerprint for row in completed_rows):
        raise RuntimeError("Existing replay belongs to another runtime; use --fresh")
    completed = {str(row["message_id"]) for row in completed_rows}
    if len(completed) != len(completed_rows):
        raise RuntimeError("Existing replay contains duplicate message_id values")

    selected = set(args.case_id)
    unknown = selected.difference(case_ids)
    if unknown:
        raise ValueError("Unknown message IDs: " + ", ".join(sorted(unknown)[:10]))
    pending = [
        case
        for case in cases
        if str(case["message_id"]) not in completed
        and (not selected or str(case["message_id"]) in selected)
    ]
    if args.max_cases is not None:
        pending = pending[: max(0, args.max_cases)]

    started = time.monotonic()
    mind = (
        MindClient(core_capabilities(), runtime, args.llm_endpoint)
        if pending
        else None
    )
    try:
        for position, case in enumerate(pending, start=1):
            assert mind is not None
            message_id = str(case["message_id"])
            row = run_case(mind, case, mappings[message_id], fingerprint)
            append_jsonl(output_path, row)
            completed_rows.append(row)
            if position % 25 == 0 or position == len(pending):
                print(
                    json.dumps(
                        {
                            "completed_this_run": position,
                            "pending_this_run": len(pending) - position,
                            "latest_verdict": row["structural_verdict"],
                            "elapsed_seconds": round(time.monotonic() - started, 1),
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
    finally:
        if mind is not None:
            mind.close()

    summary = build_summary(
        completed_rows,
        cases=cases_path,
        mapping=mapping_path,
        output=output_path,
        fingerprint=fingerprint,
        expected_count=len(cases),
    )
    write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary["duplicate_message_ids"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
