"""The two acts of a chat client that are no typed operation, decided on the view without the model (encargo IMP2).

- Reading what was last written in a chat (``semantic.chats.last_written``) on the window already titled by that chat is
  a reading: done there, citing the last conversation entry the view shows, never an act (imp1 imp-dc-leer: the click on
  the chat's own name in its header opened the person's profile over the conversation, and nothing was read).
- Leaving the call: once the click on the control that leaves it found no such control, and the view still names none
  of the names an application gives it (data conversation_acts «leaveCall.labels»), the person is in no call; that is
  said, nothing is pressed (imp1 imp-dc-salir-voz: a scroll and «la pantalla dejó de cambiar» on a channel page with no
  call).

No application is named here; the words are data (conversation_acts.v1.json).
"""

from __future__ import annotations

import re

from .semantic import app_places
from .semantic.chats import has_written_entries, last_written, leave_call_goal, leave_call_labels
from .semantic.limits import LIMIT_CODE
from .semantic.missions import fold
from .cu_acts import _click, _none, typed_text
from .cu_view import _focused, _same_control
from .cu_lookup import SEARCH_PENDING

# The stop the floor says with its absence (operation_floor.v1.json «computerUse.causes» and «limits.absences»).
CALL_NOT_FOUND = "call_not_found"
_ABSENT_CLICK = frozenset({"visible_button_not_found", "visible_control_label_mismatch"})
# Encargo TZ-WA2: what a chat's own entry is drawn as (the chat list's title cell, a result, a recent search's button).
_ENTRY_KINDS = frozenset({"DataItem", "ListItem", "Button"})
_REASON_ENTRY = "la entrada propia del chat"
_REASON_ALL = "el chat no está a la vista con este filtro: muestro todos los chats"
_REASON_FIELD = "busco el chat en el buscador de chats"


def read_in_place(question: str, view: dict, history: list[dict]) -> dict[str, object] | None:
    """A done that reads the chat the window is titled by, before any act of the sub-goal; None otherwise."""

    asked = last_written(question)
    window = view.get("window") if isinstance(view, dict) else None
    if history or asked is None or not isinstance(window, dict):
        return None
    title = str(window.get("title") or "")
    if not re.search(rf"(?<!\w){re.escape(asked.chat)}(?!\w)", fold(title)):
        return None
    entries = [
        str(control.get("name") or "") for control in view.get("controls") or ()
        if isinstance(control, dict) and control.get("kind") == "Group" and str(control.get("name") or "").strip()
    ]
    cited = entries[-1] if has_written_entries(entries) else title
    return {"operation": "done", "arguments": {"evidence": cited[:200]},
            "reason": "el chat ya está abierto: se lee lo que muestra, sin tocar nada"}


def call_not_found(goal: str, view: dict, history: list[dict]) -> dict[str, object] | None:
    """The stop of a leave-call goal whose own control the last click did not find and the view does not show."""

    if fold(goal).strip() != leave_call_goal() or not history or view.get("partial") is True:
        return None
    last = history[-1] if isinstance(history[-1], dict) else {}
    labels = [fold(label) for label in leave_call_labels()]
    if (
        last.get("operation") != "input.visible.click" or last.get("ok") is not False
        or str(last.get("error") or "") not in _ABSENT_CLICK or fold(last.get("label")).strip() not in labels
    ):
        return None
    shown = [fold(control.get("name")) for control in (view.get("controls") or ()) if isinstance(control, dict)]
    if any(label in name for name in shown for label in labels):
        return None
    return _none("no hay ninguna llamada de la que salir", code=LIMIT_CODE + CALL_NOT_FOUND)


