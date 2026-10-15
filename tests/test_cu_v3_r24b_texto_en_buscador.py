"""Ronda 24b, palanca «texto en el buscador no es mensaje enviado» (banco r23 c6, base sucia de c7/s13).

c6: Discord abrió con el teclado en su buscador («Buscar .wolfsoultm.4191», que dejó una ráfaga cortada), la regla de
«escribir» tecleó «prueba BAXY C6» ahí, la caja «Mensaje @Ron92» quedó vacía, el Enter lanzó una búsqueda y el final
dijo «lo envié». Cada arreglo con su contracaso: el acto (dónde se escribe), la verificación (``written`` y
``sent:``) y el respaldo de «envié».
"""

from __future__ import annotations

import re

from baxy_mind import cu_fields
from baxy_mind import cu_text_place
from baxy_mind import cu_rules
from baxy_mind import operation_floor
from baxy_mind import computer_use_finals
from baxy_mind.semantic import claims, missions

APPS = ("Steam", "Discord", "Google Chrome", "Calculadora", "Configuración", "Notepad", "Bloc de notas")

_SEARCH = {"i": 19, "kind": "ComboBox", "name": "Buscar .wolfsoultm.4191", "state": "collapsed focused",
           "value": "Buscar .wolfsoultm.4191 ﻿"}
_COMPOSER = {"i": 20, "kind": "Edit", "name": "Mensaje @Ron92", "value": "﻿"}
# The journal of c6 (22:02:27): the page's root Document is read-only, the search has the keyboard, the box is empty.
C6 = {
    "window": {"title": "@Ron92 - Discord", "process": "Discord",
               "focused": {"kind": "ComboBox", "name": "Buscar .wolfsoultm.4191", "value": "Buscar .wolfsoultm.4191 ﻿"}},
    "controls": [
        {"i": 0, "kind": "Document", "name": "@Ron92", "state": "readonly",
         "value": "https://discord.com/channels/@me/788990433829060618"},
        {"i": 2, "kind": "TreeItem", "name": "Mensajes directos", "state": "selected"},
        _SEARCH, _COMPOSER,
    ],
    "text": {},
}


def _click(label: str) -> dict:
    return {"step": 1, "operation": "input.visible.click", "ok": True, "label": label}


# ------------------------------------------------------------------------------------------------ (A) el acto
def test_c6_free_text_with_the_keyboard_on_the_search_clicks_the_message_box_first() -> None:
    step = cu_rules.deterministic_step(goal="escribir prueba BAXY C6", view=C6, history=[])
    assert step["operation"] == "input.visible.click"
    assert step["arguments"] == {"label": "Mensaje @Ron92", "index": 20}


def test_c6_redone_types_once_the_message_box_has_the_keyboard() -> None:
    landed = {**C6, "window": {**C6["window"], "focused": {"kind": "Edit", "name": "Mensaje @Ron92", "value": "﻿"}},
              "controls": [{**_SEARCH, "state": "collapsed"}, {**_COMPOSER, "state": "focused"}]}
    step = cu_rules.deterministic_step(goal="escribir prueba BAXY C6", view=landed, history=[_click("Mensaje @Ron92")])
    assert step["operation"] == "input.text.type" and step["arguments"]["text"] == "prueba BAXY C6"


def test_c6_redone_the_box_that_does_not_take_the_keyboard_stops_and_says_so() -> None:
    step = cu_rules.deterministic_step(goal="escribir prueba BAXY C6", view=C6, history=[_click("Mensaje @Ron92")])
    assert step["operation"] == "none" and step["code"] == cu_rules.FIELD_NOT_FOCUSED
    floor = operation_floor.floor_data()
    assert "computer_use_field_not_focused" in str(floor) and "computer_use_text_not_in_composer" in str(floor)


def test_contracase_the_search_said_or_a_search_goal_still_types_in_the_search() -> None:
    goal, check = missions.read_clause("escribí hola en el buscador")
    assert goal.startswith("poner ") and check == "stepDone:input.text.type"
    said = cu_rules.deterministic_step(goal=goal, view=C6, history=[], success_check=check)
    assert said["operation"] == "input.text.type" and said["arguments"]["text"] == "hola"
    assert said["arguments"].get("field") == "Buscar .wolfsoultm.4191"
    searched = cu_rules.deterministic_step(goal="buscar Hades", view=C6, history=[])
    assert searched is None or searched.get("arguments", {}).get("label") != "Mensaje @Ron92"


