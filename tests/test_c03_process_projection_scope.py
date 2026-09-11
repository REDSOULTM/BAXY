"""Process narration receives scope meaning without changing canonical evidence."""

import copy
import json

import pytest

from baxy_mind.measurement_prose_projection import project_process_measurements


SCOPE_MEANING = (
    "processes accessible during this observation; "
    "completeness for the whole PC is not established"
)


def observation(sort="memory"):
    return {
        "sort": sort,
        "observationScope": "accessible_processes",
        "observedProcessCount": 207,
        "returnedProcessCount": 2,
        "logicalProcessorCount": 8,
        "processes": [
            {"name": "Editor", "processId": 731, "workingSetBytes": 125_000_000,
             "cpuUsagePercent": 12.5, "sampleDurationSeconds": 0.25,
             "totalProcessorSeconds": 9000},
            {"name": "Editor", "processId": 927, "workingSetBytes": 64_000_000,
             "cpuUsagePercent": 3.5, "sampleDurationSeconds": 0.25,
             "totalProcessorSeconds": 1},
        ],
    }


@pytest.mark.parametrize("user_text", [
    "Cuántos procesos observaste sin listarlos?",
    "How many processes are running?",
    "Count the running processes without listing them.",
    "Cuántos processes están running?",
])
def test_count_only_has_scope_meaning_without_enum_or_competing_rows(user_text):
    source = observation()
    original = copy.deepcopy(source)

    projected = project_process_measurements(source, user_text)

    assert projected == {"observedProcessCount": 207, "observationScope": SCOPE_MEANING}
    assert "accessible_processes" not in json.dumps(projected)
    assert source == original


@pytest.mark.parametrize("sort", ["memory", "cpu", "name"])
@pytest.mark.parametrize("user_text", [
    "Lista los procesos.", "Count and list the processes.", "Mostrame los processes.",
])
def test_list_scope_keeps_counts_order_identity_and_resource_units(sort, user_text):
    source = observation(sort)
    original = copy.deepcopy(source)

    projected = project_process_measurements(source, user_text)

    assert projected["observationScope"] == SCOPE_MEANING
    assert "accessible_processes" not in json.dumps(projected)
    assert projected["observedProcessCount"] == 207
    assert projected["returnedProcessCount"] == 2
    assert projected["logicalProcessorCount"] == 8
    assert projected["sort"] == sort
    rows = projected["processes"]
    assert [row["process_identity"] for row in rows] == [
        "Editor (PID 731)", "Editor (PID 927)",
    ]
    if sort == "cpu":
        assert [row["current_cpu_usage"] for row in rows] == [
            {"value": 12.5, "unit": "%"}, {"value": 3.5, "unit": "%"},
        ]
        assert [row["sampleDurationSeconds"] for row in rows] == [0.25, 0.25]
        assert all("resident_memory" not in row for row in rows)
    else:
        assert [row["resident_memory"] for row in rows] == [
            {"value": 125, "unit": "MB"}, {"value": 64, "unit": "MB"},
        ]
        assert all("current_cpu_usage" not in row for row in rows)
    assert all("totalProcessorSeconds" not in row for row in rows)
    assert source == original


@pytest.mark.parametrize("user_text", ["Count the processes.", "List the processes."])
@pytest.mark.parametrize("scope", [None, "", "all_processes", "future_scope", {"unknown": True}])
def test_unknown_scope_does_not_gain_a_known_boundary(user_text, scope):
    source = observation()
    source["observationScope"] = scope
    original = copy.deepcopy(source)

    projected = project_process_measurements(source, user_text)

    assert projected["observationScope"] == scope
    assert source == original


@pytest.mark.parametrize("user_text", ["Count the processes.", "List the processes."])
def test_missing_scope_is_not_invented(user_text):
    source = observation()
    del source["observationScope"]
    original = copy.deepcopy(source)

    projected = project_process_measurements(source, user_text)

    assert "observationScope" not in projected
    assert projected["observedProcessCount"] == 207
    assert source == original


def test_scope_survives_partial_observation_without_inventing_count_or_rows():
    source = {"observationScope": "accessible_processes"}

    assert project_process_measurements(source, "List the processes.") == {
        "observationScope": SCOPE_MEANING,
    }
    assert source == {"observationScope": "accessible_processes"}
