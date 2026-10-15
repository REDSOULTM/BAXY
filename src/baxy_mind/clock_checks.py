"""The clocks a reply states, checked against the ones the result observed: scheduled notifications, exact
clock assertions and a clock a failure invents.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta

from .semantic.normalize import _accent_folded_with_punctuation
from .semantic.temporal import named_clock_dial
from .effect_intent import _PERCENTAGE_WORD_VALUES
from .semantic.request import fold as _reading_fold
from .semantic.network import _CALENDAR_MONTH_NUMBERS
from .clock_facts import _CALENDAR_DATE_PATTERNS, _local_now, _MERIDIEM_HOUR
from .compose_situation import _local_clock_from_situation, _merged_observed, attempted_texts


def _scheduled_notification_defect(text: str, dues: list[datetime]) -> str:
    """Tanda 5 / 6b: each scheduled alarm is told at its local time (HH:MM or its hour said «2 pm», «las 2 de la
    tarde»), no other time and no UTC; a date or a day word («today», «mañana») said must be one of theirs —
    «Alarms scheduled for 2 pm and 3 pm today.» for two alarms due tomorrow is false."""

    moments = [due.astimezone() for due in dues]
    expected = {(moment.hour, moment.minute) for moment in moments}
    folded = _accent_folded_with_punctuation(text).casefold()
    said = set(_clock_values(text)) | {
        (int(hour) % 12 + (12 if (marker or "") == "p" or part in {"tarde", "noche"} else 0), 0)
        for hour, marker, part in _MERIDIEM_HOUR.findall(folded)
        if 1 <= int(hour) <= 12
    }
    if not expected <= said:
        return "missing_state"
    if said - expected:
        return "reversed_result"
    if re.search(r"\bUTC\b|\bGMT\b", text, re.IGNORECASE):
        return "missing_state"
    days = {moment.date() for moment in moments}
    for pattern in _CALENDAR_DATE_PATTERNS:
        for match in pattern.finditer(text.casefold()):
            month = int(match["month"]) if match["month"].isdigit() else _CALENDAR_MONTH_NUMBERS[match["month"]]
            if not any(
                (day.month, day.day) == (month, int(match["day"]))
                and (match["year"] is None or int(match["year"]) == day.year)
                for day in days
            ):
                return "extra_claim"
    today = _local_now().date()
    relative = _reading_fold(text)
    for offset, word in (
        (0, r"\b(?:hoy|today|tonight|esta\s+(?:noche|tarde)|this\s+(?:afternoon|evening))\b"),
        # «de la mañana», «esta mañana» are a part of the day, «pasado mañana» another day.
        (1, r"(?<!\bafter )\btomorrow\b|(?<!\bla )(?<!\besta )(?<!\bpasado )\bmanana\b"),
        (2, r"\bpasado\s+manana\b|\bday\s+after\s+tomorrow\b"),
    ):
        if re.search(word, relative) and today + timedelta(days=offset) not in days:
            return "extra_claim"
    return ""


def _clock_only_from_situation(situation: dict) -> bool:
    if not _local_clock_from_situation(situation):
        return False
    observed = _merged_observed(situation)
    return "muted" not in observed and "level" not in observed


_CLOCK_TOKENS = re.compile(
    r"\b(\d{1,2})(?::|\s+(?:horas?\s+y|hours?\s+and)\s+)"
    r"(\d{2})(?:\s+(?:minutos?|minutes?))?"
    r"(?:\s*([ap])\.?\s*m\.?)?\b",
    re.IGNORECASE,
)
_CLOCK_CARDINAL_VALUES = {**_PERCENTAGE_WORD_VALUES, "una": 1}


def _clock_cardinal_pattern(maximum: int) -> str:
    # Reuse the bounded ES/EN cardinal lexicon; only a clock frame below makes
    # these words a time rather than ordinary counts in the surrounding prose.
    words = sorted(
        (word for word, value in _CLOCK_CARDINAL_VALUES.items() if value <= maximum),
        key=len,
        reverse=True,
    )
    return (
        r"(?:\d{1,2}|"
        + "|".join(re.escape(word).replace(r"\ ", r"[\s-]+") for word in words)
        + ")"
    )


_SPOKEN_CLOCK_TOKENS = re.compile(
    r"\b(?:son\s+las|es\s+la|"
    r"the\s+(?:local\s+)?time\s+is)\s+"
    rf"({_clock_cardinal_pattern(23)})(?:\s+(?:horas?|hours?))?"
    r"(?:\s+(?:y|and)\s+|\s+)"
    rf"({_clock_cardinal_pattern(59)})"
    r"(?:\s+(?:minutos?|minutes?))?(?:\s*([ap])\.?\s*m\.?)?\b",
    re.IGNORECASE,
)


_NAMED_CLOCK_TOKENS = re.compile(
    r"(?:^|[.!?;,]\s*|(?P<alternative>\b(?:o|or)\s+))"
    r"(?:"
    r"(?P<noon>(?:(?:es(?:\s+el)?|it's|it\s+is|the\s+(?:local\s+)?time\s+is)\s+)?"
    r"(?:mediodia|noon)|son\s+las\s+(?:12|doce)\s+del\s+mediodia|12\s+noon)"
    r"|(?:(?:es|it's|it\s+is|the\s+(?:local\s+)?time\s+is)\s+)?"
    r"(?:medianoche|midnight)|son\s+las\s+(?:12|doce)\s+de\s+la\s+noche|12\s+midnight"
    r")(?=\s*(?:$|[.!?;,]|\b(?:o|or)\b))",
    re.IGNORECASE,
)


def _clock_values(text: str) -> list[tuple[int, int]]:
    """Extract exact clock assertions, retaining every conflicting value."""
    folded = _accent_folded_with_punctuation(text).strip()
    # End positions tie an alternative to an already asserted clock. Bare
    # references such as "before noon" and negated statements supply no value.
    tokens: list[tuple[int, tuple[int, int]]] = []
    for match in [*_CLOCK_TOKENS.finditer(folded), *_SPOKEN_CLOCK_TOKENS.finditer(folded)]:
        values = [
            int(part)
            if part.isdecimal()
            else _CLOCK_CARDINAL_VALUES[re.sub(r"[\s-]+", " ", part)]
            for part in (match[1], match[2])
        ]
        named_hour, named_minute = values
        marker = match[3]
        if marker:
            if not 1 <= named_hour <= 12:
                tokens.append((match.end(), (-1, -1)))
                continue
            named_hour = named_hour % 12 + (12 if marker.lower() == "p" else 0)
        tokens.append((match.end(), (named_hour, named_minute)))
    for match in _NAMED_CLOCK_TOKENS.finditer(folded):
        if match["alternative"] and not any(end <= match.start() for end, _ in tokens):
            continue
        tokens.append((match.end(), (12 if match["noon"] else 0, 0)))
    return [value for _, value in tokens]


def _clock_fact_defect(
    text: str, hhmm: str, *, required: bool = True, allowed: tuple[tuple[int, int], ...] = (),
) -> str:
    try:
        hour_text, minute_text = hhmm.split(":", 1)
        observed = (int(hour_text), int(minute_text))
    except (TypeError, ValueError):
        return "missing_name"
    values = _clock_values(text)
    if required and observed not in values:
        return "missing_name"
    # CLOCK1327: a countdown answer legitimately names its target time and the
    # remaining hours and minutes; those are not contrary clock claims.
    return "reversed_result" if any(value != observed and value not in allowed for value in values) else ""


_REPLY_CLOCK = re.compile(r"(?<!\d)(\d{1,2}):(\d{2})(?!\d)")


def _failure_invents_a_clock(text: str, user_text: str, situation: dict) -> bool:
    """M63 (v3f-final F-s019 «Cambia la alarma despertador de las 8:00 a las 9:00.»): a failure that read no clock
    says only the clocks the person named, in any equivalent form («8:00», «08:00», «20:00» for «las 8»); any other
    is invented. The twin of the App's UserMessagePolicy.InventedClock, so that the mind retries what the App would
    drop (the App dropped the right answer when it counted the person's own clocks as invented). M116: a clock in
    what the failed step attempted (the words of a message said in an earlier turn) was named too."""

    if _local_clock_from_situation(situation) or _REPLY_CLOCK.search(json.dumps(situation, ensure_ascii=False)):
        return False
    named = named_clock_dial(user_text)
    for said in attempted_texts(situation):
        named |= named_clock_dial(said)
    return any((int(hour) % 12, int(minute)) not in named for hour, minute in _REPLY_CLOCK.findall(text))
