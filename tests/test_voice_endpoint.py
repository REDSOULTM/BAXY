"""When a request heard ends (src/baxy_mind/voice.py, Voice._over) and how the call is cut from its transcript
(Voice._transcribe): pinned as measured with the owner's voice in WakewordBaxy/probar_baxy.py and TranscripcionBaxy,
so a change to the endpointing is a decision and not an accident."""
from types import SimpleNamespace

import numpy
import pytest

from baxy_mind import voice
from baxy_mind.voice import BLOCK, RATE, Voice

LOUD, QUIET = 0.05, 0.002  # above and below VOICE_RMS (0.012)


def _heard(mode: str, *pieces: tuple[float, float]) -> Voice:
    """A voice in `mode` whose request opened at 0 s and has heard each (seconds, level) in order."""
    listening = object.__new__(Voice)
    listening._mode, listening._released, listening._first = mode, False, 0
    listening._audio = numpy.concatenate([numpy.full(int(s * RATE), level, numpy.float32) for s, level in pieces])
    listening._total = len(listening._audio)
    return listening


@pytest.mark.parametrize("mode", ["wake", "direct"])
def test_a_request_ends_after_the_silence_that_follows_its_last_voice(mode: str) -> None:
    assert not _heard(mode, (1.5, LOUD), (voice.END_SILENCE_S - 0.1, QUIET))._over(0.0)
    assert _heard(mode, (1.5, LOUD), (voice.END_SILENCE_S, QUIET))._over(0.0)


def test_a_pause_shorter_than_the_silence_does_not_end_it() -> None:
    assert not _heard("wake", (1.0, LOUD), (0.6, QUIET), (0.5, LOUD), (0.6, QUIET))._over(0.0)


def test_the_end_of_baxy_after_the_trigger_is_not_the_request() -> None:
    # voice only in the first WORD_TAIL_S: no request began, so it waits NO_COMMAND_S for one
    assert not _heard("wake", (voice.WORD_TAIL_S, LOUD), (2.0, QUIET))._over(0.0)
    assert _heard("wake", (voice.WORD_TAIL_S, LOUD), (voice.NO_COMMAND_S - voice.WORD_TAIL_S, QUIET))._over(0.0)


def test_a_direct_request_waits_longer_for_its_first_word() -> None:
    assert not _heard("direct", (voice.NO_COMMAND_S + 0.5, QUIET))._over(0.0)
    assert _heard("direct", (voice.DIRECT_WAIT_S, QUIET))._over(0.0)


def test_a_request_that_never_goes_quiet_ends_at_its_cap_and_a_release_ends_it_at_once() -> None:
    assert _heard("wake", (voice.MAX_S, LOUD))._over(0.0)
    held = _heard("direct", (0.5, LOUD))
    assert not held._over(0.0)
    held._released = True
    assert held._over(0.0)


class _Recognizer:
    def __init__(self, tokens: list[str], timestamps: list[float]) -> None:
        self.result = SimpleNamespace(text="".join(tokens), tokens=tokens, timestamps=timestamps)

    def create_stream(self) -> SimpleNamespace:
        return SimpleNamespace(accept_waveform=lambda rate, audio: None, result=self.result)

    def decode_stream(self, stream: SimpleNamespace) -> None:
        pass


def test_the_call_and_what_came_before_it_are_cut_by_time() -> None:
    listening = object.__new__(Voice)
    listening._hotwords = ""
    # «Hola. Baxi, abre Steam.» with the trigger at 2.0 s: «Baxi» began 0.6 s before it
    listening._recognizer = _Recognizer([" Hola", ".", " Ba", "xi", ",", " abre", " Ste", "am", "."],
                                        [0.3, 0.6, 1.4, 1.6, 1.8, 2.1, 2.4, 2.5, 2.7])
    assert listening._transcribe(numpy.full(BLOCK * 30, 0.1, numpy.float32), 2.0) == "abre Steam."
    # a word that began within CALL_LEAD_S of the trigger is the request's
    listening._recognizer = _Recognizer([" Ba", "xi", " abre"], [1.2, 1.4, 2.0 - voice.CALL_LEAD_S])
    assert listening._transcribe(numpy.full(BLOCK * 30, 0.1, numpy.float32), 2.0) == "abre"


def test_near_silence_is_never_transcribed() -> None:
    listening = object.__new__(Voice)
    listening._hotwords, listening._recognizer = "", None  # it would fail if it were asked
    assert listening._transcribe(numpy.full(RATE, 0.005, numpy.float32), None) == ""


@pytest.mark.parametrize("voiced_blocks", range(1, 61))
def test_the_silence_is_counted_exactly_whatever_the_request_s_length(voiced_blocks: int) -> None:
    # in direct mode 48 of 120 lengths waited one block more: 2.4 - 1.5 is 0.8999… in floating point
    silent_blocks = round(voice.END_SILENCE_S * RATE / BLOCK)
    heard = _heard("direct", (voiced_blocks * BLOCK / RATE, LOUD), (silent_blocks * BLOCK / RATE, QUIET))
    heard._audio = numpy.concatenate([numpy.full(voiced_blocks * BLOCK, LOUD, numpy.float32),
                                   numpy.full(silent_blocks * BLOCK, QUIET, numpy.float32)])
    heard._total = len(heard._audio)
    assert heard._over(0.0)
