"""A descriptive prose label preserves the typed observation and its meaning."""
import copy

import pytest

from baxy_mind.llm import _compose_situation_payload


@pytest.mark.parametrize("language", ["es", "en", "mixed"])
@pytest.mark.parametrize("foreground", [True, False])
@pytest.mark.parametrize("title", ["Foreground", "Órbita 23", "in_front_of_other_windows"])
def test_window_projection_preserves_boolean_names_and_geometry(language, foreground, title):
    window = {"windowId": "win_private", "title": title, "processName": title,
              "state": "normal", "foreground": foreground,
              "x": -7, "y": 13, "width": 321, "height": 456}
    situation = {"kind": "operation", "operation": "window.active",
                 "verified": True, "succeeded": True,
                 "observed": {"windows": [window], "count": 1}}
    original = copy.deepcopy(situation)
    payload = _compose_situation_payload(situation, language)
    projected = payload["seen"]["windows"][0]
    assert projected == {"title": title, "processName": title, "state": "normal",
                         "in_front_of_other_windows": foreground,
                         "x": -7, "y": 13, "width": 321, "height": 456}
    assert situation == original
    assert payload["seen"]["count"] == 1


@pytest.mark.parametrize("foreground", [None, "unknown", 0, 1])
def test_untyped_state_is_not_reinterpreted_as_a_boolean(foreground):
    window = {"title": "Example", "foreground": foreground}
    payload = _compose_situation_payload({"observed": {"windows": [window]}}, "es")
    assert payload["seen"]["windows"] == [window]


def test_existing_descriptive_field_does_not_get_overwritten():
    window = {"foreground": True, "in_front_of_other_windows": False}
    payload = _compose_situation_payload({"observed": {"windows": [window]}}, "es")
    assert payload["seen"]["windows"] == [window]


def test_nested_step_and_failure_keep_their_own_snapshot():
    step = {"operation": "window.resolve", "observed": {"windows": [{"foreground": False}]}}
    failure = {"operation": "window.active", "observed": {"windows": [{"foreground": True}]}}
    payload = _compose_situation_payload({"steps": [step], "reason": failure}, "es")
    assert payload["completedStepsInOrder"][0]["resultAtThisStep"]["seen"]["windows"] == [{"in_front_of_other_windows": False}]
    assert payload["reason"]["seen"]["windows"] == [{"in_front_of_other_windows": True}]
    assert step["observed"]["windows"] == [{"foreground": False}]
    assert failure["observed"]["windows"] == [{"foreground": True}]


def test_other_observation_fields_and_unstructured_entries_are_unchanged():
    seen = {"foreground": "literal data", "windows": [None, "Foreground", {"title": "Foreground"}]}
    assert _compose_situation_payload({"observed": seen}, "en")["seen"] == seen
