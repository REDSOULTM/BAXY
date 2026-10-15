"""The shapes of decisions the readers close alone: a conversation kind, a limit, social talk, a recovered action
or the one question about an operation.
"""

from __future__ import annotations

import re
from typing import Any

from . import effect_intent
from .semantic import dialogue as dialogue_slot
from .semantic import reading as semantic_reading
from .effect_intent import ApplicationCatalogIndex, EffectIntent, GameCatalogIndex, known_unsupported_effect_request
from .planner import PlannerCatalog
from .semantic.request import INTENT_CAPABILITY, INTENT_IDENTITY, INTENT_REFUSE, read_request
from .semantic.dialogue import _previous_user_request
from .semantic.conversation import catalog_unavailable, nonunderstanding, social_act, stable_no_effect
from .semantic.web import not_a_public_lookup
from .turn_history import _explicit_response_language


def _operation_question_decision(question: str, response_language: object) -> dict[str, object]:
    """The one question ``_withheld_operation_verdict`` asks: nothing is dispatched by it."""

    return {
        "mode": "clarify",
        "operation": None,
        "question": question,
        "conversation_kind": "",
        "effect_count": "zero",
        "effect_operations": [],
        "effect_verification": "not_applicable",
        "response_language": response_language,
    }


def _recovered_action_decision(operation: str, response_language: object) -> dict[str, object]:
    """One operation a later stage recovered for the turn: a public search of the person's own
    words, or a withheld operation ``_acts_without_asking`` lets act. Its arguments are
    grounded like any recovered proposal."""

    return {
        "mode": "action",
        "operation": operation,
        "question": "",
        "conversation_kind": "",
        "effect_count": "one",
        "effect_operations": [operation],
        "effect_verification": "recovered",
        "response_language": response_language,
    }


# Presentation shapes whose content BAXY writes itself (llm._conversation_presentation_shape).
_WRITTEN_CONTENT_SHAPES = frozenset({"free_content", "content_draft", "roleplay_draft"})


# A reply that says BAXY does not know or cannot tell (folded text).
_ADMITS_NOT_KNOWING = re.compile(
    r"\bno\s+(?:lo\s+|la\s+)?(?:conozco|se|tengo\s+(?:informacion|datos|acceso|idea))\b|"
    r"\bdesconozco\b|\bno\s+estoy\s+(?:segur[oa]|familiarizad[oa])\b|"
    r"\bi\s+(?:don'?t|do\s+not)\s+(?:know|have\s+(?:information|access|any\s+information|data))\b|"
    r"\bi'?m\s+not\s+(?:sure|familiar)\b|\bi\s+am\s+not\s+(?:sure|familiar)\b|\bi\s+have\s+no\s+information\b|"
    # M104 (D52): the talk told to give no figure from memory says it has not checked it (the M95 retry asks it to);
    # that figure is looked up like anything else BAXY does not know.
    r"\bno\s+(?:lo\s+|la\s+|los\s+|las\s+)?(?:tengo|he)\s+(?:comprobad|verificad|confirmad|consultad)[oa]s?\b|"
    r"\bno\s+(?:esta|estan)\s+(?:comprobad|verificad)[oa]s?\b|"
    r"\bi\s+(?:have\s+not|haven'?t)\s+(?:checked|verified|confirmed|looked\s+(?:it\s+)?up)\b"
)


def _public_lookup_applies(
    objective: str,
    routing_objective: str,
    llm: object,
    available_operations: tuple[str, ...],
    planner_catalog: PlannerCatalog,
) -> bool:
    """The request is public information to look up on the web (the guard's reading)."""

    reads = getattr(llm, "public_lookup_requested", None)
    return (
        "web.search" in available_operations
        and planner_catalog.get("web.search") is not None
        and not not_a_public_lookup(objective)
        # Uso real 2026-09-23 «the creator of your ai, what is their name»: a
        # question about BAXY itself is answered as BAXY, never searched.
        and not read_request(objective).intents
        & {INTENT_IDENTITY, INTENT_CAPABILITY, INTENT_REFUSE}
        # «prepárame una taza de café»: a known limit is an order, not information.
        and not known_unsupported_effect_request(objective, available_operations)
        # Verification 2026-09-25 (cien-102 090 «rent a studio on Haumea» → a page about studios in Doha): what no
        # operation of this PC reaches is a boundary, never a lookup.
        and not effect_intent.out_of_world_request(objective)
        and callable(reads)
        and bool(reads(routing_objective))
    )


def _conversation_reply_arguments(
    history: list[Any],
    *,
    conversation_kind: str,
    response_language: str | None,
    scoped: bool,
    intent_operations: list[str],
    available_operations: tuple[str, ...],
) -> dict[str, Any]:
    """The arguments of a conversation reply, the same for its preparation and its use."""

    return {
        # A closed social act is a complete new presentation. Replaying
        # an earlier saved-memory result made a new introduction claim
        # another save. Scope this generation; retain the actual dialogue
        # and all context-dependent or model-classified conversations.
        "history": [] if scoped else history,
        "tools": None,
        "temperature": 0.0,
        "conversation_kind": conversation_kind,
        "authenticated_operations": tuple(intent_operations),
        # IDENTITY1325: «cómo funciona esto» names what the served
        # catalog does on this PC; the families come from it.
        "served_operations": available_operations,
        # Language is independently constrained from the current message.
        # The routing field cannot force the wrong response language.
        "response_language": response_language,
    }


def _prepare_conversation_reply(llm: Any, objective: str, arguments: dict[str, Any]) -> None:
    """Let the reply decode beside the checks that may still withdraw it (``LlmRuntime.prepare_chat``)."""

    prepare = getattr(llm, "prepare_chat", None)
    if callable(prepare):
        prepare(objective, **arguments)


