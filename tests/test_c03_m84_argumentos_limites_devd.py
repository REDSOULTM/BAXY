"""M84 (2026-09-30, independent review of the official-window DEV-D run v3o): arguments and limits.

Evidence: %LOCALAPPDATA%/BAXY/comprension-2026-09-25/window/v3o-devD/ (REVIEW.reviewed.jsonl, turn-audit.jsonl,
compose-audit.jsonl, RUN.jsonl, run.map.json; trace = «t» + ordinal). Each test replays the recorded message, the
decider's recorded restatement and BAXY's recorded reply or verified observation of one flagged row:

1. A music service BAXY does not play on (s050 «Reproduce mi estación de Pandora Sensación de comodidad»): M80's limit
   contract held, but the station reader read it as YouTube music and the explicit contract won; «Pandora & Jordi»
   played. The play readers now leave a service named where a service stands; «música de Pandora» is the band.
2. The date a day fell on (s003 «El finde pasado, ¿en qué cayó?» → last weekend's weather): «caer en» asks the date.
3. Where a relative lives (s020 «It's going to rain en la casa de mamá?» → «No tengo información…»): the statement
   with a question mark is the forecast asked, and «mamá» is a person, not a town; where she lives is asked.
4. A moment counted from the one BAXY gave (w08-t3 «ponme recordatorio una ora antes d ese partido» → «¿Cuándo es ese
   partido?»; w02-t3 «ponme una alarma media hora antes de eso» → «Pon una alarma a las 10:30.») and the place said as
   «allá» (w02-t2 «y si allá son las 10 de la mañana acá qué hora es» → no reply): counted and named here.
5. False limits: s107 «para de repetir lo que digo» (echo mode), p01-t3 «no, cancel», p14-t3 «Cancelar foto».
6. Missing limits: s092 «enciende la repetición», s006 «confirmen el pedido», s122 «How much is my phone, I mean my
   electric bill?», p02-t1 «Saca foto ahora» (a screenshot was taken), s094 «Snap a pic after 10 seconds, no, 20
   seconds.» (an alarm was asked about), s018 «ha comentado alguien en mi comentario», s115 «my facebook update in
   every three hour should be available».
"""

from __future__ import annotations

from datetime import date

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind import llm
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import decider, dialogue
from baxy_mind.semantic.conversation import asks_to_order, stable_no_effect
from baxy_mind.semantic.network import relative_calendar_days
from baxy_mind.semantic.patterns import (
    _fold,
    _has_contradictory_correction,
    camera_photo_request,
    echo_mode_request,
    known_unsupported_effect_request,
    resolve_explicit_clarification_intent,
    resolve_explicit_effects,
    unserved_personal_request,
)
from baxy_mind.semantic.system import weather_place_known_only_through_someone
from baxy_mind.semantic.temporal import anchored_offset_request

MUSIC = ("media.play.query", "media.play.youtube", "media.play.exact", "media.control", "app.open")
SCHEDULE = ("notification.schedule", "reminder.create", "calendar.event.create", "system.time", "weather.current")


# ------------------------------------------------------------------ 1. a music service not offered


@pytest.mark.parametrize(
    "text",
    [
        "Reproduce mi estación de Pandora Sensación de comodidad",  # M84 (DEV-D v3o s050)
        "I need Pandora to play me a birthday song.",  # M80 (DEV-D v3m s069)
        "pon música en Deezer",
        "play my rock station on pandora",
        "open pandora and play top hits",
    ],
)
def test_music_on_a_service_not_offered_is_not_played_elsewhere(text: str) -> None:
    assert resolve_explicit_effects(text, MUSIC) is None
    assert known_unsupported_effect_request(text, MUSIC)


def test_the_pandora_station_turn_is_the_limit() -> None:
    # turn-audit request 292: the limit was decided, then the explicit contract replaced it with media.play.youtube.
    model = _Decider("x", "action", ("media.play.youtube",))
    result = _first("Reproduce mi estación de Pandora Sensación de comodidad", model)
    assert result["kind"] == "conversation" and result["conversationKind"] == "unsupported"
    assert result["effectOperations"] == [] and model.decisions == 0


