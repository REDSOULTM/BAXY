"""Proposed registered 75-case application-open category runner.

Prepared by root from the external proposal. Root assigns --batch and supplies
the adopted source pins after process confirmation; this file does not adopt source.
It does not adjudicate quality or update survey coverage.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
import subprocess
import sys
import threading
import time

import psutil

ROOT = Path(r"D:\Perfil\Escritorio\ETC\Programacion\BAXY DEFINITIVO")
sys.path.insert(0, str(ROOT))
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--batch", required=True, type=int)
parser.add_argument("--source-pins", required=True, type=Path)
parser.add_argument("--full-exit", required=True, type=Path)
args = parser.parse_args()
if not __debug__:
    raise RuntimeError("Optimized Python disables inherited seals; use normal Python")
assert args.batch > 803, "root assigns a fresh batch after process803"
OUT = ROOT / f"artifacts/comprobaciones/C03/APPLICATION_OPEN{args.batch}"
PRIVATE = Path(os.environ["LOCALAPPDATA"]) / f"BAXY/C03-app-open-runner{args.batch}-private"
PROFILE = PRIVATE.parent / f"C03-app-open-profile{args.batch}"
PANEL_PATH = PRIVATE.parent / "C03-app-open-category-next-private/panel.json"
PLAN_PATH = ROOT / "artifacts/comprobaciones/C03/NEXT_APPLICATION_CATEGORY.json"
PINS_PATH = args.source_pins.resolve()
assert PINS_PATH.is_relative_to(ROOT.resolve()), "pins must be canonical"


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(path, value):
    Path(path).write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def utc():
    return datetime.now(timezone.utc).isoformat()


assert ROOT.joinpath("Baxy.slnx").exists() and ROOT.joinpath("main.py").exists()
assert not any(path.exists() for path in (OUT, PRIVATE, PROFILE))
assert psutil.virtual_memory().available >= 4000 * 2**20, "preflight free RAM"
busy = [p.info for p in psutil.process_iter(["pid", "name", "cmdline"])
        if (p.info["name"] or "").lower() in {"llama-server.exe", "baxy.exe", "baxy-core.exe", "testhost.exe"}
        or any("pytest" in part for part in p.info["cmdline"] or [])]
assert not busy, f"preflight concurrent product/test processes: {busy}"

assert subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT,
                               text=True, creationflags=subprocess.CREATE_NO_WINDOW).strip() == "Goal-c03"
plan = read(PLAN_PATH)
assert plan["status"] == "prepared_not_run"
assert plan["case_count"] == 75
assert Path(plan["panel_path"]).resolve() == PANEL_PATH.resolve()
assert sha(PANEL_PATH) == plan["panel_sha256"] == "207b772a600bc7c5e334c470ab95eb56eb8831c52c10bb1d5166e6726099e8e2"
panel = read(PANEL_PATH)
assert len(panel) == 75 and len({case["case_id"] for case in panel}) == 75
assert {case["group"] for case in panel} == {"owner_open", "open_variant", "boundary"}

# Root must seal these pins after the application-open repair and before execution.
assert PINS_PATH.is_file(), f"missing sealed dependency: {PINS_PATH}"
source_pins = read(PINS_PATH)
assert source_pins and all(sha(ROOT / path) == digest for path, digest in source_pins.items())
assert read(PINS_PATH.parent / "VALIDATION_EXIT.json")["exit_code"] == 0
full_exit = args.full_exit.resolve()
assert full_exit.is_relative_to(ROOT.resolve())
assert read(full_exit)["exit_code"] == 0 and read(full_exit)["source_pins_unchanged"] is True
assert read(full_exit)["source_pins_sha256"] == sha(PINS_PATH)

manifest = PRIVATE.parent.parent / "BAXYRuntime/mind-runtime-v1.json"
config = read(manifest)
assert sha(manifest) == "13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed"
model = Path(config["gguf"])
assert sha(model) == "3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597"

# Use the identical launcher preparation and source recheck as runner799 before sealing the DLL.
preparation = subprocess.run([sys.executable, "-X", "utf8", "-c", "import main; main.compile_if_needed(force=False)"],
                             cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW, check=True)
assert all(sha(ROOT / path) == digest for path, digest in source_pins.items())
shutdown = subprocess.run([str(Path.home() / ".dotnet/dotnet.exe"), "build-server", "shutdown",
                           "--msbuild", "--vbcscompiler"], cwd=ROOT, stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           creationflags=subprocess.CREATE_NO_WINDOW, check=True)
assert psutil.virtual_memory().available >= 4000 * 2**20, "post-build free RAM"

paths = subprocess.check_output(
    ["git", "ls-files", "--cached", "--others", "--exclude-standard", "--", "src", "scripts", "main.py"],
    cwd=ROOT, text=True, encoding="utf-8", creationflags=subprocess.CREATE_NO_WINDOW).splitlines()
sources = {name: sha(ROOT / name) for name in sorted(set(paths)) if (ROOT / name).is_file()}
app = ROOT / "src/Baxy.App/bin/Release/net10.0-windows10.0.19041.0/Baxy.dll"
app_sha = sha(app)

OUT.mkdir()
PRIVATE.mkdir()
(PRIVATE / "build-preparation.log").write_bytes(preparation.stdout)
(PRIVATE / "build-servers-shutdown.log").write_bytes(shutdown.stdout)
(PRIVATE / "panel.json").write_bytes(PANEL_PATH.read_bytes())
turns = PRIVATE / "turns.jsonl"
turns.write_text("".join(json.dumps({"cmd": "turn", "text": row["text"]}, ensure_ascii=False) + "\n"
                         for row in panel), encoding="utf-8")

env = os.environ.copy()
for name in list(env):
    if name.startswith(("BAXY_MIND_", "BAXY_VOICE_", "BAXY_C03_", "BAXY_FIELD_")) or name in {
        "PYTHONPATH", "BAXY_DATA_DIR", "BAXY_ASSET_DESCRIPTOR", "BAXY_APP_TRACE"}:
        env.pop(name, None)
env.update(BAXY_MIND_LLM_GGUF=str(model), BAXY_MIND_LLAMA_SERVER=config["llama_server"],
           BAXY_MIND_PYTHONPATH=str(ROOT / "src"), BAXY_VOICE_WAKE_ON_START="0",
           BAXY_APP_TRACE=str(PRIVATE / "shell-trace.jsonl"),
           BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH=str(PRIVATE / "compose-audit.jsonl"),
           BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT="1",
           BAXY_MIND_TURN_AUDIT_PATH=str(PRIVATE / "turn-audit.jsonl"),
           BAXY_MIND_RAW_REPLY_AUDIT_PATH=str(PRIVATE / "raw-replies.jsonl"))
command = [sys.executable, "main.py", "--conductor", "--profile", str(PROFILE), "--capture",
           str(PRIVATE / "capture"), "--turns-file", str(turns), "--timeout-ms", "120000"]
prereg = {
    "utc": utc(), "batch": args.batch,
    "observation": "Independent Win32 windows/focus and processes: panel pre/post plus250ms samples. A sample is associated only when complete sequential shell-trace bookends retain the same started turn after a completed core call. Completion is not success; no automatic quality judgment or UTC alignment.",
    "method": "Registered75 application-open category from the sealed NEXT_APPLICATION_CATEGORY panel. No prompt/sampler adapters, no automated coverage credit and no native model comparison.",
    "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, creationflags=subprocess.CREATE_NO_WINDOW).strip(),
    "private": str(PRIVATE), "panel_sha256": sha(PANEL_PATH), "turns_sha256": sha(turns),
    "plan_sha256": sha(PLAN_PATH),
    "cases": [{key: case[key] for key in ("case_id", "group", "origin", "criterion")} for case in panel],
    "criteria": plan["criteria"], "coverage_rule": plan["coverage"], "effect_scope": plan["execution"],
    "profile": "Fresh isolated private conductor profile, wake disabled.",
    "dependency": {"source_pins": str(PINS_PATH), "pins": source_pins,
                   "full_exit": str(full_exit), "full_exit_sha256": sha(full_exit)},
    "sources": sources, "runner_sha256": sha(__file__),
    "manifest_sha256": sha(manifest), "model": {"path": str(model), "sha256": sha(model)},
    "backend": {"path": config["llama_server"], "sha256": sha(config["llama_server"])},
    "build_preparation_sha256": sha(PRIVATE / "build-preparation.log"), "build_prepared_before_seal": True,
    "app_dll_sha256": app_sha, "sampler_or_prompt_overrides": [],
    "limits": {"gpu_stop_mib": 3800, "minimum_free_ram_mib": 768, "wall_seconds": 900,
               "per_turn_timeout_ms": 120000, "inherited": "runner799 resource limits"},
    "quality_adjudicated": False,
}
write(OUT / "PREREG.json", prereg)


# Native read-only observation: no shell helpers, no changes to user windows.
user32 = ctypes.WinDLL("user32", use_last_error=True)
window_callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.argtypes = [window_callback, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetForegroundWindow.restype = wintypes.HWND


def observe_windows(phase):
    windows, errors = [], []
    foreground = int(user32.GetForegroundWindow() or 0)

    @window_callback
    def visit(hwnd, _):
        try:
            if user32.IsWindowVisible(hwnd):
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                title = ctypes.create_unicode_buffer(user32.GetWindowTextLengthW(hwnd) + 1)
                user32.GetWindowTextW(hwnd, title, len(title))
                windows.append({"hwnd": int(hwnd), "pid": pid.value, "title": title.value,
                                "foreground": int(hwnd) == foreground})
        except Exception as error:
            errors.append(type(error).__name__)
        return True

    if not user32.EnumWindows(visit, 0) or errors:
        raise RuntimeError(f"independent_window_observation_failed:{errors}")
    processes_now = [p.info for p in psutil.process_iter(["pid", "name", "create_time"], ad_value=None)]
    return {"utc": utc(), "monotonic": time.monotonic(), "phase": phase,
            "foreground_hwnd": foreground, "windows": windows, "processes": processes_now}


class TraceCursor:
    """Read complete AutoFlush records; uncertain reads cannot label a sample."""

    def __init__(self, path):
        self.path = path
        self.offset = 0
        self.pending = b""
        self.sequence = 0
        self.turn = None
        self.core_completed = False
        self.healthy = True

    def read(self):
        if not self.path.exists():
            return {"healthy": False}
        if self.path.stat().st_size < self.offset:
            self.healthy = False
        with self.path.open("rb") as stream:
            stream.seek(self.offset)
            self.pending += stream.read()
            self.offset = stream.tell()
        complete = self.pending.split(b"\n")
        self.pending = complete.pop()
        for line in complete:
            try:
                row = json.loads(line)
                if row["seq"] != self.sequence + 1 or row["stage"] == "trace.truncated":
                    self.healthy = False
                self.sequence = row["seq"]
                if row["scope"] != "turn":
                    continue
                if row["stage"] == "queue.wait.end":
                    self.turn = row["id"]
                    self.core_completed = False
                elif row["id"] == self.turn:
                    if row["stage"] == "core.call.start":
                        self.core_completed = False
                    elif row["stage"] == "core.call.end":
                        self.core_completed = True
            except (ValueError, KeyError, TypeError):
                self.healthy = False
        return {"seq": self.sequence, "turn_id": self.turn,
                "core_completed": self.core_completed, "healthy": self.healthy and not self.pending}


def associate_window_sample(cursor, cases, observer):
    before = cursor.read()
    sample = observer("during_panel")
    after = cursor.read()
    sample["association"] = None
    turn = before.get("turn_id")
    if (before["healthy"] and after["healthy"] and before["core_completed"]
            and after["core_completed"] and turn == after["turn_id"]
            and isinstance(turn, str) and turn.startswith("t") and turn[1:].isdigit()
            and 1 <= int(turn[1:]) <= len(cases)):
        sample["association"] = {"method": "trace_bookends", "turn_id": turn,
            "case_id": cases[int(turn[1:]) - 1]["case_id"], "seq_before": before["seq"],
            "seq_after": after["seq"], "core_completed_before": True}
    return sample


trace_cursor = TraceCursor(PRIVATE / "shell-trace.jsonl")
write(PRIVATE / "windows-before.json", observe_windows("before_panel"))

stop = threading.Event()
violations, processes = [], {}
started = time.monotonic()
with (PRIVATE / "launch.log").open("w", encoding="utf-8") as log:
    process = subprocess.Popen(command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                               stdout=log, stderr=subprocess.STDOUT,
                               creationflags=subprocess.CREATE_NO_WINDOW)
    write(OUT / "PROCESS.json", {"utc": utc(), "launcher": process.pid, "runner": os.getpid(), "command": command})
    print(json.dumps({"started": True, "launcher": process.pid, "registered_turns": 75}), flush=True)
    gpu, ram = ProcessTreeGpuSampler(process.pid), RamSampler(process.pid)

    def stop_infrastructure():
        # Never tree-kill: launched target apps can own user windows or unsaved work.
        try:
            descendants = psutil.Process(process.pid).children(recursive=True)
        except psutil.NoSuchProcess:
            descendants = []
        product_exes = {str(app.with_suffix(".exe")).casefold(),
                        str(app.parent / "baxy-core.exe").casefold(),
                        str(Path(config["llama_server"])).casefold()}
        for child in reversed(descendants):
            try:
                argv = child.cmdline()
                diagnostic = child.exe().casefold() in product_exes or any(
                    part.replace("\\", "/").endswith(("/main.py", "/run_baxy_conductor.ps1"))
                    or part in {"main.py", "baxy_mind.server"} for part in argv)
                if diagnostic:
                    child.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        if process.poll() is None:
            process.kill()

    def guard_resources():
        last_observation = 0.0
        with (PRIVATE / "memory-samples.jsonl").open("w", encoding="utf-8") as samples, (PRIVATE / "windows-timeline.jsonl").open("w", encoding="utf-8") as observations:
            while not stop.wait(0.25):
                rows = []
                try:
                    parent = psutil.Process(process.pid)
                    for child in [parent, *parent.children(recursive=True)]:
                        try:
                            key = str(child.pid)
                            if key not in processes:
                                processes[key] = {"pid": child.pid, "parent": child.ppid(),
                                                  "name": child.name(), "command": child.cmdline()}
                            info = child.memory_info()
                            rows.append({"pid": child.pid, "rss_mib": info.rss / 2**20,
                                         "private_mib": getattr(info, "private", 0) / 2**20})
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                except psutil.NoSuchProcess:
                    pass
                elapsed = time.monotonic() - started
                if elapsed - last_observation >= 0.25:
                    try:
                        sample = associate_window_sample(trace_cursor, panel, observe_windows)
                        observations.write(json.dumps(sample, ensure_ascii=False) + "\n")
                        observations.flush()
                    except Exception as error:
                        violations.append(f"independent_observation_failed:{type(error).__name__}")
                    last_observation = elapsed
                if elapsed > 5 and not gpu.is_alive():
                    violations.append("gpu_sampler_stopped")
                if elapsed > 5 and not gpu.telemetry_available:
                    violations.append("gpu_telemetry_unavailable")
                available = psutil.virtual_memory().available / 2**20
                samples.write(json.dumps({"elapsed": round(elapsed, 3), "available_mib": available,
                                          "processes": rows}) + "\n")
                if elapsed > 900:
                    violations.append("scenario_wall_time_bound")
                if gpu.peak_mib is not None and gpu.peak_mib >= 3800:
                    violations.append("owned_gpu_bound")
                if available < 768:
                    violations.append("system_free_ram_bound")
                if violations:
                    stop_infrastructure()
                    return

    guard = threading.Thread(target=guard_resources, daemon=True)
    try:
        gpu.start()
        ram.start()
        guard.start()
        try:
            code = process.wait(timeout=905)
        except subprocess.TimeoutExpired:
            violations.append("scenario_wall_time_bound")
            stop_infrastructure()
            code = process.wait(timeout=10)
    finally:
        stop.set()
        if guard.ident is not None:
            guard.join(timeout=5)
        if gpu.ident is not None:
            gpu.stop()
        if ram.ident is not None:
            ram.stop()
        write(PRIVATE / "processes.json", processes)
        write(OUT / "RESOURCES.json", {"utc": utc(), "violations": violations,
              "gpu_peak_mib": gpu.peak_mib, "gpu_telemetry_available": gpu.telemetry_available,
              "ram_peak_mib": ram.peak_mib, "seconds": round(time.monotonic() - started, 3),
              "scope": "Owned conductor product process tree; no voice or visible desktop UI credit."})

write(PRIVATE / "windows-after.json", observe_windows("after_panel"))
if not gpu.telemetry_available:
    violations.append("gpu_telemetry_unavailable")
events_path = PRIVATE / "capture/events.jsonl"
events = [json.loads(line) for line in events_path.read_text(encoding="utf-8-sig").splitlines() if line.strip()] if events_path.exists() else []
terminals = [event for event in events if event.get("type") == "terminal"]
if len(terminals) != len(panel):
    violations.append("incomplete_panel")
outcome = {"utc": utc(), "exit_code": code, "runner_violations": violations,
           "observed_terminals": len(terminals),
           "panel_unchanged": sha(PANEL_PATH) == prereg["panel_sha256"],
           "plan_unchanged": sha(PLAN_PATH) == prereg["plan_sha256"],
           "manifest_unchanged": sha(manifest) == prereg["manifest_sha256"],
           "sources_unchanged": all(sha(ROOT / path) == digest for path, digest in sources.items()),
           "dependency_sources_unchanged": all(sha(ROOT / path) == digest for path, digest in source_pins.items()),
           "runner_unchanged": sha(__file__) == prereg["runner_sha256"],
           "app_dll_unchanged": sha(app) == app_sha, "quality_adjudicated": False}
outcome["runner_exit_code"] = code or (2 if violations or not all(
    value for key, value in outcome.items() if key.endswith("_unchanged")) else 0)
write(OUT / "EXIT.json", outcome)
print(json.dumps(outcome), flush=True)
raise SystemExit(outcome["runner_exit_code"])
