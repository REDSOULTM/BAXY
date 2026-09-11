"""Time the existing packaging test's phases without editing product or deadlines."""
from __future__ import annotations

import ast
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/comprobaciones/C03/astra-packaging-phases718"
PRIVATE = Path(os.environ["LOCALAPPDATA"]) / "BAXY/C03-packaging-phases718-private"
OUT.mkdir(exist_ok=False)
PRIVATE.mkdir(exist_ok=False)
TEST = ROOT / "tests/test_product_packaging.py"
HELPER = ROOT / "scripts/product_build_common.ps1"
SAFETY = ROOT / "scripts/path_safety.ps1"


def save(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


spec = importlib.util.spec_from_file_location("packaging718", TEST)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
fixture = module.ProductPackagingTests()
fixture.setUp()
snapshot = fixture.sandbox / "head-snapshot"
assert snapshot.resolve().is_relative_to(module.BUILD_AREA.resolve())
assert fixture.sandbox.resolve().is_relative_to(module.BUILD_AREA.resolve())
node = next(item for item in ast.walk(ast.parse(TEST.read_text(encoding="utf-8")))
            if isinstance(item, ast.FunctionDef)
            and item.name == "test_detached_head_snapshot_is_exact_and_cleanup_removes_it")
assignment = next(item for item in node.body if isinstance(item, ast.Assign)
                  and any(isinstance(target, ast.Name) and target.id == "command" for target in item.targets))
command = eval(compile(ast.Expression(assignment.value), str(TEST), "eval"),
               {"ROOT": ROOT, "BUILD_AREA": module.BUILD_AREA, "snapshot": snapshot, "self": fixture})
helper = HELPER.read_text(encoding="utf-8")
start = helper.index("function New-BaxyHeadWorktreeSnapshot {")
end = helper.index("function Assert-BaxyNoAlternateDataStreams {", start)
segment = helper[start:end]
phases = [
    ("add", "        & git -C $repositoryFull worktree add --detach $snapshotFull $Commit | Out-Null"),
    ("chain", "        $null = Assert-ExistingPathChainHasNoReparsePoint -Path $snapshotFull"),
    ("tree", "        Assert-TreeHasNoReparsePoint -Root $snapshotFull"),
    ("rev", "        $snapshotCommit = ([string](& git -C $snapshotFull rev-parse --verify HEAD)).Trim().ToLowerInvariant()"),
    ("status", "        $snapshotStatus = @(& git -C $snapshotFull status --porcelain=v1 --untracked-files=all)"),
    ("remove", "    & git -C $repositoryFull worktree remove --force $snapshotFull | Out-Null"),
]
for label, line in phases:
    assert segment.count(line) == 1, label
    before = f"    [Console]::Error.WriteLine('PHASE {label}.begin ' + $script:phase718.Elapsed.TotalSeconds)"
    after = f"    [Console]::Error.WriteLine('PHASE {label}.end ' + $script:phase718.Elapsed.TotalSeconds)"
    segment = segment.replace(line, before + "\n" + line + "\n" + after)
helper = helper[:start] + segment + helper[end:]
instrumented = PRIVATE / "product_build_common.ps1"
instrumented.write_text(helper, encoding="utf-8")
old_import = f". '{HELPER}'"
assert command.count(old_import) == 1
command = command.replace(old_import, f". '{instrumented}'\n$script:phase718 = [Diagnostics.Stopwatch]::StartNew()")
command_file = PRIVATE / "probe.ps1"
command_file.write_text(command, encoding="utf-8")
pins = {str(path.relative_to(ROOT)): sha(path) for path in (TEST, HELPER, SAFETY)}
save(OUT / "PREREG.json", {
    "utc": dt.datetime.now(dt.timezone.utc).isoformat(), "source_hashes": pins,
    "commit": fixture.commit, "deadline_seconds": 45,
    "difference": "stderr phase timestamps only in a private helper copy; original test command and fixture",
    "snapshot": str(snapshot), "private_evidence": str(PRIVATE),
    "post_deadline": "record failure first, then permit at most 90 additional seconds for existing finally cleanup",
    "coverage_added": 0, "goal_complete": False,
})
started = time.monotonic()
deadline_passed = False
with (PRIVATE / "stdout.txt").open("wb") as stdout, (PRIVATE / "stderr.txt").open("wb") as stderr:
    process = subprocess.Popen(["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive",
                                "-ExecutionPolicy", "Bypass", "-File", str(command_file)],
                               cwd=fixture.sandbox, stdout=stdout, stderr=stderr)
    try:
        code = process.wait(timeout=45)
        deadline_passed = code == 0
    except subprocess.TimeoutExpired:
        save(OUT / "DEADLINE.json", {"elapsed": time.monotonic() - started,
                                    "phase_log": (PRIVATE / "stderr.txt").read_text(encoding="utf-8", errors="replace")[-6000:]})
        code = process.wait(timeout=90)
elapsed = time.monotonic() - started
unchanged = all(sha(ROOT / path) == value for path, value in pins.items())
phase_lines = [line for line in (PRIVATE / "stderr.txt").read_text(encoding="utf-8", errors="replace").splitlines()
               if line.startswith("PHASE ")]
save(OUT / "RESULT.json", {"utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                           "deadline_passed": deadline_passed, "exit_code": code, "elapsed_seconds": elapsed,
                           "phases": phase_lines, "snapshot_absent": not snapshot.exists(),
                           "sources_unchanged": unchanged, "coverage_added": 0, "goal_complete": False})
assert unchanged
assert code == 0 and not snapshot.exists(), "Probe requires guarded manual cleanup; inspect evidence"
# The original test cleans its synthetic fixture. Keep all destructive filesystem work
# in PowerShell, validate exact absolute roots, and reuse the existing fail-closed helper.
def quote(value: object) -> str:
    return "'" + str(value).replace("'", "''") + "'"

cleanup = (f"$ErrorActionPreference='Stop'\n. {quote(SAFETY)}\n"
           f"Remove-TreeFailClosed -AllowedRoot {quote(module.BUILD_AREA.resolve())} "
           f"-Target {quote(fixture.sandbox.resolve())}\n")
subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", cleanup],
               check=True, timeout=30, capture_output=True)
print(json.dumps({"deadline_passed": deadline_passed, "exit_code": code,
                  "elapsed_seconds": elapsed, "phases": phase_lines}))
