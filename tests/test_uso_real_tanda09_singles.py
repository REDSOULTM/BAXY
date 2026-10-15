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

from baxy_mind import payload_fact_checks
from baxy_mind import visible_defect
from baxy_mind import agenda_facts
from baxy_mind.semantic.reading import read
from baxy_mind.semantic.system import _weather_location
from baxy_mind.semantic import arguments as semantic_arguments

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


# ------------------------------------------------------------------ «apúntame una nota: …» is the literal note


@pytest.mark.parametrize(
    ("text", "content"),
    [
        ("apúntame una nota: revisar la factura de la luz el lunes", "revisar la factura de la luz el lunes"),
        ("apuntame una nota: pagar el gas el viernes", "pagar el gas el viernes"),
        ("anótame una nota: llamar al dentista el martes", "llamar al dentista el martes"),
        ("apunta una nota que diga comprar pilas", "comprar pilas"),
        ("apúntame en una nota que mañana viene el técnico", "mañana viene el técnico"),
        ("anota en una nota: la clave del portón es 4411", "la clave del portón es 4411"),
        ("jot down a note: call mom on sunday", "call mom on sunday"),
        ("porfa apúntame una nota: sacar la basura el jueves", "sacar la basura el jueves"),
        ("apúntame una nota: renovar el carnet en octubre", "renovar el carnet en octubre"),
        ("apunta una nota: el wifi de la abuela es casa123", "el wifi de la abuela es casa123"),
    ],
)
def test_a_note_ordered_with_anota_or_apunta_is_the_literal_note(text: str, content: str) -> None:
    assert _effects(text) == ("note.create",)
    arguments = semantic_arguments._explicit_arguments_from_evidence("note.create", text)
    assert arguments is not None and arguments["content"] == content


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        ("apúntame una tarea: lavar el auto", "task.create"),
        ("anota una tarea: lavar el auto", "task.create"),
        ("apúntame un recordatorio para el lunes a las 9 de pagar la luz", "reminder.create"),
    ],
)
def test_another_created_thing_named_after_anota_is_that_thing_alone(text: str, operation: str) -> None:
    assert _effects(text) == (operation,)


# ------------------------------------------------------------------ a work named with its maker is played


@pytest.mark.parametrize(
    ("text", "query"),
    [
        ("me puedes poner el último disco que sacó Estopa", "el último disco de Estopa"),
        ("pon el último disco que sacó Estopa", "el último disco de Estopa"),
        ("ponme la canción nueva que lanzó Bad Bunny", "la canción nueva de Bad Bunny"),
        ("pon el disco que sacaron los Rolling Stones", "el disco de los Rolling Stones"),
        ("ponme el último álbum que ha sacado Rosalía", "el último álbum de Rosalía"),
        ("poneme el tema que grabó Charly García", "el tema de Charly García"),
        ("play the new album that Drake released", "the new album by Drake"),
        ("play the latest song Taylor Swift put out", "the latest song by Taylor Swift"),
    ],
)
def test_a_work_named_with_its_maker_is_played(text: str, query: str) -> None:
    effects = _effects(text)
    assert len(effects) == 1 and effects[0] in {"media.play.youtube", "media.play.query"}
    arguments = semantic_arguments._explicit_arguments_from_evidence(effects[0], text)
    assert arguments is not None and arguments["query"] == query


def test_a_maker_said_by_a_pronoun_is_not_named_here() -> None:
    assert semantic_arguments._explicit_arguments_from_evidence("media.play.query", "pon la canción que sacó él") is None


# ------------------------------------------------------------------ a page describing itself is page voice


def _search_payload(results: list[dict]) -> dict:
    return {"operation": "web.search", "seen": {"query": "q", "count": len(results), "results": results}}


_TRAFFIC = [
    {"title": "Tempe Traffic and Road Conditions", "url": "https://example.com/tempe",
     "snippet": "Tempe traffic flow and incidents map - how to use it to check live traffic, road conditions, and weather "
                "impacts with an interactive map."},
]
_WEATHER_PAGE = [
    {"title": "El Tiempo en Madrid - 14 días", "url": "https://example.com/madrid",
     "snippet": "El Tiempo en Madrid, Madrid para los próximos 14 días, previsión actualizada del tiempo. Temperaturas, "
                "probabilidad de lluvias y velocidad del viento."},
]
_RECIPE = [
    {"title": "Chilaquiles verdes", "url": "https://example.com/chilaquiles",
     "snippet": "Los chilaquiles verdes son un platillo mexicano que consiste en totopos regados con salsa verde y "
                "acompañados de queso fresco desmigado y crema."},
]


