"""M58 (2026-09-29, review of the official-window run v3d-final): general repairs, each on the real messages and
payloads of that run (%LOCALAPPDATA%/BAXY/comprension-2026-09-25/window/v3d-final/: RUN.jsonl, turn-audit.jsonl,
compose-audit.jsonl, shell-trace.jsonl and REVIEW.reviewed.jsonl).

1. The place of the conversation. F-p05-t3 «Perdón, encuéntrame cerca de La Puntilla» after «… cerca de La Puntilla,
   El Puerto» was restated without the town (turn-audit request 682) and answered with a car park of San Juan, Puerto
   Rico; F-p06-t3 «Mejor en calle Génova» was told the car parks of Villa del Prado, whose address carries «Madrid»
   only as «Comunidad de Madrid»; F-w15-t1 «me voy a San Antonio … el weather para el sábado allá» read no place in
   its weather clause and the weather of this PC's town (Curicó) was told. F-p07-t1/t2 (Foster City read in
   Michigan) is the geocoder's choice (OpenMeteoWeatherAdapterTests).
2. Alarms and timers that asked back. F-s011 «Reanudar el ejercicio en 5 minutos, mejor en 10 minutos» (request 71:
   decided notification.schedule, the arguments step asked «¿cuándo y en qué formato?»); F-s019 «Cambia la alarma
   despertador de las 8:00 a las 9:00» and F-s044 «change the reminder for the chef's table group from 3 to 4»
   (requests 124 and 278: a plan whose steps asked the time back); F-s095 «Cambia el temporizador a una hora»
   (request 575: the decider asked «¿A qué hora lo cambio?»).
3. What the reply says. F-w05-t4 added «y una tarea más» to three tasks, all named; F-s066 «¿hará bueno para San
   Juan?» lost tomorrow's drizzle at 94 % because «bajo un cielo despejado» was read as «I lower»; F-w06-t2 «no, al
   revés» was told «No se pudo abrir Word…» against the bare correction; F-p05-t1 ended with no answer (the places
   OpenStreetMap read were judged off subject and «No he encontrado…» was not read as «no lo encontré»). F-p03-t1 is
   the shell's check (Baxy.Integration.Tests/M58NotaNoEncontradaTests).
"""

from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta, timezone

import pytest

from baxy_mind import __main__ as mind
from baxy_mind.llm import (
    LlmRuntime,
    _deterministic_final,
    _payload_fact_defect,
    _places_inside_named_place,
)
from baxy_mind.semantic.dialogue import DialogueState
from baxy_mind.semantic.patterns import resolve_explicit_clarification_intent, resolve_explicit_effects
from baxy_mind.semantic.system import _weather_location
from baxy_mind.semantic.temporal import notification_change, timed_task

# ------------------------------------------------------------------ the catalog's schemas (ProductCatalog.cs)

SCHEDULE = {
    "type": "object",
    "properties": {
        "dueUtc": {"type": "string", "maxLength": 64, "x-nonWhitespace": True},
        "kind": {"type": "string", "enum": ["alarm", "reminder"]},
        "recurrence": {"type": "string", "enum": ["daily", "hourly"]},
        "title": {"type": "string", "x-maxUtf8Bytes": 1024, "x-nonWhitespace": True},
    },
    "required": ["dueUtc", "kind", "title"],
    "additionalProperties": False,
}
CANCEL_AT = {
    "type": "object",
    "properties": {
        "hour": {"type": "integer", "minimum": 0, "maximum": 23},
        "kind": {"type": "string", "enum": ["alarm", "reminder"]},
        "minute": {"type": "integer", "minimum": 0, "maximum": 59},
        "period": {"type": "string", "enum": ["am", "pm"]},
    },
    "required": ["hour", "kind"],
    "additionalProperties": False,
}
CANCEL_LATEST = {
    "type": "object",
    "properties": {"kind": {"type": "string", "enum": ["alarm", "reminder"]}},
    "required": ["kind"],
    "additionalProperties": False,
}
WEB_SEARCH = {
    "type": "object",
    "properties": {
        "limit": {"type": "integer", "minimum": 1, "maximum": 20},
        "nearby": {"type": ["boolean", "null"]},
        "query": {"type": "string", "x-maxUtf8Bytes": 2000, "x-nonWhitespace": True},
    },
    "required": ["query"],
    "additionalProperties": False,
}
WEATHER = {
    "type": "object",
    "properties": {"location": {"type": ["string", "null"], "x-maxUtf8Bytes": 128}},
    "required": [],
    "additionalProperties": False,
}
SCHEMAS = {
    "notification.schedule": SCHEDULE,
    "notification.cancel.at": CANCEL_AT,
    "notification.cancel.latest": CANCEL_LATEST,
}
OPERATIONS = (
    "notification.schedule", "notification.cancel.at", "notification.cancel.latest", "notification.list",
    "reminder.create", "reminder.list", "task.list", "calendar.event.create", "web.search", "weather.current",
)


