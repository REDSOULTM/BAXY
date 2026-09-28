"""Tanda 2 (2026-09-23, 50 unseen real messages): families read by nobody or by the wrong reader.

- The weather asked through what it calls for: the gear to wear or carry, an amount, a sun time.
- «Ve home.»: the PC's home said bare after a movement verb.
- A radio station (a name or a spoken dial with its band) is played, even when asked what it plays now.
- «Turn dowm poquito la musica»: a typed particle, a bare diminutive and the music as the volume.
- «Silenciar la bocina»: «bocina» is the speaker.
"""

from __future__ import annotations

import pytest

from baxy_mind.__main__ import _explicit_arguments_from_evidence, _prepare_turn_result
from baxy_mind.llm import _weather_fact_defect
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import levels
from baxy_mind.semantic.guards import cut_request_tail
from baxy_mind.semantic.media import radio_station_query
from baxy_mind.semantic.patterns import (
    operation_domain_is_grounded,
    resolve_explicit_clarification_intent,
    resolve_explicit_effects,
)
from baxy_mind.semantic.system import _weather_location
from baxy_mind.semantic.web import weather_asks_later_day, weather_asks_sun_time
from baxy_mind.semantic.windows import minimize_all_request
from baxy_mind.semantic.normalize import fold
from test_c03_pointless_questions import _tool
from test_c03_unknown_looked_up import _KnowledgeLlm

_WEATHER = {"weather.current", "web.search", "reminder.create", "task.create", "notification.schedule"}


@pytest.mark.parametrize(
    "text",
    [
        "¿Cuántas pulgadas are we getting today?",
        "tengo un festival de música dentro de dos días. ¿Me llevo el chubasquero?",
        "¿Debo ponerme scarf esta noche?",
        "necesito el horario de la caída del sol para mañana.",
        "¿necesito paraguas?",
        "should I bring an umbrella tomorrow",
        "do i need a jacket tonight",
        "what time is sunset today",
        "¿cuántos grados hace?",
        "¿me pongo guantes mañana?",
    ],
)
def test_weather_asked_through_gear_amount_or_sun_time_is_the_weather_read(text: str) -> None:
    intent = resolve_explicit_effects(text, _WEATHER)

    assert intent is not None and intent.operations == ("weather.current",)
    assert operation_domain_is_grounded(text, "weather.current", ())
    # Nothing in these names a place: the read uses this PC's location, never «música» or «mañana».
    assert _weather_location(text) is None


@pytest.mark.parametrize(
    ("text", "place"),
    [
        ("¿a qué hora se pone el sol en Lima?", "Lima"),
        ("cuántos milímetros de lluvia caerán mañana en Santiago", "Santiago"),
        ("clima de mañana en Lima", "Lima"),
    ],
)
def test_a_place_named_with_en_still_names_the_place(text: str, place: str) -> None:
    assert _weather_location(text) == place


@pytest.mark.parametrize(
    "text",
    [
        "¿dónde dejé el paraguas?",
        "necesito comprar una bufanda",
        "tengo que llevar la chaqueta a la tintorería",
        "¿cuántos grados tiene un triángulo?",
        "quiero ver el atardecer",
        "¿tienes un abrigo?",
        "¿Qué es la puesta del sol?",
    ],
)
def test_gear_units_and_the_sun_outside_a_weather_question_are_not_the_weather(text: str) -> None:
    intent = resolve_explicit_effects(text, _WEATHER)

    assert intent is None or intent.operations != ("weather.current",)


def test_later_day_and_sun_time_are_recognised_for_the_answer() -> None:
    assert weather_asks_later_day("tengo un festival de música dentro de dos días. ¿Me llevo el chubasquero?")
    assert weather_asks_later_day("va a llover el fin de semana?")
    assert weather_asks_later_day("clima para pasado mañana")
    assert not weather_asks_later_day("¿llueve mañana?")
    assert not weather_asks_later_day("clima de hoy")
    assert weather_asks_sun_time("necesito el horario de la caída del sol para mañana.")
    assert not weather_asks_sun_time("¿necesito paraguas?")


