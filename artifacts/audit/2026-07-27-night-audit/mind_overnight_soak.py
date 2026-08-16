"""Long-running, effect-free soak of BAXY's live natural-language model."""

from __future__ import annotations

import argparse
import json
import os
import queue
import shutil
import statistics
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psutil


CASES: tuple[dict[str, Any], ...] = (
    {"text": "Hola", "kind": "conversation"},
    {
        "text": "¿Qué hora es?",
        "kind": "action",
        "operation": "system.time",
    },
    {
        "text": "¿Cómo está el equipo?",
        "kind": "action",
        "operation": "system.status",
    },
    {
        "text": "Abre la calculadora",
        "kind": "action",
        "operation": "app.open",
    },
    {"text": "Abre Opera", "kind": "action", "operation": "app.open"},
    {
        "text": "¿En qué volumen está el computador?",
        "kind": "action",
        "operation": "audio.status",
    },
    {
        "text": "Busca OpenAI en la web",
        "kind": "action",
        "operation": "web.search",
    },
    {"text": "Lista mis notas", "kind": "action", "operation": "note.list"},
    {
        "text": "Lista mis tareas pendientes",
        "kind": "action",
        "operation": "task.list",
    },
    {
        "text": "Abre Opera, navega a https://example.com/ y lee la página",
        "kind": "plan",
        "operations": ["browser.navigate.named", "browser.page.read"],
    },
    {
        "text": "Haz una captura de pantalla y luego léela con OCR",
        "kind": "plan",
        "operations": ["capture.screenshot", "ocr.read"],
    },
    {
        "text": "Pon el volumen al 8 por ciento y luego dime en cuánto quedó",
        "kind": "plan",
        "operations": ["audio.volume", "audio.status"],
    },
    {
        "text": "Abre Spotify, reproduce exactamente Beat It y después pausa",
        "kind": "plan",
        "operations": ["media.play.exact", "media.control"],
    },
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def read_line(process: subprocess.Popen[str], timeout: float) -> str:
    values: queue.Queue[str] = queue.Queue(maxsize=1)
    threading.Thread(
        target=lambda: values.put(process.stdout.readline()), daemon=True
    ).start()
    try:
        line = values.get(timeout=timeout)
    except queue.Empty as exception:
        raise TimeoutError("mind response timed out") from exception
    if not line:
        stderr = process.stderr.read()[-1024:] if process.poll() is not None else ""
        raise RuntimeError("mind closed before response:" + stderr)
    return line


def call(
    process: subprocess.Popen[str],
    message: dict[str, Any],
    timeout: float = 30,
) -> dict[str, Any]:
    process.stdin.write(
        json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n"
    )
    process.stdin.flush()
    return json.loads(read_line(process, timeout))


def write_checkpoint(output: Path, report: dict[str, Any]) -> None:
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output)


def process_tree_sample(process: subprocess.Popen[str]) -> dict[str, Any]:
    try:
        parent = psutil.Process(process.pid)
        tree = [parent, *parent.children(recursive=True)]
    except psutil.Error:
        tree = []
    rss = 0
    private = 0
    handles = 0
    threads = 0
    names: dict[str, int] = {}
    for item in tree:
        try:
            memory = item.memory_info()
            rss += memory.rss
            private += getattr(memory, "private", 0)
            handles += item.num_handles()
            threads += item.num_threads()
            name = item.name()
            names[name] = names.get(name, 0) + 1
        except psutil.Error:
            continue
    return {
        "atUtc": utc_now().isoformat(),
        "processCount": len(tree),
        "processNames": names,
        "rssBytes": rss,
        "privateBytes": private,
        "handles": handles,
        "threads": threads,
    }


def score(
    case: dict[str, Any],
    decision: dict[str, Any],
    plan: dict[str, Any] | None,
) -> tuple[bool, list[str]]:
    problems: list[str] = []
    if decision.get("kind") != case["kind"]:
        problems.append(
            f"kind:{decision.get('kind')}!=expected:{case['kind']}"
        )
    if case["kind"] == "action" and decision.get("operation") != case["operation"]:
        problems.append(
            f"operation:{decision.get('operation')}!=expected:{case['operation']}"
        )
    if case["kind"] == "plan":
        observed = [
            step.get("operation")
            for step in (plan or {}).get("steps", [])
            if isinstance(step, dict)
        ]
        if observed != case["operations"]:
            problems.append(
                "plan:"
                + json.dumps(observed, ensure_ascii=False)
                + "!=expected:"
                + json.dumps(case["operations"], ensure_ascii=False)
            )
    return not problems, problems


