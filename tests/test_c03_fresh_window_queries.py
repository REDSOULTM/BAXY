"""Present-time framing and user references must still select a fresh read."""
import pytest

from baxy_mind.effect_intent import resolve_explicit_effects
from baxy_mind.__main__ import _prepare_turn_result
from baxy_mind.planner import PlannerCatalog


AVAILABLE = {"window.active", "system.time", "audio.status", "app.open", "window.close"}


@pytest.mark.parametrize("prefix", ["Ahora mismo, ", "En este momento: ", "Actualmente, ", "Right now, ", "At this moment: ", "Currently, "])
@pytest.mark.parametrize("query,operation", [
    ("¿Qué ventana tiene el foco?", "window.active"),
    ("Which window is active?", "window.active"),
    ("¿Qué hora es?", "system.time"),
])
def test_present_frame_preserves_the_observation(prefix, query, operation):
    result = resolve_explicit_effects(prefix + query, AVAILABLE)
    assert result is not None and result.operations == (operation,)


@pytest.mark.parametrize("previous", ["¿Qué ventana está activa?", "Which window has focus?", "Baxy, ¿qué window tiene focus ahora?"])
@pytest.mark.parametrize("query", [
    "¿Y ahora cuál está activa?", "¿Cuál tiene el foco ahora?",
    "And which one is active now?", "Which has focus right now?",
    "Ahora mismo, ¿cuál está activa?",
])
def test_immediate_user_reference_requests_a_new_read(previous, query):
    result = resolve_explicit_effects(query, AVAILABLE, previous_user_text=previous)
    assert result is not None and result.operations == ("window.active",)


@pytest.mark.parametrize("previous", [
    None, "What time is it?", "Open Steam", "Close the active window", "What is an active window?",
    "Which window is active and what time is it?", "Is Spotify open?",
])
def test_missing_changed_or_compound_antecedent_does_not_authorize_focus(previous):
    result = resolve_explicit_effects("¿Y ahora cuál está activa?", AVAILABLE, previous_user_text=previous)
    assert result is None or "window.active" not in result.operations


@pytest.mark.parametrize("query", [
    "¿Y cuál estaba activa ayer?", "Which will be active tomorrow?",
    "Which one is active on my phone?", "No compruebes cuál está activa.",
    "Which one is active and close it?", "Explain which one is active.",
    'Write "which one is active now?"', "If one is active, close it.",
])
def test_reference_does_not_rewrite_another_request(query):
    result = resolve_explicit_effects(query, AVAILABLE, previous_user_text="Which window is active?")
    assert result is None or result.operations != ("window.active",)


def test_catalog_absence_cannot_substitute_another_operation():
    assert resolve_explicit_effects("¿Y ahora cuál está activa?", AVAILABLE - {"window.active"},
        previous_user_text="¿Qué ventana está activa?") is None


@pytest.mark.parametrize("query,history", [
    ("Ahora mismo, ¿qué ventana tiene el foco?", []),
    ("¿Y ahora cuál está activa?", [{"role": "user", "content": "Which window has focus?"},
        {"role": "assistant", "content": "The old title was Atlas."}]),
    ("Which one is active now?", [{"role": "user", "content": "¿Qué ventana está activa?"},
        {"role": "assistant", "content": "The old title was Órbita 29."}]),
])
def test_shared_turn_pipeline_selects_observation_without_reciting_history(query, history):
    tool = {"type": "function", "function": {
        "name": "window_active", "canonical_name": "window.active",
        "description": "Read the current foreground window.", "risk": "read_only",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    }}

    class NoModel:
        _verify_semantic_effect_shape = None
        retire_deferred_response_language = None

        def __getattr__(self, name):
            raise AssertionError(f"A proved current read must not call {name}")

    result = _prepare_turn_result(
        {"id": "current-reference", "text": query, "history": history},
        llm=NoModel(), planner_catalog=PlannerCatalog([tool]), turn_evidence=NoModel(),
        encoder=lambda _texts: (), tool_by_name={"window.active": tool}, application_names=(),
    )
    assert result["kind"] == "action"
    assert result["operation"] == "window.active"
    assert result["effectOperations"] == ["window.active"]
