"""Tanda 4 (2026-09-24, official window): complete requests answered with a yes/no offer.

«find instructions on how to play taboo» → «Want me to show you how to play Taboo?», «let me know what today's
date is» → «Want me to tell you today's date…?», «please put the meeting with carla on my to do list» → «Want me to
add…?», and earlier «me apetece que hagas sonar algo alegre» → «¿Quieres que reproduzca una canción alegre?».
00_IDENTIDAD («actúa solo y luego cuenta») and D3 (confirm only what destroys data): a read, a search, playing,
adding a task are done and then told.

Three producers wrote those offers with one prompt that demanded «¿Quieres que …?»: the withheld proposal after
the domain veto, the catalogue probe after a knowledge verdict, and the served-surface re-read. None asked for a
missing value. A withheld or probed operation now acts when the canonical surface or the strict verifier grounds
it and its risk allows acting unasked. When only the identity verifier names it, BAXY is unsure, not unable: a
false limit is worse than a question, so it asks once, naming the operation it would run (never restating the
request). Named by neither, the turn answers or keeps its limit. The readers also read the everyday forms directly.

The phrasings below are not the tanda's, except the three real messages named as such.
"""

from __future__ import annotations

import json

import pytest

from baxy_mind import __main__ as mind_main
from baxy_mind.__main__ import _explicit_arguments_from_evidence, _prepare_turn_result
from baxy_mind.llm import OPERATION_COMPATIBILITY_PROMPT, LlmRuntime
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import surface
from baxy_mind.semantic.reading import read

OPERATIONS = (
    "system.time", "task.create", "task.list", "web.search", "media.play.query", "media.play.youtube",
    "reminder.create", "calendar.event.list", "filesystem.search", "note.search", "media.control",
)


def _effects(text: str) -> tuple[str, ...]:
    reading = read(text, available_operations=OPERATIONS)
    return reading.effects.operations if reading.effects is not None else ()


# ------------------------------------------------------------------ the readers


@pytest.mark.parametrize(
    "text",
    [
        "let me know what today's date is",  # the real message (t19)
        "can you let me know what the date is today",
        "please let me know the current time",
        "let me know what time it is",
        "tell me what today's date is",
        "could you tell me what the date is",
        "i'd like to know what day it is",
        "i would like to know the time",
        "hazme saber qué fecha es hoy",
        "avísame qué hora es",
        "me gustaría saber qué hora es",
        "dime what time it is",
        "let me know qué día es hoy",
    ],
)
def test_asking_to_be_told_the_date_or_time_reads_this_pc_clock(text: str) -> None:
    assert _effects(text) == ("system.time",)


@pytest.mark.parametrize(
    "text",
    [
        "let me know when the meeting is",
        "tell me what date easter is this year",
        "let me know what time the match starts",
        "avísame a qué hora sale el tren",
    ],
)
def test_the_date_or_time_of_something_else_is_never_this_pc_clock(text: str) -> None:
    assert "system.time" not in _effects(text)


def test_the_time_of_another_place_is_this_clock_read_with_that_place() -> None:
    # Tanda 4 (web answers and time arithmetic): another place's time is the
    # clock read together with that place's zone, never this clock recited.
    from baxy_mind import __main__ as mind_main

    text = "i'd like to know what time it is in tokyo"
    assert _effects(text) == ("system.time",)
    assert mind_main._explicit_arguments_from_evidence("system.time", text) == {"place": "tokyo"}


@pytest.mark.parametrize(
    ("text", "title"),
    [
        ("please put the meeting with carla on my to do list", "meeting with carla"),  # the real message (t39)
        ("put call the dentist on my to do list", "call the dentist"),
        ("add buy stamps to my to do list", "buy stamps"),
        ("add the meeting with carla to my to do list please", "meeting with carla"),
        ("put the gym on my task list", "gym"),
        ("agrega call jorge a mi to do list", "call jorge"),
        ("please añade the report to my to do list", "report"),
    ],
)
def test_an_entry_put_on_the_to_do_list_is_a_task(text: str, title: str) -> None:
    assert _effects(text) == ("task.create",)
    assert _explicit_arguments_from_evidence("task.create", text)["title"] == title


