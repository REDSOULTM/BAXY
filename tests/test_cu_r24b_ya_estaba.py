"""Ronda 24b, «ya estaba» se reconoce y se dice (banco r23 u5, n6, x10; u9 is the App's: ComputerUseYaEstabaTests).

u5: «elegí libro en blanco» over a blank «Libro1» in front clicked around and failed; n6: «abrí Word y elegí documento
en blanco» over the person's thesis lost the new document because app.open was emitted only with the application not
in front, and the model's «open» on a button with no arrow was refused five times; x10: a part reached on its first
look (Steam already on its library) was left out of the final, which said only «estoy en «Tienda»».
"""

from __future__ import annotations

import json
from pathlib import Path

from baxy_mind import computer_use as cu
from baxy_mind import cu_documents
from baxy_mind import cu_validate
from baxy_mind import cu_model_calls
from baxy_mind import cu_projection
from baxy_mind import cu_finals

NAMES = ["Excel", "Word", "Steam", "Bloc de notas"]

# Revisión 1 (B2): the real views of the round (tests/data/cu_v3_r24_vistas_reales.json), whole.
_REAL = json.loads((Path(__file__).parent / "data" / "cu_v3_r24_vistas_reales.json").read_text(encoding="utf-8"))


def _real(name: str) -> dict:
    return json.loads(json.dumps(_REAL[name]))


def _decide(objective: str, goal: str, application: str, view: dict, history: list[dict] | None = None,
            subgoal: int = 0, subgoal_count: int = 1, llm: object = None) -> dict:
    return cu._decide_step(
        llm, objective=objective, goal=goal, application=application, success_check=None, view=view,
        history=history or [], budget_left=8, application_names=NAMES, subgoal=subgoal, subgoal_count=subgoal_count,
        translator=cu_model_calls.LabelTranslator(None, enabled=False),
    )


def _sheet(title: str = "Libro1 - Excel", a1: str | None = None) -> dict:
    cell = {"i": 2, "kind": "DataItem", "name": "A1", "state": "focused"}
    if a1 is not None:
        cell["value"] = a1
    return {
        "window": {"title": title, "process": "EXCEL", "rect": {"x": 0, "y": 0, "w": 1600, "h": 900}},
        "controls": [
            {"i": 0, "kind": "TabItem", "name": "Inicio", "state": "selected"},
            {"i": 1, "kind": "ComboBox", "name": "Cuadro de nombres", "value": "A1", "state": "collapsed"},
            cell,
            {"i": 3, "kind": "TabItem", "name": "Hoja1", "state": "selected"},
        ],
    }


def _word(title: str, status: str | None = None) -> dict:
    view = {
        "window": {"title": title, "process": "WINWORD", "rect": {"x": 0, "y": 0, "w": 1600, "h": 900}},
        "controls": [
            {"i": 0, "kind": "Button", "name": "Pestaña Archivo"},
            {"i": 1, "kind": "Button", "name": "Buscar en documento"},
            {"i": 2, "kind": "SplitButton", "name": "Buscar"},
        ],
    }
    if status is not None:
        # Revisión 1 (B3): the status text's count is what reads a document whose text the view does not give.
        view["controls"].append({"i": 3, "kind": "Text", "name": status})
    return view


# ---------------------------------------------------------------- u5, n6: the new document already there or made


def test_u5_a_blank_unnamed_workbook_in_front_is_the_one_asked_for() -> None:
    # Revisión 1 (B3): the real u5 view lists no cell but the focused empty A1; the grid is never read, so «Libro1» is
    # not proved blank (the person's unsaved data may be in B2:D10): the opening makes the new one and sees it made.
    decision = _decide("en excel elegí libro en blanco", "seleccionar libro en blanco", "Excel", _sheet())
    assert decision["operation"] == "app.open", decision
    assert decision["arguments"].get("newDocument") is True
    # Read empty (the status counts zero), the same «Libro1» is the one asked for, as it already was.
    counted = _sheet()
    counted["controls"].append({"i": 4, "kind": "StatusBar", "name": "0 palabras"})
    decision = _decide("en excel elegí libro en blanco", "seleccionar libro en blanco", "Excel", counted)
    assert decision["operation"] == "done"
    assert decision["arguments"] == {"evidence": "Libro1", "already": True}


def test_contracase_a_workbook_with_text_in_a1_is_no_blank_one_and_a_new_one_is_made() -> None:
    decision = _decide("en excel elegí libro en blanco", "seleccionar libro en blanco", "Excel", _sheet(a1="hola"))
    assert decision["operation"] == "app.open"
    assert decision["arguments"].get("newDocument") is True


def test_n6_the_person_document_in_front_gets_a_new_document_by_the_opening() -> None:
    decision = _decide("abrí word y elegí documento en blanco", "seleccionar documento en blanco", "Word",
                       _word("Proyecto_Puente_v3 - Word"))
    assert decision["operation"] == "app.open"
    assert decision["arguments"].get("newDocument") is True


