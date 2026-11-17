"""Aid «said_process», DIAX5 (CASX1, Notion H-049: «se pegó, apágalo y préndelo» with Spotify in front became
system_process_terminate_named {name: "chrome.exe"} 3 of 3 on the 1.5.5 and the 1.5.4; «está pegado, reinícialo» with
nothing in front, 3 of 3: a program nobody named killed with its unsaved work, unasked in Bypass). As «said_app» reads an
app_close: the program, without «.exe», is compared by form with the person's words of the conversation, BAXY's own,
and the results, and asked apart of the model (SAME_APP_*) when that finds nothing; the window in front does not name it
(H-049: «cerró Spotify sin preguntar»). Held, the result says so with the window in front; called again in the turn it
is held again and the model answers in words."""
import json
from pathlib import Path

from baxy_mind.mind import SAME_APP_SYSTEM
from test_mind_final import _call, _mind, _say

SPOTIFY = {"title": "Spotify Premium", "process": "Spotify"}


def _not_run(mind) -> list[dict]:
    told = []
    for message in mind.conversation:
        if message["role"] == "tool" and str(message.get("content")).startswith("{"):
            body = json.loads(str(message["content"]).split("\n", 1)[0])
            if body.get("status") == "not_run":
                told.append(body)
    return told


def _same_app_answers(server, answer: str) -> list:
    asked = []
    plain = server.ask_apart

    def ask_apart(body, timeout=60.0):
        if body["messages"][0]["content"] == SAME_APP_SYSTEM:
            asked.append(body)
            return {"choices": [{"message": {"content": answer}}]}
        return plain(body, timeout)

    server.ask_apart = ask_apart
    return asked


def test_a_program_nobody_named_is_held_with_the_window_in_front(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_call("system_process_terminate_named", {"name": "chrome.exe"}),
                                    _say("¿Quieres que reinicie Spotify?")])
    asked = _same_app_answers(server, "no")
    step = mind.decide(1, "se pegó, apágalo y préndelo", front=SPOTIFY)
    assert step["kind"] != "action"
    told = _not_run(mind)
    assert [t["error"] for t in told] == ["program_not_named"] and told[0]["name"] == "chrome.exe"
    assert told[0]["windowInFront"] == "«Spotify Premium» (Spotify)"
    assert "«chrome»" in asked[0]["messages"][1]["content"]


def test_called_again_it_is_held_again_and_answered_in_words(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    kill = _call("system_process_terminate_named", {"name": "chrome.exe"})
    mind, server = _mind(tmp_path, [kill, kill, _say("¿Qué programa quieres que cierre?")])
    _same_app_answers(server, "no")
    assert mind.decide(1, "está pegado, reinícialo")["kind"] != "action"
    assert len(_not_run(mind)) == 2 and server.bodies[-1].get("tool_choice") == "none"


def test_the_window_in_front_alone_does_not_name_it(tmp_path: Path, monkeypatch) -> None:
    # DIAX5: told chrome.exe was held with Spotify in front, the 4B killed Spotify 2 of 3; H-049 was «cerró Spotify sin
    # preguntar». The second unnamed kill of the turn is held too, and the model asks.
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_call("system_process_terminate_named", {"name": "chrome.exe"}),
                                    _call("system_process_terminate_named", {"name": "Spotify.exe"}),
                                    _say("¿Quieres que cierre Spotify a la fuerza?")])
    _same_app_answers(server, "no")
    assert mind.decide(1, "se pegó, apágalo y préndelo", front=SPOTIFY)["kind"] != "action"
    assert [t["error"] for t in _not_run(mind)] == ["program_not_named", "program_not_named"]
    assert _not_run(mind)[0]["name"] == "chrome.exe"


def test_a_program_said_or_shown_is_ended(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    for said, name, front, before in (
            ("mata el proceso de discord que me come la ram", "Discord.exe", None, []),
            ("fuerza el cierre del vlc que no responde", "vlc.exe", None, []),
            ("se pegó el spotify, ciérralo a la fuerza", "Spotify.exe", SPOTIFY, []),
            ("nel, mátalo", "Discord.exe", None, [{"role": "user", "content": "el discord no me deja entrar"},
                                                   {"role": "assistant", "content": "¿Quieres que reinicie Discord?"}])):
        mind, server = _mind(tmp_path, [_call("system_process_terminate_named", {"name": name})])
        asked = _same_app_answers(server, "no")
        mind.new_session(before)
        step = mind.decide(1, said, front=front)
        assert step["kind"] == "action" and step["arguments"]["name"] == name, said
        assert _not_run(mind) == [] and asked == [], said


def test_the_model_reads_apart_that_another_name_is_that_program(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_call("system_process_terminate_named", {"name": "WINWORD.EXE"})])
    asked = _same_app_answers(server, "yes")
    step = mind.decide(1, "el word no responde, ciérralo a la fuerza")
    assert step["kind"] == "action" and _not_run(mind) == [] and len(asked) == 1


def test_without_the_aid_it_runs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_AYUDAS", "none")
    mind, _ = _mind(tmp_path, [_call("system_process_terminate_named", {"name": "chrome.exe"})])
    assert mind.decide(1, "se pegó, apágalo y préndelo", front=SPOTIFY)["kind"] == "action"
