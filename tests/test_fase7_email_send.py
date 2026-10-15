"""Fase 7 (D4, 2026-09-20): un correo a una dirección libre sale por el Outlook
clásico del dueño (email.send, confirmado en modo normal); sin dirección se
pregunta la dirección, nunca se inventa ni se fuerza a la casilla de pruebas."""

from __future__ import annotations

import pytest

from baxy_mind import effect_intent
from baxy_mind import compose_situation
from baxy_mind import argument_grounding

AVAILABLE = frozenset({"email.send", "message.send.test", "message.recipient.resolve", "message.send", "message.draft", "app.open"})
SCHEMA = {"type": "object", "properties": {"subject": {"type": ["string", "null"]}, "text": {"type": "string"}, "to": {"type": "string"}}, "required": ["text", "to"], "additionalProperties": False}


@pytest.mark.parametrize(
    ("text", "arguments"),
    [
        ("mandale un correo a ana@gmail.com diciendo que llego tarde", {"to": "ana@gmail.com", "text": "llego tarde", "subject": None}),
        ("send an email to lucas@gmail.com saying hi", {"to": "lucas@gmail.com", "text": "hi", "subject": None}),
        ("escribile un correo a ana@gmail.com con asunto reunión que diga nos vemos a las 5", {"to": "ana@gmail.com", "text": "nos vemos a las 5", "subject": "reunión"}),
        ("enviá un mail a autor@example.com diciendo prueba", {"to": "autor@example.com", "text": "prueba", "subject": None}),
    ],
)
def test_a_mail_to_an_address_is_sent_from_outlook(text: str, arguments: dict) -> None:
    assert effect_intent.email_send_request(text) == arguments
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, (), ())
    assert intent is not None and intent.operations == ("email.send",)
    assert effect_intent.resolve_explicit_clarification_intent(text, AVAILABLE) is None
    assert argument_grounding._ground_explicit_arguments("email.send", text, SCHEMA) == arguments
    assert effect_intent.operation_domain_is_grounded(text, "email.send") is True


@pytest.mark.parametrize("text", ["enviá un correo a juan", "mandale un mail a Lucas que diga hola", "escribile un mail a Lucas"])
def test_a_mail_for_a_name_asks_the_address(text: str) -> None:
    assert effect_intent.email_send_request(text) is None
    clarification = effect_intent.resolve_explicit_clarification_intent(text, AVAILABLE)
    assert clarification is not None and clarification.operations == ("email.send",) and clarification.missing_fields == ("to",)
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, (), ())
    assert intent is None or "message.send.test" not in intent.operations


def test_without_email_send_the_old_test_mailbox_send_stays_and_chats_are_untouched() -> None:
    without = frozenset({"message.send.test", "message.draft", "app.open"})
    intent = effect_intent.resolve_explicit_effects("mandale un correo a ana@gmail.com diciendo que llego tarde", without, (), ())
    assert intent is not None and intent.operations == ("message.send.test",)
    # Owner 2026-09-21: with the resolve/send pair served, a chat message to a named person in a named
    # client is sent to that person (confirmed); the forced test destination stays only without the pair.
    chat = effect_intent.resolve_explicit_effects("mandale por whatsapp a Música que ya voy", AVAILABLE, (), ())
    assert chat is not None and chat.operations == ("message.recipient.resolve", "message.send")
    forced = effect_intent.resolve_explicit_effects("mandale por whatsapp a Música que ya voy", AVAILABLE - {"message.recipient.resolve"}, (), ())
    assert forced is not None and forced.operations == ("message.send.test",)
    for code in ("mail_address_invalid", "outlook_profile_not_configured", "outlook_mail_send_failed", "mail_delivery_not_verified"):
        assert code in compose_situation._CAUSE_FACT
