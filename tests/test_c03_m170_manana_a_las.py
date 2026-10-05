"""M170 (2026-10-05): «recuérdame mañana a las 8:45» rang tonight at 20:45 when asked by day.

``test_c03_m165_avisos_restantes.py::test_i_w20_t3_fifteen_minutes_before_the_meeting`` passed at night and failed at
10:39: DEV-I I-w20-t3 «tambien tengo una reunion a las 9, recuerdamelo 15 minutos antes de eso», after the alarm moved to
tomorrow at 8, was decided «Recuérdame mañana a las 8:45 que tengo una reunión a las 9.». The request holds two clocks, so
no reader reads it and the moment is read from the person's message (M58's timed task, M137's advance), which names no
day: D61 took the next 9 — at 10:39 tonight's 21:00, rung at 20:45; at 07:00 this morning's, rung at 08:45 today. In the
v4y run (20:52) the next 9 happened to be tomorrow's. A product fault, not only the test's: the decider's day was lost.

Fixed (``semantic.temporal.placed_day_of_moment``): when the message asks to be reminded some time before a moment with
no day of its own, the day the request places beside that moment's clock, or beside the clock that rings («mañana a las
8:45»), rides with the moment; D61b then reads the hour on that day (7 to 11 the morning, 1 to 6 the afternoon). Today,
no day, another day said by the person, a request that places no day on those clocks and a moment with no advance (the
other alarm of F-w35-t3, «y otra a las 5 y 10 por si las moscas») keep D61 as before.

The row is quoted with its real text and its written history; every other phrasing is our own. Clocks are fixed.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.semantic import temporal
from test_c03_m148_avisos_eso_y_cuentas import _arguments
from test_c03_m165_avisos_restantes import I20

LOCAL = timezone(timedelta(hours=-3))
# Sunday 4 October 2026 in Chile (UTC-3); the hours each case is asked at.
SUNDAY = datetime(2026, 10, 4, tzinfo=LOCAL)
HOURS = [(7, 0), (10, 39), (20, 52), (23, 30)]


def _at(hour: int, minute: int, days: int = 0) -> datetime:
    return (SUNDAY + timedelta(days=days)).replace(hour=hour, minute=minute)


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch):
    """Fix the clock the reminder's moment is read against (M108): ``clock(now)``."""

    normalize = sidecar._normalize_grounded_operation_arguments

    def fix(now: datetime) -> None:
        monkeypatch.setattr(
            sidecar, "_normalize_grounded_operation_arguments",
            lambda *args, **kwargs: normalize(*args, **{**kwargs, "now_utc": kwargs.get("now_utc") or now}),
        )

    return fix


def _rings(request: str, said: list[str]) -> datetime:
    arguments_, question = _arguments("notification.schedule", request, said)
    assert question == "" and arguments_ is not None
    return datetime.fromisoformat(arguments_["dueUtc"].replace("Z", "+00:00")).astimezone(LOCAL)


# ------------------------------------------------------------------ the row: I-w20-t3 at any hour of the day

@pytest.mark.parametrize(("hour", "minute"), HOURS)
def test_i_w20_t3_tomorrow_at_eight_forty_five_at_any_hour(clock, hour: int, minute: int) -> None:
    clock(_at(hour, minute))
    restated = "Recuérdame mañana a las 8:45 que tengo una reunión a las 9."
    assert _rings(restated, I20) == _at(8, 45, days=1)


# ------------------------------------------------------------------ the same shape in other words

@pytest.mark.parametrize(("hour", "minute"), HOURS)
@pytest.mark.parametrize(
    ("person", "decided", "rings"),
    [
        ("I also have a meeting at 9, remind me 15 minutes before that",
         "Remind me tomorrow at 8:45 that I have a meeting at 9.", _at(8, 45, days=1)),
        # D61b on a weekday: 1 to 6 is the afternoon.
        ("tengo dentista a las 4, avísame media hora antes",
         "Avísame el viernes a las 3:30 que tengo dentista a las 4.", _at(15, 30, days=5)),
        ("tengo examen a las 10, recuérdamelo una hora antes",
         "Recuérdame pasado mañana a las 9 que tengo examen a las 10.", _at(9, 0, days=2)),
        # The part of the day said keeps commanding.
        ("tengo una peli a las 10 de la noche, avísame media hora antes",
         "Avísame mañana a las 9:30 de la noche que tengo una peli a las 10 de la noche.", _at(21, 30, days=1)),
        # The person's own day, the same as the request's.
        ("mañana tengo una reunión a las 9, recuérdamelo 15 minutos antes",
         "Recuérdame mañana a las 8:45 que tengo una reunión a las 9.", _at(8, 45, days=1)),
    ],
)
def test_the_day_the_request_places_rides_with_the_moment(
    clock, person: str, decided: str, rings: datetime, hour: int, minute: int,
) -> None:
    clock(_at(hour, minute))
    assert _rings(decided, [person]) == rings


# ------------------------------------------------------------------ what does not change

