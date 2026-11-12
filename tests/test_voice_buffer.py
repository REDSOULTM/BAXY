"""The audio the voice keeps while it hears (src/baxy_mind/voice.py, Recent): the last KEEP_S seconds and their Silero
marks, in buffers allocated once. Real use, 2026-11-03: joining the 30 s window again for every 100 ms block failed with
MemoryError((481600,), float32) when the PC was short of memory, the block was lost, and a request was transcribed from
the middle of the sentence."""
import numpy as np
import pytest

from baxy_mind import voice
from baxy_mind.voice import BLOCK, KEEP_S, RATE, Voice


class _NoWake:
    def reset(self) -> None:
        pass

    def accept(self, block) -> list:
        return []

    def scores(self) -> list:
        return []


class _Marks:
    def reset(self) -> None:
        pass

    def marks(self, block, settle: bool = False) -> np.ndarray:
        return np.zeros(len(block), bool)


def _listening() -> Voice:
    listening = object.__new__(Voice)
    listening._mode, listening._detector, listening._vad = "wake", _NoWake(), _Marks()
    listening._on_early, listening._on_wake, listening._heard = None, None, 0
    listening._wake_peak, listening._write = voice.WAKE_TARGET, lambda message: None
    listening._reset()
    return listening


def test_hearing_keeps_the_last_window_without_joining_it_again(monkeypatch: pytest.MonkeyPatch) -> None:
    joined = np.concatenate

    def short_of_memory(arrays, *args, **kwargs):  # only small arrays can be made
        if sum(len(a) for a in arrays) > 4 * BLOCK:
            raise MemoryError("no room")
        return joined(arrays, *args, **kwargs)

    listening = _listening()
    monkeypatch.setattr(np, "concatenate", short_of_memory)
    heard = int(KEEP_S * 10) + 55  # every block numbered by its value
    for i in range(heard):
        listening._feed(np.full(BLOCK, i, np.float32))
    kept = int(KEEP_S * RATE)
    assert len(listening._audio) == len(listening._speech) == kept
    assert listening._first == heard * BLOCK - kept
    assert listening._audio[0] == heard - KEEP_S * 10 and listening._audio[-1] == heard - 1
    now = heard * BLOCK / RATE
    assert np.array_equal(listening._segment(now - 1.0, now), np.repeat(np.arange(heard - 10, heard), BLOCK))


def test_each_wake_is_told_on_stderr_with_its_time_and_probability_only(capsys: pytest.CaptureFixture[str]) -> None:
    from types import SimpleNamespace

    class _Fires(_NoWake):
        def __init__(self) -> None:
            self.heard = 0

        def accept(self, block) -> list:
            self.heard += 1
            return [SimpleNamespace(time_s=0.3, probability=0.987)] if self.heard == 5 else []

    listening = _listening()
    listening._detector = _Fires()
    listening._reset()
    listening._event = lambda name: None
    for _ in range(5):
        listening._feed(np.full(BLOCK, 0.0, np.float32))
    lines = [line for line in capsys.readouterr().err.splitlines() if " wake " in line]
    assert len(lines) == 1 and "p=0.987" in lines[0] and "lag=0.20s" in lines[0]


def test_a_reset_empties_what_was_kept() -> None:
    listening = _listening()
    for i in range(30):
        listening._feed(np.full(BLOCK, 1.0, np.float32))
    listening._reset()
    assert len(listening._audio) == 0 and listening._first == 0 and listening._total == 0
    listening._feed(np.full(BLOCK, 2.0, np.float32))
    assert np.array_equal(listening._audio, np.full(BLOCK, 2.0, np.float32))
