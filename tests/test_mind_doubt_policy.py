"""System One, layer 0 in the mind (BAXY_S1_DOUBT): an action the model was not sure of does not run; the model asks."""
import json
import math
from pathlib import Path

import pytest

from baxy_mind.mind import Mind


class FakeServer:
    context = 49152

    def __init__(self, replies: list) -> None:
        self.replies = replies
        self.bodies: list[dict] = []

    def chat(self, body: dict) -> dict:
        self.bodies.append(json.loads(json.dumps(body)))
        return self.replies.pop(0)

    def template(self, body: dict) -> str:
        return "PROMPT"


def _token(text: str, p: float) -> dict:
    return {"token": text, "logprob": math.log(p), "top_logprobs": [{"token": text, "logprob": math.log(p)}]}


def _call(name: str, arguments: dict, p_name: float) -> dict:
    head, tail = name.split("_", 1)
    logprobs = [_token("<tool_call>", 0.95), _token("\n", 1.0), _token("<", 1.0), _token("function", 1.0),
                _token("=", 1.0), _token(head, p_name), _token("_" + tail, 1.0), _token(">", 1.0)]
    return {"choices": [{"message": {"content": "", "tool_calls": [
        {"id": "c1", "function": {"name": name, "arguments": json.dumps(arguments)}}]},
        "logprobs": {"content": logprobs}}]}


def _say(text: str) -> dict:
    return {"choices": [{"message": {"content": text}}]}


def _mind(tmp_path: Path, replies: list) -> tuple[Mind, FakeServer]:
    server = FakeServer(replies)
    mind = Mind(server, tmp_path / "turns.jsonl")  # type: ignore[arg-type]
    mind.call_tokens = [248058]
    mind.wire_to_op = {"system_power": "system.power", "app_open": "app.open"}
    return mind, server


