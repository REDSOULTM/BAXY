"""ALR4 (owner's exception, 2026-11-09: «una regla de regex que hardcodeada… para cosas que el usuario sí o sí va a decir
en torno a las cosas de la aplicación»): while BAXY rings an alarm or a reminder, a short acknowledgement («Baxy,
gracias», «para la alarma», «cinco minutos más») stops or snoozes what rings before the model is asked, and BAXY says
the receipt in a fixed sentence. With nothing ringing the rule does not exist, and any other words go to the model."""
import json
from pathlib import Path

import pytest

from baxy_mind import ring_answer
from test_mind_final import _mind, _say

ALARM = {"id": "89abcdef", "kind": "alarm", "title": "sal a trabajar", "clock": "07:00"}
REMINDER = {"id": "76543210", "kind": "reminder", "clock": "15:00"}


def _ringing_mind(tmp_path: Path, replies: list):
    mind, server = _mind(tmp_path, replies)
    mind.wire_to_op = {"schedule_alarms": "schedule.alarms"}  # the catalog has it, as the product's does
    return mind, server


def _stopped(*rings: dict) -> str:
    told = [{**ring, "stopped": True, "ringing": False} for ring in rings]
    observed = {"version": 1, **told[0]} if len(told) == 1 else {"version": 1, "rings": told}
    return json.dumps({"status": "completed", "verification": "readback",
                       "observed": {**observed, "authority": "baxy_app_ring_postread"}})


def _snoozed(ring: dict, minutes: int, due: str) -> str:
    return json.dumps({"status": "completed", "verification": "readback", "observed": {
        "version": 1, **ring, "snoozed": True, "ringing": False, "inMinutes": minutes, "dueLocal": due,
        "scheduledFor": "today", "authority": "baxy_app_ring_postread"}})


def test_baxy_gracias_with_an_alarm_ringing_stops_it_without_the_model_and_says_the_receipt(tmp_path: Path) -> None:
    mind, server = _ringing_mind(tmp_path, [])
    result = mind.decide(1, "Baxy, gracias", None, None, None, None, [ALARM])
    assert result["kind"] == "action" and result["operation"] == "schedule.alarms"
    assert result["arguments"] == {"action": "stop"}  # no id: every one ringing (ALR3)
    reply = mind.continue_turn(2, _stopped(ALARM))
    assert reply["kind"] == "conversation" and reply["reply"] == "Paré la alarma «sal a trabajar» de las 7:00."
    assert server.bodies == []  # the model was never asked
    assert mind.conversation[-1] == {"role": "assistant", "content": "Paré la alarma «sal a trabajar» de las 7:00."}


def test_two_ringing_are_each_said_and_a_snooze_says_its_minutes_and_when_it_rings_again(tmp_path: Path) -> None:
    mind, _ = _ringing_mind(tmp_path, [])
    assert mind.decide(1, "gracias, apágalas", None, None, None, None, [ALARM, REMINDER])["arguments"] == {"action": "stop"}
    assert (mind.continue_turn(2, _stopped(ALARM, REMINDER))["reply"]
            == "Paré la alarma «sal a trabajar» de las 7:00 y el recordatorio de las 15:00.")
    result = mind.decide(3, "Baxy, cinco minutitos más", None, None, None, None, [REMINDER])
    assert result["arguments"] == {"action": "snooze", "inMinutes": 5}
    assert (mind.continue_turn(4, _snoozed(REMINDER, 5, "2026-11-09 15:05"))["reply"]
            == "Pospuse 5 minutos el recordatorio de las 15:00; vuelve a sonar a las 15:05.")


def test_words_that_name_one_kind_of_two_ringing_answer_only_that_kind(tmp_path: Path) -> None:
    mind, _ = _ringing_mind(tmp_path, [])
    result = mind.decide(1, "para el recordatorio", None, None, None, None, [ALARM, REMINDER])
    assert result["arguments"] == {"action": "stop", "kind": "reminder"}
    mind.continue_turn(2, _stopped(REMINDER))
    # With one kind ringing, its name is how the person calls what rings.
    assert mind.decide(3, "para el recordatorio", None, None, None, None, [ALARM])["arguments"] == {"action": "stop"}


