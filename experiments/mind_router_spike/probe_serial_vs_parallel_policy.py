"""Does overlapping the policy calls actually make the turn faster?

BAXY runs three llama-server slots so the primary policy, the semantic guard and
the language detector can decode at the same time. Overlap is only worth it if
the wall time of the whole group drops. The token-rate measurement says a policy
token costs 14.64 ms alone and 21.33 ms while the other two share the device, so
the overlap is not free and might not pay for itself.

This probe answers it end to end: the same three real captured payloads, one warm
server, alternating serial and parallel execution in ABBA order, comparing the
wall time of the group. Nothing is installed and no effect is executed.
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.baxy_runtime_config import (  # noqa: E402
    DEFAULT_RUNTIME_MANIFEST,
    public_runtime_identity,
    resolve_runtime,
)
from scripts.measure_mind_budget import write_json_atomic  # noqa: E402

PAYLOADS = REPO / "artifacts" / "fixes" / "policy_component_payloads_20260731.json"
OUTPUT = REPO / "artifacts" / "fixes" / "serial_vs_parallel_policy_20260731.json"
PORT = 58329
ROUNDS = 4


def _wait_ready(process: subprocess.Popen[bytes], timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"llama-server terminó (rc={process.returncode})")
        try:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{PORT}/health", timeout=3) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            time.sleep(0.5)
    raise RuntimeError("llama-server no quedó listo")


def _post(payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"http://127.0.0.1:{PORT}/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST")
    with urllib.request.urlopen(request, timeout=180) as response:
        result = json.loads(response.read().decode("utf-8"))
    timings = result.get("timings") or {}
    return {
        "predicted_n": timings.get("predicted_n"),
        "predicted_ms": timings.get("predicted_ms"),
        "prompt_ms": timings.get("prompt_ms"),
        "content": result["choices"][0]["message"].get("content") or "",
    }


def run() -> dict[str, Any]:
    runtime = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    payloads = json.loads(PAYLOADS.read_text(encoding="utf-8"))
    group = [
        payloads["baxy_turn_decision"],
        payloads["semantic_effect_guard"],
        payloads["language_grammar"],
    ]

    samples: list[dict[str, Any]] = []
    process = subprocess.Popen(
        [
            str(runtime.llama_server),
            "-m", str(runtime.gguf),
            "--host", "127.0.0.1", "--port", str(PORT),
            "-ngl", str(runtime.gpu_layers),
            "-c", "12288",
            "-fa", "on", "-ctk", "q8_0", "-ctv", "q8_0",
            "-np", "3", "--jinja", "--reasoning", "off",
            "--reasoning-budget", "0", "--cont-batching",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        _wait_ready(process, 240.0)
        for payload in group:
            _post(payload)

        with ThreadPoolExecutor(max_workers=3) as pool:
            for round_index in range(ROUNDS):
                order = (
                    ("serial", "parallel", "parallel", "serial")
                    if round_index % 2 == 0
                    else ("parallel", "serial", "serial", "parallel")
                )
                for block, arm in enumerate(order):
                    started = time.perf_counter()
                    if arm == "serial":
                        results = [_post(payload) for payload in group]
                    else:
                        results = list(pool.map(_post, group))
                    elapsed = time.perf_counter() - started
                    samples.append({
                        "round": round_index,
                        "block": block,
                        "arm": arm,
                        "group_seconds": round(elapsed, 6),
                        "policy_predicted_n": results[0]["predicted_n"],
                        "policy_predicted_ms": results[0]["predicted_ms"],
                        "policy_ms_per_token": (
                            round(results[0]["predicted_ms"] / results[0]["predicted_n"], 2)
                            if results[0].get("predicted_n") else None),
                        "contents": [result["content"] for result in results],
                    })
    finally:
        process.terminate()
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=30)

    def summarize(arm: str) -> dict[str, Any]:
        rows = [row for row in samples if row["arm"] == arm]
        values = sorted(row["group_seconds"] for row in rows)
        rates = [row["policy_ms_per_token"] for row in rows if row["policy_ms_per_token"]]
        return {
            "n": len(values),
            "group_p50_s": round(statistics.median(values), 4),
            "group_min_s": round(values[0], 4),
            "group_max_s": round(values[-1], 4),
            "group_stdev_s": round(statistics.stdev(values), 4) if len(values) > 1 else 0.0,
            "policy_ms_per_token_p50": round(statistics.median(rates), 2) if rates else None,
            "values_s": [round(value, 4) for value in values],
        }

    serial, parallel = summarize("serial"), summarize("parallel")

    # The decisions themselves must not depend on how they were scheduled.
    outputs_stable = {}
    for index, name in enumerate(("P", "G", "L")):
        serial_set = {tuple(row["contents"])[index] for row in samples if row["arm"] == "serial"}
        parallel_set = {tuple(row["contents"])[index] for row in samples if row["arm"] == "parallel"}
        outputs_stable[name] = {
            "serial_distinct": len(serial_set),
            "parallel_distinct": len(parallel_set),
            "identical": serial_set == parallel_set,
        }

    report = {
        "schema": "baxy.serial-vs-parallel-policy.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "effects_executed": 0,
        "question": (
            "BAXY overlaps the primary policy, the semantic guard and the "
            "language detector across three slots. A policy token costs 14.64 ms "
            "alone and 21.33 ms contended, so does the overlap actually shorten "
            "the turn?"),
        "method": (
            "the three real captured payloads against one warm server, serial "
            "and parallel execution alternated in ABBA order over 4 rounds, "
            "comparing the wall time of the whole group"),
        "runtime": public_runtime_identity(runtime),
        "serial": serial,
        "parallel": parallel,
        "delta_p50_s": round(parallel["group_p50_s"] - serial["group_p50_s"], 4),
        "output_stability": outputs_stable,
        "samples": samples,
    }
    write_json_atomic(OUTPUT, report)
    return report


if __name__ == "__main__":
    result = run()
    print(json.dumps({
        "serial_group_p50_s": result["serial"]["group_p50_s"],
        "parallel_group_p50_s": result["parallel"]["group_p50_s"],
        "delta_p50_s": result["delta_p50_s"],
        "serial_policy_ms_per_token": result["serial"]["policy_ms_per_token_p50"],
        "parallel_policy_ms_per_token": result["parallel"]["policy_ms_per_token_p50"],
    }, indent=1))