def test_an_unsure_action_does_not_run_and_the_model_reads_again_and_asks_in_its_own_words(tmp_path,
                                                                                            monkeypatch) -> None:
    monkeypatch.setenv("BAXY_S1_DOUBT", "0.4")
    mind, server = _mind(tmp_path, [_call("system_power", {"action": "shutdown"}, 0.3),
                                    _say("¿Qué quieres que cierre: la ventana de delante o el PC?")])
    result = mind.decide(1, "ahora ciérralo")
    assert result["kind"] == "conversation"
    assert result["operation"] is None
    assert result["reply"] == "¿Qué quieres que cierre: la ventana de delante o el PC?"
    second = server.bodies[1]
    assert "tool_choice" not in second  # it decides again, with its tools
    assert "system_power" in second["messages"][-1]["content"]
    assert not any(m.get("tool_calls") for m in second["messages"])  # the call it nearly made is not in the conversation
    rows = [json.loads(line) for line in (tmp_path / "turns.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[0]["kind"] == "doubt_reread" and rows[0]["operation"] == "system.power"
    assert rows[0]["doubt"]["confidence"] < 0.4


def test_an_unsure_action_the_model_chooses_again_on_reading_it_runs(tmp_path, monkeypatch) -> None:
    # Pregunta-eco (noche 2026-10-27): told to ask, with no tools, all a model sure of nothing but its call could ask was
    # the request itself («¿Quieres que busque…?», «¿Quieres conectarte a la red…?»). It reads the request again with its
    # tools and the note that it doubted; the same call, read again, is not held again.
    monkeypatch.setenv("BAXY_S1_DOUBT", "0.4")
    mind, server = _mind(tmp_path, [_call("app_open", {"appId": "notas"}, 0.3),
                                    _call("app_open", {"appId": "notas"}, 0.3)])
    result = mind.decide(1, "abre las notas")
    assert result["kind"] == "action" and result["operation"] == "app.open"
    assert "app_open" in server.bodies[1]["messages"][-1]["content"]
    rows = [json.loads(line) for line in mind.trace.read_text("utf-8").splitlines()]
    assert rows[0]["kind"] == "doubt_reread"


@pytest.mark.parametrize(("mode", "wire", "op", "arguments"), [
    ("", "system_power", "system.power", {"action": "shutdown"}),
    ("bypass", "app_close", "app.close", {"appId": "notas"}),
])
def test_an_unsure_work_loss_action_the_kernel_runs_unasked_is_asked_without_tools(tmp_path, monkeypatch, mode, wire,
                                                                                    op, arguments) -> None:
    # P2.34: read again with its tools, the model could make the same call, and nobody asked before it ran: the kernel
    # runs system.power unasked (identity), and every work_loss call in Bypass. Its doubt asks, as before pregunta-eco.
    monkeypatch.setenv("BAXY_S1_DOUBT", "0.4")
    monkeypatch.setenv("BAXY_DATA_DIR", str(tmp_path))
    if mode:
        (tmp_path / "confirmation-mode").write_text(mode, encoding="utf-8")
    mind, server = _mind(tmp_path, [_call(wire, arguments, 0.3), _say("¿Cuál quieres?")])
    mind.wire_to_op[wire] = op
    mind.risk = {wire: "work_loss"}
    result = mind.decide(1, "ahora ciérralo")
    assert result["operation"] is None and result["reply"] == "¿Cuál quieres?"
    assert not server.bodies[1].get("tools") or server.bodies[1].get("tool_choice") == "none"
    rows = [json.loads(line) for line in mind.trace.read_text("utf-8").splitlines()]
    assert rows[0]["kind"] == "doubt_ask" and rows[0]["operation"] == op


def _call_at(p_call: float, p_name: float) -> dict:
    reply = _call("app_open", {"appId": "notas"}, p_name)
    reply["choices"][0]["logprobs"]["content"][0] = _token("<tool_call>", p_call)
    return reply


def test_a_sure_call_under_even_odds_runs(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_S1_DOUBT", "0.4")
    mind, _ = _mind(tmp_path, [_call_at(0.45, 1.0)])
    result = mind.decide(1, "abre las notas")
    assert result["kind"] == "action" and result["operation"] == "app.open"


@pytest.mark.parametrize("p_call", [0.3, 0.45])
def test_an_unsure_call_under_even_odds_is_held_with_the_note_that_names_it(tmp_path, monkeypatch, p_call) -> None:
    # Banco v11 (2026-10-27): deciding again in words, told nothing, whenever p(call) < 0.5 turned right actions (a
    # named network, a «quítalo» after an app) into questions that echoed them. p(call) alone does not turn a call into
    # words: an unsure one is held with the note that names it, as for any other p(call).
    monkeypatch.setenv("BAXY_S1_DOUBT", "0.4")
    mind, server = _mind(tmp_path, [_call_at(p_call, 0.6), _say("¿Abro las notas?")])
    assert mind.decide(1, "abre las notas")["operation"] is None
    assert "app_open" in server.bodies[1]["messages"][-1]["content"]
    rows = [json.loads(line) for line in mind.trace.read_text("utf-8").splitlines()]
    assert rows[0]["kind"] == "doubt_reread" and rows[0]["operation"] == "app.open" and rows[0]["doubt"]["p_call"] == p_call


@pytest.mark.parametrize("threshold", ["", "0.4"])
def test_a_sure_action_or_layer_0_off_runs_as_before(tmp_path, monkeypatch, threshold) -> None:
    monkeypatch.setenv("BAXY_S1_DOUBT", threshold)
    p_name = 0.3 if not threshold else 0.99
    mind, _ = _mind(tmp_path, [_call("app_open", {"appId": "Spotify"}, p_name)])
    result = mind.decide(1, "abre spotify")
    assert result["kind"] == "action" and result["operation"] == "app.open"


class FakeSystemOne:
    ready = True

    def __init__(self, choice) -> None:
        self.choice = choice
        self.asked: list[dict] = []

    def choose(self, text, history, options):
        self.asked.append({"text": text, "options": dict(options)})
        if self.choice is None:
            return None  # not up yet, or failed: the turn goes on as the model decided
        return {"choice": self.choice, "p": 0.9, "probabilities": {self.choice: 0.9}, "ms": 140}


def _layer2(tmp_path, monkeypatch, choice, replies):
    monkeypatch.setenv("BAXY_S1_DOUBT", "")
    monkeypatch.setenv("BAXY_S1_VETO", "0.6")
    mind, server = _mind(tmp_path, replies)
    server.complete_name = lambda prompt, written: "_close"  # the rest of the rival «app»: app_close
    mind.tools = [{"type": "function", "function": {"name": n, "description": d + ". More.", "parameters": {}}}
                  for n, d in (("system_power", "Shut down the PC"), ("app_close", "Close an application"))]
    one = FakeSystemOne(choice)
    mind.system_one = one  # type: ignore[assignment]
    return mind, server, one


def _rival_call(p_name: float) -> dict:
    reply = _call("system_power", {"action": "shutdown"}, p_name)
    name = reply["choices"][0]["logprobs"]["content"][5]
    name["top_logprobs"].append({"token": "app", "logprob": math.log(1 - p_name)})
    return reply


def test_layer2_holds_an_unsure_action_the_decision_model_reads_otherwise(tmp_path, monkeypatch) -> None:
    mind, server, one = _layer2(tmp_path, monkeypatch, "app_close",
                                [_rival_call(0.5), _say("¿Cierro la ventana de delante o apago el PC?")])
    result = mind.decide(1, "ahora ciérralo")
    assert result["kind"] == "conversation" and result["operation"] is None
    assert set(one.asked[0]["options"]) == {"system_power", "app_close", "ask_user", "responder_con_palabras"}
    assert one.asked[0]["options"]["app_close"] == "Close an application."
    note = server.bodies[1]["messages"][-1]["content"]
    assert "system_power" in note and "app_close" in note
    rows = [json.loads(line) for line in (tmp_path / "turns.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[0]["system_one"]["choice"] == "app_close"
    assert "tool_choice" not in server.bodies[1]  # it reads the request again with its tools


def test_layer2_lets_the_model_do_the_reading_it_chooses_on_reading_again(tmp_path, monkeypatch) -> None:
    # Pregunta-eco (noche 2026-10-27): with both readings named and no tools, the question was «¿X o Y?» even for a
    # request that said which. It reads again with its tools; that reading is not judged again.
    mind, _, one = _layer2(tmp_path, monkeypatch, "app_close",
                           [_rival_call(0.5), _call("app_close", {"appId": "notas"}, 0.5)])
    mind.wire_to_op["app_close"] = "app.close"
    result = mind.decide(1, "cierra las notas")
    assert result["kind"] == "action" and result["operation"] == "app.close"
    assert len(one.asked) == 1
    rows = [json.loads(line) for line in mind.trace.read_text("utf-8").splitlines()]
    assert rows[0]["kind"] == "doubt_reread"


@pytest.mark.parametrize("choice", ["system_power", None])
def test_layer2_lets_the_action_run_when_the_decision_model_agrees_or_is_not_up(tmp_path, monkeypatch, choice) -> None:
    mind, _, _ = _layer2(tmp_path, monkeypatch, choice, [_rival_call(0.5)])
    assert mind.decide(1, "apaga el pc")["operation"] == "system.power"


def test_layer2_is_not_asked_when_the_model_is_sure(tmp_path, monkeypatch) -> None:
    mind, _, one = _layer2(tmp_path, monkeypatch, "app_close", [_rival_call(0.95)])
    assert mind.decide(1, "apaga el pc")["operation"] == "system.power"
    assert one.asked == []


def test_asking_is_never_held(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_S1_DOUBT", "0.9")
    mind, _ = _mind(tmp_path, [_call("ask_user", {"question": "¿Qué cierro?"}, 0.2)])
    assert mind.decide(1, "ciérralo")["kind"] == "clarify"


def _correcting(tmp_path, monkeypatch, risk: str, filled):
    monkeypatch.setenv("BAXY_S1_CORRECT", "1")
    mind, server, one = _layer2(tmp_path, monkeypatch, "app_close",
                                [_rival_call(0.5), _say("¿Cierro la ventana de delante o apago el PC?")])
    mind.wire_to_op["app_close"] = "app.close"
    mind.risk = {"system_power": "work_loss", "app_close": risk}
    fills: list[str] = []

    def fill_call(body, wire):
        fills.append(wire)
        return filled

    server.fill_call = fill_call
    return mind, server, fills


def test_layer2_corrects_to_a_harmless_tool_the_model_fills_itself(tmp_path, monkeypatch) -> None:
    mind, server, fills = _correcting(tmp_path, monkeypatch, "low_reversible",
                                      {"name": "app_close", "arguments": {"appId": "Spotify"}, "timings": {}})
    result = mind.decide(1, "ahora ciérralo")
    assert result["kind"] == "action" and result["operation"] == "app.close"
    assert result["arguments"] == {"appId": "Spotify"}
    assert fills == ["app_close"] and len(server.bodies) == 1  # no second decision: the model only filled the tool
    rows = [json.loads(line) for line in (tmp_path / "turns.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[0]["system_one"]["corrected"] is True


@pytest.mark.parametrize("risk, filled", [
    # a tool the kernel does not always confirm is never put in its mouth (work_loss: test_mind_system_one_max.py)
    ("external_communication", {"name": "app_close", "arguments": {}, "timings": {}}),
    ("low_reversible", None),  # the model did not write that call
    ("low_reversible", {"name": "system_power", "arguments": {}, "timings": {}})])
def test_layer2_asks_when_it_cannot_correct(tmp_path, monkeypatch, risk, filled) -> None:
    mind, _, _ = _correcting(tmp_path, monkeypatch, risk, filled)
    result = mind.decide(1, "ahora ciérralo")
    assert result["kind"] == "conversation" and result["operation"] is None


@pytest.mark.parametrize("effects, operation", [(["window_input"], None), (["network"], None), (None, "app.close")])
def test_layer2_never_corrects_to_a_tool_with_an_effect_of_the_catalog(tmp_path, monkeypatch, effects,
                                                                         operation) -> None:
    # Al máximo 5.1: a tool that sends keys, clicks or commands to a window, or what the model wrote out of the PC, is
    # never filled by «corrige», whatever its risk; a catalog without the field (the saved measurement ones) corrects by
    # risk alone, as before.
    mind, _, fills = _correcting(tmp_path, monkeypatch, "low_reversible",
                                 {"name": "app_close", "arguments": {"appId": "Spotify"}, "timings": {}})
    empty = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    close = {"name": "app.close", "description": "Close an application", "argumentsSchema": empty,
             "risk": "low_reversible"}
    if effects is not None:
        close["effects"] = effects
    mind.configure({"capabilities": [{"name": "system.power", "description": "Shut down the PC",
                                      "argumentsSchema": empty, "risk": "work_loss"}, close]})
    assert mind.decide(1, "ahora ciérralo")["operation"] == operation
    assert fills == ([] if operation is None else ["app_close"])


@pytest.mark.parametrize("effects, appId, text, sends, names, operation", [
    (["window_input"], "1", "ahora ciérralo", False, True, "system.power"),  # never corrected: filled only to see
    (None, "1", "ahora ciérralo", False, True, "system.power"),  # corrected and unfounded: that fill is read again
    (["window_input"], "Spotify", "ciérrame el Spotify", False, True, None),  # it could be called: both fit, it asks
    (["window_input"], "1", "ahora ciérralo", True, True, None),  # a read that sends out of the PC still asks
    (["window_input"], "1", "ahora ciérralo", False, False, None)])  # its description does not name the read: asks
def test_layer2_lets_a_read_run_when_the_decision_models_tool_lacks_an_argument_nobody_showed(
        tmp_path, monkeypatch, effects, appId, text, sends, names, operation) -> None:
    # P2.44 causa 4 (V11D202, V11D086): the model chose window_active and the decision model window_snap, which needs
    # the windowId only that read gives; asked «¿cuál de las dos?», the model asked which window or which side.
    mind, _, fills = _correcting(tmp_path, monkeypatch, "low_reversible",
                                 {"name": "app_close", "arguments": {"appId": appId}, "timings": {}})
    empty = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    close = {"name": "app.close", "description": "Close an application", "risk": "low_reversible",
             "argumentsSchema": {"type": "object", "properties": {"appId": {"type": "string"}},
                                 "required": ["appId"], "additionalProperties": False}}
    if effects is not None:
        close["effects"] = effects
    power = {"name": "system.power", "description": "Shut down the PC", "argumentsSchema": empty, "risk": "read_only"}
    if sends:
        power["effects"] = ["network"]
    mind.configure({"capabilities": [power, close]})
    if names:  # as window_snap's own: «Its windowId comes from window_resolve, window_active or app_open»
        next(t["function"] for t in mind.tools if t["function"]["name"] == "app_close")["description"] +=             " Its appId comes from system_power."
    assert mind.decide(1, text)["operation"] == operation
    assert fills == ([] if (sends or not names) and effects else ["app_close"])


def test_layer2_still_asks_when_the_decision_model_reads_a_question(tmp_path, monkeypatch) -> None:
    # Code review: ask_user's question is the model's own words, founded nowhere; the decision model asking is not a
    # tool that lacks an argument, and the read does not run in its place.
    mind, _, fills = _correcting(tmp_path, monkeypatch, "low_reversible",
                                 {"name": "ask_user", "arguments": {"question": "¿Cuál?"}, "timings": {}})
    mind.system_one = FakeSystemOne("ask_user")  # type: ignore[assignment]
    mind.risk["system_power"] = "read_only"
    assert mind.decide(1, "ahora ciérralo")["operation"] is None
    assert fills == []


def test_layer2_does_not_correct_when_correcting_is_off(tmp_path, monkeypatch) -> None:
    mind, _, fills = _correcting(tmp_path, monkeypatch, "low_reversible",
                                 {"name": "app_close", "arguments": {}, "timings": {}})
    monkeypatch.setenv("BAXY_S1_CORRECT", "")
    assert mind.decide(1, "ahora ciérralo")["operation"] is None
    assert fills == []


def test_layer_0_asks_once_per_misunderstanding(tmp_path, monkeypatch) -> None:
    # 4.2 (SAGE-Agent): the person's answer to BAXY's doubt question was held again by the same doubt, with no limit.
    monkeypatch.setenv("BAXY_S1_DOUBT", "0.4")
    mind, _ = _mind(tmp_path, [_call("system_power", {"action": "shutdown"}, 0.3), _say("¿Qué cierro?"),
                               _call("system_power", {"action": "shutdown"}, 0.3),
                               _call("system_power", {"action": "shutdown"}, 0.3), _say("¿Qué apago?")])
    assert mind.decide(1, "ciérralo")["operation"] is None
    assert mind.decide(2, "el PC")["operation"] == "system.power"  # its answer: layer 0 does not ask again
    mind.continue_turn(3, json.dumps({"status": "cancelled"}))
    assert mind.decide(4, "ciérralo otra vez")["operation"] is None  # a new request is held as before


def test_the_answer_to_ask_user_is_not_held_by_layer_0(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_S1_DOUBT", "0.4")
    mind, _ = _mind(tmp_path, [_call("ask_user", {"question": "¿Qué cierro?"}, 0.9),
                               _call("system_power", {"action": "shutdown"}, 0.3)])
    assert mind.decide(1, "ciérralo")["kind"] == "clarify"
    assert mind.decide(2, "el PC")["operation"] == "system.power"


def test_the_answer_to_a_doubt_question_goes_to_layer_2(tmp_path, monkeypatch) -> None:
    mind, server, one = _layer2(tmp_path, monkeypatch, "app_close",
                                [_rival_call(0.3), _say("¿Cierro la ventana o apago el PC?"), _rival_call(0.3),
                                 _say("¿La ventana de delante o el PC entero?")])
    monkeypatch.setenv("BAXY_S1_DOUBT", "0.4")
    assert mind.decide(1, "ciérralo")["operation"] is None
    assert one.asked == []  # layer 0 asked first
    assert mind.decide(2, "eso")["operation"] is None
    assert len(one.asked) == 1  # the answer: the decision model reads it, and it asks (with its other option)
    assert "app_close" in server.bodies[-1]["messages"][-1]["content"]


def test_layer2_asks_once_per_misunderstanding(tmp_path, monkeypatch) -> None:
    # Menos preguntas (2026-10-25): the answer to layer 2's own question went to layer 2 again, which asked again at each
    # answer while the decision model still read it otherwise, with no limit. It may still correct; it no longer asks.
    mind, _, one = _layer2(tmp_path, monkeypatch, "app_close",
                           [_rival_call(0.5), _say("¿Cierro la ventana o apago el PC?"), _rival_call(0.5),
                            _rival_call(0.5), _say("¿La ventana o el PC?")])
    assert mind.decide(1, "ciérralo")["operation"] is None
    assert mind.decide(2, "el PC")["operation"] == "system.power"  # its answer: not asked again
    assert len(one.asked) == 2  # the decision model still read the answer
    mind.continue_turn(3, json.dumps({"status": "cancelled"}))
    assert mind.decide(4, "ciérralo otra vez")["operation"] is None  # a new request is asked about as before


@pytest.mark.parametrize("answer,p_name,held", [("yes", 0.78, True), ("yes", 0.999, False), ("no", 0.78, False),
                                                ("unclear", 0.78, False)])
def test_a_yes_the_model_is_not_sure_of_is_held_and_asked(tmp_path, monkeypatch, answer, p_name, held) -> None:
    # Confirmaciones 2026-10-23: «sí pero el otro» approved a pending trash at 0.77-0.79; plain yeses were ≥ 0.998.
    # Only a yes is held: a no cancels and an unclear answer (prefijo c3, S4) runs nothing and asks again.
    monkeypatch.delenv("BAXY_S1_DOUBT", raising=False)
    monkeypatch.delenv("BAXY_CONFIRM_FLOOR", raising=False)
    reply = _call("confirm_pending", {"answer": answer}, p_name)
    reply["choices"][0]["logprobs"]["content"][0] = _token("<tool_call>", 1.0)  # the call itself is sure, as on the model
    mind, server = _mind(tmp_path, [reply, _say("¿Cuál archivo quieres que mande a la papelera?")])
    pending = {"operation": "filesystem.known.trash.named", "arguments": {"fileName": "notas.txt"}}
    result = mind.decide(1, "sí pero el otro", pending)
    if held:
        assert result["kind"] == "conversation" and result["operation"] is None
        assert "confirm_pending" in server.bodies[1]["messages"][-1]["content"]
        assert server.bodies[1]["tool_choice"] == "none"  # it only asks: a reading again could approve the same «sí»
    else:
        assert result["kind"] == "action" and result["operation"] == "confirmation.answer"
        assert result["arguments"]["answer"] == answer


def test_the_confirm_floor_can_be_turned_off(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_CONFIRM_FLOOR", "0")
    mind, _ = _mind(tmp_path, [_call("confirm_pending", {"answer": "yes"}, 0.5)])
    result = mind.decide(1, "sí", {"operation": "app.close", "arguments": {"appId": "Paint"}})
    assert result["operation"] == "confirmation.answer"


@pytest.mark.parametrize("words, held", [
    *((yes, False) for yes in ("Sí po.", "dale", "Ya.", "ok", "Hágale", "de una", "Obvio", "sí, hazlo", "ya po",
                               "Okey, dale", "claro que sí", "hágale pues", "sí, por favor", "go ahead")),
    *((other, True) for other in ("mmm", "no sé", "espera", "ya, espera", "sí pero el otro", "sí no", "ok no",
                                  "Zí"))])
def test_words_that_are_only_a_yes_are_not_held_by_the_confirm_floor(tmp_path, monkeypatch, words, held) -> None:
    # Menos preguntas (dueño, 2026-10-25): a held «sí» costs the model's question and the kernel's again (the App drops the
    # call that question left behind). A plain yes approves even if the model was unsure of it; anything else is held.
    monkeypatch.delenv("BAXY_S1_DOUBT", raising=False)
    monkeypatch.delenv("BAXY_CONFIRM_FLOOR", raising=False)
    reply = _call("confirm_pending", {"answer": "yes"}, 0.78)
    reply["choices"][0]["logprobs"]["content"][0] = _token("<tool_call>", 1.0)
    mind, _ = _mind(tmp_path, [reply, _say("¿Qué quieres que haga con notas.txt?")])
    pending = {"operation": "filesystem.known.trash.named", "arguments": {"fileName": "notas.txt"}}
    result = mind.decide(1, words, pending)
    assert result["operation"] == (None if held else "confirmation.answer")


def test_an_unsure_search_for_a_dated_question_or_a_curiosity_is_not_held(tmp_path, monkeypatch) -> None:
    # Aid «dated_search», soak of the fair (2026-10-27): web_search chosen for «¿Quién ganó el premio Nobel de Física
    # 2023?» or «Cuéntame un dato curioso de los océanos» under the threshold became «¿Quieres que busque…?» 6 times.
    monkeypatch.setenv("BAXY_S1_DOUBT", "0.4")
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("web_search", {"query": "Nobel de Física 2023"}, 0.3),
                               _call("web_search", {"query": "dato curioso océanos"}, 0.3),
                               _call("web_search", {"query": "clima"}, 0.3), _say("¿Qué quieres buscar?")])
    mind.wire_to_op["web_search"] = "web.search"
    assert mind.decide(1, "¿Quién ganó el premio Nobel de Física 2023?")["operation"] == "web.search"
    assert mind.decide(2, "Cuéntame un dato curioso de los océanos.")["operation"] == "web.search"
    assert mind.decide(3, "busca algo")["operation"] is None  # any other unsure search is held as before


def test_an_unsure_search_for_what_or_who_a_named_thing_is_is_not_held(tmp_path, monkeypatch) -> None:
    # Live on the notebook after the deploy (2026-10-27): web_search chosen for what a local brand is, under the
    # threshold, became «¿Quieres que busque…?»: it is the call aid «named_fact» asks for, so its doubt does not hold it
    monkeypatch.setenv("BAXY_S1_DOUBT", "0.4")
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("web_search", {"query": "Zorvik"}, 0.3), _say("¿Quieres que busque Zorvik?")])
    mind.wire_to_op["web_search"] = "web.search"
    assert mind.decide(1, "¿Qué es Zorvik?")["operation"] == "web.search"  # held, it would be the question


# C16 (auditoría de la noche): after pregunta-eco a doubt reads again with the tools, and nothing held what that reading
# chose. A call the kernel would run unasked though normal mode counts its risk as one to confirm (system.power; in
# Bypass every one of them, and what the kernel confirms only in normal mode) is asked about as before the night,
# whichever layer doubted it and also when the reading after another doubt chose it.
def _unasked(tmp_path, monkeypatch, mode: str) -> None:
    monkeypatch.setenv("BAXY_DATA_DIR", str(tmp_path))
    if mode:
        (tmp_path / "confirmation-mode").write_text(mode, encoding="utf-8")


def test_layer2_asks_about_an_unsure_power_call_with_no_tools(tmp_path, monkeypatch) -> None:
    _unasked(tmp_path, monkeypatch, "")
    mind, server, _ = _layer2(tmp_path, monkeypatch, "app_close",
                              [_rival_call(0.5), _say("¿Cierro la ventana o apago el PC?")])
    mind.risk = {"system_power": "work_loss", "app_close": "work_loss"}
    result = mind.decide(1, "ahora ciérralo")
    assert result["operation"] is None and result["reply"] == "¿Cierro la ventana o apago el PC?"
    assert server.bodies[1].get("tool_choice") == "none"
    assert "app_close" in server.bodies[1]["messages"][-1]["content"]
    rows = [json.loads(line) for line in mind.trace.read_text("utf-8").splitlines()]
    assert rows[0]["kind"] == "doubt_ask"


def test_the_answer_to_layer2_power_question_is_not_asked_again(tmp_path, monkeypatch) -> None:
    _unasked(tmp_path, monkeypatch, "")
    mind, _, one = _layer2(tmp_path, monkeypatch, "app_close",
                           [_rival_call(0.5), _say("¿Cierro la ventana o apago el PC?"), _rival_call(0.5)])
    mind.risk = {"system_power": "work_loss", "app_close": "work_loss"}
    assert mind.decide(1, "ciérralo")["operation"] is None
    assert mind.decide(2, "el PC")["operation"] == "system.power"  # the person answered its question
    assert len(one.asked) == 2


@pytest.mark.parametrize("p_power", [0.3, 0.5])
def test_power_chosen_unsure_on_reading_again_after_another_doubt_is_asked(tmp_path, monkeypatch, p_power) -> None:
    _unasked(tmp_path, monkeypatch, "")
    mind, server, _ = _layer2(tmp_path, monkeypatch, "app_close",
                              [_call("app_open", {"appId": "notas"}, 0.3), _rival_call(p_power), _say("¿Apago el PC?")])
    monkeypatch.setenv("BAXY_S1_DOUBT", "0.4")
    mind.risk = {"system_power": "work_loss", "app_open": "read_only", "app_close": "work_loss"}
    result = mind.decide(1, "ahora ciérralo")
    assert result["operation"] is None and result["reply"] == "¿Apago el PC?"
    assert server.bodies[2].get("tool_choice") == "none"


@pytest.mark.parametrize("risk", ["recoverable_delete", "installation", "external_communication", "work_loss"])
def test_in_bypass_an_unsure_call_normal_mode_would_confirm_is_asked(tmp_path, monkeypatch, risk) -> None:
    _unasked(tmp_path, monkeypatch, "bypass")
    monkeypatch.setenv("BAXY_S1_DOUBT", "0.4")
    mind, server = _mind(tmp_path, [_call("email_send", {"to": "ana"}, 0.3), _say("¿A quién se lo mando?")])
    mind.wire_to_op["email_send"] = "email.send"
    mind.risk = {"email_send": risk}
    mind.confirms = {"email_send": ["normal"]}  # what the kernel sends for email.send (RiskPolicy.Evaluate)
    result = mind.decide(1, "mándaselo")
    assert result["operation"] is None and server.bodies[1].get("tool_choice") == "none"


@pytest.mark.parametrize("risk", ["recoverable_delete", "installation", "external_communication", "read_only"])
def test_in_normal_mode_an_unsure_call_the_kernel_confirms_or_that_goes_direct_is_read_again(tmp_path, monkeypatch,
                                                                                               risk) -> None:
    # Normal mode: the kernel asks the person for what it confirms (and for the external calls that reach a person); the
    # rest of external_communication (a page, a song, an event in their own calendar) goes direct by the owner's
    # decision, and its doubt reads again, as pregunta-eco measured.
    _unasked(tmp_path, monkeypatch, "")
    monkeypatch.setenv("BAXY_S1_DOUBT", "0.4")
    mind, server = _mind(tmp_path, [_call("email_send", {"to": "ana"}, 0.3), _call("email_send", {"to": "ana"}, 0.3)])
    mind.wire_to_op["email_send"] = "email.send"
    mind.risk = {"email_send": risk}
    assert mind.decide(1, "mándaselo a ana")["operation"] == "email.send"
    assert all("tool_choice" not in body for body in server.bodies)  # held, it read again with its tools


# Held-out of C16, written by a subagent that never saw the change. The mind reads no words: whatever is said, an unsure
# power call asks (here at either layer), and a sure one, or an unsure call the kernel confirms or that goes direct, runs.
HELD_OUT_UNSURE = ["apágalo no más", "cierra todo y chao", "ya me voy déjalo durmiendo", "reinicia esa cuestión que se pegó",
                   "a pagar todo", "corta la sesión po", "mata todo que me tengo que ir",
                   "salte de ahí y deja la cuestión lista pa mañana"]


@pytest.mark.parametrize("words", HELD_OUT_UNSURE)
@pytest.mark.parametrize("p_power", [0.3, 0.5])
def test_held_out_unsure_power_requests_are_asked(tmp_path, monkeypatch, words, p_power) -> None:
    _unasked(tmp_path, monkeypatch, "")
    mind, server, _ = _layer2(tmp_path, monkeypatch, "app_close", [_rival_call(p_power), _say("¿Qué quieres que haga?")])
    monkeypatch.setenv("BAXY_S1_DOUBT", "0.4")
    mind.risk = {"system_power": "work_loss", "app_close": "work_loss"}
    assert mind.decide(1, words)["operation"] is None
    assert server.bodies[1].get("tool_choice") == "none"


@pytest.mark.parametrize("words, reply, operation", [
    ("reinicia el computador por favor", _call("system_power", {"action": "restart"}, 0.9), "system.power"),
    ("suspende el notebook ahora", _call("system_power", {"action": "sleep"}, 0.9), "system.power"),
    ("abre la calculadora", _call("app_open", {"appId": "calculadora"}, 0.3), "app.open"),
    ("busca en internet el clima de mañana en valparaíso", _call("web_search", {"query": "clima"}, 0.3), "web.search")])
def test_held_out_clear_requests_run(tmp_path, monkeypatch, words, reply, operation) -> None:
    _unasked(tmp_path, monkeypatch, "")
    monkeypatch.setenv("BAXY_S1_DOUBT", "0.4")
    mind, server = _mind(tmp_path, [reply, json.loads(json.dumps(reply))])
    mind.wire_to_op["web_search"] = "web.search"
    mind.risk = {"system_power": "work_loss", "app_open": "read_only", "web_search": "read_only"}
    assert mind.decide(1, words)["operation"] == operation
    assert all("tool_choice" not in body for body in server.bodies)


def test_an_unreadable_confirmation_mode_asks_about_an_unsure_external_call(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_DATA_DIR", str(tmp_path))
    (tmp_path / "confirmation-mode").mkdir()  # unreadable: it counts as Bypass (_bypass)
    monkeypatch.setenv("BAXY_S1_DOUBT", "0.4")
    mind, server = _mind(tmp_path, [_call("email_send", {"to": "ana"}, 0.3), _say("¿A quién se lo mando?")])
    mind.wire_to_op["email_send"] = "email.send"
    mind.risk = {"email_send": "external_communication"}
    mind.confirms = {"email_send": ["normal"]}
    assert mind.decide(1, "mándaselo")["operation"] is None
    assert server.bodies[1].get("tool_choice") == "none"


@pytest.mark.parametrize("risk", ["recoverable_delete", "installation"])
def test_in_bypass_layer2_asks_about_an_unsure_call_normal_mode_would_confirm(tmp_path, monkeypatch, risk) -> None:
    _unasked(tmp_path, monkeypatch, "bypass")
    monkeypatch.setenv("BAXY_S1_CORRECT", "1")
    mind, server, _ = _layer2(tmp_path, monkeypatch, "app_close", [_rival_call(0.5), _say("¿Cuál de las dos?")])
    mind.risk = {"system_power": risk, "app_close": risk}
    server.fill_call = lambda body, wire: {"name": wire, "arguments": {}, "timings": {}}
    assert mind.decide(1, "ahora ciérralo")["operation"] is None
    assert server.bodies[1].get("tool_choice") == "none"
    assert ", pero también podría ser " in server.bodies[1]["messages"][-1]["content"]


# P2.40 (C16 M11): a reply with several calls ran the ones queued behind the first without reading their doubt, so a
# power call the model wrote second ([app_open, system_power]) never asked. A queued call the kernel would run unasked
# (_unasked) goes by the same rule as the first: its own doubt, read from its own opening, asks with no tools.
def _calls(*calls: dict) -> dict:
    """One reply with the calls of several _call replies, in order: each one's tokens after the one before it."""
    logprobs, told = [], []
    for index, reply in enumerate(calls):
        if index:
            logprobs += [_token("</tool_call>", 1.0), _token("\n", 1.0)]
        logprobs += reply["choices"][0]["logprobs"]["content"]
        told += [{**c, "id": f"c{index + 1}"} for c in reply["choices"][0]["message"]["tool_calls"]]
    return {"choices": [{"message": {"content": "", "tool_calls": told}, "logprobs": {"content": logprobs}}]}


@pytest.mark.parametrize("layer", [0, 2])
def test_an_unsure_power_call_queued_second_is_asked_with_no_tools(tmp_path, monkeypatch, layer) -> None:
    _unasked(tmp_path, monkeypatch, "")
    mind, server, _ = _layer2(tmp_path, monkeypatch, "app_close", [
        _calls(_call("app_open", {"appId": "notas"}, 0.95), _rival_call(0.3 if layer == 0 else 0.5)),
        _say("¿Apago el PC?")])
    monkeypatch.setenv("BAXY_S1_DOUBT", "0.4")
    mind.risk = {"system_power": "work_loss", "app_open": "read_only", "app_close": "work_loss"}
    result = mind.decide(1, "abre las notas y después ciérralo")
    assert result["operation"] is None and result["reply"] == "¿Apago el PC?"
    assert server.bodies[1].get("tool_choice") == "none"
    assert "system_power" in server.bodies[1]["messages"][-1]["content"]
    rows = [json.loads(line) for line in mind.trace.read_text("utf-8").splitlines()]
    assert rows[0]["kind"] == "doubt_ask" and rows[0]["operation"] == "system.power"


@pytest.mark.parametrize("second, risk", [
    (_rival_call(0.95), "work_loss"),  # sure of the power call: it runs after the first, as before
    (_call("app_close", {"appId": "notas"}, 0.3), "work_loss"),  # the kernel confirms it: its «sí» names it
    (_call("app_close", {"appId": "notas"}, 0.3), "read_only"),  # nothing to confirm: queued as before
])
def test_a_queued_call_sure_or_that_the_kernel_confirms_is_queued_as_before(tmp_path, monkeypatch, second,
                                                                            risk) -> None:
    _unasked(tmp_path, monkeypatch, "")
    monkeypatch.setenv("BAXY_S1_DOUBT", "0.4")
    mind, server = _mind(tmp_path, [_calls(_call("app_open", {"appId": "notas"}, 0.95), second)])
    mind.wire_to_op["app_close"] = "app.close"
    mind.risk = {"system_power": "work_loss", "app_open": "read_only", "app_close": risk}
    result = mind.decide(1, "abre las notas y después ciérralo")
    assert result["operation"] == "app.open"
    assert [c["wire"] for c in mind._turn["queue"]] == [second["choices"][0]["message"]["tool_calls"][0]["function"]["name"]]
    assert len(server.bodies) == 1


# Held-out of P2.40, written by a subagent that never saw the change: a power call queued behind another, unsure, asks
# before the first runs; with a queued call that confirms nothing, the reply runs as before.
HELD_OUT_QUEUED = [
    ("Cierra el reproductor y después apaga todo, que me voy", "app_close", {"appId": "spotify"}, "shutdown"),
    ("Baja el volumen al diez y reinicia el compu, porfa", "volume_set", {"level": 10}, "restart"),
    ("Googlea cómo actualizar drivers y pon el PC a dormir", "web_search", {"query": "cómo actualizar drivers"}, "sleep"),
    ("Ábreme la calculadora y sácame de mi sesión al tiro", "app_open", {"appId": "calculator"}, "logoff"),
    ("Terminé con el navegador, hasta ahí llegamos por hoy", "app_close", {"appId": "chrome"}, "shutdown"),
    ("Silencia todo, que me acuesto; suspende el equipo", "volume_set", {"level": 0}, "sleep")]
HELD_OUT_QUEUED_CLEAR = [
    ("Lanza el reproductor y sube el volumen a setenta", ("app_open", {"appId": "spotify"}),
     ("volume_set", {"level": 70})),
    ("Quita la planilla y pásame el editor de texto", ("app_close", {"appId": "excel"}), ("app_open", {"appId": "notepad"})),
    ("Investiga el clima en Valparaíso y averigua el dólar de hoy", ("web_search", {"query": "clima en Valparaíso"}),
     ("web_search", {"query": "precio del dólar hoy"}))]
HELD_OUT_RISK = {"system_power": "work_loss", "app_open": "read_only", "app_close": "work_loss",
                 "web_search": "read_only", "volume_set": "low_reversible"}


def _held_out_mind(tmp_path, monkeypatch, replies):
    _unasked(tmp_path, monkeypatch, "")
    monkeypatch.setenv("BAXY_S1_DOUBT", "0.4")
    mind, server = _mind(tmp_path, replies)
    mind.wire_to_op.update({w: w.replace("_", ".", 1) for w in HELD_OUT_RISK})
    mind.risk = dict(HELD_OUT_RISK)
    return mind, server


@pytest.mark.parametrize("words, wire, arguments, action", HELD_OUT_QUEUED)
def test_held_out_unsure_power_queued_second_is_asked(tmp_path, monkeypatch, words, wire, arguments, action) -> None:
    mind, server = _held_out_mind(tmp_path, monkeypatch, [
        _calls(_call(wire, arguments, 0.95), _call("system_power", {"action": action}, 0.3)), _say("¿Apago el PC?")])
    assert mind.decide(1, words)["operation"] is None
    assert server.bodies[1].get("tool_choice") == "none"


@pytest.mark.parametrize("words, first, second", HELD_OUT_QUEUED_CLEAR)
def test_held_out_unsure_queued_call_that_confirms_nothing_runs(tmp_path, monkeypatch, words, first, second) -> None:
    mind, server = _held_out_mind(tmp_path, monkeypatch, [_calls(_call(*first, 0.95), _call(*second, 0.3))])
    assert mind.decide(1, words)["operation"] == mind.wire_to_op[first[0]]
    assert [c["wire"] for c in mind._turn["queue"]] == [second[0]] and len(server.bodies) == 1


def test_in_bypass_an_unsure_external_call_queued_second_is_asked(tmp_path, monkeypatch) -> None:
    _unasked(tmp_path, monkeypatch, "bypass")
    monkeypatch.setenv("BAXY_S1_DOUBT", "0.4")
    mind, server = _mind(tmp_path, [_calls(_call("app_open", {"appId": "correo"}, 0.95),
                                           _call("email_send", {"to": "ana"}, 0.3)), _say("¿A quién se lo mando?")])
    mind.wire_to_op["email_send"] = "email.send"
    mind.risk = {"app_open": "read_only", "email_send": "external_communication"}
    mind.confirms = {"email_send": ["normal"]}  # what the kernel sends for email.send (P2.41)
    assert mind.decide(1, "abre el correo y mándaselo")["operation"] is None
    assert server.bodies[1].get("tool_choice") == "none"


def test_an_unsure_power_call_queued_third_is_asked(tmp_path, monkeypatch) -> None:
    mind, server = _held_out_mind(tmp_path, monkeypatch, [
        _calls(_call("app_open", {"appId": "notas"}, 0.95), _call("volume_set", {"level": 0}, 0.95),
               _call("system_power", {"action": "sleep"}, 0.3)), _say("¿Suspendo el PC?")])
    assert mind.decide(1, "abre las notas, silencia y suspende")["operation"] is None
    assert server.bodies[1].get("tool_choice") == "none"
    rows = [json.loads(line) for line in mind.trace.read_text("utf-8").splitlines()]
    assert rows[0]["kind"] == "doubt_ask" and rows[0]["operation"] == "system.power"
    assert rows[0]["call_index"] == 2 and rows[0]["doubt"]["confidence"] < 0.4  # the doubt of the call held


def test_layer2_correcting_a_queued_call_keeps_the_calls_before_it(tmp_path, monkeypatch) -> None:
    _unasked(tmp_path, monkeypatch, "")
    mind, server, _ = _correcting(tmp_path, monkeypatch, "low_reversible",
                                  {"name": "app_close", "arguments": {"appId": "notas"}, "timings": {}})
    server.replies[0] = _calls(_call("app_open", {"appId": "notas"}, 0.95), _rival_call(0.5))
    mind.risk["app_open"] = "read_only"
    result = mind.decide(1, "abre las notas y después ciérralo")
    assert result["operation"] == "app.open"  # not doubted: it runs, and the correction waits behind it
    assert [(c["wire"], c["arguments"]) for c in mind._turn["queue"]] == [("app_close", {"appId": "notas"})]

# P2.41 (blind review of cand3f): in Bypass, a doubt asks in words only about a call the kernel would run unasked though
# it confirms it in normal mode, by the modes the kernel itself sends (the catalog's «confirms», RiskPolicy.Evaluate),
# not by the risk label: a song, a page or an event in the person's own calendar go direct in normal mode too, and
# message.send the kernel confirms in Bypass as well, so its doubt reads again with the tools instead of asking twice.
@pytest.mark.parametrize("operation, confirms", [("media.play.query", []), ("browser.navigate", []),
                                                ("message.send", ["normal", "bypass"])])
def test_in_bypass_an_unsure_external_call_the_kernel_does_not_run_unasked_is_read_again(tmp_path, monkeypatch,
                                                                                         operation, confirms) -> None:
    _unasked(tmp_path, monkeypatch, "bypass")
    wire = operation.replace(".", "_")
    monkeypatch.setenv("BAXY_S1_DOUBT", "0.4")
    empty = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    mind, server = _mind(tmp_path, [_call(wire, {}, 0.3), _call(wire, {}, 0.3)])
    mind.configure({"capabilities": [{"name": operation, "description": "Do it", "argumentsSchema": empty,
                                      "risk": "external_communication", "confirms": confirms}]})
    sent = mind.decide(1, "hazlo")
    assert sent["operation"] == operation and sent["unsure"] is True  # P2.43: weighed by the App with its arguments
    assert mind.continue_turn(2, json.dumps({"status": "held", "outcome": "unsure"}))["operation"] == operation
    assert all("tool_choice" not in body for body in server.bodies)  # held, it read again with its tools


def test_in_bypass_an_unsure_external_call_the_kernel_confirms_only_in_normal_mode_is_asked(tmp_path,
                                                                                         monkeypatch) -> None:
    _unasked(tmp_path, monkeypatch, "bypass")
    monkeypatch.setenv("BAXY_S1_DOUBT", "0.4")
    empty = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    mind, server = _mind(tmp_path, [_call("email_send", {}, 0.3), _say("¿A quién se lo mando?")])
    mind.configure({"capabilities": [{"name": "email.send", "description": "Send an email", "argumentsSchema": empty,
                                      "risk": "external_communication", "confirms": ["normal"]}]})
    assert mind.decide(1, "mándaselo")["operation"] is None
    assert server.bodies[1].get("tool_choice") == "none"


# P2.43: in Bypass the catalog cannot tell a click on «Enviar» (normal mode asks) from one on «Siguiente» (it does not):
# the doubt that would read again sends the action with «unsure», which the App never runs; its typed answer says whether
# the kernel would run that invocation unasked (then the doubt asks, with no tools) or not (it reads again with them).
def _click_mind(tmp_path, monkeypatch, mode: str, replies: list) -> tuple[Mind, FakeServer]:
    _unasked(tmp_path, monkeypatch, mode)
    monkeypatch.setenv("BAXY_S1_DOUBT", "0.4")
    label = {"type": "object", "properties": {"label": {"type": "string"}}, "required": ["label"],
             "additionalProperties": False}
    mind, server = _mind(tmp_path, [_call("input_visible_click", {"label": "Enviar"}, 0.3), *replies])
    mind.configure({"capabilities": [{"name": "input.visible.click", "description": "Click it",
                                      "argumentsSchema": label, "risk": "external_communication", "confirms": []}]})
    return mind, server


def test_in_bypass_an_unsure_action_goes_to_the_app_marked_unsure_and_nothing_else_is_decided(tmp_path,
                                                                                               monkeypatch) -> None:
    mind, server = _click_mind(tmp_path, monkeypatch, "bypass", [])
    result = mind.decide(1, "dale")
    assert result["kind"] == "action" and result["operation"] == "input.visible.click"
    assert result["unsure"] is True and result["arguments"] == {"label": "Enviar"}
    assert len(server.bodies) == 1
    assert not any(m.get("tool_calls") for m in mind.conversation)  # the doubted call is not in the conversation
    rows = [json.loads(line) for line in (tmp_path / "turns.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["kind"] == "doubt_unsure"


def test_an_unsure_action_the_kernel_would_run_unasked_is_asked_with_no_tools(tmp_path, monkeypatch) -> None:
    mind, server = _click_mind(tmp_path, monkeypatch, "bypass", [_say("¿Lo envío ya?")])
    mind.decide(1, "dale")
    result = mind.continue_turn(2, json.dumps({"status": "held", "outcome": "would_run_unasked"}))
    assert result["kind"] == "conversation" and result["reply"] == "¿Lo envío ya?"
    assert server.bodies[1].get("tool_choice") == "none"
    assert "input_visible_click" in server.bodies[1]["messages"][-1]["content"]
    assert not any(m.get("tool_calls") or m.get("role") == "tool" for m in server.bodies[1]["messages"])


def test_an_unsure_action_held_otherwise_is_read_again_with_tools_and_runs_when_chosen_again(tmp_path,
                                                                                              monkeypatch) -> None:
    mind, server = _click_mind(tmp_path, monkeypatch, "bypass",
                               [_call("input_visible_click", {"label": "Enviar"}, 0.3)])
    mind.decide(1, "dale")
    result = mind.continue_turn(2, json.dumps({"status": "held", "outcome": "unsure"}))
    assert "tool_choice" not in server.bodies[1]
    assert result["kind"] == "action" and result["arguments"] == {"label": "Enviar"} and "unsure" not in result


def test_in_normal_mode_an_unsure_action_reads_again_in_the_mind_as_before(tmp_path, monkeypatch) -> None:
    mind, server = _click_mind(tmp_path, monkeypatch, "", [_say("¿Cuál de los dos botones?")])
    result = mind.decide(1, "dale")
    assert result["kind"] == "conversation" and "unsure" not in result
    assert "tool_choice" not in server.bodies[1]


def test_an_app_that_ran_the_unsure_action_has_it_read_as_any_call(tmp_path, monkeypatch) -> None:
    mind, server = _click_mind(tmp_path, monkeypatch, "bypass", [_say("Listo.")])
    mind.decide(1, "dale")
    mind.continue_turn(2, json.dumps({"status": "completed", "verification": "none"}))
    messages = server.bodies[1]["messages"]
    called = [m for m in messages if m.get("tool_calls")]
    assert called and called[-1]["tool_calls"][0]["function"]["name"] == "input_visible_click"
    assert messages[-1]["role"] == "tool" and messages[-1]["tool_call_id"] == called[-1]["tool_calls"][0]["id"]


def test_an_unsure_call_the_mind_itself_refuses_is_refused_as_any_and_leaves_no_mark(tmp_path, monkeypatch) -> None:
    # Review of P2.43: a click on «Cerrar» nobody asked for is refused by the mind (aid «close_unsaid»), so it never goes
    # to the App «unsure»; the refusal keeps a valid tool transcript and the next call runs and is answered as itself.
    mind, server = _click_mind(tmp_path, monkeypatch, "bypass", [_call("app_open", {"name": "notepad"}, 0.99)])
    mind.wire_to_op["app_open"] = "app.open"
    server.replies.insert(0, _call("input_visible_click", {"label": "Cerrar"}, 0.3))
    server.replies.pop(1)
    result = mind.decide(1, "dale")
    assert "unsure" not in result and "unsure" not in mind._turn
    calls = {c["id"] for m in mind.conversation for c in m.get("tool_calls") or []}
    assert all(m["tool_call_id"] in calls for m in mind.conversation if m.get("role") == "tool")


# P2.43b (silent-failure-hunter on P2.43): the reading again after a held «unsure» was not weighed, though it may be
# another invocation (a click on «Siguiente» weighed, then one on «Enviar» chosen in doubt: Bypass ran it unasked). A
# doubted reading with another key (operation and canonical arguments) goes to the App «unsure» too, at most
# UNSURE_WEIGHS times a turn, so the doubt never loops; the same invocation, already weighed, runs.
def _weighed_again(mind: Mind, outcome: str = "unsure") -> dict:
    return mind.continue_turn(9, json.dumps({"status": "held", "outcome": outcome}))


def _first(server: FakeServer, reply: dict) -> None:
    server.replies[0] = reply  # the doubted call of _click_mind, replaced


def test_a_doubted_reading_again_of_another_invocation_is_weighed_and_asked_when_it_would_run_unasked(
        tmp_path, monkeypatch) -> None:
    mind, server = _click_mind(tmp_path, monkeypatch, "bypass",
                               [_call("input_visible_click", {"label": "Enviar"}, 0.3), _say("¿Lo envío?")])
    _first(server, _call("input_visible_click", {"label": "Siguiente"}, 0.3))
    assert mind.decide(1, "dale")["arguments"] == {"label": "Siguiente"}
    again = _weighed_again(mind)
    assert again["kind"] == "action" and again["unsure"] is True and again["arguments"] == {"label": "Enviar"}
    asked = _weighed_again(mind, "would_run_unasked")
    assert asked["kind"] == "conversation" and asked["reply"] == "¿Lo envío?"
    assert server.bodies[-1].get("tool_choice") == "none"


def test_a_sure_reading_again_of_another_invocation_runs(tmp_path, monkeypatch) -> None:
    mind, _ = _click_mind(tmp_path, monkeypatch, "bypass", [_call("input_visible_click", {"label": "Siguiente"}, 0.9)])
    mind.decide(1, "dale")
    result = _weighed_again(mind)
    assert result["arguments"] == {"label": "Siguiente"} and "unsure" not in result


def test_the_weighing_of_a_doubt_is_bounded_and_past_it_the_doubt_asks(tmp_path, monkeypatch) -> None:
    mind, server = _click_mind(tmp_path, monkeypatch, "bypass",
                               [*(_call("input_visible_click", {"label": label}, 0.3)
                                  for label in ("Ver detalles", "Vaciar papelera")), _say("¿Qué botón aprieto?")])
    mind.decide(1, "dale")
    assert _weighed_again(mind)["unsure"] is True  # the reading's other invocation, weighed
    last = _weighed_again(mind)
    assert last["kind"] == "conversation" and last["reply"] == "¿Qué botón aprieto?"  # no third weighing, no run
    assert server.bodies[-1].get("tool_choice") == "none" and len(server.bodies) == 4


def test_the_persons_answer_after_a_weighed_doubt_is_not_weighed_again(tmp_path, monkeypatch) -> None:
    # One question per misunderstanding (4.2): the reading asked with ask_user, and the call that answers it is the
    # person's, as layer 0 never holds an answer.
    mind, _ = _click_mind(tmp_path, monkeypatch, "bypass", [_call("ask_user", {"question": "¿Cuál?"}, 0.9),
                                                            _call("input_visible_click", {"label": "Siguiente"}, 0.3)])
    monkeypatch.setenv("BAXY_S1_VETO", "0.6")
    mind.system_one = FakeSystemOne("app_close")  # type: ignore[assignment]
    mind.decide(1, "dale")
    assert _weighed_again(mind)["kind"] == "clarify"
    result = mind.decide(2, "el de seguir")
    assert result["arguments"] == {"label": "Siguiente"} and "unsure" not in result


@pytest.mark.parametrize("held", [{"status": "held"}, {"status": "held", "outcome": "other"}])
def test_a_held_answer_with_an_outcome_the_mind_does_not_know_asks(tmp_path, monkeypatch, held) -> None:
    mind, server = _click_mind(tmp_path, monkeypatch, "bypass", [_say("¿Lo envío?")])
    mind.decide(1, "dale")
    assert mind.continue_turn(2, json.dumps(held))["kind"] == "conversation"
    assert server.bodies[1].get("tool_choice") == "none"


def test_in_normal_mode_the_reading_again_is_not_weighed(tmp_path, monkeypatch) -> None:
    mind, _ = _click_mind(tmp_path, monkeypatch, "", [_call("input_visible_click", {"label": "Siguiente"}, 0.3)])
    result = mind.decide(1, "dale")
    assert result["arguments"] == {"label": "Siguiente"} and "unsure" not in result


def test_in_bypass_the_reading_again_after_layer2_that_it_still_doubts_is_weighed(tmp_path, monkeypatch) -> None:
    _unasked(tmp_path, monkeypatch, "bypass")
    mind, server, one = _layer2(tmp_path, monkeypatch, "app_close",
                                [_rival_call(0.5), _call("input_visible_click", {"label": "Enviar"}, 0.5)])
    mind.wire_to_op["input_visible_click"] = "input.visible.click"
    mind.risk = {"system_power": "read_only", "app_close": "read_only", "input_visible_click": "external_communication"}
    mind.confirms = {"system_power": [], "app_close": [], "input_visible_click": []}
    result = mind.decide(1, "dale")
    assert ", pero también podría ser " in server.bodies[1]["messages"][-1]["content"]  # layer 2 held the first
    assert result["unsure"] is True and result["arguments"] == {"label": "Enviar"}
    assert len(one.asked) == 1  # the reading again is weighed by the App, not judged again


# Held-out of P2.43b, written by a subagent that never saw the change: whatever the words and the labels, a doubted
# reading of another invocation is weighed; the mind reads none of them.
HELD_OUT_NEUTRAL = ["Ver detalles", "Mostrar más opciones", "Abrir carpeta", "Vista previa", "Ir al carrito",
                    "Seguir leyendo"]
HELD_OUT_REACHES = ["Publicar ahora", "Pagar $24.990", "Confirmar transferencia", "Vaciar papelera",
                    "Borrar para todos", "Comprar ahora"]
HELD_OUT_ASKED = ["ya po, apriétale nomás", "hácele no más, si está bien", "métele, sigue con eso",
                  "ya, échale pa' delante", "pásale a lo que viene, cachai", "ya, la cuestión esa, apriétala"]


@pytest.mark.parametrize("words, first, then", list(zip(HELD_OUT_ASKED, HELD_OUT_NEUTRAL, HELD_OUT_REACHES)))
def test_held_out_doubted_readings_of_another_invocation_are_weighed(tmp_path, monkeypatch, words, first, then) -> None:
    mind, server = _click_mind(tmp_path, monkeypatch, "bypass", [_call("input_visible_click", {"label": then}, 0.3)])
    _first(server, _call("input_visible_click", {"label": first}, 0.3))
    assert mind.decide(1, words)["arguments"] == {"label": first}
    again = _weighed_again(mind)
    assert again["unsure"] is True and again["arguments"] == {"label": then}


# P2.41b (review of cand5): a catalog without «confirms» (an older App, a bench's --catalog, a fixture) is not one that
# says the kernel confirms nothing: in Bypass the doubt keeps the prudent rule from before P2.41 (external_communication
# counts as confirmed in normal mode, so it asks), and the configure trace names the tools that came without the field.
def _email_mind(tmp_path, monkeypatch, replies: list, **confirms) -> tuple[Mind, FakeServer]:
    _unasked(tmp_path, monkeypatch, "bypass")
    monkeypatch.setenv("BAXY_S1_DOUBT", "0.4")
    empty = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    mind, server = _mind(tmp_path, [_call("email_send", {}, 0.3), *replies])
    mind.configure({"capabilities": [{"name": "email.send", "description": "Send an email", "argumentsSchema": empty,
                                      "risk": "external_communication", **confirms},
                                     {"name": "app.open", "description": "Open it", "argumentsSchema": empty,
                                      "risk": "read_only", "confirms": []}]})
    return mind, server


def _absent_rows(tmp_path) -> list:
    rows = [json.loads(line) for line in (tmp_path / "turns.jsonl").read_text(encoding="utf-8").splitlines()]
    return [r["operations"] for r in rows if r["stage"] == "configure.confirms_absent"]


@pytest.mark.parametrize("confirms", [{}, {"confirms": None}, {"confirms": "normal"}, {"confirms": True},
                                      {"confirms": [1]}])
def test_a_catalog_without_confirms_keeps_the_prudent_doubt_and_says_so(tmp_path, monkeypatch, confirms) -> None:
    mind, server = _email_mind(tmp_path, monkeypatch, [_say("¿A quién se lo mando?")], **confirms)
    result = mind.decide(1, "mándaselo")
    assert result["operation"] is None and "unsure" not in result
    assert server.bodies[1].get("tool_choice") == "none"
    assert _absent_rows(tmp_path) == [["email.send"]]


def test_a_catalog_with_confirms_empty_is_read_as_the_kernel_sent_it(tmp_path, monkeypatch) -> None:
    mind, _ = _email_mind(tmp_path, monkeypatch, [], confirms=[])
    assert mind.decide(1, "mándaselo")["unsure"] is True
    assert _absent_rows(tmp_path) == []


# P2.40 with P2.43 (fusión de noche-pc-r5-8 con 7db8c2726): in Bypass a queued call the App weighs with its arguments
# (a click the catalog cannot tell) is the one held «unsure», not the first; the call before it, not doubted, runs first
# with its words, and the click goes to the App to be weighed only once that one completed.
def _queued_click(tmp_path, monkeypatch, label: str, replies: list) -> tuple[Mind, FakeServer]:
    mind, server = _click_mind(tmp_path, monkeypatch, "bypass", replies)
    server.replies[0] = _calls(_call("app_open", {"appId": "correo"}, 0.95), _call("input_visible_click",
                                                                                   {"label": label}, 0.3))
    server.replies[0]["choices"][0]["message"]["content"] = "Abro el correo."
    mind.wire_to_op["app_open"] = "app.open"
    mind.risk["app_open"] = "read_only"
    return mind, server


def test_in_bypass_an_unsure_click_queued_second_goes_to_the_app_unsure_after_the_first(tmp_path, monkeypatch) -> None:
    mind, server = _queued_click(tmp_path, monkeypatch, "Enviar", [_say("¿Lo envío?")])
    first = mind.decide(1, "abre el correo y dale a enviar")
    assert first["operation"] == "app.open" and not first.get("unsure")  # not doubted: it runs, with its words
    assert mind.conversation[-1]["content"] == "Abro el correo."
    assert [c["function"]["name"] for c in mind.conversation[-1]["tool_calls"]] == ["app_open"]
    sent = mind.continue_turn(2, json.dumps({"status": "completed", "outcome": "app_opened"}))
    assert sent["operation"] == "input.visible.click" and sent["unsure"] is True  # weighed by the App, never run
    assert sent["arguments"] == {"label": "Enviar"}
    asked = mind.continue_turn(3, json.dumps({"status": "held", "outcome": "would_run_unasked"}))
    assert asked["operation"] is None and server.bodies[-1].get("tool_choice") == "none"
    tools = [m["tool_call_id"] for m in mind.conversation if m.get("role") == "tool"]
    calls = [c["id"] for m in mind.conversation for c in m.get("tool_calls") or []]
    assert tools == calls  # app_open kept its result; the weighed click never entered the conversation


def test_in_bypass_an_unsure_click_queued_after_a_call_that_failed_is_not_weighed(tmp_path, monkeypatch) -> None:
    mind, server = _queued_click(tmp_path, monkeypatch, "Enviar", [_say("No pude abrir el correo.")])
    assert mind.decide(1, "abre el correo y dale a enviar")["operation"] == "app.open"
    told = mind.continue_turn(2, json.dumps({"status": "failed", "outcome": "app_not_found"}))
    assert told["operation"] is None and "unsure" not in mind._turn  # nothing else runs nor waits to be weighed


def test_in_bypass_a_safe_or_sure_call_queued_second_is_queued_as_before(tmp_path, monkeypatch) -> None:
    mind, _ = _queued_click(tmp_path, monkeypatch, "Siguiente", [])
    mind.server.replies[0] = _calls(_call("app_open", {"appId": "correo"}, 0.95),
                                    _call("input_visible_click", {"label": "Siguiente"}, 0.95))
    assert mind.decide(1, "abre el correo y dale a siguiente")["operation"] == "app.open"
    assert [c["wire"] for c in mind._turn["queue"]] == ["input_visible_click"] and "unsure" not in mind._turn


def test_in_bypass_an_unsure_typing_queued_behind_the_app_it_needs_is_weighed_once_it_opened(tmp_path,
                                                                                              monkeypatch) -> None:
    # Review of the merge: at deciding, the aid «unopened_app» would refuse the typing (its app not open yet), so the
    # doubt was lost and, once the app opened, it ran unweighed. It is weighed when it goes, with the state of then.
    _unasked(tmp_path, monkeypatch, "bypass")
    monkeypatch.setenv("BAXY_S1_DOUBT", "0.4")
    mind, _ = _mind(tmp_path, [_calls(_call("app_open", {"appId": "notas"}, 0.95),
                                      _call("input_text_type", {"text": "hola"}, 0.3))])
    mind.wire_to_op.update({"app_open": "app.open", "input_text_type": "input.text.type"})
    mind.risk = {"app_open": "read_only", "input_text_type": "privacy_sensitive"}
    mind.confirms = {"input_text_type": []}
    mind.names = ["notas"]
    assert mind.decide(1, "abre notas y escribe hola en notas")["operation"] == "app.open"
    sent = mind.continue_turn(2, json.dumps({"status": "completed", "outcome": "app_opened"}))
    assert sent["operation"] == "input.text.type" and sent["unsure"] is True


def test_in_bypass_a_queued_click_an_old_app_ran_enters_the_conversation(tmp_path, monkeypatch) -> None:
    mind, _ = _queued_click(tmp_path, monkeypatch, "Enviar", [_say("Listo.")])
    mind.decide(1, "abre el correo y dale a enviar")
    assert mind.continue_turn(2, json.dumps({"status": "completed", "outcome": "app_opened"}))["unsure"] is True
    mind.continue_turn(3, json.dumps({"status": "completed", "outcome": "clicked"}))  # an App that does not know it
    calls = [c["function"]["name"] for m in mind.conversation for c in m.get("tool_calls") or []]
    tools = [m["tool_call_id"] for m in mind.conversation if m.get("role") == "tool"]
    assert calls == ["app_open", "input_visible_click"] and len(tools) == 2  # read as any call that ran


@pytest.mark.parametrize("risk", ["read_only", "low_reversible"])
def test_in_bypass_an_unsure_call_queued_second_that_only_reads_or_is_undone_is_queued_as_before(tmp_path, monkeypatch,
                                                                                                 risk) -> None:
    mind, server = _queued_click(tmp_path, monkeypatch, "Siguiente", [])
    mind.risk["input_visible_click"] = risk
    assert mind.decide(1, "abre el correo y dale a siguiente")["operation"] == "app.open"
    assert [c["wire"] for c in mind._turn["queue"]] == ["input_visible_click"] and "unsure" not in mind._turn
    assert len(server.bodies) == 1
