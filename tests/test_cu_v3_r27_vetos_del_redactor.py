"""Ronda 27 (libro de cuentas del redactor, 988 episodios): los vetos de saldo negativo se retiran o se estrechan.

Cada caso es un borrador vetado de las tandas, palabra por palabra, que era verdadero según su recibo: ahora se
publica. Cada contracaso es lo que el veto debe seguir parando.
"""

from __future__ import annotations

import pytest

from baxy_mind import deterministic_finals
from baxy_mind import operation_floor
from baxy_mind import payload_fact_checks
from baxy_mind import visible_defect
from baxy_mind.semantic import claims

# ---------------------------------------------------------------- 1. el texto copiado al portapapeles no es una afirmación

COPY = "copia al portapapeles esto: reunion jueves 15:00 sala 3"
COPIED = {
    "kind": "operation", "operation": "clipboard.write.text", "polarity": "success", "verified": True,
    "succeeded": True, "observed": {"sequenceNumber": 617, "characterCount": 27, "changed": True},
}
COPIED_PAYLOAD = {
    "seen": {"sequenceNumber": 617, "characterCount": 27, "changed": True, "writtenText": "reunion jueves 15:00 sala 3"},
    "operation": "clipboard.write.text",
}


@pytest.mark.parametrize(
    "draft",
    [
        # r17/r20/r23/r23q/v3b1 t2-c17, first and retry drafts (24 vetoes; the final was «Puse el texto en el portapapeles.»).
        'He copiado al portapapeles: "reunion jueves 15:00 sala 3".',
        'He copiado al portapapeles el texto: "reunion jueves 15:00 sala 3".',
        'La frase "reunion jueves 15:00 sala 3" se ha copiado al portapapeles.',
    ],
)
def test_the_clock_inside_the_text_copied_is_the_texts(draft: str) -> None:
    assert visible_defect.compose_visible_defect(draft, "status", COPY, {"situation": COPIED}) == ""
    assert payload_fact_checks._payload_fact_defect(draft, COPIED_PAYLOAD, COPY) == ""


def test_contracase_a_clock_the_copied_text_does_not_carry_is_still_a_claim() -> None:
    told = 'He copiado al portapapeles: "reunion jueves 15:00 sala 3" y te aviso a las 14:45.'
    assert visible_defect.compose_visible_defect(told, "status", COPY, {"situation": COPIED}) == "extra_claim"
    # And the final that leaves the text out is still refused by the clipboard's own check.
    assert payload_fact_checks._payload_fact_defect("Listo, ya quedó copiado.", COPIED_PAYLOAD, COPY) == "missing_written_text"


DRAFT_ASKED = "mandale a Ron92 que si se conecta a las 9 pa jugar"
DRAFTED = {
    "kind": "operation", "operation": "message.draft", "polarity": "success", "verified": True, "succeeded": True,
    "observed": {
        "version": 1, "channel": "discord", "displayName": "Ron92", "text": "¿Te conectas a las 9 para jugar?",
        "draftVisible": True, "sent": False, "clientOpened": False,
        "authority": "desktop_client_composer_ocr_postread",
    },
}


@pytest.mark.parametrize(
    "told",
    [
        # Revisión 2 de r27u (ep 158, sent false): a message never sent told as arrived. The text of a message for
        # someone else is never masked, so the question it quotes keeps stopping these as in v3.
        "Ya le llegó a Ron92 el mensaje «¿Te conectas a las 9 para jugar?».",
        "Listo, Ron92 ya tiene tu mensaje: «¿Te conectas a las 9 para jugar?».",
        "Ron92 ya recibió «¿Te conectas a las 9 para jugar?» en Discord.",
        "Mensaje mandado a Ron92: «¿Te conectas a las 9 para jugar?».",
        "Le pregunté a Ron92 por Discord: «¿Te conectas a las 9 para jugar?».",
        "Le escribí a Ron92 por Discord: «¿Te conectas a las 9 para jugar?».",
        "Ron92 ya puede leer «¿Te conectas a las 9 para jugar?» en Discord.",
        "¿Te conectas a las 9 para jugar?",
        "Dejé escrito el mensaje para Ron92 en Discord, pero no lo envié. ¿Quieres que lo mande ahora?",
    ],
)
def test_a_message_never_sent_is_not_told_as_arrived(told: str) -> None:
    assert visible_defect.compose_visible_defect(told, "status", DRAFT_ASKED, {"situation": DRAFTED}) == "extra_claim"


