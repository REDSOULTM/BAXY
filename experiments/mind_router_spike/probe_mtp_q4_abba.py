"""ABBA of Gemma-4 MTP speculative decoding on the certified runtime.

The previous physical rejection used the official assistant converted locally to
Q8_0 and ran it on b9553, because the funnel believed the certified b9980 could
not load a Gemma4 drafter at all. Both premises were wrong:

* Google's QAT documentation requires the assistant to be a QAT checkpoint at
  the same precision as the target. Q8_0 against a Q4 QAT target is a
  combination the vendor documents as unsupported.
* b9980 does load ``mtp-gemma-4-E2B-it-Q4_0.gguf`` and serves with it. The
  ``Gemma4Assistant requires ctx_other to be set`` line llama.cpp emits is
  annotated by llama.cpp itself as normal during memory fitting.

This probe therefore re-runs the decision properly: certified b9980, certified
target, precision-matched Q4_0 drafter, product server flags, ABBA order, and a
byte-for-byte comparison of what the model actually says. Nothing is installed
and no effect is executed; both servers run on their own port and are killed.
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
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

DRAFTER = Path(
    r"D:\BAXY\experimental_assets_20260731\mtp-gemma-4-E2B-it-Q4_0.gguf")
OUTPUT = REPO / "artifacts" / "fixes" / "mtp_q4_abba_20260731.json"
PORT = 58317

# Prompts that exercise what BAXY actually asks the model for: a decision, a
# short grounded answer and free prose. Temperature 0 so the arms are
# comparable byte for byte.
PROMPTS = (
    ("chat_short", "contame en una linea que hace un ssd"),
    ("chat_medium", "explicame en tres oraciones por que conviene reiniciar la pc"),
    ("status", "cuanta bateria queda y cuanta ram tengo"),
    ("decision", "necesito dejar el equipo en silencio ya mismo"),
    ("prose", "escribi un parrafo corto sobre como cuidar la bateria de una notebook"),
)
ROUNDS = 2


def _server_command(runtime: Any, with_draft: bool) -> list[str]:
    """Product server flags, plus the drafter only in the candidate arm."""

    command = [
        str(runtime.llama_server),
        "-m", str(runtime.gguf),
        "--host", "127.0.0.1", "--port", str(PORT),
        "-ngl", str(runtime.gpu_layers),
        "-c", "12288",
        "-fa", "on", "-ctk", "q8_0", "-ctv", "q8_0",
        "-np", "3", "--jinja", "--reasoning", "off", "--reasoning-budget", "0",
        "--cont-batching",
    ]
    if with_draft:
        command += [
            "--spec-type", "draft-mtp",
            "--spec-draft-model", str(DRAFTER),
            "--spec-draft-ngl", "99",
        ]
    return command


def _wait_ready(process: subprocess.Popen[bytes], timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                f"llama-server terminó durante el arranque (rc={process.returncode})")
        try:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{PORT}/health", timeout=3) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            time.sleep(0.5)
    raise RuntimeError("llama-server no quedó listo dentro del plazo")


def _chat(text: str, timeout: float) -> tuple[float, str, int]:
    body = json.dumps({
        "messages": [{"role": "user", "content": text}],
        "temperature": 0,
        "max_tokens": 160,
    }).encode("utf-8")
    request = urllib.request.Request(
        f"http://127.0.0.1:{PORT}/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST")
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    elapsed = time.perf_counter() - started
    content = payload["choices"][0]["message"].get("content") or ""
    tokens = int((payload.get("usage") or {}).get("completion_tokens") or 0)
    return elapsed, content, tokens


def _run_arm(runtime: Any, with_draft: bool, block: str,
             samples: list[dict[str, Any]]) -> None:
    command = _server_command(runtime, with_draft)
    process = subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        _wait_ready(process, 240.0)
        # Calentamiento idéntico en ambos brazos.
        for _ in range(2):
            _chat("hola", 120.0)
        for label, text in PROMPTS:
            elapsed, content, tokens = _chat(text, 180.0)
            samples.append({
                "block": block,
                "arm": "draft" if with_draft else "baseline",
                "prompt": label,
                "seconds": round(elapsed, 6),
                "completion_tokens": tokens,
                "content": content,
            })
    finally:
        process.terminate()
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=30)
        # El puerto tarda un instante en liberarse entre brazos.
        time.sleep(2.0)


def run() -> dict[str, Any]:
    runtime = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    if not DRAFTER.is_file():
        raise RuntimeError(f"falta el drafter experimental: {DRAFTER}")

    samples: list[dict[str, Any]] = []
    for round_index in range(ROUNDS):
        order = (
            (False, True, True, False)
            if round_index % 2 == 0
            else (True, False, False, True)
        )
        for block_index, with_draft in enumerate(order):
            _run_arm(runtime, with_draft, f"r{round_index}b{block_index}", samples)

    def summarize(arm: str) -> dict[str, Any]:
        rows = [s for s in samples if s["arm"] == arm]
        values = sorted(row["seconds"] for row in rows)
        tokens = [row["completion_tokens"] for row in rows]
        per_token = [
            row["seconds"] / row["completion_tokens"]
            for row in rows if row["completion_tokens"] > 0
        ]
        return {
            "n": len(values),
            "min_s": round(values[0], 4),
            "p50_s": round(statistics.median(values), 4),
            "max_s": round(values[-1], 4),
            "mean_s": round(statistics.fmean(values), 4),
            "stdev_s": round(statistics.stdev(values), 4) if len(values) > 1 else 0.0,
            "completion_tokens_total": sum(tokens),
            "s_per_generated_token_p50": (
                round(statistics.median(per_token), 6) if per_token else None
            ),
        }

    baseline, draft = summarize("baseline"), summarize("draft")

    # La puerta dura: el modelo debe decir exactamente lo mismo. Una ganancia de
    # latencia que cambie la respuesta visible no es adoptable.
    outputs: dict[str, Any] = {}
    for label, _ in PROMPTS:
        left = {s["content"] for s in samples
                if s["prompt"] == label and s["arm"] == "baseline"}
        right = {s["content"] for s in samples
                 if s["prompt"] == label and s["arm"] == "draft"}
        outputs[label] = {
            "baseline_distinct": len(left),
            "draft_distinct": len(right),
            "identical": left == right and len(left) == 1,
        }

    report = {
        "schema": "baxy.mtp-q4-abba.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "effects_executed": 0,
        "question": (
            "on the certified b9980 runtime, does the precision-matched Q4_0 "
            "QAT drafter make BAXY faster without changing what the model says?"
        ),
        "corrects": (
            "model_research_funnel_20260730.json claimed adopting Gemma-4 MTP "
            "required downgrading llama-server to b9553 because of "
            "ggml-org/llama.cpp#24795. b9980 loads and serves with the Q4_0 "
            "drafter, so that blocker does not apply to this configuration."
        ),
        "runtime": public_runtime_identity(runtime),
        "drafter": {
            "path": str(DRAFTER),
            "source": (
                "https://huggingface.co/unsloth/gemma-4-E2B-it-qat-GGUF"
                "/resolve/main/MTP/mtp-gemma-4-E2B-it-Q4_0.gguf"),
            "license": "apache-2.0",
            "bytes": DRAFTER.stat().st_size,
            "sha256": (
                "586f2460b909008640981ec34060aa864e03c144fbabfb3173c4335087e4aae0"),
            "why_this_asset": (
                "same repository as the certified target and Q4 precision, "
                "which is what Google's QAT card requires of an MTP assistant"),
        },
        "design": (
            "ABBA over server instances (baseline, draft, draft, baseline and "
            "the mirrored order), product server flags in both arms, identical "
            "prompts at temperature 0, identical warmup, one port"),
        "baseline": baseline,
        "draft": draft,
        "delta_p50_s": round(draft["p50_s"] - baseline["p50_s"], 4),
        "output_equivalence": outputs,
        "outputs_all_identical": all(
            entry["identical"] for entry in outputs.values()),
        "samples": samples,
    }
    write_json_atomic(OUTPUT, report)
    return report


if __name__ == "__main__":
    result = run()
    print(json.dumps({
        "baseline_p50_s": result["baseline"]["p50_s"],
        "draft_p50_s": result["draft"]["p50_s"],
        "delta_p50_s": result["delta_p50_s"],
        "n_per_arm": result["baseline"]["n"],
        "outputs_all_identical": result["outputs_all_identical"],
    }, indent=1))
