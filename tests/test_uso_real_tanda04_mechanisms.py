"""Uso real tanda 4 (2026-09-24, official window) and the residuals of tanda 3: one owner per rule.

1. The sound switched on or off is the mute («Enciende el sound» was a limit). Owner: semantic/lexicon
   SOUND_SWITCH_ON / SOUND_SWITCH_OFF (UNMUTE_WORDS / MUTE_WORDS), read by the audio reader, the domain gate
   and the argument binder.
2. The home screen opened is the desktop view; the Start menu is the Windows key («Abre el start screen» was a
   limit). Owner: semantic/windows (minimize_all_request, start_menu_request). Tanda 4c: the PC's applications
   shown are the open windows read aloud (test_uso_real_tanda04c_compose_finals).
3. The person's own music collection is asked, never searched («pon cualquier cosa de mi playlist reciente»
   played an unrelated video). Owner: semantic/patterns._OWN_FAVOURITE.
4. An entry added only if the list lacks it reads the list first, in English as in Spanish («add flour to my
   shopping list if it's not already on it» was asked back). Owner: semantic/notes._ABSENCE_CONDITION.
5. The words that ask to be told are not looked up, and what happens in the person's city is local news
   («dime que esta pasando en mi ciudad» found the song «Dime»). Owner: semantic/web.public_query_body /
   news_lookup_query.
6. The day the person named may be repeated in a weather reply, never as a measurement («Digame el weather
   lunes 13 en North Carolina» ended in no_response). Owner: llm._weather_fact_defect.
7. A clock question about the month or a calendar shown answers the date («¿estamos a enero o febrero?» →
   «Son 02:54.», «¿qué mes sale ahora mismo en el calendario de mi casa?» read Outlook). Owner:
   semantic/network.asks_calendar_part and _PRESENT_CALENDAR_QUESTION.
8. Explorer's Gallery is the pictures folder («Muéstrame mi Gallery.» died asking which folder). Owner:
   planner enum aliases and the folder domain gate.
9. The arguments read the same clause the decision read («para la música, me va a explotar la cabeza» was
   asked which action). Owner: semantic/reading.utterance_form.
10. A word broken into capitals mid-word is never published («la smart camera no la prenDO»). Owner:
    llm.visible_reply_breaks_word_case.

Every list mixes Spanish, English and Spanglish and holds phrasings never seen in a run.
"""

from __future__ import annotations

import json

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind import llm
from baxy_mind.__main__ import normalize_objective_arguments
from baxy_mind.effect_intent import operation_domain_is_grounded
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic.network import asks_calendar_part
from baxy_mind.semantic.notes import list_entry_request, list_read_request
from baxy_mind.semantic.patterns import (
    _completed_list_entry_if_absent_request,
    _explicit_named_music_query,
    deferred_clarification_split,
    resolve_explicit_effects,
)
from baxy_mind.semantic.reading import read
from baxy_mind.semantic.web import news_lookup_query, public_query_body

OPERATIONS = (
    "audio.mute", "audio.volume", "audio.volume.adjust", "audio.status", "media.control", "media.play.query",
    "media.play.youtube", "window.minimize.all", "input.key.press", "app.installed", "app.open",
    "filesystem.folder.open", "task.search", "task.create", "task.list", "web.search", "system.time",
    "calendar.event.list", "weather.current", "window.resolve",
)

SCHEMAS = {
    "audio.mute": {
        "type": "object", "properties": {"state": {"type": "boolean"}}, "required": ["state"],
        "additionalProperties": False,
    },
    "input.key.press": {
        "type": "object",
        "properties": {"key": {"type": "string", "enum": ["enter", "escape", "tab", "win"]}},
        "required": ["key"], "additionalProperties": False,
    },
    "media.control": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["next", "pause", "play", "previous", "stop", "toggle"]},
            "sourceApp": {"type": ["null", "string"], "x-maxUtf8Bytes": 256},
        },
        "required": ["action"], "additionalProperties": False,
    },
    "filesystem.folder.open": {
        "type": "object",
        "properties": {"folder": {"type": "string", "enum": ["desktop", "documents", "downloads", "pictures"]}},
        "required": ["folder"], "additionalProperties": False,
    },
    "task.search": {
        "type": "object",
        "properties": {"query": {"type": "string", "x-maxUtf8Bytes": 2000, "x-nonWhitespace": True}},
        "required": ["query"], "additionalProperties": False,
    },
    "web.search": {
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "minimum": 1, "maximum": 20},
            "nearby": {"type": ["boolean", "null"]},
            "query": {"type": "string", "x-maxUtf8Bytes": 2000, "x-nonWhitespace": True},
        },
        "required": ["query"], "additionalProperties": False,
    },
}


