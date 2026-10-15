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
QUERY_WORDS = ROOT / "src" / "baxy_mind" / "data" / "query_function_words.v1.json"


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
    assert search_page.index("Get-BaxySpotifySnapshot $root") < search_page.index(
        "Wait-BaxyPoll $searchPageDeadline"
    )

    detail = _between(
        "$detailDeadline=(Get-Date).AddSeconds(12)",
        "if($null -eq $playCandidate -and $null -ne $detailObservationError)",
    )
    assert detail.index("Get-BaxySpotifySnapshot $root") < detail.index(
        "Wait-BaxyPoll $detailDeadline"
    )

    playback = _between(
        "$deadline=(Get-Date).AddSeconds(15)",
        "if(-not $verified -and $null -ne $playObservationError)",
    )
    assert playback.index("Get-BaxySpotifySnapshot $root") < playback.index(
        "Wait-BaxyPoll $deadline"
    )


def test_query_search_ends_only_on_a_result_of_this_search_never_on_the_page_before() -> None:
    # Rewritten by encargo SP (2026-10-12). It pinned the former proof that the page under the box was this search:
    # the box's value read at every poll. On redpc the URI sets that value 1.1-1.3 s after it is issued, while the page
    # under it is still the one shown before for 1.5-6.5 s more (tests/data/sp_spotify_reproducir.json, runs pr7, dry6,
    # pr8, pr9); fin2 pressed there and the control was torn down (spotify_element_not_actionable). Now the page before
    # is read once before the URI, its elements are never a result, and a query search ends early only on a result
    # that names the query (Select-BaxySpotifySearchResult).
    value_probe = _between("function Read-BaxySpotifySearchValue", "\ntry {")
    assert "ControlType]::Edit" in value_probe
    assert "ValuePattern]::Pattern" in value_probe
    assert "return $value" in value_probe

    before = _between("$foldTitle=Fold($title)", "Start-Process $searchUri")
    assert "$valueBefore=Read-BaxySpotifySearchValue $search" in before
    assert "$pageBefore=Get-BaxySpotifyPageBefore $valueBefore $foldTitle $keysBefore" in before
    # X3: the page before is what each element showed then (its runtime id and its name), never the id alone.
    assert "ForEach-Object {Get-BaxySpotifyRowKey $_}" in before
    # The page before is read only when it is not already this search.
    assert "if($valueBefore -ne $foldTitle){@((Get-BaxySpotifySnapshot" in before

    search_page = _between(
        "$searchPageDeadline=$searchedAt.AddSeconds((Get-BaxySpotifySearchPageSeconds $true))",
        "if(-not $searchPageReady -and $null -ne $searchObservationError)",
    )
    # One read of the box before the URI, none per poll. Encargo SP3 adds one more, after the wait, only to say in
    # the detail of a search that picked nothing whether the URI reached the box.
    assert "Read-BaxySpotifySearchValue" not in search_page
    assert SOURCE.count("Read-BaxySpotifySearchValue $search") == 2
    assert "Read-BaxySpotifySearchValue $search" in _between("if($null -eq $candidate){", "exit 2")
    choice = (
        "$choice=Select-BaxySpotifySearchResult $all $pageBefore $Mode $foldTitle $expectedPlay $searchRect "
        "$windowRect $queryFunctionWords $queryPurposeMarkers"
    )
    assert search_page.index(choice) < search_page.index("$searchPageReady=$choice.Answered")
    select = _between("function Select-BaxySpotifySearchResult", "# END playback-evidence")
    assert "$results=@(foreach($row in $Rows){if(-not $PageBefore.Contains((Get-BaxySpotifyRowKey $row))){$row}})" in select
    # Rewritten by encargo X3: the play controls and the card are looked for among the results; what the card titled as
    # the query contains (its identity link, its bare «reproducir») is of this search even on a reused element.
    assert select.count("foreach($element in $results)") == 2
    assert select.count("foreach($element in $Rows)") == 2
    assert select.index("$candidateRect=$candidate.Rect") < select.index("foreach($element in $Rows)")
    assert (
        "$answered=($null -ne $playCandidate -or $null -ne $candidate) -and "
        "($Mode -ne 'query' -or $null -ne $candidate -or $playCandidateOverlap -gt 0)"
    ) in select
    # At the horizon the last observation is taken as it is, as before.
    poll_end = SOURCE.index("while((Wait-BaxyPoll $searchPageDeadline 500))")
    horizon = SOURCE.index(
        "if(-not $searchPageReady -and $searchSnapshotReady -and $null -eq $searchObservationError){$searchPageReady=$true}"
    )
    assert poll_end < horizon < SOURCE.index("$effect=$true")


def test_spotify_removed_blind_waits_without_weakening_exact_postreads() -> None:
    assert "Start-Sleep -Seconds 6" not in SOURCE
    assert re.search(r"Start-Sleep -Milliseconds (?:250|300|500)\b", SOURCE) is None

    # Exact title/card selection remains bounded to the visible result area (encargo SP: the search page's choice is
    # Select-BaxySpotifySearchResult, with the same bounds; the detail page keeps its own).
    select = _between("function Select-BaxySpotifySearchResult", "# END playback-evidence")
    assert "$name -eq $Title" in select
    assert "$name -eq $ExpectedPlay -or $name.StartsWith($ExpectedPlay+' ')" in select
    assert select.count("$rect.Top -gt ($SearchRect.Top+20) -and $rect.Top -lt ($SearchRect.Top+600)") == 2
    assert select.count("$rect.Left -ge $WindowRect.Left -and $rect.Right -le $WindowRect.Right") == 2
    assert "$name -eq $expectedPlay -or $name.StartsWith($expectedPlay+' ')" in SOURCE
    assert "$rect.Top -gt ($searchRect.Top+20)" in SOURCE
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


def _ignored(presses, since, pause, pause_before, observed, before, flipped):
    return (
        f"Test-BaxySpotifyPressIgnored {presses} {since} {pause} {pause_before} "
        f"'{observed}' '{before}' {flipped}"
    )


_NUJABES = "aruarian dance de nujabes"
_BUNKERS = "llueve sobre la ciudad de los bunkers"


