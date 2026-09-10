"""Focus and display state are separate observed predicates."""
import copy

import pytest

from baxy_mind.llm import LlmRuntime, _compose_situation_payload, _payload_fact_defect


def situation(focus, state="normal", name="Atlas"):
    return {"kind":"operation", "operation":"window.resolve", "verified":True,
            "succeeded":True, "polarity":"success", "observed":{"windows":[
                {"title":name, "processName":name, "foreground":focus, "state":state}], "count":1}}


@pytest.mark.parametrize("name", ["Atlas", "Órbita 29", "Is Active"])
@pytest.mark.parametrize("focus", [True, False])
@pytest.mark.parametrize("state", ["normal", "maximized", "minimized"])
@pytest.mark.parametrize("phrase,positive", [
    ("La ventana {name} está activa.", True),
    ("La ventana {name} no está activa.", False),
    ("La ventana {name} está inactiva.", False),
    ("La ventana {name} tiene el foco.", True),
    ("La ventana {name} no tiene el foco.", False),
    ("The {name} window is active.", True),
    ("The {name} window is not active.", False),
    ("The {name} window isn't active.", False),
    ("The {name} window has focus.", True),
    ("The {name} window does not have focus.", False),
    ("The {name} window is in the foreground.", True),
])
def test_focus_is_not_inferred_from_display_state(name, focus, state, phrase, positive):
    original = situation(focus, state, name)
    saved = copy.deepcopy(original)
    defect = _payload_fact_defect(phrase.format(name=name), _compose_situation_payload(original, "en"))
    assert defect == ("" if positive == focus else "reversed_result")
    assert original == saved


@pytest.mark.parametrize("reply,focus", [
    ("No, la ventana Atlas no está activa ni configurada para mantenerse siempre encima.", True),
    ("Sí, la ventana Atlas está activa y está configurada para mantenerse siempre encima.", False),
    ("Yes, the Atlas window is active and configured to stay always on top.", False),
])
def test_unambiguous_wrong_compound_focus_is_rejected(reply, focus):
    payload = _compose_situation_payload(situation(focus), "en")
    assert _payload_fact_defect(reply, payload) == "reversed_result"


@pytest.mark.parametrize("reply,focus", [
    ("Atlas está activa, pero no se mantiene siempre encima.", True),
    ("Atlas no está activa, pero se mantiene siempre encima.", False),
    ("Atlas is active, but it is not always on top.", True),
    ("Atlas is not active, but it stays always on top.", False),
    ("No, Atlas is not active and configured to stay always on top. Atlas is active, but not always on top.", True),
    ("No sé si otra ventana está activa. Atlas tiene el foco.", True),
    ("I cannot tell whether another window is active. Atlas has focus.", True),
])
def test_valid_distinctions_and_scoped_negation_are_preserved(reply, focus):
    assert not _payload_fact_defect(reply, _compose_situation_payload(situation(focus), "en"))


@pytest.mark.parametrize("focus", [None, "unknown", 0, 1])
def test_untyped_focus_does_not_establish_truth(focus):
    assert not _payload_fact_defect("Atlas is active.", _compose_situation_payload(situation(focus), "en"))


def test_other_subject_is_not_assigned_the_only_observed_window():
    payload = _compose_situation_payload(situation(False), "en")
    assert not _payload_fact_defect("Vega is active. Atlas is not active.", payload)


@pytest.mark.parametrize("text", [
    "If Atlas is active, the shortcut goes to it.",
    "Si Atlas está activa, el atajo le llega a ella.",
    "Is Atlas active?", "¿Atlas está activa?",
    "You asked whether Atlas is active.",
    "Preguntaste si Atlas está activa.",
])
def test_conditional_question_or_reported_question_is_not_a_current_assertion(text):
    assert not _payload_fact_defect(text, _compose_situation_payload(situation(False), "en"))


def test_uncertainty_does_not_hide_a_later_assertion():
    text = "I cannot tell whether Vega is active, but Atlas is active."
    assert _payload_fact_defect(text, _compose_situation_payload(situation(False), "en")) == "reversed_result"


def test_two_explicit_subjects_retain_their_own_focus():
    value = situation(True)
    value["observed"]["windows"].append({"title":"Vega", "foreground":False, "state":"normal"})
    value["observed"]["count"] = 2
    payload = _compose_situation_payload(value, "en")
    assert not _payload_fact_defect("Atlas is active. Vega is not active.", payload)
    assert _payload_fact_defect("Atlas is not active. Vega is active.", payload) == "reversed_result"


class Recorder(LlmRuntime):
    def __init__(self, replies):
        self._gguf = "Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
        self.replies = iter(replies)
        self.requests = []

    def _post(self, payload):
        self.requests.append(payload)
        return {"choices":[{"message":{"content":next(self.replies)}, "finish_reason":"stop"}]}


def test_actual_compositor_repairs_focus_contradiction():
    good = "Atlas is not active; its window is in normal state."
    client = Recorder(["Atlas is active and in normal state.", good, good])
    result = client.compose_user_message("Is the Atlas window active?", "status", {"situation":situation(False)})
    assert result == good
    assert len(client.requests) == 2
    import json
    feedback = client.requests[1]["messages"][-1]["content"].split("\nVerified factual correction: ")[1]
    assert json.loads(feedback) == {
        "window_title":"Atlas", "contradiction":{"predicate":"is_active_window", "observed_value":False, "draft_claim":True},
        "rejected_draft":"Atlas is active and in normal state.",
    }
    assert "Verified factual correction" not in client.requests[0]["messages"][-1]["content"]


def test_valid_focus_does_not_need_an_extra_inference():
    good = "Atlas is active; its window is in normal state."
    client = Recorder([good])
    assert client.compose_user_message("Is Atlas active?", "status", {"situation":situation(True)}) == good
    assert len(client.requests) == 1


@pytest.mark.parametrize("focus", [True, False])
@pytest.mark.parametrize("name", ["Vega", "Órbita 42", "Is Active"])
def test_correction_is_derived_from_this_subject_and_value(focus, name):
    from baxy_mind.window_prose_facts import window_fact_feedback
    payload = _compose_situation_payload(situation(focus, name=name), "en")
    wrong = f"{name} is {'not ' if focus else ''}active."
    feedback = window_fact_feedback(wrong, payload)
    assert feedback == {"window_title":name, "contradiction":{"predicate":"is_active_window", "observed_value":focus, "draft_claim":not focus}, "rejected_draft":wrong}
    assert window_fact_feedback(f"{name} is {'not ' if not focus else ''}active.", payload) is None


def test_third_attempt_receives_its_own_rejected_claim():
    good = "Atlas is not active."
    first = "Atlas is active."
    second = "The Atlas window has focus."
    client = Recorder([first, second, good])
    assert client.compose_user_message("Is Atlas active?", "status", {"situation":situation(False)}) == good
    assert len(client.requests) == 3
    assert second in client.requests[2]["messages"][-1]["content"]
    assert first not in client.requests[2]["messages"][-1]["content"]
