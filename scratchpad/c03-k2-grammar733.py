"""Isolate BAXY's compact GBNF versus its original schema on native K2."""
from pathlib import Path
import copy
import importlib.util
import json
import os
import socket
import subprocess
import sys
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
OUT = base.BASE / "K2_HORIZON_GRAMMAR733"
PRIVATE = base.PRIVATE.parent / "C03-k2-grammar733-private"


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
    planned = []
    for language, text in [("es", "Dime la hora."), ("en", "What time is it?"),
                           ("mixed", "Dime the current time, por favor.")]:
        original = guard_payload(text)
        grammar = llm._compact_structured_grammar(original)
        assert grammar is not None
        compact = copy.deepcopy(original)
        del compact["response_format"]
        compact["grammar"] = grammar
        for representation, payload in [("compact_gbnf", compact), ("original_schema", original)]:
            planned.append({"case": f"{language}-{representation}", "payload": payload})
    # A discriminating backend check: accepted output must be this exact JSON
    # string if custom GBNF actually constrains generation. It dispatches nothing.
    planned.append({"case": "custom_grammar_constraint_probe", "payload": {
        "messages": [{"role": "user", "content": "Say hello in Spanish."}],
        "grammar": 'root ::= "\\\"GBNF_ACTIVE\\\""', "seed": 0}})
    OUT.mkdir()
    PRIVATE.mkdir()
    base.write(PRIVATE / "planned.json", planned)
    source_hash = base.sha(ROOT / "src/baxy_mind/llm.py")
    base.write(OUT / "PREREG.json", {
        "command": command, "reference": "K2_HORIZON_NATIVE699/run-37-q4-high-practical699",
        "model_sha256": reference["model_sha256"], "backend_files": reference["backend_files"],
        "manifest_sha256": reference["manifest_sha256"], "source_sha256": source_hash,
        "driver_sha256": base.sha(Path(__file__)),
        "adapter_sha256": base.sha(ROOT / "scratchpad/c03_k2_native_adapter732.py"),
        "planned_sha256": base.sha(PRIVATE / "planned.json"),
        "method": "Three language pairs from the actual semantic-effect guard: only replace its compact GBNF wire representation with the original identical closed JSON Schema. Same K2 high practical profile732, per-case begin_request19s and original transport retries/deadline. Seventh probe has a deliberately discriminating exact GBNF constraint. No tools dispatched, no product acceptance, no native quality ranking.",
        "criteria": "Clock guards must return external_read/one and a closed object. Preserve failures and latency. Exact-constraint probe must output the JSON string GBNF_ACTIVE if custom GBNF is enforced; any other final disproves enforcement for this path.",
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
                        response = runtime._post(row["payload"])
                        result["response"] = response
                        message = response["choices"][0]["message"]
                        content = message.get("content") or ""
                        try:
                            value = json.loads(content)
                        except json.JSONDecodeError:
                            value = None
                        result["contract_met"] = (value == "GBNF_ACTIVE" if row["case"] ==
                            "custom_grammar_constraint_probe" else value == {
                                "request_type": "external_read", "effect_count": "one"})
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
