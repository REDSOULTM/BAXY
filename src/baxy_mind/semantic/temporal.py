"""Time words shared by reminders, agenda, messages and countdowns: clock times, deictic days, months, bounded ranges. Moved from effect_intent (Fase 3.5).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Iterable
from .grammar import _PERCENTAGE_WORD_VALUES, _RELATIVE_DURATION_PATTERN, _fold, _has, _strip_request_envelope, spoken_cardinal
from .audio import _PERCENTAGE_WORD_PATTERN
from .normalize import alternation


_COUNTDOWN_HOUR_WORDS = {
    "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8,
    "nueve": 9, "diez": 10, "once": 11, "doce": 12, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}


# Tanda 7 «¿cuánto rato queda para las seis?» was searched on the web: the time left is asked with any measure of
# time («rato», «horas», «minutos», «qué tanto») and any verb of remaining, singular or plural; «how many minutes
# until», «how much time is left till», «how long do we have until» are the same countdown.
_COUNTDOWN_HEAD = (
    r"(?:(?:cuant[oa]s?|que\s+tanto)\s+(?:(?:tiempo|rato|horas?|minutos?)\s+)?(?:falta|faltan|queda|quedan|resta|"
    r"restan)\s+(?:para|hasta|pa)(?:\s+que\s+(?:sea|sean|den|llegue|lleguen))?|"
    r"how\s+(?:long|much\s+time|many\s+(?:hours|minutes|mins))\s+(?:(?:is|are|do\s+(?:i|we)\s+have|have\s+(?:i|we)\s+"
    r"got)\s+)?(?:(?:left|remaining|remain|to\s+go)\s+)?(?:until|till|til|before|to))"
)
_COUNTDOWN_TARGET = re.compile(
    r"^" + _COUNTDOWN_HEAD + r"\s+"
    r"(?:(?:el|la|las|the)\s+)?"
    r"(?:(?P<noon>mediodia|noon|midday)|(?P<midnight>medianoche|midnight)|"
    r"(?P<hour>\d{1,2}|" + "|".join(sorted(_COUNTDOWN_HOUR_WORDS, key=len, reverse=True)) + r")"
    r"(?:[:.h](?P<minute>\d{2}))?"
    r"(?:\s+(?:y\s+(?P<spoken_minute>media|cuarto|\d{1,2}))?)?"
    r"(?:\s+(?:o\W?\s*clock|en\s+punto))?"
    r"(?:\s*(?P<ampm>[ap])\.?\s*m\.?|\s+(?:de\s+la\s+|en\s+la\s+|in\s+the\s+|)"
    r"(?P<part>manana|madrugada|tarde|noche|morning|afternoon|evening|night))?"
    r"(?:\s+(?:de\s+hoy|today|hoy))?"
    r")\s*$"
)


_HOUR_WORD = r"(?:\d{1,2}|" + "|".join(sorted(_COUNTDOWN_HOUR_WORDS, key=len, reverse=True)) + r")"
# M99 (reserva A6 «las dos menos cuarto» → an alarm nobody asked for): a message that is only a clock time, with no act
# and no day of its own. Folded.
_ONLY_A_CLOCK = re.compile(
    r"[¿¡\s]*(?:(?:a|para|hasta)\s+)?(?:(?:la|las)\s+)?" + _HOUR_WORD
    + r"(?:[:.h]\d{2})?(?:\s+(?:y|menos)\s+(?:media|cuarto|\d{1,2}|" + "|".join(_COUNTDOWN_HOUR_WORDS) + r"))?"
    r"(?:\s+(?:en\s+punto|de\s+la\s+(?:manana|madrugada|tarde|noche)|[ap]\.?\s*m\.?))?[\s.!?]*"
    # M144: «half three» is half past three (British English).
    r"|[\s]*(?:at\s+)?(?:(?:a\s+)?quarter\s+(?:to|past|after)\s+|half\s+(?:past\s+)?)?" + _HOUR_WORD
    + r"(?:[:.]\d{2})?(?:\s+(?:o'?\s*clock|[ap]\.?\s*m\.?))?[\s.!?]*"
)


def said_only_a_clock(text: str) -> bool:
    """«las dos menos cuarto», «a las siete y media», «quarter to two»: the whole message is a clock time (see above).
    A bare number («dos») is a clock only after «la/las», «at» or with its part of the day."""

    folded = _fold(str(text or "")).strip()
    if _ONLY_A_CLOCK.fullmatch(folded) is None:
        return False
    return re.search(r"\b(?:la|las|at|quarter|half|clock|[ap]\.?\s*m|manana|madrugada|tarde|noche|punto)\b|\d[:.h]\d",
                     folded) is not None


# M40 (official-window rehearsal 2026-09-28 «¿qué hora será de aquí a doce minutos?»: three drafts added the
# minutes themselves, wrongly, and the turn failed): the clock later on is computed from the observed one.
_CLOCK_LATER = re.compile(
    r"\b(?:que\s+hora\s+(?:sera|seran|va\s+a\s+ser)|what\s+time\s+(?:will\s+it\s+be|is\s+it\s+going\s+to\s+be))\b"
)
# M85 (DEV-D v3o D-s025 «si pasan cuarenta minutos, ¿qué hora será?» → «la hora será la que indique tu reloj más esos
# cuarenta minutos»): the span said as time that passes is the same span.
_LATER_BY = re.compile(
    r"\b(?:de\s+aqui\s+a|dentro\s+de|en|in|after|(?:si|cuando)\s+(?:pasan|pasen|transcurren|transcurran)|"
    r"pasad[oa]s|(?:if|when)(?:\s+another)?)\s+(?P<n>(?:[a-z0-9]+\s+){0,3}?)(?P<unit>minutos?|horas?|minutes?|hours?)"
    r"(?:\s+(?:pass|go\s+by|have\s+passed|more))?\b"
)


def clock_later_asked(text: str) -> tuple[str, int] | None:
    """«¿qué hora será de aquí a doce minutos?», «what time will it be in 2 hours»: the span as said and its minutes."""

    folded = _fold(text)
    if _CLOCK_LATER.search(folded) is None:
        return None
    match = _LATER_BY.search(folded)
    if match is None:
        return None
    words = match["n"].strip()
    amount = 1 if words in {"", "un", "una", "a", "an"} else int(words) if words.isdigit() else spoken_cardinal(words)
    if amount is None or amount <= 0:
        return None
    minutes = amount * 60 if match["unit"].startswith(("hora", "hour")) else amount
    return match.group(0).strip(), minutes


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
# M91 (reserva «at seven fifteen am»): English says the minutes straight after the hour.
_ENGLISH_CLOCK_MINUTE_WORDS = {
    "oh five": 5, "o five": 5, "ten": 10, "fifteen": 15, "twenty": 20, "twenty five": 25, "twenty-five": 25,
    "thirty": 30, "thirty five": 35, "thirty-five": 35, "forty": 40, "forty five": 45, "forty-five": 45,
    "fifty": 50, "fifty five": 55, "fifty-five": 55,
}
_ENGLISH_CLOCK_MINUTE = "(?:" + "|".join(
    re.escape(word).replace(r"\ ", r"\s+") for word in sorted(_ENGLISH_CLOCK_MINUTE_WORDS, key=len, reverse=True)
) + ")"
# M156 (DEV-I v4u I-s050 «baxy necesito que me despiertes a las 6 30 que tengo turno en la clinica» → an alarm at
# 18:00): the minutes may come straight after the hour, as the ear writes «6 30», the keyboard «6.30» and Spanish says
# «seis treinta», as English says «six thirty» (M91). Two digits or a word of minutes, never a length («a las 6 30
# minutos») nor the day of a date («a las 6 15 de octubre»); «media» and «cuarto» still take their «y».
_STRAIGHT_MINUTE_WORDS = "|".join(
    sorted((word for word in _CLOCK_MINUTE_WORDS if word not in {"media", "cuarto"}), key=len, reverse=True)
)
_STRAIGHT_MINUTES = (
    rf"(?:(?:\.|\s+)[0-5][0-9](?!\d)|\s+(?:{_STRAIGHT_MINUTE_WORDS})\b)"
    rf"(?!\s*(?:minutos?|minutes?|mins?|horas?|hours?|hrs?|segundos?|seconds?|dias?|days?)\b"
    rf"|\s+(?:de\s+|of\s+)?{_CALENDAR_MONTH_TOKEN}\b)"
)
_CLOCK_MINUTES = (
    rf"(?::[0-5][0-9]|\s+y\s+{_CLOCK_MINUTE_WORD}|\s+menos\s+{_CLOCK_MINUTE_WORD}|\s+{_ENGLISH_CLOCK_MINUTE}\b|"
    rf"{_STRAIGHT_MINUTES})"
)
# The part of the day said after the hour. «a. m.» keeps its dots optional and
# needs the «m» to end a word, so «a mi casa» is never a morning. The accented
# spellings let a reader of the person's own text use it too.
# M176 (probe «ponme una alarma a las 12 del día», «alarm at 12 noon» → set at midnight): «del día» is the daytime and
# «noon» names noon; «del día siguiente» is a day, not a part of it.
_CLOCK_PERIOD = (
    r"(?:a\.?\s*m\b\.?|p\.?\s*m\b\.?|de\s+la\s+(?:ma[nñ]ana|madrugada|tarde|noche)|"
    r"del?\s+mediod[ií]a|del\s+d[ií]a\b(?!\s+siguiente)|noon\b|midday\b|"
    r"in\s+the\s+(?:morning|afternoon|evening)|at\s+night)"
)
# The part of the day said elsewhere in the request («esta tarde a las cinco»,
# «mañana por la mañana a las siete»).
_DAY_PART = (
    r"\b(?:(?:esta|por\s+la|en\s+la|a\s+la)\s+(?P<part>manana|madrugada|tarde|noche)|"
    r"(?:this|in\s+the)\s+(?P<english>morning|afternoon|evening)|(?P<tonight>tonight))\b"
)
# M73 (reserve v3j es8765 «mi cena … a las nueve» asked morning or afternoon): a meal said in the request is the part
# of the day of a bare 1–12 hour when no part of the day is said. Not a window of the day (``_DAY_PART`` in ranges).
_MEAL_PART = (
    r"\b(?:(?P<night>cena|cenas|cenar|dinner|supper)|(?P<morning>desayuno|desayunos|desayunar|breakfast)|"
    r"(?P<afternoon>almuerzo|almuerzos|almorzar|comida|merienda|lunch))\b"
)
_EARLY = r"\b(?:temprano|tempranito|early)\b"
_NOON_OR_MIDNIGHT = r"\b(?:al|a|el|at|para\s+el)\s+(?:mediod[ií]a|noon|midday|medianoche|midnight)\b"
# M110 (DEV-F v4d F-w12-t1 «ponme una alarma pa las 6 y 40 mañana» → «¿Cuándo quieres que suene?»): «pa las» is «para
# las» as it is said.
_CLOCK_LEAD = r"(?:a\s+las?|para\s+las?|pa\s+las?|sobre\s+las?|hacia\s+las?|at)"
# «a las cinco en punto», «twelve o'clock» (uso real 2026-09-24): the hour said exactly is a clock time.
_O_CLOCK = r"\s+(?:en\s+punto|o['’]?\s*clock)"
# M110 (DEV-F v4d F-s032 «Remind me on Thursday at quarter past nine in the morning…» → a reminder at 9:00): English
# may say the minutes before the hour, «quarter past nine», «half past seven», «ten to six». In words only: «10 to 12»
# is a range of numbers as often as a clock.
_ENGLISH_MINUTES_BEFORE = {"a quarter": 15, "quarter": 15, "half": 30, "five": 5, "ten": 10, "twenty": 20,
                           "twenty five": 25, "twenty-five": 25}
_BEFORE_HOUR_WORDS = r"(?:a\s+quarter|quarter|half|twenty[\s-]five|twenty|ten|five)\s+(?:past|after|to|till)"
_ENGLISH_BEFORE_HOUR = (
    r"(?:(?P<before>(?:a\s+quarter|quarter|half|twenty[\s-]five|twenty|ten|five)\s+(?P<relation>past|after|to|till))\s+|"
    # M144 (DEV-H v4p H-w38-t2 «half three» answering «what time shall I set that for?» → «What exactly do you want to
    # do with half three?»): British English says «half three» for half past three. Only an hour in words, and never
    # a part of something («half one of them»).
    r"(?P<half>half)\s+(?=(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b"
    r"(?!\s+(?:of|the|a|an)\b)))"
)
# One clock phrase with its lead («a las cinco y media de la mañana»), for
# readers that cut a request around its time.
CLOCK_PHRASE = (
    rf"(?:{_CLOCK_LEAD}\s+(?:las?\s+)?(?:{_BEFORE_HOUR_WORDS}\s+)?{_CLOCK_HOUR}{_CLOCK_MINUTES}?(?:{_O_CLOCK})?"
    rf"(?:\s*{_CLOCK_PERIOD})?)"
)
_SPOKEN_CLOCK = re.compile(
    rf"\b(?:(?P<lead>{_CLOCK_LEAD})\s+(?:las?\s+)?)?(?:{_ENGLISH_BEFORE_HOUR})?"
    rf"(?P<hour>{_CLOCK_HOUR})(?P<minutes>{_CLOCK_MINUTES})?(?P<oclock>{_O_CLOCK})?"
    rf"(?:\s*(?P<period>{_CLOCK_PERIOD}))?(?=\s|$|[,;:.?!])"
    # «a las dos horas», «at five minutes»: a duration is not a clock time.
    # M168 (D77, ESPN's kick-off said back «Chile juega el martes a las 23:30 hora local», «a las 19:30 horas» → read
    # 23:00 and 19:00, and «una hora antes de eso» counted from them): minutes written after a colon make a clock, and
    # «hora(s)» after it names the clock, not a length.
    r"(?!(?<!:[0-5][0-9])\s+(?:minutos?|minutes?|horas?|hours?|dias?|days?|segundos?|seconds?)\b)"
)


# M138 (DEV-G v4n G-s073 «programame una alarma pa las 7 que manana madrugo» → «¿A qué hora…?», where the isolated
# decider set it at 7): «pa las» is «para las» here too (M110 read it so in ``_CLOCK_LEAD``; this selector did not, and
# the incomplete-schedule reader asked for the hour that was said).
_CLOCK_TIME_SELECTOR = (
    r"\b(?:[01]?[0-9]|2[0-3]):[0-5][0-9]\b|"
    rf"\b(?:a las?|para las?|pa las?|at)\s+(?:las\s+)?{_CLOCK_HOUR}{_CLOCK_MINUTES}?"
    rf"(?:\s*{_CLOCK_PERIOD})?(?=\s|$|[,;:.?!])|"
    rf"\b{_CLOCK_HOUR}{_CLOCK_MINUTES}?\s*{_CLOCK_PERIOD}(?=\s|$|[,;:.?!])|"
    rf"\b{_CLOCK_HOUR}{_O_CLOCK}\b|"
    rf"{_NOON_OR_MIDNIGHT}"
)


@dataclass(frozen=True)
class SpokenClock:
    """One clock time as said: ``literal`` is its span in the folded text; ``hour`` is
    0–23 when ``resolved`` (a part of the day, a 24-hour value, noon or midnight),
    otherwise the 1–12 hour whose morning or afternoon was not said. ``on_the_dial`` marks a 1–12 hour resolved only
    because its minutes were written after a colon («a las 4:30»; M144): read as written, while a move of a notification
    takes the part of the day of the old one and the decider's own part of the day stands (``__main__``)."""

    literal: str
    hour: int
    minute: int
    resolved: bool
    on_the_dial: bool = field(default=False, compare=False)


def _read_clock(found: re.Match[str], folded: str) -> SpokenClock | None:
    minutes_text = found.group("minutes") or ""
    # M156: «a las 6.30» is written on the dial as «a las 6:30» is (a bare «6.30» is no clock, ``_is_a_clock``).
    colon = minutes_text.startswith((":", "."))
    raw_hour = found.group("hour")
    hour = int(raw_hour) if raw_hour.isdecimal() else _CLOCK_HOUR_WORDS[raw_hour]
    minute_word = re.sub(r"^(?::|\.|\s+(?:y|menos)\s+|\s+)", "", minutes_text)
    minute = 0
    if minute_word:
        english = " ".join(minute_word.split())
        minute = (
            int(minute_word) if minute_word.isdecimal()
            else _CLOCK_MINUTE_WORDS[minute_word] if minute_word in _CLOCK_MINUTE_WORDS
            else _ENGLISH_CLOCK_MINUTE_WORDS[english]
        )
    before = found.groupdict().get("before")
    if found.groupdict().get("half"):
        if minute_word:
            return None
        minute = 30  # M144: «half three» is 3:30.
    elif before:
        if minute_word:
            return None
        minute = _ENGLISH_MINUTES_BEFORE[" ".join(before.split()[:-1])]
        if found.group("relation") in {"to", "till"}:
            # «quarter to five» is 4:45.
            hour, minute = (12 if hour == 1 else hour - 1), 60 - minute
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
        meal = re.search(_MEAL_PART, folded) if elsewhere is None and not colon else None
        if elsewhere is None and meal is None and hour < 12 and re.search(_EARLY, folded):
            # M110 (DEV-F v4d F-s017 «despiértame mañana a las 6 y cuarto … altiro temprano» → asked morning or
            # afternoon, and the question died in composition): early is the morning.
            return SpokenClock(literal, hour, minute, True)
        if elsewhere is None and meal is None:
            # «a las 7:30» is read as written, on the 24-hour clock.
            return SpokenClock(literal, hour, minute, colon, on_the_dial=colon and not raw_hour.startswith("0"))
        if elsewhere is not None:
            period = elsewhere.group("part") or elsewhere.group("english") or "noche"
        else:
            # M73: «la cena a las nueve» is 21:00, «el desayuno a las ocho» 8:00, «el almuerzo a la una» 13:00.
            period = "noche" if meal.group("night") else "manana" if meal.group("morning") else "tarde"
    if re.search(r"^a\.?\s*m|manana|madrugada|morning", period):
        return SpokenClock(literal, hour % 12, minute, True)
    if re.search(r"mediodia|noon|midday", period):
        return SpokenClock(literal, 12 if hour == 12 else hour + 12, minute, True)
    if re.search(r"\bdia\b", period):
        # M176: «las 12 del día» is noon, «las 10 del día» the morning, «las 3 del día» the afternoon.
        return SpokenClock(literal, hour if hour >= 7 else hour + 12, minute, True)
    if re.search(r"noche|night|evening", period) and (hour == 12 or hour <= 4):
        # «las doce de la noche» is midnight; «la una de la noche» is 1:00.
        return SpokenClock(literal, hour % 12, minute, True)
    return SpokenClock(literal, hour % 12 + 12, minute, True)


def _is_a_clock(found: re.Match[str]) -> bool:
    """A number is a clock time after «a las / para las / at», before a part of the day, with its minutes
    after a colon, or said «en punto» / «o'clock» (uso real 2026-09-24 «an appointment twelve o'clock»)."""

    return bool(
        found.group("lead")
        or found.group("before")
        or found.group("half")
        or found.group("period")
        or (found.group("minutes") or "").startswith(":")
        or found.group("oclock")
    )


def spoken_clocks(folded: str) -> tuple[SpokenClock, ...]:
    """Every clock time of a folded request, read with its minutes («y media», «menos
    cuarto», «:30») and its part of the day, said after the hour or elsewhere («esta tarde
    a las cinco»); noon and midnight when no hour is said. A bare number counts only after
    «a las / para las / at», before a part of the day or with its minutes after a colon;
    an hour or a minute no clock has is not a clock."""

    clocks = tuple(
        clock
        for found in _SPOKEN_CLOCK.finditer(folded)
        if _is_a_clock(found)
        if (clock := _read_clock(found, folded)) is not None
    )
    if clocks:
        return clocks
    noon = re.search(_NOON_OR_MIDNIGHT, folded)
    if noon is None:
        return ()
    midnight = re.search(r"medianoche|midnight", noon.group(0)) is not None
    return (SpokenClock(noon.group(0), 0 if midnight else 12, 0, True),)


def named_clock_dial(text: str) -> frozenset[tuple[int, int]]:
    """M63 (v3f-final F-s019 «Cambia la alarma despertador de las 8:00 a las 9:00.»): the clocks the person named, on
    the twelve-hour dial, so that «8:00», «08:00», «8:00 a. m.», «las 8 de la mañana» and «20:00» said back are the
    same time. The twin of the App's UserMessagePolicy.PersonNamedClocks."""

    return frozenset((clock.hour % 12, clock.minute) for clock in spoken_clocks(_fold(str(text or ""))))


