"""A search box seen only as written text (OCR, no tree to report focus) takes the name only when the next look proves
it has the keyboard; otherwise nothing is typed and the mission says it could not (Steam's library, live g1)."""

from __future__ import annotations

from baxy_mind import computer_use


def _ok(step: int, operation: str, **fields: object) -> dict:
    return {"step": step, "operation": operation, "ok": True, **fields}


# Steam's library as the App reads it: one pane, the search box only a magnifier (nothing written), no focus.
LIBRARY = {
    "window": {"title": "Steam", "process": "steamwebhelper", "focused": None},
    "controls": [{"i": 0, "kind": "Pane", "name": "Chrome Legacy Window", "state": ""}],
    "text": {
        "TL": ["TIENDA BIBLIOTECA COMUNIDAD", "Página principal", "Juegos y Software", "FAVORITOS (324)"],
        "L": ["A Story About My Uncle", "Age of Empires II (2013)", "Alan Wake"],
    },
}


def test_a_search_key_that_changed_nothing_goes_on_to_the_next_key_without_escape() -> None:
    first = computer_use.deterministic_step(goal="buscar Cuphead", view=LIBRARY, history=[])
    assert first["operation"] == "input.key.press" and first["arguments"] == {"key": "ctrl_k"}
    pressed = [_ok(1, "input.key.press", key="ctrl_k")]
    step = computer_use.deterministic_step(goal="buscar Cuphead", view={**LIBRARY, "newText": []}, history=pressed)
    assert step["arguments"] == {"key": "ctrl_f"}
    # A look that cannot say what changed (no newText) still closes whatever the key may have opened.
    step = computer_use.deterministic_step(goal="buscar Cuphead", view=LIBRARY, history=pressed)
    assert step["arguments"] == {"key": "escape"}


def test_a_search_key_that_wrote_a_search_prompt_proves_the_box_took_the_keyboard() -> None:
    pressed = [_ok(1, "input.key.press", key="ctrl_k"), _ok(2, "input.key.press", key="ctrl_f")]
    opened = {**LIBRARY, "text": {**LIBRARY["text"], "TL": [*LIBRARY["text"]["TL"], "Q Buscar por nombre"]},
              "newText": ["Q Buscar por nombre"]}
    step = computer_use.deterministic_step(goal="buscar Cuphead", view=opened, history=pressed)
    assert step["operation"] == "input.text.type" and step["arguments"] == {"text": "Cuphead"}
    # Something else appeared (not a search prompt): no proof, it is closed instead of typed into.
    other = {**LIBRARY, "newText": ["Descargas"]}
    assert computer_use.deterministic_step(goal="buscar Cuphead", view=other, history=pressed)["arguments"] == {"key": "escape"}


def test_a_message_box_with_the_keyboard_is_never_typed_into_even_with_a_search_prompt_on_screen() -> None:
    pressed = [_ok(1, "input.key.press", key="ctrl_f")]
    chat = {
        "window": {"title": "Chat", "process": "x", "focused": {"kind": "Edit", "name": "Escribe un mensaje", "value": ""}},
        "controls": [],
        "text": {"L": ["Buscar un chat"], "C": ["Escribe un mensaje"]},
        "newText": ["Buscar un chat"],
    }
    step = computer_use.deterministic_step(goal="buscar Ana", view=chat, history=pressed)
    assert step is None or step["operation"] != "input.text.type"
    clicked = [_ok(1, "input.visible.click", label="Buscar un chat")]
    cleared = {**chat, "text": {"C": ["Escribe un mensaje"]}, "newText": []}
    step = computer_use.deterministic_step(goal="buscar Ana", view=cleared, history=clicked)
    assert step["operation"] == "none" and step["code"] == computer_use.SEARCH_FOCUS_UNPROVEN
    # Nor by the model: a search's name never goes into the message box that has the keyboard.
    act = {"act": "type", "text": "Ana", "why": ""}
    step = computer_use.validate_decision(act, view=chat, last_failed=None, application_names=(), history=pressed, goal="buscar Ana")
    assert step["operation"] == "none"


def test_a_written_box_whose_click_proved_nothing_is_not_typed_into() -> None:
    written = {**LIBRARY, "text": {**LIBRARY["text"], "TL": [*LIBRARY["text"]["TL"], "Q Buscar por nombre"]}}
    step = computer_use.deterministic_step(goal="buscar Cuphead", view=written, history=[])
    assert step["operation"] == "input.visible.click"
    clicked = [_ok(1, "input.visible.click", label=step["arguments"]["label"])]
    same = {**written, "newText": []}
    stopped = computer_use.deterministic_step(goal="buscar Cuphead", view=same, history=clicked)
    assert stopped["operation"] == "none" and stopped["code"] == computer_use.SEARCH_FOCUS_UNPROVEN
    # A window that went elsewhere (most lines new) is no box with the caret either.
    away = {**LIBRARY, "text": {"C": ["a", "b", "c", "d"]}, "newText": ["a", "b", "c", "d"]}
    assert computer_use.deterministic_step(goal="buscar Cuphead", view=away, history=clicked)["operation"] == "none"
    # The placeholder cleared for the caret while the rest stayed: the name is typed.
    cleared = {**LIBRARY, "newText": ["Q"]}
    assert computer_use.deterministic_step(goal="buscar Cuphead", view=cleared, history=clicked)["arguments"] == {"text": "Cuphead"}


def test_enter_after_typing_into_a_proven_written_box_submits_the_search_and_asks_otherwise() -> None:
    typed = [_ok(1, "input.key.press", key="ctrl_f"), _ok(2, "input.text.type", text="Cuphead")]
    echoed = {**LIBRARY, "newText": ["Q Cuphead", "Cuphead"]}
    step = computer_use.deterministic_step(goal="buscar Cuphead", view=echoed, history=typed)
    assert step["arguments"] == {"key": "enter"}
    # The text shows nowhere as the box's own line: the Enter may send it, so it asks first.
    unseen = {**LIBRARY, "newText": []}
    step = computer_use.deterministic_step(goal="buscar Cuphead", view=unseen, history=typed)
    assert step["arguments"] == {"key": "enter", "target": "message_composer"}
    # A message box reports the keyboard: asks first whatever is written.
    chat = {**echoed, "window": {**LIBRARY["window"], "focused": {"kind": "Edit", "name": "Escribe un mensaje", "value": "Cuphead"}}}
    step = computer_use.deterministic_step(goal="buscar Cuphead", view=chat, history=typed)
    assert step["arguments"] == {"key": "enter", "target": "message_composer"}


def test_the_stop_is_said_as_its_cause() -> None:
    assert "no escribí nada" in computer_use._STOP_CAUSES["computer_use_search_focus_unproven"]["es"]
