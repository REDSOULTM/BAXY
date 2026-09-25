"""Tanda 9 (2026-09-25, official window, first pass): single-message misses.

Each miss was classified before it was fixed (PROPUESTA_METODO_COMPRENSION_2026-09-25, step 4). A form a reader already
owns is data added to that reader in ``semantic/``; a composer check is widened only for the defect it already names.

- «dime el tiempo de Madrid» read the clock, then published a weather page's text: «el tiempo de» a name said bare is
  the weather there. Owner: semantic/web._TIEMPO_OF_A_NAME (and _NOT_WEATHER_TIEMPO for spans of something).
- «dime en que día de la semana vivimos» → «No lo encontré»: «vivimos» says the present as «estamos». Owner:
  semantic/network._PRESENT_CALENDAR_QUESTION.
- «Ir a la pantalla de homescreen» → a limit: «pantalla (de)» may wrap the English home screen. Owner:
  semantic/windows._PC_HOME_VIEW.
- «apúntame una nota: revisar la factura de la luz el lunes» → asked what to review: «anota/apunta» with the note
  noun is the literal note of «crea una nota:». Owner: grammar._literal_note_payload_request and _CREATE (twin in
  __main__ note.create grounding).
- «me puedes poner el último disco que sacó Estopa» → asked which record: a work said with its maker in a relative
  clause names it as «de <maker>» does. Owner: semantic/patterns._music_named_by_its_maker.
- «what traffic will be like in temp» → «…map provides live traffic…», and the Madrid page text: a page describing
  itself is page voice. Owner: llm._PAGE_SELF_DESCRIPTION.
- «¿me ha llegado algún correo nuevo?» without Outlook → ⚠: «No se puede verificar…» is a failure said plainly.
  Owner: llm._FAILURE_MARKERS (twin UserMessagePolicy.LooksLikeFailure).
- «Would you show me my alarms?» → «"alarm" at "2026-09-25 14:00", …»: the listing hands the model the local clock
  and the day only when it is not today, equal alarms once. Owner: llm._project_notification_listing.

The phrasings below are paraphrases (es/en/spanglish, dialects, typos) the fixes do not name, with negative controls.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind import llm
from baxy_mind.semantic.reading import read
from baxy_mind.semantic.system import _weather_location

OPERATIONS = (
    "audio.mute", "audio.volume", "audio.volume.adjust", "media.control", "media.play.query", "media.play.youtube",
    "note.create", "task.create", "reminder.create", "web.search", "weather.current", "system.time",
    "window.minimize.all", "browser.navigate", "app.open", "email.latest.read", "system.status",
)


def _effects(text: str) -> tuple[str, ...]:
    reading = read(text, available_operations=OPERATIONS)
    return tuple(reading.effects.operations) if reading.effects is not None else ()


# ------------------------------------------------------------------ «el tiempo de <lugar>» is the weather there


@pytest.mark.parametrize(
    ("text", "place"),
    [
        ("dime el tiempo de Madrid", "Madrid"),
        ("dame el tiempo de Buenos Aires", "Buenos Aires"),
        ("decime el tiempo de Córdoba", "Córdoba"),
        ("cómo está el tiempo de Lima hoy", "Lima"),
        ("¿qué tal el tiempo de Bogotá mañana?", "Bogotá"),
        ("muéstrame el tiempo de Valencia para el finde", "Valencia"),
        ("busca el tiempo de Santiago", "Santiago"),
        ("tell me el tiempo de Miami", "Miami"),
        ("dime el tiempo de Sevilla porfa", "Sevilla"),
        ("dime el tiempo de ñuñoa", "ñuñoa"),
        ("dime el tiempo de Monterrey", "Monterrey"),
        ("mostrame el tiempo de Rosario", "Rosario"),
    ],
)
def test_the_weather_of_a_name_said_bare_is_the_weather_there(text: str, place: str) -> None:
    assert _effects(text) == ("weather.current",)
    assert _weather_location(text) == place


@pytest.mark.parametrize(
    "text",
    [
        "dime el tiempo de vuelo a Madrid",
        "dime el tiempo de espera",
        "cuál es el tiempo de vida de un gato",
        "dime el tiempo de cocción del arroz",
        "dime el tiempo de la carrera",
        "dime el tiempo de descarga del juego",
        "es tiempo de irnos",
    ],
)
def test_a_span_of_something_is_not_the_weather(text: str) -> None:
    assert "weather.current" not in _effects(text)


# ------------------------------------------------------------------ «vivimos» asks the present like «estamos»


@pytest.mark.parametrize(
    "text",
    [
        "dime en que día de la semana vivimos",
        "¿en qué año vivimos?",
        "en que mes vivimos",
        "sabes en qué día vivimos hoy",
        "en q dia vivimos",
        "what year do we live in",
        "what day are we living in",
    ],
)
def test_the_day_we_live_in_is_the_clock(text: str) -> None:
    assert _effects(text) == ("system.time",)


@pytest.mark.parametrize(
    "text", ["en qué época vivimos", "en qué país vivimos", "en qué mundo vivimos", "en qué ciudad vivimos tú y yo"]
)
def test_other_places_and_eras_we_live_in_are_not_the_clock(text: str) -> None:
    assert "system.time" not in _effects(text)


# ------------------------------------------------------------------ «la pantalla de homescreen» is the desktop view


@pytest.mark.parametrize(
    "text",
    [
        "Ir a la pantalla de homescreen.",
        "ve a la pantalla home",
        "llévame a la pantalla del home screen",
        "vamos a la pantalla de home",
        "regresa a la pantalla principal",
        "abre la pantalla de homescreen",
        "muéstrame la pantalla de inicio",
        "ir a la pantalla de inicio porfa",
        "go to the home screen",
        "take me to the homescreen",
    ],
)
def test_the_home_screen_wrapped_in_pantalla_is_the_desktop(text: str) -> None:
    assert _effects(text) == ("window.minimize.all",)


@pytest.mark.parametrize(
    "text",
    ["ve a la pantalla de inicio de sesión", "ir a la pantalla de home de netflix", "ir a la pantalla de configuración"],
)
def test_other_screens_are_not_the_desktop(text: str) -> None:
    assert "window.minimize.all" not in _effects(text)
