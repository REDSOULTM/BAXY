"""Aids «same_call_closes» and «look_click_cap» (w9-bucle): a repeat the mind does not hand to the App, and the turn
answered in words from what ran (int10's long session of the notebook, 2026-10-23: a look and a click on the
calculator's «Sistema» seven times, the menu opening and closing, until context_shrunk)."""
import json
from pathlib import Path

import pytest

from baxy_mind.mind import LOOK_CLICK_NOT_RUN, NO_MORE_CALLS, NOT_RUN, SAME_CALL_NOT_RUN

from test_mind_final import _call, _mind, _say

OPENED = json.dumps({"status": "completed", "verification": "readback",
                     "observed": {"appId": "Calculadora", "foreground": True}})


def _view(state: str) -> str:
    return json.dumps({"status": "completed", "verification": "output_only",
                       "view": f"Ventana «Calculadora» (CalculatorApp, window 21038900), al frente\nControles:\n"
                               f"[0] MenuItem «Sistema» ({state})\n[1] Button «Uno»"})


def _toggled(state: str) -> str:
    return json.dumps({"status": "completed", "verification": "readback",
                       "observed": {"name": "Sistema", "kind": "MenuItem", "surfaceChanged": True,
                                    "effectObserved": True, "after": {"changed": [f"[0] MenuItem «Sistema» {state}"]}}})


LOOK = _call("input_visible_controls", {"application": "Calculadora"})
CLICK = _call("input_visible_click", {"label": "Sistema", "index": 0, "window": 21038900})


def _calculator(tmp_path: Path, looks: int) -> tuple:
    """The int10 turn: the calculator opened, then looks and clicks on «Sistema» as long as the mind hands them over."""
    script = [_call("app_open", {"appId": "Calculadora", "forControl": True})]
    for _ in range(looks):
        script += [LOOK, CLICK]
    mind, server = _mind(tmp_path, [*script, _say("Abrí la Calculadora."), _say("Abrí la Calculadora.")])
    step = mind.decide(1, "abre la calculadora")
    results = {"app_open": OPENED}
    ran, collapsed = [], True
    while step["kind"] == "action":
        operation = step["operation"]
        ran.append(operation)
        if operation == "input_visible_controls":
            result = _view("collapsed" if collapsed else "expanded")
        elif operation == "input_visible_click":
            collapsed = not collapsed
            result = _toggled("collapsed" if collapsed else "expanded")
        else:
            result = results[operation]
        step = mind.continue_turn(len(ran) + 1, result)
    return mind, server, ran, step


def _trace(mind) -> list[dict]:
    return [json.loads(line) for line in mind.trace.read_text(encoding="utf-8").splitlines()]


