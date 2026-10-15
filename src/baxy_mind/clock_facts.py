"""Clock and calendar facts of a verified system.time read: the local clock and date, a place's time,
countdowns, weekdays and dates, and what a reply may state about today.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta, timezone

from .semantic.normalize import alternation, fold
from .semantic.network import (
    calendar_parts_asked, days_until_asked, hours_until_asked, present_calendar_question, relative_calendar_days,
)
from .semantic.temporal import _DAY_WORDS, clock_elsewhere
from .semantic.request import fold as _reading_fold
from .semantic.network import (
    _CALENDAR_MONTHS, _CALENDAR_MONTH_NUMBERS, _WEEKDAY_NAMES, _WEEKDAY_NUMBERS, _WEEKDAY_WORD, _requests_weekday,
    asks_about_a_named_calendar_value,
)


def _parse_core_utc(value: str) -> datetime | None:
    """Parse the Core system.time `utc` stamp. C# round-trip uses 7 fractions."""

    stamp = (value or "").strip()
    if not stamp:
        return None
    if stamp.endswith("Z"):
        stamp = stamp[:-1] + "+00:00"
    match = re.match(
        r"^(?P<head>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?P<frac>\.\d+)?(?P<tz>.*)$",
        stamp,
    )
    if match is None:
        return None
    frac = match.group("frac") or ""
    if len(frac) > 7:
        frac = frac[:7]
    stamp = f"{match.group('head')}{frac}{match.group('tz') or ''}"
    try:
        parsed = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _countdown_facts(local: datetime, target: str, language: str) -> dict:
    """Minutes from the observed local clock to the next occurrence of target."""

    hour, minute = (int(part) for part in target.split(":", 1))
    now_minutes = local.hour * 60 + local.minute
    target_minutes = hour * 60 + minute
    already_passed_today = target_minutes <= now_minutes
    remaining = (target_minutes - now_minutes) % (24 * 60)
    hours, minutes = divmod(remaining, 60)
    if language == "en":
        parts = [f"{hours} h"] if hours else []
        parts += [f"{minutes} min"] if minutes or not parts else []
    else:
        parts = [f"{hours} h"] if hours else []
        parts += [f"{minutes} min"] if minutes or not parts else []
    return {
        "target": target,
        "remaining": " ".join(parts),
        "remaining_hours": hours,
        "remaining_minutes": minutes,
        "already_passed_today": already_passed_today,
    }


def _local_clock_from_observed(observed: dict | None) -> str | None:
    """HH:MM from the real system.time contract (`utc` + offset). Not localTime."""

    local = _local_datetime_from_observed(observed)
    return f"{local.hour:02d}:{local.minute:02d}" if local is not None else None


# Uso real tanda 4d «show me las aplicaciones»: Edge titles its window «<página> - <perfil>: Microsoft​ Edge», with
# a zero-width space inside the browser's name. The narrator wrote «Microsoft Edge (<página> - Personal)» and the
# identity check, which wants every observed title verbatim, refused all three drafts (⚠ retry_exhausted). The
# window shows the page; the browser is its process. Narrator and check read the same visible title.
_BROWSER_TITLE_SUFFIX = re.compile(
    r"\s+[-—–]\s+(?:[^-—–]{1,40}:\s+)?(?:microsoft\s+edge|google\s+chrome|mozilla\s+firefox|brave|opera)\s*$",
    re.IGNORECASE,
)


def _window_title_as_shown(title: object) -> object:
    """A window title without invisible format characters and without the browser's own name after the page."""

    if not isinstance(title, str):
        return title
    visible = "".join(ch for ch in title if unicodedata.category(ch) != "Cf")
    page = _BROWSER_TITLE_SUFFIX.sub("", visible)
    return page if page.strip() else visible


def _local_datetime_from_observed(observed: dict | None) -> datetime | None:
    """Derive clock and calendar from the same captured instant and offset."""

    if not isinstance(observed, dict):
        return None
    utc_raw = observed.get("utc")
    offset_raw = observed.get("localUtcOffsetMinutes")
    if isinstance(utc_raw, str) and offset_raw is not None:
        try:
            offset_minutes = int(offset_raw)
        except (TypeError, ValueError):
            offset_minutes = None
        else:
            parsed = _parse_core_utc(utc_raw)
            if parsed is not None:
                local = parsed.astimezone(timezone(timedelta(minutes=offset_minutes)))
                return local
    return None


