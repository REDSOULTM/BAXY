"""DIAX1 (the owner's F4, 16-11-2026, 1.5.4): «cuando te diga X quiero que …» said in one breath with no comma after the
word is still a routine of a word by its form (routine_guide._one_breath matched «cuando te diga»), and the order is the
person's own words after the word the model reads: before, the guide began with no kind, the 4B read a word that can
also name a time as «time» (k time, h 7 copied from an example) and BAXY asked «¿A qué hora, y qué días?»; told it was
at no hour, only at their word, it had lost the order said first and asked it («¿Qué quieres que haga cuando la
digas?»), and being told it was said already got the same question again. The phrases here are made up, of the same
form as theirs."""
from __future__ import annotations

from pathlib import Path

import pytest

from baxy_mind import routine_guide
from baxy_mind.routine_fill import Read
from test_mind_routine_guide import _guide_mind
from test_mind_rut14_rutinas import _reading

SAID = ("cuando te diga tarde quiero que pulses la tecla de silencio del teclado que es la que apaga o enciende los "
        "altavoces.")
ORDER = "quiero que pulses la tecla de silencio del teclado que es la que apaga o enciende los altavoces"
NOT_AT_A_TIME = "No, a ninguna hora fija ni en ningún día, nada más cuando te diga tarde."
# What the 4B wrote for each, with the 1.5.5 (tmp\DIAX1, seed 0): the first, the example's hour; the second, the order in
# its own words («pulsa» for their «quiero que pulses»), which the check of their words refuses.
AS_A_TIME = {"k": "time", "h": "7", "x": "answer"}
AS_A_WORD = {"k": "word", "p": "tarde", "t": "pulsa la tecla de silencio del teclado", "x": "answer"}
CONFIRM = f"Cuando digas «tarde»: «{ORDER}». ¿La guardo?"


def test_the_form_says_a_word_routine_so_a_time_the_model_read_is_not_asked(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [])
    _reading(server, [AS_A_TIME])
    asked = mind.decide(1, SAID)
    assert asked["kind"] == "conversation" and "hora" not in asked["reply"]
    assert mind._guide.kind == "word" and mind._guide.step == "phrase"


def test_the_order_said_first_is_kept_when_the_word_comes_after(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [])
    _reading(server, [AS_A_TIME, AS_A_WORD])
    mind.decide(1, SAID)
    told = mind.decide(2, NOT_AT_A_TIME)
    assert told["kind"] == "conversation" and told["reply"] == CONFIRM


def test_the_word_read_whole_splits_the_order_as_said_and_only_their_si_saves(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [])
    _reading(server, [AS_A_WORD])
    assert mind.decide(1, SAID)["reply"] == CONFIRM
    saved = mind.decide(2, "sí")
    assert saved["kind"] == "action" and saved["operation"] == "baxy.routines"
    assert saved["arguments"] == {"action": "create", "phrase": "tarde", "order": ORDER}


@pytest.mark.parametrize(("said", "word", "order"), [
    ("cada vez que te diga hora de cenar pon la radio", "hora de cenar", "pon la radio"),
    ("Cuando yo te diga mañana baja el volumen al veinte.", "mañana", "baja el volumen al veinte"),
])
def test_a_word_the_model_reads_at_the_start_leaves_the_rest_as_the_order(tmp_path: Path, said: str, word: str,
                                                                         order: str) -> None:
    mind, server = _guide_mind(tmp_path, [])
    _reading(server, [{"k": "time", "p": word, "x": "answer"}])
    assert mind.decide(1, said)["reply"] == f"Cuando digas «{word}»: «{order}». ¿La guardo?"


def test_a_word_that_is_not_where_their_words_begin_takes_no_order_by_form(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [])
    _reading(server, [{"k": "word", "p": "cine", "x": "answer"}])
    mind.decide(1, "cuando te diga que nos vamos al cine apaga la luz")
    assert mind._guide.phrase == "cine" and mind._guide.order == "" and mind._guide.step == "order"


def test_a_time_said_still_turns_it_into_a_routine_at_that_time() -> None:
    guide = routine_guide.heard(SAID).guide
    assert guide.kind == "word" and guide.after.startswith("tarde quiero")
    when = routine_guide.spoken("todos los días a las 8 de la mañana")
    guide.fill(Read(kind="time", when=when, text="haz eso"))
    assert guide.kind == "time"


def test_after_a_question_of_baxy_the_models_call_opens_the_guide_as_the_form_reads_it(tmp_path: Path) -> None:
    # After BAXY's own question the one-breath form is not taken by itself (it may be its answer): the model decides,
    # and when it calls baxy_routines the guide it opens reads the words by their form all the same (DIAX1, F4 with
    # history: «¿Qué quieres que haga cuando la digas?» with the order lost, as before the fix).
    from test_mind_final import _call, _say
    mind, server = _guide_mind(tmp_path, [_say("Suena una canción tranquila. ¿Quieres algo más?"), _call("baxy_routines", {})])
    _reading(server, [AS_A_TIME])
    mind.decide(1, "¿qué canción está sonando?")
    asked = mind.decide(2, SAID)
    assert mind._guide is not None and mind._guide.kind == "word" and "hora" not in asked["reply"]


@pytest.mark.parametrize("said", ["Eh cuando te diga medianoche, pausa la música.", "Bueno cuando te diga café, pausa la música",
                                  "eh, mm cuando te diga café, pausa la música"])
def test_fillers_in_front_are_no_other_request(tmp_path: Path, said: str) -> None:
    # DIAX1 held-out (hb05, ha02): «Eh cuando te diga…» with no comma after the filler went to the model, which set an
    # alarm nobody asked for («He configurado una alarma para que a medianoche se pause la música») or kept nothing.
    mind, server = _guide_mind(tmp_path, [])
    asked = mind.decide(1, said)
    assert asked["kind"] == "conversation" and asked["reply"].endswith("¿La guardo?") and server.bodies == []
