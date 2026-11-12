"""The wake log (src/baxy_mind/voice.py, WakeLog; encargo 15, development only): with BAXY_WAKE_LOG_DIR, each «Baxy»
heard leaves a WAV of 4 s before and after the trigger and a JSON with the request that followed; near misses too;
without it nothing is written. Synthetic audio and a fake detector."""
import json
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from baxy_mind import voice
from baxy_mind.voice import BLOCK, RATE, StaggeredWake, Voice, package_sha256


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
    """Hears «abre Steam», its words well after the call."""

    def create_stream(self) -> _Stream:
        return _Stream()

    def decode_stream(self, stream: _Stream) -> None:
        stream.result = SimpleNamespace(text=" abre Steam", tokens=[" abre", " Steam"], timestamps=[2.5, 2.8],
                                        ys_log_probs=[0.0, 0.0])


class _Vad:
    def reset(self) -> None:
        pass

    def marks(self, block, settle: bool = False) -> np.ndarray:
        return np.ones(len(block), bool)


@dataclass
class _Hit:
    time_s: float
    probability: float


class _Detector:
    """Fires at each (time, probability) of ``fires``; with its trace on, scores a frame every 40 ms as ``score``."""

    shift = 128

    def __init__(self, fires: list[tuple[float, float]], score=lambda t: 0.01) -> None:
        self.fires, self.score = fires, score
        self.reset()

    def reset(self) -> None:
        self.samples = 0
        self.trace = None

    def accept(self, block: np.ndarray) -> list[_Hit]:
        before, self.samples = self.samples / RATE, self.samples + len(block)
        after = self.samples / RATE
        if self.trace is not None:
            for k in range(int(round(before / 0.04)) + 1, int(round(after / 0.04)) + 1):
                self.trace.append((k * 0.04, self.score(k * 0.04)))
        return [_Hit(t, p) for t, p in self.fires if before < t <= after]


def _listening(monkeypatch: pytest.MonkeyPatch, detector: _Detector) -> Voice:
    def load(self: Voice) -> None:
        self._recognizer, self._input, self._vad = _Recognizer(), True, _Vad()
        self._detector = StaggeredWake(lambda: detector, 1, 2.0)
        self._loaded.set()

    monkeypatch.setattr(voice, "Speech", _Speech)
    monkeypatch.setattr(Voice, "_load", load)
    monkeypatch.setattr(Voice, "_open", lambda self: None)
    listening = Voice(lambda message: None)
    assert listening.start("wake")
    return listening


def _hear(listening: Voice, level: float, seconds: float) -> None:
    for _ in range(int(round(seconds * 10))):
        listening._blocks.put(np.full(BLOCK, level, np.float32))


def _call_and_request(listening: Voice) -> None:
    """A quiet room, «Baxy» ending at 5.5 s (where the detector fires), «abre Steam» and its silence: 10 s."""
    _hear(listening, 0.001, 5.0)
    _hear(listening, 0.1, 2.0)
    _hear(listening, 0.001, 3.0)


def _record(path: Path) -> dict:
    for wait in (0.05, 0.1, 0.2, 0.4, None):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except PermissionError:
            if wait is None:    # Windows refuses it for an instant while the writer's os.replace puts the new one there
                raise
            time.sleep(wait)
    raise AssertionError(path)


def _records(folder: Path) -> list[dict]:
    return [_record(path) for path in sorted(folder.glob("*/*.json"))]


def _wait_for(condition, seconds: float = 10.0) -> None:
    deadline = time.monotonic() + seconds
    while not condition() and time.monotonic() < deadline:
        time.sleep(0.02)


@pytest.fixture
def wake_dir(tmp_path: Path) -> Path:
    folder = tmp_path / "baxy-wake-prueba"
    folder.mkdir()
    (folder / "config.json").write_text('{"threshold": 0.5}', encoding="utf-8")
    (folder / "head.onnx").write_bytes(b"cabeza")
    return folder


def test_without_the_variable_nothing_is_written(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
                                                 wake_dir: Path) -> None:
    monkeypatch.delenv("BAXY_WAKE_LOG_DIR", raising=False)
    monkeypatch.setenv("BAXY_RENEW_WAKE_DIR", str(wake_dir))
    listening = _listening(monkeypatch, _Detector([(5.5, 0.87)]))
    _call_and_request(listening)
    _wait_for(lambda: listening._total >= 100 * BLOCK and listening._start is None)
    time.sleep(0.3)
    assert listening._wake_log is None
    assert sorted(p.name for p in tmp_path.rglob("*") if p.is_file()) == ["config.json", "head.onnx"]


