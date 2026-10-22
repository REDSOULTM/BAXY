"""BAXY Renew al máximo, velocidad (2026-10-22): the overhead BAXY adds to the model's own time, lever by lever."""
import json
import time
import types
from pathlib import Path

import pytest

from test_mind_final import _mind, _say


def _clock(step: float) -> types.SimpleNamespace:
    """A time module whose perf_counter moves `step` seconds per reading (the others are the real ones)."""
    ticks = iter(range(10_000))
    return types.SimpleNamespace(perf_counter=lambda: 100.0 + step * next(ticks), monotonic=time.monotonic,
                                 time=time.time, sleep=time.sleep)


# --- V4: the trace's times come from a clock that resolves them --------------------------------------------------------

def test_a_turns_time_in_the_trace_is_read_on_the_fine_clock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # On Windows, Python 3.12's monotonic clock moves in steps of ~15.6 ms: every ms of the trace was a multiple of it.
    from baxy_mind import mind as mind_module
    monkeypatch.setattr(mind_module, "time", _clock(0.0123))
    mind, _ = _mind(tmp_path, [_say("Hola.")])
    mind.decide(1, "hola")
    row = json.loads((tmp_path / "turns.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert row["stage"] == "turn.decide" and row["ms"] == 12


def test_the_voices_times_are_read_on_the_same_fine_clock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # voice.speak's row (__main__.spoken) subtracts the voice's times from the mind's clock: both are perf_counter.
    import numpy as np
    from baxy_mind import voice_output
    from test_voice_output import _FakeStream, _player
    monkeypatch.setattr(voice_output, "time", _clock(0.0))
    told: list[tuple] = []
    speech = _player(tmp_path, monkeypatch, [], _FakeStream())
    speech._on_spoken = lambda queued, sounded, notice: told.append((queued, sounded))
    speech._play(iter([np.full(10, 0.1, np.float32)]), speech._generation, 100.0)
    assert told == [(100.0, 100.0 + _FakeStream.latency)]  # the first sound
    stamps: list[float] = []
    speech._sentences = lambda text: iter([text])  # type: ignore[method-assign]
    speech._play = lambda audio, generation, stamp, *rest: stamps.append(stamp)  # type: ignore[method-assign]
    assert speech.speak("Hola.")
    deadline = time.monotonic() + 5
    while not stamps and time.monotonic() < deadline:
        time.sleep(0.01)
    assert stamps == [100.0]  # when the answer was given
