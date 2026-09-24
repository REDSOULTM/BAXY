"""Time words shared by reminders, agenda, messages and countdowns: clock times, deictic days, months, bounded ranges. Moved from effect_intent (Fase 3.5).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from .grammar import _RELATIVE_DURATION_PATTERN, _fold, _strip_request_envelope
from .audio import _PERCENTAGE_WORD_PATTERN


_COUNTDOWN_HOUR_WORDS = {
    "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8,
    "nueve": 9, "diez": 10, "once": 11, "doce": 12, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}


_COUNTDOWN_TARGET = re.compile(
    r"^(?:cuanto\s+(?:tiempo\s+)?(?:falta|queda|resta)\s+(?:para|hasta)|"
    r"how\s+(?:long|much\s+time)\s+(?:until|till|before|to|is\s+left\s+(?:until|till|before)))\s+"
    r"(?:(?:el|la|las|the)\s+)?"
    r"(?:(?P<noon>mediodia|noon|midday)|(?P<midnight>medianoche|midnight)|"
    r"(?P<hour>\d{1,2}|" + "|".join(sorted(_COUNTDOWN_HOUR_WORDS, key=len, reverse=True)) + r")"
    r"(?:[:.h](?P<minute>\d{2}))?"
    r"(?:\s+(?:y\s+(?P<spoken_minute>media|cuarto|\d{1,2}))?)?"
    r"(?:\s*(?P<ampm>[ap])\.?\s*m\.?|\s+(?:de\s+la\s+|en\s+la\s+|in\s+the\s+|)"
    r"(?P<part>manana|madrugada|tarde|noche|morning|afternoon|evening|night))?"
    r"(?:\s+(?:de\s+hoy|today|hoy))?"
    r")\s*$"
)


def countdown_target(text: str) -> str | None:
    """«cuánto falta para las 3 de la tarde» → «15:00»: the clock time asked about.

    CLOCK1327 H0399: a countdown resolves by reading the clock; the
    remaining time is computed by the mind, never by the narrator.
    """

    folded = _strip_request_envelope(_fold(text)).strip(" ¿?¡!.,")
    match = _COUNTDOWN_TARGET.match(folded)
    if match is None:
        return None
    if match.group("noon"):
        return "12:00"
    if match.group("midnight"):
        return "00:00"
    raw_hour = match.group("hour")
    hour = int(raw_hour) if raw_hour.isdecimal() else _COUNTDOWN_HOUR_WORDS[raw_hour]
    minute = int(match.group("minute") or 0)
    spoken = match.group("spoken_minute")
    if spoken == "media":
        minute = 30
    elif spoken == "cuarto":
        minute = 15
    elif spoken and spoken.isdecimal():
        minute = int(spoken)
    part = match.group("part") or ""
    ampm = match.group("ampm") or ""
    if hour > 23 or minute > 59:
        return None
    if ampm == "p" or part in {"tarde", "noche", "afternoon", "evening", "night"}:
        if hour < 12:
            hour += 12
    elif ampm == "a" or part in {"manana", "madrugada", "morning"}:
        if hour == 12:
            hour = 0
    return f"{hour:02d}:{minute:02d}"


_CALENDAR_MONTH_TOKEN = (
    r"(?:january|february|march|april|may|june|july|august|september|"
    r"october|november|december|enero|febrero|marzo|abril|mayo|junio|"
    r"julio|agosto|septiembre|octubre|noviembre|diciembre)"
)


def _absolute_calendar_range_parts(
    text: str,
) -> tuple[str, str, str, str] | None:
    """Return the two literal month/day endpoints of one bounded range."""

    folded = _fold(text)
    match = re.search(
        rf"\b(?:timeframe\s+of|between|from|entre|desde)\s+"
        rf"(?P<start_month>{_CALENDAR_MONTH_TOKEN})\s+"
        rf"(?P<start_day>{_PERCENTAGE_WORD_PATTERN}|\d{{1,2}})\s+"
        rf"(?:and|to|through|y|a|hasta)\s+"
        rf"(?P<end_month>{_CALENDAR_MONTH_TOKEN})\s+"
        rf"(?P<end_day>{_PERCENTAGE_WORD_PATTERN}|\d{{1,2}})\b",
        folded,
        re.IGNORECASE,
    )
    if match is None:
        return None
    return (
        match.group("start_month"),
        match.group("start_day"),
        match.group("end_month"),
        match.group("end_day"),
    )


_DEICTIC_DAY = (
    r"\b(?:ese\s+dia|esa\s+fecha|el\s+mismo\s+dia|"
    r"that\s+day|that\s+date|that\s+same\s+day)\b"
)


# One spoken clock time, shared by every reader that needs one (uso real
# 2026-09-23: «a las cinco y media de la mañana», «a las diez a. m.», «esta
# tarde a las cinco» were asked morning-or-afternoon although it was said).
_CLOCK_HOUR_WORDS = {
    "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8,
    "nueve": 9, "diez": 10, "once": 11, "doce": 12, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}
_CLOCK_MINUTE_WORDS = {
    "media": 30, "cuarto": 15, "cinco": 5, "diez": 10, "quince": 15, "veinte": 20, "veinticinco": 25,
    "treinta": 30, "cuarenta": 40, "cuarenta y cinco": 45, "cincuenta": 50,
}
_CLOCK_HOUR = r"(?:[01]?[0-9]|2[0-3]|" + "|".join(sorted(_CLOCK_HOUR_WORDS, key=len, reverse=True)) + r")"
_CLOCK_MINUTE_WORD = (
    r"(?:[0-5]?[0-9]|" + "|".join(sorted(_CLOCK_MINUTE_WORDS, key=len, reverse=True)) + r")"
)
_CLOCK_MINUTES = rf"(?::[0-5][0-9]|\s+y\s+{_CLOCK_MINUTE_WORD}|\s+menos\s+{_CLOCK_MINUTE_WORD})"
# The part of the day said after the hour. «a. m.» keeps its dots optional and
# needs the «m» to end a word, so «a mi casa» is never a morning. The accented
# spellings let a reader of the person's own text use it too.
_CLOCK_PERIOD = (
    r"(?:a\.?\s*m\b\.?|p\.?\s*m\b\.?|de\s+la\s+(?:ma[nñ]ana|madrugada|tarde|noche)|"
    r"del?\s+mediod[ií]a|in\s+the\s+(?:morning|afternoon|evening)|at\s+night)"
)
# The part of the day said elsewhere in the request («esta tarde a las cinco»,
# «mañana por la mañana a las siete»).
_DAY_PART = (
    r"\b(?:(?:esta|por\s+la|en\s+la|a\s+la)\s+(?P<part>manana|madrugada|tarde|noche)|"
    r"(?:this|in\s+the)\s+(?P<english>morning|afternoon|evening)|(?P<tonight>tonight))\b"
)
_NOON_OR_MIDNIGHT = r"\b(?:al|a|el|at|para\s+el)\s+(?:mediod[ií]a|noon|midday|medianoche|midnight)\b"
_CLOCK_LEAD = r"(?:a\s+las?|para\s+las?|sobre\s+las?|hacia\s+las?|at)"
# One clock phrase with its lead («a las cinco y media de la mañana»), for
# readers that cut a request around its time.
CLOCK_PHRASE = rf"(?:{_CLOCK_LEAD}\s+(?:las?\s+)?{_CLOCK_HOUR}{_CLOCK_MINUTES}?(?:\s*{_CLOCK_PERIOD})?)"
_SPOKEN_CLOCK = re.compile(
    rf"\b(?:(?P<lead>{_CLOCK_LEAD})\s+(?:las?\s+)?)?"
    rf"(?P<hour>{_CLOCK_HOUR})(?P<minutes>{_CLOCK_MINUTES})?"
    rf"(?:\s*(?P<period>{_CLOCK_PERIOD}))?(?=\s|$|[,;:.?!])"
    # «a las dos horas», «at five minutes»: a duration is not a clock time.
    r"(?!\s+(?:minutos?|minutes?|horas?|hours?|dias?|days?|segundos?|seconds?)\b)"
)


_CLOCK_TIME_SELECTOR = (
    r"\b(?:[01]?[0-9]|2[0-3]):[0-5][0-9]\b|"
    rf"\b(?:a las?|para las?|at)\s+(?:las\s+)?{_CLOCK_HOUR}{_CLOCK_MINUTES}?"
    rf"(?:\s*{_CLOCK_PERIOD})?(?=\s|$|[,;:.?!])|"
    rf"\b{_CLOCK_HOUR}{_CLOCK_MINUTES}?\s*{_CLOCK_PERIOD}(?=\s|$|[,;:.?!])|"
    rf"{_NOON_OR_MIDNIGHT}"
)


@dataclass(frozen=True)
class SpokenClock:
    """One clock time as said: ``literal`` is its span in the folded text; ``hour`` is
    0–23 when ``resolved`` (a part of the day, a 24-hour value, noon or midnight),
    otherwise the 1–12 hour whose morning or afternoon was not said."""

    literal: str
    hour: int
    minute: int
    resolved: bool


def _read_clock(found: re.Match[str], folded: str) -> SpokenClock | None:
    minutes_text = found.group("minutes") or ""
    colon = minutes_text.startswith(":")
    raw_hour = found.group("hour")
    hour = int(raw_hour) if raw_hour.isdecimal() else _CLOCK_HOUR_WORDS[raw_hour]
    minute_word = re.sub(r"^(?::|\s+(?:y|menos)\s+)", "", minutes_text)
    minute = 0
    if minute_word:
        minute = int(minute_word) if minute_word.isdecimal() else _CLOCK_MINUTE_WORDS[minute_word]
    if minute > 59:
        return None
    if minutes_text.lstrip().startswith("menos") and minute:
        # «las cinco menos cuarto» is 4:45.
        hour, minute = (12 if hour == 1 else hour - 1), 60 - minute
    literal = found.group(0).strip()
    if hour == 0 or hour > 12:
        # A 24-hour value needs no part of the day («a las 17»).
        return SpokenClock(literal, hour, minute, True)
    period = found.group("period") or ""
    if not period:
        elsewhere = re.search(_DAY_PART, folded)
        if elsewhere is None:
            # «a las 7:30» is read as written, on the 24-hour clock.
            return SpokenClock(literal, hour, minute, colon)
        period = elsewhere.group("part") or elsewhere.group("english") or "noche"
    if re.search(r"^a\.?\s*m|manana|madrugada|morning", period):
        return SpokenClock(literal, hour % 12, minute, True)
    if "mediodia" in period:
        return SpokenClock(literal, 12 if hour == 12 else hour + 12, minute, True)
    if re.search(r"noche|night|evening", period) and (hour == 12 or hour <= 4):
        # «las doce de la noche» is midnight; «la una de la noche» is 1:00.
        return SpokenClock(literal, hour % 12, minute, True)
    return SpokenClock(literal, hour % 12 + 12, minute, True)


def spoken_clocks(folded: str) -> tuple[SpokenClock, ...]:
    """Every clock time of a folded request, read with its minutes («y media», «menos
    cuarto», «:30») and its part of the day, said after the hour or elsewhere («esta tarde
    a las cinco»); noon and midnight when no hour is said. A bare number counts only after
    «a las / para las / at», before a part of the day or with its minutes after a colon;
    an hour or a minute no clock has is not a clock."""

    clocks = tuple(
        clock
        for found in _SPOKEN_CLOCK.finditer(folded)
        if found.group("lead") or found.group("period") or (found.group("minutes") or "").startswith(":")
        if (clock := _read_clock(found, folded)) is not None
    )
    if clocks:
        return clocks
    noon = re.search(_NOON_OR_MIDNIGHT, folded)
    if noon is None:
        return ()
    midnight = re.search(r"medianoche|midnight", noon.group(0)) is not None
    return (SpokenClock(noon.group(0), 0 if midnight else 12, 0, True),)


def spoken_clock(folded: str) -> SpokenClock | None:
    """The first of ``spoken_clocks``, or None."""

    clocks = spoken_clocks(folded)
    return clocks[0] if clocks else None


_WEEKDAYS = (
    ("lunes", "monday"), ("martes", "tuesday"), ("miercoles", "wednesday"), ("jueves", "thursday"),
    ("viernes", "friday"), ("sabado", "saturday"), ("domingo", "sunday"),
)
# «mañana» is tomorrow unless it is the morning («de la mañana», «esta mañana»).
_TOMORROW = r"\btomorrow\b|(?<!\bla\s)(?<!\besta\s)\b(?:manana|maniana)\b"
# Day words that name a span, not one date («esta semana», «el mes que viene»).
_UNPLACED_DAYS = r"\b(?:semana|semanas|week|weeks|weekend|mes|meses|month|months)\b"


def spoken_day(folded: str, today_weekday: int) -> tuple[int, int] | None:
    """(days from today, days to move a moment already past) for the day a clock time is
    said on: none said is today, rolling to tomorrow; «hoy», «mañana», «pasado mañana»
    are that day and never roll; a weekday is its next occurrence, rolling a week.
    None for a span («esta semana») or two weekdays, which one date cannot hold.
    ``today_weekday`` is Monday=0."""

    if re.search(_UNPLACED_DAYS, folded):
        return None
    if re.search(r"\bpasado\s+(?:manana|maniana)\b|\bday\s+after\s+tomorrow\b", folded):
        return 2, 0
    if re.search(_TOMORROW, folded):
        return 1, 0
    named = [
        index for index, names in enumerate(_WEEKDAYS)
        if re.search(rf"\b(?:{'|'.join(names)})\b", folded)
    ]
    if len(named) > 1:
        return None
    if named:
        return (named[0] - today_weekday) % 7, 7
    if re.search(r"\b(?:hoy|today|tonight|esta\s+(?:tarde|noche|manana))\b", folded):
        return 0, 0
    return 0, 1


_BOUNDED_TEMPORAL_SELECTOR = (
    r"\b(?:hoy|today|manana|tomorrow|esta noche|tonight|"
    r"despues del trabajo hoy|after work today|"
    r"ano nuevo|dia de ano nuevo|new year's day|new year day|"
    r"esta semana|this week|"
    r"la proxima semana|next week|este mes|this month|"
    r"lunes|martes|miercoles|jueves|viernes|sabado|domingo|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b|"
    r"\b\d{4}-\d{2}-\d{2}(?:t\S+)?\b|"
    r"\b(?:a las?|para las?|at|from|de|desde)\s+(?:las\s+)?"
    r"(?:\d{1,2}(?::\d{2})?|una|dos|tres|cuatro|cinco|seis|siete|ocho|"
    r"nueve|diez|once|doce|one|two|three|four|five|six|seven|eight|nine|"
    r"ten|eleven|twelve)(?:\s*(?:a\.?\s*m\.?|p\.?\s*m\.?))?\b|"
    rf"\b{_RELATIVE_DURATION_PATTERN}\b"
)