def _place_clock_facts(observed: dict | None, user_text: str, language: str) -> dict | None:
    """The time of the place a system.time reading carries, and its arithmetic.

    Uso real tanda 4 «convertir nueve de la mañana huso horario a madrid»: the
    reading gives this PC's instant and offset and the place zone's offset at
    that instant; the place's clock, a said time converted between here and
    there, the day it falls on and the hours apart are computed here. The
    narrator copies them and never computes one.
    """

    if not isinstance(observed, dict) or not isinstance(observed.get("place"), dict):
        return None
    place = observed["place"]
    there = place.get("utcOffsetMinutes")
    here = observed.get("localUtcOffsetMinutes")
    utc = _parse_core_utc(observed["utc"]) if isinstance(observed.get("utc"), str) else None
    if utc is None or not all(isinstance(value, int) and not isinstance(value, bool) for value in (there, here)):
        return None
    english = language == "en"
    there_zone, here_zone = timezone(timedelta(minutes=there)), timezone(timedelta(minutes=here))
    asked = clock_elsewhere(fold(user_text))
    named = str(place.get("name") or "").strip()
    if asked is not None and (place.get("authority") == "time_zone_id" or english):
        # A named zone keeps the person's words for it («la hora del Pacífico»);
        # the service names places in Spanish («Tokio»), so English keeps «Tokyo».
        named = asked.said if place.get("authority") == "time_zone_id" else asked.said.title()
    facts: dict[str, object] = {"place": named}
    country = str(place.get("country") or "").strip()
    if country and _reading_fold(country) != _reading_fold(named):
        facts["country"] = country
    here_word = "here" if english else "aquí"
    if asked is not None and asked.clock is not None:
        source, target = (there_zone, here_zone) if asked.clock_is_there else (here_zone, there_zone)
        day = utc.astimezone(source).date()
        given = datetime(day.year, day.month, day.day, asked.clock.hour, asked.clock.minute, tzinfo=source)
        converted = given.astimezone(target)
        facts["given"] = f"{given.hour:02d}:{given.minute:02d}"
        facts["givenAt"] = named if asked.clock_is_there else here_word
        facts["clock"] = f"{converted.hour:02d}:{converted.minute:02d}"
        facts["clockAt"] = here_word if asked.clock_is_there else named
        shift = (converted.date() - given.date()).days
    else:
        now_there = utc.astimezone(there_zone)
        facts["clock"] = f"{now_there.hour:02d}:{now_there.minute:02d}"
        facts["clockAt"] = named
        shift = (now_there.date() - utc.astimezone(here_zone).date()).days
    if shift:
        facts["day"] = (
            ("the next day" if shift > 0 else "the day before")
            if english
            else ("el día siguiente" if shift > 0 else "el día anterior")
        )
    if asked is not None and asked.difference:
        hours, minutes = divmod(abs(there - here), 60)
        amount = f"{hours} h" + (f" {minutes} min" if minutes else "")
        facts["difference"] = (
            "the same time as here" if there == here
            else f"{amount} {'ahead of' if there > here else 'behind'} here"
            if english
            else "la misma hora que aquí" if there == here
            else f"{amount} {'más' if there > here else 'menos'} que aquí"
        )
    if asked is not None and asked.zone:
        # Tanda 6c «the timezone for britain»: the zone asked is its offset now (and its name), copied, never
        # computed by the narrator.
        hours, minutes = divmod(abs(there), 60)
        facts["zone"] = f"UTC{'+' if there >= 0 else '-'}{hours:02d}:{minutes:02d}" + (
            f" ({place['timeZone']})" if isinstance(place.get("timeZone"), str) and place["timeZone"].strip() else ""
        )
    return facts


def _names_clock_place(text: str, place: str) -> bool:
    """The reply names the place whose time it gives: the whole name, or the
    word that names it («Pacífico» for «la hora del Pacífico», «India» for «la
    India»); the words for a zone or an article name nothing."""

    folded = _reading_fold(text)
    name = _reading_fold(place)
    if re.search(r"\b" + re.escape(name) + r"\b", folded):
        return True
    words = [
        word for word in re.findall(r"[a-z]+", name)
        if len(word) >= 3 and word not in {"hora", "zona", "horaria", "time", "timezone", "zone", "del", "las", "los", "the"}
    ]
    return any(re.search(r"\b" + word + r"\b", folded) for word in words[:1])


def _weekday_name(local: datetime | date, language: str) -> str:
    return _WEEKDAY_NAMES["en" if language == "en" else "es"][local.weekday()]


