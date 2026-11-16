"""Aid «said_routine», RUT19 (REVX1 R-1, R-2, R-3 on rut18): held before it ran, a calendar call or an alarm set or
cancelled went back whenever the person's words had a routine's clock or a word of what it says, whatever the call
asked, and its result said «the person's words name a routine», which is not known. Now the call runs as the model made
it; only when its own result found nothing there (a calendar read with no event starting at the clock they wrote, a
cancel with no alarm nor reminder at it) is the routine that is there said beside the result, as what is known."""
from __future__ import annotations

from pathlib import Path

from test_mind_final import _call, _say
from test_mind_routine_guide import _failed, _guide_mind, _receipt

from baxy_mind import harness_language

MORNING = "Buenos días, Leonor, que tengas un gran día"
# RoutinesHandler's store as the App writes it (ids and times invented)
TEN = {"id": "r-3a1d09", "name": "10:00", "active": True,
       "trigger": {"at": "10:00", "repeat": "days", "days": ["mon", "wed", "fri"]}, "steps": [{"say": MORNING}]}
WORK = {"id": "r-77aa01", "name": "trabajo", "active": True,
        "trigger": {"at": "08:15", "repeat": "days", "days": ["mon"]}, "steps": [{"say": "A trabajar"}]}
ALARM = _call("schedule_alarms", {"action": "create", "kind": "alarm", "at": "10:00"})
CANCEL = _call("schedule_alarms", {"action": "cancel", "at": "10:00"})
LIST = _call("calendar_event_list", {"startUtc": "2026-11-16T00:00:00", "endUtc": "2026-11-17T00:00:00"})
EVENT = _call("calendar_event_create", {"title": "Trabajar en el informe", "startUtc": "2026-11-16T15:00:00",
                                         "endUtc": "2026-11-16T16:00:00"})
NOT_FOUND = _failed("notification_clock_not_found")
MEETING = _receipt({"events": [{"subject": "Reunión de equipo", "startLocal": "2026-11-16T10:00:00",
                                "endLocal": "2026-11-16T11:00:00"}], "count": 1})
# as the App writes it (MicrosoftAccountAdapter.WriteHourHere)
MEETING_APP = _receipt({"events": [{"subject": "Reunión de equipo", "startLocal": "Monday 2026-11-16 10:00",
                                    "endLocal": "Monday 2026-11-16 11:00"}], "count": 1})
EMPTY = _receipt({"events": [], "count": 0})


def _mind(tmp_path: Path, first: dict, routines: list | None = None):
    mind, server = _guide_mind(tmp_path, [first, _say("(palabras del modelo)")], [TEN] if routines is None else routines)
    mind.wire_to_op.update({"calendar_event_list": "calendar.event.list",
                            "calendar_event_create": "calendar.event.create"})
    mind.new_session([])
    return mind, server


def _beside(server) -> str:
    """What the model read of the call's result (its tool message, with the facts line)."""
    return [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]


def test_r1_the_reviewers_calls_run_as_the_model_made_them(tmp_path: Path) -> None:
    for index, (said, call, op) in enumerate((("Ponme una alarma a las 10:00.", ALARM, "schedule.alarms"),
                                              ("¿Qué tengo mañana a las 10:00 en el calendario?", LIST,
                                               "calendar.event.list"),
                                              ("Buenos días, ¿qué tengo hoy en el calendario?", LIST,
                                               "calendar.event.list"),
                                              ("Cancela la alarma de las 10:00.", CANCEL, "schedule.alarms"))):
        mind, server = _mind(tmp_path / str(index), call)
        decided = mind.decide(1, said)
        assert decided["operation"] == op and len(server.bodies) == 1, said