def test_a_wake_leaves_eight_seconds_of_audio_and_the_request_that_followed(monkeypatch: pytest.MonkeyPatch,
                                                                            tmp_path: Path, wake_dir: Path) -> None:
    log = tmp_path / "registro"
    monkeypatch.setenv("BAXY_WAKE_LOG_DIR", str(log))
    monkeypatch.setenv("BAXY_RENEW_WAKE_DIR", str(wake_dir))
    monkeypatch.setenv("COMPUTERNAME", "PC-PRUEBA")
    listening = _listening(monkeypatch, _Detector([(5.5, 0.87)]))
    _call_and_request(listening)
    _wait_for(lambda: [r for r in _records(log) if r["after_s"] is not None and r["transcript"] is not None])

    [record] = _records(log)
    assert record["near_miss"] is False
    assert record["probability"] == 0.87
    assert record["machine"] == "PC-PRUEBA"
    assert record["renew_wake_sha256"] == package_sha256(wake_dir)
    assert record["transcript"] == "abre Steam" and record["continued"] is True and record["empty"] is None
    assert (record["before_s"], record["after_s"]) == (4.0, 4.0)
    [day] = log.iterdir()
    assert day.name == record["time"][:10]
    with wave.open(str(day / record["wav"]), "rb") as clip:
        assert (clip.getframerate(), clip.getnchannels(), clip.getsampwidth()) == (RATE, 1, 2)
        assert clip.getnframes() == 8 * RATE
        audio = np.frombuffer(clip.readframes(clip.getnframes()), "<i2")
    assert audio[4 * RATE - 1] == round(0.1 * 32767)   # «Baxy» ends at the trigger, 4 s into the clip
    assert audio[int(5.5 * RATE)] == round(0.001 * 32767)  # the request's silence after it


def test_a_wake_with_nothing_after_it_is_told_as_no_voice(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
                                                         wake_dir: Path) -> None:
    log = tmp_path / "registro"
    monkeypatch.setenv("BAXY_WAKE_LOG_DIR", str(log))
    monkeypatch.setenv("BAXY_RENEW_WAKE_DIR", str(wake_dir))
    listening = _listening(monkeypatch, _Detector([(5.5, 0.6)]))
    _hear(listening, 0.001, 5.0)
    _hear(listening, 0.1, 0.5)
    _hear(listening, 0.001, 5.0)   # NO_COMMAND_S without a word
    _wait_for(lambda: [r for r in _records(log) if r["after_s"] is not None and r["transcript"] is not None])
    [record] = _records(log)
    assert (record["transcript"], record["continued"], record["empty"]) == ("", False, "no_voice")


def test_a_microphone_closed_before_the_clip_ends_keeps_what_was_heard(monkeypatch: pytest.MonkeyPatch,
                                                                       tmp_path: Path, wake_dir: Path) -> None:
    log = tmp_path / "registro"
    monkeypatch.setenv("BAXY_WAKE_LOG_DIR", str(log))
    monkeypatch.setenv("BAXY_RENEW_WAKE_DIR", str(wake_dir))
    listening = _listening(monkeypatch, _Detector([(5.5, 0.87)]))
    _hear(listening, 0.001, 5.0)
    _hear(listening, 0.1, 2.0)   # 1.5 s past the trigger
    _wait_for(lambda: listening._total >= 70 * BLOCK)
    listening.stop()
    _wait_for(lambda: [r for r in _records(log) if r["after_s"] is not None])
    [record] = _records(log)
    assert (record["before_s"], record["after_s"]) == (4.0, 1.5)
    assert record["transcript"] is None   # the request never ended
    with wave.open(str(log / record["time"][:10] / record["wav"]), "rb") as clip:
        assert clip.getnframes() == int(5.5 * RATE)


