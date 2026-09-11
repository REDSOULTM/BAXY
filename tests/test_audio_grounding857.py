from __future__ import annotations

import pytest

from baxy_mind.__main__ import _explicit_arguments_from_evidence
from baxy_mind.effect_intent import (
    operation_domain_is_grounded,
    resolve_explicit_clarification_intent,
    resolve_explicit_effects,
)


AVAILABLE = {"audio.volume", "audio.volume.adjust", "audio.status", "audio.mute"}


@pytest.mark.parametrize("text,level", [
    ("Deja la salida del equipo a veintisiete por ciento para escuchar esta explicación.", 27),
    ("Pon el volumen del sistema al setenta y cinco por ciento.", 75),
    ("Set the volume of the computer to eleven percent.", 11),
    ("Quiero el volumen del sistema justo a la mitad de su escala.", 50),
    ("Subí el volumen al máximo.", 100),
    ("Subí el volumen a la mitad.", 50),
    ("Lower the volume to half.", 50),
    ("Set the volume to maximum.", 100),
])
def test_absolute_level_survives_intent_domain_and_literal_binding(text, level):
    assert resolve_explicit_clarification_intent(text, AVAILABLE) is None
    intent = resolve_explicit_effects(text, AVAILABLE)
    assert intent is not None
    assert intent.operations == ("audio.volume",)
    assert operation_domain_is_grounded(text, "audio.volume") is True
    assert _explicit_arguments_from_evidence("audio.volume", text) == {"level": level}


@pytest.mark.parametrize("text,amount,direction", [
    ("Baja nueve puntos el volumen que tenga ahora el equipo, sin ponerlo en silencio.", 9, "down"),
    ("Sube el volumen en siete puntos.", 7, "up"),
    ("Aumenta el nivel actual de salida en doce puntos.", 12, "up"),
    ("Reduce en cuatro puntos la salida de sonido del PC.", 4, "down"),
    ("Lower nine points the volume.", 9, "down"),
    ("Increase the volume by twelve points.", 12, "up"),
    ("Baja el volumen en veintitrés puntos.", 23, "down"),
    ("Subí el volumen en 13 puntos.", 13, "up"),
])
def test_relative_quantity_is_not_clarified_or_replaced_by_an_absolute_target(
    text, amount, direction,
):
    assert resolve_explicit_clarification_intent(text, AVAILABLE) is None
    intent = resolve_explicit_effects(text, AVAILABLE)
    assert intent is not None
    assert intent.operations == ("audio.volume.adjust",)
    assert operation_domain_is_grounded(text, "audio.volume.adjust") is True
    assert _explicit_arguments_from_evidence("audio.volume.adjust", text) == {
        "amount": amount, "direction": direction,
    }


def test_numeric_antecedent_must_be_authored_in_the_same_absolute_request():
    text = "For this call, eleven percent is enough: set the computer volume there."
    assert operation_domain_is_grounded(text, "audio.volume") is True
    assert _explicit_arguments_from_evidence("audio.volume", text) == {"level": 11}
    assert _explicit_arguments_from_evidence(
        "audio.volume", "Set the computer volume there.",
    ) is None


@pytest.mark.parametrize("text", [
    "Sube el volumen.", "Baja el volumen.", "Subí un poco el volumen.",
    "Turn up the volume.", "Speak softer please.",
])
def test_relative_requests_without_amount_never_invent_one(text):
    assert _explicit_arguments_from_evidence("audio.volume.adjust", text) is None
    clarification = resolve_explicit_clarification_intent(text, AVAILABLE)
    assert clarification is not None
    assert clarification.operations == ("audio.volume.adjust",)
    assert clarification.missing_fields == ("amount",)


@pytest.mark.parametrize("operation,text", [
    ("audio.volume", "No pongas el volumen a la mitad."),
    ("audio.volume", "No pongas el volumen a 27."),
    ("audio.volume", "Pon el volumen al 137 por ciento."),
    ("audio.volume", "Pon el volumen de Spotify al máximo."),
    ("audio.volume", "Set the volume of the app to eleven percent."),
    ("audio.volume", "Pon el volumen del sistema a once o doce por ciento."),
    ("audio.volume", "Devuélvelo a ese nivel."),
    ("audio.volume.adjust", "No subas el volumen en nueve puntos."),
    ("audio.volume.adjust", "Sube el volumen en 137 puntos."),
    ("audio.volume.adjust", "Sube el volumen de Spotify en nueve puntos."),
    ("audio.volume.adjust", "Sube el volumen de ventas en nueve puntos."),
    ("audio.volume.adjust", "Sube el volumen en nueve o doce puntos."),
    ("audio.volume.adjust", "Sube el volumen en nueve puntos y bájalo en cuatro."),
])
def test_literal_binding_preserves_denial_range_scope_and_ambiguity(operation, text):
    assert _explicit_arguments_from_evidence(operation, text) is None


@pytest.mark.parametrize("text", [
    "Pon el volumen del sistema a la mitad.", "Sube el volumen en nueve puntos.",
])
def test_quantity_does_not_create_an_unavailable_catalog_operation(text):
    assert resolve_explicit_effects(text, ()) is None


@pytest.mark.parametrize("operation,text", [
    ("audio.volume", "Pon el volumen al veintisiete por ciento para la llamada de las 5."),
    ("audio.volume", "Set the volume to twenty seven percent for the call at 5."),
    ("audio.volume.adjust", "Sube el volumen en nueve puntos para la llamada de las 5."),
    ("audio.volume.adjust", "Lower the volume by nine points for the call at 5."),
])
def test_word_quantity_with_an_unrelated_digit_never_binds_the_digit(operation, text):
    # This mixed fragment is deliberately left for grounding; the numeric
    # fallback must not substitute the appointment time for the audio amount.
    assert _explicit_arguments_from_evidence(operation, text) is None