def _minutes_ahead(due_utc: str) -> float:
    due = datetime.fromisoformat(due_utc.replace("Z", "+00:00"))
    return (due - datetime.now(timezone.utc)).total_seconds() / 60


def _plan_arguments(text: str) -> list[tuple[str, dict | None]]:
    """What the plan request builds for a message the readers read (``kind == "plan"`` with expected operations)."""

    effects = resolve_explicit_effects(text, OPERATIONS)
    assert effects is not None
    evidence = mind._restore_evidence_surfaces(text, effects.evidence)
    skeleton = mind._explicit_plan_skeleton(effects.operations, evidence)
    return [
        (step["operation"], mind._ground_explicit_arguments(step["operation"], step["purpose"], SCHEMAS[step["operation"]]))
        for step in skeleton["steps"]
    ]


# ------------------------------------------------------------------ 2. alarms and timers

F_S011 = "Reanudar el ejercicio en 5 minutos, mejor en 10 minutos."
F_S011_RESTATED = "Reanuda el ejercicio en 10 minutos."  # turn-audit request 71


@pytest.mark.parametrize("objective", [F_S011, F_S011_RESTATED])
def test_s011_a_task_at_a_corrected_time_is_a_reminder_at_the_last_time(objective: str) -> None:
    task = timed_task(F_S011)
    assert task is not None and (task.title, task.due) == ("Reanudar el ejercicio", "en 10 minutos")
    arguments = mind._ground_explicit_arguments(
        "notification.schedule", objective, SCHEDULE, history=[{"role": "user", "content": F_S011}],
    )
    assert arguments is not None
    assert arguments["kind"] == "reminder" and arguments["title"].startswith("Reanuda")
    assert 9 < _minutes_ahead(arguments["dueUtc"]) <= 10.1


@pytest.mark.parametrize(
    ("text", "title", "due"),
    [
        ("Recuérdame llamar a Ana en 10 minutos", "llamar a Ana", "en 10 minutos"),
        ("take out the trash in 20 minutes, actually in 30 minutes", "take out the trash", "in 30 minutes"),
        ("sacar la ropa de la lavadora a las seis de la tarde", "sacar la ropa de la lavadora", "a las seis de la tarde"),
    ],
)
def test_the_task_is_what_is_to_be_done_and_the_time_the_last_said(text: str, title: str, due: str) -> None:
    task = timed_task(text)
    assert task is not None and (task.title, task.due) == (title, due)


@pytest.mark.parametrize(
    "text",
    [
        "llamar a mamá en 5 minutos y a papá en 10 minutos",  # two tasks, not a correction
        "¿qué hago en 10 minutos?",
        "pon una alarma en 10 minutos",  # the alarm reader's own
        "en 10 minutos",  # no task
    ],
)
def test_what_is_not_one_task_at_one_time_is_not_read_as_one(text: str) -> None:
    assert timed_task(text) is None


