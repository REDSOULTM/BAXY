"""Physical, effect-free A/B for llama.cpp CUDA stream concurrency.

The experiment keeps BAXY's b9980 server, model, runtime flags, prompts,
schemas, payloads and case order fixed.  The only variable is the official
llama.cpp opt-in environment flag ``GGML_CUDA_GRAPH_OPT``:

* ``baseline``: the variable is absent from the child server environment;
* ``graph``: ``GGML_CUDA_GRAPH_OPT=1`` is inherited by the fresh server.

Despite the historical flag name, this tests llama.cpp's Q/K/V stream
concurrency optimization.  CUDA Graphs themselves remain at their normal
default in both arms.  The workload never starts Core or executes an external
effect.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
from pathlib import Path
from typing import Any

from benchmark_llama_slot_pinning import (  # type: ignore[import-not-found]
    CASES,
    _case_projection,
    _run_arm,
)


_ENVIRONMENT_VARIABLE = "GGML_CUDA_GRAPH_OPT"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _latency_summary(values: list[float]) -> dict[str, float | None]:
    return {
        "count": float(len(values)),
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
    ]


def _detailed_stage_summary(
    records: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for stage in ("P", "G", "L", "V", "C", "E", "chat", "other"):
        selected = [record for record in records if record["stage"] == stage]
        if not selected:
            continue
        result[stage] = {
            "request_elapsed": _latency_summary(
                _numeric(selected, "elapsed_seconds")
            ),
            "prompt": _latency_summary(
                _numeric(selected, "prompt_ms", milliseconds=True)
            ),
            "generation": _latency_summary(
                _numeric(selected, "predicted_ms", milliseconds=True)
            ),
            "cache_n_median": (
                statistics.median(_numeric(selected, "cache_n"))
                if _numeric(selected, "cache_n")
                else None
            ),
            "prompt_n_median": (
                statistics.median(_numeric(selected, "prompt_n"))
                if _numeric(selected, "prompt_n")
                else None
            ),
            "predicted_n_median": (
                statistics.median(_numeric(selected, "predicted_n"))
                if _numeric(selected, "predicted_n")
                else None
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


def _run_profile(profile: str) -> dict[str, Any]:
    if profile == "baseline":
        os.environ.pop(_ENVIRONMENT_VARIABLE, None)
    elif profile == "graph":
        os.environ[_ENVIRONMENT_VARIABLE] = "1"
    else:
        raise ValueError(f"unknown profile: {profile}")

    arm = _run_arm("auto")
    case_elapsed = [
        float(case["elapsed_seconds"]) for case in arm["cases"]
    ]
    return {
        "profile": profile,
        "environment": {
            _ENVIRONMENT_VARIABLE: os.environ.get(_ENVIRONMENT_VARIABLE),
        },
        "cases": arm["cases"],
        "posts": arm["posts"],
        "case_latency": _latency_summary(case_elapsed),
        "stage_summary": _detailed_stage_summary(arm["posts"]),
    }


def _delta(candidate: float | None, baseline: float | None) -> dict[str, Any]:
    if candidate is None or baseline is None:
        return {"seconds": None, "percent": None}
    return {
        "seconds": candidate - baseline,
        "percent": (
            ((candidate / baseline) - 1.0) * 100.0 if baseline else None
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--arm-order",
        choices=("baseline-graph", "graph-baseline"),
        default="baseline-graph",
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

    os.environ.pop("BAXY_MIND_LLM_ENDPOINT", None)
    os.environ["BAXY_MIND_LLAMA_SERVER"] = str(server)
    os.environ["BAXY_MIND_LLM_GGUF"] = str(model)
    os.environ["BAXY_MIND_NGL"] = "99"
    os.environ["BAXY_MIND_LLM_REQUEST_TIMEOUT"] = "19"

    arm_order = args.arm_order.split("-")
    arms = [_run_profile(profile) for profile in arm_order]
    by_profile = {arm["profile"]: arm for arm in arms}
    baseline = by_profile["baseline"]
    graph = by_profile["graph"]

    baseline_cases = [
        _case_projection(case) for case in baseline["cases"]
    ]
    graph_cases = [_case_projection(case) for case in graph["cases"]]
    divergent_cases = [
        {
            "case": control["case"],
            "baseline": control,
            "graph": candidate,
        }
        for control, candidate in zip(
            baseline_cases,
            graph_cases,
            strict=True,
        )
        if control != candidate
    ]

    baseline_posts = [
        _post_projection(record) for record in baseline["posts"]
    ]
    graph_posts = [_post_projection(record) for record in graph["posts"]]
    divergent_posts = [
        {
            "index": index,
            "baseline": control,
            "graph": candidate,
        }
        for index, (control, candidate) in enumerate(
            zip(baseline_posts, graph_posts, strict=True)
        )
        if control != candidate
    ]

    exact_outputs = not divergent_cases and not divergent_posts
    mode_contracts = all(
        case["decision"].get("mode") == case["expected_mode"]
        for arm in arms
        for case in arm["cases"]
    )
    payloads_identical = [
        (record["case"], record["stage"], record["payload_sha256"])
        for record in baseline["posts"]
    ] == [
        (record["case"], record["stage"], record["payload_sha256"])
        for record in graph["posts"]
    ]

    latency_delta = {
        metric: _delta(
            graph["case_latency"][metric],
            baseline["case_latency"][metric],
        )
        for metric in (
            "p50_seconds",
            "p95_seconds",
            "max_seconds",
            "total_seconds",
        )
    }
    result = {
        "schema": "baxy.llama-cuda-graph-opt-ab.v1",
        "arm_order": arm_order,
        "server": str(server),
        "server_sha256": _sha256(server),
        "model": str(model),
        "safety": {
            "core_started": False,
            "external_effects_executed": False,
        },
        "control": {
            "only_variable": (
                "GGML_CUDA_GRAPH_OPT absent versus exactly 1 in the fresh "
                "llama-server child environment"
            ),
            "cuda_graphs_disabled": False,
            "fresh_server_per_arm": True,
            "same_model": True,
            "same_case_order": True,
            "case_count_per_arm": len(CASES),
            "parallel": 3,
            "context_per_slot": 4_096,
            "temperature": 0.0,
            "seed": 0,
        },
        "payloads_identical": payloads_identical,
        "exact_outputs": exact_outputs,
        "mode_contracts": mode_contracts,
        "divergent_cases": divergent_cases,
        "divergent_posts": divergent_posts,
        "latency_delta_graph_minus_baseline": latency_delta,
        "arms": arms,
        "candidate_status": "research_only",
        "promotion_rule": (
            "Require identical payload fingerprints, exact decisions, token "
            "counts and response content; all mode contracts; opposite-order "
            "replication; a repeatable end-to-end gain; and no material p95 "
            "or max regression before touching the runtime profile."
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
                    "payloads_identical",
                    "exact_outputs",
                    "mode_contracts",
                    "latency_delta_graph_minus_baseline",
                    "candidate_status",
                )
            },
            ensure_ascii=False,
        )
    )
    return 0 if payloads_identical and exact_outputs and mode_contracts else 2


if __name__ == "__main__":
    raise SystemExit(main())
