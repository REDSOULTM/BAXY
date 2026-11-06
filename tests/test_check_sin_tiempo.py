"""The rule «answer_check» when the request's time runs out while the model writes its answer again (Mind._check_answer).
The App asks once more after a TimeoutError in a continue_turn (NativeTurnLoop, askedAgain: once per turn, and never after
a decision with no call before it), so the time spent there says nothing to the person until the last request. There, an
answer whose only finding is how far a read went is spoken; one that tells an act nothing completed, or a figure nothing
backs, is not. Every finding here is the real check's, on receipts of this file; the time spent is the fake server's."""
import json
from pathlib import Path

import pytest

from baxy_mind.answer_check import check
from baxy_mind.mind import CHECK_NOTE, COMPLETED_OUTCOMES, Mind, _outcome
from test_mind_final import _call, _mind, _say

NOTE = CHECK_NOTE[:13]  # «[Nota interna», how every note of the check starts

PAGE = {"status": "completed", "verification": "output_only",
        "observed": {"readInPart": True, "fromLine": 1, "toLine": 1904, "totalLines": 3000}}
SECOND_PAGE = {"status": "completed", "verification": "output_only",
               "observed": {"readInPart": True, "fromLine": 1905, "toLine": 2600, "totalLines": 3000}}
SCOPE = "La palabra zafiro no está en el archivo."  # all of the file, of a read that brought a part
HEDGED = "En las líneas que leí no aparece la palabra zafiro; me faltan las demás."

VIEW = {"status": "completed", "verification": "output_only",
        "view": "Ventana «Archivero» (archivero, window 4417), al frente\n"
                "Controles (no es la lista completa de la ventana: puede tener más):\n(no se leyó ninguno)\n"
                "(esta ventana no da sus controles: una línea de ahí se pulsa por su texto, como label, y que algo "
                "no salga en «Controles» no significa que no esté)\n"
                "Texto arriba: Archivero Ver Ayuda | INICIO ESTANTES | Página principal"}
NO_BUTTON = "No veo ningún botón «Estantes» en esa ventana."

CLOSE_FAILED = {"status": "failed", "error": "window_not_found"}
CLOSED_SAID = "Cerré Pizarra."

SIZE = {"status": "completed", "verification": "output_only", "observed": {"size": 3145728}}
SIZE_BENT = "El archivo pesa 30 MB."

CALCULATED = {"status": "completed", "verification": "readback", "observed": {
    "version": 1, "expression": "70000/800", "mode": "Standard", "value": "87,5"}}
RATE_SAID = "70.000 pesos son 87,5 euros con 800 pesos por euro."

WIRES = {"file_read": "file.read", "input_visible_controls": "input.visible.controls", "app_close": "app.close",
         "calculator_expression_evaluate": "calculator.expression.evaluate"}
READS = {"file.read", "input.visible.controls"}


def _spent() -> TimeoutError:
    return TimeoutError("the request's time budget is spent")


def _rules(answer: str, *results: tuple[str, dict]) -> list[str]:
    """What the check finds in an answer against these (operation, result): the answers below are found by it."""
    receipts = []
    for op, facts in results:
        observation = json.dumps(facts, ensure_ascii=False)
        outcome = _outcome(observation, read=op in READS)
        receipts.append({"op": op, "tool": op.replace(".", "_"), "arguments": {}, "observation": observation,
                         "outcome": outcome, "completed": outcome.startswith(COMPLETED_OUTCOMES), "read": op in READS})
    return [f["rule"] for f in check(answer, "", receipts, [(r["op"], r["completed"], r["read"]) for r in receipts])]


def _turn(tmp_path: Path, call: dict, *replies) -> tuple[Mind, object]:
    """A turn whose decision was that call, with what the model does after its result still to come."""
    mind, server = _mind(tmp_path, [call, *replies])
    mind.wire_to_op = dict(WIRES)
    assert mind.decide(1, "ocúpate de eso, por favor")["kind"] == "action"
    return mind, server


def _reading(tmp_path: Path, *replies) -> tuple[Mind, object]:
    return _turn(tmp_path, _call("file_read", {"path": "home/bitacora.log"}), *replies)


def _closing(tmp_path: Path, *replies) -> tuple[Mind, object]:
    return _turn(tmp_path, _call("app_close", {"appId": "Pizarra"}), *replies)


def _said(mind: Mind, answer: str) -> int:
    return sum(1 for m in mind.conversation if m["role"] == "assistant" and answer in str(m.get("content") or ""))


def _notes(messages: list[dict]) -> list[dict]:
    return [m for m in messages if NOTE in str(m.get("content") or "")]


def _spoken_once(mind: Mind, server, result: dict, answer: str) -> None:
    """The answer is the turn's last word, once and with no note, also in what the model reads in the next turn."""
    assert result["kind"] == "conversation" and result["reply"] == answer
    assert _said(mind, answer) == 1 and not _notes(mind.conversation)
    server.replies[:] = [_say("De nada.")]
    assert mind.decide(9, "gracias")["reply"] == "De nada."
    read = server.bodies[-1]["messages"]
    assert sum(1 for m in read if m["role"] == "assistant" and answer in str(m.get("content") or "")) == 1
    assert not _notes(read)


