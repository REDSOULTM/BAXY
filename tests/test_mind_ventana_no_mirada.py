"""Aid «unopened_app», I7 (AMD A2, 06-11: TY1-3 and KP1, 12 of 12 samples): «escribe … en la ventana de <una app que no
existe>» with another window in front was typed at once, with no look: with no window, into the window in front; or with
a window number no result had shown («window»: 1). Only the form is compared: a window number that no result of the
conversation showed, or the window in front (as the App read it when the words arrived) that no result showed and no call
of the turn acted on. The call is not made; its result says which window it would have reached, as data, and the model
decides again with its tools, once per turn."""
import json
from pathlib import Path

from test_mind_final import _call, _mind, _say

DONE = json.dumps({"status": "completed", "verification": "readback"})
FRONT = {"title": "Sin título: Bloc de notas", "process": "Notepad"}
NOT_THERE = json.dumps({"status": "failed", "error": "app_not_found",
                        "observed": {"candidates": [{"title": "Sin título: Bloc de notas", "process": "Notepad"}]}})
LOOK = json.dumps({"status": "completed", "verification": "output_only",
                   "observed": {"view": "Ventana «Sin título: Bloc de notas» (Notepad, window 2623998), al frente"}})


def _not_run(mind) -> list[dict]:
    told = []
    for message in mind.conversation:
        if message["role"] == "tool" and str(message.get("content")).startswith("{"):
            body = json.loads(str(message["content"]).split("\n", 1)[0])
            if body.get("status") == "not_run":
                told.append(body)
    return told


def test_typing_into_the_window_in_front_nobody_looked_at_goes_back_with_that_window(
        tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("input_text_type", {"text": "buenas tardes"}),
                               _call("window_resolve", {"applicationName": "Granulo"}),
                               _say("No encontré ninguna ventana de Granulo.")])
    step = mind.decide(1, "pon buenas tardes en la ventana de Granulo", None, None, FRONT)
    assert step["kind"] == "action" and step["operation"] == "window_resolve"
    told = _not_run(mind)
    assert len(told) == 1 and told[0]["windowInFront"] == "«Sin título: Bloc de notas» (Notepad)"
    assert mind.continue_turn(2, NOT_THERE)["kind"] == "conversation"


def test_a_key_into_the_window_in_front_nobody_looked_at_is_not_pressed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("input_key_press", {"key": "ctrl_s"}),
                               _call("window_resolve", {"applicationName": "Granulo"})])
    assert mind.decide(1, "guarda lo de Granulo con control s", None, None, FRONT)["operation"] == "window_resolve"
    assert _not_run(mind)[0]["windowInFront"] == "«Sin título: Bloc de notas» (Notepad)"


def test_a_window_number_no_result_showed_is_not_used(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("input_text_type", {"text": "buenas tardes", "window": 1}),
                               _call("window_resolve", {"applicationName": "Granulo"})])
    assert mind.decide(1, "pon buenas tardes en la ventana de Granulo", None, None, FRONT)["operation"] == "window_resolve"
    told = _not_run(mind)
    assert len(told) == 1 and told[0]["window"] == 1 and "input_visible_controls" in told[0]["reason"]


def test_a_window_number_a_look_showed_is_used(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("input_visible_controls", {"application": "Bloc de notas"}),
                               _call("input_text_type", {"text": "buenas tardes", "window": 2623998})])
    assert mind.decide(1, "pon buenas tardes en el bloc de notas", None, None, FRONT)["operation"] == \
        "input_visible_controls"
    step = mind.continue_turn(2, LOOK)
    assert step["operation"] == "input_text_type" and step["arguments"]["window"] == 2623998
    assert _not_run(mind) == []


def test_the_window_in_front_a_result_of_an_earlier_turn_showed_is_typed_into(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("input_visible_controls", {"application": "Bloc de notas"}), _say("Lo veo."),
                               _call("input_text_type", {"text": "hola"})])
    mind.decide(1, "mira el bloc de notas", None, None, FRONT)
    mind.continue_turn(2, LOOK)
    assert mind.decide(3, "ahora escribe hola", None, None, FRONT)["operation"] == "input_text_type"
    assert _not_run(mind) == []


def test_after_a_call_of_the_turn_acted_the_typing_is_made(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("app_open", {"appId": "Paint", "foreground": True}),
                               _call("input_key_press", {"key": "ctrl_s"})])
    assert mind.decide(1, "abre paint y guarda con control s", None, None, FRONT)["operation"] == "app_open"
    assert mind.continue_turn(2, DONE)["operation"] == "input_key_press"
    assert _not_run(mind) == []


