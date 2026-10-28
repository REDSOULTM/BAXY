"""bench_decision.main() closes what it started, whatever happens after the server is made, and gives each run a slot
folder of its own (held-out tests, written from the fix's specification only).

Positive: an exception in server.start, mind.configure, server.wait_ready or mind.warm, a catalog that is missing or not
JSON, a Ctrl+C while the cases run and System One's death all leave Qwen's server and System One's closed, and the
exception still reaches the caller. A run without BAXY_VISION_SLOT_DIR keeps its slots under BANKS/runs, by label,
never in the product's LOCALAPPDATA/BAXY/renew/slots.
Negative: a given BAXY_VISION_SLOT_DIR is kept as it is; a normal run writes runs/<label>.jsonl as before and closes
the server once without error; a case whose decide raises is still a failed case and the run ends normally."""
import json
import os
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "renew"))

import bench_decision  # noqa: E402

# What each fake raises, by stage ("start", "wait_ready", "configure", "warm", "decide"); reset by the fixture.
PLAN: dict = {}


def _raise_if_planned(stage: str, *args) -> None:
    planned = PLAN.get(stage)
    if planned is None:
        return
    if callable(planned) and not isinstance(planned, BaseException) and not isinstance(planned, type):
        planned = planned(*args)
        if planned is None:
            return
    raise planned


def _product_slot_dir() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", ".")) / "BAXY" / "renew" / "slots"


class FakeServer:
    made: list = []

    def __init__(self, gguf, server, **options):
        # As the real LlmServer (_slot_dir): BAXY_VISION_SLOT_DIR, or the product's folder.
        held = os.environ.get("BAXY_VISION_SLOT_DIR", "").strip()
        self.slot_dir = Path(held) if held else _product_slot_dir()
        self.running = False
        self._process = types.SimpleNamespace(pid=4242, poll=lambda: None if self.running else 0, returncode=None)
        self.close_calls = 0
        self.effective_closes = 0
        FakeServer.made.append(self)

    @property
    def closed(self) -> bool:
        return self.close_calls > 0 and not self.running

    def start(self):
        self.running = True
        _raise_if_planned("start")

    def wait_ready(self, timeout):
        _raise_if_planned("wait_ready")

    def close(self):
        # Idempotent like the real one: only a running process is terminated.
        self.close_calls += 1
        if self.running:
            self.running = False
            self.effective_closes += 1


class FakeSystemOne:
    made: list = []
    alive = True

    def __init__(self, *args):
        self.ready = FakeSystemOne.alive
        self.case = None
        self.close_calls = 0
        code = None if FakeSystemOne.alive else 3
        self._process = types.SimpleNamespace(pid=4343, poll=lambda: code, returncode=code)
        FakeSystemOne.made.append(self)

    @property
    def closed(self) -> bool:
        return self.close_calls > 0

    def start(self):
        pass

    def close(self):
        self.close_calls += 1


class FakeMind:
    def __init__(self, server, trace, system_one=None):
        pass

    def configure(self, catalog):
        _raise_if_planned("configure")

    def warm(self):
        _raise_if_planned("warm")

    def new_session(self, history):
        pass

    def decide(self, case_id, text, pending=None, unsure=None):
        _raise_if_planned("decide", case_id)
        return {"kind": "conversation", "reply": "hola"}


