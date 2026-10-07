"""R7 (live 2026-10-07, «en la Microsoft Store buscá Spotify»): the click on the store's search field opened its
history flyout, a top-level pop-up of the app's own process; the view moved to it, lost the field, and the deterministic
step clicked a history entry («speedtest. Presione la tecla Suprimir para borrar el historial de búsqueda.») as if it
were the search. The provider now keeps the frame hosting the app (ComputerUseWindowIdentityTests); here, the mind's side.
"""

from __future__ import annotations

from baxy_mind import computer_use

_HELP = ". Presione la tecla Suprimir para borrar el historial de búsqueda."


def _flyout() -> dict:
    """The look measured live after the click: the pop-up's history entries, no field, nothing focused."""

    names = ["speedtest", "geforce now", "ubuntu"]
    controls = [{"i": i, "kind": "ListItem", "name": name + _HELP, "state": "", "zone": "T"} for i, name in enumerate(names)]
    controls.append({"i": 3, "kind": "Window", "name": "Ventana emergente", "state": "", "zone": "C"})
    return {
        "window": {"title": "Host de ventanas emergentes", "process": "WinStore.App", "requested": True, "focused": None},
        "controls": controls,
        "text": {"TL": ["speedtest", "geforce now"], "L": ["ubuntu"]},
    }


def _clicked_field(kind: str = "Edit") -> list[dict]:
    return [
        {"step": 1, "operation": "app.open", "ok": True, "appId": "Store"},
        {"step": 2, "operation": "input.visible.click", "label": "Buscar", "index": 4, "ok": True, "kind": kind},
    ]


def test_a_history_entry_that_mentions_the_search_is_never_the_search() -> None:
    view = _flyout()
    assert computer_use._search_affordance(view, []) is None
    # Counter-case: a control named as a search, even with a sentence of help after it, still is one.
    view["controls"].append({"i": 9, "kind": "ListItem", "name": "Buscar. Escribí para filtrar.", "zone": "TL"})
    found = computer_use._search_affordance(view, [])
    assert found is not None and found["i"] == 9


def test_the_search_field_hidden_by_its_flyout_is_typed_into() -> None:
    step = computer_use.deterministic_step(goal="buscar Spotify", view=_flyout(), history=_clicked_field())
    assert step == {"operation": "input.text.type", "arguments": {"text": "Spotify"},
                    "reason": "el destino no está en pantalla: lo busco"}


def test_a_hidden_control_that_was_not_a_field_is_not_typed_into() -> None:
    # Counter-case: a click whose receipt says it pressed a button (no caret) and whose look lost it is no field.
    step = computer_use.deterministic_step(goal="buscar Spotify", view=_flyout(), history=_clicked_field("Button"))
    assert step is None or step["operation"] != "input.text.type"
    assert step is None or "speedtest" not in str((step.get("arguments") or {}).get("label") or "")


def test_enter_after_typing_behind_the_flyout_asks_first() -> None:
    # Counter-case for safety: with no field the view shows holding the keyboard, Enter is not known to be a search's
    # submit and goes marked so RiskPolicy asks; a suggestion is never clicked as the result of the typed echo.
    history = [*_clicked_field(), {"step": 3, "operation": "input.text.type", "text": "Spotify", "ok": True}]
    step = computer_use.deterministic_step(goal="buscar Spotify", view=_flyout(), history=history)
    assert step == {"operation": "input.key.press", "arguments": {"key": "enter", "target": "message_composer"},
                    "reason": "el objetivo lo dice"}


def test_in_the_frame_the_field_takes_the_name_and_enter_submits_it() -> None:
    frame = {
        "window": {"title": "Microsoft Store", "process": "ApplicationFrameHost", "requested": True,
                   "focused": {"kind": "Edit", "name": "Buscar", "value": ""}},
        "controls": [{"i": 4, "kind": "Edit", "name": "Buscar", "state": "focused", "value": "", "zone": "T"}],
        "text": {"T": ["Buscar aplicaciones, juegos y mucho más"]},
    }
    typed = computer_use.deterministic_step(goal="buscar Spotify", view=frame, history=_clicked_field())
    assert typed is not None and typed["operation"] == "input.text.type"
    frame["window"]["focused"]["value"] = "Spotify"
    frame["controls"][0]["value"] = "Spotify"
    history = [*_clicked_field(), {"step": 3, "operation": "input.text.type", "text": "Spotify", "ok": True}]
    enter = computer_use.deterministic_step(goal="buscar Spotify", view=frame, history=history)
    assert enter is not None and enter["arguments"] == {"key": "enter"}