def test_the_band_named_like_a_service_is_still_played() -> None:
    # «música de Pandora» names the Mexican trio; played on YouTube like any music named without a provider.
    intent = resolve_explicit_effects("pon música de pandora", MUSIC)
    assert intent is not None and intent.operations == ("media.play.youtube",)
    assert not known_unsupported_effect_request("pon música de pandora", MUSIC)
    assert not known_unsupported_effect_request("abre Tidal", MUSIC)
    spotify = resolve_explicit_effects("play a birthday song on Spotify", MUSIC)
    assert spotify is not None and spotify.operations == ("media.play.query",)


# ------------------------------------------------------------------ 2. the date a day fell on


@pytest.mark.parametrize(
    "text",
    ["El finde pasado, ¿en qué cayó?", "¿En qué cayó el fin de semana pasado?"],  # s003 and its restatement
)
def test_the_date_a_day_fell_on_is_the_calendar(text: str) -> None:
    # Wednesday 30 September 2026, the day of the run (turn-audit request 20, observed utc 2026-09-30).
    assert relative_calendar_days(text, date(2026, 9, 30)) == (date(2026, 9, 26), date(2026, 9, 27))
    intent = resolve_explicit_effects(text, SCHEDULE)
    assert intent is not None and intent.operations == ("system.time",)


def test_what_falls_on_a_day_of_something_else_is_not_the_calendar() -> None:
    assert relative_calendar_days("¿en qué cae el partido?", date(2026, 9, 30)) == ()
    assert relative_calendar_days("¿en qué cae el próximo lunes?", date(2026, 9, 30)) == (date(2026, 10, 5),)


# ------------------------------------------------------------------ 3. where a relative lives


@pytest.mark.parametrize(
    "text",
    ["It's going to rain en la casa de mamá?", "¿va a llover en la casa de mamá?", "is it going to rain at mom's?"],
)
def test_the_weather_where_a_relative_lives_asks_where(text: str) -> None:
    assert weather_place_known_only_through_someone(text)
    asked = resolve_explicit_clarification_intent(text, SCHEDULE)
    assert asked is not None and asked.operations == ("weather.current",) and asked.missing_fields == ("location",)
    # M84 (DEV-D v3o s020): no reader read the weather, and the hypothesis veto («going to») refused it; the weather
    # read the readers prove now goes before that veto (``_decide_turn_result``: the clarification first).
    intent = resolve_explicit_effects(text, SCHEDULE)
    assert intent is not None and intent.operations == ("weather.current",)


def test_the_turns_ask_where_and_read_the_calendar() -> None:
    # turn-audit request 121: «unsupported» (the hypothesis veto); request 20: the decider read the weather.
    asked = _first("It's going to rain en la casa de mamá?", _Decider("x", "limit"))
    assert asked["kind"] == "clarify" and asked["missingFields"] == ["location"]
    read = _first("El finde pasado, ¿en qué cayó?", _Decider("¿En qué cayó el fin de semana pasado?", "action",
                                                          ("weather.current",)))
    assert read["kind"] == "action" and read["operation"] == "system.time"


ROSARIO = (
    "Che, mañana viajo temprano a Rosario a ver a mi vieja y no sé qué llevar de ropa, ¿cómo va a estar el clima allá?"
)


def test_not_knowing_takes_back_nothing() -> None:
    # M84 (DEV-D v3o w04-t1): turn-audit request 1368 failed twice on the compound veto («y no sé» read as a
    # revocation) and the recovery asked the person which clothes to take.
    assert not _has_contradictory_correction(_fold(ROSARIO), SCHEDULE)
    assert _has_contradictory_correction(_fold("abre chrome y no lo cierres"), ("app.open", "app.close"))
    assert _has_contradictory_correction(_fold("pon la alarma a las 7, no, mejor no"), SCHEDULE)
    result = _first(ROSARIO, _Decider("x", "clarify"))
    assert result["kind"] == "action" and result["operation"] == "weather.current"


def test_a_town_after_the_relative_is_the_place_and_a_statement_asks_nothing() -> None:
    assert not weather_place_known_only_through_someone("¿va a llover en casa de mamá en Lima?")
    intent = resolve_explicit_effects("It's going to rain in Santiago?", SCHEDULE)
    assert intent is not None and intent.operations == ("weather.current",)
    assert resolve_explicit_effects("It's going to rain, so I stay home.", SCHEDULE) is None


