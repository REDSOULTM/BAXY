"""Capture the unchanged phase-bounded crash test after its first deadline failure."""
from pathlib import Path
import datetime as dt
import hashlib
import importlib.util
import json
import os
import subprocess
import time

import psutil

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/comprobaciones/C03/astra-dispatch-exit-probe725"
PRIVATE = Path(os.environ["LOCALAPPDATA"]) / "BAXY/C03-dispatch-exit-probe725-private"
OUT.mkdir(exist_ok=False)
PRIVATE.mkdir(exist_ok=False)
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
TEST = ROOT / "tests/test_sidecar_lifecycle.py"
test_hash = hashlib.sha256(TEST.read_bytes()).hexdigest()


def save(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


save(OUT / "PREREG.json", {"utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    "test_sha256": test_hash, "max_attempts": 5, "stop_at_first_failure": True,
    "difference": "Popen subclass captures stack only after TimeoutExpired; original test and10/3 deadlines",
    "coverage_added": 0, "adopted": False})
spec = importlib.util.spec_from_file_location("sidecar725", TEST)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
original_popen = subprocess.Popen
owned = []
current_attempt = 0


class ObservedPopen(original_popen):
    def __init__(self, args, *positional, **keywords):
        self.is_test = isinstance(args, list) and "-c" in args and "forced_dispatch_crash" in str(args)
        self.captured = False
        self.descendants = []
        super().__init__(args, *positional, **keywords)
        if self.is_test:
            owned.append(self)

    def wait(self, timeout=None):
        try:
            return super().wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            if not self.is_test or self.captured:
                raise
            self.captured = True
            parent = psutil.Process(self.pid)
            children = parent.children(recursive=True)
            self.descendants = [(child.pid, child.create_time()) for child in children]
            observations = []
            for child in [parent, *children]:
                try:
                    observations.append({"pid": child.pid, "created": child.create_time(),
                                         "rss": child.memory_info().rss, "threads": child.num_threads()})
                except psutil.NoSuchProcess:
                    pass
            target = max(observations, key=lambda item: item["rss"])["pid"]
            save(OUT / f"attempt{current_attempt}-DEADLINE.json", {
                "timeout": timeout, "utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                "processes": observations, "target": target})
            with (PRIVATE / f"attempt{current_attempt}-stack.txt").open("wb") as stream:
                completed = subprocess.run([str(Path(os.environ["TEMP"]) / "c03-pyspy712/bin/py-spy.exe"),
                                           "dump", "--pid", str(target)],
                                          stdout=stream, stderr=subprocess.STDOUT, timeout=5, check=False)
            save(OUT / f"attempt{current_attempt}-STACK_EXIT.json", {"exit_code": completed.returncode})
            raise


subprocess.Popen = ObservedPopen
results = []
try:
    for current_attempt in range(1, 6):
        started = time.monotonic()
        error = None
        try:
            module.test_dispatch_crash_exits_while_redirected_stdin_remains_open()
        except BaseException as failure:
            error = f"{type(failure).__name__}: {failure}"
        for process in owned:
            for pid, created in process.descendants:
                try:
                    child = psutil.Process(pid)
                    if child.create_time() == created and child.is_running():
                        child.kill()
                        child.wait(timeout=3)
                except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                    pass
            if error:
                for label, stream in (("stdout", process.stdout), ("stderr", process.stderr)):
                    if stream is not None:
                        (PRIVATE / f"attempt{current_attempt}-{label}.txt").write_bytes(stream.read())
        owned.clear()
        result = {"attempt": current_attempt, "pass": error is None, "error": error,
                  "elapsed_including_post_deadline_observation": time.monotonic() - started}
        results.append(result)
        save(OUT / "RESULT.json", {"results": results, "source_unchanged": hashlib.sha256(TEST.read_bytes()).hexdigest() == test_hash,
                                   "coverage_added": 0, "goal_complete": False})
        print(json.dumps(result), flush=True)
        if error is not None:
            break
finally:
    subprocess.Popen = original_popen
