"""M137 (2026-10-03, DEV-G run v4n and DEV-F run v4m): «X antes» of a moment said in the same message.

1. The advance. G-s016 «I've got a dentist appointment Thursday at 4 over on Maple St, remind me an hour before so…»
   was set at 16:00, G-s019 «recuérdame una hora antes de la reunión con el banco que es a las 3 de la tarde» at 15:00
   titled «una hora antes de la reunión con el banco que es», and F-w55-t1 «mañana a las 10 tengo turno con el dentista
   en Palermo, recordámelo una hora antes…» at 10:00: every reader read the event's clock and the advance was lost
   where the moment is converted. It is counted there now (``semantic.arguments.due_before_said_moment``, read by
   ``semantic.temporal.said_advance``), and the title is the event's.
2. M137b, the bare hour moved. G-w22-t5 «actually make it 8» after «set a reminder for Tuesday evening to check
   again»: the decider's «Tuesday at 8 PM» was judged a clock nobody said and the turn asked «8 PM or 8 AM?»; the part
   of the day the conversation said (or D61b on a named day) says it.

Every phrasing beyond the rows is our own. The clock is fixed in every test.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.semantic import arguments, decider, temporal

# Saturday 3 October 2026, 12:30 in Chile (UTC-3).
LOCAL = timezone(timedelta(hours=-3))
NOW = datetime(2026, 10, 3, 12, 30, tzinfo=LOCAL)

G_S016 = "I've got a dentist appointment Thursday at 4 over on Maple St, remind me an hour before so I'm not late again"
G_S019 = "recuérdame una hora antes de la reunión con el banco que es a las 3 de la tarde"
F_W55_T1 = (
    "mañana a las 10 tengo turno con el dentista en Palermo, recordámelo una hora antes así no salgo a las corridas"
)


def _local(due: str) -> datetime:
    return datetime.fromisoformat(due.replace("Z", "+00:00")).astimezone(LOCAL)


def _normalized(operation: str, raw: dict, context: str, said: str | None = None) -> dict | None:
    return sidecar._normalize_grounded_operation_arguments(operation, dict(raw), context, now_utc=NOW, said=said)


# ------------------------------------------------------------------ 1. the advance, through the readers that read it


def test_g_s016_the_timed_task_rings_an_hour_before_thursday_at_4() -> None:
    task = temporal.timed_task(G_S016)
    assert task is not None and task.due == "Thursday at 4"
    # ``_timed_task_arguments`` converts the moment the task read, with the message it read it from.
    read = _normalized("notification.schedule", {"dueUtc": task.due, "title": task.title, "kind": "reminder"},
                       task.due, said=G_S016)
    assert read is not None and read["kind"] == "reminder"
    due = _local(read["dueUtc"])
    assert (due.date().isoformat(), due.hour, due.minute) == ("2026-10-08", 15, 0)
    assert read["title"] == "dentist appointment over on Maple St"


def test_g_s019_the_reminder_reader_rings_at_14_titled_with_the_meeting() -> None:
    read = arguments._explicit_arguments_from_evidence("reminder.create", G_S019)
    assert read == {"dueUtc": "a las 3 de la tarde", "title": "una hora antes de la reunión con el banco que es"}
    normalized = _normalized("reminder.create", read, G_S019)
    assert normalized is not None
    due = _local(normalized["dueUtc"])
    assert (due.date().isoformat(), due.hour, due.minute) == ("2026-10-03", 14, 0)
    assert normalized["title"] == "reunión con el banco"


def test_f_w55_t1_tomorrow_at_10_less_an_hour_is_9() -> None:
    task = temporal.timed_task(F_W55_T1)
    assert task is not None
    read = _normalized("reminder.create", {"dueUtc": task.due, "title": task.title}, task.due, said=F_W55_T1)
    assert read is not None
    due = _local(read["dueUtc"])
    assert (due.date().isoformat(), due.hour, due.minute) == ("2026-10-04", 9, 0)
    assert read["title"] == "turno con el dentista en Palermo"


def test_the_extraction_that_copies_the_event_or_the_advance_is_counted_too() -> None:
    # The model copies the moment as said (llm: «dueUtc es la hora tal como la dijo la persona»).
    for raw in ("Thursday at 4", "an hour before"):
        read = _normalized("notification.schedule", {"dueUtc": raw, "kind": "reminder", "title": "dentist"}, G_S016)
        assert read is not None and (_local(read["dueUtc"]).day, _local(read["dueUtc"]).hour) == (8, 15), raw
        assert read["title"] == "dentist"


@pytest.mark.parametrize(
    ("text", "raw", "expected", "title"),
    [
        # Our own: English with the event after the advance, Spanish «del», a relative clause, a pointer «it».
        ("remind me 30 minutes before my flight at 6pm", "at 6pm", (3, 17, 30), "my flight"),
        ("avísame diez minutos antes del partido de las 9 de la noche", "9 de la noche", (3, 20, 50), "partido"),
        ("ponme una alarma media hora antes del vuelo, que sale a las 8", "a las 8", (3, 19, 30), None),
        ("I have a call with Ana at 5 pm, ping me 15 minutes before it", "at 5 pm", (3, 16, 45), None),
        ("el lunes a las 4 tengo kinesiología, avísame media hora antes porfa", "el lunes a las 4", (5, 15, 30), None),
    ],
)
def test_other_ways_of_saying_an_advance(text: str, raw: str, expected: tuple, title: str | None) -> None:
    read = _normalized("notification.schedule", {"dueUtc": raw, "kind": "reminder", "title": title or text}, text)
    assert read is not None
    due = _local(read["dueUtc"])
    assert (due.day, due.hour, due.minute) == expected
    if title is not None:
        assert read["title"] == title
    else:
        # The whole message as title is the order itself: it becomes what happens then.
        assert temporal.said_advance(text).title and read["title"] == temporal.said_advance(text).title


def test_the_event_title_is_what_happens_then() -> None:
    assert temporal.said_advance("ponme una alarma media hora antes del vuelo, que sale a las 8").title == "vuelo"
    assert temporal.said_advance("tengo turno a las 10 y recordámelo una hora antes").title == "turno"
    assert temporal.said_advance("remind me an hour before, I have a flight at 6pm").title == "flight"


def test_an_advance_that_leaves_the_moment_past_is_asked() -> None:
    # 13:00 less an hour is 12:00, already past at 12:30; the event itself is still ahead today.
    text = "recuérdame una hora antes de la reunión que es a la 1 de la tarde"
    assert _normalized("reminder.create", {"dueUtc": "a la 1 de la tarde", "title": "reunión"}, text) is None


def test_a_converted_moment_is_never_counted_twice() -> None:
    iso = "2026-10-08T18:00:00Z"
    read = _normalized("notification.schedule", {"dueUtc": iso, "kind": "reminder", "title": "dentist"}, G_S016)
    assert read is not None and read["dueUtc"] == iso


# ------------------------------------------------------------------ what must not change


@pytest.mark.parametrize(
    "text",
    [
        # The clock is the notification's own.
        "recuérdame a las 8 tomar la pastilla media hora antes de comer",
        "remind me at 3 to leave, an hour before the meeting",
        # The thing named is not the event the clock is said of.
        "tengo que tomar la pastilla a las 8, media hora antes de la cena, recuérdamelo",
        # A clause, not a moment: «antes de que…», «before I…».
        "avísame 10 minutos antes de que llegue el bus de las 6",
        "remind me an hour before I leave for the 5 pm train",
        # Pointed at an earlier message (M84 counts it from there), two clocks, no advance.
        "recuérdame media hora antes de eso",
        "tengo reunión a las 3 y a las 5, avísame una hora antes",
        "pon una alarma a las 7",
    ],
)
def test_no_advance_from_the_moment_said(text: str) -> None:
    assert temporal.said_advance(text) is None


def test_the_reminder_at_its_own_clock_rings_at_it() -> None:
    text = "recuérdame a las 8 tomar la pastilla media hora antes de comer"
    read = _normalized("reminder.create", {"dueUtc": "a las 8", "title": "tomar la pastilla"}, text)
    assert read is not None and (_local(read["dueUtc"]).hour, _local(read["dueUtc"]).minute) == (20, 0)


def test_the_calendar_start_keeps_the_event_clock() -> None:
    # The advance belongs to the notification; the moment converter itself (an event's start) is unchanged.
    due = arguments._canonical_due_utc("el jueves a las 4", "el jueves a las 4, recuérdame una hora antes", now_utc=NOW)
    assert due is not None and _local(due).hour == 16


# ------------------------------------------------------------------ 2. M137b: the bare hour moved

G_W22 = [
    "any news on the rail strikes? I've got a trip coming up",
    "The RMT has called a 48-hour walkout on 21 and 22 October; Southern and Thameslink are hit hardest.",
    "no, I meant the one in France",
    "Sorry. SNCF unions strike from Tuesday; about half of TGVs are cancelled, Eurostar is running normally.",
    "so that won't touch my Eurostar on Wednesday?",
    "Eurostar says it's keeping its normal timetable all week, so you should be fine.",
    "set a reminder for Tuesday evening to check again",
    "Done: Tuesday at 18:00 I'll remind you to check the Eurostar strike news.",
]
DECIDER_NOW = datetime(2026, 10, 3, 12, 30)


def test_g_w22_t5_the_evening_said_makes_8_the_evening() -> None:
    restated = "Set a reminder for Tuesday at 8 PM to check again."
    fidelity = decider.faithful_request(restated, "actually make it 8", G_W22, now=DECIDER_NOW)
    assert (fidelity.kind, fidelity.request) == ("kept", restated)
    # The morning nobody said is still a clock nobody said.
    morning = decider.faithful_request("Set a reminder for Tuesday at 8 AM to check again.", "actually make it 8",
                                       G_W22, now=DECIDER_NOW)
    assert morning.kind == "person" and morning.introduced == ("at 8 AM",)
    # Another hour than the one said is no move to it.
    nine = decider.faithful_request("Set a reminder for Tuesday at 9 PM to check again.", "actually make it 8",
                                    G_W22, now=DECIDER_NOW)
    assert nine.kind == "person"


def test_spanish_the_night_said_before_makes_10_the_night() -> None:
    earlier = ["ponme un recordatorio el viernes en la noche para pagar la luz",
               "Listo, el viernes a las 21:00 te recuerdo pagar la luz."]
    night = "Ponme un recordatorio el viernes a las 10 de la noche para pagar la luz."
    assert decider.faithful_request(night, "mejor que sean las 10", earlier, now=DECIDER_NOW).kind == "kept"
    morning = "Ponme un recordatorio el viernes a las 10 de la mañana para pagar la luz."
    assert decider.faithful_request(morning, "mejor que sean las 10", earlier, now=DECIDER_NOW).kind == "person"


def test_with_no_part_said_d61b_gives_a_named_day_its_daytime_hour() -> None:
    earlier = ["set a reminder for Tuesday to check again", "Done, I'll remind you on Tuesday."]
    assert decider.faithful_request(
        "Set a reminder for Tuesday at 8 AM to check again.", "actually make it 8", earlier, now=DECIDER_NOW,
    ).kind == "kept"
    assert decider.faithful_request(
        "Set a reminder for Tuesday at 8 PM to check again.", "actually make it 8", earlier, now=DECIDER_NOW,
    ).kind == "person"


@pytest.mark.parametrize(
    ("lines", "part"),
    [
        (["set a reminder for Tuesday evening to check again"], "pm"),
        (["Listo, el viernes a las 21:00 te recuerdo pagar la luz."], "pm"),
        (["despiértame mañana por la mañana"], "am"),
        (["good morning! set a reminder for Tuesday"], None),
        (["at 8 am and again at 6 pm"], None),
        (["what's the weather like?"], None),
    ],
)
def test_the_part_of_the_day_a_conversation_said(lines: list[str], part: str | None) -> None:
    assert temporal.part_of_day_said(lines) == part
