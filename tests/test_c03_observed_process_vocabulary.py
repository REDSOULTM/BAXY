"""A measured process name may contain vocabulary reserved for internals."""
import copy
import json

import pytest

from baxy_mind.observed_response_literals import without_observed_names
from test_c03_window_state_facts import Recorder


def facts(name="baxy-core"):
    return {"situation": {
        "kind": "operation", "operation": "system.process.list", "polarity": "success",
        "verified": True, "succeeded": True, "observed": {
            "sort": "cpu", "observedProcessCount": 20, "returnedProcessCount": 1,
            "observationScope": "accessible_processes", "processes": [{
                "processId": 731, "name": name, "cpuUsagePercent": 4.5,
                "sampleDurationSeconds": 0.2, "workingSetBytes": 125_000_000,
            }],
        },
    }, "forbiddenResponseTerms": ["core", "router", "qwen"]}


@pytest.mark.parametrize("name", ["baxy-core", "gpu_router", "Qwen Worker"])
@pytest.mark.parametrize("question,reply", [
    ("¿Qué proceso usa más CPU?", "El proceso {name} usa el 4,5 % de CPU."),
    ("Which process uses the most CPU?", "The process {name} uses 4.5% CPU."),
    ("Mostrame el top process por CPU.", "El proceso {name} usa el 4,5 % de CPU."),
])
def test_verified_process_name_is_published_unchanged_in_one_call(name, question, reply):
    answer = reply.format(name=name)
    client = Recorder([answer])
    assert client.compose_user_message(question, "status", facts(name)) == answer
    assert len(client.requests) == 1


@pytest.mark.parametrize("suffix", [
    " The core chose it.", " The router confirmed it.", " system.process.list.",
    " baxy-core.worker.", " internal.baxy-core.", " baxy-core_extra.",
])
def test_process_name_does_not_exempt_unobserved_words_or_longer_identifiers(suffix):
    good = "The process baxy-core uses 4.5% CPU."
    client = Recorder([good + suffix, good])
    assert client.compose_user_message("Which process uses the most CPU?", "status", facts()) == good
    assert len(client.requests) == 2


@pytest.mark.parametrize("change", [
    "unverified", "unsucceeded", "failure", "other_operation", "history", "different_name",
])
def test_process_vocabulary_requires_the_exact_verified_operation(change):
    value = facts()
    if change == "unverified":
        value["situation"]["verified"] = False
    elif change == "unsucceeded":
        value["situation"]["succeeded"] = False
    elif change == "failure":
        value["situation"]["polarity"] = "failure"
    elif change == "other_operation":
        value["situation"]["operation"] = "system.status"
    elif change == "history":
        value["context"] = "The process baxy-core uses 4.5% CPU."
        value["situation"] = {"kind": "conversation", "polarity": "success"}
    else:
        value["situation"]["observed"]["processes"][0]["name"] = "other-worker"
    client = Recorder(["The process baxy-core uses 4.5% CPU."] * 3)
    assert client.compose_user_message("Which process uses the most CPU?", "status", value) == ""
    assert len(client.requests) == 3


def test_verified_process_in_a_mission_retains_its_own_provenance():
    value = facts()
    step = copy.deepcopy(value["situation"])
    value["situation"] = {"kind": "status", "cause": "mission_completed", "polarity": "success",
                          "stepCount": 1, "steps": [json.dumps(step)], "observed": step["observed"]}
    answer = "The process baxy-core uses 4.5% CPU."
    client = Recorder([answer])
    assert client.compose_user_message("Which process uses the most CPU?", "status", value) == answer
    assert len(client.requests) == 1


@pytest.mark.parametrize("punctuation", [".", ",", ":", ";", "!", "?", ")", '"'])
def test_observed_process_name_retains_sentence_punctuation(punctuation):
    assert without_observed_names(
        f"baxy-core{punctuation}", facts()["situation"],
    ) == f"\ufffc{punctuation}"
