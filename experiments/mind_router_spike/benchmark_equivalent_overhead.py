"""Paired, token-identical overhead measurement: BAXY chat vs direct POST.

Both arms send byte-identical wire payloads to the same warm llama-server
process: the "baxy" arm runs the full ``LlmRuntime.chat`` path (payload
construction, transport pool, validation, bookkeeping) while the "direct"
arm re-sends the exact captured payload through the same transport function
without any of that work.  Same messages, sampler, seed, grammar, budgets and
slot state; ABBA physical alternation per round.  The probe never dispatches
Core operations and never streams; TTFT is derived from server timings
(queue + prompt eval + one decode step) because the product protocol does not
transmit tokens incrementally.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import random
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scripts.baxy_runtime_config import (  # noqa: E402
    DEFAULT_RUNTIME_MANIFEST,
    resolve_runtime,
)
from scripts.measure_mind_budget import write_json_atomic  # noqa: E402

DEFAULT_OUTPUT = REPO / "artifacts" / "fixes" / "equivalent_overhead_ab_20260730.json"
CASES = (
    ("es_knowledge", "¿Qué es la latencia en un sistema informático?", "es"),
    ("en_knowledge", "Why does the sky look blue?", "en"),
    ("es_social", "Cuéntame un chiste corto.", "es"),
    ("en_opinion", "What do you think about pineapple on pizza?", "en"),
)
ROUNDS = 8


def _gpu_state() -> dict[str, Any] | None:
    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=temperature.gpu,clocks.sm,pstate,"
                "clocks_event_reasons.active,memory.used",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    line = (completed.stdout or "").strip().splitlines()
    if not line:
        return None
    parts = [item.strip() for item in line[0].split(",")]
    if len(parts) != 5:
        return None
    return {
        "temperature_c": parts[0],
        "sm_clock_mhz": parts[1],
        "pstate": parts[2],
        "clocks_event_reasons": parts[3],
        "memory_used_mib": parts[4],
    }


def _summary(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    rank95 = min(len(ordered) - 1, math.ceil(0.95 * len(ordered)) - 1)
    return {
        "count": len(ordered),
        "p50": statistics.median(ordered),
        "p95_nearest_rank": ordered[rank95],
        "mean": statistics.fmean(ordered),
        "stdev": statistics.pstdev(ordered) if len(ordered) > 1 else 0.0,
        "minimum": ordered[0],
        "maximum": ordered[-1],
    }


def _bootstrap_median_ci(
    deltas: list[float],
    *,
    resamples: int = 2000,
    seed: int = 20260730,
) -> dict[str, float]:
    rng = random.Random(seed)
    medians = []
    for _ in range(resamples):
        sample = [deltas[rng.randrange(len(deltas))] for _ in deltas]
        medians.append(statistics.median(sample))
    medians.sort()
    return {
        "ci95_low": medians[int(0.025 * resamples)],
        "ci95_high": medians[int(0.975 * resamples)],
    }


def _sign_test_p(deltas: list[float]) -> float:
    """Two-sided sign test for median(delta) == 0."""

    nonzero = [d for d in deltas if d != 0.0]
    n = len(nonzero)
    if n == 0:
        return 1.0
    k = sum(1 for d in nonzero if d > 0.0)
    tail = min(k, n - k)
    total = 0.0
    for i in range(0, tail + 1):
        total += math.comb(n, i)
    p = min(1.0, 2.0 * total / (2.0**n))
    return p


def _timings(response: dict[str, Any]) -> dict[str, Any]:
    raw = response.get("timings")
    return raw if isinstance(raw, dict) else {}


def _observation(
    *,
    case_id: str,
    arm: str,
    round_index: int,
    order: str,
    elapsed: float,
    response: dict[str, Any],
) -> dict[str, Any]:
    timings = _timings(response)
    content = response["choices"][0]["message"].get("content") or ""
    predicted_n = timings.get("predicted_n")
    predicted_ms = timings.get("predicted_ms")
    ttft_proxy = None
    if isinstance(predicted_n, (int, float)) and predicted_n and isinstance(
        predicted_ms, (int, float)
    ):
        per_token = float(predicted_ms) / float(predicted_n) / 1000.0
        ttft_proxy = elapsed - float(predicted_ms) / 1000.0 + per_token
    server_ms = None
    if isinstance(predicted_ms, (int, float)) and isinstance(
        timings.get("prompt_ms"), (int, float)
    ):
        server_ms = float(predicted_ms) + float(timings["prompt_ms"])
    return {
        "case_id": case_id,
        "arm": arm,
        "round": round_index,
        "order": order,
        "elapsed_seconds": elapsed,
        "ttft_proxy_seconds": ttft_proxy,
        "prompt_ms": timings.get("prompt_ms"),
        "predicted_ms": predicted_ms,
        "predicted_n": predicted_n,
        "prompt_n": timings.get("prompt_n"),
        "cache_n": timings.get("cache_n"),
        "python_and_http_overhead_seconds": (
            elapsed - server_ms / 1000.0 if server_ms is not None else None
        ),
        "output_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
    }


def run(output: Path) -> dict[str, Any]:
    runtime_config = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    os.environ["BAXY_MIND_LLM_GGUF"] = str(runtime_config.gguf)
    os.environ["BAXY_MIND_LLAMA_SERVER"] = str(runtime_config.llama_server)
    os.environ["BAXY_MIND_NGL"] = str(runtime_config.gpu_layers)
    os.environ["BAXY_MIND_CTX"] = "4096"
    os.environ["BAXY_MIND_LLM_REQUEST_TIMEOUT"] = "30"
    os.environ.pop("BAXY_MIND_LLM_ENDPOINT", None)

    from baxy_mind.llm import LlmRuntime

    llm = LlmRuntime()
    gpu_before = _gpu_state()
    captured: dict[str, Any] = {}
    latest: dict[str, Any] | None = None
    original_post: Callable[..., dict[str, Any]] = llm._post

    def recording_post(
        payload: dict[str, Any],
        timeout: float | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        nonlocal latest
        captured["payload"] = json.loads(json.dumps(payload))
        latest = original_post(payload, timeout, **kwargs)
        return latest

    llm._post = recording_post  # type: ignore[method-assign]
    observations: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    try:
        llm.begin_request(30.0)
        llm._ensure_started()
        llm.end_request()
        llm.begin_request(30.0)
        original_post(
            {
                "messages": [{"role": "user", "content": "Reply with only: ready"}],
                "temperature": 0.0,
                "seed": 0,
                "max_tokens": 128,
                "chat_template_kwargs": {"enable_thinking": False},
            }
        )
        llm.end_request()

        reference: dict[str, dict[str, Any]] = {}
        for case_id, text, language in CASES:
            llm.begin_request(30.0)
            llm.chat(
                text,
                history=[],
                tools=None,
                temperature=0.0,
                conversation_kind="knowledge",
                response_language=language,
            )
            llm.end_request()
            reference[case_id] = {
                "payload": captured["payload"],
                "payload_sha256": hashlib.sha256(
                    json.dumps(
                        captured["payload"], sort_keys=True, ensure_ascii=False
                    ).encode("utf-8")
                ).hexdigest(),
            }

        for round_index in range(ROUNDS):
            arms = ("baxy", "direct") if round_index % 2 == 0 else ("direct", "baxy")
            for case_id, text, language in CASES:
                for position, arm in enumerate(arms):
                    order = f"{arms[0]}-first"
                    llm.begin_request(30.0)
                    latest = None
                    started = time.perf_counter()
                    if arm == "direct":
                        response = original_post(
                            reference[case_id]["payload"]
                        )
                    else:
                        llm.chat(
                            text,
                            history=[],
                            tools=None,
                            temperature=0.0,
                            conversation_kind="knowledge",
                            response_language=language,
                        )
                        response = latest
                        if not isinstance(response, dict):
                            raise RuntimeError("respuesta BAXY no capturada")
                        wire_hash = hashlib.sha256(
                            json.dumps(
                                captured["payload"],
                                sort_keys=True,
                                ensure_ascii=False,
                            ).encode("utf-8")
                        ).hexdigest()
                        if wire_hash != reference[case_id]["payload_sha256"]:
                            mismatches.append(
                                {
                                    "case_id": case_id,
                                    "round": round_index,
                                    "expected": reference[case_id][
                                        "payload_sha256"
                                    ],
                                    "observed": wire_hash,
                                }
                            )
                    elapsed = time.perf_counter() - started
                    llm.end_request()
                    observations.append(
                        _observation(
                            case_id=case_id,
                            arm=arm,
                            round_index=round_index,
                            order=order,
                            elapsed=elapsed,
                            response=response,
                        )
                    )
                    del position
    finally:
        llm._post = original_post  # type: ignore[method-assign]
        llm.close()
    gpu_after = _gpu_state()

    by_arm: dict[str, list[float]] = {"baxy": [], "direct": []}
    ttft_by_arm: dict[str, list[float]] = {"baxy": [], "direct": []}
    overhead_http: dict[str, list[float]] = {"baxy": [], "direct": []}
    paired: list[float] = []
    paired_ttft: list[float] = []
    rounds_index: dict[tuple[str, int], dict[str, dict[str, Any]]] = {}
    for item in observations:
        by_arm[item["arm"]].append(item["elapsed_seconds"])
        if item["ttft_proxy_seconds"] is not None:
            ttft_by_arm[item["arm"]].append(item["ttft_proxy_seconds"])
        if item["python_and_http_overhead_seconds"] is not None:
            overhead_http[item["arm"]].append(
                item["python_and_http_overhead_seconds"]
            )
        rounds_index.setdefault((item["case_id"], item["round"]), {})[
            item["arm"]
        ] = item
    output_equal = 0
    output_total = 0
    for pair in rounds_index.values():
        if "baxy" in pair and "direct" in pair:
            paired.append(
                pair["baxy"]["elapsed_seconds"] - pair["direct"]["elapsed_seconds"]
            )
            if (
                pair["baxy"]["ttft_proxy_seconds"] is not None
                and pair["direct"]["ttft_proxy_seconds"] is not None
            ):
                paired_ttft.append(
                    pair["baxy"]["ttft_proxy_seconds"]
                    - pair["direct"]["ttft_proxy_seconds"]
                )
            output_total += 1
            if (
                pair["baxy"]["output_sha256"]
                == pair["direct"]["output_sha256"]
            ):
                output_equal += 1

    report = {
        "schema": "baxy.equivalent-overhead-ab.v1",
        "scope": "token-identical wire payloads; warm server; ABBA per round",
        "runtime": {
            "model": runtime_config.gguf.name,
            "server": runtime_config.llama_server.name,
            "gpu_layers": runtime_config.gpu_layers,
        },
        "gpu_state_before": gpu_before,
        "gpu_state_after": gpu_after,
        "cases": len(CASES),
        "rounds": ROUNDS,
        "payload_mismatches": mismatches,
        "identical_outputs_pairs": {
            "equal": output_equal,
            "total": output_total,
        },
        "arms": {
            "baxy_total_seconds": _summary(by_arm["baxy"]),
            "direct_total_seconds": _summary(by_arm["direct"]),
            "baxy_ttft_proxy_seconds": _summary(ttft_by_arm["baxy"]),
            "direct_ttft_proxy_seconds": _summary(ttft_by_arm["direct"]),
            "baxy_python_http_overhead_seconds": _summary(
                overhead_http["baxy"]
            ),
            "direct_python_http_overhead_seconds": _summary(
                overhead_http["direct"]
            ),
        },
        "paired_delta_baxy_minus_direct": {
            "total_seconds": _summary(paired) | _bootstrap_median_ci(paired),
            "ttft_proxy_seconds": _summary(paired_ttft)
            | _bootstrap_median_ci(paired_ttft),
            "sign_test_two_sided_p": _sign_test_p(paired),
            "relative_p50_overhead": (
                statistics.median(paired)
                / statistics.median(by_arm["direct"])
                if by_arm["direct"]
                else None
            ),
        },
        "observations": observations,
    }
    write_json_atomic(output, report)
    return report


def main() -> int:
    report = run(DEFAULT_OUTPUT)
    digest = {
        "output": str(DEFAULT_OUTPUT),
        "identical_outputs_pairs": report["identical_outputs_pairs"],
        "payload_mismatches": len(report["payload_mismatches"]),
        "paired_delta": {
            key: value
            for key, value in report["paired_delta_baxy_minus_direct"].items()
            if key != "observations"
        },
        "arms_p50": {
            "baxy": report["arms"]["baxy_total_seconds"]["p50"],
            "direct": report["arms"]["direct_total_seconds"]["p50"],
        },
    }
    print(json.dumps(digest, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