# Revisión 3, B1: «en Discord buscá a Ron, escribí hola y mandalo». «buscar Ron» left «ron» in the message search while
# the chat stayed @Ana's; clicking «Mensaje @Ana» by rule wrote (and, confirmed, sent) «hola» to Ana.
def _searched_by_this_mission(typed: str = "ron", held: str = "ron﻿") -> dict:
    search = {**_SEARCH, "value": held}
    return {
        "window": {"title": "@Ana - Discord", "process": "Discord",
                   "focused": {"kind": "ComboBox", "name": _SEARCH["name"], "value": held}},
        "controls": [
            {"i": 0, "kind": "Document", "name": "@Ana", "state": "readonly", "value": "https://x/channels/@me/1"},
            search, {"i": 20, "kind": "Edit", "name": "Mensaje @Ana", "value": "﻿"},
        ],
        "text": {},
        "lastTyped": {"text": typed, "atCaret": True, "intoSearch": True},
    }


def test_b1_a_search_holding_the_missions_own_text_does_not_prove_the_chat_the_model_decides() -> None:
    step = cu_rules.deterministic_step(goal="escribir hola", view=_searched_by_this_mission(), history=[])
    assert step is None


def test_b1_contracase_c6_dirty_base_left_by_another_mission_still_clicks_the_message_box() -> None:
    # c6: the search holds nothing this mission typed (its name and the empty mark), and the mission's last text went
    # into another search (the quick switcher «Ron92»): the box of the chat is clicked as before.
    dirty = {**C6, "lastTyped": {"text": "Ron92", "atCaret": True, "intoSearch": True}}
    step = cu_rules.deterministic_step(goal="escribir prueba BAXY C6", view=dirty, history=[])
    assert step["operation"] == "input.visible.click"
    assert step["arguments"] == {"label": "Mensaje @Ron92", "index": 20}
    # The mission's text as a part of another word of the search is not it.
    other = _searched_by_this_mission(typed="ron", held="ronda﻿")
    clicked = cu_rules.deterministic_step(goal="escribir hola", view=other, history=[])
    assert clicked["operation"] == "input.visible.click" and clicked["arguments"]["label"] == "Mensaje @Ana"
    # A text typed by the mission but not into a search proves nothing about the search.
    elsewhere = {**_searched_by_this_mission(), "lastTyped": {"text": "ron", "atCaret": True}}
    assert cu_rules.deterministic_step(goal="escribir hola", view=elsewhere, history=[])["operation"] == "input.visible.click"


# Revisión 3, B2: the box «Mensaje @Ron92» kept a draft of the person's; the click left the caret in it, «prueba BAXY C6»
# joined the draft and the Enter sent both.
def test_b2_a_message_box_holding_the_persons_draft_is_never_clicked_by_rule() -> None:
    drafted = {**C6, "controls": [*C6["controls"][:2], _SEARCH, {**_COMPOSER, "value": "borrador de la persona﻿"}]}
    assert cu_rules.deterministic_step(goal="escribir prueba BAXY C6", view=drafted, history=[]) is None
    # The one editable field of a form holding the person's text is not clicked by rule either.
    form = {
        "window": {"title": "Notas", "focused": {"kind": "Edit", "name": "Buscar", "value": ""}},
        "controls": [{"i": 0, "kind": "Edit", "name": "Buscar", "state": "focused", "value": ""},
                     {"i": 1, "kind": "Edit", "name": "Nota", "value": "lo que escribió la persona"}],
        "text": {},
    }
    assert cu_rules.deterministic_step(goal="escribir hola", view=form, history=[]) is None


def test_b2_contracase_an_empty_box_or_one_showing_its_own_name_is_clicked() -> None:
    for held in ("﻿", "", "  ", "Mensaje @Ron92", "​"):
        view = {**C6, "controls": [*C6["controls"][:2], _SEARCH, {**_COMPOSER, "value": held}]}
        step = cu_rules.deterministic_step(goal="escribir prueba BAXY C6", view=view, history=[])
        assert step["operation"] == "input.visible.click", held
        assert step["arguments"] == {"label": "Mensaje @Ron92", "index": 20}


