"""Narrator process identities retain each observed name and PID as one datum."""

import copy
import json

import pytest

from baxy_mind.llm import _compose_situation_payload
from baxy_mind.measurement_prose_projection import project_process_measurements


@pytest.mark.parametrize("sort", ["memory", "cpu", "name"])
@pytest.mark.parametrize("row_count", [1, 3])
def test_compositor_preserves_selected_instances_order_measurements_and_raw_evidence(sort, row_count):
    source = {
        "kind": "operation", "operation": "system.process.list",
        "verified": True, "succeeded": True, "polarity": "success",
        "observed": {
            "sort": sort, "observedProcessCount": 217, "returnedProcessCount": row_count,
            "observationScope": "accessible_processes", "logicalProcessorCount": 8,
            "processes": [
                {"name": "Editor", "processId": 927, "workingSetBytes": 125_000_000,
                 "cpuUsagePercent": 12.5, "sampleDurationSeconds": 0.25},
                {"name": "Editor", "processId": 731, "workingSetBytes": 64_000_000,
                 "cpuUsagePercent": 3.5, "sampleDurationSeconds": 0.25},
                {"name": "System Idle Process", "processId": 0, "workingSetBytes": 0,
                 "cpuUsagePercent": 0, "sampleDurationSeconds": 0.25},
            ][:row_count],
        },
    }
    original = json.dumps(source, ensure_ascii=False)

    seen = _compose_situation_payload(source, "en", "List the selected processes.")["seen"]

    assert {key: value for key, value in seen.items() if key != "processes"} == {
        "sort": sort, "observedProcessCount": 217, "returnedProcessCount": row_count,
        "logicalProcessorCount": 8,
        "observationScope": (
            "processes accessible during this observation; "
            "completeness for the whole PC is not established"
        ),
    }
    identities = ["Editor (PID 927)", "Editor (PID 731)", "System Idle Process (PID 0)"]
    if sort == "cpu":
        expected_rows = [
            {"process_identity": identity,
             "current_cpu_usage": {"value": value, "unit": "%"}, "sampleDurationSeconds": 0.25}
            for identity, value in zip(identities, [12.5, 3.5, 0], strict=True)
        ]
    else:
        expected_rows = [
            {"process_identity": identity, "resident_memory": {"value": value, "unit": "MB"}}
            for identity, value in zip(identities, [125, 64, 0], strict=True)
        ]
    assert seen["processes"] == expected_rows[:row_count]
    assert json.dumps(source, ensure_ascii=False) == original


@pytest.mark.parametrize("name", ["Órbita 29", "  Editor  ", "worker (PID 8)", "baxy-core"])
@pytest.mark.parametrize("process_id", [0, 42, 2**100])
def test_identity_preserves_exact_name_and_integer_pid_without_an_invented_upper_limit(name, process_id):
    source = {"processes": [{"name": name, "processId": process_id, "other": "retained"}]}
    original = copy.deepcopy(source)

    assert project_process_measurements(source, "List processes.") == {
        "processes": [{"process_identity": f"{name} (PID {process_id})", "other": "retained"}],
    }
    assert source == original


@pytest.mark.parametrize("identity", [
    {}, {"name": "Editor"}, {"processId": 42},
    *[{"name": name, "processId": 42} for name in [None, "", "   ", True, 42, [], {}]],
    *[{"name": "Editor", "processId": pid} for pid in [None, True, False, "42", 42.0, -1, [], {}]],
])
def test_partial_or_malformed_identity_stays_typed_and_does_not_gain_a_synthetic_identifier(identity):
    source = {"sort": "memory", "processes": [{**identity, "workingSetBytes": 125_000_000}]}
    original = copy.deepcopy(source)

    projected = project_process_measurements(source, "List processes.")

    assert projected["processes"] == [
        {**identity, "resident_memory": {"value": 125, "unit": "MB"}},
    ]
    assert source == original


@pytest.mark.parametrize("rows", [None, {}, "unavailable", [None, "unknown", 42, []]])
def test_missing_or_malformed_rows_do_not_gain_identities(rows):
    source = {"processes": rows}
    original = copy.deepcopy(source)

    assert project_process_measurements(source, "List processes.") == original
    assert source == original


@pytest.mark.parametrize("sort", ["memory", "cpu", "name"])
def test_count_only_still_omits_all_rows_and_identity_fields(sort):
    source = {
        "sort": sort, "observedProcessCount": 217, "returnedProcessCount": 2,
        "observationScope": "accessible_processes",
        "processes": [{"name": "Editor", "processId": 42}, {"name": "Partial"}],
    }
    original = copy.deepcopy(source)

    assert project_process_measurements(source, "Count processes without listing.") == {
        "observedProcessCount": 217,
        "observationScope": (
            "processes accessible during this observation; "
            "completeness for the whole PC is not established"
        ),
    }
    assert source == original
