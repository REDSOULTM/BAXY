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


class _Vad:
    """Silero hears speech in every sample: here the levels decide (voice.Vad itself: test_voice_vad.py)."""

    def reset(self) -> None:
        pass

    def marks(self, block) -> np.ndarray:
        return np.ones(len(block), bool)


def _hearing(monkeypatch: pytest.MonkeyPatch, written: list[dict]) -> tuple[Voice, _Recognizer]:
    """A direct request whose live caption is being decoded."""
    recognizer = _Recognizer()

    def load(self: Voice) -> None:
        self._recognizer, self._input, self._vad = recognizer, True, _Vad()
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


class _InstantRecognizer:
    """Hears «abre Steam» at once, its words well after the call."""

    def create_stream(self) -> _Stream:
        return _Stream()

    def decode_stream(self, stream: _Stream) -> None:
        stream.result = SimpleNamespace(text=" abre Steam", tokens=[" abre", " Steam"], timestamps=[9.0, 9.3])


class _Wake:
    """Fires «Baxy» when the audio it was fed reaches each of `at` (seconds)."""

    def __init__(self, at: list[float]) -> None:
        self.at, self.samples = list(at), 0

    def reset(self) -> None:
        pass

    def accept(self, block: np.ndarray) -> list[SimpleNamespace]:
        self.samples += len(block)
        if self.at and self.samples / voice.RATE >= self.at[0]:
            return [SimpleNamespace(time_s=self.at.pop(0))]
        return []


def _blocks(listening: Voice, level: float, count: int) -> None:
    for _ in range(count):
        listening._blocks.put(np.full(BLOCK, level, np.float32))


def _wait_for(condition, seconds: float = 5.0) -> None:
    deadline = time.monotonic() + seconds
    while not condition() and time.monotonic() < deadline:
        time.sleep(0.02)


def test_a_repeated_wake_request_gets_its_live_caption_again(monkeypatch: pytest.MonkeyPatch) -> None:
    written: list[dict] = []

    def load(self: Voice) -> None:
        self._recognizer, self._input, self._detector = _InstantRecognizer(), True, _Wake([0.1, 4.0])
        self._vad = _Vad()
        self._loaded.set()

    monkeypatch.setattr(voice, "Speech", _Speech)
    monkeypatch.setattr(Voice, "_load", load)
    monkeypatch.setattr(Voice, "_open", lambda self: None)
    listening = Voice(written.append)
    assert listening.start("wake")
    _blocks(listening, 0.1, 15)   # «Baxy» at 0.1 s and the request: its caption
    _blocks(listening, 0.0, 15)   # 0.9 s of silence ends it
    _blocks(listening, 0.1, 25)   # «Baxy» at 4.0 s, the same request again
    _wait_for(lambda: len(_partials(written)) >= 2)
    assert _partials(written) == ["abre Steam", "abre Steam"]


class _Microphone:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_a_microphone_that_sends_nothing_is_opened_again(monkeypatch: pytest.MonkeyPatch) -> None:
    opened: list[_Microphone] = []

    def load(self: Voice) -> None:
        self._recognizer, self._input, self._vad = _InstantRecognizer(), True, _Vad()
        self._loaded.set()

    def open_(self: Voice) -> None:
        if self._stream is None:
            self._stream = _Microphone()
            opened.append(self._stream)

    monkeypatch.setattr(voice, "STALL_S", 0.2)
    monkeypatch.setattr(voice, "Speech", _Speech)
    monkeypatch.setattr(Voice, "_load", load)
    monkeypatch.setattr(Voice, "_open", open_)
    listening = Voice(lambda message: None)
    assert listening.start("direct")
    _wait_for(lambda: len(opened) >= 2)
    assert len(opened) >= 2 and opened[0].closed
    listening.stop()


def test_a_microphone_that_cannot_be_opened_again_turns_the_ear_off_and_says_so(
        monkeypatch: pytest.MonkeyPatch) -> None:
    written: list[dict] = []
    opened: list[_Microphone] = []

    def load(self: Voice) -> None:
        self._recognizer, self._input, self._vad = _InstantRecognizer(), True, _Vad()
        self._loaded.set()

    def open_(self: Voice) -> None:
        if opened:
            raise OSError("no input device")
        self._stream = _Microphone()
        opened.append(self._stream)

    monkeypatch.setattr(voice, "STALL_S", 0.2)
    monkeypatch.setattr(voice, "Speech", _Speech)
    monkeypatch.setattr(Voice, "_load", load)
    monkeypatch.setattr(Voice, "_open", open_)
    listening = Voice(written.append)
    assert listening.start("direct")
    _wait_for(lambda: any(m.get("event") == "error" for m in written))
    assert listening._mode == "off" and "no input device" in listening.failure
    assert [m["mode"] for m in written if m.get("event") == "state"][-1] == "off"


def test_the_microphone_is_the_mme_sound_mapper_unless_one_is_named(monkeypatch: pytest.MonkeyPatch) -> None:
    """PortAudio's own default microphone is the one Windows had when it started; the mapper follows the default."""
    devices = [{"max_input_channels": 2, "max_output_channels": 0}, {"max_input_channels": 1, "max_output_channels": 0},
               {"max_input_channels": 0, "max_output_channels": 2}, {"max_input_channels": 2, "max_output_channels": 0}]
    sd = SimpleNamespace(query_hostapis=lambda: [{"name": "MME", "devices": [0, 1, 2]},
                                                 {"name": "Windows WASAPI", "devices": [3]}],
                         query_devices=lambda index: devices[index])
    monkeypatch.setitem(__import__("sys").modules, "sounddevice", sd)
    monkeypatch.delenv("BAXY_RENEW_MIC", raising=False)
    listening = object.__new__(Voice)
    assert listening._device() == 0
    monkeypatch.setenv("BAXY_RENEW_MIC", "3")
    assert listening._device() == 3


def test_a_microphone_that_fails_to_start_is_closed_and_opened_again_on_the_next_start(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Revisión de calidad de la mente (2026-10-25): sounddevice opens the stream when it is built and start() may still
    fail (the device busy or gone); the stream was kept, never closed, and the next voice.start found it «open» and said
    the ear was on while it heard nothing (until STALL_S reopened it, and only if the voice was not off)."""
    streams: list = []

    class Input:
        failing = True

        def __init__(self, **_settings) -> None:
            self.started = self.closed = False
            streams.append(self)

        def start(self):
            if Input.failing:
                raise OSError("device unavailable")
            self.started = True

        def close(self) -> None:
            self.closed = True

    def load(self: Voice) -> None:
        self._recognizer, self._input, self._vad = _InstantRecognizer(), True, _Vad()
        self._loaded.set()

    monkeypatch.setitem(__import__("sys").modules, "sounddevice", SimpleNamespace(InputStream=Input))
    monkeypatch.setattr(voice, "Speech", _Speech)
    monkeypatch.setattr(Voice, "_load", load)
    monkeypatch.setattr(Voice, "_device", lambda self: None)
    listening = Voice(lambda message: None)
    assert not listening.start("direct")
    assert streams[0].closed and listening._stream is None
    Input.failing = False
    assert listening.start("direct")
    assert len(streams) == 2 and streams[1].started and listening._stream is streams[1]
    listening.stop()