@pytest.mark.parametrize(
    "told",
    [
        "Ron92 got your message: «Are you on at 9 to play?».",
        "I messaged Ron92 on Discord: «Are you on at 9 to play?».",
        "I texted Ron92 «Are you on at 9 to play?» on Discord.",
        "Your message «Are you on at 9 to play?» reached Ron92.",
        "I asked Ron92 on Discord: «Are you on at 9 to play?».",
    ],
)
def test_a_message_never_sent_is_not_told_as_arrived_in_english(told: str) -> None:
    asked = "message Ron92 and ask if he is on at 9 to play"
    drafted = {**DRAFTED, "observed": {**DRAFTED["observed"], "text": "Are you on at 9 to play?"}}
    assert visible_defect.compose_visible_defect(told, "status", asked, {"situation": drafted}) != ""


# ---------------------------------------------------------------- 2. la repetición tras una corrección

BRIGHTNESS = "joder que te he dicho brillo no volumen"
NOT_CONFIRMED = "No se pudo confirmar que el brillo esté al 40 porque no se verificó si el cambio tuvo efecto."


@pytest.mark.parametrize(
    ("intent", "kind", "last"),
    [
        # v3b1 t4-c04 t2 (ep 191), r20 t4-c04 t2 (ep 65), r23_redpc t2-c03 t3 (ep 115) and the volume twin.
        ("error", "failure", NOT_CONFIRMED),
        ("status", "operation", "He puesto el brillo al 40."),
        ("confirmation", "confirmation", "¿Quieres confirmar que cierre la configuración o cancelar la acción?"),
        ("status", "operation", "Puse el volumen al 40."),
    ],
)
def test_after_a_correction_the_last_final_is_never_told_again_whatever_the_turn(intent: str, kind: str, last: str) -> None:
    """The goal's «cero respuestas idénticas repetidas tras una corrección»."""

    situation = {"kind": kind, "polarity": "success", "correctedFinal": {"previousReply": last}}
    assert visible_defect.compose_visible_defect(last, intent, BRIGHTNESS, {"situation": situation}, said=BRIGHTNESS) == (
        "repeats_last_answer"
    )


def test_the_held_fact_is_said_by_its_sentence_never_as_a_repeat() -> None:
    # r23 t4-c04 t2 (ep 101, two vetoes of a true draft). Encargo TZ-HOLD rewrote this (a held target's draft that
    # named what was left untouched was exempt from the repeat check): a held target is never drafted, its sentence
    # (data «heldFact.target») is the final and is no repeat; judged as any reply after a correction, the held fact
    # word for word, with or without a tail, is the last answer again.
    held = {"kind": "target", "named": "brillo", "untouched": "volumen", "previousReply": "El brillo ya estaba al 40."}
    talk = {"situation": {"kind": "conversation", "polarity": "success", "alreadyHolds": held},
            "context": "El brillo ya estaba al 40."}
    final = deterministic_finals._held_fact_final(talk["situation"], "es")
    assert final == "Lo que te dije era de «brillo»; «volumen» no lo toqué."
    assert visible_defect.compose_visible_defect(final, "conversation", BRIGHTNESS, talk, said=BRIGHTNESS) == ""
    for draft in ("El brillo ya estaba al 40.", "El brillo ya estaba al 40, sin tocar el volumen."):
        assert visible_defect.compose_visible_defect(
            draft, "conversation", BRIGHTNESS, talk, said=BRIGHTNESS,
        ) == "repeats_last_answer"


def test_a_repeat_goes_to_the_results_own_sentence_without_another_draft() -> None:
    assert claims.template_suffices("repeats_last_answer", "audio.volume.set")


# ---------------------------------------------------------------- 3. la reserva dice la causa del portapapeles vacío

def test_the_floor_of_an_empty_clipboard_says_its_cause() -> None:
    # v3b1 t1-c15 «que tengo copiado?»: three true drafts vetoed and the floor said only «No pude leer el portapapeles.».
    situation = {
        "kind": "failure", "polarity": "failure", "cause": "mission_failed", "stepCount": 0, "steps": [],
        "reason": {"kind": "operation", "operation": "clipboard.read.text", "polarity": "failure", "verified": False,
                   "succeeded": False, "error": "clipboard_has_no_text"},
    }
    assert operation_floor.failure_family_cause("clipboard_has_no_text", False) == "no hay texto en él"
    plain = operation_floor.floor_final(situation, False)
    assert plain and operation_floor.with_family_cause(plain, situation, False) == plain[:-1] + ", porque no hay texto en él."
    # Contracaso: a code that only shares words with the family says no cause.
    assert operation_floor.failure_family_cause("screen_has_no_text_field", False) == ""
