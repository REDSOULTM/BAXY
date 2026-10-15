"""The turn audit: opt-in diagnostics of each turn's stages, the computer-use witness beside a final, and the
failure kind of a turn attempt. Writing a record never changes a turn.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from .compose_situation import _merged_observed
from .llm_chat import ConversationReplyContractError


_turn_audit_lock = threading.Lock()
TURN_AUDIT_ENV = "BAXY_MIND_TURN_AUDIT_PATH"
TURN_AUDIT_MAX_BYTES = 128 * 1024


def _turn_audit_stage(name: str, decision: dict[str, Any]) -> dict[str, Any]:
    """Project one internal policy stage without changing its decision."""

    return {
        "name": name,
        "mode": decision.get("mode"),
        "operation": decision.get("operation"),
        "conversation_kind": decision.get("conversation_kind"),
        "effect_operations": list(decision.get("effect_operations") or []),
        "effect_verification": decision.get("effect_verification"),
    }


def _computer_use_witness_audit(request_id: object, situation: dict) -> dict[str, Any] | None:
    """Revisión 1 de la ronda 24b (B4): what the term that closed each sub-goal of a computer-use mission read (the
    App's measured «witness»: atom, where, what it showed, the journal read), for the turn audit beside the final the
    turn tells. None when the turn tells no mission or no term closed one."""

    from .compose_situation import _computer_use_mission

    mission = _computer_use_mission(situation)
    if mission is None:
        return None
    observed = _merged_observed(mission)
    subgoals = [
        {"satisfied_by": item.get("satisfiedBy"), "witness": item.get("witness")}
        for item in observed.get("subgoals") or () if isinstance(item, dict)
    ]
    if not observed.get("satisfiedBy") and not any(item["satisfied_by"] for item in subgoals):
        return None
    record: dict[str, Any] = {
        "schema": "baxy.mind-turn-audit.v1",
        "request_id": request_id,
        "phase": "computer_use_final",
        "reached": observed.get("reached") is True,
        "satisfied_by": observed.get("satisfiedBy"),
        "witness": observed.get("witness"),
    }
    if subgoals:
        record["subgoals"] = subgoals
    return record


def _append_turn_audit(record: dict[str, Any]) -> None:
    """Append bounded opt-in diagnostics; failures never affect a turn. The readers' warm-up is no turn: no record."""

    raw_path = os.environ.get(TURN_AUDIT_ENV, "").strip()
    if not raw_path or threading.current_thread().name == _READERS_WARMUP_THREAD:
        return
    try:
        candidates = (record,)
        if "app_open_identity" in record:
            candidates += (
                {key: value for key, value in record.items() if key != "app_open_identity"},
            )
        for candidate in candidates:
            try:
                payload = (
                    json.dumps(
                        candidate, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                    ) + "\n"
                ).encode("utf-8")
            except (TypeError, ValueError, RecursionError):
                continue
            if len(payload) <= TURN_AUDIT_MAX_BYTES:
                break
        else:
            return
        path = Path(raw_path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        with _turn_audit_lock, path.open("ab") as handle:
            handle.write(payload)
            handle.flush()
    except (OSError, TypeError, ValueError):
        # Diagnostics are deliberately outside the semantic and authority path.
        return


# A turn that decided a limit («eso no lo hago») and failed only in the wording
# of that limit: the unsupported presentation contract rejected every draft.
LIMIT_WORDING_FAILURE = "limit_wording"
# M72 (conv-v3h guion t26/t28, v3j real log log:165): a turn that decided conversation and failed only in the wording
# of its reply was understood; there is nothing to clarify.
CONVERSATION_WORDING_FAILURE = "conversation_wording"


def _turn_failure_kind(error: BaseException) -> str:
    """Name the failure class of one turn attempt that did not raise a contract error."""

    reason = str(getattr(error, "audit_reason", ""))
    if isinstance(error, ConversationReplyContractError) and (
        (reason.startswith("unsupported_") and reason != "unsupported_language")
        # M97 (DEV-D v3x D-s064 «¿Sería posible suprimir mi orden de recogida en Lyft…»): the turn decided a limit and
        # its drafts failed another contract (shaped_presentation, echo); it is still the limit's wording that failed.
        or getattr(error, "conversation_kind", None) == "unsupported"
        # M139 (DEV-G v4n G-s120): the talk drafts said, as an inability in the present, what BAXY does not do
        # (failure_wording.talk_reply_tells_a_limit); the turn did not understand it as talk, it met a limit.
        or reason == "told_limit"
    ):
        return LIMIT_WORDING_FAILURE
    if isinstance(error, ConversationReplyContractError):
        return CONVERSATION_WORDING_FAILURE
    return "runtime"


_READERS_WARMUP_THREAD = "baxy-readers-warmup"
