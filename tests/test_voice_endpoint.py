"""When a request heard ends (src/baxy_mind/voice.py, Voice._over) and how the call is cut from its transcript
(Voice._transcribe): pinned as measured with the owner's voice in WakewordBaxy/probar_baxy.py and TranscripcionBaxy,
so a change to the endpointing is a decision and not an accident."""
import math
import queue
from types import SimpleNamespace

import numpy
import pytest

from baxy_mind import voice
from baxy_mind.early import EARLY_SILENCE_S
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
    listening._early_at = listening._early_heard = None
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
        self.result = SimpleNamespace(text="".join(tokens), tokens=tokens, timestamps=timestamps,
                                      ys_log_probs=[0.0] * len(tokens))

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
    assert listening._transcribe(numpy.full(BLOCK * 30, 0.1, numpy.float32), 2.0).text == "abre Steam."
    # a word that began within CALL_LEAD_S of the trigger is the request's
    listening._recognizer = _Recognizer([" Ba", "xi", " abre"], [1.2, 1.4, 2.0 - voice.CALL_LEAD_S])
    assert listening._transcribe(numpy.full(BLOCK * 30, 0.1, numpy.float32), 2.0).text == "abre"


def test_near_silence_is_never_transcribed() -> None:
    listening = object.__new__(Voice)
    listening._hotwords, listening._recognizer = "", None  # it would fail if it were asked
    assert listening._transcribe(numpy.full(RATE, 0.005, numpy.float32), None).text == ""


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


class _Said:
    """Ultra on the request window (it opens BEFORE_S before a trigger at 2.0 s into it): the (seconds, token) said up to
    where the audio it is given ends, each token as sure as ``sure`` says (1.0 when it does not name it)."""

    def __init__(self, *said: tuple[float, str], sure: dict[str, float] | None = None, probabilities: bool = True) -> None:
        self._said = said
        self._sure = sure or {}
        self._probabilities = probabilities  # False: Ultra gave none (Heard.words is empty)

    def create_stream(self) -> SimpleNamespace:
        stream = SimpleNamespace(result=None)
        stream.accept_waveform = lambda rate, audio: setattr(stream, "seconds", len(audio) / rate)
        return stream

    def decode_stream(self, stream: SimpleNamespace) -> None:
        said = [(at, token) for at, token in self._said if at < stream.seconds]
        stream.result = SimpleNamespace(text="".join(t for _, t in said), tokens=[t for _, t in said],
                                        timestamps=[at for at, _ in said],
                                        ys_log_probs=[math.log(self._sure.get(t, 1.0)) for _, t in said]
                                        if self._probabilities else [])


class _Still:
    """A detector or Silero that is only asked: the trigger is set by hand, and every block is speech (levels decide).
    As Silero, it keeps whether each block allowed its state to be reset (``settled``)."""

    def __init__(self) -> None:
        self.settled: list[bool] = []

    def accept(self, block: numpy.ndarray) -> list:
        return []

    def reset(self) -> None:
        pass

    def scores(self) -> list:
        return []

    def marks(self, block: numpy.ndarray, settle: bool = False) -> numpy.ndarray:
        self.settled.append(settle)
        return numpy.ones(len(block), bool)


def _ear(said: _Said, early: list | None = None) -> tuple[Voice, list[dict]]:
    """A voice in wake mode; with ``early``, palanca 2 on as the product runs it, its early transcripts kept there."""
    listening = object.__new__(Voice)
    listening._mode, listening._heard, listening._wake_log = "wake", 0, None
    listening._on_early = None if early is None else lambda seq, text: early.append(text)
    listening._early_s, listening._early_seq = EARLY_SILENCE_S, 0
    listening._detector = listening._vad = _Still()
    listening._wake_peak, listening._hotwords, listening._recognizer = voice.WAKE_TARGET, "", said
    listening._blocks = queue.Queue()
    listening.speech = SimpleNamespace(speaking=False)
    told: list[dict] = []
    listening._write = told.append
    listening._reset()
    return listening, told


def _say(listening: Voice, told: list[dict], *pieces: tuple[float, float], trigger_after: int) -> list[float]:
    """Each (seconds, level) heard block by block, every job run as Voice._listen runs it; the trigger is set when the
    piece numbered ``trigger_after`` has been heard. When (seconds heard) each transcript was told."""
    told_at: list[float] = []
    for index, (seconds, level) in enumerate(pieces):
        for _ in range(round(seconds * RATE / BLOCK)):
            job = listening._feed(numpy.full(BLOCK, level, numpy.float32))
            if job is not None:
                audio, wake_at, then = job
                before = len(told)
                then(listening._transcribe(audio, wake_at))
                if any(m.get("type") == "voice.transcript" for m in told[before:]):
                    told_at.append(listening._total / RATE)
        if index == trigger_after:
            listening._start = listening._total / RATE
    return told_at