def spoken_clock(folded: str) -> SpokenClock | None:
    """The first of ``spoken_clocks``, or None."""

    clocks = spoken_clocks(folded)
    return clocks[0] if clocks else None


# D61 (owner, 2026-10-02; reviewed literal H0036 «set an alarm for 8»): on an alarm, an hour after «for/para» with no
# «at/a las» is its clock when nothing but the end, a day or a «please» follows it — never a length («for 8 minutes»),
# a count or what the alarm is for («para una reunión»).
# M155 (DEV-I v4u I-s008 «set an alarm for 6 to get up for my run, cheers» → «What time of day should the alarm be set
# for 6?», where the isolated decider set it): what the alarm is for may follow the hour as a clause of its own («to get
# up», «para ir al gimnasio», «so I can…») — a verb, never a number («for 6 to 7», «for ten to seven») nor a length.
# Left as they were (asked): a reason said with «que/porque» («que mañana madrugo») and a purpose that names a day («to
# get up tomorrow»), where D61b would read a 1–6 as the afternoon of a day said only to place a wake-up.
_ALARM_PURPOSE_AFTER_HOUR = (
    r"(?:to|para|pa|so)\s+(?!(?:\d|"
    + "|".join(sorted(_CLOCK_HOUR_WORDS, key=len, reverse=True))
    + r"|minutos?|minutes?|mins?|horas?|hours?|y\s+media|half|quarter|cuarto|o'?clock)\b)"
    r"(?![^,;.!?]*\b(?:manana|tomorrow|tonight|pasado|lunes|martes|miercoles|jueves|viernes|sabado|domingo|monday|"
    r"tuesday|wednesday|thursday|friday|saturday|sunday|weekend|finde)\b)[a-z]"
)
_ALARM_FOR_HOUR = re.compile(
    r"\b(?:alarm|alarma)\b.*?\b(?P<lead>for|para)\s+(?P<hour>\d{1,2}|"
    + "|".join(sorted(_CLOCK_HOUR_WORDS, key=len, reverse=True)) + r")"
    # M156: its minutes said straight after it («for 6 30», «para 6.30») are its own.
    r"(?P<minutes>(?:\.|\s+)[0-5][0-9](?!\d))?"
    r"(?=\s*(?:$|[,;!?]|\.(?!\d)|(?:de\s+)?(?:hoy|manana|today|tomorrow|tonight|please|por\s+favor|porfa)\b|"
    + _ALARM_PURPOSE_AFTER_HOUR + r"))"
)


def alarm_for_hour(folded: str) -> str | None:
    """«set an alarm for 8» → «at 8», «pon una alarma para 7» → «a las 7»: the hour as a clock ``spoken_clock`` reads
    (D61: without its part of the day, the next time it comes), or None."""

    found = _ALARM_FOR_HOUR.search(folded)
    if found is None or spoken_clocks(folded):
        return None
    hour = found.group("hour")
    if hour.isdecimal() and not 1 <= int(hour) <= 23:
        return None
    return f"{'at' if found.group('lead') == 'for' else 'a las'} {hour}{found.group('minutes') or ''}"


# --- A time counted from the moment BAXY just gave -------------------------------
# M84 (DEV-D v3o D-w08-t3 «ponme recordatorio una ora antes d ese partido» after «América juega este 27 de septiembre
# de 2026 contra Necaxa a las 21:00 horas.» → «¿Cuándo es ese partido?»; D-w02-t3 «ponme una alarma media hora antes
# de eso» after the time here of 10:00 in Madrid → «¿Cuándo…?»): «eso», «ese partido», «that» point at the one moment
# BAXY's last answer gave, and the duration before or after it is counted here, not asked and not left to the model.
# «ora» is «hora» as the ear or the keyboard left it (owner 2026-09-19: lo mal dicho lo arregla BAXY).
_OFFSET_AMOUNT = (
    r"(?P<amount>media|half\s+an?|un\s+cuarto\s+de|a\s+quarter\s+of\s+an?|una?|an?|one|\d{1,3}|dos|tres|cuatro|cinco|"
    r"diez|quince|veinte|treinta|cuarenta|two|three|four|five|ten|fifteen|twenty|thirty|forty)"
)
_OFFSET_UNIT = r"(?P<unit>horas?|oras?|hours?|hrs?|h|minutos?|minutes?|mins?|min)"
# M110 (DEV-F v4d F-w05-t3 «ponme un recordatorio una hora antes de la junta» after the mail that set «la junta» on
# Thursday at 19:00 → «¿A qué hora es la junta?»; F-w33-t2 «Set an alarm for half an hour before kick-off» after
# «…kick-off 15:00…» → «When would you like the alarm to go off?»): a thing named with its article, or bare, points at
# the moment of the last message of the conversation that names it.
# M168 (D77; DEV-I v4y I-w12-t4 «ponem una alarma una hora antes» and I-w29-t3 «put a reminder on an hour ahead of
# tip-off…» after the kick-off BAXY gave → asked): «ahead (of)» is «before», and a length before or after with nothing
# after it but the end of the message counts from the one moment BAXY just gave, as «antes de eso» does.
_ANCHORED_OFFSET = re.compile(
    rf"\b{_OFFSET_AMOUNT}\s+{_OFFSET_UNIT}\s+(?P<sign>antes|despues|before|after|earlier|later|ahead)"
    r"(?:(?:\s+(?:de|d|del|than|of))?\s+(?:(?:eso|esto|that|it|then)\b|(?:ese|esa|este|esta|that|the)\s+[a-z]+\b|"
    r"(?:(?P<article>el|la|los|las|al|mi|my)\s+)?(?P<named>[a-z]{3,}(?:-[a-z]+)?)\b)|(?=\s*[.!?]*\s*$))"
)
# M168: the start of a match, named («antes del partido», «before kick-off», «ahead of tip-off»), is the moment of the
# newest line that tells a match (a team plays, a kick-off) with one clock; BAXY's own report of a notice it set («Listo,
# alarma el sábado a las 18:30 para el partido») tells when that notice rings, not when the match starts.
_MATCH_START_WORDS = frozenset({"partido", "match", "game", "kick", "kick-off", "kickoff", "tip", "tip-off", "tipoff"})
_TELLS_A_MATCH = re.compile(
    r"\b(?:partido|juega|juegan|jugara|jugaran|recibe|reciben|visita|visitan|match|game|plays?|playing|hosts?|"
    r"kick-?off|tip-?off)\b"
)
_TELLS_A_NOTICE = re.compile(r"\b(?:alarma|recordatorio|aviso|alarm|reminder)\b")
_OFFSET_NUMBERS = {
    "una": 1, "un": 1, "a": 1, "an": 1, "one": 1, "dos": 2, "two": 2, "tres": 3, "three": 3, "cuatro": 4, "four": 4,
    "cinco": 5, "five": 5, "diez": 10, "ten": 10, "quince": 15, "fifteen": 15, "veinte": 20, "twenty": 20,
    "treinta": 30, "thirty": 30, "cuarenta": 40, "forty": 40,
}
# The day a moment is said on, as BAXY wrote it: «el 27 de septiembre de 2026», «mañana», «el viernes».
_ANCHOR_DAY = re.compile(
    r"\b(?:(?:el|este|this|on)\s+)?(?:(?:lunes|martes|miercoles|jueves|viernes|sabado|domingo|monday|tuesday|"
    r"wednesday|thursday|friday|saturday|sunday)\s+)?\d{1,2}\s+de\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|"
    r"agosto|septiembre|setiembre|octubre|noviembre|diciembre)(?:\s+de\s+\d{4})?\b|"
    r"\b(?:(?:on\s+)?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday),?\s+)?(?:january|february|march|"
    r"april|may|june|july|august|september|october|november|december)\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?\b|"
    r"\b(?:pasado\s+manana|(?<!la\s)(?<!esta\s)manana|hoy|today|tomorrow|(?:el\s+|este\s+|on\s+|this\s+)?(?:lunes|martes|miercoles|"
    r"jueves|viernes|sabado|domingo|monday|tuesday|wednesday|thursday|friday|saturday|sunday))\b"
)
_HERE_WORD = r"\b(?:aqui|aca|here|hora\s+local|local\s+time)\b"


def _offset_minutes(found: re.Match[str]) -> int | None:
    amount = found.group("amount")
    unit = found.group("unit")
    hours = unit.startswith(("h", "o"))
    if amount == "media" or amount.startswith("half"):
        return 30 if hours else None
    if amount.startswith(("un cuarto", "a quarter")):
        return 15 if hours else None
    value = int(amount) if amount.isdecimal() else _OFFSET_NUMBERS.get(amount)
    if value is None:
        return None
    return value * 60 if hours else value


def _anchor_clock(folded_reply: str) -> SpokenClock | None:
    """The one moment of a reply: its only resolved clock, or, of several, the one said of «here»."""

    clocks = [clock for clock in spoken_clocks(folded_reply) if clock.resolved]
    if len(clocks) == 1:
        return clocks[0]
    here = []
    for clock in clocks:
        start = folded_reply.find(clock.literal)
        clause_start = max(folded_reply.rfind(mark, 0, start) for mark in (",", ".", ";", ":", "\n"))
        after = folded_reply[start + len(clock.literal):]
        clause_end = min([after.find(mark) for mark in (",", ".", ";", "\n") if after.find(mark) >= 0] or [len(after)])
        if _has(folded_reply[clause_start + 1:start], _HERE_WORD) or _has(after[:clause_end], _HERE_WORD):
            here.append(clock)
    return here[0] if len(here) == 1 else None


def anchored_offset_request(text: str, reply: str | None, earlier: Iterable[str] = ()) -> str | None:
    """``text`` with «<duration> antes/después de eso» replaced by the moment it names, counted from the one moment
    ``reply`` (BAXY's last answer) gave, in the day it gave; None when the message counts from nothing pointed at, or
    the reply gives no single moment, or the count leaves that day. A thing named by its article or bare («antes de la
    junta», «before kick-off») is counted from the newest of ``reply`` and ``earlier`` (the conversation before it,
    newest first) that names it with one moment."""

    said = " ".join(str(text or "").split())
    folded = _fold(said)
    found = _ANCHORED_OFFSET.search(folded)
    if found is None or len(folded) != len(said):
        return None
    if said_advance(said) is not None:
        # M165 (DEV-I v4y I-w20-t3 «tambien tengo una reunion a las 9, recuerdamelo 15 minutos antes de eso» after «He
        # cambiado la alarma de mañana a las 08:00.» → counted to 07:45): «eso» points at the moment the same message
        # just said, which ``said_advance`` reads; BAXY's last answer is not what it counts from.
        return None
    named = found.group("named")
    # Bare: the length and its sign end the match, nothing pointed at after them.
    bare = found.group(0).split()[-1] == found.group("sign")
    if bare and (
        # M168: bare, only a notice asked for, counted before or after (never «earlier», «later»: a notice moved).
        found.group("sign") in {"earlier", "later"}
        or not re.search(r"\b(?:alarmas?|recordatorios?|recuerd|record|avis|alarms?|reminders?|remind)", folded)
    ):
        return None
    if named is not None:
        if named in _NOT_A_POINTED_THING:
            return None
        if named in _MATCH_START_WORDS:
            # M168: the match's start is told by the newest line that tells a match, not by a notice set for it.
            reply = next(
                (
                    line for line in (reply, *earlier)
                    if line and _TELLS_A_MATCH.search(_fold(line)) and not _TELLS_A_NOTICE.search(_fold(line))
                    and _anchor_clock(_fold(" ".join(str(line).split()))) is not None
                ),
                None,
            )
        else:
            reply = next(
                (
                    line for line in (reply, *earlier)
                    if line and re.search(rf"\b{re.escape(named)}", _fold(line))
                    and _anchor_clock(_fold(" ".join(str(line).split()))) is not None
                ),
                None,
            )
    if not reply:
        return None
    minutes = _offset_minutes(found)
    answer = " ".join(str(reply).split())
    folded_answer = _fold(answer)
    anchor = _anchor_clock(folded_answer)
    if minutes is None or anchor is None:
        return None
    sign = -1 if found.group("sign") in {"antes", "before", "earlier", "ahead"} else 1
    moment = anchor.hour * 60 + anchor.minute + sign * minutes
    if not 0 <= moment < 24 * 60:
        return None
    days = {match.group(0).strip() for match in _ANCHOR_DAY.finditer(folded_answer)}
    if len(days) > 1:
        return None
    day = ""
    if days:
        start = folded_answer.find(next(iter(days)))
        day = (answer if len(answer) == len(folded_answer) else folded_answer)[start:start + len(next(iter(days)))]
    spanish = _has(folded, r"\b(?:ponme|pon|pone|poneme|recuerdame|recordame|avisame|antes|despues|alarma|recordatorio|"
                           r"de|el|la|una)\b")
    clock = f"{moment // 60:02d}:{moment % 60:02d}"
    when = (f"{day} a las {clock}" if spanish else f"{day} at {clock}").strip()
    if spanish and day and not re.match(r"(?i)(?:el|este|hoy|mañana|manana|pasado)\b", day):
        when = f"el {when}"
    if not spanish and re.search(r"(?i)\b(?:for|on|at)\s*$", said[: found.start()]):
        # «an alarm for on Saturday»: the preposition before the count already leads the day.
        when = re.sub(r"(?i)^on\s+", "", when)
    # M93 (DEV-D v3u D-w08-t3 «ponme recordatorio una ora antes d ese partido» → «ponme recordatorio el sábado 3 de
    # octubre de 2026 a las 19:00» → «¿Qué título quieres para el recordatorio…?»): the thing pointed at («ese
    # partido») is what the reminder is for; it stays, named with its article.
    pointed = re.search(r"\b(?P<determiner>ese|esa|este|esta|that|the)\s+(?P<noun>[a-z]+)$", found.group(0))
    if pointed is not None:
        noun = said[found.start() + pointed.start("noun"): found.start() + pointed.end("noun")]
        article = "la" if pointed.group("determiner") in {"esa", "esta"} else "el"
        when += f" para {article} {noun}" if spanish else f" for the {noun}"
    elif named is not None:
        noun = said[found.start("named"):found.end("named")]
        article = "la" if found.group("article") in {"la", "las"} else "el"
        when += f" para {article} {noun}" if spanish else f" for the {noun}"
    # «y ponme un recordatorio…» (F-w05-t3): the «y» that continues the conversation is not part of the request.
    return re.sub(r"(?i)^(?:y|e|and)\s+", "", (said[: found.start()] + when + said[found.end():]).strip())


# Words after «antes de» / «before» that name no thing with a moment («antes de que llegue», «before I go»).
_NOT_A_POINTED_THING = frozenset(
    "que the and una uno unos unas los las del con por para you your yo mis nos les irme salir llegar "
    "going leaving arriving we they she him her".split()
)


# M93 (DEV-D v3u D-w08-t3): the reminder the anchored request writes, «ponme recordatorio el sábado 3 de octubre de
# 2026 a las 19:00 para el partido», and the same said by a person («set a reminder tomorrow at 7pm for the game»): the
# moment first, then what it is for. Same-length folded.
_MOMENT_THEN_TITLE_REMINDER = re.compile(
    r"^(?:(?:por\s+favor|porfa|oye|please|hey)\s*,?\s+)?"
    r"(?:ponme|pon|poneme|pone|creame|crea|hazme|haz|agendame|agenda|set|create|make|add)\s+"
    r"(?:(?:un|una|a|me\s+a)\s+)?(?:recordatorio|reminder)\s+(?P<when>.+?)\s+"
    r"(?:para|for|about|sobre)\s+(?P<title>[^\d,;:.!?]+?)[\s.!]*$"
)


def moment_then_title_reminder(text: str) -> tuple[str, str] | None:
    """(title, moment) of a reminder asked with its moment first and then what it is for, both as written; None
    unless the moment holds exactly one clock (D61: without its part of the day, the next time it comes)."""

    said = " ".join(str(text or "").split())
    found = _MOMENT_THEN_TITLE_REMINDER.match(_same_length_fold(said))
    if found is None:
        return None
    clocks = spoken_clocks(found.group("when"))
    title = said[found.start("title"):found.end("title")].strip()
    if len(clocks) != 1 or not re.search(r"[^\W\d_]", title):
        return None
    return title, said[found.start("when"):found.end("when")].strip()


# --- The time of another place ---------------------------------------------------
# Uso real 2026-09-23 «in the eastern timezone, what time is it now» → «20:19»
# (this PC's clock; Eastern was 19:19), «qué hora es en tokio», «hora entre aquí
# y canadá»; tanda 4 «convertir nueve de la mañana huso horario a madrid» ended in
# «las páginas que encontré tratan de otra cosa». The time somewhere else is this
# PC's clock read together with that zone's offset (system.time with «place»),
# and a conversion is arithmetic the mind does on both; never this clock recited
# as another place's, never pages about clocks. A clock question names another
# place when it carries a zone («timezone», «GMT», «hora del Pacífico»), a
# difference between places, or «en/in <lugar>» after the clock words — «aquí»,
# «este PC», a part of the day and «en una hora» are this clock or a duration.
_CLOCK_QUESTION = (
    r"\b(?:que\s+hora|la\s+hora|hora\s+(?:es|actual|local|exacta|entre)|"
    r"diferencia\s+horaria|time\s+difference|"
    r"what\s+time|the\s+time|current\s+time|local\s+time|time\s+(?:is\s+it|now|right\s+now))\b|"
    # «time in Sydney please», «hora en Lima?»: the bare noun and its place.
    r"^(?:(?:the|la)\s+)?(?:time|hora)\s+(?:in|en)\s+(?!punto\b)"
)
_OTHER_ZONE = (
    r"\b(?:time\s*zones?|zona\s+horaria|zonas\s+horarias|huso\s+horario|husos\s+horarios|"
    r"diferencia\s+horaria|diferencia\s+de\s+hora(?:rio)?|time\s+difference|"
    r"gmt|utc|est|edt|pst|pdt|cst|cdt|mst|mdt|cet|cest|bst|jst|"
    r"(?:eastern|pacific|central|mountain|atlantic)\s+(?:time|standard|daylight)|"
    r"hora\s+(?:del\s+(?:pacifico|este|atlantico|centro)|de\s+la\s+costa\s+\w+)|"
    r"hora\s+entre)\b"
)
_CLOCK_ELSEWHERE = (
    r"\b(?:hora|time)\b.{0,32}?\b(?:en|in|at|over\s+in)\s+"
    r"(?!(?:este|esta|mi|my|this|the\s+(?:pc|computer|morning|afternoon|evening|night)|"
    r"el\s+(?:pc|equipo|computador|ordenador)|la\s+(?:pc|computadora|manana|tarde|noche)|"
    r"casa|home|aqui|aca|here|punto|una|un|one|an?|\d)\b)"
    r"[a-z]"
)
# «¿a qué hora es la cita?», «what time does the bank open in London»: the time
# of an event is not a clock reading; neither is a scheduling order. «huso
# horario» is the zone itself, not a schedule.
_CLOCK_NOT_A_READ = (
    r"\b(?:alarma|alarm|timer|temporizador|recuerda\w*|recorda\w*|remind|avisa\w*|(?<!huso\s)horario|schedule|"
    # M114: «what time will it be in Tokyo» is the clock there; «what time will the game start» is an event's.
    r"a\s+que\s+hora|what\s+time\s+(?:does|do|did|will(?!\s+it\s+be\b)|should|shall|is\s+the|are\s+the)|"
    # «la hora exacta de la puesta de sol en Badalona»: the hour of the sun there is the weather read's, not a clock.
    r"(?:puesta|salida|caida|entrada)\s+del?\s+sol|amanecer|atardecer|anochecer|ocaso|sunrise|sunset|dawn|dusk)\b"
)


def other_place_clock_question(folded: str) -> bool:
    """A question for the time in another zone or place (never this PC's clock)."""

    return (
        _has(folded, _CLOCK_QUESTION)
        and (_has(folded, _OTHER_ZONE) or _has(folded, _CLOCK_ELSEWHERE))
        and not _has(folded, _CLOCK_NOT_A_READ)
    )


