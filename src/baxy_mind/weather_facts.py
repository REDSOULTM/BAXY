"""The weather read: what of it the question asks, its projection and instruction for the writer, the checks
of the numbers and days a reply says, and its last-resort finals.
"""

from __future__ import annotations

import json
import re
from datetime import date
from functools import lru_cache
from pathlib import Path

from .semantic.web import (
    weather_asks_sun_time, asks_own_place, weather_asks_air, weather_asked_measures, weather_asked_clock,
    weather_asks_coming_days, weather_asks_week, weather_sun_events_asked,
)
from .effect_intent import _weather_location
from .semantic.request import fold as _reading_fold
from .semantic.web import _weather_asks_rain, _weather_asks_tomorrow, weather_asks_future, weather_asks_later_in_the_day, weather_asks_later_today, weather_asks_rain_now, weather_asks_today, weather_asks_whether_it_rains, weather_asked_date, weather_asked_span, weather_asks_later_time, weather_asks_past, weather_names_date
from .clock_facts import _CALENDAR_MONTH_PATTERN, _local_now


def _decimal_said(value: object, english: bool) -> str:
    text = f"{value:g}" if isinstance(value, float) else str(value)
    return text if english else text.replace(".", ",")


def _weather_number_forms(value: object) -> set[str]:
    """The ways a person writes an observed weather number: 18.8, 18,8, 19, 18."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return set()
    forms = {str(value), str(value).replace(".", ",")}
    if float(value).is_integer():
        forms.add(str(int(value)))
    else:
        forms.add(str(round(value)))
        forms.add(str(int(value)))
    return forms


def _states_weather_number(text: str, value: object) -> bool:
    """The reply states this observed number on its own, not inside another («8» in «18»)."""

    return any(
        re.search(r"(?<![\d.,])" + re.escape(form) + r"(?![\d]|[.,]\d)", text) is not None
        for form in _weather_number_forms(value)
    )


# A rain amount as a reply writes it (folded): «0 mm», «2,5 milimetros», «1 pulgada».
_RAIN_AMOUNT = re.compile(
    r"(?<![\w.,])(\d+(?:[.,]\d+)?)\s*(mm|milimetros?|millimet(?:er|re)s?|pulgadas?|inch(?:es)?|"
    r"cm|centimetros?|centimet(?:er|re)s?|litros?|lit(?:er|re)s?)\b"
)


# What makes a number a weather measurement in a reply: its unit right after it.
_WEATHER_MEASURE_UNIT = re.compile(
    r"\s*(?:°|º|%|grados?\b|degrees?\b|por\s*ciento\b|percent\b|km|mm|mil[ií]metros?\b|millimet|"
    r"pulgadas?\b|inch|cm\b|mph\b|m/s\b)",
    re.IGNORECASE,
)


def _weather_clock_forms(value: object) -> set[str]:
    """The numbers of an observed sun clock «07:05» as a reply writes them: 07, 7, 05, 5."""

    if not isinstance(value, str) or re.fullmatch(r"\d\d:\d\d", value) is None:
        return set()
    hour, minute = value.split(":")
    return {hour, str(int(hour)), minute, str(int(minute))}


_WEATHER_MEASURE_FIELDS = {
    "humidity": ("humidityPercent", "the humidity", "la humedad"),
    "wind": ("windKmh", "the wind", "el viento"),
    "apparent": ("apparentC", "the feels-like temperature", "la sensación térmica"),
    "dew_point": ("dewPointC", "the dew point", "el punto de rocío"),
}


def _weather_focus(user_text: str, english: bool) -> str:
    """The one thing the weather question asks of the read (owner 2026-09-24, «conciso… que te responda de
    una»); the composer instruction and the retry hint say the same focus."""

    measures = weather_asked_measures(user_text) - {"temperature"}
    if asks_own_place(user_text):
        return (
            "The person asked where they are: say seen.location with seen.region and seen.country as "
            "the approximate place of this PC, and nothing about the weather."
            if english
            else "La persona preguntó dónde está: di seen.location con seen.region y seen.country como "
            "el lugar aproximado de este PC, y nada del clima."
        )
    if weather_asks_past(user_text) and not weather_asks_air(user_text):
        # M79 (DEV-D v3m s003): the read starts today (_weather_asked_reach); a day already gone is not in it.
        return (
            "The person asked about a day already gone, and the forecast is read only from today on "
            "(seen.outOfReach): say plainly that you only read the weather from today on, not past days, with no "
            "figure and nothing about how it was."
            if english
            else "La persona preguntó por un día que ya pasó, y el pronóstico sólo se lee desde hoy "
            "(seen.outOfReach): di simplemente que sólo lees el tiempo desde hoy, no el de días pasados, sin ninguna "
            "cifra ni nada de cómo estuvo."
        )
    if weather_asks_air(user_text) and (weather_asks_later_time(user_text) or weather_asks_past(user_text)):
        # M78 (DEV-D v3l s048 «Estara alto the air quality the next week?» → today's index alone): the air is read
        # as it is now; a later time is beyond the read (_weather_asked_reach).
        return (
            "The person asked about the air at another time than now, and the air quality is read only as it is now "
            "(seen.outOfReach): say plainly that the air quality is only read as it is now, not for that time, "
            "with no figure."
            if english
            else "La persona preguntó por el aire en otro momento que ahora, y la calidad del aire sólo se lee como "
            "está ahora (seen.outOfReach): di simplemente que la calidad del aire sólo se lee como está ahora, no "
            "para ese momento, sin ninguna cifra."
        )
    if weather_asks_air(user_text):
        return (
            "The person asked about the air: give the index, its category and PM2.5; if "
            "seen.airQuality is null, say the air quality could not be read."
            if english
            else "La persona preguntó por el aire: da el índice, su categoría y el PM2.5; si "
            "seen.airQuality es null, di que no se pudo leer la calidad del aire."
        )
    if weather_asks_sun_time(user_text):
        # Tanda 6b: only the asked event of the asked day is sent (_project_weather_read).
        return (
            "The person asked when the sun rises or sets: give the sun time sent, with its event (sunrise is "
            "when the sun rises, sunset when it sets) and its day (tomorrow's for tomorrow or a later day). "
            # M99 (DEV-D v3x D-s054): today's sun time already behind the clock.
            "A sun time with sunrisePassed or sunsetPassed true already happened today: say it in the past (the sun set "
            "at …), never as still to come. "
            # M105 (DEV-D v4a D-s054/D-s080): and one with it false is still to come.
            "With it false, it has not happened yet today: say it as still to come (the sun will set at …), never "
            "in the past."
            if english
            else "La persona preguntó a qué hora sale o se pone el sol: da la hora del sol enviada, con su evento "
            "(sunrise es cuando sale, sunset cuando se pone) y su día (la de mañana para mañana o un día posterior). "
            "Una hora del sol con sunrisePassed o sunsetPassed en true ya pasó hoy: dila en pasado (el sol se puso a "
            "las …), nunca como algo por venir. Con false aún no llega hoy: dila como algo por venir (el sol se "
            "pondrá a las …), nunca en pasado."
        )
    if "uv" in measures:
        # Uso real tanda 6 «Dime el UV index»: the index now and the day's peak are both read.
        if _weather_asks_tomorrow(user_text):
            return (
                "The person asked about the UV index tomorrow: give tomorrow.uvIndexMax, tomorrow's peak UV index."
                if english
                else "La persona preguntó por el índice UV de mañana: da tomorrow.uvIndexMax, el máximo UV de mañana."
            )
        return (
            "The person asked about the UV index: give seen.uvIndex (now) and today.uvIndexMax (today's peak); "
            "if they are null, say the UV index could not be read."
            if english
            else "La persona preguntó por el índice UV: da seen.uvIndex (ahora) y today.uvIndexMax (el máximo de "
            "hoy); si son null, di que no se pudo leer el índice UV."
        )
    if weather_names_date(user_text):
        # M78 (DEV-D v3l p20-t1/p20-t2/p21-t1/p25-t2): a date named is that day of the read (seen.askedDay) or a day
        # the read does not cover (seen.outOfReach); today's weather is never given for it (_weather_asked_reach).
        return (
            "The person asked about a date. If seen.askedDay is sent, give that day's sky, maximum, minimum and rain "
            "probability, naming its date. If seen.outOfReach is sent, the forecast does not cover that date: say "
            "plainly that the forecast only goes up to seen.outOfReach.readUntil and the date asked is beyond it, "
            "naming both dates, with no temperature or other figure. If neither is sent, the date is today: give the "
            "weather now."
            if english
            else "La persona preguntó por una fecha. Si se envía seen.askedDay, da el cielo, la máxima, la mínima y "
            "la probabilidad de lluvia de ese día, nombrando su fecha. Si se envía seen.outOfReach, el pronóstico no "
            "cubre esa fecha: di simplemente que el pronóstico llega sólo hasta seen.outOfReach.readUntil y que la "
            "fecha preguntada queda fuera, nombrando las dos fechas, sin temperatura ni ninguna otra cifra. Si no se "
            "envía ninguno, la fecha es hoy: da el tiempo de ahora."
        )
    coming = weather_asks_coming_days(user_text)
    clock = weather_asked_clock(user_text)
    if clock is not None:
        # M93 (DEV-D v3u D-s014 «¿qué previsión de tiempo hay para las cuatro?» → «Actualmente hace 16.8 °C…»): the read
        # has no forecast by the hour; the hour asked is answered by saying so, with the day's own figures.
        return (
            f"The person asked about the weather at {clock}, and the read has no forecast by the hour: say in a few "
            f"words that you do not have the forecast for {clock} (only for the whole day), then give that day's sky, "
            "maximum, minimum and rain probability (tomorrow's for tomorrow, today's otherwise)."
            if english
            else f"La persona preguntó por el tiempo a {clock}, y la lectura no trae pronóstico por hora: di en pocas "
            f"palabras que no tienes el pronóstico para {clock} (sólo el del día entero) y da el cielo, la máxima, la "
            "mínima y la probabilidad de lluvia de ese día (los de mañana para mañana, los de hoy si no)."
        )
    if _weather_names_span(user_text) and not weather_names_date(user_text):
        # Uso real v3 tanda 1 «Madrid this weekend» → «tomorrow»: the span is resolved to its days
        # (_weather_asked_reach) and only those are sent. Revisión adversarial: after the clock asked, whose own
        # focus says the read has no forecast by the hour.
        return (
            "The person asked about the weekend or the day after tomorrow. If seen.askedDays is sent, give each "
            "day's sky, maximum, minimum and rain probability, naming it today or tomorrow when it is, its weekday "
            "otherwise. If seen.askedDay is sent, give "
            "that day's, naming its weekday. If seen.outOfReach is sent, the forecast does not reach that day: say "
            "plainly that the forecast only goes up to seen.outOfReach.readUntil, with no figure. If none is sent, "
            "the day is today: give the weather now."
            if english
            else "La persona preguntó por el fin de semana o por pasado mañana. Si se envía seen.askedDays, da el "
            "cielo, la máxima, la mínima y la probabilidad de lluvia de cada día, nombrándolo hoy o mañana si lo es "
            "y por su día de la semana si no. Si "
            "se envía seen.askedDay, da los de ese día, nombrando su día de la semana. Si se envía seen.outOfReach, "
            "el pronóstico no llega a ese día: di simplemente que llega sólo hasta seen.outOfReach.readUntil, sin "
            "ninguna cifra. Si no se envía ninguno, el día es hoy: da el tiempo de ahora."
        )
    if _weather_asks_rain(user_text):
        # M63 (v3f-final F-w01-t6): a yes-or-no rain question is answered yes or no first, as the chance says.
        plain = weather_asks_whether_it_rains(user_text)
        return (
            "The person asked about rain (or rain gear, or an amount of rain): answer with the rain "
            "probability of the day asked, tomorrow's for tomorrow"
            + (", the matching day of seen.laterDays for a later day or the likeliest days for the week." if coming
               else " or a later day.")
            + (" Say first whether it will rain (yes, it may, or no rain is expected) as that probability says; "
               "a sky (condition) that says otherwise goes with «though», never as a second fact." if plain else "")
            if english
            else "La persona preguntó por la lluvia (o por algo para la lluvia, o una cantidad): contesta "
            "con la probabilidad de lluvia del día preguntado, la de mañana para mañana"
            + (", la del día de seen.laterDays para un día posterior o los días más probables para la semana."
               if coming else " o un día posterior.")
            + (" Di primero si va a llover (sí, puede que llueva o no se espera lluvia) según esa probabilidad; "
               "un cielo (condition) que diga otra cosa va con «aunque», nunca como otro hecho." if plain else "")
        )
    if weather_asks_week(user_text):
        # Uso real tanda 6 «cuál es el pronóstico del tiempo para la semana» got today and tomorrow only. Tanda 6b:
        # the model's own range was false («entre 12,5 y 21 °C» with a minimum of 12); seen.week is computed.
        return (
            "The person asked about the coming days: sum them up with seen.week, computed from today, tomorrow "
            "and seen.laterDays: from week.minC to week.maxC, and the highest rain chance "
            "(week.rainProbabilityPercentMax) with its days (week.rainiestWeekdays); no list of every day."
            if english
            else "La persona preguntó por los próximos días: resúmelos con seen.week, calculado desde today, "
            "tomorrow y seen.laterDays: de week.minC a week.maxC, y la mayor probabilidad de lluvia "
            "(week.rainProbabilityPercentMax) con sus días (week.rainiestWeekdays); sin enumerar cada día."
        )
    if coming:
        return (
            "The person asked about a day by its weekday or a later day: give the sky, maximum, minimum and "
            "rain probability of that day, from today, tomorrow or the day of seen.laterDays with that "
            "weekday or date."
            if english
            else "La persona preguntó por un día por su nombre o un día posterior: da el cielo, la máxima, la "
            "mínima y la probabilidad de lluvia de ese día, de today, tomorrow o el día de seen.laterDays con "
            "ese weekday o esa fecha."
        )
    if _weather_asks_tomorrow(user_text):
        return (
            "The person asked about tomorrow or a later day: give tomorrow's sky, maximum and minimum and "
            "rain probability."
            if english
            else "La persona preguntó por mañana o un día posterior: da el cielo, la máxima, la mínima y la "
            "probabilidad de lluvia de mañana."
        )
    if weather_asks_later_in_the_day(user_text) and not measures:
        # M62 (v3e2-final F-p07-t1 «…later today» → only the temperature at 00:45): the rest of today is today's read.
        return (
            "The person asked about later today: give today's maximum and minimum (today.maxC, today.minC) and its "
            "rain probability (today.rainProbabilityPercent) in seen.location, naming it; the temperature now alone "
            "does not answer it."
            if english
            else "La persona preguntó por más tarde hoy: da la máxima y la mínima de hoy (today.maxC, today.minC) y "
            "su probabilidad de lluvia (today.rainProbabilityPercent) en seen.location, nombrándolo; la temperatura "
            "de ahora sola no lo contesta."
        )
    if weather_asks_future(user_text) and not measures:
        # M58 (v3d-final F-s066 «¿hará bueno para San Juan?»): what is coming is tomorrow's read.
        return (
            "The person asked what the weather will be: say the weather now in seen.location, naming it, and "
            "tomorrow's sky, maximum and rain probability."
            if english
            else "La persona preguntó qué tiempo hará: di el tiempo de ahora en seen.location, nombrándolo, y el "
            "cielo, la máxima y la probabilidad de lluvia de mañana."
        )
    if measures:
        asked = [
            _WEATHER_MEASURE_FIELDS[name][1 if english else 2] + f" ({_WEATHER_MEASURE_FIELDS[name][0]})"
            for name in ("humidity", "wind", "apparent", "dew_point")
            if name in measures
        ]
        # M79 (DEV-D v3m p25-t3 «How humid do you expect it to be?» → «…la humedad es del 22% hoy y del 22% mañana»):
        # these measures are read only as they are now; no other day's value is read (_weather_measure_for_another_day).
        return (
            "The person asked about " + " and ".join(asked) + ": give that value, which is read only as it is now; "
            "never give it for tomorrow or another day."
            if english
            else "La persona preguntó por " + " y ".join(asked) + ": da ese valor, que sólo se lee como está ahora; "
            "nunca lo des para mañana ni para otro día."
        )
    if "temperature" in weather_asked_measures(user_text):
        return (
            "The person asked about the temperature: give the current temperature of seen.location, naming it."
            if english
            else "La persona preguntó por la temperatura: da la temperatura actual de seen.location, nombrándolo."
        )
    return (
        "Say the current temperature and sky of seen.location, naming it; if the person asked what to "
        "wear or carry, answer that from the temperature."
        if english
        else "Di la temperatura actual y el cielo de seen.location, nombrándolo; si la persona preguntó "
        "qué ponerse o llevar, contéstalo desde la temperatura."
    )


_OWN_PLACE_FIELDS = ("location", "region", "country", "locatedBy")


def _weather_span_days(user_text: str, today: date) -> tuple[date, ...]:
    """The days of a relative span the weather question asks (``weather_asked_span``), when they are what it asks:
    a measure the days of the read do not carry (the UV index, the humidity, the wind) keeps the whole read.

    Revisión adversarial de la tanda 1 («UV index this weekend» → temperatures): the span's days carry the sky, the
    temperatures and the rain chance, so only a question about those is answered from them."""

    if weather_asked_measures(user_text) - {"temperature"}:
        return ()
    return weather_asked_span(user_text, today)


def _weather_names_span(user_text: str) -> bool:
    """The weather question names a relative span of days (the weekend, the day after tomorrow)."""

    return bool(_weather_span_days(user_text, _local_now().date()))


def _weather_days(seen: dict) -> list[dict]:
    """Today, tomorrow and the days after it that the read carries, in order."""

    return [day for day in (seen.get("today"), seen.get("tomorrow"), *(seen.get("laterDays") or [])) if isinstance(day, dict)]


_WEATHER_MONTHS = (
    ("enero", "January"), ("febrero", "February"), ("marzo", "March"), ("abril", "April"), ("mayo", "May"),
    ("junio", "June"), ("julio", "July"), ("agosto", "August"), ("septiembre", "September"), ("octubre", "October"),
    ("noviembre", "November"), ("diciembre", "December"),
)


def _weather_date_said(value: object, english: bool) -> str:
    """An ISO date of the read as a reply says it («1 de marzo», «March 1»); empty when it is not one."""

    try:
        day = date.fromisoformat(str(value))
    except ValueError:
        return ""
    spanish, english_name = _WEATHER_MONTHS[day.month - 1]
    return f"{english_name} {day.day}" if english else f"{day.day} de {spanish}"


_WEATHER_WEEKDAYS = (
    ("lunes", "Monday"), ("martes", "Tuesday"), ("miércoles", "Wednesday"), ("jueves", "Thursday"),
    ("viernes", "Friday"), ("sábado", "Saturday"), ("domingo", "Sunday"),
)


def _weather_weekday_said(day: dict, english: bool) -> str:
    """The weekday of a day of the read, from its ISO date; empty when it has none."""

    try:
        when = date.fromisoformat(str(day.get("date")))
    except ValueError:
        return ""
    spanish, english_name = _WEATHER_WEEKDAYS[when.weekday()]
    return english_name if english else spanish


def _calendar_day_of(value: object) -> tuple[int, int] | None:
    """(month, day) of an ISO date of the read; None when it is not one."""

    try:
        day = date.fromisoformat(str(value))
    except ValueError:
        return None
    return day.month, day.day


_SAID_MONTH = {
    name: index + 1 for index, names in enumerate(_WEATHER_MONTHS) for name in (names[0], names[1].lower(), names[1][:3].lower())
}
_SAID_MONTH_PATTERN = "|".join(sorted(_SAID_MONTH, key=len, reverse=True))
_SAID_CALENDAR_DAY = re.compile(
    rf"\b(?P<day>\d{{1,2}})(?:st|nd|rd|th)?\s+(?:de\s+|of\s+)?(?P<month>{_SAID_MONTH_PATTERN})\b|"
    rf"\b(?P<month_first>{_SAID_MONTH_PATTERN})\.?\s+(?:the\s+)?(?P<day_after>\d{{1,2}})(?:st|nd|rd|th)?\b"
)


def _calendar_days_said(folded_text: str) -> list[tuple[int, int]]:
    """Every (month, day) a folded reply names («5 de octubre», «October 5th», «the 5th of March»)."""

    days = []
    for found in _SAID_CALENDAR_DAY.finditer(folded_text):
        month = _SAID_MONTH[found.group("month") or found.group("month_first")]
        day = int(found.group("day") or found.group("day_after"))
        if 1 <= day <= 31:
            days.append((month, day))
    return days


def _weather_asked_reach(seen: dict, user_text: str) -> dict | None:
    """What of the read answers a question about a named date or, for the air, a later time; None otherwise.

    M78 (DEV-D v3l p20-t1 «weather info for the 1st of March», p20-t2 «…for March 2nd» → «…on March 2 is currently
    28.7 °C», p25-t2 «…on the 5th of March», s048 «…the air quality the next week?»): the reply gave today's read for a
    day it does not cover. A date the read carries is that day (``askedDay``); a date it does not carry, or the air at
    a later time (read only as it is now), is ``outOfReach``: the limit is said, with no figure of another day."""

    days = _weather_days(seen)
    try:
        today = date.fromisoformat(str(days[0].get("date"))) if days else None
    except ValueError:
        today = None
    if today is None:
        return None
    if weather_asks_air(user_text):
        later = weather_asks_later_time(user_text) or weather_asks_past(user_text)
        return {"outOfReach": {"read": "airQuality", "readFor": "now"}} if later else None
    if weather_asks_past(user_text):
        # M79 (DEV-D v3m s003 «¿En qué cayó el fin de semana pasado?» → today's read told as last weekend's): a day
        # already gone is before the first day of the read.
        return {"outOfReach": {"read": "forecast", "askedTime": "past", "readFrom": days[0].get("date")}}
    asked = weather_asked_date(user_text, today)
    span = _weather_span_days(user_text, today) if asked is None else ()
    if len(span) > 1:
        # Uso real v3 tanda 1 «Madrid this weekend» → «tomorrow»: a span of days the read carries is those days
        # (``askedDays``); one beyond the read is its limit, as a date is.
        carried = [day for day in days if day.get("date") in {when.isoformat() for when in span}]
        if len(carried) == len(span):
            return {"askedDays": carried}
        asked = next(when for when in span if when.isoformat() not in {day.get("date") for day in carried})
    elif span:
        asked = span[0]
    if asked is None or asked == today:
        return None
    for day in days:
        if day.get("date") == asked.isoformat():
            return {"askedDay": day}
    return {
        "outOfReach": {
            "read": "forecast",
            "askedDate": asked.isoformat(),
            "readFrom": days[0].get("date"),
            "readUntil": days[-1].get("date"),
        }
    }


def _weather_day_values(days: list[dict], key: str) -> list[float]:
    return [day[key] for day in days if isinstance(day.get(key), (int, float)) and not isinstance(day.get(key), bool)]


def _weather_week(seen: dict) -> dict:
    """Tanda 6b: the coming days summed up here (lowest minimum, highest maximum, the highest rain chance and its
    days); the narrator copies the figures instead of computing a range it got wrong."""

    days = _weather_days(seen)
    lows, highs, rains = (_weather_day_values(days, key) for key in ("minC", "maxC", "rainProbabilityPercent"))
    week: dict = {}
    if lows:
        week["minC"] = min(lows)
    if highs:
        week["maxC"] = max(highs)
    if rains:
        week["rainProbabilityPercentMax"] = max(rains)
        if max(rains) > 0:
            week["rainiestWeekdays"] = [
                day["weekday"] for day in days
                if day.get("rainProbabilityPercent") == max(rains) and isinstance(day.get("weekday"), str)
            ]
    return week


# «entre 12 y 21 °C», «de 12 a 21», «del 2% al 6%», «from 16 to 22.3°C», «between 12 and 21», «12–21 °C».
_WEATHER_RANGE = re.compile(
    r"(?:\b(?:entre|between|de|del|from)\s+(?P<low>-?\d+(?:[.,]\d+)?)\s*(?:°\s*c?|º\s*c?|grados|degrees|%|"
    r"por\s*ciento|percent)?\s*(?:y|a|al|and|to|hasta)\s+(?:el\s+|un\s+)?(?P<high>-?\d+(?:[.,]\d+)?)(?![\d:])"
    # «del 24 al 30 de septiembre», «de 7 a 9 de la mañana» are days and hours, not a range read.
    rf"(?!\s*(?:de\s+|of\s+)?(?:{_CALENDAR_MONTH_PATTERN}|de\s+la|am|pm|h|hrs?|horas?|hours?)\b)|"
    r"(?<![\w.,-])(?P<dash_low>\d+(?:[.,]\d+)?)\s*[–-]\s*(?P<dash_high>\d+(?:[.,]\d+)?)\s*(?:°|º|grados|degrees|%))",
    re.IGNORECASE,
)


def _false_week_range(text: str, seen: dict) -> bool:
    """A range said about the coming days that is none of theirs: of all temperatures, of the maximums, of the
    minimums or of the rain chances (tanda 6b «entre 12,5 °C y 21 °C» with a lowest minimum of 12)."""

    days = _weather_days(seen)
    pairs = []
    for low_key, high_key in (("minC", "maxC"), ("maxC", "maxC"), ("minC", "minC")):
        lows, highs = _weather_day_values(days, low_key), _weather_day_values(days, high_key)
        if lows and highs:
            pairs.append((min(lows), max(highs)))
    rains = _weather_day_values(days, "rainProbabilityPercent")
    if rains:
        pairs.append((min(rains), max(rains)))
    for found in _WEATHER_RANGE.finditer(text):
        said = sorted(
            (found["low"] or found["dash_low"], found["high"] or found["dash_high"]),
            key=lambda number: float(number.replace(",", ".")),
        )
        if not any(
            said[0] in _weather_number_forms(low) and said[1] in _weather_number_forms(high) for low, high in pairs
        ):
            return True
    return False


def _clock_minutes(value: object) -> int | None:
    found = re.search(r"(?:^|T)(\d{1,2}):(\d{2})", str(value or ""))
    return int(found.group(1)) * 60 + int(found.group(2)) if found else None


def _sun_time_passed(seen: dict, block: dict, event: str) -> bool | None:
    """M99: whether today's ``event`` (sunrise/sunset) is earlier than the reading's local clock (``observedAtLocal``,
    the place's own time), on the same day; ``None`` when the read cannot tell (no clock, no time, another day).

    M105 (DEV-D v4a D-s054/D-s080): the time still ahead is marked too (``False``), so the narrator and the check
    know that «se puso» at 04:45 for a 19:49 sunset is wrong, not only that «se pondrá» at 22:45 is."""

    observed = str(seen.get("observedAtLocal") or "")
    day = str(block.get("date") or "")
    now, at = _clock_minutes(observed.split("T")[-1] if "T" in observed else ""), _clock_minutes(block.get(event))
    if now is None or at is None or (day and not observed.startswith(day)):
        return None
    return at < now


# Ronda 19 (r17 t2-c13 «… en Valencia?» told Venezuela's weather with no country): the read says when towns of the
# name and of comparable size exist in other countries (namesakesElsewhere); the place fields go with every narrow
# projection so the narrator can name the country read.
_WEATHER_PLACE_FIELDS = ("location", "region", "country", "namesakesElsewhere")


def _project_weather_read(seen: dict, user_text: str) -> dict:
    """What of the weather read the narrator gets: the part the question asks (the checks keep the whole read).

    Uso real tanda 6b «let me know my current location»: given the whole read, all three drafts added the
    temperature, humidity and wind and died as extra_claim; the place alone leaves no weather to recite. Tanda 6:
    the days after tomorrow answer only a question about them; unasked, they would only lengthen every compose."""

    if asks_own_place(user_text):
        return {key: seen[key] for key in _OWN_PLACE_FIELDS if key in seen}
    if weather_asks_sun_time(user_text):
        # Tanda 6b «a la salida del sol mañana… ¿qué hora será?» → «Mañana se pone el sol a las 19:45.»: given both
        # days and both events, the narrator told the other one. The asked event of the asked day is sent.
        day = "tomorrow" if _weather_asks_tomorrow(user_text) else "today"
        events = weather_sun_events_asked(user_text) or frozenset(("sunrise", "sunset"))
        block = seen.get(day) if isinstance(seen.get(day), dict) else {}
        projected = {key: seen[key] for key in _WEATHER_PLACE_FIELDS if key in seen}
        projected[day] = {key: block[key] for key in ("date", "weekday", *sorted(events)) if key in block}
        if day == "today":
            # M99 (DEV-D v3x D-s054 «…comenzará a oscurecerse» at 22:50 → «Se pondrá el sol … a las 19:48 de hoy»): a sun
            # time of today already behind the reading's own clock is said as past.
            # M105 (DEV-D v4a D-s054 at 04:45 → «El sol se puso a las 19:49 hoy»): one still ahead is marked False.
            passed = {event: _sun_time_passed(seen, block, event) for event in sorted(events)}
            projected[day].update({f"{event}Passed": value for event, value in passed.items() if value is not None})
        return projected
    reach = _weather_asked_reach(seen, user_text)
    if reach is not None:
        # M78: only the day asked, or the limit of the read, is sent; today's figures cannot answer another day.
        return {**{key: seen[key] for key in _WEATHER_PLACE_FIELDS if key in seen}, **reach}
    projected = dict(seen)
    # Ronda 22: where the read's time went (place, forecast) is for the trace, never a fact of the weather.
    projected.pop("elapsedMs", None)
    if not weather_asks_coming_days(user_text):
        projected.pop("laterDays", None)
    if weather_asks_week(user_text):
        projected["week"] = _weather_week(seen)
    return projected


def _weather_answer_instruction(user_text: str, language: str) -> str:
    """What a weather reply says: the one thing the question asks of the read.

    Owner 2026-09-24 («conciso… que te responda de una»): the old instruction
    always asked for the temperature and the sky and then added the asked
    thing, so «¿Cuál es la tasa de humedad de hoy?» got three facts and «my
    current location» got the weather too. Only the asked focus is sent now;
    the other readings stay in seen and are not mentioned.
    """

    english = language == "en"
    if asks_own_place(user_text) or weather_asks_sun_time(user_text):
        # Tanda 6b: only the place, or only the asked sun time, is sent (_project_weather_read); no other field of
        # the weather is described.
        return _weather_focus(user_text, english) + (
            " Answer only that, in one short sentence, without naming where it was read."
            if english
            else " Contesta sólo eso, en una oración corta, sin nombrar de dónde se leyó."
        )
    fields = (
        "seen is the weather of seen.location (seen.country) now: temperatureC, apparentC (feels like), "
        "condition (sky), windKmh, humidityPercent, dewPointC (dew point), uvIndex (UV index now), "
        "today.maxC/minC, today.rainProbabilityPercent and today.uvIndexMax (peak UV), tomorrow.maxC/minC, "
        "tomorrow.rainProbabilityPercent, tomorrow.uvIndexMax and tomorrow.condition; today/tomorrow "
        "sunrise and sunset are local sun times; seen.airQuality is the air now (usAqi with its category, "
        "pm25 and pm10 in µg/m³). "
        if english
        else "seen es el clima de seen.location (seen.country) ahora: temperatureC, apparentC (sensación "
        "térmica), condition (cielo), windKmh, humidityPercent, dewPointC (punto de rocío), uvIndex (índice "
        "UV ahora), today.maxC/minC, today.rainProbabilityPercent y today.uvIndexMax (máximo UV), "
        "tomorrow.maxC/minC, tomorrow.rainProbabilityPercent, tomorrow.uvIndexMax y tomorrow.condition; "
        "sunrise y sunset de today/tomorrow son las horas locales del sol; "
        "seen.airQuality es el aire ahora (usAqi con su category, pm25 y pm10 en µg/m³). "
    )
    # Uso real tanda 6: the days after tomorrow are read too (seen.laterDays); they are sent only when the
    # question asks them (``_compose_situation_payload``), so the reach said is the reach sent.
    coverage = (
        # M78: a date named has its own reach in the focus (seen.askedDay or seen.outOfReach).
        ""
        if weather_names_date(user_text) or weather_asks_past(user_text) or _weather_names_span(user_text)
        or (weather_asks_air(user_text) and weather_asks_later_time(user_text))
        else (
            "seen.laterDays are the days after tomorrow (date, weekday, condition, maxC, minC, "
            "rainProbabilityPercent); for a day after the last of them, say the forecast does not reach it. "
            if english
            else "seen.laterDays son los días después de mañana (date, weekday, condition, maxC, minC, "
            "rainProbabilityPercent); para un día después del último, di que el pronóstico no llega hasta ahí. "
        )
        if weather_asks_coming_days(user_text)
        else (
            "The read covers today and tomorrow only: for a later day, say so. "
            if english
            else "La lectura cubre sólo hoy y mañana: para un día posterior, dilo. "
        )
    )
    closing = (
        " Answer only that, in one short sentence (two at most), with the observed numbers and their units "
        "(°C, km/h, %); no other readings. " + coverage
        + "Say it directly, without naming where it was read. Nothing was opened or changed."
        if english
        else " Contesta sólo eso, en una oración corta (dos como máximo), con los números observados y sus "
        "unidades (°C, km/h, %); sin otras lecturas. " + coverage
        + "Dilo directamente, sin nombrar de dónde se leyó. No se abrió ni se cambió nada."
    )
    if coverage == "":
        # M79: a date, a past day or the air at another time is sent as that day or the reach of the read
        # (_project_weather_read), without the fields of now that ``fields`` describes.
        fields = ""
    return fields + _weather_focus(user_text, english) + closing


# M54 (review of the official-window run v3b-final, F-s066 «¿hará bueno para San Juan?» → «Mañana será más frío, con
# 29.3 °C y llovizna» next to 29.3 °C now): a comparison between days is a fact of both days' figures. Folded.
_WEATHER_COMPARISONS = (
    ("colder", re.compile(
        r"\bmas\s+(?:frio|fria|fresco|fresca|fresquito)\b|\bmenos\s+(?:calor|caluros[oa]|calid[oa]|templad[oa])\b|"
        r"\brefrescar?a\b|\b(?:bajar?an?|descender?an?)\s+(?:las?\s+)?temperaturas?\b|\bcolder\b|\bcooler\b|"
        r"\bless\s+(?:hot|warm)\b|\btemperatures?\s+(?:will\s+)?(?:drop|fall)\b"
    )),
    ("warmer", re.compile(
        r"\bmas\s+(?:calor|caluros[oa]|calid[oa]|templad[oa])\b|\bmenos\s+(?:frio|fria|fresco|fresca)\b|"
        r"\b(?:subir?an?|aumentar?an?)\s+(?:las?\s+)?temperaturas?\b|\bwarmer\b|\bhotter\b|\bless\s+(?:cold|cool)\b|"
        r"\btemperatures?\s+(?:will\s+)?rise\b"
    )),
    ("wetter", re.compile(
        r"\bmas\s+(?:lluvia|lluvios[oa]|probabilidad\s+de\s+lluvia)\b|\bllovera\s+mas\b|\bmore\s+rain\b|\bwetter\b|"
        r"\brainier\b|\b(?:higher|greater)\s+chance\s+of\s+rain\b"
    )),
    ("drier", re.compile(
        r"\bmenos\s+(?:lluvia|lluvios[oa]|probabilidad\s+de\s+lluvia)\b|\bllovera\s+menos\b|\bless\s+rain\b|\bdrier\b|"
        r"\bdryer\b|\b(?:lower|smaller)\s+chance\s+of\s+rain\b"
    )),
)


def _weather_unsupported_comparison(text: str, seen: dict) -> bool:
    """A sentence compares a day with today (colder, warmer, more or less rain) and the figures of the read do not
    show it. Colder or warmer needs both the maximum and the minimum to move that way, one of them by a degree or more
    (29,3 → 29,3 now, 30,5 → 29,3 at the top but 25,8 → 26,2 at the bottom is not «más frío»); more or less rain needs
    the rain chances to differ that way. A day before today is never read, so «que ayer» is never shown."""

    today = seen.get("today") if isinstance(seen.get("today"), dict) else None
    days: list[tuple[str, dict]] = []
    if isinstance(seen.get("tomorrow"), dict):
        # «por la mañana» is a time of day and «pasado mañana» a later day, not tomorrow.
        days.append(("(?<!la )(?<!pasado )manana|tomorrow", seen["tomorrow"]))
    for block in (seen.get("tomorrow"), *(seen.get("laterDays") or [])):
        weekday = _reading_fold(str(block.get("weekday") or "")) if isinstance(block, dict) else ""
        if weekday:
            days.append((re.escape(weekday), block))

    def figure(block: dict | None, key: str) -> float | None:
        value = block.get(key) if isinstance(block, dict) else None
        return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None

    for sentence in re.split(r"(?<=[.!?;])\s+", _reading_fold(text)):
        said = [kind for kind, pattern in _WEATHER_COMPARISONS if pattern.search(sentence)]
        if not said:
            continue
        if re.search(r"\b(?:ayer|yesterday)\b", sentence):
            return True
        day = next((block for words, block in days if re.search(rf"\b(?:{words})\b", sentence)), None)
        if day is None:
            # Only a day the read carries is compared with today; a sentence naming none compares nothing it can show.
            continue
        for kind in said:
            if kind in {"colder", "warmer"}:
                changes = [
                    (figure(day, key) - figure(today, key))
                    for key in ("maxC", "minC")
                    if figure(day, key) is not None and figure(today, key) is not None
                ]
                sign = -1 if kind == "colder" else 1
                if len(changes) != 2 or any(sign * change < 0 for change in changes) or max(
                    sign * change for change in changes
                ) < 1:
                    return True
            else:
                later, now = figure(day, "rainProbabilityPercent"), figure(today, "rainProbabilityPercent")
                if later is None or now is None or (later <= now if kind == "wetter" else later >= now):
                    return True
    return False


# M60: the rain now a reply says (folded text): False for «no está lloviendo», «no llueve», «it isn't raining», True
# for «está lloviendo», «llueve», «it's raining», None when it says neither. The reply's wording, not the request.
_RAIN_NOW_DENIED = re.compile(
    r"\b(?:no\s+(?:esta|estan)\s+lloviendo|no\s+llueve|no\s+hay\s+lluvia|sin\s+lluvia|"
    r"(?:is\s+not|isn'?t|it'?s\s+not|not)\s+raining|no\s+rain)\b"
)
_RAIN_NOW_STATED = re.compile(r"\b(?:(?:esta|estan)\s+lloviendo|llueve|(?:is|it'?s)\s+raining)\b")
_RAINY_CONDITION = re.compile(
    r"\b(?:lluvi\w*|llovizn\w*|chubasc\w*|tormenta\w*|aguacer\w*|rain\w*|drizzl\w*|shower\w*|thunderstorm\w*)\b"
)


def _rain_now_said(folded_text: str) -> bool | None:
    if _RAIN_NOW_DENIED.search(folded_text) is not None:
        return False
    if _RAIN_NOW_STATED.search(folded_text) is not None:
        return True
    return None


def _raining_now(seen: dict) -> bool:
    """Rain read now: precipitation measured, or a rainy sky named by the read."""

    rain_mm = seen.get("precipitationMm")
    return (isinstance(rain_mm, (int, float)) and rain_mm > 0) or _RAINY_CONDITION.search(
        _reading_fold(str(seen.get("condition") or ""))
    ) is not None


# M63 (v3f-final F-w01-t6 «¿Va a llover en Ñuñoa?» → «…mañana: llovizna, de 7,9 a 23 °C, 0 % de lluvia.»): the
# forecast named drizzle for a day it gave a 0 % rain chance (the day's worst sky and its likeliest rain are two
# readings), and the reply said both as facts without saying whether it would rain. Below LOW the rain is not
# expected, from HIGH it is likely; a day's sky against its own chance is said with a concession, never beside it.
_RAIN_CHANCE_LOW, _RAIN_CHANCE_HIGH = 20, 50
_DRY_CONDITION = re.compile(r"\b(?:despejad\w*|solead\w*|clear|sunny)\b")
_CONCESSION = re.compile(r"\b(?:aunque|pero|sin\s+embargo|a\s+pesar|although|though|but|however|even\s+if)\b")
_RAIN_DENIED = re.compile(
    r"\bno\s+(?:(?:se\s+)?(?:espera|esperan|preve|preven|pronostica|anuncia|va\s+a|habra|hay|parece)\s+)?(?:que\s+)?"
    r"(?:lluvi\w*|llov\w*|llueve|llueva)\b|\bno\s+(?:hay|habra|se\s+esperan?)\s+(?:\w+\s+){1,3}lluvi\w*|"
    r"\bsin\s+lluvia\b|\bsec[oa]\b|"
    r"\b(?:no\s+rain|won'?t\s+rain|will\s+not\s+rain|not\s+(?:expected|likely|going)\s+to\s+rain|"
    r"rain\s+is\s+(?:not\s+expected|unlikely)|unlikely\s+to\s+rain|dry)\b"
)
_RAIN_AFFIRMED = re.compile(
    r"\bsi\b(?=\s*[,.:;!])|\b(?:va\s+a\s+llover|llovera|lloviznara|llueve|llueva|podria\s+llover|habra\s+lluvia|"
    r"se\s+espera\s+lluvia|yes|will\s+rain|(?:may|might|could)\s+rain|rain\s+is\s+(?:likely|possible|expected)|"
    r"likely\s+to\s+rain)\b"
)


def _rain_verdict_said(folded_text: str) -> bool | None:
    """Whether the reply says it will rain (True), it will not (False), or neither (None)."""

    if _RAIN_DENIED.search(folded_text) is not None:
        return False
    if _RAIN_AFFIRMED.search(folded_text) is not None:
        return True
    return None


def _weather_sky_contradiction(folded_text: str, seen: dict) -> bool:
    """A forecast day's rainy sky said with its low rain chance (or a clear sky with a high one) as two facts."""

    if _CONCESSION.search(folded_text) is not None:
        return False
    now_sky = _reading_fold(str(seen.get("condition") or ""))
    for day in (seen.get("tomorrow"), *(seen.get("laterDays") or [])):
        if not isinstance(day, dict) or not isinstance(chance := day.get("rainProbabilityPercent"), (int, float)):
            continue
        sky = _reading_fold(str(day.get("condition") or ""))
        if _sky_contradicts_chance(sky, chance) and sky != now_sky and sky in folded_text and _states_weather_number(folded_text, chance):
            return True
    return False


def _sky_contradicts_chance(sky: str, chance: float) -> bool:
    folded = _reading_fold(sky)
    return (_RAINY_CONDITION.search(folded) is not None and chance < _RAIN_CHANCE_LOW) or (
        _DRY_CONDITION.search(folded) is not None and chance >= _RAIN_CHANCE_HIGH
    )


@lru_cache(maxsize=1)
def _weather_words() -> dict:
    return json.loads((Path(__file__).resolve().parent / "data" / "weather_words.v1.json").read_text(encoding="utf-8"))


def _sky_said(sky: str, english: bool) -> str:
    """Uso real tanda 1 (t1-c06 «In Madrid, tomorrow: mayormente despejado…»): the read writes its sky in Spanish; an
    English final says it in English (data/weather_words.v1.json)."""

    return _weather_words()["skyEn"].get(sky.strip().casefold(), sky) if english else sky


def _weekday_said(weekday: str, english: bool) -> str:
    return _weather_words()["weekdaysEn"].get(weekday.strip().casefold(), weekday) if english else weekday


def _forecast_day_said(day: dict, english: bool) -> str:
    """A forecast day's sky, range and rain chance for the last resort; a sky its own chance contradicts (M63,
    «llovizna» at 0 %) goes after the chance with a concession instead of beside it as a second fact."""

    sky, low, high, chance = (day.get(key) for key in ("condition", "minC", "maxC", "rainProbabilityPercent"))
    if not isinstance(sky, str) or not all(isinstance(value, (int, float)) for value in (low, high, chance)):
        return ""
    low, high, rain = (_decimal_said(value, english) for value in (low, high, chance))
    figures = f"{low} to {high} °C, {rain}% chance of rain" if english else f"de {low} a {high} °C, {rain} % de lluvia"
    contradicts = _sky_contradicts_chance(sky, chance)
    sky = _sky_said(sky, english)
    if contradicts:
        return f"{figures}, though the forecast shows {sky}" if english else f"{figures}, aunque el pronóstico marca {sky}"
    return f"{sky}, {figures}"


def _weather_rain_final(location: str, days: list[tuple[str, str, dict]], english: bool) -> str:
    """The last resort for rain asked (M63): whether it will rain, from the chance of each day asked (today,
    tomorrow), with those chances; a day whose sky says otherwise is told with «aunque». ``days`` are (Spanish
    label, English label, read)."""

    read = [(es, en, day) for es, en, day in days if isinstance(day, dict) and isinstance(
        day.get("rainProbabilityPercent"), (int, float))]
    if not read:
        return ""
    top = max(day["rainProbabilityPercent"] for _, _, day in read)
    level = 2 if top >= _RAIN_CHANCE_HIGH else 1 if top >= _RAIN_CHANCE_LOW else 0
    verdict = (
        ("no rain is expected", "rain is possible", "rain is likely")
        if english else ("no se espera lluvia", "puede que llueva", "es probable que llueva")
    )[level]
    caveat = ""
    for es, en, day in read:
        sky = str(day.get("condition") or "").strip()
        # The sky goes against the answer: a rainy one when no rain is expected, a clear one when rain is likely.
        if sky and level != 1 and _sky_contradicts_chance(sky, _RAIN_CHANCE_HIGH if level == 2 else 0):
            sky = _sky_said(sky, english)
            if len(read) == 1:
                caveat = f", though the forecast shows {sky}" if english else f", aunque el pronóstico marca {sky}"
            else:
                # «el sábado» contracts after «de» («del sábado»).
                of_day = f"del {es[3:]}" if es.startswith("el ") else f"de {es}"
                caveat = f", though {en}'s forecast shows {sky}" if english else (
                    f", aunque el pronóstico {of_day} marca {sky}"
                )
            break
    chances = [(es, en, _decimal_said(day["rainProbabilityPercent"], english)) for es, en, day in read]
    if len(chances) == 1:
        es, en, chance = chances[0]
        return (
            f"In {location} {verdict} {en}: {chance}% chance{caveat}."
            if english else f"En {location} {verdict} {es}: {chance} % de probabilidad{caveat}."
        )
    if english:
        said = " and ".join(f"{chance}% {en}" for _, en, chance in chances)
        return f"In {location} {verdict}: {said}{caveat}."
    said = " y ".join(f"{es} {chance} %" for es, _, chance in chances)
    return f"En {location} {verdict}: {said} de probabilidad{caveat}."


# M78: a reply about a time the read does not cover says where the read ends («sólo llega hasta», «queda fuera»,
# «only goes up to», «beyond it», «only as it is now»). «No puedo ver…» would be a failure over a verified read (the
# composer's and the App's asserted-failure vetoes); the reach of the read is said instead.
_WEATHER_REACH_DENIED = re.compile(
    r"\b(?:hasta|fuera|mas\s+alla|solo|solamente|unicamente|no\s+llega|up\s+to|until|beyond|only|not\s+for|"
    r"doesn['’]?t\s+(?:reach|cover|go)|does\s+not\s+(?:reach|cover|go))\b"
)


_WEATHER_NOW_ONLY_MEASURES = (
    ("humidity", "humidityPercent"), ("wind", "windKmh"), ("apparent", "apparentC"), ("dew_point", "dewPointC"),
)


def _weather_measure_for_another_day(text: str, seen: dict, measures: frozenset[str]) -> bool:
    """A measure read only as it is now (humidity, wind, feels-like, dew point) said for tomorrow or a later day.

    M79 (DEV-D v3m p25-t3 «How humid do you expect it to be?» → «En Martínez la humedad es del 22% hoy y del 22%
    mañana.»): the read has no humidity for tomorrow; the value of now was repeated as tomorrow's. A clause that names
    another day and states one of those values says it of that day."""

    values = [seen.get(key) for measure, key in _WEATHER_NOW_ONLY_MEASURES if measure in measures]
    values = [value for value in values if isinstance(value, (int, float)) and not isinstance(value, bool)]
    if not values:
        return False
    weekdays = [
        _reading_fold(str(day.get("weekday") or ""))
        for day in (seen.get("tomorrow"), *(seen.get("laterDays") or []))
        if isinstance(day, dict) and day.get("weekday")
    ]
    another_day = re.compile(
        r"\b(?:(?<!la\s)manana|tomorrow" + "".join("|" + re.escape(day) for day in weekdays if day) + r")\b"
    )
    for clause in re.split(r"[.;:,](?=\s|$)|\s(?:y|e|and|pero|but|while|mientras)\s", _reading_fold(text)):
        if another_day.search(clause) and any(_states_weather_number(clause, value) for value in values):
            return True
    return False


# M93: saying that the read has no forecast for the hour asked. Folded.
_WEATHER_HOUR_UNREAD = re.compile(
    r"\bpor\s+horas?\b|\bhora\s+a\s+hora\b|\bpara\s+esa\s+hora\b|\ba\s+esa\s+hora\b|\bhourly\b|\bby\s+the\s+hour\b|"
    r"\bhour[\s-]by[\s-]hour\b|\bfor\s+that\s+(?:hour|time)\b|\bat\s+that\s+(?:hour|time)\b"
)


# M99: a sun event said as still to come. Folded.
_SUN_STILL_TO_COME = re.compile(
    r"\b(?:se\s+)?(?:pondra|saldra|ocultara|oscurecera|anochecera|amanecera|atardecera)\b|"
    r"\b(?:va|van)\s+a\s+(?:salir|ponerse|oscurecer|anochecer|amanecer|atardecer)\b|"
    r"\b(?:comenzara|empezara)\s+a\s+oscurecer|"
    r"\bwill\s+(?:set|rise|go\s+down|come\s+up|get\s+dark)\b|\bis\s+going\s+to\s+(?:set|rise|go\s+down|get\s+dark)\b"
)

# M105 (DEV-D v4a D-s054/D-s080): a sun event said as already happened. Folded.
_SUN_ALREADY_HAPPENED = re.compile(
    r"\b(?:se\s+)?(?:puso|salio|oculto|oscurecio|anochecio|amanecio|atardecio)\b|"
    r"\bya\s+(?:se\s+)?(?:fue|ha\s+puesto|ha\s+salido|esta\s+oscuro)\b|\bse\s+ha\s+(?:puesto|ocultado)\b|"
    r"\b(?:the\s+)?sun\s+(?:set|rose|went\s+down|came\s+up|has\s+(?:set|risen|gone\s+down))\b|"
    r"\b(?:it\s+)?(?:got|has\s+gotten|became)\s+dark\b"
)


def _weather_fact_defect(text: str, payload: dict, user_text: str) -> str:
    """REOPEN1993 grupo W: every number in a weather reply is an observed one
    (temperatures, wind, humidity, rain probability) and the place is named;
    a question about tomorrow or rain is answered with tomorrow's probability."""

    if payload.get("operation") != "weather.current":
        return ""
    seen = payload.get("seen")
    # Tanda 6b: the place asked alone is sent without the weather (_project_weather_read) and is checked too.
    if not isinstance(seen, dict) or not ("temperatureC" in seen or "location" in seen):
        return ""
    observed: set[str] = set()
    for key in ("temperatureC", "apparentC", "humidityPercent", "windKmh", "precipitationMm", "uvIndex", "dewPointC"):
        observed |= _weather_number_forms(seen.get(key))
    for day in ("today", "tomorrow"):
        block = seen.get(day)
        if isinstance(block, dict):
            for key in ("maxC", "minC", "rainProbabilityPercent", "uvIndexMax"):
                observed |= _weather_number_forms(block.get(key))
            for key in ("sunrise", "sunset"):
                observed |= _weather_clock_forms(block.get(key))
    # Uso real tanda 6: the days after tomorrow, sent when the question asks them.
    later = [day for day in seen.get("laterDays") or [] if isinstance(day, dict)]
    # M78: the one day a named date asked (_weather_asked_reach).
    asked_day = seen.get("askedDay") if isinstance(seen.get("askedDay"), dict) else None
    # Uso real v3 tanda 1: the days of a span asked (the weekend).
    later = [*later, *(day for day in seen.get("askedDays") or [] if isinstance(day, dict))]
    for block in [*later, *([asked_day] if asked_day else [])]:
        for key in ("maxC", "minC", "rainProbabilityPercent"):
            observed |= _weather_number_forms(block.get(key))
    air = seen.get("airQuality")
    if isinstance(air, dict):
        # Tanda 4c «Whats the air quality hoy?»: the index and the particles of the same read.
        for key in ("usAqi", "pm25", "pm10"):
            observed |= _weather_number_forms(air.get(key))
        # «PM2.5», «PM10» name what is measured; their digits are not a measurement.
        text = re.sub(r"(?i)\bpm\s*(?:2[.,]5|10)\b", "PM", text)
    # Tanda 4 «Digame el weather lunes 13 en North Carolina»: every draft that said which day could not be read
    # («no tengo el pronóstico del lunes 13») died here and the turn ended in no_response. A number the person
    # said is theirs to repeat, but never as a measurement: «13 °C» must still be observed.
    asked_numbers = set(re.findall(r"(?<![\w.,])\d+(?:[.,]\d+)?(?![\w]|[.,]\d)", user_text or ""))
    # A7 E3 (FINAL t323 «el sábado (3 de octubre)»): the day, month and year of a date the read carries are that
    # day's date, said like the person's numbers: never as a measurement.
    out_of_reach = seen.get("outOfReach") if isinstance(seen.get("outOfReach"), dict) else None
    reach_dates = [out_of_reach.get(key) for key in ("askedDate", "readFrom", "readUntil")] if out_of_reach else []
    for date_value in [
        *(block.get("date") if isinstance(block, dict) else None
          for block in [seen.get("today"), seen.get("tomorrow"), *later, asked_day]),
        *reach_dates,
    ]:
        if isinstance(date_value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_value):
            year, month, day = date_value.split("-")
            asked_numbers |= {year, month, day, month.lstrip("0"), day.lstrip("0")}
    # A number that ends the sentence («a las 20:15.») is still a number said.
    for found in re.finditer(r"(?<![\w.,])-?\d+(?:[.,]\d+)?(?!\w|[.,]\d)", text):
        number = found.group()
        if number in observed or number.lstrip("-") in observed:
            continue
        if number in asked_numbers and re.match(_WEATHER_MEASURE_UNIT, text[found.end():]) is None:
            continue
        return "invented_number"
    folded_text = _reading_fold(text)
    # An amount of rain is only the observed precipitation, in its millimetres
    # (none is none in any unit): an observed temperature or percentage said
    # as «14 pulgadas» is an invented amount even though the number was read.
    rain_mm = seen.get("precipitationMm")
    for amount, unit in _RAIN_AMOUNT.findall(folded_text):
        value = float(amount.replace(",", "."))
        if not (
            (value == 0 and rain_mm == 0)
            or (unit.startswith(("mm", "mil")) and amount in _weather_number_forms(rain_mm))
        ):
            return "invented_number"
    if out_of_reach is not None:
        # M78: nothing measured was sent for a time the read does not cover; the reply says that it cannot be seen.
        if _WEATHER_REACH_DENIED.search(folded_text) is None:
            return "missing_state"
        # M79 (DEV-D v3m p20-t2 «The weather forecast only goes up to September 29, 2026…» with the read reaching
        # October 5): a day the reply names is the day asked or the last day read; the first day read said as where
        # the forecast ends is a false reach.
        allowed = {
            said for key in ("askedDate", "readUntil") for said in [_calendar_day_of(out_of_reach.get(key))] if said
        }
        said_days = _calendar_days_said(folded_text)
        if out_of_reach.get("askedTime") == "past" or _calendar_day_of(out_of_reach.get("readUntil")) in said_days:
            allowed |= {said for said in [_calendar_day_of(out_of_reach.get("readFrom"))] if said}
        if any(day not in allowed for day in said_days):
            return "extra_claim"
        return ""
    if _weather_unsupported_comparison(text, seen):
        return "weather_unsupported_comparison"
    if _weather_sky_contradiction(folded_text, seen):
        return "weather_contradiction"
    asks = _reading_fold(user_text or "")
    tomorrow = seen.get("tomorrow")
    asks_tomorrow = _weather_asks_tomorrow(user_text or "")
    sun_time = weather_asks_sun_time(user_text or "")
    rain_asked = _weather_asks_rain(user_text or "")
    location = seen.get("location")
    # Owner 2026-09-24 (concise, «de una»): a measure asked by its name is the
    # answer; the temperature and the sky are not demanded next to it.
    narrow_measures = weather_asked_measures(user_text or "") - {"temperature"}
    # Uso real tanda 2 «¿Cuántas pulgadas are we getting today?»: a narrow
    # question about here (rain, the sun, the air, one measure) is answered by
    # its value; the place must be named when the person named one, or for a
    # general report.
    asked_place = _reading_fold(_weather_location(user_text or "") or "")
    # Tanda 6b «cuál es el pronóstico del tiempo para la semana»: the week summed up is the answer, as its focus
    # asks; the place is not demanded next to it (the draft died on missing_state for not naming it).
    week_asked = weather_asks_week(user_text or "")
    narrow = rain_asked or sun_time or week_asked or bool(narrow_measures) or weather_asks_air(user_text or "")
    if isinstance(location, str) and location and (asked_place or not narrow):
        # WEATHER2031 «how's the weather in Santiago»: the geocoder says «Santiago
        # de Chile»; the head of that name (before « de …» or a comma) names the
        # place as well as the whole.
        folded_location = _reading_fold(location)
        head = re.split(r"\s+de\s+|,", folded_location, maxsplit=1)[0].strip()
        # Uso real 2026-09-23 «what's the weather like in london»: the geocoder
        # names the place in Spanish («Londres»); the English reply names it as
        # the person did, and that is the same place named.
        if (
            folded_location not in folded_text
            and not (len(head) >= 3 and head in folded_text)
            and not (len(asked_place) >= 3 and re.search(r"\b" + re.escape(asked_place) + r"\b", folded_text))
        ):
            return "missing_state"
    if asked_day is not None:
        # M78: a date the read covers is answered with that day's figures.
        figures = [asked_day.get(key) for key in ("maxC", "minC", "rainProbabilityPercent")]
        figures = [value for value in figures if isinstance(value, (int, float)) and not isinstance(value, bool)]
        return "missing_state" if figures and not any(_states_weather_number(text, value) for value in figures) else ""
    if asks_own_place(user_text or ""):
        # Tanda 4c «i'd like to know my current location»: the place read is the
        # answer (named above); the weather was not asked. Uso real tanda 6 «let me
        # know my current location» still added the temperature, humidity and wind:
        # a reading of the weather in the reply is a claim nobody asked for. Tanda
        # 6b: only the place is sent now, so the sky is named by its words too.
        condition = _reading_fold(str(seen.get("condition") or ""))
        if (
            re.search(r"\d", text)
            or re.search(
                r"\b(?:temperatura|temperature|grados|degrees|humedad|humidity|viento|wind|clima|weather|"
                r"lluvia|rain|cielo|sky|nublad[oa]|soleado|despejado|cloudy|sunny|frio|calor|cold|hot|warm|mild)\b",
                folded_text,
            )
            or (condition not in ("", "sin dato") and re.search(r"\b" + re.escape(condition) + r"\b", folded_text))
        ):
            return "extra_claim"
        return ""
    if weather_asks_air(user_text or ""):
        # Tanda 4c «Whats the air quality hoy?»: the air is answered with its index.
        if isinstance(air, dict) and not _states_weather_number(text, air.get("usAqi")):
            return "missing_state"
        return ""
    asked_clock = weather_asked_clock(user_text or "")
    if (
        asked_clock is not None
        and _WEATHER_HOUR_UNREAD.search(folded_text) is None
        and re.search(r"\b" + re.escape(_reading_fold(asked_clock)) + r"\b", folded_text) is None
    ):
        # M93 (DEV-D v3u D-s014 «¿qué previsión de tiempo hay para las cuatro?» → «Actualmente hace 16.8 °C…»): the hour
        # asked is not in the read; the reply says so, or names the hour it speaks of.
        return "missing_state"
    if sun_time:
        # M93 (DEV-D v3u D-s054 «Necesito la hora en que comenzará a oscurecerse.» → «Mañana en Curicó, el sol se
        # pondrá a las 19:48.» with only today's sunset sent): the day said is the day of the sun time sent.
        if not asks_tomorrow and not isinstance(tomorrow, dict) and re.search(
            r"(?<!\bla\s)\bmanana\b|\btomorrow\b", folded_text,
        ):
            return "weather_wrong_day"
        # Uso real tanda 2 «el horario de la caída del sol para mañana»: the asked
        # day's sun time is the answer (tomorrow's for tomorrow or a later day).
        # Tanda 6b: the event asked (sunrise or sunset) is the answer; the other event's time is another fact.
        block = tomorrow if asks_tomorrow else seen.get("today")
        events = weather_sun_events_asked(user_text or "") or frozenset(("sunrise", "sunset"))

        def said(clock: object) -> bool:
            return isinstance(clock, str) and bool(clock) and (clock in text or clock.lstrip("0") in text)

        clocks = [block.get(key) for key in events] if isinstance(block, dict) else []
        clocks = [clock for clock in clocks if isinstance(clock, str) and clock]
        if clocks and not any(said(clock) for clock in clocks):
            return "missing_state"
        if (
            isinstance(block, dict)
            and any(block.get(f"{event}Passed") is True for event in events)
            and _SUN_STILL_TO_COME.search(folded_text) is not None
        ):
            # M99 (DEV-D v3x D-s054): today's sun time behind the clock told as still to come.
            return "weather_sun_time_passed"
        if (
            isinstance(block, dict)
            and any(block.get(f"{event}Passed") is False for event in events)
            and not any(block.get(f"{event}Passed") is True for event in events)
            and _SUN_ALREADY_HAPPENED.search(folded_text) is not None
        ):
            # M105 (DEV-D v4a D-s054/D-s080 at 04:45 «El sol se puso a las 19:49 hoy»): today's sun time still ahead of
            # the clock told as already happened.
            return "weather_sun_time_ahead"
        if any(
            said(day.get(other)) and day.get(other) not in clocks
            for day in (seen.get("today"), tomorrow) if isinstance(day, dict)
            for other in {"sunrise", "sunset"} - events
        ):
            return "extra_claim"
        return ""
    if "uv" in narrow_measures:
        # Uso real tanda 6 «Dime el UV index»: the index now or the peak of the day asked is the answer.
        values = (
            [tomorrow.get("uvIndexMax")] if asks_tomorrow and isinstance(tomorrow, dict)
            else [seen.get("uvIndex"), (seen.get("today") or {}).get("uvIndexMax")]
        )
        values = [value for value in values if value is not None]
        if values and not any(_states_weather_number(text, value) for value in values):
            return "missing_state"
        return ""
    # Uso real tanda 6 «el pronóstico del tiempo para la semana», «¿el sábado podremos comer afuera?»: with the
    # days after tomorrow read, the day asked is any of the days read (the reply names which), and the week is
    # answered with at least one of the days after tomorrow.
    coming = bool(later) and weather_asks_coming_days(user_text or "")
    if coming and week_asked:
        # Tanda 6b: the week's own figures (seen.week) sum up the days after tomorrow too; a range said about the
        # week is one of its ranges.
        if not any(
            _states_weather_number(text, value)
            for value in [
                *(day.get(key) for day in later for key in ("maxC", "minC", "rainProbabilityPercent")),
                *_weather_week(seen).values(),
            ]
            if isinstance(value, (int, float))
        ):
            return "missing_state"
        if _false_week_range(text, seen):
            return "invented_number"
    if coming and not rain_asked:
        # «¿qué tiempo hace hoy jueves?»: the day named may be today, answered with the weather now.
        today_weekday = _reading_fold(str((seen.get("today") or {}).get("weekday") or ""))
        today_asked = weather_asks_today(asks, today_weekday)
        figures = ([seen.get("temperatureC")] if today_asked else []) + [
            day.get(key)
            for day in (seen.get("today"), tomorrow, *later) if isinstance(day, dict)
            for key in ("maxC", "minC", "rainProbabilityPercent") if day.get(key) is not None
        ]
        figures = [value for value in figures if value is not None]
        if figures and not any(_states_weather_number(text, value) for value in figures):
            return "missing_state"
    elif rain_asked or asks_tomorrow:
        # Uso real tanda 2 «¿Me llevo el chubasquero?», «¿Cuántas pulgadas are we
        # getting today?», «dentro de dos días»: rain, rain gear, a rain amount
        # and a later day are answered with the rain probability of the day
        # asked — tomorrow's for tomorrow or later, today's for today, either
        # read when no day is named.
        # M60 (DEV-D w11-t1 «¿Está lloviendo en Medellín ahora?», 0 mm read): the rain asked now is answered by the
        # rain read now («No está lloviendo ahora en Medellín.» died three times wanting the day's probability); a
        # present rain said against the read is reversed.
        said_now = (
            _rain_now_said(folded_text)
            if weather_asks_rain_now(user_text or "") and isinstance(rain_mm, (int, float)) else None
        )
        if said_now is not None and said_now != _raining_now(seen):
            return "reversed_result"
        if coming:
            days = (seen.get("today"), tomorrow, *later)
        elif asks_tomorrow:
            days = (tomorrow,)
        elif weather_asks_later_today(asks):
            days = (seen.get("today"),)
        else:
            days = (seen.get("today"), tomorrow)
        probabilities = [
            day.get("rainProbabilityPercent")
            for day in days
            if isinstance(day, dict) and day.get("rainProbabilityPercent") is not None
        ]
        if said_now is None and probabilities and not any(
            _states_weather_number(text, value) for value in probabilities
        ):
            return "missing_state"
        if said_now is None and probabilities and weather_asks_whether_it_rains(user_text or ""):
            # M63 (v3f-final F-w01-t6): a yes or no said to «¿va a llover?» is the chances' («no se espera lluvia»
            # with 70 % is reversed, as «va a llover» with 4 %). The chances alone still answer it (owner
            # 2026-09-24, test_concision: «¿lloverá?» → «Hay un 6 % de probabilidad de lluvia hoy y un 35 % mañana.»).
            verdict = _rain_verdict_said(folded_text)
            top = max(probabilities)
            if (verdict is False and top >= _RAIN_CHANCE_HIGH) or (verdict is True and top < _RAIN_CHANCE_LOW):
                return "reversed_result"
    # M58 (v3d-final F-s066 «¿hará bueno para San Juan?»): asked in the future with no day named, the answer carries
    # tomorrow's read (its sky, a temperature or its rain), not the weather now alone.
    future = not narrow_measures and weather_asks_future(user_text or "") and isinstance(tomorrow, dict)
    if future and not any(
        _states_weather_number(text, tomorrow.get(key)) for key in ("maxC", "minC", "rainProbabilityPercent")
        if isinstance(tomorrow.get(key), (int, float))
    ):
        return "missing_state"
    # M62 (v3e2-final F-p07-t1 «I must verify the weather in Foster City later today.»): a later part of today is
    # answered with today's read (its maximum or minimum), not the temperature now alone.
    today = seen.get("today")
    later_today = (
        not narrow_measures and not rain_asked and not asks_tomorrow and not coming and not future
        # M97 (DEV-D v3x D-s014): an hour asked of today's forecast is answered with today's read too.
        and (weather_asks_later_in_the_day(user_text or "") or asked_clock is not None) and isinstance(today, dict)
    )
    if later_today and not any(
        _states_weather_number(text, today.get(key)) for key in ("maxC", "minC")
        if isinstance(today.get(key), (int, float))
    ) and not (
        # M93: for an hour asked, the weather now told beside «not by the hour» answers too.
        asked_clock is not None and any(form in text for form in _weather_number_forms(seen.get("temperatureC")))
    ):
        return "missing_state"
    for measure, key in _WEATHER_NOW_ONLY_MEASURES:
        if measure in narrow_measures and seen.get(key) is not None and not _states_weather_number(text, seen.get(key)):
            return "missing_state"
    if _weather_measure_for_another_day(text, seen, narrow_measures):
        return "extra_claim"
    if (
        not any(form in text for form in _weather_number_forms(seen.get("temperatureC")))
        and not rain_asked
        and not asks_tomorrow
        and not coming
        and not narrow_measures
        and not future
        and not later_today
        # M95 (DEV-D v3x D-s014 «¿qué previsión de tiempo hay para las cuatro?» at 22:45 → «No tengo el pronóstico para
        # las cuatro, pero hoy … una máxima de 19.5 °C, una mínima de 11.5 °C…», refused twice, ⚠): an hour asked that
        # the read does not cover is not now; the day's figures read answer it as well as the temperature now.
        and not (
            asked_clock is not None
            and isinstance(today, dict)
            and any(
                _states_weather_number(text, today.get(key)) for key in ("maxC", "minC", "rainProbabilityPercent")
                if isinstance(today.get(key), (int, float))
            )
        )
    ):
        return "missing_state"
    return ""
