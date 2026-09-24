"""Development corpus 2026-09-23 (MASSIVE, family «misc»): real sentences read by nobody or by the wrong reader.

- The forecast asked without an asking verb, the weather through clothes, «me gustaría saber el tiempo…».
- «la fecha hoy»; the mute said with no verb or with the plural sound.
- Posting to or reading a social network, and the devices of the house, are plain limits, never a search, a
  tweet written as if posted or a song called «en marcha una taza de café».
- Public places, events, delivery, rates and shares, polls and departures are looked up, never asked back.
- A question the ear wrote without its question mark is said to BAXY, and «cerca de mí» is not a cut message.
- A joke, an animal's sound, a sum and the description of a thing are conversation, not media, audio or search.
"""

from __future__ import annotations

import pytest

from baxy_mind.__main__ import _general_factoid_prompt, _prepare_turn_result
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import dialogue, reading
from baxy_mind.semantic.guards import _unresolved_input_kind, cut_request_tail
from baxy_mind.semantic.patterns import (
    effect_request_is_authoritative,
    known_unsupported_effect_request,
    operation_domain_is_grounded,
    resolve_explicit_clarification_intent,
    resolve_explicit_effects,
)
from baxy_mind.semantic.system import _weather_location
from baxy_mind.semantic.web import _entity_lookup_query
from test_c03_pointless_questions import _NoEvidence, _tool

_OPS = (
    "weather.current", "web.search", "system.time", "audio.mute", "audio.status", "audio.volume.adjust",
    "media.play.query", "media.play.youtube", "calendar.event.list", "message.send", "vision.describe",
    "calculator.expression.evaluate", "reminder.create", "task.create", "notification.schedule",
)


# --- the weather -------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "me gustaría saber el tiempo en barcelona",
        "quisiera saber si va a llover mañana en madrid",
        "hay alguna previsión de lluvia o nieve esta semana",
        "la temperatura de mañana va a ser caliente sí o no",
        "la temperatura será más alta de cuarenta grados mañana",
        "el sol está brillando con fuerza tendremos este tiempo el resto del día",
        "qué chaqueta debería ponerme",
        "debería ponerme sandalias o zapatos con calcetines",
    ],
)
def test_the_forecast_asked_without_an_asking_verb_is_the_weather_read(text: str) -> None:
    intent = resolve_explicit_effects(text, _OPS)

    assert intent is not None and intent.operations == ("weather.current",)
    assert operation_domain_is_grounded(text, "weather.current", ())


@pytest.mark.parametrize(
    ("text", "place"),
    [
        ("me gustaría saber el tiempo en barcelona", "barcelona"),
        ("quisiera saber si va a llover mañana en madrid", "madrid"),
        ("la temperatura será más alta de cuarenta grados mañana", None),
        ("la temperatura será más alta de 40 grados mañana en sevilla", "sevilla"),
        ("hay alguna previsión de lluvia o nieve esta semana", None),
    ],
)
def test_the_place_of_the_forecast_is_a_place_never_a_measure(text: str, place: str | None) -> None:
    assert _weather_location(text) == place


@pytest.mark.parametrize(
    "text",
    [
        "quiero saber el tiempo de cocción del arroz",
        "la temperatura de la cpu ahora",
        "la temperatura del horno para mañana",
        "qué chaqueta me recomiendas comprar",
        "hay un archivo que se llama lluvia",
    ],
)
def test_time_and_temperature_of_other_things_are_not_the_weather(text: str) -> None:
    intent = resolve_explicit_effects(text, _OPS)

    assert intent is None or intent.operations != ("weather.current",)


# --- the clock and the mute ----------------------------------------------------------------------------------------


@pytest.mark.parametrize("text", ["la fecha hoy", "la hora actual", "la fecha de hoy"])
def test_the_date_or_hour_with_its_article_is_the_clock(text: str) -> None:
    intent = resolve_explicit_effects(text, _OPS)

    assert intent is not None and intent.operations == ("system.time",)


def test_an_event_date_is_not_the_clock() -> None:
    assert resolve_explicit_effects("la fecha de la reunión de hoy", _OPS) is None


@pytest.mark.parametrize(
    "text", ["silencio altavoces", "altavoces en silencio", "apaga los sonidos", "silencia los sonidos", "mute the sounds"]
)
def test_the_silence_of_the_speakers_or_the_sounds_is_the_mute(text: str) -> None:
    intent = resolve_explicit_effects(text, _OPS)

    assert intent is not None and intent.operations == ("audio.mute",)
    assert operation_domain_is_grounded(text, "audio.mute", ())