def test_n6_the_opening_that_made_it_closes_the_blank_item() -> None:
    made = [{"step": 1, "operation": "app.open", "ok": True, "newDocument": True}]
    decision = _decide("abrí word y elegí documento en blanco", "seleccionar documento en blanco", "Word",
                       _word("Documento1 - Word"), made)
    assert decision["operation"] == "done"
    assert decision["arguments"] == {"evidence": "Documento1"}


def test_contracase_writing_in_word_without_new_words_opens_nothing() -> None:
    decision = _decide("en word escribí hola", "escribir hola", "Word", _word("Proyecto_Puente_v3 - Word"))
    assert decision["operation"] != "app.open"


def test_contracase_the_start_page_keeps_its_offer_and_makes_one_document() -> None:
    view = {
        "window": {"title": "Word", "process": "WINWORD", "rect": {"x": 0, "y": 0, "w": 1600, "h": 900}},
        "controls": [{"i": 0, "kind": "ListItem", "name": "Documento en blanco", "rect": {"x": 100, "y": 200, "w": 120, "h": 160}}],
    }
    decision = _decide("abrí word y elegí documento en blanco", "seleccionar documento en blanco", "Word", view)
    assert decision["operation"] != "app.open"
    assert cu_documents._new_document_in_front("abrí word y elegí documento en blanco", "seleccionar documento en blanco",
                                     view, "Word", NAMES, subgoal=0) is None


def test_contracase_choosing_a_sheet_or_a_theme_stays_a_selection() -> None:
    # No new document asked for: the rule stands aside and the selection goes on as before.
    for objective, goal in (("en excel elegí la hoja2", "seleccionar hoja2"),
                            ("en excel elegí el tema oscuro", "seleccionar tema oscuro")):
        assert cu_documents._new_document_in_front(objective, goal, _sheet(), "Excel", NAMES, subgoal=0) is None, objective
        assert cu_documents._new_document_made(goal, _sheet(), [{"operation": "app.open", "ok": True, "newDocument": True}]) is None


def test_contracase_typing_into_a_new_blank_document_already_there_is_no_done() -> None:
    # The blank document asked for is in front, the sub-goal is to write in it: the writing goes on there.
    assert cu_documents._new_document_in_front("abrí un documento nuevo de word y escribí hola", "escribir hola",
                                     _word("Documento1 - Word", "0 palabras"), "Word", NAMES, subgoal=0) is None


def test_a_saved_document_and_a_numbered_title_of_a_person_are_not_blank() -> None:
    assert not cu_documents._blank_document_shown(_word("Informe 2 - Word", "0 palabras"))
    assert cu_documents._blank_document_shown(_word("Sin título - Word", "0 palabras"))
    # Revisión 1 (B3): with nothing that reads its content, «Sin título» is not proved blank.
    assert not cu_documents._blank_document_shown(_word("Sin título - Word"))


# ---------------------------------------------------------------- revisión 1, B1: a later part works on the document made


def _notepad(title: str, text: str | None) -> dict:
    return {
        "window": {"title": title, "process": "Notepad", "rect": {"x": 0, "y": 0, "w": 1400, "h": 800}},
        "controls": [
            {"i": 0, "kind": "MenuItem", "name": "Archivo"},
            {"i": 1, "kind": "Document", "name": "Editor de texto", "value": text,
             "rect": {"x": 0, "y": 90, "w": 1400, "h": 650}},
            {"i": 2, "kind": "Text", "name": f"{len(text or '')} caracteres."},
        ],
    }


class _NoModel:
    """A model that gives no step: what the rules decide is all there is."""

    def _post_schema_object(self, payload: dict, purpose: str) -> dict:
        raise RuntimeError(purpose)


SAVE_AS = "abrí un bloc de notas nuevo, escribí hola y guardalo como prueba"


def test_b1_saving_the_new_document_written_opens_no_second_one() -> None:
    view = _notepad("*Sin título - Bloc de notas", "hola")
    assert cu_documents._new_document_in_front(SAVE_AS, "guardar como prueba", view, "Bloc de notas", NAMES, subgoal=1) is None
    decision = _decide(SAVE_AS, "guardar como prueba", "Bloc de notas", view, subgoal=1, subgoal_count=2, llm=_NoModel())
    assert decision["operation"] != "app.open", decision


def test_b1_the_second_cell_goes_into_the_workbook_the_first_wrote() -> None:
    objective = "en un libro nuevo de excel escribí 5 en A1 y 7 en A2"
    view = _sheet(a1="5")
    assert cu_documents._new_document_in_front(objective, "escribir 7 en A2", view, "Excel", NAMES, subgoal=1) is None
    assert _decide(objective, "escribir 7 en A2", "Excel", view, subgoal=1, subgoal_count=2)["operation"] != "app.open"


def test_contracase_b1_the_first_part_over_a_person_document_still_makes_the_new_one() -> None:
    # The same multi-part request, its first part with the person's saved file in front: the opening makes the new one.
    decision = _decide(SAVE_AS, "escribir hola", "Bloc de notas", _notepad("notas.txt - Bloc de notas", "lista del super"),
                       subgoal=0, subgoal_count=2)
    assert decision["operation"] == "app.open", decision
    assert decision["arguments"].get("newDocument") is True


