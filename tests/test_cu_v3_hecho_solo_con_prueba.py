"""Ronda 22, palanca «hecho solo con prueba» (uso real, pasada r18).

t4-c13 «en el word que tengo abierto ponle negrita al texto que tengo seleccionado»: el modelo eligió dos veces
``{"act":"type","text":"Ctrl+B","field":""}`` (model_calls t4 req 161-162) y el texto se tecleó sobre la selección de la
persona; luego citó «DOCUMENTO DE SOLO LECTURA» como la negrita aplicada. t4-c06 «crea un blank workbook»: un clic en
«Nuevo» (la galería) y la cita «Excel | Inicio | 1 | Nuevo | 2…» valió como prueba. t3-c18 t2 y t3-c19 t3: el suelo dijo
«Listo, lo hice en X» con la prueba débil del modelo. Las vistas son las que el modelo vio, recortadas a lo que se juzga.
"""

from __future__ import annotations

from baxy_mind import cu_first_look
from baxy_mind import cu_evidence
from baxy_mind import cu_validate
from baxy_mind import cu_finals
from baxy_mind import computer_use_finals
from baxy_mind import compose_payload
from baxy_mind import deterministic_finals
from baxy_mind import payload_fact_checks
from baxy_mind import visible_defect

_WORD_GOAL = "en el word que tengo abierto ponle negrita al texto que tengo seleccionado"

# t4 req 161: la ventana del documento recuperado, el foco en la pestaña «Inicio».
_WORD_VIEW = {
    "window": {"title": "Documento1  -  Autorecuperado - Word", "process": "WINWORD"},
    "controls": [
        {"i": 2, "kind": "Edit", "name": "Buscar en documento", "value": "Buscar en documento", "zone": "L"},
        {"i": 10, "kind": "Button", "name": "Guardar", "zone": "TR"},
        {"i": 20, "kind": "TabItem", "name": "Inicio", "state": "selected focused", "zone": "TL"},
        {"i": 21, "kind": "TabItem", "name": "Insertar", "zone": "TL"},
        {"i": 40, "kind": "Button", "name": "Negrita", "state": "off", "zone": "TL"},
    ],
    "text": {"TL": ["Autoguardado", "Pegar", "Fuente", "ARCHIVO NO GUARDADO RECUPERADO"], "R": ["Informe semanal"]},
}


def _validate(raw: dict, view: dict, history: list[dict], goal: str, objective: str | None = None) -> dict:
    return cu_validate.validate_decision(
        raw, view=view, last_failed=None, application_names=(), history=history, goal=goal, objective=objective or goal,
    )


def _with_body(value: str) -> dict:
    """The same window with the keyboard on the document's body (the person's text, selected)."""

    view = {**_WORD_VIEW, "controls": [
        {**control, "state": "selected"} if control.get("i") == 20 else control for control in _WORD_VIEW["controls"]
    ]}
    view["controls"] = [*view["controls"], {"i": 50, "kind": "Document", "name": "Página 1", "value": value,
                                            "state": "focused", "zone": "C"}]
    return view


# ---------------------------------------------------------------- (a) a key combination is never typed as text


def test_t4_c13_the_name_of_a_key_combination_is_never_typed() -> None:
    decision = _validate({"act": "type", "text": "Ctrl+B", "field": ""}, _WORD_VIEW, [], _WORD_GOAL)
    assert decision["operation"] == "none"
    assert decision["code"] == "typed_chord"


def test_a_key_combination_named_into_a_field_is_not_typed_either() -> None:
    for text in ("ctrl + n", "Alt+F4", "Shift-Tab", "Ctrl+Shift+S"):
        decision = _validate({"act": "type", "text": text, "field": "Buscar en documento"}, _WORD_VIEW, [], _WORD_GOAL)
        assert decision["code"] == "typed_chord", text


def test_contracase_a_quoted_combination_the_request_writes_is_typed() -> None:
    goal = "escribe \"Ctrl+B\" en el documento"
    decision = _validate({"act": "type", "text": "Ctrl+B"}, _with_body("Atajos: "), [], goal)
    assert decision["operation"] == "input.text.type"


