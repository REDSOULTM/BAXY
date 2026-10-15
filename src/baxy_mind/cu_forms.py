"""A form's fields: the field a sub-goal sets by any of its names, set to its value by its label, the lock
that ties two fields, and the button that accepts the form.
"""

from __future__ import annotations

from typing import Iterable

from .semantic.missions import field_goal_parts, field_names_for, fold
from .semantic import cu_tipos
from .semantic.cu_tipos import SEARCH_FIELD
from .cu_view import find_control
from .cu_goals import _value_terms
from .cu_fields import _COMPOSER_NAME, _focused_controls, _is_search_field, _search_box_to_type
from .cu_acts import _click, _form_field_arguments, typed_text
from .cu_history import _steps_ok, _typed_steps


# The controls a form's value is put into by its label (goal v3 point 2): a field or a combo box, never a document.
_FORM_FIELD_KINDS = ("Edit", "ComboBox", "Spinner")


def _editor_body(field: dict, view: dict) -> bool:
    """Pasada r15b (t-long-2): the empty body of an editor — a Document, or an Edit beside the focused Document (in its
    zone: «Contenido de la página 1» of a new Word document) — holding no value. Nothing there to replace: the text goes
    in (the provider refused «replacing» the empty page and nothing was written). A form's field keeps its replace."""

    if str(field.get("value") or "").strip() or field.get("kind") not in {"Edit", "Document"}:
        return False
    if field.get("kind") == "Document":
        return True
    return any(
        control.get("kind") == "Document" and control.get("zone") and control.get("zone") == field.get("zone")
        for control in _focused_controls(view)
    )


# The kinds a form's label names: the field or the list box the label stands beside (v3-27).
_LABELLED_KINDS = frozenset({"Edit", "ComboBox"})


def _field_of_label(control: dict | None, view: dict) -> dict | None:
    """Pasada r15b (v3-27): a Text of the view that is the label of a field («Caracteres para copiar:» beside the Edit
    of the same name, the colon aside): that one field (an Edit or a ComboBox), when exactly one of the view has that
    name and it takes input (never a password, a disabled or a read-only one). None for any other control."""

    if not isinstance(control, dict) or control.get("kind") != "Text":
        return None
    name = fold(control.get("name")).strip(" :：")
    controls = view.get("controls") if isinstance(view, dict) else None
    if not name or not isinstance(controls, list):
        return None
    fields = [
        item for item in controls
        if isinstance(item, dict) and item is not control and item.get("kind") in _LABELLED_KINDS
        and fold(item.get("name")).strip(" :：") == name
    ]
    if len(fields) != 1:
        return None
    states = set(str(fields[0].get("state") or "").split())
    return None if states & {"password", "disabled", "readonly"} else fields[0]


def _field_named(view: dict, names: Iterable[str]) -> dict | None:
    """The field a form's sub-goal sets, by any of its names. Two fields of one name (a size group and a skew group
    that both say «Horizontal»): the first in the view's reading order, the one a person fills first, never left to
    a guess that could write in the other (review of v3 punto 2)."""

    names = tuple(names)
    for name in names:
        for kind in _FORM_FIELD_KINDS:
            control = find_control(view, name, kind=kind)
            if control is not None:
                return control
    listed = view.get("controls") if isinstance(view, dict) else None
    if not isinstance(listed, list):
        return None
    for name in names:
        same = [
            control for control in listed
            if isinstance(control, dict) and control.get("kind") in _FORM_FIELD_KINDS
            and fold(control.get("name")).strip(" :") == fold(name)
        ]
        if len(same) > 1:
            return same[0]
    return None


