from __future__ import annotations

import json
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

import main as development_entrypoint
from scripts import build_layout as build_layout_module
from scripts.build_layout import (
    BuildLayout,
    BuildLayoutError,
    load_build_layout,
    validate_msbuild_outputs,
)


ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which("powershell.exe") or shutil.which("powershell")
WINDOWS_PROJECTS = {
    Path("src/Baxy.App/Baxy.App.csproj"),
    Path("src/Baxy.Core/Baxy.Core.csproj"),
    Path("src/Baxy.Providers.Windows/Baxy.Providers.Windows.csproj"),
    Path("src/Baxy.Security.Windows/Baxy.Security.Windows.csproj"),
    Path("src/Baxy.Setup/Baxy.Setup.csproj"),
    Path("tests/Baxy.Integration.Tests/Baxy.Integration.Tests.csproj"),
    Path("tests/Baxy.Providers.Windows.Tests/Baxy.Providers.Windows.Tests.csproj"),
    Path("tests/Baxy.Setup.Tests/Baxy.Setup.Tests.csproj"),
}


def _write_props(
    repository: Path,
    *,
    default_framework: str = "net12.0",
    windows_framework: str = "net12.0-windows10.0.99999.0",
    runtime: str = "win-arm64",
    configuration: str = "Debug",
) -> None:
    repository.mkdir(parents=True, exist_ok=True)
    (repository / "Directory.Build.props").write_text(
        (
            "<Project><PropertyGroup>"
            f"<BaxyDefaultTargetFramework>{default_framework}"
            "</BaxyDefaultTargetFramework>"
            f"<BaxyWindowsTargetFramework>{windows_framework}"
            "</BaxyWindowsTargetFramework>"
            f"<BaxyRuntimeIdentifier>{runtime}</BaxyRuntimeIdentifier>"
            f"<BaxyDevelopmentConfiguration>{configuration}"
            "</BaxyDevelopmentConfiguration>"
            "</PropertyGroup></Project>"
        ),
        encoding="utf-8",
    )


