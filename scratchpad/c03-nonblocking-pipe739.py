"""Test nonblocking stdin as one private change after deferred DSP prewarm."""
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
OUT = ROOT / "artifacts/comprobaciones/C03/NONBLOCKING_PIPE739"
PRIVATE = Path(os.environ["LOCALAPPDATA"]) / "BAXY/C03-nonblocking-pipe739-private"
OUT.mkdir(exist_ok=False)
PRIVATE.mkdir(exist_ok=False)
TEST = ROOT / "tests/test_sidecar_lifecycle.py"
CASES = [("test_dispatch_crash_exits_while_redirected_stdin_remains_open", 3.0, 1),
         ("test_cold_voice_dsp_responds_while_redirected_stdin_remains_open", 10.0, 0)]


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


tree = ast.parse(TEST.read_text(encoding="utf-8"))
pins = {name: sha(ROOT/name) for name in ["tests/test_sidecar_lifecycle.py",
    "src/baxy_mind/__main__.py", "src/baxy_mind/protocol.py", "src/baxy_mind/voice_aec.py"]}
write(OUT/"PREREG.json", {
    "utc": dt.datetime.now(dt.timezone.utc).isoformat(), "source_pins": pins,
    "profiles": ["deferred_only", "deferred_nonblocking"], "cases": CASES,
    "difference": "Both defer prepare_resampler privately; second sets stdin pipe nonblocking and retries only BlockingIOError every 5ms.",
    "preserved": "Original child scripts, deadlines, expected errors and open stdin; no production or test file edited.",
    "scope": "Mechanism diagnostic; not original-owner acceptance until a source candidate passes the unmodified tests.",
    "sources": ["https://docs.python.org/3.12/library/os.html#os.set_blocking",
                "https://learn.microsoft.com/en-us/windows/win32/ipc/anonymous-pipe-operations"],
    "previous_turn": "progress: published and verified candidate738 evidence as a296db0b060dd1857d9339638df89d39b15e3635",
})

bootstrap = '''
import atexit
import json
import os
import time
from pathlib import Path
from baxy_mind import protocol
os.set_blocking(sys.stdin.fileno(), False)
assert not os.get_blocking(sys.stdin.fileno())
_pipe_stats = {"nonblocking": True, "empty_retries": 0, "eof": 0, "reads": 0}
def nonblocking_read(descriptor, limit):
    while True:
        try:
            chunk = os.read(descriptor, limit)
            _pipe_stats["reads"] += 1
            _pipe_stats["eof"] += not bool(chunk)
            return chunk
        except BlockingIOError:
            _pipe_stats["empty_retries"] += 1
            time.sleep(0.005)
protocol._BoundedFileDescriptorLineReader.__init__.__kwdefaults__["read"] = nonblocking_read
atexit.register(lambda: Path(PIPE_STATS_PATH).write_text(json.dumps(_pipe_stats), encoding="utf-8"))
'''

results = []
environment = dict(os.environ, PYTHONPATH=str(ROOT/"src"))
for profile in ["deferred_only", "deferred_nonblocking"]:
    for name, deadline, expected in CASES:
        node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
        assignment = next(node for node in node.body if isinstance(node, ast.Assign)
                          and any(isinstance(target, ast.Name) and target.id == "script" for target in node.targets))
        script = ast.literal_eval(assignment.value)
        script = script.replace("sys.exit(sidecar.main())", "sidecar.prepare_resampler = lambda: None\nsys.exit(sidecar.main())")
        if not expected:
            script = script.replace("    from scipy.signal import resample_poly",
                                    "    assert 'scipy.signal' not in sys.modules\n    from scipy.signal import resample_poly")
        tag = profile + ("-crash" if expected else "-dsp")
        if profile == "deferred_nonblocking":
            injected = bootstrap.replace("PIPE_STATS_PATH", repr(str(PRIVATE/(tag+"-pipe.json"))))
            marker = "receiver_entered = threading.Event()" if expected else "def probe_dispatch("
            script = script.replace(marker, injected+"\n"+marker)
            script = script.replace("return os.read(descriptor, limit)", "return nonblocking_read(descriptor, limit)")
        (PRIVATE/(tag+".py")).write_text(script, encoding="utf-8")
        started = time.monotonic()
        process = subprocess.Popen([sys.executable, "-c", script], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment)
        timed_out = False
        stack_exit = None
        if not expected:
            process.stdin.write(b'{"type":"probe"}\n')
            process.stdin.flush()
        try:
            code = process.wait(timeout=deadline)
            elapsed = time.monotonic()-started
        except subprocess.TimeoutExpired:
            elapsed = time.monotonic()-started
            timed_out = True
            parent = psutil.Process(process.pid)
            children = [(child.pid, child.create_time()) for child in parent.children(recursive=True)]
            targets = parent.children(recursive=True)
            target = max(targets, key=lambda child: child.memory_info().rss) if targets else parent
            with (PRIVATE/(tag+"-stack.txt")).open("wb") as stream:
                stack_exit = subprocess.run([str(Path(os.environ["TEMP"])/"c03-pyspy712/bin/py-spy.exe"),
                    "dump", "--pid", str(target.pid)], stdout=stream, stderr=subprocess.STDOUT,
                    timeout=5, check=False).returncode
            process.stdin.close()
            for pid, created in reversed(children):
                try:
                    child = psutil.Process(pid)
                    if child.create_time() == created:
                        child.kill()
                        child.wait(timeout=3)
                except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                    pass
            if process.poll() is None:
                process.kill()
            code = process.wait(timeout=3)
        finally:
            process.stdin.close()
        stdout, stderr = process.stdout.read(), process.stderr.read()
        (PRIVATE/(tag+"-stdout.txt")).write_bytes(stdout)
        (PRIVATE/(tag+"-stderr.txt")).write_bytes(stderr)
        semantic = ((b'"type":"hello"' in stdout and b"forced_dispatch_crash" in stderr
                     and b"_enter_buffered_busy" not in stderr) if expected else
                    b'"type":"probe.done"' in stdout and not stderr)
        stats = PRIVATE/(tag+"-pipe.json")
        row = {"profile": profile, "case": name, "deadline": deadline, "elapsed": elapsed,
            "timed_out": timed_out, "exit_code": code, "passed": not timed_out and elapsed < deadline
            and code == expected and semantic, "hello_seen": b'"type":"hello"' in stdout,
            "stack_exit": stack_exit, "pipe": json.loads(stats.read_text()) if stats.exists() else None}
        results.append(row)
        write(OUT/"RESULT.json", {"rows": results, "adopted": False, "coverage_added": 0, "goal_complete": False})
        print(json.dumps(row), flush=True)
assert all(sha(ROOT/name)==h for name,h in pins.items())
write(OUT/"PINS.json", {"source": pins, "script": sha(Path(__file__)),
    "private": {path.name: sha(path) for path in PRIVATE.iterdir() if path.is_file()},
    "public": {name: sha(OUT/name) for name in ["PREREG.json", "RESULT.json"]}})
