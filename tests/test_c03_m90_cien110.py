"""M90: the three turns of cien-110 (tree 50cee2c6, 98/100) that kept cien from 100/100, from the recorded texts.

- 077 «still there?» after 076 «Don't open Word» → «I won't open Word.»: the contextual decider restated «Is Word still
  open?» and ran window.application.status («Word is installed but has no visible windows open.»). Asking whether the
  one answering is there is a social act, read before the decider in both languages (029 «¿sigues ahí?» was right only
  because the turn before named nothing).
- 073 «what is cache memory, one sentence»: the entity reader recovered web.search over the stable-knowledge reading;
  a common concept asked in English with a bare noun is a definition, answered in conversation (REGLAS_ORO rule 1).
- 079 «quién eres» → «Soy BAXY, un programa que vive y corre en este PC. No tengo nombre propio ni edad, solo soy lo
  que haces que yo haga aquí.» (cien-108, 109 and 110 alike): denying a name contradicts the name BAXY.
"""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind import llm
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic.conversation import social_act
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind.semantic.web import _entity_lookup_query, common_concept_definition

OPERATIONS = ("window.application.status", "app.open", "web.search", "system.time", "audio.status")


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


class _Decider:
    """The decision cien-110 recorded (turn-audit) and what the turn asked of the model."""

    def __init__(self, decision: ContextDecision) -> None:
        self.decision = decision
        self.asked: list[str] = []
        self.chats: list[object] = []

    def decide_in_context(self, text: str, history: object, tools: object, **_kwargs: object) -> ContextDecision:
        self.asked.append(text)
        return self.decision

    def chat(self, *_args: object, conversation_kind: object = None, **_kwargs: object) -> tuple[str, list[object]]:
        self.chats.append(conversation_kind)
        return "Yes, I'm here.", []

    def clarify_after_turn_failure(self, *_args: object, **_kwargs: object) -> str:
        return "What should I do?"

    @staticmethod
    def detect_response_language(_text: str) -> str:
        return "en"

    @staticmethod
    def consume_deferred_response_language(_text: str) -> tuple[bool, str | None]:
        return True, "en"

    @staticmethod
    def retire_deferred_response_language(_text: str) -> None:
        return None

    @staticmethod
    def public_lookup_requested(_text: str) -> bool:
        return False

    @staticmethod
    def operation_is_the_requested_effect(*_args: object, **_kwargs: object) -> bool:
        return False

    @staticmethod
    def _verify_semantic_effect_shape(_text: str) -> tuple[str, str]:
        return "no_effect", "zero"


def _turn(text: str, model: _Decider, history: list[tuple[str, str]]) -> dict[str, object]:
    tools = {name: _tool(name) for name in OPERATIONS}
    turns = [{"role": role, "content": content} for role, content in history]
    return sidecar._prepare_turn_result(
        {"id": "m90", "text": text, "history": [*turns, {"role": "user", "content": text}]},
        llm=model,
        planner_catalog=PlannerCatalog(list(tools.values())),
        encoder=lambda _texts: (),
        tool_by_name=tools,
        application_names=("Word", "Paint", "Steam"),
    )


# cien-110 073–076, as the App sent them.
WORD_HISTORY = [
    ("user", "what is cache memory, one sentence"),
    (
        "assistant",
        "Cache memory is a small, high-speed memory used to store frequently accessed data to optimize access time.",
    ),
    ("user", "y por qué importa al abrir programas"),
    (
        "assistant",
        "Importa porque reduce el tiempo de carga al guardar datos críticos que el programa necesita inmediatamente "
        "al iniciar.",
    ),
    ("user", "hora ahora"),
    ("assistant", "La hora actual es 17:42."),
    ("user", "Don't open Word"),
    ("assistant", "I won't open Word."),
]


# ------------------------------------------------------------------ 077: a presence check is said to BAXY


