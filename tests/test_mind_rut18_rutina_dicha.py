"""Aid «said_routine», RUT18 (VIVO23 row 3 and CAL1, a new conversation with a routine at 10:00 kept: «cambia la de las
10:00 a las 11» became calendar.event.list 10 of 10 in Completo, opening Outlook, and the routine stayed; in Esencial
«La de regar las plantas, pásala a las siete.» set a reminder at 17:15 nobody asked for, 2 of 2). The model's first
decision reads nothing of the routines; a calendar call or an alarm it sets, when the person's words name one of their
routines by form (its clock written H:MM, or words of what it says), is held once with that routine as data, and the
same call again runs (they may mean an event or a new alarm).
RUT19 (REVX1 R-1): nothing is held before it runs any more; what a result that found nothing there says of the routine
is in test_mind_rut19_rutina_sin_retener.py. Here, the calls that run at once."""
from __future__ import annotations

from pathlib import Path

from test_mind_final import _call, _say
from test_mind_routine_guide import _guide_mind

MORNING = "Buenos días, Leonor, que tengas un gran día"
# RoutinesHandler's store as the App writes it (ids and times invented)
TEN = {"id": "r-3a1d09", "name": "10:00", "active": True,
       "trigger": {"at": "10:00", "repeat": "days", "days": ["mon", "wed", "fri"]}, "steps": [{"say": MORNING}]}
EIGHT = {"id": "r-126adc", "name": "20:00", "active": True,
         "trigger": {"at": "20:00", "repeat": "days", "days": ["sat"]}, "steps": [{"say": "hora de regar las plantas"}]}
LIST = _call("calendar_event_list", {"startUtc": "2026-11-15T10:00:00", "endUtc": "2026-11-15T12:00:00"})
REMIND = _call("schedule_alarms", {"action": "create", "kind": "reminder", "at": "17:15", "title": "Regar las plantas"})


def _held(tmp_path: Path, said: str, first: dict, then: dict | None = None, routines: list | None = None):
    mind, server = _guide_mind(tmp_path, [first, then or _say("¿Hablas de tu rutina?")],
                               [TEN, EIGHT] if routines is None else routines)
    mind.wire_to_op.update({"calendar_event_list": "calendar.event.list"})
    mind.new_session([])
    return mind.decide(1, said), server


def _results(server) -> list[str]:
    return [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"]


def test_words_that_name_no_routine_run_at_once(tmp_path: Path) -> None:
    for index, said in enumerate(("cambia la de las 9:30 a las 11", "¿qué tengo hoy en el calendario?",
                                  "mueve la reunión de las diez a las once", "pon un recordatorio para regar")):
        decided, server = _held(tmp_path / str(index), said, LIST)
        assert decided["operation"] == "calendar.event.list" and len(server.bodies) == 1, said


def test_no_routines_kept_or_an_alarm_call_that_neither_sets_nor_cancels_runs_at_once(tmp_path: Path) -> None:
    decided, server = _held(tmp_path / "a", "cambia la de las 10:00 a las 11", LIST, routines=[])
    assert decided["operation"] == "calendar.event.list" and len(server.bodies) == 1
    listed = _call("schedule_alarms", {"action": "list"})
    decided, server = _held(tmp_path / "b", "Borra la de las 10:00.", listed)
    assert decided["operation"] == "schedule.alarms" and len(server.bodies) == 1