@pytest.mark.parametrize("text", ["silencio en la sala", "los sonidos del bosque"])
def test_silence_somewhere_else_is_not_the_mute(text: str) -> None:
    assert resolve_explicit_effects(text, _OPS) is None


# --- limits: social networks and the house -------------------------------------------------------------------------

_SOCIAL = [
    "tuitea un mensaje a mrw diciéndoles que aún estoy esperando mi pedido",
    "olly tuitea a apple que el iphone no funciona",
    "ok google tuitea qué estúpido es el dueño de la gasolinera",
    "responde con un tuit negativo al servicio de lowi",
    "abrir tuit a apple que la bateria de mi iphone siempre esta agotada",
    "publica un estado en facebook diciendo que estoy disfrutando del buen tiempo",
    "olly tweet walmart and tell them their customer service is horrible",
    "sube una foto a instagram",
    "tengo nuevas peticiones de amistad",
    "what does my facebook feed look like",
]


@pytest.mark.parametrize("text", _SOCIAL)
def test_posting_to_or_reading_a_social_network_is_a_plain_limit(text: str) -> None:
    assert known_unsupported_effect_request(text, _OPS)
    assert effect_request_is_authoritative(text)


@pytest.mark.parametrize(
    "text",
    [
        "abre facebook",
        "abre twitter",
        "entra a mi instagram",
        "busca en twitter noticias de chile",
        "qué es un tweet",
        "the tweet was funny",
        "manda un whatsapp a mamá",
        "publica la nota",
    ],
)
def test_going_to_a_network_or_naming_a_tweet_is_not_the_limit(text: str) -> None:
    assert not known_unsupported_effect_request(text, _OPS)


_HOUSE = [
    "pon en marcha una taza de café por favor",
    "poner colores oscuros en lugar de claros en la casa",
    "apaga las luces de la cocina",
    "enciende la aspiradora",
    "sube la temperatura del termostato",
    "prepárame un café",
]


@pytest.mark.parametrize("text", _HOUSE)
def test_the_devices_of_the_house_and_errands_are_a_plain_limit_never_a_song(text: str) -> None:
    assert known_unsupported_effect_request(text, _OPS)
    intent = resolve_explicit_effects(text, _OPS)
    assert intent is None or not {"media.play.query", "media.play.youtube"} & set(intent.operations)


@pytest.mark.parametrize("text", ["baja las luces", "baja la luz de la pantalla", "pon despacito de luis fonsi"])
def test_the_screen_light_and_a_song_are_not_the_house(text: str) -> None:
    assert not known_unsupported_effect_request(text, _OPS)


def test_a_named_song_is_still_played() -> None:
    intent = resolve_explicit_effects("pon despacito de luis fonsi", _OPS)

    assert intent is not None and intent.operations == ("media.play.youtube",)


@pytest.mark.parametrize("text", ["rate five", "califica esta canción con cinco estrellas", "dale 5 estrellas"])
def test_rating_what_plays_is_a_plain_limit(text: str) -> None:
    assert known_unsupported_effect_request(text, _OPS)


def test_dale_with_a_bare_number_is_not_a_rating() -> None:
    assert not known_unsupported_effect_request("dale 5", _OPS)


# --- public lookups ----------------------------------------------------------------------------------------------

_PUBLIC = [
    "me gustaría saber cuáles son los pubs mejor valorados de la zona",
    "dónde hay un buen bar de vinos cerca de mí",
    "dime qué tiendas de ropa hay en un radio de cinco kilómetros de mi",
    "i would like to know the best rating pubs in the local area",
    "encuentra una panadería sin glutén cerca de mí",
    "show me reviews of my nearest location food court",
    "chequea en los cines precios y disponibilidad por las peliculas de estreno en mi zona",
    "recomendar una película en mi área",
    "hay algún evento deportivo mañana en chicago",
    "show me nearby musical events",
    "alexa el rodilla hace envíos",
    "i need to know if mr. pizza delivers",
    "pizza hut tiene para llevar",
    "let me know about the exchange rate of rupee to dirham",
    "cuantos euros es un dólar estadounidense ahora",
    "cuál es el aumento en el valor de las acciones durante la última semana de disney",
    "cuáles son las predicciones de las votaciones de r. t. v. e. para las próximas elecciones españolas",
    "puedes decirme a qué hora sale el tren a chicago",
]


