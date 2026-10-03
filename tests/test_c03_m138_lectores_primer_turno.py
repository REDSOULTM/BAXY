"""M138 (D58, 2026-10-03): first-turn readers that overrode the isolated decider on DEV-G (window v4n-devG).

Eight first messages a reader decided (explicit_effects / explicit_conversation / explicit_clarification) where the
isolated decider full3 was right. Each reader is narrowed to what it really reads; nothing waits on a new layer:

1. The agenda reader read an event or a «my» said after the question («¿cómo se prepara el agua de jamaica? la quiero
   hacer para la comida del domingo…», «when do the Lakers play next? my buddy…»): only the question is read now
   (``notes.the_question_asked``), and M81 reads the person's own data in that question and in what the decider would
   look up, not in its context.
2. Internet had, checked or working is this PC's connection (reviewed literals H0080 «funciona mi internet», H0732
   «tengo internet» are network.status), never a web search.
3. Where someone «anda» or «se encuentra» is a place BAXY does not know: it is asked.
4. The words a message carries («diciendo que llego tarde») are not messages that arrived: the draft is the decider's.
5. «pa las 7» is «para las 7» for the incomplete-schedule reader too (M110 read it so elsewhere).
6. «play some Khruangbin»: some of a performer names the performer.
7. «… in spotify» names Spotify as «en/on Spotify» does.

Every variant phrasing here is our own; the DEV-G texts are the rows themselves.
"""

from __future__ import annotations

import json
import pathlib
from datetime import datetime, timedelta, timezone

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic.arguments import _explicit_arguments_from_evidence
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind.semantic.dialogue import DialogueState
from baxy_mind.semantic.notes import agenda_read_request, the_question_asked
from baxy_mind.semantic.patterns import (
    known_unsupported_effect_request,
    resolve_explicit_clarification_intent,
    resolve_explicit_effects,
)

OPERATIONS = tuple(
    json.loads(
        (pathlib.Path(sidecar.__file__).parent / "data" / "decider_catalog.es.v1.json").read_text(encoding="utf-8")
    )["operations"]
)


class _Decider:
    """The model of a whole turn: the decider answers what it is given; every other call is neutral."""

    _native_tool_policy_enabled = False

    def __init__(self, decision: ContextDecision | None = None) -> None:
        self.decision = decision
        self.decisions = 0

    def decide_in_context(self, *_a, **_k):
        self.decisions += 1
        if self.decision is None:
            raise AssertionError("the decider was not to be asked")
        return self.decision

    def formulate_explicit_clarification_question(self, *_a, **_k):
        return "¿Dónde?"

    def clarify_after_turn_failure(self, *_a, **_k):
        return "¿Quién es?"

    def public_lookup_requested(self, _text):
        return False

    def operation_is_the_requested_effect(self, *_a, **_k):
        return True

    def _verify_semantic_effect_shape(self, _text):
        return "no_effect", "zero"

    def chat(self, *_a, **_k):
        return "Respuesta.", []

    def prepare_chat(self, *_a, **_k):
        return None

    def detect_response_language(self, _text):
        return "es"

    def consume_deferred_response_language(self, _text):
        return True, None

    def retire_deferred_response_language(self, _text):
        return None

    def __getattr__(self, name):
        def missing(*_a, **_k):
            raise RuntimeError(f"no {name} here")
        return missing


def _tool(name: str) -> dict:
    schema = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    return {"type": "function", "function": {"name": name.replace(".", "_"), "canonical_name": name,
                                             "description": name, "risk": "read_only", "parameters": schema}}


def _turn(text: str, model: _Decider) -> dict:
    tools = {name: _tool(name) for name in OPERATIONS}
    return sidecar._prepare_turn_result(
        {"id": "m138", "text": text, "history": [{"role": "user", "content": text}]},
        llm=model, planner_catalog=PlannerCatalog(list(tools.values())), encoder=lambda _t: (), tool_by_name=tools,
        dialogue_state=DialogueState(),
    )


def _read(text: str) -> tuple[str, ...] | None:
    found = resolve_explicit_effects(text, OPERATIONS)
    return None if found is None else tuple(found.operations)


def _asked(text: str) -> tuple[str, ...] | None:
    found = resolve_explicit_clarification_intent(text, OPERATIONS)
    return None if found is None else tuple(found.missing_fields)


# ------------------------------------------------------------------ 1. the question, not its context


@pytest.mark.parametrize(
    "text",
    [
        # DEV-G G-s002, G-w42-t1
        "¿cómo se prepara el agua de jamaica? la quiero hacer para la comida del domingo con mis suegros",
        "when do the Lakers play next? my buddy wants to come over and watch it",
        # our own
        "how do you make guacamole? I'm bringing it to the party tonight",
        "¿qué vino va bien con pescado? es para la cena del sábado",
        "what time does the Barcelona match start? my dad wants to watch it with me",
    ],
)
def test_an_event_said_after_the_question_is_no_agenda_read(text: str) -> None:
    assert not agenda_read_request(text)
    assert _read(text) != ("calendar.event.list",)


