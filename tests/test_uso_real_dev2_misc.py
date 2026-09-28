"""Second development set (MASSIVE, 2026-09-24), everything outside calendar, email, lists and media: one owner per rule.

1. Road traffic is live public information, never this PC's listening ports («cómo está el tráfico cerca de mí» listed
   ports). Owner: semantic/web._road_traffic_request; the network.port.list domain gate needs ports named.
2. The weekday of a date, or the date of a placed weekday, is looked up; this PC's clock reads only today («es el
   veintitrés de abril un sábado» was asked back). Owner: semantic/web._public_calendar_fact_lookup_request.
3. The weather asked by the adjective of a day, by the rain calling something off, by a temperature bound, by gear
   needed or allowed, or with the choice left open; a sentence that only mentions a weather word inside another
   lookup is not the weather. Owner: semantic/web (_WEATHER_WORDS, _WEATHER_GEAR_*, _WEATHER_AMOUNT,
   _WEATHER_DAY_QUESTION, _live_weather_request); the purpose after «para» and a kind of place are no weather
   location (semantic/system._weather_location).
4. Public places, events, what happens around, updates about a subject, cinema listings, timetables and whether a
   business delivers are looked up. Owner: semantic/web (_NEAR_THE_PERSON, _PLACE_IN_A_PLACE, public_event_subject,
   news_lookup_query, cinema_listing, transit_schedule, business_delivery); the agenda and the playback gates refuse
   them.
5. The sound said as a switch state and the mute set are the mute. Owner: semantic/lexicon.
6. The volume of the music with a level in words is that level, not a missing amount. Owner: semantic/levels.
7. A long message that asks after a preposition, or asks the listener for something, is addressed to BAXY, not
   overheard. Owner: semantic/guards._overheard_speech.
8. The formal imperative searches. Owner: semantic/grammar._SEARCH.

Every list holds phrasings never seen in a run, in Spanish, English and Spanglish.
"""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.effect_intent import operation_domain_is_grounded
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic.guards import _overheard_speech
from baxy_mind.semantic.normalize import fold
from baxy_mind.semantic.reading import read
from baxy_mind.semantic.system import _weather_location

OPERATIONS = (
    "audio.mute", "audio.volume", "audio.volume.adjust", "audio.status", "media.control", "media.play.query",
    "media.play.youtube", "media.status", "web.search", "web.news.headlines", "weather.current", "system.time",
    "calendar.event.list", "network.port.list", "network.status", "game.catalog.list", "task.update", "note.search",
)

SCHEMAS = {
    "audio.mute": {
        "type": "object", "properties": {"state": {"type": "boolean"}}, "required": ["state"],
        "additionalProperties": False,
    },
    "audio.volume": {
        "type": "object", "properties": {"level": {"type": "integer", "minimum": 0, "maximum": 100}},
        "required": ["level"], "additionalProperties": False,
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
            "description": f"Authenticated catalog leaf {operation}.", "risk": "read_only", "parameters": schema,
        },
    }


