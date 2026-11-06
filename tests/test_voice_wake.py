"""The staggered wake detector (src/baxy_mind/voice.py, StaggeredWake): each copy is primed a fraction of a chunk of
silence behind the one before, its firings are told in the audio's own time, and one «Baxy» counts once."""
from dataclasses import dataclass
from types import SimpleNamespace

import numpy as np
import pytest

from baxy_mind.voice import RATE, StaggeredWake


@dataclass
class Hit:
    time_s: float
    probability: float


class FakeDetector:
    """Fires once when its fed audio passes `at` seconds of its own time."""

    shift = 128  # fbank frames per chunk, as k4's Kroko encoder (1.28 s)

    def __init__(self, at: float) -> None:
        self.at = at
        self.reset()

    def reset(self) -> None:
        self.samples = 0
        self.fired = False

    def accept(self, audio: np.ndarray) -> list[Hit]:
        self.samples += len(audio)
        if not self.fired and self.samples / RATE >= self.at:
            self.fired = True
            return [Hit(self.at, 0.9)]
        return []


def test_copies_are_primed_a_fraction_of_a_chunk_apart_and_told_in_the_audios_time() -> None:
    made: list[FakeDetector] = []

    def make() -> FakeDetector:
        made.append(FakeDetector(at=2.0))
        return made[-1]

    wake = StaggeredWake(make, 2, rearm_s=2.0)
    assert [d.samples for d in wake._copies] == [0, int(0.64 * RATE)]
    heard = []
    for _ in range(40):
        heard += wake.accept(np.zeros(1600, np.float32))
    # the second copy, 0.64 s of silence ahead, reaches its 2.0 s first, at 1.36 s of the audio; the first copy's
    # firing at 2.0 s is the same «Baxy» and is not told again
    assert [round(h.time_s, 2) for h in heard] == [1.36]


def test_reset_primes_the_copies_again() -> None:
    made: list[FakeDetector] = []
    wake = StaggeredWake(lambda: made.append(FakeDetector(at=5.0)) or made[-1], 4, rearm_s=2.0)
    wake.accept(np.zeros(1600, np.float32))
    wake.reset()
    assert [d.samples for d in wake._copies] == [0, int(0.32 * RATE), int(0.64 * RATE), int(0.96 * RATE)]


def test_one_detector_is_built_and_the_copies_share_its_sessions_with_their_own_state() -> None:
    made: list[FakeDetector] = []
    wake = StaggeredWake(lambda: made.append(FakeDetector(at=5.0)) or made[-1], 4, rearm_s=2.0)
    assert len(made) == 1  # the model sessions are loaded once, not once per copy
    assert len({id(d) for d in wake._copies}) == 4
    assert all(d.at is made[0].at for d in wake._copies)  # what reset() does not make again is shared
    wake._copies[1].samples += 1
    assert wake._copies[2].samples == int(0.64 * RATE)  # each copy's state is its own


def test_the_detector_hears_a_soft_call_raised_and_a_loud_one_as_it_is() -> None:
    from baxy_mind import voice as _voice
    soft = np.full(_voice.BLOCK, 0.05, np.float32)
    peak = 0.0
    for _ in range(50):  # seconds of a soft room: the gain reaches its cap
        peak, raised = _voice.wake_gain(peak, soft)
    assert np.allclose(raised, soft * _voice.WAKE_GAIN_CAP)
    loud = np.full(_voice.BLOCK, 0.9, np.float32)
    peak, raised = _voice.wake_gain(peak, loud)
    assert np.array_equal(raised, loud * (_voice.WAKE_TARGET / 0.9)) and np.abs(raised).max() <= _voice.WAKE_TARGET + 1e-6


_FAKE_RUNTIME = '''
class _Options:
    def __init__(self):
        self.entries = {}

    def add_session_config_entry(self, key, value):
        self.entries[key] = value


class _Ort:
    SessionOptions = _Options
    version = "fake"


ort = _Ort()


class BaxyWakeDetector:
    shift = 128

    def __init__(self, encoder, head, threshold, debounce_s, threads):
        self.threads = threads
        self.options = ort.SessionOptions()
        self.version = ort.version

    def reset(self):
        pass

    def accept(self, audio):
        return []
'''


