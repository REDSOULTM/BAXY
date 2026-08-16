from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT / "experiments" / "voice_latency" / "evaluate_sherpa_open_vocab_kws_raw_v1.py"
)
SPEC = importlib.util.spec_from_file_location("evaluate_sherpa_kws", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class _Stream:
    def __init__(self) -> None:
        self.finished = False
        self.samples = 0

    def accept_waveform(self, rate: int, audio: np.ndarray) -> None:
        assert rate == MODULE.SAMPLE_RATE
        self.samples += len(audio)

    def input_finished(self) -> None:
        self.finished = True


class _Kws:
    def __init__(self, result: str) -> None:
        self.result = result
        self.decode_calls = 0
        self.stream: _Stream | None = None

    def create_stream(self) -> _Stream:
        self.stream = _Stream()
        return self.stream

    def is_ready(self, stream: _Stream) -> bool:
        return stream.finished and self.decode_calls < 2

    def decode_stream(self, stream: _Stream) -> None:
        self.decode_calls += 1

    def get_result(self, stream: _Stream) -> str:
        return self.result if self.decode_calls >= 2 else ""

    def timestamps(self, stream: _Stream) -> list[float]:
        return [0.18, 0.42]


def test_decode_keyword_feeds_tail_and_returns_endpoint() -> None:
    kws = _Kws("BAXY")

    hit, endpoint = MODULE.decode_keyword(kws, np.zeros(8_000, np.float32))

    assert hit
    assert endpoint == 0.42
    assert kws.stream is not None
    assert kws.stream.samples == 8_000 + round(
        MODULE.TAIL_PADDING_SECONDS * MODULE.SAMPLE_RATE
    )


def test_decode_keyword_returns_closed_when_no_keyword() -> None:
    kws = _Kws("")

    assert MODULE.decode_keyword(kws, np.zeros(1_000, np.float32)) == (False, None)
