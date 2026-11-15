"""Aid «said_app», INT36A (gate H2: «Abre WordPad y escribe: …» became app_open {appId: "Notepad"}, a name of the list
of installed applications that the person did not say, 12 of 20 in Esencial on r4a and 0 of 20 on the 1.5.2; another
application opened and was typed into, in silence). Only the form is compared, as «said_place» compares a place: the
appId is a whole name of the installed list and none of its words is in the person's words of the conversation, in
BAXY's own nor in any result, not even close in spelling. Nothing is opened; the result says so, as data, with their
words as said, and the model decides again, once per turn: the same call again runs as written."""
import json
from pathlib import Path

from test_mind_final import _call, _mind, _say

LIST = ("Opens an application. Installed applications (use one of these names as appId): Calculator; File Explorer; "
        "Microsoft Edge; Microsoft Word; Notepad; Paint.")
ASKED = "Abre WordPad y escribe: reunión el lunes a las diez"


def _with_list(tmp_path: Path, replies: list):
    mind, server = _mind(tmp_path, replies)
    mind.tools = [{"type": "function", "function": {"name": "app_open", "description": LIST, "parameters": {
        "type": "object", "properties": {"appId": {"type": "string"}}, "required": ["appId"]}}}]
    return mind, server


def _not_run(mind) -> list[dict]:
    told = []
    for message in mind.conversation:
        if message["role"] == "tool" and str(message.get("content")).startswith("{"):
            body = json.loads(str(message["content"]).split("\n", 1)[0])
            if body.get("status") == "not_run":
                told.append(body)
    return told


def test_a_listed_application_nobody_said_goes_back_with_their_words(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _with_list(tmp_path, [_call("app_open", {"appId": "Notepad", "newDocument": True}),
                                         _call("app_open", {"appId": "WordPad"})])
    step = mind.decide(1, ASKED)
    assert step["kind"] == "action" and step["arguments"]["appId"] == "WordPad"
    told = _not_run(mind)
    assert len(told) == 1 and told[0]["appId"] == "Notepad" and told[0]["theirWords"] == ASKED
    assert told[0]["error"] == "application_not_named"
    # The line of the turn the model reads says it did not run, and why.
    held = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]
    assert "app_open → no se ejecutó: abría una aplicación que nadie nombró" in held


def test_it_is_told_once_and_the_same_call_runs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    other = _call("app_open", {"appId": "Notepad"})
    mind, _ = _with_list(tmp_path, [other, other])
    assert mind.decide(1, "abre el bloc de notas")["arguments"]["appId"] == "Notepad"
    assert len(_not_run(mind)) == 1


def test_an_application_said_in_the_words_opens(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    for said, app in (("abre notepad", "Notepad"), ("abre el word porfa", "Microsoft Word"),
                      ("abre la calculadora", "Calculator"), ("abre el explorador de archivos", "File Explorer"),
                      ("abreme el notepd", "Notepad"), ("open メモ帳", "Notepad"), ("abre edge", "Microsoft Edge")):
        mind, _ = _with_list(tmp_path, [_call("app_open", {"appId": app})])
        assert mind.decide(1, said)["arguments"]["appId"] == app, said
        assert _not_run(mind) == [], said


def test_a_name_outside_the_list_opens_as_written(tmp_path: Path, monkeypatch) -> None:
    # Whether it is installed is the result's to say (app_not_found, app_ambiguous), not this aid's.
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _with_list(tmp_path, [_call("app_open", {"appId": "Bloc de notas"})])
    assert mind.decide(1, "abre algo para escribir")["arguments"]["appId"] == "Bloc de notas"
    assert _not_run(mind) == []


def test_an_application_said_turns_before_or_offered_opens(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _with_list(tmp_path, [_say("Que te vaya bien."), _call("app_open", {"appId": "Paint"})])
    mind.decide(1, "después quiero dibujar algo en Paint")
    assert mind.decide(2, "ya, ábrelo")["arguments"]["appId"] == "Paint"
    assert _not_run(mind) == []
    mind, _ = _with_list(tmp_path, [_say("No tienes WordPad. ¿Abro Notepad?"), _call("app_open", {"appId": "Notepad"})])
    mind.decide(1, "¿tengo WordPad?")
    assert mind.decide(2, "bueno")["arguments"]["appId"] == "Notepad"
    assert _not_run(mind) == []


def test_an_application_a_result_showed_opens(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    found = json.dumps({"status": "completed", "verification": "output_only",
                        "observed": {"entries": [{"name": "apuntes.txt", "opensWith": "Notepad"}]}})
    mind, _ = _with_list(tmp_path, [_call("file_list", {"path": "Documentos"}), _call("app_open", {"appId": "Notepad"})])
    assert mind.decide(1, "abre mis apuntes con lo que corresponda")["operation"] == "file_list"
    assert mind.continue_turn(2, found)["arguments"]["appId"] == "Notepad"
    assert _not_run(mind) == []


def test_without_the_aid_it_opens(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_AYUDAS", "none")
    mind, _ = _with_list(tmp_path, [_call("app_open", {"appId": "Notepad"})])
    assert mind.decide(1, ASKED)["arguments"]["appId"] == "Notepad"


def test_in_english_mode_the_line_of_the_turn_has_no_spanish(tmp_path: Path, monkeypatch) -> None:
    from baxy_mind import harness_language

    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _with_list(tmp_path, [_call("app_open", {"appId": "Notepad"}), _call("app_open", {"appId": "WordPad"})])
    harness_language.use("en")
    try:
        mind.decide(1, "open WordPad and type: meeting on Monday at ten")
    finally:
        harness_language.use("es")
    held = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]
    assert "app_open → not run: it would have opened an application nobody named" in held and "ejecut" not in held
