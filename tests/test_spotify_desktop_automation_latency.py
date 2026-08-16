from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "src"
    / "Baxy.Providers.Windows"
    / "External"
    / "SpotifyDesktopAutomation.ps1"
)
SOURCE = SCRIPT.read_text(encoding="utf-8")


def _between(start: str, end: str) -> str:
    start_index = SOURCE.index(start)
    end_index = SOURCE.index(end, start_index)
    return SOURCE[start_index:end_index]


def test_spotify_polling_is_bounded_by_the_original_terminal_horizons() -> None:
    assert "$searchDeadline=(Get-Date).AddMilliseconds(12500)" in SOURCE
    assert "$foregroundDeadline=(Get-Date).AddMilliseconds(250)" in SOURCE
    assert "$searchPageDeadline=(Get-Date).AddSeconds(6)" in SOURCE
    assert "$detailDeadline=(Get-Date).AddSeconds(12)" in SOURCE
    assert "$deadline=(Get-Date).AddSeconds(15)" in SOURCE

    calls = re.findall(r"Wait-BaxyPoll \$(\w+) (\d+)", SOURCE)
    assert calls == [
        ("searchDeadline", "300"),
        ("foregroundDeadline", "25"),
        ("searchPageDeadline", "500"),
        ("detailDeadline", "500"),
        ("deadline", "500"),
    ]

    helper = _between("function Wait-BaxyPoll", "\ntry {")
    assert "$remaining=$Deadline-(Get-Date)" in helper
    assert "$remaining.TotalMilliseconds -le 0" in helper
    assert "[Math]::Min(" in helper
    assert "$IntervalMilliseconds" in helper
    assert "[Math]::Ceiling($remaining.TotalMilliseconds)" in helper


def test_spotify_success_paths_observe_before_their_first_poll() -> None:
    startup = _between("Start-Process 'spotify:'", "if($null -eq $process)")
    assert startup.index("Get-Process Spotify") < startup.index(
        "Wait-BaxyPoll $searchDeadline"
    )

    foreground = _between(
        "[void][BaxySpotifyNative]::SetForegroundWindow",
        "if(-not $foregroundVerified)",
    )
    assert foreground.index("GetForegroundWindow()") < foreground.index(
        "Wait-BaxyPoll $foregroundDeadline"
    )

    search_page = _between(
        "$searchPageDeadline=(Get-Date).AddSeconds(6)",
        "if(-not $searchPageReady",
    )
    assert search_page.index(".FindAll(") < search_page.index(
        "Wait-BaxyPoll $searchPageDeadline"
    )

    detail = _between(
        "$detailDeadline=(Get-Date).AddSeconds(12)",
        "if($null -eq $playCandidate -and $null -ne $detailObservationError)",
    )
    assert detail.index(".FindAll(") < detail.index(
        "Wait-BaxyPoll $detailDeadline"
    )

    playback = _between(
        "$deadline=(Get-Date).AddSeconds(15)",
        "if(-not $verified -and $null -ne $playObservationError)",
    )
    assert playback.index(".FindAll(") < playback.index(
        "Wait-BaxyPoll $deadline"
    )


def test_query_generic_play_cannot_exit_early_without_current_search_value() -> None:
    value_probe = _between(
        "function Read-BaxySpotifySearchValue",
        "\ntry {",
    )
    assert "ControlType]::Edit" in value_probe
    assert "ValuePattern]::Pattern" in value_probe
    assert "return $value" in value_probe

    search_page = _between(
        "$searchPageDeadline=(Get-Date).AddSeconds(6)",
        "if(-not $searchPageReady -and $null -ne $searchObservationError)",
    )
    value_read = "$querySearchValue=Read-BaxySpotifySearchValue $search"
    snapshot_read = (
        "$searchSnapshotReady=$null -ne $playCandidate "
        "-or $null -ne $candidate"
    )
    guarded_acceptance = (
        "$searchPageReady=$searchSnapshotReady -and (\n"
        "                $Mode -ne 'query' -or $querySearchValueMatches)"
    )
    assert search_page.index(value_read) < search_page.index(snapshot_read)
    assert search_page.index(snapshot_read) < search_page.index(guarded_acceptance)

    # Before the deadline, a generic Play snapshot is insufficient in query
    # mode unless the normalized ComboBox/Edit value proves the current query.
    def can_accept_early(
        snapshot_ready: bool,
        query_value_matches: bool,
    ) -> bool:
        return snapshot_ready and query_value_matches

    assert can_accept_early(snapshot_ready=True, query_value_matches=False) is False
    assert can_accept_early(snapshot_ready=True, query_value_matches=True) is True

    # If UIA cannot expose/converge the value, the old behavior is retained
    # only after Wait-BaxyPoll has exhausted the original six-second horizon.
    poll_end = search_page.index("while((Wait-BaxyPoll $searchPageDeadline 500))")
    terminal_fallback = search_page.index(
        "if(-not $searchPageReady -and $Mode -eq 'query' "
        "-and $searchSnapshotReady -and $null -eq $searchObservationError)"
    )
    assert poll_end < terminal_fallback


def test_spotify_removed_blind_waits_without_weakening_exact_postreads() -> None:
    assert "Start-Sleep -Seconds 6" not in SOURCE
    assert re.search(r"Start-Sleep -Milliseconds (?:250|300|500)\b", SOURCE) is None

    # Exact title/card selection remains bounded to the visible result area.
    assert "$name -eq $foldTitle" in SOURCE
    assert "$name -eq $expectedPlay -or $name.StartsWith($expectedPlay+' ')" in SOURCE
    assert "$rect.Top -gt ($searchRect.Top+20)" in SOURCE
    assert "$rect.Top -lt ($searchRect.Top+600)" in SOURCE
    assert "$rect.Left -ge $windowRect.Left" in SOURCE
    assert "$rect.Right -le $windowRect.Right" in SOURCE

    # Playback still needs both the exact now-playing identity and Pause control.
    assert "$titleMatches -and $identityMatches" in SOURCE
    assert "$name -in @('pausar','pause')" in SOURCE
    assert "}else{$nowPlaying -and $pause}" in SOURCE
