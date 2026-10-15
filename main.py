"""Punto de entrada único para desarrollar y ejecutar BAXY en Windows.

Uso normal:

    py main.py

La mente Python siempre se carga directamente desde ``src``. El host .NET se
recompila de forma incremental solo cuando cambió algún archivo que lo requiere.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from scripts.build_layout import load_build_layout, validate_msbuild_outputs


ROOT = Path(__file__).resolve().parent
BUILD_LAYOUT = load_build_layout(ROOT)
APP_PROJECT = ROOT / "src" / "Baxy.App" / "Baxy.App.csproj"
CORE_PROJECT = ROOT / "src" / "Baxy.Core" / "Baxy.Core.csproj"
APP_EXE = BUILD_LAYOUT.app_executable(ROOT)
CORE_EXE = BUILD_LAYOUT.core_publish_executable(ROOT)
RUN_SCRIPT = ROOT / "scripts" / "run_baxy.ps1"
STATE_DIRECTORY = Path(os.environ.get("LOCALAPPDATA", ROOT)) / "BAXY" / "development"
BUILD_STATE = STATE_DIRECTORY / "source-build-v1.json"

ACTIVE_DOTNET_PROJECT_ROOTS = (
    Path("src") / "Baxy.App",
    Path("src") / "Baxy.Core",
    Path("src") / "Baxy.Contracts",
    Path("src") / "Baxy.Kernel",
    Path("src") / "Baxy.Providers.Windows",
    Path("src") / "Baxy.Security.Windows",
)
RUNTIME_ASSET_ROOTS = (Path("src") / "Baxy.FieldUi" / "dist",)
EXPLICIT_BUILD_FILES = (
    Path("assets.manifest.json"),
    Path("global.json"),
    Path("src") / "Baxy.App" / "Assets" / "field-native-bridge.js",
)
IGNORED_BUILD_DIRECTORY_NAMES = frozenset({"bin", "node_modules", "obj"})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Lanza BAXY desde el código y recompila automáticamente solo cuando "
            "cambió la parte .NET."
        )
    )
    parser.add_argument(
        "--recompilar",
        action="store_true",
        help="fuerza una compilación aunque el código .NET no haya cambiado",
    )
    parser.add_argument(
        "--cpu",
        action="store_true",
        help="ejecuta el modelo en CPU en lugar de GPU",
    )
    parser.add_argument(
        "--sin-mente",
        action="store_true",
        help="lanza únicamente el cuerpo determinista",
    )
    parser.add_argument(
        "--conductor",
        action="store_true",
        help="arranca el runtime sin ventana y conduce la misma entrada de producto",
    )
    parser.add_argument("--profile", help="perfil persistente de datos del conductor")
    parser.add_argument("--capture", help="directorio de captura JSONL del conductor")
    parser.add_argument("--turns-file", help="JSONL de comandos públicos (text/session.new/upload/cancel)")
    parser.add_argument("--text", help="un turno de texto natural")
    parser.add_argument("--timeout-ms", type=int, default=120000)
    parser.add_argument(
        "--ui-probe",
        help="JSONL de turnos que la ventana teclea en su propio compositor",
    )
    parser.add_argument("--ui-capture", help="JSONL de lo que la ventana muestra")
    return parser.parse_args()


def _files_under(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []

    files: list[Path] = []
    for parent, child_directories, child_files in os.walk(directory):
        child_directories[:] = [
            name
            for name in child_directories
            if name.casefold() not in IGNORED_BUILD_DIRECTORY_NAMES
        ]
        files.extend(Path(parent) / name for name in child_files)
    return files


def source_files(root: Path = ROOT) -> list[Path]:
    root = root.resolve()
    files: list[Path] = []
    for relative in (*ACTIVE_DOTNET_PROJECT_ROOTS, *RUNTIME_ASSET_ROOTS):
        files.extend(_files_under(root / relative))
    files.extend(path for path in root.glob("Directory.*") if path.is_file())
    files.extend(
        path for relative in EXPLICIT_BUILD_FILES if (path := root / relative).is_file()
    )
    return sorted(set(files), key=lambda item: item.as_posix().lower())


def source_fingerprint(root: Path = ROOT) -> str:
    root = root.resolve()
    digest = hashlib.sha256()
    for path in source_files(root):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "little"))
        digest.update(relative)
        content = path.read_bytes()
        digest.update(len(content).to_bytes(8, "little"))
        digest.update(content)
    return digest.hexdigest()


def recorded_fingerprint() -> str | None:
    try:
        payload = json.loads(BUILD_STATE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    if payload.get("schema") != "baxy-development-build-v1":
        return None
    value = payload.get("source_sha256")
    return value if isinstance(value, str) else None


def dotnet_executable() -> str:
    local = Path.home() / ".dotnet" / "dotnet.exe"
    if local.is_file():
        return str(local)
    discovered = shutil.which("dotnet")
    if discovered:
        return discovered
    raise RuntimeError("No encontré .NET 10. Instálalo o agrega dotnet.exe al PATH.")


def run_checked(
    command: list[str],
    *,
    environment: dict[str, str] | None = None,
) -> None:
    completed = subprocess.run(command, cwd=ROOT, check=False, env=environment)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def environment_for_dotnet(dotnet: str) -> dict[str, str]:
    environment = os.environ.copy()
    dotnet_root = os.fspath(Path(dotnet).resolve().parent)
    environment["DOTNET_ROOT"] = dotnet_root
    environment["DOTNET_ROOT_X64"] = dotnet_root
    return environment


def directory_prefix(path: Path) -> str:
    normalized = os.path.normpath(os.path.abspath(os.fspath(path)))
    if normalized.endswith(("/", "\\")):
        return normalized
    return normalized + os.sep


def _powershell_single_quoted(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def close_previous_development_window() -> None:
    root_prefix_literal = _powershell_single_quoted(directory_prefix(ROOT))
    command = (
        f"$rootPrefix={root_prefix_literal};"
        "$apps=Get-Process Baxy -ErrorAction SilentlyContinue;"
        "foreach($app in $apps){try{"
        "$path=[IO.Path]::GetFullPath($app.Path);"
        "if($path.StartsWith($rootPrefix,[StringComparison]::OrdinalIgnoreCase)){"
        "$null=$app.CloseMainWindow();"
        "Wait-Process -Id $app.Id -Timeout 8 -ErrorAction SilentlyContinue;"
        "if(-not $app.HasExited){$app.Kill()}"
        "}}catch{}}"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        cwd=ROOT,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def compile_if_needed(*, force: bool) -> None:
    fingerprint = source_fingerprint()
    outputs_exist = APP_EXE.is_file() and CORE_EXE.is_file()
    if not force and outputs_exist and recorded_fingerprint() == fingerprint:
        print("Código .NET sin cambios; reutilizando la compilación actual.")
        return

    print("Cambió el código .NET; compilando automáticamente...")
    dotnet = dotnet_executable()
    validate_msbuild_outputs(dotnet, ROOT, BUILD_LAYOUT)
    run_checked(
        [
            dotnet,
            "build",
            str(APP_PROJECT),
            "-c",
            BUILD_LAYOUT.development_configuration,
        ]
    )
    run_checked(
        [
            dotnet,
            "publish",
            str(CORE_PROJECT),
            "-c",
            BUILD_LAYOUT.development_configuration,
            "-r",
            BUILD_LAYOUT.runtime_identifier,
        ]
    )
    if not APP_EXE.is_file() or not CORE_EXE.is_file():
        raise RuntimeError(
            "La compilación terminó sin producir los ejecutables esperados."
        )
    STATE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    temporary = BUILD_STATE.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(
            {
                "schema": "baxy-development-build-v1",
                "source_sha256": fingerprint,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, BUILD_STATE)
    print("Compilación actualizada.")


CONDUCTOR_SCRIPT = ROOT / "scripts" / "run_baxy_conductor.ps1"


def launch(
    *,
    cpu: bool,
    without_mind: bool,
    ui_probe: str | None = None,
    ui_capture: str | None = None,
) -> None:
    environment = environment_for_dotnet(dotnet_executable())
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(RUN_SCRIPT),
    ]
    if cpu:
        command.append("-Cpu")
    if without_mind:
        command.append("-SinMente")
    if ui_probe:
        command.extend(["-UiProbe", ui_probe])
    if ui_capture:
        command.extend(["-UiCapture", ui_capture])
    run_checked(command, environment=environment)


def launch_conductor(args: argparse.Namespace) -> None:
    environment = environment_for_dotnet(dotnet_executable())
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(CONDUCTOR_SCRIPT),
        "-TimeoutMs",
        str(args.timeout_ms),
    ]
    if args.cpu:
        command.extend(["-Cpu"])
    if args.profile:
        command.extend(["-Profile", args.profile])
    if args.capture:
        command.extend(["-Capture", args.capture])
    if args.turns_file:
        command.extend(["-TurnsFile", args.turns_file])
    if args.text:
        command.extend(["-Text", args.text])
    run_checked(command, environment=environment)


def main() -> int:
    if os.name != "nt":
        raise RuntimeError("BAXY requiere Windows.")
    args = parse_args()
    close_previous_development_window()
    compile_if_needed(force=args.recompilar)
    if args.conductor:
        launch_conductor(args)
        return 0
    launch(
        cpu=args.cpu,
        without_mind=args.sin_mente,
        ui_probe=args.ui_probe,
        ui_capture=args.ui_capture,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except RuntimeError as error:
        print(f"No pude iniciar BAXY: {error}", file=sys.stderr)
        raise SystemExit(1)