def test_it_is_told_once_and_the_models_next_typing_runs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    typing = _call("input_text_type", {"text": "hola"})
    mind, _ = _mind(tmp_path, [typing, typing])
    step = mind.decide(1, "escribe hola", None, None, FRONT)
    assert step["kind"] == "action" and step["operation"] == "input_text_type"
    assert len(_not_run(mind)) == 1


def test_told_the_window_in_front_a_window_number_nobody_showed_is_held_too(tmp_path: Path, monkeypatch) -> None:
    # I7 bench (H-TY-1, seed 0): told where the typing would go, the model typed again with «window»: 1
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("input_text_type", {"text": "buenas tardes"}),
                               _call("input_text_type", {"text": "buenas tardes", "window": 1}),
                               _call("window_resolve", {"applicationName": "Granulo"})])
    assert mind.decide(1, "pon buenas tardes en Granulo", None, None, FRONT)["operation"] == "window_resolve"
    assert [sorted(body) for body in _not_run(mind)] == [["delivered", "reason", "status", "windowInFront"],
                                                        ["delivered", "reason", "status", "window"]]


def test_with_no_window_in_front_told_the_typing_is_made_as_before(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("input_text_type", {"text": "hola"})])
    assert mind.decide(1, "escribe hola")["operation"] == "input_text_type"
    assert _not_run(mind) == []


def test_without_the_aid_both_are_made(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_AYUDAS", "none")
    mind, _ = _mind(tmp_path, [_call("input_text_type", {"text": "hola", "window": 1})])
    assert mind.decide(1, "escribe hola en Granulo", None, None, FRONT)["arguments"]["window"] == 1


def test_a_held_typing_or_key_says_nothing_reached_any_window(tmp_path: Path, monkeypatch) -> None:
    # I7 bench (A2-TY3, seed 1) and I9 (the same case, 3 of 4 seeds): told only where a typing with no window would go
    # («windowInFront»), the model answered «I typed hello in Notepad». The App's own typing and key results say whether
    # the keys reached a window in «delivered» (WindowsDesktopInteractionAdapter); a held one says it too, false, before
    # where it would have gone.
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("input_text_type", {"text": "hello"}),
                               _call("input_key_press", {"key": "enter", "window": 4}),
                               _call("window_resolve", {"applicationName": "Granulo"})])
    assert mind.decide(1, "write hello in the Granulo window and press enter", None, None, FRONT)["operation"] == \
        "window_resolve"
    named, _ = _mind(tmp_path / "named", [_call("input_text_type", {"text": "hola"}), _say("No.")])
    named.names = ["Paint"]
    named.decide(1, "escribe hola en Paint", None, None, FRONT)
    told = _not_run(mind) + _not_run(named)
    assert [body.get("delivered") for body in told] == [False, False, False]
    assert all(body["reason"].startswith("this call was not made: nothing was typed or pressed") for body in told)


# I12 (R4's review of I9, A2): «escribe hola aquí» with a question first: the mind answered the question with the window
# in front (encargo 119's ask_front, a not_run result) and then held the typing, saying no result had shown that window.
# I13 (R5-2): counted as shown, the told window let «escribe hola en la ventana de Zumbalo» go into it with no hold. The
# mind's own word is no call that found the window: the typing is held, and the held result does not deny what was told.
def test_the_window_in_front_the_mind_told_instead_of_a_question_holds_the_typing_once(tmp_path: Path,
                                                                                    monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    typing = _call("input_text_type", {"text": "hola"})
    for n, words in enumerate(("escribe hola en la ventana de Zumbalo", "escribe hola aquí")):
        mind, _ = _mind(tmp_path / str(n), [_call("ask_user", {"question": "¿Dónde lo escribo?"}), typing, typing])
        step = mind.decide(1, words, None, None, FRONT)
        assert step["kind"] == "action" and step["operation"] == "input_text_type", n
        told, held = _not_run(mind)
        assert "Sin título: Bloc de notas" in told["reason"] and "delivered" not in told, n
        assert held["windowInFront"] == "«Sin título: Bloc de notas» (Notepad)" and held["delivered"] is False, n
        assert "showed" not in held["reason"] and "no call of this conversation found that window" in held["reason"], n


# I12 (R4, A3): the process in front was found as any whole word of any result, so «"code": 200» of a web search showed
# VS Code (process «Code») and «escribe hola en la ventana de Zumbalo» was typed into it. A window is shown by a field of
# a result that names a window (title, process, processName) or by the form a look writes it in («title» (process, …).
CODE = {"title": "mind.py - BAXY - Visual Studio Code", "process": "Code"}


def test_a_word_of_the_process_in_front_in_another_result_does_not_show_it(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("web_search", {"query": "zumbalo"}), _say("ok"),
                               _call("input_text_type", {"text": "hola"}), _say("x")])
    mind.decide(1, "busca zumbalo", None, None, CODE)
    mind.continue_turn(2, json.dumps({"status": "completed", "observed": {"code": 200, "results": [
        {"title": "Code of conduct", "snippet": "code"}]}}))
    step = mind.decide(3, "escribe hola en la ventana de Zumbalo", None, None, CODE)
    assert step["kind"] != "action"
    assert [body.get("windowInFront") for body in _not_run(mind)] == ["«mind.py - BAXY - Visual Studio Code» (Code)"]


