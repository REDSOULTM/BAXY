"""HOR4: the clock line tells the part of the day beside the 24-hour time, and no 12-hour reading.
HOR1/HOR2 (INFORME_HOR2): «¿Qué hora es?» was wrong 23 of 144 times on 1.5.1, where the model turned the 24-hour time into a
12-hour one itself («11:17 PM» at 22:17, «11:10 de la mañana» at 00:10). HOR3 (INFORME_HOR3): any 12-hour reading in the line
made the model take it for the whole answer and count other days' dates itself («hace 10 días»); the part of the day alone
kept the date questions (66 → 72 of 130) and took the time 23 → 9 of 144."""
import datetime as dt
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "renew" / "decisiones"))

try:
    import banco  # noqa: E402
except ModuleNotFoundError:  # the public tree does not carry the internal bench (scripts/renew)
    banco = None
from baxy_mind.mind import Mind  # noqa: E402

MINUS_3 = dt.timezone(dt.timedelta(hours=-3))
FORM = r"\d\d:\d\d hora local \((?:de la|del) \w+\), UTC[+-]\d\d:\d\d, \w+ \d{4}-\d\d-\d\d"


@pytest.mark.parametrize(("hour", "minute", "part"), [
    (22, 17, "de la noche"), (0, 10, "de la noche"), (20, 0, "de la noche"), (23, 59, "de la noche"),
    (3, 40, "de la madrugada"), (5, 59, "de la madrugada"), (6, 0, "de la mañana"), (9, 5, "de la mañana"),
    (12, 0, "del mediodía"), (12, 30, "del mediodía"), (13, 10, "de la tarde"), (19, 59, "de la tarde")])
def test_the_clock_line_tells_the_part_of_the_day(hour: int, minute: int, part: str) -> None:
    at = dt.datetime(2026, 11, 11, hour, minute, tzinfo=MINUS_3)
    assert Mind._clock_text(at) == f"{hour:02d}:{minute:02d} hora local ({part}), UTC-03:00, Wednesday 2026-11-11"


def test_the_clock_line_tells_no_twelve_hour_reading() -> None:
    told = Mind._clock_text(dt.datetime(2026, 11, 9, 22, 10, tzinfo=MINUS_3))
    assert "10:10" not in told and "p. m." not in told and "a. m." not in told


def test_the_clock_of_the_turn_and_the_benchs_fixed_clock_are_one_form() -> None:
    if banco is None:
        pytest.skip("the bench (scripts/renew/decisiones) is not in this tree")

    class Fixed(Mind):
        pass

    banco.fix_clock(Fixed, "2026-11-11T00:10-03:00")
    assert Fixed._clock_time() == Mind._clock_text(dt.datetime(2026, 11, 11, 0, 10, tzinfo=MINUS_3))
    assert re.fullmatch(FORM, Mind._clock_time())
