"""Isolated MTP A/B on the b9553 experimental server: target vs target+assistant.

Runs completely outside the registered runtime: binaries and the converted
assistant GGUF live in an isolated folder, the registered manifest is not
read for server selection, and no Core operation or product path executes.
Both arms receive byte-identical payloads (the dumped production P payload
plus four chat cases), same sampler, seed, grammar and budgets, with fresh
servers per block in ABBA order.  Reports TTFT proxy, prefill, decode, total,
draft acceptance and VRAM.  Output hashes are compared across arms.
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

from scripts.measure_mind_budget import write_json_atomic  # noqa: E402

DEFAULT_OUTPUT = (
    REPO / "artifacts" / "fixes" / "b9553_mtp_assistant_ab_20260730.json"
)
CHAT_CASES = (
    ("es_knowledge", "¿Qué es la latencia en un sistema informático?"),
    ("en_knowledge", "Why does the sky look blue?"),
    ("es_social", "Cuéntame un chiste corto."),
    ("en_opinion", "What do you think about pineapple on pizza?"),
)
PORT = 8934


def _chat_payload(text: str) -> dict[str, Any]:
    return {
        "messages": [{"role": "user", "content": text}],
        "temperature": 0.0,
        "seed": 0,
        "max_tokens": 128,
        "chat_template_kwargs": {"enable_thinking": False},
    }


def _post(payload: dict[str, Any], timeout: float = 120.0) -> dict[str, Any]:
    request = urllib.request.Request(
        f"http://127.0.0.1:{PORT}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def _health_ok(timeout_seconds: float = 180.0) -> bool:
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
    if predicted_n and isinstance(predicted_ms, (int, float)):
        per_token = float(predicted_ms) / float(predicted_n) / 1000.0
        ttft = elapsed - float(predicted_ms) / 1000.0 + per_token
    return {
        "case_id": case_id,
        "elapsed_seconds": elapsed,
        "ttft_proxy_seconds": ttft,
        "prompt_ms": timings.get("prompt_ms"),
        "prompt_n": timings.get("prompt_n"),
        "cache_n": timings.get("cache_n"),
        "predicted_ms": predicted_ms,
        "predicted_n": predicted_n,
        "draft_n": timings.get("draft_n"),
        "draft_n_accepted": timings.get("draft_n_accepted"),
        "finish_reason": choice.get("finish_reason"),
        "output_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "output_chars": len(content),
    }


def _run_block(
    *,
    server: Path,
    target: Path,
    assistant: Path | None,
    p_payload: dict[str, Any],
    rounds: int,
) -> dict[str, Any]:
    command = [
        str(server),
        "-m",
        str(target),
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
    if assistant is not None:
        command.extend(
            [
                "--spec-type",
                "draft-mtp",
                "--model-draft",
                str(assistant),
                "-ngld",
                "99",
                "--spec-draft-n-max",
                "4",
            ]
        )
    process = subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    observations: list[dict[str, Any]] = []
    vram_peak: int | None = None
    try:
        if not _health_ok():
            raise RuntimeError("experimental server did not become healthy")
        _post(_chat_payload("Reply with only: ready"))  # warm
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
    return {"observations": observations, "vram_peak_mib": vram_peak}


def run(
    output: Path,
    assets: Path,
    rounds: int,
    target: Path,
) -> dict[str, Any]:
    server = assets / "b9553" / "llama-server.exe"
    assistant = assets / "gemma-4-E2B-it-assistant-Q8_0.gguf"
    p_payload = json.loads(
        (
            REPO / "artifacts" / "fixes" / "p_payload_dump" / "p_payload.json"
        ).read_text(encoding="utf-8")
    )
    blocks: list[dict[str, Any]] = []
    # ABBA: target, assistant, assistant, target — fresh server per block.
    for index, arm in enumerate(("target", "assistant", "assistant", "target")):
        block = _run_block(
            server=server,
            target=target,
            assistant=assistant if arm == "assistant" else None,
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
    for arm in ("target", "assistant"):
        chats = [
            value
            for case_id, _ in CHAT_CASES
            for value in collect(arm, "elapsed_seconds", case_id)
        ]
        summary[arm] = {
            "chat_total_seconds": _summary(chats),
            "chat_ttft_proxy_seconds": _summary(
                [
                    value
                    for case_id, _ in CHAT_CASES
                    for value in collect(arm, "ttft_proxy_seconds", case_id)
                ]
            ),
            "p_policy_total_seconds": _summary(
                collect(arm, "elapsed_seconds", "p_policy")
            ),
            "p_policy_prompt_ms": _summary(collect(arm, "prompt_ms", "p_policy")),
            "p_policy_predicted_ms": _summary(
                collect(arm, "predicted_ms", "p_policy")
            ),
            "vram_peak_mib": max(
                (
                    block["vram_peak_mib"]
                    for block in blocks
                    if block["arm"] == arm and block["vram_peak_mib"]
                ),
                default=None,
            ),
        }
    drafted = collect("assistant", "draft_n")
    accepted = collect("assistant", "draft_n_accepted")
    summary["draft_acceptance"] = {
        "draft_n_total": sum(drafted),
        "draft_n_accepted_total": sum(accepted),
        "acceptance_rate": (
            sum(accepted) / sum(drafted) if sum(drafted) else None
        ),
    }
    per_case_outputs: dict[str, dict[str, set[str]]] = {}
    for block in blocks:
        for row in block["observations"]:
            per_case_outputs.setdefault(row["case_id"], {}).setdefault(
                block["arm"], set()
            ).add(row["output_sha256"])
    summary["output_equivalence"] = {
        case_id: {
            "target_distinct": len(arms.get("target", set())),
            "assistant_distinct": len(arms.get("assistant", set())),
            "cross_arm_identical": bool(
                arms.get("target", set()) & arms.get("assistant", set())
            ),
        }
        for case_id, arms in sorted(per_case_outputs.items())
    }
    report = {
        "schema": "baxy.b9553-mtp-assistant-ab.v1",
        "measured_at_utc": "2026-07-30",
        "scope": "isolated experimental folder; registered runtime untouched",
        "server": str(server),
        "target_gguf": str(target),
        "assistant_gguf": str(assistant),
        "rounds_per_block": rounds,
        "block_order": ["target", "assistant", "assistant", "target"],
        "summary": summary,
        "blocks": blocks,
    }
    write_json_atomic(output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--assets",
        type=Path,
        default=Path("D:/BAXY/experimental_assets_20260730"),
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=Path(
            "D:/BAXYRuntime/assets/models/gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf"
        ),
    )
    parser.add_argument("--rounds", type=int, default=3)
    args = parser.parse_args()
    report = run(args.output, args.assets, args.rounds, args.target)
    digest = {
        "summary": {
            arm: {
                "chat_p50": report["summary"][arm]["chat_total_seconds"]["p50"],
                "p_policy_p50": report["summary"][arm]["p_policy_total_seconds"][
                    "p50"
                ],
                "vram_peak_mib": report["summary"][arm]["vram_peak_mib"],
            }
            for arm in ("target", "assistant")
        },
        "draft_acceptance": report["summary"]["draft_acceptance"],
        "output_equivalence": report["summary"]["output_equivalence"],
    }
    print(json.dumps(digest, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