def test_contracase_a_catalog_key_the_goal_asks_for_is_still_pressed() -> None:
    decision = _validate({"act": "key", "key": "ctrl_s"}, _WORD_VIEW, [], "pulsa Ctrl+S")
    assert decision["operation"] == "input.key.press"


def test_contracase_a_text_with_a_plus_sign_is_no_combination() -> None:
    decision = _validate({"act": "type", "text": "2+3"}, {"window": {"title": "Calculadora", "process": "CalculatorApp"},
                                                         "controls": []}, [], "calcular 2+3")
    assert decision.get("code") != "typed_chord"


# ---------------------------------------------------------------- (b) writing in a document stays the model's choice
# Revisión 3 de r22 (bloqueante B2): the veto «document_not_written» (a goal whose verbs a list did not read as writing
# typed nothing in a document) is retired: it refused drafting a list, a poem or a letter in an empty, new document.
# The combination typed as text (t4-c13) stays refused by (a). These goals keep typing, as in the base.

_REPORT = "Informe semanal\nLínea dos"


def _notepad(value: str) -> dict:
    return {"window": {"title": "Sin título - Bloc de notas", "process": "Notepad"},
            "controls": [{"i": 0, "kind": "Document", "name": "Editor de texto", "value": value, "state": "focused"}]}


def test_drafting_content_types_in_an_empty_or_written_document() -> None:
    for view in (_notepad(""), _notepad("Querido Juan:"), _with_body(""), _with_body("Querido Juan:")):
        for goal, text in (
            ("haz una lista con pan, leche y huevos", "pan\nleche\nhuevos"),
            ("haz una lista con pan, leche y huevos", "- pan\n- leche\n- huevos"),
            ("haz una lista de compras", "- pan\n- leche"),
            ("crea un poema en word", "La luna sobre el mar"),
            ("hazme una carta para mi jefe", "Estimado jefe:"),
            ("genera un resumen del texto", "El informe resume la semana."),
            ("termina la frase", "te escribo para saludarte."),
            ("crea una nota con la lista de compras", "pan, leche"),
        ):
            decision = _validate({"act": "type", "text": text}, view, [], goal)
            assert decision["operation"] == "input.text.type", (goal, text, decision)
            assert decision["arguments"]["text"].split() == text.split()


def test_contracase_goals_that_write_their_text_still_type_in_the_document() -> None:
    for goal, text in (
        ("reemplaza lo seleccionado con la fecha de hoy", "9 de octubre de 2026"),
        ("traduce al inglés el texto seleccionado", "Weekly report"),
        ("reemplaza el texto seleccionado por 'Informe mensual'", "Informe mensual"),
        ("poner hola en el documento", "hola"),
        ("agregar un título al documento", "Informe"),
        ("escribe \"Ctrl+B\" en el documento", "Ctrl+B"),
        ("write the date in word", "October 9, 2026"),
    ):
        decision = _validate({"act": "type", "text": text}, _with_body(_REPORT), [], goal)
        assert decision["operation"] == "input.text.type", (goal, text, decision)
        assert decision["arguments"]["text"] == text


def test_contracase_a_titled_text_still_goes_to_the_title_it_names() -> None:
    view = {**_WORD_VIEW, "controls": [*_WORD_VIEW["controls"], {"i": 51, "kind": "Edit", "name": "Título", "value": "",
                                                                "zone": "C"}]}
    decision = _validate({"act": "type", "text": "Proyecto final"}, view, [], "ponle 'Proyecto final' de título")
    assert decision["operation"] == "input.text.type"
    assert decision["arguments"]["field"] == "Título"


def test_contracase_a_field_that_has_the_keyboard_is_no_document() -> None:
    # The word «selección» decides nothing: a date box with the keyboard takes the date beside a page with text.
    view = {"window": {"title": "Formulario", "process": "msedge"},
            "controls": [{"i": 3, "kind": "Edit", "name": "Fecha", "state": "focused"},
                         {"i": 0, "kind": "Document", "name": "Formulario", "value": "Inscripción"}]}
    decision = _validate({"act": "type", "text": "9/10/2026"}, view, [],
                         "en el formulario elige la fecha en el cuadro de selección de fecha")
    assert decision["operation"] == "input.text.type"


