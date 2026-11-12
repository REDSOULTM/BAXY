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


def test_the_window_and_the_conductor_run_this_checkouts_mind(monkeypatch) -> None:
    # VIVO1 (2026-11-09): run_baxy.ps1 names the mind only for its probe, so the App took the registered runtime's copy
    # (%LOCALAPPDATA%\BAXYRuntime\mind-src\49baeba53e87, six days and 850 commits old, without external_model.py): Ollama's
    # list and translator failed in the window while the checkout had them.
    monkeypatch.delenv("BAXY_MIND_PYTHONPATH", raising=False)
    environments: list[dict[str, str]] = []
    monkeypatch.setattr(main, "dotnet_executable", lambda: sys.executable)
    monkeypatch.setattr(main, "run_checked", lambda command, **kw: environments.append(kw["environment"]))
    main.launch(cpu=False, without_mind=False)
    monkeypatch.setattr(sys, "argv", ["main.py", "--conductor", "--text", "hola"])
    main.launch_conductor(main.parse_args())
    assert [env["BAXY_MIND_PYTHONPATH"] for env in environments] == [str(main.ROOT / "src")] * 2


def test_a_mind_asked_for_on_purpose_is_kept(monkeypatch) -> None:
    # As run_renew.cmd: a bench may measure another copy of the mind by naming it first.
    monkeypatch.setenv("BAXY_MIND_PYTHONPATH", r"D:\otra\src")
    environments: list[dict[str, str]] = []
    monkeypatch.setattr(main, "dotnet_executable", lambda: sys.executable)
    monkeypatch.setattr(main, "run_checked", lambda command, **kw: environments.append(kw["environment"]))
    main.launch(cpu=False, without_mind=False)
    assert environments[0]["BAXY_MIND_PYTHONPATH"] == r"D:\otra\src"


def test_without_a_profile_the_window_keeps_its_own(monkeypatch) -> None:
    commands: list[list[str]] = []
    monkeypatch.setattr(main, "dotnet_executable", lambda: sys.executable)
    monkeypatch.setattr(main, "run_checked", lambda command, **_kw: commands.append(command))
    main.launch(cpu=False, without_mind=False)
    assert "-Profile" not in commands[0]
