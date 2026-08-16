from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTERNAL = ROOT / "src" / "Baxy.Providers.Windows" / "External"
CONTROL_SOURCE = (EXTERNAL / "SpotifyMediaControl.ps1").read_text(encoding="utf-8")
DESKTOP_SOURCE = (EXTERNAL / "SpotifyDesktopAdapter.cs").read_text(encoding="utf-8")
SMTC_SOURCE = (EXTERNAL / "WindowsMediaSessionAdapter.cs").read_text(encoding="utf-8")


def _between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    end_index = source.index(end, start_index)
    return source[start_index:end_index]


def test_spotify_media_control_preserves_terminal_horizons() -> None:
    assert "$startupDeadline=(Get-Date).AddMilliseconds(1200)" in CONTROL_SOURCE
    assert "$foregroundDeadline=(Get-Date).AddMilliseconds(200)" in CONTROL_SOURCE
    assert "$deadline=(Get-Date).AddSeconds(8)" in CONTROL_SOURCE

    calls = re.findall(r"Wait-BaxyPoll \$(\w+) (\d+)", CONTROL_SOURCE)
    assert calls == [
        ("startupDeadline", "50"),
        ("foregroundDeadline", "25"),
        ("deadline", "100"),
    ]

    helper = _between(CONTROL_SOURCE, "function Wait-BaxyPoll", "\ntry {")
    assert "$remaining=$Deadline-(Get-Date)" in helper
    assert "$remaining.TotalMilliseconds -le 0" in helper
    assert "[Math]::Min(" in helper
    assert "$IntervalMilliseconds" in helper
    assert "[Math]::Ceiling($remaining.TotalMilliseconds)" in helper


def test_spotify_media_control_observes_equivalent_predicates_before_waiting() -> None:
    startup = _between(
        CONTROL_SOURCE,
        "Start-Process 'spotify:'",
        "# Re-run the original terminal observations",
    )
    assert startup.index("Get-Process Spotify -ErrorAction SilentlyContinue") < (
        startup.index("Wait-BaxyPoll $startupDeadline")
    )
    assert startup.index("VisibleButtons $candidateRoot") < startup.index(
        "Wait-BaxyPoll $startupDeadline"
    )
    assert startup.index("FindButton $candidateButtons $targets") < startup.index(
        "Wait-BaxyPoll $startupDeadline"
    )

    foreground = _between(
        CONTROL_SOURCE,
        "[void][BaxySpotifyControlNative]::SetForegroundWindow",
        "if(-not $foregroundVerified)",
    )
    assert foreground.index("GetForegroundWindow()") < foreground.index(
        "Wait-BaxyPoll $foregroundDeadline"
    )
    assert "GetForegroundWindow() -eq $process.MainWindowHandle" in foreground

    postread = _between(
        CONTROL_SOURCE,
        "$deadline=(Get-Date).AddSeconds(8)",
        "$status=switch($Action)",
    )
    assert postread.index("VisibleButtons $root") < postread.index(
        "Wait-BaxyPoll $deadline"
    )
    assert postread.index("NearButton $afterButtons $opposites $rect") < (
        postread.index("Wait-BaxyPoll $deadline")
    )
    assert postread.index("$afterTitle -ne $beforeTitle") < postread.index(
        "Wait-BaxyPoll $deadline"
    )
    assert "$postreadObservationError=$_" in postread
    assert postread.index("Wait-BaxyPoll $deadline") < postread.index(
        "throw $postreadObservationError"
    )


def test_spotify_media_control_keeps_identity_failures_and_postconditions() -> None:
    assert "Get-Process Spotify -ErrorAction Stop" in CONTROL_SOURCE
    assert "if($null -eq $process){throw 'spotify_window_missing'}" in CONTROL_SOURCE
    assert "error='spotify_control_not_available'" in CONTROL_SOURCE
    assert "throw 'spotify_foreground_not_verified'" in CONTROL_SOURCE
    assert "'spotify_control_postread_not_verified'" in CONTROL_SOURCE

    assert "$opposite -and -not $original" in CONTROL_SOURCE
    assert "$afterTitle -ne $beforeTitle" in CONTROL_SOURCE
    assert "$process.MainWindowHandle" in CONTROL_SOURCE
    assert "$process.Id" in CONTROL_SOURCE

    assert "Start-Sleep -Milliseconds 1200" not in CONTROL_SOURCE
    assert "Start-Sleep -Milliseconds 200" not in CONTROL_SOURCE
    assert "Start-Sleep -Milliseconds 400" not in CONTROL_SOURCE


def test_desktop_retry_keeps_only_wait_without_an_observable_predicate() -> None:
    assert DESKTOP_SOURCE.count("Task.Delay(400, cancellationToken)") == 1
    retry = _between(
        DESKTOP_SOURCE,
        "if (attempt == 0",
        "return effectBoundary.Failure(operation, error, effect);",
    )
    assert "exactSelection" in retry
    assert "!effect" in retry
    assert "IsRetryableExactDiscoveryError(error)" in retry
    assert "Task.Delay(400, cancellationToken)" in retry
    assert "no cheaper readiness" in retry


def test_smtc_postreads_observe_first_and_retain_original_horizons() -> None:
    assert "SpotifyPlaybackPollIntervals = 20" in SMTC_SOURCE
    assert "TimeSpan.FromMilliseconds(500)" in SMTC_SOURCE
    assert "SmtcPostreadPollIntervals = 7" in SMTC_SOURCE
    assert "TimeSpan.FromMilliseconds(50)" in SMTC_SOURCE
    assert "Task.Delay(350" not in SMTC_SOURCE

    spotify = _between(
        SMTC_SOURCE,
        "for (int attempt = 0; attempt <= SpotifyPlaybackPollIntervals; attempt++)",
        'return ExternalJson.Failure(operation, "spotify_now_playing_not_verified"',
    )
    assert spotify.index("if (attempt > 0)") < spotify.index("SpotifyJsonAsync(")
    assert "observedId.GetString()" in spotify
    assert "trackId" in spotify
    assert "attempt == 0" in spotify
    assert "exception is HttpRequestException or JsonException" in spotify

    play = _between(
        SMTC_SOURCE,
        "private async ValueTask<ExternalCapabilityReceipt> PlayExactCurrentAsync",
        "private async ValueTask<ExternalCapabilityReceipt> ControlAsync",
    )
    assert play.index("session.TryGetMediaPropertiesAsync()") < play.index(
        "_delay(SmtcPostreadPollInterval"
    )
    assert "Fold(after.Title)" in play
    assert "PlaybackStatus.Playing" in play

    control = _between(
        SMTC_SOURCE,
        "private async ValueTask<ExternalCapabilityReceipt> ControlAsync",
        "private static async ValueTask<ExternalCapabilityReceipt> StatusAsync",
    )
    assert control.index("session.TryGetMediaPropertiesAsync()") < control.index(
        "_delay(SmtcPostreadPollInterval"
    )
    assert '"next" or "previous"' in control
    assert "Fold(before.Title" in control
    assert "Fold(after.Title" in control
    assert "smtc_postcondition_not_verified" in control

    seek = _between(
        SMTC_SOURCE,
        "private async ValueTask<ExternalCapabilityReceipt> SeekRelativeAsync",
        "private static JsonElement MediaResult",
    )
    assert seek.index("session.GetTimelineProperties()") < seek.index(
        "_delay(SmtcPostreadPollInterval"
    )
    assert "TimeSpan.FromSeconds(playing ? 2.5 : 1.0)" in seek
    assert "media_seek_postcondition_not_verified" in seek
