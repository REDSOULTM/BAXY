"""The harness cleans up after itself (PC-Q, 2026-10-25): what a run started dies with it, whatever stopped it; a path
with spaces starts the product. Doubles only: no product, no model, no GPU."""
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "renew"))

import bench_e2e  # noqa: E402
import bench_falsedades  # noqa: E402


class FakeConductor:
    instances: list = []

    def __init__(self, run_dir, profile):
        self.events = self
        self.closed = False
        FakeConductor.instances.append(self)

    def wait(self, predicate, timeout):
        return {"type": "runtime", "mindReady": True}

    def close(self):
        self.closed = True


class ReadyIsolation:
    def __init__(self, run_dir):
        pass

    def check(self):
        return None


def test_an_e2e_run_that_breaks_mid_bank_still_closes_the_product(tmp_path, monkeypatch):
    # A case that raised (an events.jsonl line cut, a Ctrl+C) left BAXY, its mind and llama-server running, and the
    # owner's Notepad tabs set aside (they are put back by Conductor.close).
    FakeConductor.instances.clear()
    monkeypatch.setattr(bench_e2e, "BANKS", tmp_path)
    monkeypatch.setattr(bench_e2e, "Isolation", ReadyIsolation)
    monkeypatch.setattr(bench_e2e, "Conductor", FakeConductor)
    monkeypatch.setattr(bench_e2e, "session_locked", lambda: False)
    monkeypatch.setattr(bench_e2e.run_meta, "product_record", lambda *a: {})

    def broken(*args):
        raise RuntimeError("events.jsonl: a line cut halfway")

    monkeypatch.setattr(bench_e2e, "judge_case", broken)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps([{"id": "E001"}]), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["bench_e2e.py", "x", "--cases", str(cases)])
    with pytest.raises(RuntimeError):
        bench_e2e.main()
    assert FakeConductor.instances and FakeConductor.instances[0].closed


def _falsedades_doubles(monkeypatch, tmp_path):
    FakeConductor.instances.clear()
    for module in (bench_falsedades, bench_e2e):
        monkeypatch.setattr(module, "ps_file", lambda path, lines: None)
        monkeypatch.setattr(module, "run_ps", lambda path, env, timeout: (0, "BENCH-READY"))
    monkeypatch.setattr(bench_falsedades, "Conductor", FakeConductor)
    monkeypatch.setattr(bench_falsedades.run_meta, "product_record", lambda *a: {})
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))


def test_a_falsehood_run_stopped_by_the_lock_screen_closes_the_product(tmp_path, monkeypatch):
    _falsedades_doubles(monkeypatch, tmp_path)
    monkeypatch.setattr(bench_falsedades, "session_locked", lambda: True)
    with pytest.raises(SystemExit, match="sesion_bloqueada"):
        bench_falsedades.run_conversations([{"id": "F001", "turns": []}], tmp_path)
    assert FakeConductor.instances[0].closed


def test_a_falsehood_run_whose_conversation_broke_closes_the_product(tmp_path, monkeypatch):
    _falsedades_doubles(monkeypatch, tmp_path)
    monkeypatch.setattr(bench_falsedades, "session_locked", lambda: False)

    def broken(conductor, case):
        raise KeyboardInterrupt

    monkeypatch.setattr(bench_falsedades, "converse", broken)
    with pytest.raises(KeyboardInterrupt):
        bench_falsedades.run_conversations([{"id": "F001", "turns": [{"text": "hola"}]}], tmp_path)
    assert FakeConductor.instances[0].closed
