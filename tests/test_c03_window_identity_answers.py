"""A window identity and a Boolean focus answer have different completeness rules."""
import pytest

from baxy_mind.llm import _compose_situation_payload, _payload_fact_defect
from test_c03_window_state_facts import Recorder, situation


@pytest.mark.parametrize("name", ["Atlas", "Órbita 29", "Is Active", "Informe.txt - Editor"])
@pytest.mark.parametrize("question", [
    "Ahora mismo, ¿qué ventana tiene el foco?", "Which window is active?",
    "¿Y ahora cuál está activa?", "Which one has focus now?",
])
def test_identity_question_accepts_the_observed_title_without_boolean_repetition(name, question):
    payload = _compose_situation_payload(situation(True, name=name), "es")
    assert not _payload_fact_defect(name, payload, question)


@pytest.mark.parametrize("name", ["Atlas", "Órbita 29", "Is Active", "Informe.txt - Editor"])
@pytest.mark.parametrize("template", [
    'La ventana con enfoque es "{name}".',
    'La ventana con foco es "{name}".',
    'Ahora está activa la ventana de "{name}".',
    'Actualmente tiene focus "{name}".',
])
@pytest.mark.parametrize("focus", [True, False])
def test_identity_word_order_conserves_the_same_observed_boolean(name, template, focus):
    payload = _compose_situation_payload(situation(focus, name=name), "es")
    assert _payload_fact_defect(template.format(name=name), payload, "Which window is active?") == ("" if focus else "reversed_result")


@pytest.mark.parametrize("answer,name,identifies", [
    ("Atlas", "Atlas", True), ('"Atlas"', "Atlas", True),
    ("Is Active", "Is Active", True), ('"Is Active"', "Is Active", True),
    ("It is active.", "Atlas", False), ("Está activa.", "Atlas", False),
])
def test_identity_and_boolean_questions_cannot_use_each_others_incomplete_answer(answer, name, identifies):
    payload = _compose_situation_payload(situation(True, name=name), "en")
    question = f"Is {name} active and always on top?" if identifies else "Which window is active?"
    assert _payload_fact_defect(answer, payload, question) == "missing_fact"


@pytest.mark.parametrize("question", [
    "Which window is active and configured to stay always on top?",
    "¿Qué ventana está activa y se mantiene siempre encima?",
])
def test_identity_shorthand_does_not_hide_an_additional_requested_predicate(question):
    assert _payload_fact_defect("Atlas", _compose_situation_payload(situation(True), "en"), question) == "missing_fact"


@pytest.mark.parametrize("answer", [
    "Vega", 'La ventana con foco es "Vega".', "Ahora está activa la ventana de Vega.",
    "Vega is active. Atlas is maximized.", "I don't know which window is active. Atlas is maximized.",
    "If Atlas is active, it receives input.", "Is Atlas active?",
])
def test_unidentified_uncertain_or_different_window_does_not_complete_identity(answer):
    assert _payload_fact_defect(answer, _compose_situation_payload(situation(True), "en"), "Which window is active?")


@pytest.mark.parametrize("answer", [
    "Ahora no está activa la ventana de Atlas.", "Actualmente no tiene foco Atlas.",
    "Ahora está inactiva Atlas.",
])
def test_inverted_negative_assertion_cannot_be_accepted_as_identity(answer):
    assert _payload_fact_defect(answer, _compose_situation_payload(situation(True), "es"), "Which window is active?") == "reversed_result"


@pytest.mark.parametrize("answer", ["Está activa Vega.", "Ahora tiene foco Vega."])
def test_inverted_other_subject_does_not_inherit_the_observed_windows_state(answer):
    assert not _payload_fact_defect(answer, _compose_situation_payload(situation(False), "es"))


@pytest.mark.parametrize("correct_title", [True, False])
def test_process_name_does_not_hide_a_different_reported_window_title(correct_title):
    facts = situation(True, name="Atlas - Notes")
    facts["observed"]["windows"][0]["processName"] = "Notes"
    title = "Atlas - Notes" if correct_title else "Vega - Notes"
    answer = f'Ahora está activa la ventana de Notes titulada "{title}".'
    defect = _payload_fact_defect(answer, _compose_situation_payload(facts, "es"), "¿Y ahora cuál está activa?")
    assert not defect if correct_title else defect


def test_renamed_real_product_shapes_publish_in_one_call():
    facts = situation(True, name="Atlas - Notes")
    facts["observed"]["windows"][0]["processName"] = "Notes"
    for question, answer in [
        ("Ahora mismo, ¿qué ventana tiene el foco?", 'La ventana con enfoque es "Atlas - Notes".'),
        ("Baxy, ¿qué window tiene focus ahora?", 'Actualmente tiene focus la ventana de Notes titulada "Atlas - Notes".'),
        ("¿Y ahora cuál está activa?", 'Ahora está activa la ventana de Notes titulada "Atlas - Notes".'),
    ]:
        client = Recorder([answer])
        assert client.compose_user_message(question, "status", {"situation": facts}) == answer
        assert len(client.requests) == 1