def test_contracase_b1_a_later_part_that_is_the_blank_item_still_makes_it() -> None:
    decision = _decide("abrí word y elegí documento en blanco", "seleccionar documento en blanco", "Word",
                       _word("Proyecto_Puente_v3 - Word"), subgoal=1, subgoal_count=2)
    assert decision["operation"] == "app.open", decision
    assert decision["arguments"].get("newDocument") is True


# ---------------------------------------------------------------- revisión 1, B2: unread emptiness is never asserted


def test_b2_the_person_word_draft_with_13_characters_is_no_blank_document() -> None:
    view = _real("word_panel_navegacion")
    assert cu_documents._status_count_shows_content(view) is True
    assert not cu_documents._blank_document_shown(view)
    decision = _decide("abrí word y elegí documento en blanco", "seleccionar documento en blanco", "Word", view)
    assert decision["operation"] != "done", decision


def test_b2_an_unread_document_with_no_count_is_not_taken_as_empty() -> None:
    view = _real("word_panel_navegacion")
    view["controls"] = [control for control in view["controls"] if "caracteres" not in str(control.get("name"))]
    assert cu_documents._status_count_shows_content(view) is None
    assert not cu_documents._blank_document_shown(view)


def test_contracase_b2_the_same_word_view_counting_zero_is_blank() -> None:
    view = _real("word_panel_navegacion")
    for control in view["controls"]:
        if "caracteres" in str(control.get("name")):
            control["name"] = "Mensaje de estado Documento1: 0 caracteres (valor aproximado)."
    assert cu_documents._status_count_shows_content(view) is False
    assert cu_documents._blank_document_shown(view)


def test_contracase_b2_a_readable_empty_document_is_blank_and_a_written_one_is_not() -> None:
    assert cu_documents._blank_document_shown(_notepad("Sin título - Bloc de notas", ""))
    assert not cu_documents._blank_document_shown(_notepad("Sin título - Bloc de notas", "hola"))
    unread = _notepad("Sin título - Bloc de notas", None)
    unread["controls"].pop()
    assert not cu_documents._blank_document_shown(unread)


# ---------------------------------------------------------------- n6: «open» on a button with no arrow is its click


def test_n6_open_on_a_button_with_no_arrow_is_its_click() -> None:
    view = _word("Proyecto_Puente_v3 - Word")
    decision = cu_validate._checked_act({"act": "open", "i": 0, "why": "archivo"}, view=view, last_failed=None,
                               application_names=NAMES, history=[], goal="seleccionar documento en blanco",
                               objective="abrí word y elegí documento en blanco", application="Word")
    assert decision["operation"] == "input.visible.click"
    assert decision["arguments"]["label"] == "Pestaña Archivo"
    assert "manner" not in decision["arguments"]


def test_contracase_open_on_a_split_button_still_opens_its_arrow() -> None:
    view = _word("Proyecto_Puente_v3 - Word")
    decision = cu_validate._checked_act({"act": "open", "i": 2, "why": "buscar"}, view=view, last_failed=None,
                               application_names=NAMES, history=[], goal="buscar opciones",
                               objective="abrí las opciones de buscar en word", application="Word")
    assert decision["operation"] == "input.visible.click"
    assert decision["arguments"].get("manner") == cu_validate._MANNERS["open"]


def test_contracase_open_on_a_removing_button_is_exactly_its_click() -> None:
    # The rewrite adds no way around a click's guards: «open» on «Eliminar» is the very click the model could ask
    # (the Kernel's risk policy asks before a removal, as for any click on it). Estabilización R19: «open» on a
    # hyperlink is exactly its click too, under the same guards (it was refused «cannot_open» before).
    view = _word("Proyecto_Puente_v3 - Word")
    view["controls"].append({"i": 3, "kind": "Button", "name": "Eliminar"})
    view["controls"].append({"i": 4, "kind": "Hyperlink", "name": "Ayuda en línea"})
    common = dict(view=view, last_failed=None, application_names=NAMES, history=[], goal="seleccionar documento en blanco",
                  objective="abrí word y elegí documento en blanco", application="Word")
    opened = cu_validate._checked_act({"act": "open", "i": 3, "why": "x"}, **common)
    clicked = cu_validate._checked_act({"act": "click", "label": "Eliminar", "i": 3, "why": "x"}, **common)
    assert opened == clicked
    link = cu_validate._checked_act({"act": "open", "i": 4, "why": "x"}, **common)
    assert link == cu_validate._checked_act({"act": "click", "label": "Ayuda en línea", "i": 4, "why": "x"}, **common)


