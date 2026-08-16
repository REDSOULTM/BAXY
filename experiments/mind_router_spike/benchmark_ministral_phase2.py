"""Phase-2 isolated microbenchmarks: Ministral-3-3B Q4_K_M vs Gemma-4 E2B QAT.

Both arms run on the registered llama-server binary (read-only use) at an
isolated port with fresh servers per block in ABBA order.  Identical chat
inputs, sampler, seed and budgets; the structured probe reuses the dumped
production P payload (model-agnostic messages + JSON schema).  Reports TTFT
proxy, prefill, decode, total, JSON validity and VRAM.  Nothing in the
registered runtime, manifests or Git changes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.baxy_runtime_config import (  # noqa: E402
    DEFAULT_RUNTIME_MANIFEST,
    resolve_runtime,
)
from scripts.measure_mind_budget import write_json_atomic  # noqa: E402

DEFAULT_OUTPUT = (
    REPO / "artifacts" / "fixes" / "ministral_phase2_ab_20260730.json"
)
CHAT_CASES = (
    ("es_knowledge", "¿Qué es la latencia en un sistema informático?"),
    ("en_knowledge", "Why does the sky look blue?"),
    ("es_social", "Cuéntame un chiste corto."),
    ("spanglish", "che, fijate how much battery is left en el notebook"),
)
PORT = 8937


def _chat_payload(text: str) -> dict[str, Any]:
    return {
        "messages": [{"role": "user", "content": text}],
        "temperature": 0.0,
        "seed": 0,
        "max_tokens": 128,
    }


def _post(payload: dict[str, Any], timeout: float = 120.0) -> dict[str, Any]:
    request = urllib.request.Request(
        f"http://127.0.0.1:{PORT}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def _health_ok(timeout_seconds: float = 240.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{PORT}/health", timeout=3
            ) as response:
                if json.load(response).get("status") == "ok":
                    return True
        except OSError:
            pass
        time.sleep(1.5)
    return False


def _gpu_mib() -> int | None:
    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.used",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return int((completed.stdout or "0").strip().splitlines()[0])
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def _summary(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    if not ordered:
        return {"count": 0}
    rank95 = min(len(ordered) - 1, math.ceil(0.95 * len(ordered)) - 1)
    return {
        "count": len(ordered),
        "p50": statistics.median(ordered),
        "p95_nearest_rank": ordered[rank95],
        "mean": statistics.fmean(ordered),
        "minimum": ordered[0],
        "maximum": ordered[-1],
    }


def _observe(case_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    response = _post(payload)
    elapsed = time.perf_counter() - started
    timings = response.get("timings") or {}
    choice = (response.get("choices") or [{}])[0]
    content = (choice.get("message") or {}).get("content") or ""
    predicted_n = timings.get("predicted_n")
    predicted_ms = timings.get("predicted_ms")
    ttft = None
    decode_tps = None
    if predicted_n and isinstance(predicted_ms, (int, float)):
        per_token = float(predicted_ms) / float(predicted_n) / 1000.0
        ttft = elapsed - float(predicted_ms) / 1000.0 + per_token
        decode_tps = float(predicted_n) / (float(predicted_ms) / 1000.0)
    json_valid = None
    if case_id == "p_policy":
        try:
            json_valid = isinstance(json.loads(content), dict)
        except json.JSONDecodeError:
            json_valid = False
    return {
        "case_id": case_id,
        "elapsed_seconds": elapsed,
        "ttft_proxy_seconds": ttft,
        "prompt_ms": timings.get("prompt_ms"),
        "prompt_n": timings.get("prompt_n"),
        "predicted_ms": predicted_ms,
        "predicted_n": predicted_n,
        "decode_tok_per_s": decode_tps,
        "finish_reason": choice.get("finish_reason"),
        "json_valid": json_valid,
        "output_chars": len(content),
        "output_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
    }


def _run_block(
    *,
    server: Path,
    model: Path,
    p_payload: dict[str, Any],
    rounds: int,
) -> dict[str, Any]:
    command = [
        str(server),
        "-m",
        str(model),
        "-ngl",
        "99",
        "--ctx-size",
        "4096",
        "--port",
        str(PORT),
        "--host",
        "127.0.0.1",
        "-fa",
        "on",
        "--parallel",
        "1",
        "-ctk",
        "q8_0",
        "-ctv",
        "q8_0",
        "--jinja",
        "--reasoning",
        "off",
        "--reasoning-budget",
        "0",
    ]
    process = subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    observations: list[dict[str, Any]] = []
    vram_peak: int | None = None
    load_seconds: float | None = None
    started = time.perf_counter()
    try:
        if not _health_ok():
            raise RuntimeError(f"server did not become healthy for {model.name}")
        load_seconds = time.perf_counter() - started
        _post(_chat_payload("Reply with only: ready"))
        for _ in range(rounds):
            for case_id, text in CHAT_CASES:
                observations.append(_observe(case_id, _chat_payload(text)))
            observations.append(_observe("p_policy", p_payload))
            sample = _gpu_mib()
            if sample is not None:
                vram_peak = max(vram_peak or 0, sample)
    finally:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=15)
    return {
        "observations": observations,
        "vram_peak_mib": vram_peak,
        "load_seconds": load_seconds,
    }


def run(output: Path, ministral: Path, rounds: int) -> dict[str, Any]:
    runtime_config = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    server = runtime_config.llama_server
    gemma = runtime_config.gguf
    p_payload = json.loads(
        (
            REPO / "artifacts" / "fixes" / "p_payload_dump" / "p_payload.json"
        ).read_text(encoding="utf-8")
    )
    blocks: list[dict[str, Any]] = []
    for index, arm in enumerate(("gemma", "ministral", "ministral", "gemma")):
        model = gemma if arm == "gemma" else ministral
        block = _run_block(
            server=server,
            model=model,
            p_payload=p_payload,
            rounds=rounds,
        )
        block["arm"] = arm
        block["order_index"] = index
        blocks.append(block)

    def collect(arm: str, key: str, case: str | None = None) -> list[float]:
        values: list[float] = []
        for block in blocks:
            if block["arm"] != arm:
                continue
            for row in block["observations"]:
                if case is not None and row["case_id"] != case:
                    continue
                value = row.get(key)
                if isinstance(value, (int, float)):
                    values.append(float(value))
        return values

    summary: dict[str, Any] = {}
    for arm in ("gemma", "ministral"):
        summary[arm] = {
            "chat_total_seconds": _summary(
                [
                    value
                    for case_id, _ in CHAT_CASES
                    for value in collect(arm, "elapsed_seconds", case_id)
                ]
            ),
            "chat_ttft_proxy_seconds": _summary(
                [
                    value
                    for case_id, _ in CHAT_CASES
                    for value in collect(arm, "ttft_proxy_seconds", case_id)
                ]
            ),
            "chat_decode_tok_per_s": _summary(
                [
                    value
                    for case_id, _ in CHAT_CASES
                    for value in collect(arm, "decode_tok_per_s", case_id)
                ]
            ),
            "p_policy_total_seconds": _summary(
                collect(arm, "elapsed_seconds", "p_policy")
            ),
            "p_policy_prompt_ms": _summary(
                collect(arm, "prompt_ms", "p_policy")
            ),
            "p_policy_json_valid": [
                row["json_valid"]
                for block in blocks
                if block["arm"] == arm
                for row in block["observations"]
                if row["case_id"] == "p_policy"
            ],
            "vram_peak_mib": max(
                (
                    block["vram_peak_mib"]
                    for block in blocks
                    if block["arm"] == arm and block["vram_peak_mib"]
                ),
                default=None,
            ),
            "load_seconds": [
                block["load_seconds"]
                for block in blocks
                if block["arm"] == arm
            ],
        }
    report = {
        "schema": "baxy.ministral-phase2-ab.v1",
        "measured_at_utc": "2026-07-30",
        "scope": "isolated port, registered server binary read-only, fresh servers, ABBA",
        "server": str(server),
        "gemma_gguf": str(gemma),
        "ministral_gguf": str(ministral),
        "rounds_per_block": rounds,
        "summary": summary,
        "blocks": blocks,
    }
    write_json_atomic(output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--ministral",
        type=Path,
        default=Path(
            "D:/BAXY/experimental_assets_20260730/"
            "Ministral-3-3B-Instruct-2512-Q4_K_M.gguf"
        ),
    )
    parser.add_argument("--rounds", type=int, default=3)
    args = parser.parse_args()
    report = run(args.output, args.ministral, args.rounds)
    digest = {
        arm: {
            "chat_p50": report["summary"][arm]["chat_total_seconds"].get("p50"),
            "ttft_p50": report["summary"][arm]["chat_ttft_proxy_seconds"].get(
                "p50"
            ),
            "decode_tps_p50": report["summary"][arm][
                "chat_decode_tok_per_s"
            ].get("p50"),
            "p_policy_p50": report["summary"][arm][
                "p_policy_total_seconds"
            ].get("p50"),
            "p_json_valid": report["summary"][arm]["p_policy_json_valid"],
            "vram_peak_mib": report["summary"][arm]["vram_peak_mib"],
        }
        for arm in ("gemma", "ministral")
    }
    print(json.dumps(digest, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
