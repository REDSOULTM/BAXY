"""M130 — D61b (owner, 2026-10-02): on another day the person names, an hour of 1 to 12 said without its part of the
day is a daytime hour — 1 to 6 the afternoon, 7 to 11 the morning, 12 noon («agendá una reunión el viernes a las 3» is
15:00, not 03:00). Today it stays D61: the next time that hour comes; a passed hour that rolls to tomorrow on its own
keeps D61 too, because that day was not said. Every phrasing here is our own.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from baxy_mind import __main__ as sidecar

LOCAL = timezone(timedelta(hours=-3))


def _at(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 10, day, hour, minute, tzinfo=LOCAL)  # Friday 2 October 2026


def _local(utc: str | None) -> datetime | None:
    return None if utc is None else datetime.fromisoformat(utc.replace("Z", "+00:00")).astimezone(LOCAL)


@pytest.mark.parametrize(
    ("value", "context", "now", "expected"),
    [
        # A day said: a daytime hour.
        ("a las 3", "agenda una reunión el lunes a las 3", _at(2, 10), _at(5, 15)),
        ("a las 3", "recuérdame mañana a las 3 pagar la luz", _at(2, 10), _at(3, 15)),
        ("a las 6", "pon una alarma el domingo a las 6", _at(2, 10), _at(4, 18)),
        ("a las 7", "despiértame mañana a las 7", _at(2, 15), _at(3, 7)),
        ("a las 11", "agenda el dentista el martes a las 11", _at(2, 15), _at(6, 11)),
        ("a las 12", "almuerzo con Ana mañana a las 12", _at(2, 15), _at(3, 12)),
        ("at 4", "remind me tomorrow at 4 to call mom", _at(2, 10), _at(3, 16)),
        # What was said still decides it.
        ("a las 3 de la mañana", "pon una alarma mañana a las 3 de la mañana", _at(2, 10), _at(3, 3)),
        ("a las 3 de la madrugada", "el lunes a las 3 de la madrugada", _at(2, 10), _at(5, 3)),
        ("a las 15", "agenda una reunión el lunes a las 15", _at(2, 10), _at(5, 15)),
        # Today: D61, the next time it comes.
        ("a las 3", "pon una alarma a las 3", _at(2, 10), _at(2, 15)),
        ("a las 3", "pon una alarma a las 3", _at(2, 1), _at(2, 3)),
        # A passed hour rolls on its own to tomorrow: that day was not said, so D61 still holds.
        ("a las 3", "pon una alarma a las 3", _at(2, 23), _at(3, 3)),
    ],
)
def test_a_named_day_takes_the_daytime_hour(value: str, context: str, now: datetime, expected: datetime) -> None:
    assert _local(sidecar._canonical_due_utc(value, context, now_utc=now)) == expected