def _field_step(goal: str, view: dict, history: list[dict]) -> dict[str, object] | None:
    """«poner ancho en 800»: the field by any of its names set to the value by its label, replacing what it held
    («1366» never becomes «1366800»), the same act as the model's «type» with «field» (no click, no Ctrl+A, no
    keyboard). Nothing once the field shows the value or the value was already sent; never a password or a read-only
    field; the model's step when no field carries a name of it."""

    parts = field_goal_parts(goal)
    if parts is None:
        return None
    field, value = parts
    if field == SEARCH_FIELD:
        # «escribí X en el buscador» (cu-v3 texto-webview): the window's own search box, known by what it is (never
        # the address bar, a message box or a name that merely holds «search», like «Research»); it takes the text
        # by its label, replacing the search it held.
        box = _search_box_to_type(view)
        if box is None or _steps_ok(history, "input.text.type"):
            return None
        arguments = _form_field_arguments(box, str(box.get("name") or ""), typed_text(value))
        if box.get("kind") == "Document":
            arguments.pop("replace", None)
        return {"operation": "input.text.type", "arguments": arguments, "reason": "escribo en el buscador que dice el pedido"}
    names = field_names_for(field)
    control = _field_named(view, names)
    if control is None:
        return None
    if fold(control.get("value")).strip() == fold(value):
        return None
    if _steps_ok(history, "input.text.type"):
        return None
    if {"password", "readonly"} & set(str(control.get("state") or "").split()):
        return None
    if (
        _COMPOSER_NAME.search(fold(control.get("name"))) and not _is_search_field(control)
        and str(control.get("value") or "").strip()
    ):
        # A message box holding the person's draft is never replaced by rule (review r2 texto-webview, finding 2).
        return None
    return {"operation": "input.text.type", "arguments": _form_field_arguments(control, field, typed_text(value)),
            "reason": "el objetivo lo dice"}


LINKED_FIELDS = "linked_fields"
_LINK_LOCK_KINDS = frozenset({"Button", "CheckBox", "ToggleButton"})


def _value_shown(view: dict, name: str, value: str) -> dict | None:
    """The field of that name whose value holds the value (the shell's ``value:`` atom: the name contained, the value
    held, ``cu_tipos.value_holds``: «500 px» holds «500», «1500» does not); None when no field of that name holds it."""

    controls = view.get("controls") if isinstance(view, dict) else None
    for control in controls if isinstance(controls, list) else ():
        if (
            isinstance(control, dict) and name in fold(control.get("name"))
            and cu_tipos.value_holds(fold(control.get("value")), value)
        ):
            return control
    return None


def _link_lock_on(view: dict) -> dict | None:
    """The switch that ties two fields of a pair (``cu_tipos.LINK_LOCK_NAMES``: «Mantener la relación de aspecto»),
    shown on; None when the view shows none, or it is off."""

    locks = tuple(fold(name) for name in cu_tipos.LINK_LOCK_NAMES)
    controls = view.get("controls") if isinstance(view, dict) else None
    for control in controls if isinstance(controls, list) else ():
        if not isinstance(control, dict) or str(control.get("kind")) not in _LINK_LOCK_KINDS:
            continue
        states = set(str(control.get("state") or "").split())
        if {"on", "selected"} & states and any(lock in fold(control.get("name")) for lock in locks):
            return control
    return None


def _form_unit_step(
    goal: str, success_check: str | None, view: dict, history: list[dict], objective: str | None = None,
    form_check: str | None = None,
) -> dict[str, object] | None:
    """Ronda 20b (pasada r18 t-long-3: «Vertical» set to 500 with the aspect lock on, the canvas was left at 177×500
    once the dialog was accepted, and the final said 500 by 500). A field of a form that holds only with the fields set
    before it (``missions._unit_field_read``: its check's terms read several fields) is set as one unit.

    Before any field is typed (revisión 2, bloqueante 1): when the request fixes the fields a lock ties (``form_check``,
    the whole form's check the plan gives each of its fields, ``missions._with_form_checks``) and the view shows them
    with that lock on, the lock is switched off first. A field that recalculates the other only when it loses the focus
    (a NumberBox, a NumericUpDown) shows no change until the form is accepted, so waiting to see one is too late.

    After this sub-goal's own field is typed: when the window changed a field set before, that field is set again
    (once), first switching off a lock still on; a field the window changes again after it was set in this sub-goal
    stops the mission with its cause (``linked_fields``), never accepted with a value the person did not ask for.
    Nothing while the form holds (independent fields: no step, no call), for a field alone, or while this sub-goal's
    own field is still to type (``_field_step`` types it). A request that keeps the link («… manteniendo la
    proporción», ``cu_tipos.keeps_link`` over ``objective``) never switches the lock off: the fields are set again with
    it on, and when they still change each other the mission stops the same way (revisión 1, bloqueante 3)."""

    parts = field_goal_parts(goal)
    if parts is None:
        return None
    first = _lock_off_first(form_check, view, history, objective)
    if first is not None:
        return first
    own = {fold(name).strip() for name in field_names_for(parts[0])}
    terms = [term for term in _value_terms(success_check) if any(name not in own for name, _ in term)]
    if not terms or any(all(_value_shown(view, name, value) for name, value in term) for term in terms):
        return None
    term = next((term for term in terms if all(_field_named(view, (name,)) for name, _ in term)), None)
    if term is None:
        return None
    failing = [(name, value) for name, value in term if _value_shown(view, name, value) is None]
    if any(name in own for name, _ in failing) and not _typed_steps(history):
        return None
    # The field the window changed: one set before this sub-goal first, else this sub-goal's own.
    return _set_again(term, sorted(failing, key=lambda pair: pair[0] in own)[0], view, history, objective)


