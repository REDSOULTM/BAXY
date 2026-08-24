"""Regression tests for desktop-safe resident inference settings."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from baxy_mind.resource_policy import (  # noqa: E402
    MAX_CPU_INFERENCE_THREADS,
    _lowest_available_affinity_mask,
    bounded_cpu_threads,
    cpu_session_options,
)
from baxy_mind import voice  # noqa: E402
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


def test_process_affinity_selects_only_the_requested_available_cpus() -> None:
    assert _lowest_available_affinity_mask(0b1111_1111, 4) == 0b0000_1111
    assert _lowest_available_affinity_mask(0b1010_1010, 3) == 0b0010_1010


def test_voice_uses_one_sherpa_thread_and_mind_keeps_two_cpu_boundary() -> None:
    root = Path(__file__).resolve().parents[1]
    voice_source = (root / "src" / "baxy_mind" / "voice.py").read_text(
        encoding="utf-8"
    )
    policy_source = (root / "src" / "baxy_mind" / "resource_policy.py").read_text(
        encoding="utf-8"
    )

    configured_stt_defaults = re.findall(
        r'"BAXY_VOICE_STT_THREADS",(?:(?!\)).)*?default=1,',
        voice_source,
        flags=re.DOTALL,
    )
    assert len(configured_stt_defaults) == 2
    assert 'bounded_cpu_threads("BAXY_MIND_PROCESS_CPUS", default=2)' in policy_source


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


def test_silero_vad_uses_numpy_and_a_non_spinning_owned_session(
    tmp_path, monkeypatch
) -> None:
    captured: dict[str, object] = {}

    class _FakeInferenceSession:
        def __init__(self, model, *, sess_options, providers) -> None:
            captured["model"] = model
            captured["options"] = sess_options
            captured["providers"] = providers

        def run(self, output_names, inputs):
            captured["inputs"] = inputs
            return np.asarray([[0.25]], dtype=np.float32), inputs["state"] + 1

    fake_ort = _fake_ort()
    fake_ort.InferenceSession = _FakeInferenceSession
    model = tmp_path / "silero_vad.onnx"
    model.write_bytes(b"not-loaded-by-the-fake")
    monkeypatch.setitem(sys.modules, "onnxruntime", fake_ort)
    monkeypatch.setitem(sys.modules, "torch", None)
    monkeypatch.setattr(
        voice.resources,
        "files",
        lambda package: tmp_path,
    )

    vad = voice.SileroVad()
    probability = vad.process(np.zeros(voice.VAD_WINDOW_SAMPLES, dtype=np.float32))

    assert probability == 0.25
    options = captured["options"]
    assert isinstance(options, _FakeSessionOptions)
    assert options.intra_op_num_threads == 1
    assert options.entries["session.intra_op.allow_spinning"] == "0"
    assert captured["providers"] == ["CPUExecutionProvider"]
    inputs = captured["inputs"]
    assert inputs["input"].shape == (1, 576)
    assert inputs["state"].shape == (2, 1, 128)
