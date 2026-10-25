"""H-ctx «vistas» (BAXY_RENEW_CTX=vistas): an older look replaced by a newer one of the same window, and an identical
result repeated later in the turn, reach the model once; off by default."""
import json
from pathlib import Path

from baxy_mind.context_vistas import SAME_RESULT, SUPERSEDED_VIEW

from test_mind_final import _call, _mind, _say

CONTROLS = "\n".join(f"[{i}] Button «Botón {i}» (centro)" for i in range(2, 30))


def _view(window: int, state: str) -> str:
    return json.dumps({"status": "completed", "verification": "output_only",
                       "view": f"Ventana «Calculadora» (CalculatorApp, window {window}), al frente\nFoco: [1] Button «Uno»\n"
                               f"Controles:\n[0] MenuItem «Sistema» ({state})\n[1] Button «Uno»\n{CONTROLS}"},
                      ensure_ascii=False)


CLICKED = json.dumps({"status": "completed", "verification": "readback",
                      "observed": {"name": "Sistema", "effectObserved": True, "after": {"changed": ["[0] expanded"]}}})
FAILED = json.dumps({"status": "failed", "error": "visible_button_postread_unchanged", "effectUncertain": True,
                     "observed": {"next": "clicking it changes nothing; the controls nearest it are " + "x" * 300}})


def _run(tmp_path: Path, monkeypatch, setting: str | None, results: list[str], calls: list[dict]) -> list[dict]:
    if setting is None:
        monkeypatch.delenv("BAXY_RENEW_CTX", raising=False)
    else:
        monkeypatch.setenv("BAXY_RENEW_CTX", setting)
    mind, server = _mind(tmp_path, [*calls, _say("Listo.")])
    step = mind.decide(1, "pon la calculadora en modo científico")
    for index, result in enumerate(results):
        assert step["kind"] == "action"
        step = mind.continue_turn(index + 2, result)
    assert step["kind"] == "conversation"
    return server.bodies


LOOK = _call("input_visible_controls", {"application": "Calculadora"})
CLICK = _call("input_visible_click", {"label": "Sistema", "index": 0, "window": 52888974})


def _tools(body: dict) -> list[str]:
    return [m["content"] for m in body["messages"] if m["role"] == "tool"]


def test_off_by_default_the_older_look_stays_whole(tmp_path: Path, monkeypatch) -> None:
    bodies = _run(tmp_path, monkeypatch, None, [_view(52888974, "collapsed"), CLICKED, _view(52888974, "expanded")],
                  [LOOK, CLICK, LOOK])
    tools = _tools(bodies[-1])
    assert "Botón 29" in tools[0] and "Botón 29" in tools[2]
    assert SUPERSEDED_VIEW[:30] not in "".join(tools)


def test_a_newer_look_of_the_same_window_leaves_the_older_view_in_short(tmp_path: Path, monkeypatch) -> None:
    results = [_view(52888974, "collapsed"), CLICKED, _view(52888974, "expanded")]
    plain = _run(tmp_path / "a", monkeypatch, None, results, [LOOK, CLICK, LOOK])
    bodies = _run(tmp_path / "b", monkeypatch, "vistas", results, [LOOK, CLICK, LOOK])
    last = bodies[-1]
    tools = _tools(last)
    older = json.loads(tools[0].split("\n[En este turno: ")[0])
    # The window line and the focus stay, the controls go with a note of how many; every other field stays.
    assert older["view"].startswith("Ventana «Calculadora» (CalculatorApp, window 52888974), al frente\nFoco:")
    assert older["view"].endswith(SUPERSEDED_VIEW.format(n=31))
    plain_tools = _tools(plain[-1])
    whole = json.loads(plain_tools[0].split("\n[En este turno: ")[0])
    assert "Botón 29" not in tools[0]
    assert {k: v for k, v in older.items() if k != "view"} == {k: v for k, v in whole.items() if k != "view"}
    # Its facts line, the click's result and the newest look stay as they came.
    assert tools[0].split("\n[En este turno: ")[1] == plain_tools[0].split("\n[En este turno: ")[1]
    assert tools[1:] == plain_tools[1:]
    # The person's words, BAXY's calls and the fixed prefix (system prompt, tools) are the same.
    assert last["messages"][0] == plain[-1]["messages"][0] and last["tools"] == plain[-1]["tools"]
    assert [m for m in last["messages"] if m["role"] != "tool"] == [m for m in plain[-1]["messages"] if m["role"] != "tool"]
    assert len(json.dumps(last)) < len(json.dumps(plain[-1])) - 600


def test_a_look_at_another_window_is_left_whole(tmp_path: Path, monkeypatch) -> None:
    bodies = _run(tmp_path, monkeypatch, "vistas", [_view(111, "collapsed"), CLICKED, _view(222, "expanded")],
                  [LOOK, CLICK, LOOK])
    tools = _tools(bodies[-1])
    assert "Botón 29" in tools[0] and "Botón 29" in tools[2]


def test_an_identical_failure_repeated_keeps_its_status_and_error_once_in_short(tmp_path: Path, monkeypatch) -> None:
    other = _call("input_visible_click", {"label": "Modo", "index": 3, "window": 52888974})
    bodies = _run(tmp_path, monkeypatch, "vistas", [FAILED, CLICKED, FAILED], [CLICK, other, CLICK])
    tools = _tools(bodies[-1])
    head = tools[0].split("\n[En este turno: ")[0]
    assert head.startswith('{"status":"failed","error":"visible_button_postread_unchanged","effectUncertain":true}\n')
    assert head.endswith(SAME_RESULT.format(tool="input_visible_click"))
    assert "x" * 300 not in tools[0] and "x" * 300 in tools[2]
    # The facts line still says the first click failed.
    assert "input_visible_click →" in tools[0].split("\n[En este turno: ")[1]


def test_a_short_result_repeated_is_left_as_it_is(tmp_path: Path, monkeypatch) -> None:
    short = json.dumps({"status": "completed", "verification": "readback", "observed": {"level": 30}})
    volume = _call("audio_volume", {"level": 30})
    plain = _run(tmp_path / "a", monkeypatch, None, [short, CLICKED, short], [volume, CLICK, volume])
    bodies = _run(tmp_path / "b", monkeypatch, "vistas", [short, CLICKED, short], [volume, CLICK, volume])
    assert _tools(bodies[-1]) == _tools(plain[-1])
