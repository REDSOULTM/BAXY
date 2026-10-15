"""The offer of a send after a verified draft: the turn that waits for it, the offer in the final, and the yes the
readers could not decide alone.
"""

from __future__ import annotations

import re
from typing import Any, Callable

from .semantic import dialogue as dialogue_slot
from .semantic import messaging as semantic_messaging
from .effect_intent import ApplicationCatalogIndex, resolve_explicit_effects
from .planner import PlannerCatalog
from .turn_history import _decisive_request_language, _prior_user_texts, _read_reply_language


def _expect_decided_turn(
    dialogue_state: dialogue_slot.DialogueState,
    turn_result: dict[str, Any],
    message: dict[str, Any],
    planner_catalog: PlannerCatalog | None = None,
    application_names: tuple[str, ...] | ApplicationCatalogIndex = (),
) -> None:
    """The request this turn decided is the last one now; its operations (the effects, or those a question is about)
    wait for their verified results (message.compose). Revisión 3 de la ronda 22: a conversation turn's reply is
    published by the shell as it is, never through message.compose, so it is kept here as the last final of this
    request (``DialogueState.said``). Estabilización B2: a draft decided with ``planner_catalog`` may offer its send
    (``_offered_send``)."""

    dialogue_state.expect(
        turn_result.get("objective") or message.get("text", ""),
        turn_result.get("effectOperations") or turn_result.get("intentOperations"),
    )
    if (
        turn_result.get("kind") == "conversation"
        and not turn_result.get("effectOperations")
        and not turn_result.get("intentOperations")
    ):
        dialogue_state.said(turn_result.get("reply"))
    elif turn_result.get("kind") == "clarify" and str(turn_result.get("question") or "").strip():
        # Ronda 24 (r23 t2-c03 #3): a question asked instead of acting is the last answer the person saw; a reproach
        # after it is about that question, never about the act before it (``correctedFinal``).
        dialogue_state.said(turn_result.get("question"))
    if planner_catalog is not None:
        dialogue_state.offer_send(_offered_send(turn_result, message, planner_catalog, application_names))


def _with_send_offer(
    text: str, dialogue_state: dialogue_slot.DialogueState, readers_send: Callable[[str], bool],
) -> str:
    """Estabilización B2: the final of a verified draft that may offer its send ends with that offer, in the person's
    words; only a yes sends it (``DialogueState.accepted_send``). A final with no words offers nothing, and a send the
    readers would not decide alone on the yes (``_readers_send``) is not offered (revisión B2 H2), nor one after a
    final that already asks something (H3: the yes would not say to what)."""

    def sent_alone(request: str) -> bool:
        try:
            return readers_send(request)
        except Exception:  # noqa: BLE001 - a send that cannot be checked is not offered
            return False

    offer = (
        dialogue_state.send_offer_question(_decisive_request_language(text) == "en", sent_alone)
        if text.strip() and not re.search(r"[¿?]", text)
        else None
    )
    return f"{text.rstrip()} {offer}" if offer is not None else text


def _send_said_result(message: dict[str, Any], said: str) -> dict[str, Any]:
    """A yes about a send answered whole from data, with nothing run: ``not_sent`` (estabilización B2: the yes to the
    offer whose send the readers could not decide alone) or ``already_sent`` (encargo E: the yes after a send already
    done and told, ``DialogueState.yes_after_a_send``)."""

    english = _read_reply_language(str(message.get("text", "")), message.get("history") or []) == "en"
    return {
        "type": "turn.result",
        "id": message.get("id"),
        "kind": "conversation",
        "operation": None,
        "intentOperations": [],
        "effectOperations": [],
        "preserveObjective": False,
        "question": "",
        "reply": semantic_messaging.send_said(said, english),
        "responseLanguage": "en" if english else "es",
    }


def _offered_send(
    turn_result: dict[str, Any],
    message: dict[str, Any],
    planner_catalog: PlannerCatalog,
    application_names: tuple[str, ...] | ApplicationCatalogIndex = (),
) -> tuple[str, str, str | None] | None:
    """Estabilización B2: the send a draft this turn decided may offer once it is verified
    (``semantic.messaging.offered_send``); None for any other turn."""

    if turn_result.get("kind") != "action" or turn_result.get("effectOperations") != ["message.draft"]:
        return None
    text = str(message.get("text", ""))
    available = tuple(tool.name for tool in planner_catalog.tools)
    if "message.send" not in available:
        return None
    return semantic_messaging.offered_send(
        text, _prior_user_texts(message.get("history") or [], text),
        lambda said: getattr(resolve_explicit_effects(said, available, application_names), "operations", ()),
    )
