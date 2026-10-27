"""Aid «unopened_app» (feria 2026-10-27, case 13; live test 2026-10-27): «escribe en <app> <texto>» with that application
not open. The model typed with no window and the text went to whatever window was in front (BAXY's at the fair; in the
live test a window of the person's own, its receipt «sentTo» that window). A typing or a key with no window, in a turn
whose words name an installed application that no call of the turn opened, focused or resolved, is not handed to the
App: its result says so as data and the model decides again."""
import json
from pathlib import Path

from test_mind_final import _call, _mind, _say

DONE = json.dumps({"status": "completed", "verification": "readback"})
OPENED = json.dumps({"status": "completed", "verification": "window_appeared", "foreground": True})
APPS = ["Bloc de notas", "Calculadora", "Microsoft Word", "Spotify"]


def _trace(mind) -> list[dict]:
    return [json.loads(line) for line in mind.trace.read_text(encoding="utf-8").splitlines()]


def _not_run(mind) -> list[dict]:
    told = []
    for message in mind.conversation:
        if message["role"] == "tool" and str(message.get("content")).startswith("{"):
            body = json.loads(str(message["content"]).split("\n", 1)[0])
            if body.get("status") == "not_run":
                told.append(body)
    return told


def test_typing_into_a_named_app_nobody_opened_goes_back_to_the_model_and_after_app_open_it_types(
        tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_call("input_text_type", {"text": "hola quién eres"}),
                                    _call("app_open", {"appId": "Bloc de notas", "foreground": True}),
                                    _call("input_text_type", {"text": "hola quién eres"}),
                                    _say("Abrí el Bloc de notas y escribí «hola quién eres».")])
    mind.names = list(APPS)
    step = mind.decide(1, "Escribe en el bloc de notas hola quién eres")
    # The typing did not reach the App: the model decided again, with its tools, and opened the application.
    assert step["kind"] == "action" and step["operation"] == "app_open"
    told = _not_run(mind)
    assert len(told) == 1 and told[0]["application"] == ["Bloc de notas"] and "app_open" in told[0]["reason"]
    assert "tool_choice" not in server.bodies[1]  # not the last answer: the model may still call
    step = mind.continue_turn(2, OPENED)
    assert step["kind"] == "action" and step["operation"] == "input_text_type"
    assert step["arguments"]["text"] == "hola quién eres"
    assert mind.continue_turn(3, DONE)["reply"].startswith("Abrí el Bloc de notas")
    assert [r["kind"] for r in _trace(mind) if r.get("kind") == "unopened_app"] == ["unopened_app"]


def test_a_key_with_no_window_into_a_named_app_nobody_opened_is_not_pressed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("input_key_press", {"key": "ctrl_s"}),
                               _call("window_resolve", {"application": "Microsoft Word"})])
    mind.names = list(APPS)
    assert mind.decide(1, "dale ctrl s en microsoft word")["operation"] == "window_resolve"
    assert _not_run(mind)[0]["application"] == ["Microsoft Word"]


def test_it_is_told_once_and_the_models_next_typing_runs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    key = _call("input_key_press", {"key": "ctrl_end"})
    mind, _ = _mind(tmp_path, [key, key])
    mind.names = [*APPS, "Cursor"]
    step = mind.decide(1, "pulsa control fin en Cursor")
    assert step["kind"] == "action" and step["operation"] == "input_key_press"
    assert [body["application"] for body in _not_run(mind)] == [["Cursor"]]


def test_a_name_of_the_catalog_said_but_not_as_where_to_write_is_not_held(tmp_path: Path, monkeypatch) -> None:
    # PC-L, decision v6 2026-10-27: «escribe … donde tengo el cursor» was held for the app named Cursor and the model
    # opened it; only a name said as the place («en …», «in …») is where the text goes
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("input_text_type", {"text": "nos vemos el lunes"}),
                               _call("input_key_press", {"key": "ctrl_end"})])
    mind.names = [*APPS, "Cursor"]
    assert mind.decide(1, "escribe «nos vemos el lunes» donde tengo el cursor")["operation"] == "input_text_type"
    assert mind.decide(2, "pon el cursor al final")["operation"] == "input_key_press"
    assert _not_run(mind) == []


