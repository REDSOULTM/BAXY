"""The voice's part of palancas 2 y 5 (src/baxy_mind/voice.py, early.py): EARLY s into the silence that may end a
request, what was said is decoded and told to the mind; if the person goes on it is taken back; the request still ends
after END_SILENCE_S with its own transcript, decoded again from all of its audio. With the switch off nothing of it
runs. «Baxy» heard is told once."""
import time
from types import SimpleNamespace

import numpy as np
import pytest

from baxy_mind import voice
from baxy_mind.voice import BLOCK, RATE, Voice


class _Speech:
    speaking = False
    ready = False

    def __init__(self, *_args) -> None:
        pass


class _Stream:
    result = None

    def __init__(self, decoded: list[float]) -> None:
        self.decoded = decoded

    def accept_waveform(self, _rate, audio) -> None:
        self.decoded.append(round(len(audio) / RATE, 2))


class _Recognizer:
    """Every decoding gives «abre Steam» and keeps how long the audio was."""

    def __init__(self) -> None:
        self.decoded: list[float] = []

    def create_stream(self) -> _Stream:
        return _Stream(self.decoded)

    def decode_stream(self, stream: _Stream) -> None:
        stream.result = SimpleNamespace(text=" abre Steam", tokens=[], timestamps=[])


class _Vad:
    """Silero hears speech in every sample: here the levels decide (voice.Vad itself: test_voice_vad.py)."""

    def reset(self) -> None:
        pass

    def marks(self, block) -> np.ndarray:
        return np.ones(len(block), bool)


class _Wake:
    """Fires «Baxy» at the first block it hears."""

    def __init__(self) -> None:
        self.fired = False

    def reset(self) -> None:
        pass

    def accept(self, _block) -> list:
        if self.fired:
            return []
        self.fired = True
        return [SimpleNamespace(time_s=0.0)]


def _voice(monkeypatch: pytest.MonkeyPatch, early_s: float, mode: str = "direct"):
    recognizer = _Recognizer()
    written: list[dict] = []
    told: list = []
    woke: list = []

    def load(self: Voice) -> None:
        self._recognizer, self._input, self._vad = recognizer, True, _Vad()
        self._detector = _Wake()
        self._loaded.set()

    monkeypatch.setattr(voice, "Speech", _Speech)
    monkeypatch.setattr(Voice, "_load", load)
    monkeypatch.setattr(Voice, "_open", lambda self: None)
    listening = Voice(written.append, on_early=lambda seq, text: told.append((seq, text)), early_s=early_s,
                      on_wake=lambda: woke.append(True))
    assert listening.start(mode)
    return listening, recognizer, written, told, woke


def _feed(listening: Voice, pattern: str) -> None:
    """«v» a block of voice, «.» a block of silence."""
    for mark in pattern:
        listening._blocks.put(np.full(BLOCK, 0.1 if mark == "v" else 0.0, np.float32))


def _until(condition, seconds: float = 5.0) -> None:
    deadline = time.monotonic() + seconds
    while not condition() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert condition()


def _transcripts(written: list[dict]) -> list[str]:
    return [m["text"] for m in written if m.get("type") == "voice.transcript"]


def test_the_words_are_told_early_and_the_request_still_ends_with_its_own_transcript(
        monkeypatch: pytest.MonkeyPatch) -> None:
    listening, recognizer, written, told, _ = _voice(monkeypatch, early_s=0.2)
    # (END_SILENCE_S is reached at the 10th block: 1.9 - 1.0 < 0.9 in floating point)
    _feed(listening, "v" * 10 + "." * 10)
    _until(lambda: _transcripts(written) == ["abre Steam"])
    assert told == [(1, "abre Steam")]
    # The early decoding heard the voice and 0.2 s of silence; the request's own, the whole 0.9 s, as before.
    # The early decoding took the place of the live caption due a block later (see the switch off): as many decodings.
    assert recognizer.decoded == [1.2, 1.9]
    assert [m["text"] for m in written if m.get("event") == "partial"] == ["abre Steam"]  # the early one, as caption


def test_going_on_after_it_takes_it_back_and_a_new_one_is_told(monkeypatch: pytest.MonkeyPatch) -> None:
    listening, recognizer, written, told, _ = _voice(monkeypatch, early_s=0.2)
    _feed(listening, "v" * 5 + "..." + "v" * 3 + "." * 10)
    _until(lambda: len(_transcripts(written)) == 1)
    assert told == [(1, "abre Steam"), (1, None), (2, "abre Steam")]
    assert recognizer.decoded == [0.7, 1.3, 2.0]


def test_a_stop_takes_it_back(monkeypatch: pytest.MonkeyPatch) -> None:
    listening, _, written, told, _ = _voice(monkeypatch, early_s=0.2)
    _feed(listening, "v" * 5 + "...")
    _until(lambda: told == [(1, "abre Steam")])
    listening.stop()
    assert told == [(1, "abre Steam"), (1, None)] and _transcripts(written) == []


def test_with_the_switch_off_the_voice_hears_and_decodes_as_before(monkeypatch: pytest.MonkeyPatch) -> None:
    listening, recognizer, written, told, _ = _voice(monkeypatch, early_s=0.0)
    _feed(listening, "v" * 10 + "." * 10)
    _until(lambda: _transcripts(written) == ["abre Steam"])
    assert told == [] and recognizer.decoded == [1.3, 1.9]  # its live caption at 1.3 s, then the request


def test_the_wake_word_is_told_once(monkeypatch: pytest.MonkeyPatch) -> None:
    listening, _, written, _, woke = _voice(monkeypatch, early_s=0.2, mode="wake")
    _feed(listening, "." * 3)
    _until(lambda: any(m.get("event") == "wake_detected" for m in written))
    assert woke == [True]
