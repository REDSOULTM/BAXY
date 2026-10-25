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


class ExitedServer:
    """A llama-server that could not start (its GGUF missing, its port taken): it exited at once."""

    def __init__(self, *args, **kwargs):
        self.pid = 0

    def poll(self):
        return 1

    def terminate(self):
        pass

    def kill(self):
        pass

    def wait(self, timeout=None):
        return 1


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def test_the_judge_does_not_wait_fifteen_minutes_for_a_server_that_exited(tmp_path, monkeypatch):
    clock = {"now": 0.0, "asked": 0}

    def urlopen(*args, **kwargs):
        clock["asked"] += 1
        raise urllib.error.URLError("refused")

    def sleep(seconds):
        clock["now"] += seconds

    monkeypatch.setattr(bench_falsedades.subprocess, "Popen", ExitedServer)
    monkeypatch.setattr(bench_falsedades.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(bench_falsedades.time, "sleep", sleep)
    monkeypatch.setattr(bench_falsedades.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(bench_falsedades, "JUDGE_PORT", _free_port())
    with pytest.raises(SystemExit, match="judge"):
        bench_falsedades.judge([[]], tmp_path)
    assert clock["asked"] <= 1 and clock["now"] < 5


class Healthy(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - http.server's name
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, *args):
        pass


def test_a_server_left_on_the_judges_port_never_judges_in_its_place(tmp_path, monkeypatch):
    # A judge server orphaned by a run that was killed holds the port: the new one cannot bind and exits, and the
    # orphan (whatever model it loaded) answered the health check and every line.
    foreign = HTTPServer(("127.0.0.1", 0), Healthy)
    threading.Thread(target=foreign.serve_forever, daemon=True).start()
    try:
        monkeypatch.setattr(bench_falsedades, "JUDGE_PORT", foreign.server_address[1])
        monkeypatch.setattr(bench_falsedades.subprocess, "Popen", ExitedServer)
        with pytest.raises(SystemExit, match="in use"):
            bench_falsedades.judge([[]], tmp_path)
    finally:
        foreign.shutdown()
        foreign.server_close()