def _fake_package(folder):
    folder.mkdir()
    (folder / "config.json").write_text('{"encoder": {"file": "e.onnx"}, "head": {"file": "h.onnx"}, '
                                        '"threshold": 0.5, "debounce_s": 2.0}', encoding="utf-8")
    (folder / "baxy_wake_runtime.py").write_text(_FAKE_RUNTIME, encoding="utf-8")
    return folder


def test_the_wake_encoder_runs_on_two_threads_that_sleep_when_idle(tmp_path, monkeypatch) -> None:
    from baxy_mind import voice as _voice
    monkeypatch.delenv("BAXY_RENEW_WAKE_THREADS", raising=False)
    wake = _voice.load_wake(_fake_package(tmp_path / "wake"))
    assert len(wake._copies) == _voice.WAKE_COPIES
    first = wake._copies[0]
    assert first.threads == 2
    # an idle ONNX Runtime thread spins by default: two spinning threads tripled the CPU of a copy (0.108 -> 0.334 of a
    # core) for the same chunk time
    assert first.options.entries == {"session.intra_op.allow_spinning": "0"}
    assert first.version == "fake"  # the rest of the package's onnxruntime is the same


def test_one_wake_thread_comes_back_with_the_variable(tmp_path, monkeypatch) -> None:
    from baxy_mind import voice as _voice
    monkeypatch.setenv("BAXY_RENEW_WAKE_THREADS", "1")
    assert _voice.load_wake(_fake_package(tmp_path / "wake"))._copies[0].threads == 1
    monkeypatch.setenv("BAXY_RENEW_WAKE_THREADS", "dos")
    assert _voice.load_wake(_fake_package(tmp_path / "wake2"))._copies[0].threads == _voice.WAKE_THREADS


class _CountingWake:
    """Counts its resets; after the second one, «Baxy» is heard 0.5 s into what it hears."""

    def __init__(self) -> None:
        self.resets, self.t, self.fired = 0, 0.0, False

    def reset(self) -> None:
        self.resets, self.t = self.resets + 1, 0.0

    def accept(self, block) -> list:
        self.t += len(block) / RATE
        if self.resets == 2 and not self.fired and self.t >= 0.5:
            self.fired = True
            return [SimpleNamespace(time_s=0.5)]
        return []


def _listening_quietly(speech: bool):
    from baxy_mind import voice as _voice

    class _Marks:
        def reset(self) -> None:
            pass

        def marks(self, block) -> np.ndarray:
            return np.full(len(block), speech, bool)

    listening = object.__new__(_voice.Voice)
    listening._mode, listening._detector, listening._vad = "wake", _CountingWake(), _Marks()
    listening._on_early, listening._on_wake, listening._heard = None, None, 0
    listening._wake_peak, listening._write = _voice.WAKE_TARGET, lambda message: None
    listening._reset()
    return listening


def test_with_no_request_the_wake_detector_starts_afresh_after_a_quiet_minute() -> None:
    from baxy_mind import voice as _voice
    listening = _listening_quietly(speech=False)
    block = np.zeros(_voice.BLOCK, np.float32)
    for _ in range(int(_voice.WAKE_RESET_S * 10) + 6):  # a minute and 0.6 s of a quiet room
        listening._feed(block)
    assert listening._detector.resets == 2
    # reset with the block that completes the minute (it began 0.1 s before), «Baxy» 0.5 s into what it heard since
    assert listening._start == pytest.approx(_voice.WAKE_RESET_S - _voice.BLOCK / RATE + 0.5)


def test_while_someone_speaks_the_wake_detector_is_not_reset() -> None:
    from baxy_mind import voice as _voice
    listening = _listening_quietly(speech=True)
    block = np.full(_voice.BLOCK, 0.0, np.float32)
    for _ in range(int(_voice.WAKE_RESET_S * 10) + 20):
        listening._feed(block)
    assert listening._detector.resets == 1  # only the start's


def test_a_package_that_names_its_copies_and_threads_gets_them(tmp_path) -> None:
    # uso-79: k6r decides every 40 ms from what it already heard; it was measured as one copy on one thread
    import json
    from baxy_mind import voice as _voice
    folder = _fake_package(tmp_path / "k6r")
    config = json.loads((folder / "config.json").read_text(encoding="utf-8"))
    (folder / "config.json").write_text(json.dumps({**config, "copies": 1, "threads": 1}), encoding="utf-8")
    wake = _voice.load_wake(folder)
    assert len(wake._copies) == 1 and wake._copies[0].threads == 1


