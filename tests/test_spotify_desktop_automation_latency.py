from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest


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
    # MUSIC1755 (e64890997): the search page gets 12 s (it was 6 s); the other
    # horizons are the original ones. M169: 20 s only while nothing is playable.
    assert "$searchDeadline=(Get-Date).AddMilliseconds(12500)" in SOURCE
    assert "$foregroundDeadline=(Get-Date).AddMilliseconds(250)" in SOURCE
    assert "$searchPageDeadline=$searchedAt.AddSeconds((Get-BaxySpotifySearchPageSeconds $true))" in SOURCE
    assert "$detailDeadline=(Get-Date).AddSeconds(12)" in SOURCE
    assert "$deadline=(Get-Date).AddSeconds(15)" in SOURCE

    calls = re.findall(r"Wait-BaxyPoll \$(\w+) (\d+)", SOURCE)
    # M86: the foreground wait is one helper, confirmed before every press.
    assert calls == [
        ("foregroundDeadline", "25"),
        ("searchDeadline", "300"),
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
        "function Confirm-BaxySpotifyForeground",
        "# BEGIN playback-evidence",
    )
    assert foreground.index("GetForegroundWindow()") < foreground.index(
        "SetForegroundWindow("
    )
    assert foreground.index("SetForegroundWindow(") < foreground.index(
        "Wait-BaxyPoll $foregroundDeadline"
    )

    search_page = _between(
        "$searchPageDeadline=$searchedAt.AddSeconds((Get-BaxySpotifySearchPageSeconds $true))",
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
        "$searchPageDeadline=$searchedAt.AddSeconds((Get-BaxySpotifySearchPageSeconds $true))",
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
    assert "if($Mode -ne 'query'){return $IdentityMatches -and $Pause}" in SOURCE
    assert (
        "$verified=Test-BaxySpotifyPlaybackVerified $Mode $pause $nowPlaying"
        in SOURCE
    )


# M86 (held-out t17 «tengo ganas de escuchar reggaetón», 3 of 6 real runs failed
# with spotify_play_clicked_not_verified after the full 15 s postread): the
# playback evidence and the single re-press are pure functions of what UIA shows,
# run here in PowerShell over plain data instead of a Spotify window.
_AFTER = "after feat young miko de conep young miko"
_LOFI = "sunrise de mxgnetic"
_T, _F = "$true", "$false"


def _verified(mode, pause, identity, observed, before, pause_before, flipped):
    return (
        f"Test-BaxySpotifyPlaybackVerified '{mode}' {pause} {identity} "
        f"'{observed}' '{before}' {pause_before} {flipped}"
    )


def _repress(presses, since, pause, pause_before, observed, before, flipped, control):
    return (
        f"Test-BaxySpotifyRepress {presses} {since} {pause} {pause_before} "
        f"'{observed}' '{before}' {flipped} {control}"
    )


def _rect(left, top, width=32, height=32):
    return f"([pscustomobject]@{{Left={left};Top={top};Width={width};Height={height}}})"


_CASES = {
    # v3i/v3j: the client restored paused on the track the result starts with.
    "cold_same_track_now_playing": (
        _verified("query", _T, _F, _AFTER, _AFTER, _F, _F), True),
    "same_track_already_playing_without_flip": (
        _verified("query", _T, _F, _AFTER, _AFTER, _T, _F), False),
    "same_track_already_playing_with_flip": (
        _verified("query", _T, _F, _AFTER, _AFTER, _T, _T), True),
    "now_playing_changed": (
        _verified("query", _T, _F, _AFTER, _LOFI, _T, _F), True),
    "changed_but_no_pause_control": (
        _verified("query", _F, _F, _AFTER, _LOFI, _F, _F), False),
    "pause_but_nothing_loaded": (
        _verified("query", _T, _F, "", "", _F, _T), False),
    "nothing_loaded_before_then_playing": (
        _verified("query", _T, _F, _AFTER, "", _F, _F), True),
    "exact_needs_identity_and_pause": (
        _verified("exact", _T, _T, _AFTER, _AFTER, _T, _F), True),
    "exact_never_accepts_flip_without_identity": (
        _verified("exact", _T, _F, _AFTER, "", _F, _T), False),
    "exact_identity_without_pause": (
        _verified("exact", _F, _T, _AFTER, "", _F, _F), False),
    # The first press left no trace five seconds later: one more press.
    "repress_when_first_press_left_no_trace": (
        _repress(1, 5200, _F, _F, _AFTER, _AFTER, _F, _T), True),
    "repress_waits_five_seconds": (
        _repress(1, 4500, _F, _F, _AFTER, _AFTER, _F, _T), False),
    "repress_only_once": (
        _repress(2, 9000, _F, _F, _AFTER, _AFTER, _F, _T), False),
    "repress_needs_the_same_control": (
        _repress(1, 6000, _F, _F, _AFTER, _AFTER, _F, _F), False),
    "no_repress_after_now_playing_moved": (
        _repress(1, 6000, _F, _F, _LOFI, _AFTER, _F, _T), False),
    "no_repress_after_pause_appeared": (
        _repress(1, 6000, _T, _F, _AFTER, _AFTER, _F, _T), False),
    "no_repress_after_flip": (
        _repress(1, 6000, _T, _T, _AFTER, _AFTER, _T, _T), False),
    "pause_name_of_named_play": (
        "Get-BaxySpotifyPauseName 'reproducir reggaeton mix'", "pausar reggaeton mix"),
    "pause_name_of_english_play": ("Get-BaxySpotifyPauseName 'play x'", "pause x"),
    "pause_name_of_generic_play": ("Get-BaxySpotifyPauseName 'reproducir'", "pausar"),
    "pause_name_needs_a_play_word": ("Get-BaxySpotifyPauseName 'playlist'", ""),
    "pause_name_of_unrelated_control": (
        "Get-BaxySpotifyPauseName 'reproductor de video'", ""),
    "near_same_place": (
        f"Test-BaxySpotifyNear {_rect(110, 240)} {_rect(100, 230)}", True),
    "near_rejects_player_bar": (
        f"Test-BaxySpotifyNear {_rect(600, 900)} {_rect(100, 230)}", False),
    # M169 (v5a-devG/devI «salsa», «Soda Stereo», «reggaetón», «música para
    # cocinar»): a client still building its accessibility tree showed the search
    # combo but nothing playable under it for the whole 12 s.
    "warm_discovery_ends_on_the_combo": (
        f"Test-BaxySpotifyContentExposed {_F} {_F}", True),
    "cold_discovery_waits_for_a_playable_control": (
        f"Test-BaxySpotifyContentExposed {_T} {_F}", False),
    "cold_discovery_ends_once_content_is_exposed": (
        f"Test-BaxySpotifyContentExposed {_T} {_T}", True),
    "search_page_with_something_playable_keeps_12_s": (
        f"Get-BaxySpotifySearchPageSeconds {_T}", 12),
    "search_page_with_nothing_playable_gets_20_s": (
        f"Get-BaxySpotifySearchPageSeconds {_F}", 20),
    "research_after_8_s_with_nothing_playable": (
        f"Test-BaxySpotifyResearch 1 8200 {_F}", True),
    "no_research_before_8_s": (
        f"Test-BaxySpotifyResearch 1 7600 {_F}", False),
    "no_research_once_something_is_playable": (
        f"Test-BaxySpotifyResearch 1 9000 {_T}", False),
    "research_only_once": (
        f"Test-BaxySpotifyResearch 2 15000 {_F}", False),
}


@pytest.fixture(scope="module")
def playback_evidence(tmp_path_factory) -> dict[str, object]:
    block = _between("# BEGIN playback-evidence", "# END playback-evidence")
    lines = [block, "$r=[ordered]@{}"]
    for name, (expression, _) in _CASES.items():
        lines.append(f"$r['{name}']=({expression})")
    lines.append("$r|ConvertTo-Json -Compress")
    script = tmp_path_factory.mktemp("m86") / "evidence.ps1"
    script.write_text("\n".join(lines), encoding="utf-8-sig")
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
         "Bypass", "-File", str(script)],
        capture_output=True, text=True, encoding="utf-8", timeout=60, check=True,
    )
    return json.loads(completed.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize("name", sorted(_CASES))
def test_spotify_playback_evidence_decisions(playback_evidence, name) -> None:
    assert playback_evidence[name] == _CASES[name][1]


def test_spotify_press_is_bounded_and_counted_before_the_second_click() -> None:
    playback = _between(
        "$deadline=(Get-Date).AddSeconds(15)",
        "if(-not $verified -and $null -ne $playObservationError)",
    )
    repress = playback[playback.index("Test-BaxySpotifyRepress"):]
    # The counter moves before the click, so an exception in the click can
    # never lead to a third press; each press confirms Spotify is in front.
    assert repress.index("$presses=2") < repress.index("InvokeElement $replayControl")
    assert repress.index("Confirm-BaxySpotifyForeground") < repress.index(
        "InvokeElement $replayControl"
    )
    first_press = _between("$selectedControlName=", "$stage='play_clicked'")
    assert first_press.index("Confirm-BaxySpotifyForeground") < first_press.index(
        "InvokeElement $playCandidate"
    )
    # The re-press stays inside the original 15 s postread horizon.
    assert "$deadline=(Get-Date).AddSeconds(15)" in SOURCE
    assert "presses=$presses" in SOURCE


def test_spotify_cold_wait_and_research_stay_before_any_press() -> None:
    # M169: the cold/warm reading happens before this request launches the
    # client, and a warm client still ends discovery on the combo alone.
    startup = _between(
        "# M169: a client with no window yet",
        "if($null -eq $process){throw 'spotify_window_missing'}",
    )
    assert startup.index("$coldStart=") < startup.index("Start-Process 'spotify:'")
    assert "$_.StartTime -lt $settledSince" in startup
    assert startup.count("Test-BaxySpotifyContentExposed $coldStart $playableSeen") == 2
    # The discovery horizon is unchanged: the cold wait lives inside it.
    assert "$searchDeadline=(Get-Date).AddMilliseconds(12500)" in startup

    search_page = _between(
        "$searchPageDeadline=$searchedAt.AddSeconds((Get-BaxySpotifySearchPageSeconds $true))",
        "if(-not $searchPageReady -and $null -ne $searchObservationError)",
    )
    research = search_page[search_page.index("Test-BaxySpotifyResearch"):]
    # Counted before navigating: never a third search; the same URI as the first.
    assert research.index("$searches=2") < research.index("Start-Process $searchUri")
    assert SOURCE.count("Start-Process $searchUri") == 2
    # The horizon follows what the last observation saw, and never moves on an
    # observation that failed.
    assert (
        "$searchPageDeadline=$searchedAt.AddSeconds((Get-BaxySpotifySearchPageSeconds $searchSnapshotReady))"
        in search_page
    )
    assert search_page.index("if($null -eq $searchObservationError){") < search_page.index(
        "Get-BaxySpotifySearchPageSeconds $searchSnapshotReady"
    )
    # Every press comes after the search page wait.
    assert SOURCE.index("Start-Process $searchUri") < SOURCE.index("$effect=$true")
    # Failures say how many searches ran and whether the client was cold.
    assert "error='spotify_exact_result_not_found';searches=$searches;coldStart=$coldStart" in SOURCE
