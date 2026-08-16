from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np


def _module():
    script = (
        Path(__file__).resolve().parents[1]
        / "experiments"
        / "voice_latency"
        / "run_nemotron_lexical_wake_physical_room_gate_v1.py"
    )
    spec = importlib.util.spec_from_file_location("baxy_nemotron_wake_gate", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_strict_policy_only_accepts_closed_prefix() -> None:
    gate = _module()

    assert gate.lexical_policies(("Basi abre Spotify",))["strictClosedPrefix"]
    assert gate.lexical_policies(("Боксе, открой",))["strictClosedPrefix"]
    assert not gate.lexical_policies(("abre Baxy en Spotify",))[
        "strictClosedPrefix"
    ]
    assert not gate.lexical_policies(("Basic security matters",))[
        "strictClosedPrefix"
    ]


def test_opened_diagnostic_policy_is_separate_from_authority() -> None:
    gate = _module()

    assert gate.lexical_policies(("Nuestra caldera Basic Roca",)) == {
        "strictClosedPrefix": False,
        "openedDiagnosticAnywhere": True,
    }
    assert gate.lexical_policies(("con una pieza del Baximan",)) == {
        "strictClosedPrefix": False,
        "openedDiagnosticAnywhere": True,
    }
    assert gate.lexical_policies(("seguimos adelante",)) == {
        "strictClosedPrefix": False,
        "openedDiagnosticAnywhere": False,
    }


def test_decode_finishes_stream_and_returns_text() -> None:
    gate = _module()

    class Result:
        text = " Baxy "

    class Stream:
        def __init__(self) -> None:
            self.options: list[tuple[str, str]] = []
            self.finished = False

        def set_option(self, key: str, value: str) -> None:
            self.options.append((key, value))

        def accept_waveform(self, sample_rate: int, audio: np.ndarray) -> None:
            assert sample_rate == 16_000
            assert audio.dtype == np.float32

        def input_finished(self) -> None:
            self.finished = True

    class Recognizer:
        def __init__(self) -> None:
            self.stream = Stream()
            self.ready = True

        def create_stream(self) -> Stream:
            return self.stream

        def is_ready(self, stream: Stream) -> bool:
            value, self.ready = self.ready, False
            return value

        def decode_stream(self, stream: Stream) -> None:
            assert stream.finished

        def get_result_all(self, stream: Stream) -> Result:
            assert stream.finished
            return Result()

    recognizer = Recognizer()
    text, latency = gate._decode(
        recognizer, np.zeros(800, dtype=np.float32), "auto"
    )

    assert text == "Baxy"
    assert latency >= 0.0
    assert recognizer.stream.options == [("language", "auto")]


def test_conditioner_removes_gate_padding_and_normalizes_level() -> None:
    gate = _module()
    audio = np.zeros(32_000, dtype=np.float32)
    audio[12_000:20_000] = 0.01

    conditioned, evidence = gate.condition_vad_bounded_audio(
        audio,
        noise_samples=8_000,
        padding_samples=1_600,
    )

    assert conditioned.size < audio.size
    assert np.isclose(float(np.max(np.abs(conditioned))), 0.2)
    assert evidence["conditioningGain"] == 20.0
    assert 0.3 < evidence["retainedFraction"] < 0.4


def test_conditioner_rejects_silence() -> None:
    gate = _module()

    try:
        gate.condition_vad_bounded_audio(
            np.zeros(16_000, dtype=np.float32), noise_samples=8_000
        )
    except ValueError as error:
        assert str(error) == "nemotron_physical_audio_silent"
    else:
        raise AssertionError("silence should not become lexical evidence")
