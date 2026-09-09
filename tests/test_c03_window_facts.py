"""Window facts reach the actual publication/retry boundary, not only shape checks."""
import pytest

from baxy_mind.llm import LlmRuntime, _compose_situation_payload, _payload_fact_defect


def situation(name="Orbit 23", installed=True, count=0):
    return {"kind": "operation", "operation": "window.application.status",
            "polarity": "success", "verified": True, "succeeded": True,
            "observed": {"requestedName": name, "displayName": name if installed else None,
                         "installed": installed, "hasVisibleWindow": count > 0,
                         "visibleWindowCount": count}}


class Recorder(LlmRuntime):
    def __init__(self, replies):
        self._gguf = "Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
        self.replies = iter(replies)
        self.payloads = []

    def _post(self, payload):
        self.payloads.append(payload)
        return {"choices": [{"message": {"content": next(self.replies)}, "finish_reason": "stop"}]}


@pytest.mark.parametrize("name", ["Spotify", "Orbit 23", "Running"])
@pytest.mark.parametrize("reply, valid", [
    ("{name} is installed and running, but no window is currently visible.", False),
    ("{name} is installed but has no visible window.", True),
    ("{name} has two visible windows.", False),
    ("{name} is not installed.", False),
    ("{name} is not running.", False),
    ("{name} is installed with no visible window; background processes were not checked.", True),
    ("{name} está instalado, pero no tiene ventanas visibles.", True),
    ("{name} tiene tres ventanas visibles.", False),
    ("{name} no está instalado.", False),
    ("{name} está ejecutándose en segundo plano.", False),
    ("{name} está instalado y no tiene ventanas visibles; no comprobé sus procesos.", True),
    ("I cannot tell whether {name} is running from this observation.", True),
    ("No sé si {name} sigue ejecutándose; sólo comprobé sus ventanas visibles.", True),
    ("I cannot tell whether {name} is running; it is running in the background.", False),
    ("No sé si {name} está ejecutándose, pero está ejecutándose en segundo plano.", False),
    ("{name} is installed and it's running in the background.", False),
    ("{name} is installed and it’s not running.", False),
    ("{name} is installed; I can't confirm whether it's running.", True),
    ("{name} is installed; I can’t tell whether it’s running.", True),
    ("The process is active.", False),
    ("El proceso está detenido.", False),
])
def test_typed_installation_visibility_and_process_scope(name, reply, valid):
    payload = _compose_situation_payload(situation(name), "en", "Is it open?")
    assert (not _payload_fact_defect(reply.format(name=name), payload)) is valid


@pytest.mark.parametrize("count, reply, valid", [
    (3, "Orbit 23 has three visible windows.", True),
    (3, "Orbit 23 has 23 visible windows.", False),
    (3, "Orbit 23 has at least two visible windows.", True),
    (3, "Orbit 23 has at most two visible windows.", False),
    (3, "Orbit 23 has more than two visible windows.", True),
    (3, "Orbit 23 has fewer than three visible windows.", False),
    (3, "Órbita 23 tiene al menos dos ventanas visibles.", True),
    (3, "Órbita 23 tiene como máximo dos ventanas visibles.", False),
    (3, "Órbita 23 tiene más de dos ventanas visibles.", True),
    (3, "Órbita 23 tiene menos de tres ventanas visibles.", False),
    (3, "Orbit 23 has no visible windows.", False),
    (3, "Órbita 23 no tiene ventanas visibles.", False),
    (3, "Orbit 23 has visible windows.", True),
    (3, "Órbita 23 tiene ventanas visibles.", True),
    (0, "Orbit 23 has visible windows.", False),
    (0, "Órbita 23 tiene ventanas visibles.", False),
    (125, "Orbit 23 has 125 visible windows.", True),
    (125, "Orbit 23 has 126 visible windows.", False),
    (2, "Two windows of Orbit 23 are open.", True),
    (2, "Three windows of Orbit 23 are open.", False),
])
def test_cardinality_is_qualified_by_windows_not_digits_in_names(count, reply, valid):
    payload = _compose_situation_payload(situation(count=count), "en", "How many windows are open?")
    assert (not _payload_fact_defect(reply, payload)) is valid


@pytest.mark.parametrize("installed, reply, valid", [
    (False, "Brújula no está instalada.", True),
    (False, "Brújula está instalada.", False),
    (False, "Brújula is not installed.", True),
    (False, "Brújula is installed.", False),
    (True, "Brújula isn't installed.", False),
    (False, "Brújula isn't installed.", True),
    (False, "Brújula hasn't been installed.", True),
    (True, "Brújula hasn't been installed.", False),
    (False, "Brújula no se encuentra instalada.", True),
    (True, "Brújula no se encuentra instalada.", False),
])
def test_installation_polarity_is_observed_not_assumed(installed, reply, valid):
    assert (not _payload_fact_defect(reply, _compose_situation_payload(situation("Brújula", installed), "en"))) is valid


@pytest.mark.parametrize("bad", [
    "Orbit 23 is installed and running, but no window is currently visible.",
    "Orbit 23 is not running.",
    "Orbit 23 has two visible windows.",
    "Orbit 23 is not installed.",
])
def test_actual_compositor_retries_bad_fact_without_publishing_it(bad):
    good = "Orbit 23 is installed but has no visible window."
    client = Recorder([bad, good, good])
    assert client.compose_user_message("Is Orbit 23 open?", "status", {"situation": situation()}) == good
    assert len(client.payloads) == 2


@pytest.mark.parametrize("reply", [
    "Orbit 23 is installed but has no visible window.",
    "Orbit 23 has no visible windows; I cannot tell whether it is running.",
])
def test_valid_draft_does_not_spend_another_inference(reply):
    client = Recorder([reply])
    assert client.compose_user_message("Is Orbit 23 open?", "status", {"situation": situation()}) == reply
    assert len(client.payloads) == 1


def test_other_operation_keeps_its_own_process_evidence_contract():
    payload = {"operation": "process.list", "seen": {"installed": True, "visibleWindowCount": 0}}
    assert not _payload_fact_defect("Orbit 23 is running.", payload)


@pytest.mark.parametrize("name", ["Is Running", "Not Installed"])
def test_state_words_inside_observed_names_are_not_assertions(name):
    assert not _payload_fact_defect(
        f"{name} is installed with no visible windows.",
        _compose_situation_payload(situation(name), "en"),
    )


def test_process_uncertainty_does_not_hide_a_separate_failure_claim():
    from baxy_mind.llm import compose_visible_defect

    text = "Orbit 23 has no visible windows; I cannot tell whether it is running, but the window check failed."
    assert compose_visible_defect(text, "status", "Is Orbit 23 open?", {"situation": situation()}) == "asserted_failure"


def test_unknown_process_state_alone_does_not_answer_the_window_question():
    client = Recorder(["I cannot tell whether Orbit 23 is running from this observation."] * 3)
    assert client.compose_user_message("Is Orbit 23 open?", "status", {"situation": situation()}) == ""
    assert len(client.payloads) == 3