def _reply_or_nothing(mind: Mind, request_id: int, observation: str) -> str | None:
    try:
        return mind.continue_turn(request_id, observation).get("reply")
    except TimeoutError:
        return None


def test_a_rewrite_out_of_time_times_out_while_the_app_will_still_ask_again(tmp_path: Path) -> None:
    assert _rules(SCOPE, ("file.read", PAGE)) == ["partial"]
    mind, server = _reading(tmp_path, _say(SCOPE), _spent())
    with pytest.raises(TimeoutError):
        mind.continue_turn(2, json.dumps(PAGE))
    # It was the writing again that ran out, and nothing of it stays for the request the App repeats.
    assert server.bodies[-1]["messages"][-1]["content"].startswith(NOTE)
    assert _said(mind, SCOPE) == 0 and not _notes(mind.conversation)


def test_the_last_request_says_an_answer_that_only_overstates_a_partial_read(tmp_path: Path) -> None:
    mind, server = _reading(tmp_path, _say(SCOPE), _spent(), _say(SCOPE), _spent())
    observation = json.dumps(PAGE)
    with pytest.raises(TimeoutError):
        mind.continue_turn(2, observation)
    result = mind.continue_turn(3, observation)
    assert not _notes(server.bodies[3]["messages"])  # the repeat decides from the result, with no note left behind
    _spoken_once(mind, server, result, SCOPE)


def test_the_last_request_says_an_answer_that_only_misses_a_control_by_its_name(tmp_path: Path) -> None:
    assert _rules(NO_BUTTON, ("input.visible.controls", VIEW)) == ["named_control"]
    mind, server = _turn(tmp_path, _call("input_visible_controls", {"application": "Archivero", "includeText": True}),
                         _say(NO_BUTTON), _spent(), _say(NO_BUTTON), _spent())
    observation = json.dumps(VIEW, ensure_ascii=False)
    with pytest.raises(TimeoutError):
        mind.continue_turn(2, observation)
    _spoken_once(mind, server, mind.continue_turn(3, observation), NO_BUTTON)


def test_a_repeat_that_writes_nothing_says_the_answer_of_the_first_request(tmp_path: Path) -> None:
    # Another TimeoutError, or empty text (after which the model may be asked once more for words).
    observation = json.dumps(PAGE)
    for name, repeat in (("time", [_spent()]), ("empty", [_say(""), _say("")]), ("empty_then_time", [_say(""), _spent()])):
        (tmp_path / name).mkdir()
        mind, server = _reading(tmp_path / name, _say(SCOPE), _spent(), *repeat)
        with pytest.raises(TimeoutError):
            mind.continue_turn(2, observation)
        _spoken_once(mind, server, mind.continue_turn(3, observation), SCOPE)


def test_a_repeat_that_writes_an_answer_with_no_finding_says_that_one(tmp_path: Path) -> None:
    assert _rules(HEDGED, ("file.read", PAGE)) == []
    mind, server = _reading(tmp_path, _say(SCOPE), _spent(), _say(HEDGED))
    observation = json.dumps(PAGE)
    with pytest.raises(TimeoutError):
        mind.continue_turn(2, observation)
    _spoken_once(mind, server, mind.continue_turn(3, observation), HEDGED)
    assert _said(mind, SCOPE) == 0


def test_after_the_apps_one_repeat_a_later_request_of_the_turn_is_the_last(tmp_path: Path) -> None:
    # askedAgain lasts the whole turn: the repeat went to an earlier decision and brought one more call, and the App
    # will not ask for the decision after that call again.
    mind, server = _reading(tmp_path, _spent(), _call("file_read", {"path": "home/bitacora.log", "offset": 4000}),
                            _say(SCOPE), _spent())
    observation = json.dumps(PAGE)
    with pytest.raises(TimeoutError):
        mind.continue_turn(2, observation)
    assert mind.continue_turn(3, observation)["kind"] == "action"
    _spoken_once(mind, server, mind.continue_turn(4, json.dumps(SECOND_PAGE)), SCOPE)


def test_an_act_nothing_completed_is_not_said_for_lack_of_time(tmp_path: Path) -> None:
    assert _rules(CLOSED_SAID, ("app.close", CLOSE_FAILED)) == ["not_completed"]
    observation = json.dumps(CLOSE_FAILED)
    for name, repeat in (("time", [_spent()]), ("again", [_say(CLOSED_SAID), _spent()])):
        (tmp_path / name).mkdir()
        mind, _ = _closing(tmp_path / name, _say(CLOSED_SAID), _spent(), *repeat)
        for request_id in (2, 3):  # the App's last request too
            with pytest.raises(TimeoutError):
                mind.continue_turn(request_id, observation)
        assert _said(mind, CLOSED_SAID) == 0 and not _notes(mind.conversation)
    # A repeat with no words is no leave to say it either.
    (tmp_path / "empty").mkdir()
    mind, _ = _closing(tmp_path / "empty", _say(CLOSED_SAID), _spent(), _say(""), _say(""))
    with pytest.raises(TimeoutError):
        mind.continue_turn(2, observation)
    assert _reply_or_nothing(mind, 3, observation) != CLOSED_SAID
    assert _said(mind, CLOSED_SAID) == 0


