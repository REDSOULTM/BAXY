"""Ronda 24, «un acto sin efecto no prueba nada» (pasada r23), la parte de la mente.

t-menu-4: un Enter con la vista idéntica (``sameView``) contó como acto con efecto en ``acted_with_effect``. v3-33:
«sacá una captura de pantalla completa» se dio por hecha citando el ListItem «Pantalla completa» elegido, con «Nueva
captura de pantalla» sin pulsar. Gemelos del App: ComputerUseSuccessCheck.ActedWithEffect, KeyLeftTheViewAsItWas,
ProductNoun y OptionNotProduct (tests/Baxy.Integration.Tests/CuV3R24UnActoSinEfectoTests.cs).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from baxy_mind import computer_use
from baxy_mind import cu_vocabulary
from baxy_mind import cu_evidence
from baxy_mind import cu_validate

_GOAL_MENU = "hacer clic en girar 90 a la derecha"


def _key(key: str, **extra: object) -> dict:
    return {"step": 1, "operation": "input.key.press", "key": key, "ok": True, **extra}


def test_t_menu_4_a_key_that_left_the_view_as_it_was_is_no_act_with_an_effect() -> None:
    # Review 4: the App marks an Enter «as it was» with the written text read the same too (sameText).
    assert cu_evidence.acted_with_effect([_key("enter", sameView=True, sameText=True)], _GOAL_MENU) is False
    # A key outside the unseen-effect keys needs only the signature.
    assert cu_evidence.acted_with_effect([_key("escape", sameView=True)], _GOAL_MENU) is False


def test_t_menu_4_contracase_a_key_that_changed_the_view_still_counts() -> None:
    # An Enter that sends a search and changes the view.
    assert cu_evidence.acted_with_effect([_key("enter")], _GOAL_MENU) is True


def test_contracase_tab_and_the_enter_after_a_query_stay_as_they_were() -> None:
    assert cu_evidence.acted_with_effect([_key("tab")], _GOAL_MENU) is False
    typed = {"step": 1, "operation": "input.text.type", "text": "girar", "ok": True, "query": True}
    assert cu_evidence.acted_with_effect([typed, _key("enter")], _GOAL_MENU) is False


def test_contracase_a_copy_key_counts_though_the_window_kept_its_signature() -> None:
    # «copiá el resultado»: the copy's effect is the clipboard, which no look shows and BAXY never reads.
    assert "ctrl_c" in cu_vocabulary.CONTENT_COPY_KEYS
    assert cu_evidence.acted_with_effect([_key("ctrl_c", sameView=True)], "apretar ctrl c") is True


def test_t_menu_4_a_done_after_a_key_without_effect_is_refused() -> None:
    view = {
        "window": {"title": "Sin título - Paint", "process": "mspaint"},
        "controls": [{"i": 0, "kind": "MenuItem", "name": "Girar 90° a la derecha"}],
    }
    decision = cu_validate._checked_act(
        {"act": "done", "evidence": "Girar 90° a la derecha", "why": "listo"}, view=view, last_failed=None,
        application_names=(), history=[_key("enter", sameView=True, sameText=True)], goal=_GOAL_MENU,
    )
    assert decision["operation"] == "none"
    assert decision["code"] == "evidence_not_visible"


# v3-33: Recortes after the list's entry «Pantalla completa» was chosen.
def _snipping(captured: bool = False) -> dict:
    controls = [
        {"i": 0, "kind": "Button", "name": "Nueva captura de pantalla"},
        {"i": 1, "kind": "ListItem", "name": "Pantalla completa", "state": "selected"},
        {"i": 2, "kind": "ListItem", "name": "Rectángulo"},
    ]
    if captured:
        controls.append({"i": 3, "kind": "Image", "name": "Captura de pantalla 1"})
    return {"window": {"title": "Recortes - Captura de pantalla 1" if captured else "Recortes", "process": "SnippingTool"},
            "controls": controls}


_CHOSE = {
    "step": 5, "operation": "input.visible.click", "label": "Pantalla completa", "ok": True, "method": "select",
    "selected": True, "kind": "ListItem", "name": "Pantalla completa", "changed": True,
}
_PRESSED = {
    "step": 6, "operation": "input.visible.click", "label": "Nueva captura de pantalla", "ok": True, "method": "invoke",
    "surfaceChanged": True, "kind": "Button", "name": "Nueva captura de pantalla", "changed": True,
}


def _done(evidence: str, view: dict, history: list[dict], goal: str) -> dict:
    return cu_validate._checked_act(
        {"act": "done", "evidence": evidence, "why": "listo"}, view=view, last_failed=None, application_names=(),
        history=history, goal=goal,
    )


def test_v3_33_an_option_chosen_is_no_product_made() -> None:
    decision = _done("Pantalla completa", _snipping(), [_CHOSE], "sacá una captura de pantalla completa")
    assert decision["operation"] == "none"
    assert decision["code"] == "option_not_product"
    # The retry names the view's command that carries the product's noun.
    assert "Nueva captura de pantalla" in str(decision["reason"])
    assert "option_not_product" in computer_use._RETRIED


@pytest.mark.parametrize(
    ("goal", "noun"),
    [
        ("sacá una captura de pantalla completa", "captura"),
        ("take a screenshot", "screenshot"),
        ("grabá un video de la pantalla", "video"),
        ("en recortes poné el modo pantalla completa", None),
        ("elegí pantalla completa", None),
        ("escribe € en el bloc de notas", None),
        ("hacer clic en nueva captura", None),
        # Revisión 2, hallazgo 1: el imperativo de tú.
        ("haz una captura de pantalla completa", "captura"),
        ("hazme una captura de pantalla completa", "captura"),
        ("hace otra foto", "foto"),
        ("sacá fotos", "fotos"),
        # Revisión 2, hallazgo 2: un objeto que ya existe (artículo definido o posesivo) se cambia, no se produce.
        ("hace la foto en blanco y negro", None),
        ("make the photo black and white", None),
        ("make the video 1080p", None),
        ("take the photos tab", None),
        ("sacá mi foto de la carpeta", None),
    ],
)
def test_the_product_noun_is_read_from_data(goal: str, noun: str | None) -> None:
    assert cu_evidence.product_noun(goal) == noun


@pytest.mark.parametrize("goal", ["en recortes poné el modo pantalla completa", "elegí pantalla completa"])
def test_v3_33_contracase_a_goal_of_choosing_closes_on_the_chosen_option(goal: str) -> None:
    decision = _done("Pantalla completa", _snipping(), [_CHOSE], goal)
    assert decision.get("code") != "option_not_product"


def test_v3_33_contracase_the_capture_made_after_its_command_closes() -> None:
    decision = _done("Captura de pantalla 1", _snipping(captured=True), [_CHOSE, _PRESSED],
                     "sacá una captura de pantalla completa")
    assert decision.get("code") != "option_not_product"
    assert decision["operation"] == "done"


# Revisión 1, hallazgo 2: el mando del producto ya se pulsó con efecto y el modelo cita la opción elegida.
def test_review_1_the_option_cited_after_the_product_was_made_names_no_pending_command() -> None:
    decision = _done("Pantalla completa", _snipping(captured=True), [_CHOSE, _PRESSED],
                     "sacá una captura de pantalla completa")
    assert decision.get("code") != "option_not_product"
    assert "hasta pulsar" not in str(decision.get("reason") or "")
    assert cu_evidence._product_made([_CHOSE, _PRESSED], "captura", "sacá una captura de pantalla completa") is True


def test_review_1_contracase_a_command_pressed_without_effect_or_without_the_noun_makes_nothing() -> None:
    goal = "sacá una captura de pantalla completa"
    # The product's command pressed but nothing changed: the capture is still pending.
    unanswered = {**_PRESSED, "surfaceChanged": False, "changed": False}
    decision = _done("Pantalla completa", _snipping(), [_CHOSE, unanswered], goal)
    assert decision["code"] == "option_not_product"
    # A command that opened the list of modes carries no product's noun: the option is still the only news.
    mode = {**_PRESSED, "label": "Modo de recorte", "name": "Modo de recorte", "kind": "SplitButton", "step": 4}
    decision = _done("Pantalla completa", _snipping(), [mode, _CHOSE], goal)
    assert decision["code"] == "option_not_product"


# Revisión 2, hallazgo 1: «haz»/«hazme» (la forma de tú) es la misma meta de v3-33.
@pytest.mark.parametrize("clause", ["haz una captura de pantalla completa", "hazme una captura de pantalla completa"])
def test_review_2_the_imperative_of_tu_refuses_the_option_chosen(clause: str) -> None:
    from baxy_mind.semantic import missions

    read = missions.read_clause(clause)
    goal = read[0] if read is not None else clause
    assert cu_evidence.product_noun(goal) == "captura"
    decision = _done("Pantalla completa", _snipping(), [_CHOSE], goal)
    assert decision["operation"] == "none"
    assert decision["code"] == "option_not_product"


# Revisión 2, hallazgo 2: en Fotos, el filtro «Blanco y negro» elegido ya cambió la foto que existe.
def _photos() -> dict:
    return {
        "window": {"title": "Fotos - IMG_0001.jpg", "process": "Photos"},
        "controls": [
            {"i": 0, "kind": "Button", "name": "Guardar como copia"},
            {"i": 1, "kind": "ListItem", "name": "Original"},
            {"i": 2, "kind": "ListItem", "name": "Blanco y negro", "state": "selected"},
        ],
    }


_FILTER = {
    "step": 4, "operation": "input.visible.click", "label": "Blanco y negro", "ok": True, "method": "select",
    "selected": True, "kind": "ListItem", "name": "Blanco y negro", "changed": True,
}


@pytest.mark.parametrize("clause", ["hacé la foto en blanco y negro", "make the photo black and white"])
def test_review_2_changing_an_existing_object_is_no_product_to_make(clause: str) -> None:
    from baxy_mind.semantic import missions

    read = missions.read_clause(clause)
    goal = read[0] if read is not None else clause
    assert cu_evidence.product_noun(goal) is None
    decision = _done("Blanco y negro", _photos(), [_FILTER], goal)
    assert decision.get("code") != "option_not_product"
    assert "produce" not in str(decision.get("reason") or "")


def test_review_2_contracase_a_new_photo_in_black_and_white_is_still_a_product() -> None:
    # «hacé una foto en blanco y negro»: the photo is new, the filter is how it is made.
    goal = "hace una foto en blanco y negro"
    assert cu_evidence.product_noun(goal) == "foto"
    view = _photos()
    view["controls"].append({"i": 3, "kind": "Button", "name": "Tomar foto"})
    decision = _done("Blanco y negro", view, [_FILTER], goal)
    assert decision["operation"] == "none"
    assert decision["code"] == "option_not_product"
    assert "Tomar foto" in str(decision["reason"])


# Revisión 4, bloqueante 1: in the Terminal the console text is no control's value, so the Enter that runs a command and
# the arrow that brings it back keep the view's signature (the App marks them sameView) although the command ran and
# its output is in the written text read. Measured on the frozen view terminal_tras_ctrl_k (test_cu_v3_teclas_sin_efecto).
def _terminal_ran_ipconfig() -> dict:
    data = json.loads((Path(__file__).parent / "data" / "cu_v3_vistas_teclas.json").read_text(encoding="utf-8"))
    view = copy.deepcopy(data["terminal_tras_ctrl_k"]["vista"])
    view["text"]["TL"] += [r"PS C:\Users\usuario> ipconfig", "Configuracion IP de Windows", "Adaptador de Ethernet Ethernet:"]
    return view


_OPENED_TERMINAL = {"step": 1, "operation": "app.open", "appId": "Terminal", "ok": True, "changed": True}


@pytest.mark.parametrize("goal", ["repetir el ultimo comando", "ejecutar de nuevo el comando anterior"])
def test_review_4_the_terminal_command_an_enter_ran_is_an_act_though_the_signature_kept(goal: str) -> None:
    view = _terminal_ran_ipconfig()
    keys = [{**_key("arrow_up", sameView=True), "step": 2}, {**_key("enter", sameView=True), "step": 3}]
    assert cu_evidence.acted_with_effect(keys, goal) is True
    assert cu_evidence.acted_with_effect([keys[1]], goal) is True
    assert not cu_evidence.key_left_the_view_as_it_was(keys[0])
    assert not cu_evidence.key_left_the_view_as_it_was(keys[1])
    marked = _done("Configuracion IP de Windows", view, [_OPENED_TERMINAL, *keys], goal)
    unmarked = _done(
        "Configuracion IP de Windows", view,
        [_OPENED_TERMINAL, *({k: v for k, v in key.items() if k != "sameView"} for key in keys)], goal,
    )
    # The same verdict as the same keys without the mark: the done is not refused as «nothing done for this goal».
    assert marked == unmarked
    assert marked.get("code") != "evidence_not_visible", marked
    assert marked["operation"] != "none", marked


def test_review_4_contracases_caret_keys_never_and_written_keys_only_with_the_text_read_the_same() -> None:
    # A caret, selection, clipboard, save or undo key is never «as it was» (its effect lands where no look reads).
    for key in ("arrow_up", "arrow_left", "home", "end", "ctrl_a", "ctrl_c", "ctrl_s", "ctrl_z", "page_down"):
        assert not cu_evidence.key_left_the_view_as_it_was(_key(key, sameView=True, sameText=True)), key
    # A key whose effect lands on the written text: «as it was» only when the App read the same text too.
    for key in ("enter", "backspace", "delete", "space", "ctrl_v", "ctrl_x"):
        assert not cu_evidence.key_left_the_view_as_it_was(_key(key, sameView=True)), key
        assert cu_evidence.key_left_the_view_as_it_was(_key(key, sameView=True, sameText=True)), key
    # A key the signature sees: the signature alone, as before; and a key without the mark is never.
    assert cu_evidence.key_left_the_view_as_it_was(_key("ctrl_k", sameView=True))
    assert not cu_evidence.key_left_the_view_as_it_was(_key("enter", sameText=True))
    # The classes are data, and the blind-key refusal reads the same unseen-effect keys.
    assert cu_vocabulary._UNSEEN_EFFECT_KEYS >= cu_vocabulary.CONTENT_WRITTEN_EFFECT_KEYS
    assert "enter" in cu_vocabulary._UNSEEN_EFFECT_KEYS and "ctrl_k" not in cu_vocabulary._UNSEEN_EFFECT_KEYS
