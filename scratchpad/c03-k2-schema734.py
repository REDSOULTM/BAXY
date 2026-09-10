"""Probe actual guard with native K2 and an explicit, unchanged JSON contract."""
from pathlib import Path
import copy
import importlib.util
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from unittest.mock import patch
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("contract732", ROOT / "scratchpad/c03-k2-contract-probe732.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
llm = base.llm
from c03_k2_native_adapter734 import install
base.install = install
OUT = base.BASE / "K2_HORIZON_SCHEMA734"
PRIVATE = base.PRIVATE.parent / "C03-k2-schema734-private"


class Captured(Exception):
    pass


def guard_payload(text):
    runtime = object.__new__(llm.LlmRuntime)
    runtime._validated_classifier_reuse_get = lambda *_: None
    captured = []

    def capture(payload, label):
        captured.append(copy.deepcopy(payload))
        raise Captured

    runtime._post_schema_object = capture
    try:
        runtime._verify_semantic_effect_shape(text)
    except Captured:
        pass
    assert len(captured) == 1
    return captured[0]


def preflight(model, endpoint):
    original = guard_payload("Dime la hora.")
    original["seed"] = 1010
    before = copy.deepcopy(original)
    captured = []
    runtime = object.__new__(llm.LlmRuntime)
    runtime._gguf, runtime._endpoint = str(model), endpoint
    runtime._cpu_prose_adapter = None
    runtime._http_connection_pool = None
    runtime._effective_request_timeout = lambda _: 19

    def capture(wire, **kwargs):
        captured.append(wire)
        raise Captured

    with tempfile.TemporaryDirectory(prefix="baxy-k2-schema734-") as directory:
        uninstall = install(Path(directory), str(model), endpoint)
        try:
            with patch.object(llm, "post_chat_completion", capture):
                try:
                    runtime._post_schema_object(original, "preflight")
                except Captured:
                    pass
        finally:
            uninstall()
    assert len(captured) == 1 and original == before
    wire = captured[0]
    assert "grammar" not in wire and wire["response_format"] == original["response_format"]
    assert wire["messages"][0] == original["messages"][0]
    assert wire["messages"][2:] == original["messages"][1:]
    schema_text = wire["messages"][1]["content"].split("JSON Schema: ", 1)[1]
    assert json.loads(schema_text) == original["response_format"]["json_schema"]["schema"]
    assert wire["seed"] == 1010 and wire["chat_template_kwargs"] == {"reasoning_effort": "high"}
    return {"original_schema_restored": True, "schema_message_is_exact_contract": True,
            "existing_messages_unchanged": True, "retry_seed_preserved": True,
            "caller_payload_unchanged": True, "scope": "Transport sentinel, no model output"}


def main():
    assert not OUT.exists() and not PRIVATE.exists()
    assert not any((p.info["name"] or "").lower() in {
        "llama-server.exe", "baxy.exe", "baxy-core.exe", "testhost.exe"}
        for p in base.psutil.process_iter(["name"]))
    reference = base.read(base.BASE / "K2_HORIZON_NATIVE699/run-37-q4-high-practical699/PREREG.json")
    command = list(reference["command"])
    binary, model = Path(command[0]), Path(command[command.index("-m") + 1])
    assert base.sha(model) == reference["model_sha256"]
    assert base.sha(base.MANIFEST) == reference["manifest_sha256"]
    for name, expected in reference["backend_files"].items():
        assert base.sha(binary.parent / name) == expected
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    endpoint = f"http://127.0.0.1:{port}"
    command[command.index("--port") + 1] = str(port)
    checks = preflight(model, endpoint)
    planned = []
    for language, text in [("es", "Dime la hora."), ("en", "What time is it?"),
                           ("mixed", "Dime the current time, por favor.")]:
        original = guard_payload(text)
        planned.append({"case": f"{language}-explicit_schema", "payload": original,
                        "text": text})
    OUT.mkdir()
    PRIVATE.mkdir()
    base.write(OUT / "PREFLIGHT.json", checks)
    base.write(PRIVATE / "planned.json", planned)
    source_hash = base.sha(ROOT / "src/baxy_mind/llm.py")
    base.write(OUT / "PREREG.json", {
        "command": command, "reference": "K2_HORIZON_NATIVE699/run-37-q4-high-practical699",
        "model_sha256": reference["model_sha256"], "backend_files": reference["backend_files"],
        "manifest_sha256": reference["manifest_sha256"], "source_sha256": source_hash,
        "driver_sha256": base.sha(Path(__file__)),
        "adapter_sha256": base.sha(ROOT / "scratchpad/c03_k2_native_adapter734.py"),
        "native_adapter_sha256": base.sha(ROOT / "scratchpad/c03_k2_native_adapter732.py"),
        "planned_sha256": base.sha(PRIVATE / "planned.json"),
        "method": "Actual semantic guard in ES/EN/mix. Same native K2 high practical profile and19s total budget as733. Restore original closed schema from the real compact-grammar conversion, retain every validator/retry/seed, and add only a serialization instruction containing that exact schema. Native reasoning is preserved. Compare descriptively with733 original-schema controls; no model promotion/product acceptance.",
        "criteria": "Actual guard must yield complete/one for each current-clock read; raw final must independently contain external_read/one. No relaxed deadline or reasoning-as-final recovery.",
        "limits": {"gpu_mib": 3800, "free_ram_mib": 768, "total_request_seconds": 19},
    })
    env = os.environ.copy()
    env["PATH"] = "C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA/v13.0/bin;" + env["PATH"]
    stop, violations, results = threading.Event(), [], []
    started = time.monotonic()
    with (PRIVATE / "launch.log").open("w", encoding="utf-8") as launch:
        process = subprocess.Popen(command, env=env, cwd=binary.parent,
            stdin=subprocess.DEVNULL, stdout=launch, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW)
    base.write(OUT / "PROCESS.json", {"pid": process.pid, "command": command})
    gpu, ram = base.ProcessTreeGpuSampler(process.pid), base.RamSampler(process.pid)
    gpu.start()
    ram.start()

    def guard():
        while not stop.wait(.25):
            if (gpu.peak_mib or 0) > 3800:
                violations.append("gpu_limit")
            if base.psutil.virtual_memory().available < 768 * 2**20:
                violations.append("free_ram_limit")
            if violations and process.poll() is None:
                process.terminate()
                return

    watcher = threading.Thread(target=guard, daemon=True)
    watcher.start()
    try:
        while time.monotonic() - started < 120:
            assert process.poll() is None
            try:
                with urllib.request.urlopen(endpoint + "/health", timeout=2) as response:
                    if json.load(response).get("status") == "ok":
                        break
            except (urllib.error.URLError, TimeoutError):
                pass
            time.sleep(.25)
        else:
            raise TimeoutError("Server startup")
        with patch.dict(os.environ, {"BAXY_MIND_LLM_ENDPOINT": endpoint,
            "BAXY_MIND_LLM_GGUF": str(model), "BAXY_MIND_LLAMA_SERVER": str(binary),
            "BAXY_MIND_NGL": "99", "BAXY_MIND_LLM_REQUEST_TIMEOUT": "19"}):
            runtime = llm.LlmRuntime()
            uninstall = base.install(PRIVATE, str(model), endpoint)
            try:
                for row in planned:
                    runtime.begin_request(19, identity=row["case"])
                    before = time.monotonic()
                    result = {"case": row["case"]}
                    try:
                        value = runtime._verify_semantic_effect_shape(row["text"])
                        result["guard_result"] = value
                        result["contract_met"] = value == ("complete", "one")
                    except Exception as error:
                        result.update(error_type=type(error).__name__, error=str(error), contract_met=False)
                    result["seconds"] = time.monotonic() - before
                    results.append(result)
                    base.write(PRIVATE / "results.json", results)
                    print(json.dumps({k: v for k, v in result.items() if k != "response"}), flush=True)
                    assert not violations
            finally:
                uninstall()
    finally:
        stop.set()
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=20)
        watcher.join(timeout=2)
        gpu.stop()
        ram.stop()
        base.write(OUT / "RESULT.json", {
            "cases": [{k: v for k, v in row.items() if k != "response"} for row in results],
            "gpu_peak_mib": gpu.peak_mib, "ram_peak_mib": ram.peak_mib,
            "seconds": time.monotonic() - started, "violations": violations,
            "manifest_unchanged": base.sha(base.MANIFEST) == reference["manifest_sha256"],
            "source_unchanged": base.sha(ROOT / "src/baxy_mind/llm.py") == source_hash,
        })


if __name__ == "__main__":
    main()