# ------------------------------------------------------------------ 4. a moment counted from the one BAXY gave

# RUN.jsonl D-w08-t2, BAXY's reply before w08-t3.
AMERICA = "América juega este 27 de septiembre de 2026 contra Necaxa a las 21:00 horas."


def test_an_hour_before_the_match_just_given() -> None:
    anchored = anchored_offset_request("ponme recordatorio una ora antes d ese partido", AMERICA)
    assert anchored == "ponme recordatorio este 27 de septiembre de 2026 a las 20:00 para el partido"  # M93: what it is for stays
    intent = resolve_explicit_effects(anchored, SCHEDULE)
    assert intent is not None and intent.operations == ("reminder.create",)


def test_half_an_hour_before_the_time_here() -> None:
    # w02-t1's verified read (compose-audit t254): Madrid +120, this PC −180. «allá» is Madrid.
    placed = dialogue.place_substituted("y si allá son las 10 de la mañana acá qué hora es", "baxy qué hora es en madrid")
    assert placed == "y si en Madrid son las 10 de la mañana acá qué hora es"
    observed = {
        "version": 1, "utc": "2026-09-30T17:49:10.8891593+00:00", "localUtcOffsetMinutes": -180,
        "place": {"name": "Madrid", "country": "España", "timeZone": "Europe/Madrid", "utcOffsetMinutes": 120,
                  "authority": "named_place_geocoded"},
    }
    facts = llm._place_clock_facts(observed, placed, "es")
    assert (facts["given"], facts["givenAt"], facts["clock"], facts["clockAt"]) == ("10:00", "Madrid", "05:00", "aquí")
    # The reply tells both clocks; «eso» is the one of here.
    reply = f"Si en Madrid son las {facts['given']}, {facts['clockAt']} son las {facts['clock']}."
    assert anchored_offset_request("ponme una alarma media hora antes de eso", reply) == "ponme una alarma a las 04:30"


@pytest.mark.parametrize(
    ("text", "reply"),
    [
        ("ponme una alarma en media hora", "Son las 19:49."),  # from now, not from something said
        ("ponme una alarma media hora antes de eso", "Hace 19 grados."),  # no moment given
        ("ponme una alarma una hora antes de eso", "Son las 00:30."),  # the day before
    ],
)
def test_nothing_is_counted_without_one_moment(text: str, reply: str) -> None:
    assert anchored_offset_request(text, reply) is None


class _Decider:
    """The contextual decider of v3o: the recorded restatement and decision (turn-audit)."""

    def __init__(self, request: str, decision: str, operations: tuple[str, ...] = ()) -> None:  # noqa: D107
        self.decided = decider.ContextDecision(request=request, decision=decision, operations=operations, question="")
        self.decisions = 0
        self.chats = 0

    def decide_in_context(self, *_args: object, **_kwargs: object) -> decider.ContextDecision:
        self.decisions += 1
        return self.decided

    def chat(self, *_args: object, **_kwargs: object) -> tuple[str, list[object]]:
        self.chats += 1
        return "Vale.", []

    @staticmethod
    def detect_response_language(_text: str) -> str:
        return "es"

    @staticmethod
    def operation_is_the_requested_effect(*_args: object, **_kwargs: object) -> bool:
        return False

    @staticmethod
    def clarify_after_turn_failure(*_args: object, **_kwargs: object) -> str:
        return "What should I add to your swimming list?"

    @staticmethod
    def formulate_explicit_clarification_question(*_args: object, **_kwargs: object) -> str:
        return "¿Dónde?"

    @staticmethod
    def public_lookup_requested(_text: str) -> bool:
        return False

    @staticmethod
    def _verify_semantic_effect_shape(_text: str) -> tuple[str, str]:
        return "no_effect", "zero"

    @staticmethod
    def consume_deferred_response_language(_text: str) -> tuple[bool, str | None]:
        return True, "es"

    @staticmethod
    def retire_deferred_response_language(_text: str) -> None:
        return None


