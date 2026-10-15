"""Estabilización F3 (banco h1, caso c6, modo bypass): un «sí» sin nada pendiente no afirma ningún efecto.

Turno 1: «en Discord abrí el chat con Ron92, escribí "prueba BAXY C6" y mandalo» → computer use falló al teclear
(``input_field_not_reachable``: el Cambio rápido de Discord tapaba el compositor) y BAXY lo dijo. Turno 2: «sí» → el
decisor habló (talk) y el redactor de conversación publicó «Sí, el mensaje "prueba BAXY C6" ya fue enviado en el chat
con Ron92.» sin ningún acto: falso éxito (juez A de bancoB_h1). Evidencia: ``cu-v3/evidencia_h1/v2-c6``
(compose_audit.jsonl del turno 1, raw_replies.jsonl del turno 2).

La causa está en la lectura: M88 ya trataba un «adelante» tras una respuesta que no preguntaba nada (nada esperaba ese
sí: el redactor oye que no se ejecutó nada y su respuesta debe decir que no se hizo), pero un «sí» a secas no contaba
como tal. Ahora cuenta cuando la última respuesta de BAXY dijo un acto que no llegó a hacer. Y la pasiva «ya fue
enviado» es un efecto afirmado más en la lectura de conversación (``visible_reply_claims_an_effect``).
"""

from __future__ import annotations

import copy
import json

import pytest

from baxy_mind import llm
from baxy_mind.reply_claims import visible_reply_claims_an_effect
from baxy_mind.visible_defect import compose_visible_defect
from baxy_mind.semantic import dialogue

# compose_audit.jsonl de v2-c6, turno 1: el final publicado.
LAST = ("No pude escribir ni enviar el mensaje en Discord porque la pantalla no mostraba el campo para escribir. "
        "Llegué a la ventana de Ron92, pero ahí me detuve.")
# raw_replies.jsonl de v2-c6, turno 2: la respuesta publicada.
MEASURED = 'Sí, el mensaje "prueba BAXY C6" ya fue enviado en el chat con Ron92.'
REQUEST = 'en Discord abrí el chat con Ron92, escribí "prueba BAXY C6" y mandalo'
HONEST = "Todavía no lo envié: la pantalla no mostraba el campo para escribir."
CONVERSATION = json.dumps({"kind": "conversation", "polarity": "success"})


class _Writer(llm.LlmRuntime):
    """The drafts stand in for the model, in order (the last one repeats); every payload sent is kept."""

    def __init__(self, drafts: list[str]) -> None:  # noqa: D107
        self._gguf = None
        self._drafts = list(drafts)
        self.sent: list[dict] = []

    def _post(self, payload, **_):  # noqa: ANN001, ANN201
        self.sent.append(copy.deepcopy(payload))
        content = self._drafts.pop(0) if len(self._drafts) > 1 else self._drafts[0]
        return {"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}


@pytest.mark.parametrize("said", ["sí", "Sí", "dale", "ok", "sí, dale"])
def test_a_bare_yes_after_an_act_not_done_has_nothing_waiting_for_it(said: str) -> None:
    assert dialogue.go_ahead_with_nothing_pending(said, LAST)


def test_the_measured_reply_is_refused_and_says_no_effect() -> None:
    facts = {"situation": CONVERSATION, "context": LAST, "priorRequests": [REQUEST]}
    assert compose_visible_defect(MEASURED, "conversation", "sí", facts)
    assert visible_reply_claims_an_effect(MEASURED, "sí")
    assert compose_visible_defect(HONEST, "conversation", "sí", facts) == ""


def test_the_minds_conversation_reply_to_the_measured_yes_never_claims_the_send() -> None:
    history = [{"role": "user", "content": REQUEST}, {"role": "assistant", "content": LAST}]
    chat = _Writer([MEASURED, json.dumps({"answer": HONEST})])
    reply, _ = chat.chat("sí", history=history, conversation_kind="knowledge", response_language="es",
                         temperature=0.0)
    assert reply == HONEST
    first = "\n".join(str(message["content"]) for message in chat.sent[0]["messages"])
    assert "nada tuyo esperaba un sí" in first


# ------------------------------------------------------------------ contracases


@pytest.mark.parametrize("last", [
    "Mañana en Curicó habrá 18 grados y cielo despejado.",  # agreeing with what was said is talk
    "Envié el mensaje a «Ron92» en Discord.",  # nothing failed
    "No pude enviarlo: ¿quieres que lo intente otra vez?",  # a question: the yes answers it
])
def test_a_yes_after_anything_else_is_read_as_before(last: str) -> None:
    assert not dialogue.go_ahead_with_nothing_pending("sí", last)


def test_a_passive_of_history_is_no_effect_claimed() -> None:
    assert not visible_reply_claims_an_effect("La primera carta por correo aéreo fue enviada en 1911.", "")
    assert visible_reply_claims_an_effect("El mensaje ya fue enviado.", "")
