"""Goal v3 paso 5 (A7): the ⚠ of the official-window FINAL and DEV-A window 3, «a verified result can always be said».

Every draft here is the one the run recorded (compose-audit of final-once and devA-window3, 2026-09-28):

- A (FINAL t23/t199/t320): after an action was decided and its arguments came back empty, ambiguous_request asks for
  one short question, and the failure branch vetoed every question as missing_failure.
- B (FINAL t151/t233, DEV-A3 t274): a verified search that answered nothing is «I couldn't find it»; the success
  branch read it as a failure asserted, and even the owner's last resort «I couldn't find it.» died.
- C (DEV-A3 t217 «¿qué hora serà de aquí a doce minutos?»): the payload carries 11:13 (M40) and the guard demanded
  the current 11:01, so the right answer could not be published.
- E1 «spotfy», E2 «operaciones», E3 «(3 de octubre)», E4 «baxy-guardia.txt», E5 Netflix sign-in, E6 «No he podido».
- Last resort: when every draft is vetoed, a verified result is told with its observed values, through the same gate.
"""

from __future__ import annotations

import json

import pytest

from baxy_mind import llm
from baxy_mind.llm import LlmRuntime

AMBIGUOUS = {"situation": {"kind": "failure", "polarity": "failure", "cause": "ambiguous_request"}}

TRAINS = "hey olly i want to get trains to manchester on wednesday"
TRAINS_SEARCH = {
    "kind": "operation", "operation": "web.search", "polarity": "success", "verified": True, "succeeded": True,
    "observed": {"version": 1, "query": "Get train schedules to Manchester on Wednesday.", "count": 5, "results": [
        {"title": "Train Schedules & Timetables | Amtrak", "url": "https://www.amtrak.com/train-schedules-timetables",
         "snippet": "Look up current train schedules for stations and routes across the country."},
        {"title": "Journey Planner | Official Train Ticket Info | National Rail",
         "url": "https://www.nationalrail.co.uk/journey-planner/",
         "snippet": "Plan your rail journey, find train information, and get tickets for destinations across the UK "
                    "with National Rail's easy- to -use planner."},
        {"title": "Train Timetables | National Rail",
         "url": "https://www.nationalrail.co.uk/travel-information/timetables/",
         "snippet": "Whether you're planning a train journey today, next week, or next month, you can always get the "
                    "most up- to -date timetable information here."},
        {"title": "Train Tickets, Schedules & Routes | Amtrak", "url": "https://www.amtrak.com/home",
         "snippet": "Book your train and bus tickets today by choosing from over 30 U.S. train routes and 500 "
                    "destinations in North America."},
        {"title": "Train Timetables | Train Schedule | Avanti West Coast",
         "url": "https://www.avantiwestcoast.co.uk/travel-information/plan-your-journey/timetables",
         "snippet": "Plan your journey with our train timetables for services in the UK. Download train schedules at "
                    "Avanti West Coast to check times & special services."},
    ], "authority": "duckduckgo_lite_https"},
}

LATER_CLOCK = "¿qué hora serà de aquí a doce minutos?"
CLOCK = {
    "kind": "operation", "operation": "system.time", "polarity": "success", "verified": True, "succeeded": True,
    "observed": {"version": 1, "utc": "2026-09-28T14:01:21.9918672+00:00", "localUtcOffsetMinutes": -180},
}

LUIS_MIGUEL = "ponme algo de luis miguel en spotfy"
YOUTUBE = {
    "kind": "operation", "operation": "media.play.youtube", "polarity": "success", "verified": True,
    "succeeded": True,
    "observed": {"version": 1, "provider": "youtube", "query": "luis miguel en spotfy",
                 "title": "Luis Miguel - Hasta Que Me Olvides (En Vivo) - YouTube",
                 "finalUrl": "https://www.youtube.com/watch?v=CMyu2H56DBk", "playbackStatus": "playing",
                 "authority": "youtube_cdp_video_postread"},
}

