from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import baxy_mind.wakeword as wakeword_module
from baxy_mind.wakeword import AcousticWakeDetector, WakeWordModelConfig


class _FakeSessionOptions:
    def __init__(self) -> None:
        self.graph_optimization_level: object | None = None
        self.execution_mode: object | None = None
        self.intra_op_num_threads = 0
        self.inter_op_num_threads = 0
        self.entries: dict[str, str] = {}

    def add_session_config_entry(self, name: str, value: str) -> None:
        self.entries[name] = value


def _config() -> WakeWordModelConfig:
    return WakeWordModelConfig(
        manifest_path=Path("wake.json"),
        model_path=Path("baxy.onnx"),
        model_name="baxy",
        phrase="Baxy",
        threshold=0.5,
        hop_samples=4_000,
        debounce_seconds=2.0,
        model_sha256="1" * 64,
        calibration={"approved": False},
    )


def _install_fake_runtime(
    monkeypatch: pytest.MonkeyPatch,
    *,
    fail_during_load: bool = False,
) -> tuple[ModuleType, list[_FakeSessionOptions]]:
    options_seen: list[_FakeSessionOptions] = []
    onnxruntime = ModuleType("onnxruntime")

    def original_factory(*_args: Any, **kwargs: Any) -> object:
        options_seen.append(kwargs["sess_options"])
        return object()

    onnxruntime.InferenceSession = original_factory  # type: ignore[attr-defined]
    onnxruntime.SessionOptions = _FakeSessionOptions  # type: ignore[attr-defined]
    onnxruntime.GraphOptimizationLevel = SimpleNamespace(  # type: ignore[attr-defined]
        ORT_ENABLE_ALL="all"
    )
    onnxruntime.ExecutionMode = SimpleNamespace(  # type: ignore[attr-defined]
        ORT_SEQUENTIAL="sequential"
    )

    wakeword = ModuleType("livekit.wakeword")

    class FakeWakeWordModel:
        def __init__(self) -> None:
            onnxruntime.InferenceSession("mel.onnx")  # type: ignore[attr-defined]
            onnxruntime.InferenceSession("embedding.onnx")  # type: ignore[attr-defined]

        def load_model(self, _path: Path, _name: str) -> None:
            if fail_during_load:
                raise RuntimeError("load failed")
            onnxruntime.InferenceSession("wake.onnx")  # type: ignore[attr-defined]

    wakeword.WakeWordModel = FakeWakeWordModel  # type: ignore[attr-defined]
    livekit = ModuleType("livekit")
    livekit.__path__ = []  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "onnxruntime", onnxruntime)
    monkeypatch.setitem(sys.modules, "livekit", livekit)
    monkeypatch.setitem(sys.modules, "livekit.wakeword", wakeword)
    return onnxruntime, options_seen


def test_livekit_sessions_are_single_threaded_and_do_not_spin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    onnxruntime, options_seen = _install_fake_runtime(monkeypatch)
    original_factory = onnxruntime.InferenceSession  # type: ignore[attr-defined]

    AcousticWakeDetector(_config())

    assert len(options_seen) == 3
    for options in options_seen:
        assert options.intra_op_num_threads == 1
        assert options.inter_op_num_threads == 1
        assert options.execution_mode == "sequential"
        assert options.entries == {
            "session.intra_op.allow_spinning": "0",
            "session.inter_op.allow_spinning": "0",
        }
    assert onnxruntime.InferenceSession is original_factory  # type: ignore[attr-defined]


def test_livekit_session_factory_is_restored_when_model_load_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    onnxruntime, _ = _install_fake_runtime(monkeypatch, fail_during_load=True)
    original_factory = onnxruntime.InferenceSession  # type: ignore[attr-defined]

    with pytest.raises(wakeword_module.WakeWordRuntimeError) as raised:
        AcousticWakeDetector(_config())

    assert str(raised.value) == "wake_word_runtime_load_failed:RuntimeError"
    assert onnxruntime.InferenceSession is original_factory  # type: ignore[attr-defined]
