"""The staggered wake detector (src/baxy_mind/voice.py, StaggeredWake): each copy is primed a fraction of a chunk of
silence behind the one before, its firings are told in the audio's own time, and one «Baxy» counts once."""
from dataclasses import dataclass

import numpy as np

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
