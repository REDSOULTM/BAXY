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
    out = capsys.readouterr().out
    assert out.startswith(f"runs: {tmp_path} (banks ") and "líneas 0" in out


def test_the_runs_read_are_those_of_baxy_renew_banks(tmp_path, monkeypatch):
    import importlib
    monkeypatch.setenv("BAXY_RENEW_BANKS", str(tmp_path))
    try:
        importlib.reload(chequeo_offline)
        assert chequeo_offline.RUNS == tmp_path / "runs"
    finally:
        monkeypatch.undo()
        importlib.reload(chequeo_offline)


def test_the_notebooks_paired_ab_reads_the_runs_of_baxy_renew_banks(tmp_path):
    import os
    import subprocess
    for prefix, ok in (("A", False), ("B", True)):
        run = tmp_path / "runs" / f"{prefix}-s0-e2e-e2e"
        run.mkdir(parents=True)
        (run / "results.jsonl").write_text(json.dumps({"summary": {}}) + "\n"
                                           + json.dumps({"id": "E001", "ok": ok, "status": "ok"}) + "\n",
                                           encoding="utf-8")
    script = Path(__file__).resolve().parents[1] / "scripts" / "renew" / "notebook" / "ayudas" / "pareado_ab.py"
    done = subprocess.run([sys.executable, "-X", "utf8", str(script), "A", "B", "0"], capture_output=True, text=True,
                          encoding="utf-8", env={**os.environ, "BAXY_RENEW_BANKS": str(tmp_path)},
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    assert done.returncode == 0, done.stderr
    assert done.stdout.startswith(f"runs: {tmp_path / 'runs'} (banks BAXY_RENEW_BANKS)")
    assert "up ['E001']" in done.stdout
