"""bench_escenas cleans up after itself (PC-Q, 2026-10-25), with doubles of the mind and its llama-server."""
import json
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "renew"))

import bench_escenas  # noqa: E402


class FakeServer:
    made: list = []

    def __init__(self, gguf, server, **options):
        self._process = object()
        self.closed = False
        FakeServer.made.append(self)

    def start(self):
        pass

    def wait_ready(self, timeout):
        pass

    def close(self):
        self.closed = True


class FakeMind:
    beat_raises = False

    def __init__(self, server, trace):
        self.trace = trace

    def configure(self, catalog):
        pass

    def warm(self):
        pass

    def new_session(self):
        pass

    def beat(self, scene_id, context):
        if FakeMind.beat_raises:
            raise TimeoutError("llama-server did not answer")
        with self.trace.open("a", encoding="utf-8") as out:  # the mind appends to its trace, as Mind does
            out.write(json.dumps({"beat": scene_id}) + "\n")
        return {"kind": "silence"}

    def end_beat(self):
        pass


@pytest.fixture
def escenas(tmp_path, monkeypatch):
    FakeServer.made.clear()
    FakeMind.beat_raises = False
    package = types.ModuleType("baxy_mind")
    package.__path__ = []
    monkeypatch.setitem(sys.modules, "baxy_mind", package)
    monkeypatch.setitem(sys.modules, "baxy_mind.llm_server", types.SimpleNamespace(LlmServer=FakeServer))
    monkeypatch.setitem(sys.modules, "baxy_mind.mind", types.SimpleNamespace(Mind=FakeMind))
    monkeypatch.setattr(bench_escenas, "BANKS", tmp_path)
    held = []
    monkeypatch.setattr(bench_escenas, "limpieza", types.SimpleNamespace(die_with_this_process=held.append), raising=False)
    catalog, scenes = tmp_path / "catalog.json", tmp_path / "scenes.json"
    catalog.write_text(json.dumps({"capabilities": []}), encoding="utf-8")
    scenes.write_text(json.dumps([{"id": "S001", "context": {}, "expect": {"kind": "silence"}}]), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["bench_escenas.py", "lbl", "--scenes", str(scenes), "--catalog", str(catalog)])
    return tmp_path, held


def test_a_scene_that_breaks_the_run_still_closes_its_server(escenas):
    FakeMind.beat_raises = True
    with pytest.raises(TimeoutError):
        bench_escenas.main()
    assert FakeServer.made[0].closed


def test_a_label_run_again_keeps_no_trace_of_the_run_before(escenas):
    folder, _ = escenas
    bench_escenas.main()
    bench_escenas.main()
    trace = (folder / "runs" / "lbl-escenas.trace.jsonl").read_text(encoding="utf-8").splitlines()
    assert trace == ['{"beat": "S001"}']
