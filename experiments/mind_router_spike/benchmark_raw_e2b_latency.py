"""Compare raw Gemma 4 E2B latency with BAXY's exact chat generation.

The probe starts the registered llama-server through ``LlmRuntime`` and never
dispatches Core operations.  It records timing metadata and output hashes, not
model prose.  Raw and BAXY calls use the same warm process, sampler and output
budget so the delta isolates prompt/presentation overhead from model startup.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import time
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


DEFAULT_OUTPUT = (
    REPO / "artifacts" / "fixes" / "raw_e2b_latency_20260730.json"
)
CASES = (
    ("es_knowledge", "¿Qué es la latencia en un sistema informático?", "es"),
    ("en_knowledge", "Why does the sky look blue?", "en"),
    ("es_social", "Cuéntame un chiste corto.", "es"),
    ("en_opinion", "What do you think about pineapple on pizza?", "en"),
)


def _summary(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    return {
        "p50": statistics.median(ordered),
        "minimum": ordered[0],
        "maximum": ordered[-1],
        "mean": statistics.fmean(ordered),
    }


def _content(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("raw response has no choice")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise ValueError("raw response has no message")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("raw response content is empty")
    return content


def _timing_record(
    *,
    case_id: str,
    arm: str,
    elapsed: float,
    response: dict[str, Any],
    content: str,
) -> dict[str, Any]:
    timings = response.get("timings")
    if not isinstance(timings, dict):
        timings = {}
    return {
        "case_id": case_id,
        "arm": arm,
        "elapsed_seconds": elapsed,
        "cache_n": timings.get("cache_n"),
        "prompt_n": timings.get("prompt_n"),
        "prompt_ms": timings.get("prompt_ms"),
        "predicted_n": timings.get("predicted_n"),
        "predicted_ms": timings.get("predicted_ms"),
        "output_chars": len(content),
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
    observations: list[dict[str, Any]] = []
    latest_response: dict[str, Any] | None = None
    original_post: Callable[..., dict[str, Any]] = llm._post

    def recording_post(
        payload: dict[str, Any],
        timeout: float | None = None,
    ) -> dict[str, Any]:
        nonlocal latest_response
        latest_response = original_post(payload, timeout)
        return latest_response

    llm._post = recording_post  # type: ignore[method-assign]
    try:
        llm.begin_request(30.0)
        llm._ensure_started()
        llm.end_request()

        # One unmeasured decode stabilizes CUDA kernels and allocator state.
        llm.begin_request(30.0)
        original_post(
            {
                "messages": [
                    {"role": "user", "content": "Reply with only: ready"}
                ],
                "temperature": 0.0,
                "seed": 0,
                "max_tokens": 128,
                "chat_template_kwargs": {"enable_thinking": False},
            }
        )
        llm.end_request()

        for case_id, text, language in CASES:
            for arm in ("raw", "baxy"):
                llm.begin_request(30.0)
                latest_response = None
                started = time.perf_counter()
                if arm == "raw":
                    response = original_post(
                        {
                            "messages": [{"role": "user", "content": text}],
                            "temperature": 0.0,
                            "seed": 0,
                            "max_tokens": 128,
                            "chat_template_kwargs": {"enable_thinking": False},
                        }
                    )
                    content = _content(response)
                else:
                    content, _ = llm.chat(
                        text,
                        history=[],
                        tools=None,
                        temperature=0.0,
                        conversation_kind="knowledge",
                        response_language=language,
                    )
                    response = latest_response
                    if not isinstance(response, dict):
                        raise RuntimeError("BAXY chat response was not captured")
                elapsed = time.perf_counter() - started
                observations.append(
                    _timing_record(
                        case_id=case_id,
                        arm=arm,
                        elapsed=elapsed,
                        response=response,
                        content=content,
                    )
                )
                llm.end_request()
    finally:
        llm.close()

    arms = {
        arm: _summary(
            [
                float(item["elapsed_seconds"])
                for item in observations
                if item["arm"] == arm
            ]
        )
        for arm in ("raw", "baxy")
    }
    report = {
        "schema": "baxy.raw-e2b-latency.v1",
        "scope": "registered_gpu_runtime_no_core_operations",
        "runtime": {
            "model": runtime_config.gguf.name,
            "server": runtime_config.llama_server.name,
            "gpu_layers": runtime_config.gpu_layers,
        },
        "cases": len(CASES),
        "observations": observations,
        "arms": arms,
        "baxy_minus_raw_p50_seconds": (
            arms["baxy"]["p50"] - arms["raw"]["p50"]
        ),
    }
    write_json_atomic(output, report)
    return report


def main() -> int:
    output = DEFAULT_OUTPUT
    report = run(output)
    print(
        json.dumps(
            {
                "output": str(output),
                "arms": report["arms"],
                "baxy_minus_raw_p50_seconds": report[
                    "baxy_minus_raw_p50_seconds"
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