def _effects(text: str) -> tuple[str, ...] | None:
    reading = read(text, available_operations=OPERATIONS)
    return reading.effects.operations if reading.effects is not None else None


def _tool(operation: str) -> dict:
    schema = SCHEMAS.get(operation, {"type": "object", "properties": {}, "required": [], "additionalProperties": False})
    return {
        "type": "function",
        "function": {
            "name": operation.replace(".", "_"), "canonical_name": operation,
            "description": f"Authenticated catalog leaf {operation}.", "risk": "low_reversible", "parameters": schema,
        },
    }


class _NoEvidence:
    @staticmethod
    def candidate_families(*_args: object) -> tuple[str, ...]:
        return ()

    @staticmethod
    def retrieve(*_args: object, **_kwargs: object) -> list[object]:
        return []


class _NoModel:
    """The readers own these turns: the model is never asked to decide them."""

    @staticmethod
    def decide_turn(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise AssertionError("a deterministic reading owns this turn")

    @staticmethod
    def retire_deferred_response_language(_text: str) -> None:
        return None


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        ("Enciende el sound", "audio.mute"),  # tanda 4 t33, a limit before
        ("Abre el start screen", "window.minimize.all"),  # tanda 4 t6, a limit before
        ("show me las aplicaciones", "window.resolve"),  # tanda 4 t40: Google Play, then the Windows key (4c)
        ("add flour to my shopping list if it's not already on it", "task.search"),  # tanda 4 t11
        ("¿qué mes sale ahora mismo en el calendario de mi casa?", "system.time"),  # tanda 4 t34, Outlook before
    ],
)
def test_the_tanda_turns_are_read_without_the_model(text, operation):
    tools = [_tool(name) for name in OPERATIONS]
    result = sidecar._prepare_turn_result(
        {"id": "tanda-04", "text": text, "history": []},
        llm=_NoModel(),
        planner_catalog=PlannerCatalog(tools),
        turn_evidence=_NoEvidence(),
        encoder=lambda _texts: (),
        tool_by_name={tool["function"]["canonical_name"]: tool for tool in tools},
    )
    assert result["kind"] == "action"
    assert result["effectOperations"] == [operation]


# ---------------------------------------------------------------- 1. the sound as a switch


@pytest.mark.parametrize(
    ("text", "state"),
    [
        ("Enciende el sound", False),  # tanda 4 t33
        ("prende el audio por favor", False),
        ("enciéndele el sonido", False),
        ("turn on the sound", False),
        ("turn the audio on please", False),
        ("switch on the sound", False),
        ("activa el sonido del pc", False),
        ("habilita el audio", False),
        ("apaga el sonido", True),
        ("turn off the sound please", True),
        ("turn the sound off", True),
        ("desactiva el audio del computador", True),
    ],
)
def test_the_sound_switched_is_the_mute(text, state):
    assert _effects(text) == ("audio.mute",)
    assert operation_domain_is_grounded(text, "audio.mute", ())
    assert sidecar._ground_explicit_arguments("audio.mute", text, SCHEMAS["audio.mute"]) == {"state": state}


@pytest.mark.parametrize(
    "text",
    [
        "enciende la música",
        "prende los parlantes",
        "desactiva el sonido de las notificaciones",
        "apaga el pc",
        "turn on the tv",
        "enciende la cámara",
    ],
)
def test_another_thing_switched_is_not_the_mute(text):
    assert _effects(text) != ("audio.mute",)


# ---------------------------------------------------------------- 2. home screen and Start menu


@pytest.mark.parametrize(
    "text",
    ["Abre el start screen", "abre la pantalla de inicio", "open the home screen", "ábreme la pantalla principal"],
)
def test_the_home_screen_opened_is_the_desktop_view(text):
    assert _effects(text) == ("window.minimize.all",)


def test_the_desktop_folder_opened_is_still_not_the_desktop_view():
    assert _effects("abre el escritorio") != ("window.minimize.all",)


@pytest.mark.parametrize(
    "text",
    [
        "abre el menú inicio",
        "open the start menu",
        "muéstrame el menú de inicio de windows",
        "pull up the start menu please",
        "despliega el menu de inicio",
    ],
)
def test_the_start_menu_is_the_windows_key(text):
    assert _effects(text) == ("input.key.press",)
    assert operation_domain_is_grounded(text, "input.key.press", ())
    assert sidecar._ground_explicit_arguments("input.key.press", text, SCHEMAS["input.key.press"]) == {"key": "win"}


