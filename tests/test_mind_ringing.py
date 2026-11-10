"""ALR1 (owner, 2026-11-08: «Baxi, gracias… Baxi para la alarma»): what rings now in the App is a note of the turn, with
each alarm's or reminder's id, words and time, so the model answers it with schedule_alarms stop or snooze. The note is
only there while something rings, and never in the person's own message."""
from pathlib import Path

from baxy_mind.mind import RINGING_NOTE
from test_mind_final import _mind, _say
from test_mind_front_not_asked import _anticipation

ALARM = {"id": "89abcdef", "kind": "alarm", "title": "sal a trabajar", "clock": "07:00"}
REMINDER = {"id": "76543210", "kind": "reminder", "clock": "15:00"}


def test_what_rings_is_a_note_after_the_clock_and_never_in_the_persons_message(tmp_path: Path) -> None:
    mind, server = _mind(tmp_path, [_say("Listo."), _say("De nada."), _say("Hola.")])
    mind.decide(1, "gracias", None, None, None, None, [ALARM, REMINDER])
    messages = server.bodies[0]["messages"]
    assert messages[-1] == {"role": "user", "content": "gracias"}
    assert messages[-2]["content"] == RINGING_NOTE.format(
        rings="la alarma id 89abcdef «sal a trabajar» de las 07:00; el recordatorio id 76543210 de las 15:00",
        call="schedule_alarms")
    mind.decide(2, "hola")
    assert all("espera respuesta" not in str(m.get("content")) for m in server.bodies[2]["messages"][-3:])


def test_a_ring_with_no_id_is_not_told(tmp_path: Path) -> None:
    mind, server = _mind(tmp_path, [_say("Hola.")])
    mind.decide(1, "hola", None, None, None, None, [{"kind": "alarm", "title": "x"}])
    assert all("espera respuesta" not in str(m.get("content")) for m in server.bodies[0]["messages"])


def test_an_early_decision_made_without_the_note_is_decided_again() -> None:
    anticipation, put_back = _anticipation({"kind": "action"})
    message = {"type": "turn.decide", "id": 7, "text": "qué dice esto", "ringing": [ALARM]}
    assert anticipation.settle("turn.decide", message, 0.05) is None
    assert put_back == ["ringing"]


def test_words_with_something_ringing_and_nothing_answered_are_told_it_still_rings_once(tmp_path: Path) -> None:
    from baxy_mind.mind import RINGING_STILL_NOTE
    from test_mind_final import _call
    mind, server = _mind(tmp_path, [_say("Listo, la paré."), _call("schedule_alarms", {"action": "stop", "id": "89abcdef"})])
    result = mind.decide(1, "ya po", None, None, None, None, [ALARM])
    assert result["kind"] == "action" and result["arguments"] == {"action": "stop", "id": "89abcdef"}
    assert server.bodies[1]["messages"][-1]["content"] == RINGING_STILL_NOTE.format(
        rings="la alarma id 89abcdef «sal a trabajar» de las 07:00")


def test_words_after_the_ring_was_answered_or_with_nothing_ringing_are_spoken_as_they_are(tmp_path: Path) -> None:
    mind, server = _mind(tmp_path, [_say("Son las siete."), _say("Hola.")])
    assert mind.decide(1, "qué hora es")["reply"] == "Son las siete."
    assert len(server.bodies) == 1


def test_a_receipt_that_answered_one_of_several_said_in_own_words_is_not_told_that_nothing_was_answered(tmp_path: Path) -> None:
    # INT20 (blind review of ALR3): with no id the App answers every one ringing, and one it did not end in time leaves
    # the call failed; its rings say the other was stopped. «En este turno no se paró … nada» would be false then.
    import json

    from test_mind_final import _call
    mind, server = _mind(tmp_path, [_call("schedule_alarms", {"action": "stop"}),
                                    _say("Paré la alarma; el recordatorio sigue sonando.")])
    mind.configure({"capabilities": [{"name": "schedule.alarms", "description": "Alarms.", "risk": "low_reversible",
                                      "argumentsSchema": {"type": "object", "properties": {"action": {"type": "string"}}}}]})
    assert mind.decide(1, "ya está, me voy a la cocina", None, None, None, None, [ALARM, REMINDER])["kind"] == "action"
    rings = [{**ALARM, "stopped": True, "ringing": False}, {**REMINDER, "stopped": False, "ringing": True}]
    receipt = {"status": "failed", "error": "notification_ring_answer_unconfirmed",
               "observed": {"version": 1, "rings": rings, "authority": "baxy_app_ring_postread"}}
    result = mind.continue_turn(2, json.dumps(receipt))
    assert result["reply"] == "Paré la alarma; el recordatorio sigue sonando."
    assert all("no se paró" not in str(m.get("content")) for body in server.bodies for m in body["messages"])


def test_a_receipt_that_answered_none_of_several_said_in_own_words_is_still_told_that_they_ring(tmp_path: Path) -> None:
    # INT20: the note is kept quiet only by a receipt that says one was stopped or snoozed; none, and it is told.
    import json

    from baxy_mind.mind import RINGING_STILL_NOTE
    from test_mind_final import _call
    mind, server = _mind(tmp_path, [_call("schedule_alarms", {"action": "snooze"}), _say("Listo, las pospuse."),
                                    _say("No pude posponerlas: siguen sonando.")])
    mind.configure({"capabilities": [{"name": "schedule.alarms", "description": "Alarms.", "risk": "low_reversible",
                                      "argumentsSchema": {"type": "object", "properties": {"action": {"type": "string"}}}}]})
    mind.decide(1, "dame cinco minutos que sigo en la ducha", None, None, None, None, [ALARM, REMINDER])
    rings = [{**ALARM, "snoozed": False, "ringing": True}, {**REMINDER, "snoozed": False, "ringing": True}]
    receipt = {"status": "failed", "error": "notification_ring_answer_unconfirmed",
               "observed": {"version": 1, "rings": rings, "authority": "baxy_app_ring_postread"}}
    assert mind.continue_turn(2, json.dumps(receipt))["reply"] == "No pude posponerlas: siguen sonando."
    assert server.bodies[-1]["messages"][-1]["content"] == RINGING_STILL_NOTE.format(
        rings="la alarma id 89abcdef «sal a trabajar» de las 07:00; el recordatorio id 76543210 de las 15:00")


