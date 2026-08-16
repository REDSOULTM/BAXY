from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
COMMON = SCRIPTS / "python_runtime_common.ps1"
LOCKER = SCRIPTS / "lock_python_dependencies.ps1"
REGISTER = SCRIPTS / "register_mind_runtime.ps1"
SETUP = SCRIPTS / "setup_mind_voice.ps1"
POWERSHELL = shutil.which("powershell")


def _powershell_literal(value: str | Path) -> str:
    return str(value).replace("'", "''")


def test_runtime_scripts_share_one_resolver_without_experimental_defaults() -> None:
    locker = LOCKER.read_text(encoding="utf-8")
    register = REGISTER.read_text(encoding="utf-8")
    setup = SETUP.read_text(encoding="utf-8")

    for source in (locker, register, setup):
        assert "python_runtime_common.ps1" in source
        assert "experiments\\mind_router_spike" not in source
    assert "Resolve-BaxyRuntimePython" in locker
    assert "Resolve-BaxyRuntimePython" in register
    assert "Resolve-BaxyRuntimePython" in setup


def test_setup_installs_only_the_hash_locked_product_graph() -> None:
    source = SETUP.read_text(encoding="utf-8")

    assert "pylock.runtime-win-x64.toml" in source
    assert "'--only-binary=:all:'" in source
    assert "'--require-hashes'" in source
    assert "'--no-deps'" in source
    assert "requirements-voice.txt" not in source
    assert source.count("Assert-BaxyRuntimeLock") == 2
    assert "-StructureOnly" in source


def test_registration_refuses_an_unverified_runtime_graph() -> None:
    source = REGISTER.read_text(encoding="utf-8")

    assert "Resolve-BaxyRuntimePython" in source
    assert "Assert-BaxyRuntimeLock" in source
    assert "mind_runtime_registration_failed" in source


def test_registration_prefers_the_promoted_cascade_with_direct_wake_fallback() -> None:
    source = REGISTER.read_text(encoding="utf-8")

    cascade = "Resolve-BaxyAsset -Name 'wake_cascade_manifest'"
    direct = "Resolve-BaxyAsset -Name 'wake_manifest'"
    assert cascade in source
    assert direct in source
    assert source.index(cascade) < source.index(direct)


def test_runtime_manifest_accepts_json_integral_gpu_layers_without_widening_range() -> (
    None
):
    source = (SCRIPTS / "mind_runtime_manifest.ps1").read_text(encoding="utf-8")

    # PowerShell deserializes JSON numeric literals as Int64.  The registered
    # runtime must accept that representation, but not fractional/out-of-range
    # values that would make the GPU profile ambiguous.
    assert "$runtime.ngl -isnot [long]" in source
    assert "[long]$runtime.ngl -lt 0" in source
    assert "[long]$runtime.ngl -gt 999" in source


@pytest.mark.skipif(POWERSHELL is None, reason="Windows PowerShell is unavailable")
def test_shared_runtime_resolver_accepts_only_the_registered_schema(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "mind-runtime-v1.json"
    manifest.write_text(
        json.dumps(
            {
                "schema": "baxy-mind-runtime-v1",
                "python": sys.executable,
            }
        ),
        encoding="utf-8",
    )
    common = _powershell_literal(COMMON)
    manifest_literal = _powershell_literal(manifest)
    completed = subprocess.run(
        [
            POWERSHELL,
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            (
                f". '{common}'; "
                "$value = Resolve-BaxyRuntimePython "
                "-Candidate '' "
                f"-ManifestPath '{manifest_literal}' "
                "-FailurePrefix 'runtime_test_failed'; "
                "Write-Output $value"
            ),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr
    assert Path(completed.stdout.strip()).resolve() == Path(sys.executable).resolve()

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["schema"] = "untrusted-schema"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    rejected = subprocess.run(
        [
            POWERSHELL,
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            (
                f". '{common}'; "
                "try { Resolve-BaxyRuntimePython "
                "-Candidate '' "
                f"-ManifestPath '{manifest_literal}' "
                "-FailurePrefix 'runtime_test_failed'; exit 91 } "
                "catch { [Console]::Error.WriteLine($_.Exception.Message); exit 17 }"
            ),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )

    assert rejected.returncode == 17
    assert rejected.stderr.strip() == "runtime_test_failed: runtime_manifest_schema"
