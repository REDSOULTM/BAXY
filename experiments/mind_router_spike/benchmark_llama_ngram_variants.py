"""Fail-closed physical A/B for llama.cpp b9980 n-gram variants.

This research-only harness reuses BAXY's existing ngram-mod benchmark
infrastructure while extending it to the other draftless implementations
advertised by the registered b9980 ``llama-server``:

* ``ngram-simple``;
* ``ngram-map-k``;
* ``ngram-map-k4v``;
* ``ngram-cache``;
* ``ngram-mod``.

Every candidate is compared with ``--spec-type none`` in fresh server
processes.  The model, q8 KV cache, Flash Attention, prompts, schemas, seeds,
scheduling and request payloads remain fixed.  Structured requests capture
raw generated token ids; case records capture final decisions, extractions,
detected language, free-form replies and end-to-end latency.  Core is never
started and no external effect is executed.

``--smoke`` runs one action and one conversation case in a single A/B order.
It is intentionally incapable of passing the promotion gate.  A full
promotion candidate requires both opposite orders, full structured-stage
coverage, exact output equivalence, actual generated drafts and repeatable
latency improvement.  Any missing evidence fails closed.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import statistics
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from benchmark_llama_kv_q4 import (  # type: ignore[import-not-found]
    KvQuantRuntime,
)
from benchmark_llama_ngram_mod import (  # type: ignore[import-not-found]
    _draft_summary,
)
from benchmark_llama_slot_pinning import (  # type: ignore[import-not-found]
    CASES,
    Case,
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


ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_SERVER = Path(
    r"D:\BAXYRuntime\assets\llama-b9980-cuda12.4\llama-server.exe"
)
_DEFAULT_MODEL = Path(
    r"D:\BAXYRuntime\assets\models"
    r"\gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf"
)
_CANDIDATE_PROFILES = (
    "ngram-simple",
    "ngram-map-k",
    "ngram-map-k4v",
    "ngram-cache",
    "ngram-mod",
)
_MAP_FLAGS = {
    "ngram-simple": (
        "--spec-ngram-simple-size-n",
        "--spec-ngram-simple-size-m",
        "--spec-ngram-simple-min-hits",
    ),
    "ngram-map-k": (
        "--spec-ngram-map-k-size-n",
        "--spec-ngram-map-k-size-m",
        "--spec-ngram-map-k-min-hits",
    ),
    "ngram-map-k4v": (
        "--spec-ngram-map-k4v-size-n",
        "--spec-ngram-map-k4v-size-m",
        "--spec-ngram-map-k4v-min-hits",
    ),
}
_COMMON_DRAFT_FLAGS = (
    "--spec-draft-n-min",
    "--spec-draft-n-max",
)
_MOD_FLAGS = (
    "--spec-ngram-mod-n-match",
    "--spec-ngram-mod-n-min",
    "--spec-ngram-mod-n-max",
)
_LOOKUP_FLAGS = (
    "--lookup-cache-static",
    "--lookup-cache-dynamic",
)
_REQUEST_SCOPE_CONTRACT = {
    "per_request_speculative_control": False,
    "per_stage_p_only_supported": False,
    "effective_scope": "server-global across every slot and request",
    "evidence": [
        {
            "source": (
                "https://github.com/ggml-org/llama.cpp/blob/b9980/"
                "tools/server/server-schema.cpp#L194-L226"
            ),
            "finding": (
                "The speculative.type/n_max/n_min/p_min and n-gram request "
                "fields are inside #if 0; b9980 does not compile them into "
                "the REST request schema."
            ),
        },
        {
            "source": (
                "https://github.com/ggml-org/llama.cpp/blob/b9980/"
                "tools/server/server-schema.cpp#L501-L506"
            ),
            "finding": (
                "Every task only copies params_base.speculative from the "
                "server-global configuration."
            ),
        },
        {
            "source": (
                "https://github.com/ggml-org/llama.cpp/blob/b9980/"
                "tools/server/server-context.cpp#L1275-L1307"
            ),
            "finding": (
                "The server initializes one common_speculative instance from "
                "params_base and assigns the same pointer to every slot."
            ),
        },
    ],
    "consequence": (
        "A stock single b9980 server cannot benchmark or deploy n-gram only "
        "for P. Doing so would require a patched llama.cpp server or a "
        "separate routed server, both outside this isolated harness."
    ),
}


@dataclass(frozen=True)
class CandidateConfig:
    """Resolved, explicit b9980 candidate configuration."""

    profile: str
    size_n: int | None = None
    size_m: int | None = None
    min_hits: int | None = None
    draft_n_min: int | None = None
    draft_n_max: int | None = None
    mod_match: int | None = None
    mod_min: int | None = None
    mod_max: int | None = None
    lookup_cache_static: Path | None = None
    lookup_cache_dynamic: Path | None = None

    def command_flags(self) -> list[str]:
        if self.profile in _MAP_FLAGS:
            if (
                self.size_n is None
                or self.size_m is None
                or self.min_hits is None
                or self.draft_n_min is None
                or self.draft_n_max is None
            ):
                raise AssertionError("map profile has unresolved parameters")
            size_n_flag, size_m_flag, hits_flag = _MAP_FLAGS[self.profile]
            return [
                size_n_flag,
                str(self.size_n),
                size_m_flag,
                str(self.size_m),
                hits_flag,
                str(self.min_hits),
                "--spec-draft-n-min",
                str(self.draft_n_min),
                "--spec-draft-n-max",
                str(self.draft_n_max),
            ]
        if self.profile == "ngram-cache":
            if self.draft_n_min is None or self.draft_n_max is None:
                raise AssertionError("ngram-cache has unresolved draft limits")
            flags = [
                "--spec-draft-n-min",
                str(self.draft_n_min),
                "--spec-draft-n-max",
                str(self.draft_n_max),
            ]
            if self.lookup_cache_static is not None:
                flags.extend(
                    [
                        "--lookup-cache-static",
                        str(self.lookup_cache_static.resolve()),
                    ]
                )
            if self.lookup_cache_dynamic is not None:
                flags.extend(
                    [
                        "--lookup-cache-dynamic",
                        str(self.lookup_cache_dynamic.resolve()),
                    ]
                )
            return flags
        if self.profile == "ngram-mod":
            if (
                self.mod_match is None
                or self.mod_min is None
                or self.mod_max is None
            ):
                raise AssertionError("ngram-mod has unresolved parameters")
            return [
                "--spec-ngram-mod-n-match",
                str(self.mod_match),
                "--spec-ngram-mod-n-min",
                str(self.mod_min),
                "--spec-ngram-mod-n-max",
                str(self.mod_max),
            ]
        raise AssertionError(f"unsupported candidate profile: {self.profile}")

    def as_json(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "size_n": self.size_n,
            "size_m": self.size_m,
            "min_hits": self.min_hits,
            "draft_n_min": self.draft_n_min,
            "draft_n_max": self.draft_n_max,
            "mod_match": self.mod_match,
            "mod_min": self.mod_min,
            "mod_max": self.mod_max,
            "lookup_cache_static": (
                str(self.lookup_cache_static.resolve())
                if self.lookup_cache_static is not None
                else None
            ),
            "lookup_cache_dynamic": (
                str(self.lookup_cache_dynamic.resolve())
                if self.lookup_cache_dynamic is not None
                else None
            ),
            "command_flags": self.command_flags(),
        }


def _positive(parser: argparse.ArgumentParser, name: str, value: int) -> None:
    if value <= 0:
        parser.error(f"{name} must be positive")


def _non_negative(
    parser: argparse.ArgumentParser,
    name: str,
    value: int,
) -> None:
    if value < 0:
        parser.error(f"{name} must be non-negative")


def _resolve_config(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
) -> CandidateConfig:
    profile = str(args.profile)
    map_options_supplied = any(
        value is not None
        for value in (args.size_n, args.size_m, args.min_hits)
    )
    draft_options_supplied = any(
        value is not None for value in (args.draft_n_min, args.draft_n_max)
    )
    mod_options_supplied = any(
        value is not None
        for value in (args.mod_match, args.mod_min, args.mod_max)
    )
    lookup_options_supplied = (
        args.lookup_cache_static is not None
        or args.lookup_cache_dynamic is not None
    )

    if profile in _MAP_FLAGS:
        if mod_options_supplied or lookup_options_supplied:
            parser.error(
                "map profiles reject --mod-* and --lookup-cache-* options"
            )
        size_n = 12 if args.size_n is None else args.size_n
        size_m = 48 if args.size_m is None else args.size_m
        min_hits = 1 if args.min_hits is None else args.min_hits
        draft_n_min = 0 if args.draft_n_min is None else args.draft_n_min
        draft_n_max = 3 if args.draft_n_max is None else args.draft_n_max
        for name, value in (
            ("--size-n", size_n),
            ("--size-m", size_m),
            ("--min-hits", min_hits),
            ("--draft-n-max", draft_n_max),
        ):
            _positive(parser, name, value)
        _non_negative(parser, "--draft-n-min", draft_n_min)
        if draft_n_min > draft_n_max:
            parser.error("--draft-n-min cannot exceed --draft-n-max")
        return CandidateConfig(
            profile=profile,
            size_n=size_n,
            size_m=size_m,
            min_hits=min_hits,
            draft_n_min=draft_n_min,
            draft_n_max=draft_n_max,
        )

    if profile == "ngram-cache":
        if map_options_supplied or mod_options_supplied:
            parser.error(
                "ngram-cache rejects --size-*, --min-hits and --mod-* options"
            )
        draft_n_min = 0 if args.draft_n_min is None else args.draft_n_min
        draft_n_max = 3 if args.draft_n_max is None else args.draft_n_max
        _non_negative(parser, "--draft-n-min", draft_n_min)
        _positive(parser, "--draft-n-max", draft_n_max)
        if draft_n_min > draft_n_max:
            parser.error("--draft-n-min cannot exceed --draft-n-max")
        static_path = args.lookup_cache_static
        dynamic_path = args.lookup_cache_dynamic
        if static_path is not None and not static_path.is_file():
            parser.error("--lookup-cache-static must name an existing file")
        if dynamic_path is not None:
            dynamic_parent = dynamic_path.resolve().parent
            if not dynamic_parent.is_dir():
                parser.error(
                    "--lookup-cache-dynamic parent directory does not exist"
                )
        if (
            static_path is not None
            and dynamic_path is not None
            and static_path.resolve() == dynamic_path.resolve()
        ):
            parser.error("static and dynamic lookup caches must be different")
        return CandidateConfig(
            profile=profile,
            draft_n_min=draft_n_min,
            draft_n_max=draft_n_max,
            lookup_cache_static=static_path,
            lookup_cache_dynamic=dynamic_path,
        )

    if profile == "ngram-mod":
        if map_options_supplied or draft_options_supplied or lookup_options_supplied:
            parser.error(
                "ngram-mod uses --mod-match/--mod-min/--mod-max and rejects "
                "map, common draft-limit and lookup-cache options"
            )
        mod_match = 24 if args.mod_match is None else args.mod_match
        mod_min = 48 if args.mod_min is None else args.mod_min
        mod_max = 64 if args.mod_max is None else args.mod_max
        for name, value in (
            ("--mod-match", mod_match),
            ("--mod-min", mod_min),
            ("--mod-max", mod_max),
        ):
            _positive(parser, name, value)
        if mod_min > mod_max:
            parser.error("--mod-min cannot exceed --mod-max")
        return CandidateConfig(
            profile=profile,
            mod_match=mod_match,
            mod_min=mod_min,
            mod_max=mod_max,
        )

    parser.error(f"unsupported profile: {profile}")
    raise AssertionError("argparse.error unexpectedly returned")


def _required_help_flags(config: CandidateConfig) -> tuple[str, ...]:
    flags = {"--spec-type"}
    flags.update(
        item for item in config.command_flags() if item.startswith("--")
    )
    return tuple(sorted(flags))


def _validate_server_help(
    server: Path,
    config: CandidateConfig,
) -> dict[str, Any]:
    completed = subprocess.run(
        [str(server.resolve()), "--help"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30.0,
    )
    help_text = completed.stdout + completed.stderr
    required_flags = _required_help_flags(config)
    missing_flags = [
        flag for flag in required_flags if flag not in help_text
    ]
    profile_advertised = config.profile in help_text
    passed = (
        completed.returncode == 0
        and not missing_flags
        and profile_advertised
    )
    return {
        "passed": passed,
        "returncode": completed.returncode,
        "profile": config.profile,
        "profile_advertised": profile_advertised,
        "required_flags": list(required_flags),
        "missing_flags": missing_flags,
    }


class NgramVariantRuntime(KvQuantRuntime):
    def __init__(
        self,
        arm: str,
        run_id: str,
        config: CandidateConfig,
    ) -> None:
        if arm not in {"baseline", "candidate"}:
            raise ValueError(f"unknown A/B arm: {arm}")
        self._ngram_arm = arm
        self._ngram_config = config
        super().__init__("q8", run_id)

    def _server_command(self) -> list[str]:
        command = super()._server_command()
        forbidden = (
            "--spec-type",
            *_COMMON_DRAFT_FLAGS,
            *_MOD_FLAGS,
            *_LOOKUP_FLAGS,
            *(
                flag
                for profile_flags in _MAP_FLAGS.values()
                for flag in profile_flags
            ),
        )
        collisions = [flag for flag in forbidden if flag in command]
        if collisions:
            raise AssertionError(
                "production command unexpectedly sets speculative flags: "
                + ", ".join(sorted(collisions))
            )
        spec_type = (
            "none"
            if self._ngram_arm == "baseline"
            else self._ngram_config.profile
        )
        command.extend(["--spec-type", spec_type])
        if self._ngram_arm == "candidate":
            command.extend(self._ngram_config.command_flags())
        return command

    def _record_profile(self) -> str:
        return self._ngram_arm

    def _extra_response_record(
        self,
        response: dict[str, Any],
        timings: dict[str, Any],
    ) -> dict[str, Any]:
        del response
        drafted = timings.get("draft_n")
        accepted = timings.get("draft_n_accepted")
        return {
            "spec_type": (
                "none"
                if self._ngram_arm == "baseline"
                else self._ngram_config.profile
            ),
            "draft_n": drafted,
            "draft_n_accepted": accepted,
            "draft_acceptance": (
                float(accepted) / float(drafted)
                if isinstance(drafted, (int, float))
                and not isinstance(drafted, bool)
                and drafted > 0
                and isinstance(accepted, (int, float))
                and not isinstance(accepted, bool)
                else None
            ),
        }


def _smoke_cases() -> tuple[Case, Case]:
    action = next(case for case in CASES if case.expected_mode == "action")
    conversation = next(
        case for case in CASES if case.expected_mode == "conversation"
    )
    return action, conversation


def _run_arm(
    arm: str,
    run_id: str,
    config: CandidateConfig,
    cases_to_run: Sequence[Case],
) -> dict[str, Any]:
    runtime = NgramVariantRuntime(arm, run_id, config)
    cases: list[dict[str, Any]] = []
    server_pid: int | None = None
    server_command: list[str] = []
    started = time.perf_counter()
    try:
        runtime.start_warmup()
        if not runtime.wait_warmup(420.0):
            raise TimeoutError("llama-server did not become ready")
        process = runtime._process
        if process is None or process.poll() is not None:
            raise RuntimeError("fresh llama-server child is not alive")
        server_pid = process.pid
        server_command = runtime._server_command()
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
        "profile": arm,
        "spec_type": (
            "none" if arm == "baseline" else config.profile
        ),
        "server_pid": server_pid,
        "server_command": server_command,
        "server_ready_seconds": ready_seconds,
        "cases": cases,
        "case_projection": [_case_projection(case) for case in cases],
        "decision_projection": [
            _case_decision_projection(case) for case in cases
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
            ("order1-candidate", "candidate"),
        ]
    if order == "candidate-baseline":
        return [
            ("order2-candidate", "candidate"),
            ("order2-baseline", "baseline"),
        ]
    if order == "both":
        return [
            ("order1-baseline", "baseline"),
            ("order1-candidate", "candidate"),
            ("order2-candidate", "candidate"),
            ("order2-baseline", "baseline"),
        ]
    raise ValueError(f"unknown order: {order}")


def _build_comparisons(
    order: str,
    arms_by_id: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    comparisons: list[dict[str, Any]] = []
    exact_case_outputs: list[dict[str, Any]] = []
    if order in {"both", "baseline-candidate"}:
        baseline = arms_by_id["order1-baseline"]
        candidate = arms_by_id["order1-candidate"]
        comparisons.append(
            _compare_pair(
                pair_id="baseline-then-candidate",
                baseline=baseline,
                candidate=candidate,
            )
        )
        exact_case_outputs.append(
            {
                "pair_id": "baseline-then-candidate",
                "equal": (
                    baseline["case_projection"]
                    == candidate["case_projection"]
                ),
            }
        )
    if order in {"both", "candidate-baseline"}:
        candidate = arms_by_id["order2-candidate"]
        baseline = arms_by_id["order2-baseline"]
        comparisons.append(
            _compare_pair(
                pair_id="candidate-then-baseline",
                baseline=baseline,
                candidate=candidate,
            )
        )
        exact_case_outputs.append(
            {
                "pair_id": "candidate-then-baseline",
                "equal": (
                    baseline["case_projection"]
                    == candidate["case_projection"]
                ),
            }
        )
    return comparisons, exact_case_outputs


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--profile",
        required=True,
        choices=_CANDIDATE_PROFILES,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "artifacts"
        / "fixes"
        / "llama_ngram_variants_ab.json",
    )
    parser.add_argument(
        "--arm-order",
        choices=("both", "baseline-candidate", "candidate-baseline"),
        default="baseline-candidate",
    )
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--size-n", type=int)
    parser.add_argument("--size-m", type=int)
    parser.add_argument("--min-hits", type=int)
    parser.add_argument("--draft-n-min", type=int)
    parser.add_argument("--draft-n-max", type=int)
    parser.add_argument("--mod-match", type=int)
    parser.add_argument("--mod-min", type=int)
    parser.add_argument("--mod-max", type=int)
    parser.add_argument("--lookup-cache-static", type=Path)
    parser.add_argument("--lookup-cache-dynamic", type=Path)
    parser.add_argument("--server", type=Path, default=_DEFAULT_SERVER)
    parser.add_argument("--model", type=Path, default=_DEFAULT_MODEL)
    return parser


def main() -> int:
    parser = _parser()
    args = parser.parse_args()
    config = _resolve_config(parser, args)
    if not args.server.is_file() or not args.model.is_file():
        raise FileNotFoundError("official b9980 runtime assets are missing")
    if args.smoke and args.arm_order == "both":
        parser.error(
            "--smoke is one small A/B pair; choose baseline-candidate or "
            "candidate-baseline"
        )

    help_contract = _validate_server_help(args.server, config)
    if not help_contract["passed"]:
        print(json.dumps(help_contract, ensure_ascii=False, indent=2))
        return 3

    os.environ.pop("BAXY_MIND_LLM_ENDPOINT", None)
    os.environ.pop("GGML_CUDA_GRAPH_OPT", None)
    os.environ.pop("CUDA_MODULE_LOADING", None)
    os.environ["BAXY_MIND_LLAMA_SERVER"] = str(args.server.resolve())
    os.environ["BAXY_MIND_LLM_GGUF"] = str(args.model.resolve())
    os.environ["BAXY_MIND_NGL"] = "99"
    os.environ["BAXY_MIND_LLM_REQUEST_TIMEOUT"] = "19"

    validation_commands: dict[str, list[str]] = {}
    for arm in ("baseline", "candidate"):
        runtime = NgramVariantRuntime(
            arm,
            f"validate-{arm}",
            config,
        )
        try:
            validation_commands[arm] = runtime._server_command()
        finally:
            runtime.close()
    validation = {
        "help_contract": help_contract,
        "request_scope_contract": copy.deepcopy(_REQUEST_SCOPE_CONTRACT),
        "candidate": config.as_json(),
        "commands": validation_commands,
        "only_server_variable": (
            "--spec-type none versus the selected n-gram spec type and its "
            "explicit b9980 tuning flags"
        ),
    }
    if args.validate_only:
        print(json.dumps(validation, ensure_ascii=False, indent=2))
        return 0

    cases_to_run: Sequence[Case] = (
        _smoke_cases() if args.smoke else CASES
    )
    arms = [
        _run_arm(arm, run_id, config, cases_to_run)
        for run_id, arm in _arm_plan(args.arm_order)
    ]
    arms_by_id = {arm["run_id"]: arm for arm in arms}
    comparisons, exact_case_outputs = _build_comparisons(
        args.arm_order,
        arms_by_id,
    )

    required_stages = (
        ("P", "G", "L") if args.smoke else TARGET_STAGES
    )
    stage_coverage = all(
        arm["stage_summary"][stage]["calls"] > 0
        for arm in arms
        for stage in required_stages
    )
    raw_tokens_captured = all(
        isinstance(record.get("tokens"), list)
        for arm in arms
        for record in arm["posts"]
        if record["stage"] in required_stages
    )
    decisions_captured = all(
        isinstance(case.get("decision"), dict)
        for arm in arms
        for case in arm["cases"]
    )
    replies_captured = all(
        isinstance(case.get("reply"), str) and bool(case["reply"].strip())
        for arm in arms
        for case in arm["cases"]
        if case["expected_mode"] == "conversation"
    )
    mode_contracts = all(
        case["decision"].get("mode") == case["expected_mode"]
        for arm in arms
        for case in arm["cases"]
    )
    exact_equivalence = (
        bool(comparisons)
        and all(item["equal"] for item in exact_case_outputs)
        and all(
            comparison["structured_post_count_equal"]
            and comparison["payloads_equal"]
            and comparison["contents_equal"]
            and comparison["raw_contents_equal"]
            and comparison["raw_tokens_available"]
            and comparison["tokens_equal"]
            and comparison["final_decisions_equal"]
            for comparison in comparisons
        )
    )
    candidate_arms = [
        arm for arm in arms if arm["profile"] == "candidate"
    ]
    candidate_drafted = bool(candidate_arms) and all(
        arm["draft_summary"]["draft_n_total"] > 0.0
        for arm in candidate_arms
    )
    latency_improved = bool(comparisons) and all(
        comparison[
            "candidate_minus_baseline_structured_total_seconds"
        ]
        < 0.0
        and comparison["candidate_minus_baseline_case_p50_seconds"] < 0.0
        and comparison["candidate_minus_baseline_case_total_seconds"] < 0.0
        for comparison in comparisons
    )
    evidence_complete = (
        stage_coverage
        and raw_tokens_captured
        and decisions_captured
        and replies_captured
    )
    run_gate_passed = (
        evidence_complete
        and mode_contracts
        and exact_equivalence
        and candidate_drafted
        and latency_improved
    )
    promotion_gate_passed = (
        not args.smoke
        and args.arm_order == "both"
        and run_gate_passed
    )

    result = {
        "schema": "baxy.llama-ngram-variants-ab.v1",
        "candidate_status": "research_only",
        "smoke": args.smoke,
        "arm_order": args.arm_order,
        "candidate": config.as_json(),
        "runtime": {
            "server": str(args.server.resolve()),
            "server_sha256": _file_sha256(args.server),
            "model": str(args.model.resolve()),
            "model_sha256": _file_sha256(args.model),
            "cache_type_k": "q8_0",
            "cache_type_v": "q8_0",
            "flash_attention": "on",
            "parallel": 3,
            "context_per_slot": 4_096,
            "ngl": 99,
        },
        "control": {
            "fresh_server_per_arm": True,
            "same_payloads": True,
            "speculation_scope": copy.deepcopy(_REQUEST_SCOPE_CONTRACT),
            "case_names": [case.name for case in cases_to_run],
            "case_count_per_arm": len(cases_to_run),
            "core_started": False,
            "external_effects_executed": False,
        },
        "measurement": {
            "raw_structured_tokens": (
                "llama.cpp b9980 __verbose.tokens via identical "
                "verbose=true and return_tokens=true"
            ),
            "final_decision_extraction_language_reply": True,
            "structured_and_end_to_end_case_latency": True,
            "draft_metrics": [
                "timings.draft_n",
                "timings.draft_n_accepted",
            ],
        },
        "validation": validation,
        "required_stages": list(required_stages),
        "stage_coverage": stage_coverage,
        "raw_tokens_captured": raw_tokens_captured,
        "decisions_captured": decisions_captured,
        "replies_captured": replies_captured,
        "evidence_complete": evidence_complete,
        "mode_contracts": mode_contracts,
        "exact_case_outputs": exact_case_outputs,
        "exact_equivalence": exact_equivalence,
        "candidate_drafted": candidate_drafted,
        "latency_improved": latency_improved,
        "comparisons": comparisons,
        "arms": arms,
        "run_gate_passed": run_gate_passed,
        "promotion_gate_passed": promotion_gate_passed,
        "promotion_rule": (
            "Fail closed unless both opposite orders cover P/G/L/V/C/E, "
            "capture every required raw token, decision and reply, preserve "
            "all raw tokens/contents/final outputs exactly, generate actual "
            "drafts, and improve structured total, case p50 and case total in "
            "both orders. A smoke can validate mechanics but can never "
            "authorize promotion."
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
                    "smoke",
                    "arm_order",
                    "required_stages",
                    "evidence_complete",
                    "mode_contracts",
                    "exact_equivalence",
                    "candidate_drafted",
                    "latency_improved",
                    "run_gate_passed",
                    "promotion_gate_passed",
                    "comparisons",
                )
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if run_gate_passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
