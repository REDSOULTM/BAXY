"""Resolve BAXY's development build outputs from the MSBuild contract."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import xml.etree.ElementTree as ET
import xml.parsers.expat
from dataclasses import asdict, dataclass
from pathlib import Path


_SAFE_SEGMENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
_WINDOWS_RESERVED_NAMES = frozenset(
    {
        "AUX",
        "CON",
        "NUL",
        "PRN",
        *(f"COM{index}" for index in range(1, 10)),
        *(f"LPT{index}" for index in range(1, 10)),
    }
)
_MAXIMUM_PROPS_BYTES = 1024 * 1024


class BuildLayoutError(ValueError):
    """The repository build layout is absent, ambiguous, or unsafe."""


@dataclass(frozen=True)
class BuildLayout:
    default_target_framework: str
    windows_target_framework: str
    runtime_identifier: str
    development_configuration: str

    def app_executable(self, repository: Path) -> Path:
        return self._framework_output(repository, "Baxy.App") / "Baxy.exe"

    def core_executable(self, repository: Path) -> Path:
        return self._framework_output(repository, "Baxy.Core") / "baxy-core.exe"

    def core_publish_executable(self, repository: Path) -> Path:
        return (
            self._framework_output(repository, "Baxy.Core")
            / self.runtime_identifier
            / "publish"
            / "baxy-core.exe"
        )

    def _framework_output(self, repository: Path, project: str) -> Path:
        return (
            Path(repository)
            / "src"
            / project
            / "bin"
            / self.development_configuration
            / self.windows_target_framework
        )


def _is_safe_windows_segment(value: str) -> bool:
    if not _SAFE_SEGMENT.fullmatch(value) or value.endswith("."):
        return False
    return value.split(".", 1)[0].upper() not in _WINDOWS_RESERVED_NAMES


def _required_property(document: ET.ElementTree, name: str) -> str:
    elements = document.findall(f"./PropertyGroup/{name}")
    if len(elements) != 1:
        raise BuildLayoutError(
            f"Directory.Build.props must define {name} exactly once."
        )
    value = (elements[0].text or "").strip()
    if not _is_safe_windows_segment(value):
        raise BuildLayoutError(
            f"Directory.Build.props contains an unsafe {name} value."
        )
    return value


def _validate_xml_declarations(payload: bytes) -> None:
    """Reject DTD/entity declarations before ElementTree expands anything."""

    parser = xml.parsers.expat.ParserCreate()

    def reject_declaration(*_args: object) -> None:
        raise BuildLayoutError(
            "Directory.Build.props must not contain DTD or entity declarations."
        )

    parser.StartDoctypeDeclHandler = reject_declaration
    parser.EntityDeclHandler = reject_declaration
    parser.ExternalEntityRefHandler = reject_declaration
    try:
        parser.Parse(payload, True)
    except xml.parsers.expat.ExpatError as error:
        raise BuildLayoutError("Directory.Build.props is not valid XML.") from error


def load_build_layout(repository: Path) -> BuildLayout:
    """Load the literal cross-language layout properties used by MSBuild."""

    props = Path(repository).resolve() / "Directory.Build.props"
    try:
        payload = props.read_bytes()
    except OSError as error:
        raise BuildLayoutError(
            f"Could not read the canonical build layout: {props}"
        ) from error
    if not payload or len(payload) > _MAXIMUM_PROPS_BYTES:
        raise BuildLayoutError(
            "Directory.Build.props has an invalid or excessive size."
        )
    _validate_xml_declarations(payload)
    try:
        document = ET.ElementTree(ET.fromstring(payload))
    except ET.ParseError as error:
        raise BuildLayoutError("Directory.Build.props is not valid XML.") from error
    if document.getroot().tag != "Project":
        raise BuildLayoutError("Directory.Build.props must have a Project root.")
    return BuildLayout(
        default_target_framework=_required_property(
            document, "BaxyDefaultTargetFramework"
        ),
        windows_target_framework=_required_property(
            document, "BaxyWindowsTargetFramework"
        ),
        runtime_identifier=_required_property(document, "BaxyRuntimeIdentifier"),
        development_configuration=_required_property(
            document, "BaxyDevelopmentConfiguration"
        ),
    )


def _read_msbuild_properties(
    dotnet: str,
    repository: Path,
    project: Path,
    *,
    configuration: str,
    runtime_identifier: str | None,
    names: tuple[str, ...],
) -> dict[str, str]:
    command = [
        dotnet,
        "msbuild",
        str(project),
        "-nologo",
        f"-p:Configuration={configuration}",
    ]
    if runtime_identifier is not None:
        command.append(f"-p:RuntimeIdentifier={runtime_identifier}")
    command.extend(f"-getProperty:{name}" for name in names)
    try:
        completed = subprocess.run(
            command,
            cwd=repository,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise BuildLayoutError(
            "Could not evaluate the MSBuild output layout."
        ) from error
    if completed.returncode != 0:
        raise BuildLayoutError("MSBuild rejected the canonical output layout.")
    start = completed.stdout.find("{")
    try:
        payload, _ = json.JSONDecoder().raw_decode(completed.stdout[start:])
        properties = payload["Properties"]
    except (KeyError, TypeError, ValueError) as error:
        raise BuildLayoutError("MSBuild returned an invalid output layout.") from error
    if not isinstance(properties, dict) or any(
        not isinstance(properties.get(name), str) for name in names
    ):
        raise BuildLayoutError("MSBuild omitted a required output property.")
    return properties


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(os.path.abspath(left)) == os.path.normcase(
        os.path.abspath(right)
    )


def validate_msbuild_outputs(
    dotnet: str,
    repository: Path,
    layout: BuildLayout,
) -> None:
    """Fail when evaluated project outputs diverge from the literal contract."""

    repository = Path(repository).resolve()
    app_project = repository / "src" / "Baxy.App" / "Baxy.App.csproj"
    core_project = repository / "src" / "Baxy.Core" / "Baxy.Core.csproj"
    common_names = (
        "TargetDir",
        "TargetFramework",
        "TargetName",
        "UseAppHost",
        "RuntimeIdentifier",
    )
    app = _read_msbuild_properties(
        dotnet,
        repository,
        app_project,
        configuration=layout.development_configuration,
        runtime_identifier=None,
        names=common_names,
    )
    core = _read_msbuild_properties(
        dotnet,
        repository,
        core_project,
        configuration=layout.development_configuration,
        runtime_identifier=None,
        names=common_names,
    )
    publish = _read_msbuild_properties(
        dotnet,
        repository,
        core_project,
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
    app_executable = Path(app["TargetDir"]) / f"{app['TargetName']}.exe"
    core_executable = Path(core["TargetDir"]) / f"{core['TargetName']}.exe"
    core_publish_executable = (
        Path(publish["ProjectDir"])
        / publish["PublishDir"]
        / f"{publish['TargetName']}.exe"
    )
    valid = (
        app["TargetFramework"] == layout.windows_target_framework
        and app["RuntimeIdentifier"] == ""
        and app["UseAppHost"].casefold() == "true"
        and _same_path(app_executable, layout.app_executable(repository))
        and core["TargetFramework"] == layout.windows_target_framework
        and core["RuntimeIdentifier"] == ""
        and core["UseAppHost"].casefold() == "true"
        and _same_path(core_executable, layout.core_executable(repository))
        and publish["TargetFramework"] == layout.windows_target_framework
        and publish["RuntimeIdentifier"] == layout.runtime_identifier
        and publish["PublishAot"].casefold() == "true"
        and _same_path(
            core_publish_executable,
            layout.core_publish_executable(repository),
        )
    )
    if not valid:
        raise BuildLayoutError(
            "The evaluated MSBuild outputs diverge from Directory.Build.props."
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Muestra el layout canónico de build de BAXY."
    )
    parser.add_argument(
        "--repository",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    args = parser.parse_args()
    print(
        json.dumps(
            asdict(load_build_layout(args.repository)),
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
