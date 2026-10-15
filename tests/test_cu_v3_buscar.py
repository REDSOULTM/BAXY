"""Lugar y clic M2, M3 y M8 (cu-v3/r3a/lugar_clic.md, rama 2) con vistas reales de la primera pasada v3.

M2: el modelo ve los controles que nombran el lugar también por su traducción, nunca las piezas de una barra de
desplazamiento, y los botones del marco al final. M3: una traducción vale como palabras contenidas en un enlace o un
ítem; en el cuadro de dirección y búsqueda vacío de una pestaña nueva se escribe el lugar, y tras escribir sin
resultado, Enter una vez. M8: un texto que es un parámetro sólo va a un campo cuyo papel encaja.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from baxy_mind import computer_use
from baxy_mind import cu_view
from baxy_mind import cu_acts
from baxy_mind import cu_languages
from baxy_mind import cu_lookup
from baxy_mind import cu_rules
from baxy_mind import cu_validate
from baxy_mind import cu_model_calls
from baxy_mind import cu_step_prompt
from baxy_mind.semantic import cu_buscar

_DATA = json.loads((Path(__file__).parent / "data" / "cu_v3_vistas_buscar.json").read_text(encoding="utf-8"))


def _view(name: str) -> dict:
    return copy.deepcopy(_DATA[name]["vista"])


def _typed(step: int, text: str) -> dict:
    return {"step": step, "operation": "input.text.type", "text": text, "ok": True}


class _Model:
    """A local model that translates labels from a table and records the step it is asked for."""

    def __init__(self, translations: dict[str, dict[str, list[str]]], step: dict | None = None) -> None:
        self.translations = translations
        self.step = step or {"act": "none"}
        self.step_payloads: list[dict] = []

    def _post_schema_object(self, payload: dict, label: str) -> object:
        user = payload["messages"][-1]["content"]
        if payload["messages"][0]["content"] == cu_model_calls.TRANSLATE_PROMPT:
            return self.translations.get(user, {"es": [], "en": []})
        self.step_payloads.append(payload)
        return self.step


# ------------------------------------------------------------------ M2: lo que ve el modelo


def test_word_insert_a_table_shows_tabla_by_its_translation() -> None:
    # t-form-3: 52 controls, the first 20 the side panel and the title bar; «Tabla» is the 31st.
    word = _view("word_insertar")
    names = computer_use._place_names("Insert a table", word, lambda label: ("Insertar tabla", "Tabla"))
    assert "Tabla" in names
    shown = cu_step_prompt.compact_view_text(word, goal="Insert a table", names=names)
    assert "«Tabla»" in shown
    # The window's frame is never what a goal inside the window looks for: with the listing cut it goes last.
    assert "«Minimizar»" not in shown and "«Maximizar»" not in shown


def test_without_the_translation_the_cut_listing_misses_tabla() -> None:
    # Contracase: the literal words alone («insert», «table») raise «Insertar» and leave «Tabla» out (the measured
    # failure: the engine pressed «Insertar» twice and never saw the table).
    word = _view("word_insertar")
    shown = cu_step_prompt.compact_view_text(word, limit_controls=25, goal="Insert a table")
    assert "«Insertar»" in shown and "«Tabla»" not in shown
    translated = cu_step_prompt.compact_view_text(word, limit_controls=25, goal="Insert a table", names=("Tabla",))
    assert "«Tabla»" in translated


def test_the_step_prompt_carries_the_translated_place() -> None:
    word = _view("word_insertar")
    model = _Model({"Insert a table": {"es": ["Insertar tabla"], "en": []}})
    computer_use.decide_step(
        model, objective="Insert a table with 4 columns and 3 rows in this Word document", goal="Insert a table",
        application="Word", success_check=None, view=word, history=[], budget_left=10, application_names=["Word"],
    )
    assert model.step_payloads and "«Tabla»" in model.step_payloads[0]["messages"][-1]["content"]


def test_a_view_that_lists_everything_asks_no_translation() -> None:
    terminal = _view("terminal")
    asked: list[str] = []
    names = computer_use._place_names("split the pane vertical", terminal, lambda label: asked.append(label) or ())
    assert asked == [] and names == ("split the pane vertical",)


def test_a_goal_word_never_raises_a_removal_above_the_place() -> None:
    word = _view("word_insertar")
    ranked = cu_step_prompt._ranked_controls(word["controls"], "insertar un comentario", 3, ("comentario",), word)
    names = [control["name"] for control in ranked]
    assert "Comentario" in names and "Eliminar comentario" not in names
    # Contracase: a goal that asks to remove it raises it.
    asked = cu_step_prompt._ranked_controls(word["controls"], "eliminar el comentario", 3, ("comentario",), word)
    assert "Eliminar comentario" in [control["name"] for control in asked]


def test_terminal_scroll_bar_buttons_are_never_listed_nor_clicked() -> None:
    # v3-40: «split the pane vertical» pressed «Aumento grande vertical», a button of the console's scroll bar.
    terminal = _view("terminal")
    shown = cu_step_prompt.compact_view_text(terminal, goal="split the pane vertical")
    assert "vertical»" not in shown.replace("«Vertical»", "")
    assert "«Nueva pestaña»" in shown and "«Vertical»" in shown
    refused = cu_validate.validate_decision(
        {"act": "click", "i": 4}, view=terminal, last_failed=None, application_names=[], history=[],
        goal="split the pane vertical",
    )
    assert refused["operation"] == "none" and refused["code"] == "scroll_part"


def test_a_goal_that_scrolls_may_press_the_scroll_bar() -> None:
    terminal = _view("terminal")
    step = cu_validate.validate_decision(
        {"act": "click", "i": 4}, view=terminal, last_failed=None, application_names=[], history=[],
        goal="desplazar la consola hacia abajo",
    )
    assert step["operation"] == "input.visible.click" and step["arguments"]["index"] == 4


def test_scroll_parts_by_name_when_the_view_has_no_rectangles() -> None:
    bare = {"controls": [{"i": 0, "kind": "Button", "name": "Line down"}, {"i": 1, "kind": "Button", "name": "Abajo"}]}
    assert cu_view._scroll_part(bare["controls"][0], bare)
    assert not cu_view._scroll_part(bare["controls"][1], bare)


# ------------------------------------------------------------------ M3: buscar


def test_the_step_prompt_opens_a_settings_control_before_searching() -> None:
    # v3-41: «iconos grandes» typed into the Control Panel's search; the option lives in «Ver por: Categoría».
    prompt = cu_step_prompt.STEP_PROMPT
    assert "collapsed" in prompt and "opción actual" in prompt and "busca contenido, no opciones" in prompt


def test_devices_and_printers_is_the_link_that_holds_its_translation() -> None:
    # v3-44: «Ver dispositivos e impresoras» on screen; the whole-name rule missed it and the English name was typed.
    panel = _view("panel_de_control")
    asked: list[str] = []

    def translate(label: str) -> tuple[str, ...]:
        asked.append(label)
        return ("Dispositivos e impresoras", "Devices and printers")

    step = cu_rules.deterministic_step(goal="ir a devices and printers", view=panel, history=[], translate=translate)
    assert step is not None and step["operation"] == "input.visible.click"
    assert step["arguments"] == {"label": "Ver dispositivos e impresoras", "index": 11}
    # Ronda 20b, palanca 8, objetivo 3: the place table now knows «devices and printers» (and the Settings page Windows
    # hands it to), and the table goes first (contract §4.4.1): the model is not asked to translate it.
    assert asked == []
    # The link holds its translation as whole words, the rule a name the table does not know still goes through.
    assert cu_languages._names_by_translation(
        {"kind": "Hyperlink", "name": "Ver dispositivos e impresoras"}, "Dispositivos e impresoras"
    )
    # The same shape with a place the table does not know: a link «Ver centro de movilidad» for «mobility center».
    mobility = _view("panel_de_control")
    mobility["controls"][12]["name"] = "Ver centro de movilidad"
    step = cu_rules.deterministic_step(
        goal="ir a mobility center", view=mobility, history=[], translate=lambda label: ("Centro de movilidad",),
    )
    assert step is not None and step["operation"] == "input.visible.click"
    assert step["arguments"] == {"label": "Ver centro de movilidad", "index": 12}
    assert step["alias"] == {"from": "mobility center", "to": "Ver centro de movilidad"}


def test_a_translation_inside_a_sentence_or_a_button_is_not_the_place() -> None:
    panel = _view("panel_de_control")
    # «Guardar copias de seguridad de tus archivos con Historial de archivos» merely mentions «copias de seguridad».
    step = cu_rules.deterministic_step(
        goal="ir a backups", view=panel, history=[], translate=lambda label: ("Copias de seguridad",),
    )
    assert step is None or step["arguments"].get("index") not in {6, 7}
    # A button holding the name among other words is no link nor item.
    assert not cu_languages._names_by_translation({"kind": "Button", "name": "Ver dispositivos"}, "Dispositivos")
    assert cu_languages._names_by_translation({"kind": "Button", "name": "Dispositivos"}, "dispositivos")


def test_new_tab_types_the_place_in_its_address_and_search_box_then_enter() -> None:
    # v3-59: Edge on a new tab, the keyboard on «Barra de direcciones y búsqueda» (empty).
    edge = _view("edge_pestana_nueva")
    first = cu_rules.deterministic_step(goal="ir a wikipedia", view=edge, history=[])
    assert first == {"operation": "input.text.type", "arguments": {"text": "wikipedia"}, "reason": cu_acts._REASON_FIND}
    typed = _view("edge_pestana_nueva")
    typed["window"]["focused"]["value"] = "wikipedia"
    typed["controls"][9]["value"] = "wikipedia"
    second = cu_rules.deterministic_step(goal="ir a wikipedia", view=typed, history=[_typed(1, "wikipedia")])
    assert second is not None and second["operation"] == "input.key.press"
    assert second["arguments"] == {"key": "enter"}


def test_enter_only_once_and_never_in_a_message_box() -> None:
    edge = _view("edge_pestana_nueva")
    edge["window"]["focused"]["value"] = "wikipedia"
    pressed = [_typed(1, "wikipedia"), {"step": 2, "operation": "input.key.press", "key": "enter", "ok": True}]
    assert not cu_lookup._submits_with_enter(edge, pressed)
    chat = {
        "window": {"title": "Chat", "process": "chat", "focused": {"kind": "Edit", "name": "Escribe un mensaje", "value": "hola"}},
        "controls": [{"i": 0, "kind": "Edit", "name": "Escribe un mensaje", "state": "focused", "value": "hola"}],
    }
    step = cu_lookup._find_step("hola", chat, [_typed(1, "hola")])
    assert step is not None and step["arguments"].get("key") != "enter"


def test_a_loaded_page_address_is_never_replaced_on_the_way() -> None:
    edge = _view("edge_pestana_nueva")
    edge["window"]["focused"]["value"] = "https://es.wikipedia.org/wiki/Valpara%C3%ADso"
    edge["controls"][9]["value"] = edge["window"]["focused"]["value"]
    step = cu_rules.deterministic_step(goal="ir a historia", view=edge, history=[])
    assert step is None or step["operation"] != "input.text.type"


# ------------------------------------------------------------------ M8: texto sin campo destino


def test_rename_text_never_goes_to_a_tab_or_a_console() -> None:
    # v3-40 turn 3: the keyboard on the tab «Windows PowerShell»; «pruebas» went to the console and was told as done.
    terminal = _view("terminal_foco_en_pestana")
    refused = cu_validate.validate_decision(
        {"act": "type", "text": "pruebas"}, view=terminal, last_failed=None, application_names=[], history=[],
        goal="renombrar la pestaña a pruebas",
    )
    assert refused["operation"] == "none" and refused["code"] == "no_text_field"
    # Nothing reports the focus (a console): a parameter has no field there either.
    unread = _view("terminal")
    refused = cu_validate.validate_decision(
        {"act": "type", "text": "pruebas"}, view=unread, last_failed=None, application_names=[], history=[],
        goal="renombrar la pestaña a pruebas",
    )
    assert refused["code"] == "no_text_field"


def test_rename_text_goes_to_the_name_field_that_has_the_keyboard() -> None:
    terminal = _view("terminal_foco_en_pestana")
    terminal["window"]["focused"] = {"kind": "Edit", "name": "Título de la pestaña", "value": "Windows PowerShell"}
    step = cu_validate.validate_decision(
        {"act": "type", "text": "pruebas"}, view=terminal, last_failed=None, application_names=[], history=[],
        goal="renombrar la pestaña a pruebas",
    )
    assert step["operation"] == "input.text.type" and step["arguments"]["text"] == "pruebas"


def test_a_document_never_takes_a_parameter_but_takes_the_persons_text() -> None:
    document = {
        "window": {"title": "Documento1 - Word", "process": "word", "focused": {"kind": "Document", "name": "Documento1"}},
        "controls": [{"i": 0, "kind": "Document", "name": "Documento1", "state": "focused"}],
    }
    refused = cu_validate.validate_decision(
        {"act": "type", "text": "casa"}, view=document, last_failed=None, application_names=[], history=[],
        goal="buscar casa",
    )
    assert refused["code"] in {"no_text_field", "search_focus_unproven"}
    written = cu_validate.validate_decision(
        {"act": "type", "text": "hola mundo"}, view=document, last_failed=None, application_names=[], history=[],
        goal="add a title to the document",
    )
    assert written["operation"] == "input.text.type"


def _typed_by_model(view: dict, goal: str, text: str) -> dict:
    return cu_validate.validate_decision(
        {"act": "type", "text": text}, view=view, last_failed=None, application_names=[], history=[], goal=goal,
    )


def test_the_persons_text_still_goes_where_the_keyboard_is() -> None:
    # Review of M8: a cell, a calculator's key and a file list take the keys as a person's would; only a parameter
    # (a new name, a search) asks for a text field.
    excel = {
        "window": {"title": "Libro1 - Excel", "process": "EXCEL", "focused": {"kind": "DataItem", "name": "A1"}},
        "controls": [
            {"i": 0, "kind": "TabItem", "name": "Inicio", "state": "selected"},
            {"i": 1, "kind": "DataItem", "name": "A1", "state": "selected focused"},
        ],
    }
    for goal in ("escribir 100 en A1", "anotar 100 en la celda A1", "put 100 in cell A1"):
        assert _typed_by_model(excel, goal, "100")["operation"] == "input.text.type", goal
    calculator = {
        "window": {"title": "Calculadora", "process": "CalculatorApp", "focused": {"kind": "Button", "name": "Igual a"}},
        "controls": [{"i": 0, "kind": "Button", "name": "Igual a", "state": "focused"}],
    }
    assert _typed_by_model(calculator, "multiplicar 12 por 3", "12*3")["operation"] == "input.text.type"
    explorer = {
        "window": {"title": "Descargas", "process": "explorer", "focused": {"kind": "ListItem", "name": "informe.pdf"}},
        "controls": [{"i": 0, "kind": "ListItem", "name": "informe.pdf", "state": "selected focused"}],
    }
    assert _typed_by_model(explorer, "ir a notas", "notas")["operation"] == "input.text.type"
    # Counter-case: a new name with the focus on a file is a parameter with no field (F2 never pressed).
    assert _typed_by_model(explorer, "renombrar informe.pdf a notas", "notas")["code"] == "no_text_field"


def test_a_document_takes_the_persons_words_in_both_languages() -> None:
    document = {
        "window": {"title": "Documento1 - Word", "process": "word", "focused": {"kind": "Document", "name": "Documento1"}},
        "controls": [{"i": 0, "kind": "Document", "name": "Documento1", "state": "focused"}],
    }
    for goal in (
        "agregar un título al documento", "ponerle un título al documento", "poner hola en el documento",
        "agregar el nombre del cliente al documento", "redactar un párrafo sobre la llamada de ayer",
        "add a title to the document", "put hello in the document", "write the client's name",
    ):
        assert _typed_by_model(document, goal, "hola")["operation"] == "input.text.type", goal
    # Counter-cases: a rename or a search heads the sub-goal in either language, said with a joining word too.
    for goal in ("renombrar el archivo a notas", "rename the file to notes", "cambiar el nombre a notas",
                 "buscar casa", "search for house", "y renombra la tab a pruebas"):
        assert _typed_by_model(document, goal, "notas")["code"] in {"no_text_field", "search_focus_unproven"}, goal


def test_a_rename_said_with_a_joining_word_still_asks_for_the_name_field() -> None:
    terminal = _view("terminal_foco_en_pestana")
    assert _typed_by_model(terminal, "y renombra la tab a pruebas", "pruebas")["code"] == "no_text_field"
    # The person's own command in the console is no parameter: it goes where the keys go.
    assert _typed_by_model(terminal, "escribir dir en la consola", "dir")["operation"] == "input.text.type"


# ------------------------------------------------------------------ M3: Enter sólo en una búsqueda que no elige sola


def _focused_field_view(name: str, value: str, *extra: dict) -> dict:
    return {
        "window": {"title": "Ventana", "process": "app", "focused": {"kind": "Edit", "name": name, "value": value}},
        "controls": [{"i": 0, "kind": "Edit", "name": name, "state": "focused", "value": value}, *extra],
    }


def test_enter_never_goes_to_a_quick_switcher_that_picks_the_highlighted_result() -> None:
    # Review of M3: in a quick switcher Enter opens the highlighted result (here a voice channel RiskPolicy would ask).
    voice = {"i": 1, "kind": "ListItem", "name": "Sala de voz (canal de voz)", "state": "selected"}
    switcher = _focused_field_view("Búsqueda rápida", "general", voice)
    assert not cu_lookup._submits_with_enter(switcher, [_typed(1, "general")])
    step = cu_lookup._find_step("general", switcher, [_typed(1, "general")])
    assert step is None or step["arguments"].get("key") != "enter"
    for name in ("¿A dónde quieres ir?", "Ir a", "Go to file", "Quick switcher"):
        assert not cu_lookup._submits_with_enter(_focused_field_view(name, "general"), [_typed(1, "general")]), name
    # A plain search box with a highlighted item in its list is no plain search either.
    assert not cu_lookup._submits_with_enter(_focused_field_view("Buscar", "general", voice), [_typed(1, "general")])
    # Counter-case: the plain search box with nothing highlighted is submitted once.
    assert cu_lookup._submits_with_enter(_focused_field_view("Buscar", "general"), [_typed(1, "general")])


def test_enter_never_submits_an_address_field_nor_a_field_that_lost_the_text() -> None:
    mail = _focused_field_view("Dirección de correo electrónico", "ana@example.com")
    assert not cu_lookup._submits_with_enter(mail, [_typed(1, "ana@example.com")])
    assert not cu_lookup._submits_with_enter(_focused_field_view("URL", "wikipedia"), [_typed(1, "wikipedia")])
    # The text did not land in the search box: no Enter on what it holds.
    assert not cu_lookup._submits_with_enter(_focused_field_view("Buscar", ""), [_typed(1, "colores")])
    assert not cu_lookup._submits_with_enter(_focused_field_view("Buscar", "otra cosa"), [_typed(1, "colores")])
    # Counter-case: the browser's address-and-search box holding what was typed (its own completion after it).
    edge = _view("edge_pestana_nueva")
    edge["window"]["focused"]["value"] = "wikipedia.org"
    edge["controls"][9]["value"] = "wikipedia.org"
    assert cu_lookup._submits_with_enter(edge, [_typed(1, "wikipedia")])


def test_a_place_of_the_browser_is_never_typed_in_the_empty_address_box() -> None:
    # Review of M3: on the new tab of v3-59, «descargas» or «historial» typed in the address-and-search box would be a
    # web search and a result named like it a false place; the engine looks elsewhere and leaves the menu to the model.
    for goal in ("ir a descargas", "ir a historial", "go to downloads", "ir a la configuración de privacidad"):
        history: list[dict] = []
        for position in range(1, 6):
            step = cu_rules.deterministic_step(goal=goal, view=_view("edge_pestana_nueva"), history=history)
            if step is None or step["operation"] != "input.key.press":
                break
            history.append({"step": position, "operation": "input.key.press", "key": step["arguments"]["key"], "ok": True})
        assert step is None or step["operation"] != "input.text.type", goal
    # Counter-cases: a site or an address is typed there.
    for goal, text in (("ir a wikipedia", "wikipedia"), ("ir a es.wikipedia.org", "es.wikipedia.org"),
                       ("ir a youtube", "youtube")):
        step = cu_rules.deterministic_step(goal=goal, view=_view("edge_pestana_nueva"), history=[])
        assert step["operation"] == "input.text.type" and step["arguments"] == {"text": text}, goal
    assert cu_buscar.browser_or_computer_place("Descargas") and not cu_buscar.browser_or_computer_place("downloads.com")
