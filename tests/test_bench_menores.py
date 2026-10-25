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