def test_contracase_writing_hola_in_the_notepad_types_in_its_body() -> None:
    view = {
        "window": {"title": "Sin título - Bloc de notas", "process": "Notepad"},
        "controls": [{"i": 0, "kind": "Document", "name": "Editor de texto", "value": "lista: pan", "state": "focused"}],
    }
    decision = _validate({"act": "type", "text": "hola"}, view, [], "escribe 'hola' en el bloc de notas")
    assert decision["operation"] == "input.text.type"
    assert decision["arguments"]["text"] == "hola"


def test_contracase_a_goal_with_no_document_keeps_typing_at_the_focus() -> None:
    view = {"window": {"title": "Calculadora", "process": "CalculatorApp"}, "controls": []}
    assert _validate({"act": "type", "text": "2+3"}, view, [], "calcular 2+3")["operation"] == "input.text.type"


# ---------------------------------------------------------------- (c) the citation relates to the goal


# t4 req 113: «crea un blank workbook» after the click on «Nuevo» of Excel's start page.
def _excel_after_new() -> dict:
    view = {
        "window": {"title": "Excel", "process": "EXCEL"},
        "controls": [
            {"i": 5, "kind": "ListItem", "name": "Inicio", "zone": "TL"},
            {"i": 6, "kind": "ListItem", "name": "Nuevo", "state": "selected focused", "zone": "TL"},
            {"i": 7, "kind": "ListItem", "name": "Abrir", "zone": "TL"},
            {"i": 10, "kind": "ListItem", "name": "Libro en blanco", "zone": "TL"},
            {"i": 11, "kind": "Edit", "name": "Buscar plantillas en línea", "zone": "C"},
        ],
        "text": {"TL": ["Excel", "Inicio", "1", "Nuevo", "2", "3", "4", "Abrir", "5", "6"], "L": ["Libro en blanco"]},
    }
    before = {
        "window": {"title": "Excel", "process": "EXCEL"},
        "controls": [
            {"i": 5, "kind": "ListItem", "name": "Inicio", "state": "selected", "zone": "TL"},
            {"i": 6, "kind": "ListItem", "name": "Nuevo", "zone": "TL"},
            {"i": 7, "kind": "ListItem", "name": "Abrir", "zone": "TL"},
            {"i": 10, "kind": "ListItem", "name": "Libro en blanco", "zone": "TL"},
        ],
        "text": {"TL": ["Excel", "Inicio", "Nuevo", "Abrir"], "L": ["Libro en blanco"]},
    }
    view["firstLook"] = "\n".join(cu_first_look.look_parts(before))
    return view


_CLICK_NEW = {"step": 1, "operation": "input.visible.click", "ok": True, "label": "Nuevo", "changed": True,
              "surfaceChanged": True}


def test_t4_c13_a_read_only_notice_is_no_proof_of_the_bold() -> None:
    view = {**_WORD_VIEW, "text": {**_WORD_VIEW["text"], "TL": [*_WORD_VIEW["text"]["TL"], "@ DOCUMENTO DE SOLO LECTURA",
                                                             "DOCUMENTO DE SOLO LECTURA"]}}
    view["firstLook"] = "\n".join(cu_first_look.look_parts(_WORD_VIEW))
    typed = {"step": 1, "operation": "input.key.press", "ok": True, "key": "ctrl_n", "changed": True, "surfaceChanged": True}
    decision = _validate({"act": "done", "evidence": "@ DOCUMENTO DE SOLO LECTURA | DOCUMENTO DE SOLO LECTURA"}, view,
                         [typed], _WORD_GOAL)
    assert decision["operation"] != "done"


