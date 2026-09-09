"""Identifying a foreground subject does not ask a second Boolean question."""
import pytest

from baxy_mind.llm import _compose_situation_payload, _payload_fact_defect
from test_c03_window_state_facts import Recorder, situation


@pytest.mark.parametrize("name", ["Atlas", "Órbita 29", "Is Active"])
@pytest.mark.parametrize("question", [
    "Dime el nombre de la ventana que está en primer plano.",
    "What is the name of the window that is in the foreground?",
    "Tell me the title of the window which has focus.",
    "¿Cómo se llama la ventana que tiene el foco?",
])
def test_title_of_foreground_subject_accepts_just_the_observed_name(name, question):
    assert not _payload_fact_defect(name, _compose_situation_payload(situation(True, name=name), "en"), question)


@pytest.mark.parametrize("name", ["Atlas", "Órbita 29"])
@pytest.mark.parametrize("question", [
    "¿La ventana que está maximizada tiene el foco?",
    "Is the window that is maximized active?",
    "Dime el nombre y si la ventana está activa.",
    "Tell me the title and whether the window is active.",
])
def test_separate_focus_question_still_requires_its_answer(name, question):
    assert _payload_fact_defect(name, _compose_situation_payload(situation(True, name=name), "en"), question) == "missing_fact"


@pytest.mark.parametrize("question", [
    "Dime el nombre de la ventana que está en primer plano.",
    "What is the name of the window that is in the foreground?",
])
def test_title_request_does_not_disable_contradiction_checks(question):
    assert _payload_fact_defect("Atlas is not active.", _compose_situation_payload(situation(True), "en"), question) == "reversed_result"


def test_product_title_request_publishes_observed_name_without_retry():
    client = Recorder(["Atlas"])
    assert client.compose_user_message(
        "Dime el nombre de la ventana que está en primer plano.", "status", {"situation": situation(True)},
    ) == "Atlas"
    assert len(client.requests) == 1
