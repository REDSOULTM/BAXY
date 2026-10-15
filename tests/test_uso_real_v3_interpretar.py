"""Uso real v3, tanda 1 (juez, causas 2, 3 y 4): lo que se pide se interpreta antes de la herramienta.

- Pedidos creativos o de conocimiento sin herramienta («dame 3 ideas de nombre para mi gata negra») se escriben,
  nunca se devuelven como «¿Qué quieres que haga con…?».
- Fechas sin interpretar: «this weekend» son el sábado y el domingo de la lectura, no «tomorrow».
"""

from __future__ import annotations

from datetime import date

import pytest

from baxy_mind import compose_payload
from baxy_mind import deterministic_finals
from baxy_mind import payload_fact_checks
from baxy_mind import weather_facts
from baxy_mind.semantic.patterns import conversation_only_content_request
from baxy_mind.semantic.web import weather_asked_span
from baxy_mind import turn_recovery


# ------------------------------------------------------------------ 1. ideas, sugerencias y nombres se escriben


@pytest.mark.parametrize(
    "text",
    [
        "dame 3 ideas de nombre para mi gata negra",
        "give me 3 name ideas for my black cat",
        "Dame tres ideas de regalo para mi vieja",
        "suggest 5 names for my startup",
        "se te ocurren nombres para un perro salchicha?",
        # Contracasos de la exclusión: lo unido que no es un acto, y la lluvia sin un día que leer, siguen siendo
        # contenido.
        "dame ideas de nombres para mis gatos y perros",
        "dame ideas de nombres para un gato, algo corto",
        "dame ideas para un día de lluvia",
        "dame ideas de nombre para mi equipo de fútbol",
    ],
)
def test_ideas_and_names_asked_are_content(text: str) -> None:
    assert conversation_only_content_request(text) is True


@pytest.mark.parametrize(
    "text",
    [
        # Contracasos: un acto en el PC unido al pedido, lo que está cerca de la persona, un listado del PC.
        "dame 3 ideas de nombre para la carpeta y créala",
        "dame ideas de restaurantes cerca",
        "dame los nombres de los archivos del escritorio",
        "abre spotify y dame ideas",
        "dame el volumen",
        # Revisión adversarial: un acto en el PC unido después, dicho por su forma (verbo con su pronombre, «and
        # <verbo> them», una orden que los lectores conocen), no por una lista de verbos.
        "dame ideas de nombres y anótalas en el bloc de notas",
        "dame ideas de nombres y cópialas al portapapeles",
        "dame ideas y pégalas en Word",
        "dame ideas y luego escríbelas",
        "give me ideas for names and type them in notepad",
        "dame sugerencias de nombres para la carpeta del escritorio y renómbrala",
        "suggest names for my files in downloads and rename them",
        "suggest names for a cat and open notepad",
        # Lo que sólo sabe este PC o una lectura en vivo.
        "dame sugerencias de ropa para el clima de hoy",
        "dame sugerencias de canciones parecidas a la que está sonando",
        "dame sugerencias de juegos de mi biblioteca de Steam",
        "dame sugerencias de restaurantes en Ñuñoa abiertos ahora",
        "dame sugerencias para liberar espacio en mi disco",
    ],
)
def test_what_is_not_only_content_stays_out(text: str) -> None:
    assert conversation_only_content_request(text) is False


class _Composer:
    """The recovery's composer: never asked what the person wants for content they asked to be written."""

    def __init__(self, replies: dict[str, str]) -> None:  # noqa: D107
        self.replies = replies
        self.intents: list[str] = []

    def clarify_after_turn_failure(self, *_args: object, **_kwargs: object) -> str:
        raise AssertionError("content asked to be written is not asked back")

    def compose_user_message(self, _text: str, intent: str, facts: dict) -> str:
        self.intents.append(intent)
        return self.replies.get(intent, "")


def test_content_whose_turn_failed_is_written_not_asked_back() -> None:
    composer = _Composer({"conversation": "Luna, Sombra y Pantera."})
    result = turn_recovery._recover_failed_turn(
        {"id": "t1-c12", "text": "dame 3 ideas de nombre para mi gata negra", "history": []},
        composer,
        failure_kinds=("runtime", "runtime"),
    )
    assert result["kind"] != "clarify"
    assert result["reply"] == "Luna, Sombra y Pantera."
    assert composer.intents[0] == "conversation"


def test_a_request_not_understood_is_still_asked_back() -> None:
    # Contracaso: a message that is no content request keeps the recovery question.
    class _Asker(_Composer):
        def clarify_after_turn_failure(self, *_args: object, **_kwargs: object) -> str:
            return "¿Qué carpeta quieres que mueva?"

    result = turn_recovery._recover_failed_turn(
        {"id": "t1-x", "text": "muévela allá", "history": []},
        _Asker({}),
        failure_kinds=("runtime", "runtime"),
    )
    assert result["kind"] == "clarify"


