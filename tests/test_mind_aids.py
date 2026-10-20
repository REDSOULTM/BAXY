"""The model aids of the mind (goal «ayudas al modelo», 2026-10-19): what they add to a result, that the trace keeps them
in a row apart from the model's decision, and that BAXY_AYUDAS=none gives back the mind as it was before them."""
import json
from pathlib import Path

import pytest

from baxy_mind.mind import Mind, beat_message

from test_mind_final import _call, _mind, _say

CLOSE_FAILED = json.dumps({"status": "failed", "error": "window_not_found"})
OPENED = json.dumps({"status": "completed", "observed": {"applicationName": "Paint"}})


def _two_calls(tmp_path: Path) -> tuple[Mind, list[str]]:
    mind, server = _mind(tmp_path, [_call("app_open", {"appId": "Paint"}), _call("app_close", {"appId": "Paint"}),
                                    _say("No pude cerrar Paint.")])
    mind.decide(1, "abre paint y ciérralo")
    mind.continue_turn(2, OPENED)
    mind.continue_turn(3, CLOSE_FAILED)
    tools = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"]
    return mind, tools


def _trace(mind: Mind) -> list[dict]:
    return [json.loads(line) for line in mind.trace.read_text(encoding="utf-8").splitlines()]


@pytest.mark.parametrize("setting", ["all", "none"])
def test_the_turn_line_is_the_one_of_the_starting_product_with_or_without_aids(tmp_path: Path, monkeypatch,
                                                                             setting: str) -> None:
    # Lever 5a (turn_facts, the line parted into done and not done) was measured and left out: falsedades s0-1 2+4
    # with it against 2+2 without it, and «de mi carpeta de trabajo» in 3 confirmation questions only with it.
    monkeypatch.setenv("BAXY_AYUDAS", setting)
    mind, tools = _two_calls(tmp_path)
    assert tools[1].endswith("\n[En este turno: app_open → completado y verificado; "
                             "app_close → falló (window_not_found)]")
    assert not [r for r in _trace(mind) if r["stage"] == "turn.aid"]


def test_the_cores_aids_are_traced_by_their_fields_and_never_change_the_result(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    calculator = json.dumps({"status": "failed", "error": "calculator_window_not_found",
                             "observed": {"next": "app_open can start the Calculator"}})
    mind, server = _mind(tmp_path, [_call("calculator_expression_evaluate", {"expression": "6*7"}),
                                    _say("Abro la Calculadora.")])
    mind.decide(1, "cuánto es 6 por 7 en la calculadora")
    mind.continue_turn(2, calculator)
    tool = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]
    assert tool.startswith(calculator + "\n")
    aid = [r for r in _trace(mind) if r["stage"] == "turn.aid"][0]
    assert aid["aids"] == {"calculator_next": {"next": "app_open can start the Calculator"}}
    # The model's own decision after the aid is its own row.
    assert _trace(mind)[-1]["stage"] == "turn.continue"


SETTINGS_AND_TRASH = {"capabilities": [
    {"name": "system.settings.set", "description": "Set a setting.", "argumentsSchema": {"type": "object", "properties": {}}},
    {"name": "filesystem.known.trash.named", "description": "Delete by name.",
     "argumentsSchema": {"type": "object", "properties": {}}}]}


def _description(mind: Mind, wire: str) -> str:
    return next(t for t in mind.tools if t["function"]["name"] == wire)["function"]["description"]


@pytest.mark.parametrize("setting,modes,folder", [("modes_sentence", False, False),
                                                  ("person_folder_sentence", False, True), ("none", False, False)])
def test_a_sentence_aid_ends_its_tools_description_only_when_on(tmp_path: Path, monkeypatch, setting: str,
                                                                modes: bool, folder: bool) -> None:
    monkeypatch.setenv("BAXY_AYUDAS", setting)
    mind, _ = _mind(tmp_path, [])
    mind.configure(SETTINGS_AND_TRASH)
    settings, trash = _description(mind, "system_settings_set"), _description(mind, "filesystem_known_trash_named")
    assert settings.endswith("do not turn on the accessible mode in its place.") is modes
    assert trash.endswith("the one filesystem_list shows).") is folder


@pytest.mark.parametrize("setting,shown", [("all", True), ("beat_no_pending", True), ("none", False)])
def test_a_beat_says_nothing_waits_for_a_yes_only_with_the_aid(monkeypatch, setting: str, shown: bool) -> None:
    # A beat only runs with no confirmation pending (MainWindowViewModel.CanBeat): the line is a fact by construction.
    monkeypatch.setenv("BAXY_AYUDAS", setting)
    message = beat_message({"weekday": "lunes", "now": "10:00", "owner_activity": "libre"})
    assert ("Confirmaciones pendientes: ninguna" in message) is shown
