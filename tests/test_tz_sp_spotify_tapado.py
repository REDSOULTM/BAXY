"""Encargo TZ-SP: why two Spotify searches of the z2 tandas picked nothing (t2-c01 «pone los bunkers en spotify pa
estudiar», t4-c01 «y ponme cumbia mientras») while z1, on the same commit, played them.

Measured: both searches left every element of the page as before and the box never showed the query, through the
re-issued search, while the client held the front; the call after found the results already drawn. In redpc that
shape comes only from a window above the client that covers all of it (tests/data/tz_sp_spotify_tapado.json): the
client draws nothing new under it and draws the pending search as soon as it goes. The script now says, in the detail
of a search that picked nothing, whether the client was in front and who covered all of it.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "src" / "Baxy.Providers.Windows" / "External" / "SpotifyDesktopAutomation.ps1"
SOURCE = SCRIPT.read_text(encoding="utf-8")
DATA = json.loads((ROOT / "tests" / "data" / "tz_sp_spotify_tapado.json").read_text(encoding="utf-8"))
SP_DATA = json.loads((ROOT / "tests" / "data" / "sp_spotify_reproducir.json").read_text(encoding="utf-8"))


def _between(start: str, end: str) -> str:
    head = SOURCE.index(start)
    return SOURCE[head:SOURCE.index(end, head)]


def _fields(detail: str) -> dict[str, str]:
    code, *pairs = detail.split(";")
    assert code == "spotify_exact_result_not_found"
    return dict(pair.split("=", 1) for pair in pairs)


def _marks(timings: str) -> dict[str, int]:
    return {key: int(value) for key, value in (pair.split("=") for pair in timings.strip(";").split(";"))}


def _powershell(tmp_path: Path, lines: list[str]) -> list[str]:
    script = tmp_path / "probe.ps1"
    script.write_text("\n".join(lines), encoding="utf-8-sig")
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script)],
        capture_output=True, text=True, encoding="utf-8", timeout=120, check=True,
    )
    return completed.stdout.strip().splitlines()


def test_z2_both_searches_left_the_page_as_it_was_while_the_client_held_the_front() -> None:
    for call in DATA["z2_not_found"]:
        fields = _fields(call["detail"])
        rows, before = int(fields["rows"]), int(fields["before"])
        # Every element as before (one more drawn at most), no play control of this search, the box never the query.
        assert rows - before <= 1 and rows > 700, call
        assert (fields["fresh"], fields["shown"], fields["box"], fields["iconic"]) == ("0", "0", "0", "0"), call
        # The search and its re-issue were both made (the client was found and brought up), and the whole horizon
        # passed: not a deadline, not a missing window, not a choice the model made.
        assert fields["searches"] == "2" and fields["cold"] == "0", call
        marks = _marks(call["timings"])
        assert marks["researched"] - marks["started"] >= 8000, call
        assert marks["searched"] - marks["started"] >= 20000, call
        assert call["core_call_s"] < 30
        # The final told that nothing was picked and that what plays was not read, never that something plays.
        assert "no pude elegir" in call["final"] and "suena" not in call["final"] and "Está sonando" not in call["final"]


def test_the_call_after_found_the_results_already_drawn_and_a_first_call_waits_for_them() -> None:
    # Contracase (z1, and the first call of each tanda): a search the client draws takes 4.5-5.8 s from the search to
    # the verified playback; right after a search that stayed undrawn, 2.4-2.9 s: its page was already there.
    after = [call["core_call_s"] - call["search_s"] for call in DATA["played"] if call["after_not_found"]]
    first = [call["core_call_s"] - call["search_s"] for call in DATA["played"] if not call["after_not_found"]]
    assert after and first
    assert max(after) < 3.0 < 4.0 < min(first)


def test_redpc_only_a_window_over_all_of_the_client_keeps_its_page_as_it_was() -> None:
    probes = DATA["redpc_probes"]
    whole = [probe for probe in probes if probe["cover"].startswith("whole")]
    others = [probe for probe in probes if not probe["cover"].startswith("whole")]
    assert len(whole) == 2 and len(others) >= 8
    # Under a window that covers all of it the client never drew the search, even holding the front and with the
    # search re-issued; it drew the pending one as soon as the cover went.
    for probe in whole:
        assert probe["landed_ms"] is None and probe["front"], probe
    [uncovered] = [probe for probe in whole if "uncovered_ms" in probe]
    assert uncovered["uncovered_ms"] > 14000 and uncovered["landed_after_uncover_ms"] < 1000
    # Minimized, partly covered, covered after the search or brought up from behind: drawn within 5 s.
    for probe in others:
        assert probe["landed_ms"] is not None and probe["landed_ms"] < 5000, probe
    # The branch's script under a whole cover gives z2's very shape.
    covered = _fields(DATA["redpc_script_under_whole_cover"]["detail"])
    z2 = _fields(DATA["z2_not_found"][0]["detail"])
    for key in ("searches", "cold", "fresh", "shown", "box", "iconic"):
        assert covered[key] == z2[key], key
    assert covered["rows"] == covered["before"]


def _native(tmp_path: Path) -> str:
    source = _between("$nativeSource=@'", "\n'@")[len("$nativeSource=@'"):]
    path = tmp_path / "native.cs"
    path.write_text(source, encoding="utf-8")
    return f"Add-Type -TypeDefinition ([IO.File]::ReadAllText('{path}'))"


@pytest.mark.parametrize(
    ("window", "above", "covered"),
    [
        # redpc probe 3: a topmost window over the whole screen, the client maximized (its frame is the work area).
        ((0, 0, 1920, 1032), [(0, 0, 1920, 1080)], True),
        # redpc probes 3 and 6: 60 px of the client left uncovered: drawn.
        ((0, 0, 1920, 1032), [(60, 0, 1920, 1032)], False),
        # Two windows that tile over all of it cover it; with a gap between them they do not.
        ((902, 0, 1920, 1020), [(0, 0, 1400, 1020), (1400, 0, 1920, 1020)], True),
        ((902, 0, 1920, 1020), [(0, 0, 1400, 1020), (1401, 0, 1920, 1020)], False),
        # The notebook's own geometry (Spotify on the right half, physical pixels) under the Task Manager the owner
        # keeps always on top (its saved position: 0,60-1572,1020): a part shows, so it is not covered.
        ((902, 0, 1920, 1020), [(0, 60, 1572, 1020)], False),
        # Nothing above.
        ((902, 0, 1920, 1020), [], False),
    ],
)
def test_covers_is_true_only_when_the_windows_above_leave_nothing_of_it(tmp_path, window, above, covered) -> None:
    def box(rect: tuple[int, int, int, int]) -> str:
        left, top, right, bottom = rect
        return f"$b=New-Object 'BaxySpotifyNative+Box';$b.Left={left};$b.Top={top};$b.Right={right};$b.Bottom={bottom};$b"

    lines = [_native(tmp_path), f"$w=$({box(window)})", "$a=New-Object 'System.Collections.Generic.List[BaxySpotifyNative+Box]'"]
    lines += [f"$a.Add($({box(rect)}))" for rect in above]
    lines.append("[BaxySpotifyNative]::Covers($w,$a.ToArray())")
    assert _powershell(tmp_path, lines)[-1] == str(covered)


def test_covered_by_reads_frames_and_ignores_the_client_s_own_and_see_through_windows() -> None:
    covered_by = _between("public static string CoveredBy(", "\n}\n'@")
    frame = _between("static bool Frame(", "public static bool Covers(")
    # The drawn frame (DWMWA_EXTENDED_FRAME_BOUNDS), cut to the screens: a maximized client's rectangle reaches past
    # them and no window could ever cover that part (redpc probe 7, before this: «covered=0» under a whole cover).
    assert "DwmGetWindowFrame(handle,9," in frame and "GetSystemMetrics(78)" in frame
    assert "Frame(handle,out window)" in covered_by and "Frame(other,out box)" in covered_by
    # Only what is above it in z-order (GW_HWNDPREV), shown, not minimized, not cloaked, of another process, and not
    # a layered window that lets it show through.
    assert "GetWindow(handle,3)" in covered_by and "GetWindow(other,3)" in covered_by
    assert "IsWindowVisible(other)" in covered_by and "IsIconic(other)" in covered_by
    assert "process==own" in covered_by and "DwmGetWindowAttribute(other,14," in covered_by
    assert "GetLayeredWindowAttributes(other," in covered_by
    # Reading only: nothing is moved, raised or activated.
    for act in ("SetWindowPos", "BringWindowToTop", "ShowWindow"):
        assert act not in covered_by and act not in frame


def test_a_search_that_picked_nothing_says_whether_the_client_was_in_front_and_who_covered_it(tmp_path) -> None:
    call = _between("$detail=Get-BaxySpotifyNotFoundDetail", "\n")
    assert "[BaxySpotifyNative]::GetForegroundWindow() -eq $process.MainWindowHandle" in call
    assert "[BaxySpotifyNative]::CoveredBy($process.MainWindowHandle)" in call
    block = _between("# BEGIN playback-evidence", "# END playback-evidence")
    run = SP_DATA["runs"][2]
    data = tmp_path / "data.json"
    data.write_text(json.dumps(run, ensure_ascii=False), encoding="utf-8")
    lines = [
        "Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes,WindowsBase",
        "[Console]::OutputEncoding=[Text.Encoding]::UTF8",
        block,
        "function SpRect($r){[Windows.Rect]::new($r[0],$r[1],$r[2],$r[3])}",
        "function Rows($rows){$list=New-Object 'System.Collections.Generic.List[object]';"
        "foreach($x in $rows){$list.Add([pscustomobject]@{Element=$null;Id=$x.id;Name=$x.name;Fold=$x.name;"
        "Type=[Windows.Automation.ControlType]::($x.type);Rect=(SpRect $x.rect);Offscreen=$false})};return ,$list}",
        f"$run=[IO.File]::ReadAllText('{data}',[Text.Encoding]::UTF8)|ConvertFrom-Json",
        "$before=Get-BaxySpotifyPageBefore $run.value_before $run.query @((Rows $run.page_before)|ForEach-Object {Get-BaxySpotifyRowKey $_})",
        "$same=Rows $run.page_before",
        # z2's shape under a whole cover (redpc probe 7), and the contracase: the same page with nothing over it.
        "Get-BaxySpotifyNotFoundDetail $same $before 0 2 $false $false $false $true 'Taskmgr'",
        "Get-BaxySpotifyNotFoundDetail $same $before 0 2 $false $false $false $true ''",
    ]
    covered, uncovered = (_fields(line) for line in _powershell(tmp_path, lines)[-2:])
    assert (covered["front"], covered["covered"]) == ("1", "Taskmgr")
    assert (uncovered["front"], uncovered["covered"]) == ("1", "0")
    assert covered["rows"] == covered["before"] and covered["fresh"] == "0"