def chat_search_step(goal: str, application: str | None, view: dict, history: list[dict]) -> dict[str, object] | None:
    """Encargo TZ-WA2 (banco zu1–zu3, 7 of 9 imp-wa-* failed): going to a chat of an application whose data say how its
    chat list is searched (app_places «chatSearch»), decided on the view without the model. The chat's own entry
    (``_is_chat_entry``: its name with only the unread or status mark before it and its time or date after it; never the row
    with the last message's preview, never a message that names the chat) is pressed once, and given a moment to open;
    else, with no entry in sight, the filter that shows every chat is chosen (only that one, once), then the chat's name
    is put into the chat search by its value (the field clicked first, its text replaced whole by its index) and the
    entry the results show is pressed. A search that holds the name and shows no entry stops: the chat was not found.
    Never another filter, never the start of a new chat. None (the engine's own way) for any other application or
    sub-goal, or when the window shows no chat search (another panel of the application). No application is named
    here; the names and the entry's shape are data."""

    found = app_places.chat_search(application, goal)
    if found is None or not isinstance(view, dict):
        return None
    spec, target = found
    controls = [control for control in view.get("controls") or () if isinstance(control, dict) and isinstance(control.get("i"), int)]
    field = _chat_field(controls, spec, target)
    if field is None:
        return None
    shape = re.compile(str(spec.get("entry") or "{name}").replace("{name}", re.escape(target)))
    steps = [step for step in history if isinstance(step, dict)]
    typed = [n for n, step in enumerate(steps) if step.get("operation") == "input.text.type" and fold(step.get("text")) == target]
    since = steps[typed[-1] + 1:] if typed else steps
    last = steps[-1] if steps else None
    pressed = [step for step in since if step.get("operation") == "input.visible.click" and _is_chat_entry(shape, step.get("label"))]
    entries = sorted((control for control in controls if control.get("kind") in _ENTRY_KINDS and _is_chat_entry(shape, control.get("name"))),
                     key=lambda control: len(fold(control.get("name"))))
    if entries and not pressed:
        return _click(entries[0], _REASON_ENTRY)
    alls = {fold(name) for name in spec.get("all") or ()}
    if last is not None and last.get("ok") is True and last.get("awaited") is not True and (
        (last.get("operation") == "input.visible.click" and (_is_chat_entry(shape, last.get("label")) or fold(last.get("label")) in alls))
        or (typed and last is steps[typed[-1]])
    ):
        # The entry pressed, the filter chosen or the name searched draws a moment later (encargo IMP2: 750–880 ms).
        return _none("lo pulsado o buscado todavía no se dibujó", code=SEARCH_PENDING)
    tabs = [control for control in controls if control.get("kind") == "TabItem"]
    show_all = next((tab for tab in tabs if fold(tab.get("name")) in alls and not _tab_chosen(tab)), None)
    if not entries and show_all is not None and any(_tab_chosen(tab) for tab in tabs) and not any(
        step.get("operation") == "input.visible.click" and fold(step.get("label")) in alls for step in steps
    ):
        return _click(show_all, _REASON_ALL)
    if fold(field.get("value")) == target:
        return _none("el chat no aparece en la lista ni en el buscador de chats")
    if not _keyboard_in(view, field) and not any(
        step.get("operation") == "input.visible.click" and step.get("ok") is True
        and fold(step.get("label")) == fold(field.get("name")) for step in steps
    ):
        return _click(field, _REASON_FIELD)
    said = goal.strip()[len("ir a "):].strip() if fold(goal).startswith("ir a ") else target
    return {"operation": "input.text.type", "arguments": {"text": typed_text(said), "index": field["i"], "replace": True},
            "reason": _REASON_FIELD}


def _is_chat_entry(shape: re.Pattern[str], name: object) -> bool:
    return bool(str(name or "").strip()) and shape.fullmatch(fold(name)) is not None


def _tab_chosen(control: dict) -> bool:
    return "selected" in str(control.get("state") or "").split()


def _chat_field(controls: list[dict], spec: dict, target: str) -> dict | None:
    """The chat search: a text field named as the data name it, the one holding the chat's name first."""

    names = {fold(name) for name in spec.get("fields") or ()}
    fields = [control for control in controls if control.get("kind") == "Edit" and fold(control.get("name")) in names]
    fields.sort(key=lambda control: fold(control.get("value")) != target)
    return fields[0] if fields else None


def _keyboard_in(view: dict, field: dict) -> bool:
    focused = _focused(view)
    return "focused" in str(field.get("state") or "").split() or (focused is not None and _same_control(focused, field))