# The zones a person names by their name instead of a place, each with the IANA
# zone that carries its current rule (daylight saving included). «hora del
# centro» is left out: in Mexico it is Mexico City's, in the US it is Chicago's.
_NAMED_ZONES = (
    (r"eastern(?:\s+(?:standard|daylight))?\s+(?:time\s*zone|timezone|time)|\be[sd]t\b|"
     r"(?:hora|zona(?:\s+horaria)?)\s+del\s+este|(?:la\s+)?costa\s+este|east\s+coast", "America/New_York"),
    (r"central(?:\s+(?:standard|daylight))?\s+(?:time\s*zone|timezone|time)|\bc[sd]t\b", "America/Chicago"),
    (r"mountain(?:\s+(?:standard|daylight))?\s+(?:time\s*zone|timezone|time)|\bm[sd]t\b|"
     r"(?:hora|zona(?:\s+horaria)?)\s+de\s+la\s+montana", "America/Denver"),
    (r"pacific(?:\s+(?:standard|daylight))?\s+(?:time\s*zone|timezone|time)|\bp[sd]t\b|"
     r"(?:hora|zona(?:\s+horaria)?)\s+del\s+pacifico|(?:la\s+)?costa\s+oeste|west\s+coast", "America/Los_Angeles"),
    (r"atlantic(?:\s+(?:standard|daylight))?\s+(?:time\s*zone|timezone|time)|"
     r"(?:hora|zona(?:\s+horaria)?)\s+del\s+atlantico", "America/Halifax"),
    (r"\b(?:gmt|utc|zulu)\b|(?:coordinated\s+)?universal\s+time|tiempo\s+universal", "UTC"),
    (r"\bcest?\b|central\s+europe(?:an)?\s+time|hora\s+(?:central\s+)?europea|hora\s+de\s+europa\s+central",
     "Europe/Paris"),
    (r"\bbst\b|british\s+(?:summer\s+)?time|hora\s+britanica", "Europe/London"),
    (r"\bjst\b|japan\s+standard\s+time", "Asia/Tokyo"),
    (r"hora\s+peninsular", "Europe/Madrid"),
)
# What introduces the place: «en/in/at Tokio» for the time there, «a/to/para
# Madrid» only for a conversion of a said time, «con/with Japón» only for a
# difference («the time needed to download it» names no place).
_PLACE_LEAD = r"\b(?:en|in|at|over\s+in)\s+"
_CONVERSION_LEAD = r"|\b(?:a|al|to|into|para|pa)\s+"
_DIFFERENCE_LEAD = r"|\b(?:con|with|is|esta|va|van|queda)\s+(?:adelantad\w+\s+|atrasad\w+\s+)?"
# Tanda 6c «i would like to know the timezone for britain» was searched on the web: the zone of a place is named
# with «for/of/de» after the zone's noun as much as with «in/en».
_ZONE_OF_LEAD = r"|\b(?:time\s*zones?|timezones?|zona\s+horaria|huso\s+horario)\s+(?:for|of|de|del|para)\s+"
# A clock of another place that is refused, remembered, reported, written or
# redefined is not asked now.
_CLOCK_ELSEWHERE_NOT_ASKED = (
    r"^(?:no|nunca|jamas|never|don'?t|do\s+not)\b|"
    r"\b(?:ayer|yesterday|anoche|te\s+pedi\w*|i\s+asked|si\s+te\s+pidiera|if\s+i\s+ask\w*|"
    r"escrib\w*|write|anota\w*|apunta\w*|nota|note|guarda\w*|save|define|explica\w*|explain|"
    r"cambia\w*\s+la\s+hora|set\s+the\s+(?:local\s+)?time)\b"
)
# Words that end the place («en Madrid ahora», «in Paris right now please»).
_PLACE_END = frozenset({
    "ahora", "ahorita", "now", "right", "mismo", "actualmente", "currently", "hoy", "today", "tonight",
    "por", "porfa", "please", "pls", "y", "and", "o", "or", "que", "what", "whats", "cual", "es", "is",
    "son", "are", "sera", "seria", "serian", "seran", "will", "would", "time", "hora", "horas", "hours",
    "horario", "huso", "zona", "timezone", "zone", "exacta", "exacto", "exact", "exactly", "exactamente",
    "local", "si", "if", "cuando", "when", "con", "with", "aqui", "aca", "here", "para", "for", "to", "a",
    "en", "in", "at", "me", "mi", "my", "tu", "your", "segun", "gracias", "thanks", "ya", "de", "del", "of",
    "estaria", "estara", "esta", "hay", "there", "manana", "tomorrow", "ayer", "yesterday", "luego", "later",
})
# What the lead may introduce that is not a place: this PC, home, a pronoun, a
# part of the day, an amount, the clock itself.
_NOT_A_PLACE = frozenset({
    "este", "esta", "ese", "esa", "eso", "mi", "my", "this", "that", "pc", "computer", "equipo",
    "computador", "computadora", "ordenador", "casa", "home", "aqui", "aca", "here", "punto", "una",
    "un", "uno", "one", "an", "ti", "me", "you", "momento", "moment", "linea", "manana", "tarde",
    "noche", "morning", "afternoon", "evening", "night", "madrugada", "total", "general", "serio",
    "realidad", "fin", "hora", "time", "horas", "hours", "minutos", "minutes", "formato", "format",
    "numeros", "numbers", "letras", "words", "voz", "voice", "ingles", "english", "espanol", "spanish",
    "local", "otra", "otro", "another", "other", "cualquier", "any", "reloj", "clock", "punto",
    "segundos", "seconds", "tiempo", "real", "vivo", "directo", "live", "lugar", "place",
    # M114 (reserve es4309 «en cuántas horas será medianoche en londres»): «en cuántas horas» asks the amount.
    "cuanto", "cuanta", "cuantos", "cuantas", "how",
})
_HERE_TARGET = (
    r"\b(?:aqui|aca|here|mi\s+(?:hora|zona(?:\s+horaria)?|huso(?:\s+horario)?)|my\s+(?:time(?:\s*zone)?|timezone)|"
    r"hora\s+local|local\s+time|para\s+mi|for\s+me|nuestra\s+hora|our\s+time|donde\s+estoy|where\s+i\s+am)\b"
)
_CONVERSION_CUE = (
    r"\b(?:convert\w*|pasa\w*|pase|cambia\w*|equivale\w*|traduc\w*|what\s+is|what'?s|whats|cuanto\s+es|"
    r"que\s+hora\s+(?:es|son|sera|seria|serian|seran)|what\s+time|hora|time)\b"
)
_DIFFERENCE_CUE = (
    r"\b(?:diferencia|difference|adelant\w*|atrasad\w*|ahead|behind|cuantas\s+horas|how\s+many\s+hours)\b"
)


@dataclass(frozen=True)
class ClockElsewhere:
    """The time asked of another place. ``place`` is what the zone read resolves
    (the place as said, or the IANA zone of a named zone); ``said`` is how the
    person named it. ``clock`` is a time to convert, when one was said, and
    ``clock_is_there`` says that time is the other place's («si en Madrid son las
    9, qué hora es aquí»), not this PC's. ``difference`` asks the hours apart; ``zone`` asks
    the zone itself («the timezone for britain»)."""

    place: str
    said: str
    clock: SpokenClock | None
    clock_is_there: bool
    difference: bool
    zone: bool = False


def _named_zone(folded: str) -> tuple[str, str] | None:
    for pattern, zone in _NAMED_ZONES:
        found = re.search(pattern, folded)
        if found is not None:
            return zone, found.group(0)
    return None


# «la hora de la cita», «hora de salida», «hora de comer»: what «hora de» names
# when it is not a place.
_HOUR_OF_EVENT = frozenset({
    "salida", "llegada", "cierre", "apertura", "entrada", "inicio", "comienzo", "almuerzo", "cena",
    "desayuno", "once", "verdad", "partida", "clase", "reunion", "cita", "junta", "misa", "turno",
    "vuelo", "tren", "bus", "pelicula", "partido", "evento", "fiesta", "siesta", "hacer", "que",
})


def _place_after(folded: str, start: int, *, verbs_are_not_places: bool = False) -> tuple[str, int] | None:
    """The place words that begin at ``start``: up to four, cut at the first word
    that ends a place; «de/del» only between words («ciudad de méxico»). After a
    lead that also introduces a purpose («para saber», «a comer»), an infinitive
    is not a place."""

    words: list[str] = []
    for found in re.finditer(r"[a-z][a-z'\-]*|\S", folded[start:]):
        word = found.group(0)
        if not re.fullmatch(r"[a-z][a-z'\-]*", word) or len(words) >= 4:
            break
        if word in _PLACE_END and not (word in {"de", "del"} and words):
            break
        words.append(word)
    while words and words[-1] in {"de", "del"}:
        words.pop()
    if words and words[0] == "the":
        words.pop(0)
    # A Spanish article may be part of the name («La Paz», «Los Ángeles», «El
    # Cairo») or not («la India»); it stays, and the zone read weighs both.
    head = words[1] if len(words) > 1 and words[0] in {"la", "el", "los", "las"} else (words[0] if words else "")
    if not head or head in _NOT_A_PLACE or len(head) < 2:
        return None
    if verbs_are_not_places and re.search(r"(?:ar|er|ir)(?:se|lo|la|le|me|te)?$", head):
        return None
    return " ".join(words), start


def clock_elsewhere(folded: str) -> ClockElsewhere | None:
    """The time of another place or zone asked in a request, or None.

    «qué hora es en tokio», «what time is it right now in paris», «in the eastern
    timezone, what time is it now», «dime la hora del pacífico», «convertir nueve
    de la mañana huso horario a madrid», «si aquí son las 9 de la noche qué hora
    es en Tokio», «when it's 3pm in London what time is it here», «diferencia
    horaria con Japón». A second place or zone to convert between is not this
    reading: it names two zones and this clock is neither.
    """

    # A quotation is content to write («una nota con el texto "la hora y …"»), not the question.
    text = re.sub(r"[\"«“][^\"»”]*[\"»”]", " ", folded)
    text = " ".join(re.sub(r"[¿?¡!,]", " ", text).split())
    if _has(text, _CLOCK_NOT_A_READ) or _has(text, _CLOCK_ELSEWHERE_NOT_ASKED):
        return None
    # «what time is it and what's the weather in Paris»: the place of another
    # question in the same request is not the clock's.
    clauses = re.split(
        # A sentence ends after a word, never inside «a. m.».
        r"(?<=[a-z]{2})[.:;](?:\s+|$)|\s*;\s*|\s+(?:despues(?:\s+de\s+eso)?|luego|finalmente|then|after\s+that|finally)\s+|"
        r"\s+(?:y|and|pero|but)\s+(?=(?:que|what|whats|what's|como|how|cual|cuanto|cuanta|cuantos|cuantas|"
        r"donde|where|cuando|when|quien|who|dime|decime|tell|pon|abre|open|busca|search|si|if|whether|"
        r"is|are|esta|estan|hay|do|does|can|puedes|sube|baja|turn|set)\b)",
        text,
    )
    text = next(
        (clause for clause in clauses if _has(clause, _CLOCK_QUESTION) or _has(clause, _OTHER_ZONE)),
        text,
    )
    clock = spoken_clock(text)
    rest = text.replace(clock.literal, " ", 1) if clock is not None else text
    difference = _has(rest, _DIFFERENCE_CUE)
    if not (
        _has(text, _CLOCK_QUESTION)
        or _has(text, _OTHER_ZONE)
        or (clock is not None and _has(rest, _CONVERSION_CUE))
        or (difference and _has(text, r"\b(?:hora\w*|hours?|time)\b"))
    ):
        return None
    zone = _named_zone(rest)
    places: list[tuple[str, int]] = []
    between = re.search(r"\b(?:entre|between)\s+(.+?)\s+(?:y|and)\s+(.+)$", rest)
    if between is not None:
        for group in (1, 2):
            if re.fullmatch(_HERE_TARGET + r".*", between.group(group)) is None:
                found = _place_after(rest, between.start(group))
                if found is not None:
                    places.append(found)
    # «how many hours ahead is Tokyo», «¿cuántas horas va adelantada Lima?».
    leads = (
        _PLACE_LEAD
        + _ZONE_OF_LEAD
        + (_CONVERSION_LEAD if clock is not None else "")
        + (_DIFFERENCE_LEAD if difference else "")
    )
    for lead in re.finditer(leads, rest):
        found = _place_after(
            rest, lead.end(), verbs_are_not_places=lead.group(0).split()[0] not in {"en", "in", "at", "over", "is"},
        )
        if found is not None and found not in places:
            places.append(found)
    # «9 am tokyo time», «las 9 hora de madrid», «dime la hora de madrid»: the
    # place named by its time; «hora de salida», «es hora de comer» name an event.
    for named in re.finditer(r"\b(?:(?P<en>[a-z][a-z'\-]+(?:\s+[a-z][a-z'\-]+)?)\s+time|hora\s+de\s+(?P<es>\S))", rest):
        if named.group("es") is not None:
            found = _place_after(rest, named.start("es"), verbs_are_not_places=True)
            if found is not None and found[0].split()[-1] not in _HOUR_OF_EVENT and not _has(rest, r"\bes\s+hora\s+de\b"):
                places.append(found)
        elif clock is not None:
            words = named.group("en").split()
            while words and words[0] in _PLACE_END | _NOT_A_PLACE | {"the", "same", "what", "what's", "it's"}:
                words.pop(0)
            if words and words[-1] not in _NOT_A_PLACE | _PLACE_END:
                places.append((" ".join(words), named.start("en")))
    if zone is not None:
        # «in the eastern timezone», «en la costa oeste»: the lead reads the zone's
        # own words; any other place is a second zone to convert between.
        if places and not all(place in zone[1] or zone[1] in place for place, _ in places):
            return None
        return ClockElsewhere(zone[0], zone[1], clock, False, difference)
    distinct = {place for place, _ in places}
    if len(distinct) != 1:
        return None
    place, position = places[0]
    here = re.search(_HERE_TARGET, rest)
    clock_is_there = clock is not None and here is not None and here.start() > position
    zone_asked = _has(rest, r"\b(?:time\s*zones?|timezones?|zona\s+horaria|huso\s+horario)\b")
    return ClockElsewhere(place, place, clock, clock_is_there, difference, zone_asked)


# M162 (DEV-H v4w H-w08-t3 «cuánta diferencia hay con aquí» after «En Lima son las 12:10.» → restated «¿Cuánta
# diferencia horaria hay entre Buenos Aires y Lima?» and searched as a figure of the world): the hours apart from here,
# asked with no place named right after BAXY told the clock of one place, are that place's. Said by its name, the
# request is the clock read of M84, whose difference is computed on the reading (``llm._place_clock_facts``), never by
# the decider nor by a talk that has no clock of here.
# The clock told of a place: «en Lima son las 12:10», «son las 01:09 en Tokio», «in Lima it's 12:10», «it's 4:15 pm in
# London» (not «el pan está a 7.50 en Lima»).
_CLOCK_TOLD = r"(?:son\s+las|es\s+la|it'?s|it\s+is)\s+(?<![\d.,])\d{1,2}[:.]\d{2}(?![\d.,]\d)"
_TOLD_PLACE = r"(?P<place>[a-z][a-z'\-]*(?:\s+(?:de\s+|del\s+)?[a-z][a-z'\-]*){0,3}?)"
_CLOCK_TOLD_OF_PLACE = (
    re.compile(rf"\b(?:en|in)\s+{_TOLD_PLACE}\s*,?\s+{_CLOCK_TOLD}"),
    re.compile(rf"{_CLOCK_TOLD}(?:\s*(?:a\.?\s?m\.?|p\.?\s?m\.?|hrs?\.?|horas))?\s+(?:en|in)\s+{_TOLD_PLACE}"
               r"(?=\s*(?:[,.;!]|$)|\s+(?:right\s+now|now|ahora|ahorita|y|and|el|the)\b)"),
)
# The difference of something else («diferencia de precio con aquí»).
_OTHER_DIFFERENCE = (
    r"\b(?:diferencia|difference)\s+(?:de|del|en|in|of)\s+(?!(?:la\s+)?(?:hora|horas|horario|time|tiempo)\b)"
)


def hours_apart_from_the_clock_told(text: str, last_reply: str | None) -> str | None:
    """«cuánta diferencia hay con aquí», «how many hours ahead of here is that?» after «En Lima son las 12:10.»: the
    request of the hours apart between that place and here, in the person's language; None when the message names a
    place or a time of its own, asks no difference with here, or the reply told no single place's clock."""

    folded = _fold(text)
    if (
        not _has(folded, _DIFFERENCE_CUE)
        or not _has(folded, _HERE_TARGET)
        or _has(folded, _OTHER_DIFFERENCE)
        or clock_elsewhere(folded) is not None
        or spoken_clock(folded) is not None
    ):
        return None
    reply = _fold(last_reply or "")
    places = {found.group("place") for pattern in _CLOCK_TOLD_OF_PLACE for found in pattern.finditer(reply)}
    if len(places) != 1:
        return None
    place = next(iter(places))
    named = " ".join(word if word in {"de", "del"} else word.capitalize() for word in place.split())
    english = _has(folded, r"\b(?:difference|ahead|behind|how\s+many\s+hours|here)\b")
    request = (
        f"what's the time difference between {named} and here?"
        if english
        else f"¿cuánta diferencia horaria hay entre {named} y aquí?"
    )
    asked = clock_elsewhere(_fold(request))
    return request if asked is not None and asked.place == place and asked.difference else None


# M85 (DEV-D v3o D-w02-t2 «y si allá son las 10 de la mañana acá qué hora es» after «qué hora es en madrid»: talked,
# and the writer said this PC's clock as the answer, ⚠ clock_pattern): «allá», «allí», «there» in a clock question
# point at the place of the clock question before it. Only a place the person named in their own earlier question.
_CLOCK_PLACE_ANAPHOR = re.compile(r"\b(?:alla|alli|over\s+there|there)\b")


def clock_there_request(text: str, prior_user_texts: Iterable[str]) -> str | None:
    """«y si allá son las 10 de la mañana acá qué hora es» after «qué hora es en madrid» → «y si en madrid son las 10
    de la mañana acá qué hora es»: the message with «allá» said as the place of the last clock question that named
    one, when that reads as the time of another place; None otherwise."""

    said = " ".join(str(text or "").split())
    folded = _fold(said)
    anaphor = _CLOCK_PLACE_ANAPHOR.search(folded)
    if anaphor is None or clock_elsewhere(folded) is not None:
        return None
    # The person's own spelling is kept where folding kept the length (accents, capitals).
    written = said if len(folded) == len(said) else folded
    for prior in reversed(tuple(prior_user_texts)):
        prior_said = " ".join(str(prior or "").split())
        prior_folded = _fold(prior_said)
        before = clock_elsewhere(prior_folded)
        if before is None:
            continue
        found = re.search(r"\b" + re.escape(before.said) + r"\b", prior_folded)
        place = (
            prior_said[found.start():found.end()]
            if found is not None and len(prior_folded) == len(prior_said)
            else before.said
        )
        lead = "in" if re.fullmatch(r"(?:over\s+)?there", anaphor.group(0)) else "en"
        resolved = f"{written[:anaphor.start()]}{lead} {place}{written[anaphor.end():]}"
        read = clock_elsewhere(_fold(resolved))
        return resolved if read is not None and read.place == before.place else None
    return None


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


# M113 (DEV-F v4d F-w18-t3 «Remind me the day before the first one's due, nine in the morning» after «…the first one due
# on 1 November.» → a reminder tomorrow at 9:00): days counted from a date said earlier in the conversation. The thing
# named after «before/antes de» is found in the newest message that names it with one date; that date, less or plus the
# days, is the day, and the clock is the one the person says.
_DAY_COUNT = r"(?P<count>the|a|an|one|two|three|el|un|una|dos|tres|\d)"
_DAY_OFFSET = re.compile(
    rf"\b(?:{_DAY_COUNT}\s+)?(?P<unit>days?|dias?)\s+(?P<sign>before|after|antes|despues)(?:\s+(?P<of>of|de|del))?\s+"
    r"(?P<what>[^,.;!?]+)"
    r"|\b(?:el\s+)?dia\s+(?P<sign2>anterior|siguiente)\s+(?:a|al)\s+(?P<what2>[^,.;!?]+)"
    r"|\b(?:la\s+)?vispera\s+(?:de|del)\s+(?P<what3>[^,.;!?]+)"
)
_DAY_COUNT_VALUES = {"two": 2, "dos": 2, "three": 3, "tres": 3}
_ONE_DATE = re.compile(
    rf"\b(?P<day>\d{{1,2}})(?:st|nd|rd|th)?\s+(?:de\s+|of\s+)?(?P<month>{_MONTH})\b(?:,?\s+(?:de\s+)?(?P<year>\d{{4}}))?"
    rf"|\b(?P<month2>{_MONTH})\s+(?P<day2>\d{{1,2}})(?:st|nd|rd|th)?\b(?:,?\s+(?P<year2>\d{{4}}))?"
)
_POINTER = r"(?:eso|esto|that|it|this|then|ese\s+dia|that\s+day)"
_SPANISH_MONTHS = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre",
    "diciembre",
)
_ENGLISH_MONTHS = (
    "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November",
    "December",
)