def test_the_fast_package_is_loaded_only_when_it_is_set(tmp_path, monkeypatch, capsys) -> None:
    from baxy_mind import voice as _voice
    monkeypatch.delenv("BAXY_RENEW_WAKE_FAST_DIR", raising=False)
    assert _voice.load_fast_wake() is None  # a machine without the package: k5 alone, as before
    assert capsys.readouterr().err == ""
    monkeypatch.setenv("BAXY_RENEW_WAKE_FAST_DIR", str(_fake_package(tmp_path / "k6r")))
    assert isinstance(_voice.load_fast_wake(), StaggeredWake)
    # uso-93: on by default, so the mind's stderr log says it is heard (an installed BAXY has no other trace of it)
    assert "k6r heard beside the wake word" in capsys.readouterr().err


def test_none_turns_the_fast_package_off_without_a_failure(tmp_path, monkeypatch, capsys) -> None:
    # uso-93: the App gives the registered package by default; a bench (or whoever wants it off) says none
    from baxy_mind import voice as _voice
    for off in ("none", "NONE", " none "):
        monkeypatch.setenv("BAXY_RENEW_WAKE_FAST_DIR", off)
        assert _voice.load_fast_wake() is None
    assert capsys.readouterr().err == ""


def test_a_fast_package_that_does_not_load_leaves_k5_alone(tmp_path, monkeypatch, capsys) -> None:
    from baxy_mind import voice as _voice
    monkeypatch.setenv("BAXY_RENEW_WAKE_FAST_DIR", str(tmp_path / "missing"))
    assert _voice.load_fast_wake() is None
    assert "k5 is heard alone" in capsys.readouterr().err


def _either(k5_at: float, fast_at: float):
    from baxy_mind import voice as _voice
    k5 = StaggeredWake(lambda: FakeDetector(at=k5_at), 1, rearm_s=2.0)
    fast = StaggeredWake(lambda: FakeDetector(at=fast_at), 1, rearm_s=2.0)
    return _voice.EitherWake(k5, fast), k5


def _heard(wake, seconds: float) -> list[float]:
    heard = []
    for _ in range(int(seconds * 10)):
        heard += [round(h.time_s, 2) for h in wake.accept(np.zeros(1600, np.float32))]
    return heard


def test_either_tells_the_first_firing_and_the_other_one_of_the_same_word_never() -> None:
    # k6r fires at the word's end (3.0 s); k5 tells the same word a chunk later, with its frame's time (2.9 s)
    wake, _ = _either(k5_at=2.9, fast_at=3.0)
    wake._main._copies[0].samples = -int(1.2 * RATE)  # k5's firing reaches it 1.2 s later than its frame time
    assert _heard(wake, 6) == [3.0]


def test_either_still_hears_what_only_k5_hears_and_a_later_word() -> None:
    wake, _ = _either(k5_at=1.0, fast_at=99.0)  # the fast package never fires: k5 alone, as before
    assert _heard(wake, 3) == [1.0]
    wake, _ = _either(k5_at=1.0, fast_at=3.5)    # another word past the re-arm is told again
    assert _heard(wake, 5) == [1.0, 3.5]


def test_either_resets_both_and_scores_are_k5s() -> None:
    wake, k5 = _either(k5_at=1.0, fast_at=1.0)
    assert _heard(wake, 2) == [1.0]
    wake.reset()
    assert _heard(wake, 2) == [1.0]  # both heard from zero again, the re-arm with them
    k5._copies[0].trace = [(0.5, 0.2)]
    assert wake.scores() == [(0.5, 0.2)]


def test_a_package_names_how_long_f44_holds_its_firings_and_k5_keeps_the_second(tmp_path) -> None:
    import json
    from baxy_mind import voice as _voice, voice_echo
    assert _voice.load_wake(_fake_package(tmp_path / "k5")).played_hold_s == voice_echo.PLAYED_HOLD_S
    folder = _fake_package(tmp_path / "k6r")
    config = json.loads((folder / "config.json").read_text(encoding="utf-8"))
    (folder / "config.json").write_text(json.dumps({**config, "played_hold_s": 0.2}), encoding="utf-8")
    fast = _voice.load_wake(folder)
    assert fast.played_hold_s == 0.2
    # beside k5 the check is k5's (EitherWake.twin), so its second stands
    assert _voice.EitherWake(_voice.load_wake(_fake_package(tmp_path / "k5b")), fast).played_hold_s == voice_echo.PLAYED_HOLD_S
