"""The mind's own tool «calculate» (feria 2026-10-27): sums the 4B model did from memory went wrong (12 for two plus
two once the recognizer misheard a digit) and an 18-digit square root went to the Calculator, which takes none. The
model writes the expression it understood; arithmetic.evaluate computes it and the result is the data it answers from."""
import json
import math
from pathlib import Path

from baxy_mind.mind import CALCULATE, SYSTEM

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
