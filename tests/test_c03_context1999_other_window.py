"""CONTEXT1999 (H0263 «cambiá a la otra ventana», H0528 «Quiero que lo veas y de que se trata?»):
the window inventory of this PC lists tiny untitled tool windows ahead of the real ones, and «lo»
with nothing named before is the active window, not the whole desktop."""

from __future__ import annotations

from baxy_mind import effect_intent
from baxy_mind.__main__ import _verified_dependency_identity_arguments

OPERATIONS = ("window.resolve", "window.focus", "capture.screenshot", "capture.active.window", "ocr.read")
TOOL = {"function": {"canonical_name": "window.focus", "parameters": {
    "type": "object", "properties": {"windowId": {"type": "string"}}, "required": ["windowId"], "additionalProperties": False}}}
# The inventory of CONTEXT1999 case 0, front to back, abridged.
INVENTORY = [
    {"windowId": "df1", "processName": "DisplayFusion", "title": "", "state": "normal", "foreground": False, "width": 33, "height": 29},
    {"windowId": "df2", "processName": "DisplayFusion", "title": "", "state": "normal", "foreground": False, "width": 33, "height": 29},
    {"windowId": "shell", "processName": "explorer", "title": "", "state": "normal", "foreground": False, "width": 0, "height": 0},
    {"windowId": "taskbar", "processName": "explorer", "title": "", "state": "normal", "foreground": False, "width": 1244, "height": 36},
    {"windowId": "notepad", "processName": "Notepad", "title": "Sin título: Bloc de notas", "state": "normal", "foreground": True, "width": 1243, "height": 732},
    {"windowId": "calc", "processName": "CalculatorApp", "title": "Calculadora", "state": "normal", "foreground": False, "width": 1257, "height": 794},
    {"windowId": "steam", "processName": "steamwebhelper", "title": "Steam", "state": "minimized", "foreground": False, "width": 1200, "height": 800},
]


def _observation(windows: list[dict]) -> list[dict]:
    return [{"stepId": "step_1", "operation": "window.resolve", "verified": True, "status": "completed",
             "result": {"windows": windows}}]


def test_the_other_window_is_the_titled_sizable_window_behind_the_foreground() -> None:
    assert _verified_dependency_identity_arguments(
        "window.focus", "cambiá a la otra ventana", _observation(INVENTORY), TOOL,
    ) == {"windowId": "calc"}


def test_the_other_window_wraps_to_the_front_when_the_foreground_is_last() -> None:
    inventory = [dict(w) for w in INVENTORY]
    inventory[4]["foreground"] = False
    inventory[5]["foreground"] = True  # the Calculator is in front, Notepad behind it in the list order
    assert _verified_dependency_identity_arguments(
        "window.focus", "switch to the other window", _observation(inventory), TOOL,
    ) == {"windowId": "notepad"}


def test_tool_windows_alone_ground_nothing() -> None:
    assert _verified_dependency_identity_arguments(
        "window.focus", "cambiá a la otra ventana", _observation(INVENTORY[:4]), TOOL,
    ) is None


def test_look_at_it_captures_the_active_window_only() -> None:
    intent = effect_intent.resolve_explicit_effects("Miralo y decime de qué se trata", OPERATIONS, previous_user_text=None)
    assert intent is not None and intent.operations == ("capture.active.window", "ocr.read")