@pytest.mark.parametrize(
    "text",
    [
        "¿cuándo es mi cita? la tengo con el dentista",
        "what's on my calendar tomorrow? I need to plan",
        "¿qué tengo mañana?",
    ],
)
def test_the_question_about_the_agenda_is_still_read(text: str) -> None:
    assert _read(text) == ("calendar.event.list",)


def test_the_question_asked_keeps_a_message_without_context() -> None:
    assert the_question_asked("¿qué tengo mañana?") == "¿qué tengo mañana?"
    assert the_question_asked("tengo una reunión el lunes, ¿a qué hora es?") == "tengo una reunión el lunes, ¿a qué hora es?"
    assert the_question_asked("ok? sí") == "ok? sí"  # too short to be a question with its context
    assert the_question_asked("when is it? my sister asked") == "when is it?"


def test_the_recipe_with_its_occasion_is_the_deciders() -> None:
    text = "¿cómo se prepara el agua de jamaica? la quiero hacer para la comida del domingo con mis suegros"
    model = _Decider(ContextDecision(request="¿Cómo se prepara el agua de jamaica?", decision="talk", operations=(),
                                     question=""))

    result = _turn(text, model)

    assert model.decisions == 1
    assert result["kind"] == "conversation"


def _searched(text: str, request: str, arguments: tuple = ()) -> dict:
    model = _Decider(ContextDecision(request=request, decision="action", operations=("web.search",), question="",
                                     arguments=arguments))
    result = _turn(text, model)
    assert model.decisions == 1
    return result


def test_m81_reads_the_question_not_its_context() -> None:
    # DEV-G G-w42-t1: the isolated decider looked the game up; «my buddy» is who comes over, not what is looked up.
    result = _searched("when do the Lakers play next? my buddy wants to come over and watch it",
                       "When do the Lakers play next?", (("query", "When do the Lakers play next?"),))
    assert result["kind"] == "action" and result["effectOperations"] == ["web.search"]
    # our own, in Spanish
    result = _searched("¿a qué hora juega el América? mi papá quiere verlo conmigo", "¿A qué hora juega el América?")
    assert result["kind"] == "action" and result["effectOperations"] == ["web.search"]


@pytest.mark.parametrize(
    ("text", "restated"),
    [
        # M81 as it was (DEV-D D-s053): a person of the person's life, in the question itself, is asked.
        ("¿Miguel sigue viviendo en Arkansas?", "¿Miguel sigue viviendo en Arkansas?"),
        # the context names the person's own data and the decider would look it up: still asked
        ("¿a qué hora juega el América? mi tío Jorge quiere verlo", "¿A qué hora juega el América con mi tío Jorge?"),
    ],
)
def test_m81_still_asks_what_only_the_person_knows(text: str, restated: str) -> None:
    assert _searched(text, restated)["kind"] == "clarify"


# ------------------------------------------------------------------ 2. internet had is this PC's connection


@pytest.mark.parametrize(
    "text",
    [
        "baxy check si tengo internet",  # DEV-G G-w33-t1
        "chequea la conexión a internet",
        "do I have internet right now",
        "¿funciona el internet?",
        "is the internet working?",
        "fíjate si hay internet",
    ],
)
def test_internet_had_checked_or_working_is_the_network_state(text: str) -> None:
    assert _read(text) == ("network.status",)
    assert _turn(text, _Decider())["effectOperations"] == ["network.status"]


@pytest.mark.parametrize(
    "text",
    ["busca en internet recetas de pan", "check online for flights to Lima", "busca en internet si tengo que votar"],
)
def test_internet_as_where_to_look_keeps_its_search(text: str) -> None:
    assert _read(text) == ("web.search",)


# ------------------------------------------------------------------ 3. where someone «anda» is asked


@pytest.mark.parametrize(
    "text",
    [
        "oye, ¿va a llover donde anda mi compadre ahorita?",  # DEV-G G-s043
        "¿hace frío donde se encuentra mi hija?",
        "¿cómo está el clima donde anda la abuela?",
    ],
)
def test_the_weather_where_someone_is_asks_where(text: str) -> None:
    assert _asked(text) == ("location",)
    result = _turn(text, _Decider())
    assert result["kind"] == "clarify" and result["missingFields"] == ["location"]


@pytest.mark.parametrize("text", ["¿va a llover donde estoy?", "¿va a llover en Lima donde anda mi compadre?"])
def test_the_weather_of_a_known_place_is_read(text: str) -> None:
    assert _asked(text) is None
    assert _read(text) == ("weather.current",)


