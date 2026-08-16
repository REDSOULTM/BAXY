"""Why does a policy token cost more than a chat token?

The pipeline measurement says the primary policy emits only 84.5 tokens yet
spends 3024 ms decoding them: 35.8 ms per token, against 14.3 ms per token for
free chat on the same model. Fewer tokens is therefore not the lever; the lever
is whatever makes each token expensive.

There are two candidates and they need separating by measurement:

  * constraint cost - llama.cpp applies the JSON-schema grammar to the logits at
    every token, and the primary schema carries two 28/29-value operation enums;
  * contention - the product runs three slots so the policy, the guard and the
    language detector can overlap, and each one's wall time then includes
    waiting for the others.

This probe posts the real captured payloads against one warm server and
alternates the arms in ABBA order, reporting ms per predicted token from
llama-server's own timings. Nothing is installed and no effect is executed.
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
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
OUTPUT = REPO / "artifacts" / "fixes" / "policy_token_rate_20260731.json"
PORT = 58321
ROUNDS = 3


def _server_command(runtime: Any, parallel: int) -> list[str]:
    return [
        str(runtime.llama_server),
        "-m", str(runtime.gguf),
        "--host", "127.0.0.1", "--port", str(PORT),
        "-ngl", str(runtime.gpu_layers),
        "-c", str(4096 * parallel),
        "-fa", "on", "-ctk", "q8_0", "-ctv", "q8_0",
        "-np", str(parallel),
        "--jinja", "--reasoning", "off", "--reasoning-budget", "0",
        "--cont-batching",
    ]


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


def _post(payload: dict[str, Any], timeout: float = 180.0) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"http://127.0.0.1:{PORT}/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST")
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.loads(response.read().decode("utf-8"))
    elapsed = time.perf_counter() - started
    timings = result.get("timings") or {}
    return {
        "seconds": round(elapsed, 6),
        "prompt_n": timings.get("prompt_n"),
        "cache_n": timings.get("cache_n"),
        "predicted_n": timings.get("predicted_n"),
        "prompt_ms": timings.get("prompt_ms"),
        "predicted_ms": timings.get("predicted_ms"),
        "content": (result["choices"][0]["message"].get("content") or ""),
    }


def _relaxed_enums(payload: dict[str, Any]) -> dict[str, Any]:
    """The same schema with its two long operation enums opened to a string.

    This keeps every field, every name and the strict object shape, and changes
    only how much alternation the grammar has to carry. It is a measurement
    variant, not a proposal: it is not decision-preserving on its own.
    """

    variant = json.loads(json.dumps(payload))
    schema = variant["response_format"]["json_schema"]["schema"]["properties"]
    schema["operation"] = {"type": "string", "maxLength": 40}
    schema["effect_operations"] = {
        "type": "array",
        "items": {"type": "string", "maxLength": 40},
        "maxItems": 8,
    }
    return variant


def _unconstrained(payload: dict[str, Any]) -> dict[str, Any]:
    variant = json.loads(json.dumps(payload))
    variant.pop("response_format", None)
    return variant


def run() -> dict[str, Any]:
    runtime = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    payloads = json.loads(PAYLOADS.read_text(encoding="utf-8"))
    primary = payloads["baxy_turn_decision"]
    guard = payloads["semantic_effect_guard"]
    language = payloads["language_grammar"]
    chat = payloads["chat"]

    variants = {
        "P_full_schema": primary,
        "P_relaxed_enums": _relaxed_enums(primary),
        "P_unconstrained": _unconstrained(primary),
        "chat_unconstrained": chat,
    }

    samples: list[dict[str, Any]] = []
    process = subprocess.Popen(
        _server_command(runtime, parallel=3),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        _wait_ready(process, 240.0)
        for payload in variants.values():
            _post(payload)

        for round_index in range(ROUNDS):
            names = list(variants)
            if round_index % 2 == 1:
                names.reverse()
            for name in names:
                result = _post(variants[name])
                result.update({"round": round_index, "arm": name, "concurrent": False})
                samples.append(result)

            # The contended arm: the policy while the guard and the language
            # detector occupy the other two slots, which is what the product
            # actually does on a model turn.
            contended: list[dict[str, Any]] = []
            errors: list[BaseException] = []

            def side(body: dict[str, Any]) -> None:
                try:
                    _post(body)
                except BaseException as error:  # noqa: BLE001 - diagnostics only
                    errors.append(error)

            threads = [
                threading.Thread(target=side, args=(guard,)),
                threading.Thread(target=side, args=(language,)),
            ]
            for thread in threads:
                thread.start()
            try:
                result = _post(primary)
                result.update({
                    "round": round_index,
                    "arm": "P_full_schema_contended",
                    "concurrent": True,
                })
                contended.append(result)
            finally:
                for thread in threads:
                    thread.join(timeout=180)
            if errors:
                raise RuntimeError(f"la carga concurrente falló: {errors[0]}")
            samples.extend(contended)
    finally:
        process.terminate()
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=30)

    def summarize(arm: str) -> dict[str, Any] | None:
        rows = [row for row in samples if row["arm"] == arm]
        if not rows:
            return None
        per_token = [
            row["predicted_ms"] / row["predicted_n"]
            for row in rows
            if row.get("predicted_n") and row.get("predicted_ms")
        ]
        return {
            "n": len(rows),
            "predicted_n_p50": statistics.median(
                [row["predicted_n"] for row in rows if row.get("predicted_n")]),
            "predicted_ms_p50": round(statistics.median(
                [row["predicted_ms"] for row in rows if row.get("predicted_ms")]), 1),
            "prompt_ms_p50": round(statistics.median(
                [row["prompt_ms"] for row in rows if row.get("prompt_ms")]), 1),
            "ms_per_predicted_token_p50": (
                round(statistics.median(per_token), 2) if per_token else None),
            "wall_seconds_p50": round(statistics.median(
                [row["seconds"] for row in rows]), 4),
        }

    arms = [*variants, "P_full_schema_contended"]
    per_arm = {arm: summarize(arm) for arm in arms}

    report = {
        "schema": "baxy.policy-token-rate.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "effects_executed": 0,
        "question": (
            "the primary policy emits only 84.5 tokens but spends 3024 ms "
            "decoding them. Is the cost per token driven by the JSON-schema "
            "grammar or by contention with the other policy calls?"),
        "method": (
            "one warm server with the product flags; the real captured payloads "
            "posted in ABBA-alternated order over 3 rounds; ms per predicted "
            "token taken from llama-server's own timings, not from wall clock"),
        "arms": {
            "P_full_schema": "the exact payload the product sends, alone",
            "P_relaxed_enums": (
                "same payload, same fields, with the two 28/29-value operation "
                "enums opened to a plain string: isolates grammar alternation "
                "cost. A measurement variant, not a proposal."),
            "P_unconstrained": (
                "same prompt with response_format removed: isolates the whole "
                "constraint cost"),
            "chat_unconstrained": "free chat, the model's own rate",
            "P_full_schema_contended": (
                "the exact product payload while the guard and the language "
                "detector occupy the other two slots"),
        },
        "runtime": public_runtime_identity(runtime),
        "per_arm": per_arm,
        "samples": samples,
    }
    write_json_atomic(OUTPUT, report)
    return report


if __name__ == "__main__":
    result = run()
    for arm, stats in result["per_arm"].items():
        if stats:
            print(f"{arm:28} tok={stats['predicted_n_p50']:>6} "
                  f"decode={stats['predicted_ms_p50']:>8} ms  "
                  f"per_token={stats['ms_per_predicted_token_p50']:>6} ms")