@pytest.fixture
def decision(tmp_path, monkeypatch):
    FakeServer.made.clear()
    FakeSystemOne.made.clear()
    FakeSystemOne.alive = True
    PLAN.clear()
    package = types.ModuleType("baxy_mind")
    package.__path__ = []
    monkeypatch.setitem(sys.modules, "baxy_mind", package)
    monkeypatch.setitem(sys.modules, "baxy_mind.llm_server", types.SimpleNamespace(LlmServer=FakeServer))
    monkeypatch.setitem(sys.modules, "baxy_mind.mind", types.SimpleNamespace(Mind=FakeMind))
    monkeypatch.setitem(sys.modules, "baxy_mind.system_one", types.SimpleNamespace(SystemOne=FakeSystemOne))
    monkeypatch.setattr(sys, "path", list(sys.path))  # main() puts --src first
    monkeypatch.setattr(bench_decision, "BANKS", tmp_path)
    monkeypatch.setattr(bench_decision, "gpu_used_mib", lambda: None)
    monkeypatch.setattr(bench_decision, "resources", lambda *a: {})
    monkeypatch.setattr(bench_decision, "run_record", lambda *a: {})
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    monkeypatch.setenv("BAXY_RENEW_DECIDE_TEMPERATURE", "0.2")
    monkeypatch.setenv("BAXY_DATA_DIR", str(tmp_path / "datos"))
    # setenv first so that teardown restores these even if main() writes them into os.environ.
    monkeypatch.setenv("BAXY_VISION_SLOT_DIR", "placeholder")
    monkeypatch.delenv("BAXY_VISION_SLOT_DIR")
    monkeypatch.setenv("BAXY_S1_GGUF", "placeholder")
    monkeypatch.delenv("BAXY_S1_GGUF")
    catalog, cases = tmp_path / "catalog.json", tmp_path / "cases.json"
    catalog.write_text(json.dumps({"capabilities": []}), encoding="utf-8")
    cases.write_text(json.dumps([{"id": "P1", "text": "hola", "expect": {"kind": "text"}},
                                 {"id": "P2", "text": "buenas", "expect": {"kind": "text"}}]), encoding="utf-8")

    def run(label, catalog_path=None, slot_dir=None):
        if slot_dir is None:
            os.environ.pop("BAXY_VISION_SLOT_DIR", None)  # each run as a fresh process: nothing left by the one before
        else:
            os.environ["BAXY_VISION_SLOT_DIR"] = str(slot_dir)
        monkeypatch.setattr(sys, "argv", ["bench_decision.py", label, "--cases", str(cases),
                                          "--catalog", str(catalog_path or catalog)])
        bench_decision.main()

    return types.SimpleNamespace(run=run, monkeypatch=monkeypatch, tmp=tmp_path, runs=tmp_path / "runs")


def _with_system_one(decision, alive=True):
    FakeSystemOne.alive = alive
    decision.monkeypatch.setenv("BAXY_S1_GGUF", "laya.gguf")


def _assert_all_closed(with_system_one: bool):
    assert len(FakeServer.made) == 1
    assert FakeServer.made[0].closed, "Qwen's llama-server was left running"
    if with_system_one:
        assert len(FakeSystemOne.made) == 1
        assert FakeSystemOne.made[0].closed, "System One's server was left running"


# ---------------------------------------------------------------- positive: closes whatever happens, and re-raises


def test_server_start_failing_still_closes_the_server_and_reraises(decision):
    PLAN["start"] = RuntimeError("llama-server would not start")
    with pytest.raises(RuntimeError, match="would not start"):
        decision.run("arranque-roto")
    _assert_all_closed(with_system_one=False)


def test_configure_failing_closes_qwen_and_system_one_and_reraises(decision):
    _with_system_one(decision)
    PLAN["configure"] = ValueError("bad catalog for configure")
    with pytest.raises(ValueError, match="bad catalog for configure"):
        decision.run("configure-roto")
    _assert_all_closed(with_system_one=True)


def test_wait_ready_timing_out_closes_the_server_and_reraises(decision):
    PLAN["wait_ready"] = TimeoutError("server not ready after 600 s")
    with pytest.raises(TimeoutError, match="not ready"):
        decision.run("nunca-listo")
    _assert_all_closed(with_system_one=False)


def test_warm_failing_closes_qwen_and_system_one_and_reraises(decision):
    _with_system_one(decision)
    PLAN["warm"] = OSError("warm-up request refused")
    with pytest.raises(OSError, match="warm-up request refused"):
        decision.run("warm-roto")
    _assert_all_closed(with_system_one=True)


def test_missing_catalog_closes_the_server_and_reraises(decision):
    with pytest.raises(FileNotFoundError):
        decision.run("sin-catalogo", catalog_path=decision.tmp / "no-existe.json")
    _assert_all_closed(with_system_one=False)