def test_the_calculators_menu_opened_and_closed_ends_at_the_third_same_look_and_click(tmp_path: Path,
                                                                                     monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server, ran, step = _calculator(tmp_path, looks=5)
    # app_open, then look-click with the menu closed, look-click with it open, twice each, and a fifth look: the click
    # after it would be the third with the menu closed. 10 calls instead of the 16 of int10.
    assert ran == ["app_open"] + ["input_visible_controls", "input_visible_click"] * 4 + ["input_visible_controls"]
    assert step["kind"] == "conversation" and step["reply"] == "Abrí la Calculadora."
    last = server.bodies[-1]
    assert last["tool_choice"] == "none"
    refused = [m for m in last["messages"] if m["role"] == "tool"][-1]["content"]
    assert refused.startswith(LOOK_CLICK_NOT_RUN + "\n[En este turno: ")
    assert "input_visible_click → no se ejecutó: la misma mirada y el mismo clic ya iban 2 veces]" in refused
    assert refused.endswith(NO_MORE_CALLS)
    row = [r for r in _trace(mind) if r.get("kind") == "look_click_closed"]
    assert len(row) == 1 and row[0]["operation"] == "input_visible_click"
    assert mind._turn["receipts"][-1]["completed"] is False


def test_without_the_aids_the_loop_goes_on_as_before(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_AYUDAS", "none")
    _, _, ran, _ = _calculator(tmp_path, looks=6)
    assert ran.count("input_visible_click") == 6


def test_a_same_click_after_a_look_that_saw_something_else_still_runs(tmp_path: Path, monkeypatch) -> None:
    # Notebook practice run (mxb-off s2): «Guardar como» not found twice; «Archivo» opened its menu, and the third
    # «Guardar como», after a look that saw that menu, saved the file.
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    look, save, file = (_call("input_visible_controls", {"application": "Bloc de notas"}),
                        _call("input_visible_click", {"label": "Guardar como"}),
                        _call("input_visible_click", {"label": "Archivo"}))
    missed = json.dumps({"status": "failed", "error": "visible_button_not_found"})
    opened = json.dumps({"status": "completed", "observed": {"surfaceChanged": True}})
    plain, menu = (json.dumps({"status": "completed", "view": "Bloc de notas\n[0] MenuItem «Archivo»"}),
                   json.dumps({"status": "completed", "view": "Bloc de notas\n[0] MenuItem «Guardar como»"}))
    mind, _ = _mind(tmp_path, [look, save, look, save, look, file, look, save, _say("Listo.")])
    mind.decide(1, "guárdalo")
    for index, result in enumerate([plain, missed, plain, missed, plain, opened, menu]):
        step = mind.continue_turn(2 + index, result)
    assert step["kind"] == "action" and step["operation"] == "input_visible_click"
    assert step["arguments"] == {"label": "Guardar como"}


@pytest.mark.parametrize("again", [{"label": "Biblioteca", "manner": None}, {"label": "Biblioteca"}])
def test_the_call_told_as_repeated_made_once_more_does_not_run(tmp_path: Path, monkeypatch, again: dict) -> None:
    # same_call_next tells a click that failed the same way twice; the same click again (the same arguments, a key
    # written as null or left out alike) is answered in words, and the look queued behind it does not run either.
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    unchanged = json.dumps({"status": "failed", "error": "visible_button_postread_unchanged"})
    click = _call("input_visible_click", {"label": "Biblioteca"})
    repeat = {"choices": [{"message": {"content": "", "tool_calls": [
        {"id": "c9", "function": {"name": "input_visible_click", "arguments": json.dumps(again)}},
        {"id": "c10", "function": {"name": "input_visible_controls", "arguments": "{}"}}]}}]}
    mind, server = _mind(tmp_path, [click, click, repeat, _say("No pude entrar en la biblioteca."),
                                    _say("No pude entrar en la biblioteca.")])
    mind.decide(1, "entra en la biblioteca")
    mind.continue_turn(2, unchanged)
    step = mind.continue_turn(3, unchanged)
    assert step["kind"] == "conversation" and step["reply"] == "No pude entrar en la biblioteca."
    results = [m for m in server.bodies[-1]["messages"] if m["role"] == "tool"]
    assert "ya se llamó 2 veces en este turno" in results[1]["content"]
    tools = {m["tool_call_id"]: m["content"] for m in results}
    assert tools["c9"].startswith(SAME_CALL_NOT_RUN + "\n[En este turno: ")
    assert "input_visible_click → no se ejecutó: la misma llamada otra vez tras el aviso]" in tools["c9"]
    assert tools["c10"] == NOT_RUN
    assert [r["kind"] for r in _trace(mind) if r.get("kind", "").endswith("_closed")] == ["same_call_closed"]


def test_the_same_call_with_other_arguments_after_the_notice_runs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    unchanged = json.dumps({"status": "failed", "error": "visible_button_postread_unchanged"})
    click = _call("input_visible_click", {"label": "Biblioteca"})
    mind, _ = _mind(tmp_path, [click, click, _call("input_visible_click", {"label": "BIBLIOTECA", "index": 3}),
                               _say("Listo.")])
    mind.decide(1, "entra en la biblioteca")
    mind.continue_turn(2, unchanged)
    step = mind.continue_turn(3, unchanged)
    assert step["kind"] == "action" and step["arguments"] == {"label": "BIBLIOTECA", "index": 3}


def test_the_call_told_as_repeated_runs_again_after_another_call(tmp_path: Path, monkeypatch) -> None:
    # E011 (TurnClosing): calculator_window_not_found twice, then app_open, and the same sum completes.
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    missing = json.dumps({"status": "failed", "error": "calculator_window_not_found"})
    total = _call("calculator_expression_evaluate", {"expression": "250+175*2"})
    mind, _ = _mind(tmp_path, [total, total, _call("app_open", {"appId": "Calculadora"}), total, _say("Da 850.")])
    mind.decide(1, "en la calculadora suma 250 más 175 y luego multiplica por 2")
    mind.continue_turn(2, missing)
    assert mind.continue_turn(3, missing)["operation"] == "app_open"
    step = mind.continue_turn(4, OPENED)
    assert step["kind"] == "action" and step["operation"] == "calculator_expression_evaluate"