def test_h31_a_meeting_at_the_routines_clock_is_moved_with_nothing_of_the_routine_beside(tmp_path: Path) -> None:
    for index, listed in enumerate((MEETING, MEETING_APP)):
        mind, server = _mind(tmp_path / str(index), LIST)
        assert mind.decide(1, "Cambia la reunión de las 10:00 a las 11.")["operation"] == "calendar.event.list"
        mind.continue_turn(2, listed)
        read = _beside(server)
        assert "Reunión de equipo" in read and "rutina" not in read and "baxy_routines" not in read


def test_r2_a_routine_of_one_long_word_is_not_named_by_that_word(tmp_path: Path) -> None:
    mind, server = _mind(tmp_path / "a", EVENT, [WORK])
    decided = mind.decide(1, "Crea un evento mañana a las tres: trabajar en el informe.")
    assert decided["operation"] == "calendar.event.create" and len(server.bodies) == 1
    cancel = _call("schedule_alarms", {"action": "cancel", "title": "trabajar"})
    mind, server = _mind(tmp_path / "b", cancel, [WORK])
    assert mind.decide(1, "Cancela el recordatorio de trabajar.")["operation"] == "schedule.alarms"
    mind.continue_turn(2, NOT_FOUND)
    assert "que escribió la persona, están en lo que dice" not in _beside(server)


def test_r3_a_cancel_while_that_alarm_rings_runs(tmp_path: Path) -> None:
    mind, server = _mind(tmp_path, CANCEL)
    ring = [{"id": "a-1", "kind": "alarm", "title": "", "clock": "10:00"}]
    decided = mind.decide(1, "Cancela la alarma de las 10:00.", ringing=ring)
    assert decided["operation"] == "schedule.alarms" and len(server.bodies) == 1


def test_rut18s_change_finds_no_event_and_reads_the_routine_there(tmp_path: Path) -> None:
    """What rut18 fixed: «cambia la de las 10:00 a las 11» with a routine at 10:00 and nothing in the calendar."""
    mind, server = _mind(tmp_path, LIST)
    assert mind.decide(1, "cambia la de las 10:00 a las 11")["operation"] == "calendar.event.list"
    mind.continue_turn(2, EMPTY)
    read = _beside(server)
    assert "en lo que leyó del calendario no hay nada que empiece a las 10:00" in read
    assert "la hora que escribió la persona, 10:00, es la de su rutina «10:00»" in read and MORNING in read
    assert "baxy_routines cambia, desactiva y borra una rutina" in read
    # what is not known is not said
    assert "nombran" not in read and "name a routine" not in read


def test_rut18s_delete_finds_no_alarm_and_reads_the_routine_there(tmp_path: Path) -> None:
    mind, server = _mind(tmp_path, CANCEL)
    assert mind.decide(1, "Borra la de las 10:00.")["operation"] == "schedule.alarms"
    mind.continue_turn(2, NOT_FOUND)
    read = _beside(server)
    assert "la hora que escribió la persona, 10:00, es la de su rutina «10:00»" in read and MORNING in read
    assert "baxy_routines cambia, desactiva y borra una rutina" in read


def test_a_cancel_that_cancelled_keeps_the_list_of_int36g(tmp_path: Path) -> None:
    mind, server = _mind(tmp_path, CANCEL)
    mind.decide(1, "Borra la de las 10:00.")
    mind.continue_turn(2, _receipt({"cancelled": [{"id": "n-1", "kind": "alarm", "dueLocal": "2026-11-16T10:00:00"}],
                                    "count": 1}))
    read = _beside(server)
    assert "no hay nada" not in read and "la persona tiene además rutinas con hora" in read


def test_in_english_the_routine_there_is_said_in_english(tmp_path: Path) -> None:
    harness_language.use("en")
    try:
        mind, server = _mind(tmp_path, LIST)
        mind.decide(1, "move the 10:00 one to 11")
        mind.continue_turn(2, EMPTY)
        read = _beside(server)
    finally:
        harness_language.use("es")
    assert "in what was read of the calendar nothing starts at 10:00" in read
    assert "is that of their routine «10:00»" in read and "baxy_routines changes, turns off and deletes" in read
