"""Measure the single K2 thinking override imposed by BAXY; no product adoption."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from unittest.mock import patch
import urllib.error
import urllib.request

import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler
from baxy_mind import llm

BASE = ROOT / "artifacts/comprobaciones/C03"
OUT = BASE / "K2_HORIZON_ADAPTER731"
PRIVATE = Path(os.environ["LOCALAPPDATA"]) / "BAXY/C03-k2-adapter731-private"
REFERENCE = BASE / "K2_HORIZON_NATIVE699/run-37-q4-high-practical699"
REFERENCE_PRIVATE = Path(os.environ["LOCALAPPDATA"]) / "BAXY/C03-k2-native699-37-q4-high-practical699-private"
MANIFEST = Path(os.environ["LOCALAPPDATA"]) / "BAXYRuntime/mind-runtime-v1.json"


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append(path: Path, value) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False) + "\n")


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


class TransportCaptured(Exception):
    pass


def capture_actual_post(payload: dict, gguf: str) -> dict:
    """Exercise only the real pre-transport method; never manufacture a model answer."""
    runtime = object.__new__(llm.LlmRuntime)
    runtime._gguf = gguf
    runtime._cpu_prose_adapter = None
    runtime._http_connection_pool = None
    captured = []

    def capture(value, **_kwargs):
        captured.append(copy.deepcopy(value))
        raise TransportCaptured

    original = copy.deepcopy(payload)
    with patch.object(llm, "post_chat_completion", capture):
        try:
            runtime._post(payload)
        except TransportCaptured:
            pass
    assert payload == original and len(captured) == 1
    return captured[0]


def capture_actual_selector(gguf: str) -> dict:
    runtime = object.__new__(llm.LlmRuntime)
    runtime._gguf = gguf
    runtime._cpu_prose_adapter = None
    runtime._http_connection_pool = None
    captured = []

    def capture(value, **_kwargs):
        captured.append(copy.deepcopy(value))
        raise TransportCaptured

    with patch.object(llm, "post_chat_completion", capture):
        try:
            runtime._post_native_tool_selection(
                "What time is it?", ["system.time"],
                {"system.time": {"description": "Reads the verified local time."}}, [],
            )
        except TransportCaptured:
            pass
    assert len(captured) == 1
    return captured[0]


def main() -> None:
    assert not OUT.exists() and not PRIVATE.exists(), "Never overwrite a prior attempt"
    assert not any(p.info["name"].lower() in {"llama-server.exe", "baxy.exe", "baxy-core.exe", "testhost.exe"}
                   for p in psutil.process_iter(["name"]) if p.info["name"])
    assert psutil.virtual_memory().available >= 1536 * 2**20
    reference = read(REFERENCE / "PREREG.json")
    command = list(reference["command"])
    binary = Path(command[0])
    model = Path(command[command.index("-m") + 1])
    assert sha(model) == reference["model_sha256"]
    assert sha(MANIFEST) == reference["manifest_sha256"]
    for name, expected in reference["backend_files"].items():
        assert sha(binary.parent / name) == expected, name
    with (REFERENCE_PRIVATE / "requests.jsonl").open(encoding="utf-8") as stream:
        reference_requests = [json.loads(line) for line in stream]
    assert len(reference_requests) == 50
    assert [row["case"] for row in reference_requests] == reference["cases"]
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    command[command.index("--port") + 1] = str(port)
    normalized = list(command)
    normalized[normalized.index("--port") + 1] = reference["command"][reference["command"].index("--port") + 1]
    assert normalized == reference["command"]
    OUT.mkdir()
    PRIVATE.mkdir()
    actual_selector = capture_actual_selector(str(model))
    assert actual_selector["chat_template_kwargs"]["enable_thinking"] is False
    write(PRIVATE / "actual-selector-transport-capture.json", actual_selector)
    planned = []
    for row in reference_requests:
        payload = copy.deepcopy(row["payload"])
        assert payload["chat_template_kwargs"] == {"reasoning_effort": "high"}
        assert payload["max_tokens"] == 4096 and payload["temperature"] == 1.0
        assert all(m["role"] in {"user", "assistant"} for m in payload["messages"])
        assert not any(k in payload for k in ("tools", "response_format"))
        assert capture_actual_post(payload, str(model)) == payload
        payload["chat_template_kwargs"]["enable_thinking"] = False
        before = copy.deepcopy(payload)
        del before["chat_template_kwargs"]["enable_thinking"]
        assert before == row["payload"]
        planned.append({"case": row["case"], "payload": payload})
    write(PRIVATE / "planned-requests.json", planned)
    source_hash = sha(ROOT / "src/baxy_mind/llm.py")
    plan = {
        "utc": datetime.now(timezone.utc).isoformat(), "command": command,
        "reference": str(REFERENCE.relative_to(ROOT)), "reference_prereg_sha256": sha(REFERENCE / "PREREG.json"),
        "reference_requests_sha256": sha(REFERENCE_PRIVATE / "requests.jsonl"),
        "planned_requests_sha256": sha(PRIVATE / "planned-requests.json"),
        "driver_sha256": sha(Path(__file__)), "llm_source_sha256": source_hash,
        "actual_selector_capture_sha256": sha(PRIVATE / "actual-selector-transport-capture.json"),
        "model_sha256": reference["model_sha256"], "backend_files": reference["backend_files"],
        "manifest_sha256": reference["manifest_sha256"], "cases": reference["cases"],
        "hypothesis": "The actual BAXY selector override enable_thinking=False changes K2 generation prefix and may change quality/latency. Isolate only this override; the current product startup flags, sampler, token cap, identity, tools, validators and retries are NOT added.",
        "method": "Same complete50 synthetic native699 tasks, order, seed, weights, backend, sampler,8192context/4096output and native high server command; only add chat_template_kwargs.enable_thinking=False. Historical reference control, no randomized replication. /apply-template verifies the actual prefixes before any generation. _post is captured with a sentinel at transport: all50 native bodies must remain unchanged and caller input immutable; this transport check is not model output.",
        "scoring": "Use the unchanged native699 case criteria; read complete final outputs. Preserve every error, missing final and length cutoff. Do not score a correct introduction followed by a material falsehood as success. Adjudicate before joining historical verdicts. No survey/product/voice credit.",
        "limits": {"gpu_mib": 3800, "minimum_free_ram_mib": 768, "request_seconds": 900},
        "scope": "Practical profile causal diagnostic; disabling thinking is NOT IFM recommended evaluation and cannot reject/promote the model. This is not complete BAXY integration or BF16 backend parity.",
    }
    write(OUT / "PREREG.json", plan)
    print(json.dumps({"stage": "preregistered", "cases": 50, "only_change": "enable_thinking=False", "post_unchanged": 50}), flush=True)
    environment = os.environ.copy()
    environment["PATH"] = "C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA/v13.0/bin;" + environment["PATH"]
    process = None
    gpu = ram = guard_thread = None
    stop = threading.Event()
    violations = []
    started = time.monotonic()
    url = f"http://127.0.0.1:{port}"

    def post_json(endpoint, body):
        request = urllib.request.Request(url + endpoint, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)

    def guard():
        while not stop.wait(.25):
            if (gpu.peak_mib or 0) > 3800:
                violations.append("gpu_limit")
            if psutil.virtual_memory().available < 768 * 2**20:
                violations.append("free_ram_limit")
            if violations:
                if process.poll() is None:
                    process.terminate()
                return

    try:
        with (PRIVATE / "launch.log").open("w", encoding="utf-8") as launch:
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=launch, stderr=subprocess.STDOUT,
                                       cwd=binary.parent, env=environment, creationflags=subprocess.CREATE_NO_WINDOW)
        write(OUT / "PROCESS.json", {"pid": process.pid, "command": command})
        gpu, ram = ProcessTreeGpuSampler(process.pid), RamSampler(process.pid)
        gpu.start()
        ram.start()
        guard_thread = threading.Thread(target=guard, daemon=True)
        guard_thread.start()
        while time.monotonic() - started < 120:
            if process.poll() is not None:
                raise RuntimeError(f"backend exited before readiness:{process.returncode}")
            try:
                with urllib.request.urlopen(url + "/health", timeout=2) as response:
                    if json.load(response).get("status") == "ok":
                        break
            except (urllib.error.URLError, TimeoutError):
                pass
            time.sleep(.25)
        else:
            raise TimeoutError("backend startup")
        with urllib.request.urlopen(url + "/props", timeout=10) as response:
            write(PRIVATE / "props.json", json.load(response))
        for original, changed in zip(reference_requests, planned, strict=True):
            first = post_json("/apply-template", original["payload"])["prompt"]
            second = post_json("/apply-template", changed["payload"])["prompt"]
            assert first.rstrip().endswith("<ifm|think>")
            assert second.rstrip().endswith("<ifm|think>\n</ifm|think>")
            expected = first.rstrip() + "\n</ifm|think>\n"
            assert second == expected, "Unexpected template transformation outside thinking suffix"
            append(PRIVATE / "rendered-prompts.jsonl", {"case": original["case"], "native": first, "disabled": second})
            append(OUT / "TEMPLATE_PARITY.jsonl", {"case": original["case"], "only_added_thinking_close": True,
                                                  "native_sha256": digest(first), "disabled_sha256": digest(second)})
        print(json.dumps({"stage": "template_verified", "pairs": 50, "only_added_thinking_close": True}), flush=True)
        for row in planned:
            assert sha(ROOT / "src/baxy_mind/llm.py") == source_hash
            payload = row["payload"]
            append(PRIVATE / "requests.jsonl", row)
            before = time.monotonic()
            record = {"case": row["case"], "content": "", "reasoning_content": "", "tool_deltas": []}
            request = urllib.request.Request(url + "/v1/chat/completions", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(request, timeout=900) as response:
                    for line in response:
                        if time.monotonic() - before > 900:
                            record["error"] = "request_wall_clock_deadline_900_seconds"
                            break
                        if not line.startswith(b"data: "):
                            continue
                        data = line[6:].strip()
                        if data == b"[DONE]":
                            break
                        event = json.loads(data)
                        append(PRIVATE / "stream.jsonl", {"case": row["case"], "seconds": time.monotonic() - before, "event": event})
                        if event.get("error"):
                            record["error"] = event["error"]
                        if event.get("usage"):
                            record["usage"] = event["usage"]
                        for choice in event.get("choices", []):
                            delta = choice.get("delta", {})
                            if any(delta.get(k) for k in ("content", "reasoning_content", "tool_calls")):
                                record.setdefault("first_token_seconds", time.monotonic() - before)
                            if delta.get("content"):
                                record.setdefault("first_content_seconds", time.monotonic() - before)
                            for key in ("content", "reasoning_content"):
                                record[key] += delta.get(key) or ""
                            if delta.get("tool_calls"):
                                record["tool_deltas"].extend(delta["tool_calls"])
                            if choice.get("finish_reason"):
                                record["finish_reason"] = choice["finish_reason"]
            except Exception as error:
                record["error"] = str(error)
                if isinstance(error, urllib.error.HTTPError):
                    record["body"] = error.read().decode(errors="replace")
            record["seconds"] = time.monotonic() - before
            append(PRIVATE / "results.jsonl", record)
            print(json.dumps({"case": row["case"], "seconds": record["seconds"], "finish_reason": record.get("finish_reason"), "error": record.get("error"), "content_characters": len(record["content"])}), flush=True)
            assert not violations
    finally:
        stop.set()
        if process is not None:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=20)
        if guard_thread is not None:
            guard_thread.join(timeout=2)
        if gpu is not None:
            gpu.stop()
        if ram is not None:
            ram.stop()
        write(OUT / "RESOURCES.json", {"gpu_peak_mib": gpu.peak_mib if gpu else None,
                                      "ram_peak_mib": ram.peak_mib if ram else None,
                                      "seconds": time.monotonic() - started, "violations": violations,
                                      "manifest_unchanged": sha(MANIFEST) == reference["manifest_sha256"],
                                      "source_unchanged": sha(ROOT / "src/baxy_mind/llm.py") == source_hash,
                                      "backend_exit": process.returncode if process else None})


if __name__ == "__main__":
    main()
