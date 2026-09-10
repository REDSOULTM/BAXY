"""Observed names are data; vocabulary exemptions must not escape their spans."""
import copy
import json

import pytest

from test_c03_window_state_facts import Recorder, situation
from baxy_mind.observed_response_literals import without_observed_window_names


NAMES = ["Qwen", "Qwen3 - Research", "Router notes", "Core designs", "Tool atlas", "router_notes.txt - Editor"]
ANSWERS = [
    ("Which window is active?", 'The window "{name}" is active.'),
    ("¿Qué ventana tiene el foco?", 'La ventana "{name}" tiene foco.'),
    ("Baxy, ¿qué window tiene focus?", 'La ventana "{name}" tiene foco.'),
]


def facts(name):
    return {"situation": situation(True, name=name),
            "forbiddenResponseTerms": ["qwen", "router", "core", "tool"]}


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("question,template", ANSWERS)
def test_exact_observed_name_reaches_publication_unchanged_in_one_call(name, question, template):
    answer = template.format(name=name)
    client = Recorder([answer])
    assert client.compose_user_message(question, "status", facts(name)) == answer
    assert len(client.requests) == 1


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("extra", [" The router chose it.", " The core confirmed it.", " window.active."])
def test_observed_name_does_not_allow_unrelated_jargon_or_codes(name, extra):
    good = f'The window "{name}" is active.'
    client = Recorder([good + extra, good])
    assert client.compose_user_message("Which window is active?", "status", facts(name)) == good
    assert len(client.requests) == 2


@pytest.mark.parametrize("name", NAMES)
def test_literal_exemption_does_not_disable_observed_focus_contradiction(name):
    good = f'The window "{name}" is active.'
    client = Recorder([f'The window "{name}" is not active.', good])
    assert client.compose_user_message("Which window is active?", "status", facts(name)) == good
    assert len(client.requests) == 2


@pytest.mark.parametrize("change", ["unverified", "unsucceeded", "failure", "other_operation", "history", "different_name"])
def test_untrusted_or_different_name_does_not_exempt_a_forbidden_term(change):
    value = facts("Router notes")
    if change == "unverified":
        value["situation"]["verified"] = False
    elif change == "unsucceeded":
        value["situation"]["succeeded"] = False
    elif change == "failure":
        value["situation"]["polarity"] = "failure"
    elif change == "other_operation":
        value["situation"]["operation"] = "system.status"
    elif change == "history":
        value["context"] = 'The window "Router notes" is active.'
        value["situation"] = {"kind": "conversation", "polarity": "success"}
    else:
        value["situation"]["observed"]["windows"][0].update(title="Router plans", processName="Editor")
    # Repeated failure is intentionally observable, rather than publishing a fallback.
    client = Recorder(['The window "Router notes" is active.'] * 3)
    assert client.compose_user_message("Which window is active?", "status", value) == ""
    assert len(client.requests) == 3


def test_successful_mission_step_keeps_its_literal_provenance():
    value = facts("Router notes")
    step = copy.deepcopy(value["situation"])
    value["situation"] = {"kind": "status", "cause": "mission_completed", "polarity": "success",
                          "stepCount": 1, "steps": [json.dumps(step)], "observed": step["observed"]}
    good = 'The window "Router notes" is active.'
    client = Recorder([good])
    assert client.compose_user_message("Which window is active?", "status", value) == good
    assert len(client.requests) == 1


@pytest.mark.parametrize("name", NAMES)
def test_unquoted_identity_preserves_the_same_names_and_polarity(name):
    good = f"{name} is active."
    client = Recorder([good])
    assert client.compose_user_message("Which window is active?", "status", facts(name)) == good
    assert len(client.requests) == 1


@pytest.mark.parametrize("bad", [
    'The window "Router notesX" is active.',
    'The window "XRouter notes" is active.',
    'My model is Router notes.',
])
def test_complete_token_boundaries_and_answer_meaning_still_apply(bad):
    good = 'The window "Router notes" is active.'
    client = Recorder([bad, good])
    assert client.compose_user_message("Which window is active?", "status", facts("Router notes")) == good
    assert len(client.requests) == 2


def test_lowercase_prose_outside_the_observed_name_still_requires_recovery():
    good = 'The window "Router notes" is active.'
    client = Recorder(['the window "Router notes" is active.', good])
    assert client.compose_user_message("Which window is active?", "status", facts("Router notes")) == good
    assert len(client.requests) == 2


@pytest.mark.parametrize("name,compound", [
    ("Atlas", "Atlas.route"),
    ("Core", "Core.schema"),
    ("Core", "internal.Core"),
    ("Router notes", "Router notes-extra"),
    ("Router notes", "extra-Router notes"),
    ("Core", "Core_schema"),
    ("Core", "internal_Core"),
])
def test_observed_name_cannot_hide_a_longer_identifier(name, compound):
    good = f'The window "{name}" is active.'
    assert without_observed_window_names(
        f"{good} {compound}.", facts(name)["situation"]
    ) == f'The window "\ufffc" is active. {compound}.'
    # The existing code-shape veto recognizes lowercase dotted operations;
    # preserving an uppercase token must not silently expand that old policy.
    client = Recorder([f"{good} {compound.lower()}.", good])
    assert client.compose_user_message("Which window is active?", "status", facts(name)) == good
    assert len(client.requests) == 2


@pytest.mark.parametrize("punctuation", [".", ",", ":", ";", "!", "?", ")", '"'])
def test_complete_name_next_to_sentence_punctuation_remains_opaque(punctuation):
    assert without_observed_window_names(
        f"Router notes{punctuation}", facts("Router notes")["situation"]
    ) == f"\ufffc{punctuation}"