def test_a_look_or_a_receipt_that_names_the_window_in_front_shows_it(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    look = json.dumps({"status": "completed", "observed": {
        "view": "Ventana «mind.py - BAXY - Visual Studio Code» (Code, window 7340), al frente"}})
    active = json.dumps({"status": "completed", "observed": {"title": "otra", "process": "Code", "windowId": "win_7"}})
    opened = json.dumps({"status": "completed", "observed": {"window": 7340, "processName": "code"}})
    for n, shown in enumerate((look, active, opened)):
        mind, _ = _mind(tmp_path / str(n), [_call("window_active", {}), _say("ok"),
                                            _call("input_text_type", {"text": "hola"})])
        mind.decide(1, "qué ventana tengo", None, None, CODE)
        mind.continue_turn(2, shown)
        assert mind.decide(3, "escribe hola", None, None, CODE)["operation"] == "input_text_type", n
        assert _not_run(mind) == []


# I12 (R4, B1): a key queued behind a held typing («escribe hola y pulsa enter») came back «the call before it … did not
# complete», with no «delivered»: what I9 closed for the first call. As Anthropic's computer use tool returns each later
# action of a batch («Not executed: an earlier computer action in this turn failed»), it says nothing reached a window.
def test_a_key_queued_behind_a_held_typing_says_nothing_reached_any_window(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    two = {"choices": [{"message": {"content": "", "tool_calls": [
        {"id": "c1", "function": {"name": "input_text_type", "arguments": json.dumps({"text": "hola"})}},
        {"id": "c2", "function": {"name": "input_key_press", "arguments": json.dumps({"key": "enter"})}}]}}]}
    mind, _ = _mind(tmp_path, [two, _say("x")])
    mind.decide(1, "escribe hola en Zumbalo y pulsa enter", None, None, FRONT)
    told = _not_run(mind)
    assert [body.get("delivered") for body in told] == [False, False]
    assert told[1]["reason"].startswith("this call was not made: nothing was typed or pressed in any window")
    assert "the call before it in this turn did not complete" in told[1]["reason"]


# I12 (R4, B2): the held result sent the model to window_resolve or window_active for a window number, and those give a
# windowId («win_…»), not the number typing takes: it comes from a look at the window (input_visible_controls, «window N»)
# or from app_open's «window».
def test_a_held_result_names_only_the_calls_that_give_a_window_number(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("input_text_type", {"text": "hola"}),
                               _call("input_text_type", {"text": "hola", "window": 1}), _say("x")])
    mind.decide(1, "pon hola en Granulo", None, None, FRONT)
    told = _not_run(mind)
    assert len(told) == 2
    for body in told:
        assert "window_resolve" not in body["reason"] and "window_active" not in body["reason"]
        assert "input_visible_controls" in body["reason"]


# I12 (R4, A1): after the hold the model looked at the window in front by the name the hold gave it and typed there. The
# held result says the way out, and the model decides with the person's words: a window they name is looked at by its
# name, one no look shows is not open (nothing is typed in this one); a typing for the window in front runs when made again.
def test_a_held_result_says_how_to_end_it_when_the_window_named_is_not_open(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("input_text_type", {"text": "hola"}),
                               _call("input_text_type", {"text": "hola", "window": 1}), _say("x")])
    mind.decide(1, "pon hola en Granulo", None, None, FRONT)
    front, number = _not_run(mind)
    assert "make the call again as it was: this time it runs" in front["reason"]
    assert "If the person's words name another application or window, it is not this one" in front["reason"]
    for body in (front, number):
        assert "if no look shows it, it is not open: say so, and type or press nothing in" in body["reason"]


# I13 (R5's review of I12, R5-3): «escribe hola en la ventana de Zumbalo», and the model looked for Zumbalo first. The
# lookup failed listing every window open (WindowControlHandlers.Candidates), the one in front among them, and the typing
# with no window that followed went into the window in front with no hold. A window is shown by a result of a call that
# completed: a failed lookup found nothing under that name, and its own «next» says to resolve the one meant again.
LISTED = json.dumps({"status": "failed", "error": "application_window_not_found", "observed": {
    "candidateCount": 2, "candidates": [{"title": "Sin título: Bloc de notas", "process": "Notepad"},
                                        {"title": "Calculadora", "process": "CalculatorApp"}]}})