# ------------------------------------------------------------------ 4. a message's words are not messages that arrived


@pytest.mark.parametrize(
    "text",
    [
        # DEV-G G-s042
        "déjame escrito un mensaje de whatsapp para mi mamá diciendo que llego tarde porque hay mucho trancón",
        "leave a whatsapp message for my brother saying I arrived safely",
        "déjale un mensaje a mi jefe que diga que llego tarde mañana",
    ],
)
def test_a_message_to_write_is_the_deciders_draft(text: str) -> None:
    assert not known_unsupported_effect_request(text, OPERATIONS)
    model = _Decider(ContextDecision(request=text, decision="action", operations=("message.draft",), question=""))

    result = _turn(text, model)

    assert model.decisions == 1
    assert result["kind"] == "action" and result["effectOperations"] == ["message.draft"]


@pytest.mark.parametrize("text", ["cuántos mensajes no leídos tengo", "¿qué me escribió mamá?"])
def test_reading_the_chats_is_still_the_limit(text: str) -> None:
    assert known_unsupported_effect_request(text, OPERATIONS)


# ------------------------------------------------------------------ 5. «pa las 7» is a clock


LOCAL = timezone(timedelta(hours=-3))


@pytest.mark.parametrize(
    "text",
    [
        "programame una alarma pa las 7 que manana madrugo",  # DEV-G G-s073
        "pon una alarma pa las 5 y media",
        "ponme una alarma pa las 8 que tengo clase",
    ],
)
def test_pa_las_is_the_hour_of_the_alarm(text: str) -> None:
    assert _asked(text) is None
    assert _read(text) == ("notification.schedule",)
    assert _turn(text, _Decider())["effectOperations"] == ["notification.schedule"]


def test_the_alarm_pa_las_7_before_an_early_morning_rings_at_seven() -> None:
    due = sidecar._canonical_due_utc(
        "pa las 7", "programame una alarma pa las 7 que manana madrugo",
        now_utc=datetime(2026, 10, 3, 4, 44, tzinfo=LOCAL),
    )
    assert datetime.fromisoformat(due.replace("Z", "+00:00")).astimezone(LOCAL) == datetime(
        2026, 10, 4, 7, 0, tzinfo=LOCAL,
    )


def test_an_alarm_with_no_hour_still_asks_it() -> None:
    assert _asked("programame una alarma para mañana") == ("alarm_time",)


# ------------------------------------------------------------------ 6. some of a performer


@pytest.mark.parametrize(
    ("text", "name"),
    [
        ("play some Khruangbin", "Khruangbin"),  # DEV-G G-w07-t1
        ("play some Tame Impala", "Tame Impala"),
        ("play a bit of Daft Punk", "Daft Punk"),
    ],
)
def test_some_of_a_performer_is_what_to_play(text: str, name: str) -> None:
    assert _read(text) == ("media.play.youtube",)
    assert _explicit_arguments_from_evidence("media.play.youtube", text) == {"query": name}


def test_some_music_still_asks_what_to_play() -> None:
    assert _asked("play some music") == ("query",)
    # «some of that» points at something; it names no performer (tests/test_uso_real_media_dev2.py)
    assert _read("play some of that") != ("media.play.youtube",)


def test_some_of_a_kind_is_still_the_kind() -> None:
    assert _explicit_arguments_from_evidence("media.play.youtube", "play some jazz") == {"query": "jazz"}


# ------------------------------------------------------------------ 7. «in spotify»


_SPOTIFY_QUERY = {
    "type": "object",
    "properties": {"provider": {"type": "string", "enum": ["spotify"]},
                   "query": {"type": "string", "x-nonWhitespace": True}},
    "required": ["provider", "query"],
    "additionalProperties": False,
}


@pytest.mark.parametrize(
    ("text", "said"),
    [
        ("baxy please play that song provenza by karol g in spotify ya mismo que la necesito", "provenza"),  # G-s096
        ("play despacito in spotify", "despacito"),
        ("please play bohemian rhapsody by queen in spotify right now", "bohemian rhapsody"),
    ],
)
def test_in_spotify_plays_on_spotify(text: str, said: str) -> None:
    assert _read(text) == ("media.play.query",)
    arguments = sidecar._ground_explicit_arguments("media.play.query", text, _SPOTIFY_QUERY)
    assert arguments["provider"] == "spotify" and said in arguments["query"].lower()
    assert "spotify" not in arguments["query"].lower()


@pytest.mark.parametrize("text", ["play despacito", "pon despacito en youtube"])
def test_music_with_no_provider_or_on_youtube_stays_on_youtube(text: str) -> None:
    assert _read(text) == ("media.play.youtube",)
