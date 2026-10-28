"""Isolation of the e2e and falsehood benches from the owner (w6-banco, 2026-10-23: the PC e2e typed into the owner's
unsaved Notepad tab, and benches left files in the owner's home): a target-app window the bench did not open makes the
run VOID, files a case created outside the sandbox go to the case's quarantine, the owner's are only reported, and the
owner's saved Notepad tabs are set aside and put back. Also the falsehood bench's summary across replicas."""
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "renew"))

import bench_e2e  # noqa: E402
import bench_falsedades  # noqa: E402


def test_the_precondition_reads_ready_void_or_a_check_that_could_not_run() -> None:
    assert bench_e2e.void_reason(0, "BENCH-READY\r\n") is None
    out = "BENCH-VOID foreign window: Notepad pid=1 hwnd=2 title='x'\nbench_void_foreign_window"
    assert bench_e2e.void_reason(1, out) == "BENCH-VOID foreign window: Notepad pid=1 hwnd=2 title='x'"
    assert bench_e2e.void_reason(1, "no se encuentra bench.ps1").startswith("precondition_failed")


def test_a_void_setup_stops_before_the_case_and_a_ready_one_records_its_windows(tmp_path, monkeypatch) -> None:
    isolation = bench_e2e.Isolation(tmp_path)
    outputs = iter([(1, "BENCH-VOID foreign window: Notepad pid=4 hwnd=9 title='notas'"),
                    (0, "BENCH-READY\nTARGET-WINDOW 77 Notepad\n")])
    monkeypatch.setattr(bench_e2e, "run_ps", lambda path, env, timeout: next(outputs))
    case = {"id": "E001", "setup": ["Reset-Sandbox"]}
    _, _, void = bench_e2e.run_setup(case, tmp_path, {}, isolation)
    assert void.startswith("BENCH-VOID")
    script = [line for line in (tmp_path / "setup.ps1").read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    assert script[1:4] == ["Assert-BenchPrecondition", "Show-TargetWindows", "Save-BenchProfile -Name 'E001'"]
    assert script[-1] == "Reset-Sandbox"
    assert bench_e2e.run_setup(case, tmp_path, {}, isolation)[2] is None
    assert isolation.before == {77}


def test_windows_a_case_left_open_are_the_benchs_for_the_next_precondition(tmp_path, monkeypatch) -> None:
    isolation = bench_e2e.Isolation(tmp_path)
    isolation.before = {5}
    after = ("PROFILE-REMOVED C:\\Users\\x\\tareas_hoy.txt\nPROFILE-CHANGED C:\\Users\\x\\config.ini\n"
             "PROFILE-RESTORED\nTARGET-WINDOW 5 Notepad\nTARGET-WINDOW 8 Notepad\n")
    monkeypatch.setattr(bench_e2e, "run_ps", lambda path, env, timeout: (0, after))
    report = isolation.after("E002", tmp_path)
    assert report["removed"] == ["C:\\Users\\x\\tareas_hoy.txt"] and report["changed"] == ["C:\\Users\\x\\config.ini"]
    assert report["restored"] and report["target_windows_left"] == [8]
    assert isolation.owned == {8} and isolation.env({})["BAXY_BENCH_OWNED_HWNDS"] == "8"
    summary = bench_e2e.profile_summary([{"id": "E002", "profile": report}])
    assert summary["profile_quarantined"] == ["E002: C:\\Users\\x\\tareas_hoy.txt"]
    assert summary["profile_review"] == ["E002: C:\\Users\\x\\config.ini"] and summary["target_windows_left"] == ["E002"]


def test_the_owners_notepad_tabs_are_set_aside_and_put_back(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(bench_e2e, "notepad_running", lambda: False)
    tabs, backup, bench = tmp_path / "TabState", tmp_path / "owner", tmp_path / "bench"
    tabs.mkdir()
    (tabs / "owner.bin").write_text("unsaved", encoding="utf-8")
    assert bench_e2e.set_aside_notepad_tabs(backup, tabs) == 1 and not any(tabs.iterdir())
    (tabs / "bench.bin").write_text("typed by a case", encoding="utf-8")
    assert bench_e2e.put_back_notepad_tabs(backup, bench, tabs) == []
    assert [p.name for p in tabs.iterdir()] == ["owner.bin"] and [p.name for p in bench.iterdir()] == ["bench.bin"]


def test_with_notepad_open_nothing_moves(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(bench_e2e, "notepad_running", lambda: True)
    tabs = tmp_path / "TabState"
    tabs.mkdir()
    (tabs / "owner.bin").write_text("unsaved", encoding="utf-8")
    assert bench_e2e.set_aside_notepad_tabs(tmp_path / "owner", tabs) == 0 and (tabs / "owner.bin").exists()


@pytest.mark.skipif(not bench_e2e.LIB.is_file(), reason="the bench library lives on the banks drive")
def test_the_library_moves_only_what_the_case_created(tmp_path) -> None:
    home = tmp_path / "home"
    for folder in ("Documents/viejo", "Desktop", "AppData", "BAXY-bench"):
        (home / folder).mkdir(parents=True)
    (home / "Documents/viejo/mio.txt").write_text("del dueño", encoding="utf-8")
    (home / "owner.ini").write_text("x", encoding="utf-8")
    os.utime(home / "owner.ini", (1_700_000_000, 1_700_000_000))
    name, quarantine = f"pytest-{uuid.uuid4().hex[:8]}", tmp_path / "quarantine"
    script = tmp_path / "case.ps1"
    script.write_text("\r\n".join([
        f". '{bench_e2e.LIB}'",
        f"Save-BenchProfile -Name '{name}'",
        "Start-Sleep -Milliseconds 200",
        f"[IO.File]::WriteAllText('{home / 'tareas_hoy.txt'}', 'a')",
        f"New-Item -ItemType Directory -Path '{home / 'q4' / 'sub'}' -Force | Out-Null",
        f"[IO.File]::WriteAllText('{home / 'q4' / 'sub' / 'notes.txt'}', 'b')",
        f"[IO.File]::WriteAllText('{home / 'owner.ini'}', 'changed')",
        f"[IO.File]::WriteAllText('{home / 'AppData' / 'x.txt'}', 'c')",
        f"[IO.File]::WriteAllText('{home / 'BAXY-bench' / 's.txt'}', 'd')",
        f"Remove-Item -LiteralPath '{home / 'Documents' / 'viejo' / 'mio.txt'}'",
        f"Restore-BenchProfile -Name '{name}' -Quarantine '{quarantine}'"]) + "\r\n", encoding="utf-8-sig")
    done = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
                          env={**os.environ, "BAXY_BENCH_PROFILE_ROOT": str(home)})
    report = bench_e2e.profile_report(done.stdout)
    assert report["restored"], done.stdout + done.stderr
    assert sorted(Path(p).name for p in report["removed"]) == ["notes.txt", "tareas_hoy.txt"]
    assert sorted(Path(p).name for p in report["removed_dirs"]) == ["q4", "sub"]
    assert [Path(p).name for p in report["changed"]] == ["owner.ini"]
    assert [Path(p).name for p in report["missing"]] == ["mio.txt"]
    assert (quarantine / "tareas_hoy.txt").is_file() and (quarantine / "q4" / "sub" / "notes.txt").is_file()
    assert not (home / "q4").exists() and (home / "owner.ini").read_text(encoding="utf-8") == "changed"
    assert (home / "AppData" / "x.txt").is_file() and (home / "BAXY-bench" / "s.txt").is_file()


def test_the_replicas_summary_counts_each_case_across_seeds() -> None:
    def summary(seed, cases, lines):
        return {"label": f"x-s{seed}", "seed": seed, "falsedades": len(cases), "casos_con_falsedad": cases,
                "lines": lines, "lineas_sin_juzgar": 0, "lineas_a_revisar": [f"{c} t1" for c in cases],
                "setup_failed": [], "turnos_fallidos": [], "profile_quarantined": [], "profile_review": []}

    across = bench_falsedades.replicas_summary("x", [summary(0, ["F002", "F015"], 30), summary(1, ["F002"], 31),
                                                     summary(2, ["F002", "F013"], 30)])
    assert across["falsedades_por_replica"] == [2, 1, 2] and across["falsedades_media"] == 1.67
    assert across["casos_con_falsedad"] == {"F002": "3/3", "F013": "1/3", "F015": "1/3"}
    assert across["casos_en_mayoria"] == ["F002"] and across["lineas"] == 91
    assert across["lineas_a_revisar"][0] == "s0 F002 t1" and across["runs"] == ["x-s0", "x-s1", "x-s2"]


# R8-NB-1: the tabs a case's setup and turns opened in the person's browser stayed open (NB-R7: 47 → 70+ tabs in Opera
# GX, and a page left by one case changed the next one's result). They are told apart by UI Automation runtime id.
def test_only_the_tabs_the_case_opened_are_closed() -> None:
    before = {1: (True, {"42.1", "42.2"})}
    now = {1: (True, {"42.1", "42.2", "42.9"}), 2: (True, {"42.7", "42.8"})}
    close, unsure = bench_e2e.tabs_to_close(before, now)
    assert close == {1: ["42.9"], 2: ["42.7", "42.8"]} and unsure == []
    # A tab the turn closed is not reopened and nothing else moves.
    assert bench_e2e.tabs_to_close(before, {1: (True, {"42.1"})}) == ({}, [])


def test_tabs_whose_identity_cannot_be_trusted_are_left_and_said() -> None:
    before = {1: (True, {"42.1", "42.2"}), 3: (False, {"42.5"})}
    # Every tab of window 1 changed id while it still has tabs: the ids were rebuilt, so none is known to be the case's.
    close, unsure = bench_e2e.tabs_to_close(before, {1: (True, {"43.1", "43.2", "43.3"}), 3: (True, {"42.5", "42.6"})})
    assert close == {} and sorted(unsure) == ["1 ids_changed", "3 partial_before"]
    close, unsure = bench_e2e.tabs_to_close(before, {1: (False, {"42.1", "42.2", "42.9"})})
    assert close == {} and unsure == ["1 partial_now"]
    # Without a list from before the case (the read did not finish), nothing is closed.
    assert bench_e2e.tabs_to_close(None, {1: (True, {"42.1"})}) == ({}, ["no_list_before"])


def test_the_case_runs_list_the_tabs_before_the_setup_and_close_the_new_ones_after(tmp_path, monkeypatch) -> None:
    isolation = bench_e2e.Isolation(tmp_path)
    lines = isolation.prelude("E003")
    assert lines[-1] == bench_e2e.TABS_LIST and f"& '{bench_e2e.TABS}' -List" in lines[-1]
    isolation.started("BENCH-READY\nBROWSER-WINDOW 10 whole\nBROWSER-TAB 10 42.1\nBROWSER-TABS-READ\n")
    calls = []

    def run_ps(path, env, timeout):
        calls.append(path.read_text(encoding="utf-8-sig"))
        if len(calls) == 1:
            return 0, ("PROFILE-RESTORED\nBROWSER-WINDOW 10 whole\nBROWSER-TAB 10 42.1\nBROWSER-TAB 10 42.4\n"
                       "BROWSER-TAB 10 42.5\nBROWSER-TABS-READ\n")
        return 0, "TAB-CLOSED 10 42.4\nTAB-LEFT 10 42.5 offscreen\n"

    monkeypatch.setattr(bench_e2e, "run_ps", run_ps)
    report = isolation.after("E003", tmp_path)
    assert bench_e2e.TABS_LIST in calls[0]
    assert f"& '{bench_e2e.TABS}' -Window 10 -Close '42.4','42.5'" in calls[1]
    assert report["browser_tabs_closed"] == ["10 42.4"] and report["browser_tabs_left"] == ["10 42.5 offscreen"]
    summary = bench_e2e.profile_summary([{"id": "E003", "profile": report}])
    assert summary["browser_tabs_left"] == ["E003: 10 42.5 offscreen"]
