from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from baxy_mind.onnx_runtime import create_with_power_efficient_onnx


class _FakeOptions:
    def __init__(self) -> None:
        self.intra_op_num_threads = 0
        self.inter_op_num_threads = 0
        self.execution_mode = None
        self.entries: dict[str, str] = {}

    def add_session_config_entry(self, key: str, value: str) -> None:
        self.entries[key] = value


def test_third_party_sessions_block_instead_of_spinning(monkeypatch) -> None:
    captured: list[_FakeOptions] = []

    def original_session(_path, sess_options=None, **_kwargs):
        captured.append(sess_options)
        return object()

    runtime = SimpleNamespace(
        InferenceSession=original_session,
        SessionOptions=_FakeOptions,
        ExecutionMode=SimpleNamespace(ORT_SEQUENTIAL="sequential"),
    )
    monkeypatch.setitem(sys.modules, "onnxruntime", runtime)

    result = create_with_power_efficient_onnx(
        lambda: runtime.InferenceSession("model.onnx", providers=["CPUExecutionProvider"])
    )

    assert result is not None
    assert runtime.InferenceSession is original_session
    assert len(captured) == 1
    options = captured[0]
    assert options.intra_op_num_threads == 1
    assert options.inter_op_num_threads == 1
    assert options.execution_mode == "sequential"
    assert options.entries == {
        "session.intra_op.allow_spinning": "0",
        "session.inter_op.allow_spinning": "0",
    }


def test_session_constructor_is_restored_when_factory_fails(monkeypatch) -> None:
    def original_session(*_args, **_kwargs):
        return object()

    runtime = SimpleNamespace(
        InferenceSession=original_session,
        SessionOptions=_FakeOptions,
        ExecutionMode=SimpleNamespace(ORT_SEQUENTIAL="sequential"),
    )
    monkeypatch.setitem(sys.modules, "onnxruntime", runtime)

    with pytest.raises(RuntimeError, match="load failed"):
        create_with_power_efficient_onnx(
            lambda: (_ for _ in ()).throw(RuntimeError("load failed"))
        )

    assert runtime.InferenceSession is original_session


def test_third_party_thread_defaults_are_overridden(monkeypatch) -> None:
    options = _FakeOptions()
    options.intra_op_num_threads = 8
    options.inter_op_num_threads = 4

    def original_session(_path, sess_options=None):
        return sess_options

    runtime = SimpleNamespace(
        InferenceSession=original_session,
        SessionOptions=_FakeOptions,
        ExecutionMode=SimpleNamespace(ORT_SEQUENTIAL="sequential"),
    )
    monkeypatch.setitem(sys.modules, "onnxruntime", runtime)

    configured = create_with_power_efficient_onnx(
        lambda: runtime.InferenceSession("model.onnx", options)
    )

    assert configured.intra_op_num_threads == 1
    assert configured.inter_op_num_threads == 1