def test_contracase_a_notice_that_says_the_goal_still_proves_it() -> None:
    view = {**_WORD_VIEW, "text": {**_WORD_VIEW["text"], "TL": [*_WORD_VIEW["text"]["TL"], "DOCUMENTO DE SOLO LECTURA"]}}
    view["firstLook"] = "\n".join(cu_first_look.look_parts(_WORD_VIEW))
    pressed = {"step": 1, "operation": "input.visible.click", "ok": True, "label": "Solo lectura", "changed": True}
    assert not cu_evidence._unrelated_evidence("DOCUMENTO DE SOLO LECTURA", view, [pressed], "abre el documento en solo lectura")


def test_contracase_the_control_the_goal_names_now_on_proves_it() -> None:
    first = "\n".join(cu_first_look.look_parts(_WORD_VIEW))
    view = {**_WORD_VIEW, "controls": [
        {**control, "state": "on"} if control.get("name") == "Negrita" else control for control in _WORD_VIEW["controls"]
    ], "firstLook": first}
    click = {"step": 1, "operation": "input.visible.click", "ok": True, "label": "Negrita", "changed": True,
             "surfaceChanged": True}
    decision = _validate({"act": "done", "evidence": "Negrita"}, view, [click], _WORD_GOAL)
    assert decision["operation"] == "done"


def test_contracase_an_alias_of_data_relates_blank_and_en_blanco() -> None:
    view = _excel_after_new()
    view["window"] = {"title": "Libro1 - Excel", "process": "EXCEL"}
    view["text"] = {"TL": ["Libro1 - Excel", "Libro en blanco abierto"]}
    click = {**_CLICK_NEW, "label": "Libro en blanco"}
    assert not cu_evidence._unrelated_evidence("Libro en blanco abierto", view, [click], "crea un blank workbook")


def test_contracase_a_created_folder_informe_still_proves_its_goal() -> None:
    assert not cu_evidence._unrelated_evidence(
        "informe", {"window": {"title": "Documentos", "process": "explorer"},
                    "controls": [{"i": 0, "kind": "ListItem", "name": "informe"}], "firstLook": "Documentos"},
        [], "crear una carpeta llamada informe",
    )


def test_contracase_a_tab_now_selected_by_the_act_still_proves_choosing_it() -> None:
    first = {"window": {"title": "Presentación1 - PowerPoint", "process": "POWERPNT"},
             "controls": [{"i": 0, "kind": "TabItem", "name": "Transiciones"}, {"i": 1, "kind": "TabItem", "name": "Inicio",
                                                                                "state": "selected"}]}
    view = {**first, "controls": [{"i": 0, "kind": "TabItem", "name": "Transiciones", "state": "selected"},
                                  {"i": 1, "kind": "TabItem", "name": "Inicio"}],
            "firstLook": "\n".join(cu_first_look.look_parts(first))}
    click = {"step": 1, "operation": "input.visible.click", "ok": True, "label": "Transiciones", "changed": True}
    assert not cu_evidence._unrelated_evidence("Transiciones", view, [click], "abrir la pestaña transiciones")


# ---------------------------------------------------------------- (d) the floor never says done on a weak proof


def _observed(satisfied_by: str | None, steps: int = 2) -> dict:
    observed = {
        "goal": "elegir el modo decimal", "application": "Calculadora", "reached": True,
        "window": {"title": "Calculadora", "process": "CalculatorApp"},
        "steps": [{"operation": "app.open", "appId": "Calculadora", "ok": True}, *[
            {"operation": "input.visible.click", "label": f"Paso {index}", "ok": True, "changed": True}
            for index in range(steps)
        ]],
    }
    if satisfied_by is not None:
        observed["satisfiedBy"] = satisfied_by
    return observed


def test_t3_c18_the_floor_counts_the_steps_on_the_models_own_evidence() -> None:
    assert cu_finals.floor_sentence(_observed("model_evidence"), False, True) == (
        "Llevo dos pasos en «Calculadora», pero la pantalla todavía no muestra que haya quedado hecho.")
    assert cu_finals.floor_sentence(_observed("model_evidence", 1), True, True) == (
        "I'm one step into «Calculadora», but the screen doesn't show it done yet.")
    assert "Listo" not in cu_finals.floor_sentence(_observed("control:decimal:current|title:decimal"), False, True)
    assert "Listo" not in cu_finals.floor_sentence(_observed("similar:decimal"), False, True)


