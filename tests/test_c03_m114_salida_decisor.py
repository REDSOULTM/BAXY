"""M114 (2026-10-01): what the app's contextual decider reads is what its LoRA was trained and measured on.

Evidence (window runs v4e-devD at a1739b28, v4d-devF and v4e-devF against the decider alone, soup V0a, full3): of the
context_decider turns, the app's audited decision equalled the isolated one in 188/223 (D) and 194/210 (F). Replayed
offline with the isolated decision and the app's own history, the mind's overrides explain 10 of the 35 differences on
D (M53/M88 lookups of D35, M84 take-backs, M85, M89, M99, M64+M110) and none on F; the other 25 + 16 are the model
writing something else. Every follow-up among them read a different conversation (BAXY's real earlier replies), and
the first turns (10 on D, 1 on F) read a different prompt: the app's catalog left out the eleven ``memory.*`` lines and
their names in the schema's enum, which the LoRA was trained with and the isolated run had (system 25 481 against
26 873 characters). Memory stays the App's own path: never planned, shortlisted or grounded by the mind.
"""

from __future__ import annotations

from typing import Any

from baxy_mind import __main__ as sidecar
from baxy_mind import effect_intent
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import decider
from baxy_mind.semantic.temporal import clock_elsewhere

OPERATIONS = ("media.status", "memory.recall", "memory.save", "note.create", "web.search")


def _tool(operation: str) -> dict[str, object]:
    return {
        "type": "function",
        "function": {
            "name": operation.replace(".", "_"),
            "canonical_name": operation,
            "description": f"Authenticated catalog leaf {operation}.",
            "risk": "read_only",
            "parameters": {
                "type": "object",
                "properties": {"selector": {"type": "string"}},
                "required": ["selector"],
                "additionalProperties": False,
            },
        },
    }


TOOLS = {operation: _tool(operation) for operation in OPERATIONS}


class _Model:
    def __init__(self, decision: str, operations: tuple[str, ...], request: str) -> None:
        self.decided = decider.ContextDecision(request=request, decision=decision, operations=operations, question="")
        self.tools: list[tuple[str, str]] = []
        self.signatures: dict[str, tuple[str, ...]] = {}

    def decide_in_context(self, _text: str, _history: object, tools: Any, **kwargs: Any) -> decider.ContextDecision:
        self.tools = list(tools)
        self.signatures = kwargs.get("signatures") or {}
        return self.decided

    @staticmethod
    def chat(*_args: object, **_kwargs: object) -> tuple[str, list]:
        return "Hola.", []


def _decided(model: _Model, text: str) -> dict[str, Any]:
    return sidecar._context_decided_result(
        {"id": "m114", "text": text, "history": [{"role": "user", "content": text}]},
        llm=model,
        planner_catalog=PlannerCatalog(list(TOOLS.values())),
    )


def test_memory_is_in_the_decider_catalog_and_never_in_the_planning_one() -> None:
    catalog = PlannerCatalog(list(TOOLS.values()))
    assert [tool.name for tool in catalog.tools] == ["media.status", "note.create", "web.search"]
    assert [tool.name for tool in catalog.decider_tools] == list(OPERATIONS)
    assert catalog.get("memory.save") is None
    assert all(not tool.name.startswith("memory.") for tool in catalog.shortlist("recuerda que me gusta esta canción"))


def test_the_decider_reads_the_memory_lines_it_was_trained_with() -> None:
    model = _Model("talk", (), "Hola.")
    _decided(model, "hola")
    assert [name for name, _ in model.tools] == list(OPERATIONS)
    assert model.signatures["memory.save"] == ("selector",)
    prompt = decider.catalog_prompt(model.tools, model.signatures)
    assert "[memoria privada]" in prompt and "- memory.recall(selector):" in prompt


def test_a_memory_choice_travels_alone_to_the_apps_memory_path() -> None:
    text = "me gustaría que recordases que me gusta esta canción"
    request = "Recuerda que me gusta esta canción."
    result = _decided(_Model("action", ("memory.save",), request), text)
    assert result["kind"] == "action" and result["operation"] == "memory.save"
    assert result["effectOperations"] == ["memory.save"]
    # Never planned with other steps: the App does not plan memory, it answers it on its own path.
    result = _decided(_Model("action", ("media.status", "memory.save"), request), text)
    assert result["kind"] == "action" and result["effectOperations"] == ["memory.save"]


def test_a_choice_without_memory_is_kept_as_decided() -> None:
    result = _decided(_Model("action", ("note.create",), "Crea una nota «compras» con pan."),
                      "crea una nota compras con pan")
    assert result["kind"] == "action" and result["operation"] == "note.create"


# ------------------------------------------------------------------ a clock said in the future is still a clock read
# The reserve replay of a1739b28 closed a future clock question («¿en cuántas horas será…?») as a hypothetical state
# (``grammar.past_or_hypothetical_message``: «será», «will») and refused it. The phrasings below are our own.

CLOCK_OPERATIONS = ("system.time", "web.search", "weather.current")
CLOCK_TOOLS = {operation: _tool(operation) for operation in CLOCK_OPERATIONS}


class _Turn:
    """The decider talks; every other model call answers as the guards would with nothing to add."""

    _native_tool_policy_enabled = False

    def decide_in_context(self, text: str, *_args: object, **_kwargs: object) -> decider.ContextDecision:
        return decider.ContextDecision(request=text, decision="talk", operations=(), question="")

    @staticmethod
    def chat(*_args: object, **_kwargs: object) -> tuple[str, list]:
        return "Vale.", []

    @staticmethod
    def prepare_chat(*_args: object, **_kwargs: object) -> None:
        return None

    @staticmethod
    def detect_response_language(text: str) -> str:
        return "en" if all(ord(ch) < 128 for ch in text) else "es"

    @staticmethod
    def consume_deferred_response_language(_text: str) -> tuple[bool, None]:
        return True, None

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
        return "complete", "one"


def _clock_turn(text: str) -> dict[str, Any]:
    return sidecar._prepare_turn_result(
        {"id": "m114", "text": text, "history": [{"role": "user", "content": text}]},
        llm=_Turn(),
        planner_catalog=PlannerCatalog(list(CLOCK_TOOLS.values())),
        encoder=lambda _texts: (),
        tool_by_name=CLOCK_TOOLS,
    )


def test_the_hours_until_a_time_in_another_place_are_that_places_clock() -> None:
    elsewhere = clock_elsewhere(effect_intent._fold("¿en cuántas horas será mediodía en Tokio?"))
    assert elsewhere is not None and elsewhere.place == "tokio" and elsewhere.difference
    elsewhere = clock_elsewhere(effect_intent._fold("what time will it be in Paris"))
    assert elsewhere is not None and elsewhere.place == "paris"
    assert clock_elsewhere(effect_intent._fold("what time will the match start in Paris")) is None
    assert clock_elsewhere(effect_intent._fold("en cuántas horas llego a Madrid")) is None


def test_a_clock_asked_in_the_future_is_read_never_refused() -> None:
    for text in ("¿en cuántas horas será mediodía en Tokio?", "what time will it be in Paris",
                 "si pasan veinte minutos, ¿qué hora será?"):
        result = _clock_turn(text)
        assert result["kind"] == "action" and result["operation"] == "system.time", (text, result)
    # A future state that is no clock is still not read now.
    assert _clock_turn("¿cuánta memoria usará el navegador mañana?")["kind"] == "conversation"
