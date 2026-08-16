"""Concurrency, backpressure and cancellation probes against the owned server.

Starts the registered llama-server through ``LlmRuntime`` and measures, with
identical fixed prompts and budgets: per-request latency and makespan for
1/2/3 concurrent POSTs (three slots), queue wait for a fourth concurrent POST
(backpressure), and recovery latency after a mid-decode client disconnect.
No Core operation is dispatched; nothing in the product changes.
"""

from __future__ import annotations

import http.client
import json
import math
import os
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

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
    REPO / "artifacts" / "fixes" / "server_concurrency_cancel_20260730.json"
)
PROMPT = "Explica en una frase por qué el cielo es azul."


def _payload(max_tokens: int, seed: int) -> dict[str, Any]:
    return {
        "messages": [{"role": "user", "content": PROMPT}],
        "temperature": 0.0,
        "seed": seed,
        "max_tokens": max_tokens,
        "chat_template_kwargs": {"enable_thinking": False},
    }


def _post_direct(endpoint: str, payload: dict[str, Any], timeout: float) -> dict:
    host = endpoint.split("//", 1)[1].split("/", 1)[0]
    connection = http.client.HTTPConnection(host, timeout=timeout)
    try:
        body = json.dumps(payload).encode("utf-8")
        connection.request(
            "POST",
            "/v1/chat/completions",
            body=body,
            headers={"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        data = response.read()
        return json.loads(data)
    finally:
        connection.close()


def _summary(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    rank95 = min(len(ordered) - 1, math.ceil(0.95 * len(ordered)) - 1)
    return {
        "count": len(ordered),
        "p50": statistics.median(ordered),
        "p95_nearest_rank": ordered[rank95],
        "minimum": ordered[0],
        "maximum": ordered[-1],
    }


def _gpu_sample() -> str | None:
    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=temperature.gpu,clocks.sm,pstate,memory.used",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return (completed.stdout or "").strip()
    except (OSError, subprocess.TimeoutExpired):
        return None


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
    report: dict[str, Any] = {
        "schema": "baxy.server-concurrency-cancel.v1",
        "scope": "owned llama-server, identical prompts, no product change",
        "runtime": {
            "model": runtime_config.gguf.name,
            "gpu_layers": runtime_config.gpu_layers,
        },
        "gpu_state_before": _gpu_sample(),
    }
    try:
        llm.begin_request(60.0)
        llm._ensure_started()
        endpoint = llm._endpoint  # local owned loopback
        llm.end_request()
        _post_direct(endpoint, _payload(64, 0), 30.0)  # warm

        concurrency_results: dict[str, Any] = {}
        for width in (1, 2, 3, 4):
            latencies: list[float] = []
            lock = threading.Lock()

            def worker(seed: int) -> None:
                begun = time.perf_counter()
                _post_direct(endpoint, _payload(64, seed), 60.0)
                took = time.perf_counter() - begun
                with lock:
                    latencies.append(took)

            threads = [
                threading.Thread(target=worker, args=(seed,))
                for seed in range(width)
            ]
            makespan_start = time.perf_counter()
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            makespan = time.perf_counter() - makespan_start
            concurrency_results[f"width_{width}"] = {
                "per_request": _summary(latencies),
                "makespan_seconds": makespan,
                "queueing_estimate_seconds": (
                    max(latencies) - min(latencies) if width == 4 else None
                ),
            }
        report["concurrency"] = concurrency_results

        # Cancellation: open a long decode, drop the socket mid-decode, then
        # measure how quickly a fresh short request completes.
        def cancelled_long_decode() -> float:
            host = endpoint.split("//", 1)[1].split("/", 1)[0]
            connection = http.client.HTTPConnection(host, timeout=60.0)
            body = json.dumps(_payload(512, 99)).encode("utf-8")
            connection.request(
                "POST",
                "/v1/chat/completions",
                body=body,
                headers={"Content-Type": "application/json"},
            )
            time.sleep(0.5)
            connection.close()
            return 0.5

        recovery_samples: list[float] = []
        for attempt in range(5):
            cancelled_long_decode()
            begun = time.perf_counter()
            _post_direct(endpoint, _payload(16, 200 + attempt), 30.0)
            recovery_samples.append(time.perf_counter() - begun)
        baseline_short: list[float] = []
        for attempt in range(5):
            begun = time.perf_counter()
            _post_direct(endpoint, _payload(16, 300 + attempt), 30.0)
            baseline_short.append(time.perf_counter() - begun)
        report["cancellation"] = {
            "method": "client socket close 0.5s into a 512-token decode",
            "short_probe_after_cancel_seconds": _summary(recovery_samples),
            "short_probe_baseline_seconds": _summary(baseline_short),
        }
    finally:
        llm.close()
    report["gpu_state_after"] = _gpu_sample()
    write_json_atomic(output, report)
    return report


def main() -> int:
    report = run(DEFAULT_OUTPUT)
    print(
        json.dumps(
            {
                "concurrency": {
                    key: {
                        "p50": value["per_request"]["p50"],
                        "max": value["per_request"]["maximum"],
                        "makespan": value["makespan_seconds"],
                    }
                    for key, value in report["concurrency"].items()
                },
                "cancel_recovery_p50": report["cancellation"][
                    "short_probe_after_cancel_seconds"
                ]["p50"],
                "short_baseline_p50": report["cancellation"][
                    "short_probe_baseline_seconds"
                ]["p50"],
            },
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