def _named_weekdays(text: str) -> set[int]:
    """The weekdays a draft names, in either language."""

    return {_WEEKDAY_NUMBERS[found] for found in re.findall(rf"\b{_WEEKDAY_WORD}\b", _reading_fold(text))}


def _states_only_the_weekday(text: str, weekday: int) -> bool:
    """The draft states the observed weekday, in either language, and no other; one it denies is no claim.

    Tanda 6b «¿hoy es lunes?» → «No, hoy no es lunes. Hoy es jueves.»: the weekday of the question, denied, is the
    answer's «no», not a second weekday."""

    folded = _reading_fold(text)
    return {
        _WEEKDAY_NUMBERS[found.group(0)]
        for found in re.finditer(rf"\b{_WEEKDAY_WORD}\b", folded)
        if not _denied_at(folded, found.start())
    } == {weekday}


_CALENDAR_MONTH_PATTERN = "(?:" + "|".join(_CALENDAR_MONTH_NUMBERS) + ")"
_CALENDAR_DATE_PATTERNS = (
    re.compile(r"\b(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})\b"),
    re.compile(r"\b(?P<day>\d{1,2})\s+(?:de\s+)?(?P<month>"
               + _CALENDAR_MONTH_PATTERN + r")(?:\s+(?:de\s+)?(?P<year>\d{4}))?\b"),
    re.compile(r"\b(?P<month>" + _CALENDAR_MONTH_PATTERN
               + r")\s+(?P<day>\d{1,2})(?:,?\s+(?P<year>\d{4}))?\b"),
)


def _preserves_calendar_date(text: str, local: datetime | date) -> bool:
    found = False
    for pattern in _CALENDAR_DATE_PATTERNS:
        for match in pattern.finditer(text.casefold()):
            found = True
            month = match["month"]
            month_number = int(month) if month.isdigit() else _CALENDAR_MONTH_NUMBERS[month]
            if (month_number != local.month or int(match["day"]) != local.day
                    or match["year"] is not None and int(match["year"]) != local.year):
                return False
    return found


