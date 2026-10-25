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