@pytest.mark.parametrize(
    "text",
    [
        "Cambia la alarma despertador de las 8:00 a las 9:00.",  # F-s019
        "Cambia la alarma de las 8:00 a las 9:00.",  # its restatement, request 124
    ],
)
def test_s019_moving_an_alarm_cancels_the_one_at_eight_and_sets_nine(text: str) -> None:
    (cancel, cancelled), (schedule, scheduled) = _plan_arguments(text)
    assert (cancel, cancelled) == ("notification.cancel.at", {"hour": 8, "kind": "alarm"})
    assert schedule == "notification.schedule" and scheduled is not None
    assert scheduled["kind"] == "alarm" and scheduled["title"].startswith("alarma")
    assert datetime.fromisoformat(scheduled["dueUtc"].replace("Z", "+00:00")).astimezone().strftime("%H:%M") == "09:00"


def test_s019_keeps_what_the_alarm_is_for() -> None:
    change = notification_change("Cambia la alarma despertador de las 8:00 a las 9:00.")
    assert change is not None and change.schedule_arguments()["title"] == "alarma despertador"


@pytest.mark.parametrize(
    "text", ["change the reminder for the chef's table group from 3 to 4",
             "Change the reminder for the chef's table group from 3 to 4."],  # F-s044 and request 278
)
def test_s044_moving_a_reminder_cancels_the_one_at_three(text: str) -> None:
    (cancel, cancelled), (schedule, scheduled) = _plan_arguments(text)
    assert (cancel, cancelled) == ("notification.cancel.at", {"hour": 3, "kind": "reminder"})
    change = notification_change(text)
    assert change is not None and change.schedule_arguments() == {
        "dueUtc": "at 4", "kind": "reminder", "title": "reminder for the chef's table group",
    }
    # Neither «3» nor «4» says morning or afternoon: that alone is left to ask (the cancellation matches either).
    assert schedule == "notification.schedule" and scheduled is None


def test_a_part_of_the_day_said_for_the_old_time_is_the_new_ones() -> None:
    (_, cancelled), (_, scheduled) = _plan_arguments("mueve el recordatorio del dentista de las 3 de la tarde a las 5")
    assert cancelled == {"hour": 3, "kind": "reminder", "period": "pm"}
    assert scheduled is not None and scheduled["title"] == "recordatorio del dentista"
    assert datetime.fromisoformat(scheduled["dueUtc"].replace("Z", "+00:00")).astimezone().hour == 17


def test_s095_a_timer_set_to_an_hour_is_an_hour_from_now() -> None:
    (cancel, cancelled), (schedule, scheduled) = _plan_arguments("Cambia el temporizador a una hora.")
    assert (cancel, cancelled) == ("notification.cancel.latest", {"kind": "alarm"})
    assert schedule == "notification.schedule" and scheduled is not None
    assert (scheduled["kind"], scheduled["title"]) == ("alarm", "temporizador")
    assert 59 < _minutes_ahead(scheduled["dueUtc"]) <= 60.1


@pytest.mark.parametrize("text", ["cambia el fondo de pantalla a azul", "cambia la alarma", "change the channel to 4"])
def test_other_changes_are_not_a_notification_moved(text: str) -> None:
    assert notification_change(text) is None


def test_s040_the_plural_alarms_rule_of_2026_09_24_is_unchanged() -> None:
    # «Cancela las alarmas, por favor.» still asks which one (uso real 2026-09-24, owner's rule); M58 only reports it.
    asked = resolve_explicit_clarification_intent("Cancela las alarmas, por favor.", OPERATIONS)
    assert asked is not None and asked.missing_fields == ("which_alarm",)


# ------------------------------------------------------------------ 1. the place of the conversation

