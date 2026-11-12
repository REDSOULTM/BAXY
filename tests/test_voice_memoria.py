"""Uso 95 (uso real 2026-11-04 13:19): three tries at start found 556, 360 and 671 MB left to commit for the 1200 MB the
recognizer needs, and the ear was never tried again once memory was freed; the interface said «No hay micrófono». While
the mind runs the ear keeps trying on its own with a growing wait, says how much memory it needs and has, and tells the
App when it loaded."""
import time

import numpy as np
import pytest

from baxy_mind import voice, voice_output
from baxy_mind.voice import Voice


class _Speech:
    ready = False
    deferred = ""

    def __init__(self, *_args) -> None:
        pass


class _Recognizer:
    pass


class _Vad:
    def reset(self) -> None:
        pass

    def marks(self, block, settle: bool = False) -> np.ndarray:
        return np.ones(len(block), bool)


def test_not_enough_memory_says_its_figures_as_before() -> None:
    error = voice_output.NotEnoughMemory("recognizer", 556, 1200)
    assert isinstance(error, MemoryError)
    assert str(error) == "recognizer not loaded: 556 MB of memory left to commit, 1200 MB needed"
    assert (error.left_mb, error.need_mb) == (556, 1200)


def test_a_low_memory_recognizer_keeps_trying_on_its_own_and_says_the_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    built: list[int] = []
    sent: list[dict] = []

    def recognize(self: Voice, *_args) -> None:
        built.append(1)
        if len(built) <= voice_output.NATIVE_LOAD_RETRIES + 1:
            raise voice_output.NotEnoughMemory("recognizer", 556, 1200)
        self._recognizer = _Recognizer()

    def load(self: Voice) -> None:
        self._input, self._vad = True, _Vad()
        self._load_recognizer(None, None)
        self._loaded.set()

    monkeypatch.setattr(voice, "Speech", _Speech)
    monkeypatch.setattr(voice, "STT_RETRY_WAITS_S", (0.05, 0.05))
    monkeypatch.setattr(Voice, "_recognize", recognize)
    monkeypatch.setattr(Voice, "_load", load)
    monkeypatch.setattr(Voice, "_open", lambda self: None)
    listening = Voice(sent.append)

    assert listening._loaded.wait(5)
    status = listening.status()
    assert status["deferred"] is True and not listening.failure
    assert status["memory"] == {"needMb": 1200, "leftMb": 556}

    deadline = time.monotonic() + 5
    while not any(m.get("event") == "voice_ready" for m in sent) and time.monotonic() < deadline:
        time.sleep(0.01)
    assert listening._recognizer is not None, "past the old cap of tries, the ear still loads once memory is free"
    assert not listening.failure and not listening.deferred
    assert listening.status()["memory"] is None
    assert any(m.get("event") == "voice_ready" for m in sent), "the App is told the ear came"
