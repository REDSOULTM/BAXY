"""Contracts of the mind no earlier test held (review of «pruebas que no prueban», 2026-10-22): each one fails with the
mutation named beside it."""
import json
from pathlib import Path

import pytest

from test_mind_doubt_policy import FakeSystemOne, _call as _doubted, _correcting, _layer2, _mind as _doubt_mind
from test_mind_final import _call, _mind, _say


def _rows(tmp_path: Path) -> list[dict]:
    return [json.loads(line) for line in (tmp_path / "turns.jsonl").read_text(encoding="utf-8").splitlines()]


def _sure(name: str, arguments: dict, confidence: float) -> dict:
    """A call whose doubt reads `confidence` (p_call 0.95 × p_name)."""
    return _doubted(name, arguments, confidence / 0.95)


# a) The person's No and the pending confirmation (mutation: approve always True; the pending note dropped).
def test_a_no_on_a_confirmation_is_approve_false_in_the_call_and_the_conversation(tmp_path: Path) -> None:
    mind, _ = _mind(tmp_path, [])
    result = mind.confirm(1, False, "No")
    assert result["operation"] == "confirmation.answer" and result["arguments"] == {"approve": False}
    call = mind.conversation[-1]["tool_calls"][0]["function"]
    assert call["name"] == "confirm_pending" and json.loads(call["arguments"]) == {"approve": False}
    assert mind.conversation[-2] == {"role": "user", "content": "No"}


def test_a_pending_confirmation_is_told_in_the_clock(tmp_path: Path) -> None:
    mind, server = _mind(tmp_path, [_say("¿Lo borro?")])
    mind.decide(1, "sí", pending={"operation": "file.delete", "arguments": {"path": "a.txt"}})
    clock = server.bodies[0]["messages"][-2]["content"]
    assert clock.startswith("[Reloj:") and "file_delete" in clock and "confirm_pending" in clock


# b) The thresholds at their edges (mutation: < turned into <=, or the layers' order swapped).
@pytest.mark.parametrize("confidence, asks", [(0.39, True), (0.41, False)])
def test_layer_0_asks_just_under_its_threshold(tmp_path: Path, monkeypatch, confidence: float, asks: bool) -> None:
    monkeypatch.setenv("BAXY_S1_DOUBT", "0.4")
    monkeypatch.delenv("BAXY_S1_VETO", raising=False)
    mind, _ = _doubt_mind(tmp_path, [_sure("app_open", {"appId": "Paint"}, confidence), _say("¿Qué abro?")])
    assert (mind.decide(1, "abre eso")["operation"] is None) is asks


@pytest.mark.parametrize("confidence, consulted", [(0.59, True), (0.61, False)])
def test_layer_2_is_consulted_just_under_its_threshold(tmp_path: Path, monkeypatch, confidence: float,
                                                       consulted: bool) -> None:
    mind, _, one = _layer2(tmp_path, monkeypatch, "system_power", [_sure("system_power", {}, confidence)])
    assert mind.decide(1, "apaga el pc")["operation"] == "system.power"
    assert bool(one.asked) is consulted


def test_with_both_layers_an_unsure_action_asks_without_consulting_the_decision_model(tmp_path: Path,
                                                                                    monkeypatch) -> None:
    mind, _, one = _layer2(tmp_path, monkeypatch, "system_power", [_sure("system_power", {}, 0.3), _say("¿Qué?")])
    monkeypatch.setenv("BAXY_S1_DOUBT", "0.4")
    assert mind.decide(1, "apaga eso")["operation"] is None
    assert one.asked == []