def test_a_key_after_typing_a_name_of_the_catalog_is_pressed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("input_text_type", {"text": "nos vemos en Spotify"}),
                               _call("input_key_press", {"key": "enter"})])
    mind.names = list(APPS)
    assert mind.decide(1, "escribe nos vemos en Spotify y pulsa enter")["operation"] == "input_text_type"
    assert mind.continue_turn(2, DONE)["operation"] == "input_key_press"
    assert _not_run(mind) == []


def test_a_completed_call_that_acted_naming_the_application_counts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("file_open", {"name": "informe.docx", "application": "Microsoft Word"}),
                               _call("input_text_type", {"text": "gracias"})])
    mind.names = list(APPS)
    assert mind.decide(1, "abre informe.docx con microsoft word y escribe gracias")["operation"] == "file_open"
    assert mind.continue_turn(2, DONE)["operation"] == "input_text_type"


def test_a_call_that_only_read_about_the_application_does_not_count(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("app_installed", {"appId": "Bloc de notas"}),
                               _call("input_text_type", {"text": "hola"}),
                               _call("app_open", {"appId": "Bloc de notas", "foreground": True})])
    mind.names = list(APPS)
    mind.risk = {"app_installed": "read_only"}
    assert mind.decide(1, "escribe hola en el bloc de notas")["operation"] == "app_installed"
    assert mind.continue_turn(2, DONE)["operation"] == "app_open"


def test_a_key_after_a_typing_into_a_given_window_is_pressed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("input_text_type", {"text": "hola", "window": 2623998}),
                               _call("input_key_press", {"key": "enter"})])
    mind.names = list(APPS)
    assert mind.decide(1, "escribe hola en el bloc de notas y pulsa enter")["operation"] == "input_text_type"
    assert mind.continue_turn(2, DONE)["operation"] == "input_key_press"
    assert _not_run(mind) == []


def test_a_field_of_the_last_look_is_left_as_it_is(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("input_text_type", {"text": "hola", "index": 4})])
    mind.names = list(APPS)
    assert mind.decide(1, "escribe hola en el bloc de notas")["arguments"]["index"] == 4


def test_typing_with_no_application_named_is_made_as_before(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("input_text_type", {"text": "hola"})])
    mind.names = list(APPS)
    step = mind.decide(1, "escribe hola")
    assert step["kind"] == "action" and step["operation"] == "input_text_type"


def test_an_application_named_only_in_the_text_to_type_is_not_where_it_goes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("input_text_type", {"text": "mañana instalo Spotify"})])
    mind.names = list(APPS)
    assert mind.decide(1, "escribe mañana instalo Spotify")["operation"] == "input_text_type"


def test_an_application_named_in_an_earlier_turn_does_not_count(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("app_open", {"appId": "Bloc de notas", "foreground": True}),
                               _say("Abrí el Bloc de notas."), _call("input_text_type", {"text": "hola"})])
    mind.names = list(APPS)
    assert mind.decide(1, "abre el bloc de notas")["operation"] == "app_open"
    assert mind.continue_turn(2, OPENED)["kind"] == "conversation"
    assert mind.decide(3, "ahora escribe hola")["operation"] == "input_text_type"


def test_an_application_named_in_the_answer_to_a_question_counts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("ask_user", {"question": "¿Dónde lo escribo?"}),
                               _call("input_text_type", {"text": "hola"}),
                               _call("app_open", {"appId": "Bloc de notas", "foreground": True})])
    mind.names = list(APPS)
    assert mind.decide(1, "escribe hola")["kind"] == "clarify"
    assert mind.decide(2, "en el bloc de notas")["operation"] == "app_open"
    assert _not_run(mind)[0]["application"] == ["Bloc de notas"]


def test_a_window_given_is_left_as_it_is(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("input_text_type", {"text": "hola", "window": 2623998})])
    mind.names = list(APPS)
    step = mind.decide(1, "escribe hola en el bloc de notas")
    assert step["kind"] == "action" and step["arguments"]["window"] == 2623998


def test_without_the_aid_the_typing_is_made(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_AYUDAS", "none")
    mind, _ = _mind(tmp_path, [_call("input_text_type", {"text": "hola"})])
    mind.names = list(APPS)
    assert mind.decide(1, "escribe hola en el bloc de notas")["operation"] == "input_text_type"