class _NoModel:
    """The readers own these turns: the model is never asked to decide them."""

    @staticmethod
    def decide_turn(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise AssertionError("a deterministic reading owns this turn")

    @staticmethod
    def retire_deferred_response_language(_text: str) -> None:
        return None


def _turn(text: str) -> dict:
    tools = [_tool(name) for name in OPERATIONS]
    return sidecar._prepare_turn_result(
        {"id": "dev2-misc", "text": text, "history": []},
        llm=_NoModel(),
        planner_catalog=PlannerCatalog(tools),
        encoder=lambda _texts: (),
        tool_by_name={tool["function"]["canonical_name"]: tool for tool in tools},
    )


# ---------------------------------------------------------------- 1. road traffic


@pytest.mark.parametrize(
    "text",
    [
        "qué tal está el tráfico en la ruta 68",
        "hay mucho tráfico para llegar al aeropuerto",
        "how bad is the traffic downtown right now",
        "any traffic jams on the highway this morning",
        "cómo anda el trafico por providencia",
        "dime si hay atascos en la autopista del sol",
        "check the traffic on my way to work",
    ],
)
def test_road_traffic_is_looked_up_without_the_model(text):
    result = _turn(text)
    assert result["kind"] == "action"
    assert result["effectOperations"] == ["web.search"]


@pytest.mark.parametrize(
    "text",
    [
        "cómo está el tráfico en mi zona",
        "what's the traffic like near me",
        "me gustaría saber cómo está el tráfico",
    ],
)
def test_road_traffic_never_lists_the_ports(text):
    assert operation_domain_is_grounded(text, "network.port.list", ()) is False


@pytest.mark.parametrize(
    "text",
    [
        "qué puertos están escuchando en este pc",
        "list the listening tcp ports",
        "muéstrame los puertos udp abiertos",
    ],
)
def test_the_ports_named_keep_the_port_listing(text):
    assert operation_domain_is_grounded(text, "network.port.list", ()) is True


@pytest.mark.parametrize(
    "text",
    [
        "cuánto tráfico de datos llevo este mes",
        "muestra el tráfico de red",
        "how much network traffic is this pc using",
        "abre google maps y mira el tráfico",
    ],
)
def test_network_traffic_or_an_open_order_is_not_a_traffic_lookup(text):
    assert _effects(text) != ("web.search",)


# ---------------------------------------------------------------- 2. another day of the calendar


@pytest.mark.parametrize(
    "text",
    [
        "en qué día de la semana cae el cuatro de julio",
        "el primero de mayo es un lunes",
        "qué fecha es el último viernes de este mes",
        "what weekday is march third",
        "is december twenty fifth a sunday",
        "tell me the date of next thursday",
        "what day does christmas fall on this year",
        "qué día cae el día de la madre",
    ],
)
def test_the_weekday_of_another_day_is_looked_up(text):
    assert _effects(text) == ("web.search",)


@pytest.mark.parametrize("text", ["qué día es hoy", "what's the date today", "en qué mes estamos"])
def test_today_is_still_the_clock(text):
    assert _effects(text) == ("system.time",)


@pytest.mark.parametrize("text", ["qué día es el partido", "what day is my dentist appointment"])
def test_the_date_of_an_event_is_not_a_calendar_fact(text):
    assert _effects(text) != ("web.search",)


# ---------------------------------------------------------------- 3. the weather asked indirectly


@pytest.mark.parametrize(
    "text",
    [
        "va a estar lluvioso el domingo",
        "estará despejado mañana en la tarde",
        "will the soccer match get rained out tomorrow",
        "va a hacer más de treinta grados mañana",
        "is it going to be below zero degrees tonight",
        "será necesario llevar abrigo esta noche",
        "¿puedo ponerme sandalias hoy?",
        "do i need a rain coat tonight or not",
        "is it going to be a lovely day on sunday",
        "va a hacer buen día el sábado",
    ],
)
def test_the_weather_asked_indirectly_is_read(text):
    assert _effects(text) == ("weather.current",)


@pytest.mark.parametrize(
    "text",
    [
        "will it be a good idea to sell my car tomorrow",
        "la cpu va a pasar de noventa grados hoy",
        "necesito comprar un abrigo nuevo",
        "novedades sobre el oso de la nieve del zoológico",
        "gira la imagen más de noventa grados",
    ],
)
def test_other_things_are_not_the_weather(text):
    assert _effects(text) != ("weather.current",)


@pytest.mark.parametrize(
    ("text", "place"),
    [
        ("hace falta paraguas para salir esta noche", None),
        ("do i need sunscreen for walking to the office today", None),
        ("will it be nice at the park on saturday", None),
        ("va a llover mañana para Santiago", "Santiago"),
        ("will it be warm tomorrow in Lisbon", "Lisbon"),
    ],
)
def test_a_purpose_or_a_kind_of_place_is_no_weather_location(text, place):
    assert _weather_location(text) == place


# ---------------------------------------------------------------- 4. the public world around the person


@pytest.mark.parametrize(
    "text",
    [
        "qué heladerías hay a mi alrededor",
        "cuántas farmacias hay en mi vecindario",
        "busca supermercados cerca de mi ubicación",
        "hay algún restaurante peruano en ñuñoa",
        "is there a sushi place in soho",
        "dime los conciertos que hay en curicó",
        "hay ferias artesanales cerca de la ciudad",
        "public holidays in my location",
        "qué está pasando a mi alrededor",
        "novedades sobre la misión a la luna",
        "any updates about the hurricane",
        "which films are showing at the cinema tonight",
        "películas en cartelera cerca de mí",
        "cuál es el horario de los buses de santiago a ñuñoa",
        "what are the bus times from boston to new york",
        "la pizzería don carlo entrega a domicilio",
        "does the corner cafe offer takeout",
    ],
)
def test_the_public_world_is_looked_up(text):
    assert _effects(text) in {("web.search",), ("web.news.headlines",)}


@pytest.mark.parametrize(
    "text",
    [
        "qué está pasando en la",
        "what are the bus times for",
        "qué pasa en mi pc",
        "novedades sobre mi pedido",
        "cuándo llega mi pedido de sushi",
        "qué pasó en la clase de ayer",
        "crea un evento a las cinco en la oficina de lima",
        "schedule an event in denver for next friday",
        "please delete that event",
        "hay eventos nuevos en mi lista",
        "detesto los atascos de los lunes",
    ],
)
def test_a_cut_scope_this_pc_or_the_persons_own_order_is_not_looked_up(text):
    assert _effects(text) != ("web.search",)


@pytest.mark.parametrize(
    "text",
    ["dime los eventos que hay en lisboa este fin de semana", "what events are happening in chicago"],
)
def test_public_events_are_not_the_agenda(text):
    assert operation_domain_is_grounded(text, "calendar.event.list", ()) is False


@pytest.mark.parametrize("text", ["qué eventos tengo mañana", "show my calendar events for friday"])
def test_the_agenda_is_still_the_agenda(text):
    assert operation_domain_is_grounded(text, "calendar.event.list", ()) is True


@pytest.mark.parametrize(
    "text",
    ["what movies are playing near me tonight", "qué películas están dando en el cine"],
)
def test_cinema_listings_are_not_this_pcs_playback(text):
    assert operation_domain_is_grounded(text, "media.status", ()) is False


def test_what_this_pc_plays_is_still_the_playback():
    assert operation_domain_is_grounded("what song is playing right now", "media.status", ()) is True


# ---------------------------------------------------------------- 5. the mute as a switch state


@pytest.mark.parametrize(
    ("text", "state"),
    [
        ("sound on", False),
        ("audio off please", True),
        ("sonido on", False),
        ("set mute", True),
        ("set it to mute now", True),
    ],
)
def test_the_switch_state_and_the_mute_set_are_the_mute(text, state):
    assert _effects(text) == ("audio.mute",)
    assert operation_domain_is_grounded(text, "audio.mute", ())
    assert sidecar._ground_explicit_arguments("audio.mute", text, SCHEMAS["audio.mute"]) == {"state": state}


@pytest.mark.parametrize("text", ["the audio on the tv is broken", "audio on my headphones sounds bad"])
def test_the_sound_described_is_not_switched(text):
    assert _effects(text) != ("audio.mute",)


# ---------------------------------------------------------------- 6. the volume of the music


@pytest.mark.parametrize(
    ("text", "level"),
    [
        ("sube el volumen de la música a ochenta", 80),
        ("baja el volumen de la música a veinte", 20),
        ("turn the volume of the music down to 15", 15),
    ],
)
def test_the_volume_of_the_music_with_a_level_is_set(text, level):
    result = _turn(text)
    assert result["kind"] == "action"
    assert result["effectOperations"] == ["audio.volume"]
    assert sidecar._ground_explicit_arguments("audio.volume", text, SCHEMAS["audio.volume"]) == {"level": level}


def test_the_volume_of_the_music_without_a_level_asks_how_much():
    assert read("sube el volumen de la música", available_operations=OPERATIONS).clarification is not None


# ---------------------------------------------------------------- 7. addressed, not overheard


@pytest.mark.parametrize(
    "text",
    [
        "durante cuántos minutos hay que hervir los huevos para que la yema quede blanda y no se rompa la cáscara",
        "for how long should i leave the chicken in the oven so that it is cooked through but not dry at all",
        "si tienes acceso a la web podrías explicarme de la forma más sencilla por qué el cielo se ve azul de día",
        "with everything you know about history can you summarize for me why the roman empire fell in the west",
    ],
)
def test_a_long_question_or_request_is_addressed_to_baxy(text):
    assert not _overheard_speech(fold(text))


def test_a_long_stretch_of_talk_is_still_overheard():
    text = "entonces mi prima le dijo al vecino que el perro se había escapado otra vez por la reja del patio anoche"
    assert _overheard_speech(fold(text))


# ---------------------------------------------------------------- 8. the formal imperative


@pytest.mark.parametrize("text", ["busque la definición de ornitorrinco", "búsquenme el significado de resiliencia"])
def test_the_formal_imperative_keeps_the_proposed_search(text):
    assert operation_domain_is_grounded(text, "web.search", ()) is True