_SEEN = {
    "location": "Curicó",
    "temperatureC": 15.2,
    "apparentC": 13.8,
    "humidityPercent": 70,
    "windKmh": 9.1,
    "precipitationMm": 0.0,
    "today": {"maxC": 18.0, "minC": 11.0, "rainProbabilityPercent": 5, "sunrise": "07:12", "sunset": "19:31"},
    "tomorrow": {"maxC": 17.5, "minC": 10.4, "rainProbabilityPercent": 40, "sunrise": "07:11", "sunset": "19:32"},
}
_PAYLOAD = {"operation": "weather.current", "seen": _SEEN}


def test_a_sun_time_question_is_answered_with_the_asked_days_observed_clock() -> None:
    asked = "necesito el horario de la caída del sol para mañana."

    assert _weather_fact_defect("Mañana en Curicó el sol se pone a las 19:32.", _PAYLOAD, asked) == ""
    # Today's clock does not answer a question about tomorrow; an unread clock is invented.
    assert _weather_fact_defect("En Curicó el sol se pone a las 19:31.", _PAYLOAD, asked) == "missing_state"
    assert _weather_fact_defect("En Curicó el sol se pone a las 20:15.", _PAYLOAD, asked) == "invented_number"


def test_rain_gear_and_a_later_day_are_answered_with_tomorrows_rain_probability() -> None:
    gear = "tengo un festival de música dentro de dos días. ¿Me llevo el chubasquero?"
    answered = (
        "En Curicó leo sólo hoy y mañana: mañana hay un 40 % de probabilidad de lluvia, "
        "con máxima de 17,5 °C."
    )

    assert _weather_fact_defect(answered, _PAYLOAD, gear) == ""
    assert _weather_fact_defect("En Curicó hay 15,2 °C y está despejado.", _PAYLOAD, gear) == "missing_state"
    assert _weather_fact_defect("En Curicó hay 15,2 °C.", _PAYLOAD, "¿Debo ponerme scarf esta noche?") == ""


@pytest.mark.parametrize(
    "text",
    ["Ve home.", "go home", "go back home please", "vuelve al inicio", "llévame al home", "go to desktop",
     "show desktop", "ve a la pantalla principal"],
)
def test_the_pc_home_said_bare_after_a_movement_is_the_desktop(text: str) -> None:
    intent = resolve_explicit_effects(text, {"window.minimize.all", "web.search", "browser.navigate"})

    assert intent is not None and intent.operations == ("window.minimize.all",)
    assert operation_domain_is_grounded(text, "window.minimize.all", ())


@pytest.mark.parametrize(
    "text",
    ["abre home", "ve a home depot", "muestra el inicio", "go to the home page", "abre la carpeta home",
     "ve a la página de inicio de google"],
)
def test_home_elsewhere_is_not_the_desktop(text: str) -> None:
    assert not minimize_all_request(fold(text))


@pytest.mark.parametrize(
    ("text", "query"),
    [
        ("pon kiss f. m. para mi", "kiss FM en vivo"),
        ("qué música está poniendo actualmente novecientos noventa y nueve f. m.", "99.9 FM en vivo"),
        ("tune in to eight hundred and ninety seven f. m.", "89.7 FM en vivo"),
        ("pon la noventa y nueve punto siete f m", "99.7 FM en vivo"),
        ("pon radio cooperativa", "radio cooperativa en vivo"),
        ("quiero escuchar radio bio bio", "radio bio bio en vivo"),
        ("pon mil ochenta a. m.", "1080 AM en vivo"),
    ],
)
def test_a_named_radio_station_is_played_in_the_local_player(text: str, query: str) -> None:
    intent = resolve_explicit_effects(text, {"media.play.query", "media.play.youtube", "web.search"})

    assert intent is not None and intent.operations == ("media.play.youtube",)
    assert radio_station_query(text) == query
    assert _explicit_arguments_from_evidence("media.play.youtube", text, (), ()) == {"query": query}


def test_a_station_asked_on_spotify_stays_on_spotify() -> None:
    intent = resolve_explicit_effects("pon kiss fm en spotify", {"media.play.query", "media.play.youtube"})

    assert intent is not None and intent.operations == ("media.play.query",)


