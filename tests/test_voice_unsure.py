"""How sure the ear was (feria 2026-10-27, cases 11 and 12): in the noise a short greeting came out as a word nobody
said, and a phrase cut into syllables reached the mind one piece at a time. Parakeet's per-token probabilities
(ys_log_probs) become voice.Heard: the words the ear is not sure of reach the model as a fact beside the person's words
(Mind.decide), and the model decides whether to ask for them again. Nothing is dropped by them (voice.UNSURE_P)."""
import math
import threading
from pathlib import Path
from types import SimpleNamespace

import numpy

from baxy_mind import voice
from baxy_mind.early import Anticipation
from baxy_mind.mind import BEAT_SYSTEM, SYSTEM, UNSURE_NOTE
from baxy_mind.voice import BLOCK, Heard, Voice
from test_mind_final import _call, _mind, _say

SURE, UNSURE, MIDDLE = math.log(0.97), math.log(voice.UNSURE_P / 4), math.log(voice.UNSURE_P / 2)


def test_each_word_is_as_sure_as_its_least_sure_token_and_punctuation_does_not_count() -> None:
    heard = Heard.of("Abre Spotify.", [" Abre", " Spo", "tify", "."], [SURE, SURE, MIDDLE, UNSURE])
    assert [word for word, _ in heard.words] == ["Abre", "Spotify."]
    assert heard.words[1][1] == math.exp(MIDDLE)
    assert heard.unsure() == [("Spotify.", math.exp(MIDDLE))]


def test_without_probabilities_for_its_tokens_nothing_is_said_of_a_transcript() -> None:
    assert Heard.of("abre Steam", [], []).words == ()
    assert Heard.of("abre Steam", [" abre", " Steam"], [SURE]).words == ()


def test_the_call_leaves_with_its_words() -> None:
    heard = Heard.of("Baxi, abre Steam.", [" Baxi", ",", " abre", " Ste", "am", "."],
                     [UNSURE, SURE, SURE, MIDDLE, SURE, SURE]).without_call()
    assert heard.text == "abre Steam." and heard.unsure() == [("Steam.", math.exp(MIDDLE))]
    assert Heard.of("Baxi.", [" Baxi", "."], [UNSURE, SURE]).without_call() == Heard("")
    glued = Heard.of("Baxi,abre Steam.", [" Baxi", ",", "abre", " Steam", "."], [UNSURE, SURE, SURE, SURE, SURE])
    assert glued.without_call() == Heard("abre Steam.")  # its words no longer match the text: nothing is said


class _Recognizer:
    def __init__(self, tokens: list[str], timestamps: list[float], log_probs: list[float]) -> None:
        self.result = SimpleNamespace(text="".join(tokens), tokens=tokens, timestamps=timestamps,
                                      ys_log_probs=log_probs)

    def create_stream(self) -> SimpleNamespace:
        return SimpleNamespace(accept_waveform=lambda rate, audio: None, result=self.result)

    def decode_stream(self, stream: SimpleNamespace) -> None:
        pass


def test_the_words_cut_with_the_call_take_their_probabilities_with_them() -> None:
    listening = object.__new__(Voice)
    listening._hotwords = ""
    listening._recognizer = _Recognizer([" Ba", "xi", ",", " o", "la", "."], [1.4, 1.6, 1.8, 2.1, 2.3, 2.4],
                                        [UNSURE, UNSURE, SURE, MIDDLE, SURE, SURE])
    heard = listening._transcribe(numpy.full(BLOCK * 30, 0.1, numpy.float32), 2.0)
    assert heard == Heard("ola.", (("ola.", math.exp(MIDDLE)),))


def test_a_request_without_the_call_keeps_its_probabilities_too() -> None:
    listening = object.__new__(Voice)
    listening._hotwords = ""
    listening._recognizer = _Recognizer([" Vo", "le", "."], [0.1, 0.3, 0.4], [MIDDLE, SURE, SURE])
    heard = listening._transcribe(numpy.full(BLOCK * 30, 0.1, numpy.float32), None)
    assert heard == Heard("Vole.", (("Vole.", math.exp(MIDDLE)),))


def _finished(heard: Heard) -> tuple[Voice, list[dict]]:
    """A wake request that ended, decoded as ``heard``; what the voice wrote."""
    written: list[dict] = []
    listening = object.__new__(Voice)
    listening._write, listening._mode, listening._released, listening._first = written.append, "wake", False, 0
    listening._audio = numpy.full(int(2.5 * voice.RATE), 0.05, numpy.float32)
    listening._speech = numpy.ones(len(listening._audio), bool)
    listening._total, listening._start, listening._early_at = len(listening._audio), 0.0, None
    listening._lock, listening._told = threading.Lock(), Heard("")
    listening._event = listening._state = lambda *a: None
    _, _, then = listening._finish(0.0)
    then(heard)
    return listening, written


