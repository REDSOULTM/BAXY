"""Preflight native K2 adaptation, then exercise three actual BAXY wire formats."""
from __future__ import annotations

import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
from unittest.mock import patch
import urllib.error
import urllib.request

import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT), str(ROOT / "scratchpad")]
from baxy_mind import llm
from c03_k2_native_adapter732 import PROFILE, adapt_payload, install
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler

BASE = ROOT / "artifacts/comprobaciones/C03"
OUT = BASE / "K2_HORIZON_CONTRACT732"
PRIVATE = Path(os.environ["LOCALAPPDATA"]) / "BAXY/C03-k2-contract732-private"
MANIFEST = Path(os.environ["LOCALAPPDATA"]) / "BAXYRuntime/mind-runtime-v1.json"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def preflight(panel, model, endpoint):
    for row in panel:
        payload = row["payload"]
        before = copy.deepcopy(payload)
        wire = adapt_payload(payload)
        assert payload == before and wire["messages"] == payload["messages"]
        allowed = {*PROFILE, "seed", "chat_template_kwargs"}
        assert {k: v for k, v in wire.items() if k not in allowed} == {
            k: v for k, v in payload.items() if k not in allowed}
        assert wire["seed"] == payload.get("seed", 0)
        assert wire["chat_template_kwargs"].get("enable_thinking") is None
    with tempfile.TemporaryDirectory(prefix="baxy-k2-adapter732-") as directory:
        private = Path(directory)
        runtime = object.__new__(llm.LlmRuntime)
        runtime._gguf, runtime._endpoint = model, endpoint
        runtime._cpu_prose_adapter = None
        runtime._http_connection_pool = object()
        runtime._ensure_started = lambda: None
        runtime._effective_request_timeout = lambda requested: min(requested or 19, 19)
        cancel, sentinel, failure = object(), object(), RuntimeError("transport sentinel")
        uninstall = install(private, model, endpoint)
        payload = {"messages": [{"role": "system", "content": "A"},
                                {"role": "system", "content": "B"},
                                {"role": "user", "content": "C"}],
                   "grammar": 'root ::= "{}"', "seed": 1010, "custom": {"value": 3}}
        before = copy.deepcopy(payload)
        calls = []

        def transport(wire, **kwargs):
            calls.append(wire)
            assert kwargs["endpoint_for_attempt"]() == endpoint
            assert kwargs["timeout_for_attempt"]() == 7
            assert kwargs["max_attempts"] == 1 and kwargs["cancellation"] is cancel
            assert kwargs["connection_pool"] is runtime._http_connection_pool
            assert wire["grammar"] == payload["grammar"] and wire["seed"] == 1010
            return {"sentinel": id(sentinel)}

        try:
            with patch.object(llm, "post_chat_completion", transport):
                result = runtime._post(payload, 7, max_attempts=1, cancellation=cancel)
                assert result == {"sentinel": id(sentinel)}
            with patch.object(llm, "post_chat_completion", side_effect=failure):
                try:
                    runtime._post(payload)
                except RuntimeError as error:
                    assert error is failure
                else:
                    raise AssertionError("Exception swallowed")
            assert payload == before and len(calls) == 1
            logs = [json.loads(line) for line in (private / "adapter-http.jsonl").read_text().splitlines()]
            assert [row["stage"] for row in logs] == ["request", "response", "request", "failure"]
        finally:
            uninstall()
    return {"captured_payloads_preserved_outside_profile": len(panel),
            "messages_unchanged": True, "transport_arguments_and_exception_preserved": True,
            "scope": "No model answers or product acceptance from this preflight"}