def test_contracase_a_launcher_whose_only_field_is_its_search_types_at_the_caret() -> None:
    launcher = {
        "window": {"title": "Inicio", "process": "StartMenuExperienceHost",
                   "focused": {"kind": "Edit", "name": "Buscar", "value": ""}},
        "controls": [{"i": 0, "kind": "Edit", "name": "Buscar", "state": "focused", "value": ""},
                     {"i": 1, "kind": "ListItem", "name": "Bloc de notas"}],
        "text": {"top": ["Escribe aquí para buscar"]},
    }
    step = cu_rules.deterministic_step(goal="escribir notepad", view=launcher, history=[])
    assert step["operation"] == "input.text.type" and step["arguments"]["text"] == "notepad"


def test_contracase_notepad_with_the_keyboard_on_its_document_is_unchanged() -> None:
    notepad = {
        "window": {"title": "Sin título: Bloc de notas", "process": "Notepad",
                   "focused": {"kind": "Document", "name": "Editor de texto", "value": ""}},
        "controls": [{"i": 0, "kind": "Document", "name": "Editor de texto", "state": "focused", "value": ""},
                     {"i": 1, "kind": "Edit", "name": "Buscar", "value": ""}],
        "text": {},
    }
    step = cu_rules.deterministic_step(goal="escribir hola", view=notepad, history=[])
    assert step["operation"] == "input.text.type" and step["arguments"]["text"] == "hola"


def test_contracase_a_chat_without_tree_leaves_it_to_the_model_never_the_search() -> None:
    unreadable = {
        "window": {"title": "@Ron92 - Discord", "process": "Discord",
                   "focused": {"kind": "ComboBox", "name": "Buscar .wolfsoultm.4191", "value": ""}},
        "controls": [],
        "text": {"bottom": ["Enviar mensaje a @Ron92"]},
    }
    assert cu_rules.deterministic_step(goal="escribir hola", view=unreadable, history=[]) is None


def test_several_fields_and_no_message_box_leave_it_to_the_model() -> None:
    form = {
        "window": {"title": "Contacto", "focused": {"kind": "Edit", "name": "Buscar en el sitio", "value": ""}},
        "controls": [{"i": 0, "kind": "Edit", "name": "Buscar en el sitio", "state": "focused", "value": ""},
                     {"i": 1, "kind": "Edit", "name": "Nombre", "value": ""},
                     {"i": 2, "kind": "Edit", "name": "Apellido", "value": ""}],
        "text": {},
    }
    assert cu_rules.deterministic_step(goal="escribir hola", view=form, history=[]) is None


# --------------------------------------------------------------------------------------- (B) la verificación
def test_the_search_pattern_is_one_datum_for_the_mind_and_the_app() -> None:
    data = operation_floor.floor_data()["computerUse"]["searchField"]
    assert cu_fields._SEARCH_NAME.pattern == data["name"] and cu_fields._ADDRESS_NAME.pattern == data["address"]
    assert re.search(data["name"], "buscar .wolfsoultm.4191") and not re.search(data["name"], "mensaje @ron92")


def test_a_free_text_has_its_own_written_marker_apart_from_search_and_field() -> None:
    assert missions.read_clause("escribí prueba BAXY C6")[1] == missions.WRITTEN_CHECK == "stepDone:input.text.type:written"
    assert "written" not in missions.read_clause("buscá Hades")[1]
    assert missions.read_clause("escribí hola en el buscador")[1] == "stepDone:input.text.type"


# ------------------------------------------------------------------------------------------------ (C) el envío
def test_send_after_writing_asks_for_the_message_sent() -> None:
    request = missions.mission_request("en Discord andá a Ron92, escribí prueba BAXY C6 y mandalo", APPS)
    assert request is not None
    goals = [(step.goal, step.success_check) for step in request.steps]
    assert goals[-2] == ("escribir prueba BAXY C6", missions.WRITTEN_CHECK)
    # The App folds what an atom names: the text's case is not part of the check.
    assert goals[-1][0] == "enviar"
    assert goals[-1][1].casefold() == "stepDone:input.key.press:enter&sent:prueba BAXY C6".casefold()
    # Contracase: «mandalo» alone knows no text; the Enter stays its check.
    assert missions.read_clause("mandalo") == ("enviar", "stepDone:input.key.press:enter")


def test_send_rule_refuses_an_enter_on_a_search_holding_the_text() -> None:
    held = {**C6, "window": {**C6["window"], "focused": {**C6["window"]["focused"], "value": "prueba BAXY C6"}},
            "lastTyped": {"text": "prueba BAXY C6", "atCaret": True, "intoSearch": True, "otherField": True}}
    step = cu_rules.deterministic_step(goal="enviar", view=held, history=[])
    assert step["operation"] == "none" and step["code"] == cu_rules.TEXT_NOT_IN_COMPOSER