def test_an_unsure_transcript_is_told_as_any_other_and_the_mind_takes_its_doubts_once_for_those_words() -> None:
    misheard = Heard.of("Vole, ¿qué tal?", [" Vo", "le", ",", " ¿", "qué", " tal", "?"],
                        [MIDDLE, SURE, SURE, SURE, SURE, SURE, SURE])
    listening, written = _finished(misheard)
    assert written == [{"type": "voice.transcript", "text": "Vole, ¿qué tal?"}]
    assert listening.unsure("otra cosa escrita") == []  # typed words are not what was heard
    listening, _ = _finished(misheard)
    assert listening.unsure("Vole, ¿qué tal?") == [("Vole,", math.exp(MIDDLE))]
    assert listening.unsure("Vole, ¿qué tal?") == []
    listening, _ = _finished(misheard)
    assert listening.unsure("otra cosa escrita") == [] and listening.unsure("Vole, ¿qué tal?") == []  # taken once
    listening, written = _finished(Heard.of("Lu.", [" Lu", "."], [UNSURE, SURE]))
    assert written == [{"type": "voice.transcript", "text": "Lu."}]  # however unsure, the model reads it
    listening, _ = _finished(Heard.of("Cinco.", [" Cinco", "."], [SURE, SURE]))
    assert listening.unsure("Cinco.") == []


def test_the_model_reads_the_unsure_words_beside_the_clock_and_never_in_the_persons_message(tmp_path: Path) -> None:
    mind, server = _mind(tmp_path, [_say("¿Me lo repites? No te escuché bien."), _say("Hola.")])
    mind.decide(1, "Vole.", None, [("Vole.", 0.31)])
    messages = server.bodies[0]["messages"]
    note = UNSURE_NOTE.format(words="«Vole.» (31 %)")
    assert messages[-1] == {"role": "user", "content": "Vole."}
    assert messages[-2]["content"].endswith("\n" + note)
    mind.decide(2, "Hola.")
    assert all(note not in str(m.get("content")) for m in server.bodies[1]["messages"][-2:])



def test_the_rules_say_what_the_ears_doubts_and_words_that_make_no_sense_ask_for() -> None:
    """P1.4 (noche 2026-10-27): with the note beside the clock the model still answered as said (0/10 in decision): rule
    6 only told it to guess the word a transcript sounds like, and rule 4 to say it does not do what no tool does. The
    rule now says what the note is for and what to do when the words sound like nothing: ask, in its own words, to hear
    them again. Nothing decides for it."""
    rule = SYSTEM[SYSTEM.index("\n6. "):SYSTEM.index("\n7. ")]
    assert "«sincuenta» es 50" in rule
    assert "el oído no está seguro" in UNSURE_NOTE and "el oído no está seguro" in rule
    assert "repita" in rule
    assert "«sincuenta» es 50" in BEAT_SYSTEM and "repita" not in BEAT_SYSTEM  # in the heartbeat nobody spoke

def test_an_answer_to_the_models_question_carries_its_unsure_words(tmp_path: Path) -> None:
    mind, server = _mind(tmp_path, [_call("ask_user", {"question": "¿A qué nivel?"}), _say("Listo.")])
    mind.decide(1, "pon el volumen")
    mind.decide(2, "Treinta.", None, [("Treinta.", 0.4)])
    assert server.bodies[1]["messages"][-1]["content"].endswith(UNSURE_NOTE.format(words="«Treinta.» (40 %)"))


def test_an_early_decision_did_not_read_the_unsure_words_so_it_is_not_used() -> None:
    put_back: list[str] = []
    anticipation = object.__new__(Anticipation)
    anticipation.mind = SimpleNamespace(_clock_time=lambda: "minute")
    anticipation._held = {"text": "Vole.", "clock": "minute"}
    anticipation._back = lambda held, reason, reread=True: put_back.append(reason)
    assert anticipation.settle("turn.decide", {"type": "turn.decide", "text": "Vole."}, 0.0, [("Vole.", 0.3)]) is None
    assert put_back == ["unsure"]


def test_a_direct_request_told_from_its_early_transcript_keeps_that_transcripts_doubts() -> None:
    written: list[dict] = []
    listening = object.__new__(Voice)
    listening._write, listening._mode, listening._resume, listening._released, listening._first = (
        written.append, "direct", "off", False, 0)
    listening._audio = numpy.concatenate([numpy.full(voice.RATE, 0.05, numpy.float32),
                                          numpy.zeros(voice.RATE, numpy.float32)])
    listening._speech = numpy.concatenate([numpy.ones(voice.RATE, bool), numpy.zeros(voice.RATE, bool)])
    listening._total, listening._start = len(listening._audio), 0.0
    listening._lock, listening._told = threading.Lock(), Heard("")
    listening._event = listening._state = listening._close = listening._reset = lambda *a: None
    listening._early_at = listening._voice_end(0.0)
    listening._early_heard = Heard.of("Baxi, abre Steam.", [" Baxi", ",", " abre", " Ste", "am", "."],
                                      [UNSURE, SURE, SURE, MIDDLE, SURE, SURE])
    _, _, then = listening._finish(0.0)
    then(Heard(""))  # nothing decoded again: the early transcript is the request's
    assert written == [{"type": "voice.transcript", "text": "abre Steam."}]
    assert listening.unsure("abre Steam.") == [("Steam.", math.exp(MIDDLE))]