def test_contracase_a_strong_proof_still_says_done() -> None:
    assert cu_finals.floor_sentence(_observed("control:decimal:current"), False, True) == "Listo, lo hice en «Calculadora»."
    assert cu_finals.floor_sentence(_observed("title:decimal"), True, True) == "Done, I did it in «Calculadora»."
    assert cu_finals.floor_sentence(_observed(None), False, True) == "Listo, lo hice en «Calculadora»."


def test_a_weak_sub_goal_makes_the_whole_mission_weak() -> None:
    observed = _observed("control:decimal:current")
    observed["subgoals"] = [
        {"goal": "abrir el menú", "reached": True, "satisfiedBy": "control:menu:current"},
        {"goal": "elegir el modo decimal", "reached": True, "satisfiedBy": "model_evidence"},
    ]
    assert "Listo" not in cu_finals.floor_sentence(observed, False, True)


def _mission(observed: dict) -> dict:
    return {"kind": "operation", "operation": "mission.computer.use", "polarity": "success", "verified": True,
            "succeeded": True, "cause": "mission_completed", "observed": observed}


def test_the_weak_done_template_passes_the_book_of_acts() -> None:
    # Revisión 1 de r22 (hallazgo d): after a draft dies on unbacked_act the composer publishes the template only when
    # it is publishable; «Hice 2 pasos» read «2» as a thing done and «I took» is no lemma of the book.
    import json

    from baxy_mind.semantic import claims

    assert claims.template_suffices("unbacked_act", "mission.computer.use")
    for count in (1, 2, 3, 7, 10, 12):
        situation = _mission(_observed("model_evidence", count))
        facts = {"situation": json.dumps(situation, ensure_ascii=False)}
        for language, said in (("es", "en la calculadora elige el modo decimal"), ("en", "choose decimal mode in calculator")):
            payload = compose_payload._compose_situation_payload(situation, language, said)
            template = deterministic_finals._told_result_final(situation, payload, said, language)
            assert template and "Listo" not in template and "Done" not in template, template
            assert computer_use_finals._claims_defect(template, "status", situation) == "", template
            assert visible_defect.compose_visible_defect(template, "status", said, facts) == "", template
            assert not visible_defect._truncated_fact_word(template, payload), template
            assert payload_fact_checks._payload_fact_defect(template, payload, said) == "", template


def test_contracase_the_book_still_refuses_the_count_told_as_an_act() -> None:
    situation = _mission(_observed("model_evidence", 2))
    assert computer_use_finals._claims_defect(
        "Hice 2 pasos en «Calculadora», pero la pantalla todavía no muestra que haya quedado hecho.", "status", situation,
    ) == "unbacked_act"
    assert computer_use_finals._claims_defect("Borré el historial en «Calculadora».", "status", situation) == "unbacked_act"


# ---------------------------------------------------------------- revisión 2 de r22, bloqueante 1: the act changed its control
# The citation of a goal whose act changed the state of the very control it pressed relates to the goal by the
# control's identity (the App's «changedByClick»), by a switch the click turned, or by the option the click chose now
# shown as a control's value; a number said in words is a number. In any application.


def _after_click(first_controls: list[dict], after_controls: list[dict], process: str, **extra: object) -> dict:
    first = {"window": {"title": "Ventana", "process": process}, "controls": first_controls}
    return {**first, "controls": after_controls, "firstLook": "\n".join(cu_first_look.look_parts(first)), **extra}


def _click(label: str, step: int = 1) -> dict:
    return {"step": step, "operation": "input.visible.click", "ok": True, "label": label, "changed": True}


def _done(evidence: str, view: dict, history: list[dict], goal: str) -> dict:
    return _validate({"act": "done", "evidence": evidence}, view, history, goal)


