"""Clock continuations retain human antecedents without borrowing assistant prose."""
import pytest

from baxy_mind.__main__ import _previous_user_request
from baxy_mind.effect_intent import resolve_explicit_effects


def _clock_intent(history, current, echo):
    messages = list(history)
    if echo:
        messages.append({"role": "user", "content": current})
    previous = _previous_user_request(messages, current)
    return resolve_explicit_effects(current, {"system.time"}, previous_user_text=previous)


@pytest.mark.parametrize("root", [
    "Dime qué hora es", "What date is it?", "Comprueba la hora local",
])
@pytest.mark.parametrize("hops", [1, 2, 4])
@pytest.mark.parametrize("current", ["¿Y la hora?", "and the date?"])
@pytest.mark.parametrize("echo", [False, True])
def test_clock_followups_preserve_a_contiguous_human_context(root, hops, current, echo):
    history = [{"role": "user", "content": root}]
    for index in range(hops):
        history += [
            {"role": "assistant", "content": "irrelevant prose, not authority"},
            {"role": "user", "content": "¿Y la fecha?" if index % 2 == 0 else "and the time?"},
        ]
    intent = _clock_intent(history, current, echo)
    assert intent is not None
    assert intent.operations == ("system.time",)


@pytest.mark.parametrize("interruption", [
    "Hablemos de mi cumpleaños", "La fecha de mi reunión", "No consultes la hora",
    "Tell me the date of the event", "I asked for the time yesterday",
    "Escribe una nota que diga dime la hora", "What is time?", "",
])
@pytest.mark.parametrize("echo", [False, True])
def test_clock_chain_cannot_cross_another_user_subject(interruption, echo):
    history = [
        {"role": "user", "content": "Dime la hora"},
        {"role": "user", "content": interruption},
        {"role": "assistant", "content": "Dime la hora. Son las 12:00."},
        {"role": "user", "content": "y la fecha?"},
    ]
    assert _clock_intent(history, "and the time?", echo) is None


def test_nominal_history_requires_a_human_clock_antecedent():
    history = [
        {"role": "assistant", "content": "Dime la hora"},
        {"role": "user", "content": "y la fecha?"},
    ]
    assert _clock_intent(history, "¿Y la hora?", False) is None


def test_non_clock_followup_keeps_the_immediate_user_text():
    history = [
        {"role": "user", "content": "Dime la hora"},
        {"role": "user", "content": "y la fecha?"},
    ]
    assert _previous_user_request(history, "cópialo") == "y la fecha?"