SAN_ANTONIO = (
    "ok so este weekend me voy a San Antonio con unos friends, like, can you check el weather para el sábado allá?"
)
WEATHER = {
    "kind": "operation", "operation": "weather.current", "polarity": "success", "verified": True, "succeeded": True,
    "observed": {
        "version": 1, "location": "Curico", "region": "Region de Curico", "country": "Chile",
        "locatedBy": "public_ip_address", "observedAtLocal": "2026-09-28T11:15", "timezone": "America/Santiago",
        "temperatureC": 18, "apparentC": 17.8, "humidityPercent": 71, "windKmh": 9.3, "precipitationMm": 0,
        "uvIndex": 5.2, "dewPointC": 12.6, "weatherCode": 0, "condition": "despejado",
        "today": {"date": "2026-09-28", "weekday": "lunes", "maxC": 18.5, "minC": 12.2,
                  "rainProbabilityPercent": 0, "uvIndexMax": 7.2, "sunrise": "07:27", "sunset": "19:47"},
        "tomorrow": {"date": "2026-09-29", "weekday": "martes", "maxC": 18.1, "minC": 11.4,
                     "rainProbabilityPercent": 0, "uvIndexMax": 4.4, "condition": "nublado", "sunrise": "07:26",
                     "sunset": "19:47"},
        "laterDays": [
            {"date": "2026-09-30", "weekday": "miércoles", "condition": "nublado", "maxC": 19.5, "minC": 11.1,
             "rainProbabilityPercent": 0},
            {"date": "2026-10-01", "weekday": "jueves", "condition": "nublado", "maxC": 25.1, "minC": 14.3,
             "rainProbabilityPercent": 2},
            {"date": "2026-10-02", "weekday": "viernes", "condition": "llovizna", "maxC": 19.3, "minC": 12.8,
             "rainProbabilityPercent": 43},
            {"date": "2026-10-03", "weekday": "sábado", "condition": "nublado", "maxC": 18.3, "minC": 10.7,
             "rainProbabilityPercent": 14},
            {"date": "2026-10-04", "weekday": "domingo", "condition": "nublado", "maxC": 17.9, "minC": 11.9,
             "rainProbabilityPercent": 4},
        ],
        "authority": "open_meteo_forecast_v1",
    },
}

NETFLIX = {
    "kind": "failure", "polarity": "failure", "cause": "mission_failed", "stepCount": 0, "steps": [],
    "reason": {"kind": "operation", "operation": "streaming.play.named", "polarity": "failure", "verified": False,
               "succeeded": False, "error": "netflix_authentication_required", "cause": "external_effect_ambiguous",
               "effectUncertain": True},
}

VOLUME = {
    "kind": "operation", "operation": "audio.volume.adjust", "polarity": "success", "verified": True,
    "succeeded": True,
    "observed": {"version": 1, "direction": "down", "amount": 10, "baselineLevel": 50, "level": 40, "muted": True,
                 "authority": "windows_core_audio_output_endpoint_postread"},
}


class _Drafts(LlmRuntime):
    """The recorded drafts stand in for the model, in order; ``timeout_after`` ends the budget like FINAL t323."""

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


def _visible(text: str, intent: str, user_text: str, situation: dict) -> str:
    return llm.compose_visible_defect(text, intent, user_text, {"situation": situation})


def _payload(text: str, user_text: str, situation: dict, language: str) -> str:
    return llm._payload_fact_defect(text, llm._compose_situation_payload(situation, language, user_text), user_text)


# A — the question is the reply to ambiguous_request.
@pytest.mark.parametrize(("user_text", "question"), [
    ("please inform me of any new status updates", "Could you please provide the missing detail about what you want?"),
    ("¿Es el pollen count muy alto afuera?", "¿Qué tipo de información específica necesitas sobre el conteo de polen?"),
    ("perfect, copialo al clipboard", "¿Qué detalle específico falta para que funcione?"),
])
def test_ambiguous_request_is_answered_by_its_question(user_text: str, question: str) -> None:
    assert _visible(question, "error", user_text, AMBIGUOUS["situation"]) == ""


@pytest.mark.parametrize(("user_text", "draft", "reason"), [
    ("please inform me of any new status updates",
     "The task failed because one detail of what the person wants is missing.", "internal_code"),
    ("¿Es el pollen count muy alto afuera?", "No, no he verificado el conteo de polen afuera.", "missing_failure"),
    ("perfect, copialo al clipboard", "No has especificado el detalle faltante que necesitas.", "missing_failure"),
])
def test_ambiguous_request_still_vetoes_what_is_not_a_question(user_text: str, draft: str, reason: str) -> None:
    assert _visible(draft, "error", user_text, AMBIGUOUS["situation"]) == reason


def test_the_clarification_names_the_field_the_app_declares_missing() -> None:
    # The App now reports empty arguments of a decided action as a clarification with missingValue (FINAL t320).
    situation = {"kind": "clarification", "polarity": "pending", "cause": "ambiguous_request", "missingValue": "text"}
    payload = llm._compose_situation_payload(situation, "es", "perfect, copialo al clipboard")
    assert payload["missingValue"] == "text"
    assert _visible("¿Qué texto quieres que copie al portapapeles?", "clarification",
                    "perfect, copialo al clipboard", situation) == ""


# B — a verified search's «not found» is the report, and the owner's last resort passes.
@pytest.mark.parametrize("draft", [
    "I couldn't find it.",
    "I could not find specific train schedules to Manchester on Wednesday in the provided results.",
    "I could not find the train schedules to Manchester on Wednesday.",
])
def test_verified_search_not_found_is_publishable(draft: str) -> None:
    assert _visible(draft, "status", TRAINS, TRAINS_SEARCH) == ""


