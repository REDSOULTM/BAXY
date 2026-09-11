"""Keep verified app opening distinct from the app's pre-invocation state."""

import copy

import pytest

from baxy_mind.llm import _compose_situation_payload


@pytest.mark.parametrize(
    "app_id,name,window_handle,user_text",
    [
        ("windows.calculator", "Calculadora", 1379672, "¿Puedes abrir la Calculadora?"),
        ("Paint", "Paint", 265804, "Por favor, inicia Paint."),
    ],
)
@pytest.mark.parametrize("already_running", [False, True])
def test_verified_open_preserves_completion_and_previous_running_state(
    app_id,
    name,
    window_handle,
    user_text,
    already_running,
):
    situation = {
        "kind": "operation",
        "operation": "app.open",
        "polarity": "success",
        "verified": True,
        "succeeded": True,
        "observed": {
            "appId": app_id,
            "displayName": name,
            "alreadyRunning": already_running,
            "windowHandle": window_handle,
        },
    }
    original = copy.deepcopy(situation)

    payload = _compose_situation_payload(situation, "es", user_text)

    assert payload["outcome"] == "completed"
    assert payload["operation"] == "app.open"
    assert payload["seen"] == {
        "appId": app_id,
        "displayName": name,
        "windowHandle": window_handle,
        "was_running_before_open": already_running,
    }
    assert situation == original


@pytest.mark.parametrize(
    "authority",
    [
        {"verified": False},
        {"verified": None},
        {"verified": "true"},
        {"succeeded": False},
        {"succeeded": None},
        {"polarity": "failure"},
        {"polarity": "pending"},
        {"effectUncertain": True},
        {"kind": "confirmation"},
    ],
)
def test_window_identity_and_requested_open_do_not_supply_missing_authority(authority):
    situation = {
        "kind": "operation",
        "operation": "app.open",
        "polarity": "success",
        "verified": True,
        "succeeded": True,
        "observed": {
            "displayName": "Orbit Editor",
            "alreadyRunning": False,
            "windowHandle": 42,
        },
        **authority,
    }

    payload = _compose_situation_payload(situation, "en", "Open Orbit Editor now.")

    assert payload.get("outcome") != "completed"
    if authority.get("effectUncertain"):
        assert payload["outcome"] == "unverified"
        assert payload["effect"] == "unknown"
    if authority.get("polarity") == "failure":
        assert payload["outcome"] == "failed"


def test_failed_mission_retains_completed_open_at_its_own_step_only():
    step = {
        "kind": "operation",
        "operation": "app.open",
        "polarity": "success",
        "verified": True,
        "succeeded": True,
        "observed": {"displayName": "Editor", "alreadyRunning": False},
    }

    payload = _compose_situation_payload(
        {"kind": "operation", "polarity": "failure", "steps": [step]},
        "en",
    )

    assert payload["outcome"] == "failed"
    opened = payload["completedStepsInOrder"][0]["resultAtThisStep"]
    assert opened["outcome"] == "completed"
    assert opened["seen"]["was_running_before_open"] is False
    assert step["observed"]["alreadyRunning"] is False


@pytest.mark.parametrize("value", [None, "false", 0])
def test_untyped_previous_state_is_not_invented_as_a_boolean(value):
    payload = _compose_situation_payload(
        {"operation": "app.open", "observed": {"alreadyRunning": value}},
        "en",
    )
    assert payload["seen"] == {"alreadyRunning": value}
    assert payload.get("outcome") != "completed"


def test_other_operation_observations_do_not_acquire_app_open_completion():
    situation = {
        "kind": "operation",
        "operation": "window.application.status",
        "polarity": "success",
        "verified": True,
        "succeeded": True,
        "observed": {"alreadyRunning": False},
    }
    payload = _compose_situation_payload(situation, "en", "Open the app.")
    assert payload["seen"] == {"alreadyRunning": False}
    assert payload.get("outcome") != "completed"
