"""The development launcher's command for the window (main.py launch): what it hands scripts/run_baxy.ps1, recorded
instead of run."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main  # noqa: E402


def test_the_window_starts_on_the_profile_it_was_given(monkeypatch) -> None:
    # Calidad PC 2026-10-25: --profile was taken and dropped unless --conductor: `main.py --profile X` (and hablar.py's
    # arms) opened the window on dev-mente-v2, the owner's development profile.
    commands: list[list[str]] = []
    monkeypatch.setattr(main, "dotnet_executable", lambda: sys.executable)
    monkeypatch.setattr(main, "run_checked", lambda command, **_kw: commands.append(command))
    main.launch(cpu=False, without_mind=False, profile="hablar-default1")
    assert commands[0][-2:] == ["-Profile", "hablar-default1"]


def test_without_a_profile_the_window_keeps_its_own(monkeypatch) -> None:
    commands: list[list[str]] = []
    monkeypatch.setattr(main, "dotnet_executable", lambda: sys.executable)
    monkeypatch.setattr(main, "run_checked", lambda command, **_kw: commands.append(command))
    main.launch(cpu=False, without_mind=False)
    assert "-Profile" not in commands[0]
