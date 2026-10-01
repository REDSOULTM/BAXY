"""M104 (2026-10-01): the 24 cases the reserve replay on 38d03aa2 (v3z-hold) broke against 817dde50 (v3w-hold).

The phrasings here are this file's own; the reserve's texts stay in the reserve.

1. Talk answers came out as «conversation» with no ``conversationKind`` (18 cases). The M95 veto on figures from memory
   refused the talk twice, its rejection did not carry the kind the turn decided, and the recovery published a
   conversation of no kind (once with no reply at all). The rejection carries the kind, the recovery publishes it, and
   a retry made only of figures falls back to the first draft's sentences without them.
2. The veto read only digits: the person's «raíz cuadrada de nueve» gave no number, so the computed answer was memory;
   and the retry spelled its figures out («seven to eight minutes») and passed. A number is said in digits or words,
   on both sides (``semantic.quantities.spoken_numbers_in``).
3. D52 (step 6 of goal v3): a figure of the world asked as such is looked up (``semantic.knowledge.figure_lookup``),
   the talk that says it has not checked a figure looks it up too, and one computed from the person's numbers stays
   talk.
4. The rest: «speak loudly» asks how much (owner rule on relative volume), «hows <place> climate today» is the weather
   of that place, and notifications of the news on a subject are a limit, never a notice scheduled for nothing.
"""

from __future__ import annotations

import copy
import json

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind import llm
from baxy_mind.llm import ConversationReplyContractError
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import decider, knowledge, quantities, reading, system, web

# ------------------------------------------------------------------ 2. numbers said in words


@pytest.mark.parametrize(
    ("text", "numbers"),
    [
        ("la raíz cuadrada de dieciséis", [16]),
        ("multiplica veintidós por tres", [22, 3]),
        ("the sum of seven hundred and forty two and nine", [742, 9]),
        ("la suma de catorce y veinticinco", [14, 25]),
        ("twenty-one divided by seven", [21, 7]),
        # An article, a pronoun or «once» alone gives no number.
        ("cuéntame un chiste", []),
        ("which one is better", []),
        ("once upon a time there was a fox", []),
    ],
)
def test_numbers_said_in_words_are_said(text: str, numbers: list[int]) -> None:
    assert quantities.spoken_numbers_in([text]) == numbers


@pytest.mark.parametrize(
    ("reply", "asked"),
    [
        ("La raíz cuadrada de dieciséis es 4.", "dime la raíz cuadrada de dieciséis"),
        ("Ochenta entre cinco da dieciséis.", "cuánto da ochenta entre cinco"),
        ("Twenty-one divided by seven is 3.", "what is twenty-one divided by seven"),
        ("Con tres tazas de arroz te alcanza.", "tengo tres tazas de arroz, ¿me alcanza?"),
    ],
)
def test_a_figure_computed_from_the_persons_words_is_not_memory(reply: str, asked: str) -> None:
    assert llm.talk_memory_figures(reply, asked) == []


@pytest.mark.parametrize(
    ("reply", "asked", "figures"),
    [
        ("Steep green tea for two to three minutes.", "how do I make green tea", ["three minutes"]),
        ("La Torre Eiffel mide unos trescientos metros.", "háblame de la torre eiffel", ["trescientos metros"]),
        ("The Moon is about two hundred thousand miles away.", "tell me about the moon", ["hundred thousand"]),
    ],
)
def test_a_figure_spelled_out_from_memory_is_still_a_figure(reply: str, asked: str, figures: list[str]) -> None:
    assert llm.talk_memory_figures(reply, asked) == figures


def test_the_sentence_with_a_spelled_figure_is_dropped() -> None:
    reply = "Green tea is delicate. Two to Three Minutes is enough."
    assert llm._without_memory_figures(reply, ["three minutes"]) == "Green tea is delicate."


# ------------------------------------------------------------------ 1. the kind travels; no empty answer


