"""scripts/renew/tandas.py: a bank split into batches of at most --por cases and their runs joined back as one run."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "renew"))

import summarize  # noqa: E402
import tandas  # noqa: E402

RUN = {"mind_sha256": "m", "judge_sha256": "j", "gguf": {"sha256": "g"}, "temp": 0.2}


def _cases(n: int) -> list[dict]:
    return [{"id": f"C{i}", "family": "a" if i % 2 else "b", "text": "x", "expect": {"kind": "text"}} for i in range(n)]


def _run(path: Path, label: str, rows: list[dict], run: dict | None = None) -> Path:
    summary = {"label": label, "ok": sum(r["ok"] for r in rows), "n": len(rows), "warm_s": 3.0, "run": run or RUN}
    path.write_text("\n".join(json.dumps(x) for x in [{"summary": summary}, *rows]) + "\n", encoding="utf-8")
    return path


def _row(case_id: str, ok: bool, family: str = "a", latency: float = 1.0, **extra) -> dict:
    return {"id": case_id, "family": family, "ok": ok, "excluded": False, "latency_s": latency, "error": None, **extra}


def test_partir_keeps_every_case_once_in_order_in_batches_of_at_most_por(tmp_path):
    cases = tmp_path / "decision.json"
    cases.write_text(json.dumps(_cases(7)), encoding="utf-8")
    written = tandas.partir(cases, 3, tmp_path / "t")
    assert [p.name for p in written] == ["decision.t01.json", "decision.t02.json", "decision.t03.json"]
    batches = [json.loads(p.read_text(encoding="utf-8")) for p in written]
    assert [len(b) for b in batches] == [3, 3, 1]
    assert [c["id"] for b in batches for c in b] == [f"C{i}" for i in range(7)]


def test_partir_refuses_repeated_ids_and_a_file_that_is_not_a_list(tmp_path):
    cases = tmp_path / "c.json"
    cases.write_text(json.dumps([{"id": "A"}, {"id": "A"}]), encoding="utf-8")
    with pytest.raises(SystemExit, match="repeated"):
        tandas.partir(cases, 5, tmp_path / "t")
    cases.write_text(json.dumps({"cases": []}), encoding="utf-8")
    with pytest.raises(SystemExit, match="not a non-empty list"):
        tandas.partir(cases, 5, tmp_path / "t")


def test_juntar_counts_like_one_run_and_keeps_each_batch_summary(tmp_path):
    one = _run(tmp_path / "x-t1.jsonl", "x-t1", [_row("C0", True, "b"), _row("C1", False, "a", 2.0)])
    two = _run(tmp_path / "x-t2.jsonl", "x-t2", [_row("C2", True, "b", 3.0),
                                                 {**_row("C3", False), "excluded": True},
                                                 {**_row("C4", False), "error": "HTTP 500"}])
    joined = tandas.juntar([one, two])
    assert (joined["ok"], joined["n"], joined["accuracy"]) == (2, 4, 0.5)
    assert joined["excluded_retired"] == ["C3"] and joined["error_ids"] == ["C4"] and joined["errors"] == 1
    assert joined["families"] == {"b": [2, 2], "a": [0, 2]}
    assert joined["run"] == RUN and [t["label"] for t in joined["tandas"]] == ["x-t1", "x-t2"]


def test_juntar_refuses_runs_measured_with_another_mind_or_a_case_run_twice(tmp_path):
    one = _run(tmp_path / "a.jsonl", "a", [_row("C0", True)])
    other = _run(tmp_path / "b.jsonl", "b", [_row("C1", True)], {**RUN, "mind_sha256": "otra"})
    with pytest.raises(SystemExit, match="mind_sha256"):
        tandas.juntar([one, other])
    again = _run(tmp_path / "c.jsonl", "c", [_row("C0", False)])
    with pytest.raises(SystemExit, match="C0"):
        tandas.juntar([one, again])


def test_the_joined_file_is_read_by_summarize_as_one_decision_run(tmp_path, monkeypatch):
    one = _run(tmp_path / "x-t1.jsonl", "x-t1", [_row("C0", True)])
    two = _run(tmp_path / "x-t2.jsonl", "x-t2", [_row("C1", False)])
    out = tmp_path / "x-decision.jsonl"
    monkeypatch.setattr(sys, "argv", ["tandas.py", "juntar", str(out), str(one), str(two)])
    tandas.main()
    assert summarize.first(out)["ok"] == 1 and summarize.first(out)["n"] == 2
    assert [json.loads(line)["id"] for line in out.read_text(encoding="utf-8").splitlines()[1:]] == ["C0", "C1"]
