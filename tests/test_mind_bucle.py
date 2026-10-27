"""Aids «same_call_closes» and «look_click_cap» (w9-bucle): a repeat the mind does not hand to the App, and the turn
answered in words from what ran (int10's long session of the notebook, 2026-10-23: a look and a click on the
calculator's «Sistema» seven times, the menu opening and closing, until context_shrunk)."""
import json
from pathlib import Path

import pytest

from baxy_mind.mind import (ASKED_AGAIN_NOT_RUN, LOOK_CLICK_NOT_RUN, NO_MORE_CALLS, NOT_RUN, SAID_AGAIN_NOTE,
                            SAME_CALL_NOT_RUN)

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


def test_a_question_alike_to_one_already_answered_in_the_turn_is_not_asked_again(tmp_path: Path, monkeypatch) -> None:
    # Aid «ask_once» (uso real 2026-10-26): the same clarifying question came back at each answer. The second one alike
    # (another article, the same letters at 0.9) is not asked; the model answers in words, with no tools.
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_call("ask_user", {"question": "¿Lo cambio en la pantalla o en una ventana?"}),
                                    _call("ask_user", {"question": "¿Lo cambio en toda la pantalla o en una ventana?"}),
                                    _say("Eso no lo hago.")])
    assert mind.decide(1, "cambia el tono")["kind"] == "clarify"
    step = mind.decide(2, "en toda la pantalla")
    assert step["kind"] == "conversation" and step["reply"] == "Eso no lo hago."
    last = server.bodies[-1]
    assert last["tool_choice"] == "none"
    assert [m for m in last["messages"] if m["role"] == "tool"][-1]["content"] == ASKED_AGAIN_NOT_RUN
    assert [r["kind"] for r in _trace(mind) if r.get("kind") == "ask_repeat_closed"] == ["ask_repeat_closed"]


def test_another_question_in_the_turn_is_asked(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("ask_user", {"question": "¿A qué hora?"}),
                               _call("ask_user", {"question": "¿Qué día?"})])
    mind.decide(1, "pon una alarma")
    step = mind.decide(2, "a las siete")
    assert step["kind"] == "clarify" and step["question"] == "¿Qué día?"


def test_without_the_aid_the_same_question_is_asked_again(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_AYUDAS", "none")
    ask = _call("ask_user", {"question": "¿Cuál?"})
    mind, _ = _mind(tmp_path, [ask, ask])
    mind.decide(1, "abre eso")
    assert mind.decide(2, "el otro")["kind"] == "clarify"


def test_the_last_answer_again_in_a_turn_with_no_call_is_written_once_more(tmp_path: Path, monkeypatch) -> None:
    # Aid «say_once» (uso real 2026-10-26): the same words turn after turn. The second time they are written again with
    # the note, words only; the second answer is spoken whatever it says, and the note does not stay.
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_say("Hola, ¿qué hacemos?"), _say("Hola, ¿Qué hacemos?"),
                                    _say("Aquí sigo, dime.")])
    assert mind.decide(1, "hola")["reply"] == "Hola, ¿qué hacemos?"
    step = mind.decide(2, "oye")
    assert step["kind"] == "conversation" and step["reply"] == "Aquí sigo, dime."
    last = server.bodies[-1]
    assert last["tool_choice"] == "none" and last["messages"][-1]["content"] == SAID_AGAIN_NOTE
    assert SAID_AGAIN_NOTE not in [m.get("content") for m in mind.conversation]
    assert mind.conversation[-1] == {"role": "assistant", "content": "Aquí sigo, dime."}
    assert len([r for r in _trace(mind) if r["stage"] == "turn.repeat"]) == 1


def test_the_last_answer_again_after_calls_is_written_once_more_and_another_answer_is_not(
        tmp_path: Path, monkeypatch) -> None:
    # uso real 2026-10-26: every search of the turn failed and the answer was the turn before's, letter for letter
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_say("Son las 10."), _call("system_status", {}), _say("Son las 10."),
                                    _say("No pude leer la hora del sistema."), _say("Hola.")])
    mind.decide(1, "¿qué hora es?")
    mind.decide(2, "¿y ahora?")
    assert mind.continue_turn(3, json.dumps({"status": "failed"}))["reply"] == "No pude leer la hora del sistema."
    assert mind.decide(4, "hola")["reply"] == "Hola."
    assert len(server.bodies) == 5