def test_r19_open_on_a_control_with_nothing_to_open_is_its_click_under_its_guards() -> None:
    # Estabilización R19 (libro de vetos §5): «open» on a control with no arrow nor list was refused «cannot_open»,
    # whose text already said «para pulsarlo, click». Measured on the views the model saw (pasada r27 and banco r30):
    # v3-10 «Búsqueda de Microsoft» (an Edit), v3-32 «Sin retraso» (a Group), g1 «Chrome Legacy Window» (the pane of
    # Steam's whole page). Each is now its click, checked as one.
    window = {"title": "Steam", "process": "steamwebhelper", "rect": {"x": 0, "y": 0, "w": 1200, "h": 800}}
    view = {
        "window": window,
        "controls": [
            {"i": 0, "kind": "Pane", "name": "Chrome Legacy Window", "rect": {"x": 0, "y": 30, "w": 1200, "h": 770}},
            {"i": 1, "kind": "Edit", "name": "Buscar", "rect": {"x": 20, "y": 80, "w": 200, "h": 24}},
            {"i": 2, "kind": "Group", "name": "Sin retraso", "rect": {"x": 300, "y": 40, "w": 120, "h": 30}},
        ],
    }
    common = dict(view=view, last_failed=None, application_names=NAMES, history=[], goal="buscar Cuphead",
                  objective="abrí Steam, andá a la biblioteca y buscá Cuphead", application="Steam")
    field = cu_validate.validate_decision({"act": "open", "i": 1}, **common)
    assert field["operation"] == "input.visible.click" and "manner" not in field["arguments"]
    assert field["arguments"]["label"] == "Buscar"
    group = cu_validate.validate_decision({"act": "open", "i": 2}, **common)
    assert group["operation"] == "input.visible.click" and group["arguments"]["label"] == "Sin retraso"
    # Contracase (g1): the click on the pane that covers the whole window stays refused, now by the click's own guard.
    whole = cu_validate.validate_decision({"act": "open", "i": 0}, **common)
    assert whole["operation"] == "none" and whole["code"] == "control_covers_window"
    # Contracase: a drop-down still opens only its list, never pressed.
    combo = {**view, "controls": [*view["controls"], {"i": 3, "kind": "ComboBox", "name": "Retraso"}]}
    listed = cu_validate.validate_decision({"act": "open", "i": 3}, **{**common, "view": combo})
    assert listed["operation"] == "input.visible.click" and listed["arguments"].get("manner") == cu_validate._MANNERS["open"]


# ---------------------------------------------------------------- x10: the part found already there is told


def _x10(acted: bool, satisfied: str = "mark:biblioteca", arrived: str | None = "BIBLIOTECA") -> dict:
    first = {"goal": "ir a biblioteca", "application": "Steam", "reached": True, "stepCount": 0,
             "satisfiedBy": satisfied, "acted": acted}
    if arrived is not None:
        first["arrivedAs"] = arrived
    steps = [{"step": 1, "operation": "app.open", "ok": True, "alreadyRunning": True, "subgoal": 0}]
    if acted:
        steps.append({"step": 2, "operation": "input.visible.click", "label": "biblioteca", "name": "BIBLIOTECA",
                      "ok": True, "subgoal": 0})
    steps.append({"step": len(steps) + 1, "operation": "input.visible.click", "label": "tienda", "name": "TIENDA",
                  "ok": True, "subgoal": 1})
    return {
        "goal": "ir a biblioteca; luego ir a tienda",
        "application": "Steam",
        "reached": True,
        "chained": True,
        "satisfiedBy": "control:tienda:selected",
        "steps": steps,
        "window": {"title": "Steam", "process": "steamwebhelper"},
        "screen": {"title": "Steam", "lines": ["TIENDA", "COMUNIDAD"]},
        "subgoals": [first, {"goal": "ir a tienda", "application": "Steam", "reached": True, "stepCount": 1,
                             "satisfiedBy": "control:tienda:selected", "acted": True, "arrivedAs": "TIENDA"}],
    }


def test_x10_the_library_found_already_there_is_told_with_the_store() -> None:
    said = cu_finals.floor_sentence(_x10(acted=False), False, True)
    assert said == "Listo, ya estaba en «Biblioteca» y ahora estoy en «Tienda».", said
    seen = cu_projection.project_seen(_x10(acted=False), "es")
    assert seen["subgoals"][0]["alreadyThere"] is True
    assert seen["subgoals"][0]["arrivedAs"] == "BIBLIOTECA"


def test_contracase_x10_a_library_reached_by_a_click_is_passed_through() -> None:
    said = cu_finals.floor_sentence(_x10(acted=True), False, True)
    assert "ya estaba" not in said
    assert "«Biblioteca»" in said and "«Tienda»" in said


def test_contracase_a_weak_term_with_no_act_is_never_already() -> None:
    observed = _x10(acted=False, satisfied="page:biblioteca")
    said = cu_finals.floor_sentence(observed, False, True)
    assert "ya estaba" not in said
    assert "alreadyThere" not in cu_projection.project_seen(observed, "es")["subgoals"][0]


