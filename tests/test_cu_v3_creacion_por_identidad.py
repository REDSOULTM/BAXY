"""Ronda 20, palanca P4: un recibo de creación sólo vale con una parte nueva de verdad.

v3-08 (pasada r18): «en OneNote creá una página nueva» pulsó «Agregar página» (ok, changed, broughtNew) y el teclado
quedó en el «Título de página» vacío de la página nueva. La primera vista del sub-objetivo ya tenía un «Título de
página» vacío (la página que estaba, también sin título), así que ``_seen_at_start`` rechazó la cita y
``creates_again`` dijo «no llevó al objetivo»: el final negó una página creada. La novedad de la parte se juzga ahora
por identidad: el App pasa los ids (UIA runtime id) de las partes vacías y la enfocada de la primera vista
(«firstIds») y el id de la parte enfocada ahora («focusedId»). Vistas modeladas sobre la evidencia de v3-08
(compose_audit: observed.steps[1], window.focused) y del diagnóstico 8 de r18_tramo1.json.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from baxy_mind import cu_first_look
from baxy_mind import cu_creation
from baxy_mind import cu_evidence
from baxy_mind import cu_validate
from baxy_mind import cu_step_prompt

GOAL = "crea una pagina nueva"
FIRST_LOOK = "\n".join([
    "sin titulo - onenote", "crear una nueva seccion", "agregar pagina", "ordenar paginas", "sin titulo",
    "comprar pan, leche y huevos", "titulo de pagina",
])
# The page that was already there: its empty title, focused, with this id.
OLD_TITLE_ID = "42.3348.4.11"
NEW_TITLE_ID = "42.3348.4.97"


def _view(*, focused_id: str = NEW_TITLE_ID, first_ids: list[str] | None = None, extra: list[dict] | None = None) -> dict:
    controls = [
        {"i": 0, "kind": "Button", "name": "Atrás", "state": ""},
        {"i": 1, "kind": "Button", "name": "Deshacer", "state": ""},
        {"i": 2, "kind": "TreeItem", "name": "Crear una nueva sección", "state": ""},
        {"i": 3, "kind": "Button", "name": "Agregar página", "state": ""},
        {"i": 4, "kind": "Button", "name": "Ordenar páginas", "state": ""},
        {"i": 5, "kind": "ListItem", "name": "Comprar pan, leche y huevos", "state": ""},
        {"i": 6, "kind": "ListItem", "name": "Sin título", "state": "selected"},
        {"i": 7, "kind": "Document", "name": "Título de página", "state": "focused"},
        *(extra or []),
    ]
    return {
        "window": {"title": "Sin título - OneNote", "process": "onenote",
                   "focused": {"kind": "Document", "name": "Título de página", "value": "", "i": 7}},
        "controls": controls,
        "text": {},
        "firstLook": FIRST_LOOK,
        "firstIds": [OLD_TITLE_ID] if first_ids is None else first_ids,
        "focusedId": focused_id,
        "newTextAfterClick": ["Atrás", "Deshacer"],
    }


def _pressed(label: str = "Agregar página", *, brought_new: bool = True) -> dict:
    return {"step": 1, "operation": "input.visible.click", "source": "model", "label": label, "index": 3,
            "ok": True, "changed": True, "broughtNew": brought_new}


def _done(view: dict, history: list[dict], goal: str = GOAL) -> dict:
    return cu_validate.validate_decision({"act": "done", "evidence": "Título de página"}, view=view, last_failed=None,
                                application_names=("OneNote",), history=history, goal=goal)


def test_v3_08_the_new_page_s_empty_title_closes_the_creation() -> None:
    step = cu_creation._created_by_effect(GOAL, _view(), [_pressed()])

    assert step is not None and step["operation"] == "done"
    assert step["arguments"] == {"evidence": "Título de página"}


def test_v3_08_the_model_s_done_citing_the_new_title_is_taken() -> None:
    step = _done(_view(), [_pressed()])

    assert step["operation"] == "done"


@pytest.mark.parametrize(("view", "history", "goal"), [
    # The page without a title already focused, and a click with no broughtNew and the same id: nothing new.
    (_view(focused_id=OLD_TITLE_ID), [_pressed(brought_new=False)], GOAL),
    # The same id as the first look's, even after a creating click that brought something.
    (_view(focused_id=OLD_TITLE_ID), [_pressed()], GOAL),
    # A new id but the click brought nothing new.
    (_view(), [_pressed(brought_new=False)], GOAL),
    # «Agregar página» opened a menu of templates: a page is not made yet.
    (_view(extra=[{"i": 8, "kind": "Menu", "name": "Plantillas de página", "state": ""}]), [_pressed()], GOAL),
    # Navigating to an existing empty title (the list's «Sin título») is no creating command.
    (_view(), [_pressed("Sin título")], GOAL),
    # «crea dos páginas» says how many: one is not all of it.
    (_view(), [_pressed()], "crea dos paginas nuevas"),
    # The command creates another thing than the goal's.
    (_view(), [_pressed("Crear una nueva sección")], GOAL),
    # The App gave no ids (an older look): judged as before.
    ({**_view(), "firstIds": None}, [_pressed()], GOAL),
])
def test_contracases_of_a_part_new_by_identity(view: dict, history: list[dict], goal: str) -> None:
    assert not cu_first_look._new_part_by_identity("Título de página", view, history, goal)
    assert cu_creation._created_by_effect(goal, view, history) is None
    assert _done(view, history, goal)["operation"] != "done"


def test_a_part_that_holds_text_is_no_new_empty_part() -> None:
    view = _view()
    view["window"]["focused"] = {**view["window"]["focused"], "value": "Lista del super"}
    view["controls"][7] = {**view["controls"][7], "value": "Lista del super"}

    assert not cu_first_look._new_part_by_identity("Título de página", view, [_pressed()], GOAL)


def test_the_cited_part_must_be_the_focused_one() -> None:
    view = copy.deepcopy(_view())
    view["window"]["focused"] = {"kind": "ListItem", "name": "Sin título", "value": "", "i": 6}

    assert not cu_first_look._new_part_by_identity("Título de página", view, [_pressed()], GOAL)


# (c) creates_again: the command that already created just what was asked admits done on the retry.
def test_creates_again_after_the_asked_thing_admits_done() -> None:
    again = cu_validate.validate_decision({"act": "click", "text": "Agregar página", "i": 3}, view=_view(), last_failed=None,
                                 application_names=("OneNote",), history=[_pressed()], goal=GOAL)

    assert again["operation"] == "none" and again["code"] == "creates_again"
    assert again.get("admits_done") is True
    assert "ya creó lo pedido" in again["reason"]
    retry = cu_step_prompt.retry_instruction(str(again["reason"]), [{"i": 3, "name": "Agregar página"}], admits_done=True)
    assert "done" in retry


def test_creates_again_on_a_goal_that_does_not_ask_for_it_offers_no_done() -> None:
    again = cu_validate.validate_decision({"act": "click", "text": "Agregar página", "i": 3}, view=_view(), last_failed=None,
                                 application_names=("OneNote",), history=[_pressed()],
                                 goal="ponele de titulo Lista del super")

    assert again["operation"] == "none" and again["code"] == "creates_again"
    assert "admits_done" not in again
    assert "done" not in cu_step_prompt.retry_instruction(str(again["reason"]), [])


# Revisión 1 de P4: «crea un evento nuevo» pulsó «Nuevo evento» (ok, changed, broughtNew) y el foco quedó en el
# «Agregar un título» vacío de un formulario que ofrece «Guardar» y «Descartar»; la primera vista ya mostraba un
# «Agregar un título» vacío de otro formulario (id 9.1). La parte enfocada tiene otro id (9.2), pero el evento no
# existe hasta guardarlo: nada de lo pedido está hecho.
EVENT_GOAL = "crea un evento nuevo"


def _event_view(*, commit: bool = True) -> dict:
    controls = [
        {"i": 0, "kind": "Button", "name": "Nuevo evento", "state": ""},
        {"i": 1, "kind": "Button", "name": "Hoy", "state": ""},
        *([{"i": 2, "kind": "Button", "name": "Guardar", "state": ""},
           {"i": 3, "kind": "Button", "name": "Descartar", "state": ""}] if commit else []),
        {"i": 4, "kind": "Edit", "name": "Agregar un título", "state": "focused", "value": ""},
    ]
    return {
        "window": {"title": "Calendario", "process": "calendario",
                   "focused": {"kind": "Edit", "name": "Agregar un título", "value": "", "i": 4}},
        "controls": controls,
        "text": {},
        "firstLook": "\n".join(["calendario", "nuevo evento", "hoy", "agregar un titulo"]),
        "firstIds": ["9.1"],
        "focusedId": "9.2",
        "newTextAfterClick": ["Guardar", "Descartar"] if commit else [],
    }


def _event_done(view: dict) -> dict:
    return cu_validate.validate_decision({"act": "done", "evidence": "Agregar un título"}, view=view, last_failed=None,
                                application_names=("Calendario",), history=[_pressed("Nuevo evento")],
                                goal=EVENT_GOAL)


def test_a_form_still_to_be_saved_is_no_new_part_by_identity() -> None:
    view = _event_view()

    assert not cu_first_look._new_part_by_identity("Agregar un título", view, [_pressed("Nuevo evento")], EVENT_GOAL)
    assert cu_creation._created_by_effect(EVENT_GOAL, view, [_pressed("Nuevo evento")]) is None
    assert _event_done(view)["operation"] != "done"


def test_the_same_part_with_no_button_that_saves_is_new_by_identity() -> None:
    # Contracaso: without «Guardar» on offer the empty part with a new id after the creating click is the new thing's.
    assert cu_first_look._new_part_by_identity("Agregar un título", _event_view(commit=False), [_pressed("Nuevo evento")],
                                    EVENT_GOAL)


@pytest.mark.parametrize("name", ["Guardar y cerrar", "Save & close", "Crear", "OK"])
def test_every_button_that_saves_or_confirms_holds_the_part(name: str) -> None:
    view = _event_view(commit=False)
    view["controls"].append({"i": 5, "kind": "Button", "name": name, "state": ""})

    assert not cu_first_look._new_part_by_identity("Agregar un título", view, [_pressed("Nuevo evento")], EVENT_GOAL)


def test_a_button_that_only_names_a_creation_does_not_hold_the_part() -> None:
    # «Agregar página» is the creating command itself, not a form's confirmation: v3-08 still closes.
    assert cu_first_look._new_part_by_identity("Título de página", _view(), [_pressed()], GOAL)


# Revisión 2 de P4: «creates_again» sólo dice «ya creó lo pedido» y ofrece done con la prueba de que lo creado existe.
def _again_on_event(view: dict) -> dict:
    return cu_validate.validate_decision({"act": "click", "text": "Nuevo evento", "i": 0}, view=view, last_failed=None,
                                application_names=("Calendario",), history=[_pressed("Nuevo evento")],
                                goal=EVENT_GOAL)


def test_creates_again_over_a_form_still_to_save_offers_no_done() -> None:
    again = _again_on_event(_event_view())

    assert again["operation"] == "none" and again["code"] == "creates_again"
    assert "admits_done" not in again
    assert "ya creó lo pedido" not in again["reason"]
    assert "seguí con lo que apareció" in again["reason"]


def test_creates_again_with_the_new_part_and_no_form_admits_done() -> None:
    # Contracaso: the same command and part with no button that saves: the new part by identity proves the thing.
    again = _again_on_event(_event_view(commit=False))

    assert again["code"] == "creates_again" and again.get("admits_done") is True


def test_creates_again_with_a_menu_open_offers_no_done() -> None:
    view = _view(extra=[{"i": 8, "kind": "Menu", "name": "Plantillas de página", "state": ""}])
    again = cu_validate.validate_decision({"act": "click", "text": "Agregar página", "i": 3}, view=view, last_failed=None,
                                 application_names=("OneNote",), history=[_pressed()], goal=GOAL)

    assert again["code"] == "creates_again" and "admits_done" not in again


@pytest.mark.parametrize("cited", ["Guardar", "Descartar"])
def test_a_form_s_own_button_is_no_proof_of_creation(cited: str) -> None:
    done = cu_validate.validate_decision({"act": "done", "evidence": cited}, view=_event_view(), last_failed=None,
                                application_names=("Calendario",), history=[_pressed("Nuevo evento")],
                                goal=EVENT_GOAL)

    assert done["operation"] != "done"


def test_a_button_cited_with_no_form_to_save_is_judged_as_before() -> None:
    # Contracaso: with no button that saves or confirms on offer, citing a button is not this rule's.
    view = _event_view(commit=False)
    view["controls"].append({"i": 5, "kind": "Button", "name": "Descartar", "state": ""})
    view["newTextAfterClick"] = ["Descartar"]

    assert not cu_creation._form_button_cited("Descartar", view, EVENT_GOAL)
    assert cu_creation._form_button_cited("Descartar", _event_view(), EVENT_GOAL)
    # A goal that creates nothing (saving the form) is not this rule's either.
    assert not cu_creation._form_button_cited("Guardar", _event_view(), "guarda el evento")


# Revisión 3 de P4: el formulario es el que trajo el subobjetivo, no el «Guardar» de la barra de acceso rápido de
# Office (vista en vivo de Word grabada en tests/data/cu_v3_vistas_buscar.json, word_insertar) ni la burbuja de un
# favorito ya agregado.
_WORD = json.loads((Path(__file__).parent / "data" / "cu_v3_vistas_buscar.json").read_text(encoding="utf-8"))[
    "word_insertar"]["vista"]
BULLETS_GOAL = "agrega vinetas a la lista"


def _word_bullets(*, state: str) -> dict:
    view = copy.deepcopy(_WORD)
    view["controls"].append({"i": 90, "kind": "SplitButton", "name": "Viñetas", "state": state, "zone": "T"})
    return view


def _word_bullets_on() -> tuple[dict, list[dict]]:
    view = _word_bullets(state="on")
    view["firstLook"] = "\n".join(cu_first_look.look_parts(_word_bullets(state="")))
    view["newTextAfterClick"] = []
    history = [{"step": 1, "operation": "input.visible.click", "source": "model", "label": "Viñetas", "index": 90,
                "ok": True, "changed": True, "chosenBefore": False}]
    return view, history


def test_word_s_quick_access_save_is_no_form_to_save() -> None:
    view, history = _word_bullets_on()
    assert any(item.get("kind") == "Button" and item.get("name") == "Guardar" for item in view["controls"])

    assert not cu_creation._form_button_cited("Viñetas", view, BULLETS_GOAL)
    done = cu_validate.validate_decision({"act": "done", "evidence": "Viñetas"}, view=view, last_failed=None,
                                application_names=("Word",), history=history, goal=BULLETS_GOAL)
    assert done["operation"] == "done", done


def test_a_save_button_already_on_the_first_look_is_not_brought() -> None:
    view, _ = _word_bullets_on()
    save = next(item for item in view["controls"] if item.get("name") == "Guardar")

    assert not cu_creation._brought_this_subgoal(save, view)
    # The same button that the click made appear is the form's.
    assert cu_creation._brought_this_subgoal(save, {**view, "newTextAfterClick": ["Guardar"]})
    assert cu_creation._brought_this_subgoal(save, {**view, "firstLook": "documento1 - word"})
    # Without a first look or a click's new text, nothing counts as brought.
    assert not cu_creation._brought_this_subgoal(save, {**view, "firstLook": None})


def test_the_favourite_s_own_button_beside_its_done_bubble_proves_it() -> None:
    # «agrega esta pagina a favoritos»: the star, now «Editar favorito…», and the bubble with «Listo» and «Quitar» it
    # brought. The renamed star names the thing; «Listo» is the bubble's own.
    goal = "agrega esta pagina a favoritos"
    controls = [
        {"i": 0, "kind": "Button", "name": "Editar favorito para esta página (Ctrl+D)", "state": ""},
        {"i": 1, "kind": "Button", "name": "Listo", "state": ""},
        {"i": 2, "kind": "Button", "name": "Quitar", "state": ""},
    ]
    view = {
        "window": {"title": "Ejemplo - Microsoft Edge", "process": "msedge"},
        "controls": controls,
        "text": {},
        "firstLook": "\n".join(["ejemplo - microsoft edge", "agregar esta pagina a favoritos (ctrl+d)"]),
        "newTextAfterClick": ["Listo", "Quitar"],
    }

    assert not cu_creation._form_button_cited("Editar favorito para esta página (Ctrl+D)", view, goal)
    assert cu_creation._form_button_cited("Quitar", view, goal)


def test_a_split_citation_is_new_when_one_piece_is_new_by_identity() -> None:
    """Integración ronda 20 (P4 + P6): a citation of several lines (« | ») is judged piece by piece, and a piece that is
    the part new by identity makes it new; with the old part focused every piece was seen at the start."""

    cited = "Sin título | Título de página"

    assert not cu_evidence._seen_at_start_all(cited, _view(), [_pressed()], GOAL)
    assert cu_evidence._seen_at_start_all(cited, _view(focused_id=OLD_TITLE_ID), [_pressed()], GOAL)
    # Without the goal no part is new by identity: judged as P6 alone did.
    assert cu_evidence._seen_at_start_all(cited, _view(), [_pressed()])
