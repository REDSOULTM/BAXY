"""Physical A/B for llama.cpp unified KV in BAXY's three-slot GPU profile."""

from __future__ import annotations

import argparse
import json
import os
import statistics
from pathlib import Path
from typing import Any

from benchmark_llama_slot_pinning import (  # type: ignore[import-not-found]
    CASES,
    InstrumentedRuntime,
    _case_projection,
    _run_case,
    _stage_summary,
)


class KvRuntime(InstrumentedRuntime):
    def __init__(self, profile: str) -> None:
        self._kv_profile = profile
        super().__init__(profile)

    def _server_command(self) -> list[str]:
        command = super()._server_command()
        if self._kv_profile == "unified":
            command.append("--kv-unified")
        return command


def _run_arm(profile: str) -> dict[str, Any]:
    runtime = KvRuntime(profile)
    cases: list[dict[str, Any]] = []
    try:
        runtime.start_warmup()
        if not runtime.wait_warmup(420.0):
            raise TimeoutError("llama-server did not become ready")
        for case in CASES:
            cases.append(_run_case(runtime, case))
    finally:
        runtime.close()
    elapsed = [float(case["elapsed_seconds"]) for case in cases]
    return {
        "profile": profile,
        "cases": cases,
        "posts": runtime._benchmark_records,
        "stage_summary": _stage_summary(runtime._benchmark_records),
        "elapsed_p50_seconds": statistics.median(elapsed),
        "elapsed_total_seconds": sum(elapsed),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--arm-order",
        choices=("separate-unified", "unified-separate"),
        default="separate-unified",
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
    if not args.server.is_file() or not args.model.is_file():
        raise FileNotFoundError("official runtime assets are missing")

    os.environ.pop("BAXY_MIND_LLM_ENDPOINT", None)
    os.environ["BAXY_MIND_LLAMA_SERVER"] = str(args.server)
    os.environ["BAXY_MIND_LLM_GGUF"] = str(args.model)
    os.environ["BAXY_MIND_NGL"] = "99"
    os.environ["BAXY_MIND_LLM_REQUEST_TIMEOUT"] = "19"

    arm_order = args.arm_order.split("-")
    arms = [_run_arm(profile) for profile in arm_order]
    by_profile = {arm["profile"]: arm for arm in arms}
    separate_projection = [
        _case_projection(case) for case in by_profile["separate"]["cases"]
    ]
    unified_projection = [
        _case_projection(case) for case in by_profile["unified"]["cases"]
    ]
    exact_outputs = separate_projection == unified_projection
    mode_contracts = all(
        case["decision"].get("mode") == case["expected_mode"]
        for arm in arms
        for case in arm["cases"]
    )
    result = {
        "schema": "baxy.llama-kv-unified-ab.v1",
        "arm_order": arm_order,
        "runtime": {
            "server": str(args.server.resolve()),
            "model": str(args.model.resolve()),
            "parallel": 3,
            "context_per_slot": 4096,
        },
        "exact_outputs": exact_outputs,
        "mode_contracts": mode_contracts,
        "arms": arms,
        "candidate_status": "research_only",
        "promotion_rule": (
            "Promote only after opposite-order replicas preserve every output "
            "and show stable end-to-end improvement without tail regression."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0 if exact_outputs and mode_contracts else 2


if __name__ == "__main__":
    raise SystemExit(main())