# c) Layer 2 off without BAXY_S1_VETO (mutation: a default threshold for the veto).
def test_layer_2_is_off_without_its_threshold_even_with_the_decision_model_up(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_S1_DOUBT", raising=False)
    monkeypatch.delenv("BAXY_S1_VETO", raising=False)
    mind, _ = _doubt_mind(tmp_path, [_sure("system_power", {}, 0.3)])
    one = FakeSystemOne("app_close")
    mind.system_one = one  # type: ignore[assignment]
    assert mind.decide(1, "apaga el pc")["operation"] == "system.power"
    assert one.asked == []


# d) «corrige» only to a harmless tool or one the kernel confirms (mutation: CORRECTABLE_RISKS widened, or an unknown risk
# let through). Al máximo, System One 3: work_loss, installation and recoverable_delete are corrected in normal mode only
# (test_mind_system_one_max.py); what the kernel does not always confirm never is.
@pytest.mark.parametrize("risk", ["", "external", "irreversible", "external_communication", "privacy_sensitive", "high"])
def test_a_correction_to_any_other_risk_asks_and_never_fills(tmp_path: Path, monkeypatch, risk: str) -> None:
    mind, _, fills = _correcting(tmp_path, monkeypatch, risk, {"name": "app_close", "arguments": {}, "timings": {}})
    result = mind.decide(1, "ahora ciérralo")
    assert result["kind"] == "conversation" and result["operation"] is None
    assert fills == []


# e) The doubt never holds a confirmation, a continuation step or the heartbeat (mutation: a guard of _held removed).
def test_the_doubt_never_holds_a_confirmation(tmp_path: Path, monkeypatch) -> None:
    # System One's threshold never holds it; only a yes under CONFIRM_FLOOR is held (test_mind_doubt_policy.py).
    monkeypatch.setenv("BAXY_S1_DOUBT", "0.99")
    monkeypatch.delenv("BAXY_CONFIRM_FLOOR", raising=False)
    mind, _ = _doubt_mind(tmp_path, [_sure("confirm_pending", {"approve": True}, 0.97)])
    pending = {"operation": "file.delete", "arguments": {"path": "a.txt"}}
    assert mind.decide(1, "sí, dale", pending=pending)["operation"] == "confirmation.answer"


# F005 (notebook's falsehood bench): an approval with nothing pending never reaches the App; the model answers in words.
def test_a_confirmation_with_nothing_pending_is_not_sent(tmp_path: Path) -> None:
    mind, server = _mind(tmp_path, [_call("confirm_pending", {"approve": True}), _say("No, todavía no lo hice.")])
    result = mind.decide(1, "¿ya lo subiste?")
    assert result["operation"] is None and result["reply"] == "No, todavía no lo hice."
    told = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"]
    assert told and json.loads(told[-1])["error"] == "nothing_pending"
    # F010 (int3): «nothing waiting» was read as «already done»; the result says this call did nothing.
    assert "this call did nothing" in json.loads(told[-1])["reason"]


# Auditoría de confirmaciones (2026-10-23): the answer to the model's own question reads what waits now, as the App says
# with those words (mutation: the turn keeps the pending flag it began with).
def test_an_answer_to_a_question_never_approves_a_confirmation_that_no_longer_waits(tmp_path: Path) -> None:
    pending = {"operation": "file.delete", "arguments": {"path": "a.txt"}}
    mind, server = _mind(tmp_path, [_call("ask_user", {"question": "¿Cuál otro?"}),
                                    _call("confirm_pending", {"approve": True}), _say("No hay nada esperando tu sí.")])
    assert mind.decide(1, "sí, pero el otro", pending=pending)["kind"] == "clarify"
    result = mind.decide(2, "el informe", pending=None)
    assert result["operation"] is None and result["reply"] == "No hay nada esperando tu sí."
    told = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"]
    assert told[0] == "el informe" and json.loads(told[-1])["error"] == "nothing_pending"


def test_an_answer_to_a_question_can_answer_a_confirmation_asked_since(tmp_path: Path) -> None:
    pending = {"operation": "file.delete", "arguments": {"path": "a.txt"}}
    mind, server = _mind(tmp_path, [_call("ask_user", {"question": "¿Cuál borro?"}),
                                    _call("confirm_pending", {"approve": True})])
    assert mind.decide(1, "borra eso")["kind"] == "clarify"
    result = mind.decide(2, "sí", pending=pending)
    assert result["operation"] == "confirmation.answer" and result["arguments"] == {"approve": True}
    answer = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][0]
    assert answer.startswith("sí\n[Espera el sí de la persona: file_delete") and "confirm_pending" in answer


