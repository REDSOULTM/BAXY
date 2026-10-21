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


CLICK_UNSURE = json.dumps({"status": "failed", "error": "visible_surface_changed_while_waiting"})
CLICKED = json.dumps({"status": "completed", "observed": {"ok": True, "name": "TIENDA"}})


@pytest.mark.parametrize("setting,clicks,told", [("all", [CLICK_UNSURE, CLICK_UNSURE], 1), ("none", [CLICK_UNSURE], 0),
                                                 ("all", [CLICKED], 0)])
def test_a_click_that_fails_in_an_application_with_places_tells_them_once(tmp_path: Path, monkeypatch, setting: str,
                                                                          clicks: list[str], told: int) -> None:
    # Uso real 2026-10-20: seven clicks in Steam's web-drawn store while app_open opens its store and its search.
    monkeypatch.setenv("BAXY_AYUDAS", setting)
    script = [_call("app_open", {"appId": "Steam"})] + [_call("input_visible_click", {"label": "TIENDA"})] * len(clicks)
    mind, server = _mind(tmp_path, [*script, _say("Listo.")])
    mind.decide(1, "abre steam y entra en la tienda")
    mind.continue_turn(2, OPENED)
    for index, click in enumerate(clicks):
        mind.continue_turn(3 + index, click)
    tools = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"]
    notes = [t for t in tools if "[Ayuda: Steam también se abre directo en sus lugares" in t]
    assert len(notes) == told
    if told:
        assert notes[0].endswith("place community, game (placeValue: el número del juego), library, "
                                 "results (placeValue: lo que se busca), store.]")
        assert [r for r in _trace(mind) if r["stage"] == "turn.aid"][0]["aids"]["app_places_next"].startswith("[Ayuda")
    else:
        assert not [r for r in _trace(mind) if r["stage"] == "turn.aid"]


def test_a_look_that_fails_after_another_windows_look_still_names_the_opened_applications_places(
        tmp_path: Path, monkeypatch) -> None:
    # Uso real 2026-10-21: Epic opened and pressed, then its look found no window and the model looked at the browser.
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    not_found = json.dumps({"status": "failed", "error": "application_window_not_found"})
    looked = json.dumps({"status": "completed", "observed": {"ok": True}})
    script = [_call("app_open", {"appId": "Epic Games Launcher"}),
              _call("input_visible_controls", {"application": "Fortnite | Epic Games Store - Opera"}),
              _call("input_visible_controls", {"application": "Epic Games Launcher"}), _say("Listo.")]
    mind, server = _mind(tmp_path, script)
    mind.decide(1, "ahora en la app")
    mind.continue_turn(2, OPENED)
    mind.continue_turn(3, looked)
    mind.continue_turn(4, not_found)
    tool = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]
    assert tool.endswith("[Ayuda: Epic Games Launcher también se abre directo en sus lugares, sin pulsar: app_open con "
                         "appId «Epic Games Launcher» y place results (placeValue: lo que se busca), store.]")


LONG = "https://news.google.com/rss/articles/" + "CBMi" + "x" * 300 + "?oc=5"


@pytest.mark.parametrize("setting", ["all", "none"])
def test_a_long_address_reaches_the_model_as_a_short_reference_and_goes_back_whole(tmp_path: Path, monkeypatch,
                                                                                setting: str) -> None:
    # PLAN_GENERAL C1 (uso real 2026-10-20: ~500-token news addresses copied wrong, a 400 and a cut JSON).
    monkeypatch.setenv("BAXY_AYUDAS", setting)
    found = json.dumps({"status": "completed", "observed": {"results": [
        {"title": "Lluvia en Santiago", "url": LONG}, {"title": "Corto", "url": "https://example.org/a"}]}})
    shown = "ref:r1" if setting == "all" else LONG
    mind, server = _mind(tmp_path, [_call("web_search", {"query": "clima"}), _call("web_fetch", {"url": shown}),
                                    _say("Listo.")])
    mind.decide(1, "el clima de mañana")
    fetched = mind.continue_turn(2, found)
    tool = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]
    assert (LONG in tool) is (setting == "none")
    assert ("ref:r1" in tool) is (setting == "all")
    assert "https://example.org/a" in tool
    assert fetched["arguments"]["url"] == LONG


def test_the_same_call_with_the_same_result_a_third_time_is_told_once(tmp_path: Path, monkeypatch) -> None:
    # PLAN_GENERAL C2 (uso real: the same click 5-7 times with a look between each).
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    missed = json.dumps({"status": "failed", "error": "visible_button_not_found"})
    looked = json.dumps({"status": "completed", "observed": {"ok": True}})
    click, look = _call("input_visible_click", {"label": "FORTNITE"}), _call("input_visible_controls", {})
    mind, server = _mind(tmp_path, [click, look, click, look, click, look, click, _say("No pude.")])
    mind.decide(1, "busca fortnite ahí")
    for index, result in enumerate([missed, looked, missed, looked, missed, looked, missed]):
        mind.continue_turn(2 + index, result)
    tools = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"]
    told = [i for i, t in enumerate(tools) if "ya se hizo 3 veces" in t]
    assert told == [4]
    assert "input_visible_click ya se hizo 3 veces en este turno" in tools[4]


def test_the_applications_with_places_are_named_from_the_data(tmp_path: Path) -> None:
    # PLAN_GENERAL A6 (uso real 2026-10-21: Epic had places in the data, but the hand-written sentences did not name it).
    mind, _ = _mind(tmp_path, [])
    mind.configure({"capabilities": [{"name": "app.open", "description": "Open an app.", "argumentsSchema": {
        "type": "object", "properties": {"appId": {"type": "string"}, "place": {"type": "string"}}}}]})
    tool = next(t for t in mind.tools if t["function"]["name"] == "app_open")["function"]
    texts = tool["description"] + tool["parameters"]["properties"]["place"]["description"]
    assert "{app_places}" not in texts
    for app in ("«Epic Games Launcher» (results, store)", "«Steam» (", "«Discord» (directs)", "«Configuración» ("):
        assert app in texts


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
