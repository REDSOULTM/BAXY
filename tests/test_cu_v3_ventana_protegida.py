"""Contract «Seguridad v2» with no application named (integration of round 2).

A mission that names no application works on the window in front. When that window is a developer's or BAXY's own
(VS Code, Visual Studio, a terminal, a console, BAXY) the view marks it ``protected`` by its process, and the mind takes
no step on it, asks no model, and the final says why in the person's words (data in operation_floor.v1.json).
"""

from __future__ import annotations

from baxy_mind import computer_use
from baxy_mind import cu_projection


class _NoModel:
    def chat(self, *args, **kwargs):  # pragma: no cover - reaching it is the failure
        raise AssertionError("no model is asked on a protected window")

    def __getattr__(self, name):  # pragma: no cover
        raise AssertionError(f"no model is asked on a protected window ({name})")


def _view(protected: bool) -> dict:
    window = {"title": "ComputerUseMission.cs - BAXY - Visual Studio Code", "process": "Code", "processId": 77, "hwnd": 999,
              "requested": False, "focused": {"kind": "Document", "name": "editor", "i": 0}}
    if protected:
        window["protected"] = True
    return {"window": window, "controls": [{"i": 0, "kind": "Document", "name": "editor", "state": "focused"}]}


def _decide(view: dict, goal: str = "apretar ctrl shift s") -> dict:
    return computer_use.decide_step(
        _NoModel(), objective="guardá esto como baxy-x.txt", goal=goal, application=None, success_check=None,
        view=view, history=[], budget_left=10, application_names=[],
    )


def test_a_protected_window_in_front_takes_no_step_with_no_application_named() -> None:
    decision = _decide(_view(protected=True))
    assert decision["operation"] == "none"
    assert decision.get("code") == "window_protected"


def test_an_unmarked_window_in_front_takes_the_dictated_step() -> None:
    # Counter-case: the same order on a window the view does not mark goes on (the deterministic key step).
    decision = _decide(_view(protected=False))
    assert decision["operation"] == "input.key.press"
    assert decision["arguments"]["key"] == "ctrl_shift_s"


def test_the_stop_is_said_in_the_persons_words() -> None:
    cause = cu_projection._STOP_CAUSES["computer_use_window_protected"]
    assert "no pulsé ni escribí nada" in cause["es"]
    assert "pressed and typed nothing" in cause["en"]
    assert "operación" not in cause["es"] and "computer_use" not in cause["es"]
