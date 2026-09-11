"""The process narrator receives the verified inventory boundary and identities."""

import copy
import json

import pytest

from baxy_mind.llm import LlmRuntime


class Recorder(LlmRuntime):
    def __init__(self, replies):
        self._gguf = "Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
        self.replies = iter(replies)
        self.requests = []

    def _post(self, payload):
        self.requests.append(copy.deepcopy(payload))
        return {"choices": [{"message": {"content": next(self.replies)}, "finish_reason": "stop"}]}


def situation():
    return {
        "kind": "operation",
        "operation": "system.process.list",
        "verified": True,
        "succeeded": True,
        "polarity": "success",
        "observed": {
            "sort": "memory",
            "observationScope": "accessible_processes",
            "observedProcessCount": 207,
            "returnedProcessCount": 2,
            "processes": [
                {"name": "Editor", "processId": 731, "workingSetBytes": 125_000_000},
                {"name": "Editor", "processId": 927, "workingSetBytes": 64_000_000},
            ],
        },
    }


@pytest.mark.parametrize(
    ("question", "reply"),
    [
        (
            "Lista los procesos por memoria.",
            "Se observaron 207 procesos accesibles; esta lista muestra 2 de ellos: "
            "Editor (PID 731), 125 MB; Editor (PID 927), 64 MB.",
        ),
        (
            "List the processes by memory.",
            "207 accessible processes were observed; this list shows 2 of them: "
            "Editor (PID 731), 125 MB; Editor (PID 927), 64 MB.",
        ),
    ],
)
def test_verified_process_scope_reaches_first_prompt_and_existing_retry(question, reply):
    source = situation()
    original = copy.deepcopy(source)
    client = Recorder(["", reply])

    assert client.compose_user_message(question, "status", {"situation": source}) == reply
    assert len(client.requests) == 2
    assert source == original

    for request in client.requests:
        system = request["messages"][0]["content"].casefold()
        for field in ("observationscope", "observedprocesscount", "returnedprocesscount", "processid"):
            assert field in system

    prompt_facts = client.requests[0]["messages"][-1]["content"]
    facts = json.loads(prompt_facts.split("situation: ", 1)[1].split("\n", 1)[0])
    seen = facts["seen"]
    assert seen["observationScope"] == "accessible_processes"
    assert seen["observedProcessCount"] == 207
    assert seen["returnedProcessCount"] == 2
    assert [row["processId"] for row in seen["processes"]] == [731, 927]


def test_count_only_prompt_keeps_the_observed_count_and_scope_without_rows():
    client = Recorder(["Se observaron 207 procesos accesibles."])

    assert client.compose_user_message(
        "Cuántos procesos observaste sin listarlos?", "status", {"situation": situation()}
    ) == "Se observaron 207 procesos accesibles."
    assert len(client.requests) == 1
    prompt_facts = client.requests[0]["messages"][-1]["content"]
    facts = json.loads(prompt_facts.split("situation: ", 1)[1].split("\n", 1)[0])
    assert facts["seen"] == {
        "observedProcessCount": 207,
        "observationScope": "accessible_processes",
    }


@pytest.mark.parametrize(
    "change",
    [
        "other_operation", "wrong_kind", "failure_polarity", "unverified", "unsucceeded",
        "missing_scope", "different_scope", "acting",
    ],
)
def test_process_scope_prompt_requires_a_completed_verified_process_read(change):
    source = situation()
    if change == "other_operation":
        source["operation"] = "system.status"
    elif change == "wrong_kind":
        source["kind"] = "status"
    elif change == "failure_polarity":
        source["polarity"] = "failure"
    elif change == "unverified":
        source["verified"] = False
    elif change == "unsucceeded":
        source["succeeded"] = False
    elif change == "missing_scope":
        del source["observed"]["observationScope"]
    elif change == "different_scope":
        source["observed"]["observationScope"] = "all_processes"
    else:
        source["cause"] = "acting"
    client = Recorder(["Se observaron 207 procesos accesibles."] * 3)

    client.compose_user_message("Cuántos procesos observaste?", "status", {"situation": source})

    system = client.requests[0]["messages"][0]["content"].casefold()
    assert "observedprocesscount is the count observed" not in system
