"""The mind's own tool «calculate» (feria 2026-10-27): sums the 4B model did from memory went wrong (12 for two plus
two once the recognizer misheard a digit) and an 18-digit square root went to the Calculator, which takes none. The
model writes the expression it understood; arithmetic.evaluate computes it and the result is the data it answers from."""
import json
import math
from pathlib import Path

from baxy_mind.mind import CALCULATE, SAME_CALL_NOT_RUN, SYSTEM

from test_mind_final import _call, _mind, _say


def test_the_model_writes_the_expression_and_answers_from_its_value(tmp_path: Path) -> None:
    mind, server = _mind(tmp_path, [_call("calculate", {"expression": "2+2"}), _say("Son cuatro.")])
    step = mind.decide(1, "¿Cuánto es do más dos?")
    assert step["kind"] == "conversation" and step["reply"] == "Son cuatro." and step["operation"] is None
    told = server.bodies[1]["messages"][-1]
    assert told["role"] == "tool" and json.loads(told["content"]) == {"status": "completed", "value": "4"}
    rows = [json.loads(line) for line in mind.trace.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["kind"] == "calculated" and rows[0]["arguments"] == {"expression": "2+2"}


def test_a_root_the_calculator_app_cannot_take_is_computed(tmp_path: Path) -> None:
    mind, server = _mind(tmp_path, [_call("calculate", {"expression": "sqrt(567344565230966678)"}),
                                    _say("Unos 753 millones.")])
    mind.decide(1, "¿Cuánto es la raíz cuadrada de 567344565230966678?")
    assert json.loads(server.bodies[1]["messages"][-1]["content"])["value"].startswith("≈ 753222785.92")


def test_an_expression_that_cannot_be_computed_says_why(tmp_path: Path) -> None:
    mind, server = _mind(tmp_path, [_call("calculate", {"expression": "1/0"}), _say("No se puede dividir por cero.")])
    assert mind.decide(1, "¿Cuánto es uno entre cero?")["reply"] == "No se puede dividir por cero."
    assert json.loads(server.bodies[1]["messages"][-1]["content"]) == {"status": "failed", "error": "division by zero"}
    rows = [json.loads(line) for line in mind.trace.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["kind"] == "calculation_failed"


def test_the_same_expression_again_closes_the_turns_calls(tmp_path: Path, monkeypatch) -> None:
    # code review 2026-10-27: a calculation the model repeats never reaches the App's step budget
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    same = _call("calculate", {"expression": "2x3"})
    mind, server = _mind(tmp_path, [same, same, _say("No pude calcularlo.")])
    assert mind.decide(1, "¿Cuánto es dos por tres?")["reply"] == "No pude calcularlo." and len(server.bodies) == 3
    assert server.bodies[2]["messages"][-1]["content"].startswith(SAME_CALL_NOT_RUN)


def test_calls_written_beside_it_wait_for_its_value(tmp_path: Path) -> None:
    reply = _call("calculate", {"expression": "6*7"})
    reply["choices"][0]["message"]["tool_calls"].append(
        {"id": "c2", "function": {"name": "input_text_type", "arguments": json.dumps({"text": "41"})}})
    mind, server = _mind(tmp_path, [reply, _call("input_text_type", {"text": "42"})])
    mind.wire_to_op = {"input_text_type": "input.text.type"}
    step = mind.decide(1, "Escribe cuánto es seis por siete.")
    assert step["kind"] == "action" and step["arguments"] == {"text": "42"}
    told = [json.loads(m["content"]) for m in server.bodies[1]["messages"] if m["role"] == "tool"]
    assert told[0]["value"] == "42" and told[1]["status"] == "not_run"


def test_an_unsure_calculation_is_not_held(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_S1_DOUBT", "0.4")
    reply = _call("calculate", {"expression": "3*3"})
    reply["choices"][0]["logprobs"] = {"content": [
        {"token": token, "logprob": math.log(p), "top_logprobs": [{"token": token, "logprob": math.log(p)}]}
        for token, p in (("<tool_call>", 0.95), ("\n", 1.0), ("<", 1.0), ("function", 1.0), ("=", 1.0),
                         ("calculate", 0.2), (">", 1.0))]}
    mind, server = _mind(tmp_path, [reply, _say("Nueve.")])
    assert mind.decide(1, "tres por tres")["reply"] == "Nueve."


def test_it_is_offered_beside_the_catalog_and_rule_5_sends_sums_to_it(tmp_path: Path) -> None:
    mind, _ = _mind(tmp_path, [])
    mind.configure({"capabilities": [{"name": "app.open", "description": "Open an app.", "risk": "low_reversible"}]})
    assert CALCULATE in mind.tools and "calculate" in SYSTEM.split("\n5. ")[1].split("\n")[0]


def test_the_calculator_app_and_calculate_send_each_other_what_is_theirs(tmp_path: Path) -> None:
    # noche 2026-10-27 (P1.5): the Calculator app's description, older than calculate, sent a plain arithmetic question
    # to an answer «without tools» and took only an explicit ask; with the Calculator just opened, «haz una
    # multiplicación» was answered by the mind (1/10). Each description names the other for what the other does.
    mind, _ = _mind(tmp_path, [])
    app = mind.english["calculator.expression.evaluate"]
    assert "without tools" not in app and "(calculate)" in app
    assert "(calculator_expression_evaluate)" in CALCULATE["function"]["description"]


def test_the_calculator_opened_in_this_conversation_is_used_not_opened_again(tmp_path: Path) -> None:
    # noche 2026-10-28 (P2.24, held-out R1-c03 9/10 fallos): «It must be open ... first (app_open)» was a condition the
    # model could only meet by calling app_open again, with the Calculator just opened. With none open nothing is pressed
    # and the result says so (calculator_window_not_found, with app_open as its next step).
    app = _mind(tmp_path, [])[0].english["calculator.expression.evaluate"]
    assert "first (app_open)" not in app and "calculator_window_not_found" in app


def test_an_application_named_to_write_in_goes_to_app_open(tmp_path: Path) -> None:
    # noche 2026-10-28 (P2.24, held-out R5-c13 4/10 fallos): with the application to write in named and not open, a note,
    # a file or a look at a window that is not there won over opening it. Each says when app_open is the call.
    english = _mind(tmp_path, [])[0].english
    for operation in ("note.create", "file.write", "input.visible.controls"):
        avoid = english[operation].split("Do not use when:")[1].split("Examples:")[0]
        assert "(app_open" in avoid, operation


def test_a_calculation_after_memory_keeps_its_expression_out_of_the_trace(tmp_path: Path) -> None:
    # privacy review 2026-10-27: figures of what the person keeps stay out of the trace, as every row after memory
    mind, server = _mind(tmp_path, [_call("memory_recall", {"query": "saldo"}),
                                    _call("calculate", {"expression": "0.15*4823.5"}), _say("Unos 723.")])
    mind.wire_to_op = {"memory_recall": "memory.recall"}
    mind.decide(1, "¿Cuánto es el 15 % de mi saldo?")
    mind.continue_turn(2, json.dumps({"status": "completed", "items": [{"text": "saldo 4823.5"}]}))
    rows = [json.loads(line) for line in mind.trace.read_text(encoding="utf-8").splitlines()]
    assert [r for r in rows if r.get("kind") == "calculated"][0]["arguments"] is None


def test_calculations_have_a_bound_and_then_the_answer_is_in_words(tmp_path: Path, monkeypatch) -> None:
    # code review 2026-10-27: each calculation decides again (_next) without the App's step budget; a model that keeps
    # writing new expressions must still end the turn
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    calls = [_call("calculate", {"expression": f"2*{n}"}) for n in range(1, 5)]
    mind, server = _mind(tmp_path, [*calls, _say("Son dieciséis.")])
    assert mind.decide(1, "¿Cuánto es dos por ocho?")["kind"] == "conversation"
    assert len(server.bodies) == len(calls) + 1 and server.bodies[-1].get("tool_choice") == "none"


def test_its_examples_carry_no_number_to_copy_and_a_rate_it_was_not_given_goes_to_web_search() -> None:
    # noche 2026-10-28 (P2.25): the example numbers were copied into the answer: rule 6's «sincuenta» es 50 read
    # «beinticinco» and «zinco» as 50 and 52, and «15% of 200» turned the 17,5 % of 2.380 into 15 %. A conversion
    # was multiplied by a rate the model made up, and a logarithm was answered from memory, wrong.
    rule_6 = SYSTEM[SYSTEM.index("\n6. ") + 4:SYSTEM.index("\n7. ")]
    description = CALCULATE["function"]["description"]
    assert not any(character.isdecimal() for character in rule_6)
    assert "15%" not in description and "log10()" in description and "ln()" in description
    assert "(web_search)" in description


def _told(server, at: int = 1) -> str:
    return server.bodies[at]["messages"][-1]["content"]


def test_a_number_nobody_gave_is_said_beside_the_value(tmp_path: Path, monkeypatch) -> None:
    # uso real 2026-11-02: a conversion was computed with a rate the model made up and told as fact. The result says
    # which number of the expression neither the person said nor a result gave; «450 mil» is 450000, said.
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_call("calculate", {"expression": "450000 * 0.0038"}), _say("Unos 1.710."),
                                    _say("No sé la tasa de hoy.")])
    mind.decide(1, "¿Cuánto son 450 mil pesos chilenos en pesos colombianos?")
    value, note = _told(server).split("\n", 1)
    assert json.loads(value) == {"status": "completed", "value": "1710"}
    assert note.startswith("[Ayuda: 0.0038 ") and "450000" not in note


def test_held_out_a_unit_factor_nobody_gave_is_said_too(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_call("calculate", {"expression": "(12 + 7) * 0.31"}), _say("Unos 5,9 metros."),
                                    _say("Son casi seis metros.")])
    mind.decide(1, "Tengo una tabla de 12 pies y otra de 7, ¿cuántos metros suman?")
    note = _told(server).split("\n", 1)[1]
    assert note.startswith("[Ayuda: 0.31 ") and "12" not in note and "7 " not in note


