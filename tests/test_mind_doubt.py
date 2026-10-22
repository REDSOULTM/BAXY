"""The decision's doubt, read from its own token logprobs (src/baxy_mind/doubt.py)."""
import math

from baxy_mind.doubt import read


def token(text, p, alternatives=()):
    return {"token": text, "logprob": math.log(p),
            "top_logprobs": [{"token": t, "logprob": math.log(q)} for t, q in ((text, p), *alternatives)]}


def reply(tokens):
    return {"choices": [{"message": {}, "logprobs": {"content": tokens}}]}


def test_a_call_is_as_sure_as_opening_it_times_its_name():
    # «ahora ciérralo» on the PC, 2026-10-21: system .75, app .24.
    tokens = [token("<tool_call>", 0.9, [("Ent", 0.05)]), token("\n", 1.0), token("<", 1.0), token("function", 1.0),
              token("=", 1.0), token("system", 0.75, [("app", 0.24)]), token("_power", 1.0), token(">", 1.0)]
    doubt = read(reply(tokens))
    assert doubt["p_call"] == 0.9
    assert doubt["p_name"] == 0.75
    assert doubt["confidence"] == round(0.9 * 0.75, 4)
    # Review 2026-10-22: the token chosen is not its own rival.
    assert doubt["rivals"] == [("app", 0.24)]


def test_a_rival_token_that_carries_the_equals_sign_still_counts_as_the_name():
    tokens = [token("<tool_call>", 1.0), token("\n", 1.0), token("<", 1.0), token("function", 1.0),
              token("=schedule", 0.6, [("=schedules", 0.4)]), token("_alarms", 1.0), token(">", 1.0)]
    doubt = read(reply(tokens))
    assert doubt["p_name"] == 0.6
    assert doubt["rivals"] == [("=schedules", 0.4)]


def test_words_are_as_sure_as_not_opening_a_call():
    tokens = [token("La", 0.6, [("<tool_call>", 0.17)]), token(" hora", 0.98)]
    assert read(reply(tokens)) == {"confidence": 0.83, "p_call": 0.17}


def test_a_reply_without_logprobs_has_no_doubt():
    assert read({"choices": [{"message": {"content": "hola"}}]}) is None
    assert read(None) is None
    assert read(reply([])) is None


def _call_reply(tokens):
    return {"choices": [{"message": {"tool_calls": [{"function": {"name": "system_power"}}]},
                         "logprobs": {"content": tokens}}]}


def test_words_before_a_call_are_not_read_as_the_decision():
    # Review 2026-10-22: «Claro,» before <tool_call> was read as words, 1 − p(call) at the first token.
    tokens = [token("Claro", 0.7, [("<tool_call>", 0.3)]), token(",", 1.0), token("<tool_call>", 0.9),
              token("\n", 1.0), token("<", 1.0), token("function", 1.0), token("=", 1.0),
              token("system", 0.75, [("app", 0.24)]), token("_power", 1.0), token(">", 1.0)]
    doubt = read(_call_reply(tokens))
    assert doubt["p_call"] == 0.9 and doubt["p_name"] == 0.75
    assert doubt["confidence"] == round(0.9 * 0.75, 4)


def test_a_call_whose_opening_is_not_in_the_logprobs_has_no_doubt():
    assert read(_call_reply([token("Claro", 0.7), token(",", 1.0)])) is None


def test_each_argument_value_has_the_probability_of_its_least_sure_token():
    # Al máximo 4.5: the value's own tokens, never the parameter's name or the tags around it.
    tokens = [token("<tool_call>", 1.0), token("\n", 1.0), token("<", 1.0), token("function", 1.0), token("=", 1.0),
              token("web", 1.0), token("_search", 1.0), token(">", 1.0), token("\n", 1.0),
              token("<parameter=query>", 0.5), token("\n", 1.0), token("receta", 0.2), token(" de lentejas", 0.9),
              token("\n", 0.7), token("</parameter>", 1.0), token("\n", 1.0), token("<parameter=limit>", 1.0),
              token("\n", 1.0), token("5", 0.6), token("\n", 1.0), token("</parameter>", 1.0)]
    assert read(_call_reply(tokens))["values"] == {"query": 0.2, "limit": 0.6}
