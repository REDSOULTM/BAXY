"""Prefijo c3, S4 (T6 of BRIEF_FT_C3): confirm_pending answers yes, no or unclear; an unclear answer leaves the call
waiting and the model asks again (the App's side: NativeTurnLoopTests, AnUnclearAnswer…)."""
import json

import pytest

ASKS = json.dumps({"status": "needs_confirmation", "next": "ask the person"})
ASKED_AGAIN = json.dumps({"status": "needs_confirmation", "operation": "app.close", "next": "ask the person again"})
CLOSED = json.dumps({"status": "completed", "verification": "readback", "observed": {"appId": "Calculadora"}})


def test_confirm_pending_answers_yes_no_or_unclear() -> None:
    from baxy_mind.mind import CONFIRM
    function = CONFIRM["function"]
    assert function["parameters"] == {"type": "object", "required": ["answer"], "properties": {
        "answer": {"type": "string", "enum": ["yes", "no", "unclear"]}}}
    assert "unclear when their words do not settle it" in function["description"]
    assert "approve" not in json.dumps(CONFIRM)


@pytest.fixture
def asked_again(tmp_path, monkeypatch):
    """BAXY asked whether to close the Calculator, the person's words settled nothing and the model asked again."""
    from test_mind_final import _call, _mind, _say
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    monkeypatch.delenv("BAXY_CONFIRM_FLOOR", raising=False)
    mind, server = _mind(tmp_path, [_call("app_close", {"appId": "Calculadora"}), _say("¿Cierro la Calculadora?"),
                                    _call("confirm_pending", {"answer": "unclear"}), _say("¿La cierro, sí o no?"),
                                    _say("Listo."), _say("Vale.")])
    mind.wire_to_op = {"app_close": "app.close"}
    mind.decide(1, "ciérrala")
    mind.continue_turn(2, ASKS, final=True)
    result = mind.decide(3, "no sé", {"operation": "app.close", "arguments": {"appId": "Calculadora"}})
    assert (result["operation"], result["arguments"]) == ("confirmation.answer", {"answer": "unclear"})
    mind.continue_turn(4, ASKED_AGAIN, final=True)
    return mind, server


def test_a_press_after_an_unclear_answer_names_the_call_that_still_waits(asked_again) -> None:
    mind, server = asked_again
    assert mind.confirm(5, True, "Sí")["arguments"] == {"answer": "yes"}
    call = mind.conversation[-1]["tool_calls"][0]["function"]
    assert (call["name"], json.loads(call["arguments"])) == ("confirm_pending", {"answer": "yes"})
    mind.continue_turn(6, CLOSED)
    facts = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]
    assert "[En este turno: confirm_pending (app_close) → completado y verificado" in facts


@pytest.mark.parametrize("ended, how", [("dropped", "su pregunta quedó sin respuesta"),
                                        ("expired", "se acabó el tiempo para contestar su pregunta")])
def test_a_question_asked_again_that_ended_unanswered_no_longer_waits(asked_again, ended, how) -> None:
    # Vivo larga (2026-10-27) held for the first question only: the confirm_pending an unclear answer left waiting
    # still said «espera el sí» in the clock and in its own turn once the question ended.
    from baxy_mind.mind import WAITS_FOR_YES

    from test_mind_w8_audit import _clock_of
    mind, server = asked_again
    mind.decide(5, "otra cosa", {"operation": "app.close", "ended": ended})
    clock = _clock_of(server)
    assert WAITS_FOR_YES not in clock
    assert f"app_close → no se ejecutó: {how}" in clock
    assert f"confirm_pending (app_close) → no se ejecutó: {how}" in clock
    facts = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"]
    assert len(facts) == 2 and not any(WAITS_FOR_YES in told for told in facts)
