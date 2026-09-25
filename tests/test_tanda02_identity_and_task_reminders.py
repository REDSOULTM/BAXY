"""tanda-02 (2026-09-23, official window): questions about BAXY himself and tasks to remember.

- A question addressed to BAXY about himself —origin, who made him and when, his name, what he
  is, where he lives, whether he is real, what he does with his free time— is an identity turn:
  answered from BAXY's own facts, never searched, never a question back, never an invented
  maker, date, age or hobby. Only a question for the name needs the name in the answer.
- Remembering a task to do («recuerda arreglar una reunión … mañana a las siete») is a reminder
  with its moment and title, not a datum for the private memory; «recuerda que <dato>» is not
  read as a reminder.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from baxy_mind import __main__ as mind_main  # noqa: E402
from baxy_mind import llm as llm_module  # noqa: E402
from baxy_mind.planner import PlannerCatalog  # noqa: E402
from baxy_mind.semantic.request import (  # noqa: E402
    INTENT_CAPABILITY,
    INTENT_IDENTITY,
    read_request,
)
from baxy_mind.semantic.reading import read  # noqa: E402

from test_uso_real_facts_and_effects import (  # noqa: E402
    _WEB_SEARCH,
    _GuardSaysPublic,
    _IdentityTurnLlm,
    _turn,
)

# --- 1. Every question about BAXY himself is identity ---------------------------------

_ABOUT_BAXY = [
    "¿cuál es tu lugar de origen?",
    "¿quién ha tenido la idea de crearte?",
    "¿cuándo te crearon?",
    "the creator of your ai, what is their name",
    "what keeps you busy in your free time",
    "¿dónde vives?",
    "where do you live",
    "¿existes en el mundo real?",
    "are you real?",
    "¿eres una persona?",
    "are you a robot",
    "¿qué eres?",
    "what are you",
    "¿cómo te llamas?",
    "what do you do for fun",
    "¿tienes hobbies?",
    "¿qué te gusta hacer?",
    "who came up with the idea of creating you",
    "since when do you exist",
    "¿en qué año te crearon?",
    "¿dónde te desarrollaron?",
    "¿qué haces en tu tiempo libre?",
]

_NOT_ABOUT_BAXY = [
    "no te creo",
    "¿puedo hacerte una pregunta?",
    "¿cómo te hizo sentir eso?",
    "how can I build you a website",
    "what are you doing",
    "quién creó el iPhone",
    "who invented AI",
    "¿dónde vive el presidente?",
    "¿existe vida en Marte?",
]


@pytest.mark.parametrize("text", _ABOUT_BAXY)
def test_every_question_about_baxy_himself_is_an_identity_turn(text: str) -> None:
    reading = read_request(text)
    assert reading.has(INTENT_IDENTITY), text
    # A trait of BAXY is not a question about what he does on the PC.
    assert not reading.has(INTENT_CAPABILITY), text
    assert (
        llm_module._conversation_presentation_shape(
            text, conversation_kind="knowledge", has_history=False,
        )
        == "identity"
    )


@pytest.mark.parametrize("text", _NOT_ABOUT_BAXY)
def test_a_you_that_is_not_about_baxy_himself_is_not_identity(text: str) -> None:
    assert not read_request(text).has(INTENT_IDENTITY), text


@pytest.mark.parametrize(
    "text", ["who are you and what can you do", "¿qué puedes hacer?", "what do you do"]
)
def test_a_capability_named_in_so_many_words_still_reads_as_capability(text: str) -> None:
    assert read_request(text).has(INTENT_CAPABILITY)


@pytest.mark.parametrize("text", _ABOUT_BAXY)
def test_a_question_about_baxy_is_never_a_public_lookup(text: str) -> None:
    guard = _GuardSaysPublic()
    catalog = PlannerCatalog([_WEB_SEARCH])
    assert not mind_main._public_lookup_applies(text, text, guard, ("web.search",), catalog)


class _SearchingModel(_IdentityTurnLlm):
    """A model that would search «¿cuándo te crearon?» (tanda-02 turn 48)."""

    def __init__(self) -> None:
        super().__init__()
        self.decisions = 0

    def decide_turn(self, *_args: object, **_kwargs: object) -> dict[str, object]:
        self.decisions += 1
        return {
            "mode": "action", "operation": "web.search", "question": "",
            "conversation_kind": None, "effect_count": "one",
            "effect_operations": ["web.search"], "effect_verification": "observed",
            "response_language": "es",
        }


@pytest.mark.parametrize(
    "text",
    ["¿cuándo te crearon?", "¿quién ha tenido la idea de crearte?", "what keeps you busy in your free time"],
)
def test_the_identity_reading_owns_the_turn_before_a_model_can_search(text: str) -> None:
    model = _SearchingModel()
    result = _turn(text, ("web.search",), model)
    assert result["kind"] == "conversation"
    assert result["operation"] is None
    assert result["effectOperations"] == []
    assert "web.search" not in result["intentOperations"]
    assert model.decisions == 0
    assert model.chat_texts == [text]


# --- 2. The identity answer: BAXY's facts only -------------------------------------------

_violates = llm_module._shaped_conversation_answer_violates_contract


@pytest.mark.parametrize(
    ("request_text", "reply"),
    [
        # tanda-02 turn 12: both drafts were right and died for not saying «BAXY».
        ("¿cuál es tu lugar de origen?", "No tengo un lugar de origen ni una edad. Vivo en este PC."),
        ("¿cuál es tu lugar de origen?", "No tengo un lugar de origen ni una edad, solo existo en este PC."),
        ("¿quién ha tenido la idea de crearte?", "No tengo el dato de quién tuvo la idea de crearme; vivo en este PC."),
        ("what keeps you busy in your free time", "I don't have free time or hobbies; I'm BAXY and I live on this PC."),
        ("¿existes en el mundo real?", "Sí, existo como un programa que corre en este PC, no como una persona."),
        ("¿qué te gusta hacer?", "No me gusta nada en especial: no tengo gustos, vivo en este PC para ayudarte."),
        ("¿cómo te llamas?", "Me llamo BAXY y vivo en este PC."),
    ],
)
def test_an_answer_from_baxys_facts_passes(request_text: str, reply: str) -> None:
    assert not _violates(reply, request_text, "identity")


@pytest.mark.parametrize(
    ("request_text", "reply"),
    [
        # tanda-02: an invented hobby.
        ("what keeps you busy in your free time", "In my free time I enjoy coding and fixing bugs."),
        ("what keeps you busy in your free time", "I'm BAXY and I love coding and fixing bugs."),
        ("¿qué te gusta hacer?", "Soy BAXY y me encanta escuchar música."),
        ("¿tienes hobbies?", "Soy BAXY; mi pasatiempo favorito es leer."),
        # tanda-02: an invented maker, and a date.
        ("¿quién ha tenido la idea de crearte?", "Soy BAXY, un modelo de lenguaje desarrollado por OpenAI."),
        ("¿cuándo te crearon?", "Soy BAXY y me crearon en 2025."),
        # The name asked for and not said.
        ("¿cómo te llamas?", "Soy un compañero que vive en este PC."),
        ("who are you", "I'm the assistant that lives on this PC."),
        # A question back.
        ("¿cuál es tu lugar de origen?", "¿Te refieres a un lugar geográfico?"),
    ],
)
def test_an_invented_trait_or_a_missing_name_is_rejected(request_text: str, reply: str) -> None:
    assert _violates(reply, request_text, "identity")


def test_the_identity_instructions_hold_baxys_facts_and_forbid_invention() -> None:
    prompt = llm_module.IDENTITY_PRESENTATION_PROMPT
    assert "lives and runs on this PC" in prompt
    assert "no body, tastes, hobbies or free time" in prompt
    assert "not a person" in prompt
    assert "say plainly you do not have that" in prompt


class _AlwaysFailingRecovery:
    """The identity wording failed twice; the recovery model would ask back."""

    @staticmethod
    def clarify_after_turn_failure(*_args: object, **_kwargs: object) -> str:
        return "¿Te refieres a un lugar geográfico o a algo más específico?"

    @staticmethod
    def compose_user_message(*_args: object, **_kwargs: object) -> str:
        return "¿Te refieres a un lugar geográfico o a algo más específico?"


@pytest.mark.parametrize("text", ["¿cuál es tu lugar de origen?", "¿cuándo te crearon?"])
def test_a_failed_identity_turn_is_never_recovered_as_a_question(text: str) -> None:
    result = mind_main._recover_failed_turn(
        {"id": "tanda-02", "text": text, "history": []},
        _AlwaysFailingRecovery(),
        failure_kinds=("runtime", "runtime"),
    )
    assert result["kind"] == "conversation"
    assert result["question"] == ""
    # The composed question is not smuggled out as the reply either.
    assert "?" not in result["reply"]
    assert result["operation"] is None
    assert result["effectOperations"] == []


def test_a_failed_turn_about_something_else_still_gets_its_question() -> None:
    result = mind_main._recover_failed_turn(
        {"id": "tanda-02", "text": "¿cuál es el lugar de origen del tango?", "history": []},
        _AlwaysFailingRecovery(),
        failure_kinds=("runtime", "runtime"),
    )
    assert result["kind"] == "clarify"


# --- 3. A task to remember is a reminder, a datum is not ---------------------------------

_OPERATIONS = ("reminder.create", "notification.schedule", "task.create", "reminder.list", "web.search")


@pytest.mark.parametrize(
    "text",
    [
        "recuerda arreglar una reunión entre los jugadores y yo mañana por la tarde noche a las siete",
        "recuerda llamar a mamá esta tarde a las cinco",
        "recordá sacar la basura en 20 minutos",
        "acordate de pagar la luz el viernes",
        "acuérdate de llevarle el cargador a Ana mañana",
        "remember to call Ana tomorrow at 6 pm",
    ],
)
def test_a_task_to_remember_with_its_moment_is_a_reminder(text: str) -> None:
    reading = read(text, available_operations=_OPERATIONS)
    assert reading.effects is not None
    assert reading.effects.operations == ("reminder.create",)


@pytest.mark.parametrize(
    "text",
    [
        "recuerda que tengo prueba mañana",
        "recuerda que mi hermana vive en Curicó",
        "remember that I prefer tea",
        # A task with no moment is a deferred action, not a reminder.
        "recuerda abrir Steam cuando te lo pregunte",
    ],
)
def test_a_datum_or_an_undated_task_is_not_read_as_a_reminder(text: str) -> None:
    reading = read(text, available_operations=_OPERATIONS)
    assert reading.effects is None or "reminder.create" not in reading.effects.operations


@pytest.mark.parametrize(
    ("text", "due", "title"),
    [
        (
            "recuerda arreglar una reunión entre los jugadores y yo mañana por la tarde noche a las siete",
            "a las siete",
            "arreglar una reunión entre los jugadores y yo mañana por la tarde noche",
        ),
        ("remember to call Ana at 6 pm", "at 6 pm", "call Ana"),
        ("acordate de pagar la luz en 20 minutos", "en 20 minutos", "pagar la luz"),
    ],
)
def test_the_task_reminder_keeps_its_literal_moment_and_title(text: str, due: str, title: str) -> None:
    arguments = mind_main._explicit_arguments_from_evidence("reminder.create", text)
    assert arguments == {"dueUtc": due, "title": title}