@pytest.mark.parametrize(
    ("text", "closed"),
    [
        ("show me las aplicaciones", False),
        ("muéstrame mis apps", False),
        ("lista las aplicaciones", False),  # tanda 4c: the open ones, read by the window inventory
        ("list the apps installed", True),
        ("Mostrar todas ah todas las aplicaciones descargadas hoy.", True),
    ],
)
def test_only_a_listing_the_start_menu_cannot_show_stays_a_limit(text, closed):
    assert sidecar._closed_unsupported_request(text) is closed


@pytest.mark.parametrize(
    "text",
    ["show me the apps on my phone", "comprueba en el menú inicio la presencia de Spotify", "dale enter"],
)
def test_other_asks_do_not_press_the_windows_key(text):
    effects = _effects(text)
    if effects == ("input.key.press",):
        assert sidecar._ground_explicit_arguments("input.key.press", text, SCHEMAS["input.key.press"]) != {"key": "win"}


# ---------------------------------------------------------------- 3. the person's own music collection


@pytest.mark.parametrize(
    "text",
    [
        "pon cualquier cosa de mi playlist reciente",  # tanda 4 t9
        "play something from my recently played",
        "play anything from my playlist",
        "pon una canción de mi lista de reproducción",
        "play my liked songs",
        "ponme algo de mi biblioteca de spotify",
        "reproduce mis canciones guardadas",
    ],
)
def test_the_own_collection_is_asked_never_searched(text):
    reading = read(text, available_operations=OPERATIONS)
    assert _explicit_named_music_query(text) is None
    assert reading.clarification is not None and reading.clarification.missing_fields == ("query",)
    assert reading.effects is None or "media.play.youtube" not in reading.effects.operations


@pytest.mark.parametrize("text", ["pon música de Bad Bunny", "play song aces high", "pon rock en spotify"])
def test_named_music_still_plays(text):
    assert _explicit_named_music_query(text) is not None


# ---------------------------------------------------------------- 4. add only if absent


@pytest.mark.parametrize(
    ("text", "entry", "list_name", "clause"),
    [
        ("add flour to my shopping list if it's not already on it", "flour", "shopping list",
         "if it's not already on it"),  # tanda 4 t11
        ("añade harina a mi lista de la compra si no está", "harina", "lista de la compra", "si no está"),
        ("put eggs on my grocery list unless they're already there", "eggs", "grocery list",
         "unless they're already there"),
        ("agrega azúcar a la lista de compras si todavía no la tengo", "azúcar", "lista de compras",
         "si todavía no la tengo"),
        ("add milk to my shopping list if it isn't there yet", "milk", "shopping list", "if it isn't there yet"),
        ("anota pan en mi lista del súper, solo si falta", "pan", "lista del súper", "solo si falta"),
    ],
)
def test_an_add_if_absent_reads_the_list_first(text, entry, list_name, clause):
    listed = list_read_request(text)
    assert listed is not None and (listed.operation, listed.entry, listed.list_name) == ("task.search", entry, list_name)
    assert list_entry_request(text) is None
    deferred = deferred_clarification_split(text, OPERATIONS)
    assert deferred is not None and deferred.kind == "list_entry_if_absent" and deferred.clause == clause
    effects = resolve_explicit_effects(text, OPERATIONS)
    assert effects is not None and effects.operations == ("task.search",)
    assert sidecar._ground_explicit_arguments("task.search", text, SCHEMAS["task.search"]) == {"query": entry}
    completed = _completed_list_entry_if_absent_request("sí", text)
    assert completed is not None and entry in completed and list_name in completed


@pytest.mark.parametrize("text", ["add flour to my shopping list", "añade harina a mi lista de la compra"])
def test_a_plain_add_still_adds(text):
    assert list_read_request(text) is None
    assert resolve_explicit_effects(text, OPERATIONS).operations == ("task.create",)


# ---------------------------------------------------------------- 5. what is looked up


