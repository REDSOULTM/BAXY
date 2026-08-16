from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "probe_mvp_ui_smoke.ps1"


def test_ui_smoke_uses_the_real_launcher_without_audio() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "run_mvp.ps1" in text
    assert "-NoWake" in text
    assert "audioCapturedOrPlayed = 0" in text
    assert "[char]0x00bf" in text
    assert "[char]0x00e9" in text


def test_ui_smoke_requires_the_typed_core_and_painted_response() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    for stage in (
        "startup.ready",
        "submit.received",
        "core.call.start",
        "system.time",
        "visible.text",
        "response.final",
        "paint.observed",
    ):
        assert stage in text


def test_ui_smoke_requires_graceful_shutdown_and_no_residual_tree() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "CloseMainWindow" in text
    assert "closeMainWindowSucceeded" in text
    assert "residualProcesses" in text
    assert "gatePassed" in text
