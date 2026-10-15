"""Encargo TZ-DC (tandas finales z1/z2 en el notebook, main 8d90cc2d0): los dos envíos por Discord al MD de Ron92 que
salieron distinto en las dos tandas, con lo que llegó de verdad congelado.

t4-c03 t2 «mandale a Ron92 que si se conecta a las 9 pa jugar» (tras «abre discord porfa»): en las dos tandas el
decisor contextual reformuló el pedido como «Manda a Ron92 en Discord: «si se conecta a las 9 pa jugar».» y ése fue el
objetivo del paso ``message.send`` (``plan.ground``). El lector sin modelo del cuerpo (``messaging.message_body``) no
leía las comillas españolas, así que el cuerpo fue al modelo: en z2 lo copió (envío verificado), en z1 se abstuvo dos
veces (18 tokens cada una) y el paso terminó en ``step_data_missing`` («No pude enviar el mensaje.»). Ahora el cuerpo se
lee de las comillas y el modelo no interviene.

t1-c09 t1 «mandale a Ron92 por discord que hoy no llego a jugar…»: en z2 el registro del dueño vio input sin marca de
BAXY de 15:04:28,8 a 15:04:36,4 UTC, en mitad del envío (15:04:26,9–15:04:30,6). La ráfaga paró antes del Enter y el
compositor ya había cambiado (``message_draft_left_after_interruption``). Es una causa del entorno: el final dice que
lo intentó y que no pudo confirmarlo, nunca que lo envió.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from baxy_mind import __main__ as sidecar
from baxy_mind import argument_grounding, operation_floor, plan_dependencies
from baxy_mind.semantic import messaging

SEND_SCHEMA = {
    "type": "object",
    "properties": {
        "recipientId": {"type": "string", "minLength": 1},
        "text": {"type": "string"},
    },
    "required": ["recipientId", "text"],
    "additionalProperties": False,
}

# turn_audit.jsonl de z1/t4 (request 57) y z2/t4 (request 60): la misma reformulación en las dos tandas.
RESTATED = "Manda a Ron92 en Discord: «si se conecta a las 9 pa jugar»."
# journal del Core, secuencia 7046 (z1): la identidad que resolvió el paso anterior.
RESOLVED = {
    "operation": "message.recipient.resolve",
    "verified": True,
    "status": "completed",
    "result": {
        "version": 1,
        "recipientId": "recipient_6820872f7ff447a8b9b375287851002f",
        "channel": "discord",
        "displayName": "Ron92",
        "verified": True,
    },
}


def _grounded_send(objective: str, observations: list[dict]) -> dict | None:
    """El paso message.send como lo responde el sidecar a ``plan.ground`` sin modelo, con sus mismas comprobaciones."""

    arguments = plan_dependencies._verified_message_send_arguments(objective, observations)
    if arguments is None:
        return None
    grounded = sidecar.normalize_grounded_arguments(
        arguments, SEND_SCHEMA, argument_grounding.trusted_plan_grounding_source(objective, observations),
    )
    if grounded is None:
        return None
    return argument_grounding._normalize_grounded_operation_arguments("message.send", grounded, objective)


def test_z1_t4_the_restated_send_takes_its_quoted_words_without_the_model() -> None:
    assert messaging.message_body(RESTATED) == "si se conecta a las 9 pa jugar"
    assert _grounded_send(RESTATED, [RESOLVED]) == {
        "recipientId": "recipient_6820872f7ff447a8b9b375287851002f",
        "text": "si se conecta a las 9 pa jugar",
    }


def test_contracases_the_quotes_never_invent_or_cut_a_body() -> None:
    # Sin palabras citadas ni separador no hay cuerpo: el paso sigue sin datos y se pregunta, nunca se inventa.
    assert messaging.message_body("Manda a Ron92 en Discord.") is None
    assert messaging.message_body("Manda a Ron92 en Discord: «».") is None
    assert _grounded_send("Manda a Ron92 en Discord.", [RESOLVED]) is None
    # Las palabras de la persona leídas por su propio lector conservan sus comillas interiores.
    assert messaging.message_body("dile a Ana que vi «Dune» anoche") == "vi «Dune» anoche"
    assert messaging.message_body("mandale a Ron92 que si se conecta a las 9 pa jugar") == (
        "si se conecta a las 9 pa jugar"
    )
    # Dos identidades resueltas: ningún destinatario es el verificado, aunque el cuerpo se lea.
    other = json.loads(json.dumps(RESOLVED))
    other["result"]["recipientId"] = "recipient_otro"
    assert _grounded_send(RESTATED, [RESOLVED, other]) is None
    # Sin la identidad verificada, tampoco.
    unverified = json.loads(json.dumps(RESOLVED))
    unverified["verified"] = False
    assert _grounded_send(RESTATED, [unverified]) is None


# compose_audit.jsonl de z2/t1, traza t21 (floor_first): la situación del envío que la persona interrumpió.
Z2_T1_SITUATION = json.loads(
    '{"kind": "failure", "polarity": "failure", "cause": "result_unverified", "step": 2, "pendingRequest": "mandale a '
    'Ron92 por discord que hoy no llego a jugar, que arranquen sin mi", "effectUncertain": true, "verified": false, '
    '"pending": true, "canRepeat": false, "evidenceRetained": true, "steps": ["{\\"kind\\":\\"operation\\",\\"operation'
    '\\":\\"message.recipient.resolve\\",\\"polarity\\":\\"success\\",\\"verified\\":true,\\"succeeded\\":true,\\"'
    'observed\\":{\\"version\\":1,\\"recipientId\\":\\"recipient_83078650b39046bd9ed161520a15bdc8\\",\\"channel\\":\\"'
    'discord\\",\\"displayName\\":\\"Ron92\\",\\"verified\\":true},\\"readOnly\\":true}"], "reason": {"kind": '
    '"operation", "operation": "message.send", "polarity": "failure", "verified": false, "succeeded": false, '
    '"effectUncertain": true, "attempted": {"text": "hoy no llego a jugar, que arranquen sin mi"}, "target": "Ron92"}}'
)


def test_z2_t1_a_send_the_person_interrupted_is_never_told_as_sent() -> None:
    assert messaging.verified_send(Z2_T1_SITUATION) is False
    final = operation_floor.floor_final(Z2_T1_SITUATION, False, datetime(2026, 10, 14, 15, 4, 30, tzinfo=timezone.utc))
    assert final == (
        "Intenté enviar el mensaje a «Ron92»: «hoy no llego a jugar, que arranquen sin mi», "
        "pero no pude confirmar si se hizo."
    )


def test_contracase_the_same_send_verified_is_told_as_sent() -> None:
    sent = {
        "kind": "operation", "operation": "message.send", "polarity": "success", "verified": True, "succeeded": True,
        "observed": {"channel": "discord", "displayName": "Ron92", "delivery": "visible_postcondition"},
    }
    assert messaging.verified_send(sent) is True
