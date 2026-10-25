"""Defects of bench_decision.py seen by PC-Q (2026-10-25) and left as they are: its judge's identity in every run is the
sha256 of the whole file (run_record's judge_sha256, 8935ddf0… for holdouts v5 and v6), so any change to it, even one
that does not touch judge(), gives the next runs another judge. The fix is the owner's decision; these tests show the
defect and turn green when it is fixed (strict xfail)."""
import json
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "renew"))

import bench_decision  # noqa: E402

KEEPS_THE_JUDGE = "fixing it changes bench_decision.py and with it judge_sha256 (8935ddf0…): the owner decides"


class FakeServer:
    made: list = []

    def __init__(self, gguf, server, **options):
        import os
        self.slot_dir = os.environ.get("BAXY_VISION_SLOT_DIR") or "LOCALAPPDATA/BAXY/renew/slots (the product's)"
        self._process = types.SimpleNamespace(pid=0)
        self.closed = False
        FakeServer.made.append(self)

    def start(self):
        pass

    def wait_ready(self, timeout):
        pass

    def close(self):
        self.closed = True


class DeadSystemOne:
    made: list = []

    def __init__(self, *args):
        self.ready, self.closed = False, False
        self._process = types.SimpleNamespace(poll=lambda: 3, returncode=3)
        DeadSystemOne.made.append(self)

    def start(self):
        pass

    def close(self):
        self.closed = True


class FakeMind:
    def __init__(self, server, trace, system_one=None):
        pass

    def configure(self, catalog):
        pass

    def warm(self):
        pass

    def new_session(self, history):
        pass

    def decide(self, case_id, text, pending=None):
        return {"kind": "conversation", "reply": "hola"}


@pytest.fixture
def decision(tmp_path, monkeypatch):
    FakeServer.made.clear()
    DeadSystemOne.made.clear()
    package = types.ModuleType("baxy_mind")
    package.__path__ = []
    monkeypatch.setitem(sys.modules, "baxy_mind", package)
    monkeypatch.setitem(sys.modules, "baxy_mind.llm_server", types.SimpleNamespace(LlmServer=FakeServer))
    monkeypatch.setitem(sys.modules, "baxy_mind.mind", types.SimpleNamespace(Mind=FakeMind))
    monkeypatch.setitem(sys.modules, "baxy_mind.system_one", types.SimpleNamespace(SystemOne=DeadSystemOne))
    monkeypatch.setattr(bench_decision, "BANKS", tmp_path)
    monkeypatch.setattr(bench_decision, "gpu_used_mib", lambda: None)
    monkeypatch.setattr(bench_decision, "resources", lambda *a: {})
    monkeypatch.setattr(bench_decision, "run_record", lambda *a: {})
    monkeypatch.setenv("BAXY_RENEW_DECIDE_TEMPERATURE", "0.2")
    monkeypatch.setenv("BAXY_DATA_DIR", str(tmp_path / "datos"))
    monkeypatch.delenv("BAXY_VISION_SLOT_DIR", raising=False)
    monkeypatch.delenv("BAXY_S1_GGUF", raising=False)
    catalog, cases = tmp_path / "catalog.json", tmp_path / "cases.json"
    catalog.write_text(json.dumps({"capabilities": []}), encoding="utf-8")
    cases.write_text(json.dumps([{"id": "P1", "text": "hola", "expect": {"kind": "text"}}]), encoding="utf-8")

    def run(label):
        monkeypatch.setattr(sys, "argv", ["bench_decision.py", label, "--cases", str(cases), "--catalog", str(catalog)])
        bench_decision.main()
    return run, monkeypatch


@pytest.mark.xfail(strict=True, reason=KEEPS_THE_JUDGE)
def test_a_run_stopped_because_system_one_died_closes_qwens_server(decision):
    # main() has no finally: wait_system_one's SystemExit (and any exception outside the per-case try: the catalog,
    # configure, warm, resources, a Ctrl+C) leaves Qwen's llama-server and System One's running after python exits.
    run, monkeypatch = decision
    monkeypatch.setenv("BAXY_S1_GGUF", "laya.gguf")
    with pytest.raises(SystemExit, match="exited"):
        run("s1-muerto")
    assert FakeServer.made[0].closed and DeadSystemOne.made[0].closed


@pytest.mark.xfail(strict=True, reason=KEEPS_THE_JUDGE)
def test_two_runs_keep_their_prompt_prefix_in_folders_of_their_own(decision):
    # Every run's llama-server saves its prefix in the same --slot-save-path (BAXY_VISION_SLOT_DIR or the product's
    # LOCALAPPDATA\BAXY\renew\slots) and LlmServer.save_prefix removes every other key's state there: two runs at once
    # (2026-10-25) collided on baxy_prefix_*.slot with WinError 32, and a run removes the product's own kept prefix.
    run, _ = decision
    run("a")
    run("b")
    assert FakeServer.made[0].slot_dir != FakeServer.made[1].slot_dir
