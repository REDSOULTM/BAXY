"""Revisión 1 de r24b (B3, banco r23 x7): una llegada que sólo probó un campo enfocado (átomo focus:) es prueba débil
también para el libro de actos y lugares. «en Spotify andá a search» con un clic en «Buscar» que llevó el foco de un
botón a un campo: el borrador «Ya estamos en la pestaña de búsqueda» cae (search_told_as_place) y la plantilla dice que
se abrió la búsqueda y en qué campo está el cursor. Cada regla con su contracaso: la plantilla pasa, «abrí la búsqueda»
dice lo mismo que ella, y la misma frase sobre una llegada fuerte (control:…:current) sigue publicándose."""

from __future__ import annotations

import json

import pytest

from baxy_mind import cu_finals
from baxy_mind.visible_defect import compose_visible_defect
from baxy_mind import computer_use_finals
from baxy_mind.semantic import claims


def _mission(observed: dict) -> dict:
    return {
        "kind": "operation", "operation": "mission.computer.use", "polarity": "success",
        "verified": True, "succeeded": True, "observed": observed,
    }


def _facts(situation: dict) -> dict:
    return {"situation": json.dumps(situation, ensure_ascii=False)}


def _search(satisfied_by: str, focused: str | None = "¿Qué quieres reproducir?") -> dict:
    observed = {
        "goal": "ir a search", "application": "Spotify", "reached": True, "satisfiedBy": satisfied_by,
        "successCheck": satisfied_by,
        "steps": [{"step": 1, "operation": "input.visible.click", "label": "Buscar", "ok": True, "name": "Buscar",
                   "kind": "Button", "changed": True, "surfaceChanged": True}],
        "window": {"title": "Spotify Premium", "process": "Spotify"},
        "screen": {"title": "Spotify Premium", "values": [{"name": "Inicio", "state": ""}]},
    }
    if focused:
        observed["focusedField"] = focused
    return observed


X7 = _search("focus:search")
STRONG = _search("control:buscar:current", focused=None)

DRAFTS = [
    "Ya estamos en la pestaña de búsqueda de Spotify.",
    "Listo, estoy en la búsqueda de Spotify.",
    "Fui a la búsqueda de Spotify.",
    "Listo, ya estás en «Buscar».",
    "Done, I'm now in the search page of Spotify.",
    "I went to the search in Spotify.",
]


def test_focus_is_a_weak_proof():
    assert claims.weak_proof("focus:search")
    assert claims.weak_proof("title:spotify&focus:search")
    # Contracase: a control the window marks current is a strong arrival.
    assert not claims.weak_proof("control:buscar:current")


@pytest.mark.parametrize("draft", DRAFTS)
def test_x7_a_search_told_as_a_place_is_refused(draft):
    assert computer_use_finals._claims_defect(draft, "status", _mission(X7)) == "search_told_as_place"
    assert compose_visible_defect(draft, "status", "en spotify andá a search", _facts(_mission(X7))) != ""


@pytest.mark.parametrize("draft", DRAFTS[:4])
def test_the_same_place_over_a_strong_arrival_is_published(draft):
    assert computer_use_finals._claims_defect(draft, "status", _mission(STRONG)) == ""


def test_the_template_and_an_opened_search_pass():
    for english in (False, True):
        sentence = cu_finals.floor_sentence(X7, english, True)
        assert sentence == (
            "Done, the search is open and the cursor is in «¿Qué quieres reproducir?»." if english
            else "Listo, se abrió la búsqueda y el cursor está en «¿Qué quieres reproducir?»."
        )
        assert computer_use_finals._claims_defect(sentence, "status", _mission(X7)) == ""
        assert compose_visible_defect(
            sentence, "status", "en spotify andá a search", _facts(_mission(X7))) == ""
    # «abrí la búsqueda» says what the template says («se abrió la búsqueda»): no place told.
    assert computer_use_finals._claims_defect("Listo, abrí la búsqueda de Spotify.", "status", _mission(X7)) == ""
    # The defect lets the template stand in for a third draft.
    assert claims.template_suffices("search_told_as_place", "mission.computer.use")


