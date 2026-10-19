"""The model aids of the mind (goal «ayudas al modelo», 2026-10-19): what they add to a result, that the trace keeps them
in a row apart from the model's decision, and that BAXY_AYUDAS=none gives back the mind as it was before them."""
import json
from pathlib import Path

import pytest

from baxy_mind.mind import Mind

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


def test_a_turn_with_a_failed_call_parts_what_was_done_from_what_was_not(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, tools = _two_calls(tmp_path)
    # The first result had nothing that failed: the line of the starting product.
    assert tools[0].endswith("\n[En este turno: app_open → completado y verificado]")
    assert tools[1].endswith("\n[Hecho y verificado en este turno: app_open → completado y verificado. "
                             "No hecho: app_close → falló (window_not_found).]")
    rows = _trace(mind)
    aid = [r for r in rows if r["stage"] == "turn.aid"]
    assert len(aid) == 1 and aid[0]["operation"] == "app_close"  # no catalog configured: the wire name
    assert aid[0]["aids"]["turn_facts"].startswith("[Hecho y verificado en este turno:")
    # The model's own decision after the aid is its own row.
    assert rows[-1]["stage"] == "turn.continue" and rows[-1]["content"] == "No pude cerrar Paint."


def test_nothing_verified_is_said_as_nothing_and_an_unverified_call_apart(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_call("input_text_type", {"text": "hola"}), _say("Escribí hola.")])
    mind.decide(1, "escribe hola")
    mind.continue_turn(2, json.dumps({"status": "completed", "verified": False}))
    tool = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]
    assert tool.endswith("\n[Hecho y verificado en este turno: nada. "
                         "Sin verificar: input_text_type → completado sin verificar.]")


@pytest.mark.parametrize("setting", ["none", "0", "calculator_next"])
def test_with_the_aid_off_the_turn_line_is_the_one_of_the_starting_product(tmp_path: Path, monkeypatch,
                                                                         setting: str) -> None:
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
    assert aid["aids"]["calculator_next"] == {"next": "app_open can start the Calculator"}
    assert "turn_facts" in aid["aids"]


SETTINGS_AND_TRASH = {"capabilities": [
    {"name": "system.settings.set", "description": "Set a setting.", "argumentsSchema": {"type": "object", "properties": {}}},
    {"name": "filesystem.known.trash.named", "description": "Delete by name.",
     "argumentsSchema": {"type": "object", "properties": {}}}]}


def _description(mind: Mind, wire: str) -> str:
    return next(t for t in mind.tools if t["function"]["name"] == wire)["function"]["description"]


@pytest.mark.parametrize("setting,modes,folder", [("modes_sentence", True, False),
                                                  ("person_folder_sentence", False, True), ("none", False, False)])
def test_a_sentence_aid_ends_its_tools_description_only_when_on(tmp_path: Path, monkeypatch, setting: str,
                                                                modes: bool, folder: bool) -> None:
    monkeypatch.setenv("BAXY_AYUDAS", setting)
    mind, _ = _mind(tmp_path, [])
    mind.configure(SETTINGS_AND_TRASH)
    settings, trash = _description(mind, "system_settings_set"), _description(mind, "filesystem_known_trash_named")
    assert settings.endswith("do not turn on the accessible mode in its place.") is modes
    assert trash.endswith("the one filesystem_list shows).") is folder
