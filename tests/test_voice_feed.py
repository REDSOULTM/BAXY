"""Spoken turns without a microphone (src/baxy_mind/voice_feed.py, scripts/voice/hablar.py): BAXY_RENEW_VOICE_FEED's WAV
files reach the voice as the microphone's blocks would, in real time, each after BAXY answered the one before and its
gap; the microphone is never opened; while the voice is closed the files wait where they were; a feed that cannot be
heard is told as the missing input. The clock runs faster here (Feed.pace)."""
import datetime as dt
import json
import sys
import threading
import time
import wave
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from baxy_mind import voice, voice_feed
from baxy_mind.voice import BLOCK, RATE, Voice
from baxy_mind.voice_feed import listed

PACE = 0.05


class _Speech:
    ready = False

    def __init__(self, *_args) -> None:
        self.speaking = False


class _Stream:
    result = None

    def accept_waveform(self, _rate, audio) -> None:
        self.audio = audio


class _Recognizer:
    """«uno» for the file of constant voice, «dos» for the one whose voice alternates its sign."""

    def create_stream(self) -> _Stream:
        return _Stream()

    def decode_stream(self, stream: _Stream) -> None:
        word = " dos" if (stream.audio < 0).any() else " uno"
        stream.result = SimpleNamespace(text=word, tokens=[word], timestamps=[99.0], ys_log_probs=[0.0])  # after any call


class _Vad:
    """Silero hears speech in every sample: here the levels decide (voice.Vad itself: test_voice_vad.py)."""

    def reset(self) -> None:
        pass

    def marks(self, block) -> np.ndarray:
        return np.ones(len(block), bool)


def _wav(path: Path, voice_s: float, alternate: bool = False, rate: int = RATE) -> Path:
    n = int(voice_s * rate)
    said = np.full(n, 0.1, np.float32)
    if alternate:
        said[1::2] = -0.1
    audio = np.concatenate([np.zeros(int(0.2 * rate), np.float32), said, np.zeros(int(0.2 * rate), np.float32)])
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes((audio * 32767).astype("<i2").tobytes())
    return path


def _voice(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, spec: str, answer: bool = True):
    """A Voice hearing ``spec``; ``answer``: BAXY answers each transcript (an answer sounds, then it is silent)."""
    log = tmp_path / "feed.jsonl"
    monkeypatch.setenv("BAXY_RENEW_VOICE_FEED", spec)
    monkeypatch.setenv("BAXY_RENEW_VOICE_FEED_GAP", "0.5")
    monkeypatch.setenv("BAXY_RENEW_VOICE_FEED_LOG", str(log))
    monkeypatch.setattr(voice_feed.Feed, "pace", PACE)
    monkeypatch.setitem(sys.modules, "sounddevice", None)  # importing it fails: the microphone is never touched
    monkeypatch.setattr(voice, "Speech", _Speech)

    def load(self: Voice) -> None:
        self._recognizer, self._vad = _Recognizer(), _Vad()
        self._hear_from(_Vad)
        self._loaded.set()

    monkeypatch.setattr(Voice, "_load", load)
    written: list[dict] = []
    answers: list[float] = []
    holder: dict = {}

    def reply() -> None:
        listening = holder["voice"]
        listening.speech.speaking = True
        answers.append(time.time())
        listening._sounding(0.0, 0.0, False)
        time.sleep(0.1)
        listening.speech.speaking = False

    def write(message: dict) -> None:
        written.append(message)
        if answer and message.get("type") == "voice.transcript":
            threading.Thread(target=reply, daemon=True).start()

    holder["voice"] = listening = Voice(write)
    listening._loaded.wait(5)
    return listening, written, answers, log


def _until(condition, seconds: float = 10.0) -> None:
    deadline = time.monotonic() + seconds
    while not condition() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert condition()


def _transcripts(written: list[dict]) -> list[str]:
    return [m["text"] for m in written if m.get("type") == "voice.transcript"]


