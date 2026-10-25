"""The smaller harness scripts (PC-Q, 2026-10-25): they close what they start and find the banks where the rest do."""
import json
import sys
import types
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1] / "scripts" / "renew"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "ayudas"))

import continuacion  # noqa: E402
import make_arms_d20  # noqa: E402
import summarize_arms_d20  # noqa: E402


class FakeServer:
    made: list = []

    def __init__(self, *args, **options):
        self.closed = False
        FakeServer.made.append(self)

    def start(self):
        pass

    def wait_ready(self, timeout):
        pass

    def close(self):
        self.closed = True


class ColdMind:
    def __init__(self, server, trace):
        pass

    def configure(self, catalog):
        pass

    def warm(self):
        raise TimeoutError("llama-server did not answer the warm-up")


def test_the_continuation_probe_closes_its_server_when_it_breaks(tmp_path, monkeypatch):
    FakeServer.made.clear()
    package = types.ModuleType("baxy_mind")
    package.__path__ = []
    monkeypatch.setitem(sys.modules, "baxy_mind", package)
    monkeypatch.setitem(sys.modules, "baxy_mind.llm_server", types.SimpleNamespace(LlmServer=FakeServer))
    monkeypatch.setitem(sys.modules, "baxy_mind.mind", types.SimpleNamespace(Mind=ColdMind))
    monkeypatch.setattr(continuacion, "RUNS", tmp_path)
    monkeypatch.setenv("BAXY_AYUDAS", "none")
    monkeypatch.setenv("BAXY_RENEW_DECIDE_TEMPERATURE", "0.2")
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps({"capabilities": []}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["continuacion.py", "x", "--src", str(tmp_path), "--catalog", str(catalog)])
    with pytest.raises(TimeoutError):
        continuacion.main()
    assert FakeServer.made[0].closed


def test_the_d20_arms_go_to_the_banks_of_baxy_renew_banks(tmp_path, monkeypatch):
    written = []
    monkeypatch.setattr(make_arms_d20, "write", lambda out, arm, seed: written.append(out) or out)
    monkeypatch.setenv("BAXY_RENEW_BANKS", str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["make_arms_d20.py", "base", "--seeds", "0"])
    make_arms_d20.main()
    assert written == [tmp_path / "ab"]


def test_the_d20_summary_reads_the_runs_of_baxy_renew_banks(tmp_path, monkeypatch, capsys):
    (tmp_path / "runs").mkdir()
    (tmp_path / "runs" / "pcq-prueba-base-s0-dec.jsonl").write_text(
        json.dumps({"summary": {"ok": 7, "p50": 1.5}}) + "\n", encoding="utf-8")
    monkeypatch.setenv("BAXY_RENEW_BANKS", str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["summarize_arms_d20.py", "--prefix", "pcq-prueba"])
    summarize_arms_d20.main()
    assert capsys.readouterr().out.startswith("base     dec [7]")