@pytest.mark.parametrize(
    ("person", "decided"),
    [
        # Today said: D61, the next 8:45 (at 10:39 tonight's).
        ("tengo reunión a las 9, recuérdamelo 15 minutos antes", "Recuérdame hoy a las 8:45 que tengo una reunión a las 9."),
        # No day said anywhere: D61.
        ("tengo reunión a las 9, recuérdamelo 15 minutos antes", "Recuérdame a las 8:45 que tengo una reunión a las 9."),
        # The person said today and the request another day: the person's word stands.
        ("hoy tengo reunión a las 9, recuérdamelo 15 minutos antes",
         "Recuérdame mañana a las 8:45 que tengo una reunión a las 9."),
        # The request does not name the moment the person said: nothing of it is carried.
        ("tengo reunión a las 9, recuérdamelo 15 minutos antes", "Recuérdame mañana a las 7 que tengo una reunión a las 11."),
    ],
)
def test_no_day_placed_keeps_d61(clock, person: str, decided: str) -> None:
    clock(_at(10, 39))
    assert _rings(decided, [person]) == _at(20, 45)
    clock(_at(7, 0))
    assert _rings(decided, [person]) == _at(8, 45)


@pytest.mark.parametrize(("hour", "minute"), HOURS)
@pytest.mark.parametrize(
    ("said", "rings"),
    [
        # A day said beside the clock was already read so (D61b): 7 to 11 the morning, 1 to 6 the afternoon.
        ("pon una alarma mañana a las 7", _at(7, 0, days=1)),
        ("recuérdame mañana a las 3 llamar a Ana", _at(15, 0, days=1)),
        ("recuérdame el lunes a las 8 pagar la luz", _at(8, 0, days=1)),
        ("remind me tomorrow at 8:45 to call Ana", _at(8, 45, days=1)),
        ("recuérdame mañana a las 8:45 que tengo reunión", _at(8, 45, days=1)),
        ("recuérdame pasado mañana a las 9 ir al banco", _at(9, 0, days=2)),
        ("recuérdame el viernes a las 3 la reunión", _at(15, 0, days=5)),
        ("recuérdame mañana a las 10 de la noche ver la peli", _at(22, 0, days=1)),
    ],
)
def test_a_day_said_beside_the_clock_is_unchanged(clock, said: str, rings: datetime, hour: int, minute: int) -> None:
    clock(_at(hour, minute))
    assert _rings(said, [said]) == rings


@pytest.mark.parametrize(
    ("now", "rings"),
    [(_at(7, 0), _at(9, 0)), (_at(10, 39), _at(21, 0)), (_at(20, 52), _at(21, 0)), (_at(23, 30), _at(9, 0, days=1))],
)
def test_nine_without_a_day_is_still_the_next_nine(clock, now: datetime, rings: datetime) -> None:
    clock(now)
    assert _rings("pon una alarma a las 9", ["pon una alarma a las 9"]) == rings


@pytest.mark.parametrize(("now", "rings"), [(_at(7, 0), _at(9, 0)), (_at(10, 39), _at(21, 0)), (_at(20, 52), _at(21, 0))])
def test_today_at_nine_is_the_next_nine_today(clock, now: datetime, rings: datetime) -> None:
    clock(now)
    assert _rings("recuérdame hoy a las 9 sacar la basura", ["recuérdame hoy a las 9 sacar la basura"]) == rings


# ------------------------------------------------------------------ the reader

@pytest.mark.parametrize(
    ("decided", "said", "due", "day"),
    [
        ("Recuérdame mañana a las 8:45 que tengo una reunión a las 9.", I20[-1], "a las 9", "mañana"),
        ("Remind me tomorrow at 8:45 that I have a meeting at 9.", "I have a meeting at 9, remind me 15 minutes before",
         "at 9", "tomorrow"),
        ("Avísame el viernes a las 3:30 que tengo dentista a las 4.", "tengo dentista a las 4, avísame media hora antes",
         "a las 4", "el viernes"),
        # The day beside the moment itself rather than beside the clock that rings.
        ("Recuérdame a las 8:45 que tengo una reunión mañana a las 9.", I20[-1], "a las 9", "mañana"),
        # Today, no day, a day of the moment's own, two days, a conflicting day of the person's, no clock of the moment.
        ("Recuérdame hoy a las 8:45 que tengo una reunión a las 9.", I20[-1], "a las 9", None),
        ("Recuérdame a las 8:45 que tengo una reunión a las 9.", I20[-1], "a las 9", None),
        ("Recuérdame mañana a las 8:45 que tengo una reunión a las 9.", I20[-1], "el lunes a las 9", None),
        ("Recuérdame mañana a las 8:45 y el viernes a las 9.", I20[-1], "a las 9", None),
        ("Recuérdame mañana a las 8:45 que tengo una reunión a las 9.",
         "el viernes tengo reunion a las 9, recuérdamelo 15 minutos antes", "a las 9", None),
        ("Recuérdame mañana a las 7 que tengo una reunión a las 11.", I20[-1], "a las 9", None),
        # No advance asked (DEV-F F-w35-t3 «y otra a las 5 y 10 por si las moscas», decided «Pon una alarma mañana a las
        # 5:10 para el vuelo a Cartagena.»): the decider's dial clock is read where the request is; nothing is carried.
        ("Pon una alarma mañana a las 5:10 para el vuelo a Cartagena.", "y otra a las 5 y 10 por si las moscas",
         "a las 5 y 10", None),
    ],
)
def test_placed_day_of_moment(decided: str, said: str, due: str, day: str | None) -> None:
    assert temporal.placed_day_of_moment(decided, said, due) == day