@pytest.mark.parametrize("early", [None, []])
def test_a_short_request_said_in_one_breath_after_baxy_is_heard(early: list | None) -> None:
    # VOZ1: «Baxi, gracias» with no pause (DEP6, 2026-11-09): the causal detector fires as the word ends, so all of
    # «gracias» falls in the first WORD_TAIL_S after the trigger and the request was closed with nothing transcribed.
    # The trigger is at 3.0 s, so the request window opens at 1.0 s: «Baxi» 0.5-1.0 s before it, «gracias» right after.
    listening, told = _ear(_Said((1.5, " Ba"), (1.7, "xi"), (1.9, ","), (2.0, " gra"), (2.15, "cias"), (2.3, ".")),
                           early)
    told_at = _say(listening, told, (2.5, QUIET), (0.5, LOUD), (0.3, LOUD), (3.0, QUIET), trigger_after=1)
    assert [m["text"] for m in told if m.get("type") == "voice.transcript"] == ["gracias."]
    # told after the long silence (words only in the call's tail may be the end of «Baxy» misheard), before NO_COMMAND_S
    assert voice.END_SLOW_S <= told_at[0] - 3.3 <= voice.END_SLOW_S + 0.2 < voice.NO_COMMAND_S
    if early is not None:  # the mind could decide on it early, as on any request
        assert early == ["gracias."]


def test_baxy_alone_still_waits_for_the_request_after_a_pause() -> None:
    # the end of «Baxi» heard after the trigger, a pause, then the request: the pause does not end it, and the call is
    # never the request
    listening, told = _ear(_Said((1.5, " Ba"), (1.7, "xi"), (3.2, " abre"), (3.5, " Ste"), (3.7, "am"), (3.9, ".")))
    _say(listening, told, (2.5, QUIET), (0.5, LOUD), (0.2, LOUD), (1.0, QUIET), (0.8, LOUD), (2.0, QUIET), trigger_after=1)
    assert [m["text"] for m in told if m.get("type") == "voice.transcript"] == ["abre Steam."]


def test_the_end_of_baxy_misheard_as_a_word_does_not_end_the_request_before_its_words() -> None:
    # VOZ1, the owner's real calls with a pause after «Baxi»: Ultra heard its last syllable as a word that began at the
    # trigger («see.», «seat.»); with the usual 0.8-0.9 s the request ended on it and the words said after the pause
    # (0.5-1.9 s) were lost, or came as a second request after a second «Baxi».
    said = _Said((1.5, " Ba"), (1.7, "ck"), (2.0, " see"), (2.1, "."), (3.6, " abre"), (3.9, " Ste"), (4.1, "am"),
                 (4.3, "."))
    listening, told = _ear(said)
    _say(listening, told, (2.5, QUIET), (0.5, LOUD), (0.1, LOUD), (1.4, QUIET), (0.8, LOUD), (2.5, QUIET),
         trigger_after=1)
    heard = [m["text"] for m in told if m.get("type") == "voice.transcript"]
    assert len(heard) == 1 and heard[0].endswith("abre Steam.")


@pytest.mark.parametrize("probabilities", [True, False])
def test_a_word_in_the_call_s_tail_the_ear_is_unsure_of_is_the_end_of_baxy(probabilities: bool) -> None:
    # VOZ1: on the owner's real calls the misheard last syllable of «Baxi» was unsure (0.33-0.50), a request said in one
    # breath sure (0.54 and over, 36 decoded in two voices): an unsure word alone in the tail is no request, and after a
    # pause of more than END_SLOW_S the words said then are the request, as before; a word Ultra gave no probability
    # for is not known to be sure
    said = _Said((1.5, " Ba"), (1.7, "ck"), (2.0, " see"), (2.1, "."), (4.9, " abre"), (5.2, " Ste"), (5.4, "am"),
                 (5.6, "."), sure={" see": voice.UNSURE_P - 0.1 if probabilities else 1.0}, probabilities=probabilities)
    listening, told = _ear(said)
    _say(listening, told, (2.5, QUIET), (0.5, LOUD), (0.1, LOUD), (2.7, QUIET), (0.8, LOUD), (2.5, QUIET),
         trigger_after=1)
    assert [m["text"] for m in told if m.get("type") == "voice.transcript"] == ["see. abre Steam."]


def test_silero_is_reset_only_while_no_request_is_open() -> None:
    # VOZ1: a reset in a 0.7 s pause inside a request heard the owner's soft words after it too late, and the request was
    # cut; Pipecat resets once the user is quiet, its turn over
    listening, told = _ear(_Said((1.5, " Ba"), (1.7, "xi"), (2.1, " abre"), (2.4, " Ste"), (2.6, "am"), (2.8, ".")))
    _say(listening, told, (2.5, QUIET), (0.5, LOUD), (1.0, LOUD), (3.0, QUIET), trigger_after=1)
    settled = listening._vad.settled
    request = range(30, 30 + 10 + round((voice.END_SILENCE_S + 0.1) * RATE / BLOCK) - 1)  # trigger to close
    assert all(settled[:30]) and not any(settled[i] for i in request) and settled[-1]
    assert [m["text"] for m in told if m.get("type") == "voice.transcript"] == ["abre Steam."]


@pytest.mark.parametrize(("heard", "asked"), [
    ("Baxi.", ""), ("Paksi.", ""), ("Baxy, Baxi", ""), ("Baxi, abre la calculadora.", "abre la calculadora."),
    ("Maxi, prepárate para mañana.", "prepárate para mañana."), ("¿Baxi? sube el volumen", "sube el volumen"),
    ("abre el taxi de la app", "abre el taxi de la app"), ("Pásame la sal", "Pásame la sal"),
    ("Hola, ¿qué hora es?", "Hola, ¿qué hora es?")])
def test_the_call_is_never_part_of_the_request(heard: str, asked: str) -> None:
    assert voice.without_call(heard) == asked
