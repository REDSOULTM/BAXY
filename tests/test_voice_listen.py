"""Listening transcribes outside the voice's lock (src/baxy_mind/voice.py): while Ultra decodes what was heard, a
push-to-talk let go, a stop or BAXY starting to speak do not wait for it, and what was heard before a stop is not told."""
import threading
import time
from types import SimpleNamespace

import numpy as np
import pytest

from baxy_mind import voice
from baxy_mind.voice import BLOCK, Voice


class _Speech:
    speaking = False
    ready = False

    def __init__(self, *_args) -> None:
        pass


class _Stream:
    result = None

    def accept_waveform(self, _rate, _audio) -> None:
        pass


class _Recognizer:
    """Decodes «abre Steam» in one second."""

    def __init__(self) -> None:
        self.decoding = threading.Event()
        self.decoded = threading.Event()

    def create_stream(self) -> _Stream:
        return _Stream()

    def decode_stream(self, stream: _Stream) -> None:
        self.decoding.set()
        time.sleep(1.0)
        stream.result = SimpleNamespace(text=" abre Steam", tokens=[], timestamps=[])
        self.decoded.set()


def _hearing(monkeypatch: pytest.MonkeyPatch, written: list[dict]) -> tuple[Voice, _Recognizer]:
    """A direct request whose live caption is being decoded."""
    recognizer = _Recognizer()

    def load(self: Voice) -> None:
        self._recognizer, self._input = recognizer, True
        self._loaded.set()

    monkeypatch.setattr(voice, "Speech", _Speech)
    monkeypatch.setattr(Voice, "_load", load)
    monkeypatch.setattr(Voice, "_open", lambda self: None)
    listening = Voice(written.append)
    assert listening.start("direct")
    for _ in range(13):  # 1.3 s of voice: the first live caption is decoded
        listening._blocks.put(np.full(BLOCK, 0.1, np.float32))
    assert recognizer.decoding.wait(5)
    return listening, recognizer


def _partials(written: list[dict]) -> list[str]:
    return [message["text"] for message in written if message.get("event") == "partial"]


def test_letting_go_does_not_wait_for_a_transcription(monkeypatch: pytest.MonkeyPatch) -> None:
    written: list[dict] = []
    listening, recognizer = _hearing(monkeypatch, written)
    began = time.monotonic()
    listening.release()
    assert time.monotonic() - began < 0.2
    assert recognizer.decoded.wait(5)
    deadline = time.monotonic() + 5
    while not _partials(written) and time.monotonic() < deadline:
        time.sleep(0.02)
    assert _partials(written) == ["abre Steam"]


def test_what_was_heard_before_a_stop_is_not_told(monkeypatch: pytest.MonkeyPatch) -> None:
    written: list[dict] = []
    listening, recognizer = _hearing(monkeypatch, written)
    began = time.monotonic()
    listening.stop()
    assert time.monotonic() - began < 0.2
    assert recognizer.decoded.wait(5)
    time.sleep(0.2)
    assert _partials(written) == []