def test_numbers_said_in_words_with_points_or_as_a_percentage_are_said(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    for said, expression in (("¿Cuánto es dos más dos?", "2+2"),
                             ("multiplica cuatrocientos cincuenta mil por tres", "450000*3"),
                             ("reparte 1.250.000 entre 4,5 personas", "1250000/4.5"),
                             ("¿cuánto es 1,5 millones menos 300 mil?", "1500000-300000"),
                             ("¿cuánto es el 15 % de 2380?", "15/100*2380"),
                             ("súmale el 19% a 1000", "1000*(1+0.19)")):
        mind, server = _mind(tmp_path, [_call("calculate", {"expression": expression}), _say("Listo.")])
        mind.decide(1, said)
        assert "[Ayuda" not in _told(server), said


def test_a_number_a_tool_gave_is_said_and_a_note_gives_none(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_call("memory_recall", {"query": "tasa"}),
                                    _call("calculate", {"expression": "450000*4.31"}),
                                    _call("calculate", {"expression": "1939500*0.0038"}), _say("Listo.")])
    mind.wire_to_op = {"memory_recall": "memory.recall"}
    mind.decide(1, "¿Cuánto son 450 mil con la tasa que guardé?")
    mind.continue_turn(2, json.dumps({"status": "completed", "items": [{"text": "tasa 4,31"}]}))
    assert "[Ayuda" not in _told(server, 2)
    assert _told(server, 3).split("\n", 1)[1].startswith("[Ayuda: 0.0038 ")