def test_a_button_the_click_renamed_proves_play_and_mute() -> None:
    for before, after, goals in (
        ("Reproducir (k)", "Pausa (k)", ("dale play al video", "reproduce el video")),
        ("Silenciar", "Activar sonido", ("silencia el video", "mute the video")),
    ):
        view = _after_click([{"i": 0, "kind": "Button", "name": before, "state": "off"}],
                            [{"i": 0, "kind": "Button", "name": after, "state": "on"}], "msedge", changedByClick=[1])
        for goal in goals:
            assert _done(after, view, [_click(before)], goal)["operation"] == "done", (goal, after)


def test_a_switch_the_click_turned_on_proves_turning_on_wifi() -> None:
    for state in ("Activado", "Encendido"):
        view = _after_click(
            [{"i": 0, "kind": "Button", "name": "Wi-Fi", "state": "off"}, {"i": 1, "kind": "Text", "name": "Desactivado"}],
            [{"i": 0, "kind": "Button", "name": "Wi-Fi", "state": "on"}, {"i": 1, "kind": "Text", "name": state}],
            "SystemSettings",
        )
        for goal in ("activa el wifi", "enciende el wi-fi", "turn on wi-fi"):
            assert _done(state, view, [_click("Wi-Fi")], goal)["operation"] == "done", (goal, state)


def test_the_option_the_click_chose_now_the_value_proves_dark_mode_and_language() -> None:
    for name, old, new, goals in (
        ("Elige tu modo", "Claro", "Oscuro", ("pon el tema negro", "activa el modo nocturno")),
        ("Idioma para mostrar de Windows", "Español (México)", "English (United States)", ("cambia el idioma a inglés",)),
    ):
        view = _after_click([{"i": 0, "kind": "ComboBox", "name": name, "value": old}],
                            [{"i": 0, "kind": "ComboBox", "name": name, "value": new}], "SystemSettings")
        for goal in goals:
            assert _done(new, view, [_click(new)], goal)["operation"] == "done", (goal, new)


def test_a_number_said_in_words_relates_the_calculators_result() -> None:
    first = {"window": {"title": "Calculadora", "process": "CalculatorApp"},
             "controls": [{"i": 0, "kind": "Text", "name": "La pantalla muestra 0"},
                          {"i": 1, "kind": "Button", "name": "Siete"},
                          {"i": 2, "kind": "Button", "name": "Multiplicar por"},
                          {"i": 3, "kind": "Button", "name": "Ocho"},
                          {"i": 4, "kind": "Button", "name": "Es igual a"}]}
    view = {**first, "controls": [{"i": 0, "kind": "Text", "name": "La pantalla muestra 56"}, *first["controls"][1:]],
            "firstLook": "\n".join(cu_first_look.look_parts(first))}
    history = [_click(label, step) for step, label in enumerate(("Siete", "Multiplicar por", "Ocho", "Es igual a"), 1)]
    for goal in ("calcula cuánto es siete por ocho", "multiplica siete por ocho", "calcula 7 por 8",
                 "multiply seven by eight"):
        assert _done("La pantalla muestra 56", view, history, goal)["operation"] == "done", goal


# ---------------------------------------------------------------- revisión 2 de r22, bloqueante 2: the text said wins a format word


def test_a_goal_that_says_its_text_and_a_format_types_it_in_an_empty_or_written_document() -> None:
    for value in ("", "lista: pan"):
        view = {"window": {"title": "Sin título - Bloc de notas", "process": "Notepad"},
                "controls": [{"i": 0, "kind": "Document", "name": "Editor de texto", "value": value, "state": "focused"}]}
        for goal, text in (("pon hola en negrita", "hola"),
                           ("en el bloc de notas pon hola mundo con fuente Arial", "hola mundo"),
                           ("pon el texto bienvenidos centrado", "bienvenidos"),
                           ("ponle de título Informe en negrita", "Informe")):
            decision = _validate({"act": "type", "text": text}, view, [], goal)
            assert decision["operation"] == "input.text.type", (goal, value, decision)
            assert decision["arguments"]["text"] == text


