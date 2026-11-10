"""INS-1: Steam uninstalls BAXY by deleting its folder, so the alarms BAXY set in Windows' Task Scheduler leave only if
Steam starts BAXY one last time for that. The install script, the depot script that marks it, the build that puts it in the folder and
the argument the App answers to have to say the same thing."""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPOSITORY / "scripts"))

import package_channel  # noqa: E402

STEAM = REPOSITORY / "scripts" / "steam"


def _code(path: Path, comment: str) -> str:
    return "\n".join(line for line in path.read_text(encoding="utf-8").splitlines() if not line.strip().startswith(comment))


def _app_argument() -> str:
    source = (REPOSITORY / "src" / "Baxy.App" / "ScheduledRingsUninstall.cs").read_text(encoding="utf-8")
    return re.search(r'internal const string Argument = "([^"]+)";', source).group(1)


def test_steam_runs_baxy_with_the_argument_the_app_answers_to_when_it_uninstalls() -> None:
    script = _code(STEAM / "installscript.vdf", "//")
    block = re.search(r'"Run Process On Uninstall"\s*\{\s*"[^"]+"\s*\{([^}]*)\}', script).group(1)
    pairs = dict(re.findall(r'"([^"]+)"\s+"([^"]*)"', block))
    assert pairs == {
        # Where scripts\build_steam.ps1 puts the App, as the person's own account: the tasks and the data are theirs.
        "Process 1": r"%INSTALLDIR%\\app\\Baxy.exe",
        "Command 1": _app_argument(),
        "AsCurrentUser": "1",
    }


def test_the_app_answers_to_that_argument_before_it_takes_the_single_instance() -> None:
    startup = (REPOSITORY / "src" / "Baxy.App" / "App.xaml.cs").read_text(encoding="utf-8")
    assert startup.index("ScheduledRingsUninstall.IsRequested(e.Args)") < startup.index("new Mutex(")


def test_the_depot_marks_the_install_script_and_the_build_puts_it_in_steams_folder_alone() -> None:
    depot = _code(STEAM / "app_build.vdf", "//")
    assert '"InstallScript" "installscript.vdf"' in depot
    # scripts\build_steam.ps1 writes each store's files with scripts\package_channel.py, and its check asks for them.
    assert package_channel.files("steam") == {"installscript.vdf": (STEAM / "installscript.vdf").read_bytes()}
    assert "installscript.vdf" not in package_channel.files("itch")
    build = _code(REPOSITORY / "scripts" / "build_steam.ps1", "#")
    assert r"(Join-Path $repo 'scripts\package_channel.py'), '--depot', $Output, '--channel', $Channel)" in build