def _tool(operation: str) -> dict[str, object]:
    return {
        "type": "function",
        "function": {
            "name": operation.replace(".", "_"),
            "canonical_name": operation,
            "description": f"Authenticated catalog leaf {operation}.",
            "risk": "read_only",
            "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        },
    }


TOOLS = (*SCHEDULE, *MUSIC, "task.create", "web.search", "capture.screenshot")
# Every session of the run opened with BAXY's welcome, a question.
WELCOME = [("assistant", "Hola, soy BAXY. ¿En qué puedo ayudarte hoy?")]


def _first(text: str, model: _Decider) -> dict[str, object]:
    tools = {name: _tool(name) for name in TOOLS}
    return sidecar._prepare_turn_result(
        {"id": "m84", "text": text, "history": [{"role": r, "content": c} for r, c in WELCOME]
         + [{"role": "user", "content": text}]},
        llm=model,
        planner_catalog=PlannerCatalog(list(tools.values())),
        encoder=lambda _texts: (),
        tool_by_name=tools,
    )


def _decided(text: str, history: list[tuple[str, str]], model: _Decider) -> dict[str, object]:
    tools = [_tool(name) for name in TOOLS]
    turns = [{"role": role, "content": content} for role, content in history]
    return sidecar._context_decided_result(
        {"id": "m84", "text": text, "history": [*turns, {"role": "user", "content": text}]},
        llm=model,
        planner_catalog=PlannerCatalog(tools),
    )


def test_the_decider_does_not_count_the_moment() -> None:
    # turn-audit request 1467: «Ponme un recordatorio mañana a las 20:00 para el partido de América.», rejected.
    model = _Decider("Ponme un recordatorio mañana a las 20:00 para el partido de América.", "action",
                     ("notification.schedule",))
    history = [("user", "cuanto qedo el america anoche"), ("assistant", "No encontré cuánto quedó el america anoche."),
               ("user", "y cuando juega el sigiente"), ("assistant", AMERICA)]
    result = _decided("ponme recordatorio una ora antes d ese partido", history, model)
    assert result["kind"] == "action" and result["operation"] == "reminder.create"
    assert result["objective"] == "ponme recordatorio este 27 de septiembre de 2026 a las 20:00 para el partido"  # M93


def test_there_is_the_place_just_asked_and_the_decider_is_not_asked() -> None:
    # turn-audit request 1334: «¿Qué hora es en Madrid si allá son las 10 de la mañana?», talk, composition failed.
    model = _Decider("¿Qué hora es en Madrid si allá son las 10 de la mañana?", "talk")
    history = [("user", "baxy qué hora es en madrid"), ("assistant", "Ahora son las 19:49 en Madrid.")]
    result = _decided("y si allá son las 10 de la mañana acá qué hora es", history, model)
    assert result["kind"] == "action" and result["operation"] == "system.time"
    assert result["objective"] == "y si en Madrid son las 10 de la mañana acá qué hora es"
    assert model.decisions == 0


def test_the_list_name_is_not_its_entry() -> None:
    # turn-audit request 981: «Add swimming to my list.», task.create; «swimming» was added as the entry.
    model = _Decider("Add swimming to my list.", "action", ("task.create",))
    history = [("user", "add an item to a list"), ("assistant", "What item would you like to add to the list?"),
               ("user", "hiking"), ("assistant", "I've added hiking to your list.")]
    result = _decided("nevermind add an item to my swimming list", history, model)
    assert result["kind"] == "clarify" and result["question"] == "What should I add to your swimming list?"
    # An entry said is added.
    said = _decided("add goggles to my swimming list", history, _Decider("Add goggles to my swimming list.", "action",
                                                                        ("task.create",)))
    assert said["kind"] == "action" and said["operation"] == "task.create"


# ------------------------------------------------------------------ 5. false limits


def test_stopping_the_repetition_asks_for_no_mode() -> None:
    assert not echo_mode_request("para de repetir lo que digo")  # M84 (DEV-D v3o s107)
    assert not echo_mode_request("stop repeating what I say")
    assert stable_no_effect("para de repetir lo que digo") is None
    # The mode itself is still the known limit.
    assert echo_mode_request("di lo mismo que yo hasta que te avise")
    assert echo_mode_request("repite todo lo que digo")


@pytest.mark.parametrize(
    ("text", "restated", "history"),
    [
        # p01-t3 (turn-audit request 743: «Cancel the Christmas list.», limit)
        ("no, cancel", "Cancel the Christmas list.",
         [("user", "i changed my mind"), ("assistant", "Got it, no problem. What do you want to do now?"),
          ("user", "show christmas list"),
          ("assistant", "The situation shows zero tasks were found in the Christmas list search.")]),
        # p14-t3 (turn-audit request 939: «Cancela la foto.», limit)
        ("Cancelar foto", "Cancela la foto.",
         [("user", "No hagas la foto"), ("assistant", "Entendido, no haré la foto."),
          ("user", "Quiero hace una foto a cámara lenta"),
          ("assistant", "Eso no lo hago: las fotos a cámara lenta no las tomo yo.")]),
    ],
)
def test_taking_back_what_was_just_asked_is_no_limit(text: str, restated: str, history: list) -> None:
    model = _Decider(restated, "limit")
    result = _decided(text, history, model)
    assert result["kind"] == "conversation" and result["conversationKind"] == "knowledge"


def test_cancelling_something_else_keeps_its_limit() -> None:
    assert dialogue.takes_back("no, cancel", "show christmas list")
    assert dialogue.takes_back("Cancelar foto", "Quiero hace una foto a cámara lenta")
    assert not dialogue.takes_back("cancela la cita del lunes", "qué tengo el lunes")
    model = _Decider("Cancela la cita del lunes.", "limit")
    result = _decided("cancela la cita del lunes", [("user", "qué tengo el lunes"), ("assistant", "Nada.")], model)
    assert result["kind"] == "conversation" and result["conversationKind"] == "unsupported"


def test_something_wanted_from_a_shop_is_bought() -> None:
    # M84 (DEV-D v3o s042): turn-audit request 245 failed on limit_wording and the recovery published «No hago
    # pasteles de camote.»; the recovered limit is judged by limit_voice_defect only.
    request = "quiero pastel de camote de una panadería local"
    assert asks_to_order(request)
    assert llm.limit_voice_defect("No hago pasteles de camote.", request) == "limit_changed_act"
    assert asks_to_order("I want bagels from the bakery")
    assert not asks_to_order("quiero saber el horario de la farmacia")
    assert not asks_to_order("I want to see a movie at the local cinema")


# ------------------------------------------------------------------ 6. missing limits


@pytest.mark.parametrize(
    "text",
    [
        "enciende la repetición",  # M84 (DEV-D v3o s092)
        "confirmen el pedido",  # s006
        "How much is my phone, I mean my electric bill?",  # s122
        "Saca foto ahora",  # p02-t1
        "Snap a pic after 10 seconds, no, 20 seconds.",  # s094
    ],
)
def test_a_request_no_operation_serves_is_closed_as_a_limit(text: str) -> None:
    assert unserved_personal_request(text)
    # v3o: the decider asked «¿Qué pedido confirmo?», «¿La repetición de qué?», or took a capture or asked an alarm.
    model = _Decider(text, "action", ("capture.screenshot",))
    result = _first(text, model)
    assert result["kind"] == "conversation" and result["conversationKind"] == "unsupported"
    assert model.decisions == 0


@pytest.mark.parametrize(
    "text",
    [
        "saca una foto de la pantalla",
        "take a picture of my screen",
        "sacame una foto de steam",
        "create a new list of my pending bills",
        "cancela el pedido",
        "¿ya llegó mi pedido?",
        "pon la canción de nuevo",
    ],
)
def test_what_is_served_or_said_otherwise_stays_open(text: str) -> None:
    assert not unserved_personal_request(text)


def test_a_photo_is_the_camera_only_without_the_screen() -> None:
    assert camera_photo_request("toma una foto")
    assert camera_photo_request("hazme una selfie")
    assert not camera_photo_request("toma una captura")


@pytest.mark.parametrize(
    "text",
    ["ha comentado alguien en mi comentario", "my facebook update in every three hour should be available"],  # s018, s115
)
def test_the_persons_social_account_is_a_limit(text: str) -> None:
    assert known_unsupported_effect_request(text, ("web.search", "app.open"))