@pytest.mark.parametrize(
    "text",
    ["pon la alarma a las 7 a. m.", "pon un recordatorio a las 9 am", "qué música está poniendo spotify",
     "apaga la radio del wifi", "qué está sonando en la radio"],
)
def test_a_clock_a_player_or_a_network_radio_is_not_a_station(text: str) -> None:
    assert radio_station_query(text) is None


@pytest.mark.parametrize(
    ("text", "direction"),
    [
        ("Turn dowm poquito la musica", "down"),
        ("turn down the music", "down"),
        ("Turn up poquito la musica", "up"),
        ("bajale poquito", "down"),
        ("súbele tantito", "up"),
        ("turn it dowm", "down"),
    ],
)
def test_a_direction_without_amount_asks_only_the_amount(text: str, direction: str) -> None:
    level = levels.read(text)

    assert level == levels.Level(levels.VOLUME if "music" in fold(text) else None, direction, None, None)
    clarification = resolve_explicit_clarification_intent(text, {"audio.volume.adjust", "media.play.query"})
    assert clarification is not None
    assert clarification.operations == ("audio.volume.adjust",)
    assert clarification.missing_fields == ("amount",)


def test_music_with_a_level_is_the_volume_and_more_music_is_not() -> None:
    intent = resolve_explicit_effects("baja la música al 20", {"audio.volume", "audio.volume.adjust"})

    assert intent is not None and intent.operations == ("audio.volume",)
    assert levels.read("más música") is None
    assert levels.read("ponle más música") is None


@pytest.mark.parametrize("text", ["Silenciar la bocina please.", "silencia las bocinas", "mute the speaker"])
def test_the_speaker_by_any_regional_name_is_muted(text: str) -> None:
    intent = resolve_explicit_effects(text, {"audio.mute", "audio.volume.adjust"})

    assert intent is not None and intent.operations == ("audio.mute",)
    assert operation_domain_is_grounded(text, "audio.mute", ())


# --- the whole turn: the readers decide before the model's own reading -------------------------------------


class _TalkingLlm(_KnowledgeLlm):
    """A model that would answer every one of these as talk (the real run searched the web or asked)."""

    @staticmethod
    def formulate_explicit_clarification_question(*_args: object, **_kwargs: object) -> str:
        return "¿Cuánto bajo el volumen?"


def _turn(text: str) -> dict[str, object]:
    tools = {
        name: _tool(name, required=required)
        for name, required in (
            ("web.search", ("query",)),
            ("weather.current", ()),
            ("media.play.youtube", ("query",)),
            ("window.minimize.all", ()),
            ("audio.mute", ()),
            ("audio.volume.adjust", ("amount",)),
        )
    }
    return _prepare_turn_result(
        {"id": "turn-tanda02", "text": text},
        llm=_TalkingLlm("x"),
        planner_catalog=PlannerCatalog(list(tools.values())),
        encoder=lambda _texts: (),
        tool_by_name=tools,
    )


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        ("¿Cuántas pulgadas are we getting today?", "weather.current"),
        ("tengo un festival de música dentro de dos días. ¿Me llevo el chubasquero?", "weather.current"),
        ("¿Debo ponerme scarf esta noche?", "weather.current"),
        ("necesito el horario de la caída del sol para mañana.", "weather.current"),
        ("Ve home.", "window.minimize.all"),
        ("qué música está poniendo actualmente novecientos noventa y nueve f. m.", "media.play.youtube"),
        # «para mi» closes the request: it did not arrive cut (uso-real-01 asked how it went on).
        ("pon kiss f. m. para mi", "media.play.youtube"),
        ("Silenciar la bocina please.", "audio.mute"),
    ],
)
def test_the_turn_acts_on_the_read_request(text: str, operation: str) -> None:
    result = _turn(text)

    assert result["kind"] == "action"
    assert result["operation"] == operation


def test_para_mi_closes_a_request_and_a_possessive_left_open_is_still_cut() -> None:
    assert cut_request_tail("pon kiss f. m. para mi") is None
    assert cut_request_tail("abre el archivo que está en la carpeta de mi") == "carpeta de mi"


def test_the_turn_asks_only_the_amount_of_a_typed_spanglish_volume_order() -> None:
    result = _turn("Turn dowm poquito la musica")

    assert result["kind"] == "clarify"
    assert result["question"] == "¿Cuánto bajo el volumen?"