def test_contracase_send_from_the_message_box_is_still_asked_first() -> None:
    composer = {"window": {"title": "@Ron92 - Discord", "focused": {"kind": "Edit", "name": "Mensaje @Ron92", "value": "hola"}},
                "controls": [], "text": {}, "lastTyped": {"text": "hola", "atCaret": True}}
    step = cu_rules.deterministic_step(goal="enviar", view=composer, history=[])
    assert step["arguments"] == {"key": "enter", "target": "message_composer"}
    # The text went into the search but the keyboard is now in the message box: the rule does not stop.
    moved = {**composer, "lastTyped": {"text": "hola", "atCaret": True, "intoSearch": True}}
    assert cu_rules.deterministic_step(goal="enviar", view=moved, history=[])["arguments"]["target"] == "message_composer"


# ---------------------------------------------------------------------------------------- (D) «envié» respaldado
def _c6_mission(sent: bool) -> dict:
    observed = {
        "goal": "ir a ron92; luego escribir prueba BAXY C6; luego enviar", "application": "Discord", "reached": sent,
        "steps": [
            {"operation": "input.visible.click", "ok": True, "label": "@Ron92"},
            {"operation": "input.text.type", "ok": True, "text": "prueba BAXY C6"},
            {"operation": "input.key.press", "ok": True, "key": "enter", "target": "message_composer"},
        ],
        "subgoals": [
            {"goal": "ir a ron92", "application": "Discord", "reached": True},
            {"goal": "escribir prueba BAXY C6", "application": "Discord", "reached": True},
            {"goal": "enviar", "application": "Discord", "reached": sent},
        ],
    }
    return {"kind": "operation", "operation": "mission.computer.use", "polarity": "success" if sent else "failure",
            "verified": sent, "succeeded": sent, "cause": "mission_completed" if sent else "mission_failed",
            "observed": observed}


def test_an_enter_towards_the_box_backs_sent_only_when_sending_held() -> None:
    assert "enviar" in claims.unreached_qualified_acts(_c6_mission(False)["observed"])
    assert claims.unreached_qualified_acts(_c6_mission(True)["observed"]) == frozenset()
    told = "Escribí «prueba BAXY C6» y lo envié."
    assert computer_use_finals._claims_defect(told, "status", _c6_mission(False)) == "unbacked_act"
    assert computer_use_finals._claims_defect(told, "status", _c6_mission(True)) == ""


# ------------------------------------------------- revisión 1 (B3): un documento no es un buscador por su título
def _word_with_header(document: str) -> dict:
    # The Word fixture of test_cu_v3_escritura_destino (_word) with an Edit «Encabezado» without the keyboard.
    return {
        "window": {"title": f"{document} - Word", "process": "WINWORD",
                   "focused": {"kind": "Document", "name": document, "i": 50}},
        "controls": [
            {"i": 3, "kind": "Edit", "name": "Buscar en documento", "value": "Buscar en documento", "zone": "T"},
            {"i": 45, "kind": "TabItem", "name": "Inicio", "state": "selected", "zone": "T"},
            {"i": 50, "kind": "Document", "name": document, "state": "focused", "value": "Introducción al proyecto",
             "zone": "C"},
            {"i": 51, "kind": "Edit", "name": "Encabezado", "zone": "C"},
        ],
        "text": {},
    }


def test_review1_b3_a_document_titled_with_a_search_word_keeps_the_text() -> None:
    # «Búsqueda de empleo», «Ir a la playa», «Filtros de café», «Find my phone», «Search notes» are the person's
    # documents with the keyboard: the text goes into the body, never a click on another field.
    for document in ("Búsqueda de empleo", "Ir a la playa", "Filtros de café", "Find my phone", "Search notes"):
        view = _word_with_header(document)
        assert cu_fields._keyboard_on_a_search(view) is None, document
        assert cu_text_place._off_the_search(view, []) is None, document
        step = cu_rules.deterministic_step(goal="escribir hola mundo", view=view, history=[])
        assert step is None or step["operation"] != "input.visible.click", (document, step)


