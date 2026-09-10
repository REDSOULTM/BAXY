"""Run the same complete status category through actual BAXY with native profiles."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler

BASE = ROOT / "artifacts/comprobaciones/C03"
LOCAL = Path(os.environ["LOCALAPPDATA"])
MANIFEST = LOCAL / "BAXYRuntime/mind-runtime-v1.json"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def source_snapshot():
    paths = subprocess.check_output(["git", "ls-files", "--cached", "--others",
        "--exclude-standard", "--", "src", "main.py"], cwd=ROOT, text=True).splitlines()
    return {name: sha(ROOT / name) for name in sorted(set(paths)) if (ROOT / name).is_file()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("model", choices=["k2", "qwen"])
    args = parser.parse_args()
    kind = args.model
    campaign = BASE / "NATIVE_PRODUCT736"
    out = campaign / kind
    private = LOCAL / f"BAXY/C03-native-product736-{kind}-private"
    profile_dir = LOCAL / f"BAXY/C03-native-product736-{kind}-profile"
    assert not out.exists() and not private.exists() and not profile_dir.exists()
    assert not any((p.info["name"] or "").lower() in {
        "llama-server.exe", "baxy.exe", "baxy-core.exe", "testhost.exe"}
        for p in psutil.process_iter(["name"]))
    assert psutil.virtual_memory().available >= 2700 * 2**20
    fast = Path(os.environ["TEMP"]) / "c03-native-route735-fast.log"
    assert "source_quality_gate_passed: mode=Fast" in fast.read_text(encoding="utf-8-sig")
    reference_name = "37-q4-high-practical699" if kind == "k2" else "qwen-q4-practical699"
    reference = read(BASE / f"K2_HORIZON_NATIVE699/run-{reference_name}/PREREG.json")
    config = read(MANIFEST)
    assert sha(MANIFEST) == reference["manifest_sha256"]
    command = list(reference["command"])
    binary, model = Path(command[0]), Path(command[command.index("-m") + 1])
    assert sha(model) == reference["model_sha256"]
    for name, expected in reference["backend_files"].items():
        assert sha(binary.parent / name) == expected, name
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    command[command.index("--port") + 1] = str(port)
    if "--log-file" in command:
        command[command.index("--log-file") + 1] = str(private / "server.log")
    endpoint = f"http://127.0.0.1:{port}"
    panel_path = LOCAL / "BAXY/C03-status-batch729-private/panel.json"
    assert sha(panel_path) == "5880182539982018f8472524a36ef0eb2fab80a67a4cf80bb3a5fe7cb568d669"
    panel = read(panel_path)
    assert len(panel) == 73
    sources = source_snapshot()
    scripts = ["scratchpad/c03-native-product736.py", "scratchpad/c03-native-product736-hook/sitecustomize.py",
               "scratchpad/c03_k2_native_adapter732.py", "scratchpad/c03_k2_native_adapter734.py"]
    script_hashes = {p: sha(ROOT / p) for p in scripts}
    app_dll = ROOT / "src/Baxy.App/bin/Release/net10.0-windows10.0.19041.0/Baxy.dll"
    app_dll_hash = sha(app_dll)
    companion = campaign / ("qwen" if kind == "k2" else "k2") / "PREREG.json"
    if companion.exists():
        other = read(companion)
        assert other["sources"] == sources, "Pair must use identical source"
        assert other["scripts"] == script_hashes, "Pair must use identical adapter and driver"
        assert other["app_dll_sha256"] == app_dll_hash, "Pair must use identical app binary"
    campaign.mkdir(exist_ok=True)
    out.mkdir()
    private.mkdir()
    (private / "panel.json").write_bytes(panel_path.read_bytes())
    turns = private / "turns.jsonl"
    turns.write_text("".join(json.dumps({"cmd": "turn", "text": row["text"]},
        ensure_ascii=False) + "\n" for row in panel), encoding="utf-8")
    env = os.environ.copy()
    for name in list(env):
        if name.startswith(("BAXY_MIND_", "BAXY_VOICE_", "BAXY_C03_", "BAXY_FIELD_")) or name in {
            "PYTHONPATH", "BAXY_DATA_DIR", "BAXY_ASSET_DESCRIPTOR", "BAXY_APP_TRACE"}:
            env.pop(name, None)
    python_path = os.pathsep.join(str(ROOT / name) for name in [
        "scratchpad/c03-native-product736-hook", "scratchpad", "src"])
    env.update(BAXY_MIND_LLM_GGUF=str(model), BAXY_MIND_LLAMA_SERVER=str(binary),
        BAXY_MIND_LLM_ENDPOINT=endpoint, BAXY_MIND_PYTHONPATH=python_path,
        BAXY_MIND_NGL="99", BAXY_MIND_NATIVE_TOOL_POLICY="1", BAXY_VOICE_WAKE_ON_START="0",
        BAXY_C03_COMPARE_MODEL=kind, BAXY_C03_COMPARE_PRIVATE=str(private),
        BAXY_APP_TRACE=str(private / "shell-trace.jsonl"),
        BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH=str(private / "compose-audit.jsonl"),
        BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT="1",
        BAXY_MIND_TURN_AUDIT_PATH=str(private / "turn-audit.jsonl"),
        BAXY_MIND_RAW_REPLY_AUDIT_PATH=str(private / "raw-replies.jsonl"),
        PYTHONDONTWRITEBYTECODE="1")
    if kind == "k2":
        env["PATH"] = "C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA/v13.0/bin;" + env["PATH"]
    product_command = ["py", "main.py", "--conductor", "--profile", str(profile_dir),
        "--capture", str(private / "capture"), "--turns-file", str(turns), "--timeout-ms", "120000"]
    preflight_code = '''import copy,json
from unittest.mock import patch
from baxy_mind import llm
r=llm.LlmRuntime()
assert r._c03_native_profile736 in {'k2','qwen'} and r._native_tool_policy_enabled
p={'messages':[{'role':'system','content':'A'},{'role':'system','content':'B'},{'role':'user','content':'C'}],'seed':17,'max_tokens':64,'chat_template_kwargs':{'enable_thinking':False}}
before=copy.deepcopy(p);seen=[]
class Captured(Exception): pass
def capture(wire,**kwargs):
 seen.append(wire);raise Captured
with patch.object(llm,'post_chat_completion',capture):
 try:r._post(p)
 except Captured:pass
assert p==before and len(seen)==1 and seen[0]['messages']==p['messages'] and seen[0]['seed']==17
assert seen[0]['max_tokens']==4096
assert seen[0]['temperature']==(1.0 if r._c03_native_profile736=='k2' else .7)
assert seen[0].get('chat_template_kwargs',{}).get('enable_thinking') is None
print(json.dumps({'profile':r._c03_native_profile736,'wire':seen[0],'native_policy':r._native_tool_policy_enabled}))
'''
    write(out / "PREREG.json", {
        "utc": datetime.now(timezone.utc).isoformat(), "kind": kind, "command": command,
        "product_command": product_command, "manifest_sha256": sha(MANIFEST),
        "model_sha256": reference["model_sha256"], "backend_files": reference["backend_files"],
        "profile_reference": reference_name, "panel_sha256": sha(panel_path),
        "case_count": len(panel), "sources": sources, "scripts": script_hashes,
        "app_dll_sha256": app_dll_hash,
        "fast_sha256": sha(fast), "preflight_code": preflight_code,
        "method": "Actual shared BAXY conductor, same complete73 status category, order, fresh isolated profile and identical source for each model. Native practical699 per-model sampler/server/8192 context/4096 generation; one slot; original role/retry seeds and product deadlines; all original policy/catalog/kernel/provider/validators retained. Both use original system messages and the same explicit schema serialization adapter. Native route is enabled as in registered defaults. Log actual legacy-guard reachability; do not attribute direct-role733/734 guard failures to this route without a live call.",
        "scope": "Read-only product comparison after native699, not UI/voice/reserve acceptance or model promotion. Dynamic status facts may differ; judge each against its own fresh observations. Full5 is still red, no source adoption. Historical729 is context, not the same-source model control.",
        "limits": {"gpu_stop_mib": 3800, "minimum_free_ram_mib": 768,
                   "turn_watchdog_ms": 120000, "campaign_seconds": len(panel) * 120 + 120},
    })
    pre_env = {**env, "PYTHONPATH": python_path}
    preflight = subprocess.run([config["python"], "-X", "utf8", "-c", preflight_code],
        cwd=ROOT, env=pre_env, stdin=subprocess.DEVNULL, capture_output=True, text=True,
        encoding="utf-8", timeout=60, creationflags=subprocess.CREATE_NO_WINDOW)
    (private / "preflight.log").write_text(preflight.stdout + preflight.stderr, encoding="utf-8")
    assert preflight.returncode == 0, "Hook preflight failed before product launch"
    receipt = json.loads(preflight.stdout)
    assert receipt["profile"] == kind
    write(out / "PREFLIGHT.json", receipt)
    # Preserve the sentinel trace separately so it cannot count as model traffic.
    for name in ["adapter-http.jsonl", "http-posts.jsonl", "hook-ready.jsonl", "runtime-init.jsonl"]:
        if (private / name).exists():
            (private / name).rename(private / ("preflight-" + name))
    stop, violations, memory_samples = threading.Event(), [], []
    server = product = None
    gpu, ram = ProcessTreeGpuSampler(os.getpid()), RamSampler(os.getpid())
    started = time.monotonic()

    def terminate_owned():
        if product is not None and product.poll() is None:
            subprocess.run(["taskkill", "/PID", str(product.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
                creationflags=subprocess.CREATE_NO_WINDOW)
        if server is not None and server.poll() is None:
            server.terminate()

    def guard():
        while not stop.wait(.25):
            memory_samples.append({"elapsed": time.monotonic()-started,
                "free_ram_mib": psutil.virtual_memory().available/2**20})
            if (gpu.peak_mib or 0) >= 3800:
                violations.append("owned_gpu_bound")
            if psutil.virtual_memory().available < 768*2**20:
                violations.append("free_ram_bound")
            if time.monotonic()-started > len(panel)*120+120:
                violations.append("campaign_watchdog")
            if violations:
                terminate_owned()
                return

    watcher = threading.Thread(target=guard, daemon=True)
    code = None
    try:
        gpu.start()
        ram.start()
        watcher.start()
        with (private / "server-launch.log").open("w", encoding="utf-8") as log:
            server = subprocess.Popen(command, cwd=binary.parent, env=env, stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        write(out / "PROCESS.json", {"driver": os.getpid(), "server": server.pid, "command": command})
        while time.monotonic()-started < 120:
            assert server.poll() is None, "Server exited before ready"
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
            write(private / "props.json", json.load(response))
        assert source_snapshot() == sources
        assert {p: sha(ROOT / p) for p in scripts} == script_hashes
        assert sha(app_dll) == app_dll_hash
        with (private / "launch.log").open("w", encoding="utf-8") as log:
            product = subprocess.Popen(product_command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        write(out / "PROCESS.json", {"driver": os.getpid(), "server": server.pid,
            "product": product.pid, "command": command, "product_command": product_command})
        print(json.dumps({"stage": "product_started", "model": kind, "cases": 73,
                          "product_pid": product.pid, "server_pid": server.pid}), flush=True)
        code = product.wait()
    finally:
        stop.set()
        terminate_owned()
        if server is not None:
            server.wait(timeout=20)
        watcher.join(timeout=5)
        gpu.stop()
        ram.stop()
        write(private / "memory-samples.json", memory_samples)
        write(out / "RESOURCES.json", {"gpu_peak_mib": gpu.peak_mib, "ram_peak_mib": ram.peak_mib,
            "gpu_telemetry_available": gpu.telemetry_available, "violations": violations,
            "seconds": time.monotonic()-started,
            "scope": "Owned driver/server/hidden product tree; no visible UI or physical voice credit"})
        write(out / "EXIT.json", {"exit_code": code, "manifest_unchanged": sha(MANIFEST)==reference["manifest_sha256"],
            "sources_unchanged": source_snapshot()==sources,
            "scripts_unchanged": {p: sha(ROOT / p) for p in scripts} == script_hashes,
            "app_dll_unchanged": sha(app_dll) == app_dll_hash, "adopted": False,
            "model_promoted": False, "survey_coverage_added": 0})
    print(json.dumps({"stage": "product_terminal", "model": kind, "exit_code": code,
                      "private": str(private), "violations": violations}), flush=True)
    raise SystemExit(code if code is not None else 1)


if __name__ == "__main__":
    main()
