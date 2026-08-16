"""Physical, effect-free A/B for the official external Gemma 4 MTP assistant.

The control arm is BAXY's registered b9980 target with speculation disabled.
The candidate adds the official Gemma 4 E2B assistant converted with the same
b9980 toolchain.  Every arm starts a fresh server; Core is never started and
no external effect is executed.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from pathlib import Path
from typing import Any

from benchmark_llama_b10182_mtp import (  # type: ignore[import-not-found]
    MtpRuntime as _EmbeddedMtpRuntime,
)
from benchmark_llama_ngram_mod import (  # type: ignore[import-not-found]
    _draft_summary,
)
from benchmark_llama_slot_pinning import (  # type: ignore[import-not-found]
    CASES,
    _case_projection,
    _run_case,
)
from benchmark_structured_top_k1 import (  # type: ignore[import-not-found]
    TARGET_STAGES,
    _case_decision_projection,
    _compare_pair,
    _file_sha256,
    _quantile,
    _stage_summary,
)


_PROFILES = ("baseline", "external-mtp")
_SMOKE_CASES = frozenset({"task_create_a", "knowledge_a"})


class ExternalMtpRuntime(_EmbeddedMtpRuntime):
    def __init__(
        self,
        profile: str,
        run_id: str,
        *,
        draft_model: Path,
        draft_n_max: int,
        draft_p_min: float,
        draft_device: str,
        draft_gpu_device: str,
    ) -> None:
        if profile not in _PROFILES:
            raise ValueError(f"unknown external MTP profile: {profile}")
        if draft_n_max <= 0:
            raise ValueError("draft_n_max must be positive")
        if draft_device not in {"gpu", "cpu"}:
            raise ValueError(f"unknown draft device: {draft_device}")
        self._external_profile = profile
        self._external_draft_model = draft_model.resolve()
        self._external_draft_n_max = draft_n_max
        self._external_draft_p_min = draft_p_min
        self._external_draft_device = draft_device
        self._external_draft_gpu_device = draft_gpu_device
        embedded_profile = "none" if profile == "baseline" else "draft-mtp"
        super().__init__(embedded_profile, run_id)
        self._server_log_path = (
            Path("artifacts/fixes")
            / f"llama_external_mtp_{run_id}_{time.time_ns()}.log"
        ).resolve()

    def _record_profile(self) -> str:
        return self._external_profile

    def _server_command(self) -> list[str]:
        command = super()._server_command()
        spec_index = command.index("--spec-type")
        if self._external_profile == "baseline":
            if command[spec_index + 1] != "none":
                raise AssertionError("baseline must disable speculative decoding")
            return command

        if command[spec_index + 1] != "draft-mtp":
            raise AssertionError("candidate must use draft-mtp")
        n_max_index = command.index("--spec-draft-n-max")
        command[n_max_index + 1] = str(self._external_draft_n_max)
        command.extend(
            [
                "--spec-draft-model",
                str(self._external_draft_model),
                "--spec-draft-p-min",
                str(self._external_draft_p_min),
            ]
        )
        if self._external_draft_device == "gpu":
            command.extend(
                [
                    "--spec-draft-device",
                    self._external_draft_gpu_device,
                    "--spec-draft-ngl",
                    "99",
                ]
            )
        else:
            command.extend(
                [
                    "--spec-draft-device",
                    "none",
                    "--spec-draft-ngl",
                    "0",
                ]
            )
        return command

    def _post(
        self,
        payload: dict[str, Any],
        timeout: float | None = None,
        *,
        max_attempts: int = 2,
        cancellation: Any = None,
    ) -> dict[str, Any]:
        wire = dict(payload)
        # MTP is server-global, so chat must receive the same response-only
        # token observability as the structured stages.
        wire["verbose"] = True
        wire["return_tokens"] = True
        return super()._post(
            wire,
            timeout,
            max_attempts=max_attempts,
            cancellation=cancellation,
        )


def _selected_cases(smoke: bool) -> tuple[Any, ...]:
    if not smoke:
        return tuple(CASES)
    selected = tuple(case for case in CASES if case.name in _SMOKE_CASES)
    if {case.name for case in selected} != _SMOKE_CASES:
        raise AssertionError("smoke workload no longer matches canonical cases")
    return selected


def _run_arm(
    profile: str,
    run_id: str,
    *,
    cases_to_run: tuple[Any, ...],
    draft_model: Path,
    draft_n_max: int,
    draft_p_min: float,
    draft_device: str,
    draft_gpu_device: str,
) -> dict[str, Any]:
    runtime = ExternalMtpRuntime(
        profile,
        run_id,
        draft_model=draft_model,
        draft_n_max=draft_n_max,
        draft_p_min=draft_p_min,
        draft_device=draft_device,
        draft_gpu_device=draft_gpu_device,
    )
    cases: list[dict[str, Any]] = []
    server_pid: int | None = None
    started = time.perf_counter()
    command_projection = _command_projection(runtime)
    try:
        runtime.start_warmup()
        if not runtime.wait_warmup(420.0):
            raise TimeoutError("llama-server did not become ready")
        process = runtime._process
        if process is None or process.poll() is not None:
            raise RuntimeError("fresh llama-server child is not alive")
        server_pid = process.pid
        ready_seconds = time.perf_counter() - started
        for case in cases_to_run:
            cases.append(_run_case(runtime, case))
    finally:
        owned_process = runtime._process
        runtime.close()
        if owned_process is not None and owned_process.poll() is None:
            raise RuntimeError("llama-server child survived runtime.close()")

    elapsed = [float(case["elapsed_seconds"]) for case in cases]
    targeted = [
        record
        for record in runtime._benchmark_records
        if record["stage"] in TARGET_STAGES
    ]
    return {
        "run_id": run_id,
        "profile": profile,
        "server_pid": server_pid,
        "spec_type": "none" if profile == "baseline" else "draft-mtp",
        "server_log": str(runtime._server_log_path),
        "server_ready_seconds": ready_seconds,
        "command_projection": command_projection,
        "cases": cases,
        "case_projection": [_case_projection(case) for case in cases],
        "decision_projection": [
            _case_decision_projection(case) for case in cases
        ],
        "all_post_projection": [
            {
                key: record.get(key)
                for key in (
                    "case",
                    "stage",
                    "stage_ordinal",
                    "payload_sha256_without_instrumentation_or_candidate",
                    "content",
                    "raw_content",
                    "tokens",
                    "finish_reason",
                )
            }
            for record in runtime._benchmark_records
        ],
        "posts": runtime._benchmark_records,
        "stage_summary": _stage_summary(runtime._benchmark_records),
        "draft_summary": _draft_summary(runtime._benchmark_records),
        "structured_elapsed_total_seconds": sum(
            float(record["elapsed_seconds"]) for record in targeted
        ),
        "case_elapsed_total_seconds": sum(elapsed),
        "case_elapsed_p50_seconds": statistics.median(elapsed),
        "case_elapsed_p95_seconds": _quantile(elapsed, 0.95),
        "case_elapsed_max_seconds": max(elapsed),
    }


def _arm_plan(order: str) -> list[tuple[str, str]]:
    if order == "baseline-candidate":
        return [
            ("order1-baseline", "baseline"),
            ("order1-candidate", "external-mtp"),
        ]
    if order == "candidate-baseline":
        return [
            ("order2-candidate", "external-mtp"),
            ("order2-baseline", "baseline"),
        ]
    if order == "both":
        return [
            ("order1-baseline", "baseline"),
            ("order1-candidate", "external-mtp"),
            ("order2-candidate", "external-mtp"),
            ("order2-baseline", "baseline"),
        ]
    raise ValueError(f"unknown order: {order}")


def _manifest_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        return Path("__missing_local_app_data__")
    return Path(local_app_data) / "BAXYRuntime" / "mind-runtime-v1.json"


def _file_snapshot(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"exists": False, "sha256": None, "size": None, "mtime_ns": None}
    stat = path.stat()
    return {
        "exists": True,
        "sha256": _file_sha256(path),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def _registered_runtime_contract(
    manifest: Path,
    *,
    server: Path,
    model: Path,
) -> dict[str, Any]:
    if not manifest.is_file():
        return {"passed": False, "reason": "runtime manifest is missing"}
    try:
        descriptor = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {"passed": False, "reason": f"invalid runtime manifest: {exc}"}
    registered_server = Path(str(descriptor.get("llama_server") or ""))
    registered_model = Path(str(descriptor.get("gguf") or ""))
    server_hash = _file_sha256(server)
    model_hash = _file_sha256(model)
    checks = {
        "schema": descriptor.get("schema") == "baxy-mind-runtime-v1",
        "server_path": (
            registered_server.is_file()
            and registered_server.resolve() == server.resolve()
        ),
        "model_path": (
            registered_model.is_file()
            and registered_model.resolve() == model.resolve()
        ),
        "server_hash": (
            str(descriptor.get("llama_server_sha256") or "").lower()
            == server_hash.lower()
        ),
        "model_hash": (
            str(descriptor.get("gguf_sha256") or "").lower()
            == model_hash.lower()
        ),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "registered_server": str(registered_server),
        "registered_model": str(registered_model),
        "server_sha256": server_hash,
        "model_sha256": model_hash,
    }


def _command_projection(runtime: ExternalMtpRuntime) -> dict[str, Any]:
    command = runtime._server_command()

    def value(flag: str) -> str | None:
        return command[command.index(flag) + 1] if flag in command else None

    return {
        "spec_type": value("--spec-type"),
        "spec_draft_model": value("--spec-draft-model"),
        "spec_draft_n_max": value("--spec-draft-n-max"),
        "spec_draft_p_min": value("--spec-draft-p-min"),
        "spec_draft_device": value("--spec-draft-device"),
        "spec_draft_ngl": value("--spec-draft-ngl"),
        "cache_type_k": value("-ctk"),
        "cache_type_v": value("-ctv"),
        "flash_attention": value("-fa"),
        "parallel": value("-np"),
        "context_total": value("-c"),
        "duplicate_spec_flags": {
            flag: command.count(flag)
            for flag in (
                "--spec-type",
                "--spec-draft-model",
                "--spec-draft-n-max",
                "--spec-draft-p-min",
                "--spec-draft-device",
                "--spec-draft-ngl",
            )
            if command.count(flag) > 1
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--draft-model", type=Path, required=True)
    parser.add_argument("--draft-n-max", type=int, default=1)
    parser.add_argument("--draft-p-min", type=float, default=0.0)
    parser.add_argument(
        "--draft-device",
        choices=("gpu", "cpu"),
        default="gpu",
    )
    parser.add_argument("--draft-gpu-device", default="CUDA0")
    parser.add_argument(
        "--arm-order",
        choices=("both", "baseline-candidate", "candidate-baseline"),
        default="both",
    )
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
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
    if args.draft_n_max <= 0:
        parser.error("--draft-n-max must be positive")
    if not 0.0 <= args.draft_p_min <= 1.0:
        parser.error("--draft-p-min must be between 0 and 1")
    missing = [
        path
        for path in (args.server, args.model, args.draft_model)
        if not path.is_file()
    ]
    if missing:
        raise FileNotFoundError(
            "external MTP audit assets are missing: "
            + ", ".join(str(path) for path in missing)
        )

    os.environ.pop("BAXY_MIND_LLM_ENDPOINT", None)
    os.environ.pop("GGML_CUDA_GRAPH_OPT", None)
    os.environ.pop("CUDA_MODULE_LOADING", None)
    os.environ["BAXY_MIND_LLAMA_SERVER"] = str(args.server.resolve())
    os.environ["BAXY_MIND_LLM_GGUF"] = str(args.model.resolve())
    os.environ["BAXY_MIND_NGL"] = "99"
    os.environ["BAXY_MIND_CTX"] = "4096"
    os.environ["BAXY_MIND_LLM_REQUEST_TIMEOUT"] = "19"

    if args.validate_only:
        validations: dict[str, Any] = {}
        for profile in _PROFILES:
            runtime = ExternalMtpRuntime(
                profile,
                f"validate-{profile}",
                draft_model=args.draft_model,
                draft_n_max=args.draft_n_max,
                draft_p_min=args.draft_p_min,
                draft_device=args.draft_device,
                draft_gpu_device=args.draft_gpu_device,
            )
            try:
                validations[profile] = _command_projection(runtime)
                if runtime._process is not None:
                    raise AssertionError("validate-only started a server process")
            finally:
                runtime.close()
        print(json.dumps(validations, ensure_ascii=False, indent=2))
        return 0

    manifest = _manifest_path()
    manifest_before = _file_snapshot(manifest)
    registered_runtime = _registered_runtime_contract(
        manifest,
        server=args.server,
        model=args.model,
    )
    cases_to_run = _selected_cases(args.smoke)
    arms = [
        _run_arm(
            profile,
            run_id,
            cases_to_run=cases_to_run,
            draft_model=args.draft_model,
            draft_n_max=args.draft_n_max,
            draft_p_min=args.draft_p_min,
            draft_device=args.draft_device,
            draft_gpu_device=args.draft_gpu_device,
        )
        for run_id, profile in _arm_plan(args.arm_order)
    ]
    manifest_after = _file_snapshot(manifest)
    by_id = {arm["run_id"]: arm for arm in arms}
    comparisons: list[dict[str, Any]] = []
    exact_case_outputs: list[dict[str, Any]] = []

    def compare(pair_id: str, baseline_id: str, candidate_id: str) -> None:
        baseline = by_id[baseline_id]
        candidate = by_id[candidate_id]
        comparison = _compare_pair(
            pair_id=pair_id,
            baseline=baseline,
            candidate=candidate,
        )
        comparison["candidate_minus_baseline_case_p95_seconds"] = (
            float(candidate["case_elapsed_p95_seconds"])
            - float(baseline["case_elapsed_p95_seconds"])
        )
        comparison["candidate_minus_baseline_case_max_seconds"] = (
            float(candidate["case_elapsed_max_seconds"])
            - float(baseline["case_elapsed_max_seconds"])
        )
        comparisons.append(comparison)
        exact_case_outputs.append(
            {
                "pair_id": pair_id,
                "equal": (
                    baseline["case_projection"]
                    == candidate["case_projection"]
                ),
                "all_posts_equal": (
                    baseline["all_post_projection"]
                    == candidate["all_post_projection"]
                ),
            }
        )

    if args.arm_order in {"both", "baseline-candidate"}:
        compare(
            "baseline-then-candidate",
            "order1-baseline",
            "order1-candidate",
        )
    if args.arm_order in {"both", "candidate-baseline"}:
        compare(
            "candidate-then-baseline",
            "order2-baseline",
            "order2-candidate",
        )

    stage_coverage = all(
        arm["stage_summary"][stage]["calls"] > 0
        for arm in arms
        for stage in TARGET_STAGES
    )
    mode_contracts = all(
        case["decision"].get("mode") == case["expected_mode"]
        for arm in arms
        for case in arm["cases"]
    )
    exact_equivalence = (
        all(
            item["equal"] and item["all_posts_equal"]
            for item in exact_case_outputs
        )
        and all(
            comparison["payloads_equal"]
            and comparison["contents_equal"]
            and comparison["raw_contents_equal"]
            and comparison["raw_tokens_available"]
            and comparison["tokens_equal"]
            and comparison["final_decisions_equal"]
            for comparison in comparisons
        )
    )
    candidate_drafted = all(
        arm["draft_summary"]["draft_n_total"] > 0.0
        for arm in arms
        if arm["profile"] == "external-mtp"
    )
    candidate_accepted = all(
        0.0 < arm["draft_summary"]["draft_n_accepted_total"]
        <= arm["draft_summary"]["draft_n_total"]
        for arm in arms
        if arm["profile"] == "external-mtp"
    )
    baseline_without_drafts = all(
        arm["draft_summary"]["draft_n_total"] == 0.0
        and arm["draft_summary"]["draft_n_accepted_total"] == 0.0
        for arm in arms
        if arm["profile"] == "baseline"
    )
    fresh_server_per_arm = (
        all(isinstance(arm["server_pid"], int) for arm in arms)
        and len({arm["server_pid"] for arm in arms}) == len(arms)
    )
    opposite_order_improvement = (
        len(comparisons) == 2
        and all(
            comparison["candidate_minus_baseline_structured_total_seconds"]
            < 0.0
            and comparison["candidate_minus_baseline_case_p50_seconds"] < 0.0
            and comparison["candidate_minus_baseline_case_total_seconds"] < 0.0
            for comparison in comparisons
        )
    )
    tail_not_worse = (
        len(comparisons) == 2
        and all(
            comparison["candidate_minus_baseline_case_p95_seconds"] <= 0.0
            and comparison["candidate_minus_baseline_case_max_seconds"] <= 0.0
            for comparison in comparisons
        )
    )
    manifest_unchanged = manifest_before == manifest_after
    command_contracts = all(
        not arm["command_projection"]["duplicate_spec_flags"]
        and arm["command_projection"]["cache_type_k"] == "q8_0"
        and arm["command_projection"]["cache_type_v"] == "q8_0"
        and arm["command_projection"]["flash_attention"] == "on"
        and arm["command_projection"]["parallel"] == "3"
        and arm["command_projection"]["context_total"] == "12288"
        and (
            (
                arm["profile"] == "baseline"
                and arm["command_projection"]["spec_type"] == "none"
                and arm["command_projection"]["spec_draft_model"] is None
            )
            or (
                arm["profile"] == "external-mtp"
                and arm["command_projection"]["spec_type"] == "draft-mtp"
                and arm["command_projection"]["spec_draft_model"]
                == str(args.draft_model.resolve())
            )
        )
        for arm in arms
    )
    valid_measurement = (
        stage_coverage
        and mode_contracts
        and exact_equivalence
        and candidate_drafted
        and candidate_accepted
        and baseline_without_drafts
        and fresh_server_per_arm
        and manifest_unchanged
        and bool(registered_runtime["passed"])
        and command_contracts
    )
    promotion_gate_passed = (
        not args.smoke
        and args.arm_order == "both"
        and valid_measurement
        and opposite_order_improvement
        and tail_not_worse
    )
    result = {
        "schema": "baxy.llama-external-mtp-ab.v1",
        "candidate_status": (
            "promotion_ready" if promotion_gate_passed else "research_only"
        ),
        "smoke": args.smoke,
        "arm_order": args.arm_order,
        "runtime": {
            "release": "b9980",
            "server": str(args.server.resolve()),
            "server_sha256": _file_sha256(args.server),
            "model": str(args.model.resolve()),
            "model_sha256": _file_sha256(args.model),
            "cache_type_k": "q8_0",
            "cache_type_v": "q8_0",
            "flash_attention": "on",
            "parallel": 3,
            "context_per_slot": 4_096,
        },
        "candidate": {
            "spec_type": "draft-mtp",
            "draft_model": str(args.draft_model.resolve()),
            "draft_model_sha256": _file_sha256(args.draft_model),
            "spec_draft_n_max": args.draft_n_max,
            "spec_draft_p_min": args.draft_p_min,
            "draft_device": args.draft_device,
            "draft_gpu_device": (
                args.draft_gpu_device if args.draft_device == "gpu" else None
            ),
        },
        "control": {
            "candidate_delta": (
                "official external draft model plus draft-mtp flags"
            ),
            "fresh_server_per_arm": True,
            "same_payloads": True,
            "case_count_per_arm": len(cases_to_run),
            "core_started": False,
            "external_effects_executed": False,
            "installed": False,
            "runtime_manifest": str(manifest),
            "runtime_manifest_before": manifest_before,
            "runtime_manifest_after": manifest_after,
            "runtime_manifest_unchanged": manifest_unchanged,
            "registered_runtime_contract": registered_runtime,
            "command_contracts": command_contracts,
        },
        "measurement": {
            "raw_structured_tokens": (
                "llama.cpp b9980 __verbose.tokens via identical "
                "verbose=true and return_tokens=true"
            ),
            "visible_chat_reply_in_case_projection": True,
            "draft_metrics": [
                "timings.draft_n",
                "timings.draft_n_accepted",
            ],
            "server_ready_seconds": True,
            "end_to_end_case_latency": True,
            "stage_latency": list(TARGET_STAGES),
        },
        "stage_coverage": stage_coverage,
        "mode_contracts": mode_contracts,
        "exact_case_outputs": exact_case_outputs,
        "exact_equivalence": exact_equivalence,
        "candidate_drafted": candidate_drafted,
        "candidate_accepted": candidate_accepted,
        "baseline_without_drafts": baseline_without_drafts,
        "fresh_server_per_arm": fresh_server_per_arm,
        "command_contracts": command_contracts,
        "opposite_order_improvement": opposite_order_improvement,
        "tail_not_worse": tail_not_worse,
        "valid_measurement": valid_measurement,
        "comparisons": comparisons,
        "arms": arms,
        "promotion_gate_passed": promotion_gate_passed,
        "promotion_rule": (
            "Require a full six-case run in both orders; generated drafts; "
            "unchanged runtime manifest; exact structured raw tokens/content, "
            "visible replies, operations and final decisions; full P/G/L/V/C/E "
            "coverage; lower structured total, turn p50 and turn total; and no "
            "p95/max regression in both opposite-order pairs."
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
                    "stage_coverage",
                    "mode_contracts",
                    "exact_equivalence",
                    "candidate_drafted",
                    "candidate_accepted",
                    "baseline_without_drafts",
                    "fresh_server_per_arm",
                    "opposite_order_improvement",
                    "tail_not_worse",
                    "valid_measurement",
                    "promotion_gate_passed",
                    "comparisons",
                )
            },
            ensure_ascii=False,
        )
    )
    return 0 if valid_measurement else 2


if __name__ == "__main__":
    raise SystemExit(main())