class _Writer(llm.LlmRuntime):
    """The drafts stand in for the model, in order (the last one repeats)."""

    def __init__(self, drafts: list[str]) -> None:  # noqa: D107
        self._gguf = None
        self._drafts = list(drafts)
        self.sent: list[dict] = []

    def _post(self, payload, **_):  # noqa: ANN001, ANN201
        self.sent.append(copy.deepcopy(payload))
        content = self._drafts.pop(0) if len(self._drafts) > 1 else self._drafts[0]
        return {"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}


def _chat(writer: _Writer, text: str) -> str:
    reply, _ = writer.chat(text, history=[], conversation_kind="knowledge", response_language="en", temperature=0.0)
    return reply


def test_a_retry_made_only_of_figures_keeps_the_first_drafts_other_sentences() -> None:
    first = (
        "The Gregorian calendar fixed the drift of the Julian one by skipping leap years in most century years. "
        "It was adopted in 1582."
    )
    writer = _Writer([first, json.dumps({"answer": "It was adopted in 1582."})])

    reply = _chat(writer, "what changed between the julian and the gregorian calendars")
    assert reply == "The Gregorian calendar fixed the drift of the Julian one by skipping leap years in most century years."
    assert len(writer.sent) == 2


def test_an_answer_that_is_only_figures_fails_with_the_decided_kind() -> None:
    writer = _Writer(["Sunlight takes 8 minutes to reach us.", json.dumps({"answer": "It takes 8 minutes."})])

    with pytest.raises(ConversationReplyContractError) as refused:
        _chat(writer, "tell me about sunlight reaching the earth")
    assert refused.value.audit_reason == "memory_figures"
    assert refused.value.conversation_kind == "knowledge"


class _Composer:
    def __init__(self, replies: dict[str, str]) -> None:  # noqa: D107
        self.replies = replies

    def clarify_after_turn_failure(self, *_args: object, **_kwargs: object) -> str:
        raise AssertionError("an understood turn is not asked what the person wants")

    def compose_user_message(self, _text: str, intent: str, _facts: dict) -> str:
        return self.replies.get(intent, "")


def test_talk_recovered_after_its_wording_failed_keeps_its_kind() -> None:
    composer = _Composer({"conversation": "The Gregorian calendar corrected the drift of the Julian one."})
    result = sidecar._recover_failed_turn(
        {"id": "m104", "text": "what changed between the julian and the gregorian calendars", "history": []},
        composer,
        failure_kinds=(sidecar.CONVERSATION_WORDING_FAILURE, sidecar.CONVERSATION_WORDING_FAILURE),
        conversation_kinds=("knowledge", "knowledge"),
    )
    assert result["kind"] == "conversation" and result["conversationKind"] == "knowledge"
    assert result["reply"].startswith("The Gregorian calendar")


def test_a_recovery_with_no_decided_talk_kind_publishes_none() -> None:
    composer = _Composer({"conversation": "Claro."})
    result = sidecar._recover_failed_turn(
        {"id": "m104", "text": "hola", "history": []},
        composer,
        failure_kinds=(sidecar.CONVERSATION_WORDING_FAILURE, sidecar.CONVERSATION_WORDING_FAILURE),
        conversation_kinds=("knowledge", "social"),
    )
    assert result["conversationKind"] is None


# ------------------------------------------------------------------ 3. figures of the world are looked up


@pytest.mark.parametrize(
    "text",
    [
        "what is the height of the eiffel tower",
        "cuántos kilómetros mide el río amazonas",
        "how deep is the mariana trench",
        "qué tan grande es groenlandia",
        "hey baxy, how long should pasta boil",
    ],
)
def test_a_figure_of_the_world_is_looked_up_with_the_persons_words(text: str) -> None:
    found = knowledge.figure_lookup(text)
    assert found is not None and found.kind == "figure"
    assert knowledge.reference_lookup(text) == found


@pytest.mark.parametrize(
    "text",
    [
        "cuánto es ochenta entre cuatro",  # computed from the person's numbers
        "what is the square root of sixteen",
        "how old are you",  # BAXY himself
        "how much battery do I have left",  # this PC
        "cuántos años tengo",  # the person's own
        "how much does it cost",  # nothing named to look up
        "what year is it",  # the calendar of today
        "cuánto falta para el viernes",
        "convert three cups to milliliters",
    ],
)
def test_what_is_no_figure_of_the_world_is_not_looked_up(text: str) -> None:
    assert knowledge.figure_lookup(text) is None


class _Decider:
    def __init__(self, decision: str, operations: tuple[str, ...] = ()) -> None:  # noqa: D107
        self.decided = decider.ContextDecision(request="", decision=decision, operations=operations, question="")
        self.chats = 0

    def decide_in_context(self, text: str, *_args: object, **_kwargs: object) -> decider.ContextDecision:
        return decider.ContextDecision(
            request=text, decision=self.decided.decision, operations=self.decided.operations, question="",
        )

    def chat(self, *_args: object, **_kwargs: object) -> tuple[str, list[object]]:
        self.chats += 1
        return "Te cuento.", []

    @staticmethod
    def detect_response_language(_text: str) -> str:
        return "es"


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


CATALOG = PlannerCatalog([_tool(op) for op in ("web.search", "notification.schedule", "web.news.headlines")])


def test_a_figure_the_decider_would_talk_is_searched() -> None:
    text = "cuántos kilómetros mide el río amazonas"
    model = _Decider("talk")
    result = sidecar._context_decided_result(
        {"id": "m104", "text": text, "history": [{"role": "user", "content": text}]},
        llm=model,
        planner_catalog=CATALOG,
    )
    assert result["kind"] == "action" and result["operation"] == "web.search"
    assert model.chats == 0


@pytest.mark.parametrize(
    "reply",
    ["I haven't checked how deep the trench is.", "No la tengo comprobada.", "No lo he verificado todavía."],
)
def test_a_figure_the_talk_has_not_checked_is_what_it_does_not_know(reply: str) -> None:
    assert sidecar._ADMITS_NOT_KNOWING.search(sidecar.effect_intent._fold(reply)) is not None


# ------------------------------------------------------------------ 4. the rest


@pytest.mark.parametrize("text", ["speak loudly", "talk more quietly please", "speak up"])
def test_speaking_louder_or_softer_asks_how_much(text: str) -> None:
    read = reading.read(text, available_operations=("audio.volume.adjust", "audio.volume", "audio.status"))
    assert read.effects is None
    assert read.clarification is not None
    assert read.clarification.operations == ("audio.volume.adjust",)
    assert read.clarification.missing_fields == ("amount",)


@pytest.mark.parametrize(
    ("text", "place"),
    [("hows quito climate today", "quito"), ("what's Lisbon weather like", "Lisbon"), ("how is cusco weather now", "cusco")],
)
def test_the_place_named_before_the_weather_is_its_place(text: str, place: str) -> None:
    read = reading.read(text, available_operations=("weather.current", "web.search"))
    assert read.effects is not None and read.effects.operations == ("weather.current",)
    assert system._weather_location(text) == place


@pytest.mark.parametrize("text", ["how is the weather today", "what is tomorrow weather", "how is the local weather"])
def test_a_time_or_an_article_before_the_weather_is_no_place(text: str) -> None:
    assert system._weather_location(text) is None


def test_the_climate_of_the_world_is_no_weather_read() -> None:
    read = reading.read("how will climate change affect farming", available_operations=("weather.current", "web.search"))
    assert read.effects is None or read.effects.operations != ("weather.current",)


@pytest.mark.parametrize(
    "text",
    [
        "quiero alertas de noticias sobre el litio",
        "set up notifications for news about the mars mission",
        "avísame de las noticias sobre la huelga portuaria",
    ],
)
def test_notifications_of_the_news_are_a_limit(text: str) -> None:
    assert web.asks_to_watch_the_news(text)
    result = sidecar._context_decided_result(
        {"id": "m104", "text": text, "history": [{"role": "user", "content": text}]},
        llm=_Decider("action", ("notification.schedule",)),
        planner_catalog=CATALOG,
    )
    assert result["kind"] == "conversation" and result["conversationKind"] == "unsupported"


def test_a_notice_at_a_time_to_read_the_news_is_a_notice() -> None:
    assert not web.asks_to_watch_the_news("avísame a las ocho para leer las noticias")