def test_the_focused_fields_question_mark_is_the_windows_not_baxys():
    # Contracase: the same words unquoted are BAXY asking.
    assert compose_visible_defect(
        "Listo, se abrió la búsqueda. ¿Qué quieres reproducir?", "status", "en spotify andá a search",
        _facts(_mission(X7))) == "extra_claim"


def test_the_floor_says_the_search_opened_without_a_field_and_without_the_place_spelled():
    no_field = _search("focus:search", focused=None)
    for english, said in ((False, "Listo, se abrió la búsqueda."), (True, "Done, the search is open.")):
        assert cu_finals.floor_sentence(no_field, english, True) == said
        assert compose_visible_defect(said, "status", "en spotify andá a search", _facts(_mission(no_field))) == ""


def test_a_chain_tells_its_other_place_but_not_the_search_as_one():
    chain = {
        "goal": "ir a tu biblioteca; luego ir a search", "application": "Spotify", "reached": True,
        "satisfiedBy": "focus:search",
        "subgoals": [
            {"goal": "ir a tu biblioteca", "reached": True, "satisfiedBy": "control:tu biblioteca:current"},
            {"goal": "ir a search", "reached": True, "satisfiedBy": "focus:search"},
        ],
        "steps": [
            {"step": 1, "operation": "input.visible.click", "label": "Tu biblioteca", "ok": True},
            {"step": 2, "operation": "input.visible.click", "label": "Buscar", "ok": True},
        ],
        "window": {"title": "Spotify Premium"},
    }
    situation = _mission(chain)
    # Contracase: the place a control proved is told as one, the search as opened.
    assert computer_use_finals._claims_defect(
        "Listo, fui a «Tu biblioteca» y se abrió la búsqueda.", "status", situation) == ""
    assert computer_use_finals._claims_defect(
        "Fui a «Tu biblioteca» y luego estoy en la búsqueda.", "status", situation) == "search_told_as_place"


def test_a_question_tells_no_place():
    assert claims.search_told_as_place("¿Querés que vaya a la búsqueda?") == ""
    # Contracase of revisión 2 (B1): a question of BAXY's around a quoted field still tells nothing.
    assert claims.search_told_as_place(
        "¿Querés que me quede en «¿Qué quieres reproducir?»?", ["¿Qué quieres reproducir?"]) == ""


# Revisión 2 de r24b (B1): the focused field quoted with its own «?» neither ends the sentence nor makes it a question.
QUOTED_FIELD_DRAFTS = [
    "Listo, estoy en la búsqueda de Spotify y el cursor está en «¿Qué quieres reproducir?».",
    "Listo, estoy en «¿Qué quieres reproducir?».",
    "Ya estoy en la búsqueda: el cursor quedó en «¿Qué quieres reproducir?»",
    "Done, I'm in the search, cursor in «¿Qué quieres reproducir?».",
]


@pytest.mark.parametrize("draft", QUOTED_FIELD_DRAFTS)
def test_b1_a_place_told_beside_a_quoted_field_with_a_question_mark_is_refused(draft):
    assert computer_use_finals._claims_defect(draft, "status", _mission(X7)) == "search_told_as_place"
    assert compose_visible_defect(draft, "status", "en spotify andá a search", _facts(_mission(X7))) != ""


def test_b1_the_same_drafts_over_a_field_without_a_question_mark_are_refused_too():
    field = _search("focus:search", focused="Buscar en la biblioteca")
    for draft in QUOTED_FIELD_DRAFTS:
        said = draft.replace("¿Qué quieres reproducir?", "Buscar en la biblioteca")
        assert computer_use_finals._claims_defect(said, "status", _mission(field)) == "search_told_as_place"


