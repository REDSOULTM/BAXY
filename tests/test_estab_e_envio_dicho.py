"""Encargo E (estabilización): el envío hecho se dice como envío, y por quien lo hizo.

Banco i1 (fable/estab-fase3 d5b314e30, bypass), caso c6: «en Discord abrí el chat con Ron92, escribí "prueba BAXY C6" y
mandalo» y luego «sí». El journal del Core prueba un envío (compositor con «prueba BAXY C6», un Enter, compositor vacío).
Finales publicados: «Escribí "prueba BAXY C6" en el chat con Ron92 en Discord.» (el modelo, etapa «first»: calla el
envío) y, al «sí», «Sí, lo enviaste.» (la charla atribuye el envío a la persona). En fix2 el mismo caso dijo «…y lo
envié.»: la frase dependía del modelo, porque el suelo de la misión no sabía decir la parte «enviar» (caía en la rama
de «calcular» y devolvía nada). Imp3 (04:40, f2914ef3c): lo mismo en WhatsApp («Llegué a Música y escribí prueba BAXY
imp.», enviado una vez según el journal) y, en Normal, la pregunta «¿Quieres confirmar que envíes el mensaje…?».
Evidencia: cu-v3/evidencia_i1/v2-c6, cu-v3/evidencia_imp3/v2-imp-wa-enviar{,-normal} (compose_audit, journal-caso).
"""

from __future__ import annotations

import copy
import json

import pytest

from baxy_mind import computer_use_finals, deterministic_finals, operation_floor
from baxy_mind.semantic import dialogue, messaging, missions
from baxy_mind.turn_decide import _prepare_turn_result
from baxy_mind.visible_defect import compose_visible_defect

C6_REQUEST = 'en Discord abrí el chat con Ron92, escribí "prueba BAXY C6" y mandalo'
C6_NUMBERS = ["@Ron92", "Ron92 (mensaje directo)", "Ron92 .wolfsoultm.4191"]
SENT_TERM = "stepDone:input.key.press:enter&sent:prueba baxy c6"
# compose_audit.jsonl de evidencia_i1/v2-c6 (turno 1): la situación que redactó el modelo, con sus campos de llegada.
C6 = {
    "kind": "operation", "operation": "mission.computer.use", "polarity": "success", "verified": True,
    "succeeded": True,
    "observed": {
        "goal": "ir a ron92; luego escribir prueba BAXY C6; luego enviar", "application": "Discord", "reached": True,
        "stepCount": 2,
        "steps": [
            {"step": 1, "operation": "input.text.type", "source": "model", "typedOn": "Discord", "into": "@Ron92",
             "intoDocument": True, "atCaret": True, "subgoal": 1, "text": "prueba BAXY C6", "ok": True,
             "method": "keyboard", "changed": True, "appeared": []},
            {"step": 2, "operation": "input.key.press", "source": "model", "process": "Discord", "rule": True,
             "subgoal": 2, "key": "enter", "target": "message_composer", "ok": True, "method": "keyboard",
             "changed": True, "appeared": []},
        ],
        "window": {"title": "@Ron92 - Discord", "process": "Discord", "requested": True, "foreground": True,
                   "focused": {"kind": "Edit", "name": "Mensaje @Ron92", "value": "﻿", "i": 47}},
        "joined": False,
        "screen": {"title": "@Ron92 - Discord", "values": [
            {"name": "Ron92 (mensaje directo)", "value": "https://discord.com/channels/@me/788990433829060618"},
            {"name": "@Ron92", "value": "https://discord.com/channels/@me/788990433829060618"},
            {"name": "Mensajes directos", "state": "selected"},
            {"name": "Amigos", "value": "https://discord.com/channels/@me"},
        ], "numbers": C6_NUMBERS},
        "satisfiedBy": SENT_TERM,
        "subgoals": [
            {"goal": "ir a ron92", "application": "Discord", "reached": True, "stepCount": 0,
             "satisfiedBy": "title:ron92", "successCheck": "control:ron92:current|title:ron92|page:ron92|mark:ron92",
             "numbers": C6_NUMBERS, "acted": False},
            {"goal": "escribir prueba BAXY C6", "application": "Discord", "reached": True, "stepCount": 1,
             "satisfiedBy": missions.WRITTEN_CHECK, "successCheck": missions.WRITTEN_CHECK, "numbers": C6_NUMBERS,
             "acted": True},
            {"goal": "enviar", "application": "Discord", "reached": True, "stepCount": 1, "satisfiedBy": SENT_TERM,
             "successCheck": "stepDone:input.key.press:enter&sent:prueba BAXY C6", "acted": True},
        ],
    },
}
C6_SAID = "Listo, le mandé «prueba BAXY C6» a «Ron92» por «Discord»."
C6_SAID_EN = "Done, I sent «prueba BAXY C6» to «Ron92» on «Discord»."
# Los dos finales medidos en i1 y el de fix2.
MEASURED_SILENT = 'Escribí "prueba BAXY C6" en el chat con Ron92 en Discord.'
MEASURED_FIX2 = 'Llegué a Discord con Ron92, escribí "prueba BAXY C6" y lo envié.'