def _calendar_facts(local: datetime, user_text: str, language: str) -> dict[str, object]:
    """The part of the observed date the question asks for (semantic.network.calendar_parts_asked).

    Tanda 4c: «¿qué mes sale…?» carried the whole date and every «Este mes es septiembre.» was rejected for
    lacking the day. A month or a year asked is carried alone; the date keeps its weekday when that is asked.
    Tanda 6 «¿sabes qué días fueron el último fin de semana?»: a day counted from today is computed here from the
    observed date (semantic.network.relative_calendar_days) and carried with its weekday, instead of today's."""

    until = days_until_asked(user_text, local.date())
    if until is not None:
        # M37: the days left are counted here; the narrator copies them with today's weekday.
        facts: dict[str, object] = {"weekday": _weekday_name(local, language), "until": until[0], "days_until": until[1]}
        if hours_until_asked(user_text):
            # M85 (DEV-D v3o D-s001): asked in hours, the time left until that day begins is counted here too.
            day = local.date() + timedelta(days=until[1])
            start = datetime(day.year, day.month, day.day, tzinfo=local.tzinfo)
            hours, minutes = divmod(max(0, int((start - local).total_seconds() // 60)) if until[1] else 0, 60)
            facts["hours_until"] = f"{hours} h" + (f" {minutes} min" if minutes else "")
        return facts
    asked = relative_calendar_days(user_text, local.date())
    if asked:
        return {"asked_days": [{"date": day.isoformat(), "weekday": _weekday_name(day, language)} for day in asked]}
    parts = calendar_parts_asked(user_text)
    facts: dict[str, object] = {}
    if "weekday" in parts:
        facts["weekday"] = _weekday_name(local, language)
    if "date" in parts:
        facts["date"] = local.date().isoformat()
        if _requests_weekday(user_text):
            facts["weekday"] = _weekday_name(local, language)
    if "month" in parts:
        names = _CALENDAR_MONTHS[local.month - 1].split()
        facts["month"] = names[-1].capitalize() if language == "en" else names[0]
    if "year" in parts:
        facts["year"] = str(local.year)
    return facts


def _calendar_instruction(user_text: str) -> str:
    """What the narrator states from the calendar facts _calendar_facts carries."""

    if days_until_asked(user_text, date(2000, 1, 3)) is not None and hours_until_asked(user_text):
        return (
            "Say that today is weekday and how much time is left until the day named in until: hours_until, copied; "
            "0 h means it is already that day. Never compute or guess a number."
        )
    if days_until_asked(user_text, date(2000, 1, 3)) is not None:
        return (
            "Say that today is weekday and how many days are left until the day named in until: days_until, "
            "copied; 0 means it is already that day. Never compute or guess a number."
        )
    if relative_calendar_days(user_text, date(2000, 1, 3)):
        return (
            "State each day in asked_days with its weekday: that is the day the person asked about, not today. "
            "Copy the dates and weekdays, each day of the month with its month's name; never compute or guess one."
        )
    parts = calendar_parts_asked(user_text)
    # Tanda 6: a yes/no question about a named value is answered yes or no, then with the observed value.
    yes_no = (
        " The person asked whether it is the one they named: say yes or no first, then only the observed one;"
        " do not repeat theirs."
        if asks_about_a_named_calendar_value(user_text)
        else ""
    )
    if parts == ("weekday",):
        return f"State only the weekday from weekday; no date is needed. Do not guess.{yes_no}"
    if "date" not in parts:
        named = " and ".join(parts)
        return f"State only the {named} from {named}; say no day. Do not guess.{yes_no}"
    if _requests_weekday(user_text):
        return f"State the weekday from weekday and the local calendar date from date. Do not guess either.{yes_no}"
    return f"State the local calendar date from date. Do not guess a date.{yes_no}"


# M89: «26 de 2026», «Saturday 26, 2026», «the 26th of 2026»: a day of the month and a year with no month. Folded.
_DATE_WITHOUT_MONTH = re.compile(
    r"(?<![\d/.-])\d{1,2}\s+de(?:l)?\s+(?:19|20)\d{2}\b|"
    r"\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday),?\s+(?:the\s+)?\d{1,2}(?:st|nd|rd|th)?,?\s+"
    r"(?:of\s+)?(?:19|20)\d{2}\b|\bthe\s+\d{1,2}(?:st|nd|rd|th)\s+of\s+(?:19|20)\d{2}\b"
)


def _misses_calendar_facts(text: str, facts: dict) -> bool:
    """The draft states each calendar fact carried (date, weekday, month, year, asked days) and no other.

    Without a carried date or weekday, any day stated is a guess; the month named is the carried one and no other («may»
    counts only as the capitalised month, not the English modal); the year likewise. Tanda 6: the days asked
    relative to today are named each by its day of the month and weekday, and no other date is written."""

    if _DATE_WITHOUT_MONTH.search(_reading_fold(text)) is not None:
        # M89 (DEV-D v3r D-s003 «El finde pasado cayó el sábado 26 de 2026 y el domingo 27 de 2026.»): a day of the
        # month joined to a year with no month between is a broken date, whatever day it is.
        return True
    hours_until = str(facts.get("hours_until") or "").split()
    if hours_until and hours_until[0] != "0" and re.search(rf"(?<!\d){hours_until[0]}(?!\d)", text) is None:
        # M85 (DEV-D v3o D-s001): asked in hours, the hours counted are the answer («Quedan dos días» is not).
        return True
    asked = facts.get("asked_days")
    if isinstance(asked, list) and asked:
        try:
            days = [date.fromisoformat(str(item["date"])) for item in asked]
        except (KeyError, TypeError, ValueError):
            return True
        # Every asked day by its day of the month and its weekday; every date written is one of them.
        return (
            any(re.search(rf"(?<!\d){day.day}(?!\d)", text) is None for day in days)
            or _named_weekdays(text) != {day.weekday() for day in days}
            or any(
                (
                    int(match["month"]) if match["month"].isdigit() else _CALENDAR_MONTH_NUMBERS[match["month"]],
                    int(match["day"]),
                ) not in {(day.month, day.day) for day in days}
                or match["year"] is not None and int(match["year"]) not in {day.year for day in days}
                for pattern in _CALENDAR_DATE_PATTERNS
                for match in pattern.finditer(text.casefold())
            )
        )
    carried_date = facts.get("date")
    if isinstance(carried_date, str) and carried_date:
        try:
            local = datetime.fromisoformat(carried_date)
        except ValueError:
            return True
        if not _preserves_calendar_date(text, local):
            return True
        if facts.get("weekday") and not _states_only_the_weekday(text, local.weekday()):
            return True
    elif isinstance(weekday := facts.get("weekday"), str) and weekday:
        # Tanda 6b: the weekday asked alone is the answer; a date said with it is judged against the clock by
        # _calendar_contradiction, which every visible reply passes.
        if not _states_only_the_weekday(text, _WEEKDAY_NUMBERS.get(_reading_fold(weekday), -1)):
            return True
    elif any(pattern.search(text.casefold()) for pattern in _CALENDAR_DATE_PATTERNS):
        return True
    month = facts.get("month")
    if isinstance(month, str) and month:
        folded = _reading_fold(text)
        named = {
            number
            for word, number in _CALENDAR_MONTH_NUMBERS.items()
            if re.search(rf"\b{word}\b", folded) and (word != "may" or re.search(r"\bMay\b", text))
        }
        if named != {_CALENDAR_MONTH_NUMBERS.get(month.casefold())}:
            return True
    year = facts.get("year")
    if isinstance(year, str) and year:
        if set(re.findall(r"(?<!\d)\d{4}(?!\d)", text)) != {year}:
            return True
    return False


# --- No reply contradicts the clock (tanda 6, «nunca inventa») -------------------------------------------------
# t5 «¿hoy es lunes?» → «Hoy es lunes 24 de septiembre de 2026.» (a Thursday), t47 «el mes en el que estamos» → a
# search snippet «Hoy es el primero de marzo, creo.», t40 «¿sabes el año de ahora?» → «el año actual es 2024». Every
# weekday, day of the month, month and year a reply states about today is checked against this PC's calendar, on
# every route: a sentence that says what today is («hoy es…», «today is…», «estamos en…», «el año actual es…»), and,
# when the person asked which day it is (or a day counted from today), every date the reply states. A date denied
# («hoy no es lunes»), another day's date said as such, history («hoy se cumplen 50 años del 11 de septiembre de
# 1973») and another place's calendar are not claims about today.
_DATE_TOKEN = (
    rf"(?P<weekday>{_WEEKDAY_WORD})|(?P<month>{_CALENDAR_MONTH_PATTERN})|(?P<year>(?:19|20)\d\d)|"
    r"(?P<day>(?:3[01]|[12]\d|0?[1-9])(?:st|nd|rd|th|o|º)?)(?![\d:.,/]\d)|"
    r"(?P<word_day>" + alternation(tuple(_DAY_WORDS))[3:-1].replace(r"\ ", r"\s+") + r")"
    rf"(?=\s+(?:de\s+|of\s+)?{_CALENDAR_MONTH_PATTERN}\b)"
)
_DATE_WORD = re.sub(r"\(\?P<\w+>", "(?:", _DATE_TOKEN)
_DATE_RUN = re.compile(rf"\b(?:{_DATE_WORD})\b(?:(?:\s*,\s*|\s+)(?:(?:de|del|of|the|el)\s+)*(?:{_DATE_WORD})\b)*")
# What today is, said. A lone day number is a claim only after «hoy es», «estamos a» or «el día de hoy es» («hoy es
# 24»), never after «hoy,» or «ahora es» («ahora es 5 veces mejor»).
_TODAY_IS = re.compile(
    r"\b(?:"
    # «ahora» and «now» only with their verb: «reproduciendo ahora September» names a song, not a month.
    r"(?P<now>hoy|today)\s*,?\s*(?P<said>(?:es|seria|estamos(?:\s+(?:a|en))?|is|it['’]s|"
    r"we['’]re(?:\s+(?:in|on))?|we\s+are(?:\s+(?:in|on))?)\s+)?|"
    r"(?:ahora|now|actualmente|currently)\s*,?\s*(?:es|estamos(?:\s+(?:a|en))?|is|it['’]s|"
    r"we['’]re(?:\s+(?:in|on))?|we\s+are(?:\s+(?:in|on))?)\s+|"
    r"(?P<noun>(?:(?:el|la|the)\s+)?(?:(?:ano|mes|dia|fecha)\s+(?:actual|de\s+hoy|de\s+ahora|en\s+curso)|"
    r"(?:current|present)\s+(?:year|month|day|date)|today['’]s\s+date|este\s+(?:ano|mes)|this\s+(?:year|month))"
    r"\s+(?:es|is|sera))\s+|"
    r"(?:(?P<at>estamos\s+a)|estamos\s+en|we['’]re\s+(?:in|on)|we\s+are\s+(?:in|on))\s+"
    r")(?:(?:el|la|the|a|de|del|on)\s+)*(?=\S)"
)
# A sentence about another time: its dates are not today's.
_OTHER_TIME = re.compile(
    r"\b(?:fue|fueron|era|eran|sera|seran|was|were|will\s+be|manana|tomorrow|ayer|yesterday|anteayer|hace|ago|"
    r"dentro\s+de|proxim[oa]s?|pasad[oa]s?|ultim[oa]s?|que\s+viene|next|last|since|desde|hasta|until|cumplen?|"
    r"aniversario|anniversary)\b"
)
_DATE_HEDGE = re.compile(
    r"\b(?:creo|supongo|quizas?|tal\s+vez|probablemente|posiblemente|aproximadamente|me\s+parece|i\s+think|"
    r"i\s+guess|i\s+believe|maybe|probably|perhaps|possibly)\b"
)


# «hoy no es lunes», «it isn't Monday», «ni martes»: a value denied is no claim about today.
_DENIED_BEFORE = re.compile(
    r"\b(?:no|not|isn['’]t|ni|nor)\s+"
    r"(?:(?:es|estamos|era|sera|fue|is|was|it['’]s|today|hoy|en|a|el|la|un|una|the)\s+){0,3}$"
)


def _denied_at(folded: str, start: int) -> bool:
    return _DENIED_BEFORE.search(folded[:start]) is not None


def _date_run_fits(run: str, days: tuple[date, ...], *, bare_day: bool) -> bool | None:
    """Whether one of ``days`` has every weekday, day of the month, month and year the run states; None when the
    run states none. A day number alone counts only where the sentence says it is today's (``bare_day``)."""

    weekdays: set[int] = set()
    numbers: set[int] = set()
    months: set[int] = set()
    years: set[int] = set()
    for token in re.finditer(_DATE_TOKEN, run):
        if token["weekday"]:
            weekdays.add(_WEEKDAY_NUMBERS[token["weekday"]])
        elif token["month"]:
            months.add(_CALENDAR_MONTH_NUMBERS[token["month"]])
        elif token["year"]:
            years.add(int(token["year"]))
        elif token["day"]:
            numbers.add(int(re.match(r"\d+", token["day"]).group(0)))
        elif token["word_day"]:
            numbers.add(_DAY_WORDS[" ".join(token["word_day"].split())])
    if "may" in run.split() and not (numbers or years):
        months.discard(5)  # the English modal, not the month
    if not (weekdays or months or years) and not (numbers and bare_day):
        return None
    return any(
        weekdays <= {day.weekday()} and months <= {day.month} and years <= {day.year} and numbers <= {day.day}
        for day in days
    )


def _calendar_contradiction(text: str, user_text: str, local: datetime | date) -> str:
    """Why a reply states a date about today that this PC's calendar denies («false_date») or states it as a
    guess («hedged_date»), or ""; ``local`` is the observed (or this PC's) local moment."""

    if clock_elsewhere(_reading_fold(user_text)) is not None:
        return ""  # another place's calendar may be another day
    today = local.date() if isinstance(local, datetime) else local
    asked = relative_calendar_days(user_text, today)
    whole = bool(asked) or present_calendar_question(user_text)
    for sentence in re.split(r"(?<=[.!?;])\s+|\n+", _reading_fold(text)):
        verdicts = [
            _date_run_fits(run.group(0), (today,), bare_day=bool(anchor["said"] or anchor["noun"] or anchor["at"]))
            for anchor in _TODAY_IS.finditer(sentence)
            if not _denied_at(sentence, anchor.start()) and (run := _DATE_RUN.match(sentence, anchor.end())) is not None
        ]
        if whole and (asked or _OTHER_TIME.search(sentence) is None):
            # A day counted from today is that day; today's own date only where the sentence names today.
            days = (*asked, today) if not asked or re.search(r"\b(?:hoy|today)\b", sentence) else asked
            verdicts += [
                _date_run_fits(run.group(0), days, bare_day=False)
                for run in _DATE_RUN.finditer(sentence)
                if not _denied_at(sentence, run.start())
            ]
        if False in verdicts:
            return "false_date"
        if True in verdicts and _DATE_HEDGE.search(sentence) is not None:
            return "hedged_date"
    return ""


def _local_now() -> datetime:
    """This PC's local moment, for the replies whose turn read no clock (a conversation, a search report)."""

    return datetime.now().astimezone()


# «2 pm», «3p.m.», «las 8 de la tarde», «a las 7 de la mañana»: an hour with its part of the day, no minutes.
_MERIDIEM_HOUR = re.compile(
    r"(?<![\d:.,])(\d{1,2})\s*(?:([ap])\.?\s*m\b\.?|(?:de|en|por)\s+la\s+(manana|madrugada|tarde|noche))"
)