def _query_evidence(pause, observed, before, pause_before, flipped, pressed, seen_now, seen_window):
    return (
        f"Get-BaxySpotifyQueryEvidence {pause} '{observed}' '{before}' {pause_before} {flipped} "
        f"'{pressed}' @('{seen_now}','{seen_window}')"
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
    # Tanda t4-r6: the re-press left no trace four seconds later, so the wait
    # ends there instead of running out the 15 s horizon.
    "ignored_after_the_repress_left_no_trace": (
        _ignored(2, 4200, _F, _F, _AFTER, _AFTER, _F), True),
    "ignored_waits_four_seconds_after_the_repress": (
        _ignored(2, 3500, _F, _F, _AFTER, _AFTER, _F), False),
    "never_ignored_before_the_repress": (
        _ignored(1, 9000, _F, _F, _AFTER, _AFTER, _F), False),
    "not_ignored_once_now_playing_moved": (
        _ignored(2, 6000, _F, _F, _LOFI, _AFTER, _F), False),
    "not_ignored_once_pause_appeared": (
        _ignored(2, 6000, _T, _F, _AFTER, _AFTER, _F), False),
    "not_ignored_once_the_control_flipped": (
        _ignored(2, 6000, _F, _F, _AFTER, _AFTER, _T), False),
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
    # Ronda 19, t2-c01 T1 «pone los bunkers en spotify pa estudiar»: the client had Nujabes loaded in pause, the
    # press only resumed it and that was told as the search played. Resuming the loaded track proves nothing about
    # the pressed result unless what plays is related to that result.
    "r19_resumed_unrelated_track_is_not_confirmed": (
        _query_evidence(_T, _NUJABES, _NUJABES, _F, _F, "los bunkers",
                        _NUJABES, "nujabes aruarian dance"), "resumed"),
    "r19_resumed_track_of_the_pressed_result_is_started": (
        _query_evidence(_T, _BUNKERS, _BUNKERS, _F, _F, "los bunkers", _BUNKERS, ""), "started"),
    # Heldout t17 contracase: the client restored paused on the first track of the pressed playlist, whose own
    # control now reads as its pause label.
    "r19_resumed_with_the_pressed_control_flipped_is_started": (
        _query_evidence(_T, _AFTER, _AFTER, _F, _T, "reggaeton mix", _AFTER, ""), "started"),
    # Something new plays: an album, a playlist, a generic or a misheard search all start their result, and none of
    # them is compared with the words of the request (the review's «un verano sin ti», «top 50 chile», «música
    # navideña», «los bonkers»).
    "r19_album_track_now_playing_is_started": (
        _query_evidence(_T, "moscow mule de bad bunny", _NUJABES, _F, _F, "un verano sin ti",
                        "moscow mule de bad bunny", ""), "started"),
    "r19_playlist_flipped_is_started": (
        _query_evidence(_T, _NUJABES, _NUJABES, _T, _T, "top 50 chile", _NUJABES, ""), "started"),
    "r19_generic_search_new_track_is_started": (
        _query_evidence(_T, "all i want for christmas is you de mariah carey", "", _F, _F,
                        "navidad 2024", "", ""), "started"),
    "r19_misheard_name_corrected_by_the_client_is_started": (
        _query_evidence(_T, _BUNKERS, _NUJABES, _F, _F, "los bunkers", _BUNKERS, ""), "started"),
    "r19_nothing_plays_is_none": (
        _query_evidence(_F, _NUJABES, _NUJABES, _F, _F, "los bunkers", _NUJABES, ""), "none"),
    "r19_pressed_result_named_by_its_control": (
        "Get-BaxySpotifyPressedResult 'reproducir reggaeton mix' ''", "reggaeton mix"),
    "r19_pressed_result_of_a_bare_control_is_its_card": (
        "Get-BaxySpotifyPressedResult 'reproducir' 'los bunkers'", "los bunkers"),
    "r19_relation_a_long_word_starts_a_played_word": (
        "Test-BaxySpotifyPlayingRelatesTo 'los prisionero' @('tren al sur de los prisioneros')", True),
    "r19_relation_ignores_short_shared_words": (
        "Test-BaxySpotifyPlayingRelatesTo 'los bunkers' @('la voz de los 80 de los prisioneros')", False),
    "r19_relation_of_a_short_name_needs_all_its_words": (
        "Test-BaxySpotifyPlayingRelatesTo 'ac dc' @('back in black de ac dc')", True),
    "r19_relation_of_a_short_name_is_not_a_part_of_a_word": (
        "Test-BaxySpotifyPlayingRelatesTo 'ac dc' @('acdc tribute de los ac')", False),
    "r19_relation_needs_something_pressed": (
        "Test-BaxySpotifyPlayingRelatesTo '' @('aruarian dance de nujabes')", False),
    # Ronda 23 t2-c01 «pone los bunkers en spotify pa estudiar»: the control of the result named like the query
    # outranks one of an unrelated result, whatever their places on the page. Ronda 24, revisión 2: the rank is the
    # core named (x100) and then the purpose; function words (data) never count, short content words always do.
    "r24_overlap_of_the_result_named_like_the_query": (
        "Get-BaxySpotifyQueryOverlap 'los bunkers' (Get-BaxySpotifyPressedResult 'reproducir los bunkers' '') $fw $pm",
        100),
    "r24_overlap_of_an_unrelated_result_is_zero": (
        "Get-BaxySpotifyQueryOverlap 'los bunkers' "
        "(Get-BaxySpotifyPressedResult 'reproducir nada en este mundo de fother muckers' '') $fw $pm", 0),
    "r24_overlap_never_counts_function_words": (
        "Get-BaxySpotifyQueryOverlap 'los bunkers' 'la voz de los 80 de los prisioneros' $fw $pm", 0),
    "r24_overlap_of_words_written_together": (
        "Get-BaxySpotifyQueryOverlap 'lo fi para estudiar' 'lofi para estudiar' $fw $pm", 101),
    "r24_overlap_of_a_short_query_written_apart": (
        "Get-BaxySpotifyQueryOverlap 'ac dc' 'back in black de ac dc' $fw $pm", 100),
    "r24_overlap_of_nothing_is_zero": ("Get-BaxySpotifyQueryOverlap '' 'los bunkers' $fw $pm", 0),
    # Revisión 2, «rap para entrenar»: «para» counted and «rap» did not, so «Rock para entrenar» outranked «Rap
    # Workout». Now the core decides and the purpose only breaks ties.
    "r24b_rap_workout_outranks_rock_para_entrenar": (
        "(Get-BaxySpotifyQueryOverlap 'rap para entrenar' 'rap workout' $fw $pm) -gt "
        "(Get-BaxySpotifyQueryOverlap 'rap para entrenar' 'rock para entrenar' $fw $pm)", True),
    "r24b_rap_chileno_outranks_rock_para_entrenar": (
        "(Get-BaxySpotifyQueryOverlap 'rap para entrenar' 'rap chileno' $fw $pm) -gt "
        "(Get-BaxySpotifyQueryOverlap 'rap para entrenar' 'rock para entrenar' $fw $pm)", True),
    "r24b_rock_para_entrenar_ranks_only_by_its_purpose": (
        "Get-BaxySpotifyQueryOverlap 'rap para entrenar' 'rock para entrenar' $fw $pm", 1),
    # t1-c07 «lo fi para estudiar»: «lofi beats» and the lo-fi radio outrank «Piano para estudiar».
    "r24b_lofi_beats_outranks_piano_para_estudiar": (
        "(Get-BaxySpotifyQueryOverlap 'lo fi para estudiar' 'lofi beats' $fw $pm) -gt "
        "(Get-BaxySpotifyQueryOverlap 'lo fi para estudiar' 'piano para estudiar' $fw $pm)", True),
    "r24b_lofi_radio_outranks_piano_para_estudiar": (
        "(Get-BaxySpotifyQueryOverlap 'lo fi para estudiar' 'lofi hip hop radio beats to relax study to' $fw $pm) -gt "
        "(Get-BaxySpotifyQueryOverlap 'lo fi para estudiar' 'piano para estudiar' $fw $pm)", True),
    "r24b_a_short_content_word_counts_whole": ("Get-BaxySpotifyQueryOverlap 'pop' 'pop latino' $fw $pm", 100),
    "r24b_a_short_content_word_is_not_the_start_of_another": (
        "Get-BaxySpotifyQueryOverlap 'pop' 'popular hits' $fw $pm", 0),
    "r24b_a_query_written_together_finds_it_apart": (
        "Get-BaxySpotifyQueryOverlap 'lofi' 'lo fi beats' $fw $pm", 100),
    # The fact the receipt carries: what plays names the core of the query, or the pressed result names it and flipped.
    "r24_fother_muckers_for_los_bunkers_does_not_match": (
        "Test-BaxySpotifyMatchesQuery 'los bunkers' 'nada en este mundo de fother muckers' $false "
        "@('nada en este mundo de fother muckers','fother muckers nada en este mundo') $fw $pm",
        False),
    "r24_a_track_of_the_band_matches": (
        "Test-BaxySpotifyMatchesQuery 'los bunkers' 'los bunkers' $false @('llueve sobre la ciudad de los bunkers','') $fw $pm",
        True),
    "r24_the_pressed_matching_playlist_flipped_matches": (
        "Test-BaxySpotifyMatchesQuery 'lo fi para estudiar' 'lofi para estudiar' $true @('snowman de wys','wys snowman') $fw $pm",
        True),
    "r24_a_matching_press_that_did_not_flip_is_not_enough": (
        "Test-BaxySpotifyMatchesQuery 'lo fi para estudiar' 'lofi para estudiar' $false @('snowman de wys','wys snowman') $fw $pm",
        False),
    # Contracaso «música para estudiar»: no result shares a word, the choice stays by position and the fact is false
    # (told in a neutral tone, never as the request done).
    "r24_a_descriptive_query_with_no_shared_word_does_not_match": (
        "Test-BaxySpotifyMatchesQuery 'musica para estudiar' 'chill vibes' $true @('snowman de wys','wys snowman') $fw $pm",
        False),
    # Revisión 2: «Rock para entrenar» pressed for «rap para entrenar», «Eye of the Tiger» plays: never a match.
    "r24b_rock_para_entrenar_does_not_match_rap_para_entrenar": (
        "Test-BaxySpotifyMatchesQuery 'rap para entrenar' 'rock para entrenar' $true "
        "@('eye of the tiger de survivor','survivor eye of the tiger') $fw $pm", False),
    "r24b_rap_chileno_matches_rap_para_entrenar": (
        "Test-BaxySpotifyMatchesQuery 'rap para entrenar' 'rap chileno' $true @('tiempos de guerra de portavoz','') $fw $pm",
        True),
    "r24b_salsa_para_bailar_does_not_match_cumbia_para_bailar": (
        "Test-BaxySpotifyMatchesQuery 'cumbia para bailar' 'salsa para bailar' $true @('salsa para bailar','') $fw $pm",
        False),
    "r24b_piano_para_estudiar_does_not_match_lo_fi_para_estudiar": (
        "Test-BaxySpotifyMatchesQuery 'lo fi para estudiar' 'piano para estudiar' $true @('river flows in you de yiruma','') $fw $pm",
        False),
    # The other side (a final that falls short is also dishonest): a lo-fi playlist without «para estudiar» in its
    # name, pressed and playing, is what was asked for.
    "r24b_lofi_beats_matches_lo_fi_para_estudiar": (
        "Test-BaxySpotifyMatchesQuery 'lo fi para estudiar' 'lofi beats' $true @('snowman de wys','wys snowman') $fw $pm",
        True),
    "r24b_the_now_playing_line_alone_can_match": (
        "Test-BaxySpotifyMatchesQuery 'lo fi para estudiar' '' $false @('lofi study de chillhop','') $fw $pm", True),
    # A query that names only the medium and a purpose has that purpose as what was asked for.
    "r24b_a_purpose_only_query_matches_its_purpose": (
        "Test-BaxySpotifyMatchesQuery 'musica para estudiar' 'piano para estudiar' $true @('river flows in you de yiruma','') $fw $pm",
        True),
    # Fold: two regular expressions, the same result as the former character loop.
    "r24b_fold_hyphen_case_and_accents": ("Fold 'Lo-Fi Para Estudiar'", "lo fi para estudiar"),
    "r24b_fold_tilde_and_punctuation": (
        "Fold ('Est'+[char]0x00E1+'s escuchando: Canci'+[char]0x00F3+'n de '+[char]0x00D1+'and'+[char]0x00FA)",
        "estas escuchando cancion de nandu"),
    "r24b_fold_slash_and_spaces": ("Fold '  AC/DC  - Back in Black '", "ac dc back in black"),
    "r24b_fold_nothing": ("Fold ''", ""),
    # Encargo SP: the elements of the page shown before the search are never a result of it, unless that page already
    # was this search (its box held the query); an element with no runtime id is never set aside. Encargo X3: an
    # element of the page before is the same element still showing the same name (Get-BaxySpotifyRowKey).
    "sp_page_before_of_another_page": ("(Get-BaxySpotifyPageBefore '' 'los bunkers' @('42.1|a','42.2|b')).Count", 2),
    "sp_page_before_of_another_search": (
        "(Get-BaxySpotifyPageBefore 'los bunkers' 'lo fi para estudiar' @('42.1|a')).Count", 1),
    "sp_page_before_already_this_search": (
        "(Get-BaxySpotifyPageBefore 'los bunkers' 'los bunkers' @('42.1|a','42.2|b')).Count", 0),
    "sp_page_before_ignores_blank_ids": ("(Get-BaxySpotifyPageBefore '' 'x' @('|reproducir x','42.1|a')).Count", 1),
    "x3_row_key_is_the_id_and_the_name": (
        "Get-BaxySpotifyRowKey ([pscustomobject]@{Id='42.7.1.800';Fold='reproducir mix cumbia'})",
        "42.7.1.800|reproducir mix cumbia"),
    "x3_a_reused_element_renamed_is_not_of_the_page_before": (
        "(Get-BaxySpotifyPageBefore 'los bunkers' 'cumbia' @('42.1|reproducir los bunkers')).Contains("
        "(Get-BaxySpotifyRowKey ([pscustomobject]@{Id='42.1';Fold='reproducir mix cumbia'})))", False),
    "x3_an_element_still_as_before_is_of_the_page_before": (
        "(Get-BaxySpotifyPageBefore 'los bunkers' 'cumbia' @('42.1|reproducir los bunkers')).Contains("
        "(Get-BaxySpotifyRowKey ([pscustomobject]@{Id='42.1';Fold='reproducir los bunkers'})))", True),
}