def test_strong_terms() -> None:
    assert cu_projection._strong_arrival("mark:biblioteca")
    assert cu_projection._strong_arrival("title:buscar")
    assert cu_projection._strong_arrival("control:=tienda:selected")
    assert not cu_projection._strong_arrival("page:biblioteca")
    assert not cu_projection._strong_arrival("control:tienda")
    assert not cu_projection._strong_arrival("model_evidence")


# ---------------------------------------------------------------- revisión 1, B3: a launched application was not «already»


def test_b3_a_place_where_the_launch_left_steam_is_never_already() -> None:
    observed = _x10(acted=False)
    observed["steps"][0]["alreadyRunning"] = False
    said = cu_finals.floor_sentence(observed, False, True)
    assert "ya estaba" not in said, said
    # Revisión 2 (B3): the library verified on its mark after the launch is told as passed through, never left out.
    assert said == "Listo, pasé por «Biblioteca» y ya estoy en «Tienda».", said
    assert "alreadyThere" not in cu_projection.project_seen(observed, "es")["subgoals"][0]


def test_contracase_b3_with_steam_already_open_it_was_already_there() -> None:
    observed = _x10(acted=False)
    assert observed["steps"][0]["alreadyRunning"] is True
    assert cu_projection.project_seen(observed, "es")["subgoals"][0]["alreadyThere"] is True
    assert cu_projection._mission_launched(observed) is False
    observed["steps"][0]["alreadyRunning"] = False
    assert cu_projection._mission_launched(observed) is True


# ---------------------------------------------------------------- revisión 1, B3: an unread surface is never blank


def test_b3_an_unread_workbook_is_no_blank_one_already_there() -> None:
    # The person's unsaved «Libro1» with data in B2:D10 and A1 focused looks the same as the real u5 view.
    assert cu_documents._document_content(_sheet()) is None
    assert not cu_documents._blank_document_shown(_sheet())


def test_b3_writing_in_a_new_workbook_over_an_unread_one_makes_the_new_one() -> None:
    decision = _decide("en excel elegí libro en blanco y escribí 5", "escribir 5", "Excel", _sheet(), subgoal_count=2)
    assert decision["operation"] == "app.open", decision
    assert decision["arguments"].get("newDocument") is True


def test_b3_a_canvas_with_no_text_is_not_read_blank() -> None:
    canvas = {
        "window": {"title": "Sin título - Paint", "process": "mspaint", "rect": {"x": 0, "y": 0, "w": 1600, "h": 900}},
        "controls": [{"i": 0, "kind": "Pane", "name": "Lienzo", "rect": {"x": 0, "y": 150, "w": 1600, "h": 700}}],
    }
    assert cu_documents._document_content(canvas) is None
    assert not cu_documents._blank_document_shown(canvas)


def test_contracase_b3_the_opening_that_made_it_closes_an_unread_new_workbook() -> None:
    # What the mission's own opening made and saw made (newDocument) is the new one, unread or not; content shown denies it.
    made = [{"step": 1, "operation": "app.open", "ok": True, "newDocument": True}]
    decision = _decide("en excel elegí libro en blanco", "seleccionar libro en blanco", "Excel", _sheet(), made)
    assert decision["operation"] == "done", decision
    assert decision["arguments"] == {"evidence": "Libro1"}
    assert cu_documents._new_document_made("seleccionar libro en blanco", _sheet(a1="hola"), made) is None


def test_contracase_b3_a_read_empty_document_is_blank_already() -> None:
    view = _notepad("Sin título - Bloc de notas", "")
    assert cu_documents._document_content(view) is False
    decision = _decide("en el bloc de notas elegí documento en blanco", "seleccionar documento en blanco",
                       "Bloc de notas", view)
    assert decision["operation"] == "done", decision
    assert decision["arguments"] == {"evidence": "Sin título", "already": True}


# ---------------------------------------------------------------- revisión 1, B4: what an earlier part's act showed


def _options() -> dict:
    def part(goal: str, satisfied: str, acted: bool, arrived: str, count: int) -> dict:
        return {"goal": goal, "application": "Steam", "reached": True, "stepCount": count, "satisfiedBy": satisfied,
                "acted": acted, "arrivedAs": arrived}

    return {
        "goal": "ir a opciones; luego ir a general; luego ir a privacidad",
        "application": "Steam",
        "reached": True,
        "chained": True,
        "satisfiedBy": "control:privacidad:selected",
        "steps": [
            {"step": 1, "operation": "app.open", "ok": True, "alreadyRunning": True, "subgoal": 0},
            {"step": 2, "operation": "input.visible.click", "label": "opciones", "name": "Opciones", "ok": True,
             "subgoal": 0},
            {"step": 3, "operation": "input.visible.click", "label": "privacidad", "name": "Privacidad", "ok": True,
             "subgoal": 2},
        ],
        "window": {"title": "Opciones", "process": "steamwebhelper"},
        "screen": {"title": "Opciones", "lines": ["General", "Privacidad"]},
        "subgoals": [
            part("ir a opciones", "title:opciones", True, "Opciones", 1),
            part("ir a general", "control:general:selected", False, "General", 0),
            part("ir a privacidad", "control:privacidad:selected", True, "Privacidad", 1),
        ],
    }


