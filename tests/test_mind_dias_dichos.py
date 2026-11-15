"""Aid «said_days», RUT16 (RUT15's owner phrase in Esencial: «todos los lunes, miércoles y viernes a las 10 10 de la
mañana digas Buenos días…» became a reminder with recurrence daily at 10:10, or three reminders once each on Saturday,
Sunday and Monday). An alarm or reminder rings once, every day or every hour: a create is compared by form with the days
of the week the person's words of the turn name. Nothing is set; the result says so, as data, with what rings on some
days of the week, and the model decides again, once per turn."""
import datetime as dt
import json
from pathlib import Path

from baxy_mind.mind import Mind
from test_mind_final import _call, _mind, _say

OWNER = ("quiero que todos los lunes, miércoles y viernes a las 10 10 de la mañana digas Buenos días, Aurelio, que "
         "tengas una linda jornada")
FRIDAY = dt.datetime(2026, 11, 13, 16, 27)   # the owner's moment: Friday, 16:27


def _not_run(mind) -> list[dict]:
    told = []
    for message in mind.conversation:
        if message["role"] == "tool" and str(message.get("content")).startswith("{"):
            body = json.loads(str(message["content"]).split("\n", 1)[0])
            if body.get("status") == "not_run":
                told.append(body)
    return told


def _at_friday(monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    monkeypatch.setattr(Mind, "_now", staticmethod(lambda: FRIDAY))
    monkeypatch.setattr(Mind, "_today", staticmethod(lambda: FRIDAY.date()))


def test_a_daily_reminder_for_days_said_goes_back_with_the_days_and_the_number_said_twice(tmp_path: Path,
                                                                                         monkeypatch) -> None:
    _at_friday(monkeypatch)
    daily = {"action": "create", "kind": "reminder", "title": "Buenos días, Aurelio", "at": "10:10",
             "recurrence": "daily"}
    mind, _ = _mind(tmp_path, [_call("schedule_alarms", daily), _say("¿Lo hago como rutina?")])
    step = mind.decide(1, OWNER)
    assert step["kind"] != "action"
    told = _not_run(mind)
    assert len(told) == 1 and told[0]["days"] == ["Monday", "Wednesday", "Friday"]
    assert "all seven days" in told[0]["reason"] and "«10» twice in a row" in told[0]["reason"]


def test_reminders_once_on_days_not_said_go_back_and_the_ones_queued_behind_do_not_run(tmp_path: Path,
                                                                                      monkeypatch) -> None:
    _at_friday(monkeypatch)
    calls = [{"action": "create", "kind": "reminder", "title": "Buenos días, Aurelio", "inMinutes": minutes}
             for minutes in (1440, 2880, 4320)]
    three = {"choices": [{"message": {"content": "", "tool_calls": [
        {"id": f"c{n}", "function": {"name": "schedule_alarms", "arguments": json.dumps(args)}}
        for n, args in enumerate(calls)]}}]}
    mind, _ = _mind(tmp_path, [three, _say("Entendido.")])
    assert mind.decide(1, OWNER)["kind"] != "action"
    told = _not_run(mind)
    assert len(told) == 3 and "Saturday 2026-11-14 at 16:27" in told[0]["reason"]
    assert all(f"The next {day} is 2026-11-{date}" in told[0]["reason"]
               for day, date in (("Monday", 16), ("Wednesday", 18), ("Friday", 20)))
    assert all("did not complete" in later["reason"] for later in told[1:])


def test_it_is_told_once_and_the_same_call_runs(tmp_path: Path, monkeypatch) -> None:
    _at_friday(monkeypatch)
    daily = _call("schedule_alarms", {"action": "create", "at": "10:00", "recurrence": "daily", "title": "Buenos días"})
    mind, _ = _mind(tmp_path, [daily, daily])
    assert mind.decide(1, OWNER)["arguments"]["recurrence"] == "daily"
    assert len(_not_run(mind)) == 1


def test_what_the_days_said_allow_runs(tmp_path: Path, monkeypatch) -> None:
    _at_friday(monkeypatch)
    for said, args in (
            ("pon una alarma todos los días a las 7 menos los domingos", {"at": "07:00", "recurrence": "daily"}),
            ("despiértame el lunes a las 7", {"at": "2026-11-16T07:00"}),
            ("recuérdame el martes a las 9 llamar a mi madre", {"at": "2026-11-17 09:00"}),
            ("recuérdame mañana a las 9 que el viernes es el cumpleaños de Ana", {"at": "09:00"}),
            ("ponme una alarma a las 8", {"at": "08:00", "recurrence": "daily"}),
            ("avísame cada hora los lunes", {"inMinutes": 60, "recurrence": "hourly"}),
            ("every Saturday at 9 remind me", {"inMinutes": 1440})):
        mind, _ = _mind(tmp_path, [_call("schedule_alarms", {"action": "create", "kind": "reminder", **args})])
        assert mind.decide(1, said)["kind"] == "action", said
        assert _not_run(mind) == [], said


def test_a_day_said_in_english_is_compared_too(tmp_path: Path, monkeypatch) -> None:
    _at_friday(monkeypatch)
    mind, _ = _mind(tmp_path, [_call("schedule_alarms", {"action": "create", "at": "2026-11-18T09:00"}), _say("Ok.")])
    mind.decide(1, "set an alarm for Thursday at 9")
    told = _not_run(mind)
    assert len(told) == 1 and "Wednesday 2026-11-18 at 09:00" in told[0]["reason"] and told[0]["days"] == ["Thursday"]
    # the date the day said comes next, so the model need not count it (held-out u04: «el jueves» set on Friday 20)
    assert "The next Thursday is 2026-11-19" in told[0]["reason"]


def test_without_the_aid_it_runs(tmp_path: Path, monkeypatch) -> None:
    _at_friday(monkeypatch)
    monkeypatch.setenv("BAXY_AYUDAS", "none")
    mind, _ = _mind(tmp_path, [_call("schedule_alarms", {"action": "create", "at": "10:10", "recurrence": "daily"})])
    assert mind.decide(1, OWNER)["arguments"]["recurrence"] == "daily"