@pytest.fixture(scope="module")
def playback_evidence(tmp_path_factory) -> dict[str, object]:
    block = _between("# BEGIN playback-evidence", "# END playback-evidence")
    # The function words and purpose markers the adapter passes from data (query_function_words.v1.json).
    words = json.loads(QUERY_WORDS.read_text(encoding="utf-8"))

    def array(values: list[str]) -> str:
        return "@(" + ",".join(f"'{value}'" for value in values) + ")"

    lines = [
        block,
        f"$fw={array(words['function_words'] + words['medium_words'])}",
        f"$pm={array(words['purpose_markers'])}",
        "$r=[ordered]@{}",
    ]
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


def test_spotify_ignored_press_ends_the_wait_unverified_never_verified() -> None:
    playback = _between(
        "$deadline=(Get-Date).AddSeconds(15)",
        "if(-not $verified -and $null -ne $playObservationError)",
    )
    # The early end is read only after the re-press was counted and timed, and
    # it leaves the loop as a failure: $verified stays false, so the result is
    # spotify_play_clicked_not_verified as before, only sooner.
    assert playback.index("$repressedAt=Get-Date") < playback.index("Test-BaxySpotifyPressIgnored")
    assert "if($verified -or $pressIgnored){break}" in playback
    assert "$verified=$true" not in playback
    assert "pressIgnored=$pressIgnored" in SOURCE


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
    # Failures say how many searches ran and whether the client was cold (encargo SP3: inside the detail, the one field
    # of the three the adapter carries into the receipt).
    not_found = _between("if($null -eq $candidate){", "exit 2")
    assert "$searches $coldStart" in not_found and "detail=$detail" in not_found