# evidencia_imp3/v2-imp-wa-enviar: el clic que abrió el grupo leyó «Música» (arrivedAs), un Enter, compositor vacío.
WA_TERM = "stepDone:input.key.press:enter&sent:prueba BAXY imp"
WA = {
    "kind": "operation", "operation": "mission.computer.use", "polarity": "success", "verified": True,
    "succeeded": True,
    "observed": {
        "goal": "ir a musica; luego escribir prueba BAXY imp; luego enviar", "application": "WhatsApp",
        "reached": True, "stepCount": 4,
        "steps": [
            {"step": 1, "operation": "input.visible.click", "subgoal": 0, "label": "musica", "ok": False,
             "error": "visible_button_not_found"},
            {"step": 2, "operation": "input.visible.click", "subgoal": 0, "label": "Música 29/9/2026", "ok": True,
             "name": "Música 29/9/2026", "kind": "DataItem", "changed": True},
            {"step": 3, "operation": "input.text.type", "subgoal": 1, "into": "Escribir un mensaje para el grupo Música",
             "atCaret": True, "text": "prueba BAXY imp", "ok": True, "method": "keyboard", "changed": True},
            {"step": 4, "operation": "input.key.press", "subgoal": 2, "key": "enter", "target": "message_composer",
             "ok": True, "method": "keyboard", "changed": True},
        ],
        "window": {"title": "(5) WhatsApp", "process": "msedgewebview2"},
        "joined": False,
        "screen": {"title": "(5) WhatsApp", "values": [{"name": "Chats", "state": "on"}]},
        "satisfiedBy": WA_TERM,
        "subgoals": [
            {"goal": "ir a musica", "application": "WhatsApp", "reached": True, "arrivedAs": "Música",
             "satisfiedBy": "page:musica",
             "acted": True},
            {"goal": "escribir prueba BAXY imp", "application": "WhatsApp", "reached": True,
             "satisfiedBy": missions.WRITTEN_CHECK, "acted": True},
            {"goal": "enviar", "application": "WhatsApp", "reached": True, "satisfiedBy": WA_TERM, "acted": True},
        ],
    },
}


def _with(observed_change: dict) -> dict:
    situation = copy.deepcopy(C6)
    situation["observed"].update(observed_change)
    return situation


def _unsent() -> dict:
    """«enviar» did not hold: the App saw nothing sent (contracase)."""

    situation = copy.deepcopy(C6)
    situation.update({"polarity": "failure", "verified": False, "succeeded": False, "cause": "mission_failed"})
    situation["observed"]["reached"] = False
    situation["observed"]["subgoals"][2].update({"reached": False, "satisfiedBy": ""})
    return situation


# ------------------------------------------------------------------------------------------ the floor says the send
def test_the_c6_send_is_said_by_the_floor_as_a_send() -> None:
    assert computer_use_finals._computer_use_floor_first(C6, "es") == C6_SAID
    assert computer_use_finals._computer_use_floor_first(C6, "en") == C6_SAID_EN
    assert deterministic_finals._deterministic_final(C6, {}, "", "es") == C6_SAID


def test_the_whatsapp_send_is_said_by_the_floor_as_a_send() -> None:
    said = "Listo, le mandé «prueba BAXY imp» a «Música» por «WhatsApp»."
    assert computer_use_finals._computer_use_floor_first(WA, "es") == said


def test_the_text_seen_sent_reads_only_from_the_held_atom() -> None:
    assert messaging.proven_sent(SENT_TERM) == "prueba baxy c6"
    assert messaging.proven_sent(missions.SEND_CHECK) == ""
    assert messaging.proven_sent("stepDone:input.key.press:enter|sent:hola") == ""
    assert messaging.verified_send(C6) and messaging.verified_send(WA)
    # The mission reader writes the atom the floor reads.
    request = missions.mission_request("en Discord andá a Ron92, escribí prueba BAXY C6 y mandalo", ("Discord",))
    assert request is not None
    assert messaging.proven_sent(request.steps[-1].success_check) == "prueba baxy c6"