@pytest.mark.parametrize(
    ("asked", "answer", "results"),
    [
        ("i need to know what traffic will be like in temp",
         "Tempe traffic flow and incidents map provides live traffic, road conditions, and weather impacts.", _TRAFFIC),
        ("how's traffic in tempe rn", "The Tempe map shows live traffic and road conditions.", _TRAFFIC),
        ("cómo está el tráfico en Tempe", "Hay tráfico en vivo y condiciones de las rutas en un mapa interactivo.",
         _TRAFFIC),
        ("dime el tiempo de Madrid",
         "El Tiempo en Madrid, Madrid para los próximos 14 días, previsión actualizada del tiempo.", _WEATHER_PAGE),
        ("el tiempo de Madrid porfa", "El sitio ofrece temperaturas y probabilidad de lluvias en Madrid.",
         _WEATHER_PAGE),
    ],
)
def test_a_page_describing_itself_is_page_voice(asked: str, answer: str, results: list[dict]) -> None:
    assert payload_fact_checks._payload_fact_defect(answer, _search_payload(results), asked) == "search_report_page_voice"


@pytest.mark.parametrize(
    ("asked", "answer", "results"),
    [
        ("cómo se hacen los chilaquiles verdes",
         "Los chilaquiles verdes son totopos regados con salsa verde, con queso fresco desmigado y crema.", _RECIPE),
        ("i need to know what traffic will be like in temp", "I couldn't find it.", _TRAFFIC),
        ("dime el tiempo de Madrid", "No lo encontré.", _WEATHER_PAGE),
    ],
)
def test_an_answer_or_a_not_found_is_not_page_voice(asked: str, answer: str, results: list[dict]) -> None:
    assert payload_fact_checks._payload_fact_defect(answer, _search_payload(results), asked) != "search_report_page_voice"


# ------------------------------------------------------------------ «no se puede verificar» is a failure said


_NO_OUTLOOK = json.dumps(
    {
        "kind": "failure", "polarity": "failure", "cause": "mission_failed", "stepCount": 0, "steps": [],
        "reason": {"kind": "operation", "operation": "email.latest.read", "polarity": "failure", "verified": False,
                   "succeeded": False, "error": "outlook_profile_not_configured"},
    }
)


@pytest.mark.parametrize(
    "draft",
    [
        "No se puede verificar si hay correos nuevos porque Outlook no está configurado en este PC.",
        "No se puede comprobar tu correo: Outlook no está configurado en este PC.",
        "No pude verificar si te llegó correo, porque Outlook no está configurado aquí.",
        "No se verifica el correo porque Outlook no está configurado en este PC.",
    ],
)
def test_a_check_that_cannot_be_made_is_a_failure_said(draft: str) -> None:
    assert visible_defect.compose_visible_defect(draft, "failure", "¿me ha llegado algún correo nuevo?",
                                      {"situation": _NO_OUTLOOK}) == ""


@pytest.mark.parametrize(
    "draft",
    [
        # Inventing that no mail came is not the failure.
        "No, no ha llegado ningún correo nuevo porque en este PC no está configurado Outlook.",
        "No he recibido correos nuevos porque Outlook no está configurado en este PC.",
    ],
)
def test_inventing_the_mailbox_state_is_still_not_the_failure(draft: str) -> None:
    assert visible_defect.compose_visible_defect(draft, "failure", "¿me ha llegado algún correo nuevo?",
                                      {"situation": _NO_OUTLOOK}) == "missing_failure"


# ------------------------------------------------------------------ the alarm listing as it is heard


def _utc(local: datetime) -> str:
    return local.astimezone(timezone.utc).isoformat()


def test_the_alarm_listing_carries_the_local_clock_and_the_day_only_when_not_today() -> None:
    now = datetime.now().astimezone().replace(second=0, microsecond=0)
    today_at = now.replace(hour=23, minute=58)
    tomorrow_at = (now + timedelta(days=1)).replace(hour=6, minute=15)
    later_at = (now + timedelta(days=3)).replace(hour=7, minute=0)
    observed = {
        "count": 4,
        "notifications": [
            {"kind": "alarm", "nextRunUtc": _utc(today_at)},
            {"kind": "alarm", "nextRunUtc": _utc(today_at)},
            {"kind": "reminder", "title": "Pastilla", "nextRunUtc": _utc(tomorrow_at)},
            {"kind": "alarm", "nextRunUtc": _utc(later_at)},
        ],
    }
    projected = agenda_facts._project_notification_listing(observed, "es")
    assert projected["count"] == 4
    assert projected["scheduled"] == [
        {"kind": "alarma", "time": "23:58", "howMany": 2},
        {"kind": "recordatorio", "title": "Pastilla", "time": "06:15", "day": "mañana"},
        {"kind": "alarma", "time": "07:00", "date": later_at.date().isoformat()},
    ]
    english = agenda_facts._project_notification_listing(observed, "en")
    assert english["scheduled"][1]["day"] == "tomorrow"
    # No UTC instant, no «YYYY-MM-DD HH:MM» string reaches the model.
    assert "nextRun" not in json.dumps(projected) and "T" not in json.dumps(projected["scheduled"][0])