def test_r19_query_mode_waits_out_a_resumed_track_before_calling_it_unconfirmed() -> None:
    # Ronda 19: query mode reads the evidence of each poll; a poll that only saw the loaded track resume never ends
    # the wait (the now-playing line or the pressed control may still move to the result, as with a client restored
    # paused), and only a wait that never saw more ends as spotify_query_result_not_confirmed. The exact mode keeps
    # its identity check unchanged.
    play = _between("$stage='play_clicked'", "$failure=")
    assert "$evidence=Get-BaxySpotifyQueryEvidence $pause $observedNowPlaying $beforeNowPlaying" in play
    assert "$verified=$evidence -eq 'started'" in play
    assert "if($evidence -eq 'resumed'){$resumedOnly=$true}" in play
    # The loop ends only on a verified press or an ignored re-press (the inner breaks leave a foreach).
    assert re.findall(r"^        if\(.*\)\{break\}$", play, re.MULTILINE) == ["        if($verified -or $pressIgnored){break}"]
    assert "if($verified -or $pressIgnored){break}" in play
    assert "elseif($resumedOnly){'spotify_query_result_not_confirmed'}" in SOURCE
    assert "TermsBase64" not in SOURCE
    # The pressed result is read before the press, from the pressed control and the card it stands in.
    assert SOURCE.index("$pressedResult=Get-BaxySpotifyPressedResult $selectedFold") < SOURCE.index(
        "InvokeElement $playCandidate"
    )


def test_r24_query_candidates_are_ranked_by_overlap_and_exact_mode_is_unranked() -> None:
    page = _between("$playCandidateOverlap=-1", "$candidate=$null")
    overlap = (
        "$overlap=if($Mode -eq 'query'){Get-BaxySpotifyQueryOverlap $Title "
        "(Get-BaxySpotifyPressedResult $name '') $FunctionWords $PurposeMarkers}else{0}"
    )
    assert overlap in page
    # Revisión 2: the rank is computed only for a control that passed the type, name and place filters (a handful
    # per page), never for each of the elements of the tree before filtering.
    assert page.index("if($element.Type -ne $button -or $element.Offscreen){continue}") < page.index(overlap)
    assert page.index("$rect.Right -le $WindowRect.Right)){continue}") < page.index(overlap)
    # Position decides only between equals; in exact mode every control ranks 0, so the old leftmost rule holds.
    assert "($overlap -gt $playCandidateOverlap -or ($overlap -eq $playCandidateOverlap -and $rect.Left -lt $playCandidateLeft))" in page
    # The exact-mode match of the control's name is the one it always was.
    assert "else{$name -eq $ExpectedPlay -or $name.StartsWith($ExpectedPlay+' ')}" in page