@pytest.mark.parametrize("change", [
    # «enviar» held on the Enter alone (a text with «&» rides no atom): no send proven, the model words it.
    {"subgoals": [*C6["observed"]["subgoals"][:2], {**C6["observed"]["subgoals"][2], "satisfiedBy": missions.SEND_CHECK}]},
    # The text seen sent is not the one typed.
    {"subgoals": [*C6["observed"]["subgoals"][:2],
                  {**C6["observed"]["subgoals"][2], "satisfiedBy": "stepDone:input.key.press:enter&sent:otra cosa"}]},
])
def test_a_send_not_proven_is_never_said_sent_by_the_floor(change: dict) -> None:
    assert computer_use_finals._computer_use_floor_first(_with(change), "es") == ""


def test_a_typed_text_without_a_send_part_stays_typed() -> None:
    typed = _with({"goal": "ir a ron92; luego escribir prueba BAXY C6",
                   "subgoals": C6["observed"]["subgoals"][:2], "satisfiedBy": missions.WRITTEN_CHECK})
    said = deterministic_finals._deterministic_final(typed, {}, "", "es")
    assert "escribí «prueba BAXY C6»" in said and "mand" not in said
    assert not messaging.verified_send(typed)


def test_a_send_not_done_is_said_not_done() -> None:
    said = deterministic_finals._deterministic_final(_unsent(), {}, "", "es")
    assert said.startswith("No pude") and "mandé" not in said and "envié" not in said
    assert not messaging.verified_send(_unsent())


def test_a_chat_place_is_spelled_without_its_sigil_and_only_then() -> None:
    gone = _with({"goal": "ir a ron92", "subgoals": [], "satisfiedBy": "title:ron92", "steps": []})
    assert "«Ron92»" in deterministic_finals._deterministic_final(gone, {}, "", "es")
    plain = copy.deepcopy(gone)
    plain["observed"]["screen"]["values"] = [{"name": "Ron92x"}]
    plain["observed"]["screen"]["numbers"] = []
    plain["observed"]["window"]["title"] = "Discord"
    assert "«Ron92»" not in deterministic_finals._deterministic_final(plain, {}, "", "es")


# ------------------------------------------------------------------------- the gate: a send final that omits it
@pytest.mark.parametrize("draft", [MEASURED_SILENT, "Listo, escribí «prueba BAXY C6» en Discord."])
def test_a_mission_final_that_omits_the_verified_send_is_not_published(draft: str) -> None:
    facts = {"situation": json.dumps(C6, ensure_ascii=False)}
    assert compose_visible_defect(draft, "status", C6_REQUEST, facts) == "send_not_stated"


def test_a_send_told_as_the_persons_is_not_published() -> None:
    facts = {"situation": json.dumps(C6, ensure_ascii=False)}
    # «lo enviaste» names no send of BAXY's; the act given to the person is refused before (its own veto).
    assert compose_visible_defect("Sí, lo enviaste.", "status", C6_REQUEST, facts) in {
        "action_attributed_to_user", "send_not_stated"}


@pytest.mark.parametrize("draft", [MEASURED_FIX2, C6_SAID])
def test_a_mission_final_that_says_the_send_is_not_refused_for_it(draft: str) -> None:
    facts = {"situation": json.dumps(C6, ensure_ascii=False)}
    assert compose_visible_defect(draft, "status", C6_REQUEST, facts) != "send_not_stated"


def test_the_gate_is_no_gate_where_nothing_was_sent() -> None:
    for situation in (_unsent(), _with({"subgoals": [*C6["observed"]["subgoals"][:2],
                                                     {**C6["observed"]["subgoals"][2], "satisfiedBy": missions.SEND_CHECK}]})):
        facts = {"situation": json.dumps(situation, ensure_ascii=False)}
        assert compose_visible_defect(MEASURED_SILENT, "status", C6_REQUEST, facts) != "send_not_stated"
    draft = {"kind": "operation", "operation": "message.draft", "polarity": "success", "verified": True,
             "succeeded": True, "observed": {"recipient": "Ron92", "channel": "discord"}}
    assert not messaging.verified_send(draft)


def test_a_typed_send_operation_keeps_its_told_verbs() -> None:
    # MAIL1859: over a send operation «le escribí» states the delivery; only a mission's «escribí» is its typing part.
    send = {"kind": "operation", "operation": "message.send", "polarity": "success", "verified": True,
            "succeeded": True, "observed": {"recipient": "Ron92", "channel": "discord"}}
    facts = {"situation": json.dumps(send, ensure_ascii=False)}
    request = "mandale a Ron92 por discord que hola"
    assert compose_visible_defect("Le escribí «hola» a Ron92 en Discord.", "status", request, facts) != "send_not_stated"
    assert compose_visible_defect("Hola Ron92.", "status", request, facts) == "send_not_stated"


# ------------------------------------------------------------------------------------ «sí» after the send done
def _told_state(situation: dict, final: str) -> dialogue.DialogueState:
    state = dialogue.DialogueState()
    state.expect(C6_REQUEST, ["mission.computer.use"])
    state.record(situation)
    state.told(situation, final)
    return state