@pytest.mark.parametrize("text", _PUBLIC)
def test_public_places_events_rates_and_departures_are_looked_up(text: str) -> None:
    assert _unresolved_input_kind(text) is None
    assert resolve_explicit_clarification_intent(text, _OPS) is None
    intent = resolve_explicit_effects(text, _OPS)
    assert intent is not None and intent.operations == ("web.search",)


@pytest.mark.parametrize(
    "text",
    [
        "cuándo se entregará mi comida china",
        "cuántos pesos tengo en la cuenta",
        "cuánto es 5 euros más 3 euros",
        "a qué hora sale mi vuelo",
        "baja el brillo desde las acciones rápidas",
    ],
)
def test_the_persons_own_order_trip_or_sum_is_not_a_public_lookup(text: str) -> None:
    intent = resolve_explicit_effects(text, _OPS)

    assert intent is None or intent.operations != ("web.search",)


@pytest.mark.parametrize("text", ["qué eventos tengo mañana", "qué hay en mi calendario hoy"])
def test_the_persons_own_agenda_is_still_the_calendar(text: str) -> None:
    intent = resolve_explicit_effects(text, _OPS)

    assert intent is not None and intent.operations == ("calendar.event.list",)


def test_a_calendar_system_is_not_the_agenda() -> None:
    assert resolve_explicit_effects("cuál es la diferencia entre el calendario romano y el gregoriano", _OPS) is None


def test_let_me_know_is_not_a_message_to_send() -> None:
    assert resolve_explicit_clarification_intent("let me know about the weather in lima", _OPS) is None


# --- what the ear drops: the question mark and the accent of «mí» ---------------------------------------------------


def test_a_long_message_that_opens_asking_or_ordering_is_said_to_baxy() -> None:
    assert _unresolved_input_kind(
        "muéstrame la respuesta a este problema doscientos cuarenta y seis más seiscientos cincuenta y cuatro"
    ) is None
    assert _unresolved_input_kind(
        "how many minutes do i need to wait to pick up my food from china on the go today please"
    ) is None
    # A long stretch of talk with no question and no order is still overheard.
    assert _unresolved_input_kind(
        "y entonces le dije que no porque la verdad es que ya estaba cansado de todo eso y se fue enojado"
    ) == "overheard_speech"


def test_de_mi_after_a_place_or_a_distance_is_where_the_person_is() -> None:
    assert cut_request_tail("dime qué tiendas de ropa hay en un radio de cinco kilómetros de mi") is None
    assert cut_request_tail("busca un restaurante italiano que esté cerca de mi") is None
    assert cut_request_tail("abre el archivo que está en la carpeta de mi") == "carpeta de mi"


def test_a_time_said_first_does_not_make_a_question_a_story() -> None:
    assert dialogue.talk_act("ayer mediodía en el centro de palma por qué fue la protesta") is None
    assert dialogue.talk_act("anoche vi Oppenheimer y me gustó") == "statement"


def test_a_request_after_a_story_is_not_talk() -> None:
    text = "i had a problem with my burger can you tweet bk"

    assert reading.plain_talk(text, effects=None, clarification=None) is None


# --- conversation, not media, audio or search -------------------------------------------------------------------


@pytest.mark.parametrize("text", ["i want to hear a joke", "me gustaría escuchar algunos buenos chistes divertidos"])
def test_a_joke_is_told_not_played(text: str) -> None:
    assert reading.read(text, available_operations=_OPS).effects is None


@pytest.mark.parametrize(
    "text",
    [
        "que sonido hace un perro",
        "what is four plus five",
        "cuál es la suma de los dos números cuatro y seis",
        "muéstrame la respuesta a este problema doscientos cuarenta y seis más seiscientos cincuenta y cuatro",
        "cuánto es 25 por 4",
        "describe infierno",
        "dime la descripción de teléfono inteligente",
        "cómo describirías una pelota",
        "describe rock sand",
    ],
)
def test_sounds_sums_and_descriptions_are_stable_knowledge(text: str) -> None:
    assert _general_factoid_prompt(text)


@pytest.mark.parametrize(
    "text",
    [
        "cuánto es 6 por 7 en la calculadora",
        "cuanto es 20 por ciento de 50",
        "describe lo que ves en la pantalla",
        "describe esta imagen",
        "describe el clima de hoy",
        "describe mi pc",
    ],
)
def test_the_calculator_a_percentage_the_screen_and_live_reads_keep_their_readers(text: str) -> None:
    assert not _general_factoid_prompt(text)