def test_r24_the_output_says_whether_what_plays_matches_the_query() -> None:
    play = _between("$stage='play_clicked'", "$failure=")
    assert (
        "$matchesQuery=Test-BaxySpotifyMatchesQuery $foldTitle $pressedResult $selectedFlipped "
        "@($observedNowPlaying,$windowNow) $queryFunctionWords $queryPurposeMarkers"
    ) in play
    assert "matchesQuery=$(if($Mode -eq 'query'){$matchesQuery}else{$null})" in SOURCE
    # The match is a fact for the receipt; it never turns a verified start into a failure nor the reverse.
    assert "$verified=$evidence -eq 'started'" in play
    assert SOURCE.index(
        "$pressedOverlap=Get-BaxySpotifyQueryOverlap $foldTitle $pressedResult $queryFunctionWords $queryPurposeMarkers"
    ) < SOURCE.index("InvokeElement $playCandidate.Element")


def test_r24b_the_query_words_come_from_data_before_any_effect() -> None:
    # Palabras vacías desde datos: the adapter passes query_function_words.v1.json; a query search without them fails
    # before searching, never compares with every word counted.
    load = _between("$queryFunctionWords=@()", "$expectedPlay=")
    assert "if(-not $QueryWordsBase64){throw 'spotify_query_words_missing'}" in load
    assert "$queryFunctionWords=@($queryWords.function_words)+@($queryWords.medium_words)" in load
    assert "$queryPurposeMarkers=@($queryWords.purpose_markers)" in load
    assert SOURCE.index("$queryFunctionWords=@()") < SOURCE.index("$effect=$true")
    words = json.loads(QUERY_WORDS.read_text(encoding="utf-8"))
    for key in ("function_words", "medium_words", "purpose_markers"):
        values = words[key]
        # Folded (lower case, no accents, one word each) and sorted, like every catalog.
        assert values == sorted(set(values)), key
        assert all(re.fullmatch(r"[a-z0-9]+", value) for value in values), key
    # Short content words are never function words: they count («rap», «pop», «fi»).
    assert not {"rap", "pop", "fi", "rock", "cumbia", "lofi"} & set(words["function_words"] + words["medium_words"])
    assert {"lo", "los", "para"} <= set(words["function_words"] + words["purpose_markers"])


def test_r24b_every_phase_reads_one_cached_snapshot_and_discovery_asks_for_its_control_types() -> None:
    # Ronda 23 (t1-c07 «pon lo-fi para estudiar en spotify plis», 38,4 s; t4-c01, 32,5 s): four FindAll with
    # TrueCondition, then each element's properties read across the process boundary in every loop, and every name
    # folded by a PowerShell loop over its characters in each of those loops.
    assert "Condition]::TrueCondition" not in SOURCE
    main = _between("\ntry {\n    # M169", "\n} catch {\n    Add-BaxySpotifyMark\n    [pscustomobject]@{ok=$false;effectObserved=$effect;error='spotify_uia_failed'")
    assert ".Current.Name" not in main
    assert "$element.Current." not in main
    snapshot = _between("function Get-BaxySpotifySnapshot", "function Read-BaxySpotifySearchValue")
    assert "CacheRequest" in snapshot
    for prop in ("NameProperty", "ControlTypeProperty", "BoundingRectangleProperty", "IsOffscreenProperty",
                 "RuntimeIdProperty"):
        assert f"$cache.Add([Windows.Automation.AutomationElement]::{prop})" in snapshot
    assert "[Windows.Automation.NotCondition]::new([Windows.Automation.PropertyCondition]::new(" in snapshot
    assert snapshot.count(".FindAll(") == 1
    assert "$activation.Dispose()" in snapshot
    assert "Fold=(Fold $name)" in snapshot
    # Each of the four phases takes exactly one snapshot per poll; discovery asks UIA only for the combo (and the play
    # buttons while a cold client builds its page) by a PropertyCondition on the control type.
    assert SOURCE.count("Get-BaxySpotifySnapshot $root") == 4
    startup = _between("$searchDeadline=(Get-Date).AddMilliseconds(12500)", "if($null -eq $process){throw")
    assert "[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::ComboBox)" in startup
    assert "Get-BaxySpotifySnapshot $root $(if($coldStart -and -not $playableSeen){$discoveryCombosAndButtons}else{$discoveryCombos})" in startup
    # Fold is two regular expressions, never a loop over the characters.
    fold = _between("function Fold(", "function Test-BaxySpotifyNear")
    assert "ToCharArray" not in fold
    assert "[regex]::Replace(" in fold
    # Presses act on the live element behind the cached copy.
    assert "InvokeElement $candidate.Element" in SOURCE
    assert "InvokeElement $playCandidate.Element" in SOURCE
    assert "InvokeElement $replayControl.Element" in SOURCE