def test_the_window_in_front_listed_by_a_lookup_that_failed_is_not_shown(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    for n, (looked, failed) in enumerate(((_call("window_resolve", {"applicationName": "Zumbalo"}), NOT_THERE),
                                          (_call("input_visible_controls", {"application": "Zumbalo"}), LISTED))):
        mind, _ = _mind(tmp_path / str(n), [looked, _call("input_text_type", {"text": "hola"}), _say("x")])
        mind.decide(1, "escribe hola en la ventana de Zumbalo", None, None, FRONT)
        assert mind.continue_turn(2, failed)["kind"] != "action", n
        assert [body.get("windowInFront") for body in _not_run(mind)] == ["«Sin título: Bloc de notas» (Notepad)"], n
        assert "no call of this conversation found that window or opened it" in _not_run(mind)[0]["reason"], n


# I13: with nothing that named it, the held result keeps I12's words («no result … showed that window»): «no call found
# that window» everywhere was read as no window open, and the window in front wanted was given up (bench, 8/8 → 3/8).
def test_a_window_in_front_nothing_named_is_said_not_shown(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("input_key_press", {"key": "enter"}), _say("x")])
    mind.decide(1, "dale enter", None, None, FRONT)
    reason = _not_run(mind)[0]["reason"]
    assert "no result of this conversation showed that window" in reason and "no call" not in reason


def test_a_lookup_that_completed_with_the_window_in_front_shows_it(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    found = json.dumps({"status": "completed", "verification": "output_only", "observed": {"version": 1, "windows": [
        {"windowId": "win_7", "processName": "Notepad", "title": "Sin título: Bloc de notas", "foreground": True}]}})
    mind, _ = _mind(tmp_path, [_call("window_resolve", {"process": "Notepad"}),
                               _call("input_text_type", {"text": "hola"})])
    mind.decide(1, "escribe hola en el bloc de notas", None, None, FRONT)
    assert mind.continue_turn(2, found)["operation"] == "input_text_type"
    assert _not_run(mind) == []


# I13 (R5-6): the process of the person's browser in a failed audio result («personBrowser», «appsWithAudio») is no window
# shown either: «silencia Zumbalo» failed naming chrome, and «escribe hola en la ventana de Mardunex» went into Chrome.
def test_the_browser_named_by_a_failed_audio_call_does_not_show_its_window(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    chrome = {"title": "YouTube - Google Chrome", "process": "chrome"}
    no_session = json.dumps({"status": "failed", "error": "app_audio_session_not_found_on_default_output", "observed": {
        "version": 1, "appsWithAudio": ["chrome"], "personBrowser": {"name": "Google Chrome", "process": "chrome"}}})
    mind, _ = _mind(tmp_path, [_call("audio_app_volume_set", {"app": "Zumbalo", "level": 0}), _say("No suena."),
                               _call("input_text_type", {"text": "hola"}), _say("x")])
    mind.decide(1, "silencia Zumbalo", None, None, chrome)
    mind.continue_turn(2, no_session)
    assert mind.decide(3, "escribe hola en la ventana de Mardunex", None, None, chrome)["kind"] != "action"
    assert [body.get("windowInFront") for body in _not_run(mind)] == ["«YouTube - Google Chrome» (chrome)"]


# I13 (R5-1): «abre la calculadora», then «escribe 2+2». The real app_open result has no title, and names the window by
# the program a view names it by (CalculatorApp, not its frame host ApplicationFrameHost: OpenedWindowFront); the App
# reads the window in front the same way (HeartbeatMoment.PersonFront), so that result shows it.
def test_an_application_in_a_frame_opened_in_an_earlier_turn_shows_the_window_in_front(tmp_path: Path,
                                                                                       monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    opened = json.dumps({"status": "completed", "verification": "readback", "observed": {
        "appId": "calculator", "displayName": "Calculadora", "alreadyRunning": False, "processId": 4242,
        "windowHandle": 655362, "windowId": "win_a1b2", "window": 655362, "processName": "CalculatorApp",
        "foreground": True}})
    mind, _ = _mind(tmp_path, [_call("app_open", {"appId": "calculator"}), _say("Listo."),
                               _call("input_text_type", {"text": "2+2"})])
    mind.decide(1, "abre la calculadora", None, None, FRONT)
    mind.continue_turn(2, opened)
    assert mind.decide(3, "escribe 2+2", None, None, {"title": "Calculadora", "process": "CalculatorApp"})[
        "operation"] == "input_text_type"
    assert _not_run(mind) == []
