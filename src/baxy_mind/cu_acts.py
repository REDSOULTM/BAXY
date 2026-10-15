"""The shapes of the steps the engine dictates: a click, a text, a key, a reveal, a form field set by its label,
«none» with its code, and whether an act repeats the one that just failed.
"""

from __future__ import annotations

import re

from .semantic.missions import fold


# Line breaks, tabs and other control characters in a typed text are keys of their own: a line break in a chat box
# sends what was written without anyone asking. A typed step carries one line.
_TYPED_BREAKS = re.compile(r"[\x00-\x1f\x7f\x85\u2028\u2029]+")


def typed_text(text: str) -> str:
    return _TYPED_BREAKS.sub(" ", text)


def _reveal_arguments(name: str) -> dict[str, object]:
    """An element of a long list brought into view by its name through UI Automation (input.scroll with label): no
    wheel, no pointer, the window may stay behind the person's (goal v3 point 2). The deterministic «mostrar X» and the
    model's «reveal» act send the same."""

    return {"direction": "down", "amount": 10, "label": name[:256]}


def _form_field_arguments(control: dict, named: str, text: str) -> dict[str, object]:
    """A form's field set to a value by its label (input.text.type with field + replace: SetValue or EM_REPLACESEL to
    that field, no click, no Ctrl+A, no keyboard). The label without the colon that ends it on screen («Nombre de
    archivo:»): the shell folds both sides alike. The deterministic «poner X en V» and the model's «type» act with
    «field» send the same."""

    label = str(control.get("name") or named).rstrip(":： ").strip() or named
    return {"text": text[:4096], "field": label, "replace": True}


_REASON_FIND = "el destino no está en pantalla: lo busco"


def _click(control: dict, reason: str) -> dict[str, object]:
    arguments: dict[str, object] = {"label": str(control.get("name") or "")}
    if isinstance(control.get("i"), int):
        arguments["index"] = control["i"]
    return {"operation": "input.visible.click", "arguments": arguments, "reason": reason}


def _type(target: str) -> dict[str, object]:
    return {"operation": "input.text.type", "arguments": {"text": typed_text(target)}, "reason": _REASON_FIND}


def _key(key: str) -> dict[str, object]:
    return {"operation": "input.key.press", "arguments": {"key": key}, "reason": _REASON_FIND}


_ACT_KEYS = ("label", "key", "text", "direction", "appId", "field", "manner")


def _guard_repeat(decision: dict[str, object], last_failed: dict | None) -> dict[str, object]:
    if last_failed is None or last_failed.get("operation") != decision["operation"]:
        return decision
    arguments = decision["arguments"]
    assert isinstance(arguments, dict)
    same = all(
        fold(last_failed.get(key)) == fold(arguments.get(key))
        for key in _ACT_KEYS
        if key in arguments or key in last_failed
    )
    return _none("repetiría el paso que acaba de fallar", code="repeated_step") if same else decision


def _none(reason: str, *, code: str = "no_step_visible") -> dict[str, object]:
    return {"operation": "none", "arguments": {}, "reason": reason, "code": code}