def test_077_still_there_after_word_is_talk_and_reads_no_window() -> None:
    model = _Decider(ContextDecision("Is Word still open?", "action", ("window.application.status",), ""))

    result = _turn("still there?", model, WORD_HISTORY)

    assert model.asked == []
    assert result["kind"] == "conversation"
    assert result.get("effectOperations", []) == []
    assert result.get("operation") is None


def test_029_sigues_ahi_is_the_same_act_in_spanish() -> None:
    model = _Decider(ContextDecision("¿Sigues ahí?", "talk", (), ""))

    result = _turn("¿sigues ahí?", model, [("user", "traduce 'see you' al español, nada más"), ("assistant", "nos vemos")])

    assert model.asked == []
    assert result["kind"] == "conversation"
    assert result.get("effectOperations", []) == []


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("still there?", "en"),
        ("Still there?", "en"),
        ("you there?", "en"),
        ("are you still there?", "en"),
        ("Are you there?", "en"),
        ("hey, you there?", "en"),
        ("hello baxy, are you still there?", "en"),
        ("can you hear me?", "en"),
        ("anyone there?", "en"),
        ("¿sigues ahí?", "es"),
        ("sigues ahi", "es"),
        ("¿seguís ahí?", "es"),
        ("¿estás?", "es"),
        ("¿Estás ahí?", "es"),
        ("¿todavía estás ahí?", "es"),
        ("¿sigues por ahí?", "es"),
        ("¿me escuchas?", "es"),
        ("hola, ¿estás ahí?", "es"),
        ("¿hay alguien ahí?", "es"),
    ],
)
def test_a_presence_check_is_a_social_act_in_both_languages(text: str, language: str) -> None:
    assert social_act(text, []) == ("social", language)
    decision = sidecar._explicit_social_turn_decision(text, [])
    assert decision is not None and decision["effect_operations"] == []


@pytest.mark.parametrize(
    "text",
    [
        "is Word still there?",
        "is Word still open?",
        "¿sigue abierto Word?",
        "¿Word sigue ahí?",
        "the file still there?",
        "¿está ahí?",
        "¿estás bien?",
        "estas",
        "sigues ahí, abre word",
        "are you there, open word",
    ],
)
def test_a_named_thing_or_another_request_is_no_presence_check(text: str) -> None:
    assert sidecar._explicit_social_turn_decision(text, []) is None


def test_a_presence_check_defers_to_a_pending_question() -> None:
    assert social_act("still there?", [{"role": "assistant", "content": "What should I close?"}]) is None


# ------------------------------------------------------------------ 073: a common concept is defined, not looked up


@pytest.mark.parametrize(
    "text",
    [
        "what is cache memory, one sentence",
        "what is photosynthesis",
        "What is photosynthesis?",
        "tell me what is machine learning",
        "what was perestroika",
        "baxy, what is cache memory",
    ],
)
def test_an_english_bare_concept_is_a_definition(text: str) -> None:
    assert common_concept_definition(text)


@pytest.mark.parametrize(
    "text",
    [
        # KNOWLEDGE1473 and the layer-C forms: a named thing, a person or a Spanish bare name stay a lookup.
        "¿Quién es Daredevil?",
        "Que es doom eternal=",
        "explicame que es docker",
        "Dime que es power automate",
        "tell me what is Kubernetes",
        "what is Monkey C",
        "what is C++",
        "what is marvel vs. capcom",
        "who is Nikola Tesla",
        # Not the entity reader's at all.
        "what is four plus five",
        "qué es una GPU",
    ],
)
def test_a_name_keeps_its_lookup(text: str) -> None:
    assert not common_concept_definition(text)


def test_an_installed_program_by_that_name_is_a_name() -> None:
    assert _entity_lookup_query("what is steam") == "steam"
    assert common_concept_definition("what is steam")
    assert not common_concept_definition("what is steam", ("Steam", "Spotify"))


