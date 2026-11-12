"""REM5 (VIVO15, VIVOP1): the routine guide lets go of the person after a word refused, and the phrase of a routine
turned off says so instead of going to the model and opening the guide to create one (REM6, REV15 B-3: no longer;
it is the person's own words, test_mind_rem6)."""
from __future__ import annotations

from pathlib import Path

import pytest

from baxy_mind import routine_guide
from test_mind_routine_guide import _guide_mind

NIGHT = {"id": "r-000011", "name": "buenas noches", "trigger": {"phrase": "buenas noches"}, "active": True,
         "steps": [], "order": "baja el volumen a 10"}


def _refused_once() -> routine_guide.Guide:
    guide = routine_guide.Guide(lang="es", step="phrase", kind="word")
    said, _, ended = guide.answer("sí", [NIGHT], False, None)
    assert "ya es una orden mía" in said and not ended and guide.step == "phrase"
    return guide


# ---------------------------------------------------------------------------------------------------------------------
# The guide at «¿Qué palabra vas a decir?» lets go
# ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("said", ["Cuando te diga para, pausa la música.", "¿Qué rutinas tengo?",
                                  "pon una alarma para mañana a las siete y media", "sí"])
def test_after_a_word_refused_the_next_order_leaves_the_guide(said: str) -> None:
    assert _refused_once().leaves(said, [NIGHT])


@pytest.mark.parametrize("said", ["¿qué palabra puedo usar?", "Cuando te diga lectura, baja el volumen a 15.",
                                  "Cuando te diga para, pausa la música.", "¿Qué rutinas tengo?"])
def test_what_is_no_phrase_by_its_form_leaves_at_once(said: str) -> None:
    assert routine_guide.Guide(lang="es", step="phrase", kind="word").leaves(said, [NIGHT])


@pytest.mark.parametrize("said", ["modo lectura", "cine", "la palabra es lectura", "Baxy, modo cine", "cancela"])
def test_a_phrase_or_cancel_stays_in_the_guide(said: str) -> None:
    assert not _refused_once().leaves(said, [NIGHT])
    assert not routine_guide.Guide(lang="es", step="phrase", kind="word").leaves(said, [NIGHT])


def test_through_the_mind_the_order_after_a_refused_word_is_not_taken_for_a_word(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [], [NIGHT])
    refused = mind.decide(1, "Cuando te diga sí, abre la calculadora.")
    assert "ya es una orden mía" in refused["reply"]
    listed = mind.decide(2, "¿Qué rutinas tengo?")
    assert listed["kind"] == "action" and listed["arguments"] == {"action": "list"}


def test_through_the_mind_a_one_breath_routine_after_a_refused_word_is_read_as_one(tmp_path: Path) -> None:
    mind, server = _guide_mind(tmp_path, [], [NIGHT])
    mind.decide(1, "Cuando te diga sí, abre la calculadora.")
    again = mind.decide(2, "Cuando te diga lectura, baja el volumen a 15.")
    assert "muy largo" not in again["reply"] and "ya es una orden mía" not in again["reply"]
    assert "lectura" in again["reply"]


@pytest.mark.parametrize("said", ["Ponme una alarma a las siete de la mañana.", "sí", "gracias"])
def test_after_a_word_refused_in_one_breath_a_second_one_refused_leaves(tmp_path: Path, said: str) -> None:
    # The model's measure (held-out g-06, g-11): the word refused in a one-breath routine is its first answer refused.
    mind, server = _guide_mind(tmp_path, [{"choices": [{"message": {"role": "assistant", "content": "Vale."}}]}], [])
    mind.decide(1, "Baxy, cuando te diga no, pon el volumen en cero.")
    assert mind._guide is not None and mind._guide.leaves(said, [])

