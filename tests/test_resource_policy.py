"""Regression tests for desktop-safe resident inference settings."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from baxy_mind.resource_policy import (  # noqa: E402
    MAX_CPU_INFERENCE_THREADS,
    bounded_cpu_threads,
    cpu_session_options,
)
from baxy_mind import voice_output  # noqa: E402


class _FakeSessionOptions:
    def __init__(self) -> None:
        self.graph_optimization_level = None
        self.intra_op_num_threads = None
        self.inter_op_num_threads = None
        self.execution_mode = None
        self.entries: dict[str, str] = {}

    def add_session_config_entry(self, name: str, value: str) -> None:
        self.entries[name] = value


def _fake_ort() -> SimpleNamespace:
    return SimpleNamespace(
        SessionOptions=_FakeSessionOptions,
        GraphOptimizationLevel=SimpleNamespace(ORT_ENABLE_ALL="all"),
        ExecutionMode=SimpleNamespace(ORT_SEQUENTIAL="sequential"),
    )


def test_cpu_session_options_bound_workers_and_disable_spinning(monkeypatch) -> None:
    monkeypatch.setenv("BAXY_TEST_ONNX_THREADS", "999")

    options = cpu_session_options(
        _fake_ort(),
        environment_name="BAXY_TEST_ONNX_THREADS",
    )

    assert options.intra_op_num_threads == MAX_CPU_INFERENCE_THREADS
    assert options.inter_op_num_threads == 1
    assert options.execution_mode == "sequential"
    assert options.entries == {
        "session.intra_op.allow_spinning": "0",
        "session.inter_op.allow_spinning": "0",
    }


def test_invalid_thread_override_returns_small_default(monkeypatch) -> None:
    monkeypatch.setenv("BAXY_TEST_ONNX_THREADS", "not-a-number")
    assert bounded_cpu_threads("BAXY_TEST_ONNX_THREADS") == 2


def test_piper_owns_a_non_spinning_bounded_session(tmp_path, monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _FakeInferenceSession:
        def __init__(self, model, *, sess_options, providers) -> None:
            captured["model"] = model
            captured["options"] = sess_options
            captured["providers"] = providers

    fake_ort = _fake_ort()
    fake_ort.InferenceSession = _FakeInferenceSession
    monkeypatch.setitem(sys.modules, "onnxruntime", fake_ort)
    monkeypatch.setattr(voice_output, "_espeak_exe", lambda: tmp_path / "espeak.exe")

    model = tmp_path / "voice.onnx"
    model.write_bytes(b"not-loaded-by-the-fake")
    model.with_suffix(".onnx.json").write_text(
        json.dumps(
            {
                "phoneme_id_map": {"^": [1], "$": [2]},
                "audio": {"sample_rate": 22050},
            }
        ),
        encoding="utf-8",
    )

    voice_output._PiperOnnxEngine(model)  # noqa: SLF001

    options = captured["options"]
    assert isinstance(options, _FakeSessionOptions)
    assert options.intra_op_num_threads == 2
    assert options.inter_op_num_threads == 1
    assert options.entries["session.intra_op.allow_spinning"] == "0"
    assert captured["providers"] == ["CPUExecutionProvider"]