# Encargo SP (2026-10-12): t1-c07 «pon lo-fi para estudiar en spotify plis» and t2-c01 «pone los bunkers en spotify pa
# estudiar», same code, played in tandas fin1 and failed in fin2 (stage «searched», spotify_element_not_actionable,
# «no pude confirmar si se hizo»). Frozen data: the four turns and four runs of the script on redpc, one snapshot per
# poll after the search URI.
SP_DATA = json.loads((ROOT / "tests" / "data" / "sp_spotify_reproducir.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def sp_choices(tmp_path_factory) -> dict[str, list[dict[str, object]]]:
    block = _between("# BEGIN playback-evidence", "# END playback-evidence")
    words = json.loads(QUERY_WORDS.read_text(encoding="utf-8"))
    data = tmp_path_factory.mktemp("sp") / "data.json"
    data.write_text(json.dumps(SP_DATA["runs"], ensure_ascii=False), encoding="utf-8")

    def array(values: list[str]) -> str:
        return "@(" + ",".join(f"'{value}'" for value in values) + ")"

    harness = "\n".join([
        "Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes,WindowsBase",
        "[Console]::OutputEncoding=[Text.Encoding]::UTF8",
        block,
        f"$fw={array(words['function_words'] + words['medium_words'])}",
        f"$pm={array(words['purpose_markers'])}",
        "function SpRect($r){[Windows.Rect]::new($r[0],$r[1],$r[2],$r[3])}",
        "function Rows($rows){$list=New-Object 'System.Collections.Generic.List[object]';"
        "foreach($x in $rows){$list.Add([pscustomobject]@{Element=$null;Id=$x.id;Name=$x.name;Fold=$x.name;"
        "Type=[Windows.Automation.ControlType]::($x.type);Rect=(SpRect $x.rect);Offscreen=$false})};return ,$list}",
        f"$runs=[IO.File]::ReadAllText('{data}',[Text.Encoding]::UTF8)|ConvertFrom-Json",
        "$none=New-Object 'System.Collections.Generic.HashSet[string]'",
        "$out=[ordered]@{}",
        "foreach($run in $runs){",
        "  $before=Get-BaxySpotifyPageBefore $run.value_before $run.query @((Rows $run.page_before)|ForEach-Object {Get-BaxySpotifyRowKey $_})",
        "  $expected=Fold('Reproducir '+$run.query)",
        "  $polls=@(foreach($poll in @([pscustomobject]@{ms=0;value=$run.value_before;rows=$run.page_before})+@($run.polls)){",
        "    $rows=Rows $poll.rows",
        "    $new=Select-BaxySpotifySearchResult $rows $before 'query' $run.query $expected (SpRect $run.search_box) (SpRect $run.window) $fw $pm",
        "    $old=Select-BaxySpotifySearchResult $rows $none 'query' $run.query $expected (SpRect $run.search_box) (SpRect $run.window) $fw $pm",
        "    [ordered]@{ms=$poll.ms;answered=$new.Answered;play=$(if($new.Play){$new.Play.Fold}else{''});"
        "card=$(if($new.Card){$new.Card.Fold}else{''});"
        "oldReady=($poll.value -eq $run.query -and $null -ne $old.Play);oldPlay=$(if($old.Play){$old.Play.Fold}else{''})}",
        "  })",
        "  $out[$run.run]=$polls",
        "}",
        "# Contracase: the page before already was this search (its box held the query): its results count.",
        "$last=$runs[2].polls[-1]",
        "$same=Get-BaxySpotifyPageBefore $last.value $runs[2].query @((Rows $last.rows)|ForEach-Object {Get-BaxySpotifyRowKey $_})",
        "$c=Select-BaxySpotifySearchResult (Rows $last.rows) $same 'query' $runs[2].query (Fold('Reproducir '+$runs[2].query)) (SpRect $runs[2].search_box) (SpRect $runs[2].window) $fw $pm",
        "$out['same_search']=@([ordered]@{ms=0;answered=$c.Answered;play=$c.Play.Fold;card='';oldReady=$true;oldPlay=''})",
        "# X3: pr8 (los bunkers -> lo fi para estudiar) with its results drawn on the elements of the page before, as",
        "# Spotify reuses them (each new play control takes the runtime id of a play control of the page before).",
        "$run=$runs[2]",
        "$beforeRows=Rows $run.page_before",
        "$x3before=Get-BaxySpotifyPageBefore $run.value_before $run.query @($beforeRows|ForEach-Object {Get-BaxySpotifyRowKey $_})",
        "$ids=@($beforeRows|Where-Object {$_.Type -eq [Windows.Automation.ControlType]::Button}|ForEach-Object {$_.Id})",
        "$reused=Rows $run.polls[-1].rows",
        "$k=0",
        "foreach($row in $reused){if($row.Type -eq [Windows.Automation.ControlType]::Button -and $row.Fold.StartsWith('reproducir ') -and -not $x3before.Contains((Get-BaxySpotifyRowKey $row))){$row.Id=$ids[$k % $ids.Count];$k++}}",
        "$exp=Fold('Reproducir '+$run.query)",
        "$r=Select-BaxySpotifySearchResult $reused $x3before 'query' $run.query $exp (SpRect $run.search_box) (SpRect $run.window) $fw $pm",
        "$out['x3_reused']=@([ordered]@{ms=$k;answered=$r.Answered;play=$(if($r.Play){$r.Play.Fold}else{''});card='';oldReady=$false;oldPlay=@($reused|ForEach-Object {$_.Id})})",
        "# Contracase: a search that never shows anything new (every element as before) still finds nothing.",
        "$n=Select-BaxySpotifySearchResult $beforeRows $x3before 'query' 'cumbia' (Fold('Reproducir cumbia')) (SpRect $run.search_box) (SpRect $run.window) $fw $pm",
        "$out['x3_nothing_new']=@([ordered]@{ms=0;answered=$n.Answered;play=$(if($n.Play){$n.Play.Fold}else{''});card=$(if($n.Card){$n.Card.Fold}else{''});oldReady=$false;oldPlay=''})",
        "$out|ConvertTo-Json -Compress -Depth 5",
    ])
    script = tmp_path_factory.mktemp("sp") / "choices.ps1"
    script.write_text(harness, encoding="utf-8-sig")
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script)],
        capture_output=True, text=True, encoding="utf-8", timeout=120, check=True,
    )
    return json.loads(completed.stdout.strip().splitlines()[-1])


# The live runs on redpc of the same code: what each one pressed once the wait ended, and what then played (verified).
_SP_PRESSED = {
    "pr7": ("reproducir", "los bunkers"),  # «Los Bunkers - Llueve Sobre La Ciudad»
    "dry6": ("reproducir lo fi focus study work beats musica para concentrarte en estudiar o trabajar", ""),  # pr6
    "pr8": ("reproducir lo fi focus study work beats musica para concentrarte en estudiar o trabajar", ""),  # Snowfall
    "pr9": ("reproducir el baile de los que sobran", "los prisioneros"),  # «El Baile De Los Que Sobran»
}


def _sp_arrival(polls: list[dict[str, object]]) -> dict[str, object]:
    return next(poll for poll in polls if poll["answered"])


def test_sp_the_wait_ends_on_the_search_page_with_the_control_the_live_run_played(sp_choices) -> None:
    for run, (play, card) in _SP_PRESSED.items():
        polls = sp_choices[run]
        arrival = _sp_arrival(polls)
        # Before the search page: the page before (Home, the library rows, the previous search) and what a cold
        # client drew after it was read («reproducir descubrimiento semanal», «reproducir 00s rock anthems») never
        # end the wait.
        assert all(not poll["answered"] for poll in polls[: polls.index(arrival)]), run
        assert (arrival["play"], arrival["card"]) == (play, card), run
    # Contracase: the page before already was this search (the box held the query): its own results count at once.
    assert sp_choices["same_search"][0]["answered"] is True
    assert sp_choices["same_search"][0]["play"] == _SP_PRESSED["pr8"][0]


