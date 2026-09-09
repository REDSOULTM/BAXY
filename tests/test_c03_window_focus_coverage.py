"""Required focus is distinguished from an incidental active-window identifier."""
import pytest

from baxy_mind.llm import _compose_situation_payload, _payload_fact_defect
from test_c03_window_state_facts import Recorder, situation


@pytest.mark.parametrize("name", ["Atlas", "Brújula 7", "Nimbus 41", "Is Active"])
@pytest.mark.parametrize("focus", [True, False])
@pytest.mark.parametrize("question", [
    "Is the {name} window active and configured to stay always on top?",
    "¿La ventana {name} está activa y se mantiene siempre encima?",
    "Is {name} active?", "¿Está activa {name}?",
    "Does {name} have focus?", "¿Tiene {name} el foco?",
])
def test_requested_focus_cannot_disappear(name, focus, question):
    payload = _compose_situation_payload(situation(focus, name=name), "en")
    assert _payload_fact_defect("The window is in normal state.", payload, question.format(name=name)) == "missing_fact"


@pytest.mark.parametrize("question", [
    "Is the active window maximized?", "¿Está maximizada la ventana activa?",
    "Is Atlas configured to stay always on top?", "¿Atlas se mantiene siempre encima?",
    "What is the title of the active window?", "¿Cuál es el título de la ventana activa?",
    "Is Is Active maximized?", "¿Está maximizada Is Active?",
])
def test_incidental_focus_does_not_add_a_question(question):
    payload = _compose_situation_payload(situation(True, name="Is Active" if "Is Active" in question else "Atlas"), "en")
    assert not _payload_fact_defect("The window is in normal state.", payload, question)


@pytest.mark.parametrize("answer", [
    'La ventana activa es "Atlas".', 'The active window is "Atlas".',
    'La ventana en primer plano es Atlas.', 'Atlas has focus.',
    'La ventana Atlas está activa.', 'Está activa.',
])
def test_explicit_focus_or_identity_answers_remain_valid(answer):
    payload = _compose_situation_payload(situation(True), "en")
    assert not _payload_fact_defect(answer, payload, "Which window is active?")


def test_ambiguous_conjunction_does_not_establish_explicit_focus_answer():
    payload = _compose_situation_payload(situation(True), "en")
    reply = "No, the Atlas window is not active and configured to stay always on top."
    assert _payload_fact_defect(reply, payload, "Is Atlas active and always on top?") == "missing_fact"


def test_compositor_missing_feedback_does_not_invent_a_rejected_boolean_claim():
    import json
    first = "Atlas is not configured to stay always on top."
    good = "Atlas is active, but not configured to stay always on top."
    client = Recorder([first, good, good])
    facts = situation(True)
    facts["observed"]["windows"][0]["alwaysOnTop"] = False
    assert client.compose_user_message("Is Atlas active and always on top?", "status", {"situation":facts}) == good
    assert len(client.requests) == 2
    content = client.requests[1]["messages"][-1]["content"]
    feedback = json.loads(content.split("\nVerified factual correction: ")[1])
    assert feedback == {"window_title":"Atlas", "missing_answer":{"predicate":"is_active_window", "observed_value":True}, "rejected_draft":first}
