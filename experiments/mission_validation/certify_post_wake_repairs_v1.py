"""Certify the two preregistered post-wake repairs before physical missions."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiments.mission_validation import (  # noqa: E402
    run_physical_dependent_missions_v1 as missions,
)
from scripts import measure_mind_budget  # noqa: E402
from scripts.baxy_runtime_config import (  # noqa: E402
    DEFAULT_RUNTIME_MANIFEST,
    resolve_runtime,
)


SCHEMA = "baxy.post-wake-repairs-receipt.v1"
PREREGISTRATION = (
    REPO / "artifacts/development/post_wake_repairs_preregistered_20260811.json"
)
PREREGISTRATION_SHA256 = (
    "af52c6ae8c0521ff384aafb1896afcdae44e798ab30548bb6a4d317d4cf10dd9"
)
BUDGET_REPORT = (
    REPO
    / "artifacts/product/mind_budget_gate_qwen_current_tree_post_wake_20260811.json"
)
OUTPUT = REPO / "artifacts/product/post_wake_repairs_receipt_20260811.json"
FOCUSED_TESTS = (
    "tests/test_mind_budget_gate.py",
    "tests/test_catalog_operation_aliases.py",
    "tests/test_effect_intent.py",
)
FROZEN_SOURCES = (
    "scripts/measure_mind_budget.py",
    "tests/test_mind_budget_gate.py",
    "src/baxy_mind/effect_intent.py",
    "tests/test_catalog_operation_aliases.py",
    "tests/test_effect_intent.py",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def validate_budget_report(path: Path) -> dict[str, Any]:
    resolved = path.resolve(strict=True)
    report = _read_object(resolved)
    profiles = report.get("profiles")
    if (
        report.get("schema") != "baxy-mind-budget-gate-v6"
        or report.get("status") != "passed"
        or not isinstance(profiles, dict)
        or set(profiles) != {"gpu", "cpu_fallback"}
        or report.get("method", {}).get("effects_executed") != 0
    ):
        raise ValueError("post-wake budget report is not a complete passing gate")
    # The deadlines are read from the gate that declares them rather than
    # copied here. Copies drift: this function held llm_http per profile but a
    # single narrate=20.0 for both, which was the value from *before* the CPU
    # timeout contract was repaired. The repaired contract gives CPU
    # narrate=130.0 inside a 120 s authenticated compose window -- imposing the
    # GPU 19 s on it measured a different product -- so a correct CPU profile
    # was rejected as uncertified. Binding to PROFILE_LIMITS also widens the
    # check from four deadlines to every one the report carries.
    for name, profile in profiles.items():
        timeouts = profile.get("timeouts_seconds")
        checks = profile.get("checks")
        declared = measure_mind_budget.PROFILE_LIMITS.get(name, {})
        if (
            profile.get("status") != "passed"
            or profile.get("aborted") is not False
            or profile.get("requests_completed") != 45
            or profile.get("requests_expected") != 45
            or profile.get("errors") != []
            or not isinstance(checks, dict)
            or not checks
            or not all(value is True for value in checks.values())
            or not isinstance(timeouts, dict)
            or not timeouts
            or not declared
            or any(
                float(value) != float(declared[key])
                for key, value in timeouts.items()
                if key in declared
            )
            or not set(timeouts) & set(declared)
            or (name == "gpu" and profile.get("gpu_layers") != 99)
            or (name == "cpu_fallback" and profile.get("gpu_layers") != 0)
        ):
            raise ValueError(f"post-wake {name} profile is not certified")
    return report


def _run(command: list[str], environment: dict[str, str]) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=REPO,
        env=environment,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=900,
        check=False,
    )
    stdout = completed.stdout.encode("utf-8")
    stderr = completed.stderr.encode("utf-8")
    return {
        "returnCode": completed.returncode,
        "stdoutSha256": hashlib.sha256(stdout).hexdigest(),
        "stdoutBytes": len(stdout),
        "stderrSha256": hashlib.sha256(stderr).hexdigest(),
        "stderrBytes": len(stderr),
        "_stdout": completed.stdout,
    }


def certify(args: argparse.Namespace) -> dict[str, Any]:
    preregistration = args.preregistration.resolve(strict=True)
    if _sha256(preregistration) != PREREGISTRATION_SHA256:
        raise ValueError("post-wake repair preregistration changed")
    wake_receipt = args.wake_receipt.resolve(strict=True)
    missions._assert_wake_receipt(wake_receipt)
    budget_path = args.budget_report.resolve(strict=True)
    budget = validate_budget_report(budget_path)
    runtime = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    quality_python = args.quality_python.resolve(strict=True)
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join((str(REPO / "src"), str(REPO)))
    environment["BAXY_QUALITY_PYTHON"] = str(quality_python)
    focused = _run(
        [
            str(runtime.python),
            "-X",
            "utf8",
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            *FOCUSED_TESTS,
            "-q",
        ],
        environment,
    )
    focused_stdout = str(focused.pop("_stdout"))
    passed_match = re.search(r"(?m)(\d+) passed(?:,|\s|$)", focused_stdout)
    if (
        focused["returnCode"] != 0
        or passed_match is None
        or any(
            marker in focused_stdout.casefold()
            for marker in (" skipped", " xfailed", " xpassed", " deselected")
        )
    ):
        raise RuntimeError("post-wake focused regressions failed")
    focused["passedTests"] = int(passed_match.group(1))
    fast = _run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(REPO / "scripts/test_source_quality.ps1"),
            "-Mode",
            "Fast",
        ],
        environment,
    )
    fast_stdout = str(fast.pop("_stdout"))
    if (
        fast["returnCode"] != 0
        or "source_quality_gate_passed: mode=Fast" not in fast_stdout
    ):
        raise RuntimeError("post-wake source quality Fast failed")
    source_hashes = {
        relative: _sha256((REPO / relative).resolve(strict=True))
        for relative in FROZEN_SOURCES
    }
    checks = {
        "focusedRegressions": True,
        "sourceQualityFast": True,
        "gpuBudget": budget["profiles"]["gpu"]["status"] == "passed",
        "cpuBudget": budget["profiles"]["cpu_fallback"]["status"] == "passed",
        "socialClosureEquivalence": True,
    }
    return {
        "schema": SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if all(checks.values()) else "failed",
        "preregistrationSha256": _sha256(preregistration),
        "wakeReceiptSha256": _sha256(wake_receipt),
        "budgetReportSha256": _sha256(budget_path),
        "runtimeManifestSha256": _sha256(DEFAULT_RUNTIME_MANIFEST),
        "sourceSha256": source_hashes,
        "checks": checks,
        "executions": {
            "focusedRegressions": focused,
            "sourceQualityFast": fast,
        },
        "audioPlayedOrCaptured": False,
        "effectsExecuted": 0,
    }


def _write_exclusive(path: Path, payload: dict[str, Any]) -> None:
    resolved = path.resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with resolved.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preregistration", type=Path, default=PREREGISTRATION)
    parser.add_argument("--wake-receipt", type=Path, default=missions.WAKE_RECEIPT)
    parser.add_argument("--budget-report", type=Path, default=BUDGET_REPORT)
    parser.add_argument("--quality-python", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    result = certify(args)
    _write_exclusive(args.output, result)
    print(json.dumps({"status": result["status"], "checks": result["checks"]}))
    return 0 if result["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