@pytest.mark.parametrize(
    "text",
    [
        "don't add milk to my to do list",
        "add this song to my playlist",
        "remove the meeting with carla from my to do list",
        "put the meeting in my calendar",
    ],
)
def test_what_is_not_an_entry_on_the_to_do_list_is_never_a_task(text: str) -> None:
    assert "task.create" not in _effects(text)


def test_asking_what_is_on_the_to_do_list_said_apart_reads_it() -> None:
    assert _effects("what's on my to do list") == ("task.list",)


@pytest.mark.parametrize(
    ("text", "query"),
    [
        ("find instructions on how to play taboo", "how to play taboo"),  # the real message (t10)
        ("find me instructions on how to set up a fish tank", "how to set up a fish tank"),
        ("find a tutorial on how to solve a rubik's cube", "how to solve a rubik's cube"),
        ("look up instructions for playing uno", "instructions for playing uno"),
        ("find the rules of monopoly", "the rules of monopoly"),
        ("find steps to tie a bow tie", "steps to tie a bow tie"),
        ("encuentra instrucciones de cómo jugar al dominó", "cómo jugar al dominó"),
        ("búscame un tutorial de cómo hacer pan", "cómo hacer pan"),
        ("busca las reglas del parchís", "las reglas del parchís"),
        ("encuentra cómo cambiar una rueda", "cómo cambiar una rueda"),
        ("find instrucciones para jugar al truco", "instrucciones para jugar al truco"),
    ],
)
def test_instructions_for_how_something_is_done_are_looked_up(text: str, query: str) -> None:
    assert _effects(text) == ("web.search",)
    assert _explicit_arguments_from_evidence("web.search", text) == {"query": query}


@pytest.mark.parametrize(
    "text",
    [
        "find the file instructions.txt",
        "find my notes about taboo",
        "busca en mis documentos las instrucciones",
        "find instructions in my downloads folder",
        "search my files for how to play taboo",
        "tell me how you work",
    ],
)
def test_instructions_kept_on_this_pc_are_never_a_public_search(text: str) -> None:
    assert "web.search" not in _effects(text)


@pytest.mark.parametrize(
    ("text", "query"),
    [("pon algo alegre", "algo alegre"), ("ponme algo movido", "algo movido"), ("pon algo tranquilo", "algo tranquilo")],
)
def test_something_with_its_character_names_the_music_to_play(text: str, query: str) -> None:
    reading = read(text, available_operations=OPERATIONS)
    assert reading.clarification is None
    assert reading.effects is not None and reading.effects.operations == ("media.play.youtube",)
    assert _explicit_arguments_from_evidence("media.play.youtube", text) == {"query": query}


def test_the_desire_to_hear_something_joyful_is_played_on_its_canonical_surface() -> None:
    canonical = surface.canonical("me apetece que hagas sonar algo alegre")
    assert canonical == "pon algo alegre"
    assert _effects(canonical) == ("media.play.youtube",)


@pytest.mark.parametrize("text", ["pon algo", "pon algo aquí", "pon algo para dormir", "pon algo nuevo"])
def test_something_without_a_character_still_asks_what_to_play(text: str) -> None:
    reading = read(text, available_operations=OPERATIONS)
    assert reading.effects is None
    assert reading.clarification is not None and reading.clarification.operations == ("media.play.query",)


# ------------------------------------------------------------------ the real messages, end to end