def test_with_the_unsourced_number_aid_off_the_value_is_told_alone(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_AYUDAS", "same_call_closes")
    mind, server = _mind(tmp_path, [_call("calculate", {"expression": "450000 * 0.0038"}), _say("Unos 1.710.")])
    mind.decide(1, "¿Cuánto son 450 mil pesos chilenos en pesos colombianos?")
    assert json.loads(_told(server)) == {"status": "completed", "value": "1710"}


# Encargo 35 (bancos de uso, R18 «usa la calculadora para pasar 250 mil pesos chilenos a pesos colombianos con la tasa de
# hoy»): the model opened the Windows Calculator and multiplied by a rate it made up (0.00085; the day's was 3.2264), and
# told the display's value as the conversion «con la tasa de hoy». The Calculator's result says, as calculate's does,
# which number of its expression neither the person said nor a result gave.
CALCULATOR_SHOWN = json.dumps({"status": "completed", "verification": "readback", "observed": {
    "version": 1, "expression": "250000*0.00085", "mode": "Standard", "value": "212.5"}})


def _calculator(tmp_path: Path, expression: str) -> tuple:
    mind, server = _mind(tmp_path, [_call("calculator_expression_evaluate", {"expression": expression}),
                                    _say("Listo.")])
    mind.wire_to_op = {"calculator_expression_evaluate": "calculator.expression.evaluate"}
    return mind, server


def test_the_calculators_value_says_a_number_nobody_gave(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _calculator(tmp_path, "250000*0.00085")
    mind.decide(1, "Usa la calculadora para pasar 250 mil pesos chilenos a pesos colombianos con la tasa de hoy.")
    mind.continue_turn(1, CALCULATOR_SHOWN)
    told = _told(server)
    assert "[Ayuda: 0.00085 " in told and "250000" not in told.split("[Ayuda:", 1)[1]


def test_the_calculators_value_from_numbers_said_has_no_note(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _calculator(tmp_path, "250000*0.00085")
    mind.decide(1, "Usa la calculadora para multiplicar 250 mil por 0,00085.")
    mind.continue_turn(1, CALCULATOR_SHOWN)
    assert "[Ayuda" not in _told(server)


def test_a_calculator_that_failed_has_no_note(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _calculator(tmp_path, "250000*0.00085")
    mind.decide(1, "Usa la calculadora para pasar 250 mil pesos chilenos a pesos colombianos con la tasa de hoy.")
    mind.continue_turn(1, json.dumps({"status": "failed", "error": "calculator_window_not_found"}))
    assert "[Ayuda: 0.00085" not in _told(server)


def test_a_number_nobody_gave_says_where_the_one_that_changes_is_looked_up(tmp_path: Path, monkeypatch) -> None:
    # Encargo A2 (HP3): the note of an unsourced number also carries its next, a web_search, and leaves a fixed factor
    # to the model; it names no digit of the expression and writes no reply.
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _calculator(tmp_path, "50000*0.0011")
    mind.decide(1, "Abre la calculadora y dime cuánto son 50.000 pesos en dólares.")
    mind.continue_turn(1, CALCULATOR_SHOWN)
    note = _told(server).split("[Ayuda:", 1)[1]
    assert "web_search" in note and "factor fijo" in note and "50000" not in note
    mind, server = _calculator(tmp_path, "250000*0.00085")
    mind.decide(1, "Usa la calculadora para multiplicar 250 mil por 0,00085.")
    mind.continue_turn(1, CALCULATOR_SHOWN)
    assert "[Ayuda" not in _told(server)


def test_an_answer_that_tells_the_rate_nobody_gave_is_asked_again_with_its_tools(tmp_path: Path, monkeypatch) -> None:
    # Encargo A2 (HP3): the answer «50.000 entre 900 es 55,56» tells the made-up rate; the model reads the fact and its
    # next (web_search), keeps its tools and may search. A figure the person gave is not checked.
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    shown = json.dumps({"status": "completed", "verification": "readback", "observed": {
        "version": 1, "expression": "50000/900", "mode": "Standard", "value": "55,55555556"}})
    mind, server = _mind(tmp_path, [_call("calculator_expression_evaluate", {"expression": "50000/900"}),
                                    _say("50.000 pesos son 55,56 dólares con 900 pesos por dólar."),
                                    _call("web_search", {"query": "dólar hoy en pesos"})])
    mind.wire_to_op = {"calculator_expression_evaluate": "calculator.expression.evaluate", "web_search": "web.search"}
    mind.decide(1, "Abre la calculadora y dime cuánto son 50.000 pesos en dólares.")
    step = mind.continue_turn(1, shown)
    assert step["kind"] == "action" and step["operation"] == "web.search"
    asked = server.bodies[2]["messages"][-1]["content"]
    assert "web_search" in asked and "900" in asked and "tools" in server.bodies[2] and server.bodies[2].get("tool_choice") != "none"


def test_a_fixed_factor_told_again_after_the_note_is_spoken(tmp_path: Path, monkeypatch) -> None:
    # Encargo A2, control «¿cuántos kilos son 150 libras?»: the factor 0.453592 nobody gave is told, the note says once
    # that a fixed factor of a unit stands, and the model tells it again: that answer is spoken, with no second note
    # (the bench's controls got it three times and searched for a «tasa» of a unit).
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    shown = json.dumps({"status": "completed", "verification": "readback", "observed": {
        "version": 1, "expression": "150*0.453592", "mode": "Standard", "value": "68,0388"}})
    mind, server = _mind(tmp_path, [_call("calculator_expression_evaluate", {"expression": "150*0.453592"}),
                                    _say("150 libras son 68,04 kilos."),
                                    _say("150 libras son 68,04 kilos, con el factor fijo de 0,453592."),
                                    _call("web_search", {"query": "tasa libra a kilo"})])
    mind.wire_to_op = {"calculator_expression_evaluate": "calculator.expression.evaluate", "web_search": "web.search"}
    mind.decide(1, "¿Cuántos kilos son 150 libras? Hazlo en la calculadora.")
    step = mind.continue_turn(1, shown)
    assert step["kind"] == "conversation" and "68,04" in step["reply"]
    assert len(server.bodies) == 3 and sum("cuenta como cálculo una cifra" in str(b["messages"]) for b in server.bodies) == 1