def test_without_the_aid_the_same_answer_is_said_again(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_AYUDAS", "none")
    mind, server = _mind(tmp_path, [_say("Hola."), _say("Hola.")])
    mind.decide(1, "hola")
    assert mind.decide(2, "hola")["reply"] == "Hola." and len(server.bodies) == 2


def test_a_click_that_failed_twice_with_only_looks_between_is_not_made_a_third_time(tmp_path: Path, monkeypatch) -> None:
    # Uso real 2026-10-26: the same «Reproducir» refused five times (protected_window), each look seeing a bit else.
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    look, play = (_call("input_visible_controls", {"application": "Música"}),
                  _call("input_visible_click", {"label": "Reproducir", "index": 48}))
    refused = json.dumps({"status": "failed", "error": "protected_window"})
    views = [json.dumps({"status": "completed", "view": f"Música\n[48] Button «Reproducir» {n}"}) for n in range(3)]
    mind, server = _mind(tmp_path, [look, play, look, play, look, play, _say("No pude pulsar Reproducir.")])
    mind.risk = {"input_visible_controls": "read_only"}  # as the catalog sends it: a look changes nothing
    mind.decide(1, "dale play")
    for index, result in enumerate([views[0], refused, views[1], refused, views[2]]):
        step = mind.continue_turn(2 + index, result)
    assert step["kind"] == "conversation" and step["reply"] == "No pude pulsar Reproducir."
    assert [r["kind"] for r in _trace(mind) if r.get("kind") == "look_click_closed"] == ["look_click_closed"]


def test_a_page_read_twice_is_not_read_a_third_time_whatever_the_size(tmp_path: Path, monkeypatch) -> None:
    # Uso real 2026-10-26: the same page read 14 times, only maximumCharacters going up.
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    page = "https://es.wikipedia.org/wiki/Ciencia"
    calls = [_call("web_fetch", {"url": page, "maximumCharacters": size}) for size in (500, 1000, 2000)]
    mind, _ = _mind(tmp_path, [*calls, _say("La ciencia es el conocimiento ordenado.")])
    read = json.dumps({"status": "completed", "observed": {"text": "La ciencia es..."}})
    mind.decide(1, "qué es la ciencia")
    step = mind.continue_turn(2, read)
    assert step["kind"] == "action" and step["arguments"]["maximumCharacters"] == 1000
    step = mind.continue_turn(3, read)
    assert step["kind"] == "conversation" and step["reply"] == "La ciencia es el conocimiento ordenado."
    assert [r["kind"] for r in _trace(mind) if r.get("kind") == "same_call_closed"] == ["same_call_closed"]


def test_a_call_that_turns_back_what_the_turn_set_is_not_made(tmp_path: Path, monkeypatch) -> None:
    # Uso real 2026-10-26: unmute, mute, unmute… seven times for «baja el volumen a 30».
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("audio_mute", {"state": False}), _call("audio_mute", {"state": True}),
                               _say("Quité el silencio.")])
    done = json.dumps({"status": "completed", "observed": {"muted": False}})
    mind.decide(1, "quita el silencio")
    step = mind.continue_turn(2, done)
    assert step["kind"] == "conversation" and step["reply"] == "Quité el silencio."
    assert [r["kind"] for r in _trace(mind) if r.get("kind") == "flip_closed"] == ["flip_closed"]


def test_the_same_operation_with_other_values_still_runs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("app_open", {"appId": "Calculadora"}), _call("app_open", {"appId": "Paint"})])
    mind.decide(1, "abre la calculadora y paint")
    step = mind.continue_turn(2, json.dumps({"status": "completed"}))
    assert step["kind"] == "action" and step["arguments"]["appId"] == "Paint"


SET_100 = _call("audio_volume", {"level": 100})
SET_DONE = json.dumps({"status": "completed", "verification": "readback", "observed": {"before": 30, "final": 100}})
SET_SAME = json.dumps({"status": "completed", "verification": "unchanged", "observed": {"final": 100}})


def test_a_set_repeated_after_it_changed_says_the_turn_set_it_and_is_not_made_a_third_time(tmp_path: Path,
                                                                                          monkeypatch) -> None:
    # Feria 2026-10-27: the volume set at the first call, the same set three times more, each «unchanged», and the
    # answer said it already was so. The repeat that came back unchanged says the turn's own call left it so; the same
    # call again after it is not made, and its result is the first one's.
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [SET_100, SET_100, SET_100, _say("Listo, en 100."), _say("Listo, en 100.")])
    mind.decide(1, "sube el volumen")
    assert mind.continue_turn(2, SET_DONE)["operation"] == "audio_volume"
    step = mind.continue_turn(3, SET_SAME)
    assert step["kind"] == "conversation" and step["reply"] == "Listo, en 100."
    tools = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"]
    assert "ya estaba así antes de esta llamada" not in tools[1]
    assert "audio_volume → ya había quedado así por la misma llamada hecha antes en este turno" in tools[1]
    refused = json.loads(tools[2].split("\n")[0])
    assert refused["status"] == "not_run" and refused["earlier"] == json.loads(SET_DONE)
    assert [r["kind"] for r in _trace(mind) if r.get("kind", "").endswith("_closed")] == ["unchanged_closed"]


def test_a_call_that_changed_something_each_time_still_runs_again(tmp_path: Path, monkeypatch) -> None:
    # A key or a click that does something each time it is made (a digit typed twice) is never taken as done.
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    key = _call("input_key_press", {"key": "down"})
    mind, _ = _mind(tmp_path, [key, key, key])
    pressed = json.dumps({"status": "completed", "verification": "readback"})
    mind.decide(1, "baja tres líneas")
    assert mind.continue_turn(2, pressed)["operation"] == "input_key_press"
    assert mind.continue_turn(3, pressed)["operation"] == "input_key_press"


def test_a_call_that_came_back_unchanged_runs_again_after_another_call_changed_something(tmp_path: Path,
                                                                                         monkeypatch) -> None:
    # A close of a window already gone, then the app opened: the same close again acts on what the turn changed.
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    close = _call("app_close", {"appId": "Paint"})
    mind, _ = _mind(tmp_path, [close, _call("app_open", {"appId": "Paint"}), close])
    gone = json.dumps({"status": "completed", "verification": "unchanged", "observed": {"alreadyGone": True}})
    mind.decide(1, "cierra paint, ábrelo y ciérralo")
    assert mind.continue_turn(2, gone)["operation"] == "app_open"
    step = mind.continue_turn(3, OPENED)
    assert step["kind"] == "action" and step["operation"] == "app_close"