def test_sp_the_former_proof_by_the_box_value_ended_on_the_page_before(sp_choices) -> None:
    # The fin2 mechanism on the frozen runs: the box already held the query while the page was not the search's, so
    # the former readiness (value + any play control) ended the wait there, on a control of the page before.
    before_arrival = {
        run: [poll for poll in polls[: polls.index(_sp_arrival(polls))] if poll["oldReady"]]
        for run, polls in sp_choices.items() if run in _SP_PRESSED
    }
    assert {run: [poll["oldPlay"] for poll in polls] for run, polls in before_arrival.items()} == {
        "pr7": ["reproducir los bunkers"],  # a row of the person's library, not the search
        "dry6": ["reproducir tus me gusta"],
        "pr8": ["reproducir tus me gusta"],
        "pr9": ["reproducir tus me gusta"],
    }
    # Even on the search page a library row outranked the results on a tie (all overlap 0, leftmost): pr9.
    assert _sp_arrival(sp_choices["pr9"])["oldPlay"] == "reproducir tus me gusta"


def test_sp_fin2_pressed_before_any_measured_search_page_and_fin1_after(sp_choices) -> None:
    arrivals = {run: _sp_arrival(sp_choices[run])["ms"] for run in _SP_PRESSED}
    cold = [arrivals["pr7"], arrivals["dry6"]]
    by_run: dict[str, list[dict[str, object]]] = {}
    for turn in SP_DATA["tandas"]:
        by_run.setdefault(turn["run"], []).append(turn)
    assert all(not turn["verified"] and turn["receipt"]["detail"] == "spotify_element_not_actionable"
               and turn["receipt"]["stage"] == "searched" for turn in by_run["fin2"])
    assert all(turn["verified"] for turn in by_run["fin1"])
    # fin2 pressed (and failed) 1.3-1.5 s after the URI: before the earliest search page measured (2.6 s); fin1 pressed
    # after the latest cold one (3.6 s) and played.
    assert max(turn["uri_to_end_ms"] for turn in by_run["fin2"]) < min(arrivals.values())
    assert min(turn["uri_to_end_ms"] for turn in by_run["fin1"]) > max(cold)


def test_sp_a_press_uses_the_control_s_own_action_before_a_click() -> None:
    # Encargo SP (redpc, cold client, «lo-fi para estudiar»): two clicks at the centre of «Reproducir Lo-Fi Focus…»
    # left no trace in 15 s, twice; its InvokePattern played it at once (4 of 4 cold and warm). The click remains for
    # a control without the pattern, and a control with neither is not actionable.
    invoke = _between("function InvokeElement", "function Wait-BaxyPoll")
    assert invoke.index("InvokePattern]::Pattern") < invoke.index("[BaxySpotifyNative]::Click(")
    assert invoke.index("[BaxySpotifyNative]::Click(") < invoke.index("throw 'spotify_element_not_actionable'")


def test_x3_results_drawn_on_reused_elements_are_results_of_this_search(sp_choices) -> None:
    # Encargo X3 (tandas n1/n2 del notebook, tests/data/x3_spotify_notebook.json): Spotify reuses elements across
    # searches (in pr8/pr9 the filter chips keep their runtime ids on the next search). On pr8's arrival with every new
    # play control drawn on an element of the page before, the runtime id alone set them all aside; the id with the
    # name keeps them, and the wait ends on the control the live run played.
    reused = sp_choices["x3_reused"][0]
    assert reused["ms"] >= 10  # the ten lo-fi results, each on a reused element
    before_ids = {row["id"] for row in SP_DATA["runs"][2]["page_before"]}
    assert set(reused["oldPlay"]) - before_ids  # the rest of the page kept its own ids
    assert reused["answered"] is True
    assert reused["play"] == _SP_PRESSED["pr8"][0]
    # Contracase: a page that shows nothing new (every element with the id and the name it had) answers nothing, and
    # the call still ends spotify_exact_result_not_found.
    nothing = sp_choices["x3_nothing_new"][0]
    assert (nothing["answered"], nothing["play"], nothing["card"]) == (False, "", "")


X3_DATA = json.loads((ROOT / "tests" / "data" / "x3_spotify_notebook.json").read_text(encoding="utf-8"))


def test_x3_the_notebook_failures_ran_out_the_wait_and_the_one_success_set_nothing_aside() -> None:
    # The measured shape of the notebook runs: 7 of 8 calls «spotify_exact_result_not_found» after the 20 s horizon of
    # a page with nothing playable and its one re-issued search (Get-BaxySpotifySearchPageSeconds,
    # Test-BaxySpotifyResearch), on a client that played these same queries before SP; the success (t4-c01 turn 4 of
    # n2, the same query as the turn before) issued its search 0.7 s after «spotify:», with no read of the page before
    # (its box already held the query, so nothing was set aside), and played at the first look.
    failures = [call for call in X3_DATA["calls"] if call["error"]]
    successes = [call for call in X3_DATA["calls"] if not call["error"]]
    assert len(failures) == 7 and all(call["error"] == "spotify_exact_result_not_found" for call in failures)
    for call in failures:
        launches = call["spotify_launches_s"]
        searched = launches[1]
        assert launches[-1] - searched >= 8, call  # the re-issued search
        assert call["core_call_s"] >= searched + 20, call  # the whole horizon
    [success] = successes
    assert success["played"] and success["query"] == "cumbia"
    assert success["spotify_launches_s"][1] - success["spotify_launches_s"][0] < 1
    assert len(success["spotify_launches_s"]) == 2 and success["core_call_s"] < 20
    research = _between("function Test-BaxySpotifyResearch", "function Test-BaxySpotifyTermIn")
    assert "$SinceSearchMilliseconds -ge 8000" in research
    assert "return 20" in _between("function Get-BaxySpotifySearchPageSeconds", "function Test-BaxySpotifyResearch")


def test_x3_a_search_with_nothing_picked_is_told_as_such_never_as_no_results() -> None:
    # Juez de n2 (t1-c07, t2-c01, t4-c01): «la búsqueda … no devolvió resultados» and «nothing is playing» were not
    # what happened: BAXY searched and pressed nothing; what plays was not read.
    from baxy_mind.compose_situation import _CAUSE_FACT

    cause = _CAUSE_FACT["spotify_exact_result_not_found"]
    assert "searched" in cause and "nothing was pressed" in cause and "not checked" in cause
    assert "no result" not in cause and "nothing is playing" not in cause