def test_b4_a_place_an_earlier_click_opened_was_never_already_there() -> None:
    observed = _options()
    assert cu_projection._mission_acted_until(observed, observed["subgoals"], 1)
    assert "alreadyThere" not in cu_projection.project_seen(observed, "es")["subgoals"][1]
    said = cu_finals.floor_sentence(observed, False, True)
    assert "ya estaba" not in said, said


def test_b4_the_steps_own_part_tells_an_earlier_act_too() -> None:
    observed = _options()
    observed["subgoals"][0]["acted"] = False  # only the click step (subgoal 0) tells it
    assert cu_projection._mission_acted_until(observed, observed["subgoals"], 1)
    assert "alreadyThere" not in cu_projection.project_seen(observed, "es")["subgoals"][1]


def test_contracase_b4_with_no_act_before_the_part_closed_it_was_already_there() -> None:
    # x10's shape: the first part reached with no act, the act came after it (a later part's step).
    observed = _x10(acted=False)
    assert not cu_projection._mission_acted_until(observed, observed["subgoals"], 0)
    assert cu_projection.project_seen(observed, "es")["subgoals"][0]["alreadyThere"] is True


# ---------------------------------------------------------------- revisión 2, B1: only the new document asked for


def _budget() -> dict:
    return {
        "window": {"title": "Presupuesto - Excel", "process": "EXCEL", "rect": {"x": 0, "y": 0, "w": 1600, "h": 900}},
        "controls": [
            {"i": 0, "kind": "TabItem", "name": "Inicio", "state": "selected",
             "rect": {"x": 10, "y": 40, "w": 60, "h": 24}},
            {"i": 1, "kind": "TabItem", "name": "Hoja1", "state": "selected",
             "rect": {"x": 10, "y": 860, "w": 60, "h": 24}},
            {"i": 2, "kind": "Button", "name": "Nueva hoja", "rect": {"x": 80, "y": 860, "w": 24, "h": 24}},
        ],
    }


NAMES_FILES = [*NAMES, "Explorador de archivos"]


def test_b1r2_a_new_sheet_in_excel_is_the_view_command_never_a_new_workbook() -> None:
    view = _budget()
    for objective in ("en excel agregá una hoja nueva", "crea una hoja nueva en excel"):
        assert cu_documents._new_document_in_front(objective, "agregar una hoja nueva", view, "Excel", NAMES, subgoal=0) is None
    assert cu_documents._new_document_in_front("en word agregá una hoja nueva", "agregar una hoja nueva",
                                     _word("Informe - Word", "120 palabras"), "Word", NAMES, subgoal=0) is None
    decision = _decide("en excel agregá una hoja nueva", "agregar una hoja nueva", "Excel", view)
    assert decision["operation"] == "input.visible.click", decision
    assert decision["arguments"]["label"] == "Nueva hoja"


def test_b1r2_a_new_file_in_the_file_explorer_opens_no_second_window() -> None:
    view = {
        "window": {"title": "Documentos - Explorador de archivos", "process": "explorer",
                   "rect": {"x": 0, "y": 0, "w": 1400, "h": 800}},
        "controls": [
            {"i": 0, "kind": "SplitButton", "name": "Nuevo", "rect": {"x": 10, "y": 60, "w": 60, "h": 30}},
            {"i": 1, "kind": "ListItem", "name": "informe.docx", "rect": {"x": 300, "y": 200, "w": 400, "h": 22}},
        ],
    }
    objective = "en el explorador de archivos crea un archivo nuevo"
    assert cu_documents._new_document_in_front(objective, "crear un archivo nuevo", view, "Explorador de archivos", NAMES_FILES,
                                     subgoal=0) is None
    decision = cu._decide_step(
        _NoModel(), objective=objective, goal="crear un archivo nuevo", application="Explorador de archivos",
        success_check=None, view=view, history=[], budget_left=8, application_names=NAMES_FILES, subgoal=0,
        subgoal_count=1, translator=cu_model_calls.LabelTranslator(None, enabled=False),
    )
    assert decision["operation"] != "app.open", decision
    # A file manager's content view is a folder, never a document: «un documento nuevo» there opens nothing either.
    files = {**view, "controls": [*view["controls"], {"i": 2, "kind": "HeaderItem", "name": "Fecha de modificación"}]}
    assert cu_documents._new_document_in_front("en el explorador de archivos crea un documento nuevo", "crear un documento nuevo",
                                     files, "Explorador de archivos", NAMES_FILES, subgoal=0) is None


def test_contracase_b1r2_a_new_workbook_over_the_person_book_is_still_made() -> None:
    # «libro» names the whole document Excel makes on its New command; «Nueva hoja» makes a part of the person's book.
    decision = _decide("en excel creá un libro nuevo", "crear un libro nuevo", "Excel", _budget())
    assert decision["operation"] == "app.open", decision
    assert decision["arguments"].get("newDocument") is True
    decision = _decide("en excel elegí libro en blanco", "crear libro en blanco", "Excel", _budget())
    assert decision["operation"] == "app.open", decision


