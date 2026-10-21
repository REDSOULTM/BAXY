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
    assert doubt["rivals"][:2] == [("system", 0.75), ("app", 0.24)]


def test_a_rival_token_that_carries_the_equals_sign_still_counts_as_the_name():
    tokens = [token("<tool_call>", 1.0), token("\n", 1.0), token("<", 1.0), token("function", 1.0),
              token("=schedule", 0.6, [("=schedules", 0.4)]), token("_alarms", 1.0), token(">", 1.0)]
    doubt = read(reply(tokens))
    assert doubt["p_name"] == 0.6
    assert doubt["rivals"][1] == ("=schedules", 0.4)


def test_words_are_as_sure_as_not_opening_a_call():
    tokens = [token("La", 0.6, [("<tool_call>", 0.17)]), token(" hora", 0.98)]
    assert read(reply(tokens)) == {"confidence": 0.83, "p_call": 0.17}


def test_a_reply_without_logprobs_has_no_doubt():
    assert read({"choices": [{"message": {"content": "hola"}}]}) is None
    assert read(None) is None
    assert read(reply([])) is None
