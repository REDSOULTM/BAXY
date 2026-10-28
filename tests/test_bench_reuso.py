"""A run folder is one conductor's (R8-NB-2, 2026-10-28): repeated with a label already used, the e2e bench read the
earlier run's events.jsonl as its own and stopped at once on that run's «conductor_not_ready», before the new App had
emptied the file; the new App would also have replayed the earlier commands/ from 00001 on. A used folder is refused
and left as it was. Doubles only: no product, no desktop."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "renew"))

import bench_e2e  # noqa: E402
import bench_falsedades  # noqa: E402

EARLIER = [{"type": "meta", "profile": "p", "t_ms": 339},
           {"type": "runtime", "ready": True, "mindReady": False, "status": "x", "t_ms": 189123},
           {"type": "terminal", "kind": "blocked_environment", "t_ms": 189130}]


def earlier_run(run_dir: Path, events: bool = True) -> None:
    (run_dir / "commands").mkdir(parents=True)
    (run_dir / "commands" / "00001.json").write_text('{"exit": true}', encoding="utf-8")
    if events:
        (run_dir / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in EARLIER), encoding="utf-8")


def no_launch(monkeypatch) -> list:
    launched = []
    monkeypatch.setattr(bench_e2e.subprocess, "Popen", lambda command, **options: launched.append(options) or
                        SimpleNamespace())
    monkeypatch.setattr(bench_e2e, "set_aside_notepad_tabs", lambda backup: 0)
    return launched


@pytest.mark.parametrize("events", [True, False])
def test_a_folder_an_earlier_conductor_wrote_is_refused_and_kept(tmp_path, monkeypatch, events) -> None:
    run_dir = tmp_path / "r-e2e"
    earlier_run(run_dir, events)
    before = {p.name: p.read_bytes() for p in run_dir.rglob("*") if p.is_file()}
    launched = no_launch(monkeypatch)
    with pytest.raises(SystemExit, match="new label"):
        bench_e2e.Conductor(run_dir, tmp_path / "perfil")
    assert not launched
    assert {p.name: p.read_bytes() for p in run_dir.rglob("*") if p.is_file()} == before


def test_the_e2e_bench_refuses_a_used_label_before_the_desktop_is_looked_at(tmp_path, monkeypatch) -> None:
    earlier_run(tmp_path / "runs" / "r-e2e")
    (tmp_path / "runs" / "r-e2e" / "results.jsonl").write_text('{"summary": {"ok": 3}}\n', encoding="utf-8")
    cases = tmp_path / "cases.json"
    cases.write_text('[{"id": "C1"}]', encoding="utf-8")
    monkeypatch.setattr(bench_e2e, "BANKS", tmp_path)
    monkeypatch.setattr(bench_e2e, "Isolation", lambda run_dir: pytest.fail("the isolation check ran"))
    monkeypatch.setattr(sys, "argv", ["bench_e2e.py", "r", "--cases", str(cases)])
    with pytest.raises(SystemExit, match="new label"):
        bench_e2e.main()
    assert (tmp_path / "runs" / "r-e2e" / "results.jsonl").read_text(encoding="utf-8") == '{"summary": {"ok": 3}}\n'


def test_a_void_run_left_no_conductor_so_its_folder_starts_again(tmp_path, monkeypatch) -> None:
    run_dir = tmp_path / "r-e2e"
    run_dir.mkdir()
    (run_dir / "results.jsonl").write_text('{"summary": {"void": "x"}}\n', encoding="utf-8")
    (run_dir / "commands").mkdir()
    launched = no_launch(monkeypatch)
    conductor = bench_e2e.Conductor(run_dir, tmp_path / "perfil")
    assert len(launched) == 1 and conductor.events.wait(lambda e: True, 0.2) is None
    launched[0]["stdout"].close()


def test_the_falsehood_bench_keeps_the_used_folders_transcripts(tmp_path, monkeypatch) -> None:
    run_dir = tmp_path / "r-falsedades"
    earlier_run(run_dir)
    (run_dir / "transcripts.json").write_text("[]", encoding="utf-8")

    def no_isolation(run_dir):
        raise AssertionError("a used folder is refused before the desktop is looked at")

    monkeypatch.setattr(bench_falsedades, "Isolation", no_isolation)
    with pytest.raises(SystemExit, match="new label"):
        bench_falsedades.run_conversations([], run_dir)
    assert (run_dir / "transcripts.json").read_text(encoding="utf-8") == "[]"