F_P05 = [
    {"role": "user", "content": "Encuentra aparcamiento en Plaza del Polvorista"},
    {"role": "assistant", "content": "[sin respuesta publicada: composition_failed: no_response;retry_exhausted]"},
    {"role": "user", "content": "Encuentrame aparcamiento cerca de La Puntilla, El Puerto"},
    {"role": "assistant", "content": "Hay aparcamientos en Avenida de la Bajamar, Calle Alhaja, Calle Pescadores, Calle "
                                     "Tórtola y Ronda de Las Dunas en El Puerto de Santa María."},
    {"role": "user", "content": "Perdón, encuentrame cerca de La Puntilla"},
]
F_P06 = [
    {"role": "user", "content": "Aparcar en Plaza de las Salesas"},
    {"role": "assistant", "content": "Eso no lo hago: no aparcas en Plaza de las Salesas."},
    {"role": "user", "content": "¿Podrías buscar aparcamiento en la Plaza de las Salesas en Madrid?"},
    {"role": "assistant", "content": "Los aparcamientos en esa zona están en la Calle de Fernando VI, Calle de Doña "
                                     "Bárbara de Braganza, Calle de Regueros, Calle de Orellana o Calle de Campoamor."},
    {"role": "user", "content": "Mejor en calle Génova"},
]


def test_p05_t3_the_same_place_keeps_the_town_said_with_it() -> None:
    # Request 682 restated «Encuentrame aparcamiento cerca de La Puntilla.» and the search reached San Juan.
    placed = mind._with_conversation_place(
        "web.search", {"query": "Encuentrame aparcamiento cerca de La Puntilla."}, F_P05, WEB_SEARCH,
    )
    assert placed == {"query": "Encuentrame aparcamiento cerca de La Puntilla, El Puerto."}


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("aparcamiento en calle Génova", "aparcamiento en calle Génova, Madrid"),
        # The decider's restatement of F-p06-t3 (request 699) already carried the town: nothing is added.
        ("aparcamiento en la calle Génova en Madrid", "aparcamiento en la calle Génova en Madrid"),
        # Another town said is what is searched; the conversation's never replaces it.
        ("aparcamiento en Sevilla", "aparcamiento en Sevilla"),
        ("aparcamiento en la calle Sierpes, Sevilla", "aparcamiento en la calle Sierpes, Sevilla"),
    ],
)
def test_p06_a_street_named_alone_is_in_the_town_of_the_conversation(query: str, expected: str) -> None:
    assert mind._with_conversation_place("web.search", {"query": query}, F_P06, WEB_SEARCH) == {"query": expected}


def test_a_place_near_this_pc_is_not_placed_by_the_conversation() -> None:
    near = {"query": "aparcamiento cerca de La Puntilla", "nearby": True}
    assert mind._with_conversation_place("web.search", near, F_P05, WEB_SEARCH) == near


def test_the_weather_of_a_town_said_before_with_its_region_keeps_the_region() -> None:
    history = [
        {"role": "user", "content": "¿Qué tiempo hace en San Juan, Puerto Rico?"},
        {"role": "assistant", "content": "En San Juan hay 28,5 °C."},
        {"role": "user", "content": "¿y mañana en San Juan?"},
    ]
    assert mind._with_conversation_place("weather.current", {"location": "San Juan"}, history, WEATHER) == {
        "location": "San Juan, Puerto Rico",
    }
    assert mind._with_conversation_place("weather.current", {"location": "Lima"}, history, WEATHER) == {
        "location": "Lima",
    }


F_W15_T1 = "ok so este weekend me voy a San Antonio con unos friends, like, can you check el weather para el sábado allá?"


def test_w15_t1_there_is_the_town_the_person_is_going_to() -> None:
    # The arguments step read {"location": None} from the weather clause and the provider located this PC.
    assert mind._ground_explicit_arguments("weather.current", F_W15_T1, WEATHER) == {"location": "San Antonio"}
    assert _weather_location("¿qué tiempo hace allá?") is None
    assert _weather_location("I must verify the weather in Foster City later today.") == "Foster City"