def _lock_to_switch_off(view: dict, history: list[dict], objective: str | None) -> dict | None:
    """The lock that ties a pair of fields, shown on, that this sub-goal may switch off: never when the request keeps
    the link (``cu_tipos.keeps_link``), nor once this sub-goal pressed it."""

    lock = None if cu_tipos.keeps_link(fold(objective or "")) else _link_lock_on(view)
    if lock is None or any(
        isinstance(step, dict) and step.get("operation") == "input.visible.click"
        and fold(step.get("label")) == fold(lock.get("name")) for step in history
    ):
        return None
    return lock


def _lock_off_first(
    form_check: str | None, view: dict, history: list[dict], objective: str | None,
) -> dict[str, object] | None:
    """Revisión 2 de la ronda 20b (bloqueante 1): the click that switches a lock off before the first field of a form
    whose tied fields (a term of ``form_check`` that reads two or more) the view shows, with nothing typed yet in this
    sub-goal; None otherwise."""

    if _typed_steps(history):
        return None
    tied = [term for term in _value_terms(form_check) if len(term) > 1]
    term = next((term for term in tied if all(_field_named(view, (name,)) for name, _ in term)), None)
    if term is None:
        return None
    lock = _lock_to_switch_off(view, history, objective)
    if lock is None:
        return None
    fields = " y ".join(str((_field_named(view, (name,)) or {}).get("name") or name) for name, _ in term)
    return _click(lock, cu_tipos.LINK_FIRST_NOTE.format(fields=fields, lock=str(lock.get("name") or "")))


def _set_again(
    term: list[tuple[str, str]], pair: tuple[str, str], view: dict, history: list[dict], objective: str | None,
    once: bool = False,
) -> dict[str, object] | None:
    """A field of ``term`` the window changed (``pair``: its name and value) set again, first switching a lock still on
    off; when this sub-goal already set it (with ``once``, any field of the form), the mission stops with
    ``linked_fields``."""

    name, value = pair
    field = _field_named(view, (name,))
    if field is None:
        return None
    others = [other for other, _ in term if other != name]
    note = {
        "changed": str(field.get("name") or name), "shown": str(field.get("value") or ""),
        "typed": " y ".join(others) or name,
    }
    lock = _lock_to_switch_off(view, history, objective)
    if lock is not None:
        return _click(lock, cu_tipos.LINK_OFF_NOTE.format(**note, lock=str(lock.get("name") or "")))
    label = fold(str(field.get("name") or name).rstrip(":： ")).strip()
    typed = _typed_steps(history)
    if (once and typed) or any(fold(step.get("field")).strip(" :") in {label, name} for step in typed):
        # Set once in this sub-goal and changed again: the fields recalculate each other or the window does not take
        # the value; the form is left unaccepted, said as such.
        return {"operation": "none", "arguments": {}, "reason": cu_tipos.LINKED_NOTE.format(**note), "code": LINKED_FIELDS}
    return {
        "operation": "input.text.type",
        "arguments": _form_field_arguments(field, name, typed_text(value)),
        "reason": cu_tipos.LINKED_NOTE.format(**note),
    }


def _form_confirm_step(
    form_check: str, view: dict, history: list[dict], objective: str | None = None,
) -> dict[str, object] | None:
    """Revisión 2 de la ronda 20b (bloqueante 1): before the button that accepts a form (a sub-goal that carries
    ``form_check``, the whole form's check), every field of the form is evaluated again on the view. When the view
    shows the form's fields and no term of its check holds, the first field off its value is set again (once, the lock
    switched off first unless the request keeps it), and the form still off after that (the same field or another
    one changed) stops the mission with ``linked_fields`` instead of accepting. None while the form holds, or when the view does not show its fields (the
    click goes on: the shell's check and the final judge the result)."""

    terms = [term for term in _value_terms(form_check) if all(_field_named(view, (name,)) for name, _ in term)]
    if not terms or any(all(_value_shown(view, name, value) for name, value in term) for term in terms):
        return None
    term = terms[0]
    failing = [(name, value) for name, value in term if _value_shown(view, name, value) is None]
    return _set_again(term, failing[0], view, history, objective, once=True) if failing else None