def _log(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.is_file() else []


def _at(text: str) -> float:
    return dt.datetime.fromisoformat(text).timestamp()


def test_the_files_are_heard_as_the_microphone_and_each_waits_for_the_answer(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _wav(tmp_path / "1.wav", 0.5)
    _wav(tmp_path / "2.wav", 0.8, alternate=True)
    listening, written, answers, log = _voice(monkeypatch, tmp_path, str(tmp_path))
    assert listening.status()["input"] and listening.start("wake") is False  # no wake word here: direct only
    assert listening.start("direct")
    _until(lambda: _transcripts(written) == ["uno"])
    # A direct request is one utterance: the voice closes, and the second file waits until it is opened again.
    time.sleep(40 * BLOCK / RATE * PACE)
    assert _transcripts(written) == ["uno"] and [row["event"] for row in _log(log)] == ["said"]
    assert listening.start("direct")
    _until(lambda: _transcripts(written) == ["uno", "dos"])
    _until(lambda: [row["event"] for row in _log(log)] == ["said", "said", "done"])
    first, second, _ = _log(log)
    assert first["wav"].endswith("1.wav") and second["wav"].endswith("2.wav") and second["audio_s"] == 1.2
    # The second began after the answer to the first and its gap of quiet; its voice ends 1.0 s in, as voice.py sees it.
    assert _at(second["started_at"]) >= answers[0] + 0.5 * PACE
    assert _at(second["voice_end_at"]) - _at(second["started_at"]) == pytest.approx(1.0 * PACE, abs=0.002)


def test_in_wake_mode_the_next_file_waits_for_the_answer_or_the_reply_wait(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _wav(tmp_path / "1.wav", 0.5)
    _wav(tmp_path / "2.wav", 0.5, alternate=True)
    monkeypatch.setattr(voice_feed, "REPLY_WAIT_S", 3.0)
    listening, written, answers, log = _voice(monkeypatch, tmp_path, str(tmp_path), answer=False)

    class Wake:
        """«Baxy» is heard at the first block of voice after quiet."""

        def __init__(self) -> None:
            self.t, self.armed = 0.0, True

        def reset(self) -> None:
            self.t, self.armed = 0.0, True

        def accept(self, block) -> list:
            self.t += len(block) / RATE
            if self.armed and np.abs(block).max() > 0.05:
                self.armed = False
                return [SimpleNamespace(time_s=self.t - len(block) / RATE)]
            return []

    listening._detector = Wake()
    assert listening.start("wake")
    _until(lambda: len(_transcripts(written)) == 1)
    listening._detector.armed = True
    _until(lambda: len(_transcripts(written)) == 2)
    _until(lambda: [row["event"] for row in _log(log)][-1:] == ["done"])
    first, second = _log(log)[:2]
    # Nobody answered: the second waited REPLY_WAIT_S after the first ended, then its gap.
    assert _at(second["started_at"]) - _at(first["ended_at"]) >= (3.0 + 0.5) * PACE - 0.01
    assert answers == []


def test_the_list_names_the_files_and_their_gaps(tmp_path: Path) -> None:
    for name in ("b.wav", "a.wav"):
        _wav(tmp_path / name, 0.1)
    assert listed(str(tmp_path)) == [(tmp_path / "a.wav", None), (tmp_path / "b.wav", None)]
    (tmp_path / "feed.txt").write_text("# a comment\nb.wav\t3.5\n\na.wav\n", encoding="utf-8")
    assert listed(str(tmp_path / "feed.txt")) == [(tmp_path / "b.wav", 3.5), (tmp_path / "a.wav", None)]
    assert listed(str(tmp_path / "a.wav")) == [(tmp_path / "a.wav", None)]
    assert listed(f"{tmp_path / 'a.wav'};{tmp_path / 'b.wav'}") == [(tmp_path / "a.wav", None), (tmp_path / "b.wav", None)]


def test_a_feed_that_cannot_be_heard_is_told_and_no_microphone_is_opened(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _wav(tmp_path / "44k.wav", 0.2, rate=44100)
    listening, _, _, _ = _voice(monkeypatch, tmp_path, str(tmp_path / "44k.wav"))
    assert listening.failure.startswith("voice feed:") and "44100 Hz" in listening.failure
    assert not listening.status()["input"] and not listening.status()["available"]
    assert listening.start("direct") is False


def test_without_the_setting_there_is_no_feed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BAXY_RENEW_VOICE_FEED", raising=False)
    assert voice_feed.from_env(RATE, BLOCK, lambda audio: np.ones(len(audio) // BLOCK, bool), lambda: True,
                               lambda: 0) is None
