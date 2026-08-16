from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "experiments"
    / "voice_latency"
    / "evaluate_nemotron_mswc_spanish_word_gate_v2.py"
)
SPEC = importlib.util.spec_from_file_location("nemotron_mswc_v2", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class _Result:
    def __init__(self, text: str) -> None:
        self.text = text


class _Stream:
    def __init__(self, text: str) -> None:
        self.text = text
        self.language = ""
        self.audio = np.empty(0, dtype=np.float32)
        self.finished = False
        self.ready = True

    def set_option(self, key: str, value: str) -> None:
        assert key == "language"
        self.language = value

    def accept_waveform(self, sample_rate: int, audio: np.ndarray) -> None:
        assert sample_rate == 16_000
        self.audio = audio

    def input_finished(self) -> None:
        self.finished = True


class _Recognizer:
    def __init__(self) -> None:
        self.streams: list[_Stream] = []

    def create_stream(self) -> _Stream:
        stream = _Stream(f"texto-{len(self.streams)}")
        self.streams.append(stream)
        return stream

    @staticmethod
    def is_ready(stream: _Stream) -> bool:
        return stream.ready

    @staticmethod
    def decode_streams(streams: list[_Stream]) -> None:
        for stream in streams:
            stream.ready = False

    @staticmethod
    def get_result_all(stream: _Stream) -> _Result:
        return _Result(stream.text)


def test_decode_stream_batch_sets_language_padding_and_finalizes() -> None:
    recognizer = _Recognizer()
    texts = MODULE.decode_stream_batch(
        recognizer=recognizer,
        audio_batch=[np.ones(4, dtype=np.float32), np.ones(7, dtype=np.float32)],
        sample_rate=16_000,
        language="es",
        tail_padding_samples=3,
    )
    assert texts == ["texto-0", "texto-1"]
    assert [len(stream.audio) for stream in recognizer.streams] == [7, 10]
    assert all(stream.language == "es" for stream in recognizer.streams)
    assert all(stream.finished for stream in recognizer.streams)


def test_fixed_comparison_contract_is_not_result_tuned() -> None:
    assert MODULE.LANGUAGE == "es"
    assert MODULE.TAIL_PADDING_SECONDS == 1.0
    assert MODULE.TARGET_ACCURACY == 0.99


def test_reuses_identical_normalization_and_aggregate_summary() -> None:
    assert MODULE._PARAKEET.normalized_words("¡MÚSICA!") == ("musica",)
    checkpoint = MODULE._PARAKEET.empty_checkpoint({"manifest": "x"}, 2)
    assert "transcript" not in checkpoint
    assert "className" not in checkpoint
