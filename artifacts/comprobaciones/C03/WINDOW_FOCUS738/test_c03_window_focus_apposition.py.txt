"""Verified appositions and predicate order preserve the same focus fact."""
import copy

import pytest

from baxy_mind.llm import _compose_situation_payload, _payload_fact_defect
from test_c03_window_state_facts import Recorder, situation


NAMES = [("Cuaderno", "NoteShell"), ("Órbita 29", "EditorX"), ("Panel azul", "Is Active")]


def observed(focus, label, process, state="normal"):
    value = situation(focus, state, f"Sin título: {label}")
    value["observed"]["windows"][0]["processName"] = process
    return value


@pytest.mark.parametrize("label,process", NAMES)
@pytest.mark.parametrize("focus", [True, False])
@pytest.mark.parametrize("state", ["normal", "maximized", "minimized"])
@pytest.mark.parametrize("phrase", [
    "Activa está la ventana de {label} ({process}).",
    "Está activa la ventana de {label} ({process}).",
    "En primer plano está la ventana de {label} ({process}).",
    "Está en primer plano la ventana de {label} ({process}).",
    "La ventana de {label} ({process}) está activa.",
    "The window of {label} ({process}) is active.",
    "In the foreground is the window of {label} ({process}).",
    "The {label} ({process}) window is in the foreground.",
])
def test_same_verified_subject_and_focus_across_word_orders(label, process, focus, state, phrase):
    facts = observed(focus, label, process, state)
    saved = copy.deepcopy(facts)
    answer = phrase.format(label=label, process=process)
    defect = _payload_fact_defect(answer, _compose_situation_payload(facts, "en"), "Which window is active?")
    assert defect == ("" if focus else "reversed_result")
    assert facts == saved


@pytest.mark.parametrize("label,process", NAMES)
@pytest.mark.parametrize("focus", [True, False])
@pytest.mark.parametrize("phrase", [
    "Inactiva está la ventana de {label} ({process}).",
    "Activa no está la ventana de {label} ({process}).",
    "En primer plano no está la ventana de {label} ({process}).",
    "In the foreground isn't the window of {label} ({process}).",
    "The window of {label} ({process}) is not active.",
    "La ventana de {label} ({process}) no tiene el foco.",
])
def test_apposition_preserves_negative_polarity(label, process, focus, phrase):
    payload = _compose_situation_payload(observed(focus, label, process), "en")
    assert _payload_fact_defect(phrase.format(label=label, process=process), payload,
                                f"Is {process} active?") == ("reversed_result" if focus else "")


@pytest.mark.parametrize("label,process", NAMES)
@pytest.mark.parametrize("phrase", [
    "Activa está la ventana de Otra aplicación ({process}).",
    "Está activa la ventana de {label} (OtherProcess).",
    "La ventana de Otra aplicación ({process}) está activa.",
    "The window of Other application ({process}) is active.",
    "If the window of {label} ({process}) is active, it receives input.",
    "Si activa está la ventana de {label} ({process}), recibe la entrada.",
    "¿Activa está la ventana de {label} ({process})?",
    "No puedo confirmar si activa está la ventana de {label} ({process}).",
])
def test_unknown_alias_or_nonassertion_cannot_answer_identity(label, process, phrase):
    payload = _compose_situation_payload(observed(True, label, process), "en")
    assert _payload_fact_defect(phrase.format(label=label, process=process), payload,
                                "Which window is active?") == "missing_fact"


@pytest.mark.parametrize("label,process", NAMES)
def test_correct_apposition_publishes_without_another_inference(label, process):
    facts = observed(True, label, process)
    answer = f'Activa está la ventana de {label} ({process}), su título es "Sin título: {label}".'
    client = Recorder([answer])
    assert client.compose_user_message("qué ventana está activa", "status", {"situation": facts}) == answer
    assert len(client.requests) == 1


@pytest.mark.parametrize("name", ["Atlas", "Órbita 29", "Informe.txt - Editor"])
@pytest.mark.parametrize("focus", [True, False])
@pytest.mark.parametrize("phrase", ["Activa está {name}.", "In the foreground is {name}."])
def test_inverted_predicate_also_accepts_a_plain_observed_identity(name, focus, phrase):
    payload = _compose_situation_payload(situation(focus, name=name), "en")
    answer = phrase.format(name=f'"{name}"')
    assert _payload_fact_defect(answer, payload, "Which window is active?") == ("" if focus else "reversed_result")


@pytest.mark.parametrize("process,question", [
    ("Is Active", "Which window is active?"),
    ("Está activa", "¿Qué ventana está activa?"),
    ("Has Focus", "Which window has focus?"),
    ("Tiene foco", "¿Qué ventana tiene foco?"),
])
@pytest.mark.parametrize("answer", ["Other window", "The window is maximized.", "No lo sé.", "Is it active?"])
def test_process_name_cannot_mask_the_question_predicate(process, question, answer):
    payload = _compose_situation_payload(observed(True, "Panel azul", process), "en")
    assert _payload_fact_defect(answer, payload, question) == "missing_fact"


@pytest.mark.parametrize("label,process", NAMES)
@pytest.mark.parametrize("focus", [True, False])
@pytest.mark.parametrize("phrase", [
    'Activa está la ventana de "{title}" ({process}).',
    'La ventana de "{title}" ({process}) está activa.',
    'The window of "{title}" ({process}) is active.',
])
def test_quoted_observed_title_remains_opaque_inside_apposition(label, process, focus, phrase):
    payload = _compose_situation_payload(observed(focus, label, process), "en")
    answer = phrase.format(title=f"Sin título: {label}", process=process)
    assert _payload_fact_defect(answer, payload, "Which window is active?") == ("" if focus else "reversed_result")
