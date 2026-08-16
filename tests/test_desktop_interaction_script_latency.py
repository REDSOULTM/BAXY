from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTERNAL = ROOT / "src" / "Baxy.Providers.Windows" / "External"
FOLDER_SOURCE = (EXTERNAL / "KnownFolderOpen.ps1").read_text(encoding="utf-8")
FILE_SOURCE = (EXTERNAL / "KnownFileOpen.ps1").read_text(encoding="utf-8")
SELECT_SOURCE = (EXTERNAL / "DesktopSelectAll.ps1").read_text(encoding="utf-8")


def _between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    end_index = source.index(end, start_index)
    return source[start_index:end_index]


def _assert_bounded_poll_helper(source: str) -> None:
    helper = _between(source, "function Wait-BaxyPoll", "\ntry {")
    assert "$remaining=$Deadline-(Get-Date)" in helper
    assert "$remaining.TotalMilliseconds -le 0" in helper
    assert "[Math]::Min(" in helper
    assert "$IntervalMilliseconds" in helper
    assert "[Math]::Ceiling($remaining.TotalMilliseconds)" in helper


def test_known_folder_observes_before_waiting_and_retains_eight_second_horizon() -> None:
    _assert_bounded_poll_helper(FOLDER_SOURCE)
    poll = _between(
        FOLDER_SOURCE,
        "$deadline=(Get-Date).AddSeconds(8)",
        "[pscustomobject]@{version=1;ok=$verified",
    )

    assert poll.index("$shell.Windows()") < poll.index(
        "Wait-BaxyPoll $deadline 250"
    )
    assert "Start-Sleep -Milliseconds 250" not in poll
    assert "[Uri]::UnescapeDataString" in poll
    assert "[IO.Path]::GetFullPath($observed)" in poll
    assert "[StringComparison]::OrdinalIgnoreCase" in poll


def test_known_file_retains_stability_window_but_fails_on_observed_exit() -> None:
    assert "Start-Sleep -Milliseconds 350" not in FILE_SOURCE
    wait_index = FILE_SOURCE.index("$exited=$process.WaitForExit(350)")
    verify_index = FILE_SOURCE.index(
        "$verified=-not $exited -and -not $process.HasExited"
    )

    assert wait_index < verify_index
    assert "$null -ne $process" in FILE_SOURCE
    assert "known_folder_latest_safe_file_process_postread" in FILE_SOURCE


def test_select_all_observes_before_waiting_and_retains_250_ms_horizon() -> None:
    _assert_bounded_poll_helper(SELECT_SOURCE)
    poll = _between(
        SELECT_SOURCE,
        "$deadline=(Get-Date).AddMilliseconds(250)",
        "[pscustomobject]@{\n        version=1\n        ok=$verified",
    )

    assert poll.index("FocusedElement") < poll.index(
        "Wait-BaxyPoll $deadline 25"
    )
    assert "Start-Sleep -Milliseconds 250" not in poll


def test_select_all_poll_keeps_exact_identity_and_selection_postreads() -> None:
    assert re.search(
        r"\[int\]\$focusedAfter\.Current\.ProcessId\s+-ne\s+\$processId",
        SELECT_SOURCE,
    )
    assert "$afterHandle -ne $nativeHandle" in SELECT_SOURCE
    assert "$selection.Count -eq 1" in SELECT_SOURCE
    assert SELECT_SOURCE.count("CompareEndpoints(") == 2
    assert "$textLength -gt 0" in SELECT_SOURCE
    assert "$selectionStart -eq 0" in SELECT_SOURCE
    assert "$selectionEnd -eq [uint32]$textLength" in SELECT_SOURCE
    assert "select_all_input_not_accepted" in SELECT_SOURCE
    assert "select_all_postcondition_not_verified" in SELECT_SOURCE
