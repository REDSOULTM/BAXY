"""Encargo X1: «mandale a Ron92 por discord que hoy no llego a jugar, que arranquen sin mi» a veces envía y a veces no.

Tandas n1 y n2 en el notebook (fable/estab-fase3 9b7d8d757, bypass), t1-c09 t1, ruta tipada
``message.recipient.resolve`` → ``message.send`` en las dos. n2: el MD de Ron92 ya estaba abierto (lo dejó n1 t4-c03),
el título lo nombró, el resolve volvió en 0,2 s y el envío se verificó. n1: Discord en otra vista; la búsqueda pulsó la
primera fila a los 1,2 s fijos, antes de que el cliente filtrara, se abrió otro chat y el resolve volvió
``recipient_identity_not_verified`` con efecto incierto (8 s); nunca se llegó a ``message.send``. El arreglo está en el
proveedor (la fila se pulsa cuando el resultado activo nombra al destinatario, X1EnvioBusquedaTests.cs). Aquí se fijan
los dos payloads medidos (compose_audit.jsonl, trace t21): el fallo no dice un envío y el envío verificado se dice una
sola vez.
"""

from __future__ import annotations

import json

from baxy_mind import deterministic_finals

SAID = "mandale a Ron92 por discord que hoy no llego a jugar, que arranquen sin mi"

# tandas_n1_notebook/t1/compose_audit.jsonl:48
N1 = json.loads(
    '{"kind": "failure", "polarity": "failure", "cause": "mission_failed", "stepCount": 0, "steps": [], "reason": '
    '{"kind": "operation", "operation": "message.recipient.resolve", "polarity": "failure", "verified": false, '
    '"succeeded": false, "error": "recipient_identity_not_verified", "cause": "external_effect_ambiguous", '
    '"effectUncertain": true, "target": "Ron92", "attempted": {"channel": "discord", "recipient": "Ron92"}, '
    '"notDone": [{"operation": "message.send", "target": "Ron92"}]}}'
)

_RESOLVED = {
    "kind": "operation", "operation": "message.recipient.resolve", "polarity": "success", "verified": True,
    "succeeded": True, "readOnly": True,
    "observed": {"version": 1, "recipientId": "recipient_5a68f21757c04ae1bab428e13ba7a4b7", "channel": "discord",
                 "displayName": "Ron92", "verified": True},
}
_SENT = {
    "kind": "operation", "operation": "message.send", "polarity": "success", "verified": True, "succeeded": True,
    "readOnly": False,
    "observed": {"version": 1, "messageId": "message_7292a39c83c275d7799cbaee",
                 "recipientId": "recipient_5a68f21757c04ae1bab428e13ba7a4b7", "channel": "discord",
                 "displayName": "Ron92",
                 "contentSha256": "30b73ade4bac616bfc554310a4629e3754a54f7938484732d8fc08ad4bd32e3a",
                 "delivery": "visible_postcondition", "text": "hoy no llego a jugar, que arranquen sin mi"},
}
# tandas_n2_notebook/t1/compose_audit.jsonl:49 (los pasos llegan como texto JSON, como en la situación medida)
N2 = {
    "kind": "status", "polarity": "success", "cause": "mission_completed", "stepCount": 2,
    "steps": [json.dumps(_RESOLVED, separators=(",", ":")), json.dumps(_SENT, separators=(",", ":"))],
    "completedRequest": SAID,
}


def test_n1_the_search_that_did_not_reach_the_chat_never_says_a_send() -> None:
    said = deterministic_finals._deterministic_final(N1, {}, SAID, "es")
    assert said
    assert "envié" not in said.lower()
    assert "Ron92" in said


def test_n2_the_verified_send_is_said_once_with_its_text() -> None:
    said = deterministic_finals._deterministic_final(N2, {}, SAID, "es")
    assert said == "Envié el mensaje a «Ron92» en Discord: dice «hoy no llego a jugar, que arranquen sin mi»."
    # Contracaso «no duplicar el envío»: one message.send, told once.
    assert said.lower().count("envié") == 1
