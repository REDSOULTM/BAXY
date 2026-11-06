"""Listening transcribes outside the voice's lock (src/baxy_mind/voice.py): while Ultra decodes what was heard, a
push-to-talk let go, a stop or BAXY starting to speak do not wait for it, and what was heard before a stop is not told."""
import threading
import time
from types import SimpleNamespace

import numpy as np
import pytest

from baxy_mind import voice, voice_output
from baxy_mind.voice import BLOCK, Voice


class _Speech:
    speaking = False
    ready = False
    deferred = ""

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
        stream.result = SimpleNamespace(text=" abre Steam", tokens=[], timestamps=[], ys_log_probs=[])
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


# Encargo 10 (punto 6): too little memory to commit when the recognizer is built does not turn the ear off for the
# session; it is deferred (the status says so, not a failure) and retried on the next start(), until it loads.
def test_a_low_memory_recognizer_is_deferred_and_retried_on_the_next_start(monkeypatch: pytest.MonkeyPatch) -> None:
    built: list[int] = []

    def recognize(self: Voice, *_args) -> None:
        built.append(1)
        if len(built) < 3:
            raise MemoryError("recognizer not loaded: 200 MB left to commit, 1200 MB needed")
        self._recognizer = _Recognizer()

    def load(self: Voice) -> None:
        self._input, self._vad = True, _Vad()
        self._load_recognizer(None, None)
        self._loaded.set()

    monkeypatch.setattr(voice, "Speech", _Speech)
    monkeypatch.setattr(Voice, "_recognize", recognize)
    monkeypatch.setattr(Voice, "_load", load)
    monkeypatch.setattr(Voice, "_open", lambda self: None)
    listening = Voice(lambda message: None)

    assert listening._loaded.wait(5)
    assert listening._recognizer is None
    assert listening.deferred and not listening.failure
    assert listening.status()["deferred"] is True
    assert listening.status()["stt"] is False

    assert not listening.start("direct")   # a first retry still finds no room: no recognizer, start refused
    assert listening.start("direct")       # a later one loads it: the ear works
    assert listening._recognizer is not None
    assert listening.deferred == ""
    assert not listening.failure
    assert listening.status()["deferred"] is False
    assert built == [1, 1, 1]


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
        stream.result = SimpleNamespace(text=" abre Steam", tokens=[" abre", " Steam"], timestamps=[9.0, 9.3],
                                        ys_log_probs=[0.0, 0.0])


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
    monkeypatch.setattr(voice, "BEHIND_BLOCKS", 100)  # the blocks are queued at once here, never behind a microphone
    listening = Voice(written.append)
    assert listening.start("wake")
    _blocks(listening, 0.1, 15)   # «Baxy» at 0.1 s and the request: its caption
    _blocks(listening, 0.0, 15)   # 0.9 s of silence ends it
    _blocks(listening, 0.1, 25)   # «Baxy» at 4.0 s, the same request again
    _wait_for(lambda: len(_partials(written)) >= 2)
    assert _partials(written) == ["abre Steam", "abre Steam"]


class _VadOutOfMemory(_Vad):
    """Silero, short of memory on the block ``fails`` (F17: a block lost with the PC out of memory)."""

    def __init__(self, fails: int) -> None:
        self.fails, self.seen = fails, 0

    def marks(self, block) -> np.ndarray:
        self.seen += 1
        if self.seen == self.fails:
            raise MemoryError("no room")
        return super().marks(block)


def _request_with_vad(monkeypatch: pytest.MonkeyPatch, written: list[dict], vad: _Vad) -> Voice:
    def load(self: Voice) -> None:
        self._recognizer, self._input, self._detector = _InstantRecognizer(), True, _Wake([0.1])
        self._vad = vad
        self._loaded.set()

    monkeypatch.setattr(voice, "Speech", _Speech)
    monkeypatch.setattr(Voice, "_load", load)
    monkeypatch.setattr(Voice, "_open", lambda self: None)
    monkeypatch.setattr(voice, "BEHIND_BLOCKS", 100)
    listening = Voice(written.append)
    assert listening.start("wake")
    _blocks(listening, 0.1, 15)
    _blocks(listening, 0.0, 15)
    _wait_for(lambda: listening._blocks.empty() and listening._start is None)
    return listening


def _transcripts(written: list[dict]) -> list[str]:
    return [message["text"] for message in written if message.get("type") == "voice.transcript"]


def test_what_is_left_of_a_request_that_lost_audio_does_not_reach_the_mind(monkeypatch: pytest.MonkeyPatch) -> None:
    """F17: what is left of it is not the request. The failure is told (the App's chime and «Falló la escucha») and nothing
    is transcribed as said."""
    written: list[dict] = []
    _request_with_vad(monkeypatch, written, _VadOutOfMemory(5))
    time.sleep(0.2)
    assert _transcripts(written) == []
    assert any(message.get("event") == "error" for message in written)