def test_b1_contracase_the_template_quoting_the_field_still_passes():
    # «el cursor está en «…»» (third person) tells no place, whatever the field's own signs.
    said = "Listo, se abrió la búsqueda y el cursor está en «¿Qué quieres reproducir?»."
    assert computer_use_finals._claims_defect(said, "status", _mission(X7)) == ""
    assert compose_visible_defect(said, "status", "en spotify andá a search", _facts(_mission(X7))) == ""
    # Over a strong arrival, the place quoted is a place reached.
    strong = _search("control:buscar:current", focused="¿Qué quieres reproducir?")
    assert computer_use_finals._search_told_as_place("Listo, estoy en «¿Qué quieres reproducir?».", _mission(strong)) == ""


# Revisión 3 de r24b (B1): a focused field is weak for the book of acts, not for the weak final of a chain. A chain
# whose first part a focused field proved and whose last part a strong atom proved, which _parts_final cannot tell,
# was told «Llevo dos pasos…, pero la pantalla todavía no muestra que haya quedado hecho», denying what was verified.
def _chain_then(second_goal: str, second_proof: str, second_step: dict) -> dict:
    return {
        "goal": f"ir a search; luego {second_goal}", "application": "Spotify", "reached": True,
        "satisfiedBy": second_proof,
        "subgoals": [
            {"goal": "ir a search", "reached": True, "satisfiedBy": "focus:search"},
            {"goal": second_goal, "reached": True, "satisfiedBy": second_proof},
        ],
        "steps": [
            {"step": 1, "operation": "input.visible.click", "label": "Buscar", "ok": True, "name": "Buscar"},
            {"step": 2, **second_step, "ok": True},
        ],
        "window": {"title": "Spotify Premium", "process": "Spotify"},
    }


STRONG_SECOND_PARTS = [
    ("abrir el reproductor de lofi", "page:lofi",
     {"operation": "input.visible.click", "label": "Canciones", "name": "Canciones"}),
    ("pulsar enter", "stepDone:input.key.press:enter", {"operation": "input.key.press", "key": "enter"}),
]


@pytest.mark.parametrize("second_goal,second_proof,second_step", STRONG_SECOND_PARTS)
def test_r3_b1_a_strong_last_part_after_an_opened_search_is_told_done(second_goal, second_proof, second_step):
    chain = _chain_then(second_goal, second_proof, second_step)
    assert not cu_finals._weakly_reached(chain)
    assert cu_finals.floor_sentence(chain, False, True) == "Listo, lo hice en «Spotify»."
    assert cu_finals.floor_sentence(chain, True, True) == "Done, I did it in «Spotify»."


def test_r3_b1_contracase_a_weak_part_beside_the_search_still_counts_the_steps():
    # The model's own citation (or a resemblance) on the last part is still weak: the screen does not show it done.
    chain = _chain_then("abrir el reproductor de lofi", "model_evidence",
                        {"operation": "input.visible.click", "label": "Canciones", "name": "Canciones"})
    assert cu_finals._weakly_reached(chain)
    assert cu_finals.floor_sentence(chain, False, True).startswith("Llevo dos pasos en «Spotify»")
    assert cu_finals._weakly_reached({"reached": True, "satisfiedBy": "focus:search&similar:lofi"})
    assert cu_finals._weakly_reached({"reached": True, "satisfiedBy": "focus:search|page:lofi"})
    # And focus stays weak for the book of acts and for «ya estás en».
    assert claims.weak_proof("focus:search")


def test_r3_b1_contracase_a_one_part_search_is_still_told_as_opened():
    single = _search("focus:search")
    single["subgoals"] = [{"goal": "ir a search", "reached": True, "satisfiedBy": "focus:search"}]
    assert cu_finals.floor_sentence(single, False, True) == (
        "Listo, se abrió la búsqueda y el cursor está en «¿Qué quieres reproducir?».")