def test_ideas_joined_to_an_act_whose_turn_failed_are_not_told_as_done() -> None:
    # Revisión adversarial: la recuperación no redacta como charla un pedido que también pide un acto en el PC.
    class _Asker(_Composer):
        def clarify_after_turn_failure(self, *_args: object, **_kwargs: object) -> str:
            return "¿Dónde quieres que las anote?"

    result = turn_recovery._recover_failed_turn(
        {"id": "t1-y", "text": "dame ideas de nombres y anótalas en el bloc de notas", "history": []},
        _Asker({}),
        failure_kinds=("runtime", "runtime"),
    )
    assert result["kind"] == "clarify"


# ------------------------------------------------------------------ 2. «this weekend» son el sábado y el domingo

THURSDAY = date(2026, 10, 8)


@pytest.mark.parametrize(
    ("text", "today", "days"),
    [
        ("what's the weather gonna be like in Madrid this weekend", THURSDAY, (date(2026, 10, 10), date(2026, 10, 11))),
        ("¿cómo va a estar el finde en Curicó?", THURSDAY, (date(2026, 10, 10), date(2026, 10, 11))),
        ("el fin de semana va a llover?", date(2026, 10, 10), (date(2026, 10, 10), date(2026, 10, 11))),
        ("¿y el fin de semana?", date(2026, 10, 11), (date(2026, 10, 11),)),
        ("weather next weekend", date(2026, 10, 10), (date(2026, 10, 17), date(2026, 10, 18))),
        # Integración ronda 3: one weekend reader with the agenda (semantic.temporal.weekend_saturday): «next weekend»
        # said midweek is the one after the coming one, as «el fin de semana que viene» is in the agenda's gold.
        ("weather next weekend", THURSDAY, (date(2026, 10, 17), date(2026, 10, 18))),
        ("¿va a llover el fin de semana que viene?", THURSDAY, (date(2026, 10, 17), date(2026, 10, 18))),
        ("¿qué tiempo hará pasado mañana?", THURSDAY, (date(2026, 10, 10),)),
        # Revisión adversarial: el fin de semana más allá del próximo es una semana después.
        ("what's the weather in Madrid the weekend after next", THURSDAY, (date(2026, 10, 17), date(2026, 10, 18))),
        ("weather the weekend after next", date(2026, 10, 10), (date(2026, 10, 24), date(2026, 10, 25))),
        ("en dos fines de semana va a llover?", THURSDAY, (date(2026, 10, 17), date(2026, 10, 18))),
        # Hoy o mañana nombrados junto al lapso son días pedidos; «por la mañana» es una franja, no mañana.
        ("¿y mañana y el finde en Madrid?", THURSDAY, (date(2026, 10, 9), date(2026, 10, 10), date(2026, 10, 11))),
        ("¿qué tiempo hará hoy y el fin de semana?", THURSDAY,
         (date(2026, 10, 8), date(2026, 10, 10), date(2026, 10, 11))),
        ("el finde por la mañana va a hacer frío?", THURSDAY, (date(2026, 10, 10), date(2026, 10, 11))),
    ],
)
def test_a_span_of_days_is_resolved_against_the_calendar(text: str, today: date, days: tuple[date, ...]) -> None:
    assert weather_asked_span(text, today) == days


@pytest.mark.parametrize(
    "text",
    [
        # Contracasos: un fin de semana ya pasado, mañana a secas, hoy.
        "¿qué tal estuvo el fin de semana pasado?",
        "will it rain tomorrow in Madrid",
        "¿qué tiempo hace hoy?",
        # Revisión adversarial: un día de la semana, una hora o la semana nombrados junto al lapso son lo pedido, y
        # los lee el lector de ese día o de esa hora.
        "ok so este weekend me voy a San Antonio con unos amigos, can you check el weather para el sábado allá?",
        "¿cómo va a estar pasado mañana a las cuatro?",
        "weather next week and the weekend",
    ],
)
def test_no_span_is_read_where_none_is_named(text: str) -> None:
    assert weather_asked_span(text, THURSDAY) == ()