def test_a_log_that_cannot_be_written_does_not_stop_the_voice(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
                                                              wake_dir: Path, capfd: pytest.CaptureFixture) -> None:
    blocked = tmp_path / "es-un-fichero"
    blocked.write_text("", encoding="utf-8")
    written: list[dict] = []
    monkeypatch.setenv("BAXY_WAKE_LOG_DIR", str(blocked))
    monkeypatch.setenv("BAXY_RENEW_WAKE_DIR", str(wake_dir))
    listening = _listening(monkeypatch, _Detector([(5.5, 0.87)]))
    listening._write = written.append
    _call_and_request(listening)
    _wait_for(lambda: any(m.get("type") == "voice.transcript" for m in written))
    assert [m["text"] for m in written if m.get("type") == "voice.transcript"] == ["abre Steam"]
    err: list[str] = []
    _wait_for(lambda: err.append(capfd.readouterr().err) or "baxy_mind_renew_voice: wake log:" in "".join(err))
    assert "baxy_mind_renew_voice: wake log:" in "".join(err)


def test_a_near_miss_is_kept_once_in_two_seconds_and_never_beside_a_firing(monkeypatch: pytest.MonkeyPatch,
                                                                         tmp_path: Path, wake_dir: Path) -> None:
    def score(t: float) -> float:
        if 3.0 <= t <= 3.1:
            return 0.3
        if 3.8 <= t <= 3.9:
            return 0.35    # the same near miss, sure-er: it is the one kept
        if 9.6 <= t <= 9.7:
            return 0.4     # just before «Baxy»: part of it
        if 9.9 <= t <= 10.0:
            return 0.9
        return 0.01

    log = tmp_path / "registro"
    monkeypatch.setenv("BAXY_WAKE_LOG_DIR", str(log))
    monkeypatch.setenv("BAXY_RENEW_WAKE_DIR", str(wake_dir))
    listening = _listening(monkeypatch, _Detector([(10.0, 0.9)], score))
    _hear(listening, 0.001, 9.5)
    _hear(listening, 0.1, 0.5)
    _hear(listening, 0.001, 5.0)
    _wait_for(lambda: len([r for r in _records(log) if r["after_s"] is not None]) >= 2
              and all(r["transcript"] is not None for r in _records(log) if not r["near_miss"]))
    time.sleep(0.3)
    records = _records(log)
    near = [r for r in records if r["near_miss"]]
    assert [r["probability"] for r in near] == [0.35]
    assert (near[0]["transcript"], near[0]["continued"]) == (None, None)
    assert [r["probability"] for r in records if not r["near_miss"]] == [0.9]


def test_a_record_being_replaced_can_still_be_read(tmp_path: Path, wake_dir: Path) -> None:
    """Windows refuses to open a file for an instant while os.replace puts another in its place: under load this hit the
    tests above, each polling while the writer rewrites."""
    log = tmp_path / "registro"
    wake_log = voice.WakeLog(log, wake_dir)
    wake_log.hear(np.full(BLOCK, 0.001, np.float32))
    key = wake_log.mark(0.0, 0.3)
    _wait_for(lambda: _records(log))
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        wake_log.turn(key, "abre Steam", True)
        _records(log)
    assert _records(log)


def test_a_near_miss_before_baxy_speaks_keeps_its_own_clip(tmp_path: Path, wake_dir: Path) -> None:
    """While BAXY speaks the detector hears nothing (no scores), but the microphone's blocks still come: the near miss
    is kept on time, with its 4 s before and after."""
    log = tmp_path / "registro"
    wake_log = voice.WakeLog(log, wake_dir)
    for _ in range(60):
        wake_log.hear(np.full(BLOCK, 0.001, np.float32))
    wake_log.scores([(0.0, 0.3)], [])   # a frame at 6 s, the end of what was heard
    for _ in range(200):                # 20 s of BAXY's answer, the detector off
        wake_log.hear(np.full(BLOCK, 0.2, np.float32))
    _wait_for(lambda: [r for r in _records(log) if r["after_s"] is not None])
    [record] = _records(log)
    assert (record["near_miss"], record["probability"]) == (True, 0.3)
    assert (record["before_s"], record["after_s"]) == (4.0, 4.0)
    with wave.open(str(log / record["time"][:10] / record["wav"]), "rb") as clip:
        audio = np.frombuffer(clip.readframes(clip.getnframes()), "<i2")
    assert len(audio) == 8 * RATE and audio[4 * RATE - 1] == round(0.001 * 32767)