# ---------------------------------------------------------------- revisión 2, B2: a blank item is created, and said so


def test_b2r2_choosing_a_blank_item_is_planned_as_its_creation() -> None:
    from baxy_mind.semantic import missions

    goal, check = missions.read_clause("elegí documento en blanco")
    assert goal == "crear documento en blanco", goal
    assert "stepDone:input.visible.click:=documento en blanco" in check
    assert ":selected" not in check and ":on" not in check
    # Counter-case: an item that is no blank one stays a selection.
    goal, check = missions.read_clause("elegí la hoja2")
    assert goal == "seleccionar hoja2" and "control:=hoja2:selected" in check


def _made(goal: str, steps: list[dict], title: str = "Documento1 - Word") -> dict:
    return {
        "goal": goal, "application": "Word", "reached": True, "satisfiedBy": "model_evidence", "steps": steps,
        "window": {"title": title, "process": "WINWORD"}, "screen": {"title": title, "lines": []},
    }


_OPENED_NEW = {"step": 1, "operation": "app.open", "appId": "Word", "ok": True, "newDocument": True}


def test_b2r2_the_final_says_the_document_the_opening_made() -> None:
    said = cu_finals.floor_sentence(_made("crear documento en blanco", [_OPENED_NEW]), False, True)
    assert said == "Listo, creé «Documento1».", said
    english = cu_finals.floor_sentence(_made("crear documento en blanco", [_OPENED_NEW]), True, True)
    assert english == "Done, I created «Documento1».", english
    # The mind still closes the creating part on the opening that made it.
    made = [{"step": 1, "operation": "app.open", "ok": True, "newDocument": True}]
    decision = _decide("abrí word y elegí documento en blanco", "crear documento en blanco", "Word",
                       _word("Documento1 - Word"), made)
    assert decision["operation"] == "done" and decision["arguments"] == {"evidence": "Documento1"}


def test_b2r2_a_chained_creation_keeps_the_final_by_parts() -> None:
    observed = _made("ir a inicio; luego crear documento en blanco", [
        {"step": 1, "operation": "input.visible.click", "label": "inicio", "name": "Inicio", "ok": True, "subgoal": 0},
        {**_OPENED_NEW, "step": 2, "subgoal": 1},
    ])
    observed["chained"] = True
    observed["subgoals"] = [
        {"goal": "ir a inicio", "application": "Word", "reached": True, "stepCount": 1,
         "satisfiedBy": "control:inicio:selected", "acted": True, "arrivedAs": "Inicio"},
        {"goal": "crear documento en blanco", "application": "Word", "reached": True, "stepCount": 1,
         "satisfiedBy": "model_evidence", "acted": True},
    ]
    said = cu_finals.floor_sentence(observed, False, True)
    assert said.endswith("creé «Documento1».") and "elegí" not in said, said


def test_contracase_b2r2_the_offer_clicked_on_a_start_page_is_told_too() -> None:
    # Revisión 3 (B1): the offer's click is told, as chosen: the click's name proves no new document (another
    # «Documento1» may have been there); the click whose receipt recorded the document it made is told created.
    click = {"step": 2, "operation": "input.visible.click", "label": "documento en blanco", "name": "Documento en blanco",
             "ok": True}
    said = cu_finals.floor_sentence(_made("crear documento en blanco", [{"step": 1, "operation": "app.open", "ok": True}, click]),
                             False, True)
    assert said == "Listo, elegí «Documento en blanco».", said
    recorded = {**click, "createdDocument": "Sin título"}
    said = cu_finals.floor_sentence(_made("crear documento en blanco", [{"step": 1, "operation": "app.open", "ok": True}, recorded],
                                   title="Sin título - Word"), False, True)
    assert said == "Listo, creé «Sin título».", said


def test_contracase_b2r2_nothing_made_is_never_said_created() -> None:
    # The blank document already there (no act) and a plain opening made nothing: no «creé».
    for steps in ([], [{"step": 1, "operation": "app.open", "ok": True}]):
        said = cu_finals.floor_sentence(_made("crear documento en blanco", steps), False, True)
        assert "creé" not in said, said
    assert cu_finals._created_document([_OPENED_NEW], {"window": {"title": "Word"}}) == ""


# ---------------------------------------------------------------- revisión 3, B1: only a new document is «creé»


def _explorer_folder(goal: str) -> dict:
    observed = _made(goal, [
        {"step": 1, "operation": "app.open", "appId": "Explorador de archivos", "ok": True, "alreadyRunning": True},
        {"step": 2, "operation": "input.visible.click", "label": "nuevo", "name": "Nuevo", "ok": True},
        {"step": 3, "operation": "input.visible.click", "label": "carpeta", "name": "Carpeta", "ok": True},
    ], title="Proyectos - Explorador de archivos")
    observed["application"] = "Explorador de archivos"
    observed["window"]["process"] = "explorer"
    return observed