def test_sp2_nothing_is_searched_or_pressed_after_the_deadline() -> None:
    assert "[int]$DeadlineMs=0" in SOURCE
    deadline_check = "if((Get-Date) -ge $hardEnd){throw 'spotify_deadline_reached'}"
    search = _between("$searchUri='spotify:search:'", "$searchedAt=Get-Date")
    assert search.index(deadline_check) < search.index("Start-Process $searchUri")
    # The first press: the check comes before the press is counted as a possible effect.
    press = _between("$flipBefore=$false", "$presses=1")
    assert press.index(deadline_check) < press.index("$effect=$true") < press.index("InvokeElement $playCandidate")
    # Every press (the card, the re-press) goes through InvokeElement, which checks first.
    invoke = _between("function InvokeElement", "function Wait-BaxyPoll")
    assert invoke.index(deadline_check) < invoke.index("Invoke()")
    # A run the deadline stopped says its stage and the time of each stage.
    catch = SOURCE[SOURCE.rindex("} catch {"):]
    assert "Add-BaxySpotifyMark" in catch
    assert "stage=$stage;detail=$_.Exception.Message;timings=$timings" in catch
    for stage in ("searched", "candidate", "result", "play_clicked"):
        assert f"Add-BaxySpotifyMark;$stage='{stage}'" in SOURCE


@pytest.mark.parametrize(
    ("hard_end_seconds", "expected"),
    [(-1, "False"), (3600, "True")],
)
def test_sp2_every_wait_ends_by_the_deadline(tmp_path, hard_end_seconds, expected) -> None:
    helper = _between("function Wait-BaxyPoll", "function Confirm-BaxySpotifyForeground")
    script = tmp_path / "wait.ps1"
    script.write_text(
        "\n".join([
            f"$hardEnd=(Get-Date).AddSeconds({hard_end_seconds})",
            helper,
            "$sw=[Diagnostics.Stopwatch]::StartNew()",
            "$r=Wait-BaxyPoll ((Get-Date).AddSeconds(30)) 50",
            "\"$r $($sw.ElapsedMilliseconds)\"",
        ]),
        encoding="utf-8-sig",
    )
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script)],
        capture_output=True, text=True, encoding="utf-8", timeout=60, check=True,
    )
    result, elapsed = completed.stdout.strip().splitlines()[-1].split()
    assert result == expected
    # A wait past the deadline returns at once; one before it sleeps one interval, never the 30 s horizon.
    assert int(elapsed) < 1000


# Encargo SP3 (tandas n9/n10 del notebook): t1-c07 and t2-c01 played in n9 and ended «spotify_exact_result_not_found»
# after 24 s in n10, the only failure of the script whose output carried no stage, detail or times (the receipt kept
# nothing). It now says them like every other failure: the stage, what the last look of the page showed, and when.
def test_sp3_a_search_that_picked_nothing_says_its_stage_what_it_saw_and_when(tmp_path) -> None:
    not_found = _between("if($null -eq $candidate){", "exit 2")
    assert "Add-BaxySpotifyMark" in not_found
    assert "stage=$stage;detail=$detail;timings=$timings" in not_found
    research = _between("$searches=2", "} while((Wait-BaxyPoll $searchPageDeadline 500))")
    assert research.index("Start-Process $searchUri") < research.index("Add-BaxySpotifyMark 'researched'")
    block = _between("# BEGIN playback-evidence", "# END playback-evidence")
    data = tmp_path / "data.json"
    data.write_text(json.dumps(SP_DATA["runs"][2], ensure_ascii=False), encoding="utf-8")
    script = tmp_path / "detail.ps1"
    script.write_text("\n".join([
        "Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes,WindowsBase",
        "[Console]::OutputEncoding=[Text.Encoding]::UTF8",
        block,
        "function SpRect($r){[Windows.Rect]::new($r[0],$r[1],$r[2],$r[3])}",
        "function Rows($rows){$list=New-Object 'System.Collections.Generic.List[object]';"
        "foreach($x in $rows){$list.Add([pscustomobject]@{Element=$null;Id=$x.id;Name=$x.name;Fold=$x.name;"
        "Type=[Windows.Automation.ControlType]::($x.type);Rect=(SpRect $x.rect);Offscreen=$false})};return ,$list}",
        f"$run=[IO.File]::ReadAllText('{data}',[Text.Encoding]::UTF8)|ConvertFrom-Json",
        "$before=Get-BaxySpotifyPageBefore $run.value_before $run.query @((Rows $run.page_before)|ForEach-Object {Get-BaxySpotifyRowKey $_})",
        "$box=SpRect $run.search_box; $win=SpRect $run.window",
        "$expected=Fold('Reproducir '+$run.query)",
        "# The page never changed (every element as before), then the search page arrived: the count of kept play",
        "# controls is the one the choice of the search page made.",
        "$same=Rows $run.page_before",
        "$c=Select-BaxySpotifySearchResult $same $before 'query' $run.query $expected $box $win @() @()",
        "Get-BaxySpotifyNotFoundDetail $same $before $c.Shown 2 $false $true $false",
        "$arrived=Rows $run.polls[-1].rows",
        "$c=Select-BaxySpotifySearchResult $arrived $before 'query' $run.query $expected $box $win @() @()",
        "Get-BaxySpotifyNotFoundDetail $arrived $before $c.Shown 1 $true $false $true",
    ]), encoding="utf-8-sig")
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script)],
        capture_output=True, text=True, encoding="utf-8", timeout=120, check=True,
    )
    unchanged, arrived = completed.stdout.strip().splitlines()[-2:]

    def fields(line: str) -> dict[str, str]:
        code, *pairs = line.split(";")
        assert code == "spotify_exact_result_not_found"
        return dict(pair.split("=") for pair in pairs)

    unchanged_fields, arrived_fields = fields(unchanged), fields(arrived)
    page_before = SP_DATA["runs"][2]["page_before"]
    assert unchanged_fields["rows"] == unchanged_fields["before"] == str(len(page_before))
    assert int(unchanged_fields["plays"]) > 0
    assert (unchanged_fields["fresh"], unchanged_fields["shown"]) == ("0", "0")
    assert (unchanged_fields["searches"], unchanged_fields["cold"], unchanged_fields["box"], unchanged_fields["iconic"]) == ("2", "0", "1", "0")
    assert int(arrived_fields["fresh"]) >= int(arrived_fields["shown"]) > 0
    assert (arrived_fields["searches"], arrived_fields["cold"], arrived_fields["box"], arrived_fields["iconic"]) == ("1", "1", "0", "1")
    # The adapter carries at most 300 characters of a detail into the receipt.
    assert max(len(unchanged), len(arrived)) < 300
