"""M79: the wording of a reply says what was read, in the conversation's language, in whole sentences.

Pinned on the independent review of the official-window DEV-D run v3m (REVIEW.reviewed.jsonl, cause «redacción»),
with that run's recorded payloads and drafts (tests/data/c03_m79_v3m_evidence.json, from its compose-audit.jsonl):

- s054 «Necesito la hora en que comenzará a oscurecerse.», s080 «¿a qué hora ya no habrá la luz del sol por las calles
  hoy?»: the sunset was read and the temperature was said. Getting dark and the daylight that ends are the sunset
  (semantic.web._WEATHER_SUNSET), and a projected weather read (the sun time, the day asked, the reach, the place)
  now gets its focus: the instruction was only sent when the payload carried a temperature.
- s003 «El finde pasado, ¿en qué cayó?» → today's read told as last weekend's: a day already gone is before the read
  (semantic.web.weather_asks_past, llm._weather_asked_reach).
- p25-t2/p25-t3: «Martínez» in the understood request made an English turn «mixed» and the replies came in Spanish;
  the accent of a name is not the person's language (semantic.request._without_proper_names). p25-t3 also gave a
  humidity «mañana» that no read has (llm._weather_measure_for_another_day).
- p20-t2 «The weather forecast only goes up to September 29…» with the read reaching October 5: the days a reach
  names are the day asked and the last day read.
- s047 «Ahora se está pausado la canción…»: «se» + «estar» + participle is no Spanish sentence.
- p19-t2: «'After the Wedding'» in quotes was no name for the off-subject judge («Wedding'»), so three right answers
  died, and the last resort said «who in the movie 'After the Wedding' is».
- p24-t5 «The plan is confirmed to proceed.» and p27-t4 «…in my database» in turns that ran nothing.
- w19-t4 «…el sistema no pudo verificar la causa del fallo externo», w09-t3 «…el efecto externo es ambiguo»: the code
  external_effect_ambiguous reached the writer as words; it now has its fact, and the jargon is vetoed.
- w04-t4 ⚠ missing_literal_fact: the App judges a failure's clocks against the person's own message; the mind judged
  them against its understood request («…a las 6:15 a las 6:00»), so it published what the App dropped.
- s007 ⚠: «No tengo acceso…» is refused, and the retry was told only «Sin códigos internos ni jerga de contrato.».
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from baxy_mind import llm
from baxy_mind.semantic.request import read_request
from baxy_mind.semantic.web import (
    searched_clause,
    weather_asks_coming_days,
    weather_asks_past,
    weather_asks_sun_time,
    weather_sun_events_asked,
)

EVIDENCE = json.loads((Path(__file__).parent / "data" / "c03_m79_v3m_evidence.json").read_text(encoding="utf-8"))


def _stage(case: str, index: int = 0) -> dict:
    return EVIDENCE[case]["stages"][index]


def _situation(case: str) -> dict:
    return json.loads(_stage(case)["situation"])


def _payload(case: str, user_text: str, language: str = "es") -> dict:
    return llm._compose_situation_payload(_situation(case), language, user_text)


class _Drafts(llm.LlmRuntime):
    """The drafts stand in for the model, in order (the last one repeats); every payload sent is kept."""

    def __init__(self, drafts: list[str]) -> None:  # noqa: D107
        self._gguf = r"D:\BAXYRuntime\assets\models\granite-4.2-3b-Q4_K_M.gguf"
        self._drafts = list(drafts)
        self.sent: list[dict] = []

    def _post(self, payload, **_):  # noqa: ANN001, ANN201
        self.sent.append(payload)
        content = self._drafts.pop(0) if len(self._drafts) > 1 else self._drafts[0]
        return {"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}


def _sent_text(writer: _Drafts, index: int = 0) -> str:
    return "\n".join(str(message.get("content")) for message in writer.sent[index]["messages"])


# ------------------------------------------------------------------ the sunset asked in other words


@pytest.mark.parametrize(
    "text",
    [
        "Necesito la hora en que comenzará a oscurecerse.",  # M79 (DEV-D v3m s054)
        "¿A qué hora comenzará a oscurecerse aquí?",  # s054, the decider's restatement
        "¿a qué hora ya no habrá la luz del sol por las calles hoy?",  # s080
        "¿a qué hora oscurece?",
        "cuando se hace de noche en Madrid",
        "¿hasta qué hora hay luz?",
        "when does it get dark today",
    ],
)
def test_getting_dark_is_the_sunset(text: str) -> None:
    assert weather_asks_sun_time(text)
    assert weather_sun_events_asked(text) == frozenset({"sunset"})


@pytest.mark.parametrize(
    "text", ["oscurece la pantalla", "¿a qué hora se oscurece la pantalla?", "no hay luz en la cocina"],
)
def test_a_screen_or_a_room_is_no_sunset(text: str) -> None:
    assert not weather_asks_sun_time(text)


@pytest.mark.parametrize(
    ("case", "user_text"),
    [("D-s054", "¿A qué hora comenzará a oscurecerse aquí?"),
     ("D-s080", "¿A qué hora ya no habrá la luz del sol por las calles hoy?")],
)
def test_the_sunset_read_answers_and_the_temperature_does_not(case: str, user_text: str) -> None:
    payload = _payload(case, user_text)
    assert payload["seen"]["today"] == {"date": "2026-09-29", "weekday": "martes", "sunset": "19:47"}
    assert llm._payload_fact_defect(_stage(case)["draft"], payload, user_text) != ""
    assert llm._payload_fact_defect("Hoy oscurece a las 19:47 en Curicó.", payload, user_text) == ""


def test_a_projected_weather_read_gets_its_focus() -> None:
    user_text = "¿A qué hora comenzará a oscurecerse aquí?"
    writer = _Drafts(["Hoy oscurece a las 19:47."])
    published = writer.compose_user_message(user_text, "status", {"situation": _stage("D-s054")["situation"]})
    assert published == "Hoy oscurece a las 19:47."
    assert "sale o se pone el sol" in _sent_text(writer)


# ------------------------------------------------------------------ a day already gone


def test_last_weekend_is_a_past_day_not_a_coming_one() -> None:
    assert weather_asks_past("¿En qué cayó el fin de semana pasado?")  # M79 (DEV-D v3m s003)
    assert weather_asks_past("¿llovió ayer?") and weather_asks_past("what was the weather last weekend")
    assert not weather_asks_coming_days("¿En qué cayó el fin de semana pasado?")
    assert weather_asks_coming_days("¿va a llover el finde?") and not weather_asks_past("¿va a llover el finde?")
    assert not weather_asks_past("¿y pasado mañana?")


def test_a_past_day_is_before_the_read() -> None:
    user_text = "¿En qué cayó el fin de semana pasado?"
    payload = _payload("D-s003", user_text)
    assert payload["seen"]["outOfReach"] == {"read": "forecast", "askedTime": "past", "readFrom": "2026-09-29"}
    assert "temperatureC" not in payload["seen"] and "today" not in payload["seen"]
    assert llm._payload_fact_defect(_stage("D-s003")["draft"], payload, user_text) == "invented_number"
    final = llm._deterministic_final(_situation("D-s003"), payload, user_text, "es")
    assert final == "El tiempo de Curico sólo lo leo desde hoy, no el de días pasados."
    assert llm._payload_fact_defect(final, payload, user_text) == ""


# ------------------------------------------------------------------ the conversation's language


@pytest.mark.parametrize(
    "text",
    ["Check the weather in Martínez on March 5.", "How humid is it expected to be in Martínez?"],  # p25-t2, p25-t3
)
def test_the_accent_of_a_name_is_not_the_persons_language(text: str) -> None:
    assert read_request(text).language == "en"


@pytest.mark.parametrize("text", ["¿Qué hora es en París?", "pon música", "Martínez, qué tal", "Abre Configuración"])
def test_spanish_words_and_marks_still_count(text: str) -> None:
    assert read_request(text).language == "es"


# ------------------------------------------------------------------ a measure read only now


def test_a_humidity_read_now_is_not_said_for_tomorrow() -> None:
    user_text = "How humid is it expected to be in Martínez?"
    payload = _payload("D-p25-t3", user_text, "en")
    assert llm._payload_fact_defect(
        "The humidity in Martínez is 22% today and 22% tomorrow.", payload, user_text,
    ) == "extra_claim"
    assert llm._payload_fact_defect(
        "In Martínez the humidity is 22% right now; tomorrow's is not read.", payload, user_text,
    ) == ""
    assert "never give it for tomorrow" in llm._weather_answer_instruction(user_text, "en")


# ------------------------------------------------------------------ where the forecast ends


def test_the_reach_names_the_last_day_read() -> None:
    user_text = "The city is Palo Alto, and weather info for March 2nd."
    payload = _payload("D-p20-t2", user_text, "en")
    assert llm._payload_fact_defect(_stage("D-p20-t2", 1)["draft"], payload, user_text) == "extra_claim"
    for reply in (
        "The forecast for Palo Alto only goes up to October 5; March 2 is beyond it.",
        "The forecast for Palo Alto only covers September 29 up to October 5, so March 2 is beyond it.",
        "The forecast doesn't reach March 2nd yet.",
    ):
        assert llm._payload_fact_defect(reply, payload, user_text) == ""


# ------------------------------------------------------------------ whole sentences


def test_a_reflexive_estar_with_a_participle_is_vetoed() -> None:
    draft = _stage("D-s047")["draft"]  # «Ahora se está pausado la canción "Noc turne" de Zeitgeister.»
    assert llm.compose_visible_defect(draft, "status", "cuál es el nombre de la música", {}) == "broken_estar_participle"
    for reply in (
        'La canción "Noc turne" de Zeitgeister está pausada.',
        "Se está reproduciendo «Noc turne» de Zeitgeister.",
        'Suena "Se está acabado" de Nadie.',
    ):
        assert llm.compose_visible_defect(reply, "status", "cuál es el nombre de la música", {}) == ""


def test_a_quoted_title_is_the_subject_of_the_search() -> None:
    stages = EVIDENCE["D-p19-t2"]["stages"]
    user_text = "Who's in the movie 'After the Wedding'?"
    assert [stage["reason"] for stage in stages[:3]] == ["search_report_off_subject"] * 3
    for stage in stages[1:3]:  # «The 2006 film *After the Wedding* stars Mads Mikkelsen…», «The movie '…' stars…»
        assert not llm._search_report_off_subject(stage["draft"], stage["payload"], user_text)
    assert searched_clause(user_text, "en") == ("who is in the movie 'After the Wedding'", True)
    assert searched_clause("What's the capital of Peru?", "en") == ("what the capital of Peru is", True)


# ------------------------------------------------------------------ turns that ran nothing


@pytest.mark.parametrize(
    ("reply", "request_text", "claim"),
    [
        ("The plan is confirmed to proceed.", "That is confirmed to proceed.", "effect_claim"),  # p24-t5
        ("El plan ya está confirmado.", "vale, adelante", "effect_claim"),
        ("I don't have any movies featuring Eugene Dynarski in my database.", "That one sounds good.",
         "own_store_claim"),  # p27-t4
        ("No tengo esa película en mi base de datos.", "ponla", "own_store_claim"),
    ],
)
def test_a_settled_plan_or_an_own_database_is_invented(reply: str, request_text: str, claim: str) -> None:
    assert llm.conversation_world_claim(reply, request_text, ()) == claim


@pytest.mark.parametrize(
    "reply", ["The movie is set in Paris.", "Is the plan confirmed?", "If you want, the plan is confirmed once you say so."],
)
def test_knowledge_and_questions_claim_nothing(reply: str) -> None:
    assert llm.conversation_world_claim(reply, "x", ()) == ""


# ------------------------------------------------------------------ a failure said without its code


def test_an_ambiguous_external_effect_reaches_the_writer_as_its_fact() -> None:
    situation = json.loads(_stage("D-w19-t4")["situation"])
    payload = llm._compose_situation_payload(situation, "es", "ok entonces ponme una alarma a las 8:40 para pedirlo yo")
    said = json.dumps(payload, ensure_ascii=False)
    assert "external effect ambiguous" not in said and "could not be confirmed" in said


@pytest.mark.parametrize(
    "draft",
    [
        "No se pudo programar la alarma porque el sistema no pudo verificar la causa del fallo externo.",  # w19-t4
        "No he podido abrir el archivo porque el efecto externo es ambiguo.",  # w09-t3
    ],
)
def test_the_code_said_in_words_is_still_the_code(draft: str) -> None:
    assert llm.compose_visible_defect(draft, "error", "ponlo", {}) == "internal_code"


def test_a_failures_clocks_are_the_persons_own() -> None:
    stage = _stage("D-w04-t4")
    facts = {"situation": stage["situation"]}
    understood = "Cambia el recordatorio de cargar el termo y el mate de mañana a las 6:15 a las 6:00."
    said = "Mejor a las 6 en punto, que si no no llego al micro"
    assert llm.compose_visible_defect(stage["draft"], "error", understood, facts) == ""
    assert llm.compose_visible_defect(stage["draft"], "error", understood, facts, said=said) == "extra_claim"


def test_the_access_refusal_is_told_what_to_say() -> None:
    first = _stage("D-s007")["draft"]  # «No tengo acceso a los emails de la última semana…»
    writer = _Drafts([first, "No hago listas de los remitentes de tus correos."])
    published = writer.compose_user_message(
        EVIDENCE["D-s007"]["text"], "conversation", {"situation": _stage("D-s007")["situation"]},
    )
    assert published == "No hago listas de los remitentes de tus correos."
    assert "Nunca digas que no tienes acceso" in _sent_text(writer, 1)
