"""Falsify deferred DSP loading before proposing any product change."""
from pathlib import Path
import ast
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import time

import psutil

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/comprobaciones/C03/astra-cold-dsp-probe719"
PRIVATE = Path(os.environ["LOCALAPPDATA"]) / "BAXY/C03-cold-dsp-probe719-private"
OUT.mkdir(exist_ok=False)
PRIVATE.mkdir(exist_ok=False)
TEST = ROOT / "tests/test_sidecar_lifecycle.py"
tree = ast.parse(TEST.read_text(encoding="utf-8"))
CASES = [("test_dispatch_crash_exits_while_redirected_stdin_remains_open", 3.0, 1),
         ("test_cold_voice_dsp_responds_while_redirected_stdin_remains_open", 10.0, 0)]


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


pins = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        for path in ("tests/test_sidecar_lifecycle.py", "src/baxy_mind/__main__.py", "src/baxy_mind/voice_aec.py")}
write(OUT / "PREREG.json", {
    "utc": dt.datetime.now(dt.timezone.utc).isoformat(), "source_hashes": pins,
    "cases": CASES, "profiles": ["original", "deferred_warmup_only"],
    "difference": "Replace prepare_resampler only in the private child process, no source edits",
    "cold_assertion": "Deferred DSP profile requires scipy.signal absent before its first native import",
    "post_deadline_observer": "py-spy on actual interpreter, then creation-time-checked disposal",
    "adoption": False, "coverage_added": 0,
})
results = []
environment = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
for profile in ("original", "deferred_warmup_only"):
    for name, deadline, expected_code in CASES:
        node = next(item for item in ast.walk(tree) if isinstance(item, ast.FunctionDef) and item.name == name)
        assignment = next(item for item in node.body if isinstance(item, ast.Assign)
                          and any(isinstance(target, ast.Name) and target.id == "script" for target in item.targets))
        script = ast.literal_eval(assignment.value)
        if profile == "deferred_warmup_only":
            script = script.replace("sys.exit(sidecar.main())", "sidecar.prepare_resampler = lambda: None\nsys.exit(sidecar.main())")
            if expected_code == 0:
                script = script.replace("    from scipy.signal import resample_poly",
                                        "    assert 'scipy.signal' not in sys.modules\n    from scipy.signal import resample_poly")
        tag = profile + ("-crash" if expected_code else "-dsp")
        (PRIVATE / (tag + ".py")).write_text(script, encoding="utf-8")
        started = time.monotonic()
        process = subprocess.Popen([sys.executable, "-c", script], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment)
        timed_out = False
        stack_exit = None
        if expected_code == 0:
            assert process.stdin is not None
            process.stdin.write(b'{"type":"probe"}\n')
            process.stdin.flush()
        try:
            code = process.wait(timeout=deadline)
            elapsed = time.monotonic() - started
        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - started
            timed_out = True
            parent = psutil.Process(process.pid)
            descendants = [(child.pid, child.create_time()) for child in parent.children(recursive=True)]
            targets = [child for child in parent.children(recursive=True) if child.is_running()]
            target = max(targets, key=lambda child: child.memory_info().rss) if targets else parent
            with (PRIVATE / (tag + "-stack.txt")).open("wb") as stream:
                stack_exit = subprocess.run([str(Path(os.environ["TEMP"]) / "c03-pyspy712/bin/py-spy.exe"),
                                             "dump", "--pid", str(target.pid)], stdout=stream,
                                            stderr=subprocess.STDOUT, timeout=5, check=False).returncode
            for pid, created in reversed(descendants):
                try:
                    child = psutil.Process(pid)
                    if child.create_time() == created:
                        child.kill()
                        child.wait(timeout=3)
                except psutil.NoSuchProcess:
                    pass
            if process.poll() is None:
                process.kill()
            code = process.wait(timeout=3)
        finally:
            if process.stdin is not None:
                process.stdin.close()
        stdout = process.stdout.read() if process.stdout else b""
        stderr = process.stderr.read() if process.stderr else b""
        (PRIVATE / (tag + "-stdout.txt")).write_bytes(stdout)
        (PRIVATE / (tag + "-stderr.txt")).write_bytes(stderr)
        semantic_pass = ((b'"type":"hello"' in stdout and b"forced_dispatch_crash" in stderr
                          and b"_enter_buffered_busy" not in stderr) if expected_code
                         else b'"type":"probe.done"' in stdout and not stderr)
        result = {"profile": profile, "case": name, "deadline_seconds": deadline,
                  "elapsed_seconds": elapsed, "timed_out": timed_out, "code": code,
                  "pass": not timed_out and code == expected_code and semantic_pass,
                  "hello_seen": b'"type":"hello"' in stdout,
                  "stack_exit_code": stack_exit}
        results.append(result)
        write(OUT / "RESULT.json", {"results": results, "coverage_added": 0, "goal_complete": False})
        print(json.dumps(result), flush=True)
assert all(hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == value for path, value in pins.items())
