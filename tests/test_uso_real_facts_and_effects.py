"""Uso real 2026-09-23 (official window, tanda-01 and uso-real-01/02/03): wrong facts
and wrong effects on everyday requests.

Each block pins one family at its root: the reader or gate that decided, and the
turn that comes out of ``_prepare_turn_result`` with a fake model.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from baxy_mind import __main__ as mind_main  # noqa: E402
from baxy_mind import llm as llm_module  # noqa: E402
from baxy_mind.__main__ import _prepare_turn_result  # noqa: E402
from baxy_mind.effect_intent import (  # noqa: E402
    known_unsupported_effect_request,
    operation_domain_is_grounded,
    resolve_explicit_clarification_intent,
    resolve_explicit_effects,
)
from baxy_mind.planner import PlannerCatalog  # noqa: E402
from baxy_mind.semantic.request import INTENT_IDENTITY, read_request  # noqa: E402
from baxy_mind.semantic import dialogue  # noqa: E402
from baxy_mind.semantic.grammar import _is_past_or_hypothetical_state  # noqa: E402
from baxy_mind.semantic.system import _weather_location  # noqa: E402
from baxy_mind.semantic.temporal import clock_elsewhere, other_place_clock_question  # noqa: E402
from baxy_mind.semantic.web import (  # noqa: E402
    person_fact_subject,
    record_fact_query,
)


def _tool(operation: str, properties: dict | None = None) -> dict:
    properties = properties or {}
    return {
        "type": "function",
        "function": {
            "name": operation.replace(".", "_"),
            "canonical_name": operation,
            "description": f"Authenticated catalog leaf {operation}.",
            "risk": "read_only",
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": list(properties),
                "additionalProperties": False,
            },
        },
    }


_WEB_SEARCH = _tool("web.search", {"query": {"type": "string", "x-nonWhitespace": True}})


class _NoModel:
    """The readers must own the turn: the model is never asked to decide it."""

    @staticmethod
    def decide_turn(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise AssertionError("a deterministic reading owns this turn")

    @staticmethod
    def retire_deferred_response_language(_text: str) -> None:
        return None


def _turn(text: str, operations: tuple[str, ...], llm: object, history: list | None = None) -> dict:
    tools = [_WEB_SEARCH if operation == "web.search" else _tool(operation) for operation in operations]
    return _prepare_turn_result(
        {"id": "uso-real", "text": text, "history": history or []},
        llm=llm,
        planner_catalog=PlannerCatalog(tools),
        encoder=lambda _texts: (),
        tool_by_name={tool["function"]["canonical_name"]: tool for tool in tools},
    )


# --- 1. The time somewhere else is never this PC's clock ---------------------------

_OTHER_PLACE_CLOCKS = [
    "in the eastern timezone, what time is it now",
    "qué hora es en tokio",
    "what time is it in London right now?",
    "Dime la hora en Madrid",
    "what is the current time in new york",
    "qué hora es ahora en Chile",
    "dime la hora del pacífico",
    "what time is it GMT",
    "hora entre aquí y canadá",
]
_THIS_CLOCK = [
    "qué hora es",
    "dime la hora",
    "what time is it now",
    "¿qué hora es en este momento?",
    "qué hora es en la pc",
    "hora actual en",
    "es hora de dormir",
    "¿a qué hora abre el banco?",
    "pon una alarma a la hora en punto",
    "¿a qué hora es la cita para mañana?",
    "what time does the bank open in London",
    "recuérdame a la hora de comer en casa",
]


@pytest.mark.parametrize("text", _OTHER_PLACE_CLOCKS)
def test_the_clock_of_another_place_is_read_with_that_place(text: str) -> None:
    # Tanda 4 supersedes the web lookup: the time somewhere else is this PC's
    # clock read together with that place's zone, so system.time is grounded only
    # because the place is read, and it always carries that place.
    folded = llm_module._policy_guard_text(text)
    assert other_place_clock_question(folded)
    assert clock_elsewhere(folded) is not None
    assert operation_domain_is_grounded(text, "system.time") is True
    assert mind_main._explicit_arguments_from_evidence("system.time", text)["place"]


@pytest.mark.parametrize("text", _THIS_CLOCK)
def test_this_clock_and_clock_idioms_are_not_another_place(text: str) -> None:
    folded = llm_module._policy_guard_text(text)
    assert not other_place_clock_question(folded)
    assert clock_elsewhere(folded) is None


@pytest.mark.parametrize("text", _OTHER_PLACE_CLOCKS[:5])
def test_the_time_elsewhere_is_this_clock_read_before_the_model_speaks(text: str) -> None:
    result = _turn(text, ("system.time", "web.search"), _NoModel())
    assert result["kind"] == "action"
    assert result["operation"] == "system.time"
    assert "web.search" not in result["effectOperations"]


def test_a_clock_of_another_place_that_names_no_single_place_is_never_this_clock() -> None:
    text = "what time is it in london and in paris"
    assert other_place_clock_question(llm_module._policy_guard_text(text))
    assert clock_elsewhere(llm_module._policy_guard_text(text)) is None
    assert operation_domain_is_grounded(text, "system.time") is False


def test_the_local_clock_still_reads_this_pc() -> None:
    result = _turn("dime la hora", ("system.time", "web.search"), _NoModel())
    assert result["operation"] == "system.time"


# --- 2. A question about BAXY is answered as BAXY, never searched --------------------

_SELF_QUESTIONS = [
    "the creator of your ai, what is their name",
    "¿cuál es tu lugar de origen?",
    "can you tell me the age of the ai",
    "who made you",
    "quién te creó",
    "de dónde eres",
    "how old are you",
    "¿cuántos años tienes?",
    "what is your name",
    "who built you?",
    "what company made you",
    "cuál es la edad de baxy",
]
_NOT_ABOUT_BAXY = [
    "who invented AI",
    "quién creó el iPhone",
    "cuál es la edad de Jennifer López",
    "te pido que me digas el nombre del presidente",
    "what is the name of this song",
    "quien invento la ia",
]


@pytest.mark.parametrize("text", _SELF_QUESTIONS)
def test_questions_about_the_one_answering_read_as_identity(text: str) -> None:
    assert read_request(text).has(INTENT_IDENTITY)
    assert (
        llm_module._conversation_presentation_shape(
            text, conversation_kind="knowledge", has_history=False,
        )
        == "identity"
    )


@pytest.mark.parametrize("text", _NOT_ABOUT_BAXY)
def test_a_you_elsewhere_or_a_third_party_is_not_identity(text: str) -> None:
    assert not read_request(text).has(INTENT_IDENTITY)


class _GuardSaysPublic:
    """The semantic guard misreads the question as public information."""

    def __init__(self) -> None:
        self.guard_calls = 0

    def public_lookup_requested(self, _text: str) -> bool:
        self.guard_calls += 1
        return True


@pytest.mark.parametrize("text", _SELF_QUESTIONS)
def test_identity_is_never_a_public_lookup_whatever_the_guard_reads(text: str) -> None:
    guard = _GuardSaysPublic()
    catalog = PlannerCatalog([_WEB_SEARCH])
    assert not mind_main._public_lookup_applies(text, text, guard, ("web.search",), catalog)
    # The same guard reading still searches public information.
    assert mind_main._public_lookup_applies(
        "cuál es la tasa de cambio del yen", "cuál es la tasa de cambio del yen",
        guard, ("web.search",), catalog,
    )


class _IdentityTurnLlm:
    def __init__(self) -> None:
        self.chat_texts: list[str] = []

    @staticmethod
    def decide_turn(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {
            "mode": "conversation", "operation": None, "question": "",
            "conversation_kind": "knowledge", "effect_count": "zero",
            "effect_operations": [], "effect_verification": "not_applicable",
            "response_language": "en",
        }

    @staticmethod
    def public_lookup_requested(_text: str) -> bool:
        return True

    @staticmethod
    def _verify_semantic_effect_shape(_text: str) -> tuple[str, str]:
        return "no_effect", "zero"

    @staticmethod
    def consume_deferred_response_language(_text: str) -> tuple[bool, str | None]:
        return True, "en"

    @staticmethod
    def retire_deferred_response_language(_text: str) -> None:
        return None

    @staticmethod
    def detect_response_language(_text: str) -> str:
        return "en"

    def chat(self, text: str, **_kwargs: object) -> tuple[str, list[object]]:
        self.chat_texts.append(text)
        return "I'm BAXY, the assistant that lives on this PC.", []


@pytest.mark.parametrize("text", ["the creator of your ai, what is their name", "who made you"])
def test_an_identity_turn_answers_without_a_web_search(text: str) -> None:
    llm = _IdentityTurnLlm()
    result = _turn(text, ("web.search",), llm)
    assert result["kind"] == "conversation"
    assert result["effectOperations"] == []
    assert "web.search" not in result["intentOperations"]
    assert llm.chat_texts == [text]


def test_the_identity_answer_sees_the_question_and_never_invents_an_origin() -> None:
    text = "who made you"
    payload = llm_module._shaped_presentation_text(text, "identity", response_language="en")
    assert '"asked": "who made you"' in payload
    violates = llm_module._shaped_conversation_answer_violates_contract
    assert violates("I'm BAXY and OpenAI made me.", text, "identity")
    assert violates("I'm BAXY, built on Qwen.", text, "identity")
    assert violates("I'm BAXY and I was born in 2024.", text, "identity")
    assert not violates(
        "I'm BAXY, the assistant that lives on this PC; I don't have the name of who made me.",
        text,
        "identity",
    )


# --- 3. The home screen of a PC is its desktop ---------------------------------------

_DESKTOP = (
    "Ve al homescreen",
    "Go to the home screen",
    "ve al escritorio",
    "muéstrame el escritorio",
    "show desktop",
    "take me back to the desktop",
    "llévame al escritorio por favor",
    "ve a la pantalla de inicio",
)
_NAVIGATION_OPS = frozenset({"window.minimize.all", "web.search", "browser.navigate", "app.open"})


@pytest.mark.parametrize("text", _DESKTOP)
def test_going_to_the_home_screen_shows_the_desktop(text: str) -> None:
    intent = resolve_explicit_effects(text, _NAVIGATION_OPS)
    assert intent is not None and intent.operations == ("window.minimize.all",)
    assert operation_domain_is_grounded(text, "window.minimize.all") is True
    assert operation_domain_is_grounded(text, "browser.navigate") is not True


def test_the_home_screen_is_never_a_website_even_without_minimize_all() -> None:
    intent = resolve_explicit_effects("Ve al homescreen", {"web.search", "browser.navigate"})
    assert intent is None or "browser.navigate" not in intent.operations


@pytest.mark.parametrize("text", ["ve a youtube", "abre el escritorio", "minimiza todo"])
def test_sites_the_desktop_folder_and_minimize_keep_their_readings(text: str) -> None:
    intent = resolve_explicit_effects(text, _NAVIGATION_OPS)
    operations = () if intent is None else intent.operations
    if text == "ve a youtube":
        assert operations == ("web.search", "browser.navigate")
    elif text == "abre el escritorio":
        assert "window.minimize.all" not in operations
    else:
        assert operations == ("window.minimize.all",)


# --- 4. A timer without a duration asks it; a coffee is a plain limit ---------------

@pytest.mark.parametrize("text", ["i would like a timer set", "i'd like an alarm", "we need an alarm set"])
def test_a_desired_timer_without_its_duration_asks_for_it(text: str) -> None:
    asked = resolve_explicit_clarification_intent(
        text, {"notification.schedule", "reminder.create"}, (),
    )
    assert asked is not None
    assert asked.operations == ("notification.schedule",)
    assert asked.missing_fields == ("alarm_time",)


@pytest.mark.parametrize(
    "text, hypothetical",
    [
        ("i would like a timer set", False),
        ("i would love a reminder", False),
        ("what would happen if I close it", True),
        ("how much ram would it use", True),
        ("would you open it", False),
    ],
)
def test_would_like_is_a_desire_not_a_hypothesis(text: str, hypothetical: bool) -> None:
    assert _is_past_or_hypothetical_state(llm_module._policy_guard_text(text)) is hypothetical


_ERRANDS = [
    "prepárame una taza de café",
    "make me a coffee",
    "bring me a beer",
    "hazme el desayuno",
    "¿puedes hacerme un café?",
    "sírveme un vaso de agua",
]


@pytest.mark.parametrize("text", _ERRANDS)
def test_food_and_drink_are_a_known_limit(text: str) -> None:
    assert known_unsupported_effect_request(text, ("app.open", "web.search", "audio.volume"))


@pytest.mark.parametrize("text", ["hazme una presentación", "prepara una nota", "tráeme el archivo", "haz una captura"])
def test_pc_work_with_the_same_verbs_is_not_an_errand(text: str) -> None:
    assert not known_unsupported_effect_request(
        text, ("app.open", "web.search", "document.presentation.create", "note.create"),
    )


class _LimitLlm(_IdentityTurnLlm):
    @staticmethod
    def decide_turn(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise AssertionError("a known limit is closed before the model decides")

    @staticmethod
    def detect_response_language(_text: str) -> str:
        return "es"

    def chat(self, text: str, **kwargs: object) -> tuple[str, list[object]]:
        self.chat_texts.append(str(kwargs.get("conversation_kind")))
        return "Eso no lo hago: el café se prepara fuera de este PC.", []


def test_a_coffee_order_is_a_plain_limit_not_a_question_about_the_pc() -> None:
    llm = _LimitLlm()
    result = _turn("prepárame una taza de café", ("audio.volume", "web.search"), llm)
    assert result["kind"] == "conversation"
    assert result["conversationKind"] == "unsupported"
    assert result["question"] == ""
    assert result["effectOperations"] == []
    assert llm.chat_texts == ["unsupported"]


# --- 5. The limit sentence is plain, short and never echoes the request --------------

def test_courtesy_is_never_the_anchor_of_a_limit() -> None:
    assert llm_module._unsupported_request_anchor_token("Stop listening por favor") == "listening"
    assert llm_module._unsupported_request_anchor_token("abre el portal, porfa") == "portal"


@pytest.mark.parametrize(
    "request_text, reply, reason",
    [
        ("Stop listening por favor", "No puedo detener el escuchado por favor", "unsupported_forbidden"),
        ("Stop listening por favor", "No puedo hacer eso.", "unsupported_missing_anchor"),
        ("Stop listening por favor", "No puedo dejar de escucharte desde el chat.", ""),
        ("¿puedes poner un canal de noticias en francés?", "Eso no lo hago: los canales de noticias no los pongo yo.", ""),
        ("¿puedes poner un canal de noticias en francés?", "Eso no lo hago.", "unsupported_missing_anchor"),
        # tanda-02: the request made the subject («Preparar café no lo hago») echoes it;
        # the same limit in BAXY's own first person does not.
        ("prepárame una taza de café", "Preparar café no lo hago: pasa fuera de este PC.",
         "unsupported_limit_echoes_request"),
        ("prepárame una taza de café", "Eso no lo hago: el café no lo preparo yo, pasa fuera de este PC.", ""),
    ],
)
def test_limit_prose_contract(request_text: str, reply: str, reason: str) -> None:
    assert llm_module._unsupported_answer_contract_failure(reply, request_text) == reason


def test_the_limit_instructions_no_longer_dictate_the_robotic_formula() -> None:
    assert "tal como fue" not in llm_module.UNSUPPORTED_PRESENTATION_PROMPT
    assert "como se pidió" not in llm_module.UNSUPPORTED_PRESENTATION_PROMPT
    assert "no lo haces" in llm_module.UNSUPPORTED_PRESENTATION_PROMPT
    source = Path(llm_module.__file__).read_text(encoding="utf-8")
    assert "tal como fue pedido" not in source
    assert "tal como fue solicitado" not in source


# --- 6. A span or a holiday is a time, not a place ------------------------------------

@pytest.mark.parametrize(
    "text, place",
    [
        ("pronóstico de diez días", None),
        ("pronóstico para los próximos 5 días", None),
        ("forecast for the next 7 days", None),
        ("Dígame el weather para San Valentín.", None),
        ("dime el clima para navidad", None),
        ("clima de la semana en Buenos Aires", "Buenos Aires"),
        ("qué tiempo hace en Buenos Aires para mañana", "Buenos Aires"),
        ("clima de mañana en Lima", "Lima"),
        ("tell me the weather in Paris", "Paris"),
        ("clima en Santiago de Chile", "Santiago de Chile"),
        ("weather in Rio de Janeiro tomorrow", "Rio de Janeiro"),
        ("clima en Ñuñoa", "Ñuñoa"),
    ],
)
def test_weather_place_is_a_place(text: str, place: str | None) -> None:
    assert _weather_location(text) == place


@pytest.mark.parametrize(
    "text",
    ["Dígame el weather para San Valentín.", "tell me the weather in Paris", "give me the forecast for tomorrow"],
)
def test_formal_and_english_asking_heads_read_the_weather(text: str) -> None:
    intent = resolve_explicit_effects(text, {"weather.current", "web.search"})
    assert intent is not None and intent.operations == ("weather.current",)


# --- 7. A person's age and who holds an office are looked up -------------------------

@pytest.mark.parametrize(
    "text, subject",
    [
        ("cuantos años tiene jennifer lopez", "jennifer lopez"),
        ("¿Quién es el presidente de Chile?", "el presidente de Chile"),
        ("how old is Taylor Swift", "Taylor Swift"),
        ("who is the current prime minister of the UK", "the current prime minister of the UK"),
        ("qué edad tiene el papa", "el papa"),
        ("sabes cuántos años tiene Shakira?", "Shakira"),
    ],
)
def test_person_facts_are_public_lookups(text: str, subject: str) -> None:
    assert person_fact_subject(text) == subject
    assert record_fact_query(text) is not None
    intent = resolve_explicit_effects(text, {"web.search"})
    assert intent is not None and intent.operations == ("web.search",)


@pytest.mark.parametrize(
    "text",
    ["cuántos años tiene", "cuántos años tienes", "cuántos años tiene mi hijo", "cuántos años tiene él",
     "how old is the ai", "cuantos años tiene baxy", "quién es el presidente"],
)
def test_nobody_named_the_person_or_baxy_is_not_a_person_lookup(text: str) -> None:
    assert person_fact_subject(text) is None


def test_a_person_fact_turn_searches_the_question_words() -> None:
    result = _turn("cuantos años tiene jennifer lopez", ("web.search",), _NoModel())
    assert result["operation"] == "web.search"
    assert result["effectOperations"] == ["web.search"]


@pytest.mark.parametrize(
    "followup, antecedent, completed",
    [
        ("cuántos años tiene", "quién es el presidente de chile", "cuántos años tiene el presidente de chile"),
        ("¿y qué edad tiene?", "¿Quién es Daredevil?", "cuántos años tiene Daredevil"),
        ("how old is he", "who is the ceo of tesla", "how old is the ceo of tesla"),
    ],
)
def test_an_age_asked_without_the_person_takes_the_person_just_asked_about(
    followup: str, antecedent: str, completed: str,
) -> None:
    slot = dialogue.read_slot({}, [{"role": "user", "content": antecedent},
                                   {"role": "assistant", "content": "Una respuesta."}], followup)
    assert dialogue.dependency(followup, slot) == "subject"
    assert dialogue.subject_completed(followup, antecedent) == completed

