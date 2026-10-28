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


@pytest.mark.parametrize("mode", ["", "bypass"])
def test_an_unsure_work_loss_action_the_kernel_runs_unasked_is_asked_without_tools(tmp_path, monkeypatch, mode) -> None:
    # P2.34: read again with its tools, the model could make the same call, and nobody asked before it ran: the kernel
    # runs system.power unasked (identity), and every work_loss call in Bypass. Its doubt asks, as before pregunta-eco.
    monkeypatch.setenv("BAXY_S1_DOUBT", "0.4")
    monkeypatch.setenv("BAXY_DATA_DIR", str(tmp_path))
    if mode:
        (tmp_path / "confirmation-mode").write_text(mode, encoding="utf-8")
    mind, server = _mind(tmp_path, [_call("system_power", {"action": "shutdown"}, 0.3), _say("¿Apago el PC?")])
    mind.risk = {"system_power": "work_loss"}
    result = mind.decide(1, "ahora ciérralo")
    assert result["operation"] is None and result["reply"] == "¿Apago el PC?"
    assert not server.bodies[1].get("tools") or server.bodies[1].get("tool_choice") == "none"
    rows = [json.loads(line) for line in mind.trace.read_text("utf-8").splitlines()]
    assert rows[0]["kind"] == "doubt_ask" and rows[0]["operation"] == "system.power"


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


@pytest.mark.parametrize("approve,p_name,held", [(True, 0.78, True), (True, 0.999, False), (False, 0.78, False)])
def test_a_yes_the_model_is_not_sure_of_is_held_and_asked(tmp_path, monkeypatch, approve, p_name, held) -> None:
    # Confirmaciones 2026-10-23: «sí pero el otro» approved a pending trash at 0.77-0.79; plain yeses were ≥ 0.998.
    monkeypatch.delenv("BAXY_S1_DOUBT", raising=False)
    monkeypatch.delenv("BAXY_CONFIRM_FLOOR", raising=False)
    reply = _call("confirm_pending", {"approve": approve}, p_name)
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
        assert result["arguments"]["approve"] is approve


def test_the_confirm_floor_can_be_turned_off(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_CONFIRM_FLOOR", "0")
    mind, _ = _mind(tmp_path, [_call("confirm_pending", {"approve": True}, 0.5)])
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
    reply = _call("confirm_pending", {"approve": True}, 0.78)
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
# Bypass every one of them, and what goes out of the PC) is asked about as before the night, whichever layer doubted it
# and also when the reading after another doubt chose it.
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
    ("busca en internet el clima de mañana en curicó", _call("web_search", {"query": "clima"}, 0.3), "web.search")])
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
