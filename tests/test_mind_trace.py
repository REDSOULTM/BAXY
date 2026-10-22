"""The mind's trace (src/baxy_mind/__main__.py, BAXY Renew al máximo 11.6): it has a size cap."""
from pathlib import Path

from baxy_mind.__main__ import bounded_trace


def test_a_trace_past_its_cap_is_kept_once_as_dot_one_and_a_new_one_starts(tmp_path: Path) -> None:
    trace = tmp_path / "renew" / "turns.jsonl"
    trace.parent.mkdir()
    (trace.parent / "turns.jsonl.1").write_text("older\n", encoding="utf-8")
    trace.write_text("x" * 101, encoding="utf-8")

    assert bounded_trace(trace, limit=100) == trace

    assert not trace.exists()
    assert (trace.parent / "turns.jsonl.1").read_text(encoding="utf-8") == "x" * 101


def test_a_trace_under_its_cap_stays_and_a_missing_folder_is_made(tmp_path: Path) -> None:
    trace = tmp_path / "renew" / "turns.jsonl"
    assert bounded_trace(trace, limit=100) == trace
    assert trace.parent.is_dir()

    trace.write_text("x" * 100, encoding="utf-8")
    bounded_trace(trace, limit=100)

    assert trace.read_text(encoding="utf-8") == "x" * 100
    assert not (trace.parent / "turns.jsonl.1").exists()
