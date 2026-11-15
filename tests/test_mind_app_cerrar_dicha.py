"""Aid «said_app» for app_close, INT36F (BAN2 b2p-41: «cierra la calculadora y el bloc de notas» became app_close
{appId: "Command Prompt"}, a name of the installed list nobody said, 6 of 10 on int36c; the 1.5.2 and int36b 0 of 10:
an application closed in silence, and the answer said the calculator was closed). The same form as for app_open: the
appId is a whole name of the installed list and none of its words is in the person's words of the conversation, in
BAXY's own, in any result nor in the window that was in front when they spoke («ciérrala», «cierra esto»), not even
close in spelling. Nothing is closed; the result says so, as data, and the model decides again, once per turn: the
same call again runs as written. A windowId comes from a result (window_active, window_resolve): it runs."""
import json
from pathlib import Path

from baxy_mind.mind import SAME_APP_SYSTEM
from test_mind_final import _call, _mind, _say

LIST = ("Opens an application. Installed applications (use one of these names as appId): Calculator; Command Prompt; "
        "File Explorer; Google Chrome; Microsoft Word; Notepad; Paint; Settings.")
ASKED = "cierra la calculadora y el bloc de notas"


def _with_list(tmp_path: Path, replies: list):
    mind, server = _mind(tmp_path, replies)
    app = {"type": "object", "properties": {"appId": {"type": "string"}, "windowId": {"type": "string"}}}
    mind.tools = [{"type": "function", "function": {"name": "app_open", "description": LIST, "parameters": app}},
                  {"type": "function", "function": {"name": "app_close", "description": "Close an open application.",
                                                    "parameters": app}}]
    return mind, server


def _not_run(mind) -> list[dict]:
    told = []
    for message in mind.conversation:
        if message["role"] == "tool" and str(message.get("content")).startswith("{"):
            body = json.loads(str(message["content"]).split("\n", 1)[0])
            if body.get("status") == "not_run":
                told.append(body)
    return told


def test_closing_a_listed_application_nobody_said_goes_back_with_their_words(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _with_list(tmp_path, [_call("app_close", {"appId": "Command Prompt"}),
                                         _call("app_close", {"appId": "Calculator"})])
    step = mind.decide(1, ASKED)
    assert step["kind"] == "action" and step["arguments"]["appId"] == "Calculator"
    told = _not_run(mind)
    assert len(told) == 1 and told[0]["appId"] == "Command Prompt" and told[0]["theirWords"] == ASKED
    assert told[0]["error"] == "application_not_named"
    assert "nothing was closed" in told[0]["reason"]
    held = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]
    assert "app_close → no se ejecutó: cerraba una aplicación que nadie nombró" in held


def test_a_short_alias_alone_is_not_a_name_said(tmp_path: Path, monkeypatch) -> None:
    # «ms dos» is a name of Command Prompt in app_aliases; «dos» alone in other words is no name of it.
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _with_list(tmp_path, [_call("app_close", {"appId": "Command Prompt"}),
                                    _call("app_close", {"appId": "Calculator"})])
    assert mind.decide(1, "cierra los dos, la calculadora y la otra")["arguments"]["appId"] == "Calculator"
    assert len(_not_run(mind)) == 1


def test_it_is_told_once_and_the_same_close_runs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    other = _call("app_close", {"appId": "Notepad"})
    mind, _ = _with_list(tmp_path, [other, other])
    assert mind.decide(1, "cierra lo que dejé abierto para escribir")["arguments"]["appId"] == "Notepad"
    assert len(_not_run(mind)) == 1