def main():
    assert not OUT.exists() and not PRIVATE.exists()
    assert not any((p.info["name"] or "").lower() in {
        "llama-server.exe", "baxy.exe", "baxy-core.exe", "testhost.exe"}
        for p in psutil.process_iter(["name"]))
    assert psutil.virtual_memory().available >= 1536 * 2**20
    reference_path = BASE / "K2_HORIZON_NATIVE699/run-37-q4-high-practical699/PREREG.json"
    reference = read(reference_path)
    command = list(reference["command"])
    binary, model = Path(command[0]), Path(command[command.index("-m") + 1])
    assert sha(model) == reference["model_sha256"]
    for name, expected in reference["backend_files"].items():
        assert sha(binary.parent / name) == expected, name
    assert sha(MANIFEST) == reference["manifest_sha256"]
    panel_path = PRIVATE.parent / "C03-k2-comparison696-private/panel.json"
    panel = read(panel_path)
    assert len(panel) == 50
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    endpoint = f"http://127.0.0.1:{port}"
    command[command.index("--port") + 1] = str(port)
    checks = preflight(panel, str(model), endpoint)
    OUT.mkdir()
    PRIVATE.mkdir()
    write(OUT / "PREFLIGHT.json", checks)
    source_hash = sha(ROOT / "src/baxy_mind/llm.py")
    write(OUT / "PREREG.json", {
        "utc": datetime.now(timezone.utc).isoformat(), "command": command,
        "model_sha256": reference["model_sha256"], "backend_files": reference["backend_files"],
        "manifest_sha256": reference["manifest_sha256"], "source_sha256": source_hash,
        "driver_sha256": sha(Path(__file__)),
        "adapter_sha256": sha(ROOT / "scratchpad/c03_k2_native_adapter732.py"),
        "panel_sha256": sha(panel_path), "profile": PROFILE,
        "method": "Technical compatibility only: actual native selector, actual structured turn policy with compact GBNF, and a captured writer with multiple system messages. Native high profile inherited699, no enable_thinking false, no system fusion, 4096 total generation tokens. Preserve schema/grammar/tools, retry seeds, transport, cancellation and original19s GPU HTTP cap. No operation dispatch, UI, voice, survey credit, promotion or quality ranking.",
        "interpretation": "This is a model-adapter bundle preflight, not a causal comparison of all individual sampler changes. Grammar/parser rejection or timeout is an integration failure, not evidence against native model knowledge. No native699/731 quality campaign repeated.",
        "limits": {"gpu_mib": 3800, "free_ram_mib": 768, "http_seconds": 19},
    })
    environment = os.environ.copy()
    environment["PATH"] = "C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA/v13.0/bin;" + environment["PATH"]
    process = None
    gpu = ram = guard_thread = None
    stop, violations = threading.Event(), []
    started = time.monotonic()
    results = []

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
            process = subprocess.Popen(command, cwd=binary.parent, env=environment,
                stdin=subprocess.DEVNULL, stdout=launch, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW)
        write(OUT / "PROCESS.json", {"pid": process.pid, "command": command})
        gpu, ram = ProcessTreeGpuSampler(process.pid), RamSampler(process.pid)
        gpu.start()
        ram.start()
        guard_thread = threading.Thread(target=guard, daemon=True)
        guard_thread.start()
        while time.monotonic() - started < 120:
            assert process.poll() is None, "Server exited before ready"
            try:
                with urllib.request.urlopen(endpoint + "/health", timeout=2) as response:
                    if json.load(response).get("status") == "ok":
                        break
            except (urllib.error.URLError, TimeoutError):
                pass
            time.sleep(.25)
        else:
            raise TimeoutError("Server startup")
        with urllib.request.urlopen(endpoint + "/props", timeout=10) as response:
            write(PRIVATE / "props.json", json.load(response))
        with patch.dict(os.environ, {"BAXY_MIND_LLM_ENDPOINT": endpoint,
            "BAXY_MIND_LLM_GGUF": str(model), "BAXY_MIND_LLAMA_SERVER": str(binary),
            "BAXY_MIND_NGL": "99", "BAXY_MIND_LLM_REQUEST_TIMEOUT": "19"}):
            runtime = llm.LlmRuntime()
            assert runtime._request_timeout == 19 and not runtime._parallel_turn_verification
            uninstall = install(PRIVATE, str(model), endpoint)
            writer = next(row["payload"] for row in panel if row["id"] == "writer521-8")
            policy = llm._build_turn_policy_payload("Dime la hora.", ["system.time"],
                                                   "system.time: Lee la hora local verificada.", [])
            cases = [
                ("native_tool_selector", lambda: runtime._post_native_tool_selection(
                    "Dime la hora.", ["system.time"], {"system.time": {
                        "description": "Lee la hora local verificada."}}, [])),
                ("structured_turn_policy", lambda: runtime._post_schema_object(policy, "turn policy")),
                ("multiple_system_writer", lambda: runtime._post(writer)),
            ]
            try:
                for name, invoke in cases:
                    before = time.monotonic()
                    row = {"case": name}
                    try:
                        row["result"] = invoke()
                    except Exception as error:
                        row.update(error_type=type(error).__name__, error=str(error))
                    row["seconds"] = time.monotonic() - before
                    results.append(row)
                    write(PRIVATE / "results.json", results)
                    print(json.dumps({k: v for k, v in row.items() if k != "result"}), flush=True)
                    assert not violations
            finally:
                uninstall()
    finally:
        stop.set()
        if process is not None:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=20)
        if guard_thread:
            guard_thread.join(timeout=2)
        if gpu:
            gpu.stop()
        if ram:
            ram.stop()
        write(OUT / "RESULT.json", {
            "cases": [{k: v for k, v in row.items() if k != "result"} for row in results],
            "gpu_peak_mib": gpu.peak_mib if gpu else None,
            "ram_peak_mib": ram.peak_mib if ram else None,
            "seconds": time.monotonic() - started, "violations": violations,
            "manifest_unchanged": sha(MANIFEST) == reference["manifest_sha256"],
            "source_unchanged": sha(ROOT / "src/baxy_mind/llm.py") == source_hash,
            "scope": "Server resource peak only; three technical formats, no product acceptance",
        })


if __name__ == "__main__":
    main()
