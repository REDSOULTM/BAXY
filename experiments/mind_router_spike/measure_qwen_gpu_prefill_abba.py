"""ABBA gate for llama.cpp memory placement on BAXY's registered Qwen.

The experiment may change logical/physical prefill batch, KV placement and
the number of model blocks resident on GPU. Model weights, 4K context per
slot, three-way concurrency, prompts and workload remain identical. No
catalog operation is executed.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.baxy_runtime_config import (  # noqa: E402
    DEFAULT_RUNTIME_MANIFEST,
    file_sha256,
    public_runtime_identity,
    resolve_runtime,
)
from scripts.measure_mind_budget import (  # noqa: E402
    CPU_TURN_P50_BUDGET_SECONDS,
    CPU_VRAM_TOLERANCE_MIB,
    GPU_VRAM_BUDGET_MIB,
    current_core_capabilities,
    discover_core,
    evaluate_profile,
    run_profile,
    write_json_atomic,
)


ORDER = ("control", "candidate", "candidate", "control")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ABBA físico de buffers de prefill del Qwen registrado."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO
        / "artifacts"
        / "development"
        / "qwen_gpu_prefill_abba.v1.json",
    )
    parser.add_argument("--control-batch", type=int, default=2048)
    parser.add_argument("--control-ubatch", type=int, default=512)
    parser.add_argument("--candidate-batch", type=int, default=512)
    parser.add_argument("--candidate-ubatch", type=int, default=128)
    parser.add_argument(
        "--candidate-kv-offload",
        choices=("on", "off"),
        default="on",
    )
    parser.add_argument(
        "--candidate-kv-cache-type",
        choices=("q8_0", "q4_0"),
        default="q8_0",
    )
    parser.add_argument("--candidate-gpu-layers", type=int)
    return parser.parse_args()


def _median(values: list[float]) -> float:
    return round(statistics.median(values), 3) if values else 0.0


def _signatures(run: dict[str, Any], key: str) -> dict[str, str]:
    return {
        str(item["case_id"]): str(item[key])
        for item in run["response_signatures"]
    }


def run_experiment(args: argparse.Namespace) -> dict[str, Any]:
    runtime = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    capabilities = current_core_capabilities(discover_core(None))
    candidate_gpu_layers = (
        runtime.gpu_layers
        if args.candidate_gpu_layers is None
        else args.candidate_gpu_layers
    )
    if not 0 <= candidate_gpu_layers <= runtime.gpu_layers:
        raise ValueError("candidate_gpu_layers fuera del runtime registrado")
    profiles = {
        "control": (
            args.control_batch,
            args.control_ubatch,
            "on",
            "q8_0",
            runtime.gpu_layers,
        ),
        "candidate": (
            args.candidate_batch,
            args.candidate_ubatch,
            args.candidate_kv_offload,
            args.candidate_kv_cache_type,
            candidate_gpu_layers,
        ),
    }
    previous_batch = os.environ.get("BAXY_MIND_BATCH")
    previous_ubatch = os.environ.get("BAXY_MIND_UBATCH")
    previous_kv_offload = os.environ.get("BAXY_MIND_KV_OFFLOAD")
    previous_kv_cache_type = os.environ.get("BAXY_MIND_KV_CACHE_TYPE")
    runs: list[dict[str, Any]] = []
    try:
        for index, arm in enumerate(ORDER, start=1):
            batch, ubatch, kv_offload, kv_cache_type, gpu_layers = profiles[arm]
            os.environ["BAXY_MIND_BATCH"] = str(batch)
            os.environ["BAXY_MIND_UBATCH"] = str(ubatch)
            os.environ["BAXY_MIND_KV_OFFLOAD"] = "1" if kv_offload == "on" else "0"
            os.environ["BAXY_MIND_KV_CACHE_TYPE"] = kv_cache_type
            measured = evaluate_profile(
                "gpu",
                run_profile(
                    "gpu",
                    replace(runtime, gpu_layers=gpu_layers),
                    capabilities,
                ),
                gpu_vram_budget_mib=GPU_VRAM_BUDGET_MIB,
                cpu_vram_tolerance_mib=CPU_VRAM_TOLERANCE_MIB,
                cpu_turn_p50_budget_seconds=CPU_TURN_P50_BUDGET_SECONDS,
            )
            runs.append(
                {
                    "sequence": index,
                    "arm": arm,
                    "batch": batch,
                    "ubatch": ubatch,
                    "kv_offload": kv_offload,
                    "kv_cache_type": kv_cache_type,
                    "gpu_layers": gpu_layers,
                    **measured,
                }
            )
    finally:
        if previous_batch is None:
            os.environ.pop("BAXY_MIND_BATCH", None)
        else:
            os.environ["BAXY_MIND_BATCH"] = previous_batch
        if previous_ubatch is None:
            os.environ.pop("BAXY_MIND_UBATCH", None)
        else:
            os.environ["BAXY_MIND_UBATCH"] = previous_ubatch
        if previous_kv_offload is None:
            os.environ.pop("BAXY_MIND_KV_OFFLOAD", None)
        else:
            os.environ["BAXY_MIND_KV_OFFLOAD"] = previous_kv_offload
        if previous_kv_cache_type is None:
            os.environ.pop("BAXY_MIND_KV_CACHE_TYPE", None)
        else:
            os.environ["BAXY_MIND_KV_CACHE_TYPE"] = previous_kv_cache_type

    contract_maps = [_signatures(run, "contract_sha256") for run in runs]
    complete_maps = [_signatures(run, "complete_reply_sha256") for run in runs]
    case_ids = sorted(set.intersection(*(set(value) for value in contract_maps)))
    contract_equal = sum(
        1 for case_id in case_ids if len({value[case_id] for value in contract_maps}) == 1
    )
    complete_equal = sum(
        1 for case_id in case_ids if len({value[case_id] for value in complete_maps}) == 1
    )
    by_arm = {
        arm: [run for run in runs if run["arm"] == arm]
        for arm in ("control", "candidate")
    }

    def arm_values(arm: str, key: str) -> list[float]:
        return [float(run[key]) for run in by_arm[arm]]

    control_turn_p95 = [
        float(run["latency_seconds"]["turn.decide"]["p95"])
        for run in by_arm["control"]
    ]
    candidate_turn_p95 = [
        float(run["latency_seconds"]["turn.decide"]["p95"])
        for run in by_arm["candidate"]
    ]
    checks = {
        "all_four_runs_completed": all(
            run["requests_completed"] == run["requests_expected"] for run in runs
        ),
        "zero_contract_errors": all(not run["errors"] for run in runs),
        "all_contract_projections_identical": (
            len(case_ids) == 45 and contract_equal == len(case_ids)
        ),
        "candidate_under_3072_mib_both_orders": all(
            float(run["process_tree_vram_peak_mib"]) <= GPU_VRAM_BUDGET_MIB
            for run in by_arm["candidate"]
        ),
        "candidate_reduces_vram_both_orders": all(
            float(candidate["process_tree_vram_peak_mib"])
            < float(control["process_tree_vram_peak_mib"])
            for control, candidate in zip(
                by_arm["control"],
                by_arm["candidate"],
                strict=True,
            )
        ),
        "candidate_turn_p95_not_over_120_percent": (
            _median(candidate_turn_p95) <= _median(control_turn_p95) * 1.20
        ),
    }
    return {
        "schema": "baxy.qwen-gpu-prefill-abba.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if all(checks.values()) else "failed",
        "scope": {
            "order": list(ORDER),
            "tree_frozen_during_measurement": True,
            "effects_executed": 0,
            "changed_variable": (
                "llama.cpp prefill buffers, KV format/placement and GPU layers"
            ),
            "context_tokens_per_slot": 4096,
            "parallel_slots": 3,
        },
        "source": {
            "llm_py_sha256": file_sha256(REPO / "src" / "baxy_mind" / "llm.py"),
            "budget_gate_sha256": file_sha256(
                REPO / "scripts" / "measure_mind_budget.py"
            ),
            "experiment_sha256": file_sha256(Path(__file__).resolve()),
        },
        "runtime": public_runtime_identity(runtime),
        "catalog_operations": len(capabilities),
        "profiles": {
            name: {
                "batch": value[0],
                "ubatch": value[1],
                "kv_offload": value[2],
                "kv_cache_type": value[3],
                "gpu_layers": value[4],
            }
            for name, value in profiles.items()
        },
        "checks": checks,
        "comparison": {
            "common_cases": len(case_ids),
            "contract_projections_identical": contract_equal,
            "complete_replies_identical": complete_equal,
            "control_vram_peak_mib_median": _median(
                arm_values("control", "process_tree_vram_peak_mib")
            ),
            "candidate_vram_peak_mib_median": _median(
                arm_values("candidate", "process_tree_vram_peak_mib")
            ),
            "control_turn_p95_seconds_median": _median(control_turn_p95),
            "candidate_turn_p95_seconds_median": _median(candidate_turn_p95),
        },
        "runs": runs,
    }


def main() -> int:
    args = parse_args()
    report = run_experiment(args)
    write_json_atomic(args.output.resolve(), report)
    print(
        json.dumps(
            {
                "schema": report["schema"],
                "status": report["status"],
                "checks": report["checks"],
                "comparison": report["comparison"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
