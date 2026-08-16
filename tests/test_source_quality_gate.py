"""Fail-closed contracts for the source-quality PowerShell gate."""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts" / "test_source_quality.ps1"
QUALITY_REQUIREMENTS = ROOT / "requirements-quality.txt"
QUALITY_LOCK = ROOT / "requirements-quality-win-x64.lock.txt"
POWERSHELL = shutil.which("powershell")


def _powershell_literal(path: Path) -> str:
    return str(path).replace("'", "''")


def _run_powershell_source_health(
    scripts_root: Path,
) -> subprocess.CompletedProcess[str]:
    gate_literal = _powershell_literal(GATE)
    scripts_literal = _powershell_literal(scripts_root)
    return subprocess.run(
        [
            POWERSHELL,
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            (
                f". '{gate_literal}'; "
                f"Assert-PowerShellSourceHealth -ScriptsRoot '{scripts_literal}'"
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


def _run_source_quality_dry_run(mode: str) -> dict:
    gate_literal = _powershell_literal(GATE)
    command = f"""
. '{gate_literal}' -Mode '{mode}'
$global:QualityCalls = New-Object 'Collections.Generic.List[object]'
$global:PowerShellSourceChecks = 0
function Invoke-SourceQualityPreflight {{
    return [pscustomobject]@{{
        Quality = [pscustomobject]@{{
            Path = 'quality-python.exe'
            PythonVersion = '3.12'
            RuffVersion = 'ruff fixture'
        }}
        Dotnet = [pscustomobject]@{{
            Path = 'C:\\fixture-dotnet\\dotnet.exe'
            Version = '10.0.100'
        }}
        FieldUi = [pscustomobject]@{{
            Root = 'C:\\fixture-field-ui'
            Eslint = 'eslint.cmd'
            EslintVersion = 'fixture-eslint'
            TypeScript = 'tsc.cmd'
            TypeScriptVersion = 'fixture-tsc'
        }}
        Runtime = [pscustomobject]@{{
            Path = 'runtime-python.exe'
            Version = '3.12'
        }}
    }}
}}
function Assert-PowerShellSourceHealth {{
    param([string]$ScriptsRoot)
    $global:PowerShellSourceChecks += 1
}}
function Invoke-Checked {{
    param(
        [string]$Stage,
        [string]$Executable,
        [string[]]$Arguments,
        [string]$WorkingDirectory
    )
    $global:QualityCalls.Add([pscustomobject]@{{
            stage = $Stage
            executable = $Executable
            arguments = @($Arguments)
            working_directory = $WorkingDirectory
        }})
}}
Invoke-SourceQualityGate | Out-Null
[pscustomobject]@{{
    powershell_source_checks = $global:PowerShellSourceChecks
    calls = $global:QualityCalls.ToArray()
}} | ConvertTo-Json -Depth 6 -Compress
"""
    completed = subprocess.run(
        [
            POWERSHELL,
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            command,
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
    return json.loads(completed.stdout.strip().splitlines()[-1])


def test_source_quality_gate_prohibits_mutating_tool_commands() -> None:
    source = GATE.read_text(encoding="utf-8")

    assert "pip install" not in source
    assert "pnpm install" not in source
    assert "vite build" not in source


@pytest.mark.skipif(POWERSHELL is None, reason="Windows PowerShell is unavailable")
@pytest.mark.parametrize("mode", ["Fast", "Full"])
def test_source_quality_gate_dispatches_non_mutating_checks(mode: str) -> None:
    result = _run_source_quality_dry_run(mode)
    calls = {call["stage"]: call for call in result["calls"]}
    expected_stages = {
        "python-ruff",
        "python-compileall",
        "field-ui-eslint",
        "field-ui-tsc-app",
        "field-ui-tsc-node",
        "dotnet-format",
        "dotnet-build-release",
    }
    if mode == "Full":
        expected_stages.update({"dotnet-tests", "python-tests"})

    assert result["powershell_source_checks"] == 1
    assert set(calls) == expected_stages
    assert "--no-cache" in calls["python-ruff"]["arguments"]
    assert any(
        argument.endswith("experiments\\mind_llm_tournament")
        for argument in calls["python-ruff"]["arguments"]
    )
    assert any(
        argument.endswith("experiments\\mind_router_spike")
        for argument in calls["python-ruff"]["arguments"]
    )
    assert "--max-warnings" in calls["field-ui-eslint"]["arguments"]
    for stage in ("field-ui-tsc-app", "field-ui-tsc-node"):
        arguments = calls[stage]["arguments"]
        assert arguments[arguments.index("--incremental") + 1] == "false"
    assert "--verify-no-changes" in calls["dotnet-format"]["arguments"]
    assert "--no-restore" in calls["dotnet-format"]["arguments"]
    assert "--no-restore" in calls["dotnet-build-release"]["arguments"]
    if mode == "Full":
        assert "--no-build" in calls["dotnet-tests"]["arguments"]
        assert "-m:1" in calls["dotnet-tests"]["arguments"]
        assert "no:cacheprovider" in calls["python-tests"]["arguments"]


@pytest.mark.skipif(POWERSHELL is None, reason="Windows PowerShell is unavailable")
def test_powershell_source_health_rejects_parse_errors_and_unused_functions(
    tmp_path: Path,
) -> None:
    scripts_root = tmp_path / "scripts"
    scripts_root.mkdir()
    used_script = scripts_root / "used.ps1"
    unused_script = scripts_root / "unused.ps1"
    library_script = scripts_root / "library.ps1"
    consumer_script = scripts_root / "consumer.ps1"
    used_script.write_text(
        "function Invoke-DuplicateHelper { return 1 }\nInvoke-DuplicateHelper\n",
        encoding="utf-8",
    )
    unused_script.write_text(
        "function Invoke-DuplicateHelper { return 2 }\n",
        encoding="utf-8",
    )
    library_script.write_text(
        "function Invoke-LibraryHelper { return 3 }\n",
        encoding="utf-8",
    )
    consumer_script.write_text(
        ". (Join-Path $PSScriptRoot 'library.ps1')\nInvoke-LibraryHelper\n",
        encoding="utf-8",
    )

    unused = _run_powershell_source_health(scripts_root)

    assert unused.returncode != 0
    assert "powershell-unused-function" in unused.stderr
    assert "unused.ps1" in unused.stderr
    assert "Invoke-DuplicateHelper" in unused.stderr
    assert "Invoke-LibraryHelper" not in unused.stderr

    unused_script.write_text(
        (
            "function Invoke-DuplicateHelper { return 2 }\n"
            "Invoke-DuplicateHelper\n"
        ),
        encoding="utf-8",
    )
    valid = _run_powershell_source_health(scripts_root)
    assert valid.returncode == 0, valid.stderr

    unused_script.write_text(
        "function Invoke-BrokenHelper {\n",
        encoding="utf-8",
    )
    invalid = _run_powershell_source_health(scripts_root)
    assert invalid.returncode != 0
    assert "powershell-parse" in invalid.stderr


@pytest.mark.skipif(POWERSHELL is None, reason="Windows PowerShell is unavailable")
def test_source_quality_accepts_the_current_locked_runtime() -> None:
    gate_literal = _powershell_literal(GATE)
    python_literal = _powershell_literal(Path(sys.executable))
    completed = subprocess.run(
        [
            POWERSHELL,
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            (
                f". '{gate_literal}'; "
                f"Assert-RuntimePythonLocks -Python '{python_literal}'; "
                "Write-Output 'runtime-locks-ok'"
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
    assert completed.stdout.strip() == "runtime-locks-ok"


def test_quality_lock_matches_the_declared_ruff_version() -> None:
    requirements = QUALITY_REQUIREMENTS.read_text(encoding="utf-8")
    lock = QUALITY_LOCK.read_text(encoding="utf-8")
    version = re.search(r"(?m)^ruff==(\d+\.\d+\.\d+)$", requirements)

    assert version is not None
    assert "--only-binary=:all:" in lock
    assert "--require-hashes" in lock
    assert f"ruff=={version.group(1)} \\" in lock
    assert re.findall(r"--hash=sha256:([0-9a-f]{64})", lock) == [
        "9be63ba1eb936acd2d1342fb8337c356353706fce233b2a15a09a97037e6acde"
    ]


@pytest.mark.skipif(POWERSHELL is None, reason="Windows PowerShell is unavailable")
def test_source_quality_gate_fails_closed_before_work_for_missing_python(
    tmp_path: Path,
) -> None:
    missing_python = tmp_path / "missing-quality-python.exe"
    completed = subprocess.run(
        [
            POWERSHELL,
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(GATE),
            "-Mode",
            "Fast",
            "-QualityPython",
            str(missing_python),
            "-PreflightOnly",
        ],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )

    assert completed.returncode == 1
    assert "source_quality_preflight_failed: quality_python_missing" in (
        completed.stderr
    )
    assert "source_quality_stage_started:" not in completed.stdout
    assert "CategoryInfo" not in completed.stderr


@pytest.mark.skipif(POWERSHELL is None, reason="Windows PowerShell is unavailable")
@pytest.mark.parametrize(
    ("supplied", "expected"),
    [("fast", "Fast"), ("FAST", "Fast"), ("full", "Full"), ("FULL", "Full")],
)
def test_source_quality_mode_is_canonicalized(
    supplied: str,
    expected: str,
) -> None:
    gate_literal = _powershell_literal(GATE)
    completed = subprocess.run(
        [
            POWERSHELL,
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            f". '{gate_literal}' -Mode {supplied}; Write-Output $Mode",
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
    assert completed.stdout.strip() == expected


@pytest.mark.skipif(POWERSHELL is None, reason="Windows PowerShell is unavailable")
def test_temporary_python_cache_is_removed_and_environment_restored() -> None:
    gate_literal = _powershell_literal(GATE)
    command = f"""
. '{gate_literal}'
[Environment]::SetEnvironmentVariable(
    'PYTHONPYCACHEPREFIX',
    'source-quality-test-sentinel',
    [EnvironmentVariableTarget]::Process)
$global:ObservedSourceQualityCache = $null
try {{
    Invoke-WithTemporaryPythonCache {{
        $global:ObservedSourceQualityCache =
            [Environment]::GetEnvironmentVariable(
                'PYTHONPYCACHEPREFIX',
                [EnvironmentVariableTarget]::Process)
        [IO.File]::WriteAllText(
            (Join-Path $global:ObservedSourceQualityCache 'probe.pyc'),
            'probe')
        throw 'expected-source-quality-action-failure'
    }}
    exit 91
}} catch {{
    if ($_.Exception.Message -cne 'expected-source-quality-action-failure') {{
        [Console]::Error.WriteLine($_.Exception.Message)
        exit 92
    }}
}}
$restored = [Environment]::GetEnvironmentVariable(
    'PYTHONPYCACHEPREFIX',
    [EnvironmentVariableTarget]::Process)
if ($restored -cne 'source-quality-test-sentinel') {{
    [Console]::Error.WriteLine('environment-not-restored')
    exit 93
}}
if ([string]::IsNullOrWhiteSpace($global:ObservedSourceQualityCache)) {{
    [Console]::Error.WriteLine('temporary-cache-not-observed')
    exit 94
}}
if (Test-Path -LiteralPath $global:ObservedSourceQualityCache) {{
    [Console]::Error.WriteLine('temporary-cache-not-removed')
    exit 95
}}
Write-Output 'source-quality-cleanup-ok'
"""
    completed = subprocess.run(
        [
            POWERSHELL,
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            command,
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
    assert "source-quality-cleanup-ok" in completed.stdout


@pytest.mark.skipif(POWERSHELL is None, reason="Windows PowerShell is unavailable")
def test_dotnet_environment_is_scoped_and_restored_after_failure() -> None:
    gate_literal = _powershell_literal(GATE)
    command = f"""
. '{gate_literal}'
$originalRoot = [Environment]::GetEnvironmentVariable(
    'DOTNET_ROOT',
    [EnvironmentVariableTarget]::Process)
$originalRootX64 = [Environment]::GetEnvironmentVariable(
    'DOTNET_ROOT_X64',
    [EnvironmentVariableTarget]::Process)
$originalPath = [Environment]::GetEnvironmentVariable(
    'PATH',
    [EnvironmentVariableTarget]::Process)
$fakeDotnet = Join-Path $env:TEMP 'baxy-quality-dotnet\\dotnet.exe'
try {{
    Invoke-WithDotnetEnvironment -DotnetPath $fakeDotnet -Action {{
        $expectedRoot = Split-Path -Parent $fakeDotnet
        if ($env:DOTNET_ROOT -cne $expectedRoot -or
            $env:DOTNET_ROOT_X64 -cne $expectedRoot -or
            -not $env:PATH.StartsWith(
                $expectedRoot + [IO.Path]::PathSeparator,
                [StringComparison]::OrdinalIgnoreCase)) {{
            throw 'dotnet-environment-not-scoped'
        }}
        throw 'expected-dotnet-action-failure'
    }}
    exit 91
}} catch {{
    if ($_.Exception.Message -cne 'expected-dotnet-action-failure') {{
        [Console]::Error.WriteLine($_.Exception.Message)
        exit 92
    }}
}}
if ($env:DOTNET_ROOT -cne $originalRoot -or
    $env:DOTNET_ROOT_X64 -cne $originalRootX64 -or
    $env:PATH -cne $originalPath) {{
    [Console]::Error.WriteLine('dotnet-environment-not-restored')
    exit 93
}}
Write-Output 'dotnet-environment-cleanup-ok'
"""
    completed = subprocess.run(
        [
            POWERSHELL,
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            command,
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
    assert "dotnet-environment-cleanup-ok" in completed.stdout