F_P06_T3 = "Mejor en calle Génova"
F_P06_T3_PAYLOAD = {  # compose-audit trace t118
    "seen": {"query": "aparcamiento en la calle Génova en Madrid", "count": 3, "results": [
        {"title": "parking", "url": "https://www.openstreetmap.org/way/384660237",
         "snippet": "Calle Príncipe de Asturias, Villa del Prado, Comunidad de Madrid, 28630, España"},
        {"title": "parking", "url": "https://www.openstreetmap.org/way/923728903",
         "snippet": "Avenida de España, Villa del Prado, Comunidad de Madrid, 28630, España"},
        {"title": "parking", "url": "https://www.openstreetmap.org/way/736899529",
         "snippet": "Avenida del Alamín, Villa del Prado, Comunidad de Madrid, 28630, España"},
    ], "authority": "openstreetmap_nominatim"},
    "operation": "web.search",
}
F_P06_T3_SITUATION = {
    "kind": "operation", "operation": "web.search", "polarity": "success", "verified": True, "succeeded": True,
    "observed": dict(F_P06_T3_PAYLOAD["seen"], version=1),
}


def test_p06_t3_the_car_parks_of_villa_del_prado_are_not_madrid_s() -> None:
    assert _places_inside_named_place(F_P06_T3_PAYLOAD) == []
    assert _deterministic_final(F_P06_T3_SITUATION, F_P06_T3_PAYLOAD, F_P06_T3, "es") == ""
    published = "Encontré: Calle Príncipe de Asturias, Avenida de España y Avenida del Alamín."
    assert _payload_fact_defect(published, F_P06_T3_PAYLOAD, F_P06_T3) == "search_report_off_subject"
    # The run's first draft is then what fits.
    assert _payload_fact_defect("No encontré aparcamiento en la calle Génova en Madrid.", F_P06_T3_PAYLOAD, F_P06_T3) == ""


# ------------------------------------------------------------------ 3. what the reply says


class _Writer(LlmRuntime):
    def __init__(self, drafts: list[str]) -> None:
        self._gguf = None
        self.drafts = list(drafts)
        self.requests: list[dict] = []

    def _post(self, payload: dict, **_kwargs: object) -> dict:
        self.requests.append(copy.deepcopy(payload))
        return {"choices": [{"message": {"content": self.drafts.pop(0)}, "finish_reason": "stop"}]}


F_W05_T4 = "genial tío oye y aparte de eso qué más tengo pendiente"
F_W05_T4_SITUATION = {  # compose-audit trace of F-w05-t4
    "kind": "operation", "operation": "task.list", "polarity": "success", "verified": True, "succeeded": True,
    "observed": {"tasks": [
        {"taskId": "878d5a5e-433a-45db-928c-8f13807ccf28", "title": "palta y pisco", "completed": False,
         "deleted": False, "updatedAtUtc": "2026-09-29T02:16:56.1892993+00:00", "version": 1},
        {"taskId": "b7f9d1b2-db9c-4908-bbf3-b5358460af06", "title": "ice cream", "completed": False, "deleted": False,
         "updatedAtUtc": "2026-09-29T02:14:43.1251282+00:00", "version": 1},
        {"taskId": "0a8c0cb6-6edb-45bc-a420-f55eaef1bcf5", "title": "ice cream", "completed": False, "deleted": False,
         "updatedAtUtc": "2026-09-29T02:14:39.3771456+00:00", "version": 1},
    ], "count": 3, "mode": "tasks", "limit": 20},
}
F_W05_T4_PAYLOAD = {"seen": F_W05_T4_SITUATION["observed"], "operation": "task.list"}
F_W05_T4_PUBLISHED = 'Tienes pendientes "palta y pisco", "ice cream" (2 veces) y una tarea más.'


@pytest.mark.parametrize(
    ("reply", "defect"),
    [
        (F_W05_T4_PUBLISHED, "listing_wrong_count"),
        ('Tienes 4 tareas: "palta y pisco" y "ice cream".', "listing_wrong_count"),
        ('Tienes pendientes "palta y pisco" e "ice cream" (2 veces).', ""),
        ('Tienes 3 tareas: "palta y pisco" y "ice cream" dos veces.', ""),
    ],
)
def test_w05_t4_how_many_tasks_there_are_is_how_many_were_read(reply: str, defect: str) -> None:
    assert _payload_fact_defect(reply, F_W05_T4_PAYLOAD, F_W05_T4) == defect


