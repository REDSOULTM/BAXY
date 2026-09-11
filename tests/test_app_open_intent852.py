from __future__ import annotations

import pytest

from baxy_mind.__main__ import apply_explicit_effect_contract
from baxy_mind.effect_intent import (
    operation_domain_is_grounded,
    resolve_application_catalog_app_id,
    resolve_explicit_effects,
)


NAMES = ("Paint", "Órbita 23", "Visual Studio Code", "Atlas.NET")
AVAILABLE = ("app.open", "app.installed", "window.application.status")


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("surface", [
    "Quiero que abras {name}, por favor.",
    "Necesito que inicies {name}; por favor.",
    "Quisiera que lances {name}, please.",
    "Dale, abrime {name}.",
    "Dale: abrí {name}.",
    "Baxy, dale, abrime {name}.",
    "Dale, abre {name}, por favor.",
    "I need you to open {name}, please.",
    "Quiero que abras {name}.",
    "Abrime {name}.",
    "Por favor, inicia {name}.",
])
def test_explicit_app_request_recovers_operation_and_exact_target(name, surface):
    text = surface.format(name=name)
    intent = resolve_explicit_effects(text, AVAILABLE, NAMES)

    assert intent is not None
    assert intent.operations == ("app.open",)
    assert resolve_application_catalog_app_id(text, NAMES) == name
    assert operation_domain_is_grounded(text, "app.open", NAMES)
    contracted = apply_explicit_effect_contract(
        {
            "mode": "conversation",
            "operation": None,
            "conversation_kind": "knowledge",
            "effect_count": "zero",
            "effect_operations": [],
            "response_language": "es",
        },
        intent,
    )
    assert contracted["mode"] == "action"
    assert contracted["operation"] == "app.open"
    assert contracted["effect_operations"] == ["app.open"]
    assert contracted["effect_verification"] == "recovered"
    assert contracted["response_language"] == "es"


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("surface", [
    "No quiero que abras {name}, por favor.",
    "Quiero que no abras {name}, por favor.",
    "Dale, no abras {name}.",
    "Dale, no quiero que abras {name}, por favor.",
    "La frase 'quiero que abras {name}, por favor' es un ejemplo.",
    "¿Qué significa 'Dale, abrime {name}'?",
    "Quiero que abras {name} mañana, por favor.",
    "Quiero que abras {name} en mi teléfono, por favor.",
    "Dale, abrime {name} o Nebula.",
    "Quiero que abras {name} o Nebula, por favor.",
    "Quiero que abras {name} documentation, por favor.",
    "Dale abrime {name}.",
])
def test_wrappers_do_not_authorize_negative_informational_or_ambiguous_text(
    name, surface,
):
    text = surface.format(name=name)
    names = (*NAMES, "Nebula")

    assert resolve_explicit_effects(text, AVAILABLE, names) is None
    assert resolve_application_catalog_app_id(text, names) is None


@pytest.mark.parametrize("surface", [
    "Quiero que abras {name}, por favor.",
    "Dale, abrime {name}.",
])
def test_wrappers_cannot_invent_an_application_or_catalog_operation(surface):
    text = surface.format(name="Órbita 23")

    assert resolve_explicit_effects(text, AVAILABLE, ()) is None
    assert resolve_application_catalog_app_id(text, ()) is None
    assert resolve_explicit_effects(text, ("app.installed",), NAMES) is None


def test_courtesy_words_in_exact_app_identity_are_preserved():
    names = ("Atlas", "Atlas, please")
    text = "Dale, abrime Atlas, please."

    intent = resolve_explicit_effects(text, AVAILABLE, names)
    assert intent is not None
    assert intent.operations == ("app.open",)
    assert resolve_application_catalog_app_id(text, names) == "Atlas, please"


@pytest.mark.parametrize("surface", [
    "Quiero que abras Atlas, por favor.",
    "Dale, abrime Atlas.",
])
def test_ambiguous_catalog_identity_does_not_supply_provider_input(surface):
    names = ("Atlas North", "Atlas South")

    assert resolve_explicit_effects(surface, AVAILABLE, names) is None
    assert resolve_application_catalog_app_id(surface, names) is None
