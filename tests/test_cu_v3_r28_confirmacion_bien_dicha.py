"""Ronda 28 (banco c7 t2): ningún turno acaba sin final. El «no» a la confirmación de un clic dio dos borradores
``asserted_failure``, no quedó tiempo para el tercero y la persona leyó la línea de composición fallida
(``no_response;retry_exhausted``). Un plan cancelado que ningún borrador pudo contar se dice desde sus hechos: lo que
se hizo antes, con su recibo, y el acto que no se hizo (datos ``cancelledFloor``). Desde la estabilización F lo dice el
suelo antes de cualquier borrador (orden del dueño 2026-10-11).

Los payloads son los de ``evidencia_cd/v2-{c7,s11,s14}/compose_audit.jsonl``.
"""

from __future__ import annotations

import copy
import json

import pytest

from baxy_mind import operation_floor
from baxy_mind import visible_defect
from baxy_mind.llm import LlmRuntime

C7 = "en Discord andá al canal Cotele y después en Steam andá a la tienda"
COTELE = {
    "operation": "input.visible.click", "purpose": "Cumplir exactamente el efecto solicitado.",
    "arguments": {"label": "Cotele!!!😎, Canal de voz, Choche", "index": 60, "window": 68208},
}
# compose_audit.jsonl of v2-c7, turn 2: the two drafts the mind refused.
C7_DRAFTS = [
    "No se pudo navegar a Discord ni a Steam porque la acción fue cancelada.",
    "El resultado fue cancelado y no se pudo acceder al canal Cotele en Discord ni a la tienda de Steam.",
]
RECIPIENT = "recipient_1deafb00c7314918b3fff70b4d3b9d08"
SEND = {
    "operation": "message.send", "purpose": 'mandale a Ron92 "prueba BAXY 14" en Discord',
    "arguments": {"recipientId": RECIPIENT, "text": "prueba BAXY 14"},
}
RESOLVED = {
    "kind": "operation", "operation": "message.recipient.resolve", "polarity": "success", "verified": True,
    "succeeded": True, "readOnly": True,
    "observed": {"version": 1, "recipientId": RECIPIENT, "channel": "discord", "displayName": "Ron92", "verified": True},
}
OPENED = {
    "kind": "operation", "operation": "app.open", "polarity": "success", "verified": True, "succeeded": True,
    "readOnly": False, "observed": {"application": "Discord"},
}


def _cancelled(request: str, action: dict, steps: list[object] | None = None) -> dict:
    return {
        "kind": "status", "polarity": "success", "cause": "remaining_steps_cancelled",
        "steps": [step if isinstance(step, str) else json.dumps(step, ensure_ascii=False) for step in steps or []],
        "cancelledRequest": request, "cancelledAction": action,
    }


class _Writer(LlmRuntime):
    """A writer that says the drafts given, in order, and then runs out of time."""

    def __init__(self, drafts: list[str]) -> None:
        self._gguf = None
        self.drafts = list(drafts)
        self.requests: list[dict] = []

    def _post(self, payload: dict, **_kwargs: object) -> dict:
        self.requests.append(copy.deepcopy(payload))
        if not self.drafts:
            raise TimeoutError("no queda presupuesto de la petición para otro borrador")
        return {"choices": [{"message": {"content": self.drafts.pop(0)}, "finish_reason": "stop"}]}


def _composed(writer: _Writer, situation: dict) -> str:
    return writer.compose_user_message("no", "status", {"situation": json.dumps(situation, ensure_ascii=False)})


def test_banco_c7_the_no_whose_drafts_were_refused_still_ends_with_a_final() -> None:
    situation = _cancelled(C7, COTELE)
    facts = {"situation": json.dumps(situation, ensure_ascii=False)}
    for draft in C7_DRAFTS:
        # Nothing failed: it was cancelled. The veto is right and stays.
        assert visible_defect.compose_visible_defect(draft, "status", "no", facts) == "asserted_failure"
    writer = _Writer(C7_DRAFTS)
    assert _composed(writer, situation) == (
        "No llegué a hacer clic en el botón «Cotele!!!😎» porque se canceló."
    )
    # Estabilización F: a cancelled plan is said from the floor before any draft; the model is not asked.
    assert len(writer.requests) == 0


def test_three_refused_drafts_end_the_same_way_and_a_writer_that_never_answers_too() -> None:
    expected = "No llegué a hacer clic en el botón «Cotele!!!😎» porque se canceló."
    assert _composed(_Writer([C7_DRAFTS[0], C7_DRAFTS[1], C7_DRAFTS[0]]), _cancelled(C7, COTELE)) == expected
    assert _composed(_Writer([]), _cancelled(C7, COTELE)) == expected


