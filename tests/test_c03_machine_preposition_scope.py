"""A Spanish preposition must not turn a local read into foreign hardware."""
import pytest

from baxy_mind import effect_intent
from baxy_mind.__main__ import _explicit_system_status_scope


@pytest.mark.parametrize("target", [
    "la notebook", "mi notebook", "esta notebook",
    "la laptop", "mi laptop", "esta laptop",
    "la computadora", "mi computadora", "esta computadora", "este PC",
])
@pytest.mark.parametrize("surface", [
    "¿Cuánta batería le queda a {target}?",
    "Dime cuánta batería le queda a {target}.",
    "Baxy, comprueba cuánta batería le queda a {target}.",
])
def test_local_battery_relation_reaches_exact_catalog_read(target, surface):
    text = surface.format(target=target)
    assert effect_intent.operation_domain_is_grounded(text, "system.status") is True
    intent = effect_intent.resolve_explicit_effects(text, {"system.status"})
    assert intent is not None
    assert intent.operations == ("system.status",)
    assert _explicit_system_status_scope(text) == {"scope": "battery"}
    assert effect_intent.resolve_explicit_effects(text, {"system.time"}) is None


@pytest.mark.parametrize("text", [
    "How much battery is left?", "Check the battery", "battery level please",
    "¿Cuánta batería queda?", "Revisa la batería", "Nivel de carga de la batería",
])
def test_existing_english_and_spanish_reads_keep_their_scope(text):
    intent = effect_intent.resolve_explicit_effects(text, {"system.status"})
    assert intent is not None
    assert intent.operations == ("system.status",)
    assert _explicit_system_status_scope(text) == {"scope": "battery"}


@pytest.mark.parametrize("target", [
    "a laptop", "a small notebook", "an expensive laptop", "another notebook",
    "a typical gaming laptop", "una notebook", "otro equipo", "una nueva computadora",
])
def test_indefinite_hardware_is_not_a_live_local_read(target):
    text = f"How much battery does {target} have?"
    assert effect_intent.operation_domain_is_grounded(text, "system.status") is False
    assert effect_intent.resolve_explicit_effects(text, {"system.status"}) is None
    assert _explicit_system_status_scope(text) is None


@pytest.mark.parametrize("text", [
    "No compruebes cuánta batería le queda a la notebook",
    "No me digas cuánta batería le queda a mi laptop",
    "¿Cuánta batería le quedaba ayer a la notebook?",
    "¿Cuánta batería le quedaría a mi laptop?",
    "¿Cuánta batería le quedaría a esta computadora?",
    "Dime cuánta batería le queda a mi celular",
    "¿Cuánta batería le queda a la notebook de otra persona?",
    "Dime cuánta batería le queda a la laptop de otro usuario",
    "How much battery is left on somebody else's laptop?",
    "Traduce: cuánta batería le queda a la notebook",
    "Explica por qué le queda poca batería a mi laptop",
])
def test_preposition_does_not_authorize_negated_past_or_foreign_reads(text):
    assert effect_intent.resolve_explicit_effects(text, {"system.status"}) is None