def _dotnet_executable() -> str:
    candidates = (
        Path.home() / ".dotnet" / "dotnet.exe",
        Path(shutil.which("dotnet") or ""),
    )
    for candidate in candidates:
        if not candidate.is_file():
            continue
        probe = subprocess.run(
            [str(candidate), "--version"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if probe.returncode == 0:
            return str(candidate)
    pytest.skip("A compatible .NET SDK is not available.")


def _powershell_literal(value: Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _run_powershell_layout(repository: Path) -> subprocess.CompletedProcess[str]:
    if POWERSHELL is None:
        pytest.skip("PowerShell is not available.")
    helper = ROOT / "scripts" / "build_layout.ps1"
    # powershell.exe -Command joins the remaining arguments with spaces and
    # reparses them, so positional paths split on any space in the repository
    # path. Quote them into the command instead.
    command = (
        f". {_powershell_literal(helper)}; "
        f"Get-BaxyBuildLayout -RepositoryRoot {_powershell_literal(repository)} "
        "| ConvertTo-Json -Compress"
    )
    return subprocess.run(
        [
            POWERSHELL,
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            command,
        ],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def _evaluated_msbuild_properties(
    dotnet: str,
    project: Path,
    *,
    configuration: str | None = None,
    runtime_identifier: str | None = None,
    names: tuple[str, ...] = ("TargetFramework", "RuntimeIdentifier"),
) -> dict[str, str]:
    command = [dotnet, "msbuild", str(project), "-nologo"]
    if configuration is not None:
        command.append(f"-p:Configuration={configuration}")
    if runtime_identifier is not None:
        command.append(f"-p:RuntimeIdentifier={runtime_identifier}")
    command.extend(f"-getProperty:{name}" for name in names)
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    start = completed.stdout.find("{")
    assert start >= 0, completed.stdout
    payload, _ = json.JSONDecoder().raw_decode(completed.stdout[start:])
    return payload["Properties"]


def test_current_launchers_use_the_canonical_build_outputs() -> None:
    layout = load_build_layout(ROOT)

    assert layout.default_target_framework == "net10.0"
    assert layout.windows_target_framework == "net10.0-windows10.0.19041.0"
    assert layout.runtime_identifier == "win-x64"
    assert layout.development_configuration == "Release"
    release = (
        ROOT / "src" / "Baxy.Core" / "bin" / "Release" / "net10.0-windows10.0.19041.0"
    )
    assert layout.app_executable(ROOT) == (
        ROOT
        / "src"
        / "Baxy.App"
        / "bin"
        / "Release"
        / "net10.0-windows10.0.19041.0"
        / "Baxy.exe"
    )
    assert layout.core_executable(ROOT) == release / "baxy-core.exe"
    assert layout.core_publish_executable(ROOT) == (
        release / "win-x64" / "publish" / "baxy-core.exe"
    )
    assert development_entrypoint.APP_EXE == layout.app_executable(ROOT)
    assert development_entrypoint.CORE_EXE == layout.core_publish_executable(ROOT)


def test_current_msbuild_outputs_match_the_canonical_layout() -> None:
    dotnet = _dotnet_executable()
    layout = load_build_layout(ROOT)
    app = _evaluated_msbuild_properties(
        dotnet,
        ROOT / "src" / "Baxy.App" / "Baxy.App.csproj",
        configuration=layout.development_configuration,
        names=(
            "TargetDir",
            "TargetFramework",
            "TargetName",
            "UseAppHost",
        ),
    )
    core = _evaluated_msbuild_properties(
        dotnet,
        ROOT / "src" / "Baxy.Core" / "Baxy.Core.csproj",
        configuration=layout.development_configuration,
        names=(
            "TargetDir",
            "TargetFramework",
            "TargetName",
            "UseAppHost",
        ),
    )
    publish = _evaluated_msbuild_properties(
        dotnet,
        ROOT / "src" / "Baxy.Core" / "Baxy.Core.csproj",
        configuration=layout.development_configuration,
        runtime_identifier=layout.runtime_identifier,
        names=(
            "ProjectDir",
            "PublishAot",
            "PublishDir",
            "RuntimeIdentifier",
            "TargetFramework",
            "TargetName",
        ),
    )

    assert app["TargetFramework"] == layout.windows_target_framework
    assert app["UseAppHost"].casefold() == "true"
    assert Path(app["TargetDir"]) / f"{app['TargetName']}.exe" == (
        layout.app_executable(ROOT)
    )
    assert core["TargetFramework"] == layout.windows_target_framework
    assert core["UseAppHost"].casefold() == "true"
    assert Path(core["TargetDir"]) / f"{core['TargetName']}.exe" == (
        layout.core_executable(ROOT)
    )
    assert publish["TargetFramework"] == layout.windows_target_framework
    assert publish["RuntimeIdentifier"] == layout.runtime_identifier
    assert publish["PublishAot"].casefold() == "true"
    assert Path(publish["ProjectDir"]) / publish[
        "PublishDir"
    ] / f"{publish['TargetName']}.exe" == layout.core_publish_executable(ROOT)
    validate_msbuild_outputs(dotnet, ROOT, layout)


def test_setup_build_contract_remains_independently_pinned() -> None:
    setup = ET.parse(ROOT / "src" / "Baxy.Setup" / "Baxy.Setup.csproj")
    setup_tests = ET.parse(
        ROOT / "tests" / "Baxy.Setup.Tests" / "Baxy.Setup.Tests.csproj"
    )

    assert setup.findtext("./PropertyGroup/TargetFramework") == (
        "net10.0-windows10.0.19041.0"
    )
    assert setup.findtext("./PropertyGroup/RuntimeIdentifier") == "win-x64"
    assert setup_tests.findtext("./PropertyGroup/TargetFramework") == (
        "net10.0-windows10.0.19041.0"
    )


def test_output_resolution_follows_a_changed_contract(tmp_path: Path) -> None:
    _write_props(tmp_path)

    layout = load_build_layout(tmp_path)

    assert layout.app_executable(tmp_path) == (
        tmp_path
        / "src"
        / "Baxy.App"
        / "bin"
        / "Debug"
        / "net12.0-windows10.0.99999.0"
        / "Baxy.exe"
    )
    assert layout.core_publish_executable(tmp_path) == (
        tmp_path
        / "src"
        / "Baxy.Core"
        / "bin"
        / "Debug"
        / "net12.0-windows10.0.99999.0"
        / "win-arm64"
        / "publish"
        / "baxy-core.exe"
    )


def test_msbuild_validation_rejects_an_executable_name_drift(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    layout = BuildLayout(
        default_target_framework="net12.0",
        windows_target_framework="net12.0-windows",
        runtime_identifier="win-arm64",
        development_configuration="Debug",
    )

    def fake_properties(
        _dotnet: str,
        _repository: Path,
        project: Path,
        *,
        configuration: str,
        runtime_identifier: str | None,
        names: tuple[str, ...],
    ) -> dict[str, str]:
        assert configuration == "Debug"
        if project.name == "Baxy.App.csproj":
            values = {
                "TargetDir": str(
                    tmp_path / "src" / "Baxy.App" / "bin" / "Debug" / "net12.0-windows"
                ),
                "TargetFramework": "net12.0-windows",
                "TargetName": "Unexpected",
                "UseAppHost": "true",
                "RuntimeIdentifier": "",
            }
        elif runtime_identifier is None:
            values = {
                "TargetDir": str(
                    tmp_path / "src" / "Baxy.Core" / "bin" / "Debug" / "net12.0-windows"
                ),
                "TargetFramework": "net12.0-windows",
                "TargetName": "baxy-core",
                "UseAppHost": "true",
                "RuntimeIdentifier": "",
            }
        else:
            values = {
                "ProjectDir": str(tmp_path / "src" / "Baxy.Core"),
                "PublishAot": "true",
                "PublishDir": str(
                    Path("bin") / "Debug" / "net12.0-windows" / "win-arm64" / "publish"
                ),
                "RuntimeIdentifier": "win-arm64",
                "TargetFramework": "net12.0-windows",
                "TargetName": "baxy-core",
            }
        return {name: values[name] for name in names}

    monkeypatch.setattr(
        build_layout_module,
        "_read_msbuild_properties",
        fake_properties,
    )

    with pytest.raises(BuildLayoutError, match="diverge"):
        validate_msbuild_outputs("dotnet", tmp_path, layout)


def test_development_build_does_not_record_missing_outputs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    state_directory = tmp_path / "state"
    events: list[str] = []
    monkeypatch.setattr(development_entrypoint, "APP_EXE", tmp_path / "missing-app.exe")
    monkeypatch.setattr(
        development_entrypoint,
        "CORE_EXE",
        tmp_path / "missing-core.exe",
    )
    monkeypatch.setattr(development_entrypoint, "STATE_DIRECTORY", state_directory)
    monkeypatch.setattr(
        development_entrypoint,
        "BUILD_STATE",
        state_directory / "source-build-v1.json",
    )
    monkeypatch.setattr(development_entrypoint, "source_fingerprint", lambda: "f" * 64)
    monkeypatch.setattr(development_entrypoint, "dotnet_executable", lambda: "dotnet")
    monkeypatch.setattr(
        development_entrypoint,
        "validate_msbuild_outputs",
        lambda *_args: events.append("validated"),
    )
    monkeypatch.setattr(
        development_entrypoint,
        "run_checked",
        lambda _command: events.append("built"),
    )

    with pytest.raises(RuntimeError, match="sin producir"):
        development_entrypoint.compile_if_needed(force=True)

    assert events == ["validated", "built", "built"]
    assert not development_entrypoint.BUILD_STATE.exists()


@pytest.mark.parametrize(
    ("property_name", "value"),
    (
        ("BaxyWindowsTargetFramework", "$(UnexpectedProperty)"),
        ("BaxyRuntimeIdentifier", "../win-x64"),
        ("BaxyDevelopmentConfiguration", "Release/other"),
        ("BaxyDevelopmentConfiguration", "Release."),
        ("BaxyDevelopmentConfiguration", "CON"),
        ("BaxyRuntimeIdentifier", "nul.json"),
        ("BaxyRuntimeIdentifier", "COM1"),
    ),
)
def test_layout_rejects_unresolved_or_unsafe_segments(
    tmp_path: Path,
    property_name: str,
    value: str,
) -> None:
    values = {
        "BaxyDefaultTargetFramework": "net10.0",
        "BaxyWindowsTargetFramework": "net10.0-windows",
        "BaxyRuntimeIdentifier": "win-x64",
        "BaxyDevelopmentConfiguration": "Release",
    }
    values[property_name] = value
    _write_props(
        tmp_path,
        default_framework=values["BaxyDefaultTargetFramework"],
        windows_framework=values["BaxyWindowsTargetFramework"],
        runtime=values["BaxyRuntimeIdentifier"],
        configuration=values["BaxyDevelopmentConfiguration"],
    )

    with pytest.raises(BuildLayoutError):
        load_build_layout(tmp_path)


def test_python_and_powershell_reject_dtd_entity_expansion(
    tmp_path: Path,
) -> None:
    (tmp_path / "Directory.Build.props").write_text(
        (
            '<!DOCTYPE Project [<!ENTITY tf "net10.0">]>'
            "<Project><PropertyGroup>"
            "<BaxyDefaultTargetFramework>&tf;</BaxyDefaultTargetFramework>"
            "<BaxyWindowsTargetFramework>net10.0-windows</BaxyWindowsTargetFramework>"
            "<BaxyRuntimeIdentifier>win-x64</BaxyRuntimeIdentifier>"
            "<BaxyDevelopmentConfiguration>Release</BaxyDevelopmentConfiguration>"
            "</PropertyGroup></Project>"
        ),
        encoding="utf-8",
    )

    with pytest.raises(BuildLayoutError):
        load_build_layout(tmp_path)
    completed = _run_powershell_layout(tmp_path)
    assert completed.returncode != 0


@pytest.mark.parametrize("unsafe_value", ("Release.", "CON", "nul.json", "COM1"))
def test_powershell_rejects_noncanonical_windows_segments(
    tmp_path: Path,
    unsafe_value: str,
) -> None:
    _write_props(tmp_path, configuration=unsafe_value)

    completed = _run_powershell_layout(tmp_path)

    assert completed.returncode != 0


@pytest.mark.parametrize(
    ("windows_framework", "runtime", "configuration", "expected_error"),
    (
        (
            "net10.0-windows10.0.99999.0",
            "win-x64",
            "Release",
            "certified only for net10.0-windows10.0.19041.0",
        ),
        (
            "net10.0-windows10.0.19041.0",
            "win-arm64",
            "Release",
            "certified only for win-x64",
        ),
        (
            "net10.0-windows10.0.19041.0",
            "win-x64",
            "Debug",
            "certified only for Release builds",
        ),
    ),
)
def test_gpu_gate_rejects_an_uncertified_layout_before_execution(
    tmp_path: Path,
    windows_framework: str,
    runtime: str,
    configuration: str,
    expected_error: str,
) -> None:
    if POWERSHELL is None:
        pytest.skip("PowerShell is not available.")
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in ("build_layout.ps1", "path_safety.ps1", "test_gpu_status.ps1"):
        shutil.copy2(ROOT / "scripts" / name, scripts / name)
    _write_props(
        tmp_path,
        windows_framework=windows_framework,
        runtime=runtime,
        configuration=configuration,
    )

    completed = subprocess.run(
        [
            POWERSHELL,
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(scripts / "test_gpu_status.ps1"),
        ],
        cwd=tmp_path,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )

    assert completed.returncode != 0
    assert expected_error in completed.stderr


def test_powershell_and_python_resolve_the_same_changed_layout(
    tmp_path: Path,
) -> None:
    _write_props(tmp_path)
    completed = _run_powershell_layout(tmp_path)

    assert completed.returncode == 0, completed.stderr
    powershell_layout = json.loads(completed.stdout)
    python_layout = load_build_layout(tmp_path)
    assert (
        powershell_layout["DefaultTargetFramework"]
        == python_layout.default_target_framework
    )
    assert (
        powershell_layout["WindowsTargetFramework"]
        == python_layout.windows_target_framework
    )
    assert powershell_layout["RuntimeIdentifier"] == python_layout.runtime_identifier
    assert Path(
        powershell_layout["CorePublishExecutable"]
    ) == python_layout.core_publish_executable(tmp_path)


def test_all_active_projects_evaluate_the_canonical_framework() -> None:
    dotnet = _dotnet_executable()
    layout = load_build_layout(ROOT)
    projects = sorted(
        (
            *ROOT.glob("src/**/*.csproj"),
            *ROOT.glob("tests/**/*.csproj"),
        ),
        key=lambda path: path.as_posix(),
    )

    for project in projects:
        properties = _evaluated_msbuild_properties(dotnet, project)
        relative = project.relative_to(ROOT)
        expected_framework = (
            layout.windows_target_framework
            if relative in WINDOWS_PROJECTS
            else layout.default_target_framework
        )
        assert properties["TargetFramework"] == expected_framework, relative
        expected_runtime = (
            layout.runtime_identifier
            if relative == Path("src/Baxy.Setup/Baxy.Setup.csproj")
            else ""
        )
        assert properties["RuntimeIdentifier"] == expected_runtime, relative
