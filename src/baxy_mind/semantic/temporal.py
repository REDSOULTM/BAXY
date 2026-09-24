"""Time words shared by reminders, agenda, messages and countdowns: clock times, deictic days, months, bounded ranges. Moved from effect_intent (Fase 3.5).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from .grammar import _PERCENTAGE_WORD_VALUES, _RELATIVE_DURATION_PATTERN, _fold, _strip_request_envelope
from .audio import _PERCENTAGE_WORD_PATTERN
from .normalize import alternation


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


# --- Dates, spans and the window of an agenda read (uso real 2026-09-23) ----------------------------
# «tengo algo programado para el cuatro de julio de este año», «mis planes para el mes de mayo», «algún
# evento para los próximos tres meses», «añade práctica el cuatro de febrero a las dos de la tarde»: a
# date said in words, a month, a span counted from now. One reader serves the agenda read, the event
# created and the reminder's day.

MONTH_NUMBERS = {
    "enero": 1, "january": 1, "febrero": 2, "february": 2, "marzo": 3, "march": 3, "abril": 4, "april": 4,
    "mayo": 5, "may": 5, "junio": 6, "june": 6, "julio": 7, "july": 7, "agosto": 8, "august": 8,
    "septiembre": 9, "setiembre": 9, "september": 9, "octubre": 10, "october": 10, "noviembre": 11,
    "november": 11, "diciembre": 12, "december": 12,
}
_MONTH = alternation(tuple(MONTH_NUMBERS))
_ENGLISH_ORDINALS = (
    "first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth",
    "eleventh", "twelfth", "thirteenth", "fourteenth", "fifteenth", "sixteenth", "seventeenth",
    "eighteenth", "nineteenth", "twentieth",
)
_DAY_WORDS = {
    **{word: value for word, value in _PERCENTAGE_WORD_VALUES.items() if 1 <= value <= 31 and word != "un"},
    **{word: index for index, word in enumerate(_ENGLISH_ORDINALS, 1)},
    **{f"twenty {word}": 20 + index for index, word in enumerate(_ENGLISH_ORDINALS[:9], 1)},
    "thirtieth": 30, "thirty first": 31, "primero": 1,
}
_DAY = (
    r"(?:(?:3[01]|[12][0-9]|0?[1-9])(?:st|nd|rd|th)?|"
    + alternation(tuple(_DAY_WORDS)).replace(r"\ ", r"\s+")
    + ")"
)
# What follows a number that is not a day of the month («el dos por ciento», «el cinco de la tarde»).
_NOT_A_DAY_AFTER = (
    r"(?![\w%])(?!\s+(?:horas?|hours?|minutos?|minutes?|dias?|days?|semanas?|weeks?|meses|months?|"
    r"anos|years|por\s+ciento|percent|veces|times|de\s+la|en\s+punto|y\s+media|y\s+cuarto)\b)"
)
_SPOKEN_DATE = re.compile(
    rf"\b(?:(?P<day>{_DAY})\s+(?:(?:de|of)\s+)?(?P<month>{_MONTH})"
    rf"|(?P<month_first>{_MONTH})\s+(?:the\s+)?(?P<day_after>{_DAY})"
    rf"|(?:el|on\s+the|the|dia)\s+(?P<day_alone>{_DAY})(?!\s+(?:(?:de|of)\s+)?{_MONTH}\b))"
    r"(?:,?\s+(?:(?:de|del|of)\s+)?(?P<year>\d{4})|\s+(?:(?:de|del|of)\s+)?(?P<this_year>este\s+ano|this\s+year))?"
    + _NOT_A_DAY_AFTER
)


def _hyphens_as_spaces(folded: str) -> str:
    """«twenty-first», «fifty-two»: a hyphen between words is a space to the number readers."""

    return re.sub(r"(?<=[a-z])-(?=[a-z])", " ", folded)


def _day_value(word: str) -> int:
    digits = re.match(r"\d+", word)
    return int(digits.group()) if digits else _DAY_WORDS[" ".join(word.split())]


@dataclass(frozen=True)
class SpokenDate:
    """A calendar date as said. ``month`` None is that day of whichever month comes next
    («el veintiuno»); ``year`` None is the next such date, unless ``this_year`` («de este año»)."""

    literal: str
    day: int
    month: int | None
    year: int | None
    this_year: bool

    def on_or_after(self, today: date) -> date | None:
        """The date meant, read from ``today``: a date without its year is the next one; with its year
        (or «de este año») it is that one even when it has passed. None for a date no calendar has."""

        if self.month is None:
            year, month = today.year, today.month
            for _ in range(13):
                try:
                    candidate: date | None = date(year, month, self.day)
                except ValueError:
                    candidate = None
                if candidate is not None and candidate >= today:
                    return candidate
                year, month = (year + 1, 1) if month == 12 else (year, month + 1)
            return None
        years = (
            (self.year,) if self.year is not None
            else (today.year,) if self.this_year
            else (today.year, today.year + 1)
        )
        for year in years:
            try:
                candidate = date(year, self.month, self.day)
            except ValueError:
                continue
            if len(years) == 1 or candidate >= today:
                return candidate
        return None


def spoken_date(folded: str) -> SpokenDate | None:
    """The one calendar date a folded request says, in digits or words, Spanish or English
    («el cuatro de julio de este año», «fourth of july», «march seven», «el 21», «el veintiuno»);
    None when it says none or two different ones."""

    dates = {
        SpokenDate(
            found.group(0).strip(),
            _day_value(found.group("day") or found.group("day_after") or found.group("day_alone")),
            MONTH_NUMBERS[month] if (month := found.group("month") or found.group("month_first")) else None,
            int(found.group("year")) if found.group("year") else None,
            found.group("this_year") is not None,
        )
        for found in _SPOKEN_DATE.finditer(_hyphens_as_spaces(folded))
    }
    if len({(item.day, item.month, item.year) for item in dates}) != 1:
        return None
    return next(iter(dates))


# How long an agenda read looks ahead when no time is said («qué tengo por venir», «cuándo es mi
# brunch con Jennifer»): the next thirty days, a window the provider bounds and the reply can name.
UPCOMING_DAYS = 30

_SPAN_COUNT_WORDS = alternation(
    tuple(word for word, value in _PERCENTAGE_WORD_VALUES.items() if 1 <= value <= 24) + ("una",)
).replace(r"\ ", r"\s+")
_RELATIVE_SPAN = re.compile(
    r"\b(?:(?P<ahead>proxim[oa]s|siguientes|next|coming)|(?P<behind>ultim[oa]s|pasad[oa]s|last|past))\s+"
    rf"(?P<count>\d{{1,2}}|{_SPAN_COUNT_WORDS})\s+(?P<unit>dias?|days?|semanas?|weeks?|mes(?:es)?|months?)\b"
    rf"|\b(?P<count_first>\d{{1,2}}|{_SPAN_COUNT_WORDS})\s+"
    r"(?:(?P<ahead_after>proxim[oa]s|siguientes)|(?P<behind_after>ultim[oa]s))\s+"
    r"(?P<unit_first>dias|semanas|meses)\b"
)
_NTH_WEEK = re.compile(
    r"\b(?P<nth>primera|segunda|tercera|cuarta|ultima|first|second|third|fourth|last)\s+"
    rf"(?:semana\s+de|week\s+of)\s+(?:(?:the\s+)?month\s+of\s+|(?:el\s+)?mes\s+de\s+)?(?P<month>{_MONTH})\b"
)
_SPOKEN_MONTH = re.compile(
    rf"\b(?:(?:el\s+)?mes\s+de|(?:the\s+)?month\s+of|en|para|in|for|during|durante|de)\s+(?P<month>{_MONTH})\b"
    rf"(?!\s+(?:the\s+)?{_DAY}\b)"
)
# Parts of a day an agenda read is bounded to (local hours, the end exclusive).
_PART_HOURS = {
    "madrugada": (0, 6), "manana": (6, 12), "morning": (6, 12), "tarde": (12, 20), "afternoon": (12, 20),
    "noche": (18, 24), "evening": (18, 24), "tonight": (18, 24),
}


def _add_months(moment: datetime, months: int) -> datetime:
    index = moment.month - 1 + months
    year, month = moment.year + index // 12, index % 12 + 1
    last_day = (date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)).day
    return moment.replace(year=year, month=month, day=min(moment.day, last_day))


def _month_span(month: int, today: date) -> tuple[date, date]:
    """The month named: this year's while it has not ended, otherwise next year's."""

    start = date(today.year + (month < today.month), month, 1)
    return start, _add_months(datetime.combine(start, time()), 1).date()


def _relative_span(text: str, now: datetime) -> tuple[datetime, datetime] | None:
    """«los próximos tres meses», «the last two weeks»: a span counted from ``now``."""

    span = _RELATIVE_SPAN.search(text)
    if span is None:
        return None
    raw = " ".join((span.group("count") or span.group("count_first")).split())
    count = int(raw) if raw.isdecimal() else 1 if raw == "una" else _PERCENTAGE_WORD_VALUES[raw]
    unit = span.group("unit") or span.group("unit_first")
    forward = bool(span.group("ahead") or span.group("ahead_after"))
    sign = 1 if forward else -1
    if unit.startswith(("mes", "month")):
        other = _add_months(now, sign * count)
    else:
        other = now + timedelta(days=sign * count * (7 if unit.startswith(("semana", "week")) else 1))
    return (now, other) if forward else (other, now)


def _said_days(text: str, today: date) -> set[tuple[date, date]]:
    """Every run of whole days a folded request names (the end exclusive)."""

    days: set[tuple[date, date]] = set()

    def add(start: date, length: int = 1) -> None:
        days.add((start, start + timedelta(days=length)))

    if re.search(r"\b(?:ano\s+nuevo|new\s+year'?s?\s+day)\b", text):
        add(date(today.year + (today > date(today.year, 1, 1)), 1, 1))
    if re.search(r"\bpasado\s+(?:manana|maniana)\b|\bday\s+after\s+tomorrow\b", text):
        add(today + timedelta(days=2))
    elif re.search(_TOMORROW, text):
        add(today + timedelta(days=1))
    if re.search(
        r"\b(?:hoy|today|tonight|esta\s+jornada|this\s+day|for\s+the\s+day|"
        rf"(?:(?:para|de|en)\s+el|del)\s+dia(?!\s+{_DAY}\b))\b",
        text,
    ):
        add(today)
    saturday = (
        today - timedelta(days=1) if today.weekday() == 6 else today + timedelta(days=(5 - today.weekday()) % 7)
    )
    if re.search(r"\bproximo\s+fin\s+de\s+semana\b|\bfin\s+de\s+semana\s+que\s+viene\b|\bnext\s+weekend\b", text):
        add(saturday + timedelta(days=7), 2)
    elif re.search(r"\bfin\s+de\s+semana\b|\bweekend\b", text):
        add(saturday, 2)
    monday = today - timedelta(days=today.weekday())
    if re.search(r"\bproxima\s+semana\b|(?<!\bfin\sde\s)\bsemana\s+que\s+viene\b|\bnext\s+weeks?\b", text):
        add(monday + timedelta(days=7), 7)
    elif re.search(r"\bsemana\s+pasada\b|\blast\s+week\b", text):
        add(monday - timedelta(days=7), 7)
    elif re.search(r"\besta\s+semana\b|\bthis\s+week\b", text):
        add(monday, 7)
    first_of_month = datetime.combine(today.replace(day=1), time())
    for pattern, offset in (
        (r"\bproximo\s+mes\b|\bmes\s+que\s+viene\b|\bnext\s+month\b", 1),
        (r"\bmes\s+pasado\b|\blast\s+month\b", -1),
        (r"\beste\s+mes\b|\bthis\s+month\b", 0),
    ):
        if re.search(pattern, text):
            start = _add_months(first_of_month, offset)
            days.add((start.date(), _add_months(start, 1).date()))
            break
    said_date = spoken_date(text)
    weekdays = [index for index, names in enumerate(_WEEKDAYS) if re.search(rf"\b(?:{'|'.join(names)})\b", text)]
    if said_date is not None:
        on = said_date.on_or_after(today)
        if on is not None:
            add(on)
    elif len(weekdays) == 1:
        ahead = (weekdays[0] - today.weekday()) % 7
        if ahead == 0 and re.search(r"\b(?:proxim[oa]|que\s+viene|next|coming)\b", text):
            ahead = 7
        add(today + timedelta(days=ahead))
    elif weekdays:
        # Two weekdays: no one window holds them.
        days.update({(today, today), (today, today + timedelta(days=1))})
    nth = _NTH_WEEK.search(text)
    if nth is not None:
        start, end = _month_span(MONTH_NUMBERS[nth.group("month")], today)
        index = {"primera": 0, "first": 0, "segunda": 1, "second": 1, "tercera": 2, "third": 2,
                 "cuarta": 3, "fourth": 3}.get(nth.group("nth"))
        add(end - timedelta(days=7) if index is None else start + timedelta(days=7 * index), 7)
    elif said_date is None and (month := _SPOKEN_MONTH.search(text)) is not None:
        days.add(_month_span(MONTH_NUMBERS[month.group("month")], today))
    return days


def _said_windows(text: str, now: datetime) -> list[tuple[datetime, datetime]]:
    """Every window a folded request says; the caller keeps one."""

    absolute = _absolute_calendar_range_parts(text)
    if absolute is not None:
        start_month, end_month = MONTH_NUMBERS[absolute[0]], MONTH_NUMBERS[absolute[2]]
        try:
            start_day, end_day = _day_value(absolute[1]), _day_value(absolute[3])
            first = date(now.year, start_month, start_day)
            end_year = now.year + int((end_month, end_day) < (start_month, start_day))
            # The spoken final day is included: the end is the next midnight.
            last = date(end_year, end_month, end_day) + timedelta(days=1)
        except (KeyError, ValueError):
            return []
        return [(datetime.combine(first, time()), datetime.combine(last, time()))]
    span = _relative_span(text, now)
    if span is not None:
        return [span]
    days = _said_days(text, now.date())
    part = None
    if re.search(r"\b(?:after\s+work|despues\s+del\s+trabajo)\b", text):
        part = (17, 24)
    elif (part_found := re.search(_DAY_PART, text)) is not None:
        part = _PART_HOURS[part_found.group("part") or part_found.group("english") or "tonight"]
    if not days and part is not None:
        days.add((now.date(), now.date() + timedelta(days=1)))
    windows = []
    for start, end in days:
        if part is not None and end - start == timedelta(days=1):
            windows.append((datetime.combine(start, time(part[0])), datetime.combine(start, time()) + timedelta(hours=part[1])))
        else:
            windows.append((datetime.combine(start, time()), datetime.combine(end, time())))
    return windows


def spoken_window(folded: str, now: datetime) -> tuple[datetime, datetime] | None:
    """The one window of local time a folded request says (a day, a part of it, a week, a month, a
    date, a span counted from ``now``), as naive local datetimes with the end exclusive; None when it
    says none or more than one («hoy y mañana»). ``now`` is naive local time."""

    windows = _said_windows(_hyphens_as_spaces(folded), now)
    return windows[0] if len(windows) == 1 else None


_WINDOW_WORDS = frozenset(
    "para for el la los las the this esta este estos estas next proximo proxima proximos proximas que viene "
    "de del of on en in a al at during durante later luego mas tarde tardes noche noches manana madrugada hoy "
    "today tomorrow tonight morning afternoon evening pasado pasada day days dia dias semana semanas week weeks "
    "weekend weekends fin mes meses month months ano year ultimos ultimas last past siguientes coming after "
    "despues work trabajo mismo entero entera completo completa whole primera segunda tercera cuarta ultima "
    "second third several few couple varios varias unos unas pocos pocas upcoming venir".split()
) | frozenset(MONTH_NUMBERS) | frozenset(name for names in _WEEKDAYS for name in names) | frozenset(
    token for word in _DAY_WORDS for token in word.split()
)


def is_window_phrase(folded: str) -> bool:
    """«para el cuatro de julio de este año», «la semana que viene», «this afternoon», «the next few
    days»: the words say a window of time, or what is coming, and nothing else (a stricter test than
    finding one inside a longer request)."""

    tokens = re.findall(r"[a-z0-9']+", _hyphens_as_spaces(folded))
    return (
        bool(tokens)
        and all(token in _WINDOW_WORDS or re.fullmatch(r"\d{1,4}(?:st|nd|rd|th)?", token) for token in tokens)
        and (
            bool(_said_windows(" ".join(tokens), datetime(2000, 1, 3)))
            or bool({"next", "proximos", "proximas", "coming", "siguientes", "upcoming", "venir"} & set(tokens))
        )
    )


# --- When an event happens (uso real 2026-09-23 «añade una reunión con Tom a mi calendario para las
# nueve de la mañana», «no estoy disponible de cuatro a seis de la tarde», «una reunión de dos horas»,
# «pon el almuerzo todos los días a las doce y media») -------------------------------------------------
_CLOCK_BODY = (
    rf"(?:las?\s+)?{_CLOCK_HOUR}{_CLOCK_MINUTES}?(?:\s+(?:en\s+punto|o'?clock))?(?:\s*(?P<{{name}}_period>{_CLOCK_PERIOD}))?"
)
_CLOCK_RANGE = re.compile(
    r"\b(?:de|desde|from|entre|between)\s+(?P<start>" + _CLOCK_BODY.format(name="start") + r")\s+"
    r"(?:a|hasta|to|until|till|y|and)\s+(?P<end>" + _CLOCK_BODY.format(name="end") + r")(?=\s|$|[,;:.?!])"
)
_CLOCK_UNTIL = re.compile(
    r"\b(?:hasta|until|till)\s+(?P<end>" + _CLOCK_BODY.format(name="end") + r")(?=\s|$|[,;:.?!])"
)
_EVENT_DURATION = re.compile(
    r"\b(?:durante|por|for|de|lasting)\s+(?:(?P<half>media|half\s+an?)\s+|(?P<amount>\d{1,2}|"
    + alternation(tuple(word for word, value in _PERCENTAGE_WORD_VALUES.items() if 1 <= value <= 12) + ("una", "an", "a"))
    .replace(r"\ ", r"\s+")
    + r")\s+)(?P<unit>horas?|hours?|minutos?|minutes?|mins?)\b"
)
_RECURRENCE = re.compile(
    r"\b(?:(?:cada|todos\s+los|todas\s+las|every|each)\s+(?:(?P<skip>dos|two|other)\s+)?(?P<unit>\w+)"
    rf"(?:\s+(?:de|of|in|en)\s+(?P<month>{_MONTH}))?|(?P<word>diariamente|a\s+diario|daily|hourly|weekly|"
    r"semanalmente|mensualmente|monthly|anualmente|yearly))\b"
)
_DAY_PHRASE = re.compile(
    r"\b(?:hoy|today|tonight|tomorrow|pasado\s+manana|manana|madrugada|tarde|noche|mediodia|noon|"
    r"morning|afternoon|evening|night|semana|week|weekend|fin\s+de\s+semana|mes|month|"
    + "|".join(rf"{name}s?" for names in _WEEKDAYS for name in names)
    + r")(?:\s+(?:que\s+viene|proxim[oa]|pasad[oa]|next))?\b"
)
# Words that lead into a time phrase («el», «para el», «on the», «de»): cut with it from a title.
_TIME_LEAD_WORDS = frozenset(
    "el la los las para for on at the a al de del this este esta next proximo proxima coming en in "
    "por durante during".split()
)


@dataclass(frozen=True)
class EventTiming:
    """When an event said in one request happens: its ``start`` and ``end`` clocks (the end of a
    range or «hasta»), a said duration in ``minutes``, a ``recurrence`` («cada …», «daily»; the
    repeated unit, folded) with the month that bounds it, and every time phrase's span in the folded
    text (``spans``), so the words left are what the event is."""

    start: SpokenClock | None
    end: SpokenClock | None
    minutes: int | None
    recurrence: str | None
    recurrence_month: int | None
    spans: tuple[tuple[int, int], ...]


def _range_clock(body: str, period: str | None, folded: str) -> SpokenClock | None:
    """A clock said inside a range («de cuatro a seis de la tarde»), with the range's part of the day."""

    phrase = "a " + body if re.match(r"las?\b", body) else "a las " + body
    if period and not re.search(_CLOCK_PERIOD + r"\s*$", body):
        phrase += " " + period
    found = _SPOKEN_CLOCK.match(phrase)
    return _read_clock(found, folded) if found is not None else None