def test_b1r3_creating_a_folder_never_names_the_folder_in_front() -> None:
    # Sonda de la revisión 3: «creá una carpeta», clicks on «Nuevo» and «Carpeta» judged by the model alone, ended
    # «Listo, creé «Proyectos».»; the base's cautious final comes back.
    said = cu_finals.floor_sentence(_explorer_folder("crear carpeta"), False, True)
    assert said == ("Llevo dos pasos en «Explorador de archivos», pero la pantalla todavía no muestra que haya quedado "
                    "hecho."), said
    for goal in ("crear documento de texto", "crear una nota", "crear vacia", "crear fila vacia"):
        assert "creé" not in cu_finals.floor_sentence(_explorer_folder(goal), False, True), goal


def test_b1r3_a_blank_offer_over_the_person_document_is_never_created() -> None:
    click = {"step": 2, "operation": "input.visible.click", "label": "presentacion en blanco",
             "name": "Presentación en blanco", "ok": True}
    observed = _made("crear presentacion en blanco", [{"step": 1, "operation": "app.open", "ok": True}, click],
                     title="Ventas Q3 - PowerPoint")
    for english in (False, True):
        said = cu_finals.floor_sentence(observed, english, True)
        assert "Ventas Q3" not in said and "creé" not in said and "created" not in said, said
    # Not even an opening that made a new document names the person's document when that one is in front.
    assert cu_finals._created_document([_OPENED_NEW], {"window": {"title": "Informe - Word"}}) == ""
    # Nor a click whose recorded document is another one.
    other = {**click, "createdDocument": "Sin título"}
    assert cu_finals._created_document([other], {"window": {"title": "Documento2 - Word"}}) == ""


def test_b1r3_a_blank_page_in_a_named_document_is_chosen_never_created() -> None:
    # Escenario 2: «en word elegí la página en blanco» over «Informe - Word»: Insertar > «Página en blanco».
    from baxy_mind.semantic import missions

    goal, _ = missions.read_clause("elegí la página en blanco")
    assert not goal.startswith("crear") and "pagina en blanco" in goal, goal
    steps = [
        {"step": 1, "operation": "app.open", "ok": True, "alreadyRunning": True},
        {"step": 2, "operation": "input.visible.click", "label": "insertar", "name": "Insertar", "ok": True},
        {"step": 3, "operation": "input.visible.click", "label": "pagina en blanco", "name": "Página en blanco", "ok": True},
    ]
    observed = _made("crear pagina en blanco", steps, title="Informe - Word")
    observed["satisfiedBy"] = "stepDone:input.visible.click:=pagina en blanco"
    for english in (False, True):
        said = cu_finals.floor_sentence(observed, english, True)
        assert "Informe" not in said and "creé" not in said and "created" not in said, said
    observed["goal"] = "seleccionar pagina en blanco"
    assert cu_finals.floor_sentence(observed, False, True) == "Listo, elegí «Página en blanco».", observed


def test_contracase_b1r3_the_new_document_the_opening_made_is_still_created() -> None:
    assert cu_finals._created_document([_OPENED_NEW], {"window": {"title": "Documento1 - Word"}}) == "Documento1"
    said = cu_finals.floor_sentence(_made("crear libro en blanco", [_OPENED_NEW], title="Libro1 - Excel"), False, True)
    assert said == "Listo, creé «Libro1».", said


# ---------------------------------------------------------------- revisión 3, B2: only a whole document is «crear»


def test_b2r3_choosing_an_empty_thing_stays_a_selection() -> None:
    from baxy_mind.semantic import missions

    for said in ("seleccioná la carpeta vacía", "seleccioná la fila vacía", "elegí la página en blanco",
                 "elegí el diseño en blanco", "select the empty folder"):
        goal, _ = missions.read_clause(said)
        assert goal.startswith("seleccionar"), (said, goal)
    for name in ("carpeta vacia", "fila vacia", "pagina en blanco", "diseno en blanco", "vacia", "en blanco",
                 "empty folder", "documento de texto", "documento nuevo"):
        assert not missions.names_a_blank_document(name), name


def test_contracase_b2r3_a_whole_blank_document_is_still_its_creation() -> None:
    from baxy_mind.semantic import missions

    for said, goal in (("elegí documento en blanco", "crear documento en blanco"),
                       ("elegí libro en blanco", "crear libro en blanco"),
                       ("elegí la presentación en blanco", "crear presentacion en blanco"),
                       ("select a blank workbook", "crear blank workbook")):
        assert missions.read_clause(said)[0] == goal, said
        assert missions.names_a_blank_document(goal.removeprefix("crear "))
        # The floor's «create» part names exactly what the plan names created (the App reads the same data).
        assert cu_finals._PART_GOALS["create"].match(goal) is not None, goal
    for goal in ("crear carpeta", "crear documento de texto", "crear una nota", "crear vacia", "crear pagina en blanco"):
        assert cu_finals._PART_GOALS["create"].match(goal) is None, goal