def test_a_failure_beside_the_not_found_is_still_a_failure_asserted() -> None:
    draft = "I couldn't find train times, and I couldn't open the page."
    assert _visible(draft, "status", TRAINS, TRAINS_SEARCH) == "asserted_failure"


def test_the_english_not_found_last_resort_publishes_after_three_vetoed_drafts() -> None:
    drafts = [
        "None of the returned pages provide specific train schedules to Manchester for Wednesday.",
        "The search returned pages with train timetables.",
        "The search returned pages with train timetables.",
    ]
    text = _Drafts(drafts).compose_user_message(TRAINS, "status", {"situation": TRAINS_SEARCH})
    assert text == "I couldn't find it."


# C — the clock later on.
def test_the_clock_later_on_is_the_answer_to_a_later_clock_question() -> None:
    assert _visible("Serán las 11:13.", "status", LATER_CLOCK, CLOCK) == ""
    assert _payload("Serán las 11:13.", LATER_CLOCK, CLOCK, "es") == ""


@pytest.mark.parametrize("draft", ["Serán las 11:25.", "Serán las 11:24.", "Será las once y veintidós."])
def test_a_clock_summed_twice_is_still_vetoed(draft: str) -> None:
    assert _visible(draft, "status", LATER_CLOCK, CLOCK) == "missing_name"


def test_the_current_clock_question_still_owes_the_current_clock() -> None:
    assert _visible("Son las 11:13.", "status", "¿qué hora es?", CLOCK) != ""
    assert _visible("Son las 11:01.", "status", "¿qué hora es?", CLOCK) == ""


# E1 — «spotfy» is Spotify misspelled, not a name nobody said.
def test_a_misspelled_service_name_is_the_one_the_person_said() -> None:
    assert llm._said_misspelled(LUIS_MIGUEL, "spotify")
    assert not llm._said_misspelled("ponme algo de luis miguel", "spotify")
    draft = "Está sonando «Luis Miguel - Hasta Que Me Olvides (En Vivo) - YouTube» en YouTube, no en Spotify."
    assert _visible(draft, "status", LUIS_MIGUEL, YOUTUBE) != "unmentioned_name"
    assert _visible(draft, "status", "ponme algo de luis miguel", YOUTUBE) == "unmentioned_name"


# E2 — a jargon term is a whole word.
def test_forbidden_terms_are_whole_words() -> None:
    assert not llm._names_forbidden_term("botones para operaciones básicas", "operacion")
    assert llm._names_forbidden_term("la operacion fallo", "operacion")
    assert not llm._names_forbidden_term("a Python toolkit", "tool")
    assert llm._names_forbidden_term("XRouter notes", "router")
    assert llm._names_forbidden_term("resolver el efecto 'abrir'", "el efecto '")


def test_the_gui_answer_with_arithmetic_operations_publishes() -> None:
    draft = (
        "Para crear una interfaz gráfica en Python, puedes usar la librería Tkinter y buscar ejemplos de código que "
        "implementen botones para operaciones básicas y funciones científicas adicionales."
    )
    facts = {"situation": {"kind": "conversation", "polarity": "success"},
             "forbiddenResponseTerms": ["operación", "operacion", "core", "tool"]}
    user = ("Podrías decirme como crear una interfaz sencilla (también conocida como gui) de una calculadora para el "
            "lenguaje de programación Python?")
    assert _Drafts([draft]).compose_user_message(user, "conversation", facts) == draft


# E3 — the date of the day asked is not an invented measurement.
def test_the_day_of_a_read_date_is_not_an_invented_number() -> None:
    draft = (
        "No hay pronóstico de clima para San Antonio, pero en Curicó el sábado (3 de octubre) estará nublado con "
        "una máxima de 18.3 °C, una mínima de 10.7 °C y una probabilidad de lluvia del 14 %."
    )
    assert _payload(draft, SAN_ANTONIO, WEATHER, "es") == ""
    assert _payload(draft.replace("18.3 °C", "3 °C"), SAN_ANTONIO, WEATHER, "es") == "invented_number"


# E4 — a file name inside an observed window title is what was seen.
def test_an_observed_file_name_is_not_an_internal_code() -> None:
    windows = {
        "kind": "operation", "operation": "window.resolve", "polarity": "success", "verified": True,
        "succeeded": True,
        "observed": {"version": 1, "windows": [
            {"processName": "Notepad", "title": "baxy-guardia.txt: Bloc de notas"},
            {"processName": "steamwebhelper", "title": "Steam"},
        ], "count": 2, "observedCount": 2, "complete": True, "totalCount": 2},
    }
    draft = "Estas son las ventanas visibles: Bloc de notas con un archivo llamado baxy-guardia.txt y Steam."
    assert _visible(draft, "status", "Show me mis apps", windows) != "internal_code"
    assert _visible("La operación window.resolve terminó.", "status", "Show me mis apps", windows) == "internal_code"