def _history(final: str, said: str) -> list[dict]:
    return [{"role": "user", "content": C6_REQUEST}, {"role": "assistant", "content": final},
            {"role": "user", "content": said}]


@pytest.mark.parametrize("said", ["sí", "Sí", "dale", "ok", "sí, mandalo", "yes"])
def test_a_yes_after_the_send_told_is_answered_as_done_by_baxy(said: str) -> None:
    state = _told_state(C6, C6_SAID)
    assert state.yes_after_a_send(said, _history(C6_SAID, said))
    result = _prepare_turn_result(
        {"id": "11", "text": said, "history": _history(C6_SAID, said)},
        llm=None, planner_catalog=None, encoder=None, tool_by_name={}, dialogue_state=state,
    )
    english = said == "yes"
    assert result["kind"] == "conversation" and not result["effectOperations"]
    assert result["reply"] == ("I already sent it." if english else "Ya lo envié.")
    assert result["reply"] == messaging.send_said("already_sent", english)


@pytest.mark.parametrize("said", ["no", "¿sí?", "bueno...", "ya", "qué hora es", "mandale otro"])
def test_anything_but_a_whole_yes_is_read_as_before(said: str) -> None:
    assert not _told_state(C6, C6_SAID).yes_after_a_send(said, _history(C6_SAID, said))


def test_a_yes_after_no_send_is_read_as_before() -> None:
    # The send not done (F: said as not done or unconfirmed), a draft left written (B2: its offer has its own yes), a
    # question asked last: nothing of «ya lo envié».
    unsent = _told_state(_unsent(), "No pude enviar el mensaje.")
    assert not unsent.yes_after_a_send("sí", _history("No pude enviar el mensaje.", "sí"))
    draft = {"kind": "operation", "operation": "message.draft", "polarity": "success", "verified": True,
             "succeeded": True, "observed": {}}
    written = _told_state(draft, "Dejé escrito «hola» para Ron92 en Discord.")
    assert not written.yes_after_a_send("sí", _history("Dejé escrito «hola» para Ron92 en Discord.", "sí"))
    asked = _told_state(C6, C6_SAID)
    assert not asked.yes_after_a_send("sí", _history(C6_SAID + " ¿Algo más?", "sí"))


def test_the_yes_reads_only_the_turn_right_after_the_send() -> None:
    state = _told_state(C6, C6_SAID)
    state.expect("sí", [])
    state.said("Ya lo envié.")
    assert not state.yes_after_a_send("sí", _history("Ya lo envié.", "sí"))
    other = _told_state(C6, C6_SAID)
    other.expect("abre la calculadora", ["app.open"])
    assert not other.yes_after_a_send("sí", _history(C6_SAID, "sí"))


def test_a_typed_send_verified_counts_too() -> None:
    # WhatsApp by the typed route: message.send verified, said first by the floor (F); a «sí» after it.
    send = {"kind": "operation", "operation": "message.send", "polarity": "success", "verified": True,
            "succeeded": True, "observed": {"recipient": "Música", "channel": "whatsapp"}}
    final = "Envié el mensaje a «Música» en WhatsApp."
    state = dialogue.DialogueState()
    state.expect('en WhatsApp mandale a Música "prueba BAXY imp"', ["message.recipient.resolve", "message.send"])
    state.told(send, final)
    assert state.yes_after_a_send("sí", _history(final, "sí"))


# --------------------------------------------------------------------- Normal: the confirmation is BAXY's send
# evidencia_imp3/v2-imp-wa-enviar-normal: the pending Enter towards the message box.
PENDING_SEND = {
    "kind": "confirmation", "polarity": "pending", "cause": "step_needs_confirmation",
    "choices": ["confirmar", "confirm", "cancelar", "cancel"], "step": 1,
    "pendingRequest": 'en WhatsApp mandale a Música "prueba BAXY imp"',
    "pendingAction": {"operation": "input.key.press", "purpose": "Cumplir exactamente el efecto solicitado.",
                      "arguments": {"key": "enter", "target": "message_composer", "window": 8129610}},
}


def test_the_confirmation_of_the_send_asks_for_baxys_own_send() -> None:
    assert operation_floor.tells_first(PENDING_SEND)
    assert operation_floor.pending_final(PENDING_SEND, False) == "¿Quieres confirmar que envíe el mensaje o cancelar?"
    assert operation_floor.pending_final(PENDING_SEND, True) == "Do you want to confirm that I send the message, or cancel?"


def test_another_pending_key_keeps_its_draft() -> None:
    other = copy.deepcopy(PENDING_SEND)
    other["pendingAction"]["arguments"] = {"key": "enter", "target": "overwrite_confirm"}
    assert operation_floor.pending_final(other, False) == ""
    assert not operation_floor.tells_first(other)
