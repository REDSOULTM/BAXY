"""Goal v3 point 2 (cu-v3 r2 diag_tipos §2.B), the mind's side of the mouse-free primitives: the model's «type» with a
«field» puts a form's field to a value (input.text.type field + replace), «reveal» brings an element of a long list into
view (input.scroll with label), and the new keys are in the closed repertoire. Each rule with its contracase."""

from __future__ import annotations

from baxy_mind import computer_use
from baxy_mind import cu_validate
from baxy_mind import cu_step_prompt
from baxy_mind.semantic.missions import KEYS

_FORM = {
    "window": {"title": "Cambiar tamaño", "process": "x"},
    "controls": [
        {"i": 0, "kind": "Edit", "name": "Horizontal", "state": "focused", "value": "1366"},
        {"i": 1, "kind": "Edit", "name": "Vertical", "state": "", "value": "768"},
        {"i": 2, "kind": "ComboBox", "name": "Fuente", "state": "", "value": "Calibri"},
        {"i": 3, "kind": "Edit", "name": "Contraseña", "state": "password"},
        {"i": 4, "kind": "Document", "name": "Texto", "state": ""},
        {"i": 5, "kind": "Button", "name": "Aceptar", "state": ""},
    ],
}


def _act(raw: dict, view: dict = _FORM) -> dict:
    return cu_validate.validate_decision(raw, view=view, last_failed=None, application_names=[], history=[], goal="cambiar el tamaño")


def test_a_type_that_names_its_field_replaces_that_fields_value() -> None:
    step = _act({"act": "type", "text": "600", "field": "vertical"})
    assert step["operation"] == "input.text.type"
    assert step["arguments"] == {"text": "600", "field": "Vertical", "replace": True}


def test_a_combo_box_takes_a_value_by_its_label() -> None:
    step = _act({"act": "type", "text": "Arial", "field": "Fuente"})
    assert step["arguments"] == {"text": "Arial", "field": "Fuente", "replace": True}


_SAVE_AS = {
    "window": {"title": "Guardar como", "process": "x"},
    "controls": [
        {"i": 0, "kind": "ComboBox", "name": "Nombre de archivo:", "state": "", "value": "*.txt"},
        {"i": 1, "kind": "ComboBox", "name": "Tipo:", "state": "", "value": "Documentos de texto"},
        {"i": 2, "kind": "Button", "name": "Guardar", "state": ""},
    ],
}


def test_a_field_labelled_with_a_colon_is_named_without_it() -> None:
    # Guardar como writes «Nombre de archivo:»; the step names the field by its label, not by the colon that ends it.
    for asked in ("Nombre de archivo", "Nombre de archivo:"):
        step = _act({"act": "type", "text": "notas.txt", "field": asked}, view=_SAVE_AS)
        assert step["arguments"] == {"text": "notas.txt", "field": "Nombre de archivo", "replace": True}
    assert _act({"act": "type", "text": "Texto", "field": "Tipo"}, view=_SAVE_AS)["arguments"]["field"] == "Tipo"


def test_a_field_name_without_a_colon_is_kept_whole() -> None:
    # Contracase: only the trailing colon goes; a name with inner punctuation stays as the view wrote it.
    view = {"window": {"title": "x"}, "controls": [{"i": 0, "kind": "Edit", "name": "Ancho (px)", "state": ""}]}
    assert _act({"act": "type", "text": "800", "field": "Ancho (px)"}, view=view)["arguments"]["field"] == "Ancho (px)"


def test_without_a_field_the_text_is_typed_where_the_keyboard_is() -> None:
    # Contracase: the plain «type» keeps its meaning (no replace, no field).
    step = _act({"act": "type", "text": "600"})
    assert step["arguments"] == {"text": "600"}


def test_a_field_that_is_not_one_is_refused() -> None:
    # Contracases: a label the view does not have, a button, a document (the person's work) and a password.
    assert _act({"act": "type", "text": "600", "field": "Ancho"})["operation"] == "none"
    assert _act({"act": "type", "text": "600", "field": "Aceptar"})["operation"] == "none"
    assert _act({"act": "type", "text": "hola", "field": "Texto"})["operation"] == "none"
    refused = _act({"act": "type", "text": "x", "field": "Contraseña"})
    assert refused["operation"] == "none" and refused["code"] == "password_field"


def test_a_document_read_empty_takes_the_text_in_and_never_replaced() -> None:
    # r25 (c1): only a body the view read empty («empty», as the App sends it), never one whose content is unknown
    # (above), takes it.
    view = {**_FORM, "controls": [*_FORM["controls"][:4], {**_FORM["controls"][4], "empty": True}, _FORM["controls"][5]]}
    step = _act({"act": "type", "text": "hola", "field": "Texto"}, view=view)
    assert step["operation"] == "input.text.type"
    assert step["arguments"] == {"text": "hola", "field": "Texto"}


def test_reveal_brings_an_element_into_view_by_its_name() -> None:
    step = _act({"act": "reveal", "text": "Omega"})
    assert step["operation"] == "input.scroll"
    assert step["arguments"] == {"direction": "down", "amount": 10, "label": "Omega"}


def test_reveal_without_a_name_is_no_step() -> None:
    assert _act({"act": "reveal", "text": "  "})["operation"] == "none"


def test_the_grammar_and_the_prompt_carry_the_new_acts() -> None:
    assert "reveal" in computer_use.ACTS
    assert '\\"reveal\\"' in cu_step_prompt.STEP_GRAMMAR and '\\"field\\"' in cu_step_prompt.STEP_GRAMMAR
    assert '"act":"reveal"' in cu_step_prompt.STEP_PROMPT and '"field"' in cu_step_prompt.STEP_PROMPT


def test_the_new_keys_are_in_the_repertoire_and_the_grammar() -> None:
    for key in ("ctrl_s", "ctrl_shift_s", "ctrl_o", "ctrl_h", "ctrl_x", "f10", "shift_f10"):
        assert key in KEYS
        assert f'\\"{key}\\"' in cu_step_prompt.STEP_GRAMMAR
    assert _act({"act": "key", "key": "shift_f10"})["arguments"]["key"] == "shift_f10"
    # Contracase: a key outside the catalog stays refused.
    assert _act({"act": "key", "key": "alt_f4"})["operation"] == "none"


def test_keys_that_act_outside_the_missions_window_are_never_a_mission_step() -> None:
    # Safety review r10a: switching windows, the Start menu and the Task Manager act on the desktop over the person,
    # wherever the key is bound; they are neither offered to the model nor accepted from it.
    from baxy_mind.semantic import missions

    assert set(missions.KEYS_OUTSIDE_THE_WINDOW) == {"alt_tab", "ctrl_shift_escape", "win"}
    for key in missions.KEYS_OUTSIDE_THE_WINDOW:
        assert key not in KEYS
        assert f'\\"{key}\\"' not in cu_step_prompt.STEP_GRAMMAR
        assert _act({"act": "key", "key": key})["operation"] == "none", key
    # Contracase: the keys that act inside the window stay (escape, tab, the context menu).
    for key in ("escape", "tab", "context_menu"):
        assert _act({"act": "key", "key": key})["arguments"]["key"] == key