def test_a_request_that_lost_nothing_is_as_sure_as_the_ear_was(monkeypatch: pytest.MonkeyPatch) -> None:
    written: list[dict] = []
    listening = _request_with_vad(monkeypatch, written, _Vad())
    _wait_for(lambda: bool(_transcripts(written)))
    assert _transcripts(written) == ["abre Steam"]
    assert not any(message.get("event") == "error" for message in written)
    assert listening.unsure("abre Steam") == []


def test_a_block_lost_before_the_audio_of_a_request_does_not_touch_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """Control: a block lost long before the request's audio begins (BEFORE_S) took nothing of it."""
    written: list[dict] = []

    def load(self: Voice) -> None:
        self._recognizer, self._input, self._detector = _InstantRecognizer(), True, _Wake([5.0])
        self._vad = _VadOutOfMemory(3)
        self._loaded.set()

    monkeypatch.setattr(voice, "Speech", _Speech)
    monkeypatch.setattr(Voice, "_load", load)
    monkeypatch.setattr(Voice, "_open", lambda self: None)
    monkeypatch.setattr(voice, "BEHIND_BLOCKS", 100)
    listening = Voice(written.append)
    assert listening.start("wake")
    _blocks(listening, 0.1, 65)
    _blocks(listening, 0.0, 15)
    _wait_for(lambda: bool(_transcripts(written)))
    assert _transcripts(written) == ["abre Steam"]
    assert listening.unsure("abre Steam") == []


def test_a_transcription_out_of_memory_ends_a_direct_request_and_is_told(monkeypatch: pytest.MonkeyPatch) -> None:
    """F17: the recognizer short of memory: nothing is told as heard, the failure is, and the ear goes back to what it
    was doing instead of staying in a dictation nobody is hearing."""
    written: list[dict] = []

    class _Failing(_InstantRecognizer):
        def decode_stream(self, stream: _Stream) -> None:
            raise MemoryError("no room")

    def load(self: Voice) -> None:
        self._recognizer, self._input, self._vad = _Failing(), True, _Vad()
        self._loaded.set()

    monkeypatch.setattr(voice, "Speech", _Speech)
    monkeypatch.setattr(Voice, "_load", load)
    monkeypatch.setattr(Voice, "_open", lambda self: None)
    monkeypatch.setattr(Voice, "_close", lambda self: None)
    monkeypatch.setattr(voice, "BEHIND_BLOCKS", 100)
    listening = Voice(written.append)
    assert listening.start("direct")
    _blocks(listening, 0.1, 5)
    listening.release()
    _blocks(listening, 0.1, 1)
    _wait_for(lambda: listening._mode == "off")
    assert listening._mode == "off" and _transcripts(written) == []
    assert any(message.get("event") == "error" for message in written)


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


# uso-116, seen live with the PC out of commit: sherpa raised RuntimeError «... failed:bad allocation» (std::bad_alloc's
# what() on MSVC), not a MemoryError: the retry thread died on it and the ear never came back, with nothing said.
def test_a_bad_allocation_inside_a_native_load_is_a_lack_of_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(voice_output, "commit_available_mb", lambda: 2000)
    with pytest.raises(voice_output.NotEnoughMemory) as caught:
        with voice_output.native_load(1200, "recognizer"):
            raise RuntimeError("Load model from encoder.int8.onnx failed:bad allocation")
    assert (caught.value.need_mb, caught.value.left_mb) == (1200, 2000)


def test_any_other_error_inside_a_native_load_stays_what_it_is(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(voice_output, "commit_available_mb", lambda: 2000)
    with pytest.raises(RuntimeError, match="no such file"):
        with voice_output.native_load(1200, "recognizer"):
            raise RuntimeError("no such file")


def test_a_retry_that_fails_for_another_reason_says_it_and_stops() -> None:
    def fails() -> None:
        raise RuntimeError("the model file is broken")

    owner = SimpleNamespace(_stt_lock=threading.Lock(), _stt_retry=fails, _recognizer=None, failure="", deferred="d",
                            _stt_memory={"needMb": 1}, _event=lambda _name: None)
    Voice._retry_recognizer(owner)
    assert "broken" in owner.failure and owner._stt_retry is None and owner.deferred == "" and owner._stt_memory is None


# Uso real 2026-11-02: the recognizer is the voice's largest piece (814 MB more committed on the notebook as it loads);
# with less memory left to commit than it needs it is not built, and the voice's failure says why.
def test_the_recognizer_is_not_built_without_the_memory_to_load_it(
        tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    built: list[dict] = []
    sherpa = SimpleNamespace(OfflineRecognizer=SimpleNamespace(
        from_transducer=lambda **kwargs: built.append(kwargs) or object()))
    monkeypatch.setenv("BAXY_RENEW_STT_HOTWORDS", "0")
    monkeypatch.setattr(voice_output, "commit_available_mb", lambda: voice_output.EAR_COMMIT_MB - 1, raising=False)
    owner = SimpleNamespace(_named=threading.Event(), _names=None, _recognizer=None, _hotwords="")
    with pytest.raises(MemoryError, match="MB"):
        Voice._recognize(owner, sherpa, tmp_path)
    assert built == []
    assert owner._recognizer is None
