"""Fail-closed structural contract for the source MVP launcher."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "run_mvp.ps1"
BOOTSTRAP = ROOT / "scripts" / "bootstrap.ps1"


def test_mvp_launcher_pins_measured_wake_candidate_and_receipt() -> None:
    source = LAUNCHER.read_text(encoding="utf-8")

    assert (
        "a9a3a9fb2a98eee6d903df6afbc59bfa02d0111e9e7bd6de626ade441585001d"
        in source
    )
    assert (
        "f93d363bca35fc84fee31c08aa5a2a8e31fc7cb5c578cd923747fc61562eff88"
        in source
    )
    assert "openedDevelopmentPassed" in source
    assert "runtimeFalseActivations" in source
    assert "effectsExecuted" in source
    assert "Get-FileHash -Algorithm SHA256" in source


def test_mvp_launcher_uses_best_existing_voice_roles_without_training() -> None:
    source = LAUNCHER.read_text(encoding="utf-8")

    assert "BAXY_VOICE_STREAMING_STT = 'on'" in source
    assert "BAXY_VOICE_STREAMING_LANGUAGE = 'auto'" in source
    assert "BAXY_VOICE_LEXICAL_WAKE_FALLBACK = 'off'" in source
    assert "BAXY_VOICE_WAKE_CASCADE_MANIFEST" in source
    assert "BAXY_VOICE_WAKE_CASCADE_ALLOW_UNCALIBRATED = '1'" in source
    assert "main.py" in source
    assert "train" not in source.casefold()


def test_mvp_launcher_uses_the_hash_bound_isolated_python() -> None:
    source = LAUNCHER.read_text(encoding="utf-8")

    assert "$runtime.python" in source
    assert "$runtime.python_sha256" in source
    assert "Test-BaxyMvpPython" in source
    assert "sys.version_info[:2] == (3, 12)" in source
    assert "import baxy_mind.voice" in source
    assert "BAXY_MIND_PYTHON = $python" in source
    assert "BAXY_MIND_PYTHONPATH = $mvpPythonPath" in source
    assert "& $python (Join-Path $repo 'main.py')" in source
    assert "& py -3.12" not in source


def test_mvp_launcher_does_not_install_or_promote() -> None:
    source = LAUNCHER.read_text(encoding="utf-8").casefold()

    assert "baxy.setup" not in source
    assert "install_baxy" not in source
    assert "register_runtime" not in source
    assert "promote" not in source


def test_validate_only_reports_the_rejected_physical_wake_honestly() -> None:
    source = LAUNCHER.read_text(encoding="utf-8")

    assert "identidad v25a verificada como candidata de desarrollo" in source
    assert "prueba fisica v17 fue rechazada (46/48)" in source
    assert "no esta promovida" in source
    assert "detector historico" in source


def test_bootstrap_checks_the_real_user_dotnet_before_path_fallbacks() -> None:
    source = BOOTSTRAP.read_text(encoding="utf-8")

    user_dotnet = "Join-Path $env:USERPROFILE '.dotnet\\dotnet.exe'"
    path_dotnet = "Get-Command dotnet"
    assert user_dotnet in source
    assert source.index(user_dotnet) < source.index(path_dotnet)