def test_a_question_baxy_just_asked_is_answered_by_the_model_and_so_are_unsure_words(tmp_path: Path) -> None:
    mind, server = _ringing_mind(tmp_path, [_say("Son las 7:05. ¿Te leo las noticias?"), _say("Ahí van."),
                                            _say("Ahí van."), _say("Hecho."), _say("Hecho.")])
    mind.decide(1, "qué hora es")
    assert mind.decide(2, "sí", None, None, None, None, [ALARM])["reply"] == "Ahí van."
    assert server.bodies[1]["messages"][-1] == {"role": "user", "content": "sí"}
    mind.decide(3, "para", None, [("para", 0.2)], None, None, [ALARM])  # the ear was unsure of «para»
    assert server.bodies[3]["messages"][-1] == {"role": "user", "content": "para"}


@pytest.mark.parametrize(("question", "words"), [
    ("¿Para qué hora?", "Para las dos"), ("¿En cuántos minutos?", "10 minutos"),
    ("Listo, la alarma sonará a las 7:00. ¿Algo más?", "Baxy, gracias"), ("¿La apago o la dejo?", "apágala"),
    ("How long should the timer be?", "five more minutes"), ("¿Cuándo te lo recuerdo?", "más tarde")])
def test_after_a_question_of_baxy_the_rule_does_not_act_and_the_words_go_to_the_model(
        tmp_path: Path, question: str, words: str) -> None:
    # ALR5 (M1 of REV_MENTE; leader's decision): the rule only compares form, so words that answer what BAXY just asked
    # («¿Para qué hora?» → «Para las dos») looked like an order to what rings and stopped or snoozed it with no model.
    mind, server = _ringing_mind(tmp_path, [_say(question), _say("Hecho."), _say("Hecho.")])
    mind.decide(1, "pon una alarma")
    result = mind.decide(2, words, None, None, None, None, [ALARM])
    assert result["kind"] == "conversation" and result["reply"] == "Hecho."
    assert server.bodies[1]["messages"][-1] == {"role": "user", "content": words}


def test_after_words_of_baxy_that_ask_nothing_the_rule_acts(tmp_path: Path) -> None:
    mind, server = _ringing_mind(tmp_path, [_say("Son las 7:05.")])
    mind.decide(1, "qué hora es")
    assert mind.decide(2, "Baxy, gracias", None, None, None, None, [ALARM])["arguments"] == {"action": "stop"}
    assert len(server.bodies) == 1


def test_english_words_are_answered_in_english_and_shared_ones_in_the_interfaces_language(tmp_path: Path) -> None:
    mind, _ = _ringing_mind(tmp_path, [])
    mind.decide(1, "Thanks, Baxy!", None, None, None, None, [ALARM])
    assert mind.continue_turn(2, _stopped(ALARM))["reply"] == "Stopped the 7:00 alarm «sal a trabajar»."
    mind.lang = "en"
    mind.decide(3, "ok", None, None, None, None, [REMINDER])
    assert mind.continue_turn(4, _stopped(REMINDER))["reply"] == "Stopped the 15:00 reminder."
    mind.decide(5, "vale", None, None, None, None, [REMINDER])
    assert mind.continue_turn(6, _stopped(REMINDER))["reply"] == "Paré el recordatorio de las 15:00."


def test_with_nothing_ringing_the_rule_does_not_exist(tmp_path: Path) -> None:
    mind, server = _ringing_mind(tmp_path, [_say("¡De nada!")])
    assert mind.decide(1, "Baxy, gracias")["reply"] == "¡De nada!"
    assert len(server.bodies) == 1


@pytest.mark.parametrize("words", ["gracias, ¿qué tiempo hace?", "para la música", "apaga la luz del cuarto",
                                   "ya voy a la cocina", "gracias por despertarme, ¿qué tengo hoy?", "pospón la reunión"])
def test_longer_words_go_to_the_model_even_with_gracias_in_them(tmp_path: Path, words: str) -> None:
    mind, server = _ringing_mind(tmp_path, [_say("Hecho."), _say("Hecho.")])  # RINGING_STILL_NOTE asks once more
    assert mind.decide(1, words, None, None, None, None, [ALARM])["reply"] == "Hecho."
    assert server.bodies[0]["messages"][-1] == {"role": "user", "content": words}


@pytest.mark.parametrize("ended", [False, True])
def test_words_that_answer_a_yes_baxy_waits_for_go_to_the_model(tmp_path: Path, ended: bool) -> None:
    mind, server = _ringing_mind(tmp_path, [_say("Lo borro."), _say("Lo borro.")])
    pending = {"operation": "filesystem.delete", "arguments": {"path": "x"}, **({"ended": "expired"} if ended else {})}
    assert mind.decide(1, "vale", pending, None, None, None, [ALARM])["reply"] == "Lo borro."
    assert server.bodies[0]["messages"][-1] == {"role": "user", "content": "vale"}


