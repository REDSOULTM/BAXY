"""Physical, effect-free A/B for llama.cpp CUDA Graphs.

The experiment keeps BAXY's b9980 server, model, runtime flags, prompts,
schemas, payloads and case order fixed.  The only experimental variable is
the *presence* of llama.cpp's official CUDA Graphs kill switch:

* ``baseline``: ``GGML_CUDA_DISABLE_GRAPHS`` is absent, so the compiled
  default keeps CUDA Graphs enabled;
* ``disabled``: ``GGML_CUDA_DISABLE_GRAPHS=1`` is present in the fresh
  llama-server child environment, so CUDA Graphs are disabled.

llama.cpp b9980 checks only whether this variable exists.  A value such as
``0`` would therefore still disable graphs and is deliberately never used.
The unrelated historical ``GGML_CUDA_GRAPH_OPT`` stream-concurrency flag is
removed in both arms.  The workload never starts Core or executes an external
effect.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
from pathlib import Path
from typing import Any, Callable

from benchmark_llama_slot_pinning import (  # type: ignore[import-not-found]
    CASES,
    _case_projection,
    _run_arm,
)


_DISABLE_GRAPHS_ENV = "GGML_CUDA_DISABLE_GRAPHS"
_UNRELATED_GRAPH_OPT_ENV = "GGML_CUDA_GRAPH_OPT"
_CRITICAL_STAGES = ("P", "G", "L")
_BACKEND_FILENAMES = (
    "llama-server-impl.dll",
    "llama.dll",
    "llama-common.dll",
    "ggml.dll",
    "ggml-base.dll",
    "ggml-cuda.dll",
)
_TAIL_ABSOLUTE_TOLERANCE_SECONDS = 0.250
_TAIL_RELATIVE_TOLERANCE = 0.03
_CRITICAL_ABSOLUTE_TOLERANCE_SECONDS = 0.100
_CRITICAL_RELATIVE_TOLERANCE = 0.03


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _contains_bytes(path: Path, needle: bytes) -> bool:
    if not needle:
        raise ValueError("needle must not be empty")
    overlap = b""
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            haystack = overlap + chunk
            if needle in haystack:
                return True
            overlap = haystack[-(len(needle) - 1) :] if len(needle) > 1 else b""
    return False


def _runtime_hashes(server: Path, model: Path) -> dict[str, Any]:
    component_paths = {
        "llama-server.exe": server,
        **{
            filename: server.parent / filename
            for filename in _BACKEND_FILENAMES
        },
    }
    missing = [
        str(path)
        for path in component_paths.values()
        if not path.is_file()
    ]
    if missing:
        raise FileNotFoundError(
            "official llama.cpp runtime components are missing: "
            + ", ".join(missing)
        )
    return {
        "model": {
            "path": str(model),
            "sha256": _sha256(model),
        },
        "runtime_components": {
            name: {
                "path": str(path),
                "sha256": _sha256(path),
            }
            for name, path in component_paths.items()
        },
    }


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + ((ordered[upper] - ordered[lower]) * fraction)


def _latency_summary(values: list[float]) -> dict[str, float | int | None]:
    return {
        "count": len(values),
        "p50_seconds": statistics.median(values) if values else None,
        "p95_seconds": _percentile(values, 0.95),
        "max_seconds": max(values) if values else None,
        "total_seconds": sum(values),
    }


def _numeric(
    records: list[dict[str, Any]],
    key: str,
    *,
    milliseconds: bool = False,
) -> list[float]:
    scale = 0.001 if milliseconds else 1.0
    return [
        float(record[key]) * scale
        for record in records
        if isinstance(record.get(key), (int, float))
        and not isinstance(record.get(key), bool)
    ]


def _detailed_stage_summary(
    records: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for stage in ("P", "G", "L", "V", "C", "E", "chat", "other"):
        selected = [record for record in records if record["stage"] == stage]
        if not selected:
            continue
        cache_n = _numeric(selected, "cache_n")
        prompt_n = _numeric(selected, "prompt_n")
        predicted_n = _numeric(selected, "predicted_n")
        result[stage] = {
            "calls": len(selected),
            "request_elapsed": _latency_summary(
                _numeric(selected, "elapsed_seconds")
            ),
            "prompt": _latency_summary(
                _numeric(selected, "prompt_ms", milliseconds=True)
            ),
            "generation": _latency_summary(
                _numeric(selected, "predicted_ms", milliseconds=True)
            ),
            "cache_n_median": statistics.median(cache_n) if cache_n else None,
            "prompt_n_median": statistics.median(prompt_n) if prompt_n else None,
            "predicted_n_median": (
                statistics.median(predicted_n) if predicted_n else None
            ),
        }
    return result


def _post_projection(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: record.get(key)
        for key in (
            "case",
            "stage",
            "id_slot",
            "payload_sha256",
            "predicted_n",
            "content",
        )
    }


def _payload_projection(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: record.get(key)
        for key in (
            "case",
            "stage",
            "payload_sha256",
        )
    }


def _effect_projection(case: dict[str, Any]) -> dict[str, Any]:
    decision = case.get("decision")
    if not isinstance(decision, dict):
        decision = {}
    return {
        "case": case.get("case"),
        "mode": decision.get("mode"),
        "operation": decision.get("operation"),
        "effect_count": decision.get("effect_count"),
        "effect_operations": decision.get("effect_operations"),
        "extraction": case.get("extraction"),
    }


def _has_effect(projection: dict[str, Any]) -> bool:
    return bool(
        projection.get("mode") in {"action", "plan"}
        or projection.get("operation")
        or projection.get("effect_operations")
        or projection.get("extraction") is not None
    )


def _environment_snapshot(profile: str) -> dict[str, Any]:
    disable_present = _DISABLE_GRAPHS_ENV in os.environ
    disable_value = os.environ.get(_DISABLE_GRAPHS_ENV)
    graph_opt_present = _UNRELATED_GRAPH_OPT_ENV in os.environ
    graph_opt_value = os.environ.get(_UNRELATED_GRAPH_OPT_ENV)
    return {
        "profile": profile,
        _DISABLE_GRAPHS_ENV: {
            "present": disable_present,
            "value": disable_value,
        },
        _UNRELATED_GRAPH_OPT_ENV: {
            "present": graph_opt_present,
            "value": graph_opt_value,
        },
        "cuda_graphs_expected_enabled": profile == "baseline",
    }


def _environment_contract(snapshot: dict[str, Any]) -> bool:
    profile = snapshot.get("profile")
    disable = snapshot.get(_DISABLE_GRAPHS_ENV)
    graph_opt = snapshot.get(_UNRELATED_GRAPH_OPT_ENV)
    if not isinstance(disable, dict) or not isinstance(graph_opt, dict):
        return False
    if graph_opt.get("present") or graph_opt.get("value") is not None:
        return False
    if profile == "baseline":
        return (
            not disable.get("present")
            and disable.get("value") is None
            and snapshot.get("cuda_graphs_expected_enabled") is True
        )
    if profile == "disabled":
        return (
            disable.get("present") is True
            and disable.get("value") == "1"
            and snapshot.get("cuda_graphs_expected_enabled") is False
        )
    return False


def _run_profile(profile: str) -> dict[str, Any]:
    os.environ.pop(_UNRELATED_GRAPH_OPT_ENV, None)
    if profile == "baseline":
        os.environ.pop(_DISABLE_GRAPHS_ENV, None)
    elif profile == "disabled":
        os.environ[_DISABLE_GRAPHS_ENV] = "1"
    else:
        raise ValueError(f"unknown profile: {profile}")

    environment = _environment_snapshot(profile)
    if not _environment_contract(environment):
        raise RuntimeError(f"invalid environment contract for {profile}")

    arm = _run_arm("auto")
    case_elapsed = [
        float(case["elapsed_seconds"])
        for case in arm["cases"]
    ]
    return {
        "profile": profile,
        "environment": environment,
        "completed_without_exception": True,
        "case_count": len(arm["cases"]),
        "post_count": len(arm["posts"]),
        "cases": arm["cases"],
        "posts": arm["posts"],
        "case_latency": _latency_summary(case_elapsed),
        "stage_summary": _detailed_stage_summary(arm["posts"]),
    }


def _delta(
    candidate: float | int | None,
    baseline: float | int | None,
) -> dict[str, Any]:
    if candidate is None or baseline is None:
        return {"seconds": None, "percent": None}
    candidate_float = float(candidate)
    baseline_float = float(baseline)
    return {
        "seconds": candidate_float - baseline_float,
        "percent": (
            ((candidate_float / baseline_float) - 1.0) * 100.0
            if baseline_float
            else None
        ),
    }


def _indexed_differences(
    baseline_records: list[dict[str, Any]],
    disabled_records: list[dict[str, Any]],
    projection: Callable[[dict[str, Any]], dict[str, Any]],
) -> list[dict[str, Any]]:
    differences: list[dict[str, Any]] = []
    for index in range(max(len(baseline_records), len(disabled_records))):
        baseline_present = index < len(baseline_records)
        disabled_present = index < len(disabled_records)
        baseline = (
            projection(baseline_records[index]) if baseline_present else None
        )
        disabled = (
            projection(disabled_records[index]) if disabled_present else None
        )
        if baseline_present != disabled_present or baseline != disabled:
            differences.append(
                {
                    "index": index,
                    "baseline_present": baseline_present,
                    "disabled_present": disabled_present,
                    "baseline": baseline,
                    "disabled": disabled,
                }
            )
    return differences


def _post_multiplicity(posts: list[dict[str, Any]]) -> dict[str, int]:
    result: dict[str, int] = {}
    for post in posts:
        key = f"{post.get('case')}::{post.get('stage')}"
        result[key] = result.get(key, 0) + 1
    return result


def _multiplicity_deltas(
    baseline_posts: list[dict[str, Any]],
    disabled_posts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    baseline = _post_multiplicity(baseline_posts)
    disabled = _post_multiplicity(disabled_posts)
    return [
        {
            "case_stage": key,
            "baseline_count": baseline.get(key, 0),
            "disabled_count": disabled.get(key, 0),
        }
        for key in sorted(set(baseline) | set(disabled))
        if baseline.get(key, 0) != disabled.get(key, 0)
    ]


def _case_sequence(arm: dict[str, Any]) -> list[Any]:
    return [case.get("case") for case in arm["cases"]]


def _post_sequence(arm: dict[str, Any]) -> list[tuple[Any, Any]]:
    return [
        (post.get("case"), post.get("stage"))
        for post in arm["posts"]
    ]


def _latency_deltas(
    disabled: dict[str, Any],
    baseline: dict[str, Any],
) -> dict[str, Any]:
    return {
        metric: _delta(
            disabled["case_latency"][metric],
            baseline["case_latency"][metric],
        )
        for metric in (
            "p50_seconds",
            "p95_seconds",
            "max_seconds",
            "total_seconds",
        )
    }


def _stage_latency_deltas(
    disabled: dict[str, Any],
    baseline: dict[str, Any],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    stages = sorted(
        set(disabled["stage_summary"])
        | set(baseline["stage_summary"])
    )
    for stage in stages:
        disabled_stage = disabled["stage_summary"].get(stage)
        baseline_stage = baseline["stage_summary"].get(stage)
        if not isinstance(disabled_stage, dict) or not isinstance(
            baseline_stage,
            dict,
        ):
            result[stage] = {
                "present_in_both": False,
                "disabled_minus_baseline": {},
            }
            continue
        result[stage] = {
            "present_in_both": True,
            "calls_equal": (
                disabled_stage["calls"] == baseline_stage["calls"]
            ),
            "disabled_minus_baseline": {
                metric: _delta(
                    disabled_stage["request_elapsed"][metric],
                    baseline_stage["request_elapsed"][metric],
                )
                for metric in (
                    "p50_seconds",
                    "p95_seconds",
                    "max_seconds",
                    "total_seconds",
                )
            },
        }
    return result


def _no_material_regression(
    candidate: float | int | None,
    baseline: float | int | None,
    *,
    absolute_tolerance: float,
    relative_tolerance: float,
) -> bool:
    if candidate is None or baseline is None:
        return False
    baseline_float = float(baseline)
    allowed = max(
        absolute_tolerance,
        abs(baseline_float) * relative_tolerance,
    )
    return float(candidate) - baseline_float <= allowed


def _critical_path_gate(
    disabled: dict[str, Any],
    baseline: dict[str, Any],
) -> bool:
    for stage in _CRITICAL_STAGES:
        disabled_stage = disabled["stage_summary"].get(stage)
        baseline_stage = baseline["stage_summary"].get(stage)
        if not isinstance(disabled_stage, dict) or not isinstance(
            baseline_stage,
            dict,
        ):
            return False
        if disabled_stage["calls"] != baseline_stage["calls"]:
            return False
        for metric in ("p50_seconds", "p95_seconds", "total_seconds"):
            if not _no_material_regression(
                disabled_stage["request_elapsed"][metric],
                baseline_stage["request_elapsed"][metric],
                absolute_tolerance=_CRITICAL_ABSOLUTE_TOLERANCE_SECONDS,
                relative_tolerance=_CRITICAL_RELATIVE_TOLERANCE,
            ):
                return False
    return True


def _restore_environment(
    name: str,
    *,
    was_present: bool,
    value: str | None,
) -> None:
    if was_present and value is not None:
        os.environ[name] = value
    elif was_present:
        os.environ[name] = ""
    else:
        os.environ.pop(name, None)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--arm-order",
        choices=("baseline-disabled", "disabled-baseline"),
        default="baseline-disabled",
    )
    parser.add_argument(
        "--server",
        type=Path,
        default=Path(
            r"D:\BAXYRuntime\assets\llama-b9980-cuda12.4\llama-server.exe"
        ),
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=Path(
            r"D:\BAXYRuntime\assets\models"
            r"\gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf"
        ),
    )
    args = parser.parse_args()
    server = args.server.resolve()
    model = args.model.resolve()
    if not server.is_file() or not model.is_file():
        raise FileNotFoundError("official b9980 runtime assets are missing")

    ggml_cuda = server.parent / "ggml-cuda.dll"
    if not ggml_cuda.is_file():
        raise FileNotFoundError(f"CUDA backend is missing: {ggml_cuda}")
    backend_switch_literal_present = _contains_bytes(
        ggml_cuda,
        _DISABLE_GRAPHS_ENV.encode("ascii"),
    )
    runtime_hashes = _runtime_hashes(server, model)

    disable_was_present = _DISABLE_GRAPHS_ENV in os.environ
    disable_original = os.environ.get(_DISABLE_GRAPHS_ENV)
    graph_opt_was_present = _UNRELATED_GRAPH_OPT_ENV in os.environ
    graph_opt_original = os.environ.get(_UNRELATED_GRAPH_OPT_ENV)

    os.environ.pop("BAXY_MIND_LLM_ENDPOINT", None)
    os.environ["BAXY_MIND_LLAMA_SERVER"] = str(server)
    os.environ["BAXY_MIND_LLM_GGUF"] = str(model)
    os.environ["BAXY_MIND_NGL"] = "99"
    os.environ["BAXY_MIND_LLM_REQUEST_TIMEOUT"] = "19"
    os.environ.pop(_UNRELATED_GRAPH_OPT_ENV, None)

    arm_order = args.arm_order.split("-")
    try:
        arms = [_run_profile(profile) for profile in arm_order]
    finally:
        _restore_environment(
            _DISABLE_GRAPHS_ENV,
            was_present=disable_was_present,
            value=disable_original,
        )
        _restore_environment(
            _UNRELATED_GRAPH_OPT_ENV,
            was_present=graph_opt_was_present,
            value=graph_opt_original,
        )

    by_profile = {arm["profile"]: arm for arm in arms}
    baseline = by_profile["baseline"]
    disabled = by_profile["disabled"]

    divergent_cases = _indexed_differences(
        baseline["cases"],
        disabled["cases"],
        _case_projection,
    )
    divergent_posts = _indexed_differences(
        baseline["posts"],
        disabled["posts"],
        _post_projection,
    )
    divergent_payloads = _indexed_differences(
        baseline["posts"],
        disabled["posts"],
        _payload_projection,
    )
    effect_deltas = _indexed_differences(
        baseline["cases"],
        disabled["cases"],
        _effect_projection,
    )
    unsafe_effect_deltas = [
        delta
        for delta in effect_deltas
        if (
            isinstance(delta.get("baseline"), dict)
            and _has_effect(delta["baseline"])
        )
        or (
            isinstance(delta.get("disabled"), dict)
            and _has_effect(delta["disabled"])
        )
    ]
    post_multiplicity_deltas = _multiplicity_deltas(
        baseline["posts"],
        disabled["posts"],
    )

    workload_complete = all(
        arm["completed_without_exception"]
        and arm["case_count"] == len(CASES)
        for arm in arms
    )
    execution_errors_zero = all(
        arm["completed_without_exception"]
        for arm in arms
    )
    environment_contracts_exact = all(
        _environment_contract(arm["environment"])
        for arm in arms
    )
    case_count_equal = baseline["case_count"] == disabled["case_count"]
    case_sequence_equal = _case_sequence(baseline) == _case_sequence(disabled)
    post_count_equal = baseline["post_count"] == disabled["post_count"]
    post_sequence_equal = _post_sequence(baseline) == _post_sequence(disabled)
    differential_retries_zero = not post_multiplicity_deltas
    payloads_identical = post_count_equal and not divergent_payloads
    exact_case_outputs = case_count_equal and not divergent_cases
    exact_post_outputs = post_count_equal and not divergent_posts
    exact_outputs = exact_case_outputs and exact_post_outputs
    mode_contracts = all(
        case["decision"].get("mode") == case["expected_mode"]
        for arm in arms
        for case in arm["cases"]
    )
    unsafe_effect_deltas_zero = not unsafe_effect_deltas
    critical_stage_coverage = all(
        stage in arm["stage_summary"]
        and arm["stage_summary"][stage]["calls"] > 0
        for arm in arms
        for stage in _CRITICAL_STAGES
    )

    latency_delta = _latency_deltas(disabled, baseline)
    stage_latency_delta = _stage_latency_deltas(disabled, baseline)
    p50_and_total_improved = all(
        latency_delta[metric]["seconds"] is not None
        and latency_delta[metric]["seconds"] < 0.0
        for metric in ("p50_seconds", "total_seconds")
    )
    tail_no_material_regression = all(
        _no_material_regression(
            disabled["case_latency"][metric],
            baseline["case_latency"][metric],
            absolute_tolerance=_TAIL_ABSOLUTE_TOLERANCE_SECONDS,
            relative_tolerance=_TAIL_RELATIVE_TOLERANCE,
        )
        for metric in ("p95_seconds", "max_seconds")
    )
    critical_path_no_material_regression = _critical_path_gate(
        disabled,
        baseline,
    )

    measurement_valid = all(
        (
            backend_switch_literal_present,
            workload_complete,
            execution_errors_zero,
            environment_contracts_exact,
            case_count_equal,
            case_sequence_equal,
            post_count_equal,
            post_sequence_equal,
            differential_retries_zero,
            payloads_identical,
            exact_outputs,
            mode_contracts,
            unsafe_effect_deltas_zero,
            critical_stage_coverage,
        )
    )
    candidate_supported_in_this_order = (
        measurement_valid
        and p50_and_total_improved
        and tail_no_material_regression
        and critical_path_no_material_regression
    )

    result = {
        "schema": "baxy.llama-cuda-graphs-disable-ab.v1",
        "arm_order": arm_order,
        "measurement_outcome": (
            "invalid_measurement"
            if not measurement_valid
            else (
                "single_order_candidate_supported"
                if candidate_supported_in_this_order
                else "valid_candidate_not_supported"
            )
        ),
        "candidate_status": "research_only",
        "runtime": {
            "server": str(server),
            "model": str(model),
            "backend": str(ggml_cuda),
            "cache_type_k": "q8_0",
            "cache_type_v": "q8_0",
            "flash_attention": "on",
            "parallel": 3,
            "context_per_slot": 4_096,
        },
        "runtime_hashes": runtime_hashes,
        "backend_contract": {
            "disable_switch": _DISABLE_GRAPHS_ENV,
            "disable_switch_literal_present": backend_switch_literal_present,
            "presence_semantics": (
                "b9980 disables CUDA Graphs whenever the environment variable "
                "exists, regardless of its value"
            ),
            "baseline_expected_state": "enabled (compiled default)",
            "disabled_expected_state": "disabled by present value 1",
            "capture_warmup_note": (
                "llama.cpp graph capture/replay requires repeated compatible "
                "graph calls; evaluate the complete fixed workload, not only "
                "the first turn"
            ),
        },
        "safety": {
            "core_started": False,
            "external_effects_executed": False,
        },
        "control": {
            "only_variable": (
                "GGML_CUDA_DISABLE_GRAPHS absent versus present with exactly "
                "the value 1 in each fresh llama-server child environment"
            ),
            "unrelated_graph_opt_absent_in_both_arms": True,
            "fresh_server_per_arm": True,
            "same_model": True,
            "same_case_order": case_sequence_equal,
            "case_count_per_arm": len(CASES),
            "temperature": 0.0,
            "seed": 0,
        },
        "gates": {
            "backend_switch_literal_present": backend_switch_literal_present,
            "workload_complete": workload_complete,
            "execution_errors_zero": execution_errors_zero,
            "environment_contracts_exact": environment_contracts_exact,
            "case_count_equal": case_count_equal,
            "case_sequence_equal": case_sequence_equal,
            "post_count_equal": post_count_equal,
            "post_sequence_equal": post_sequence_equal,
            "differential_retries_zero": differential_retries_zero,
            "payloads_identical": payloads_identical,
            "exact_case_outputs": exact_case_outputs,
            "exact_post_outputs": exact_post_outputs,
            "exact_outputs": exact_outputs,
            "mode_contracts": mode_contracts,
            "unsafe_effect_deltas_zero": unsafe_effect_deltas_zero,
            "critical_stage_coverage": critical_stage_coverage,
            "measurement_valid": measurement_valid,
            "p50_and_total_improved": p50_and_total_improved,
            "tail_no_material_regression": tail_no_material_regression,
            "critical_path_no_material_regression": (
                critical_path_no_material_regression
            ),
            "candidate_supported_in_this_order": (
                candidate_supported_in_this_order
            ),
            "opposite_order_replication_present": False,
            "promotion_gate_passed": False,
        },
        "regression_tolerances": {
            "tail": {
                "absolute_seconds": _TAIL_ABSOLUTE_TOLERANCE_SECONDS,
                "relative_fraction": _TAIL_RELATIVE_TOLERANCE,
                "metrics": ["case_p95", "case_max"],
            },
            "critical_stages": {
                "stages": list(_CRITICAL_STAGES),
                "absolute_seconds": (
                    _CRITICAL_ABSOLUTE_TOLERANCE_SECONDS
                ),
                "relative_fraction": _CRITICAL_RELATIVE_TOLERANCE,
                "metrics": ["request_p50", "request_p95", "request_total"],
            },
        },
        "counts": {
            "baseline_cases": baseline["case_count"],
            "disabled_cases": disabled["case_count"],
            "baseline_posts": baseline["post_count"],
            "disabled_posts": disabled["post_count"],
        },
        "divergent_cases": divergent_cases,
        "divergent_posts": divergent_posts,
        "divergent_payloads": divergent_payloads,
        "post_multiplicity_deltas": post_multiplicity_deltas,
        "effect_deltas": effect_deltas,
        "unsafe_effect_deltas": unsafe_effect_deltas,
        "latency_delta_disabled_minus_baseline": latency_delta,
        "stage_latency_delta_disabled_minus_baseline": stage_latency_delta,
        "arms": arms,
        "promotion_rule": (
            "Changing the runtime to disable CUDA Graphs requires two valid "
            "opposite-order artifacts with exact payloads, outputs, decisions "
            "and arguments; equal post counts and multiplicities; expected "
            "modes; zero unsafe deltas; lower end-to-end p50 and total in both "
            "orders; no material p95/max regression; and no material P/G/L "
            "request-latency regression. A single artifact can never pass the "
            "promotion gate."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "schema",
                    "arm_order",
                    "measurement_outcome",
                    "gates",
                    "latency_delta_disabled_minus_baseline",
                    "candidate_status",
                )
            },
            ensure_ascii=False,
        )
    )
    return 0 if measurement_valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