def test_review1_b3_contracase_a_small_document_labelled_search_and_an_edit_still_are() -> None:
    # A Document whose whole name is a search label (the Character Map's «Buscar:») is still a search, and so is an Edit
    # whose name holds a search word; with the keyboard there, the free text steps off to the one other field.
    labelled = _word_with_header("Notas")
    labelled["window"]["focused"] = {"kind": "Document", "name": "Buscar:", "i": 60}
    labelled["controls"].append({"i": 60, "kind": "Document", "name": "Buscar:", "state": "focused", "value": ""})
    labelled["controls"] = [c for c in labelled["controls"] if c.get("i") != 50]
    assert cu_fields._keyboard_on_a_search(labelled) is not None
    assert cu_text_place._off_the_search(labelled, []) == ("click", labelled["controls"][-2])
    edit = _word_with_header("Notas")
    edit["window"]["focused"] = {"kind": "Edit", "name": "Buscar en documento", "i": 3}
    edit["controls"][0]["state"] = "focused"
    edit["controls"][2]["state"] = ""
    assert cu_fields._keyboard_on_a_search(edit) is not None
    # The window's own search label is data the App reads too.
    label = operation_floor.floor_data()["computerUse"]["searchField"]["label"]
    assert re.fullmatch(label, "buscar") and not re.search(label, "busqueda de empleo")


# ------------------------------- revisión 2 (B1): el destinatario de una caja de mensaje no la vuelve buscador
_RECIPIENT_BOXES = ("Enviar mensaje a #búsqueda-de-equipo", "Message #job-search", "Message #find-a-duo",
                    "Enviar mensaje a #filtros", "Mensaje @Buscador99")


def _box_with_keyboard(name: str, value: str = "") -> dict:
    return {
        "window": {"title": "Discord", "process": "Discord", "focused": {"i": 20, "kind": "Edit", "name": name, "value": value}},
        "controls": [
            {"i": 19, "kind": "ComboBox", "name": "Buscar .wolfsoultm.4191", "state": "collapsed", "value": ""},
            {"i": 20, "kind": "Edit", "name": name, "state": "focused", "value": value},
        ],
        "text": {},
    }


def test_review2_b1_a_message_box_named_for_a_search_like_recipient_is_no_search() -> None:
    for name in _RECIPIENT_BOXES:
        view = _box_with_keyboard(name)
        assert not cu_fields._is_search_field(view["controls"][1]), name
        assert cu_fields._keyboard_on_a_search(view) is None, name
        typed = cu_rules.deterministic_step(goal="escribir hola", view=view, history=[])
        assert typed["operation"] == "input.text.type" and typed["arguments"]["text"] == "hola", (name, typed)
        # «… y mandalo»: the Enter in that box is a send, asked first by RiskPolicy, never refused as a search.
        held = {**_box_with_keyboard(name, "hola"), "lastTyped": {"text": "hola", "atCaret": True, "intoSearch": True}}
        sent = cu_rules.deterministic_step(goal="enviar", view=held, history=[])
        assert sent["operation"] == "input.key.press", (name, sent)
        assert sent["arguments"] == {"key": "enter", "target": "message_composer"}, name
        assert cu_fields._composer_with_text(held, []), name


def test_review2_b1_contracase_a_search_that_says_chat_is_still_the_search() -> None:
    whatsapp = {
        "window": {"title": "WhatsApp", "process": "WhatsApp",
                   "focused": {"i": 4, "kind": "Edit", "name": "Buscar o empezar un chat nuevo", "value": "hola"}},
        "controls": [
            {"i": 4, "kind": "Edit", "name": "Buscar o empezar un chat nuevo", "state": "focused", "value": "hola"},
            {"i": 30, "kind": "Edit", "name": "Escribe un mensaje", "value": ""},
        ],
        "text": {},
        "lastTyped": {"text": "hola", "atCaret": True, "intoSearch": True, "otherField": True},
    }
    assert cu_fields._is_search_field(whatsapp["controls"][0])
    assert cu_fields._keyboard_on_a_search(whatsapp) is not None
    step = cu_rules.deterministic_step(goal="enviar", view=whatsapp, history=[])
    assert step["operation"] == "none" and step["code"] == cu_rules.TEXT_NOT_IN_COMPOSER
    # And the search word outside a recipient still counts beside one: «Search messages in #general».
    assert cu_fields._is_search_field({"kind": "Edit", "name": "Search messages in #general"})
    data = operation_floor.floor_data()["computerUse"]["searchField"]
    assert cu_fields._COMPOSER_NAME.pattern == data["composer"] and cu_fields._RECIPIENT.pattern == data["recipient"]