# A question that ended unanswered (the App says how with the next words) is told once as what it is, and the model may
# call the tool again, which the kernel asks again (mutation: ended read as nothing_pending, or final at once).
@pytest.mark.parametrize("how, error", [("dropped", "confirmation_dropped"), ("expired", "confirmation_expired")])
def test_a_si_to_a_question_that_ended_reads_how_it_ended_and_may_ask_again(tmp_path: Path, how: str,
                                                                           error: str) -> None:
    ended = {"operation": "app.close", "ended": how}
    mind, server = _mind(tmp_path, [_call("confirm_pending", {"approve": True}), _call("app_close", {"windowId": 7})])
    mind.wire_to_op["app_close"] = "app.close"
    result = mind.decide(1, "sí", pending=ended)
    assert "[Espera el sí" not in server.bodies[0]["messages"][-2]["content"]
    assert result["operation"] == "app.close" and "tool_choice" not in server.bodies[-1]
    told = json.loads([m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1])
    assert told["error"] == error and told["operation"] == "app.close" and "effectUncertain" not in told
    assert "app_close did not run" in told["reason"] and "call app_close again" in told["next"]


def test_an_ended_question_is_told_once_and_then_nothing_waits(tmp_path: Path) -> None:
    ended = {"operation": "file.delete", "ended": "expired", "effectUncertain": True}
    mind, server = _mind(tmp_path, [_call("confirm_pending", {"approve": True}),
                                    _call("confirm_pending", {"approve": True}), _say("Esa pregunta ya venció.")])
    result = mind.decide(1, "sí", pending=ended)
    assert result["operation"] is None and result["reply"] == "Esa pregunta ya venció."
    told = [json.loads(m["content"]) for m in server.bodies[-1]["messages"] if m["role"] == "tool"]
    assert told[0]["error"] == "confirmation_expired" and told[0]["effectUncertain"] is True
    assert "may have started" in told[0]["reason"]
    assert told[1]["error"] == "nothing_pending" and server.bodies[-1]["tool_choice"] == "none"