def test_w05_t4_three_invented_counts_end_in_the_tasks_read() -> None:
    writer = _Writer([F_W05_T4_PUBLISHED] * 3)
    reply = writer.compose_user_message(F_W05_T4, "status", {"situation": json.dumps(F_W05_T4_SITUATION)})
    assert reply == "Tienes pendientes «palta y pisco» y «ice cream» (2 veces)."


F_S066 = "¿hará bueno para San Juan?"
F_S066_SITUATION = {  # compose-audit trace of F-s066 (laterDays left out: the question names no later day)
    "kind": "operation", "operation": "weather.current", "polarity": "success", "verified": True, "succeeded": True,
    "observed": {
        "version": 1, "location": "San Juan", "country": "", "locatedBy": "named_place_geocoded",
        "observedAtLocal": "2026-09-28T22:00", "timezone": "America/Puerto_Rico", "temperatureC": 28.5,
        "apparentC": 33.3, "humidityPercent": 79, "windKmh": 11.3, "precipitationMm": 0, "uvIndex": 0,
        "dewPointC": 24.5, "weatherCode": 0, "condition": "despejado",
        "today": {"date": "2026-09-28", "weekday": "lunes", "maxC": 30.7, "minC": 25.8, "rainProbabilityPercent": 34,
                  "uvIndexMax": 7.8, "sunrise": "06:14", "sunset": "18:15"},
        "tomorrow": {"date": "2026-09-29", "weekday": "martes", "maxC": 29, "minC": 26.2, "rainProbabilityPercent": 94,
                     "uvIndexMax": 8.4, "condition": "llovizna", "sunrise": "06:14", "sunset": "18:14"},
        "airQuality": {"usAqi": 23, "category": "buena", "pm25": 3.2, "pm10": 5.1},
        "authority": "open_meteo_forecast_v1",
    },
}
F_S066_PAYLOAD = {"seen": {k: v for k, v in F_S066_SITUATION["observed"].items() if k != "version"},
                  "operation": "weather.current"}
F_S066_DRAFTS = [  # the three drafts of the run, all vetoed as reversed_result
    "En San Juan hace 28.5 °C bajo un cielo despejado y mañana lloverá con 94 % de probabilidad.",
    "Hace 28.5°C bajo un cielo despejado en San Juan, con lluvia probable al 34% hoy y al 94% mañana.",
    "En San Juan hoy hace 28.5 °C bajo un cielo despejado, y mañana lloverá con 94 % de probabilidad bajo 29 °C.",
]


@pytest.mark.parametrize("draft", F_S066_DRAFTS)
def test_s066_under_a_clear_sky_is_not_i_lower(draft: str) -> None:
    assert _payload_fact_defect(draft, F_S066_PAYLOAD, F_S066) == ""


def test_s066_the_first_draft_of_the_run_is_published() -> None:
    writer = _Writer(list(F_S066_DRAFTS))
    assert writer.compose_user_message(F_S066, "status", {"situation": json.dumps(F_S066_SITUATION)}) == F_S066_DRAFTS[0]


def test_s066_asked_in_the_future_the_reply_carries_tomorrow() -> None:
    assert _payload_fact_defect("Hace 28.5°C en San Juan.", F_S066_PAYLOAD, F_S066) == "missing_state"
    assert _deterministic_final(F_S066_SITUATION, F_S066_PAYLOAD, F_S066, "es") == (
        "En San Juan hay 28,5 °C ahora, despejado; mañana: llovizna, de 26,2 a 29 °C, 94 % de lluvia."
    )
    # The weather now, asked in the present, is still the weather now.
    assert _deterministic_final(F_S066_SITUATION, F_S066_PAYLOAD, "¿qué tiempo hace en San Juan?", "es") == (
        "En San Juan hay 28,5 °C ahora, despejado."
    )


def test_i_lower_is_still_a_claim_over_a_read() -> None:
    claim = "Bajo el brillo; en San Juan hay 28,5 °C y mañana llovizna al 94 %."
    assert _payload_fact_defect(claim, F_S066_PAYLOAD, F_S066) == "reversed_result"