@pytest.mark.parametrize(
    ("text", "body"),
    [
        ("dime que esta pasando en mi ciudad", "que esta pasando en mi ciudad"),
        ("Dígame el precio del cobre hoy", "el precio del cobre hoy"),
        ("quiero saber cuántas copas tiene Argentina", "cuántas copas tiene Argentina"),
        ("can you tell me the population of Chile", "the population of Chile"),
        ("i'd like to know who won the match", "who won the match"),
        ("cuéntame, qué pasó con la bolsa", "qué pasó con la bolsa"),
        ("can you tell me about wayne gretzky", "wayne gretzky"),
        ("dime si taco bell hace envíos", "taco bell hace envíos"),
        ("puedes decirme a qué hora sale el tren a Chicago", "a qué hora sale el tren a Chicago"),
        ("siri dime la hora en g. m. t. más cinco", "la hora en g. m. t. más cinco"),
        ("el precio del dólar", "el precio del dólar"),
    ],
)
def test_the_words_asking_to_be_told_are_not_looked_up(text, body):
    assert public_query_body(text) == body


# Tanda 4c: the news near the person is searched near this PC's city (``nearby``), never generic «local news»
# alone (t45 found US portals); a named place keeps its own news.
@pytest.mark.parametrize(
    ("text", "query", "nearby"),
    [
        ("dime que esta pasando en mi ciudad", "noticias locales", True),  # tanda 4 t45
        ("What's happening near me?", "local news", True),
        ("¿qué hay de nuevo por aquí?", "noticias locales", True),
        ("can you tell me what's going on in my town", "local news", True),
        ("¿Qué está pasando en Barcelona?", "noticias en Barcelona", False),
        ("what is happening in London", "news in London", False),
        ("what's happening around town", "local news", True),
        ("what's happening around the world", "news around the world", False),
        ("qué pasó hoy en el mundo", "noticias de hoy en el mundo", False),
        ("what happened today", "news today", False),
    ],
)
def test_what_happens_somewhere_is_its_news(text, query, nearby):
    assert news_lookup_query(text) == query
    expected = {"query": query, "nearby": True} if nearby else {"query": query}
    assert sidecar._ground_explicit_arguments("web.search", text, SCHEMAS["web.search"]) == expected


def test_a_plain_public_question_keeps_its_words_without_the_ask():
    assert sidecar._ground_explicit_arguments(
        "web.search", "dime el precio del cobre hoy", SCHEMAS["web.search"],
    ) == {"query": "el precio del cobre hoy"}


# ---------------------------------------------------------------- 6. the weather of a named day


def _weather_payload() -> dict:
    return {"operation": "weather.current", "seen": {
        "location": "Raleigh", "country": "Estados Unidos", "temperatureC": 22.6, "apparentC": 24.8,
        "humidityPercent": 82, "windKmh": 9.7, "precipitationMm": 0, "condition": "despejado",
        "today": {"maxC": 25.8, "minC": 20.1, "rainProbabilityPercent": 1, "sunrise": "07:26", "sunset": "19:31"},
        "tomorrow": {"date": "2026-09-25", "maxC": 26.2, "minC": 16, "rainProbabilityPercent": 0,
                     "condition": "nublado", "sunrise": "07:27", "sunset": "19:30"},
    }}


@pytest.mark.parametrize(
    ("ask", "reply", "defect"),
    [
        ("Digame el weather lunes 13 en North Carolina",
         "En Raleigh hace 22,6 °C y está despejado; el pronóstico del lunes 13 no lo tengo.", ""),
        ("what's the weather on the 30th in Raleigh",
         "It's 22.6 °C and clear in Raleigh now; I can't read the 30th yet.", ""),
        ("Digame el weather lunes 13 en North Carolina", "En Raleigh hace 13 °C y está despejado.", "invented_number"),
        ("Digame el weather lunes 13 en North Carolina", "En Raleigh hace 22,6 °C, con 13% de lluvia.",
         "invented_number"),
        ("Digame el weather lunes 13 en North Carolina",
         "En Raleigh hace 22,6 °C; mañana (14 de septiembre) estará nublado.", "invented_number"),
    ],
)
def test_the_day_asked_may_be_named_but_never_measured(ask, reply, defect):
    assert llm._weather_fact_defect(reply, _weather_payload(), ask) == defect


# ---------------------------------------------------------------- 7. the date asked of the clock


@pytest.mark.parametrize(
    "text",
    [
        "¿estamos a enero o febrero?",  # tanda 3 t34
        "¿qué mes sale ahora mismo en el calendario de mi casa?",  # tanda 4 t34
        "what month is it",
        "en qué año estamos",
        "is today friday",
        "a cuántos estamos",
        "¿hoy es lunes?",
        "qué fecha es hoy",
    ],
)
def test_a_calendar_part_is_asked(text):
    assert asks_calendar_part(text)