def test_with_the_alarms_kept_off_in_the_profile_the_rule_still_answers_what_rings(tmp_path: Path) -> None:
    # ALR5 (M2; PRE21 3: the rule looked for the whole tool in the catalog): what already rings is answered whatever
    # the profile, as its card's buttons are.
    mind, server = _mind(tmp_path, [])
    mind.configure({"capabilities": [], "withheld": [{"name": "schedule.alarms", "title": "Alarm or reminder"}]})
    result = mind.decide(1, "Baxy, gracias", None, None, None, None, [ALARM])
    assert result["kind"] == "action" and result["operation"] == "schedule.alarms"
    assert result["arguments"] == {"action": "stop"}
    assert mind.continue_turn(2, _stopped(ALARM))["reply"] == "Paré la alarma «sal a trabajar» de las 7:00."
    assert server.bodies == []


def test_a_tool_the_catalog_does_not_have_leaves_the_words_to_the_model(tmp_path: Path) -> None:
    mind, server = _mind(tmp_path, [_say("De nada."), _say("De nada.")])  # an older App's catalog, without it
    assert mind.decide(1, "gracias", None, None, None, None, [ALARM])["reply"] == "De nada."
    assert server.bodies[0]["messages"][-1] == {"role": "user", "content": "gracias"}


def test_a_receipt_that_does_not_say_each_ring_answered_goes_to_the_model(tmp_path: Path) -> None:
    mind, server = _ringing_mind(tmp_path, [_say("No pude pararla: sigue sonando."), _say("No pude pararla.")])
    mind.decide(1, "gracias", None, None, None, None, [ALARM])
    failed = json.dumps({"status": "failed", "error": "notification_ring_answer_unconfirmed", "effectUncertain": True,
                         "observed": {"version": 1, **ALARM, "stopped": False, "ringing": True}})
    assert mind.continue_turn(2, failed)["reply"].startswith("No pude pararla")
    assert server.bodies[0]["messages"][-1]["role"] == "tool"  # the model read the receipt


@pytest.mark.parametrize(("words", "action", "minutes", "lang"), [
    ("Baxy, gracias", "stop", None, "es"), ("gracias Baxy", "stop", None, "es"), ("ay, ya, ya", "stop", None, "es"),
    ("Párala", "stop", None, "es"), ("apágala por favor", "stop", None, "es"), ("ya está", "stop", None, "es"),
    ("ok", "stop", None, None), ("Stop!", "stop", None, None), ("I'm up", "stop", None, "en"),
    ("thank you", "stop", None, "en"), ("pospón", "snooze", None, "es"), ("diez minutos más", "snooze", 10, "es"),
    ("dame 15 minutos más", "snooze", 15, "es"), ("snooze for 20 minutes", "snooze", 20, "en"),
    ("five more minutes", "snooze", 5, "en"), ("más tarde", "snooze", None, "es"),
    ("para, para, ya está", "stop", None, "es"), ("ya, gracias, apágalas", "stop", None, "es"),
    ("Ya po, cállate", "stop", None, "es"), ("yeah yeah, I'm up", "stop", None, "en"),
    ("ahorita no, pospón por favor", "snooze", None, "es"), ("posponé las dos veinte minutos", "snooze", 20, "es"),
    ("en media hora", "snooze", 30, "es"), ("snooze them both", "snooze", None, "en"),
    ("snooze 10 min", "snooze", 10, "en"), ("10 min", "snooze", 10, None),
])
def test_the_closed_lists_hear_the_whole_words(words: str, action: str, minutes: int | None, lang: str | None) -> None:
    assert ring_answer.heard(words) == ring_answer.Answer(action, minutes, lang)


@pytest.mark.parametrize("words", ["", "Baxy", "gracias por todo", "qué hora es", "no la pares", "para nada",
                                   "0 minutos más", "cinco minutos más y diez minutos", "apaga el pc",
                                   "apágala, cinco minutos más", "ya, ok, gracias, listo, vale, perfecto", "stop the music",
                                   "remind me later to call the bank", "ok, abre el correo", "¿ya?", "¿listo?",
                                   "\U00010a40 minutos", "para la alarma y el recordatorio"])
def test_anything_else_is_not_heard(words: str) -> None:
    assert ring_answer.heard(words) is None


def test_words_that_name_a_kind_are_heard_with_it() -> None:
    assert ring_answer.heard("para la alarma") == ring_answer.Answer("stop", None, "es", "alarm")
    assert ring_answer.heard("snooze the reminder") == ring_answer.Answer("snooze", None, "en", "reminder")
