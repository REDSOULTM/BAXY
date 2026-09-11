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
@pytest.mark.parametrize("cpu_fallback", [False, True])
def test_verified_process_scope_reaches_first_prompt_and_existing_retry(
    question, reply, cpu_fallback, monkeypatch
):
    monkeypatch.setenv("BAXY_MIND_NGL", "0" if cpu_fallback else "99")
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
        assert "include every supplied row once, in that order" in system
        assert "keeping its name, processid and observed resource value and unit together" in system
        assert "even for a single result" in system
        assert "state how many rows you actually list" in system
        assert "disclose when the list is a subset" in system
        assert "a process working set is not an application total" in system

    prompt_facts = client.requests[0]["messages"][-1]["content"]
    facts = json.loads(prompt_facts.split("situation: ", 1)[1].split("\n", 1)[0])
    seen = facts["seen"]
    assert seen["observationScope"] == (
        "processes accessible during this observation; "
        "completeness for the whole PC is not established"
    )
    assert seen["observedProcessCount"] == {
        "value": 207, "unit": "accessible process instances observed before row selection",
    }
    assert seen["returnedProcessCount"] == {"value": 2, "unit": "selected process rows supplied from that observation"}
    assert [row["process_identity"] for row in seen["processes"]] == [
        "Editor (PID 731)", "Editor (PID 927)",
    ]


@pytest.mark.parametrize("row_count", [1, 10])
@pytest.mark.parametrize("resource", ["memory", "cpu"])
def test_selected_ranking_keeps_all_rows_and_identities_on_retry(row_count, resource):
    source = situation()
    rows = [
        {"name": "Editor", "processId": 731, "workingSetBytes": 481_000_000},
        {"name": "Browser", "processId": 927, "workingSetBytes": 397_000_000},
        *[
            {"name": f"Worker{index}", "processId": 1000 + index,
             "workingSetBytes": (300 - index) * 1_000_000}
            for index in range(8)
        ],
    ][:row_count]
    if resource == "cpu":
        for index, row in enumerate(rows):
            row.update(cpuUsagePercent=17.5-index, sampleDurationSeconds=0.5)
    source["observed"]["sort"] = resource
    source["observed"]["processes"] = rows
    source["observed"]["returnedProcessCount"] = row_count
    original = copy.deepcopy(source)
    expected_rows = [
        {"process_identity": f"{row['name']} (PID {row['processId']})",
         "resident_memory": {"value": row["workingSetBytes"] / 1_000_000, "unit": "MB"}}
        for row in rows
    ]
    if resource == "cpu":
        expected_rows = [
            {"process_identity": f"{row['name']} (PID {row['processId']})",
             "current_cpu_usage": {"value": row["cpuUsagePercent"], "unit": "%"},
             "sampleDurationSeconds": 0.5}
            for row in rows
        ]
    def measurement(row):
        return (f"{row['cpuUsagePercent']}%" if resource == "cpu"
                else f"{row['workingSetBytes'] // 1_000_000} MB")
    reply = f"Se observaron 207 procesos accesibles; estos son {row_count}: " + "; ".join(
        f"{row['name']} (PID {row['processId']}), {measurement(row)}"
        for row in rows
    ) + "."
    client = Recorder(["", reply])

    assert client.compose_user_message(
        f"Lista los {row_count} procesos con más {'CPU actual' if resource == 'cpu' else 'memoria'}, en orden.",
        "status", {"situation": source},
    ) == reply
    assert len(client.requests) == 2
    assert source == original
    for request in client.requests:
        prompt_facts = request["messages"][-1]["content"]
        facts = json.loads(prompt_facts.split("situation: ", 1)[1].split("\n", 1)[0])
        assert facts["seen"]["processes"] == expected_rows
        assert facts["seen"]["returnedProcessCount"] == {
            "value": row_count, "unit": "selected process rows supplied from that observation",
        }
        assert facts["seen"]["observedProcessCount"] == {
            "value": 207, "unit": "accessible process instances observed before row selection",
        }


@pytest.mark.parametrize("question,reply", [
    ("Cuántos procesos observaste sin listarlos?", "Se observaron 207 procesos accesibles."),
    ("How many processes did you observe?", "207 accessible processes were observed."),
])
@pytest.mark.parametrize("retry", [False, True])
def test_count_only_prompt_keeps_the_observed_count_and_scope_without_rows_on_retry(question, reply, retry):
    source = situation()
    original = copy.deepcopy(source)
    client = Recorder(["", reply] if retry else [reply])

    assert client.compose_user_message(
        question, "status", {"situation": source}
    ) == reply
    assert len(client.requests) == (2 if retry else 1)
    assert source == original
    for request in client.requests:
        system = request["messages"][0]["content"].casefold()
        assert "a count-only reply states the observed count and scope without rows" in system
        prompt_facts = request["messages"][-1]["content"]
        facts = json.loads(prompt_facts.split("situation: ", 1)[1].split("\n", 1)[0])
        assert facts["seen"] == {
            "observedProcessCount": {
                "value": 207, "unit": "accessible process instances observed before row selection",
            },
            "observationScope": (
                "processes accessible during this observation; "
                "completeness for the whole PC is not established"
            ),
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
    assert "for this process inventory" not in system