F_W06_T2_SITUATION = {  # compose-audit trace t162
    "kind": "failure", "polarity": "failure", "cause": "mission_failed", "stepCount": 0, "steps": [],
    "reason": {"kind": "operation", "operation": "window.resolve", "polarity": "failure", "verified": False,
               "succeeded": False, "error": "window_not_found", "target": ["Word", "Google Chrome"]},
}
F_W06_T2_RESTATED = "Coloca la ventana de Word en la mitad derecha y la de Chrome en la mitad izquierda."  # request 912


def test_w06_t2_a_failed_mission_is_told_against_the_request_decided() -> None:
    state = DialogueState()
    state.expect(F_W06_T2_RESTATED, ["window.snap"])
    assert state.understood("no, al revés", F_W06_T2_SITUATION) == F_W06_T2_RESTATED
    # With no turn decided, the person's text stays.
    assert DialogueState().understood("no, al revés", F_W06_T2_SITUATION) == "no, al revés"


F_P05_T1 = "Encuentra aparcamiento en Plaza del Polvorista"
F_P05_T1_SITUATION = {  # compose-audit trace t113
    "kind": "operation", "operation": "web.search", "polarity": "success", "verified": True, "succeeded": True,
    "observed": {"version": 1, "query": "aparcamiento en Plaza del Polvorista", "count": 5, "results": [
        {"title": "parking", "url": "https://www.openstreetmap.org/way/301754179",
         "snippet": "Avenida de la Bajamar, Valdelagrana, El Puerto de Santa María, Bahía de Cádiz, Cádiz, Andalucía, "
                    "11500, España"},
        {"title": "parking", "url": "https://www.openstreetmap.org/way/952407272",
         "snippet": "Avenida de Valdelagrana, Las Viñas, Valdelagrana, El Puerto de Santa María, Bahía de Cádiz, Cádiz, "
                    "Andalucía, 11500, España"},
        {"title": "parking", "url": "https://www.openstreetmap.org/way/301734891",
         "snippet": "Calle Brújula, Valdelagrana, El Puerto de Santa María, Bahía de Cádiz, Cádiz, Andalucía, 11500, "
                    "España"},
        {"title": "Parking Calderón", "url": "https://www.openstreetmap.org/way/237016675",
         "snippet": "Parking Calderón, Calle Ribera del Río, Sudamérica, El Puerto de Santa María, Bahía de Cádiz, "
                    "Cádiz, Andalucía, 11500, España"},
        {"title": "parking", "url": "https://www.openstreetmap.org/way/952407268",
         "snippet": "Calle Río Majaceite, Las Viñas, Valdelagrana, El Puerto de Santa María, Bahía de Cádiz, Cádiz, "
                    "Andalucía, 11500, España"},
    ], "authority": "openstreetmap_nominatim"},
}
F_P05_T1_DRAFTS = [  # the run's three drafts
    "No encontré aparcamiento en Plaza del Polvorista.",
    "En los resultados no se menciona Plaza del Polvorista, así que no he encontrado aparcamiento allí.",
    "No he encontrado aparcamiento en Plaza del Polvorista en los resultados.",
]


def test_p05_t1_the_places_read_around_the_square_are_the_answer() -> None:
    writer = _Writer(list(F_P05_T1_DRAFTS))
    reply = writer.compose_user_message(F_P05_T1, "status", {"situation": json.dumps(F_P05_T1_SITUATION)})
    assert reply == "Encontré: Avenida de la Bajamar, Avenida de Valdelagrana y Calle Brújula."
    payload = {"seen": {k: v for k, v in F_P05_T1_SITUATION["observed"].items() if k != "version"},
               "operation": "web.search"}
    # «No he encontrado …» over the places read is the same denial as «No encontré …».
    assert _payload_fact_defect("No he encontrado aparcamiento en Plaza del Polvorista.", payload, F_P05_T1) == (
        "search_places_denied"
    )