def _explicit_turn_decision(
    intent: EffectIntent,
    objective: str,
) -> dict[str, object]:
    operations = list(intent.operations)
    return {
        "mode": intent.kind,
        "operation": operations[0] if len(operations) == 1 else None,
        "question": "",
        "conversation_kind": "",
        "effect_count": "one" if len(operations) == 1 else "multiple",
        "effect_operations": operations,
        "effect_verification": ("recovered" if len(operations) == 1 else "multiple"),
        "response_language": _explicit_response_language(objective),
    }


def _conversation_turn_decision(kind: str, language: str) -> dict[str, object]:
    """A turn a reader closed as conversation: its kind and the language to answer in; no operation."""

    return {
        "mode": "conversation",
        "operation": None,
        "question": "",
        "conversation_kind": kind,
        "effect_count": "zero",
        "effect_operations": [],
        "effect_verification": "not_applicable",
        "response_language": language,
    }


def _explicit_unsupported_turn_decision(objective: str) -> dict[str, object]:
    """Close a high-confidence out-of-scope language turn without effects."""

    return _conversation_turn_decision("unsupported", _explicit_response_language(objective))


def _explicit_social_turn_decision(
    objective: str, history: object = None, *, pending_clarification: bool | None = None,
) -> dict[str, object] | None:
    read = social_act(objective, history, pending_clarification=pending_clarification)
    return _conversation_turn_decision(*read) if read is not None else None


def _explicit_nonunderstanding_turn_decision(
    objective: str, history: object = None, *, pending_clarification: bool | None = None,
) -> dict[str, object] | None:
    language = nonunderstanding(objective, history, pending_clarification=pending_clarification)
    return _conversation_turn_decision("followup", language) if language is not None else None


def _explicit_stable_no_effect_turn_decision(
    objective: str, history: object = None, *, pending_clarification: bool | None = None,
) -> dict[str, object] | None:
    read = stable_no_effect(objective, history, pending_clarification=pending_clarification)
    return _conversation_turn_decision(*read) if read is not None else None


def _conversation_reader_keeps_followup(
    objective: str,
    *,
    non_target_language: bool,
    catalog_fact: bool,
    recalled: bool,
    explicit_non_action: bool,
    social_act: bool,
    reaction: bool,
) -> bool:
    """M112: whether a conversation reader's closure of a follow-up stands without the contextual decider.

    The readers read the message alone. A reaction («uf, está muy fuerte», «jaja no lo entendí») is about what just
    happened, and a message whose form leans on the turn before («no esa, la otra», «ahí tiene que estar el PDF…
    ¿me lo resumes?», ``dialogue.leans_on_context``) names its object there: both are the contextual decider's, which
    sees the conversation (DEV-F v4d w28-t5, w60-t2, w19-t2; the decider alone was right on every follow-up these
    readers lost). What holds whatever was said before keeps its reader: a language BAXY does not answer in, a limit
    of the catalog (a known unsupported contract, an application or game that is not installed), the words recalled
    or drawn on request, an explicit «don't do anything» or prohibition, a social act, and talk or a question that
    stands on its own (M83: «What is photosynthesis?» names what it asks about).
    """

    if (
        non_target_language
        or catalog_fact
        or recalled
        or explicit_non_action
        or social_act
        or effect_intent.explicit_negative_constraint(objective)
        or dialogue_slot.is_social(objective)
    ):
        return True
    return not (reaction or dialogue_slot.leans_on_context(objective))


def _catalog_unavailable_turn_decision(
    objective: str,
    explicit_intent: EffectIntent | None,
    application_names: tuple[str, ...] | ApplicationCatalogIndex,
    game_catalog: GameCatalogIndex,
) -> dict[str, object] | None:
    if catalog_unavailable(objective, explicit_intent, application_names, game_catalog):
        return _explicit_unsupported_turn_decision(objective)
    return None


def _talk_act_turn_decision(
    objective: str,
    explicit_intent: EffectIntent | None,
    asked: object | None,
) -> dict[str, object] | None:
    """Talk that asks nothing is answered as talk (Fase 3.5, guard class).

    «Me gusta crear cosas, como tú» got «¿Qué tipo de cosas te gustaría crear?»;
    «odio estos fallos» got the recovery error; «tus detectores no funcionan…»
    got a question in planner vocabulary. The form and its limits are read by
    ``semantic.reading.plain_talk``. Feedback keeps the dialogue history; it is
    about it.
    """

    if semantic_reading.plain_talk(objective, effects=explicit_intent, clarification=asked) is None:
        return None
    return {
        "mode": "conversation",
        "operation": None,
        "question": "",
        "conversation_kind": "social",
        "effect_count": "zero",
        "effect_operations": [],
        "effect_verification": "not_applicable",
        "response_language": _explicit_response_language(objective),
    }


def _completes_previous_request(
    objective: str,
    history: object,
    available_operations: tuple[str, ...],
    application_names: tuple[str, ...] | ApplicationCatalogIndex = (),
    game_catalog: GameCatalogIndex = GameCatalogIndex(),
) -> bool:
    """AUDIO1789: the text answers the previous incomplete request (an amount, a
    level, the music asked for) so the readers resolve it as that request."""

    if not isinstance(history, list):
        return False
    previous = _previous_user_request(history, objective)
    if not previous:
        return False
    try:
        return effect_intent.resolve_explicit_effects(
            objective,
            available_operations,
            application_names,
            game_catalog,
            previous_user_text=previous,
        ) is not None and effect_intent.resolve_explicit_effects(
            objective, available_operations, application_names, game_catalog,
        ) is None
    except (ValueError, TypeError):
        return False
