from __future__ import annotations

import os
from pathlib import Path

import main as development_entrypoint


def _write(root: Path, relative: str, content: str = "content") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path.resolve()


def test_source_files_are_limited_to_the_active_build_closure(
    tmp_path: Path,
) -> None:
    included_relatives = (
        "Directory.Build.props",
        "Directory.Build.targets",
        "Directory.Packages.props",
        "global.json",
        "src/Baxy.App/App.xaml",
        "src/Baxy.App/Assets/field-native-bridge.js",
        "src/Baxy.Core/Program.cs",
        "src/Baxy.Contracts/Protocol.cs",
        "src/Baxy.Kernel/Mission.cs",
        "src/Baxy.Providers.Windows/External/Action.ps1",
        "src/Baxy.Security.Windows/Protection.cs",
        "src/Baxy.FieldUi/dist/index.html",
        "src/Baxy.FieldUi/dist/assets/app.js",
    )
    excluded_relatives = (
        "README.md",
        "src/Baxy.App/bin/Release/Baxy.exe",
        "src/Baxy.App/node_modules/library/index.js",
        "src/Baxy.Core/obj/project.assets.json",
        "src/Baxy.FieldUi/node_modules/library/index.js",
        "src/Baxy.FieldUi/src/App.tsx",
        "src/Baxy.Setup/Program.cs",
        "src/baxy_mind/router.py",
        "src/Unreferenced.Project/Other.cs",
    )
    included = {_write(tmp_path, relative) for relative in included_relatives}
    for relative in excluded_relatives:
        _write(tmp_path, relative)

    assert set(development_entrypoint.source_files(tmp_path)) == included


def test_source_fingerprint_changes_only_for_active_build_inputs(
    tmp_path: Path,
) -> None:
    included = _write(tmp_path, "src/Baxy.Core/Program.cs", "first")
    excluded = _write(tmp_path, "src/baxy_mind/router.py", "first")
    initial = development_entrypoint.source_fingerprint(tmp_path)

    excluded.write_text("second", encoding="utf-8")
    assert development_entrypoint.source_fingerprint(tmp_path) == initial

    included.write_text("second", encoding="utf-8")
    assert development_entrypoint.source_fingerprint(tmp_path) != initial


def test_directory_prefix_does_not_match_a_sibling_with_the_same_prefix(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    child = root / "src" / "Baxy.App" / "Baxy.exe"
    sibling = tmp_path / "source-other" / "src" / "Baxy.App" / "Baxy.exe"
    prefix = os.path.normcase(development_entrypoint.directory_prefix(root))

    assert os.path.normcase(os.path.abspath(child)).startswith(prefix)
    assert not os.path.normcase(os.path.abspath(sibling)).startswith(prefix)


def test_dotnet_runtime_environment_is_scoped_to_the_child(
    monkeypatch,
    tmp_path: Path,
) -> None:
    dotnet = _write(tmp_path, ".dotnet/dotnet.exe")
    monkeypatch.setenv("DOTNET_ROOT", "persisted-root")
    monkeypatch.setenv("DOTNET_ROOT_X64", "persisted-x64-root")

    environment = development_entrypoint.environment_for_dotnet(str(dotnet))

    assert environment["DOTNET_ROOT"] == str(dotnet.parent)
    assert environment["DOTNET_ROOT_X64"] == str(dotnet.parent)
    assert os.environ["DOTNET_ROOT"] == "persisted-root"
    assert os.environ["DOTNET_ROOT_X64"] == "persisted-x64-root"


def test_launch_passes_the_private_dotnet_runtime_only_to_baxy(
    monkeypatch,
    tmp_path: Path,
) -> None:
    dotnet = _write(tmp_path, ".dotnet/dotnet.exe")
    observed: dict[str, object] = {}
    monkeypatch.setattr(
        development_entrypoint,
        "dotnet_executable",
        lambda: str(dotnet),
    )

    def capture(
        command: list[str],
        *,
        environment: dict[str, str] | None = None,
    ) -> None:
        observed["command"] = command
        observed["environment"] = environment

    monkeypatch.setattr(development_entrypoint, "run_checked", capture)

    development_entrypoint.launch(cpu=True, without_mind=True)

    command = observed["command"]
    environment = observed["environment"]
    assert isinstance(command, list)
    assert command[-2:] == ["-Cpu", "-SinMente"]
    assert isinstance(environment, dict)
    assert environment["DOTNET_ROOT"] == str(dotnet.parent)
    assert environment["DOTNET_ROOT_X64"] == str(dotnet.parent)