@pytest.mark.parametrize("text", ["qué hora es", "what time is it", "may I know the time", "dime la hora exacta"])
def test_the_time_alone_asks_no_date(text):
    assert not asks_calendar_part(text)


@pytest.mark.parametrize(
    "text",
    [
        "¿qué mes sale ahora mismo en el calendario de mi casa?",
        "¿qué día marca el calendario hoy?",
        "what date does the calendar show",
        "qué año dice el reloj",
    ],
)
def test_what_a_calendar_shows_now_is_the_clock(text):
    assert _effects(text) == ("system.time",)


@pytest.mark.parametrize("text", ["qué eventos hay en mi calendario", "¿qué hay en mi calendario hoy?"])
def test_the_agenda_is_still_the_agenda(text):
    assert _effects(text) == ("calendar.event.list",)


_CLOCK = {
    "kind": "operation", "operation": "system.time", "polarity": "success", "verified": True, "succeeded": True,
    "observed": {"utc": "2026-09-24T05:54:00+00:00", "localUtcOffsetMinutes": -180},
}


# Tanda 4c: the month asked is carried and answered alone (test_uso_real_tanda04c_compose_finals); the calendar
# part, never the time, is what these questions get.
@pytest.mark.parametrize(
    ("text", "time_only", "date", "carried"),
    [
        ("¿estamos a enero o febrero?", "Son las 02:54.", "Estamos en septiembre.", {"month": "septiembre"}),
        ("a cuántos estamos", "Son las 02:54.", "Estamos a 24 de septiembre.", {"date": "2026-09-24"}),
        ("what month is it", "It is 02:54.", "It is September.", {"month": "septiembre"}),
    ],
)
def test_the_month_asked_is_answered_with_the_date_not_the_time(text, time_only, date, carried):
    payload = llm._compose_situation_payload(_CLOCK, "es", text)
    assert {key: payload[key] for key in ("date", "month") if key in payload} == carried
    assert "clock" not in payload
    facts = {"situation": json.dumps(_CLOCK)}
    assert llm.compose_visible_defect(time_only, "status", text, facts) != ""
    assert llm.compose_visible_defect(date, "status", text, facts) == ""


# ---------------------------------------------------------------- 8. the Gallery


@pytest.mark.parametrize("text", ["Muéstrame mi Gallery.", "abre la galería", "open my gallery"])
def test_the_gallery_is_the_pictures_folder(text):
    # tanda-03c t3: the model proposed the pictures folder and the literal check asked «¿Cuál es la carpeta…?».
    grounded, _ = normalize_objective_arguments({"folder": "pictures"}, SCHEMAS["filesystem.folder.open"], text)
    assert grounded == {"folder": "pictures"}


# ---------------------------------------------------------------- 9. the order inside talk


@pytest.mark.parametrize(
    ("text", "operation", "arguments"),
    [
        ("para la música, me va a explotar la cabeza", "media.control", {"action": "stop"}),  # tanda 3 t33
        ("pausa el video, ya me aburrió", "media.control", {"action": "pause"}),
        ("oye, para la música", "media.control", {"action": "stop"}),
        ("apaga el sonido, me duele la cabeza", "audio.mute", {"state": True}),
    ],
)
def test_the_arguments_read_the_order_the_decision_read(text, operation, arguments):
    reading = read(text, available_operations=OPERATIONS)
    assert reading.effects is not None and reading.effects.operations == (operation,)
    assert sidecar._ground_explicit_arguments(operation, text, SCHEMAS[operation]) == arguments


# ---------------------------------------------------------------- 10. a word broken into capitals


@pytest.mark.parametrize(
    ("reply", "ask", "broken"),
    [
        ("Eso no lo hago: la smart camera no la prenDO.", "Prende la smart camera", True),  # tanda 3 t12
        ("No hago eso: las luces no las enciENDO.", "enciende las luces", True),
        ("Eso no lo hago: la smart camera no la prendo.", "Prende la smart camera", False),
        ("Abrí la tienda de macOS.", "abre la tienda de macOS", False),
        ("Listo, BAXY está en la bandeja.", "", False),
    ],
)
def test_a_word_broken_into_capitals_is_never_published(reply, ask, broken):
    assert llm.visible_reply_breaks_word_case(reply, ask) is broken
    if broken:
        assert llm._unsupported_answer_contract_failure(reply, ask) == "unsupported_broken_case"
