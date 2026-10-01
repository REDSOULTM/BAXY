"""M105 (2026-10-01): the regressions the independent review of DEV-D v4a found.

1. D-s054/D-s080 (read at 04:45): «El sol se puso a las 19:49 hoy». M99 marked only a sun time already behind the
   reading's clock; one still ahead was left unmarked and told in the past. Both are marked now (``…Passed``
   True/False from ``observedAtLocal``, the place's own clock), and the past told of one still ahead is a defect.
2. D-s047: the PC's media session read nothing playing, the assistant's YouTube tab was not found, and the tab's
   absence replaced the session's read (provider); the reply then said no music played «because no YouTube video was
   opened». Only the tab checked never tells that nothing plays.
3. D-p28-t3: «Hustlers is playing at the Union City theater» with no listing read.
4. D-p24-t5 / D-p24-t4: «I confirm the action will proceed» with nothing run; and the honest «I have not done it yet
   because … failed …» refused as a failure told in talk, which ended in «What specific detail is missing…?».
5. D-p23-t5: «I can add English subtitles to your videos» in a turn that ran nothing.
6. D-p23-t2: «…mentioned in the provided text» (metadiscourse).
7. D-s076: «sentadillas búlgar» (a word cut short).
8. D-p27-t1: «I couldn't find it.» over pages listing films; the draft died on «films» for the pages' «movies».
9. D-w03-t4: the dollar in Colombian pesos in a Chilean conversation (a nationality nobody said).
10. D-w08-t2: the next match of another team (the restatement put another team where the conversation's goes).

No test reads today's date or clock: the weather read carries its own ``observedAtLocal`` and ``faithful_request``
gets ``now``.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from baxy_mind import llm
from baxy_mind.semantic import decider

# ------------------------------------------------------------------ 1. sun times against the read's own clock

_SOUTH = {  # America/Santiago, spring
    "location": "Curico", "country": "Chile", "timezone": "America/Santiago",
    "today": {"date": "2026-10-01", "weekday": "jueves", "sunrise": "07:23", "sunset": "19:49"},
    "tomorrow": {"date": "2026-10-02", "weekday": "viernes", "sunrise": "07:22", "sunset": "19:49"},
}
_NORTH = {  # Europe/Madrid, autumn
    "location": "Madrid", "country": "Spain", "timezone": "Europe/Madrid",
    "today": {"date": "2026-10-01", "weekday": "jueves", "sunrise": "08:02", "sunset": "19:33"},
    "tomorrow": {"date": "2026-10-02", "weekday": "viernes", "sunrise": "08:03", "sunset": "19:31"},
}
_SUNSET_ES = "¿A qué hora se pone el sol hoy?"
_SUNSET_EN = "What time does the sun set today?"
_SUNRISE_ES = "¿A qué hora sale el sol hoy?"


@pytest.mark.parametrize("read", [_SOUTH, _NORTH], ids=["south", "north"])
@pytest.mark.parametrize(("clock", "passed"), [("04:45", False), ("12:00", False), ("21:30", True)])
def test_todays_sunset_is_marked_against_the_reads_own_clock(read: dict, clock: str, passed: bool) -> None:
    seen = llm._project_weather_read({**read, "observedAtLocal": f"2026-10-01T{clock}"}, _SUNSET_ES)
    assert seen["today"]["sunsetPassed"] is passed


@pytest.mark.parametrize("read", [_SOUTH, _NORTH], ids=["south", "north"])
@pytest.mark.parametrize(("clock", "passed"), [("04:45", False), ("12:00", True), ("21:30", True)])
def test_todays_sunrise_is_marked_against_the_reads_own_clock(read: dict, clock: str, passed: bool) -> None:
    seen = llm._project_weather_read({**read, "observedAtLocal": f"2026-10-01T{clock}"}, _SUNRISE_ES)
    assert seen["today"]["sunrisePassed"] is passed


def test_a_read_of_another_day_or_with_no_clock_marks_nothing() -> None:
    for observed in ("2026-09-30T23:10", "", None):
        seen = llm._project_weather_read({**_SOUTH, "observedAtLocal": observed}, _SUNSET_ES)
        assert "sunsetPassed" not in seen["today"]


@pytest.mark.parametrize("read", [_SOUTH, _NORTH], ids=["south", "north"])
def test_before_sunset_the_sunset_is_never_told_in_the_past(read: dict) -> None:
    sunset = read["today"]["sunset"]
    early = llm._project_weather_read({**read, "observedAtLocal": "2026-10-01T04:45"}, _SUNSET_ES)
    payload = {"operation": "weather.current", "seen": early}
    assert llm._weather_fact_defect(f"El sol se puso a las {sunset} hoy.", payload, _SUNSET_ES) == "weather_sun_time_ahead"
    assert llm._weather_fact_defect(f"Hoy el sol se pondrá a las {sunset}.", payload, _SUNSET_ES) == ""
    english = llm._project_weather_read({**read, "observedAtLocal": "2026-10-01T04:45"}, _SUNSET_EN)
    payload_en = {"operation": "weather.current", "seen": english}
    assert llm._weather_fact_defect(f"The sun set at {sunset} today.", payload_en, _SUNSET_EN) == "weather_sun_time_ahead"
    assert llm._weather_fact_defect(f"The sun will set at {sunset} today.", payload_en, _SUNSET_EN) == ""


@pytest.mark.parametrize("read", [_SOUTH, _NORTH], ids=["south", "north"])
def test_after_sunset_the_sunset_is_still_told_in_the_past(read: dict) -> None:
    sunset = read["today"]["sunset"]
    late = llm._project_weather_read({**read, "observedAtLocal": "2026-10-01T21:30"}, _SUNSET_ES)
    payload = {"operation": "weather.current", "seen": late}
    assert llm._weather_fact_defect(f"Hoy el sol se puso a las {sunset}.", payload, _SUNSET_ES) == ""
    assert llm._weather_fact_defect(f"Hoy el sol se pondrá a las {sunset}.", payload, _SUNSET_ES) == "weather_sun_time_passed"


def test_the_writer_is_told_both_marks() -> None:
    assert "With it false, it has not happened yet today" in llm._weather_focus(_SUNSET_EN, english=True)
    assert "Con false aún no llega hoy" in llm._weather_focus(_SUNSET_ES, english=False)


# ------------------------------------------------------------------ 2. only the assistant's tab checked


def _media_failure(error: str) -> dict:
    return {
        "situation": {
            "kind": "failure", "polarity": "failure", "cause": "mission_failed", "stepCount": 0, "steps": [],
            "reason": {"kind": "operation", "operation": "media.status", "polarity": "failure",
                       "verified": False, "succeeded": False, "error": error},
        }
    }


@pytest.mark.parametrize(
    ("draft", "asked"),
    [
        ("No hay música reproduciéndose porque no se ha abierto ningún video de YouTube.", "qué canción suena ahora"),
        ("No suena nada: no encuentro ningún video de YouTube abierto.", "qué canción está sonando ahora"),
        ("Nothing is playing because there is no YouTube video open.", "what song is playing right now"),
    ],
)
def test_the_assistants_tab_missing_never_tells_that_nothing_plays(draft: str, asked: str) -> None:
    assert llm.compose_visible_defect(draft, "error", asked, _media_failure("youtube_tab_not_found")) == (
        "absence_beyond_check"
    )
    # The PC's media session read nothing playing: then it is the truth.
    assert llm.compose_visible_defect(draft, "error", asked, _media_failure("media_session_not_found")) == ""


def test_what_was_checked_is_told_as_checked() -> None:
    draft = "No encontré abierta la pestaña de YouTube que uso, así que no pude leer qué suena ahí."
    assert llm.compose_visible_defect(
        draft, "error", "qué canción está sonando ahora", _media_failure("youtube_tab_not_found"),
    ) == ""
    # The fact the narrator gets says what was checked, not that nothing plays.
    assert "is playing" not in llm._CAUSE_FACT["youtube_tab_not_found"]
    assert "only that tab was checked" in llm._CAUSE_FACT["youtube_tab_not_found"]


# ------------------------------------------------------------------ 3. what a cinema shows, unread


@pytest.mark.parametrize(
    ("reply", "asked", "prior"),
    [
        ("Hustlers is playing at the Union City theater.", "Hustlers is perfect.", ("Look for films in Union City.",)),
        ("Tonight Hustlers is showing at the cinema downtown.", "that one sounds good", ("any movies tonight?",)),
        ("Hustlers está en cartelera en el cine de Union City.", "esa me gusta", ("busca películas en Union City",)),
        ("Hay funciones a las 19:30 y a las 22:00.", "¿y a qué hora?", ("quiero ir al cine a ver Hustlers",)),
    ],
)
def test_a_listing_nobody_read_is_not_stated(reply: str, asked: str, prior: tuple[str, ...]) -> None:
    assert llm.conversation_world_claim(reply, asked, prior) == "unread_showtimes"


@pytest.mark.parametrize(
    ("reply", "asked", "prior"),
    [
        ("I have not checked what is playing at the Union City theater.", "Hustlers is perfect.", ("movies?",)),
        ("No sé qué dan hoy en el cine de Union City.", "esa me gusta", ("busca películas",)),
        # No film or cinema in the conversation.
        ("Messi is playing at Inter Miami this season.", "where does Messi play?", ()),
    ],
)
def test_not_knowing_the_listing_or_another_topic_is_no_listing_claim(
    reply: str, asked: str, prior: tuple[str, ...],
) -> None:
    assert llm.conversation_world_claim(reply, asked, prior) != "unread_showtimes"


# ------------------------------------------------------------------ 4. an act confirmed that nobody ran


@pytest.mark.parametrize(
    "reply",
    [
        "I confirm the action will proceed.",
        "I confirm that the playback will start now.",
        "The action will proceed now.",
        "Te confirmo que la reproducción se hará enseguida.",
        "I'll proceed with it.",
        "Procederé con la reproducción.",
    ],
)
def test_an_act_confirmed_in_a_turn_that_ran_nothing_is_a_settled_plan(reply: str) -> None:
    assert llm.visible_reply_settles_a_plan(reply)
    assert llm.conversation_world_claim(reply, "That is confirmed to proceed.") == "effect_claim"


@pytest.mark.parametrize(
    "reply",
    [
        "If you want, I will proceed with it.",
        "I can't confirm that it will start.",
        "¿Quieres que proceda?",
        "I confirm what you said: you like dramas.",
    ],
)
def test_an_offer_a_question_or_a_confirmation_of_words_settles_nothing(reply: str) -> None:
    assert not llm.visible_reply_settles_a_plan(reply)


def test_the_go_ahead_after_a_failed_act_is_answered_without_a_failure_told() -> None:
    told_failed = (
        "I have not done it yet because the streaming of Hustlers failed because Netflix requires a sign-in on this "
        "PC before playback can begin."
    )
    assert llm._go_ahead_reply_unmet(told_failed, "Yes, do it for me.")
    assert not llm._go_ahead_reply_unmet(
        "I haven't played Hustlers yet: Netflix asks to sign in on this PC first.", "Yes, do it for me.",
    )
    assert llm._go_ahead_reply_unmet("Sure, it is on its way.", "Yes, do it for me.")
    instruction = llm._go_ahead_instruction(told_failed, "en")
    assert "without the words failed, could not or cannot" in instruction
    assert "sin las palabras falló, no pude ni no puedo" in llm._go_ahead_instruction(told_failed, "es")


# ------------------------------------------------------------------ 5. «I can …» in a turn that ran nothing


@pytest.mark.parametrize(
    ("reply", "asked"),
    [
        ("I can add English subtitles to your videos.", "Actually, English subtitles then."),
        ("Puedo ponerle subtítulos en inglés a la película.", "mejor en inglés"),
        ("Sure, I can turn on the kitchen lights.", "and the kitchen lights"),
    ],
)
def test_an_ability_claimed_in_a_turn_that_ran_nothing_is_vetoed(reply: str, asked: str) -> None:
    assert llm.conversation_world_claim(reply, asked) == "claimed_ability"


@pytest.mark.parametrize(
    ("reply", "asked"),
    [
        ("I do not add subtitles to movies.", "Actually, English subtitles then."),
        ("If you want, I can play it on Netflix.", "sounds good"),
        ("I can't add subtitles.", "add subtitles"),
        ("I can explain how subtitles work.", "how do subtitles work?"),
        # The person asked what BAXY can do: the capability answer gives it.
        ("I can play music on Spotify and open your apps.", "what can you do?"),
    ],
)
def test_a_denial_an_offer_or_an_asked_capability_is_no_claimed_ability(reply: str, asked: str) -> None:
    assert llm.conversation_world_claim(reply, asked) != "claimed_ability"


# ------------------------------------------------------------------ 6. «the provided text»


def test_the_provided_text_is_metadiscourse_and_clipped_off_a_not_found() -> None:
    draft = "I could not find specific drama films mentioned in the provided text."
    assert llm._SEARCH_RESULTS_TAIL.sub("", draft).rstrip(" ,;") == "I could not find specific drama films."
    assert llm._SEARCH_MECHANICS.search(llm._reading_fold("Drama films are listed in the provided text.")) is not None
    assert llm._SEARCH_MECHANICS.search(llm._reading_fold("Según el texto proporcionado, es un drama.")) is not None
    assert llm._TASK_METADISCOURSE.search("The venue is not specified in the provided text.") is not None


# ------------------------------------------------------------------ 7. a word cut short


@pytest.mark.parametrize(
    "reply",
    [
        "Lunes: sentadillas con peso.\nViernes: peso muerto rumano y sentadillas búlgar.\nSábado: piernas.",
        "Haz tres series de ejercicios regular, sin pausa.",
    ],
)
def test_a_word_cut_after_a_plural_noun_is_broken(reply: str) -> None:
    assert llm.visible_reply_cuts_a_word(reply)
    assert llm._shaped_conversation_answer_violates_contract(reply, "rutina semanal para ganar músculo", "content_draft")


@pytest.mark.parametrize(
    "reply",
    [
        "Viernes: peso muerto rumano y sentadillas búlgaras.",
        "Tenemos que descansar.",
        "Organiza las tareas del hogar.",
        "Las flexiones con peso son ideales para empezar.",
        "Do three sets of squats regular.",
    ],
)
def test_whole_words_are_not_cut(reply: str) -> None:
    assert not llm.visible_reply_cuts_a_word(reply)


# ------------------------------------------------------------------ 8. a list read is reported, one word paraphrased


def test_titles_the_pages_list_are_reported_with_the_reports_own_noun() -> None:
    payload = {
        "operation": "web.search",
        "seen": {
            "query": "good movies to watch",
            "count": 2,
            "results": [
                {"title": "Most Popular Movies Right Now", "url": "https://example.org/popular",
                 "snippet": "The most popular movies right now, including Paper Lanterns, The Glass Orchard and "
                            "Northbound Tide. See where to watch."},
                {"title": "Recommended Movies", "url": "https://example.org/list",
                 "snippet": "A list of memorable and entertaining movies."},
            ],
            "authority": "duckduckgo_lite_https",
        },
    }
    asked = "Any good movies for me to watch?"
    draft = "You can watch popular films like Paper Lanterns, The Glass Orchard and Northbound Tide."
    assert llm._search_report_unsourced_words(draft, payload, asked) == []
    # Two words of its own are still a claim of its own.
    assert llm._search_report_unsourced_words(
        "Critics adore the hilarious films Paper Lanterns and Northbound Tide.", payload, asked,
    )


# ------------------------------------------------------------------ 9 and 10. what the restatement brought

_NOW = datetime(2026, 10, 1, 4, 45)


def test_a_nationality_nobody_said_is_taken_off_the_restatement() -> None:
    chat = ["lista del super: pan, palta y leche", "Anoté pan, palta y leche.", "ya. dolar hoy?"]
    fidelity = decider.faithful_request("¿Cuánto vale hoy el dólar en pesos colombianos?", "ya. dolar hoy?", chat, now=_NOW)
    assert (fidelity.kind, fidelity.request) == ("trimmed", "¿Cuánto vale hoy el dólar en pesos?")
    assert fidelity.introduced == ("colombianos",)


def test_a_nationality_of_a_country_said_stays() -> None:
    chat = ["estoy de viaje en Colombia", "¡Qué bien!", "ya. dolar hoy?"]
    fidelity = decider.faithful_request("¿Cuánto vale hoy el dólar en pesos colombianos?", "ya. dolar hoy?", chat, now=_NOW)
    assert (fidelity.kind, fidelity.request) == ("kept", "¿Cuánto vale hoy el dólar en pesos colombianos?")


def test_the_team_the_conversation_named_replaces_the_one_the_restatement_brought() -> None:
    chat = [
        "cuanto qedo el america anoche",
        "No se encontró información sobre cuánto quedó el América anoche.",
        "y cuando juega el sigiente",
    ]
    fidelity = decider.faithful_request(
        "¿Cuándo juega el Atlético Nacional el próximo partido?", "y cuando juega el sigiente", chat, now=_NOW,
    )
    assert (fidelity.kind, fidelity.request) == ("carried", "¿Cuándo juega el América el próximo partido?")


def test_a_message_that_names_its_own_subject_keeps_the_person_words() -> None:
    chat = ["cuanto qedo el america anoche", "No se encontró nada sobre el América.", "y cuando juega Toluca el siguiente"]
    fidelity = decider.faithful_request(
        "¿Cuándo juega el Atlético Nacional el siguiente partido?", "y cuando juega Toluca el siguiente", chat, now=_NOW,
    )
    assert fidelity.kind == "person"