def event_timing(folded: str) -> EventTiming:
    """The time phrases of one folded request about an event (see ``EventTiming``)."""

    text = _hyphens_as_spaces(folded)
    spans: list[tuple[int, int]] = []
    start = end = None
    ranged = _CLOCK_RANGE.search(text)
    if ranged is not None:
        spans.append(ranged.span())
        end_period = ranged.group("end_period")
        end = _range_clock(ranged.group("end"), None, text)
        start = _range_clock(ranged.group("start"), end_period, text)
    else:
        until = _CLOCK_UNTIL.search(text)
        if until is not None:
            spans.append(until.span())
            end = _range_clock(until.group("end"), None, text)
        for found in _SPOKEN_CLOCK.finditer(text):
            if until is not None and until.start() <= found.start() < until.end():
                continue
            if found.group("lead") or found.group("period") or (found.group("minutes") or "").startswith(":"):
                spans.append(found.span())
                if start is None:
                    start = _read_clock(found, text)
        if start is None and (noon := re.search(_NOON_OR_MIDNIGHT, text)) is not None:
            spans.append(noon.span())
            start = SpokenClock(noon.group(0), 0 if re.search("medianoche|midnight", noon.group(0)) else 12, 0, True)
    minutes = None
    duration = _EVENT_DURATION.search(text)
    if duration is not None:
        spans.append(duration.span())
        if duration.group("half"):
            minutes = 30
        else:
            raw = " ".join(duration.group("amount").split())
            amount = int(raw) if raw.isdecimal() else 1 if raw in {"una", "an", "a"} else _PERCENTAGE_WORD_VALUES[raw]
            minutes = amount * (60 if duration.group("unit").startswith(("hora", "hour")) else 1)
    recurrence = None
    recurrence_month = None
    repeated = _RECURRENCE.search(text)
    if repeated is not None:
        spans.append(repeated.span())
        # «cada dos días» repeats, but not daily: the skip stays in what is read.
        recurrence = " ".join(filter(None, (repeated.group("skip"), repeated.group("unit") or repeated.group("word"))))
        recurrence_month = MONTH_NUMBERS[repeated.group("month")] if repeated.group("month") else None
    spans.extend(found.span() for found in re.finditer(r"\b(?:en\s+punto|o'?clock)\b", text))
    spans.extend(found.span() for found in _DAY_PHRASE.finditer(text))
    spans.extend(found.span() for found in _SPOKEN_DATE.finditer(text))
    spans.extend(found.span() for found in _NTH_WEEK.finditer(text))
    spans.extend(found.span() for found in _SPOKEN_MONTH.finditer(text))
    spans.extend(found.span() for found in _RELATIVE_SPAN.finditer(text))
    return EventTiming(start, end, minutes, recurrence, recurrence_month, _with_leads(text, spans))


def _with_leads(text: str, spans: list[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    """Each span widened over the lead words right before it («para el» martes, «on the» 21st)."""

    widened = []
    for start, end in spans:
        while True:
            before = re.search(r"(\S+)\s+$", text[:start])
            if before is None or before.group(1) not in _TIME_LEAD_WORDS:
                break
            start = before.start(1)
        widened.append((start, end))
    return tuple(sorted(widened))


def says_a_window(folded: str) -> bool:
    """Whether a folded request says any window of time («el martes», «esta tarde», «en mayo»)."""

    return bool(_said_windows(_hyphens_as_spaces(folded), datetime(2000, 1, 3)))


def agenda_window(folded: str, now: datetime) -> tuple[datetime, datetime] | None:
    """The window an agenda read covers: the one it says, or the next ``UPCOMING_DAYS`` from ``now``
    when it says none («qué tengo por venir»); None when it says more than one."""

    windows = _said_windows(_hyphens_as_spaces(folded), now)
    if not windows:
        return now, now + timedelta(days=UPCOMING_DAYS)
    return windows[0] if len(windows) == 1 else None
