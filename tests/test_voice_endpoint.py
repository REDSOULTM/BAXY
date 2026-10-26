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
    """A voice in `mode` whose request opened at 0 s and has heard each (seconds, level) in order, all of it heard as
    speech by Silero: here the levels decide."""
    listening = object.__new__(Voice)
    listening._mode, listening._released, listening._first = mode, False, 0
    listening._audio = numpy.concatenate([numpy.full(int(s * RATE), level, numpy.float32) for s, level in pieces])
    listening._speech = numpy.ones(len(listening._audio), bool)
    listening._total = len(listening._audio)
    return listening


@pytest.mark.parametrize("mode", ["wake", "direct"])
def test_a_request_ends_after_the_silence_that_follows_its_last_voice(mode: str) -> None:
    assert not _heard(mode, (1.5, LOUD), (voice.END_SILENCE_S - 0.1, QUIET))._over(0.0)
    assert _heard(mode, (1.5, LOUD), (voice.END_SILENCE_S, QUIET))._over(0.0)


def test_a_pause_shorter_than_the_silence_does_not_end_it() -> None:
    assert not _heard("wake", (1.0, LOUD), (0.6, QUIET), (0.5, LOUD), (0.6, QUIET))._over(0.0)


@pytest.mark.parametrize("mode", ["wake", "direct"])
def test_under_steady_noise_a_request_ends_after_the_silence_that_follows_its_last_speech(mode: str) -> None:
    # the noise stays loud (above VOICE_RMS) all along; Silero heard speech only in the first 1.5 s
    def noisy(silence_s: float) -> Voice:
        heard = _heard(mode, (1.5 + silence_s, LOUD))
        heard._speech[int(1.5 * RATE):] = False
        return heard

    assert not noisy(voice.END_SILENCE_S - 0.1)._over(0.0)
    assert noisy(voice.END_SILENCE_S)._over(0.0)


def _called(room: float, *pieces: tuple[float, float, bool]) -> Voice:
    """«Baxy» heard after 3 s of a room at level ``room`` (no speech in it) and then each (seconds, level, speech) from
    the trigger, at 3 s."""
    heard = _heard("wake", (3.0, room), *[(s, level) for s, level, _ in pieces])
    heard._speech[:3 * RATE] = False
    at = 3 * RATE
    for s, _, speech in pieces:
        heard._speech[at:at + int(s * RATE)] = speech
        at += int(s * RATE)
    return heard


def test_in_a_loud_room_silero_s_hold_of_baxy_is_not_the_request() -> None:
    # Silero holds «Baxy» 0.7 s past the trigger in the noise; a pause of 0.9 s after that is not the end of a request
    pause = ((0.7, LOUD, True), (voice.END_SILENCE_S, LOUD, False))
    assert not _called(LOUD, *pause)._over(3.0)
    assert not _called(LOUD, *pause, (1.0, LOUD, True), (voice.END_SILENCE_S - 0.1, LOUD, False))._over(3.0)
    assert _called(LOUD, *pause, (1.0, LOUD, True), (voice.END_SILENCE_S, LOUD, False))._over(3.0)


def test_in_a_quiet_room_a_short_request_right_after_baxy_still_ends_after_its_silence() -> None:
    # «Baxy, sí»: the word ends 0.7 s after the trigger
    assert _called(QUIET, (0.7, LOUD, True), (voice.END_SILENCE_S, QUIET, False))._over(3.0)


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
    heard._speech = numpy.ones(len(heard._audio), bool)
    heard._total = len(heard._audio)
    assert heard._over(0.0)


@pytest.mark.parametrize("mode", ["wake", "direct"])
def test_speech_far_under_the_speaker_does_not_keep_the_request_open(mode: str) -> None:
    # a TV or people talking behind: speech to Silero, loud to VOICE_RMS, but more than SPEAKER_DB under the speaker
    near = 0.2
    behind = near * 10 ** (-(voice.SPEAKER_DB + 3) / 20)
    assert behind >= voice.VOICE_RMS
    assert _heard(mode, (1.5, near), (voice.END_SILENCE_S, behind))._over(0.0)
    assert not _heard(mode, (1.5, near), (voice.END_SILENCE_S, near * 10 ** (-(voice.SPEAKER_DB - 3) / 20)))._over(0.0)


@pytest.mark.parametrize("mode", ["wake", "direct"])
def test_a_soft_speaker_under_voice_rms_is_heard_to_the_end(mode: str) -> None:
    soft = voice.VOICE_RMS / 2
    assert not _heard(mode, (1.5, soft), (voice.END_SILENCE_S - 0.1, QUIET))._over(0.0)
    assert _heard(mode, (1.5, soft), (voice.END_SILENCE_S, QUIET))._over(0.0)


def test_a_request_with_no_voice_after_the_call_is_not_transcribed() -> None:
    # «Baxy» alone (a false wake in noise): only the end of the word after the trigger, then the room
    heard = _heard("wake", (voice.WORD_TAIL_S, LOUD), (voice.NO_COMMAND_S, QUIET))
    heard._start, heard._early_at = 0.0, None
    heard._event = lambda name: None
    audio, _, _ = heard._finish(0.0)
    assert len(audio) == 0
    spoken = _heard("wake", (1.5, LOUD), (voice.END_SILENCE_S, QUIET))
    spoken._start, spoken._early_at = 0.0, None
    spoken._event = lambda name: None
    assert len(spoken._finish(0.0)[0]) == len(spoken._audio)


@pytest.mark.parametrize(("heard", "asked"), [
    ("Baxi.", ""), ("Paksi.", ""), ("Baxy, Baxi", ""), ("Baxi, abre la calculadora.", "abre la calculadora."),
    ("Maxi, prepárate para mañana.", "prepárate para mañana."), ("¿Baxi? sube el volumen", "sube el volumen"),
    ("abre el taxi de la app", "abre el taxi de la app"), ("Pásame la sal", "Pásame la sal"),
    ("Hola, ¿qué hora es?", "Hola, ¿qué hora es?")])
def test_the_call_is_never_part_of_the_request(heard: str, asked: str) -> None:
    assert voice.without_call(heard) == asked