def stop_mind(
    process: subprocess.Popen[str],
) -> tuple[int | None, str, list[str]]:
    descendant_names: list[str] = []
    try:
        parent = psutil.Process(process.pid)
        descendants = parent.children(recursive=True)
    except psutil.Error:
        descendants = []
    if process.poll() is None:
        try:
            call(process, {"type": "shutdown", "id": str(uuid.uuid4())}, 10)
        except Exception:
            pass
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    _, alive = psutil.wait_procs(descendants, timeout=10)
    for child in alive:
        try:
            descendant_names.append(child.name())
            child.terminate()
        except psutil.Error:
            pass
    psutil.wait_procs(alive, timeout=5)
    stderr = process.stderr.read() if process.stderr is not None else ""
    return process.returncode, stderr[-2048:], sorted(descendant_names)


def start_mind(
    environment: dict[str, str],
    capabilities: list[dict[str, Any]],
) -> tuple[subprocess.Popen[str], dict[str, Any], dict[str, Any]]:
    process = subprocess.Popen(
        [sys.executable, "-X", "utf8", "-m", "baxy_mind"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=environment,
        cwd=Path.cwd(),
    )
    hello = json.loads(read_line(process, 20))
    ready = call(
        process,
        {
            "type": "catalog.configure",
            "id": str(uuid.uuid4()),
            "capabilities": capabilities,
        },
        20,
    )
    time.sleep(8)
    return process, hello, ready


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--deadline", required=True)
    parser.add_argument("--interval-seconds", type=float, default=60)
    parser.add_argument("--segment-seconds", type=float, default=7200)
    args = parser.parse_args()
    deadline = datetime.fromisoformat(args.deadline)
    if deadline.tzinfo is None:
        raise SystemExit("--deadline must include an offset")
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    data_root = (
        Path(os.environ["LOCALAPPDATA"])
        / "BAXY"
        / ("audit-mind-soak-" + uuid.uuid4().hex)
    )
    data_root.mkdir(parents=True, exist_ok=False)
    manifest = json.loads(
        (
            Path(os.environ["LOCALAPPDATA"])
            / "BAXYRuntime"
            / "mind-runtime-v1.json"
        ).read_text(encoding="utf-8")
    )
    environment = {
        **os.environ,
        "PYTHONPATH": str(Path.cwd() / "src"),
        "BAXY_DATA_DIR": str(data_root),
        "BAXY_MIND_LLM_GGUF": str(manifest["gguf"]),
        "BAXY_MIND_LLAMA_SERVER": str(manifest["llama_server"]),
        "BAXY_MIND_LLM_REQUEST_TIMEOUT": "8",
        "HF_HUB_OFFLINE": "1",
    }
    environment.pop("BAXY_MIND_LLM_ENDPOINT", None)

    core = subprocess.Popen(
        [str(args.core.resolve(strict=True))],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=environment,
    )
    core_hello = json.loads(read_line(core, 10))
    capabilities = [
        {
            key: item[key]
            for key in ("name", "description", "argumentsSchema", "risk")
        }
        for item in core_hello["capabilities"]
    ]
    core.stdin.close()
    core.wait(timeout=10)

    report: dict[str, Any] = {
        "schema": "baxy.audit.mind-overnight-soak.v1",
        "running": True,
        "startedUtc": utc_now().isoformat(),
        "checkpointUtc": utc_now().isoformat(),
        "deadline": args.deadline,
        "coreVersion": core_hello.get("coreVersion"),
        "catalogCount": len(capabilities),
        "intervalSeconds": args.interval_seconds,
        "calls": [],
        "aggregate": {
            "decisions": 0,
            "matched": 0,
            "mismatched": 0,
            "protocolAnomalies": 0,
        },
        "segments": [],
        "resourceSamples": [],
        "finalError": None,
    }
    write_checkpoint(output, report)
    history = [
        {
            "role": "assistant",
            "content": "Hola. Estoy lista para ayudarte con este equipo.",
        }
    ]
    mind: subprocess.Popen[str] | None = None
    segment_started = 0.0
    call_index = 0
    final_error: str | None = None

    try:
        while utc_now() < deadline.astimezone(timezone.utc):
            if mind is None or time.monotonic() - segment_started >= args.segment_seconds:
                if mind is not None:
                    exit_code, stderr, remaining = stop_mind(mind)
                    report["segments"][-1].update(
                        {
                            "stoppedUtc": utc_now().isoformat(),
                            "exitCode": exit_code,
                            "stderrTail": stderr,
                            "descendantsAfterShutdown": remaining,
                        }
                    )
                mind, hello, ready = start_mind(environment, capabilities)
                segment_started = time.monotonic()
                report["segments"].append(
                    {
                        "index": len(report["segments"]) + 1,
                        "pid": mind.pid,
                        "startedUtc": utc_now().isoformat(),
                        "hello": hello,
                        "catalogReady": ready,
                        "exitCode": None,
                        "stderrTail": "",
                    }
                )

            case = CASES[call_index % len(CASES)]
            call_index += 1
            started = time.perf_counter()
            row: dict[str, Any] = {
                "index": call_index,
                "atUtc": utc_now().isoformat(),
                "segment": len(report["segments"]),
                "caseIndex": (call_index - 1) % len(CASES),
                "text": case["text"],
                "expected": case,
            }
            try:
                decision = call(
                    mind,
                    {
                        "type": "turn.decide",
                        "id": f"turn-{call_index}",
                        "text": case["text"],
                        "history": history,
                    },
                    30,
                )
                plan = None
                if decision.get("kind") == "plan":
                    plan = call(
                        mind,
                        {
                            "type": "plan",
                            "id": f"plan-{call_index}",
                            "text": case["text"],
                            "history": history,
                        },
                        30,
                    )
                matched, problems = score(case, decision, plan)
                row.update(
                    {
                        "decision": decision,
                        "plan": plan,
                        "matched": matched,
                        "problems": problems,
                    }
                )
                report["aggregate"]["decisions"] += 1
                report["aggregate"]["matched" if matched else "mismatched"] += 1
            except Exception as exception:
                row.update(
                    {
                        "matched": False,
                        "problems": [
                            f"{type(exception).__name__}:{exception}"
                        ],
                    }
                )
                report["aggregate"]["protocolAnomalies"] += 1
                exit_code, stderr, remaining = stop_mind(mind)
                report["segments"][-1].update(
                    {
                        "stoppedUtc": utc_now().isoformat(),
                        "exitCode": exit_code,
                        "stderrTail": stderr,
                        "descendantsAfterShutdown": remaining,
                        "restartReason": row["problems"][0],
                    }
                )
                mind = None
            row["elapsedSeconds"] = time.perf_counter() - started
            report["calls"].append(row)
            if mind is not None:
                sample = process_tree_sample(mind)
                sample["segment"] = len(report["segments"])
                report["resourceSamples"].append(sample)
            report["checkpointUtc"] = utc_now().isoformat()
            write_checkpoint(output, report)

            remaining_seconds = (
                deadline.astimezone(timezone.utc) - utc_now()
            ).total_seconds()
            wait_seconds = min(
                max(0.0, args.interval_seconds - row["elapsedSeconds"]),
                max(0.0, remaining_seconds),
            )
            if wait_seconds > 0:
                time.sleep(wait_seconds)
    except Exception as exception:
        final_error = f"{type(exception).__name__}:{exception}"
    finally:
        if mind is not None:
            exit_code, stderr, remaining = stop_mind(mind)
            report["segments"][-1].update(
                {
                    "stoppedUtc": utc_now().isoformat(),
                    "exitCode": exit_code,
                    "stderrTail": stderr,
                    "descendantsAfterShutdown": remaining,
                }
            )
        shutil.rmtree(data_root, ignore_errors=True)

    latencies = [
        float(row["elapsedSeconds"])
        for row in report["calls"]
        if "elapsedSeconds" in row
    ]
    report["running"] = False
    report["checkpointUtc"] = utc_now().isoformat()
    report["finalError"] = final_error
    report["latencySeconds"] = (
        {
            "minimum": min(latencies),
            "median": statistics.median(latencies),
            "maximum": max(latencies),
            "mean": statistics.fmean(latencies),
        }
        if latencies
        else {}
    )
    write_checkpoint(output, report)
    print(
        json.dumps(
            {
                "calls": len(report["calls"]),
                "aggregate": report["aggregate"],
                "segments": len(report["segments"]),
                "latencySeconds": report["latencySeconds"],
                "finalError": final_error,
            },
            ensure_ascii=False,
        )
    )
    return 0 if final_error is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