def test_a_figure_that_bends_a_reading_is_not_said_for_lack_of_time(tmp_path: Path) -> None:
    assert _rules(SIZE_BENT, ("file.read", SIZE)) == ["number"]
    observation = json.dumps(SIZE)
    for name, repeat in (("time", [_spent()]), ("again", [_say(SIZE_BENT), _spent()])):
        (tmp_path / name).mkdir()
        mind, _ = _reading(tmp_path / name, _say(SIZE_BENT), _spent(), *repeat)
        for request_id in (2, 3):
            with pytest.raises(TimeoutError):
                mind.continue_turn(request_id, observation)
        assert _said(mind, SIZE_BENT) == 0


def test_a_rate_nobody_gave_is_not_said_for_lack_of_time(tmp_path: Path) -> None:
    # The rule «unsourced_number» is told once, and the answer after its note is the model's decision. A note that ran
    # out of time was never read: the same figure written in the App's repeat still has not been told anything.
    observation = json.dumps(CALCULATED)
    for name, repeat in (("time", [_spent()]), ("again", [_say(RATE_SAID), _spent()])):
        (tmp_path / name).mkdir()
        mind, server = _mind(tmp_path / name, [_call("calculator_expression_evaluate", {"expression": "70000/800"}),
                                               _say(RATE_SAID), _spent(), *repeat])
        mind.wire_to_op = dict(WIRES)
        mind.decide(1, "Con la calculadora dime cuánto son 70.000 pesos en euros.")
        with pytest.raises(TimeoutError):
            mind.continue_turn(2, observation)
        assert "800" in server.bodies[-1]["messages"][-1]["content"]  # the real finding's note, naming the figure
        with pytest.raises(TimeoutError):
            mind.continue_turn(3, observation)
        assert _said(mind, RATE_SAID) == 0


def test_a_finding_beyond_the_scope_of_a_read_keeps_the_answer_from_being_said(tmp_path: Path) -> None:
    # «Lo único»: a partial read beside a false act in one answer; and a repeat that writes the false act after an answer
    # of mere scope, which does not get spoken in its place.
    both = f"{SCOPE} {CLOSED_SAID}"
    assert set(_rules(both, ("file.read", PAGE), ("app.close", CLOSE_FAILED))) == {"partial", "not_completed"}
    assert _rules(SCOPE, ("file.read", PAGE), ("app.close", CLOSE_FAILED)) == ["partial"]
    close, failed = _call("app_close", {"appId": "Pizarra"}), json.dumps(CLOSE_FAILED)

    (tmp_path / "both").mkdir()
    mind, _ = _reading(tmp_path / "both", close, _say(both), _spent(), _spent())
    assert mind.continue_turn(2, json.dumps(PAGE))["kind"] == "action"
    for request_id in (3, 4):
        with pytest.raises(TimeoutError):
            mind.continue_turn(request_id, failed)
    assert _said(mind, CLOSED_SAID) == 0

    (tmp_path / "turned").mkdir()
    mind, _ = _reading(tmp_path / "turned", close, _say(SCOPE), _spent(), _say(CLOSED_SAID), _spent())
    assert mind.continue_turn(2, json.dumps(PAGE))["kind"] == "action"
    with pytest.raises(TimeoutError):
        mind.continue_turn(3, failed)
    assert _reply_or_nothing(mind, 4, failed) != CLOSED_SAID
    assert _said(mind, CLOSED_SAID) == 0


def test_a_decision_with_no_call_before_it_is_not_said_for_lack_of_time(tmp_path: Path) -> None:
    # The App repeats nothing here, so this request is the last one, and a false act still is not told.
    false = "Sí, ya cerré Pizarra."
    request = "¿Ya cerraste Pizarra?"
    assert [f["rule"] for f in check(false, request, [], [])]
    mind, server = _mind(tmp_path, [_say(false), _spent()])
    with pytest.raises(TimeoutError):
        mind.decide(1, request)
    assert len(server.bodies) == 2 and server.bodies[-1]["messages"][-1]["content"].startswith(NOTE)
    assert _said(mind, false) == 0 and not _notes(mind.conversation)


def test_with_no_finding_nothing_changes(tmp_path: Path) -> None:
    observation = json.dumps(PAGE)
    (tmp_path / "said").mkdir()
    mind, server = _reading(tmp_path / "said", _say(HEDGED))
    assert mind.continue_turn(2, observation)["reply"] == HEDGED
    assert len(server.bodies) == 2 and _said(mind, HEDGED) == 1  # nothing was asked again

    # And with no answer written there is nothing to say for lack of time: both requests time out.
    (tmp_path / "unwritten").mkdir()
    mind, _ = _reading(tmp_path / "unwritten", _spent(), _spent())
    for request_id in (2, 3):
        with pytest.raises(TimeoutError):
            mind.continue_turn(request_id, observation)