def test_an_application_said_or_shown_closes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    # A name of the same application in app_aliases.v1.json is that application said (b2p-41: «el bloc de notas»).
    for said, app in (("cierra la calculadora", "Calculator"), ("cierra el bloc de notas", "Notepad"), (ASKED, "Notepad"),
                      ("cierra el símbolo del sistema", "Command Prompt"), ("cierra el cmd", "Command Prompt"),
                      ("cierra el word porfa", "Microsoft Word"), ("cierra el chrome", "Google Chrome"), ("close paint", "Paint"),
                      ("ciérrame el cromo, porfa", "Google Chrome"), ("cierra la configuración", "Settings"),
                      ("cierra el explorador de archivos", "File Explorer")):
        mind, _ = _with_list(tmp_path, [_call("app_close", {"appId": app})])
        assert mind.decide(1, said)["arguments"]["appId"] == app, said
        assert _not_run(mind) == [], said


def test_the_window_in_front_closes_on_cierra_esto(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    for front in ({"title": "Sin título: Bloc de notas", "process": "Notepad"},
                  {"title": "Símbolo del sistema", "process": "Command Prompt"}):
        app = front["process"]
        mind, _ = _with_list(tmp_path, [_call("app_close", {"appId": app})])
        assert mind.decide(1, "ciérrala", front=front)["arguments"]["appId"] == app
        assert _not_run(mind) == []


def test_one_opened_turns_before_closes_on_ciérrala(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    opened = json.dumps({"status": "completed", "verification": "readback", "observed": {"appId": "Paint"}})
    mind, _ = _with_list(tmp_path, [_call("app_open", {"appId": "Paint"}), _say("Abrí Paint."),
                                    _call("app_close", {"appId": "Paint"})])
    mind.decide(1, "abre paint")
    mind.continue_turn(2, opened)
    assert mind.decide(3, "ya, ciérrala")["arguments"]["appId"] == "Paint"
    assert _not_run(mind) == []


def test_a_window_id_or_a_name_outside_the_list_closes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    for arguments in ({"windowId": "win_7"}, {"appId": "Belmora"}):
        mind, _ = _with_list(tmp_path, [_call("app_close", arguments)])
        assert mind.decide(1, "cierra esa")["arguments"] == arguments
        assert _not_run(mind) == []


def test_without_the_aid_it_closes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_AYUDAS", "none")
    mind, _ = _with_list(tmp_path, [_call("app_close", {"appId": "Command Prompt"})])
    assert mind.decide(1, ASKED)["arguments"]["appId"] == "Command Prompt"


def test_in_english_mode_the_close_line_has_no_spanish(tmp_path: Path, monkeypatch) -> None:
    from baxy_mind import harness_language

    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _with_list(tmp_path, [_call("app_close", {"appId": "Command Prompt"}),
                                         _call("app_close", {"appId": "Calculator"})])
    harness_language.use("en")
    try:
        mind.decide(1, "close the calculator and notepad")
    finally:
        harness_language.use("es")
    held = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]
    assert "app_close → not run: it would have closed an application nobody named" in held and "ejecut" not in held


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


def test_the_model_reads_apart_that_a_name_in_another_language_is_the_same_app(tmp_path: Path, monkeypatch) -> None:
    """INT36G (cn-18, «cierra el teclado en pantalla» for «On-Screen Keyboard»: with the result alone the 4B left it
    open 9 of 10): asked apart, «yes» closes it at once."""
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    said = "cierra el programa de dibujo"
    mind, server = _with_list(tmp_path, [_call("app_close", {"appId": "Paint"})])
    asked = _same_app_answers(server, "yes")
    step = mind.decide(1, said)
    assert step["kind"] == "action" and step["arguments"]["appId"] == "Paint" and _not_run(mind) == []
    note = asked[0]["messages"][1]["content"]
    assert f"«{said}»" in note and "«Paint»" in note and asked[0]["grammar"] == 'root ::= "yes" | "no"'


def test_another_app_read_apart_as_no_is_held(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _with_list(tmp_path, [_call("app_close", {"appId": "Command Prompt"}),
                                         _call("app_close", {"appId": "Calculator"})])
    _same_app_answers(server, "no")
    step = mind.decide(1, ASKED)
    assert step["arguments"]["appId"] == "Calculator"
    assert [t["appId"] for t in _not_run(mind)] == ["Command Prompt"]