def _madrid_read() -> dict:
    """The read of the t1-c06 turn (compose_audit of uso-real-v3 t1-base), trimmed to what the reply uses."""

    return {
        "kind": "operation",
        "operation": "weather.current",
        "polarity": "success",
        "verified": True,
        "succeeded": True,
        "observed": {
            "version": 1, "location": "Madrid", "region": "Comunidad Autónoma de Madrid", "country": "España",
            "locatedBy": "named_place_geocoded", "observedAtLocal": "2026-10-08T03:30", "timezone": "Europe/Madrid",
            "temperatureC": 15.3, "condition": "parcialmente nublado", "precipitationMm": 0,
            "today": {"date": "2026-10-08", "weekday": "jueves", "maxC": 20.4, "minC": 13.2,
                      "rainProbabilityPercent": 3},
            "tomorrow": {"date": "2026-10-09", "weekday": "viernes", "maxC": 20, "minC": 7.1,
                         "rainProbabilityPercent": 0, "condition": "mayormente despejado"},
            "laterDays": [
                {"date": "2026-10-10", "weekday": "sábado", "condition": "nublado", "maxC": 23.5, "minC": 8.4,
                 "rainProbabilityPercent": 0},
                {"date": "2026-10-11", "weekday": "domingo", "condition": "nublado", "maxC": 22.1, "minC": 12.7,
                 "rainProbabilityPercent": 0},
                {"date": "2026-10-12", "weekday": "lunes", "condition": "parcialmente nublado", "maxC": 24,
                 "minC": 11.7, "rainProbabilityPercent": 0},
            ],
            "authority": "open_meteo_forecast_v1",
        },
    }


def test_the_weekend_read_is_its_saturday_and_sunday() -> None:
    text = "what's the weather gonna be like in Madrid this weekend"
    situation = _madrid_read()
    payload = compose_payload._compose_situation_payload(situation, "en", text)
    seen = payload["seen"]
    assert [day["date"] for day in seen["askedDays"]] == ["2026-10-10", "2026-10-11"]
    assert "tomorrow" not in seen and "today" not in seen
    final = deterministic_finals._deterministic_final(situation, payload, text, "en")
    assert "tomorrow" not in final.casefold()
    assert "Saturday" in final and "Sunday" in final and "23.5" in final and "12.7" in final
    assert payload_fact_checks._payload_fact_defect(final, payload, text) == ""


def test_the_weekend_in_spanish_names_its_days() -> None:
    text = "¿cómo va a estar el finde en Madrid?"
    situation = _madrid_read()
    payload = compose_payload._compose_situation_payload(situation, "es", text)
    final = deterministic_finals._deterministic_final(situation, payload, text, "es")
    assert final.startswith("En Madrid, el sábado: nublado") and "el domingo:" in final
    assert payload_fact_checks._payload_fact_defect(final, payload, text) == ""


def test_tomorrow_is_still_tomorrow() -> None:
    # Contracaso: «tomorrow» keeps tomorrow's read.
    text = "what's the weather tomorrow in Madrid"
    situation = _madrid_read()
    payload = compose_payload._compose_situation_payload(situation, "en", text)
    assert "askedDays" not in payload["seen"]
    assert "tomorrow" in deterministic_finals._deterministic_final(situation, payload, text, "en").casefold()


def test_tomorrow_and_the_weekend_are_all_told() -> None:
    # Revisión adversarial: «mañana y el finde» perdía mañana; los tres días van al redactor y al final.
    text = "¿y mañana y el finde en Madrid?"
    situation = _madrid_read()
    payload = compose_payload._compose_situation_payload(situation, "es", text)
    assert [day["date"] for day in payload["seen"]["askedDays"]] == ["2026-10-09", "2026-10-10", "2026-10-11"]
    final = deterministic_finals._deterministic_final(situation, payload, text, "es")
    assert final.startswith("En Madrid, mañana: mayormente despejado") and "el sábado:" in final
    assert "el domingo:" in final
    assert payload_fact_checks._payload_fact_defect(final, payload, text) == ""


def test_a_measure_over_the_weekend_keeps_the_whole_read() -> None:
    # Contracaso: el UV no viene en los días del lapso; la lectura entera (con mañana) sigue yendo.
    text = "UV index this weekend in Madrid"
    payload = compose_payload._compose_situation_payload(_madrid_read(), "en", text)
    assert "askedDays" not in payload["seen"] and "tomorrow" in payload["seen"]


def test_the_weekend_after_next_is_beyond_the_read() -> None:
    # Revisión adversarial: «the weekend after next» daba este fin de semana como si fuera el pedido.
    text = "what's the weather in Madrid the weekend after next"
    situation = _madrid_read()
    payload = compose_payload._compose_situation_payload(situation, "en", text)
    assert payload["seen"]["outOfReach"]["askedDate"] == "2026-10-17"
    final = deterministic_finals._deterministic_final(situation, payload, text, "en")
    assert "23.5" not in final and "October 12" in final


def test_a_rain_caveat_contracts_the_weekday() -> None:
    final = weather_facts._weather_rain_final(
        "Madrid",
        [("el sábado", "Saturday", {"rainProbabilityPercent": 0, "condition": "lluvia"}),
         ("el domingo", "Sunday", {"rainProbabilityPercent": 0, "condition": "nublado"})],
        False,
    )
    assert "del sábado" in final and "de el" not in final
