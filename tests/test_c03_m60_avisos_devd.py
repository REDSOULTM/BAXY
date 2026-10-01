"""Goal v3 paso 5 (M60): the ⚠ of DEV-D in the official window (v3c-devD, v3d-devD-np2, q4-devD, 2026-09-28/29).

Every draft and situation here is the one the run recorded (compose-audit.jsonl); the request is the one the mind
composed against (turn-audit raw_decision.request, which dialogue_state.understood hands to the writer).

- D-s004 / D-w03-t3 (limit): «…porque eso no lo hago» died on limit_gives_a_reason; the limit before the reason is
  whole, so it is clipped.
- D-p03-t3 (resolve + task.delete): «I have removed chips from your shopping list.» died on missing_name for not
  saying «note» or «title».
- D-p16-t1 v3c (web_search_unavailable): «open the search page in your web browser» is the offer the cause asks.
- D-p25-t1 v3c (weather_service_unavailable): «it did not respond» is the typed cause, not an invented non-answer.
- D-w10-t6 v3d (media_seek_postcondition_not_verified): the cause fell back to «external effect ambiguous».
- D-w11-t1 (rain asked now, 0 mm read): «No está lloviendo ahora en Medellín.» is the answer.
- D-s032 q4 (news): the feed's «: Taylor Swift abre…» was quoted without its stray colon.
- D-s067 q4 (task.create «patatas y patatas y huevos»): three drafts shortened the title; the item is told as written.
"""

from __future__ import annotations

import json

import pytest

from baxy_mind import llm
from baxy_mind.llm import LlmRuntime
from baxy_mind.semantic.web import weather_asks_rain_now


