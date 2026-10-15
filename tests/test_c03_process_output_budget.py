"""Complete process inventories share the bounded inventory output allowance."""

import copy
import json

import pytest

from baxy_mind.llm import LlmRuntime


class FirstRequest(BaseException):
    pass


class Capture(LlmRuntime):
    def __init__(self):
        self._gguf = "Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
        self.requests = []

    def _post(self, payload):
        self.requests.append(copy.deepcopy(payload))
        raise FirstRequest()


def observation(count=10):
    return {
        "kind": "operation", "operation": "system.process.list",
        "verified": True, "succeeded": True, "polarity": "success",
        "observed": {
            "sort": "memory", "observationScope": "accessible_processes",
            "observedProcessCount": 209, "returnedProcessCount": count,
            "processes": [
                {"processId": 701 + i, "name": "Editor", "workingSetBytes": 1_000_000}
                for i in range(count)
            ],
        },
    }


def first_request(source, text):
    original = copy.deepcopy(source)
    client = Capture()
    with pytest.raises(FirstRequest):
        client.compose_user_message(text, "status", {"situation": source})
    assert source == original
    return client.requests[0]


@pytest.mark.parametrize("text", ["Lista los procesos.", "List the processes."])
@pytest.mark.parametrize("count,expected", [(0, 256), (1, 256), (3, 256), (8, 512), (10, 512), (50, 512)])
def test_process_instances_get_enough_bounded_output_without_changing_their_facts(text, count, expected):
    request = first_request(observation(count), text)
    assert request["max_tokens"] == expected
    user_message = request["messages"][-1]["content"]
    facts = json.loads(user_message.split("situation: ", 1)[1].split("\n", 1)[0])
    assert len(facts["seen"]["processes"]) == count
    assert facts["seen"]["observedProcessCount"] == {
        "value": 209, "unit": "accessible process instances observed before row selection",
    }
    assert [p["process_identity"] for p in facts["seen"]["processes"]] == [
        f"Editor (PID {pid})" for pid in range(701, 701 + count)
    ]


@pytest.mark.parametrize("text", ["Cuántos procesos observaste sin listarlos?", "How many processes did you observe?"])
def test_count_only_reply_keeps_the_small_budget_even_when_provider_returned_many_rows(text):
    request = first_request(observation(50), text)
    assert request["max_tokens"] == 256


@pytest.mark.parametrize("mutation", [
    {"verified": False}, {"verified": "true"}, {"succeeded": False},
    {"succeeded": "true"}, {"operation": "system.status"},
])
def test_other_or_unverified_observations_do_not_gain_process_inventory_budget(mutation):
    source = observation()
    source.update(mutation)
    assert first_request(source, "List the processes.")["max_tokens"] == 256
