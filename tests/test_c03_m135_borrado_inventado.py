"""M135 (2026-10-03, DEV-F v4i/v4k/v4m F-w47-t2): a report that says something was deleted when its operation deletes
nothing is refused (``report_claims_a_deletion``) and composed again.

The recorded draft and payload are DEV-F's (window/v4m-devF/compose-audit.jsonl, trace t229): a WhatsApp draft left
unverified was told «Se borró el borrador…», the same in three rounds.
"""

from __future__ import annotations

from baxy_mind import llm

DRAFT = (
    "Se borró el borrador para mi contacto en WhatsApp con el mensaje de que me viene genial, pero no se confirmó si "
    "se envió."
)
PAYLOAD = {
    "outcome": "failed",
    "reason": {
        "target": "mi contacto",
        "attempted": {"channel": "whatsapp", "recipient": "mi contacto", "text": "Sí, que me viene genial."},
        "outcome": "unverified",
        "effect": "unknown",
        "cause": "it was attempted, but afterwards it could not be confirmed whether it took effect",
        "operation": "message.draft",
    },
}


def test_f_w47_t2_an_unverified_draft_is_not_told_as_deleted() -> None:
    assert llm._report_claims_a_deletion(DRAFT, PAYLOAD)
    assert llm._payload_fact_defect(DRAFT, PAYLOAD, "Contéstale por WhatsApp que sí, déjalo sin enviar") == (
        "report_claims_a_deletion"
    )
    for honest in (
        "Intenté dejar el borrador para tu contacto en WhatsApp, pero no pude confirmar que quedó escrito.",
        "No se borró nada: el borrador quizá quedó escrito en WhatsApp; revísalo.",
        "I tried to leave the draft in WhatsApp but couldn't confirm it was written.",
    ):
        assert not llm._report_claims_a_deletion(honest, PAYLOAD), honest


def test_a_deleting_operation_or_a_plan_may_say_it_deleted() -> None:
    trashed = {"operation": "filesystem.trash.commit", "seen": {"name": "notas.txt"}}
    assert not llm._report_claims_a_deletion("Se eliminó notas.txt a la papelera.", trashed)
    cancelled = {"operation": "notification.cancel.at", "seen": {"title": "gym"}}
    assert not llm._report_claims_a_deletion("I deleted the gym alarm.", cancelled)
    plan = {"completedStepsInOrder": [{"operation": "task.delete"}], "operation": "task.list"}
    assert not llm._report_claims_a_deletion("He borrado «chips» de tu lista.", plan)


def test_other_reports_claiming_a_deletion() -> None:
    note = {"operation": "note.create", "seen": {"title": "viaje"}}
    assert llm._report_claims_a_deletion("He borrado la nota anterior y guardé «viaje».", note)
    assert llm._report_claims_a_deletion("The old draft was deleted.", {"operation": "message.draft", "seen": {}})