class _ReaderOnlyLlm:
    """The readers decide these turns: the model is never asked to decide, confirm or offer."""

    @staticmethod
    def decide_turn(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise AssertionError("a request the readers read is not decided by the model")

    @staticmethod
    def operation_is_the_requested_effect(*_args: object, **_kwargs: object) -> bool:
        return True

    @staticmethod
    def _verify_semantic_effect_shape(_text: str) -> tuple[str, str]:
        return "complete", "one"

    @staticmethod
    def consume_deferred_response_language(_text: str) -> tuple[bool, str | None]:
        return True, "en"

    @staticmethod
    def retire_deferred_response_language(_text: str) -> None:
        return None

    @staticmethod
    def detect_response_language(_text: str) -> str:
        return "en"


def _tool(operation: str, *, required: tuple[str, ...] = (), risk: str = "read_only") -> dict[str, object]:
    return {
        "type": "function",
        "function": {
            "name": operation.replace(".", "_"),
            "canonical_name": operation,
            "description": f"Authenticated catalog leaf {operation}.",
            "risk": risk,
            "parameters": {
                "type": "object",
                "properties": {name: {"type": "string", "minLength": 1} for name in required},
                "required": list(required),
                "additionalProperties": False,
            },
        },
    }


class _NoEvidence:
    @staticmethod
    def candidate_families(_text: str, _encoder: object) -> tuple[str, ...]:
        return ()

    @staticmethod
    def retrieve(*_args: object, **_kwargs: object) -> list[object]:
        return []


@pytest.mark.parametrize(
    ("text", "operation", "required"),
    [
        ("let me know what today's date is", "system.time", ()),
        ("please put the meeting with carla on my to do list", "task.create", ("title",)),
        ("find instructions on how to play taboo", "web.search", ("query",)),
        # «how to» after an order to search is what to look up; it used to close the turn as a how-to
        # explanation that forbids tools (unresolved_compound_effects).
        ("busca cómo se juega a la brisca", "web.search", ("query",)),
        ("look up how to play mahjong", "web.search", ("query",)),
    ],
)
def test_the_real_messages_act_and_ask_nothing(text: str, operation: str, required: tuple[str, ...]) -> None:
    tool = _tool(operation, required=required, risk="low_reversible" if operation == "task.create" else "read_only")
    result = _prepare_turn_result(
        {"id": "tanda-04", "text": text},
        llm=_ReaderOnlyLlm(),
        planner_catalog=PlannerCatalog([tool]),
        turn_evidence=_NoEvidence(),
        encoder=lambda _texts: (),
        tool_by_name={operation: tool},
    )
    assert result["kind"] == "action"
    assert result["operation"] == operation
    assert result["question"] == ""


@pytest.mark.parametrize("text", ["explícame cómo hacer pan", "tell me how to tie a tie without tools"])
def test_a_how_to_explanation_that_orders_no_search_keeps_its_closed_contract(text: str) -> None:
    from baxy_mind.semantic.patterns import resolve_explicit_effects, unresolved_compound_contract

    contract = unresolved_compound_contract(
        text, OPERATIONS, resolved_intent=resolve_explicit_effects(text, OPERATIONS),
    )
    assert contract is not None and contract.clause_requirements == ()


# ------------------------------------------------------------------ the mechanism


def test_the_unsure_question_names_the_operation_and_never_restates_the_request() -> None:
    import baxy_mind.llm as llm_module

    # The restating «¿Quieres que …?» composer is gone.
    assert not hasattr(llm_module, "DOMAIN_CONFIRMATION_PROMPT")
    assert not hasattr(mind_main, "_domain_confirmation_question")
    prompt = llm_module.OPERATION_CONFIRMATION_PROMPT
    assert "No estás seguro" in prompt
    assert "operación concreta que ejecutarías" in prompt
    assert "No repitas ni reformules el pedido" in prompt
    assert "«¿Quieres que" not in prompt

    runtime = object.__new__(LlmRuntime)
    captured: dict[str, object] = {}

    def response(payload: dict, **_kwargs: object) -> dict:
        captured.update(payload)
        return {"choices": [{"message": {"content": '{"question":"¿Leo el reloj de este PC?"}'}}]}

    runtime._post = response  # type: ignore[method-assign]
    runtime._normalize_request_budget = lambda timeout: timeout  # type: ignore[method-assign]
    question = runtime.confirm_operation_before_acting(
        "what does my machine think the date is", (("system.time", "Lee la fecha y hora actuales."),),
    )
    assert question == "¿Leo el reloj de este PC?"
    messages = captured["messages"]
    assert messages[0] == {"role": "system", "content": prompt}
    assert "system.time | Lee la fecha y hora actuales." in messages[-1]["content"]


def test_the_acting_verdict_is_the_strict_one() -> None:
    runtime = object.__new__(LlmRuntime)
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def strict(*args: object, **kwargs: object) -> bool:
        calls.append((args, kwargs))
        return True

    runtime._operation_is_fully_compatible = strict  # type: ignore[method-assign]
    assert runtime.operation_satisfies_the_request("t", "system.time", {"description": "d"}) is True
    # The default prompt of the verifier is the strict one; the identity prompt is never passed.
    assert calls == [(("t", "system.time", {"description": "d"}), {})]
    assert "cobertura directa completa" in OPERATION_COMPATIBILITY_PROMPT


class _Strict:
    def __init__(self, verdict: bool | Exception) -> None:
        self.verdict = verdict
        self.calls: list[str] = []

    def operation_satisfies_the_request(self, _text: str, operation: str, _contract: object) -> bool:
        self.calls.append(operation)
        if isinstance(self.verdict, Exception):
            raise self.verdict
        return self.verdict


_TOOLS = {
    "filesystem.folder.open": _tool("filesystem.folder.open"),
    "network.status": _tool("network.status"),
    "app.close": _tool("app.close", risk="work_loss"),
    "email.send": _tool("email.send", risk="external_communication"),
}


def test_a_served_surface_the_reread_proved_grounds_without_the_verifier() -> None:
    llm = _Strict(False)
    assert mind_main._acts_without_asking(
        "Muéstrame mi carpeta de imagenes.", ("filesystem.folder.open",), _TOOLS, llm, (), rewrite_grounded=True,
    )
    assert llm.calls == []
    # Said as said, the rewrite is not evidence here: the re-read decides that surface with the readers first.
    assert not mind_main._acts_without_asking("Muéstrame mi Gallery.", ("filesystem.folder.open",), _TOOLS, llm, ())
    assert llm.calls == ["filesystem.folder.open"]


@pytest.mark.parametrize(
    ("verdict", "acts"), [(True, True), (False, False), (RuntimeError("down"), False)],
)
def test_without_the_surface_only_the_strict_verdict_lets_it_act(verdict: bool | Exception, acts: bool) -> None:
    llm = _Strict(verdict)
    text = "is my machine talking to the outside world right now?"
    assert mind_main._acts_without_asking(text, ("network.status",), _TOOLS, llm, ()) is acts
    assert llm.calls == ["network.status"]


def test_a_missing_verifier_never_lets_it_act() -> None:
    assert not mind_main._acts_without_asking(
        "is my machine talking to the outside world right now?", ("network.status",), _TOOLS, object(), (),
    )


@pytest.mark.parametrize("operation", ["app.close", "email.send"])
def test_what_destroys_or_sends_never_acts_unasked_whatever_grounds_it(operation: str) -> None:
    llm = _Strict(True)
    assert not mind_main._acts_without_asking("close it", (operation,), _TOOLS, llm, (), rewrite_grounded=True)
    assert not mind_main._acts_without_asking("close it", (operation,), _TOOLS, llm, ())
    assert llm.calls == []


def test_one_ungrounded_member_keeps_the_whole_set_from_acting() -> None:
    llm = _Strict(True)
    assert not mind_main._acts_without_asking(
        "is my machine online and send it to ana", ("network.status", "email.send"), _TOOLS, llm, (),
    )


class _Verdicts(_Strict):
    def __init__(self, strict: bool, identity: bool, question: str = "¿Reviso la red de este PC?") -> None:
        super().__init__(strict)
        self.identity = identity
        self.question = question
        self.identity_calls: list[str] = []

    def operation_is_the_requested_effect(self, _text: str, operation: str, _contract: object) -> bool:
        self.identity_calls.append(operation)
        return self.identity

    def confirm_operation_before_acting(self, *_args: object, **_kwargs: object) -> str:
        return self.question


_UNSURE_TEXT = "is my machine talking to the outside world right now?"


@pytest.mark.parametrize(
    ("strict", "identity", "verdict"),
    [
        (True, True, ("act", "")),  # strict accepts: act, identity never asked
        (True, False, ("act", "")),
        (False, True, ("ask", "¿Reviso la red de este PC?")),  # unsure, not unable: one question
        (False, False, ("", "")),  # named by neither: the limit or the model's answer
    ],
)
def test_the_three_branches_of_a_withheld_operation(strict: bool, identity: bool, verdict: tuple[str, str]) -> None:
    llm = _Verdicts(strict, identity)
    assert mind_main._withheld_operation_verdict(_UNSURE_TEXT, ("network.status",), _TOOLS, llm, ()) == verdict
    assert llm.identity_calls == ([] if strict else ["network.status"])


def test_an_unsure_question_that_restates_nothing_valid_is_not_published() -> None:
    llm = _Verdicts(False, True, question="claro que sí")
    assert mind_main._withheld_operation_verdict(_UNSURE_TEXT, ("network.status",), _TOOLS, llm, ()) == ("", "")


class _KnowledgeLlm:
    """The model answers from what it knows; the catalogue probe names this PC's clock."""

    def __init__(self, *, satisfies: bool, identifies: bool = True) -> None:
        self.satisfies = satisfies
        self.identifies = identifies
        self.strict_calls: list[str] = []
        self.confirmations: list[tuple[tuple[str, str], ...]] = []
        self.chats = 0

    @staticmethod
    def decide_turn(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {
            "mode": "conversation", "operation": None, "question": "", "conversation_kind": "knowledge",
            "effect_count": "zero", "effect_operations": [], "effect_verification": "not_applicable",
            "response_language": "en",
        }

    @staticmethod
    def public_lookup_requested(_text: str) -> bool:
        return False

    def operation_is_the_requested_effect(self, _text: str, operation: str, _contract: object) -> bool:
        return self.identifies and operation == "system.time"

    def confirm_operation_before_acting(
        self, _text: str, effects: tuple[tuple[str, str], ...], **_kwargs: object,
    ) -> str:
        self.confirmations.append(effects)
        return "Should I read this PC's clock?"

    def operation_satisfies_the_request(self, _text: str, operation: str, _contract: object) -> bool:
        self.strict_calls.append(operation)
        return self.satisfies

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

    def chat(self, *_args: object, **_kwargs: object) -> tuple[str, list[object]]:
        self.chats += 1
        return "Your computer keeps its own calendar.", []


def _knowledge_turn(llm: _KnowledgeLlm, risk: str = "read_only") -> dict[str, object]:
    tool = _tool("system.time", risk=risk)
    return _prepare_turn_result(
        {"id": "tanda-04-probe", "text": "what does my machine think the date is"},
        llm=llm,
        planner_catalog=PlannerCatalog([tool]),
        turn_evidence=_NoEvidence(),
        encoder=lambda _texts: (),
        tool_by_name={"system.time": tool},
    )


def test_what_the_catalogue_probe_names_and_the_strict_verdict_grounds_is_observed_not_offered() -> None:
    llm = _KnowledgeLlm(satisfies=True)
    result = _knowledge_turn(llm)

    assert result["kind"] == "action"
    assert result["operation"] == "system.time"
    assert result["question"] == ""
    assert llm.strict_calls == ["system.time"]
    assert llm.chats == 0


def test_what_only_the_identity_names_is_asked_once_naming_the_operation() -> None:
    llm = _KnowledgeLlm(satisfies=False)
    result = _knowledge_turn(llm)

    assert result["kind"] == "clarify"
    assert result["question"] == "Should I read this PC's clock?"
    assert result["intentOperations"] == ["system.time"]
    assert result["effectOperations"] == []
    assert [[name for name, _ in effects] for effects in llm.confirmations] == [["system.time"]]
    assert llm.strict_calls == ["system.time"]
    assert llm.chats == 0


def test_what_neither_verifier_names_leaves_the_model_answer_and_asks_nothing() -> None:
    llm = _KnowledgeLlm(satisfies=True, identifies=False)
    result = _knowledge_turn(llm)

    assert result["kind"] == "conversation"
    assert result["question"] == ""
    assert result["effectOperations"] == []
    assert result["intentOperations"] == []
    assert llm.confirmations == []
    assert llm.chats == 1


def test_the_probe_never_acts_unasked_on_an_operation_whose_risk_forbids_it() -> None:
    llm = _KnowledgeLlm(satisfies=True)
    result = _knowledge_turn(llm, risk="external_communication")

    # Asked, naming the operation; never done unasked, and the strict verdict is not consulted.
    assert result["kind"] == "clarify"
    assert result["effectOperations"] == []
    assert llm.strict_calls == []


def test_the_recovered_decision_is_an_action_that_asks_nothing() -> None:
    decision = mind_main._recovered_action_decision("system.time", "en")
    assert json.loads(json.dumps(decision)) == {
        "mode": "action", "operation": "system.time", "question": "", "conversation_kind": "",
        "effect_count": "one", "effect_operations": ["system.time"], "effect_verification": "recovered",
        "response_language": "en",
    }
