"""REOPEN1993 grupo E (D24): un mensaje a una persona o grupo con nombre y sin
cliente nombrado (H0019 «mandale a Música que ya voy», H0408, H0198/H0231/H0536
«… al grupo Musica: …», H0024 «escribile a Lucas que llego tarde») busca al
destinatario en los clientes (message.recipient.resolve{channel: any}) y, si es
único, lo envía (message.send, confirmado en modo normal); ni pregunta el
cliente ni lo elige a ciegas. Un cliente nombrado antes del texto sigue siendo
el envío de prueba; uno al final del texto es el cliente."""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as mind
from baxy_mind import effect_intent, llm

AVAILABLE = frozenset({"message.send.test", "message.recipient.resolve", "message.send", "message.draft", "client.channel.locate", "app.open"})
RESOLVE_SCHEMA = {
    "type": "object",
    "properties": {"channel": {"type": "string", "enum": ["any", "discord", "whatsapp"]}, "recipient": {"type": "string"}},
    "required": ["channel", "recipient"],
    "additionalProperties": False,
}


@pytest.mark.parametrize(
    ("text", "recipient", "body"),
    [
        ("mandale a Música que ya voy", "Música", "ya voy"),
        ("Manda un mensaje a Música que dija hola", "Música", "hola"),
        ("mandale al grupo Musica: prueba 1 de WhatsApp, ya funciona de nuevo", "Musica", "prueba 1 de WhatsApp, ya funciona de nuevo"),
        ("mandale al grupo Musica: prueba de WhatsApp, ya funciona de nuevo", "Musica", "prueba de WhatsApp, ya funciona de nuevo"),
        ("enviale un mensaje al grupo Musica que diga: prueba 2, todo OK", "Musica", "prueba 2, todo OK"),
        ("escribile a Lucas que llego tarde", "Lucas", "llego tarde"),
        ("text Lucas that I am late", "Lucas", "I am late"),
        ("send Lucas a message saying hi", "Lucas", "hi"),
        ("avisale a Música que ya voy", "Música", "ya voy"),
        ("let Lucas know that I am late", "Lucas", "I am late"),
    ],
)
def test_a_named_recipient_without_a_client_is_looked_up_and_sent(text: str, recipient: str, body: str) -> None:
    assert effect_intent.message_request_any_channel(text) == (recipient, body, None)
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, (), ())
    assert intent is not None and intent.operations == ("message.recipient.resolve", "message.send")
    assert effect_intent.resolve_explicit_clarification_intent(text, AVAILABLE) is None
    assert mind._ground_explicit_arguments("message.recipient.resolve", text, RESOLVE_SCHEMA) == {"channel": "any", "recipient": recipient}
    observations = [{"operation": "message.recipient.resolve", "verified": True, "status": "completed", "result": {"recipientId": "recipient_1", "channel": "whatsapp", "displayName": recipient}}]
    assert mind._verified_message_send_arguments(text, observations) == {"recipientId": "recipient_1", "text": body}
    skeleton = mind._explicit_plan_skeleton(("message.recipient.resolve", "message.send"), (text, text))
    assert skeleton["steps"][1]["argumentsMode"] == "after_dependencies"
    assert effect_intent.operation_domain_is_grounded(text, "message.recipient.resolve") is True


def test_a_client_at_the_end_of_the_text_is_the_client_and_one_before_stays_the_test_send() -> None:
    trailing = "dile a Ana que llegare tarde por WhatsApp"
    assert effect_intent.message_request_any_channel(trailing) == ("Ana", "llegare tarde", "whatsapp")
    assert mind._ground_explicit_arguments("message.recipient.resolve", trailing, RESOLVE_SCHEMA) == {"channel": "whatsapp", "recipient": "Ana"}
    leading = "mandale por whatsapp a Música que ya voy"
    assert effect_intent.message_request_any_channel(leading) is None
    # Owner 2026-09-21: a client named before the text is the named-client send (looked up there, confirmed).
    assert effect_intent.message_request_named_client(leading) == ("Música", "ya voy", "whatsapp")
    intent = effect_intent.resolve_explicit_effects(leading, AVAILABLE, (), ())
    assert intent is not None and intent.operations == ("message.recipient.resolve", "message.send")


@pytest.mark.parametrize("text", ["tell me a joke", "dile que si", "contestale que si", "no le mandes nada a Lucas", "manda flores a mi madre", "mandale a Música un ramo de rosas"])
def test_what_is_not_a_message_to_someone_is_not_read_as_one(text: str) -> None:
    assert effect_intent.message_request_any_channel(text) is None
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, (), ())
    assert intent is None or "message.recipient.resolve" not in intent.operations


def test_without_the_resolve_pair_the_client_is_still_asked() -> None:
    without = frozenset({"message.send", "app.open"})
    clarification = effect_intent.resolve_explicit_clarification_intent("mandale a Música que ya voy", without)
    assert clarification is not None and clarification.missing_fields == ("channel",)


def test_the_absences_have_their_cause_facts_and_the_final_names_chat_and_client() -> None:
    for code in ("recipient_not_found_in_clients", "recipient_channel_ambiguous"):
        assert code in llm._CAUSE_FACT
    situation = {
        "kind": "status",
        "cause": "mission_completed",
        "steps": [
            '{"kind":"operation","operation":"message.recipient.resolve","polarity":"success","verified":true,"succeeded":true,"observed":{"recipientId":"recipient_1","channel":"whatsapp","displayName":"Música"}}',
            '{"kind":"operation","operation":"message.send","polarity":"success","verified":true,"succeeded":true,"observed":{"messageId":"message_1","recipientId":"recipient_1","channel":"whatsapp","displayName":"Música","delivery":"visible_postcondition"}}',
        ],
    }
    steps = llm._situation_steps(situation)
    assert [step["operation"] for step in steps] == ["message.recipient.resolve", "message.send"]