def test_catalog_that_is_not_json_closes_qwen_and_system_one_and_reraises(decision):
    _with_system_one(decision)
    broken = decision.tmp / "roto.json"
    broken.write_text("{esto no es json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        decision.run("catalogo-roto", catalog_path=broken)
    _assert_all_closed(with_system_one=True)


def test_ctrl_c_while_the_cases_run_closes_both_servers_and_propagates(decision):
    _with_system_one(decision)
    PLAN["decide"] = lambda case_id: KeyboardInterrupt() if case_id == "P2" else None
    with pytest.raises(KeyboardInterrupt):
        decision.run("ctrl-c")
    _assert_all_closed(with_system_one=True)


def test_system_one_dead_stops_the_run_and_closes_both_servers(decision):
    _with_system_one(decision, alive=False)
    with pytest.raises(SystemExit, match="exited"):
        decision.run("s1-muerto")
    _assert_all_closed(with_system_one=True)


# ---------------------------------------------------------------- positive: a slot folder of the run's own


def test_a_run_without_the_env_gets_a_slot_folder_of_its_own_under_runs(decision):
    decision.run("corrida-alfa")
    slot_dir = Path(FakeServer.made[0].slot_dir).resolve()
    runs = decision.runs.resolve()
    assert slot_dir != _product_slot_dir().resolve(), "the run used the product's slot folder"
    assert runs in slot_dir.parents, f"{slot_dir} is not under {runs}"
    assert "corrida-alfa" in str(slot_dir.relative_to(runs)), "the run's slot folder does not say its label"


def test_two_labels_get_two_different_slot_folders_neither_the_products(decision):
    decision.run("tanda-1")
    decision.run("tanda-2")
    first, second = (Path(server.slot_dir).resolve() for server in FakeServer.made)
    product = _product_slot_dir().resolve()
    assert first != second
    assert product not in (first, second)
    assert product not in first.parents and product not in second.parents


# ---------------------------------------------------------------- negative: what must not change


def test_a_given_vision_slot_dir_is_kept_as_it_is(decision):
    given = decision.tmp / "vision" / "slots-de-la-app"
    decision.run("con-vision", slot_dir=given)
    assert Path(FakeServer.made[0].slot_dir) == given


def test_a_normal_run_still_writes_its_jsonl_with_summary_and_rows(decision):
    decision.run("normal")
    lines = (decision.runs / "normal.jsonl").read_text(encoding="utf-8").splitlines()
    summary = json.loads(lines[0])["summary"]
    rows = [json.loads(line) for line in lines[1:]]
    assert summary["label"] == "normal"
    assert summary["n"] == 2
    assert summary["ok"] == sum(row["ok"] for row in rows)
    assert summary["accuracy"] == round(summary["ok"] / summary["n"], 4)
    assert summary["errors"] == 0
    assert [row["id"] for row in rows] == ["P1", "P2"]
    assert all(row["error"] is None for row in rows)


def test_a_normal_run_closes_the_server_once_and_without_error(decision):
    decision.run("normal-cierre")
    server = FakeServer.made[0]
    assert server.closed
    assert server.effective_closes == 1
    assert server.close_calls >= 1


def test_a_case_whose_decide_raises_is_a_failed_case_and_the_run_ends(decision):
    PLAN["decide"] = lambda case_id: ValueError("model returned garbage") if case_id == "P1" else None
    decision.run("caso-roto")  # does not raise
    lines = (decision.runs / "caso-roto.jsonl").read_text(encoding="utf-8").splitlines()
    summary = json.loads(lines[0])["summary"]
    rows = {row["id"]: row for row in map(json.loads, lines[1:])}
    assert summary["errors"] == 1 and summary["error_ids"] == ["P1"]
    assert summary["n"] == 2
    assert rows["P1"]["ok"] is False and "model returned garbage" in rows["P1"]["error"]
    assert rows["P2"]["error"] is None
    assert FakeServer.made[0].effective_closes == 1
