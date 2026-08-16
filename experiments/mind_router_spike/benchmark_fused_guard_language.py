"""Physical, effect-free A/B for fusing candidate-free G and L.

The ``separate`` control runs BAXY's previous P+G+L schedule.  The ``fused``
candidate runs P+GL, where one closed structured response carries the existing
semantic guard fields plus an independent language field.  GL receives only
the current user text: no catalog, candidates, history or evidence.

The candidate stores the language in the existing request-local L cache before
returning G.  The product scheduler can therefore start speculative chat at G's
barrier without another HTTP inference.  Core is never started and no external
effect is executed.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

from benchmark_guard_gated_language import (  # type: ignore[import-not-found]
    _latency_deltas,
    _latency_summary,
    _selected_cases,
)
from benchmark_llama_slot_pinning import (  # type: ignore[import-not-found]
    _case_projection,
    _run_case,
    _stage_summary,
)
from benchmark_guard_gated_language import ScheduleRuntime  # type: ignore[import-not-found]
from baxy_mind import llm as llm_module  # type: ignore[import-not-found]
from baxy_mind.llm import derive_semantic_effect_state  # type: ignore[import-not-found]


_PROFILES = ("separate", "fused")
_LANGUAGES = frozenset({"es", "en", "mixed"})
_FUSED_PROMPT = (
    llm_module.SEMANTIC_EFFECT_GUARD_PROMPT
    + " En un tercer campo completamente independiente, aplica esta regla: "
    + llm_module.RESPONSE_LANGUAGE_PROMPT
    + " La clasificación language nunca puede cambiar, justificar ni aportar "
    "evidencia a request_type o effect_count. Ejemplos exclusivos de language: "
    + "; ".join(
        f"{json.dumps(text, ensure_ascii=False)} -> {language}"
        for text, language in llm_module._RESPONSE_LANGUAGE_EXAMPLES
    )
    + "."
)
_FUSED_GRAMMAR = "\n".join(
    (
        (
            "root ::= "
            + llm_module._gbnf_terminal('{"request_type":')
            + " request-type "
            + llm_module._gbnf_terminal(',"effect_count":')
            + " effect-count "
            + llm_module._gbnf_terminal(',"language":')
            + " language "
            + llm_module._gbnf_terminal("}")
        ),
        (
            "request-type ::= "
            + " | ".join(
                llm_module._gbnf_terminal(
                    json.dumps(value, ensure_ascii=False)
                )
                for value in (
                    "stable_conversation",
                    "external_read",
                    "environment_change",
                    "incomplete_effect",
                )
            )
        ),
        (
            "effect-count ::= "
            + " | ".join(
                llm_module._gbnf_terminal(
                    json.dumps(value, ensure_ascii=False)
                )
                for value in ("zero", "one", "multiple")
            )
        ),
        (
            "language ::= "
            + " | ".join(
                llm_module._gbnf_terminal(
                    json.dumps(value, ensure_ascii=False)
                )
                for value in ("es", "en", "mixed")
            )
        ),
    )
)


class FusedRuntime(ScheduleRuntime):
    def __init__(self, profile: str) -> None:
        if profile not in _PROFILES:
            raise ValueError(f"unknown fused profile: {profile}")
        self._fused_profile = profile
        self.fused_guard_projection: list[dict[str, Any]] = []
        self.fused_fallbacks = 0
        super().__init__("eager" if profile == "separate" else "gated")

    def _verify_semantic_effect_shape(
        self,
        text: str,
    ) -> tuple[str, str | None]:
        if self._fused_profile == "separate":
            return super()._verify_semantic_effect_shape(text)

        semantic_cache = getattr(self, "_semantic_effect_cache", None)
        if semantic_cache is not None and text in semantic_cache:
            return semantic_cache[text]
        payload = {
            "messages": [
                {"role": "system", "content": _FUSED_PROMPT},
                {"role": "user", "content": f"Mensaje actual:\n{text}"},
            ],
            "grammar": _FUSED_GRAMMAR,
            "temperature": 0.0,
            "max_tokens": 64,
            "seed": 0,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        try:
            raw = self._post_schema_object(
                payload,
                "el veto semántico e idioma candidate-free",
            )
            guard_raw = {
                "request_type": raw.get("request_type"),
                "effect_count": raw.get("effect_count"),
            }
            state = derive_semantic_effect_state(guard_raw)
            language = raw.get("language")
            if state == "invalid" or language not in _LANGUAGES:
                raise ValueError("GL devolvió un contrato inválido")
        except ValueError:
            self.fused_fallbacks += 1
            return super()._verify_semantic_effect_shape(text)

        effect_count = (
            "zero" if state == "no_effect" else guard_raw["effect_count"]
        )
        assert isinstance(effect_count, str)
        result = (state, effect_count)
        if semantic_cache is not None:
            semantic_cache[text] = result
        language_cache = getattr(self, "_response_language_cache", None)
        if language_cache is not None:
            language_cache[text] = str(language)
        self.fused_guard_projection.append(
            {
                "case": self._benchmark_case,
                "request_type": guard_raw["request_type"],
                "effect_count": guard_raw["effect_count"],
                "state": state,
                "derived_effect_count": effect_count,
                "language": language,
            }
        )
        return result


def _run_arm(profile: str, cases_to_run: tuple[Any, ...]) -> dict[str, Any]:
    runtime = FusedRuntime(profile)
    cases: list[dict[str, Any]] = []
    server_pid: int | None = None
    started = time.perf_counter()
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
    return {
        "profile": profile,
        "server_pid": server_pid,
        "server_ready_seconds": ready_seconds,
        "cases": cases,
        "posts": runtime._benchmark_records,
        "timeline": runtime.timeline,
        "stage_summary": _stage_summary(runtime._benchmark_records),
        "latency": _latency_summary(cases),
        "fused_guard_projection": runtime.fused_guard_projection,
        "fused_fallbacks": runtime.fused_fallbacks,
    }


def _parse_closed_content(record: dict[str, Any]) -> dict[str, Any] | None:
    try:
        value = json.loads(str(record.get("content") or ""))
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _separate_projection(arm: dict[str, Any]) -> list[dict[str, Any]]:
    by_case: dict[str, dict[str, Any]] = {}
    for record in arm["posts"]:
        stage = record["stage"]
        if stage not in {"G", "L"}:
            continue
        raw = _parse_closed_content(record)
        if raw is None:
            continue
        item = by_case.setdefault(str(record["case"]), {})
        if stage == "G":
            guard_raw = {
                "request_type": raw.get("request_type"),
                "effect_count": raw.get("effect_count"),
            }
            state = derive_semantic_effect_state(guard_raw)
            item.update(
                {
                    "request_type": guard_raw["request_type"],
                    "effect_count": guard_raw["effect_count"],
                    "state": state,
                    "derived_effect_count": (
                        "zero"
                        if state == "no_effect"
                        else guard_raw["effect_count"]
                    ),
                }
            )
        else:
            item["language"] = raw.get("language")
    return [
        {"case": case["case"], **by_case.get(str(case["case"]), {})}
        for case in arm["cases"]
    ]


def _strict_case_projection(case: dict[str, Any]) -> dict[str, Any]:
    projection = _case_projection(case)
    projection.pop("reply", None)
    return projection


def _common_post_projection(
    arm: dict[str, Any],
) -> dict[str, list[list[Any]]]:
    grouped: dict[str, list[list[Any]]] = {}
    for record in arm["posts"]:
        stage = str(record["stage"])
        if stage not in {"P", "V", "C", "E", "chat"}:
            continue
        key = f"{record['case']}::{stage}"
        grouped.setdefault(key, []).append(
            [
                record.get("payload_sha256"),
                record.get("content"),
            ]
        )
    return grouped


def _post_counts(arm: dict[str, Any]) -> dict[str, int]:
    result: dict[str, int] = {}
    for record in arm["posts"]:
        stage = str(record["stage"])
        result[stage] = result.get(stage, 0) + 1
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--arm-order",
        choices=("separate-fused", "fused-separate"),
        default="separate-fused",
    )
    parser.add_argument("--smoke", action="store_true")
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
        raise FileNotFoundError("registered runtime assets are missing")

    os.environ.pop("BAXY_MIND_LLM_ENDPOINT", None)
    os.environ["BAXY_MIND_LLAMA_SERVER"] = str(args.server)
    os.environ["BAXY_MIND_LLM_GGUF"] = str(args.model)
    os.environ["BAXY_MIND_NGL"] = "99"
    os.environ["BAXY_MIND_LLM_REQUEST_TIMEOUT"] = "19"

    cases_to_run = _selected_cases(args.smoke)
    arm_order = args.arm_order.split("-")
    arms = [_run_arm(profile, cases_to_run) for profile in arm_order]
    by_profile = {arm["profile"]: arm for arm in arms}
    separate = by_profile["separate"]
    fused = by_profile["fused"]
    separate_guard = _separate_projection(separate)
    fused_guard = fused["fused_guard_projection"]
    guard_language_projection_exact = separate_guard == fused_guard
    strict_final_projection_exact = [
        _strict_case_projection(case) for case in separate["cases"]
    ] == [_strict_case_projection(case) for case in fused["cases"]]
    reply_exact = [
        case.get("reply") for case in separate["cases"]
    ] == [case.get("reply") for case in fused["cases"]]
    common_post_exact = (
        _common_post_projection(separate)
        == _common_post_projection(fused)
    )
    mode_contracts = all(
        case["decision"].get("mode") == case["expected_mode"]
        for arm in arms
        for case in arm["cases"]
    )
    post_counts = {
        profile: _post_counts(arm) for profile, arm in by_profile.items()
    }
    fused_has_no_separate_language = post_counts["fused"].get("L", 0) == 0
    quality_gate = (
        guard_language_projection_exact
        and strict_final_projection_exact
        and mode_contracts
        and fused_has_no_separate_language
        and fused["fused_fallbacks"] == 0
    )
    divergent_final_cases = [
        {
            "case": control["case"],
            "separate": control,
            "fused": candidate,
        }
        for control, candidate in zip(
            [_case_projection(case) for case in separate["cases"]],
            [_case_projection(case) for case in fused["cases"]],
            strict=True,
        )
        if control != candidate
    ]
    result = {
        "schema": "baxy.fused-guard-language-ab.v1",
        "arm_order": arm_order,
        "smoke": args.smoke,
        "safety": {
            "core_started": False,
            "external_effects_executed": False,
            "fused_input": "current user text only",
        },
        "control": {
            "only_candidate_change": "G and L fused into closed GL",
            "same_model_server_primary_and_downstream_contracts": True,
            "maximum_executor_workers": 3,
            "fresh_server_per_arm": True,
        },
        "quality": {
            "guard_language_projection_exact": (
                guard_language_projection_exact
            ),
            "strict_final_projection_without_free_reply_exact": (
                strict_final_projection_exact
            ),
            "free_reply_exact": reply_exact,
            "common_post_wire_and_content_exact": common_post_exact,
            "mode_contracts": mode_contracts,
            "fused_has_no_separate_language": (
                fused_has_no_separate_language
            ),
            "fused_fallbacks": fused["fused_fallbacks"],
            "passed_classifier_gate": quality_gate,
            "divergent_final_cases": divergent_final_cases,
        },
        "separate_guard_language_projection": separate_guard,
        "fused_guard_language_projection": fused_guard,
        "post_counts": post_counts,
        "latency_delta_fused_minus_separate": _latency_deltas(
            separate,
            fused,
        ),
        "arms": arms,
        "candidate_status": "research_only",
        "promotion_rule": (
            "Require classifier/final exactness and zero fallbacks in both "
            "physical orders, repeatable all/action/conversation E2E gains, "
            "then exact G/L agreement on the canonical classifier corpus. "
            "Free replies need an independent semantic-quality gate because "
            "fresh-server greedy GPU runs are not byte-stable."
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
                "schema": result["schema"],
                "arm_order": arm_order,
                "smoke": args.smoke,
                "quality": result["quality"],
                "post_counts": post_counts,
                "latency_delta_fused_minus_separate": result[
                    "latency_delta_fused_minus_separate"
                ],
            },
            ensure_ascii=False,
        )
    )
    return 0 if quality_gate else 2


if __name__ == "__main__":
    raise SystemExit(main())