def test_a_sum_is_not_a_named_thing_to_look_up() -> None:
    assert _entity_lookup_query("what is four plus five") is None
    assert _entity_lookup_query("what is Monkey C") == "Monkey C"


# --- the whole turn ---------------------------------------------------------------------------------------------


class _ClosedLlm:
    """A model that must not be asked to decide: these turns close before it."""

    def __init__(self, reply: str = "Eso no lo hago.") -> None:
        self.reply = reply
        self.chat_kinds: list[str] = []

    @staticmethod
    def decide_turn(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise AssertionError("the readers close this turn before the model decides")

    def chat(self, _text: str, **kwargs: object) -> tuple[str, list[object]]:
        self.chat_kinds.append(str(kwargs.get("conversation_kind")))
        return self.reply, []

    @staticmethod
    def public_lookup_requested(_text: str) -> bool:
        return False

    @staticmethod
    def _verify_semantic_effect_shape(_text: str) -> tuple[str, str]:
        return "no_effect", "zero"

    @staticmethod
    def detect_response_language(_text: str) -> str:
        return "es"

    @staticmethod
    def consume_deferred_response_language(_text: str) -> tuple[bool, str | None]:
        return True, "es"

    @staticmethod
    def retire_deferred_response_language(_text: str) -> None:
        return None


def _turn(text: str, llm: object) -> dict[str, object]:
    tools = {
        name: _tool(name, required=required)
        for name, required in (
            ("web.search", ("query",)),
            ("weather.current", ()),
            ("media.play.youtube", ("query",)),
            ("audio.mute", ()),
            ("audio.status", ()),
            ("vision.describe", ()),
        )
    }
    return _prepare_turn_result(
        {"id": "turn-misc", "text": text},
        llm=llm,
        planner_catalog=PlannerCatalog(list(tools.values())),
        turn_evidence=_NoEvidence(),
        encoder=lambda _texts: (),
        tool_by_name=tools,
    )


@pytest.mark.parametrize(
    "text",
    [
        "tuitea un mensaje a vodafone diciéndoles que su servicio es malo",
        "what does my facebook feed look like",
        "pon en marcha una taza de café por favor",
        "poner colores oscuros en lugar de claros en la casa",
    ],
)
def test_the_turn_is_a_plain_limit(text: str) -> None:
    llm = _ClosedLlm()
    result = _turn(text, llm)

    assert result["kind"] == "conversation"
    assert result["conversationKind"] == "unsupported"
    assert result["effectOperations"] == []
    assert llm.chat_kinds == ["unsupported"]


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        ("me gustaría saber el tiempo en barcelona", "weather.current"),
        ("hay alguna previsión de lluvia o nieve esta semana", "weather.current"),
        ("silencio altavoces", "audio.mute"),
        ("dónde hay un buen bar de vinos cerca de mí", "web.search"),
        ("hay algún evento deportivo mañana en chicago", "web.search"),
        ("dime qué tiendas de ropa hay en un radio de cinco kilómetros de mi", "web.search"),
    ],
)
def test_the_turn_acts_on_the_read_request(text: str, operation: str) -> None:
    result = _turn(text, _ClosedLlm())

    assert result["kind"] == "action"
    assert result["operation"] == operation


@pytest.mark.parametrize("text", ["que sonido hace un perro", "describe infierno", "what is four plus five"])
def test_the_turn_answers_in_conversation(text: str) -> None:
    llm = _ClosedLlm("Respuesta.")
    result = _turn(text, llm)

    assert result["kind"] == "conversation"
    assert result["effectOperations"] == []
    assert result["conversationKind"] == "knowledge"


def test_knock_knock_is_played_along() -> None:
    llm = _ClosedLlm("¿Quién es?")
    result = _turn("toc toc", llm)

    assert result["kind"] == "conversation"
    assert result["conversationKind"] == "social"


class _NotKnowingLlm(_ClosedLlm):
    @staticmethod
    def decide_turn(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {
            "mode": "conversation", "operation": None, "question": "", "conversation_kind": "knowledge",
            "effect_count": "zero", "effect_operations": [], "effect_verification": "not_applicable",
            "response_language": "en",
        }


def test_a_known_limit_the_model_answers_is_never_searched() -> None:
    result = _turn("rate five", _NotKnowingLlm("I don't know what you want me to rate."))

    assert result["effectOperations"] == []
    assert "web.search" not in result["intentOperations"]