def test_banco_s11_the_floor_says_it_before_any_draft() -> None:
    # Estabilización F (owner, 2026-10-11): what the floor can say is not drafted, even a draft that would pass.
    good = "No he ido al canal Cotele en Discord porque la acción fue cancelada."
    writer = _Writer([good])
    assert _composed(writer, _cancelled("en Discord andá al canal Cotele", COTELE)) == (
        "No llegué a hacer clic en el botón «Cotele!!!😎» porque se canceló."
    )
    assert len(writer.requests) == 0


def test_what_was_made_before_the_cancellation_is_told_with_its_receipt() -> None:
    # Revisión de r28u, bloqueante 5: «Cancelado: no llegué a enviar… y no seguí con nada más.» hid the app opened.
    situation = _cancelled("abrí Discord y mandale a Ron92 hola", SEND, [OPENED, RESOLVED])
    assert operation_floor.cancelled_final(situation, False) == (
        "Abrí la aplicación «Discord», pero no llegué a enviar el mensaje a «Ron92» porque se canceló."
    )
    assert operation_floor.cancelled_final(situation, True) == (
        "I opened the app «Discord», but I didn't send the message to «Ron92» because it was cancelled."
    )


def test_banco_s14_the_send_not_made_names_who_it_was_for_and_never_quotes_its_text() -> None:
    situation = _cancelled('en Discord mandale a Ron92 "prueba BAXY 14"', SEND, [RESOLVED])
    told = operation_floor.cancelled_final(situation, False)
    assert told == "No llegué a enviar el mensaje a «Ron92» porque se canceló."
    # Nothing of the message's own words reaches the sentence, so no veto can read them as BAXY's claim.
    assert "prueba" not in told
    worded = {**SEND, "arguments": {"recipientId": RECIPIENT, "text": "no pude ir, falló el auto\nhttps://example.com/x steam.exe"}}
    assert operation_floor.cancelled_final({**situation, "cancelledAction": worded}, False) == told


def test_the_sentence_claims_nothing_about_the_rest_and_nothing_done() -> None:
    for situation in (_cancelled(C7, COTELE), _cancelled("mandale a Ron92 hola", SEND, [RESOLVED])):
        folded = operation_floor.cancelled_final(situation, False).casefold()
        assert "nada más" not in folded and "envié" not in folded and "hice clic" not in folded


@pytest.mark.parametrize(
    "situation",
    [
        # Another turn: a confirmation still pending, a cancelled memory, a result.
        {"kind": "confirmation", "polarity": "pending", "cause": "step_needs_confirmation", "pendingAction": SEND},
        {**_cancelled("guardá eso", SEND), "cause": "memory_cancelled"},
        {**OPENED},
        # An act of no operation of the data.
        _cancelled("hacé eso", {"operation": "no.such.operation", "arguments": {}}),
        # A step made that the floor cannot tell (prose, or an effect of an operation it does not know): saying only
        # the act not made would hide it.
        _cancelled("abrí Discord y mandale a Ron92 hola", SEND, ["Abrí Discord."]),
        _cancelled("hacé eso y mandale a Ron92 hola", SEND, [{**OPENED, "operation": "no.such.operation"}]),
    ],
)
def test_contracase_nothing_is_said_from_here(situation: dict) -> None:
    assert operation_floor.cancelled_final(situation, False) == ""


def test_contracase_an_identifier_no_step_observed_names_no_one() -> None:
    situation = _cancelled("mandale a Ron92 hola", SEND, [{**RESOLVED, "observed": {"recipientId": "recipient_other", "displayName": "Ana"}}])
    assert operation_floor.cancelled_final(situation, False) == "No llegué a enviar el mensaje porque se canceló."


def test_banco_s11_a_correction_over_the_cancelled_act_is_said_again_not_drafted() -> None:
    # Revisión F (H2): the cancelled floor would repeat the last answer; it is said as the same result, no draft.
    first = "No llegué a hacer clic en el botón «Cotele!!!😎» porque se canceló."
    situation = {**_cancelled("en Discord andá al canal Cotele", COTELE), "correctedFinal": {"previousReply": first}}
    writer = _Writer(["No he ido al canal Cotele en Discord porque la acción fue cancelada."])
    assert _composed(writer, situation) == "El resultado es el mismo. " + first
    assert writer.requests == []
