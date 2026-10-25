"""maximo/chequeo_offline.py over stored runs (PC-Q, 2026-10-25): no model, no product."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "renew" / "maximo"))

import chequeo_offline  # noqa: E402


def test_a_run_killed_mid_line_does_not_stop_the_check(tmp_path, monkeypatch):
    # An e2e run killed while the conductor wrote leaves its events.jsonl with half a line at the end: json.loads
    # raised and no run after it was read.
    run = tmp_path / "pc-x-e2e"
    run.mkdir()
    events = [{"type": "command.done", "session": "new"}, {"type": "turn.start", "input": {"text": "hola"}},
              {"type": "message", "speaker": "baxy", "body": "Hola."}]
    (run / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events) + '\n{"type": "ste', encoding="utf-8")
    monkeypatch.setattr(chequeo_offline, "RUNS", tmp_path)
    found = list(chequeo_offline._conversations())
    assert [(bank, case, [t["person"] for t in turns]) for bank, _, case, turns in found] == [("e2e", "S00", ["hola"])]


def test_with_no_line_to_check_it_says_so_instead_of_failing(tmp_path, monkeypatch, capsys):
    # On a machine without the practice runs (the notebook reads D:), the timings were empty: IndexError at the end.
    monkeypatch.setattr(chequeo_offline, "RUNS", tmp_path)
    monkeypatch.setattr(chequeo_offline, "HAND", tmp_path / "none.json")
    monkeypatch.setattr(sys, "argv", ["chequeo_offline.py"])
    assert chequeo_offline.main() == 0
    assert "líneas 0" in capsys.readouterr().out
