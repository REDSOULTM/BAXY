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
