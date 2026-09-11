"""Process counts retain exact values and explicitly identify their populations."""

import copy
import json

import pytest

from baxy_mind.measurement_prose_projection import project_process_measurements


OBSERVED_UNIT = "accessible process instances observed before row selection"
RETURNED_UNIT = "selected process rows supplied from that observation"
SCOPE_MEANING = (
    "processes accessible during this observation; "
    "completeness for the whole PC is not established"
)


@pytest.mark.parametrize("observed,returned", [
    (0, 0), (1, 1), (139, 139), (139, 10), (139, 1), (141, 1),
    (2**100, 2**100 - 1), (1, 10),
])
@pytest.mark.parametrize("rows", [[], None, [None, "unavailable"]])
def test_counts_describe_their_own_population_without_rounding_or_recounting(observed, returned, rows):
    source = {
        "observationScope": "accessible_processes",
        "observedProcessCount": observed, "returnedProcessCount": returned,
        "processes": rows, "other": {"retained": True},
    }
    original = json.dumps(source)

    projected = project_process_measurements(source, "List the processes.")

    assert projected == {
        "observationScope": SCOPE_MEANING,
        "observedProcessCount": {"value": observed, "unit": OBSERVED_UNIT},
        "returnedProcessCount": {"value": returned, "unit": RETURNED_UNIT},
        "processes": rows, "other": {"retained": True},
    }
    assert type(projected["observedProcessCount"]["value"]) is int
    assert type(projected["returnedProcessCount"]["value"]) is int
    assert list(projected) == list(source)
    assert json.dumps(source) == original
    assert json.loads(json.dumps(projected)) == projected


@pytest.mark.parametrize("key,other_key,other_unit", [
    ("observedProcessCount", "returnedProcessCount", RETURNED_UNIT),
    ("returnedProcessCount", "observedProcessCount", OBSERVED_UNIT),
])
@pytest.mark.parametrize("invalid", [True, False, "139", 139.0, -1, -1.5, None, [], {}])
def test_invalid_count_is_unchanged_while_valid_sibling_is_projected(key, other_key, other_unit, invalid):
    source = {"observationScope": "accessible_processes", key: invalid, other_key: 139}
    original = copy.deepcopy(source)

    projected = project_process_measurements(source, "List the processes.")

    assert projected == {
        "observationScope": SCOPE_MEANING, key: invalid,
        other_key: {"value": 139, "unit": other_unit},
    }
    assert type(projected[key]) is type(invalid)
    assert source == original


@pytest.mark.parametrize("counts", [{}, {"observedProcessCount": 139}, {"returnedProcessCount": 10}])
def test_missing_counts_are_not_inferred_from_rows_or_sibling(counts):
    source = {"observationScope": "accessible_processes", **counts, "processes": [None]}
    original = copy.deepcopy(source)

    projected = project_process_measurements(source, "List the processes.")

    assert set(projected) == set(source)
    for key, unit in (("observedProcessCount", OBSERVED_UNIT), ("returnedProcessCount", RETURNED_UNIT)):
        if key in counts:
            assert projected[key] == {"value": counts[key], "unit": unit}
        else:
            assert key not in projected
    assert source == original


@pytest.mark.parametrize("scope", [{}, {"observationScope": None}, {"observationScope": "all_processes"},
                                   {"observationScope": "future_scope"}, {"observationScope": SCOPE_MEANING}])
def test_counts_without_canonical_accessible_scope_stay_raw(scope):
    source = {**scope, "observedProcessCount": 139, "returnedProcessCount": 10}
    original = copy.deepcopy(source)

    assert project_process_measurements(source, "List the processes.") == original
    assert source == original


@pytest.mark.parametrize("text", ["Cuántos procesos observaste sin listarlos?", "Count processes without listing."])
@pytest.mark.parametrize("count", [0, 139, 2**100])
def test_count_only_keeps_only_observed_population_and_scope(text, count):
    source = {
        "observationScope": "accessible_processes", "observedProcessCount": count,
        "returnedProcessCount": 10, "processes": [None],
    }
    original = copy.deepcopy(source)

    assert project_process_measurements(source, text) == {
        "observationScope": SCOPE_MEANING,
        "observedProcessCount": {"value": count, "unit": OBSERVED_UNIT},
    }
    assert source == original
