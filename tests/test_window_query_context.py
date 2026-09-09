"""Contextual reads must preserve scope without reviving earlier commands."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from baxy_mind import effect_intent
from baxy_mind.__main__ import _ground_explicit_arguments, _prepare_turn_result
from baxy_mind.planner import PlannerCatalog


APPS = ("Steam", "Spotify", "Órbita 23", "Bloc de notas")
SCHEMA = {
    "type": "object", "properties": {"name": {"type": "string"}},
    "required": ["name"], "additionalProperties": False,
}


@pytest.mark.parametrize("name", APPS)
@pytest.mark.parametrize("surface", ["And {name}?", "¿Y {name}?", "What about {name}?", "¿Qué hay de {name}?"])
def test_named_followup_reads_the_new_catalog_identity(name, surface):
    text = surface.format(name=name)
    assert effect_intent.resolve_application_window_followup_name(
        text, ["Is Steam open?"], APPS,
    ) == name


@pytest.mark.parametrize("surface", [
    "Is it open now?", "Is that application closed?", "¿Está abierta esa aplicación?",
    "¿Esa aplicación tiene alguna ventana abierta?", "¿Está cerrado ese programa?",
])
def test_pronoun_retains_the_latest_named_question_through_a_chain(surface):
    assert effect_intent.resolve_application_window_followup_name(
        surface, ["Is Steam open?", "And Spotify?", "Is it open now?", "¿Y Órbita 23?"], APPS,
    ) == "Órbita 23"


@pytest.mark.parametrize("intervening", [
    "Open Spotify", "Close Steam", "What is a window?", "No abras nada",
    "Is Steam open and is Spotify closed?", "And Unknown App?", "What time is it?",
    "Spotify is open", "Is Spotify open on my phone?", "Was Spotify open yesterday?",
])
def test_new_or_unresolved_topic_clears_the_read_reference(intervening):
    assert effect_intent.resolve_application_window_followup_name(
        "Is it open now?", ["Is Steam open?", intervening], APPS,
    ) is None


@pytest.mark.parametrize("text", [
    "And Spotify?", "Is it open?", "¿Y Steam?", "¿Esa aplicación tiene alguna ventana abierta?",
])
def test_reference_without_a_question_does_not_inherit_an_action(text):
    for history in [[], ["Open Steam"], ["Close Steam"], ["Explain Spotify"]]:
        assert effect_intent.resolve_application_window_followup_name(text, history, APPS) is None


@pytest.mark.parametrize("text", [
    "No abras ninguna ventana.", "And close Spotify", "Is it open on my phone?",
    "Was it open yesterday?", "Why is it open?", "Is it running in the background?",
    "Is it open and close Steam", "Thanks for checking.", "¿Está mi puerta abierta?",
])
def test_context_does_not_change_the_current_request(text):
    assert effect_intent.resolve_application_window_followup_name(text, ["Is Steam open?"], APPS) is None


def test_grounding_uses_user_reference_and_revalidates_the_exact_schema():
    text = "Is it open now?"
    history = [
        {"role": "user", "content": "Is Steam open?"},
        {"role": "assistant", "content": "Spotify is open."},
        {"role": "user", "content": text},
    ]
    assert _ground_explicit_arguments(
        "window.application.status", text, SCHEMA, APPS, history=history,
    ) == {"name": "Steam"}
    assert _ground_explicit_arguments(
        "window.application.status", text,
        {"type": "object", "properties": {}, "additionalProperties": False},
        APPS, history=history,
    ) is None
    assert _ground_explicit_arguments("app.open", text, SCHEMA, APPS, history=history) is None


def test_assistant_text_cannot_supply_the_reference():
    assert _ground_explicit_arguments(
        "window.application.status", "Is it open?", SCHEMA, APPS,
        history=[{"role": "assistant", "content": "Is Spotify open?"}],
    ) is None


@pytest.mark.parametrize("text", ["And Spotify?", "Is it open now?", "¿Y Órbita 23?", "¿Esa aplicación tiene alguna ventana abierta?"])
def test_scoped_followup_reaches_the_typed_read_without_retrieving_old_actions(text):
    tool = {"type": "function", "function": {
        "name": "window_application_status", "canonical_name": "window.application.status",
        "description": "Read visible windows for one installed application.",
        "risk": "read_only", "parameters": SCHEMA,
    }}

    class NoModel:
        _verify_semantic_effect_shape = None
        retire_deferred_response_language = None

        def __getattr__(self, name):
            raise AssertionError(f"A proved contextual read must not call {name}")

    result = _prepare_turn_result(
        {"id": "scoped-reference", "text": text, "history": [
            {"role": "user", "content": "Is Steam open?"},
            {"role": "assistant", "content": "Steam has two visible windows."},
        ]},
        llm=NoModel(), planner_catalog=PlannerCatalog([tool]), turn_evidence=NoModel(),
        encoder=lambda _texts: (), tool_by_name={"window.application.status": tool},
        application_names=APPS,
    )
    assert result["kind"] == "action"
    assert result["operation"] == "window.application.status"
    assert result["effectOperations"] == ["window.application.status"]
