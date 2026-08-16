"""Physical, effect-free A/B between two llama.cpp server builds.

The experiment keeps BAXY's model, prompts, schemas, runtime flags, case order
and request code fixed.  Only ``BAXY_MIND_LLAMA_SERVER`` changes between fresh
server processes.  It exercises LLM decisions, argument extraction and chat,
but never starts Core or executes a catalog operation.
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
    _case_projection,
    _run_arm,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_version(
    profile: str,
    server: Path,
    model: Path,
) -> dict[str, Any]:
    os.environ.pop("BAXY_MIND_LLM_ENDPOINT", None)
    os.environ["BAXY_MIND_LLAMA_SERVER"] = str(server)
    os.environ["BAXY_MIND_LLM_GGUF"] = str(model)
    os.environ["BAXY_MIND_NGL"] = "99"
    os.environ["BAXY_MIND_LLM_REQUEST_TIMEOUT"] = "19"
    arm = _run_arm("auto")
    elapsed = [float(case["elapsed_seconds"]) for case in arm["cases"]]
    return {
        "profile": profile,
        "server": str(server.resolve()),
        "server_sha256": _sha256(server),
        "cases": arm["cases"],
        "posts": arm["posts"],
        "stage_summary": arm["stage_summary"],
        "elapsed_p50_seconds": statistics.median(elapsed),
        "elapsed_total_seconds": sum(elapsed),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--arm-order",
        choices=("old-new", "new-old"),
        default="old-new",
    )
    parser.add_argument("--old-server", type=Path, required=True)
    parser.add_argument("--new-server", type=Path, required=True)
    parser.add_argument(
        "--model",
        type=Path,
        default=Path(
            r"D:\BAXYRuntime\assets\models"
            r"\gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf"
        ),
    )
    args = parser.parse_args()
    servers = {
        "old": args.old_server.resolve(),
        "new": args.new_server.resolve(),
    }
    for label, path in (*servers.items(), ("model", args.model)):
        if not path.is_file():
            raise FileNotFoundError(f"{label} runtime asset is missing: {path}")

    arm_order = args.arm_order.split("-")
    arms = [
        _run_version(profile, servers[profile], args.model.resolve())
        for profile in arm_order
    ]
    by_profile = {arm["profile"]: arm for arm in arms}
    old_projection = [
        _case_projection(case) for case in by_profile["old"]["cases"]
    ]
    new_projection = [
        _case_projection(case) for case in by_profile["new"]["cases"]
    ]
    divergent_cases = [
        {
            "case": old["case"],
            "old": old,
            "new": new,
        }
        for old, new in zip(old_projection, new_projection, strict=True)
        if old != new
    ]
    exact_outputs = not divergent_cases
    old_p50 = float(by_profile["old"]["elapsed_p50_seconds"])
    new_p50 = float(by_profile["new"]["elapsed_p50_seconds"])
    old_total = float(by_profile["old"]["elapsed_total_seconds"])
    new_total = float(by_profile["new"]["elapsed_total_seconds"])
    result = {
        "schema": "baxy.llama-version-ab.v1",
        "arm_order": arm_order,
        "safety": {
            "core_started": False,
            "external_effects_executed": False,
        },
        "control": {
            "only_variable": "llama-server build and adjacent runtime DLLs",
            "same_model": str(args.model.resolve()),
            "same_case_order": True,
            "fresh_server_per_arm": True,
            "parallel": 3,
            "context_per_slot": 4096,
            "temperature": 0.0,
            "seed": 0,
        },
        "exact_outputs": exact_outputs,
        "divergent_cases": divergent_cases,
        "latency_delta_new_minus_old": {
            "p50_seconds": new_p50 - old_p50,
            "p50_percent": (
                ((new_p50 / old_p50) - 1.0) * 100.0 if old_p50 else None
            ),
            "total_seconds": new_total - old_total,
            "total_percent": (
                ((new_total / old_total) - 1.0) * 100.0 if old_total else None
            ),
        },
        "arms": arms,
        "candidate_status": "research_only",
        "promotion_rule": (
            "Require exact normalized outputs and an opposite-order replica "
            "with a repeatable end-to-end gain and no material tail regression."
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
                    "exact_outputs",
                    "divergent_cases",
                    "latency_delta_new_minus_old",
                    "candidate_status",
                )
            },
            ensure_ascii=False,
        )
    )
    return 0 if exact_outputs else 2


if __name__ == "__main__":
    raise SystemExit(main())
