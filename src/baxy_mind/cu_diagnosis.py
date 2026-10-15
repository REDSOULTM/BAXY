"""Why a step failed, read from the view after it, and the guards on a rule's step: one that repeats the step
that just failed, presses a spent key, or comes after the App's guard refused one.
"""

from __future__ import annotations

from .semantic.missions import fold
from .cu_view import _area, find_control
from .cu_fields import _focused_controls, _search_box, _writable
from .cu_acts import _guard_repeat
from .cu_history import _spent_keys
from .cu_rules import CONTAINER_REFUSAL


_DROPDOWN_KINDS = frozenset({"ComboBox", "SplitButton", "MenuItem", "Button"})


def failed_click_diagnosis(failed: dict | None, view: dict) -> str:
    """Why a click that came back ok=false did not do its act, read from the view after it (rule 2 of «teclas sin
    efecto», r9 v3-32: the area list was clicked, its receipt said «unchanged» and the next look showed it expanded;
    then «Sin retraso», the value shown by a closed list, was pressed twice); and why a text aimed at a field did not
    go there, with the way out (pasada r15b, t-long-2). Empty for any other step."""

    if isinstance(failed, dict) and failed.get("operation") == "input.text.type" and failed.get("ok") is False:
        return _failed_typing_diagnosis(failed, view)
    if not isinstance(failed, dict) or failed.get("operation") != "input.visible.click" or failed.get("ok") is not False:
        return ""
    if CONTAINER_REFUSAL in str(failed.get("error") or ""):
        # Ronda 24b, revisión 3 (D): nothing was pressed; the place is reached through one of the container's rows.
        return "es un contenedor (lista, árbol o tabla): elegí uno de sus elementos, nunca el contenedor otra vez"
    label = str(failed.get("label") or "")
    index = failed.get("index") if isinstance(failed.get("index"), int) else None
    control = find_control(view, label, index) if label else None
    if control is None:
        # find_control says None for an ambiguous name too: two «Aceptar» are still in the view.
        same = [
            item.get("i") for item in view.get("controls") or []
            if isinstance(item, dict) and label and fold(item.get("name")) == fold(label)
        ]
        if len(same) > 1:
            numbers = ", ".join(f"[{number}]" for number in same[:4])
            return f"hay varios controles con ese nombre ({numbers}): elegí uno por su número"
        return "el control ya no está en la vista"
    states = str(control.get("state") or "").split()
    if "disabled" in states:
        return "está deshabilitado: otro camino"
    if "expanded" in states:
        return "el clic sí lo desplegó: elegí una de sus opciones"
    if _area(control.get("rect")) > 0 and control.get("kind") in {"ListItem", "MenuItem", "DataItem", "TreeItem"}:
        rect = control["rect"]
        left, top = float(rect["x"]), float(rect["y"])
        right, bottom = left + float(rect["w"]), top + float(rect["h"])
        # The closed list that shows the value holds the whole option in one row of about its height: a big collapsed
        # button (a panel, a card) that merely lies under the option is no list showing it.
        holders = [
            item for item in view.get("controls") or []
            if isinstance(item, dict) and item is not control and item.get("kind") in _DROPDOWN_KINDS
            and "collapsed" in str(item.get("state") or "").split() and _area(item.get("rect")) > 0
            and float(item["rect"]["x"]) <= left and right <= float(item["rect"]["x"]) + float(item["rect"]["w"])
            and float(item["rect"]["y"]) <= top and bottom <= float(item["rect"]["y"]) + float(item["rect"]["h"])
            and float(item["rect"]["h"]) <= 3 * float(rect["h"])
        ]
        if holders:
            holder = min(holders, key=lambda item: _area(item.get("rect")))
            return f"es la opción que muestra el desplegable [{holder.get('i')}] «{str(holder.get('name') or '')[:50]}»: abrí ese"
    if "not_invokable" in str(failed.get("error") or ""):
        return "ese control no se pulsa: probá el que lo contiene o otro camino"
    return "no hizo nada: otro control u otro camino, nunca el mismo clic"


# Pasada r15b (t-long-2): the provider's refusals of a text aimed at a field, as the retry tells them.
_FIELD_REFUSALS = {
    "input_field_not_replaceable": "ese campo no se reemplaza",
    "input_field_not_found": "ese campo no está en la vista",
    "input_field_not_writable": "ese campo no se escribe",
    "input_field_not_reachable": "a ese campo no le llega el texto sin su foco",
}


def _failed_typing_diagnosis(failed: dict, view: dict) -> str:
    """Why a text aimed at a field came back failed, and the way out the view offers: the keyboard already on a part
    that takes text (the page of a document) is typed into with no field named."""

    error = str(failed.get("error") or "")
    said = next((reason for code, reason in _FIELD_REFUSALS.items() if code in error), "")
    if not said or not str(failed.get("field") or "").strip():
        return ""
    focused = next((
        control for control in _focused_controls(view)
        if control.get("kind") in {"Document", "Edit"} and _writable(control) and not _search_box(view, control)
    ), None)
    if focused is None:
        return f"{said}: otro campo de la vista, o pulsá el campo y escribí sin field"
    return f"{said}; el foco ya está en «{str(focused.get('name') or '')[:50]}»: type sin field"


def repeats_the_failed_step(dictated: dict | None, history: list[dict]) -> bool:
    """Ronda 21 (pasada r18 t-scroll-4): a step a rule dictated is the very act the sub-goal's last step tried and
    failed (``_guard_repeat`` against it). A rule whose last step was another act, or did not fail, dictates as before."""

    if not isinstance(dictated, dict) or dictated.get("operation") in (None, "none", "done"):
        return False
    if not isinstance(dictated.get("arguments"), dict):
        return False
    last = history[-1] if history and isinstance(history[-1], dict) else None
    if last is None or last.get("ok") is not False:
        return False
    return _guard_repeat(dictated, last).get("operation") == "none"


def presses_a_spent_key(dictated: dict | None, view: dict) -> bool:
    """Ronda 21 (revisión 1, hallazgo b): a rule's step that presses a key spent on the view's application (one that
    brought up something not sought, or one the App's guard refused on a document the mission may not touch)."""

    if not isinstance(dictated, dict) or dictated.get("operation") != "input.key.press":
        return False
    arguments = dictated.get("arguments")
    key = str(arguments.get("key") or "") if isinstance(arguments, dict) else ""
    return bool(key) and key in _spent_keys(view)


def refused_by_the_guard(history: list[dict]) -> bool:
    """Ronda 21 (pasada r18 v3-36): the sub-goal's last step is a rule's or a learned key the App's guard refused on a
    document the mission may not touch (``refused``, never pressed): the next step is the model's."""

    last = history[-1] if history and isinstance(history[-1], dict) else None
    return last is not None and last.get("refused") is True and last.get("ok") is False
