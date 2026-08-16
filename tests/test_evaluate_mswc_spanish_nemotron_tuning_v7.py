from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "evaluate_mswc_spanish_nemotron_tuning_v7.py"
)
SPEC = importlib.util.spec_from_file_location(
    "evaluate_mswc_spanish_nemotron_tuning_v7", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class _Result:
    text = "hola"


class _Stream:
    def __init__(self) -> None:
        self.language = None
        self.finished = False
        self.result = _Result()

    def set_option(self, name: str, value: str) -> None:
        assert name == "language"
        self.language = value

    def accept_waveform(self, sample_rate: int, audio: np.ndarray) -> None:
        assert sample_rate == 16000
        assert len(audio) > 0

    def input_finished(self) -> None:
        self.finished = True


class _Recognizer:
    def __init__(self) -> None:
        self.decoded: set[int] = set()

    def create_stream(self) -> _Stream:
        return _Stream()

    def is_ready(self, stream: _Stream) -> bool:
        return stream.finished and id(stream) not in self.decoded

    def decode_streams(self, streams: list[_Stream]) -> None:
        self.decoded.update(id(stream) for stream in streams)

    def get_result_all(self, stream: _Stream) -> _Result:
        assert id(stream) in self.decoded
        return stream.result


def test_decode_stream_batch_sets_language_finishes_and_drains() -> None:
    recognizer = _Recognizer()
    transcripts = MODULE.decode_stream_batch(
        recognizer=recognizer,
        audio_batch=[np.ones(80, dtype=np.float32), np.ones(40, dtype=np.float32)],
        sample_rate=16000,
        language="es",
        tail_padding_samples=160,
    )
    assert transcripts == ["hola", "hola"]
    assert len(recognizer.decoded) == 2
