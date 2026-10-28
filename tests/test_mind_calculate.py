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