def test_073_cache_memory_is_answered_in_conversation_without_a_search() -> None:
    model = _Decider(ContextDecision("What is cache memory?", "action", ("web.search",), ""))

    result = _turn("what is cache memory, one sentence", model, [])

    assert result["kind"] == "conversation"
    assert result.get("effectOperations", []) == []
    assert result.get("conversationKind", "knowledge") == "knowledge"


@pytest.mark.parametrize("text", ["tell me what is Kubernetes", "what is Monkey C"])
def test_a_named_thing_is_still_looked_up_on_a_first_message(text: str) -> None:
    model = _Decider(ContextDecision(text, "talk", (), ""))

    result = _turn(text, model, [])

    assert result["kind"] == "action"
    assert result["operation"] == "web.search"


# ------------------------------------------------------------------ 079: his name is BAXY, never «no name»


RECORDED_079 = {
    "cien-108": "Soy BAXY, un programa que vive y corre en este PC. No tengo nombre propio ni edad, solo soy lo que "
    "haces que te ayude aquí.",
    "cien-109": "Soy BAXY, un programa que vive y corre en este PC. No tengo nombre propio ni edad, solo soy lo que "
    "haces que te pide.",
    "cien-110": "Soy BAXY, un programa que vive y corre en este PC. No tengo nombre propio ni edad, solo soy lo que "
    "haces que yo haga aquí.",
}


@pytest.mark.parametrize("run", sorted(RECORDED_079))
def test_079_denying_a_name_breaks_the_identity_contract(run: str) -> None:
    assert llm._shaped_conversation_answer_violates_contract(RECORDED_079[run], "quién eres", "identity")
    assert llm._identity_answer_head(RECORDED_079[run], "quién eres") == (
        "Soy BAXY, un programa que vive y corre en este PC."
    )


@pytest.mark.parametrize(
    ("request_text", "draft"),
    [
        ("who are you", "I'm BAXY, a program on this PC. I don't have a name of my own."),
        ("cómo te llamas", "No tengo nombre, soy un programa de este PC."),
        ("what's your name", "I have no name; I am a program on this PC."),
    ],
)
def test_any_denial_of_his_name_is_vetoed(request_text: str, draft: str) -> None:
    assert llm._shaped_conversation_answer_violates_contract(draft, request_text, "identity")


@pytest.mark.parametrize(
    ("request_text", "draft"),
    [
        ("quién eres", "Soy BAXY, un programa que vive y corre en este PC."),
        # cien-110 032/056/099: the facts he lacks are no name denial.
        ("who are you", "I am BAXY, a program running on this PC. I do not have a body, tastes, hobbies, or free time."),
        ("¿no tienes nombre?", "Sí, me llamo BAXY; no tengo otro nombre."),
    ],
)
def test_his_name_and_the_facts_he_lacks_still_pass(request_text: str, draft: str) -> None:
    assert not llm._shaped_conversation_answer_violates_contract(draft, request_text, "identity")
    assert llm._identity_answer_head(draft, request_text) == draft


class _Writer(llm.LlmRuntime):
    """The drafts stand in for the model, in order (the last one repeats); every payload sent is kept."""

    def __init__(self, drafts: list[str]) -> None:  # noqa: D107
        self._gguf = r"D:\BAXYRuntime\assets\models\granite-4.2-3b-Q4_K_M.gguf"
        self._drafts = list(drafts)
        self.sent: list[dict] = []

    def _post(self, payload, **_):  # noqa: ANN001, ANN201
        self.sent.append(payload)
        content = self._drafts.pop(0) if len(self._drafts) > 1 else self._drafts[0]
        return {"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}


def test_079_the_first_sentence_is_published_without_writing_it_again() -> None:
    writer = _Writer([RECORDED_079["cien-110"], "No debería pedirse otra redacción."])

    answer, _ = writer.chat("quién eres", history=[], conversation_kind="knowledge", response_language="es")

    assert answer == "Soy BAXY, un programa que vive y corre en este PC."
    assert len(writer.sent) == 1