def test_the_doubt_never_holds_a_continuation_step(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_S1_DOUBT", "0.9")
    mind, _ = _doubt_mind(tmp_path, [_sure("app_open", {"appId": "Paint"}, 0.95), _sure("app_close", {}, 0.2)])
    mind.wire_to_op["app_close"] = "app.close"
    mind.decide(1, "abre paint y ciérralo")
    assert mind.continue_turn(2, json.dumps({"status": "completed"}))["operation"] == "app.close"


def test_the_doubt_never_holds_the_heartbeat(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_S1_DOUBT", "0.9")
    decision = json.dumps({"pedido": "ninguno", "preferencia": "ninguna", "vence": "nada", "bloqueo": "app colgada",
                           "analisis": "Una app no responde.", "intervenir": True})
    mind, _ = _doubt_mind(tmp_path, [_say(decision), _sure("app_close", {}, 0.2)])
    mind.wire_to_op["app_close"] = "app.close"
    assert mind.beat(1, {"now": "22:00"})["operation"] == "app.close"


# f) SystemOne.choose and LlmServer.fill_call on their own (mutation: one order only, no option check, bad JSON taken).
def _laya(monkeypatch, answers: list):
    from baxy_mind.system_one import SystemOne
    monkeypatch.setattr(SystemOne, "ready", property(lambda self: True))
    laya = SystemOne("laya.gguf", "llama-server.exe")
    asked: list = []

    def ask(text, history, options, timeout):
        asked.append(list(options))
        return answers.pop(0)

    laya._ask = ask
    return laya, asked


OPTIONS = {"app_close": "Close.", "ask_user": "preguntar", "responder_con_palabras": "contestar"}


def test_the_decision_model_is_asked_in_both_orders_and_their_mean_decides(monkeypatch) -> None:
    answers = [{"probabilities": {"app_close": 0.7, "ask_user": 0.3}},
               {"probabilities": {"app_close": 0.4, "ask_user": 0.6}}]
    laya, asked = _laya(monkeypatch, answers)
    judged = laya.choose("ciérralo", [], OPTIONS)
    assert asked == [list(OPTIONS), list(reversed(OPTIONS))]
    assert judged["choice"] == "app_close" and judged["p"] == 0.55
    assert judged["probabilities"] == {"app_close": 0.55, "ask_user": 0.45}


@pytest.mark.parametrize("answers", [[{"probabilities": {"otra": 1.0}}, {"probabilities": {"otra": 1.0}}],
                                     [{"probabilities": {"app_close": 1.0}}, None]])
def test_the_decision_model_has_no_answer_off_its_options_or_when_one_order_fails(monkeypatch, answers) -> None:
    laya, _ = _laya(monkeypatch, answers)
    assert laya.choose("ciérralo", [], OPTIONS) is None


def test_the_decision_model_has_no_answer_before_it_is_up() -> None:
    from baxy_mind.system_one import SystemOne
    laya = SystemOne("laya.gguf", "llama-server.exe")
    laya._ask = lambda *args: pytest.fail("asked before it was up")
    assert laya.choose("ciérralo", [], OPTIONS) is None


def _filled(arguments: str) -> dict:
    return {"choices": [{"message": {"tool_calls": [{"function": {"name": "app_close", "arguments": arguments}}]}}]}


@pytest.mark.parametrize("arguments, expected", [("{no es json", None), ('["Spotify"]', {}),
                                                 ('{"appId": "Spotify"}', {"appId": "Spotify"})])
def test_fill_call_reads_only_an_object_of_arguments(arguments: str, expected) -> None:
    from baxy_mind.llm_server import LlmServer
    server = LlmServer("model.gguf", "llama-server.exe")
    sent: list = []
    server._post = lambda path, body, timeout: sent.append(body) or _filled(arguments)
    filled = server.fill_call({"messages": [{"role": "user", "content": "x"}], "logit_bias": [[1, False]]}, "app_close")
    assert (filled if filled is None else filled["arguments"]) == expected
    assert "logit_bias" not in sent[0] and sent[0]["messages"][-1]["content"] == "<tool_call>\n<function=app_close>\n"


# g) The rest (mutation: no logit_bias; the queue kept after a correction; memory text in the trace; the answer to
# ask_user as a new request).
def test_the_final_answer_cannot_open_a_call(tmp_path: Path) -> None:
    mind, server = _mind(tmp_path, [_call("app_open", {"appId": "Paint"}), _say("Abrí Paint.")])
    mind.decide(1, "abre paint")
    mind.continue_turn(2, json.dumps({"status": "completed"}), final=True)
    assert server.bodies[-1]["tool_choice"] == "none" and server.bodies[-1]["logit_bias"] == [[248058, False]]


def test_a_correction_drops_the_calls_queued_behind_the_doubted_one(tmp_path: Path, monkeypatch) -> None:
    mind, server, _ = _correcting(tmp_path, monkeypatch, "low_reversible",
                                  {"name": "app_close", "arguments": {"appId": "Spotify"}, "timings": {}})
    second = {"id": "c2", "function": {"name": "app_open", "arguments": "{}"}}
    server.replies[0]["choices"][0]["message"]["tool_calls"].append(second)
    assert mind.decide(1, "ahora ciérralo")["operation"] == "app.close"
    calls = mind.conversation[-1]["tool_calls"]
    assert [c["function"]["name"] for c in calls] == ["app_close"]
    assert mind._turn["queue"] == []


def test_a_memory_call_keeps_the_persons_words_its_arguments_and_the_models_text_out_of_the_trace(
        tmp_path: Path) -> None:
    mind, _ = _mind(tmp_path, [_call("memory_save", {"text": "mi clave es 4321"})])
    mind.wire_to_op = {"memory_save": "memory.save"}
    assert mind.decide(1, "recuerda que mi clave es 4321")["operation"] == "memory.save"
    row = _rows(tmp_path)[-1]
    assert row["operation"] == "memory.save"
    assert row["text"] is None and row["arguments"] is None and row["content"] is None


def test_the_answer_to_ask_user_is_that_calls_result(tmp_path: Path) -> None:
    mind, server = _mind(tmp_path, [_call("ask_user", {"question": "¿A qué hora?"}),
                                    _call("schedule_alarms", {"time": "07:00"})])
    assert mind.decide(1, "pon una alarma") == {"type": "turn.result", "id": 1, "kind": "clarify", "operation": None,
                                                "arguments": None, "question": "¿A qué hora?", "reply": ""}
    mind.decide(2, "a las 7")
    messages = server.bodies[-1]["messages"]
    asked = messages[-2]["tool_calls"][0]["id"]
    assert messages[-1] == {"role": "tool", "tool_call_id": asked, "content": "a las 7"}
    assert sum(str(m.get("content", "")).startswith("[Reloj:") for m in messages) == 1