class _Drafts(LlmRuntime):
    """The recorded drafts stand in for the model, in order; ``timeout_after`` ends the budget."""

    def __init__(self, drafts: list[str], timeout_after: int | None = None) -> None:  # noqa: D107
        self._gguf = r"D:\BAXYRuntime\assets\models\granite-4.2-3b-Q4_K_M.gguf"
        self._drafts = list(drafts)
        self._timeout_after = timeout_after
        self.calls = 0

    def _post(self, payload, **_):  # noqa: ANN001, ANN201
        self.calls += 1
        if self._timeout_after is not None and self.calls > self._timeout_after:
            raise TimeoutError("se agotó el presupuesto de composición opcional")
        content = self._drafts.pop(0) if len(self._drafts) > 1 else self._drafts[0]
        return {"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}


def _compose(drafts: list[str], user_text: str, intent: str, situation: str | dict, **facts: object) -> str:
    return _Drafts(drafts).compose_user_message(user_text, intent, {"situation": situation, **facts})


LIMIT = '{"kind":"failure","polarity":"failure","cause":"out_of_catalog"}'

CHIPS_DELETED = (
    '{"kind":"status","polarity":"success","cause":"mission_completed","stepCount":2,"steps":['
    + json.dumps(json.dumps({
        "kind": "operation", "operation": "task.resolve.exact", "polarity": "success", "verified": True,
        "succeeded": True, "observed": {"taskId": "75c31918-bda1-4821-a8e4-00d650598946", "expectedVersion": 1,
                                        "reviewLabel": "chips", "deleted": False, "status": "open"},
        "readOnly": True,
    }, separators=(",", ":")))
    + ","
    + json.dumps(json.dumps({
        "kind": "operation", "operation": "task.delete", "polarity": "success", "verified": True, "succeeded": True,
        "observed": {"taskId": "75c31918-bda1-4821-a8e4-00d650598946", "title": "chips", "details": "shopping list",
                     "completed": False, "deleted": True, "createdAtUtc": "2026-09-29T03:46:03.1292962+00:00",
                     "updatedAtUtc": "2026-09-29T03:46:05.0247208+00:00", "version": 2},
        "readOnly": False,
    }, separators=(",", ":")))
    + '],"completedRequest":"Remove chips from my shopping list."}'
)
CHIPS = "Remove chips from my shopping list."
CHIPS_PRIOR = ["Please put ice on my shopping list", "also chips"]

SEARCH_UNAVAILABLE = (
    '{"kind":"failure","polarity":"failure","cause":"mission_failed","stepCount":0,"steps":[],"reason":'
    '{"kind":"operation","operation":"web.search","polarity":"failure","verified":false,"succeeded":false,'
    '"error":"web_search_unavailable"}}'
)
KENZI = "Search for valet parking at the Kenzi Rose Garden."

WEATHER_UNAVAILABLE = (
    '{"kind":"failure","polarity":"failure","cause":"mission_failed","stepCount":0,"steps":[],"reason":'
    '{"kind":"operation","operation":"weather.current","polarity":"failure","verified":false,"succeeded":false,'
    '"error":"weather_service_unavailable"}}'
)
MARTINEZ = "Check the weather in Martinez on March 5."

SEEK_UNVERIFIED = (
    '{"kind":"failure","polarity":"failure","cause":"mission_failed","stepCount":0,"steps":[],"reason":'
    '{"kind":"operation","operation":"media.seek.relative","polarity":"failure","verified":false,"succeeded":false,'
    '"error":"media_seek_postcondition_not_verified","cause":"external_effect_ambiguous","effectUncertain":true}}'
)

MEDELLIN = "¿Está lloviendo en Medellín ahora?"
MEDELLIN_READ = {
    "kind": "operation", "operation": "weather.current", "polarity": "success", "verified": True, "succeeded": True,
    "observed": {
        "version": 1, "location": "Medellín", "region": "Antioquia", "country": "Colombia",
        "locatedBy": "named_place_geocoded", "observedAtLocal": "2026-09-28T21:30", "timezone": "America/Bogota",
        "temperatureC": 18.9, "apparentC": 21.3, "humidityPercent": 95, "windKmh": 3.4, "precipitationMm": 0,
        "uvIndex": 0, "dewPointC": 18, "weatherCode": 2, "condition": "parcialmente nublado",
        "today": {"date": "2026-09-28", "weekday": "lunes", "maxC": 26.9, "minC": 17.6, "rainProbabilityPercent": 82,
                  "uvIndexMax": 8.2, "sunrise": "05:50", "sunset": "17:55"},
        "tomorrow": {"date": "2026-09-29", "weekday": "martes", "maxC": 29.6, "minC": 17.2,
                     "rainProbabilityPercent": 51, "uvIndexMax": 9.7, "condition": "llovizna", "sunrise": "05:50",
                     "sunset": "17:54"},
        "airQuality": {"usAqi": 28, "category": "buena", "pm25": 8, "pm10": 8.1},
        "authority": "open_meteo_forecast_v1",
    },
}

TAYLOR = "Noticias sobre Taylor Swift."
TAYLOR_READ = {
    "kind": "operation", "operation": "web.news.headlines", "polarity": "success", "verified": True, "succeeded": True,
    "observed": {"version": 1, "topic": "Taylor Swift", "edition": "es-419/CL", "count": 5, "headlines": [
        {"title": "Taylor Swift supera a Beyoncé como la artista más premiada de los MTV VMA 2026",
         "source": "CNN en Español", "publishedAt": "Mon, 28 Sep 2026 03:46:00 GMT"},
        {"title": "Taylor Swift y Lisa hacen historia y Madonna reina otra vez: los ganadores de los MTV VMA 2026",
         "source": "BioBioChile", "publishedAt": "Mon, 28 Sep 2026 03:57:28 GMT"},
        {"title": "Dakota Johnson tiene malas noticias para los fans que esperaban ver fotos de la boda de Taylor Swift",
         "source": "HOLA", "publishedAt": "Mon, 28 Sep 2026 22:40:48 GMT"},
        {"title": ": Taylor Swift abre su intimidad con Travis Kelce", "source": "MUNDIARIO",
         "publishedAt": "Tue, 29 Sep 2026 00:14:30 GMT"},
        {"title": "Taylor Swift lanza video de ‘Patient Zero’ con giro en la trama inquietante: Dónde verlo",
         "source": "Billboard", "publishedAt": "Mon, 28 Sep 2026 15:20:17 GMT"},
    ], "authority": "google_news_rss_es419_cl"},
}

PATATAS = "Pon patatas y patatas y huevos en la lista de deseos."
PATATAS_CREATED = {
    "kind": "operation", "operation": "task.create", "polarity": "success", "verified": True, "succeeded": True,
    "observed": {"taskId": "32bd0da8-7a94-49a2-9d21-2894ddd679d8", "title": "patatas y patatas y huevos",
                 "details": "lista de deseos", "completed": False, "deleted": False,
                 "createdAtUtc": "2026-09-29T03:43:11.8097653+00:00",
                 "updatedAtUtc": "2026-09-29T03:43:11.8097653+00:00", "version": 1},
}


# D-s004 (v3c, v3d) and D-w03-t3 (q4): the limit said with a reason is clipped to the limit.
@pytest.mark.parametrize(("user_text", "drafts", "published"), [
    ("prende la luz de la cosina",
     ["No enciendo la luz de la cocina porque eso no es lo que hago.",
      "Eso no lo hago porque no apago ni enciendo luces.",
      "No enciendo las luces, ya que eso no lo hago."],
     "No enciendo la luz de la cocina."),
])
def test_a_limit_given_with_a_reason_is_told_without_it(user_text: str, drafts: list[str], published: str) -> None:
    assert llm.compose_visible_defect(drafts[0], "error", user_text, {"situation": LIMIT}) == "limit_gives_a_reason"
    assert _compose(drafts, user_text, "error", LIMIT) == published


RECOMPRAR = "recomprar el último billete de tren a huesca"
RECOMPRAR_DRAFTS = [
    "No recomprobo billetes de tren porque eso no es lo que hago en este PC.",
    "No recompré el billete porque eso no lo hago.",
    "No recompraré el último billete de tren a Huesca.",
]


def test_a_limit_with_a_verb_form_that_does_not_exist_is_never_clipped_into_the_reply() -> None:
    # M60 clipped the reason and published «No recomprobo billetes de tren.»; the independent review of DEV-D v3l
    # (M78, D-s004) marks it: «recomprobo» is no form of «recomprar». The broken first person is judged first, and the
    # clipped limit is not publishable either.
    assert llm.compose_visible_defect(RECOMPRAR_DRAFTS[0], "error", RECOMPRAR, {"situation": LIMIT}) == (
        "limit_broken_person"
    )
    assert _compose(RECOMPRAR_DRAFTS, RECOMPRAR, "error", LIMIT) != "No recomprobo billetes de tren."
    assert _compose([RECOMPRAR_DRAFTS[0], "Eso no lo hago: recomprar billetes de tren."], RECOMPRAR, "error", LIMIT) == (
        "Eso no lo hago: recomprar billetes de tren."
    )


def test_the_second_limit_draft_clips_to_the_plain_limit() -> None:
    drafts = ["Eso no lo hago porque no apago ni enciendo luces."]
    assert _compose(drafts, "prende la luz de la cosina", "error", LIMIT) == "Eso no lo hago."


def test_a_reason_the_person_asked_for_is_not_clipped() -> None:
    # Independent review B1: «¿por qué no puedes…?» asks for the reason, so the draft is judged whole.
    draft = "No enciendo luces porque no controlo aparatos de la casa."
    assert llm.compose_visible_defect(draft, "error", "¿por qué no puedes prender la luz?", {"situation": LIMIT}) != (
        "limit_gives_a_reason"
    )


# D-p03-t3 (all three runs): the removed item is named by its title.
@pytest.mark.parametrize("draft", [
    "I have removed chips from your shopping list.",
    'I removed the "chips" item from your shopping list.',
    'The item "chips" has been removed from your shopping list.',
    "The chips item has been removed from your shopping list.",
])
def test_a_removed_task_is_named_by_its_title(draft: str) -> None:
    facts = {"situation": CHIPS_DELETED, "priorRequests": CHIPS_PRIOR}
    assert llm.compose_visible_defect(draft, "status", CHIPS, facts) == ""


def test_a_removal_told_as_not_done_is_still_vetoed() -> None:
    draft = "I did not remove the chips from your shopping list because you requested that."
    facts = {"situation": CHIPS_DELETED, "priorRequests": CHIPS_PRIOR}
    # M107: the vetoed draft is not published; the verified removal is told from its facts instead of no final.
    assert _compose([draft], CHIPS, "status", CHIPS_DELETED, priorRequests=CHIPS_PRIOR) == "I removed the task «chips»."
    assert llm.compose_visible_defect(draft, "status", CHIPS, facts) != ""


@pytest.mark.parametrize(("draft", "user_text"), [
    ("I did not remove chips.", CHIPS),
    ("The chips item has not been removed from your shopping list.", CHIPS),
    ("No he añadido patatas y patatas y huevos a la lista de deseos.", PATATAS),
    ("Patatas y patatas y huevos no se ha añadido a la lista de deseos.", PATATAS),
])
def test_a_verified_task_write_told_as_not_done_is_reversed(draft: str, user_text: str) -> None:
    situation = CHIPS_DELETED if user_text == CHIPS else PATATAS_CREATED
    facts = {"situation": situation, "priorRequests": CHIPS_PRIOR} if user_text == CHIPS else {"situation": situation}
    assert llm.compose_visible_defect(draft, "status", user_text, facts) == "reversed_result"


def test_a_task_title_alone_still_owes_its_word_outside_task_and_note_writes() -> None:
    # The exemption is for the writes of a task or a note; a titled read keeps the old rule.
    assert llm._TITLED_ITEM_WRITES >= {"task.delete", "task.create", "note.create"}
    assert "window.focus" not in llm._TITLED_ITEM_WRITES


# D-p16-t1 v3c: the browser offer is not the lookup shown; the failure fact is the last resort.
def test_the_browser_offer_of_a_search_is_not_the_search_shown() -> None:
    drafts = [
        "The search for valet parking at the Kenzi Rose Garden failed because it could not be looked up right now. "
        "I can open it in your web browser.",
        "The valet parking information at the Kenzi Rose Garden could not be looked up right now. I can open the "
        "search page in your web browser for you.",
    ]
    assert llm.compose_visible_defect(drafts[0], "error", KENZI, {"situation": SEARCH_UNAVAILABLE}) == ""
    assert _compose(drafts, KENZI, "error", SEARCH_UNAVAILABLE) == drafts[1]


def test_narrating_the_failed_search_is_still_the_search_shown() -> None:
    payload = llm._compose_situation_payload(json.loads(SEARCH_UNAVAILABLE), "en", KENZI)
    narrated = ("The search for valet parking at the Kenzi Rose Garden failed because it could not be looked up "
                "right now.")
    assert llm._payload_fact_defect(narrated, payload, KENZI) == "search_report_shows_the_search"
    offer = "I could not look up valet parking right now. Would you like me to open the search in your web browser?"
    assert llm._payload_fact_defect(offer, payload, KENZI) == ""


@pytest.mark.parametrize(("situation", "user_text", "english", "spanish"), [
    (SEARCH_UNAVAILABLE, KENZI, "I couldn't look it up right now; I can open it in your web browser.",
     "No pude buscarlo ahora; puedo abrirlo en tu navegador."),
    (WEATHER_UNAVAILABLE, MARTINEZ, "I couldn't read the weather: the weather service didn't answer.",
     "No pude leer el tiempo: el servicio meteorológico no respondió."),
    (SEEK_UNVERIFIED, "Adelanta diez segundos la canción.", "I couldn't confirm the jump in the playback.",
     "No pude confirmar el salto en la reproducción."),
])
def test_a_typed_failure_is_told_by_its_cause_after_three_vetoed_drafts(
    situation: str, user_text: str, english: str, spanish: str,
) -> None:
    vetoed = ["La operación de búsqueda relativa falló porque el efecto externo es ambiguo."]
    language = "en" if user_text.isascii() else "es"
    expected = english if language == "en" else spanish
    assert llm._deterministic_final(json.loads(situation), {}, user_text, language) == expected
    assert _compose(vetoed, user_text, "error", situation, forbiddenResponseTerms=["operación", "operacion"]) == (
        expected
    )


def test_the_failure_template_is_publishable_in_both_languages() -> None:
    for situation, user_text in ((SEARCH_UNAVAILABLE, "Busca aparcamiento cerca del hotel."),
                                 (WEATHER_UNAVAILABLE, "¿Qué tiempo hace en Martínez?")):
        text = llm._deterministic_final(json.loads(situation), {}, user_text, "es")
        assert llm.compose_visible_defect(text, "error", user_text, {"situation": situation}) == ""


# D-p25-t1 v3c: the weather service that did not answer is the typed cause.
def test_the_weather_service_that_did_not_answer_is_the_cause() -> None:
    draft = "I checked the weather service for Martinez, but it did not respond, so no forecast was available."
    assert llm.compose_visible_defect(draft, "error", MARTINEZ, {"situation": WEATHER_UNAVAILABLE}) == ""
    # A non-answer said of a cause that is not one is still invented.
    other = SEARCH_UNAVAILABLE
    assert llm.compose_visible_defect(
        "I could not look it up because the server did not respond.", "error", KENZI, {"situation": other},
    ) == "extra_claim"


def test_the_seek_cause_reaches_the_payload_as_its_fact() -> None:
    payload = llm._compose_situation_payload(json.loads(SEEK_UNVERIFIED), "es", "Adelanta diez segundos la canción.")
    assert "external effect ambiguous" not in json.dumps(payload)
    assert "could not be confirmed" in json.dumps(payload)


# D-w11-t1 (v3c, v3d): the rain asked now is the rain read now.
@pytest.mark.parametrize("draft", [
    "No está lloviendo ahora en Medellín.",
    "Actualmente no está lloviendo en Medellín.",
])
def test_the_rain_asked_now_is_answered_by_the_rain_read_now(draft: str) -> None:
    payload = llm._compose_situation_payload(MEDELLIN_READ, "es", MEDELLIN)
    assert llm._payload_fact_defect(draft, payload, MEDELLIN) == ""


def test_rain_said_now_against_the_read_is_reversed() -> None:
    payload = llm._compose_situation_payload(MEDELLIN_READ, "es", MEDELLIN)
    assert llm._payload_fact_defect("Sí, está lloviendo ahora en Medellín.", payload, MEDELLIN) == "reversed_result"


def test_the_place_named_by_the_person_is_still_owed() -> None:
    payload = llm._compose_situation_payload(MEDELLIN_READ, "es", MEDELLIN)
    draft = "No está lloviendo ahora, pero la probabilidad de lluvia para hoy es del 82%."
    assert llm._payload_fact_defect(draft, payload, MEDELLIN) == "missing_state"


@pytest.mark.parametrize(("user_text", "now"), [
    ("¿Está lloviendo en Medellín ahora?", True),
    ("Parce, ¿sabes si allá está lloviendo ahorita?", True),
    ("is it raining in London?", True),
    ("¿llueve ahora en Santiago?", True),
    ("¿Va a llover mañana?", False),
    ("¿Lloverá esta tarde?", False),
    ("¿Está lloviendo el sábado en Madrid?", False),
    ("¿Me llevo el paraguas?", False),
])
def test_rain_asked_now_is_read_in_semantic(user_text: str, now: bool) -> None:
    assert weather_asks_rain_now(user_text) is now


def test_the_weather_template_says_the_rain_now_when_it_is_asked() -> None:
    text = llm._deterministic_final(MEDELLIN_READ, {"seen": MEDELLIN_READ["observed"]}, MEDELLIN, "es")
    assert text == "En Medellín hay 18,9 °C ahora, parcialmente nublado; no llueve ahora."
    payload = llm._compose_situation_payload(MEDELLIN_READ, "es", MEDELLIN)
    assert llm._payload_fact_defect(text, payload, MEDELLIN) == ""


def test_three_vetoed_rain_drafts_end_in_the_rain_read_now() -> None:
    vetoed = ["No está lloviendo ahora, pero la probabilidad de lluvia para hoy es del 82%."]
    assert _compose(vetoed, MEDELLIN, "status", MEDELLIN_READ) == (
        "En Medellín hay 18,9 °C ahora, parcialmente nublado; no llueve ahora."
    )


# D-s032 q4: a headline is quoted by its words; punctuation is typography.
@pytest.mark.parametrize("draft", [
    "Taylor Swift supera a Beyoncé como la artista más premiada de los MTV VMA 2026; Taylor Swift y Lisa hacen "
    "historia y Madonna reina otra vez: los ganadores de los MTV VMA 2026; Taylor Swift abre su intimidad con Travis "
    "Kelce.",
    "Hoy hay cinco titulares sobre Taylor Swift. Taylor Swift supera a Beyoncé como la artista más premiada de los MTV "
    "VMA 2026; Taylor Swift y Lisa hacen historia y Madonna reina otra vez: los ganadores de los MTV VMA 2026; Taylor "
    "Swift abre su intimidad con Travis Kelce.",
])
def test_headlines_quoted_without_the_feeds_stray_colon_count(draft: str) -> None:
    payload = llm._compose_situation_payload(TAYLOR_READ, "es", TAYLOR)
    assert llm._payload_fact_defect(draft, payload, TAYLOR) == ""


def test_two_headlines_are_still_too_few() -> None:
    payload = llm._compose_situation_payload(TAYLOR_READ, "es", TAYLOR)
    draft = ("Taylor Swift supera a Beyoncé como la artista más premiada de los MTV VMA 2026; Taylor Swift abre su "
             "intimidad con Travis Kelce.")
    assert llm._payload_fact_defect(draft, payload, TAYLOR) == "missing_state"


def test_the_headlines_read_are_the_last_resort() -> None:
    text = llm._deterministic_final(TAYLOR_READ, {"seen": TAYLOR_READ["observed"]}, TAYLOR, "es")
    assert text == (
        "Titulares sobre Taylor Swift: «Taylor Swift supera a Beyoncé como la artista más premiada de los MTV VMA "
        "2026»; «Taylor Swift y Lisa hacen historia y Madonna reina otra vez: los ganadores de los MTV VMA 2026»; "
        "«Dakota Johnson tiene malas noticias para los fans que esperaban ver fotos de la boda de Taylor Swift»."
    )
    assert _compose(["Hoy hay titulares sobre Taylor Swift y su boda."], TAYLOR, "status", TAYLOR_READ) == text


# D-s067 q4: the created item is told with the title the store verified.
def test_three_shortened_titles_end_in_the_created_item() -> None:
    drafts = [
        "He añadido las patatas y los huevos a tu lista de deseos.",
        "He añadido las patatas y los huevos a la lista de deseos creada el 29 de septiembre de 2026.",
        "He añadido las patatas y las patatas y huevos a la lista de deseos.",
    ]
    assert _compose(drafts, PATATAS, "status", PATATAS_CREATED) == "Añadí «patatas y patatas y huevos»."


def test_an_unverified_task_write_is_never_told_as_written() -> None:
    # M107: a write that failed has a final too — the failure, never «Añadí…».
    unverified = {**PATATAS_CREATED, "verified": False, "succeeded": False, "polarity": "failure"}
    assert llm._deterministic_final(unverified, {"seen": unverified["observed"]}, PATATAS, "es") == (
        "No pude anotar la tarea «patatas y patatas y huevos»."
    )