# E5 — Netflix asks to sign in: that is the cause told, and «ambiguo» is no cut of the English cause.
def test_netflix_sign_in_reaches_the_payload_as_its_cause() -> None:
    payload = llm._compose_situation_payload(NETFLIX, "es", "baxy poné la casa de papel en netflix")
    assert payload["reason"]["cause"] == llm._CAUSE_FACT["netflix_authentication_required"]
    draft = "No pude poner La casa de papel en Netflix porque el efecto externo es ambiguo."
    assert not llm._truncated_fact_word(draft, {"reason": {"cause": "external effect ambiguous"}})


# E6 — «No he podido» is the failure said.
def test_the_perfect_tense_failure_is_a_failure_asserted() -> None:
    assert llm._asserts_failure(
        "No he podido subir el volumen ni oír nada, ya que el cambio no se confirmó después de la acción."
    )
    assert llm._asserts_failure("I haven't been able to raise the volume.")


# Last resort — the verified result is told when every draft is vetoed.
def test_three_vetoed_volume_drafts_end_in_the_observed_level() -> None:
    drafts = ["The volume is muted.", "The volume is muted.", "The volume is muted."]
    text = _Drafts(drafts).compose_user_message("turn it down 10", "status", {"situation": VOLUME})
    assert text == "I turned the volume down to 40%; it is muted."


def test_the_spanish_volume_template_says_the_observed_level() -> None:
    payload = llm._compose_situation_payload(VOLUME, "es", "bajale 10")
    assert llm._deterministic_final(VOLUME, payload, "bajale 10", "es") == "Bajé el volumen a 40 %; está silenciado."


def test_vetoed_youtube_drafts_end_in_the_observed_title() -> None:
    drafts = [
        "No puedo reproducir música de Luis Miguel en Spotify porque estoy conectado a YouTube y no tengo acceso a "
        "otras plataformas.",
        "Luis Miguel está reproduciendo un video en vivo de YouTube, pero no se está accediendo a Spotify.",
        "No he accedido a Spotify ni reproduzco música, solo he iniciado la reproducción de un video de Luis Miguel "
        "en YouTube.",
    ]
    text = _Drafts(drafts).compose_user_message(LUIS_MIGUEL, "status", {"situation": YOUTUBE})
    assert text == "Está sonando «Luis Miguel - Hasta Que Me Olvides (En Vivo) - YouTube»."


def test_a_later_clock_that_ran_out_of_time_is_still_told() -> None:
    text = _Drafts(["Serán las 11:25."], timeout_after=1).compose_user_message(LATER_CLOCK, "status",
                                                                                {"situation": CLOCK})
    assert text == "Serán las 11:13."


def test_the_netflix_sign_in_is_told_as_the_failure_it_was() -> None:
    drafts = ["Listo, está sonando La casa de papel."] * 3
    text = _Drafts(drafts).compose_user_message("baxy poné la casa de papel en netflix", "error",
                                                {"situation": NETFLIX})
    assert text == "No pude poner nada en Netflix: pide iniciar sesión en este PC."


def test_an_unverified_result_has_no_deterministic_final() -> None:
    unverified = {**VOLUME, "verified": False, "succeeded": False, "polarity": "failure"}
    payload = llm._compose_situation_payload(unverified, "es", "bajale 10")
    assert llm._deterministic_final(unverified, payload, "bajale 10", "es") == ""


def test_the_weather_template_names_the_day_asked_from_the_read() -> None:
    payload = llm._compose_situation_payload(WEATHER, "es", SAN_ANTONIO)
    text = llm._deterministic_final(WEATHER, payload, SAN_ANTONIO, "es")
    assert text == "En Curico, el sábado: nublado, de 10,7 a 18,3 °C, 14 % de lluvia."
    assert llm._payload_fact_defect(text, payload, SAN_ANTONIO) == ""


def test_the_last_resort_is_recorded_as_its_own_stage(monkeypatch: pytest.MonkeyPatch) -> None:
    stages: list[tuple[str, bool]] = []
    monkeypatch.setattr(llm, "_capture_compose_stage", lambda **row: stages.append((row["stage"], row["published"])))
    _Drafts(["The volume is muted."]).compose_user_message("turn it down 10", "status", {"situation": VOLUME})
    assert stages[-1] == ("deterministic_fallback", True)
    assert json.dumps(stages)