def test_a_part_new_by_identity_is_related_by_the_command_that_brought_it() -> None:
    # Twin of CuV3CreacionPorIdentidadTests.TheSamePartWithNoButtonThatSavesIsNewByIdentity: «Nuevo evento» brought the
    # empty «Agregar un título» (a new id) for «crea un evento nuevo»; the title says no word of the goal, the command
    # that made it does. Contracase: the same part with its first-look id is no new thing and relates nothing.
    view = {
        "window": {"title": "Agenda", "process": "agenda",
                   "focused": {"kind": "Edit", "name": "Agregar un título", "value": "", "i": 4}},
        "controls": [{"i": 0, "kind": "Button", "name": "Nuevo evento", "state": ""},
                     {"i": 4, "kind": "Edit", "name": "Agregar un título", "state": "focused", "value": ""}],
        "text": {},
        "firstLook": "\n".join(["agenda", "nuevo evento"]),
        "firstIds": ["9.1"],
        "focusedId": "9.2",
    }
    pressed = {"step": 1, "operation": "input.visible.click", "label": "Nuevo evento", "index": 0, "ok": True,
               "changed": True, "broughtNew": True}
    assert not cu_evidence._unrelated_evidence("Agregar un título", view, [pressed], "crea un evento nuevo")


# ---------------------------------------------------------------- revisión 3 de r22, bloqueante B1: new text after the act proves
# Whatever its words: the act was a key of the catalog, or the result showed in another control than the one clicked.


def _key(key: str, step: int = 1) -> dict:
    return {"step": step, "operation": "input.key.press", "ok": True, "key": key, "changed": True, "surfaceChanged": True}


def test_the_song_a_click_on_next_brought_in_another_control_proves_skipping() -> None:
    controls = [{"i": 0, "kind": "Button", "name": "Siguiente"}, {"i": 1, "kind": "Button", "name": "Anterior"}]
    view = _after_click([*controls, {"i": 2, "kind": "Text", "name": "Bohemian Rhapsody"}],
                        [*controls, {"i": 2, "kind": "Text", "name": "Under Pressure"}], "Spotify", changedByClick=[])
    for goal in ("en spotify salta esta canción", "activar siguiente cancion", "cambia de cancion", "skip this song"):
        assert not cu_evidence._unrelated_evidence("Under Pressure", view, [_click("Siguiente")], goal), goal
        assert _done("Under Pressure", view, [_click("Siguiente")], goal)["operation"] == "done", goal


def test_the_state_a_catalog_key_left_proves_its_goal() -> None:
    for key, before, after, goal in (
        ("k", "Pausa (k)", "Reproducir (k)", "pausa el video"),
        ("m", "Silenciar (m)", "Activar sonido (m)", "silencia el video"),
        ("l", "0:10 / 3:20", "0:25 / 3:20", "adelanta el video"),
        ("ctrl_z", "Ln 1, Col 14", "Ln 1, Col 1", "deshaz el último cambio"),
    ):
        kind = "Button" if "(" in before else "Text"
        view = _after_click([{"i": 0, "kind": kind, "name": before}], [{"i": 0, "kind": kind, "name": after}], "msedge")
        assert not cu_evidence._unrelated_evidence(after, view, [_key(key)], goal), goal
        assert _done(after, view, [_key(key)], goal)["operation"] == "done", goal


def test_the_tab_a_chord_chose_proves_the_next_tab() -> None:
    first = {"window": {"title": "Gmail - Personal: Microsoft Edge", "process": "msedge"},
             "controls": [{"i": 0, "kind": "TabItem", "name": "Gmail", "state": "selected"},
                          {"i": 1, "kind": "TabItem", "name": "YouTube"}]}
    view = {"window": {"title": "YouTube - Personal: Microsoft Edge", "process": "msedge"},
            "controls": [{"i": 0, "kind": "TabItem", "name": "Gmail"},
                         {"i": 1, "kind": "TabItem", "name": "YouTube", "state": "selected"}],
            "firstLook": "\n".join(cu_first_look.look_parts(first))}
    assert not cu_evidence._unrelated_evidence("YouTube", view, [_key("ctrl_tab")], "cambia a la siguiente pestaña")
    assert _done("YouTube", view, [_key("ctrl_tab")], "cambia a la siguiente pestaña")["operation"] == "done"
