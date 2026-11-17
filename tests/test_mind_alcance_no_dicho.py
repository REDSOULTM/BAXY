"""Aid «said_scope», DIAX16 (DIAX12's bench, the 4B ×10: «Cierra Opera entero, que no quede nada abierto atrás» →
window_close_all 2 of 10, every window of the desktop; «Termina Steam, ya terminé de jugar» →
game_install_cancel_active 10 of 10, a download in progress cancelled). Before either runs, the model is asked apart
which application their words ask to close, or the call's own word when they ask for its whole reach; a name holds
it with what the call does, and in the turn it does not run again."""
import json
import re
from pathlib import Path

from baxy_mind import mind as mind_module
from test_mind_final import _call, _mind, _say


def _not_run(mind) -> list[dict]:
    told = []
    for message in mind.conversation:
        if message["role"] == "tool" and str(message.get("content")).startswith("{"):
            body = json.loads(str(message["content"]).split("\n", 1)[0])
            if body.get("status") == "not_run":
                told.append(body)
    return told


def _read_as(server, answer: str) -> list:
    asked = []
    plain = server.ask_apart

    def ask_apart(body, timeout=60.0):
        system = getattr(mind_module, "SCOPE_SYSTEM", "#none#")  # read at the call: the language rebinds it
        if body["messages"][0]["content"].startswith(system.split("{")[0]):
            asked.append(body)
            return {"choices": [{"message": {"content": answer}}]}
        return plain(body, timeout)

    server.ask_apart = ask_apart
    return asked


def test_closing_every_window_when_they_named_one_app_goes_back_with_what_it_closes(tmp_path: Path,
                                                                                   monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_call("window_close_all", {}), _call("app_close", {"appId": "Opera"})])
    asked = _read_as(server, "Opera")
    step = mind.decide(1, "Cierra Opera entero, que no quede nada abierto atrás")
    assert step["operation"] == "app_close" and step["arguments"] == {"appId": "Opera"}
    told = _not_run(mind)
    assert [t["error"] for t in told] == ["scope_not_asked"]
    assert "every open window of the desktop" in told[0]["reason"] and "app_close" in told[0]["next"]
    assert told[0]["theirWords"] == "Cierra Opera entero, que no quede nada abierto atrás"
    assert "«Cierra Opera entero, que no quede nada abierto atrás»" in asked[0]["messages"][1]["content"]
    assert asked[0]["grammar"].startswith('root ::= "todas" | ')


def test_cancelling_the_downloads_when_they_asked_to_close_the_launcher_goes_back(tmp_path: Path,
                                                                                 monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_call("game_install_cancel_active", {}), _call("app_close", {"appId": "Steam"})])
    asked = _read_as(server, "Steam")
    step = mind.decide(1, "Termina Steam, ya terminé de jugar")
    assert step["operation"] == "app_close"
    told = _not_run(mind)
    assert [t["error"] for t in told] == ["scope_not_asked"]
    assert "cancels the game downloads" in told[0]["reason"]
    assert asked[0]["grammar"].startswith('root ::= "descargas" | ')


def test_called_again_in_the_turn_it_is_held_again_and_answered_in_words(tmp_path: Path, monkeypatch) -> None:
    # As DIAX5 measured: told once and allowed again, the 4B repeats the call. The question is asked once in the turn.
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_call("window_close_all", {}), _call("window_close_all", {}),
                                    _say("¿Cierro sólo Opera o todas las ventanas?")])
    asked = _read_as(server, "Opera")
    step = mind.decide(1, "cierra Opera entero")
    assert step["kind"] != "action"
    assert [t["error"] for t in _not_run(mind)] == ["scope_not_asked", "scope_not_asked"]
    assert server.bodies[-1].get("tool_choice") == "none" and len(asked) == 1


def test_read_apart_as_the_whole_reach_it_runs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    for said, call, answer in (("cierra todas las ventanas", "window_close_all", "todas"),
                               ("cancela las descargas de steam", "game_install_cancel_active", "descargas")):
        mind, server = _mind(tmp_path, [_call(call, {})])
        _read_as(server, answer)
        assert mind.decide(1, said)["operation"] == call, said
        assert _not_run(mind) == [], said


def test_unreadable_it_runs_as_written_and_other_calls_are_not_asked(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_call("window_close_all", {})])
    _read_as(server, "")  # nothing written
    assert mind.decide(1, "cierra todo")["operation"] == "window_close_all"
    mind, server = _mind(tmp_path, [_call("app_close", {"appId": "Opera"})])
    asked = _read_as(server, "Opera")
    assert mind.decide(1, "cierra Opera")["operation"] == "app_close" and asked == []


def test_the_answer_to_baxys_question_is_read_with_that_question(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_call("window_close_all", {})])
    asked = _read_as(server, "todas")
    mind.new_session([{"role": "user", "content": "cierra Opera entero"},
                      {"role": "assistant", "content": "¿Cierro sólo Opera o todas las ventanas?"}])
    assert mind.decide(1, "todas")["operation"] == "window_close_all"
    note = asked[0]["messages"][1]["content"]
    assert "«cierra Opera entero»" in note and "todas las ventanas?»" in note and "«todas»" in note


def test_without_the_aid_it_runs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_AYUDAS", "none")
    mind, server = _mind(tmp_path, [_call("window_close_all", {})])
    asked = _read_as(server, "Opera")
    assert mind.decide(1, "Cierra Opera entero")["operation"] == "window_close_all" and asked == []


def test_in_english_what_it_tells_the_model_is_english(tmp_path: Path, monkeypatch) -> None:
    from baxy_mind import harness_language
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_call("game_install_cancel_active", {}), _say("Steam is closed.")])
    asked = _read_as(server, "Steam")
    mind.configure({"capabilities": [], "lang": "en"})
    try:
        mind.decide(1, "quit Steam, I'm done playing")
        told = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]
        assert "scope_not_asked" in told and "→ not run: it reached past" in told
        assert not re.search(r"[áéíóúñ¿¡]|se ejecutó", told), told
        assert not re.search(r"[áéíóúñ¿¡]", asked[0]["messages"][0]["content"] + asked[0]["messages"][1]["content"]
                             .replace("«quit Steam, I'm done playing»", ""))
    finally:
        harness_language.use("es")