def test_a_receipt_that_answered_one_of_several_by_the_rule_is_not_told_that_nothing_was_answered(tmp_path: Path) -> None:
    # INT20 (blind review of ALR3): with no id the App answers every one ringing, and one it did not end in time leaves
    # the call failed; its rings say the other was stopped. «En este turno no se paró … nada» would be false then.
    import json

    mind, server = _mind(tmp_path, [_say("Paré la alarma; el recordatorio sigue sonando.")])
    mind.configure({"capabilities": [{"name": "schedule.alarms", "description": "Alarms.", "risk": "low_reversible",
                                      "argumentsSchema": {"type": "object", "properties": {"action": {"type": "string"}}}}]})
    assert mind.decide(1, "ya está", None, None, None, None, [ALARM, REMINDER])["kind"] == "action"
    rings = [{**ALARM, "stopped": True, "ringing": False}, {**REMINDER, "stopped": False, "ringing": True}]
    receipt = {"status": "failed", "error": "notification_ring_answer_unconfirmed",
               "observed": {"version": 1, "rings": rings, "authority": "baxy_app_ring_postread"}}
    result = mind.continue_turn(2, json.dumps(receipt))
    assert result["reply"] == "Paré la alarma; el recordatorio sigue sonando."
    assert all("no se paró" not in str(m.get("content")) for body in server.bodies for m in body["messages"])


def test_a_receipt_that_answered_none_of_several_by_the_rule_is_still_told_that_they_ring(tmp_path: Path) -> None:
    # INT20: the note is kept quiet only by a receipt that says one was stopped or snoozed; none, and it is told.
    import json

    from baxy_mind.mind import RINGING_STILL_NOTE
    mind, server = _mind(tmp_path, [_say("Listo, las pospuse."), _say("No pude posponerlas: siguen sonando.")])
    mind.configure({"capabilities": [{"name": "schedule.alarms", "description": "Alarms.", "risk": "low_reversible",
                                      "argumentsSchema": {"type": "object", "properties": {"action": {"type": "string"}}}}]})
    mind.decide(1, "dame cinco minutos", None, None, None, None, [ALARM, REMINDER])
    rings = [{**ALARM, "snoozed": False, "ringing": True}, {**REMINDER, "snoozed": False, "ringing": True}]
    receipt = {"status": "failed", "error": "notification_ring_answer_unconfirmed",
               "observed": {"version": 1, "rings": rings, "authority": "baxy_app_ring_postread"}}
    assert mind.continue_turn(2, json.dumps(receipt))["reply"] == "No pude posponerlas: siguen sonando."
    assert server.bodies[-1]["messages"][-1]["content"] == RINGING_STILL_NOTE.format(
        rings="la alarma id 89abcdef «sal a trabajar» de las 07:00; el recordatorio id 76543210 de las 15:00")


def test_what_rings_after_baxys_own_question_is_told_as_not_what_the_answer_is_for(tmp_path: Path) -> None:
    # ALR5 (M1): after BAXY's own question, the note that words like «ya» or a time answer what rings made the stock model
    # stop or snooze it with the answer («¿Te envío el correo?» → «sí, dale» stopped the alarm, 3 of 3). Then it is told
    # that what follows is for its question; on any other turn, the note of ALR1.
    rings = "la alarma id 89abcdef «sal a trabajar» de las 07:00"
    mind, server = _mind(tmp_path, [_say("¿Para qué hora?"), _say("Listo."), _say("Sigue sonando."), _say("De nada."),
                                    _say("De nada.")])
    mind.decide(1, "ponme una alarma")
    mind.decide(2, "para las dos", None, None, None, None, [ALARM])
    asked = server.bodies[1]["messages"]
    assert asked[-1] == {"role": "user", "content": "para las dos"}
    assert "si sus palabras la contestan" not in asked[-2]["content"]
    from baxy_mind.mind import RINGING_ASKED_NOTE
    assert asked[-2]["content"].endswith("\n" + RINGING_ASKED_NOTE.format(rings=rings, call="schedule_alarms"))
    assert "{" not in RINGING_ASKED_NOTE.format(rings="", call="") and rings in asked[-2]["content"]
    mind.decide(3, "gracias", None, None, None, None, [ALARM])
    assert server.bodies[3]["messages"][-2]["content"] == RINGING_NOTE.format(rings=rings, call="schedule_alarms")


def test_what_rings_after_a_question_baxy_asked_with_a_call_is_the_note_of_any_turn(tmp_path: Path) -> None:
    # ALR5: only BAXY's last words ending in a question change the note (what was measured); the answer to a question
    # asked with a call, or words after a result, read the note of ALR1.
    from test_mind_final import _call
    mind, server = _mind(tmp_path, [_call("schedule_alarms", {"action": "list"}), _say("No hay ninguna. ¿Algo más?")])
    mind.decide(1, "qué alarmas tengo", None, None, None, None, [ALARM])
    assert server.bodies[0]["messages"][-2]["content"] == RINGING_NOTE.format(
        rings="la alarma id 89abcdef «sal a trabajar» de las 07:00", call="schedule_alarms")
