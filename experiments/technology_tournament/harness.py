#!/usr/bin/env python3
"""Reproducible Windows harness for BAXY technology-tournament round A."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import math
import os
import shutil
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT = ROOT / "experiments" / "technology_tournament"
ARTIFACTS = ROOT / "artifacts" / "technology_tournament"
WORK_ROOT = ARTIFACTS / "work"
RAW_ROOT = ARTIFACTS / "raw"
CASES_PATH = EXPERIMENT / "cases.json"
PROTOCOL_PATH = ARTIFACTS / "protocol.json"
REQUIRED_RESPONSE_FIELDS = {
    "schema_version",
    "invocation_id",
    "mission_id",
    "state",
    "intent",
    "effect",
    "risk",
    "operations",
    "verification",
    "response",
    "replayed",
}


@dataclass(frozen=True)
class Contender:
    contender_id: str
    cwd: Path
    command: tuple[str, ...]
    build_command: tuple[str, ...]
    source_files: tuple[Path, ...]
    artifact_files: tuple[Path, ...]
    runtime_external: bool


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_tree(files: Iterable[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(files, key=lambda item: item.as_posix()):
        relative = path.relative_to(ROOT).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        data = path.read_bytes()
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def safe_reset_directory(path: Path, allowed_root: Path) -> None:
    resolved = path.resolve(strict=False)
    allowed = allowed_root.resolve(strict=False)
    if resolved == allowed or allowed not in resolved.parents:
        raise RuntimeError(f"refusing to reset path outside owned work root: {resolved}")
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def percentile(values: list[float], percentile_value: float) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    rank = (len(ordered) - 1) * percentile_value
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - rank) + ordered[upper] * (rank - lower)


if os.name == "nt":
    from ctypes import wintypes

    class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
            ("PrivateUsage", ctypes.c_size_t),
        ]

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]


def process_memory(pid: int) -> dict[str, int] | None:
    if os.name != "nt":
        return None
    process_query_information = 0x0400
    process_vm_read = 0x0010
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
    handle = kernel32.OpenProcess(process_query_information | process_vm_read, False, pid)
    if not handle:
        return None
    try:
        counters = PROCESS_MEMORY_COUNTERS_EX()
        counters.cb = ctypes.sizeof(counters)
        success = psapi.GetProcessMemoryInfo(
            handle,
            ctypes.byref(counters),
            ctypes.sizeof(counters),
        )
        if not success:
            return None
        return {
            "private_bytes": int(counters.PrivateUsage),
            "working_set_bytes": int(counters.WorkingSetSize),
            "peak_working_set_bytes": int(counters.PeakWorkingSetSize),
        }
    finally:
        kernel32.CloseHandle(handle)


def process_tree_pids(root_pid: int) -> list[int]:
    if os.name != "nt":
        return [root_pid]
    th32cs_snapprocess = 0x00000002
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    snapshot = kernel32.CreateToolhelp32Snapshot(th32cs_snapprocess, 0)
    invalid_handle = ctypes.c_void_p(-1).value
    if snapshot == invalid_handle:
        return [root_pid]
    relationships: dict[int, list[int]] = {}
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        if not kernel32.Process32FirstW(snapshot, ctypes.byref(entry)):
            return [root_pid]
        while True:
            relationships.setdefault(int(entry.th32ParentProcessID), []).append(int(entry.th32ProcessID))
            entry.dwSize = ctypes.sizeof(entry)
            if not kernel32.Process32NextW(snapshot, ctypes.byref(entry)):
                break
    finally:
        kernel32.CloseHandle(snapshot)
    discovered: list[int] = []
    pending = [root_pid]
    seen: set[int] = set()
    while pending:
        pid = pending.pop(0)
        if pid in seen:
            continue
        seen.add(pid)
        discovered.append(pid)
        pending.extend(relationships.get(pid, ()))
    return discovered


def process_tree_memory(root_pid: int) -> dict[str, Any] | None:
    samples: list[dict[str, int]] = []
    for pid in process_tree_pids(root_pid):
        memory = process_memory(pid)
        if memory is not None:
            samples.append({"pid": pid, **memory})
    if not samples:
        return None
    return {
        "private_bytes": sum(sample["private_bytes"] for sample in samples),
        "working_set_bytes": sum(sample["working_set_bytes"] for sample in samples),
        "peak_working_set_bytes": sum(sample["peak_working_set_bytes"] for sample in samples),
        "processes": samples,
    }


def network_snapshot(pid: int) -> dict[str, Any]:
    pids = process_tree_pids(pid)
    powershell_pids = ",".join(str(value) for value in pids)
    script = (
        f"$ids=@({powershell_pids});"
        "$tcp=@(Get-NetTCPConnection -ErrorAction SilentlyContinue | Where-Object {$ids -contains $_.OwningProcess} | "
        "Select-Object State,LocalAddress,LocalPort,RemoteAddress,RemotePort);"
        "$udp=@(Get-NetUDPEndpoint -ErrorAction SilentlyContinue | Where-Object {$ids -contains $_.OwningProcess} | "
        "Select-Object LocalAddress,LocalPort);"
        "@{tcp=$tcp;udp=$udp}|ConvertTo-Json -Compress -Depth 4"
    )
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=10,
            check=False,
        )
        if completed.returncode != 0 or not completed.stdout.strip():
            return {"error": "snapshot_failed", "exit_code": completed.returncode}
        return json.loads(completed.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return {"error": "snapshot_failed"}


def effects_snapshot(workspace: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for directory in (workspace / "notes", workspace / "trash"):
        if not directory.exists():
            continue
        for path in sorted(item for item in directory.rglob("*") if item.is_file()):
            relative = path.relative_to(workspace).as_posix()
            result[relative] = {
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
    return result


def workspace_snapshot(workspace: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    if not workspace.exists():
        return result
    for path in sorted(item for item in workspace.rglob("*") if item.is_file()):
        relative = path.relative_to(workspace).as_posix()
        result[relative] = {
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    return result


def external_file_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False}
    if path.is_file():
        return {"exists": True, "kind": "file", "bytes": path.stat().st_size, "sha256": sha256_file(path)}
    return {"exists": True, "kind": "directory"}


def contenders() -> list[Contender]:
    python_dir = EXPERIMENT / "python_core"
    dotnet_dir = EXPERIMENT / "dotnet_windows_core"
    rust_dir = EXPERIMENT / "rust_core"
    python_file = python_dir / "baxy_slice.py"
    dotnet_dll = dotnet_dir / "bin" / "Release" / "net10.0" / "baxy-dotnet-slice.dll"
    rust_exe = rust_dir / "target" / "release" / "baxy-rust-slice.exe"
    cargo = str(Path.home() / ".cargo" / "bin" / "cargo.exe")
    return [
        Contender(
            "python_core",
            python_dir,
            (sys.executable, str(python_file), "--server"),
            (sys.executable, "-m", "py_compile", str(python_file)),
            (python_file,),
            (python_file,),
            True,
        ),
        Contender(
            "dotnet_windows_core",
            dotnet_dir,
            ("dotnet", str(dotnet_dll), "--server"),
            ("dotnet", "build", "-c", "Release", "--nologo"),
            (dotnet_dir / "BaxySlice.csproj", dotnet_dir / "Program.cs"),
            (
                dotnet_dll,
                dotnet_dll.with_name("baxy-dotnet-slice.deps.json"),
                dotnet_dll.with_name("baxy-dotnet-slice.runtimeconfig.json"),
            ),
            True,
        ),
        Contender(
            "rust_core",
            rust_dir,
            (str(rust_exe), "--server"),
            (cargo, "build", "--release", "--locked"),
            (rust_dir / "Cargo.toml", rust_dir / "Cargo.lock", rust_dir / "src" / "main.rs"),
            (rust_exe,),
            False,
        ),
    ]


def build_contender(contender: Contender) -> dict[str, Any]:
    started = time.perf_counter_ns()
    completed = subprocess.run(
        contender.build_command,
        cwd=contender.cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=180,
        check=False,
    )
    elapsed = time.perf_counter_ns() - started
    artifacts = []
    for path in contender.artifact_files:
        if path.is_file():
            artifacts.append(
                {
                    "path": path.relative_to(ROOT).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    return {
        "command": list(contender.build_command),
        "cwd": contender.cwd.relative_to(ROOT).as_posix(),
        "elapsed_ns": elapsed,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "source_tree_sha256": sha256_tree(contender.source_files),
        "source_lines": sum(len(path.read_text(encoding="utf-8").splitlines()) for path in contender.source_files),
        "runtime_external": contender.runtime_external,
        "artifacts": artifacts,
        "artifact_bytes": sum(item["bytes"] for item in artifacts),
    }


class RunningContender:
    def __init__(self, contender: Contender, authorized_root: Path) -> None:
        environment = os.environ.copy()
        environment["BAXY_TOURNAMENT_ROOT"] = str(authorized_root)
        environment["PYTHONUTF8"] = "1"
        self.process = subprocess.Popen(
            contender.command,
            cwd=contender.cwd,
            env=environment,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="strict",
            bufsize=1,
        )

    def request(self, value: dict[str, Any]) -> tuple[dict[str, Any], int]:
        if self.process.stdin is None or self.process.stdout is None:
            raise RuntimeError("process pipes unavailable")
        wire = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        started = time.perf_counter_ns()
        self.process.stdin.write(wire + "\n")
        self.process.stdin.flush()
        output = self.process.stdout.readline()
        elapsed = time.perf_counter_ns() - started
        if not output:
            raise RuntimeError(f"contender exited before response: {self.process.poll()}")
        return json.loads(output), elapsed

    def close(self) -> tuple[int, str]:
        if self.process.stdin is not None:
            self.process.stdin.close()
        exit_code = self.process.wait(timeout=10)
        stderr = self.process.stderr.read() if self.process.stderr is not None else ""
        return exit_code, stderr


def assert_response_contract(response: dict[str, Any], expected_invocation: str) -> list[str]:
    failures: list[str] = []
    missing = sorted(REQUIRED_RESPONSE_FIELDS - response.keys())
    if missing:
        failures.append(f"missing response fields: {missing}")
    if response.get("schema_version") != 1:
        failures.append("wrong schema_version")
    if response.get("invocation_id") != expected_invocation:
        failures.append("wrong invocation_id")
    if response.get("state") not in {"done", "blocked", "failed"}:
        failures.append("invalid state")
    verification = response.get("verification")
    if not isinstance(verification, dict) or verification.get("status") not in {
        "verified",
        "not_applicable",
        "unverified",
    }:
        failures.append("invalid verification object")
    if not isinstance(response.get("response"), str) or response.get("response", "").startswith(("{", "[")):
        failures.append("response is not natural language")
    if response.get("state") == "done" and response.get("effect") != "none":
        if not isinstance(verification, dict) or verification.get("status") != "verified":
            failures.append("action declared done without verification")
    return failures


def validate_case(
    case: dict[str, Any],
    response: dict[str, Any],
    expected_invocation: str,
    workspace: Path,
    before_effects: dict[str, Any],
    external_before: dict[str, Any] | None,
    external_after: dict[str, Any] | None,
) -> list[str]:
    expected = case["expected"]
    failures = assert_response_contract(response, expected_invocation)
    for field in ("state", "intent", "effect", "risk"):
        if field in expected and response.get(field) != expected[field]:
            failures.append(f"{field}: expected {expected[field]!r}, got {response.get(field)!r}")
    verification = response.get("verification", {})
    if expected.get("verification") is not None and verification.get("status") != expected["verification"]:
        failures.append("verification status mismatch")
    if "operations" in expected and len(response.get("operations", [])) != expected["operations"]:
        failures.append("operation count mismatch")
    if "response_contains" in expected and expected["response_contains"].casefold() not in response.get("response", "").casefold():
        failures.append("natural response omitted expected content")
    if "file" in expected:
        target = workspace / Path(expected["file"])
        if not target.is_file():
            failures.append(f"expected file missing: {expected['file']}")
        elif "content" in expected and target.read_text(encoding="utf-8") != expected["content"]:
            failures.append("file content mismatch")
    if "present" in expected and not (workspace / Path(expected["present"])).is_file():
        failures.append(f"expected present path missing: {expected['present']}")
    if "absent" in expected and (workspace / Path(expected["absent"])).exists():
        failures.append(f"expected absent path exists: {expected['absent']}")
    if "content" in expected and case["id"] == "T07_IDEMPOTENT_REPLAY":
        target = workspace / "notes" / "unica.txt"
        if not target.is_file() or target.read_text(encoding="utf-8") != expected["content"]:
            failures.append("idempotent file content mismatch")
    if expected.get("filesystem_changes") == 0 and effects_snapshot(workspace) != before_effects:
        failures.append("unexpected note/trash filesystem change")
    if expected.get("outside_writes") == 0 and external_before != external_after:
        failures.append("outside target changed")
    if expected.get("journal_tail_quarantined") and not response.get("journal_recovered"):
        failures.append("journal recovery flag missing")
    if expected.get("journal_tail_quarantined") and not list(workspace.glob("journal.corrupt.*.jsonl")):
        failures.append("corrupt journal tail was not quarantined")
    return failures


def journal_completed_count(workspace: Path, invocation_id: str) -> int:
    count = 0
    with (workspace / "journal.jsonl").open("r", encoding="utf-8") as stream:
        for line in stream:
            value = json.loads(line)
            if value.get("status") == "completed" and value.get("invocation_id") == invocation_id:
                count += 1
    return count


def malformed_request_probe(contender: Contender, root: Path) -> dict[str, Any]:
    environment = os.environ.copy()
    environment["BAXY_TOURNAMENT_ROOT"] = str(root)
    completed = subprocess.run(
        contender.command,
        cwd=contender.cwd,
        env=environment,
        input='{"invocation_id":\n',
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=10,
        check=False,
    )
    passed = (
        completed.returncode == 0
        and not completed.stdout.strip()
        and "BAXY_PROTOCOL_ERROR malformed_json" in completed.stderr
        and "Traceback" not in completed.stderr
        and " at " not in completed.stderr
    )
    return {
        "case_id": "T16_MALFORMED_REQUEST",
        "passed": passed,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "failures": [] if passed else ["malformed request contract failed"],
    }


def unauthorized_workspace_probe(runner: RunningContender, root: Path, repetition: int) -> dict[str, Any]:
    outside = root.parent / f"unauthorized_{repetition:02d}"
    if outside.exists():
        safe_reset_directory(outside, WORK_ROOT)
        outside.rmdir()
    before = external_file_state(outside)
    invocation_id = f"gate-workspace-{repetition:02d}"
    response, elapsed = runner.request(
        {
            "invocation_id": invocation_id,
            "message": "Crea la nota escape.txt con el texto: fuera",
            "workspace": str(outside),
        }
    )
    after = external_file_state(outside)
    failures = assert_response_contract(response, invocation_id)
    if response.get("state") != "blocked" or response.get("intent") != "invalid":
        failures.append("unauthorized workspace was not blocked")
    if before != after or outside.exists():
        failures.append("unauthorized workspace path was created or changed")
    return {
        "passed": not failures,
        "failures": failures,
        "external_elapsed_ns": elapsed,
        "response": response,
        "path_before": before,
        "path_after": after,
    }


def functional_run(contender: Contender, cases: list[dict[str, Any]], repetition: int) -> dict[str, Any]:
    root = WORK_ROOT / contender.contender_id / f"functional_{repetition:02d}"
    safe_reset_directory(root, WORK_ROOT)
    workspace = root / "workspace"
    workspace.mkdir(parents=True)
    runner = RunningContender(contender, root)
    samples: list[dict[str, Any]] = []
    max_private_bytes = 0
    max_working_set_bytes = 0
    protected_path = Path("C:/Windows/Temp/baxy-escape.txt")
    unauthorized_probe = unauthorized_workspace_probe(runner, root, repetition)
    for case in cases:
        if case["id"] == "T16_MALFORMED_REQUEST":
            continue
        invocation_id = f"r{repetition:02d}-{case['id'].lower()}"
        if case.get("setup") == "append_partial_json_to_journal_after_T14":
            with (workspace / "journal.jsonl").open("ab") as stream:
                stream.write(b'{"partial":')
                stream.flush()
                os.fsync(stream.fileno())
        before_effects = effects_snapshot(workspace)
        before_workspace = workspace_snapshot(workspace)
        external_target: Path | None = None
        if case["id"] == "T09_BLOCK_TRAVERSAL":
            external_target = workspace.parent / "escape.txt"
        elif case["id"] == "T10_BLOCK_ABSOLUTE_PATH":
            external_target = protected_path
        external_before = external_file_state(external_target) if external_target else None
        request = {
            "invocation_id": invocation_id,
            "message": case["message"],
            "workspace": str(workspace),
        }
        response, elapsed = runner.request(request)
        memory = process_tree_memory(runner.process.pid)
        if memory:
            max_private_bytes = max(max_private_bytes, memory["private_bytes"])
            max_working_set_bytes = max(max_working_set_bytes, memory["peak_working_set_bytes"])
        replay_response = None
        if case.get("repeat_same_invocation_id"):
            replay_response, replay_elapsed = runner.request(request)
            elapsed += replay_elapsed
        external_after = external_file_state(external_target) if external_target else None
        failures = validate_case(
            case,
            response,
            invocation_id,
            workspace,
            before_effects,
            external_before,
            external_after,
        )
        if replay_response is not None:
            failures.extend(assert_response_contract(replay_response, invocation_id))
            if not replay_response.get("replayed"):
                failures.append("second invocation was not marked replayed")
            if journal_completed_count(workspace, invocation_id) != case["expected"]["journal_completed_records"]:
                failures.append("idempotent replay created another completed record")
        samples.append(
            {
                "case_id": case["id"],
                "weight": case["weight"],
                "passed": not failures,
                "failures": failures,
                "external_elapsed_ns": elapsed,
                "response": response,
                "replay_response": replay_response,
                "workspace_before": before_workspace,
                "workspace_after": workspace_snapshot(workspace),
                "external_before": external_before,
                "external_after": external_after,
                "effects_after": effects_snapshot(workspace),
            }
        )
    network = network_snapshot(runner.process.pid)
    exit_code, stderr = runner.close()
    malformed = malformed_request_probe(contender, root)
    samples.append({**malformed, "weight": next(case["weight"] for case in cases if case["id"] == "T16_MALFORMED_REQUEST")})
    return {
        "repetition": repetition,
        "command": list(contender.command),
        "cwd": contender.cwd.relative_to(ROOT).as_posix(),
        "exit_code": exit_code,
        "stderr": stderr,
        "network_snapshot": network,
        "unauthorized_workspace_probe": unauthorized_probe,
        "max_sampled_private_bytes": max_private_bytes,
        "peak_working_set_bytes": max_working_set_bytes,
        "samples": samples,
    }


def cold_start_run(contender: Contender, repetitions: int) -> dict[str, Any]:
    root = WORK_ROOT / contender.contender_id / "cold"
    safe_reset_directory(root, WORK_ROOT)
    environment = os.environ.copy()
    environment["BAXY_TOURNAMENT_ROOT"] = str(root)
    samples: list[dict[str, Any]] = []
    for index in range(repetitions):
        workspace = root / f"workspace_{index:03d}"
        request = json.dumps(
            {
                "invocation_id": f"cold-{index:03d}",
                "message": "Hola BAXY, ¿cómo estás?",
                "workspace": str(workspace),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        started = time.perf_counter_ns()
        completed = subprocess.run(
            contender.command,
            cwd=contender.cwd,
            env=environment,
            input=request + "\n",
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=15,
            check=False,
        )
        elapsed = time.perf_counter_ns() - started
        valid = False
        try:
            output = json.loads(completed.stdout.strip())
            valid = output.get("state") == "done" and output.get("intent") == "conversation"
        except (json.JSONDecodeError, AttributeError):
            output = None
        samples.append(
            {
                "index": index,
                "elapsed_ns": elapsed,
                "exit_code": completed.returncode,
                "valid": valid,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "response": output,
            }
        )
    valid_ns = [sample["elapsed_ns"] for sample in samples if sample["valid"] and sample["exit_code"] == 0]
    return {
        "samples": samples,
        "valid_samples": len(valid_ns),
        "p50_ms": percentile(valid_ns, 0.50) / 1_000_000,
        "p95_ms": percentile(valid_ns, 0.95) / 1_000_000,
    }


def warm_run(contender: Contender, repetitions: int) -> dict[str, Any]:
    root = WORK_ROOT / contender.contender_id / "warm"
    safe_reset_directory(root, WORK_ROOT)
    workspace = root / "workspace"
    workspace.mkdir(parents=True)
    runner = RunningContender(contender, root)
    time.sleep(0.2)
    idle_memory = process_tree_memory(runner.process.pid)
    samples: list[dict[str, Any]] = []
    memory_samples: list[dict[str, int]] = []
    for index in range(repetitions):
        response, elapsed = runner.request(
            {
                "invocation_id": f"warm-{index:03d}",
                "message": "Hola BAXY, ¿cómo estás?",
                "workspace": str(workspace),
            }
        )
        memory = process_tree_memory(runner.process.pid)
        if memory:
            memory_samples.append(memory)
        samples.append(
            {
                "index": index,
                "external_elapsed_ns": elapsed,
                "internal_elapsed_ns": response.get("elapsed_ns"),
                "valid": response.get("state") == "done" and response.get("intent") == "conversation",
            }
        )
    network = network_snapshot(runner.process.pid)
    exit_code, stderr = runner.close()
    measured = samples[1:]
    valid_ns = [sample["external_elapsed_ns"] for sample in measured if sample["valid"]]
    total_seconds = sum(valid_ns) / 1_000_000_000
    return {
        "warmup_discarded": samples[0],
        "samples": measured,
        "valid_samples": len(valid_ns),
        "p50_ms": percentile(valid_ns, 0.50) / 1_000_000,
        "p95_ms": percentile(valid_ns, 0.95) / 1_000_000,
        "throughput_per_second": len(valid_ns) / total_seconds if total_seconds else 0.0,
        "idle_memory": idle_memory,
        "max_sampled_private_bytes": max((sample["private_bytes"] for sample in memory_samples), default=0),
        "peak_working_set_bytes": max((sample["peak_working_set_bytes"] for sample in memory_samples), default=0),
        "network_snapshot": network,
        "exit_code": exit_code,
        "stderr": stderr,
    }


def command_version(command: list[str]) -> str:
    completed = subprocess.run(command, text=True, encoding="utf-8", errors="replace", capture_output=True, check=False, timeout=10)
    return (completed.stdout or completed.stderr).strip()


def ambient_snapshot() -> dict[str, Any]:
    power = subprocess.run(
        ["powercfg", "/getactivescheme"],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=10,
    )
    process_script = (
        "@(Get-Process | Sort-Object Id | Select-Object Id,ProcessName,WorkingSet64)"
        "|ConvertTo-Json -Compress"
    )
    processes = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", process_script],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=15,
    )
    gpu = subprocess.run(
        [
            "nvidia-smi",
            "--query-compute-apps=pid,process_name,used_memory",
            "--format=csv,noheader,nounits",
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=10,
    )
    try:
        process_values = json.loads(processes.stdout) if processes.stdout.strip() else []
    except json.JSONDecodeError:
        process_values = {"error": "process_snapshot_parse_failed"}
    return {
        "power_plan": power.stdout.strip(),
        "power_plan_exit_code": power.returncode,
        "processes": process_values,
        "process_snapshot_exit_code": processes.returncode,
        "gpu_compute_processes_csv": gpu.stdout.strip(),
        "gpu_snapshot_exit_code": gpu.returncode,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run BAXY technology tournament round A")
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--functional-repetitions", type=int, default=3)
    parser.add_argument("--cold-repetitions", type=int, default=21)
    parser.add_argument("--warm-repetitions", type=int, default=101)
    parser.add_argument("--output", type=Path, default=RAW_ROOT / "round_a_results.json")
    args = parser.parse_args(argv)

    if sys.version_info[:2] != (3, 12):
        raise SystemExit("The frozen protocol requires CPython 3.12 for the harness and Python contender")
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    case_document = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    if protocol["protocol_id"] != case_document["protocol_id"]:
        raise SystemExit("protocol and cases IDs differ")
    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    RAW_ROOT.mkdir(parents=True, exist_ok=True)

    result: dict[str, Any] = {
        "schema_version": 1,
        "protocol_id": protocol["protocol_id"],
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "host": protocol["hardware"],
        "toolchains_observed": {
            "python": command_version([sys.executable, "--version"]),
            "dotnet": command_version(["dotnet", "--version"]),
            "rustc": command_version([str(Path.home() / ".cargo" / "bin" / "rustc.exe"), "--version"]),
            "cargo": command_version([str(Path.home() / ".cargo" / "bin" / "cargo.exe"), "--version"]),
        },
        "environment_allowlist": {
            key: os.environ.get(key)
            for key in ("OS", "PROCESSOR_ARCHITECTURE", "NUMBER_OF_PROCESSORS", "PYTHONUTF8")
        },
        "protocol_sha256": sha256_file(PROTOCOL_PATH),
        "cases_sha256": sha256_file(CASES_PATH),
        "harness_sha256": sha256_file(Path(__file__)),
        "git_commit": command_version(["git", "rev-parse", "HEAD"]),
        "ambient_before": ambient_snapshot(),
        "contenders": {},
    }
    for contender in contenders():
        build = None if args.skip_build else build_contender(contender)
        if build is not None and build["exit_code"] != 0:
            result["contenders"][contender.contender_id] = {"build": build, "fatal": "build_failed"}
            continue
        if build is None:
            build = build_contender(contender)
        functional = [
            functional_run(contender, case_document["cases"], repetition)
            for repetition in range(1, args.functional_repetitions + 1)
        ]
        result["contenders"][contender.contender_id] = {
            "build": build,
            "functional": functional,
            "cold_start": cold_start_run(contender, args.cold_repetitions),
            "warm": warm_run(contender, args.warm_repetitions),
        }
    result["ambient_after"] = ambient_snapshot()
    result["finished_utc"] = datetime.now(timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