def _one_date(folded_line: str, today: date) -> date | None:
    """The one date a message gives (its day and month, and its year or the next time that day comes), or None."""

    found = list(_ONE_DATE.finditer(folded_line))
    if len({match.group(0) for match in found}) != 1:
        return None
    match = found[0]
    day = int(match.group("day") or match.group("day2"))
    month = MONTH_NUMBERS[match.group("month") or match.group("month2")]
    year_said = match.group("year") or match.group("year2")
    year = int(year_said) if year_said else today.year
    try:
        moment = date(year, month, day)
        if not year_said and moment < today:
            moment = date(year + 1, month, day)
    except ValueError:
        return None
    return moment


def anchored_day_request(
    text: str, reply: str | None, earlier: Iterable[str] = (), *, today: date | None = None,
) -> str | None:
    """The reminder request «the day before <thing said earlier>, <clock>» makes («set a reminder on 31 October at
    09:00 for the first one's due»), in the person's language; None unless the message counts days from a thing that
    the newest message naming it dates once, and says one clock with its part of the day."""

    said = " ".join(str(text or "").split())
    folded = _fold(said)
    found = _DAY_OFFSET.search(folded)
    if found is None or len(folded) != len(said):
        return None
    clocks = [clock for clock in spoken_clocks(folded) if clock.resolved]
    if len(clocks) != 1:
        return None
    group = next(name for name in ("what", "what2", "what3") if found.group(name))
    what_start, what_end = found.span(group)
    clock_start = folded.find(clocks[0].literal, what_start)
    if 0 <= clock_start < what_end:
        # «el día antes de eso a las 8»: the clock closes what the days are counted from.
        what_end = clock_start
    what = folded[what_start:what_end].strip()
    title = said[what_start:what_end].strip()
    if found.group("of") == "del":
        title = f"el {title}"
    sign_word = found.group("sign") or found.group("sign2") or "before"
    sign = -1 if sign_word in {"before", "antes", "anterior"} else 1
    count = found.group("count") or "one"
    days = _DAY_COUNT_VALUES.get(count, int(count) if count.isdecimal() else 1)
    if found.group("unit") and found.group("unit").endswith("s") and days == 1:
        return None
    today = today or date.today()
    pointer = re.fullmatch(_POINTER, what) is not None
    words = {word for word in re.findall(r"[a-z]{4,}", what) if word not in _NOT_A_POINTED_THING}
    if not pointer and not words:
        return None
    lines = (reply, *earlier) if not pointer else (reply,)
    anchor = next(
        (
            moment for line in lines
            if line and (pointer or words & set(re.findall(r"[a-z]{4,}", _fold(str(line)))))
            and (moment := _one_date(_fold(" ".join(str(line).split())), today)) is not None
        ),
        None,
    )
    if anchor is None:
        return None
    moment = anchor + timedelta(days=sign * days)
    clock = f"{clocks[0].hour:02d}:{clocks[0].minute:02d}"
    spanish = _has(folded, r"\b(?:recuerdame|recordame|recordar|avisame|ponme|pon|antes|despues|dia|vispera|de|el|la)\b")
    for_what = "" if pointer else (f" para {title}" if spanish else f" for {title}")
    alarm = _has(folded, r"\b(?:alarmas?|alarms?|despertador|despiertame|wake\s+me)\b")
    try:
        coming = date(today.year, moment.month, moment.day)
        if coming < today:
            coming = date(today.year + 1, moment.month, moment.day)
    except ValueError:
        coming = None
    # The year is said only when that day's next coming is not the one counted («el 2 de marzo de 2028»).
    year = "" if coming == moment else (f" de {moment.year}" if spanish else f" {moment.year}")
    if spanish:
        noun = "una alarma" if alarm else "un recordatorio"
        return f"ponme {noun} el {moment.day} de {_SPANISH_MONTHS[moment.month - 1]}{year} a las {clock}{for_what}"
    noun = "an alarm" if alarm else "a reminder"
    return f"set {noun} on {moment.day} {_ENGLISH_MONTHS[moment.month - 1]}{year} at {clock}{for_what}"


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
    rf"|(?:el|on\s+the|the|dia)\s+(?P<day_alone>{_DAY})(?!\s+(?:(?:de|of)\s+)?{_MONTH}\b)"
    # M113 (DEV-F v4d F-w18-t3 «…for the first one's due»): «the first one», «the second time», «first thing» count
    # things, not days.
    r"(?!\s+(?:one|ones|time|times|thing|things|uno|una|vez)\b))"
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
# A run of days said by its ends («entre hoy y el veintiuno», «desde el lunes hasta el jueves», «from
# monday to friday») or by its last day («hasta el viernes»); each end is read as a day on its own.
_DAY_RANGE = re.compile(
    r"\b(?:(?:entre|between|desde|from)\s+(?P<first>.+?)\s+(?:y|and|hasta|to|until|till|al|a)\s+|"
    r"(?:hasta|until|till)\s+)(?P<last>.+)$"
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


def _count_value(raw: str) -> int:
    raw = " ".join(raw.split())
    return int(raw) if raw.isdecimal() else 1 if raw == "una" else _PERCENTAGE_WORD_VALUES[raw]


def _relative_span(text: str, now: datetime) -> tuple[datetime, datetime] | None:
    """«los próximos tres meses», «the last two weeks»: a span counted from ``now``."""

    span = _RELATIVE_SPAN.search(text)
    if span is None:
        return None
    count = _count_value(span.group("count") or span.group("count_first"))
    unit = span.group("unit") or span.group("unit_first")
    forward = bool(span.group("ahead") or span.group("ahead_after"))
    sign = 1 if forward else -1
    if unit.startswith(("mes", "month")):
        other = _add_months(now, sign * count)
    else:
        other = now + timedelta(days=sign * count * (7 if unit.startswith(("semana", "week")) else 1))
    return (now, other) if forward else (other, now)


# Tanda 6 «¿sabes qué días fueron el último fin de semana?»: a weekend or a weekday already gone, and a day counted
# from today («dentro de diez días», «hace tres días», «in 3 days», «two days ago»), are days of the calendar too.
_WEEKDAY_NAME = alternation(tuple(name for names in _WEEKDAYS for name in names))
_LAST_WEEKEND = (
    r"\b(?:ultimo|pasado|anterior)\s+(?:fin\s+de\s+semana|finde)\b|\b(?:fin\s+de\s+semana|finde)\s+(?:pasado|anterior)\b|"
    r"\b(?:last|past|previous)\s+weekend\b"
)
_PAST_WEEKDAY = (
    rf"\b(?:{_WEEKDAY_NAME})\s+(?:pasado|anterior)\b|\b(?:ultimo|pasado|last|previous|past)\s+(?:{_WEEKDAY_NAME})\b"
)
_COUNTED_DAY = re.compile(
    rf"\b(?:(?:dentro\s+de|en|in)\s+(?P<ahead>\d{{1,3}}|{_SPAN_COUNT_WORDS})\s+(?:dias|days)|"
    rf"hace\s+(?P<ago>\d{{1,3}}|{_SPAN_COUNT_WORDS})\s+dias|(?P<ago_after>\d{{1,3}}|{_SPAN_COUNT_WORDS})\s+days\s+ago)\b"
)


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
    # Uso real 2026-09-24 «qué pasó en la reunión de ayer»: a day already gone is a window too.
    if re.search(r"\b(?:anteayer|antier)\b|\bday\s+before\s+yesterday\b", text):
        add(today - timedelta(days=2))
    elif re.search(r"\b(?:ayer|yesterday|anoche|last\s+night)\b", text):
        add(today - timedelta(days=1))
    counted = _COUNTED_DAY.search(text)
    if counted is not None:
        ahead = counted.group("ahead")
        add(today + timedelta(days=_count_value(ahead) if ahead else -_count_value(
            counted.group("ago") or counted.group("ago_after")
        )))
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
    elif re.search(_LAST_WEEKEND, text):
        add(saturday - timedelta(days=7), 2)
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
    elif len(weekdays) == 1 and re.search(_PAST_WEEKDAY, text):
        add(today - timedelta(days=(today.weekday() - weekdays[0]) % 7 or 7))
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
    day_range = _DAY_RANGE.search(text)
    if day_range is not None:
        # Uso real 2026-09-24 «todos los eventos entre hoy y el veintiuno», «from monday to friday», «hasta
        # el viernes»: from the first day said (today when none) to the end of the last.
        first = _said_days(day_range.group("first"), now.date()) if day_range.group("first") else {
            (now.date(), now.date() + timedelta(days=1))
        }
        last = _said_days(day_range.group("last"), now.date())
        if len(first) == 1 and len(last) == 1:
            (start, _), (_, end) = next(iter(first)), next(iter(last))
            if end <= start and re.search(r"\b(?:" + "|".join(n for names in _WEEKDAYS for n in names) + r")\b",
                                          day_range.group("last")):
                # «from monday to friday» said on a Thursday: the Friday after that Monday.
                end += timedelta(days=7)
            if start < end:
                return [(datetime.combine(start, time()), datetime.combine(end, time()))]
    days = _said_days(text, now.date())
    part = None
    if re.search(r"\b(?:after\s+work|despues\s+del\s+trabajo)\b", text):
        part = (17, 24)
    elif (part_found := re.search(_DAY_PART, text)) is not None:
        part = _PART_HOURS[part_found.group("part") or part_found.group("english") or "tonight"]
    if not days and part is not None:
        days.add((now.date(), now.date() + timedelta(days=1)))
    clocks = _CLOCK_RANGE.search(text)
    if clocks is not None and len(days) <= 1:
        # «entre las ocho de la mañana y las cinco de la tarde hoy», «esta mañana entre las diez y las
        # doce»: the hours said bound the one day (today when none is said).
        end_clock = _range_clock(clocks.group("end"), None, text)
        start_clock = _range_clock(clocks.group("start"), clocks.group("end_period"), text)
        day = next(iter(days))[0] if days else now.date()
        if (
            start_clock is not None and end_clock is not None and start_clock.resolved and end_clock.resolved
            and (start_clock.hour, start_clock.minute) < (end_clock.hour, end_clock.minute)
        ):
            base = datetime.combine(day, time())
            return [(
                base + timedelta(hours=start_clock.hour, minutes=start_clock.minute),
                base + timedelta(hours=end_clock.hour, minutes=end_clock.minute),
            )]
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
    "second third several few couple varios varias unos unas pocos pocas upcoming venir "
    "ayer anteayer antier anoche yesterday entre between desde from hasta until till y and to por "
    "ultimo anterior previous hace ago dentro finde".split()
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


def relative_days(folded: str, today: date) -> tuple[date, ...]:
    """The days a phrase that says only a time names, counted from ``today`` («mañana», «el último fin de semana»,
    «el lunes pasado», «in three days»), in order; empty for a phrase that says something else, several runs of
    days, or more than a week. Tanda 6: these are arithmetic on this PC's calendar, never a guess. A date or a
    holiday named by itself («el 4 de julio», «el 21», «año nuevo») is not counted from today."""

    if (
        not is_window_phrase(folded)
        or spoken_date(folded) is not None
        or _has(folded, rf"\b{_MONTH}\b|\b(?:ano\s+nuevo|new\s+year'?s?)\b")
    ):
        return ()
    spans = _said_days(_hyphens_as_spaces(folded), today)
    if len(spans) != 1:
        return ()
    start, end = next(iter(spans))
    length = (end - start).days
    return tuple(start + timedelta(days=index) for index in range(length)) if 1 <= length <= 7 else ()


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
            if _is_a_clock(found):
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

    # M97 (reserve «what is happening after one and before three p.m.»): a span said by its two edges is the span
    # from one to the other.
    folded = re.sub(r"\bdespues\s+de\s+(.{1,40}?)\s+y\s+antes\s+de\s+", r"de \1 a ", folded)
    folded = re.sub(r"\bafter\s+(.{1,40}?)\s+and\s+before\s+", r"from \1 to ", folded)
    windows = _said_windows(_hyphens_as_spaces(folded), now)
    if not windows and spoken_clock(folded) is not None:
        # M97 (reserve «estoy libre a las cuatro de la tarde»): an hour with no day said is today's.
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return midnight, midnight + timedelta(days=1)
    if not windows:
        return now, now + timedelta(days=UPCOMING_DAYS)
    return windows[0] if len(windows) == 1 else None


# --- A task at a time, and the change of a notification's time (M58) ---------------------------------------------
# v3d-final F-s011 «Reanudar el ejercicio en 5 minutos, mejor en 10 minutos» asked «¿cuándo y en qué formato?»: the
# decider chose notification.schedule and restated «en 10 minutos», but no reader took a task said without the word
# «alarma» or «recordatorio», and the model's extraction abstained. F-s019 «Cambia la alarma despertador de las 8:00 a
# las 9:00», F-s044 «change the reminder for the chef's table group from 3 to 4» and F-s095 «Cambia el temporizador a
# una hora» asked the time back: a change is cancelling the one at the old time (or the last one) and setting the new.


def _same_length_fold(text: str) -> str:
    """``text`` lower-cased and without accents, one character for each character, so a span found here cuts the
    person's own words."""

    folded = []
    for character in text:
        base = "".join(part for part in unicodedata.normalize("NFKD", character) if not unicodedata.combining(part))
        folded.append(base.lower() if len(base) == 1 else character.lower())
    return "".join(folded)


# M110 (DEV-F v4d F-w32-t5 «recuérdame enchufar el compu en una hora más» → titled «más enchufar la compu»): «en una
# hora más» is «en una hora»; the «más» belongs to the time, never to what is reminded.
_DURATION_MORE = r"(?:\s+mas\b(?!\s+o\s+menos))?"
_RELATIVE_DUE = rf"(?:en|in|dentro\s+de|within)\s+{_RELATIVE_DURATION_PATTERN}{_DURATION_MORE}"
_TASK_TIME = re.compile(rf"\b(?:{_RELATIVE_DUE}|{CLOCK_PHRASE})(?=\s|$|[,;:.?!])")
# M110: the day said right beside a clock («el jueves a las 10», «a las 3 de la tarde el domingo», «mañana at 6:30 pm»).
# «esta mañana» and «la mañana» are a part of the day, not tomorrow. Same-length folded.
_SAID_WEEKDAY = "(?:" + "|".join(name for names in _WEEKDAYS for name in names) + ")"
_SAID_DAY = (
    r"(?P<day>pasado\s+manana|day\s+after\s+tomorrow|(?<!\besta\s)(?<!\bla\s)manana|tomorrow|hoy|today|tonight|"
    # «el domingo 2 de octubre», «on Friday, October 9th»: a date said with or without its weekday.
    rf"(?:(?:el|este|this|on|next|el\s+proximo|this\s+coming)\s+)?(?:{_SAID_WEEKDAY},?\s+)?"
    rf"(?:\d{{1,2}}\s+de\s+{_MONTH}(?:\s+de\s+\d{{4}})?|{_MONTH}\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?)|"
    rf"(?:(?:el|este|this|on|next|el\s+proximo|this\s+coming)\s+)?{_SAID_WEEKDAY})"
)
# «la reunión de mañana a las nueve»: a day after «de / del / of» names the thing, and stays in what it is for.
_DAY_BEFORE_TIME = re.compile(rf"(?<!\bde\s)(?<!\bdel\s)(?<!\bof\s)\b{_SAID_DAY}\s*,?\s*$")
_DAY_AFTER_TIME = re.compile(rf"\s*,?\s*{_SAID_DAY}\b")
# The words that open an answer or a request and say nothing of it («órale, pues», «yeah sure», «ok»).
_OPENING_WORDS = (
    r"(?:(?:oye|ok|okey|okay|vale|bueno|pues|[oó]rale|dale|venga|yeah|yes|yep|sure|s[ií]|claro)\b\s*,?\s*)*"
)
# What may stand between a time and the one that corrects it: «en 5 minutos, mejor en 10», «at 6, actually at 7».
_TIME_CORRECTION = re.compile(
    r"\s*[,;]?\s*(?:y\s+|and\s+)?(?:no\s*,?\s*)?(?:mejor(?:\s+dicho)?|digo|o\s+sea|perdon|rather|actually|i\s+mean|"
    # M76 (DEV-D v3l D-s097 «… en 2 , no espera en 3 minutos»): «espera» / «wait» take the time back too.
    r"make\s+it|(?:no\s*,?\s*)?(?:espera|espere|wait)(?:\s*,?\s*no)?|no)\s*[,;]?\s*"
)
# M76 (DEV-D v3l D-s097 «Quiero retomar el entrenamiento de glúteo en 2 , no espera en 3 minutos» → a timer of 2
# minutes): the time taken back may leave its unit to the time that corrects it; only the number is said.
_ELIDED_TAKEN_BACK = re.compile(
    r"\b(?P<taken>(?:en|in|dentro\s+de|within|a\s+las?|at)\s+(?:\d{1,4}(?::\d{2})?|un[oa]?|dos|tres|cuatro|cinco|"
    r"seis|siete|ocho|nueve|diez|quince|veinte|treinta|one|two|three|four|five|six|seven|eight|nine|ten|fifteen|"
    r"twenty|thirty))(?:" + _TIME_CORRECTION.pattern + r")$"
)


# «at 8:30 actually 9:30», «en 5 minutos, mejor 10 minutos»: the time kept may leave its lead to the one taken back.
_BARE_KEPT_TIME = re.compile(
    rf"(?:{_RELATIVE_DURATION_PATTERN}|{_CLOCK_HOUR}{_CLOCK_MINUTES}?(?:{_O_CLOCK})?(?:\s*{_CLOCK_PERIOD})?)"
    r"(?=\s|$|[,;:.?!])"
)
_TIME_LEAD = re.compile(r"(?:en|in|dentro\s+de|within|a\s+las?|para\s+las?|at)\s+")


@dataclass(frozen=True)
class TakenBackTime:
    """A time the person said and took back at once for another, both in the person's words: ``taken_back`` (with
    its unit or without it) and ``kept``, the one that stands (with the lead of the one taken back when it said
    none); ``start`` is where the time taken back begins and ``end`` where the time kept ends."""

    taken_back: str
    kept: str
    start: int
    end: int


def taken_back_time(text: str) -> TakenBackTime | None:
    """«en 2, no espera en 3 minutos», «at 8:30 actually 9:30», «en 5 minutos, mejor en 10 minutos»: the time taken
    back and the one kept. None without such a correction."""

    said = str(text or "")
    folded = _same_length_fold(said)
    times = list(_TASK_TIME.finditer(folded))
    for before, after in zip(times, times[1:]):
        if _TIME_CORRECTION.fullmatch(folded[before.end():after.start()]) is not None:
            return TakenBackTime(
                said[before.start():before.end()], said[after.start():after.end()], before.start(), after.end(),
            )
    for kept in times:
        elided = _ELIDED_TAKEN_BACK.search(folded[:kept.start()])
        if elided is not None:
            return TakenBackTime(
                said[elided.start("taken"):elided.end("taken")], said[kept.start():kept.end()], elided.start(),
                kept.end(),
            )
    for before in times:
        correction = _TIME_CORRECTION.match(folded, before.end())
        bare = _BARE_KEPT_TIME.match(folded, correction.end()) if correction is not None else None
        lead = _TIME_LEAD.match(folded, before.start())
        if bare is not None and lead is not None:
            return TakenBackTime(
                said[before.start():before.end()], f"{said[lead.start():lead.end()]}{said[bare.start():bare.end()]}",
                before.start(), bare.end(),
            )
    return None
_NOTIFICATION_NOUN = (
    r"\b(?:alarmas?|alarms?|alertas?|alerts?|temporizador(?:es)?|timers?|recordatorios?|reminders?|avisos?|"
    r"despertador(?:es)?|notificacion(?:es)?|notifications?)\b"
)


_DURATION_NUMBER_WORDS = {
    "un": 1, "una": 1, "uno": 1, "one": 1, "a": 1, "an": 1, "dos": 2, "two": 2, "tres": 3, "three": 3, "cuatro": 4,
    "four": 4, "cinco": 5, "five": 5, "seis": 6, "six": 6, "siete": 7, "seven": 7, "ocho": 8, "eight": 8, "nueve": 9,
    "nine": 9, "diez": 10, "ten": 10, "once": 11, "eleven": 11, "doce": 12, "twelve": 12, "quince": 15, "fifteen": 15,
    "veinte": 20, "twenty": 20, "treinta": 30, "thirty": 30, "cuarenta y cinco": 45, "forty five": 45, "sesenta": 60,
    "sixty": 60,
}
_SAID_DURATION = re.compile(
    r"\b(?P<duration>(?P<number>\d{1,3}|" + "|".join(sorted(_DURATION_NUMBER_WORDS, key=len, reverse=True))
    + r")[\s-]*(?P<unit>minutos?|minutes?|mins?|min|horas?|hours?|hrs?|h)|(?P<half>media\s+hora|half\s+an?\s+hour))\b"
)


def trailing_day(text: str) -> tuple[str, str] | None:
    """(``text`` without it, the day) when ``text`` ends with a day («pagar la luz mañana» → («pagar la luz»,
    «mañana»)); None otherwise. M110: the day a reader left at the end of a title belongs to the moment after it."""

    said = str(text or "")
    found = _DAY_BEFORE_TIME.search(_same_length_fold(said))
    if found is None or not said[: found.start()].strip(" ,"):
        return None
    return said[: found.start()].rstrip(" ,"), said[found.start("day"):].strip(" ,")


def said_durations(text: str) -> tuple[tuple[str, int], ...]:
    """M110: each length of time the person wrote, as written, with its minutes («en 15 minutes» → («15 minutes»,
    15), «una hora más» → («una hora», 60), «a 25-minute countdown» → («25-minute», 25))."""

    said = str(text or "")
    folded = _same_length_fold(said)
    found: list[tuple[str, int]] = []
    for match in _SAID_DURATION.finditer(folded):
        minutes = _duration_minutes(match)
        if minutes:
            found.append((said[match.start("duration"):match.end("duration")], minutes))
    return tuple(found)


def _duration_minutes(match: re.Match[str]) -> int:
    """The minutes of one ``_SAID_DURATION`` match."""

    if match.group("half"):
        return 30
    number = match.group("number")
    amount = int(number) if number.isdecimal() else _DURATION_NUMBER_WORDS[" ".join(number.split())]
    return amount * (60 if match.group("unit").startswith("h") else 1)


@dataclass(frozen=True)
class TimedTask:
    """A thing to do and when, said without naming an alarm or a reminder: ``title`` in the person's words and
    ``due`` the one time kept (the last of a corrected pair)."""

    title: str
    due: str
    kind: str = "reminder"


# M76 (DEV-D v3l D-s120 «Cojamos un descanso de 14 minutos del yoga para el yoga.» → «¿Cuándo … y si es una alarma o un
# recordatorio?»): a rest of a stated length ends after that length; what is set is the alarm that ends it.
_TIMED_BREAK = re.compile(
    r"\b(?:tom(?:ar|a|emos|emonos|ate|arme|arnos)|coj(?:amos|o)|coger(?:nos|me)?|hacer|hagamos|haz|haga|"
    r"take|let'?s\s+take|have|having)\s+(?:(?:un|una|a|an)\s+)?"
    rf"(?:(?P<before>{_RELATIVE_DURATION_PATTERN})[\s-]+)?(?P<noun>descanso|pausa|break|respiro|rest)\b"
    rf"(?:\s+(?:de|of)\s+(?P<after>{_RELATIVE_DURATION_PATTERN}))?"
)


def timed_break(text: str) -> TimedTask | None:
    """«Cojamos un descanso de 14 minutos», «take a 10 minute break»: the alarm at the end of the rest, titled with
    the rest as said. None without a length, or for a question."""

    said = " ".join(str(text or "").split())
    folded = _same_length_fold(said)
    found = _TIMED_BREAK.search(folded)
    if "?" in said or found is None or not (found.group("before") or found.group("after")):
        return None
    amount = found.group("after") or found.group("before")
    title = said[found.start("noun"):].strip(" ,;:.!¡¿")
    english = found.group("noun") in {"break", "rest"}
    return TimedTask(title, f"{'in' if english else 'en'} {amount}", "alarm")


def timed_task(text: str) -> TimedTask | None:
    """«Reanudar el ejercicio en 5 minutos, mejor en 10 minutos» → TimedTask(«Reanudar el ejercicio», «en 10
    minutos»). None when an alarm or reminder noun is said (their own readers read it), for a question, with two
    times that are not a correction of each other, or with no task beside the time."""

    folded = _same_length_fold(str(text or ""))
    if "?" in text or re.search(_NOTIFICATION_NOUN, folded):
        return None
    times = list(_TASK_TIME.finditer(folded))
    if not times or any(
        _TIME_CORRECTION.fullmatch(folded[before.end():after.start()]) is None
        for before, after in zip(times, times[1:])
    ):
        return None
    head_end, tail_start, due = times[0].start(), times[-1].end(), text[times[-1].start():times[-1].end()]
    taken_back = taken_back_time(text)
    if taken_back is not None:
        # M76 (DEV-D v3l D-s097): «en 2 , no espera» before the time kept, or «actually 9:30» after the one taken
        # back, is the correction, not the task; the time kept is the due.
        head_end, tail_start, due = min(head_end, taken_back.start), max(tail_start, taken_back.end), taken_back.kept
    if not re.match(_RELATIVE_DUE, _same_length_fold(due)):
        # M110 (DEV-F v4d F-w37-t3 «Recuérdame el jueves a las 10:00 que conteste…» → titled «el jueves que conteste…»
        # for tomorrow at 10:00; F-w48-t4 «recuérdame eso el domingo a las 3 de la tarde» → today at 15:00): the day
        # said beside the clock is the day it rings, never words of what is reminded.
        before = _DAY_BEFORE_TIME.search(folded[:head_end])
        after = _DAY_AFTER_TIME.match(folded[tail_start:])
        if before is not None:
            due, head_end = f"{text[before.start('day'):head_end].strip(' ,')} {due}", before.start()
        if after is not None:
            due, tail_start = f"{due} {text[tail_start + after.start('day'):tail_start + after.end()]}", tail_start + after.end()
    title = re.sub(r"\s+([,;:])", r"\1", " ".join(f"{text[:head_end]} {text[tail_start:]}".split())).strip(" ,;:.!¡¿")
    # «Recuérdame llamar a Ana en 10 minutos»: the order to remind is not what is reminded. M76 (D-s097 «Quiero
    # retomar el entrenamiento…»): nor is the wish that opens it, nor (M110, F-w48-t4 «órale, pues recuérdame…»,
    # F-w59-t2 «yeah sure mañana at 6:30 pm») the word that opens the answer.
    title = re.sub(
        rf"^{_OPENING_WORDS}(?:(?:por\s+favor|please)\s*,?\s+)?(?:recu[eé]rd(?:a|ame)|record[aá]me|av[ií]same|"
        r"ac[uú]erdate|remind\s+me|remember|quiero|quisiera|necesito|i\s+want\s+to|i'd\s+like\s+to|i\s+need\s+to)\s+"
        rf"(?:de\s+|que\s+|to\s+)?|^{_OPENING_WORDS}(?:que|to)\s+|^{_OPENING_WORDS}$",
        "", title, flags=re.IGNORECASE,
    )
    if (
        not re.match(r"[^\W\d_]", title)
        or len(title) > 160
        or _TASK_TIME.search(_same_length_fold(title))
        # «recuérdame eso»: what «eso» points at is not said here; no reminder is titled «eso».
        or re.fullmatch(r"(?:eso|esto|aquello|lo|that|this|it)", _same_length_fold(title))
    ):
        return None
    return TimedTask(title, " ".join(due.split()))


def placed_day_of_moment(request: str, said: str, due: str) -> str | None:
    """M170 (DEV-I v4y I-w20-t3 «tambien tengo una reunion a las 9, recuerdamelo 15 minutos antes de eso» after the
    alarm moved to tomorrow at 8, decided «Recuérdame mañana a las 8:45 que tengo una reunión a las 9.»): for a moment
    ``due`` with no day of its own, read from ``said`` (the person's message, or the request itself) that asks to be
    reminded some time before it (``said_advance``), the day the request places beside that moment's clock or beside the
    clock that rings (the moment less the advance: «mañana a las 8:45»), as said. D61b then reads the hour on that day.
    None with no advance said, when the moment or ``said`` names a day other than that one or a date, or when the request
    places those clocks on two days, only on today or on none."""

    folded_due = _fold(str(due or ""))
    due_clocks = spoken_clocks(folded_due)
    advance = said_advance(str(said or ""))
    if (
        advance is None
        or len(due_clocks) != 1
        or (due_clocks[0].hour % 12, due_clocks[0].minute) != (advance.clock.hour % 12, advance.clock.minute)
        or spoken_date(folded_due) is not None
        or spoken_day(folded_due, 0) != (0, 1)
    ):
        return None
    moment = (due_clocks[0].hour % 12) * 60 + due_clocks[0].minute
    rings = divmod((moment - advance.minutes) % 720, 60)
    request_text = " ".join(str(request or "").split())
    folded_request = _same_length_fold(request_text)
    days: dict[str, str] = {}
    for found in _TASK_TIME.finditer(folded_request):
        clocks = spoken_clocks(_fold(found.group(0)))
        if not clocks or (clocks[0].hour % 12, clocks[0].minute) not in {divmod(moment, 60), rings}:
            continue
        before = _DAY_BEFORE_TIME.search(folded_request[:found.start()])
        after = _DAY_AFTER_TIME.match(folded_request[found.end():])
        for match, offset in ((before, 0), (after, found.end())):
            if match is not None:
                day = request_text[offset + match.start("day"):offset + match.end("day")]
                days.setdefault(" ".join(_fold(day).split()), day)
    if len(days) != 1:
        return None
    folded_day, day = next(iter(days.items()))
    placed = spoken_day(folded_day, 0)
    if spoken_date(folded_day) is None and placed in {None, (0, 0), (0, 1)}:
        # «hoy a las 8:45», «tonight at 8:45»: today keeps D61 (the next time it comes), as with no day said.
        return None
    folded_said = _fold(str(said or ""))
    if spoken_date(folded_said) is not None or spoken_day(folded_said, 0) not in {(0, 1), placed}:
        return None
    return day


@dataclass(frozen=True)
class UnschedulableTime:
    """M80: the clock the person said (``clock``, as said) on days one alarm or reminder cannot ring at: ``passed``
    the days said whose moment is already past, ``ahead`` those still to come (the words as said)."""

    clock: str
    passed: tuple[str, ...]
    ahead: tuple[str, ...]


_THIS_WEEK = r"\b(?:this\s+week|esta\s+semana)\b"
_TODAY_WORD = r"\b(?:hoy|today|tonight|esta\s+(?:tarde|noche|manana))\b"


def unschedulable_time(text: str, now: datetime) -> UnschedulableTime | None:
    """M80 (DEV-D v3m D-s104 «…para la cena a las 18:00 hoy.» at 19:35, D-s108 «…for Monday, Tuesday and Wednesday of
    this week for 7am» on a Tuesday): one clock said for a moment no single notification holds: today's clock already
    past, or several days (some of them maybe past this week). Every value was said; what is left is only which moment,
    and why. None for a date, a clock without its part of the day, two clocks or any moment one notification holds.
    ``now`` is the local time with its zone."""

    folded = _fold(str(text or ""))
    clocks = spoken_clocks(folded)
    if len(clocks) != 1 or not clocks[0].resolved or spoken_date(folded) is not None:
        return None
    clock = clocks[0]
    at = time(clock.hour, clock.minute)
    this_week = re.search(_THIS_WEEK, folded) is not None
    named = [
        (index, found.group(0))
        for index, names in enumerate(_WEEKDAYS)
        if (found := re.search(rf"\b(?:{'|'.join(names)})\b", folded)) is not None
    ]
    if named:
        passed: list[str] = []
        ahead: list[str] = []
        for index, word in named:
            offset = index - now.weekday()
            if not this_week:
                offset %= 7
            moment = datetime.combine(now.date() + timedelta(days=offset), at, tzinfo=now.tzinfo)
            if not this_week and moment <= now:
                moment += timedelta(days=7)
            (passed if moment <= now else ahead).append(word)
        if len(named) == 1 and not passed:
            return None
        return UnschedulableTime(clock.literal, tuple(passed), tuple(ahead))
    today = re.search(_TODAY_WORD, folded)
    if today is None or spoken_day(folded, now.weekday()) != (0, 0):
        return None
    if datetime.combine(now.date(), at, tzinfo=now.tzinfo) > now:
        return None
    return UnschedulableTime(clock.literal, (today.group(0),), ())


_CHANGE_CLOCK = rf"{_CLOCK_HOUR}{_CLOCK_MINUTES}?(?:\s*{_CLOCK_PERIOD})?"
_CHANGE_NOUN = r"(?P<noun>alarma|alerta|temporizador|recordatorio|aviso|despertador|alarm|alert|timer|reminder)"
_REMINDER_NOUNS = frozenset({"recordatorio", "aviso", "reminder"})
_MASCULINE_NOUNS = frozenset({"temporizador", "recordatorio", "aviso", "despertador"})
_NOTIFICATION_CHANGE = (
    re.compile(
        r"^(?:(?:por\s+favor|oye|baxy)\s*,?\s+)*(?:cambia(?:me|la|lo)?|cambie|cambiar|mueve(?:me|la|lo)?|mover|"
        r"pasa(?:me|la|lo)?|pasar|modifica(?:la|lo)?|modificar|atrasa(?:me|la|lo)?|adelanta(?:me|la|lo)?)\s+"
        rf"(?:(?:la|el|mi|tu)\s+)?{_CHANGE_NOUN}(?P<title>(?:\s+(?!de\s+las?\s)[^\d,;]+?)?)"
        rf"(?:\s+de\s+(?:las?\s+)?(?P<old>{_CHANGE_CLOCK}))?"
        rf"\s+(?:a|para)\s+(?:(?:las?|una?)\s+)?(?P<new>{_RELATIVE_DURATION_PATTERN}|{_CHANGE_CLOCK})"
        # M110 (DEV-F v4d F-w07-t4, restated «Cambia la alarma de las 18:30 a las 18:15 para el impermeable.»): what
        # it is for may follow the new time.
        r"(?:\s+(?:para|por)\s+(?P<tail>[^\d,;.!?]+?))?"
        r"(?:\s*,?\s*(?:por\s+favor|porfa|please))?[\s.!]*$"
    ),
    re.compile(
        r"^(?:(?:please|hey|baxy)\s*,?\s+)*(?:change|move|reschedule|push|shift|switch|update)\s+"
        rf"(?:(?:the|my)\s+)?{_CHANGE_NOUN}(?P<title>(?:\s+(?:for|about|of|to)\s+[^\d,;]+?)?)"
        rf"(?:\s+from\s+(?P<old>{_CHANGE_CLOCK}))?"
        # M110 (DEV-F v4d F-w15-t4, restated «Move the reminder to pack the rain jackets to Friday at 7:15 pm.»): the
        # new time may come with its day.
        rf"\s+to\s+(?:(?P<newday>(?:(?:this|next|on)\s+)?{_SAID_WEEKDAY}|tomorrow|today|tonight)\s+(?:at\s+)?)?"
        rf"(?:an?\s+)?(?P<new>{_RELATIVE_DURATION_PATTERN}|{_CHANGE_CLOCK})"
        r"(?:\s*,?\s*please)?[\s.!]*$"
    ),
)


# D39 (owner, 2026-09-29; v3d-final F-s040 «Cancela las alarmas, por favor.» → «¿Qué alarma deseas cancelar?»): the
# alarms named in the plural without saying which are read first, and BAXY offers to cancel all of them with the list
# («Tienes 3 alarmas (7:00, 8:30 y 12:00). ¿Las cancelo todas?»); they are cancelled only when the person says yes.
# This replaces the plural branch of the which-alarm clarification of uso real 2026-09-24. A plural that says which
# («mis alarmas de la mañana», «my alarms for tomorrow», «las de las 7») is still asked.
_PLURAL_ALARM_CANCELLATION = re.compile(
    r"^(?:(?:por\s+favor|porfa|oye|baxy|please|hey)\s*,?\s+)*"
    r"(?:apaga(?:me)?|quita(?:me)?|borra(?:me)?|elimina(?:me)?|cancela(?:me)?|desactiva(?:me)?|remove|delete|cancel|"
    r"turn\s+off|clear|disable)\s+"
    r"(?:(?:mis|las|todas\s+(?:mis|las)|my|the|all(?:\s+(?:of\s+)?(?:my|the))?)\s+)?(?:alarmas|alarms)"
    r"(?:\s*,?\s*(?:por\s+favor|porfa|please))?[\s.!]*$"
)


def plural_alarm_cancellation(text: str) -> bool:
    """«Cancela las alarmas», «quita todas mis alarmas», «cancel my alarms»: every alarm, none said (D39)."""

    return _PLURAL_ALARM_CANCELLATION.match(_strip_request_envelope(_fold(str(text or ""))).strip()) is not None


# D39: the yes to the offer («sí», «dale», «sí, cancélalas todas», «yes, all of them»); anything else is not it.
_ALARM_OFFER_ASSENT = re.compile(
    r"^[¿?¡!\s]*(?:si|dale|ok|okey|okay|bueno|claro|por\s+favor|yes|yeah|yep|sure|please|go\s+ahead|do\s+it|hazlo|"
    r"hacelo|todas|all\s+of\s+them|cancelalas|cancela(?:las)?\s+todas|borralas|quitalas|cancel\s+(?:them|all)(?:\s+of\s+them)?)"
    r"(?:[,\s]+(?:si|dale|por\s+favor|please|hazlo|hacelo|todas(?:\s+ellas)?|all(?:\s+of\s+them)?|cancelalas(?:\s+todas)?|"
    r"cancela(?:las)?\s+todas|borralas|quitalas|cancel\s+(?:them|all)(?:\s+of\s+them)?|go\s+ahead))*[\s.!]*$"
)


def assents_to_alarm_offer(text: str) -> bool:
    return _ALARM_OFFER_ASSENT.match(_fold(str(text or "")).strip()) is not None


# M110 (DEV-F v4d F-w33-t4 «Yeah, go on» after «…kick-off 17:30. Shall I move the alarm to 17:00?» → «What time is the
# Spurs game?»): BAXY offered to set or move a notification at one time; the yes is that notification, at that time.
_NOTIFICATION_OFFER = re.compile(
    r"(?:\b(?:shall|should|can|may)\s+i|\b(?:do\s+you\s+)?want\s+me\s+to|\bwould\s+you\s+like\s+me\s+to)\s+"
    r"(?:set|move|put|change|schedule|reschedule|push)\b|"
    r"(?:\b(?:te\s+)?(?:pongo|muevo|cambio|programo|paso|corro|dejo)|\bquieres\s+que\s+(?:te\s+)?"
    r"(?:ponga|mueva|cambie|programe|pase|corra|deje))\b"
)
_OFFER_YES = re.compile(
    r"(?:(?:si|sip|dale|ok|okay|okey|claro|bueno|vale|va|yes|yeah|yep|sure|please|por\s+favor|porfa|go\s+on|"
    r"go\s+ahead|do\s+it|hazlo|hacelo|adelante|ponla|ponlo|muevela|muevelo)[\s,.!]*){1,4}"
)


# M110 (DEV-F v4d F-w45-t3 «go with 12, the bag says 10 to 12…» after «How long for the garlic knots?», restated «Set a
# reminder at 12:00…» → «When would you like this reminder to go off?»): BAXY asked how long a timer runs, and the
# answer opens with a number; that number is the length, in the unit asked (minutes unless hours were asked).
_ASKS_HOW_LONG = re.compile(
    r"\b(?:how\s+long|how\s+many\s+(?P<en_unit>minutes|hours)|for\s+how\s+long|"
    r"cuanto\s+tiempo|por\s+cuanto\s+tiempo|de\s+cuanto|cuant[oa]s\s+(?P<es_unit>minutos|horas))\b"
)
_LEADING_AMOUNT = re.compile(
    r"^(?:(?:ok|okay|yeah|yes|si|dale|bueno|pues|mmm|uh|hmm|go\s+with|make\s+it|let'?s\s+(?:do|say|go\s+with)|"
    r"say|ponle|ponlo|pon|que\s+sean?|mejor|unos|unas|about|around|like|como|tipo)[\s,]+)*"
    r"(?P<amount>\d{1,3}|"
    + "|".join(sorted((word for word in _DURATION_NUMBER_WORDS if word not in {"a", "an"}), key=len, reverse=True))
    + r")(?:[\s-]*(?P<unit>minutos?|minutes?|mins?|min|horas?|hours?|hrs?|h))?\b"
)


def answered_timer_length(text: str, reply: str | None, earlier: Iterable[str] = ()) -> str | None:
    """The timer request an answer to BAXY's «how long?» makes («set a 12-minute timer for the garlic knots»), in the
    question's language; None unless the reply's last question asks how long, the conversation just before it was
    about a timer, alarm or countdown, and the message opens with the amount."""

    answer = " ".join(str(reply or "").split())
    if not answer.endswith("?"):
        return None
    question = re.split(r"(?<=[.!?])\s+", answer)[-1]
    asked = _ASKS_HOW_LONG.search(_fold(question))
    said = _LEADING_AMOUNT.match(_fold(str(text or "")).strip(" ¿?¡!."))
    if asked is None or said is None:
        return None
    if not any(re.search(rf"{_NOTIFICATION_NOUN}|\bcount\s*down\b|\bcountdown\b", _fold(line)) for line in [
        answer, *list(earlier)[:3]
    ]):
        return None
    amount = said.group("amount")
    if amount in {"un", "una", "uno", "one"} and not said.group("unit"):
        # «una» alone opens many answers; only «una hora», «one minute» say a length.
        return None
    value = int(amount) if amount.isdecimal() else _DURATION_NUMBER_WORDS[" ".join(amount.split())]
    unit = said.group("unit") or asked.group("en_unit") or asked.group("es_unit") or "minutes"
    hours = unit.startswith("h")
    if not 0 < value <= (24 if hours else 24 * 60):
        return None
    english = re.search(r"\bhow\b", _fold(question)) is not None
    purpose = re.search(r"\b(?:for|para)\s+(?P<what>[^?]+?)\s*\?$", question)
    what = f" {'for' if english else 'para'} {purpose.group('what')}" if purpose is not None else ""
    if english:
        return f"set a {value} {'hour' if hours else 'minute'} timer{what}"
    return f"pon un temporizador de {value} {'horas' if hours else 'minutos'}{what}".replace("de 1 horas", "de 1 hora")


# M175 (DEV-F v5c F-w34-t4 «Venga, ponme el temporizador para lo de pochar» after «…Pocha patata y cebolla a fuego lento
# unos 20 minutos…», DEV-D v5c D-w10-t3 «¿Me pones un temporizador para voltearlas?» after «…Las cocinamos 5 minutos por
# cada lado.» → «¿Cuántos minutos le pongo al temporizador?»; F-w45-t2 «and one for the garlic knots» after the pizza's
# 25-minute countdown → 25 minutes for the garlic knots): a timer asked «para» a step or a thing BAXY's recent answer
# named with one length is that length, titled by the step; a range («10 a 12 min», «2-3 minutos») is its longest end,
# as M62 reads «later» by the day's maximum. A length said for something else is never borrowed.
# Only what counts a length down: an alarm or a reminder «para el partido» names a moment, not a step.
_STEP_NOTICE = re.compile(
    r"\b(?:temporizador(?:es)?|timers?|count\s*down|countdown|cuenta\s+regresiva|cronometro|avisos?|avisame)\b"
)
_STEP_PURPOSE = re.compile(r"\b(?P<lead>para|pa|for|to)\s+(?P<what>[^,.;:!?¿¡()]+)")
_STEP_GAP = re.compile(r"(?:\s+(?:ahora|now|ya|porfa|please|plis|tambien|too|de\s+cocina|kitchen|nomas|po))*\s*")
_ONE_MORE_FOR = re.compile(
    r"\b(?:(?:one|another)(?:\s+more)?|otr[oa]|un[oa]\s+mas)\s+(?P<lead>for|para|pa)\s+(?P<what>[^,.;:!?¿¡()]+)"
)
_PURPOSE_LEAD_IN = re.compile(r"(?:(?:lo|eso|la\s+parte|el\s+paso|the\s+part|cuando|when)\s+(?:de\s+|que\s+|of\s+)?)")
_PURPOSE_TAIL = re.compile(
    r"(?:\s+(?:por\s+favor|porfa|please|plis|pls|xfa|po|pues|parce|ya|now|ahora|then|entonces|too|tambien|also))+\s*$"
)
_PURPOSE_FILLER = frozenset({
    "lo", "de", "del", "el", "la", "los", "las", "eso", "esa", "ese", "esto", "esta", "este", "estas", "estos", "the",
    "of", "an", "my", "mi", "mis", "tu", "tus", "su", "sus", "que", "and", "to", "them", "it", "its", "con", "with",
    "en", "in", "on", "al", "un", "una", "uno", "this", "that", "these", "those", "cuando", "when", "part", "parte",
    "paso", "step", "thing", "cosa", "les", "le", "se", "me", "for", "para", "por",
})
# A moment («para mañana», «for tonight», «for the day after») is when, never a step.
_PURPOSE_MOMENT = re.compile(
    r"\b(?:hoy|manana|tarde|noche|dia|dias|semana|today|tomorrow|tonight|morning|evening|afternoon|night|day|days|"
    r"week|after|despues|luego|rato|later|now|ahora|lunes|martes|miercoles|jueves|viernes|sabado|domingo|monday|"
    r"tuesday|wednesday|thursday|friday|saturday|sunday)\b"
)
# Flipping is the length of one side («5 minutos por lado», «3 minutes each side»).
_FLIP_STEP = re.compile(r"\b(?:volte\w+|dar(?:le|les|la|las|lo|los)?\s+(?:la\s+)?vuelta|flip\w*|turn\w*\s+(?:\w+\s+)?over)\b")
_ONE_SIDE = re.compile(
    r"\b(?:por\s+(?:cada\s+)?(?:lado|cara)|de\s+cada\s+(?:lado|cara)|cada\s+(?:lado|cara)|(?:per|each|a)\s+side|"
    r"volte\w+|flip\w*|dale(?:s)?\s+(?:la\s+)?vuelta)\b"
)
_LENGTH_RANGE_JOIN = re.compile(r"^\s*(?:a|to|-|–|o|or|y|and|hasta)\s*$")
_SAME_LENGTH_AGAIN = re.compile(
    r"\b(?:igual(?:ito)?|mism[oa]s?|same|again|otra\s+vez|de\s+nuevo|identic\w*)\b"
)
# The step of a word said in the conversation: the word, its plural, or (a verb) another form of it.
_STEP_VERB = re.compile(r"(?P<stem>[a-z]{3,}?)(?:ar|er|ir)(?:la|las|lo|los|le|les|se)?")
_STEP_VERB_FORM = r"(?:a|as|an|ar|e|es|en|o|ad|ado|ada|ados|adas|ando|er|ir|ido|ida|iendo)(?:la|las|lo|los|le|les|se)?"


@dataclass(frozen=True)
class _NoticePurpose:
    """What a timer is asked for: ``said`` in the person's words, ``words`` folded and ``flip`` for a side."""

    said: str
    lead: str
    words: tuple[str, ...]
    flip: bool


def _notice_purpose(text: str, *, one_more: bool = False) -> _NoticePurpose | None:
    said = str(text or "")
    folded = _same_length_fold(said)
    notice = _STEP_NOTICE.search(folded)
    found = _STEP_PURPOSE.match(folded, _STEP_GAP.match(folded, notice.end()).end()) if notice is not None else None
    if found is None and one_more:
        found = _ONE_MORE_FOR.search(folded)
    if found is None or (found.group("lead") == "to" and notice is None):
        # What the timer is for follows it («un temporizador para voltearlas», «a timer to flip them»); a «para» further
        # on is about something else («recuérdame comprar tinto para la oficina»).
        return None
    start, end = found.span("what")
    lead_in = _PURPOSE_LEAD_IN.match(folded, start)
    start = lead_in.end() if lead_in is not None else start
    tail = _PURPOSE_TAIL.search(folded[:end])
    end = tail.start() if tail is not None and tail.start() > start else end
    what = folded[start:end].strip()
    if not what or _PURPOSE_MOMENT.search(what) or re.search(r"\d", what):
        return None
    flip = _FLIP_STEP.search(what) is not None
    words = tuple(word for word in re.findall(r"[a-z]{3,}", what) if word not in _PURPOSE_FILLER)[:4]
    if not words and not flip:
        return None
    return _NoticePurpose(said[start:end].strip(), found.group("lead"), words, flip)


def _step_word_said(word: str, said: Iterable[str]) -> bool:
    verb = _STEP_VERB.fullmatch(word)
    for other in said:
        if other == word or other in {f"{word}s", f"{word}es", f"{word}ed", f"{word}ing"} or (
            word.endswith("s") and other == word[:-1]
        ):
            return True
        if verb is not None and re.fullmatch(verb.group("stem") + _STEP_VERB_FORM, other):
            return True
    return False


def _step_named(purpose: _NoticePurpose, clause: str) -> int:
    """How many of the purpose's words the clause says (a side counts for a flip)."""

    if purpose.flip:
        return 1 if _ONE_SIDE.search(clause) else 0
    said = re.findall(r"[a-z]+", clause)
    return sum(1 for word in purpose.words if _step_word_said(word, said))


def _clause_lengths(clause: str) -> tuple[int, ...]:
    return tuple(minutes for minutes in map(_duration_minutes, _SAID_DURATION.finditer(clause)) if minutes)


def _clause_length(clause: str) -> int | None:
    """The one length a clause says; two joined as a range («10 minutos a 12 minutos») are their longer end."""

    found = [match for match in _SAID_DURATION.finditer(clause) if _duration_minutes(match)]
    if not found:
        return None
    if any(_LENGTH_RANGE_JOIN.match(clause[before.end():after.start()]) is None for before, after in zip(found, found[1:])):
        return None
    return max(_duration_minutes(match) for match in found)


def _answer_clauses(answer: str) -> list[str]:
    folded = _same_length_fold(" ".join(str(answer or "").replace("\n", " . ").split()))
    sentences = re.split(r"(?:(?<!\bmin)(?<!\bmins)(?<!\bseg)\.(?!\d)|[;!?\n])", folded)
    return [clause.strip() for sentence in sentences for clause in sentence.split(",") if clause.strip()]


def step_timer_request(text: str, answers: Iterable[str]) -> str | None:
    """The timer request a timer asked «para» a step or a thing makes («pon un temporizador de 20 minutos para
    pochar»), with the length BAXY's recent ``answers`` (newest first) give that step, in the person's language; None
    unless the message asks a timer or a notice for something and says no length nor clock, and the newest answer
    naming that step gives it one length (a notification BAXY reports setting, or a clock, is no step)."""

    said = str(text or "")
    folded = _fold(said)
    if said_durations(said) or spoken_clocks(folded) or _SAME_LENGTH_AGAIN.search(folded):
        return None
    purpose = _notice_purpose(said)
    if purpose is None:
        return None
    for answer in list(answers)[:3]:
        named: dict[int, set[int]] = {}
        for clause in _answer_clauses(answer):
            if re.search(_NOTIFICATION_NOUN + r"|\bcount\s*down\b|\bcountdown\b", clause) or spoken_clocks(clause):
                # A notification BAXY reports setting, or a moment, is no step.
                continue
            score = _step_named(purpose, clause)
            length = _clause_length(clause) if score else None
            if length is not None:
                named.setdefault(score, set()).add(length)
        if not named:
            continue
        lengths = named[max(named)]
        if len(lengths) != 1:
            return None
        return _step_timer_wording(lengths.pop(), purpose)
    return None


def _step_timer_wording(minutes: int, purpose: _NoticePurpose) -> str:
    hours = minutes // 60 if minutes >= 60 and minutes % 60 == 0 else 0
    if purpose.lead in {"for", "to"}:
        amount = hours or minutes
        article = "an" if str(amount).startswith("8") or amount in {11, 18} else "a"
        return f"set {article} {amount} {'hour' if hours else 'minute'} timer {purpose.lead} {purpose.said}"
    length = (f"{hours} hora" if hours == 1 else f"{hours} horas") if hours else f"{minutes} minutos"
    return f"pon un temporizador de {length} para {purpose.said}"


def length_borrowed_for_another(text: str, restated: str, earlier: Iterable[str]) -> bool:
    """True when the restated timer's length, which the message does not say, was said in the conversation only for
    something other than what the message asks the timer for («and one for the garlic knots» restated «Set a
    25-minute countdown for the garlic knots.» after the pizza's 25 minutes)."""

    said = str(text or "")
    folded = _fold(said)
    if said_durations(said) or spoken_clocks(folded) or _SAME_LENGTH_AGAIN.search(folded):
        return False
    lengths = {minutes for _, minutes in said_durations(restated)}
    purpose = _notice_purpose(said, one_more=True)
    if not lengths or purpose is None:
        return False
    for line in list(earlier)[:6]:
        for clause in _answer_clauses(line):
            if _step_named(purpose, clause) and set(_clause_lengths(clause)) & lengths:
                return False
    return True


# M113 (DEV-F v4d F-w45-t4 «ugh wait, scratch the garlic knots one, I'll just watch them» after «Done, 12-minute timer
# for the garlic knots.» → task.delete): the person takes back the notification BAXY just reported setting, named by what
# it is for or by its noun; that is the latest one set.
_TAKE_BACK = re.compile(
    r"\b(?:cancel|cancell?ing|scratch|kill|drop|forget|remove|delete|nix|ditch|scrap|"
    r"cancela|cancelala|cancelalo|cancelar|quita|quitala|quitalo|quitar|borra|borrala|borralo|borrar|elimina|eliminala|"
    r"eliminalo|anula|anulala|anulalo|olvida|olvidate|saca|sacala|sacalo)\b"
)
_SET_REPORT_FILLER = frozenset({
    "done", "listo", "lista", "minute", "minutes", "minuto", "minutos", "hour", "hours", "hora", "horas", "timer",
    "alarm", "reminder", "temporizador", "alarma", "recordatorio", "the", "for", "your", "para", "con", "una", "uno",
    "set", "puesto", "puesta", "ready", "okay", "countdown", "cuenta", "regresiva", "will", "ring", "sonara", "sonar",
})


def cancelled_notification_just_set(text: str, reply: str | None) -> str | None:
    """The request that cancels the notification BAXY's last reply reports setting («cancel the last timer»), in the
    reply's language; None unless the message takes something back and names that notification, by a word of what it
    is for or by its own noun."""

    answer = _fold(" ".join(str(reply or "").split()))
    folded = _fold(str(text or ""))
    noun = re.search(_NOTIFICATION_NOUN + r"|\bcount\s*down\b|\bcountdown\b", answer)
    if noun is None or answer.endswith("?") or _TAKE_BACK.search(folded) is None:
        return None
    if re.search(r"\b(?:cancel\w*|borr\w+|elimin\w+|quit\w+|deleted|removed)\b", answer):
        return None
    reported = {word for word in re.findall(r"[a-z]{4,}", answer) if word not in _SET_REPORT_FILLER}
    said = set(re.findall(r"[a-z]{4,}", folded))
    named_noun = re.search(_NOTIFICATION_NOUN + r"|\bcount\s*down\b|\bcountdown\b", folded) is not None
    if not (reported & said or named_noun):
        return None
    word = noun.group(0)
    english = re.search(r"\b(?:timer|alarm|reminder|countdown|count\s*down|alert|notification)s?\b", word) is not None
    if english:
        kind = "alarm" if word.startswith("alarm") else "reminder" if word.startswith("reminder") else "timer"
        return f"cancel the last {kind}"
    if word.startswith("alarma"):
        return "cancela la última alarma"
    return "cancela el último recordatorio" if word.startswith("recordatorio") else "cancela el último temporizador"


def accepted_notification_offer(text: str, reply: str | None) -> str | None:
    """The request a yes to BAXY's offer to set or move an alarm, a timer or a reminder makes («set the alarm on
    Saturday at 17:00»), in the offer's language; None unless the message is only a yes and the reply's last question
    offers one notification at one time (and at most one day)."""

    answer = " ".join(str(reply or "").split())
    if not answer.endswith("?") or _OFFER_YES.fullmatch(_fold(str(text or "")).strip(" ¿?¡!.,")) is None:
        return None
    question = re.split(r"(?<=[.!?])\s+", answer)[-1]
    folded = _fold(question)
    noun = re.search(_NOTIFICATION_NOUN, folded)
    clocks = [clock for clock in spoken_clocks(folded) if clock.resolved]
    if _NOTIFICATION_OFFER.search(folded) is None or noun is None or len(clocks) != 1:
        return None
    days = {match.group(0).strip() for match in _ANCHOR_DAY.finditer(_fold(answer))}
    if len(days) > 1:
        return None
    day = next(iter(days), "")
    clock = f"{clocks[0].hour:02d}:{clocks[0].minute:02d}"
    english = re.search(r"\b(?:shall|should|can|may|want|would|the|alarm|reminder|timer)\b", folded) is not None
    word = noun.group(0)
    if english:
        return " ".join(f"set the {word} {day} at {clock}".split())
    article = "el" if word.startswith(("recordatorio", "temporizador", "aviso", "despertador")) else "la"
    if day and not re.match(r"(?:el|este|hoy|manana|pasado)\b", day):
        day = f"el {day}"
    return " ".join(f"pon {article} {word} {day} a las {clock}".split())


def alarm_cancellation_request(clocks: tuple[tuple[int, int], ...], english: bool) -> str | None:
    """The request that cancels each offered alarm by its local (hour, minute), one clause each, as the readers of a
    cancellation read it; None with none, or with more than a plan can hold (eight steps). Each clock says its part
    of the day, so the alarm at 7:00 is never the one at 19:00."""

    if not clocks or len(clocks) > 8:
        return None

    def said(hour: int, minute: int) -> str:
        if hour > 12 or (hour == 0 and not english):
            return f"{hour}:{minute:02d}"
        if english:
            return f"{hour % 12 or 12}:{minute:02d} {'am' if hour < 12 else 'pm'}"
        return f"{hour}:{minute:02d} {'de la mañana' if hour < 12 else 'de la tarde'}"

    if english:
        return " and ".join(f"cancel the alarm at {said(hour, minute)}" for hour, minute in clocks)
    return " y ".join(
        f"cancela la alarma de {'la' if hour == 1 else 'las'} {said(hour, minute)}" for hour, minute in clocks
    )


# M158 (DEV-I v4u/v4v I-w26-t4 «cancela la de las 7 que mañana no trabajo» after BAXY listed eleven alarms and
# reminders, one of them at 7:00 → the decider chose notification.cancel.latest, restated «cancela la última alarma», and
# BAXY cancelled the last one set, which was not the one at 7): a cancellation that names its alarm or reminder by its
# clock is of the one at that clock. Only one alarm, timer or reminder named by its clock, after a verb of taking it
# back: «la de las 7», «la alarma de las 6:30», «el recordatorio de mañana a las 9», «the 7 o'clock one», «my 7am
# alarm», «the alarm at 7». «La reunión de las 7» is no notification; «las de las 7» is D39's plural.
_CLOCK_CANCEL_VERB = re.compile(
    r"\b(?:cancel\w*|quit[aeo]\w*|borr[aeo]\w*|elimin\w*|anul\w*|delete|remove|scratch|kill|nix|ditch|scrap|"
    r"get\s+rid\s+of)\b"
)
_NAMED_CLOCK = rf"(?P<clock>{_CLOCK_HOUR}{_CLOCK_MINUTES}?(?:{_O_CLOCK})?(?:\s*{_CLOCK_PERIOD})?)"
_SPANISH_CLOCK_NAMED_NOTIFICATION = re.compile(
    r"\b(?:la|el|esa|ese|mi)\s+(?:(?P<noun>alarma|recordatorio|temporizador|despertador)\s+)?"
    r"(?:(?:de|para)\s+(?:hoy|manana|pasado\s+manana)\s+)?(?:de|para|a)\s+las?\s+" + _NAMED_CLOCK
    + r"(?=\s|$|[,;:.?!])"
)
_ENGLISH_CLOCK_NAMED_NOTIFICATION = (
    re.compile(r"\b(?:the|my|that)\s+" + _NAMED_CLOCK + r"\s*(?P<noun>one|alarm|reminder|timer|countdown)\b"),
    re.compile(
        r"\b(?:the|my|that)\s+(?P<noun>one|alarm|reminder|timer|countdown)\s+(?:set\s+)?(?:at|for)\s+" + _NAMED_CLOCK
        + r"(?=\s|$|[,;:.?!])"
    ),
)
_ALARM_KIND_NOUN = r"\b(?:alarmas?|alarms?|temporizador(?:es)?|timers?|countdowns?|despertador(?:es)?)\b"
_REMINDER_KIND_NOUN = r"\b(?:recordatorios?|reminders?)\b"


def clock_named_cancellation(text: str, restated: str = "") -> str | None:
    """M158: the request that cancels the alarm or reminder ``text`` names by its clock, said the way the readers of
    ``notification.cancel.at`` read it («cancela la alarma de las 7:00», «cancel the alarm at 7:00»). The clock keeps
    the part of the day said, and only that: a bare 7 stays either 7, as ``notification.cancel.at`` selects it. The kind
    is the one the message names, else the one ``restated`` (the decider's restatement) names; with neither, the
    message itself is the request. None unless one notification is named by one clock after a verb of cancelling it,
    and for a move («cambia la de las 7 a las 8»)."""

    said = " ".join(str(text or "").split())
    folded = _same_length_fold(said)
    verb = _CLOCK_CANCEL_VERB.search(folded)
    if verb is None or notification_change(said) is not None:
        return None
    named = [
        (english, found)
        for english, patterns in ((False, (_SPANISH_CLOCK_NAMED_NOTIFICATION,)), (True, _ENGLISH_CLOCK_NAMED_NOTIFICATION))
        for pattern in patterns
        for found in pattern.finditer(folded)
        if found.start() >= verb.end()
    ]
    if len({found.start("clock") for _, found in named}) != 1:
        return None
    english, found = named[0]
    clocks = spoken_clocks(f"{'at' if english else 'a las'} {found.group('clock')}")
    if len(clocks) != 1:
        return None
    clock = clocks[0]
    kinds: list[str] = []
    for source in (found.group("noun") or "", _fold(str(restated or ""))):
        kinds = [
            kind for kind, pattern in (("alarm", _ALARM_KIND_NOUN), ("reminder", _REMINDER_KIND_NOUN))
            if re.search(pattern, source)
        ]
        if kinds:
            break
    if len(kinds) != 1:
        return said
    hour, minute = clock.hour, clock.minute
    if not clock.resolved or clock.on_the_dial:
        dial = f"{hour}:{minute:02d}"
    elif english:
        dial = f"{hour % 12 or 12}:{minute:02d} {'am' if hour < 12 else 'pm'}"
    elif hour > 12 or hour == 0:
        dial = f"{hour}:{minute:02d}"
    else:
        dial = f"{hour}:{minute:02d} {'de la mañana' if hour < 12 else 'de la tarde'}"
    if english:
        return f"cancel the {kinds[0]} at {dial}"
    noun = "la alarma" if kinds[0] == "alarm" else "el recordatorio"
    return f"cancela {noun} de {'la' if dial.startswith('1:') else 'las'} {dial}"


def names_another_notice(text: str, old: datetime, new: datetime | None = None) -> bool:
    """M173: whether ``text`` names an alarm or reminder by a clock other than its ``old`` one (local) — «y la de las 7
    pásala a las 8», «Cambia la alarma de las 7 a las 8.», «move the 7 o'clock one to 8» right after BAXY set one at
    6:30 move another one, not that one. «la de las 7», «the 7 o'clock one» say which one is meant; «la alarma a las
    8», «the alarm for 8» may say the ``new`` time as well. The clock as said: a bare 7 is either 7; «las 18:30» is
    that hour."""

    def same(clock: SpokenClock, moment: datetime | None) -> bool:
        if moment is None or clock.minute != moment.minute:
            return False
        if clock.resolved and not clock.on_the_dial:
            return clock.hour == moment.hour
        return clock.hour % 12 == moment.hour % 12

    folded = _same_length_fold(" ".join(str(text or "").split()))
    named = [
        (False, re.search(r"\bde\s+las?\s+$", folded[found.start():found.start("clock")]) is not None, found)
        for found in _SPANISH_CLOCK_NAMED_NOTIFICATION.finditer(folded)
    ] + [
        (True, index == 0, found)
        for index, pattern in enumerate(_ENGLISH_CLOCK_NAMED_NOTIFICATION)
        for found in pattern.finditer(folded)
    ]
    for english, which, found in named:
        for clock in spoken_clocks(f"{'at' if english else 'a las'} {found.group('clock')}"):
            if not same(clock, old) and (which or not same(clock, new)):
                return True
    return False


def _clock_article(clock: str) -> str:
    """«la» before one o'clock, «las» before the others («de la una», «a las 9:00»)."""

    return "la" if re.match(r"(?:1|una)\b", _fold(clock)) else "las"


@dataclass(frozen=True)
class NotificationChange:
    """A notification moved to another time: which one (``kind``, the ``old`` clock as said or, without it, the last
    one set) and when it rings now (``new_literal``, a clock or a duration from now)."""

    english: bool
    kind: str
    noun: str
    title: str
    old: str | None
    new_literal: str
    duration: bool
    day: str = ""

    def cancel_request(self) -> str:
        """The cancellation, said the way the readers of a cancellation read it."""

        masculine = self.noun in _MASCULINE_NOUNS
        if self.old is None:
            if self.english:
                return f"cancel the last {self.noun}"
            return f"cancela {'el último' if masculine else 'la última'} {self.noun}"
        if self.english:
            return f"cancel the {self.noun} at {self.old}"
        return f"cancela {'el' if masculine else 'la'} {self.noun} de {_clock_article(self.old)} {self.old}"

    def schedule_arguments(self, part_of_day: str | None = None) -> dict[str, str]:
        """notification.schedule's arguments: the new moment as said (a duration counts from now; a clock without its
        part of the day takes the old one's, or ``part_of_day`` — «am»/«pm», ``change_part_of_day``), the kind, and
        what it is for in the person's words."""

        if self.duration:
            due = f"{'in' if self.english else 'en'} {self.new_literal}"
        else:
            due = f"{'at' if self.english else 'a ' + _clock_article(self.new_literal)} {self.new_literal}"
            old_period = re.search(_CLOCK_PERIOD, _fold(self.old)) if self.old else None
            if re.search(_CLOCK_PERIOD, _fold(self.new_literal)) is None:
                if old_period is not None:
                    due = f"{due} {old_period.group(0)}"
                elif part_of_day in {"am", "pm"}:
                    due = f"{due} {part_of_day if self.english else part_of_day[0] + '. m.'}"
            if self.day:
                due = f"{self.day} {due}"
        return {"dueUtc": due, "kind": self.kind, "title": " ".join(f"{self.noun} {self.title}".split())}

    def clocks_lack_the_part_of_day(self) -> bool:
        """Both clocks are hours of 1 to 12 with no morning or afternoon said («from 3 to 4»)."""

        if self.old is None or self.duration:
            return False
        lead = "at" if self.english else "a las"
        old = spoken_clocks(_fold(f"{lead} {self.old}"))
        new = spoken_clocks(_fold(f"{lead} {self.new_literal}"))
        return len(old) == 1 and len(new) == 1 and not old[0].resolved and not new[0].resolved


def change_part_of_day(change: NotificationChange, said_before: Iterable[str] = ()) -> str | None:
    """M62 (v3e2-final F-s044 «change the reminder for the chef's table group from 3 to 4» → «¿Cuándo, en tus propias
    palabras…?»): the part of the day («am»/«pm») the new clock of a change inherits when neither clock says it —
    the old clock said earlier in this conversation (newest first) with its part of the day or in 24 hours («remind me
    at 3 pm», «Listo, a las 15:00»). None when nothing said it: then it is asked."""

    if change.old is None or change.duration:
        return None
    lead = "at" if change.english else "a las"
    olds = spoken_clocks(_fold(f"{lead} {change.old}"))
    news = spoken_clocks(_fold(f"{lead} {change.new_literal}"))
    if len(olds) != 1 or len(news) != 1 or news[0].resolved:
        return None
    old = olds[0]
    if old.resolved:
        # «de las 15:00 a las 4»: the old clock says it in 24 hours.
        return "am" if old.hour < 12 else "pm"
    for text in said_before:
        for clock in spoken_clocks(_fold(str(text or ""))):
            if clock.resolved and clock.hour % 12 == old.hour % 12 and clock.minute == old.minute:
                return "am" if clock.hour < 12 else "pm"
    return None


def notification_change(text: str) -> NotificationChange | None:
    """«Cambia la alarma despertador de las 8:00 a las 9:00», «change the reminder for the chef's table group from 3
    to 4», «Cambia el temporizador a una hora»: the notification and its new time. None for anything else."""

    said = " ".join(str(text or "").split())
    folded = _same_length_fold(said)
    for english, pattern in enumerate(_NOTIFICATION_CHANGE):
        found = pattern.match(folded)
        if found is None:
            continue
        lead = "at" if english else "a las"
        if found.group("old") and len(spoken_clocks(f"{lead} {found.group('old')}")) != 1:
            return None
        new = found.group("new")
        duration = re.fullmatch(_RELATIVE_DURATION_PATTERN, new) is not None
        if not duration and len(spoken_clocks(f"{lead} {new}")) != 1:
            return None
        title = said[found.start("title"):found.end("title")].strip()
        groups = found.groupdict()
        if not title and groups.get("tail"):
            title = f"para {said[found.start('tail'):found.end('tail')].strip()}"
        day = said[found.start("newday"):found.end("newday")] if groups.get("newday") and not duration else ""
        beside = trailing_day(title) if not day and not duration else None
        if beside is not None:
            # M144 (DEV-H v4p H-w45-t2 «actually ponlo una hora antes de eso» restated «Cambia el recordatorio del
            # dentista para el jueves a las 15:30.» → set today at 15:30, titled «…para el jueves»): the day said before
            # the new time is the new moment's, not what the notification is for.
            title, day = re.sub(r"(?i)(?:^|\s+)(?:para|for|on)$", "", beside[0]).strip(), beside[1]
        return NotificationChange(
            english=bool(english),
            kind="reminder" if found.group("noun") in _REMINDER_NOUNS else "alarm",
            noun=said[found.start("noun"):found.end("noun")].lower(),
            title=title,
            old=said[found.start("old"):found.end("old")] if found.group("old") else None,
            new_literal=said[found.start("new"):found.end("new")],
            duration=duration,
            day=day,
        )
    return None


# M76 (DEV-D v3l): the notification just set, moved by a message that names only its new time. D-w16-t2 «Actually,
# make it 6:30.» after «set an alarm for 6:45 tomorrow morning», D-w04-t4 «Mejor a las 6 en punto, que si no no llego
# al micro» after a reminder for tomorrow at 6:15 and D-w18-t5 «wait no, make it una hora» after «remind me en 45
# minutes to take a break» were each asked «¿A qué hora y qué tipo…?» or «¿Qué … deseas cancelar?»: the time was in the
# message and the notification is the one the last turn set. The message opens with the change (a correction word or a
# verb of making it so), then the time; a reason may follow it after a comma or a «que / because».
_RETIMING_OPENING = (
    r"(?:actually|wait|no|oh|oops|sorry|hmm|instead|mejor(?:\s+dicho)?|espera|perdon|en\s+realidad|o\s+sea|"
    r"pensandolo\s+bien|uy|ah)"
)
_RETIMING_VERB = (
    r"(?:make\s+(?:it|that)|change\s+it\s+to|move\s+it\s+to|set\s+it\s+(?:to|for)|let'?s\s+(?:do|say)|que\s+sea(?:n)?|"
    r"mejor|ponla|ponlo|p[oó]nmela|p[oó]nmelo|c[aá]mbiala\s+a|c[aá]mbialo\s+a|p[aá]sala\s+a|p[aá]salo\s+a)"
)
_RETIMING = re.compile(
    rf"^(?P<opening>(?:{_RETIMING_OPENING}\s*[,.;!]?\s+)*)(?P<verb>{_RETIMING_VERB}\s+)?"
    r"(?:(?:en|in|dentro\s+de|within|a|at|para|for|to)\s+)?(?:las?\s+)?"
    rf"(?P<new>{_RELATIVE_DURATION_PATTERN}|{_CLOCK_HOUR}{_CLOCK_MINUTES}?(?:{_O_CLOCK})?(?:\s*{_CLOCK_PERIOD})?)"
    r"(?:\s*[,;]\s*.*|\s+(?:que|porque|because|since|so|then|pues|asi)\b.*)?[\s.!]*$"
)


@dataclass(frozen=True)
class Retiming:
    """The new time a message gives the notification just set: a duration from now, or a clock (``hour`` 0–23 when
    ``resolved``, otherwise the 1–12 hour whose part of the day the old time decides)."""

    duration: str | None
    hour: int = 0
    minute: int = 0
    resolved: bool = False


def notification_retiming(text: str) -> Retiming | None:
    """«Actually, make it 6:30.», «Mejor a las 6 en punto, que si no no llego al micro», «wait no, make it una hora»:
    the new time of the notification just set. None unless the message opens with the change and names only its time
    (a bare «a las 6» may answer a question; «que sea en una hora» is a change)."""

    folded = _same_length_fold(" ".join(str(text or "").split()))
    found = _RETIMING.match(folded)
    if found is None or not (found.group("opening") or found.group("verb")):
        return None
    new = found.group("new")
    if re.fullmatch(_RELATIVE_DURATION_PATTERN, new):
        return Retiming(duration=new)
    clocks = spoken_clocks(f"a las {new}")
    if len(clocks) != 1:
        return None
    # M144 (DEV-H v4p H-w29-t2 «no espera, mejor a las 7:30» after an alarm set at 19:00 → read as 07:30, already past,
    # so the move was not read and the decider's plan went on): «7:30» says no part of the day either; the old time's
    # is nearer (``retimed_local_moment``), as for «a las 7».
    return Retiming(None, clocks[0].hour, clocks[0].minute, clocks[0].resolved and not clocks[0].on_the_dial)


# M137b (DEV-G v4n G-w22-t5 «actually make it 8» after «set a reminder for Tuesday evening to check again», restated
# «Set a reminder for Tuesday at 8 PM to check again.» → «Could you confirm if you meant 8 PM or 8 AM?»): the part of
# the day a conversation already said («Tuesday evening», «a las 18:00», «por la mañana») is the part of a bare hour
# said after it. «good morning» or «buenas noches» greet; they say no part of the day.
_PART_OF_DAY_SAID = re.compile(
    _DAY_PART
    + r"|(?<!\bgood\s)\b(?P<english_bare>morning|afternoon|evening|night)\b"
    + r"|\b(?:en|por|de)\s+la\s+(?P<spanish_bare>manana|madrugada|tarde|noche)\b"
)


def part_of_day_said(lines: Iterable[str]) -> str | None:
    """«am» or «pm» of the newest of ``lines`` (newest first) that says a part of the day, in words or with a clock
    that says it (a. m., p. m., 24 hours); None when none does, or that line says both."""

    for line in lines:
        folded = _fold(str(line or ""))
        parts = {
            "am" if re.match(r"manana|madrugada|morning", word) else "pm"
            for found in _PART_OF_DAY_SAID.finditer(folded)
            for word in [next(group for group in found.groups() if group)]
        }
        parts |= {"am" if clock.hour < 12 else "pm" for clock in spoken_clocks(folded) if clock.resolved}
        if parts:
            return next(iter(parts)) if len(parts) == 1 else None
    return None


def bare_hour_with_its_part(
    clock: SpokenClock, text: str, earlier: Iterable[str], *, another_day: bool, now: datetime,
) -> bool:
    """M137b: ``clock`` (with its part of the day) is the bare hour a message moving a notification says («actually
    make it 8», «mejor a las 8») in the part of the day the conversation said before (``earlier``, newest first);
    with none said, the part D61b gives another day the person named (1 to 6 the afternoon, 7 to 11 the morning) or,
    on no day named, D61's next time that hour comes after ``now``."""

    retiming = notification_retiming(text)
    if (
        retiming is None
        or retiming.duration is not None
        or retiming.resolved
        or not clock.resolved
        or (retiming.hour % 12, retiming.minute) != (clock.hour % 12, clock.minute)
    ):
        return False
    part = part_of_day_said(earlier)
    base = clock.hour % 12
    if part is not None:
        expected = base + 12 if part == "pm" else base
    elif another_day:
        expected = base + 12 if 1 <= base <= 6 else (12 if base == 0 else base)
    else:
        expected = next(
            (hour for hour in (base, base + 12) if (hour, clock.minute) > (now.hour, now.minute)), base,
        )
    return clock.hour == expected


# M113 (DEV-F v4d F-w55-t2 «no, mejor media hora antes, una hora es mucho» after «mañana a las 10 tengo turno…,
# recordámelo una hora antes»): the change gives a new count before or after the same moment the notification was
# counted from; the notification moves by the difference (one hour before → half an hour before is 30 minutes later).
_OFFSET_RETIMING = re.compile(
    rf"^(?P<opening>(?:{_RETIMING_OPENING}\s*[,.;!]?\s+)*)(?P<verb>{_RETIMING_VERB}\s+)?(?:que\s+sea\s+|make\s+it\s+)?"
    rf"{_OFFSET_AMOUNT}\s+{_OFFSET_UNIT}\s+(?P<sign>antes|before|despues|after|earlier|later)\b"
    r"(?:\s*[,;]\s*.*|\s+(?:que|porque|because|since|so|then|pues|asi)\b.*)?[\s.!]*$"
)
_COUNTED_OFFSET = re.compile(
    rf"\b{_OFFSET_AMOUNT}\s+{_OFFSET_UNIT}\s+(?P<sign>antes|before|despues|after|earlier|later)\b"
)


def offset_retiming(text: str, setting_request: str) -> int | None:
    """The minutes a notification set «<duration> antes/después» of a moment moves when the message gives another
    count from that moment; None unless the message opens with the change and says only the new count, and the request
    that set it said exactly one count."""

    folded = _same_length_fold(" ".join(str(text or "").split()))
    found = _OFFSET_RETIMING.match(folded)
    counted = list(_COUNTED_OFFSET.finditer(_fold(str(setting_request or ""))))
    if found is None or not (found.group("opening") or found.group("verb")) or len(counted) != 1:
        return None
    new, old = _offset_minutes(found), _offset_minutes(counted[0])
    if new is None or old is None:
        return None
    before = {"antes", "before", "earlier"}
    shift = (-new if found.group("sign") in before else new) - (-old if counted[0].group("sign") in before else old)
    return shift or None


# M152 (DEV-G v4s G-w19-t3 «vale, pues recuérdamelo veinte minutos antes de salir» after two answers about the traffic,
# restated «Recuérdame en 20 minutos que tengo que ir al aeropuerto.» → set 20 minutes from then, «Te recordaré a la
# hora programada, 21:20.»; so G-w19-t4 «pues salgo sobre las 6 de la tarde, así que calcula desde ahí» answered no
# question and M148's count from the answered moment never ran): a length counted before or after another moment is no
# delay from now. When neither the message nor the conversation readers place that moment, the restatement that turned the
# same length into a delay from now («en 20 minutos», «in 30 minutes») rings at a moment nobody said.
_COUNTED_FROM_A_MOMENT = frozenset({"antes", "before", "despues", "after"})
_SAID_DELAY = re.compile(rf"\b{_RELATIVE_DUE}\b")
_AFTER_WHAT = re.compile(r"\s+(?:de|del|d|al|que|of|the|my|your|i|you|we|he|she|they)\b")


def advance_restated_as_delay(text: str, restated: str) -> bool:
    """Whether ``text`` counts one length before or after a moment it does not say («veinte minutos antes de salir»,
    «half an hour before I leave») and ``restated`` keeps no such count but says that same length once as a delay from
    now. False when the message says a clock or a delay of its own, or ``said_advance`` reads its moment."""

    said = " ".join(str(text or "").split())
    folded = _same_length_fold(said)
    counts = list(_COUNTED_OFFSET.finditer(folded))
    if len(counts) != 1 or counts[0].group("sign") not in _COUNTED_FROM_A_MOMENT:
        return False
    if counts[0].group("sign") in {"despues", "after"} and not _AFTER_WHAT.match(folded, counts[0].end()):
        # «avísame media hora después» names no moment it counts from: it may well be half an hour from now.
        return False
    minutes = _offset_minutes(counts[0])
    if minutes is None or spoken_clocks(folded) or _SAID_DELAY.search(folded) or said_advance(said) is not None:
        return False
    told = _same_length_fold(" ".join(str(restated or "").split()))
    if _COUNTED_OFFSET.search(told) or spoken_clocks(told):
        return False
    delays = [found.group(0) for found in _SAID_DELAY.finditer(told)]
    return len(delays) == 1 and [length for _, length in said_durations(delays[0])] == [minutes]


# --- An advance before the moment said in the same message ------------------------
# M137 (DEV-G v4n G-s016 «I've got a dentist appointment Thursday at 4 over on Maple St, remind me an hour before so…»
# → set at 16:00; G-s019 «recuérdame una hora antes de la reunión con el banco que es a las 3 de la tarde» → 15:00
# titled «una hora antes de la reunión con el banco que es»; DEV-F v4m F-w55-t1 «mañana a las 10 tengo turno con el
# dentista en Palermo, recordámelo una hora antes así no salgo a las corridas» → 10:00): the clock said is the event's,
# and «<duración> antes» counts back from it. What follows the advance may make it a clause instead of a moment
# («antes de que llegue», «before I leave», «antes de salir», «before leaving»): then it is not one.
_ADVANCE_OF_A_CLAUSE = re.compile(
    r"\s*(?:(?:de\s+|d\s+)?que\b|than\b|(?:de|d)\s+(?:ir|[a-z]+(?:ar|er|ir))(?:me|te|se|lo|la|le|nos|los|las|les)?\b|"
    r"(?:i|you|u|we|they|he|she)\b|"
    r"(?!(?:morning|evening|meeting|wedding|briefing|training|screening|boarding|building|ceiling)\b)[a-z]+ing\b)"
)
# The head of the order to remind or to ring; a clock right after it, with only its day between, is when it rings.
_REMIND_HEAD = (
    r"\b(?:recuerd(?:a|ame|amelo|amela|eme|emelo)|record(?:a|ame|amelo|amela)|avis(?:a|ame|amelo|amela)|"
    r"acord(?:ate|ame|amelo)|remind\s+me|ping\s+me|alert\s+me|notify\s+me|wake\s+me(?:\s+up)?|"
    r"alarmas?|alarms?|recordatorios?|reminders?|avisos?|alertas?|alerts?|timers?|temporizador(?:es)?|despertador)\b"
)
_OWN_CLOCK = re.compile(
    rf"{_REMIND_HEAD}(?:[\s,]+(?:me|for|at|on|by|para|pa|a|al|el|la|las|this|este|esta|next|proximo|hoy|today|"
    rf"tomorrow|tonight|manana|pasado|{_SAID_WEEKDAY}))*[\s,]*$"
)
# Where the clause of the event ends: a pause, or the reason that follows the order («so I'm not late», «así no salgo»).
_EVENT_CLAUSE_END = re.compile(
    r"\s*[,;.!?]|\s+(?:so|asi|para\s+que|porque|because|cause|que\s+si\s+no|pls|plz|please|por\s+favor|porfa)\b"
)
# Words that only lead the event («tengo», «I've got»), say where its moment was («que es», «which is») or are its
# article: not what it is.
_EVENT_LEAD = re.compile(
    r"^(?:(?:y|and|e)\s+)?(?:(?:yo\s+)?tengo|tenemos|hay|me\s+toca|i(?:'ve|’ve|\s+have)?\s+got|i\s+have|"
    r"we(?:'ve|’ve|\s+have)?\s+got|we\s+have|there(?:'s|’s|\s+is))\s+"
)
_EVENT_GLUE = re.compile(
    r"\s+(?:(?:que|which|that)(?:\s+(?:es|son|sera|empieza|comienza|arranca|is|starts|begins|will\s+be))?|"
    r"es|is|de|del|a|at|on|el|la|las|for|para|y|and)$"
)
_EVENT_ARTICLE = re.compile(r"^(?:el|la|los|las|un|una|mi|mis|my|the|a|an|our|nuestro|nuestra|su|your|tu)\s+")
# M143: a clock said right after the advance, as what it counts back from («antes de las 9», «before 9 pm»). Folded.
_ADVANCE_OF_A_CLOCK = re.compile(
    rf"\s+(?:(?:de|d)\s+)?(?:las?\s+)?(?P<clock>{_CLOCK_HOUR}{_CLOCK_MINUTES}?(?:{_O_CLOCK})?(?:\s*{_CLOCK_PERIOD})?)"
    r"(?=\s*$|\s*[,;:.?!]|\s+(?:de\s+)?(?:hoy|manana|today|tomorrow|tonight|esta|este|this|pls|please|por\s+favor|porfa)\b)"
    r"(?!\s+(?:minutos?|minutes?|horas?|hours?|dias?|days?|segundos?|seconds?)\b)"
)
_EVENT_POINTERS = frozenset({"eso", "esto", "ello", "aquello", "that", "this", "it", "then"})
_EVENT_CONNECTORS = frozenset(
    {"so", "asi", "para", "porque", "because", "cause", "pls", "plz", "please", "por", "porfa", "y", "and", "o", "or",
     "to", "just", "ok", "okay", "nomas", "no", "si", "pa", "que", "tambien", "too", "also"}
)


@dataclass(frozen=True)
class SaidAdvance:
    """A notification asked for «<duración> antes» of a moment said in the same message: ``minutes`` before it,
    ``moment`` its day and clock as written, ``clock`` that clock, ``phrase`` the advance as written and ``title``
    what happens then in the person's words ("" when it cannot be told apart from the rest)."""

    minutes: int
    moment: str
    clock: SpokenClock
    phrase: str
    title: str


def _event_title(said: str, folded: str, start: int, end: int, moment: tuple[int, int]) -> str:
    """What happens at the moment, from the span ``start``–``end`` of the message less the moment itself."""

    parts = [(start, end)]
    if start <= moment[0] < end or start < moment[1] <= end:
        parts = [(start, max(start, moment[0])), (min(end, moment[1]), end)]
    text = " ".join(" ".join(said[first:last].split()) for first, last in parts if last > first)
    folded_text = " ".join(" ".join(folded[first:last].split()) for first, last in parts if last > first)
    for pattern in (re.compile(r"^[\s,;:.!?¡¿]+"), _EVENT_LEAD, _EVENT_ARTICLE):
        found = pattern.match(folded_text)
        if found is not None:
            text, folded_text = text[found.end():], folded_text[found.end():]
    if (relative := re.search(r"\s*,\s*(?:que|which|that)\b", folded_text)) is not None:
        # «el vuelo, que sale a las 8»: what follows says when, not what.
        text, folded_text = text[: relative.start()], folded_text[: relative.start()]
    while (found := _EVENT_GLUE.search(folded_text)) is not None:
        text, folded_text = text[: found.start()], folded_text[: found.start()]
    title = text.strip(" ,;:.!?¡¿")
    return title if re.search(r"[^\W\d_]", title) else ""


def said_advance(text: str) -> SaidAdvance | None:
    """M137: «remind me an hour before», «recuérdame una hora antes de la reunión que es a las 3», «recordámelo media
    hora antes» with the event's clock said in the same message. None with no advance or more than one count, an
    advance of a clause («antes de que…»), none or several clocks, or a clock that is the notification's own («remind
    me at 3, an hour before the meeting»). A thing named after the advance («antes de la cena») must be the event the
    clock is said of («tomar la pastilla a las 8, media hora antes de la cena» is no advance from 8)."""

    said = " ".join(str(text or "").split())
    folded = _same_length_fold(said)
    counts = list(_COUNTED_OFFSET.finditer(folded))
    if len(counts) != 1 or counts[0].group("sign") not in {"antes", "before", "earlier"}:
        return None
    advance = counts[0]
    minutes = _offset_minutes(advance)
    if minutes is not None and (direct := _ADVANCE_OF_A_CLOCK.match(folded, advance.end())) is not None:
        # M143 (DEV-H v4o H-s047 «¿me podrías poner una alarma una hora antes de las 9?» → «¿A qué hora…?», where the
        # isolated decider set it at 8): the clock may be what the advance counts back from, said right after it
        # («una hora antes de las 9», «half an hour before 7 pm»); it is the event's, never the notification's own. The
        # moment is that clock read with its lead; the phrase is the advance with its clock, as written.
        lead = "at " if advance.group("sign") != "antes" else "a las "
        written = lead + direct.group("clock")
        clocks = spoken_clocks(_fold(written))
        if len(clocks) == 1 and len(spoken_clocks(folded)) == 0:
            return SaidAdvance(minutes, written, clocks[0], said[advance.start():direct.end()], "")
    clocks = spoken_clocks(folded)
    if minutes is None or len(clocks) != 1 or _ADVANCE_OF_A_CLAUSE.match(folded, advance.end()):
        return None
    clock = clocks[0]
    clock_start = folded.find(clock.literal)
    if clock_start < 0 or advance.start() <= clock_start < advance.end() or re.search(_OWN_CLOCK, folded[:clock_start]):
        return None
    clock_end = clock_start + len(clock.literal)
    head, tail = clock_start, clock_end
    if (before := _DAY_BEFORE_TIME.search(folded[:clock_start])) is not None:
        head = before.start()
    if (after := _DAY_AFTER_TIME.match(folded[clock_end:])) is not None:
        tail = clock_end + after.end()
    moment = said[head:tail].strip(" ,")
    rest = folded[advance.end():]
    lead = re.match(r"\s+(?:de|d|del|al|of)\s+(?=\S)", rest) if advance.group("sign") == "antes" else (
        re.match(r"\s+(?:of\s+)?(?=\S)", rest)
    )
    first_word = re.match(r"[a-z]+", rest[lead.end():]) if lead is not None else None
    if first_word is not None and first_word.group(0) not in _EVENT_POINTERS | _EVENT_CONNECTORS:
        # «una hora antes de la reunión con el banco que es a las 3»: the thing named is the event; «…antes del vuelo,
        # que sale a las 8» says its moment in the clause that follows it.
        start = advance.end() + lead.end()
        stop = _EVENT_CLAUSE_END.search(folded, start)
        while stop is not None and stop.group(0).strip() == "," and re.match(
            r"\s*(?:que|which|that)\b(?!\s+si\s+no\b)", folded[stop.end():],
        ):
            stop = _EVENT_CLAUSE_END.search(folded, stop.end())
        end = stop.start() if stop is not None else len(folded)
        title = _event_title(said, folded, start, end, (head, tail))
        noun = _EVENT_ARTICLE.sub("", _same_length_fold(title)).split()[:1]
        if not (start <= clock_start < end) and not (noun and re.search(rf"\b{re.escape(noun[0])}\b", folded[:advance.start()])):
            return None
    else:
        # «tengo turno mañana a las 10, recordámelo una hora antes»: the event is the clause that says the clock,
        # cut where the order to remind or the advance begins.
        cuts = sorted(
            {0, len(folded), advance.start(), advance.end()}
            | {found.start() for found in re.finditer(r"[,;.!?]", folded)}
            | {edge for found in re.finditer(_REMIND_HEAD, folded) for edge in (found.start(), found.end())}
        )
        start = max(cut for cut in cuts if cut <= head)
        end = min(cut for cut in cuts if cut >= tail)
        title = _event_title(said, folded, start, end, (head, tail))
    return SaidAdvance(minutes, moment, clock, said[advance.start():advance.end()], title)


# --- An advance counted from the moment an answer gives ----------------------------
# M148 (DEV-G v4r G-w19-t4 «pues salgo sobre las 6 de la tarde, así que calcula desde ahí» after «vale, pues
# recuérdamelo veinte minutos antes de salir» → «¿A qué hora tienes pensado salir?» → set at 18:00, the moment of
# leaving, where 17:40 was asked; the isolated decider set 16:40): the request counted «<duración> antes» of something
# whose moment it did not say («antes de salir» is a clause, so ``said_advance`` reads no advance), BAXY asked when, and
# the answer gives that moment. The notification rings that long before it; what it is for is what the advance counted
# from. The question is the last one of BAXY's reply; the answer is a moment, never an order with a clock of its own.
_ASKS_WHEN = re.compile(r"\b(?:a\s+que\s+hora|cuando|what\s+time|when)\b")
_INFINITIVE_LEAD = re.compile(r"[a-z]*(?:ar|er|ir)(?:me|te|se|lo|la|le|nos|los|las|les)?")
_ALARM_HEAD = re.compile(r"\b(?:alarmas?|alarms?|despertador|despiertame|despertame|wake\s+me)\b")
_ANSWERED_DAY = re.compile(rf"\b{_SAID_DAY}\b")


def answered_advance_request(
    text: str, pending: str | None, reply: str | None, *, now: datetime | None = None,
) -> str | None:
    """«recuérdame salir a las 17:40» for «salgo sobre las 6 de la tarde» answering «¿A qué hora tienes pensado
    salir?» about «vale, pues recuérdamelo veinte minutos antes de salir» (``pending``, the person's request BAXY's
    question was about). None unless the reply's last question asks when or offers no clock of its own (M165), the
    request asks to be reminded or woken with
    one count before something named after it and no clock of its own, and the answer says one clock, at most one day,
    and neither another count nor an order of its own («avísame a las 5» is the notification's own clock). A clock
    without its part of the day is the next time it comes (D61) when no day is said; with a day it is left alone."""

    question = " ".join(str(reply or "").split())
    asked = _fold(re.split(r"(?<=[.!?])\s+", question)[-1])
    # M165 (DEV-G v4y G-w19-t4 «pues salgo sobre las 6 de la tarde, así que calcula desde ahí» after BAXY asked «¿Te
    # gustaría que te lo recuerde en ese momento?» instead of when → set at 18:00): a question about the request that
    # offers no clock of its own is answered with the moment of what the count is from, as one asking when; one that
    # offers a clock («¿te aviso a las 6?») is answered with the notification's own.
    if not question.endswith("?") or (_ASKS_WHEN.search(asked) is None and spoken_clocks(asked)):
        return None
    request = " ".join(str(pending or "").split())
    folded_request = _same_length_fold(request)
    counts = list(_COUNTED_OFFSET.finditer(folded_request))
    if (
        len(counts) != 1
        or counts[0].group("sign") not in {"antes", "before"}
        or re.search(_REMIND_HEAD, folded_request) is None
        or spoken_clocks(folded_request)
    ):
        return None
    minutes = _offset_minutes(counts[0])
    spanish = counts[0].group("sign") == "antes"
    lead = re.match(r"\s+(?:de|d|del)\s+" if spanish else r"\s+", folded_request[counts[0].end():])
    if minutes is None or lead is None:
        return None
    start = counts[0].end() + lead.end()
    stop = _EVENT_CLAUSE_END.search(folded_request, start)
    event = request[start: stop.start() if stop is not None else len(request)].strip(" ,;:.!?¡¿")
    first = re.match(r"[a-z]+", _same_length_fold(event))
    if first is None or first.group(0) in _EVENT_POINTERS:
        # «veinte minutos antes de eso»: what it counts from is pointed at, read by ``anchored_offset_request``.
        return None
    said = " ".join(str(text or "").split())
    answer = _fold(said)
    written = said if len(said) == len(answer) else answer
    clocks = spoken_clocks(answer)
    days = [written[found.start(): found.end()] for found in _ANSWERED_DAY.finditer(answer)] or [
        request[found.start(): found.end()] for found in _ANSWERED_DAY.finditer(folded_request)
    ]
    if len(clocks) != 1 or len(days) > 1 or _COUNTED_OFFSET.search(answer) or re.search(_REMIND_HEAD, answer):
        return None
    clock = clocks[0]
    day = days[0] if days else ""
    if clock.resolved:
        moment = clock.hour * 60 + clock.minute
    elif day:
        return None
    else:
        current = (now or datetime.now().astimezone()).astimezone()
        later = [hour * 60 + clock.minute for hour in (clock.hour % 12, clock.hour % 12 + 12)
                 if hour * 60 + clock.minute > current.hour * 60 + current.minute]
        if not later:
            return None
        moment = later[0]
    moment -= minutes
    if moment < 0:
        return None
    when = f"{moment // 60:02d}:{moment % 60:02d}"
    day = f"{day} " if day else ""
    if _ALARM_HEAD.search(folded_request):
        return f"pon una alarma {day}a las {when} para {event}" if spanish else f"set an alarm {day}at {when} before {event}"
    if not spanish:
        return f"remind me {day}at {when} before {event}"
    if _INFINITIVE_LEAD.fullmatch(first.group(0)):
        return f"recuérdame {event} {day}a las {when}"
    return f"recuérdame {day}a las {when} antes de {event}"


_ISO_DATE =re.compile(r"(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})(?:T00:00(?::00)?(?:Z|[+-]00:00)?)?")


def task_due_date(value: str, *, today: date | None = None) -> str | None:
    """M115 (DEV-F v4e2 F-s022 «renovar el passport antes del 15 de noviembre» → the task kept no date; v4d F-w39-t3
    «…hacer esos ejercicios de gases para el jueves» → «el sistema la considera inválida»): the day a task is for, as
    the task store reads it (``YYYY-MM-DD``), from what the person said of it («15 de noviembre», «el jueves»,
    «mañana») or that day already written so; None when it names no one day."""

    raw = " ".join(str(value or "").split())
    today = today or datetime.now().astimezone().date()
    iso = _ISO_DATE.fullmatch(raw)
    if iso is not None:
        try:
            return date(int(iso.group("year")), int(iso.group("month")), int(iso.group("day"))).isoformat()
        except ValueError:
            return None
    folded = _fold(raw)
    said = spoken_date(folded)
    if said is not None:
        meant = said.on_or_after(today)
        return meant.isoformat() if meant is not None else None
    day = spoken_day(folded, today.weekday())
    if day is None or day == (0, 1):
        return None
    return (today + timedelta(days=day[0])).isoformat()


def iso_day_said(value: str, said: str, *, today: date | None = None) -> bool:
    """A day written ``YYYY-MM-DD`` is said when what the person said names that same day (M115)."""

    if _ISO_DATE.fullmatch(" ".join(str(value or "").split())) is None:
        return False
    today = today or datetime.now().astimezone().date()
    written = task_due_date(value, today=today)
    return written is not None and written == task_due_date(said, today=today)


def said_day_of(value: str, said: str, *, today: date | None = None) -> str | None:
    """M118 (D58, DEV-F F-s022 due «2025-11-15» for «renovar el passport antes del 15 de noviembre»): the decider wrote
    the day the person named with a year of its own; the day said, with the same month and day, is that day as the task
    store reads it. None when the value is no written day or what was said names another."""

    iso = _ISO_DATE.fullmatch(" ".join(str(value or "").split()))
    if iso is None:
        return None
    meant = task_due_date(said, today=today)
    return meant if meant is not None and meant[5:] == f"{iso.group('month')}-{iso.group('day')}" else None


_DIAL_ONLY_CLOCK = re.compile(r"(?<![\d:])(?:[1-9]|1[0-2]):[0-5]\d$")


def moved_to_clock(text: str, old: datetime) -> Retiming | None:
    """M115 (DEV-F v4e2 F-w12-t2 «no, cachai que mejor a las 6 y cuarto, el vuelo llega antes…», F-w15-t4 «hmm no, the
    kids won't be home till 7:15, push it there», F-w07-t4 «uy no, espérate, que me toca tanquear antes: córrelo a las 6
    y cuarto»): once the turn is decided as moving the notification just set (cancel it, set it again), its new time is
    the one clock the message says other than the old one, wherever it says it. None with no such clock, more than one,
    or a length of time said beside it."""

    if said_durations(text):
        return None
    clocks = {
        # «till 7:15» says no part of the day (its digits read as 07:15): the dial time nearer the old one is meant.
        (clock.hour, clock.minute, clock.resolved and _DIAL_ONLY_CLOCK.search(clock.literal) is None)
        for clock in spoken_clocks(_fold(str(text or "")))
        if not (
            clock.minute == old.minute
            and (clock.hour == old.hour if clock.resolved else clock.hour % 12 == old.hour % 12)
        )
    }
    if len(clocks) != 1:
        return None
    hour, minute, resolved = clocks.pop()
    return Retiming(None, hour, minute, resolved)


# M148 (DEV-F v4q F-w45-t3 «go with 12, the bag says 10 to 12 but my oven runs cold» after BAXY set «a 25-minute
# countdown for the garlic knots», planned «Change the garlic knots countdown to 12 minutes.» → «¿Qué tipo de alarma o
# recordatorio necesitas cancelar?»): a timer moved to a new length rings that long from now. A length counted from
# another moment («10 minutes later», «media hora antes») moves it by that much and is not its length.
_LENGTH_SHIFT = re.compile(
    r"\s+(?:antes|despues|before|after|earlier|later|mas\s+(?:tarde|temprano)|more|less|menos|de\s+mas|de\s+menos)\b"
)


def moved_to_length(text: str) -> Retiming | None:
    """Once the turn is decided as moving a timer just set, its new length: the one length of time the message says
    (``said_durations``), with no clock and not counted from another moment. None otherwise."""

    said = " ".join(str(text or "").split())
    durations = said_durations(said)
    if len(durations) != 1 or spoken_clocks(_fold(said)):
        return None
    folded = _same_length_fold(said)
    end = folded.find(_same_length_fold(durations[0][0])) + len(durations[0][0])
    if _LENGTH_SHIFT.match(folded, end):
        return None
    return Retiming(duration=durations[0][0])


def retimed_local_moment(retiming: Retiming, old: datetime, now: datetime | None = None) -> datetime | None:
    """The new local moment of a notification set for ``old`` (local, with its zone): the clock on the same day, in
    the part of the day nearer the old time when it said none (6:45 → «6:30» is 6:30, 18:00 → «7» is 19:00). None
    for a duration (it counts from now) or a moment already past."""

    if retiming.duration is not None:
        return None
    hours = (retiming.hour,) if retiming.resolved else (retiming.hour % 12, retiming.hour % 12 + 12)
    candidates = [old.replace(hour=hour, minute=retiming.minute, second=0, microsecond=0) for hour in hours]
    moment = min(candidates, key=lambda candidate: abs((candidate - old).total_seconds()))
    return moment if moment > (now or datetime.now(old.tzinfo)) else None
