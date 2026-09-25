"""Entrada del sidecar baxy-mind: loop JSONL sobre stdin/stdout.

Solicitudes: turn.decide, plan, narrate, shutdown (voice.* llega con la
Fase de voz). Fail-closed: cualquier violación de protocolo emite error y, si es
irrecuperable, termina con exit != 0 para que el shell degrade a su camino
determinista.
"""

from __future__ import annotations

import json
import os
import queue
import re
import stat
import sys
import threading
import time
import unicodedata
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from functools import partial
from pathlib import Path
from typing import Any, Callable

# PyTorch otherwise sizes its CPU pools for the whole machine. On a 16 GiB
# notebook that creates dozens of workers and can turn startup into minutes of
# paging. Keep explicit operator overrides, but use a small production default.
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from . import protocol
from . import effect_intent
from .semantic import dialogue as dialogue_slot
from .semantic import levels as semantic_levels
from .semantic import reading as semantic_reading
from .semantic import surface as semantic_surface
from .semantic.patterns import output_level_request
from .semantic.web import asks_for_information, near_the_person, news_lookup_query
from .semantic.windows import start_menu_request
from .corrector import catalog_correction_terms
from .first_signal import (
    PATH_MODEL,
    PATH_RECOGNIZER,
    PendingTurnSignal,
    should_emit_early,
    turn_signal_payload,
)
from .effect_intent import (
    ApplicationCatalogIndex,
    CompoundEffectContract,
    EffectIntent,
    GameCatalogIndex,
    build_application_catalog_index,
    build_game_catalog_index,
    compound_retrieval_clauses,
    compound_retrieval_operation_hints,
    confident_non_target_language,
    conversation_only_content_request,
    effect_request_is_authoritative,
    known_unsupported_effect_request,
    operation_domain_is_grounded,
    resolve_application_catalog_app_id,
    resolve_explicit_clarification_intent,
    resolve_explicit_effects,
    resolve_game_catalog_app_id,
    unresolved_compound_contract,
    reassurance_statement,
    unsupported_effect_demonstration_request,
    unsupported_live_machine_query,
    visual_content_request,
)
from .llm import (
    ConversationReplyContractError,
    LlmRuntime,
    _literal_recall_reference,
    _merged_observed,
    _native_selection_description,
    _situation_from_facts,
    served_capability_families,
    visible_reply_is_only_questions,
)
from .llm_transport import ChatCompletionCancellation
from .planner import (
    MAX_SHORTLIST_OPERATIONS,
    PlannerCatalog,
    PlannerContractError,
    PlannerTool,
    attach_arguments,
    conditional_predecessors,
    guarding_predecessors,
    is_required_predecessor,
    normalize_grounded_arguments,
    required_predecessors,
    validate_argument_grounding,
    validate_json_schema_instance,
    validate_skeleton,
)
from .semantic.request import (
    fold as read_fold,
    INTENT_CAPABILITY,
    INTENT_CONTINUE_CONSTRAINT,
    INTENT_IDENTITY,
    INTENT_REFUSE,
    is_elliptical_followup,
    read_request,
    response_language as read_language,
)
from .process_lifecycle import (
    ReapResource,
    ReapStatus,
    report_incomplete_reap,
)
from .skill_registry import SkillRegistry
from .router import (
    DEFAULT_ENCODER_REQUEST_TIMEOUT_SECONDS,
    ProcessIntentRouter,
    RequestBudgetEncoder,
)
from .turn_evidence import TurnEvidenceService
from .voice import VoiceEngine
from .semantic.reading import (  # noqa: F401 - moved to baxy_mind.semantic.reading; callers migrate
    _CLAUSE_EDGE_PUNCTUATION,
    _original_clause,
    _CLAUSE_COORDINATION,
    _LEADING_VOCATIVE,
    _coordinated_clauses,
    _clause_starts_with_order,
    _LEAD_NOT_TALK,
    _order_with_talk,
    _FRONTED_PLACE,
    _desired_media_request,
    _fronted_place_request,
    _TALK_PC_DOMAIN,
    _TALK_LOOKUP,
    _TALK_DESIRED_REQUEST,
    _TALK_EXTRA_ORDER,
    _leading_proved_clauses,
    _compound_partial_offer,
    _OVERHEARD_ACTION_WORDS,
)
from .semantic.guards import (  # noqa: F401 - moved to baxy_mind.semantic.guards; callers migrate
    _BARE_PATH,
    bare_path_file_name,
    _CUT_TAIL_WORDS,
    cut_request_tail,
    _echoed_words,
    _unresolved_input_kind,
    _conversation_in_progress,
    _overheard_speech,
)
from .semantic.dialogue import (
    _history_has_pending_clarification,
    _previous_user_request,
)
from .semantic.conversation import (
    _assistant_capability_aspiration,
    _closed_unsupported_request,
    _current_public_role_question,
    _deictic_open_request,
    _general_factoid_prompt,
    _personal_checkin_statement,
    _standalone_deictic_request,
    _conversation_presentation_shape,
    _reads_as_an_observation,
    catalog_unavailable,
    first_person_observation,
    names_a_question_word,
    nonunderstanding,
    random_draw_request,
    social_act,
    stable_no_effect,
)
from .semantic.arguments import (
    _canonical_due_utc,
    _explicit_arguments_from_evidence,
    _fully_enumerated_note_create_arguments,
    _presentation_arguments,
    _select_referenced_predecessor,
    closes_the_active_window,
    literal_ocr_language,
    literal_vision_prompt,
    names_spotify,
    reminder_title_without_que,
)
from .semantic.messaging import chat_message_dispatch, message_body
from .semantic.arguments import (  # noqa: F401 - moved to baxy_mind.semantic.arguments; callers migrate
    _SYSTEM_STATUS_SCOPES,
    _explicit_calendar_event_arguments,
    _explicit_calendar_range_arguments,
    _explicit_media_control_arguments,
    _explicit_notification_schedule_arguments,
    _explicit_system_status_scope,
)
from .semantic.web import (
    not_a_public_lookup,
)


_write_lock = threading.Lock()
_turn_audit_lock = threading.Lock()

# The desktop transport cancels turn.decide after 22 seconds. Keep a fixed
# margin for JSONL scheduling while guaranteeing a separate, candidate-free
# recovery window after the bounded normal attempts.
TURN_DECIDE_NORMAL_BUDGET_SECONDS = 17.0
# Both side-effect-free attempts share the normal deadline. A per-attempt cap
# below that deadline stranded three seconds that cannot complete one CPU
# decode; an early contract failure still leaves its unused time to the retry.
TURN_DECIDE_ATTEMPT_BUDGET_SECONDS = TURN_DECIDE_NORMAL_BUDGET_SECONDS
TURN_DECIDE_RECOVERY_BUDGET_SECONDS = 2.5
TURN_DECIDE_TRANSPORT_SLA_SECONDS = 22.0
DEICTIC_CLARIFICATION_CPU_BUDGET_SECONDS = 15.0
TURN_AUDIT_ENV = "BAXY_MIND_TURN_AUDIT_PATH"
# Failures whose final is a question to the person: a replan of the same
# suffix would only repeat the failed step (REOPEN1957 H0170/H0376).
_NO_REPLAN_ERROR_CODES = frozenset({"wifi_place_unknown"})
TURN_AUDIT_MAX_BYTES = 128 * 1024
# The shell owns one 120-second startup cancellation window. Keep the model
# warmup and the catalog request inside it, with explicit time left for JSONL
# delivery and authenticated catalog validation.
MIND_STARTUP_TRANSPORT_SLA_SECONDS = 120.0
CATALOG_LLM_WARMUP_SECONDS = 90.0
CATALOG_REQUEST_BUDGET_SECONDS = 105.0
ARGUMENT_REQUEST_BUDGET_SECONDS = 19.25
# GPU compositions keep their 5/10 s desktop budgets. The certified CPU
# profile needs the same visible-response contract. Isolated generations reach
# 14.51 s, accumulated history exceeds 20 s, and a verified three-step mission
# exceeds 45 s. Dense verified output can contain hundreds of literal tokens,
# so CPU realizes dense verified output through a short model-authored scaffold
# under one 120 s budget, then substitutes exact dynamic facts into its markers.
# The accelerated path retains its smaller explicit 5/10 s budget.
MESSAGE_COMPOSITION_MAX_BUDGET_SECONDS = 120.0
BACKGROUND_ENCODER_TIMEOUT_SECONDS = DEFAULT_ENCODER_REQUEST_TIMEOUT_SECONDS
BACKGROUND_WORKER_JOIN_TIMEOUT_SECONDS = 0.15
BACKGROUND_WORKER_ABORT_JOIN_SECONDS = 0.25
# Protocol lines may be 1 MiB. Bound both read-ahead stages so a stalled
# model request cannot turn a cooperative desktop transport into a memory sink.
CONTROL_EVENT_QUEUE_LIMIT = 4
SERIAL_PENDING_REQUEST_LIMIT = 16
_BLOCKING_REQUEST_TYPES = frozenset(
    {
        "arguments",
        "catalog.configure",
        "message.compose",
        "narrate",
        "plan",
        "plan.ground",
        "turn.decide",
        "voice.speak",
        "voice.start",
        "voice.status",
        "voice.stop",
    }
)
_VOICE_MUTATION_REQUEST_TYPES = frozenset(
    {
        "voice.speak",
        "voice.start",
        "voice.stop",
    }
)


def _message_composition_budget(value: Any) -> float:
    try:
        return max(
            1.0,
            min(MESSAGE_COMPOSITION_MAX_BUDGET_SECONDS, float(value)),
        )
    except (TypeError, ValueError):
        return 3.25


_IDENTITY_CONSUMERS = frozenset(
    {
        "app.close",
        "bluetooth.device.pair",
        "filesystem.read.text",
        "game.install.commit",
        "game.purchase.commit",
        "message.send",
        "notification.dismiss",
        "ocr.read",
        "package.install.commit",
        "peripheral.print",
        "peripheral.scan",
        "reminder.delete",
        "task.delete",
        "vision.describe",
        "window.focus",
        "window.maximize",
        "window.minimize",
        "window.move",
        "window.resize",
        "window.restore",
        "window.snap",
        "wifi.connect",
    }
)


def _write(message: dict) -> None:
    with _write_lock:
        protocol.write_message(message)


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


def _append_turn_audit(record: dict[str, Any]) -> None:
    """Append bounded opt-in diagnostics; failures never affect a turn."""

    raw_path = os.environ.get(TURN_AUDIT_ENV, "").strip()
    if not raw_path:
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


def _turn_failure_kind(error: BaseException) -> str:
    """Name the failure class of one turn attempt that did not raise a contract error."""

    reason = str(getattr(error, "audit_reason", ""))
    if (
        isinstance(error, ConversationReplyContractError)
        and reason.startswith("unsupported_")
        and reason != "unsupported_language"
    ):
        return LIMIT_WORDING_FAILURE
    return "runtime"


def _audit_turn_attempt_failure(
    message: dict[str, Any],
    error: BaseException,
    failure_kind: str,
) -> None:
    """Record a stable failure class without exposing exception text."""

    failure_reason = str(getattr(error, "audit_reason", ""))[:64]
    if not failure_reason:
        traceback = error.__traceback__
        while traceback is not None:
            frame = traceback.tb_frame
            code = frame.f_code
            module = str(frame.f_globals.get("__name__") or "")
            if module.startswith("baxy_mind.") or code.co_filename == __file__:
                failure_reason = f"{code.co_name[:48]}:{traceback.tb_lineno}"[:64]
            traceback = traceback.tb_next
    record = {
        "schema": "baxy.mind-turn-audit.v1",
        "request_id": message.get("id"),
        "phase": "attempt_failure",
        "failure_kind": failure_kind,
        "failure_stage": _stable_turn_failure_stage(error),
        "error_type": type(error).__name__,
        "candidate_operations": [],
        "raw_decision": None,
        "stages": [],
    }
    if failure_reason:
        record["failure_reason"] = failure_reason
    _append_turn_audit(record)


_TURN_FAILURE_STAGE_BY_FRAME = {
    "decide_turn": "model_decision",
    "validate_turn_decision": "decision_validation",
    "apply_explicit_effect_contract": "explicit_contract",
    "apply_information_question_effect_veto": "information_question",
    "apply_operation_domain_grounding_veto": "domain_grounding",
    "apply_compound_effect_conservation_veto": "compound_conservation",
    "apply_turn_action_relevance_veto": "action_relevance",
    "apply_turn_action_grounding_gate": "action_grounding",
    "extract_direct_arguments": "action_grounding",
    "formulate_missing_argument_question": "action_grounding",
    "apply_conversation_effect_presentation": "conversation_effect_presentation",
    "apply_non_effect_conversation_classification": "conversation_classification",
    "clarify_after_turn_failure": "intent_clarification",
    "detect_response_language": "response_language",
    "consume_deferred_response_language": "response_language",
    "retire_deferred_response_language": "response_language_retirement",
    "chat": "conversation_reply",
}


def _stable_turn_failure_stage(error: BaseException) -> str:
    """Map a traceback to a bounded stage without retaining private details."""

    declared_stage = str(getattr(error, "audit_stage", ""))
    if declared_stage in set(_TURN_FAILURE_STAGE_BY_FRAME.values()):
        return declared_stage
    frames: list[tuple[bool, str]] = []
    traceback = error.__traceback__
    while traceback is not None:
        module = str(traceback.tb_frame.f_globals.get("__name__") or "")
        code = traceback.tb_frame.f_code
        owned = module.startswith("baxy_mind.") or code.co_filename == __file__
        frames.append((owned, code.co_name))
        traceback = traceback.tb_next
    for owned, function in reversed(frames):
        if owned and (
            stage := _TURN_FAILURE_STAGE_BY_FRAME.get(function)
        ):
            return stage
    return "turn_preparation"


@dataclass(frozen=True)
class _ReadFailure:
    error: BaseException


@dataclass(frozen=True)
class _InboundMessage:
    message: dict[str, Any] | None


@dataclass(frozen=True)
class _DispatchFinished:
    result: int | None = None
    error: BaseException | None = None


class _AcknowledgedVoiceCancel(dict[str, Any]):
    """Internal replay marker that cannot be forged by a JSON object."""


class _LaneSubmission(str, Enum):
    """Closed outcomes for one bounded serial-lane admission."""

    ACCEPTED = "accepted"
    CLOSED = "closed"
    FULL = "full"


class _TerminalProtocolWriter:
    """Serialize replies and make a shutdown acknowledgement terminal."""

    def __init__(self, write_message: Callable[[dict], None]) -> None:
        self._write_message = write_message
        self._lock = threading.Lock()
        self._hello_written = threading.Event()
        self._terminal = False

    def write(self, message: dict) -> bool:
        with self._lock:
            if self._terminal:
                return False
            self._write_message(message)
            if message.get("type") == "hello":
                self._hello_written.set()
            if message.get("type") == "shutdown.ack":
                self._terminal = True
            return True

    def write_terminal(self, message: dict) -> bool:
        with self._lock:
            if self._terminal:
                return False
            self._write_message(message)
            self._terminal = True
            return True

    def wait_until_hello(self, timeout: float) -> bool:
        return self._hello_written.wait(timeout=max(0.0, timeout))


class _SerialRequestLane:
    """Keep model/catalog work serial while exposing its scheduling state."""

    def __init__(
        self,
        pending_limit: int | None = None,
    ) -> None:
        pending_limit = (
            SERIAL_PENDING_REQUEST_LIMIT if pending_limit is None else pending_limit
        )
        if pending_limit < 1:
            raise ValueError("pending_limit must be positive")
        self._condition = threading.Condition()
        self._pending: deque[dict[str, Any] | _ReadFailure] = deque()
        self._active: dict[str, Any] | None = None
        self._pending_limit = pending_limit
        self._normal_pending = 0
        self._blocking_work = 0
        self._voice_mutations = 0
        self._voice_mutation_sequence = 0
        self._replayed_voice_mutation_sequence = 0
        self._closed = False

    @staticmethod
    def _kind(message: dict[str, Any] | None) -> str:
        return str(message.get("type")) if message is not None else ""

    def submit(
        self,
        message: dict[str, Any] | _ReadFailure,
        *,
        reserved: bool = False,
    ) -> _LaneSubmission:
        with self._condition:
            if self._closed:
                return _LaneSubmission.CLOSED
            if (
                isinstance(message, dict)
                and not isinstance(message, _AcknowledgedVoiceCancel)
                and not reserved
                and self._normal_pending >= self._pending_limit
            ):
                return _LaneSubmission.FULL
            self._pending.append(message)
            if isinstance(message, dict) and not isinstance(
                message, _AcknowledgedVoiceCancel
            ):
                self._normal_pending += 1
                kind = self._kind(message)
                if kind in _BLOCKING_REQUEST_TYPES:
                    self._blocking_work += 1
                if kind in _VOICE_MUTATION_REQUEST_TYPES:
                    self._voice_mutations += 1
                    self._voice_mutation_sequence += 1
            self._condition.notify()
            return _LaneSubmission.ACCEPTED

    def voice_cancel_snapshot(self) -> tuple[bool, int | None]:
        """Capture urgency and the last prior voice mutation atomically."""

        with self._condition:
            replay_token = (
                self._voice_mutation_sequence if self._voice_mutations > 0 else None
            )
            return self._blocking_work > 0, replay_token

    def schedule_voice_cancel_replay(self, replay_token: int) -> bool:
        """Append one silent barrier for a pre-cancel mutation snapshot."""

        with self._condition:
            if self._closed or replay_token <= self._replayed_voice_mutation_sequence:
                return False
            self._pending.append(_AcknowledgedVoiceCancel({"type": "voice.cancel"}))
            self._replayed_voice_mutation_sequence = replay_token
            self._condition.notify()
            return True

    def close(self, *, drop_pending: bool) -> None:
        with self._condition:
            self._closed = True
            if drop_pending:
                self._pending.clear()
                self._normal_pending = 0
                active_kind = self._kind(self._active)
                self._blocking_work = int(active_kind in _BLOCKING_REQUEST_TYPES)
                self._voice_mutations = int(
                    active_kind in _VOICE_MUTATION_REQUEST_TYPES
                )
            self._condition.notify_all()

    def read_message(self) -> dict[str, Any] | None:
        with self._condition:
            while not self._pending and not self._closed:
                self._condition.wait()
            if not self._pending:
                return None
            item = self._pending.popleft()
            if isinstance(item, _ReadFailure):
                raise item.error
            if not isinstance(item, _AcknowledgedVoiceCancel):
                self._normal_pending -= 1
            self._active = item
            return item

    def finish(self, message: dict[str, Any]) -> None:
        with self._condition:
            if self._active is message:
                kind = self._kind(message)
                if kind in _BLOCKING_REQUEST_TYPES:
                    self._blocking_work -= 1
                if kind in _VOICE_MUTATION_REQUEST_TYPES:
                    self._voice_mutations -= 1
                self._active = None
            self._condition.notify_all()

    def has_blocking_work(self) -> bool:
        with self._condition:
            return self._blocking_work > 0


def _finish_request_scope(
    *,
    interactive_encoder: Any,
    llm: Any | None,
    encoder_scope_attempted: bool,
    llm_scope_attempted: bool,
    request_finished: Callable[[dict[str, Any]], None] | None,
    message: dict[str, Any],
) -> None:
    """Release every attempted request scope once, even after partial entry."""

    cleanup_errors: list[BaseException] = []

    def attempt(callback: Callable[[], Any]) -> None:
        try:
            callback()
        except BaseException as error:  # noqa: BLE001 - finish all scopes
            cleanup_errors.append(error)

    if encoder_scope_attempted:
        attempt(interactive_encoder.end_request)
    if llm_scope_attempted:
        attempt(llm.end_request)
    if request_finished is not None:
        attempt(lambda: request_finished(message))
    if cleanup_errors:
        raise cleanup_errors[0]


def _turn_evidence_query(text: str, history: object) -> str:
    """Retain a small conversational window for semantic evidence retrieval."""

    context: list[str] = []
    if isinstance(history, list):
        for turn in history[-4:]:
            if not isinstance(turn, dict):
                continue
            role = turn.get("role")
            content = turn.get("content")
            if role in {"user", "assistant"} and isinstance(content, str):
                compact = " ".join(content.split())
                if compact:
                    context.append(f"{role}: {compact[:1_024]}")
    current = " ".join(text.split())[:2_048]
    return "\n".join([*context, f"user: {current}"])[-4_096:]


_OPERATION_NAME = re.compile(r"^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*)+$")
_ARGUMENT_FIELD_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,127}$")
_KNOWN_RISKS = {
    "external_communication",
    "forbidden_destructive",
    "installation",
    "low_reversible",
    "monetary",
    "privacy_sensitive",
    "read_only",
    "recoverable_delete",
    "session_disruption",
    "work_loss",
}


class PlannerClarification(PlannerContractError):
    """Typed semantic abstention; only validated LLM text can enter this path."""

    def __init__(self, question: str) -> None:
        super().__init__("semantic_clarification")
        self.question = question


def unresolved_argument_fields(
    arguments: object,
    schema: object,
    trusted_source: str,
) -> tuple[str, ...]:
    """Locate unresolved required fields from the authenticated JSON Schema.

    This is called only after whole-object grounding failed. Each required
    field is rechecked independently against the same schema and trusted user
    text, so the clarification layer never guesses from an operation name.
    """

    if not isinstance(schema, dict) or schema.get("type") != "object":
        raise PlannerContractError("schema de argumentos no canónico")
    properties = schema.get("properties")
    required = schema.get("required")
    if (
        not isinstance(properties, dict)
        or not isinstance(required, list)
        or not 1 <= len(required) <= 64
        or len(set(required)) != len(required)
        or any(
            not isinstance(name, str)
            or _ARGUMENT_FIELD_NAME.fullmatch(name) is None
            or name not in properties
            for name in required
        )
    ):
        raise PlannerContractError(
            "el schema no identifica argumentos requeridos aclarables"
        )

    unresolved: list[str] = []
    for name in required:
        if not isinstance(arguments, dict) or name not in arguments:
            unresolved.append(name)
            continue
        field_schema = {
            "type": "object",
            "properties": {name: properties[name]},
            "required": [name],
            "additionalProperties": False,
        }
        if not validate_argument_grounding(
            {name: arguments[name]},
            field_schema,
            trusted_source,
        ):
            unresolved.append(name)
    if not unresolved:
        raise PlannerContractError(
            "el fallo de argumentos no corresponde a un dato requerido"
        )
    return tuple(unresolved)


def normalize_objective_arguments(
    arguments: object,
    schema: object,
    objective: str,
) -> tuple[dict | None, tuple[str, ...]]:
    """Ground extracted literals only against the authenticated user objective."""

    grounded = normalize_grounded_arguments(arguments, schema, objective)
    if grounded is not None:
        return grounded, ()
    return None, unresolved_argument_fields(arguments, schema, objective)


def prepare_direct_argument_result(
    llm: object,
    objective: str,
    tool: dict,
    arguments: object,
    fallback_question: str = "",
) -> tuple[dict | None, str]:
    """Return only grounded arguments or one schema-grounded clarification."""

    schema = tool["function"]["parameters"]
    grounded, fields = normalize_objective_arguments(
        arguments,
        schema,
        objective,
    )
    if grounded is not None:
        operation = str(tool["function"].get("canonical_name") or "")
        normalized = _normalize_grounded_operation_arguments(
            operation,
            grounded,
            objective,
        )
        if normalized is not None:
            return normalized, ""
        fields = ("dueUtc",) if "dueUtc" in schema.get("required", []) else fields
    if fallback_question:
        return None, fallback_question
    question = llm.formulate_missing_argument_question(
        objective,
        "",
        tool,
        fields,
    )
    return None, question


def trusted_plan_grounding_source(
    objective: str,
    observations: object,
) -> str:
    """Build provenance from user text and verified dependency observations.

    A plan step's ``purpose`` is model-authored guidance. It is deliberately
    absent from this interface so it can never launder an invented argument
    into trusted textual evidence.
    """

    return (
        objective
        + "\n"
        + json.dumps(
            observations,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )


_DETERMINISTIC_DEPENDENCY_FIELDS = {
    "app.close": ("windowId",),
    "window.focus": ("windowId",),
    "window.maximize": ("windowId",),
    "window.minimize": ("windowId",),
    "window.move": ("windowId",),
    "window.resize": ("windowId",),
    "window.restore": ("windowId",),
    "window.snap": ("windowId",),
    "bluetooth.device.pair": ("deviceId",),
    "peripheral.scan": ("deviceId",),
    "filesystem.read.text": ("resourceId",),
    "game.install.commit": ("confirmationId",),
    "package.install.commit": ("confirmationId",),
    "game.purchase.commit": ("confirmationId", "expectedPriceCents"),
    "message.send": ("recipientId",),
    "note.read": ("noteId",),
    "notification.dismiss": ("reminderId", "expectedVersion"),
    "ocr.read": ("captureId",),
    "office.document.read": ("documentId",),
    "peripheral.print": ("deviceId",),
    "reminder.delete": ("reminderId", "expectedVersion", "reviewLabel"),
    "task.delete": ("taskId", "expectedVersion", "reviewLabel"),
    "vision.describe": ("captureId",),
    "wifi.connect": ("profileId",),
}


def _collect_dependency_field_values(value: object, field: str) -> list[object]:
    values: list[object] = []
    if isinstance(value, dict):
        for name, child in value.items():
            if (
                name == field
                and child is not None
                and not isinstance(child, (dict, list))
            ):
                values.append(child)
            values.extend(_collect_dependency_field_values(child, field))
    elif isinstance(value, list):
        for child in value:
            values.extend(_collect_dependency_field_values(child, field))
    return values


def _window_is_sizable(window: dict) -> bool:
    """A window a person could see as one: at least 200x100 when sizes are reported."""

    width, height = window.get("width"), window.get("height")
    if not isinstance(width, (int, float)) or not isinstance(height, (int, float)):
        return True
    return width >= 200 and height >= 100


def _verified_dependency_identity_arguments(
    operation: str,
    objective: str,
    observations: object,
    tool: dict[str, object],
    application_names: tuple[str, ...] | ApplicationCatalogIndex = (),
    game_catalog: GameCatalogIndex | None = None,
) -> dict[str, object] | None:
    """Copy a complete unique identity from permitted verified producers.

    This is the sidecar equivalent of the App boundary's deterministic
    projector.  It removes stochastic model extraction only when the selected
    dependency already proves every argument required by the exact schema.
    """

    if not isinstance(observations, list):
        return None
    if operation == "filesystem.write.text":
        report = effect_intent.process_report_file_request(effect_intent._fold(objective))
        if report is not None:
            return _process_report_file_arguments(report, observations, tool)
    if operation == "file.open":
        # REOPEN1957 H0069: the file to open is the one the download just wrote.
        downloads = [
            observation["result"]
            for observation in observations
            if isinstance(observation, dict)
            and observation.get("operation") == "web.download"
            and observation.get("verified") is True
            and observation.get("status") == "completed"
            and isinstance(observation.get("result"), dict)
        ]
        if len(downloads) == 1 and isinstance(downloads[0].get("name"), str) and isinstance(downloads[0].get("folder"), str):
            candidate = {"folder": downloads[0]["folder"], "name": downloads[0]["name"]}
            function = tool.get("function")
            schema = function.get("parameters") if isinstance(function, dict) else None
            if isinstance(schema, dict) and validate_json_schema_instance(candidate, schema):
                return candidate
    if operation == "browser.navigate.named":
        # H0516 «Abre Opera GX, busca una receta de pizza, …»: la navegación
        # que sigue a una búsqueda va al primer resultado verificado, en el
        # navegador que la persona nombró. El modelo, rellenando a ciegas,
        # escribió «opera» donde la persona dijo «Opera GX», y en este PC sólo
        # está Opera GX: el navegador es del pedido y la URL de la búsqueda.
        browser = effect_intent._named_browser(effect_intent._fold(objective))
        named_site = effect_intent._named_browser_site_request(objective, application_names)
        if named_site is not None:
            # H0081 «quiero que abras opera gx y entras a pivigames»: «abras» is
            # not one of the leading verbs the named-browser reader knows, and
            # without the browser from the reader the model wrote «opera» again.
            browser = named_site[0]
        searches = [
            observation["result"]
            for observation in observations
            if isinstance(observation, dict)
            and observation.get("operation") == "web.search"
            and observation.get("verified") is True
            and observation.get("status") == "completed"
            and isinstance(observation.get("result"), dict)
        ]
        if browser is not None and len(searches) == 1:
            first = next(
                (
                    result.get("url")
                    for result in (searches[0].get("results") or [])
                    if isinstance(result, dict) and isinstance(result.get("url"), str)
                ),
                None,
            )
            if first is not None:
                candidate = {"browser": browser, "url": first}
                function = tool.get("function")
                schema = function.get("parameters") if isinstance(function, dict) else None
                if isinstance(schema, dict) and validate_json_schema_instance(candidate, schema):
                    return candidate
    if operation == "window.focus" and effect_intent.other_window_switch_request(objective):
        # REOPEN1993 H0263 «cambiá a la otra ventana»: the first visible,
        # non-minimized window that is not in the foreground, in the order
        # the inventory observed (front to back), is «la otra».
        for observation in observations:
            if not (
                isinstance(observation, dict)
                and observation.get("operation") == "window.resolve"
                and observation.get("verified") is True
                and observation.get("status") == "completed"
                and isinstance(observation.get("result"), dict)
            ):
                continue
            windows = observation["result"].get("windows")
            if not isinstance(windows, list):
                continue
            # CONTEXT1999: the inventory also lists untitled tool windows
            # (DisplayFusion widgets 33x29, an explorer 0x0 shell window,
            # the taskbar) ahead of the real ones; a person sees as «la
            # otra ventana» the first titled, sizable, non-minimized window
            # behind the one in the foreground.
            visible = [
                window for window in windows
                if isinstance(window, dict)
                and isinstance(window.get("windowId"), str)
                and str(window.get("title") or "").strip()
                and window.get("state") != "minimized"
                and _window_is_sizable(window)
            ]
            behind = visible
            for index, window in enumerate(visible):
                if window.get("foreground") is True:
                    behind = visible[index + 1:] + visible[:index]
                    break
            for window in behind:
                if window.get("foreground") is not True:
                    return {"windowId": window["windowId"]}
        return None
    fields = _DETERMINISTIC_DEPENDENCY_FIELDS.get(operation, ())
    producers = set(required_predecessors(operation)) | set(
        conditional_predecessors(operation, objective)
    )
    if not fields or not producers:
        return None
    results = [
        observation["result"]
        for observation in observations
        if isinstance(observation, dict)
        and observation.get("operation") in producers
        and observation.get("verified") is True
        and observation.get("status") == "completed"
        and isinstance(observation.get("result"), dict)
    ]
    if not results:
        return None
    arguments: dict[str, object] = {}
    for field in fields:
        unique = {
            json.dumps(value, ensure_ascii=False, sort_keys=True): value
            for result in results
            for value in _collect_dependency_field_values(result, field)
        }
        if len(unique) == 1:
            arguments[field] = next(iter(unique.values()))
    function = tool.get("function")
    schema = function.get("parameters") if isinstance(function, dict) else None
    if not isinstance(schema, dict):
        return None
    if not validate_json_schema_instance(arguments, schema):
        # ARRANGE1781 «poné chrome a la izquierda»: the identity alone did
        # not satisfy window.snap (side missing) and the model extraction
        # produced nothing in Spanish; the fields the person authored come
        # from the effect reader, never from the model.
        explicit = _explicit_arguments_from_evidence(
            operation,
            objective,
            application_names if isinstance(application_names, tuple) else (),
            game_catalog if game_catalog is not None else GameCatalogIndex(),
        )
        if not isinstance(explicit, dict):
            return None
        merged = {**explicit, **arguments}
        if not validate_json_schema_instance(merged, schema):
            return None
        return merged
    return arguments


def _process_report_file_arguments(
    report: dict[str, object],
    observations: list[object],
    tool: dict[str, object],
) -> dict[str, object] | None:
    """FILES1705: project the verified process listing into the file text.

    Every token of the text is evidence: the header repeats the request's
    own words and each line is the observed process name with its observed
    working-set bytes, so the grounding contract holds without a model.
    """

    listings = [
        observation["result"]
        for observation in observations
        if isinstance(observation, dict)
        and observation.get("operation") == "system.process.list"
        and observation.get("verified") is True
        and observation.get("status") == "completed"
        and isinstance(observation.get("result"), dict)
        and isinstance(observation["result"].get("processes"), list)
    ]
    if len(listings) != 1:
        return None
    lines: list[str] = []
    for entry in listings[0]["processes"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            return None
        measure = entry.get("workingSetBytes") if report.get("sort") == "memory" else entry.get("cpuUsagePercent")
        if measure is None:
            measure = entry.get("totalProcessorSeconds")
        if isinstance(measure, bool) or not isinstance(measure, (int, float)):
            return None
        # Rendered exactly as the observation JSON carries it (shortest
        # round-trip for a float, no exponent), so the line stays evidence.
        if isinstance(measure, int):
            rendered = str(measure)
        elif measure.is_integer():
            rendered = str(int(measure))
        else:
            rendered = repr(measure)
            if 'e' in rendered or 'E' in rendered:
                return None
        lines.append(f"{entry['name'].strip()}: {rendered}")
    if not lines:
        return None
    header = str(report.get("description") or "").strip()
    if not header:
        return None
    # The default name is built from the request's own words (its noun and its
    # resource word) so that it grounds in either language.
    noun = "processes" if "processes" in header.split() else "procesos"
    name = str(report.get("name") or f"{noun}-{report.get('resource_word') or 'memoria'}.txt")
    arguments: dict[str, object] = {"relativePath": name, "text": header + "\n" + "\n".join(lines) + "\n"}
    function = tool.get("function")
    schema = function.get("parameters") if isinstance(function, dict) else None
    if not isinstance(schema, dict) or not validate_json_schema_instance(arguments, schema):
        return None
    return arguments


def _verified_message_send_arguments(
    objective: str,
    observations: object,
) -> dict[str, object] | None:
    """Join one verified recipient identity with the user's literal message body."""

    if not isinstance(observations, list):
        return None
    recipient_ids = {
        result["recipientId"]
        for observation in observations
        if isinstance(observation, dict)
        and observation.get("operation") == "message.recipient.resolve"
        and observation.get("verified") is True
        and observation.get("status") == "completed"
        and isinstance((result := observation.get("result")), dict)
        and isinstance(result.get("recipientId"), str)
        and result["recipientId"].strip()
    }
    if len(recipient_ids) != 1:
        return None
    body = message_body(objective)
    if body is None:
        return None
    return {"recipientId": next(iter(recipient_ids)), "text": body}


def technical_failure_message(kind: str, failure: str) -> str:
    """Return a stable machine diagnostic, never a semantic user decision."""

    if failure not in {"contract", "runtime"}:
        raise ValueError("clase de fallo técnico inválida")
    surface = {
        "arguments": "arguments",
        "plan": "plan",
        "turn.decide": "turn",
    }.get(kind, "request")
    return f"{surface}_{failure}_failure"


def configure_tools(capabilities: object) -> list[dict]:
    """Valida el catálogo recibido del hello autenticado del core."""
    if not isinstance(capabilities, list) or not 1 <= len(capabilities) <= 256:
        raise PlannerContractError("catálogo ausente o fuera de límite")
    names: set[str] = set()
    tools: list[dict] = []
    for capability in capabilities:
        if not isinstance(capability, dict) or set(capability) != {
            "argumentsSchema",
            "description",
            "name",
            "risk",
        }:
            raise PlannerContractError("capacidad con forma no canónica")
        name = capability.get("name")
        description = capability.get("description")
        schema = capability.get("argumentsSchema")
        risk = capability.get("risk")
        if (
            not isinstance(name, str)
            or _OPERATION_NAME.fullmatch(name) is None
            or name in names
            or not isinstance(description, str)
            or not description.strip()
            or len(description) > 4096
            or not isinstance(schema, dict)
            or risk not in _KNOWN_RISKS
        ):
            raise PlannerContractError("capacidad inválida o duplicada")
        names.add(name)
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": name.replace(".", "_"),
                    "canonical_name": name,
                    "description": description,
                    "parameters": schema,
                    "risk": risk,
                },
            },
        )
    return tools


def configure_application_catalog(value: object) -> tuple[str, ...]:
    """Validate a bounded OS-authenticated app-name snapshot."""

    if value is None:
        return ()
    if not isinstance(value, dict) or set(value) != {
        "version",
        "verified",
        "complete",
        "names",
    }:
        raise PlannerContractError("catálogo de aplicaciones con forma inválida")
    if (
        type(value.get("version")) is not int
        or value.get("version") != 1
        or value.get("verified") is not True
        or value.get("complete") is not True
        or not isinstance(value.get("names"), list)
    ):
        raise PlannerContractError("catálogo de aplicaciones inválido")
    names = value["names"]
    if len(names) > 2_048:
        raise PlannerContractError("catálogo de aplicaciones fuera de límite")
    retained: list[str] = []
    normalized: set[str] = set()
    total_bytes = 0
    for name in names:
        if (
            not isinstance(name, str)
            or not name.strip()
            or any(character.isspace() and character not in " \t" for character in name)
            or any(unicodedata.category(character) == "Cc" for character in name)
        ):
            raise PlannerContractError("nombre de aplicación inválido")
        encoded = name.encode("utf-8")
        total_bytes += len(encoded)
        if len(encoded) > 512 or total_bytes > 262_144:
            raise PlannerContractError("catálogo de aplicaciones fuera de límite")
        key = " ".join(
            "".join(
                character
                for character in unicodedata.normalize(
                    "NFKD",
                    name.casefold(),
                )
                if not unicodedata.combining(character)
            ).split()
        )
        if not key or key in normalized:
            continue
        normalized.add(key)
        retained.append(name)
    return tuple(retained)


def configure_game_catalog(value: object) -> tuple[tuple[str, str, str], ...]:
    """Validate a bounded Core-authenticated installed-game snapshot."""

    if value is None:
        return ()
    if not isinstance(value, dict) or set(value) != {
        "version",
        "verified",
        "complete",
        "entries",
    }:
        raise PlannerContractError("catálogo de juegos con forma inválida")
    entries = value.get("entries")
    if type(value.get("version")) is not int or value.get("version") != 1:
        raise PlannerContractError("versión de catálogo de juegos inválida")
    if not isinstance(entries, list) or len(entries) > 4_096:
        raise PlannerContractError("catálogo de juegos fuera de límite")
    if value.get("verified") is False:
        if value.get("complete") is not False or entries:
            raise PlannerContractError("catálogo de juegos no verificado inválido")
        return ()
    if value.get("verified") is not True or value.get("complete") is not True:
        raise PlannerContractError("catálogo de juegos incompleto")
    retained: list[tuple[str, str, str]] = []
    total_bytes = 0
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {
            "provider",
            "appId",
            "name",
        }:
            raise PlannerContractError("entrada de catálogo de juegos inválida")
        provider = entry.get("provider")
        app_id = entry.get("appId")
        name = entry.get("name")
        if not all(isinstance(item, str) for item in (provider, app_id, name)):
            raise PlannerContractError("identidad de juego inválida")
        total_bytes += sum(
            len(item.encode("utf-8")) for item in (provider, app_id, name)
        )
        if total_bytes > 512 * 1024:
            raise PlannerContractError("catálogo de juegos fuera de límite")
        retained.append((provider, app_id, name))
    try:
        build_game_catalog_index(retained)
    except (TypeError, ValueError) as error:
        raise PlannerContractError("catálogo de juegos inválido") from error
    return tuple(retained)


def _create_planner_resources(
    tools: list[dict],
    encoder: Callable[..., Any] | None = None,
) -> tuple[PlannerCatalog, SkillRegistry]:
    """Build a usable lexical snapshot, optionally promoted with E5 vectors."""

    catalog = PlannerCatalog(tools, encoder=encoder)
    skills = SkillRegistry.load_default(
        [tool.name for tool in catalog.tools],
        encoder=encoder,
    )
    return catalog, skills


def _require_catalog_llm_ready(
    llm: Any | None,
    timeout: float = CATALOG_LLM_WARMUP_SECONDS,
) -> None:
    """Authenticate catalog readiness against the model warmup result."""

    if llm is not None and not llm.wait_warmup(timeout):
        raise RuntimeError("the LLM was not available for the catalog")


def validate_turn_decision(
    raw: object,
    candidate_operations: set[str],
) -> dict[str, object]:
    """Enforce the turn contract before the shell can observe a decision."""

    expected_fields = {
        "mode",
        "operation",
        "question",
        "conversation_kind",
        "effect_count",
        "effect_operations",
        "effect_verification",
        "response_language",
    }
    if not isinstance(raw, dict) or set(raw) != expected_fields:
        raise PlannerContractError("decisión de turno con forma inválida")
    mode = raw.get("mode")
    operation = raw.get("operation")
    question = raw.get("question")
    conversation_kind = raw.get("conversation_kind")
    effect_count = raw.get("effect_count")
    effect_operations = raw.get("effect_operations")
    effect_verification = raw.get("effect_verification")
    response_language = raw.get("response_language")
    if mode not in {"conversation", "clarify", "action", "plan"}:
        raise PlannerContractError("modo de turno inválido")
    if effect_count not in {"zero", "one", "multiple"}:
        raise PlannerContractError("conteo de efectos inválido")
    if (
        not isinstance(effect_operations, list)
        or len(effect_operations) > 8
        or any(
            not isinstance(value, str) or value not in candidate_operations
            for value in effect_operations
        )
    ):
        raise PlannerContractError("lista de efectos inválida")
    derived_effect_count = (
        "zero"
        if not effect_operations
        else "one"
        if len(effect_operations) == 1
        else "multiple"
    )
    if effect_count != derived_effect_count:
        raise PlannerContractError("conteo de efectos inconsistente")
    if effect_verification not in {
        "not_applicable",
        "agreed",
        "primary",
        "grounding_required",
        "grounded",
        "recovered",
        "multiple",
        "disagreement",
    }:
        raise PlannerContractError("verificación de efectos inválida")
    if response_language not in {"es", "en", "mixed"}:
        raise PlannerContractError("idioma de respuesta inválido")
    if operation is not None and (
        not isinstance(operation, str) or operation not in candidate_operations
    ):
        raise PlannerContractError("operación de turno fuera del catálogo candidato")
    if not isinstance(question, str) or len(question) > 512:
        raise PlannerContractError("pregunta de turno inválida")
    if not isinstance(conversation_kind, str) or conversation_kind not in {
        "",
        "social",
        "knowledge",
        "followup",
        "unsupported",
    }:
        raise PlannerContractError("tipo de conversación inválido")
    question = question.strip()
    if mode == "action":
        if (
            effect_count != "one"
            or effect_verification
            not in {
                "agreed",
                "primary",
                "grounding_required",
                "grounded",
                "recovered",
            }
            or operation is None
            or operation != effect_operations[0]
            or question
            or conversation_kind
        ):
            raise PlannerContractError(
                "action exige un efecto, una operación y ningún texto conversacional"
            )
    elif operation is not None:
        raise PlannerContractError("solo action puede declarar operación")
    if mode == "clarify":
        if (
            effect_count != "zero"
            or effect_verification != "not_applicable"
            or not question
            or conversation_kind
        ):
            raise PlannerContractError("clarify exige una pregunta")
    elif question:
        raise PlannerContractError("solo clarify puede declarar pregunta")
    if mode == "conversation":
        if (
            effect_count != "zero"
            or effect_verification != "not_applicable"
            or not conversation_kind
        ):
            raise PlannerContractError(
                "conversation exige tipo conversacional y cero efectos"
            )
    elif conversation_kind:
        raise PlannerContractError(
            "solo conversation puede declarar tipo conversacional"
        )
    if mode == "plan" and not (
        (effect_count == "multiple" and effect_verification == "multiple")
        or effect_verification == "disagreement"
    ):
        raise PlannerContractError(
            "plan exige múltiples efectos o desacuerdo semántico"
        )
    return {
        "mode": mode,
        "operation": operation,
        "question": question,
        "conversation_kind": conversation_kind,
        "effect_count": effect_count,
        "effect_operations": effect_operations,
        "effect_verification": effect_verification,
        "response_language": response_language,
    }


def apply_turn_action_grounding_gate(
    decision: dict[str, object],
    objective: str,
    tool_by_name: dict[str, dict],
    llm: object,
    *,
    ground_recovered: bool = True,
) -> dict[str, object]:
    """Require literal schema grounding before a required-argument action."""

    if decision.get("mode") != "action" or decision.get("effect_verification") not in {
        "grounding_required",
        "recovered",
    }:
        return decision
    operation = decision.get("operation")
    tool = tool_by_name.get(operation) if isinstance(operation, str) else None
    if tool is None:
        raise PlannerContractError("the pending grounding action is not in the catalog")
    if required_predecessors(operation):
        # The missing identity belongs to a verified producer, not to the
        # person. Preserve the selected leaf effect and let the planner add its
        # catalog-defined predecessor instead of asking for an impossible ID.
        dependent = dict(decision)
        dependent.update(
            {
                "mode": "plan",
                "operation": None,
                "question": "",
                "conversation_kind": "",
                "effect_verification": "disagreement",
            }
        )
        return dependent
    if decision.get("effect_verification") == "recovered" and not ground_recovered:
        return decision
    schema = tool["function"]["parameters"]
    if decision.get("effect_verification") == "recovered" and not schema.get(
        "required"
    ):
        # Recovery already crossed an independent effect detector, closed
        # selector and compatibility verifier. Parameterless reads have no
        # user literal left to extract; every required-argument recovery still
        # crosses the same concrete grounding boundary as a primary proposal.
        return decision
    grounded = _ground_explicit_arguments(
        operation,
        objective,
        schema,
    )
    if grounded is not None:
        accepted = dict(decision)
        accepted["effect_verification"] = "grounded"
        return accepted
    extraction = llm.extract_direct_arguments(
        objective, tool, stated_fields=_stated_argument_fields(operation, objective, schema),
    )
    extracted = extraction.arguments
    grounded, _ = normalize_objective_arguments(
        extracted,
        schema,
        objective,
    )
    if grounded is not None:
        accepted = dict(decision)
        accepted["effect_verification"] = "grounded"
        return accepted
    clarified = dict(decision)
    clarified.update(
        {
            "mode": "clarify",
            "operation": None,
            "question": extraction.fallback_question,
            "conversation_kind": "",
            "effect_count": "zero",
            "effect_operations": [],
            "effect_verification": "not_applicable",
        }
    )
    return clarified


def apply_conversation_effect_presentation(
    decision: dict[str, object],
    objective: str,
    llm: object,
    *,
    explicit_conversation_contract: bool = False,
    history: object = None,
    pending_clarification: bool | None = None,
    retired_catalog_effect: bool = False,
    audit: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    """Mark unsupported effects without ever promoting conversation to action."""

    if (
        explicit_conversation_contract
        or decision.get("mode") != "conversation"
        or decision.get("conversation_kind") != "knowledge"
        or conversation_only_content_request(objective)
        # IDENTITY1323 H0012 «to quien chuta eres.»: a question about who is
        # answering or what it does is answered by identity or the catalog;
        # the effect-shape guess («chuta» as a kick) must not turn it into a
        # clarification or an unsupported boundary.
        or read_request(objective).intents & {INTENT_IDENTITY, INTENT_CAPABILITY}
        # CONVERSATION1343: a reassurance («no te preocupes si…») is answered
        # with an acknowledgement and a visual-content request with a plain
        # boundary; neither is an incomplete effect to clarify.
        or reassurance_statement(objective)
        or visual_content_request(objective)
    ):
        return decision
    try:
        state, _ = llm._verify_semantic_effect_shape(objective)
    except ValueError:
        return decision
    if audit is not None:
        audit.append({"name": "conversation_effect_shape", "effect_state": state})
    if state not in {"complete", "not_complete"}:
        return decision
    # H0401: un informe en pasado de lo que hizo la persona no es un pedido,
    # y marcarlo como no soportado publicaba «No puedo reiniciar la PC tal como
    # fue pedido», negando algo que nadie pidió.
    if effect_intent.first_person_past_report(objective):
        return decision
    # Incompleteness is not a capability verdict. Only a fresh, zero-effect
    # knowledge turn can use this path; retired observations and previously
    # selected unsupported decisions retain their existing boundary.
    reading = read_request(objective)
    if (
        state == "not_complete"
        and not decision.get("effect_operations")
        and not decision.get("intent_operations")
        and not retired_catalog_effect
        # Shell history includes the current user message, even in a new
        # session. Absence of a prior request is the contextual condition.
        and _previous_user_request(
            history if isinstance(history, list) else [], objective,
        ) is None
        and not _history_has_pending_clarification(history, pending_clarification)
        and not effect_intent.explicit_non_action_frame(objective)
        and not effect_intent._negative_action_forms(effect_intent._fold(objective))
        and not reading.intents & {INTENT_REFUSE, INTENT_CONTINUE_CONSTRAINT}
        and not unsupported_live_machine_query(objective)
        and not unsupported_effect_demonstration_request(objective)
    ):
        try:
            question = llm.clarify_after_turn_failure(
                objective, history=history, timeout=TURN_DECIDE_RECOVERY_BUDGET_SECONDS,
            )
        except ValueError:
            question = ""
        if _recovery_question_is_valid(question, objective, history):
            clarified = dict(decision)
            clarified.update(
                mode="clarify", operation=None, question=question,
                conversation_kind="", effect_count="zero",
                effect_operations=[], effect_verification="not_applicable",
            )
            return clarified
    unsupported = dict(decision)
    unsupported["conversation_kind"] = "unsupported"
    return unsupported


def apply_out_of_world_boundary(
    decision: dict[str, object],
    objective: str,
    *,
    audit: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    """Keep the boundary of an unreachable place, whatever the history.

    cien-37 030/040: in a clean session «send flowers to Deimos» answers «I
    cannot send flowers to Deimos as requested»; with a block of turns in
    front the model proposed a send with a recipient it judged missing and the
    turn became «Who specifically should receive the flowers?», a question
    about the very thing that cannot be done. Nothing was executed in either
    case, so only a turn with no effect is closed here.
    """

    if (
        not effect_intent.out_of_world_request(objective)
        or decision.get("effect_operations")
        or decision.get("conversation_kind") == "unsupported"
    ):
        return decision
    bounded = dict(decision)
    bounded.update(
        mode="conversation",
        conversation_kind="unsupported",
        operation=None,
        question=None,
        intent_operations=[],
        effect_operations=[],
        effect_count="zero",
        effect_verification="not_applicable",
    )
    if audit is not None:
        audit.append(
            {"name": "out_of_world_boundary", "mode": "conversation", "operation": None}
        )
    return bounded


def apply_non_effect_conversation_classification(
    decision: dict[str, object],
    objective: str,
    *,
    retired_catalog_effect: bool = False,
    available_operations: tuple[str, ...] = (),
) -> dict[str, object]:
    """Do not present a non-request observation as a missing capability."""

    if (
        decision.get("mode") == "conversation"
        and decision.get("conversation_kind") == "unsupported"
        and not decision.get("effect_operations")
        and effect_intent.known_unsupported_effect_request(objective, available_operations)
    ):
        # LIMITS1701 «Puedes ver tu propio código y analizar si hay alguna
        # falla.»: a request the known-unsupported contract closed is a
        # request, however much its finite verbs read as narration; the
        # followup mirror answered it as a statement and the model invented
        # its own nature («opero como un modelo de lenguaje…»).
        return decision
    folded = effect_intent._strip_request_envelope(effect_intent._fold(objective))
    information_question = asks_for_information(objective)
    if (
        decision.get("mode") == "conversation"
        and not decision.get("effect_operations")
        and (
            unsupported_live_machine_query(objective)
            or unsupported_effect_demonstration_request(objective)
            # CONVERSATION1343 H0069: memes and images cannot be shown here.
            or visual_content_request(objective)
        )
    ):
        unsupported = dict(decision)
        unsupported["conversation_kind"] = "unsupported"
        return unsupported
    reads_as_narration = _reads_as_an_observation(folded)
    if (
        decision.get("mode") != "conversation"
        or decision.get("conversation_kind") != "unsupported"
        or decision.get("effect_operations")
        or confident_non_target_language(objective) is not None
        or (
            effect_request_is_authoritative(objective)
            and not information_question
            # "Pegar las fotos nos llevo la tarde" looks authoritative because
            # folding drops the accent and the past "llevó" reads as a present
            # tense. A text that is positively a statement must still be
            # allowed to stop being treated as a missing capability.
            and not reads_as_narration
        )
    ):
        return decision
    if _current_public_role_question(objective):
        # The local model cannot verify a time-sensitive office holder. Keep
        # the explicit unsupported contract so presentation cannot hallucinate
        # a current fact merely because the clause is grammatical knowledge.
        return decision
    if retired_catalog_effect:
        # A veto retired an authenticated catalogue operation for this request,
        # which means the decider had said the answer needs an observation of
        # *this* machine. Relabelling it as knowledge invites the model to
        # answer from memory, and it does: measured on the fresh paraphrase
        # corpus of goal 03, "cual es mi direccion ip" replied "Tu dirección IP
        # es 192.168.1.100" and "que fecha y hora tenemos" replied with a date
        # in 2023. Both are invented machine state presented as observed, which
        # is the one thing BAXY may never do. The local model knows nothing
        # about this machine; it can only observe it. Keeping the unsupported
        # contract is the same reasoning as the guard above, and at least it
        # asserts nothing nobody measured.
        return decision
    observation = (
        first_person_observation(folded)
        # That only recognises the person talking about themselves.
        # "El viaje del sabado fue muy tranquilo" is third-person narration, so
        # it fell through and came back as "No puedo hacer el viaje del
        # sabado": a refusal of something nobody asked for. A declarative
        # opening or a finite verb that is not the first word marks a statement;
        # an imperative still has its verb in front and stays unsupported.
        or reads_as_narration
    )
    is_question = (
        any(marker in objective for marker in ("?", "¿", "？")) or information_question
    )
    if not observation and not is_question:
        # A downstream veto is still an unsupported requested effect unless
        # the text is positively identified as an observation or a question.
        # Defaulting every unrecognized imperative to ``followup`` produced
        # misleading mirrors such as "You mention that the alarm needs to be
        # removed" instead of an honest model-authored abstention.
        return decision
    conversational = dict(decision)
    conversational["conversation_kind"] = (
        "knowledge" if is_question or names_a_question_word(folded) else "followup"
    )
    return conversational


def apply_information_question_effect_veto(
    decision: dict[str, object],
    objective: str,
    planner_catalog: PlannerCatalog,
    explicit_intent: EffectIntent | None = None,
) -> dict[str, object]:
    """Prevent an information question from authorizing a mutating effect."""

    if explicit_intent is not None or decision.get("mode") not in {"action", "plan"}:
        return decision
    folded = effect_intent._fold(objective)
    if effect_intent._request_head(folded) not in {
        "are",
        "como",
        "cual",
        "cuando",
        "cuanto",
        "cuanta",
        "cuantos",
        "cuantas",
        "donde",
        "esta",
        "estan",
        "how",
        "is",
        "que",
        "quien",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
    } and not is_elliptical_followup(objective):
        return decision
    operations = decision.get("effect_operations")
    if not isinstance(operations, list) or not operations:
        return decision
    tools = [
        planner_catalog.get(operation)
        for operation in operations
        if isinstance(operation, str)
    ]
    if len(tools) != len(operations) or all(
        tool is not None and tool.risk == "read_only" for tool in tools
    ):
        return decision
    conversational = dict(decision)
    conversational.update(
        {
            "mode": "conversation",
            "operation": None,
            "question": "",
            "conversation_kind": "knowledge",
            "effect_count": "zero",
            "effect_operations": [],
            "effect_verification": "not_applicable",
        }
    )
    return conversational


def apply_turn_action_relevance_veto(
    decision: dict[str, object],
    objective: str,
    planner_catalog: PlannerCatalog,
) -> dict[str, object]:
    """Remove direct-action authority when retrieval relevance disagrees.

    The relevance check is only a veto. It cannot select another operation or
    rewrite the primary effect list; the full objective is re-derived by the
    independently constrained planner.
    """

    if decision.get("mode") != "action":
        return decision
    if decision.get("effect_verification") == "recovered":
        # This path already requires a candidate-free effect detector, a
        # closed-catalog selector and an independent full-contract verifier.
        # E5 remains a veto for ordinary primary proposals, but must not undo
        # that stricter semantic consensus merely because a canonical English
        # operation leaf is distant from a multilingual request.
        return decision
    operation = decision.get("operation")
    if isinstance(operation, str) and planner_catalog.operation_is_relevant(
        objective, operation
    ):
        return decision
    vetoed = dict(decision)
    vetoed.update(
        {
            "mode": "plan",
            "operation": None,
            "question": "",
            "conversation_kind": "",
            "effect_verification": "disagreement",
        }
    )
    return vetoed


def apply_operation_domain_grounding_veto(
    decision: dict[str, object],
    objective: str,
    explicit_intent: EffectIntent | None = None,
    application_names: tuple[str, ...] | ApplicationCatalogIndex = (),
    compound_contract: CompoundEffectContract | None = None,
    game_catalog: GameCatalogIndex = GameCatalogIndex(),
    *,
    previous_user_text: str | None = None,
    available_operations: tuple[str, ...] = (),
    app_identity_audit: dict[str, Any] | None = None,
) -> dict[str, object]:
    """Remove authority when an ambiguous operation lacks its real domain.

    Exempting the ``read_only`` operations from this gate was measured and
    rejected. It looked free -- the gate exists to stop an unsolicited effect and
    an observation has none, so on the fresh paraphrase corpus of goal 03 it
    recovered eight rows of 124 without adding a single effect. It is refuted by
    a case a previous campaign already paid for and that lives in
    ``tests/test_turn_policy.py``: "How is the neural net?" proposes
    ``network.status``, which is read-only, and answering it would report the
    machine's connectivity to a question about neural networks. The gate does not
    only protect against effects; it protects against answering the wrong domain,
    and ``red``, ``tiempo``, ``memoria`` and ``pagina`` are polysemous in exactly
    that way. Risk class cannot stand in for domain.
    """

    if decision.get("mode") not in {"action", "plan"}:
        return decision
    operations = decision.get("effect_operations")
    if not isinstance(operations, list) or not operations:
        return decision
    if compound_contract is not None:
        projected = _project_compound_required_operations(
            operations,
            compound_contract,
        )
        if projected is not None and projected != operations:
            decision = dict(decision)
            decision.update(
                {
                    "mode": "plan",
                    "operation": None,
                    "question": "",
                    "conversation_kind": "",
                    "effect_count": "multiple",
                    "effect_operations": projected,
                    "effect_verification": "multiple",
                }
            )
            operations = projected
    app_open_count = operations.count("app.open")
    if app_open_count:
        app_evidence: tuple[str, ...] | None = None
        evidence_source = "unavailable"
        if explicit_intent is not None and operations == list(
            explicit_intent.operations
        ):
            evidence_source = "explicit_intent"
            app_evidence = tuple(
                evidence
                for operation, evidence in zip(
                    explicit_intent.operations,
                    explicit_intent.evidence,
                    strict=True,
                )
                if operation == "app.open"
            )
        elif compound_contract is not None:
            evidence_source = "compound_contract"
            app_evidence = _compound_operation_evidence(
                operations,
                compound_contract,
                "app.open",
            )
        elif app_open_count == 1:
            evidence_source = "objective"
            app_evidence = (objective,)
        identity_reason = "resolved"
        if app_evidence is None:
            identity_reason = "evidence_missing"
        elif len(app_evidence) != app_open_count:
            identity_reason = "evidence_count_mismatch"
        else:
            for evidence_index, evidence in enumerate(app_evidence):
                resolved_app_id = resolve_application_catalog_app_id(evidence, application_names)
                if app_identity_audit is not None:
                    try:
                        app_identity_audit.setdefault("resolutions", []).append(
                            {"evidence_index": evidence_index, "resolved_app_id": resolved_app_id}
                        )
                    except Exception:  # Diagnostics must not alter resolution or its short circuit.
                        app_identity_audit.clear()
                        app_identity_audit = None
                if resolved_app_id is None:
                    identity_reason = "resolver_unresolved"
                    break
        if app_identity_audit is not None:
            try:
                indexed = isinstance(application_names, ApplicationCatalogIndex)
                catalog_entries = (
                    application_names.entries if indexed
                    else application_names if isinstance(application_names, tuple) else None
                )
                app_identity_audit.update({
                    "boundary": "domain_grounding",
                    "operations": list(operations),
                    "app_open_count": app_open_count,
                    "evidence_source": evidence_source,
                    "evidence": app_evidence,
                    "evidence_count": None if app_evidence is None else len(app_evidence),
                    "reason": identity_reason,
                    "resolutions": app_identity_audit.get("resolutions", []),
                    "catalog_input_kind": "name_key_pairs" if indexed else type(application_names).__name__,
                    "catalog_entries": catalog_entries,
                    "catalog_complete": catalog_entries is not None,
                    "catalog_entry_count": None if catalog_entries is None else len(catalog_entries),
                })
            except Exception:  # Keep the legacy audit if the optional snapshot cannot be captured.
                app_identity_audit.clear()
        if identity_reason != "resolved":
            vetoed = dict(decision)
            vetoed.update(
                {
                    "mode": "conversation",
                    "operation": None,
                    "question": "",
                    "conversation_kind": "unsupported",
                    "effect_count": "zero",
                    "effect_operations": [],
                    "effect_verification": "not_applicable",
                }
            )
            return vetoed
    game_launch_count = operations.count("game.launch")
    if game_launch_count:
        game_evidence: tuple[str, ...] | None = None
        if explicit_intent is not None and operations == list(
            explicit_intent.operations
        ):
            game_evidence = tuple(
                evidence
                for operation, evidence in zip(
                    explicit_intent.operations,
                    explicit_intent.evidence,
                    strict=True,
                )
                if operation == "game.launch"
            )
        elif compound_contract is not None:
            game_evidence = _compound_operation_evidence(
                operations,
                compound_contract,
                "game.launch",
            )
        elif game_launch_count == 1:
            game_evidence = (objective,)
        if (
            game_evidence is None
            or len(game_evidence) != game_launch_count
            or any(
                resolve_game_catalog_app_id(evidence, game_catalog) is None
                for evidence in game_evidence
            )
        ):
            vetoed = dict(decision)
            vetoed.update(
                {
                    "mode": "conversation",
                    "operation": None,
                    "question": "",
                    "conversation_kind": "unsupported",
                    "effect_count": "zero",
                    "effect_operations": [],
                    "effect_verification": "not_applicable",
                }
            )
            return vetoed
    if explicit_intent is not None and operations == list(explicit_intent.operations):
        # The compositional recognizer already proved the action and its
        # domain clause by clause. Reapplying a whole-sentence ambiguity veto
        # would erase valid cross-domain compounds such as system status plus
        # process listing.
        return decision
    if decision.get("effect_verification") == "recovered":
        # Recovery authority already requires an independent candidate-free
        # effect detector, a closed-catalog selector, and a full operation
        # contract verifier. Reapplying the lexical domain detector would
        # erase semantically verified multilingual requests it cannot parse.
        # This exemption cannot select or rewrite an operation; every later
        # grounding, risk, confirmation, and provider-verification gate stays.
        return decision
    partial_message_dispatch = (
        operations == ["message.recipient.resolve"] and chat_message_dispatch(objective)
    )
    compound_assignments = (
        _unresolved_compound_assignments(operations, compound_contract)
        if compound_contract is not None
        else None
    )
    if compound_assignments is not None:
        # Known clauses were proved by the deterministic resolver. Check each
        # unresolved proposal against its own clause instead of the entire
        # sentence, where another domain can create a false mismatch.
        domain_mismatch = any(
            operation_domain_is_grounded(
                clause,
                operation,
                application_names,
            )
            is False
            for clause, operation in compound_assignments
        )
    else:
        domain_mismatch = partial_message_dispatch or any(
            isinstance(operation, str)
            and operation_domain_is_grounded(
                objective,
                operation,
                application_names,
                previous_user_text=previous_user_text,
                available_operations=available_operations,
            )
            is False
            for operation in operations
        )
    if not domain_mismatch:
        return decision
    vetoed = dict(decision)
    vetoed.update(
        {
            "mode": "conversation",
            "operation": None,
            "question": "",
            "conversation_kind": "unsupported",
            "effect_count": "zero",
            "effect_operations": [],
            "effect_verification": "not_applicable",
        }
    )
    return vetoed


def apply_compound_effect_conservation_veto(
    decision: dict[str, object],
    contract: CompoundEffectContract | None,
    tool_by_name: dict[str, dict] | None = None,
    llm: object | None = None,
    application_names: tuple[str, ...] | ApplicationCatalogIndex = (),
) -> dict[str, object]:
    """Prevent a semantic proposal from executing only part of a compound."""

    if contract is None or decision.get("mode") not in {"action", "plan"}:
        return decision
    operations = decision.get("effect_operations")
    assignments = (
        _unresolved_compound_assignments(operations, contract)
        if isinstance(operations, list)
        and all(isinstance(operation, str) for operation in operations)
        else None
    )
    if assignments and tool_by_name is not None and llm is not None:
        compatibility = getattr(
            llm,
            "_compound_clause_is_fully_compatible",
            None,
        )
        if callable(compatibility):
            try:
                verification_inputs: list[tuple[str, str, dict[str, object]]] = []
                for clause, operation in assignments:
                    if (
                        operation_domain_is_grounded(
                            clause,
                            operation,
                            application_names,
                        )
                        is False
                    ):
                        break
                    operation_contract = _turn_operation_contract(
                        tool_by_name.get(operation),
                        operation,
                        clause,
                        application_names,
                    )
                    if operation_contract is None:
                        break
                    verification_inputs.append((clause, operation, operation_contract))
                if len(verification_inputs) == len(assignments) and (
                    _prepare_parallel_compound_verification(
                        llm,
                        verification_inputs,
                    )
                    and _compound_compatibility_all(
                        compatibility,
                        verification_inputs,
                    )
                ):
                    # A recognized clause is preserved exactly in source order,
                    # while every unresolved clause has one independently
                    # verified closed-catalog identity. Argument grounding,
                    # Core risk/confirmation and provider verification remain.
                    return decision
            except Exception:  # noqa: BLE001 - uncertainty removes authority
                pass
    # Failing to preserve the requested effects is an interpretation failure,
    # not evidence that the request can be answered from general knowledge.
    # Reuse bounded turn recovery instead of inviting chat to invent the
    # observation that was just withheld. No effects have been dispatched.
    raise PlannerContractError("unresolved_compound_effects")


def _compound_compatibility_all(
    compatibility: Callable[[str, str, dict[str, object]], bool],
    inputs: list[tuple[str, str, dict[str, object]]],
) -> bool:
    """Verify independent clauses concurrently within the server slot bound."""

    if len(inputs) == 1:
        return bool(compatibility(*inputs[0]))
    with ThreadPoolExecutor(
        max_workers=min(2, len(inputs)),
        thread_name_prefix="baxy-compound-verify",
    ) as executor:
        futures = [
            executor.submit(compatibility, clause, operation, contract)
            for clause, operation, contract in inputs
        ]
        return all(bool(future.result()) for future in futures)


def _prepare_parallel_compound_verification(
    llm: object,
    inputs: list[tuple[str, str, dict[str, object]]],
) -> bool:
    """Release unused speculative slots before two independent verifiers."""

    if len(inputs) < 2:
        return True
    for method_name in (
        "_retire_deferred_language_work",
        "_retire_deferred_count_work",
    ):
        retire = getattr(llm, method_name, None)
        if callable(retire):
            retire()
    return True


def _unresolved_compound_assignments(
    operations: list[object],
    contract: CompoundEffectContract,
) -> tuple[tuple[str, str], ...] | None:
    """Bind exactly one proposed operation to each unresolved source clause."""

    requirements = contract.clause_requirements
    if not requirements:
        # Special contracts represent ambiguity, negation, correction,
        # unsupported timing or catalog identity conflicts. Cardinality alone
        # must never turn any of those into executable authority.
        return None
    expected_count = sum(
        len(required) if required else 1 for _, required in requirements
    )
    if len(operations) != contract.minimum_effects or len(operations) != expected_count:
        return None
    cursor = 0
    assignments: list[tuple[str, str]] = []
    for clause, required in requirements:
        if required:
            width = len(required)
            if tuple(operations[cursor : cursor + width]) != required:
                return None
            cursor += width
            continue
        operation = operations[cursor]
        if not isinstance(operation, str):
            return None
        assignments.append((clause, operation))
        cursor += 1
    return tuple(assignments) if cursor == len(operations) and assignments else None


def _project_compound_required_operations(
    operations: list[object],
    contract: CompoundEffectContract,
) -> list[object] | None:
    """Restore proven clause effects while retaining only unresolved proposals."""

    requirements = contract.clause_requirements
    if not requirements:
        return None
    expected_count = sum(
        len(required) if required else 1 for _, required in requirements
    )
    if (
        len(operations) != contract.minimum_effects
        or len(operations) != expected_count
        or any(not isinstance(operation, str) for operation in operations)
    ):
        return None
    cursor = 0
    projected: list[object] = []
    for _clause, required in requirements:
        if required:
            projected.extend(required)
            cursor += len(required)
        else:
            projected.append(operations[cursor])
            cursor += 1
    return projected if cursor == len(operations) else None


def _compound_operation_evidence(
    operations: list[object],
    contract: CompoundEffectContract,
    target_operation: str,
) -> tuple[str, ...] | None:
    """Bind identity-sensitive operations to every proven source clause."""

    requirements = contract.clause_requirements
    if not requirements:
        return None
    expected_count = sum(
        len(required) if required else 1 for _, required in requirements
    )
    if len(operations) != contract.minimum_effects or len(operations) != expected_count:
        return None
    cursor = 0
    evidence: list[str] = []
    for clause, required in requirements:
        if required:
            width = len(required)
            if tuple(operations[cursor : cursor + width]) != required:
                return None
            evidence.extend(
                clause for operation in required if operation == target_operation
            )
            cursor += width
            continue
        operation = operations[cursor]
        if not isinstance(operation, str):
            return None
        if operation == target_operation:
            evidence.append(clause)
        cursor += 1
    return tuple(evidence) if cursor == len(operations) else None


def _turn_operation_contract(
    tool: object,
    operation: str,
    clause: str,
    application_names: tuple[str, ...] | ApplicationCatalogIndex,
) -> dict[str, object] | None:
    """Project one authenticated Core descriptor into the compatibility shape."""

    if not isinstance(tool, dict):
        return None
    function = tool.get("function")
    if not isinstance(function, dict):
        return None
    description = function.get("description")
    schema = function.get("parameters")
    if (
        not isinstance(description, str)
        or not description.strip()
        or not isinstance(schema, dict)
    ):
        return None
    properties = schema.get("properties")
    required = schema.get("required")
    if not isinstance(properties, dict) or not isinstance(required, list):
        return None
    if any(
        not isinstance(name, str)
        or name not in properties
        or not isinstance(properties[name], dict)
        for name in required
    ):
        return None
    effective_description = _native_selection_description(
        operation,
        description.strip(),
    )
    if operation == "app.open":
        applications = build_application_catalog_index(application_names)
        occurrence = applications.occurrence_pattern
        if (
            occurrence is not None
            and occurrence.search(effect_intent._fold(clause)) is not None
        ):
            effective_description += (
                " The application name in this clause exactly matches the "
                "authenticated local application catalog and can be grounded "
                "to the required appId."
            )

    return {
        "description": effective_description,
        "arguments_schema": schema,
        "required_arguments": tuple(
            {"name": name, "schema": properties[name]} for name in required
        ),
    }


def _catalog_answers_the_request(
    routing_objective: str,
    objective: str,
    planner_catalog: PlannerCatalog,
    tool_by_name: dict[str, dict],
    llm: object,
    application_names: tuple[str, ...] | ApplicationCatalogIndex,
    *,
    depth: int = 4,
    history: list[dict[str, str]] | None = None,
    already_declined: frozenset[str] = frozenset(),
) -> str:
    """Name a catalogue operation that *is* what a closed refusal denied.

    Several deterministic paths close a turn with ``unsupported`` before any
    retrieval runs: the known-missing-variant list, the unavailable-application
    rule, and the unresolved-compound contract. Each is a hand-maintained
    vocabulary, and each therefore denies capabilities BAXY has as soon as the
    person words the request outside it. ``open the last file I downloaded``
    closes on the ``filesystem.file.open.named`` clause because its exemption
    lists ``ultimo``, ``latest``, ``reciente`` and ``newest`` but not ``last``,
    while ``filesystem.file.open.latest`` sits in the catalogue doing exactly
    what was asked. On the goal 03 corpus five of 124 rows died that way, all of
    them capabilities the catalogue has, and the ``knowledge`` verdicts of the
    same family are the same fault wearing a politer word: ``what is on my to do
    list`` is closed as a no-effect question and answered "I don't have access to
    your personal to-do list" while ``task.list`` is in the catalogue. Social and
    follow-up turns are left alone -- nobody greeting BAXY should pay for a
    catalogue probe.

    So a closed refusal no longer gets to speak before the catalogue is asked.
    This ranks the request against the authenticated operations and returns the
    first one the independent verifier identifies as the requested effect. It
    selects nothing: naming one is only the evidence that withdraws the
    refusal, after which the ordinary ranked path decides the turn.

    ``already_declined`` holds the operations the native selector was shown for
    this same request and called none of. Tandas 04f/05: asking it again over
    four of them was a second selector call before every model-path answer
    (0.4–1 s); in 344 audited model-path turns it changed one outcome, a clock
    request turned into a question about reading the clock.
    """

    shortlist = planner_catalog.shortlist(routing_objective)[:depth]
    if shortlist and {tool.name for tool in shortlist} <= already_declined:
        return ""
    native_select = getattr(llm, "_post_native_tool_selection", None)
    if getattr(llm, "_native_tool_policy_enabled", False) and callable(native_select):
        contracts = {
            tool.name: contract
            for tool in shortlist
            if (contract := _turn_operation_contract(
                tool_by_name.get(tool.name), tool.name, objective, application_names,
            )) is not None
        }
        if not contracts:
            return ""
        try:
            selected = native_select(objective, list(contracts), contracts, history or [])
            operations = selected.get("effect_operations")
            if (
                isinstance(operations, list)
                and operations
                and all(isinstance(name, str) and name in contracts for name in operations)
            ):
                return operations[0]
        except Exception:  # noqa: BLE001 - a failed probe adds no authority
            pass
        # AUTO may abstain. Do not override that with the older weak identity
        # classifier: it called an SSID follow-up a clock, audio and web read.
        return ""
    identifies = getattr(llm, "operation_is_the_requested_effect", None)
    if not callable(identifies):
        return ""
    for tool in shortlist:
        contract = _turn_operation_contract(
            tool_by_name.get(tool.name),
            tool.name,
            objective,
            application_names,
        )
        if contract is None:
            continue
        try:
            if identifies(objective, tool.name, contract):
                return tool.name
        except Exception:  # noqa: BLE001 - a silent verifier keeps the refusal
            return ""
    return ""


def _served_surface_reread(
    message: dict[str, Any],
    objective: str,
    history: object,
    *,
    llm: Any,
    planner_catalog: PlannerCatalog,
    turn_evidence: TurnEvidenceService,
    encoder: Callable[[Any], Any],
    tool_by_name: dict[str, dict],
    application_names: tuple[str, ...] | ApplicationCatalogIndex,
    game_catalog: GameCatalogIndex,
    on_signal: PendingTurnSignal | None,
    already_signaled: list[bool],
) -> dict[str, Any] | None:
    """The turn decided again on the canonical surface of a request about to be refused, or None.

    Only when the rewrite (``semantic.surface``) reads as a served request: the readers prove an effect or
    a missing value in it, or the curated domain gate grounds in it a served operation that the words as
    said did not name. Asking the catalogue about every refusal was measured and rejected (see the public
    lookup comment in ``_decide_turn_result``): the nearest neighbours of an out-of-catalogue request turned
    honest limits into questions. Here the evidence is a word the readers know standing where the person
    said another one; a limit of something BAXY does not have keeps its words and stays a limit.
    """

    canonical = semantic_surface.canonical(objective)
    if canonical is None:
        return None
    previous = _previous_user_request(history if isinstance(history, list) else [], objective)
    reading = semantic_reading.read(
        canonical,
        available_operations=tuple(tool.name for tool in planner_catalog.tools),
        application_names=application_names,
        game_catalog=game_catalog,
        previous_user_text=previous,
    )
    family: tuple[str, ...] = ()
    if reading.effects is None and reading.clarification is None:
        family = next(
            (
                (tool.name,)
                for tool in planner_catalog.shortlist(canonical)[:4]
                if operation_domain_is_grounded(canonical, tool.name, application_names) is True
                and operation_domain_is_grounded(objective, tool.name, application_names) is not True
                # An application or a game is grounded by its installed identity, as the domain veto
                # grounds it; an open verb alone («abre la puerta») names neither.
                and (tool.name != "app.open" or resolve_application_catalog_app_id(canonical, application_names))
                and (tool.name != "game.launch" or resolve_game_catalog_app_id(canonical, game_catalog))
            ),
            (),
        )
        if not family:
            return None
    turns = list(history) if isinstance(history, list) else []
    if turns and isinstance(turns[-1], dict) and turns[-1].get("role") == "user":
        turns[-1] = {**turns[-1], "content": canonical}
    try:
        result = _decide_turn_result(
            {**message, "text": canonical, "history": turns},
            llm=llm,
            planner_catalog=planner_catalog,
            turn_evidence=turn_evidence,
            encoder=encoder,
            tool_by_name=tool_by_name,
            application_names=application_names,
            game_catalog=game_catalog,
            on_signal=on_signal,
            served_surface=family,
            already_signaled=already_signaled,
        )
    except PlannerContractError:
        # A re-read that breaks its own turn contract adds nothing: the limit already decided stands.
        return None
    # The shell plans, confirms and resumes the words that were read.
    result.setdefault("objective", canonical)
    return result


def _recogniser_identity_holds(
    explicit_intent: EffectIntent,
    objective: str,
    tool_by_name: dict[str, dict],
    llm: object,
    application_names: tuple[str, ...] | ApplicationCatalogIndex,
) -> bool:
    """Let the deterministic recogniser decline the rows it resolved wrong.

    One-sided in the same direction as every other guard here: it can only
    withdraw the recogniser's claim, never move it to another operation. When it
    withdraws, the row is not refused -- it falls through to the ranked model
    path, which is the alternative goal 03 already measured for these exact
    rows.

    A silent or unavailable verifier keeps the recogniser exactly as it was.
    """

    identifies = getattr(llm, "operation_is_the_requested_effect", None)
    if not callable(identifies):
        return True
    for operation in explicit_intent.operations:
        contract = _turn_operation_contract(
            tool_by_name.get(operation),
            operation,
            objective,
            application_names,
        )
        if contract is None:
            return True
        try:
            if not identifies(objective, operation, contract):
                return False
        except Exception:  # noqa: BLE001 - a silent verifier never withdraws
            return True
    return True


def _withheld_invocation_operations(
    operations: tuple[str, ...],
    objective: str,
    tool_by_name: dict[str, dict],
    llm: object,
    application_names: tuple[str, ...] | ApplicationCatalogIndex,
) -> tuple[str, ...]:
    """The withdrawn operations, when every one is identified as the effect the person named.

    What it returns may be asked about, never done: the identity verdict accepts
    most wrong proposals. A single unidentified member returns nothing, never a
    set with a stranger inside it.
    """

    identifies = getattr(llm, "operation_is_the_requested_effect", None)
    if not callable(identifies) or not operations:
        return ()
    for operation in operations:
        if not isinstance(operation, str):
            return ()
        if effect_intent.operation_identity_is_a_near_miss(objective, operation):
            return ()
        contract = _turn_operation_contract(
            tool_by_name.get(operation),
            operation,
            objective,
            application_names,
        )
        if contract is None:
            return ()
        try:
            if not identifies(objective, operation, contract):
                return ()
        except Exception:  # noqa: BLE001 - a silent verifier never revives authority
            return ()
    return tuple(operations)


# D3 (00_IDENTIDAD «actúa solo y luego cuenta»; confirma sólo lo que destruye
# datos): what a withheld proposal may still do without the person being asked.
# Destroying, installing, paying and sending to someone else never act on this
# evidence; everything else is read, played, set or written and then told.
_ACTS_WITHOUT_ASKING_RISKS = frozenset({"read_only", "low_reversible", "privacy_sensitive"})


def _acts_without_asking(
    objective: str,
    operations: tuple[str, ...],
    tool_by_name: dict[str, dict],
    llm: object,
    application_names: tuple[str, ...] | ApplicationCatalogIndex,
    *,
    rewrite_grounded: bool = False,
) -> bool:
    """Whether operations a stage withheld, or a catalogue probe named, are done instead of offered.

    Tanda 4 2026-09-24: «let me know what today's date is», «please put the meeting
    with carla on my to do list», «find instructions on how to play taboo» were
    answered «Want me to …?». A complete request is done, never offered back as a
    yes/no question that asks for no value. The identity verifier cannot carry
    that authority: it keeps 46 of 48 right proposals but refuses only 21 of 84
    wrong ones (``LlmRuntime.operation_is_the_requested_effect``). Each operation
    acts only on stronger evidence: the words a reader knows name its domain once
    the request is said in its canonical surface (``rewrite_grounded``: the
    served-surface re-read proved it, and the readers read that surface first),
    or the strict verifier finds it satisfies the whole request. A near miss, a
    risk outside ``_ACTS_WITHOUT_ASKING_RISKS``, a silent verifier or a failed
    one keeps the stricter side: nothing acts.
    """

    if not operations:
        return False
    satisfies = getattr(llm, "operation_satisfies_the_request", None)
    for operation in operations:
        tool = tool_by_name.get(operation) if isinstance(operation, str) else None
        if (
            tool is None
            or (tool.get("function") or {}).get("risk") not in _ACTS_WITHOUT_ASKING_RISKS
            or effect_intent.operation_identity_is_a_near_miss(objective, operation)
        ):
            return False
        if rewrite_grounded:
            continue
        contract = _turn_operation_contract(tool, operation, objective, application_names)
        if contract is None or not callable(satisfies):
            return False
        try:
            if not satisfies(objective, operation, contract):
                return False
        except Exception:  # noqa: BLE001 - a silent verifier never grants authority
            return False
    return True


def _withheld_operation_verdict(
    objective: str,
    operations: tuple[str, ...],
    tool_by_name: dict[str, dict],
    llm: object,
    application_names: tuple[str, ...] | ApplicationCatalogIndex,
    *,
    rewrite_grounded: bool = False,
) -> tuple[str, str]:
    """What a withheld or probed proposal becomes: ``("act", "")``, ``("ask", question)`` or ``("", "")``.

    It acts when ``_acts_without_asking`` grounds it. When it may not act -- the
    strict verdict refused it, or its risk forbids acting unasked -- but the
    identity verifier names it, BAXY is unsure, not unable: a limit there would be
    a false «no hago eso» (00_IDENTIDAD: dice que no sólo a lo que no sabe hacer).
    It asks one yes/no question naming the operation it would run, never a
    restatement of the request. Named by neither, the model's answer or the limit
    stands.
    """

    if _acts_without_asking(
        objective, operations, tool_by_name, llm, application_names, rewrite_grounded=rewrite_grounded,
    ):
        return "act", ""
    if not _withheld_invocation_operations(operations, objective, tool_by_name, llm, application_names):
        return "", ""
    compose = getattr(llm, "confirm_operation_before_acting", None)
    if not callable(compose):
        return "", ""
    effects: list[tuple[str, str]] = []
    for operation in operations:
        contract = _turn_operation_contract(tool_by_name.get(operation), operation, objective, ())
        if contract is None:
            return "", ""
        effects.append((operation, str(contract["description"])))
    try:
        question = str(compose(objective, tuple(effects), timeout=TURN_DECIDE_RECOVERY_BUDGET_SECONDS))
    except Exception:  # noqa: BLE001 - a failed question is an honest refusal
        return "", ""
    return ("ask", question) if _recovery_question_is_valid(question, objective) else ("", "")


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
    r"\bi'?m\s+not\s+(?:sure|familiar)\b|\bi\s+am\s+not\s+(?:sure|familiar)\b|\bi\s+have\s+no\s+information\b"
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
        and callable(reads)
        and bool(reads(routing_objective))
    )


def _shortlist_with_required_effects(
    shortlist: tuple[PlannerTool, ...],
    required_operations: tuple[str, ...],
    planner_catalog: PlannerCatalog,
) -> tuple[PlannerTool, ...]:
    """Keep contract-recognized effects visible without exceeding the cap."""

    required_tools: list[PlannerTool] = []
    for operation in required_operations:
        tool = planner_catalog.get(operation)
        if tool is None:
            raise PlannerContractError(
                "el efecto reconocido no pertenece al catálogo autenticado"
            )
        if tool not in required_tools:
            required_tools.append(tool)
    required_names = {tool.name for tool in required_tools}
    remaining = [tool for tool in shortlist if tool.name not in required_names]
    return tuple([*required_tools, *remaining][:MAX_SHORTLIST_OPERATIONS])


def _compound_clause_shortlist(
    objective: str,
    planner_catalog: PlannerCatalog,
) -> tuple[PlannerTool, ...]:
    """Retrieve each spoken sequence clause without assigning an operation."""

    clauses = compound_retrieval_clauses(objective)
    if not clauses:
        return ()
    per_clause = min(4, max(3, 24 // len(clauses)))
    selected: list[PlannerTool] = []
    selected_names: set[str] = set()
    for clause in clauses:
        ranked = planner_catalog.shortlist(clause)
        added = 0
        for tool in ranked:
            if tool.name in selected_names:
                continue
            selected.append(tool)
            selected_names.add(tool.name)
            added += 1
            if added >= per_clause:
                break
    return tuple(selected[:MAX_SHORTLIST_OPERATIONS])


def _prepare_plan_prompt_resources(
    objective: str,
    expected_plan_operations: tuple[str, ...],
    planner_catalog: PlannerCatalog,
    skill_registry: SkillRegistry | None,
) -> tuple[tuple[PlannerTool, ...], str]:
    """Prepare only the retrieval context that can influence this plan."""

    if expected_plan_operations:
        # turn.decide already conserved these catalog-authenticated effects.
        # The explicit skeleton, its contract validation and argument grounding
        # consume only the effects (plus their required predecessors). E5
        # ranking and skill selection cannot change that closed skeleton.
        return (
            _shortlist_with_required_effects(
                (),
                expected_plan_operations,
                planner_catalog,
            ),
            "",
        )
    shortlist = planner_catalog.shortlist(objective)
    selected_skills = (
        skill_registry.select(
            objective,
            [tool.name for tool in shortlist],
        )
        if skill_registry is not None
        else ()
    )
    return shortlist, SkillRegistry.compact_prompt(selected_skills)


def apply_explicit_effect_contract(
    decision: dict[str, object],
    intent: EffectIntent | None,
) -> dict[str, object]:
    """Preserve explicit effects while leaving arguments and authority gated."""

    if intent is None:
        return decision
    operations = list(intent.operations)
    if not operations:
        return decision
    contracted = dict(decision)
    contracted.update(
        {
            "mode": intent.kind,
            "operation": operations[0] if len(operations) == 1 else None,
            "question": "",
            "conversation_kind": "",
            "effect_count": "one" if len(operations) == 1 else "multiple",
            "effect_operations": operations,
            "effect_verification": (
                "recovered" if len(operations) == 1 else "multiple"
            ),
        }
    )
    return contracted


def _explicit_response_language(objective: str) -> str:
    """Idioma de presentación de un efecto explícito. Owner: read_request."""

    return read_language(objective)


def _decisive_request_language(objective: str) -> str | None:
    """Idioma cuando la lectura tiene una selección inequívoca o mezcla explícita.

    El detector del modelo respondía en español a «post a letter to Eris» y a
    «book a shuttle to Callisto». Cuando la lectura del pedido tiene evidencia
    de un solo idioma no hay nada que preguntar: manda ella, que es el mismo
    owner con el que después se redacta y se valida.
    """

    reading = read_request(objective)
    if reading.language == "mixed":
        # Balanced evidence is a positive request for both languages, not an
        # absence of evidence to be replaced by a second monolingual choice.
        return "mixed"
    spanish, english = reading.evidence
    if bool(spanish) == bool(english):
        return None
    return reading.language


def _read_reply_language(objective: str, history: list[Any]) -> str | None:
    """The reply language the readers settle without the model, or None."""

    language = _decisive_request_language(objective)
    if language is None and _answers_the_last_question(history, objective):
        # MUSIC1753 «Play a song on Spotify.» → «Queen»: an answer with
        # no language of its own keeps the language of the request it
        # answers; a proper name is not Spanish evidence. tanda-02: only
        # an answer — a new request with no evidence goes to the detector.
        previous = _previous_user_request(history, objective)
        if isinstance(previous, str) and previous.strip():
            language = _decisive_request_language(previous)
    return language


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


def _with_session_alarm_selector(objective: str, history: object) -> str:
    """REOPEN1993 H0011: «cancelá la alarma» after this conversation set exactly
    one alarm reads as the latest-alarm cancellation; otherwise the text stays
    and the readers ask which alarm."""

    if not isinstance(history, list):
        return objective
    previous = history
    if previous and isinstance(previous[-1], dict) and previous[-1].get("role") == "user" and previous[-1].get("content") == objective:
        previous = previous[:-1]
    requests = [
        str(item.get("content") or "")
        for item in reversed(previous)
        if isinstance(item, dict) and item.get("role") == "user"
    ]
    rewritten = effect_intent.session_single_alarm_rewrite(objective, requests)
    return rewritten if rewritten is not None else objective


def _answers_the_last_question(history: object, current_request: str) -> bool:
    """BAXY's last message asked a question, so this one may be its answer."""

    last_reply = dialogue_slot.read_slot({}, history, current_request).last_reply
    return bool(last_reply) and last_reply.rstrip().endswith(("?", "？"))


def _window_query_reference_name(
    objective: str,
    history: object,
    application_names: tuple[str, ...] | ApplicationCatalogIndex,
) -> str | None:
    """Read the same bounded user reference during selection and grounding."""
    if not isinstance(history, list):
        return None
    previous = history[-12:]
    if (
        previous
        and isinstance(previous[-1], dict)
        and previous[-1].get("role") == "user"
        and previous[-1].get("content") == objective
    ):
        previous = previous[:-1]
    requests = [
        str(item.get("content") or "")
        for item in previous
        if isinstance(item, dict) and item.get("role") == "user"
    ]
    return effect_intent.resolve_application_window_followup_name(
        objective, requests, application_names,
    )


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


_OUTPUT_LEVEL_OPERATIONS = ("audio.volume", "audio.volume.adjust", "system.settings.adjust", "system.settings.set")


def _stated_argument_fields(operation: str, objective: str, schema: dict[str, object]) -> tuple[str, ...]:
    """Required fields the request already settles, so the question for the rest never asks them again.

    Tanda 3: a brightness lowered «un nivel» was asked «¿Cuánto y en qué dirección…?»:
    the direction was said. A field with one allowed value is settled by the operation itself, and the
    direction of a level change by the words that raise or lower it.
    """

    properties = schema.get("properties")
    required = schema.get("required")
    if not isinstance(properties, dict) or not isinstance(required, list):
        return ()
    stated: list[str] = []
    for field in required:
        contract = properties.get(field)
        enum = contract.get("enum") if isinstance(contract, dict) else None
        if isinstance(enum, list) and len(enum) == 1:
            stated.append(field)
        elif (
            field == "direction"
            and operation in _OUTPUT_LEVEL_OPERATIONS
            and semantic_levels.direction_of(objective) is not None
        ):
            stated.append(field)
    return tuple(stated)


def _ground_explicit_arguments(
    operation: str,
    evidence: str,
    schema: dict[str, object],
    application_names: tuple[str, ...] = (),
    game_catalog: GameCatalogIndex = GameCatalogIndex(),
    *,
    history: object = None,
) -> dict[str, object] | None:
    """Return a complete schema-grounded literal or abstain without inference."""

    explicit = _explicit_arguments_from_evidence(
        operation,
        evidence,
        application_names,
        game_catalog,
    )
    if explicit is None and operation == "window.application.status":
        name = _window_query_reference_name(evidence, history, application_names)
        if name is not None:
            explicit = {"name": name}
    if explicit is None:
        deferred = effect_intent.deferred_clarification_split(
            evidence, (operation, "audio.volume.adjust", "audio.volume"), application_names, game_catalog,
        )
        if deferred is not None:
            # AUDIO858 H0067, H0527: the App sends the whole compound; the
            # read clause alone carries the arguments (window.resolve's
            # listing selector), the other clause is asked in the final.
            explicit = _explicit_arguments_from_evidence(
                operation, deferred.read_text, application_names, game_catalog,
            )
    if explicit is None:
        # Tanda 3 «para la música, me va a explotar la cabeza»: the decision read the order inside talk,
        # an address or a fronted place; the arguments read that same clause.
        uttered = semantic_reading.utterance_form(
            evidence,
            lambda clause: effect_intent.resolve_explicit_effects(
                clause, (operation,), application_names, game_catalog,
            ),
        )
        if uttered is not None and uttered[1].operations == (operation,):
            explicit = _explicit_arguments_from_evidence(
                operation, uttered[1].evidence[0], application_names, game_catalog,
            )
    if explicit is None and operation == "browser.navigate.named":
        # MUSIC1827 «abrí chrome y poné música» → «¿qué música?» → «rock»: the
        # decision read the answer as the completed browser music request;
        # the arguments read that same surface (history or resumed objective).
        previous = _previous_user_request(history, evidence) if isinstance(history, list) else None
        answer = evidence
        folded_evidence = effect_intent._fold(evidence)
        if previous is None and "aclaracion confiable del usuario:" in folded_evidence:
            previous, _, answer = folded_evidence.partition("aclaracion confiable del usuario:")
        completed = effect_intent._completed_missing_music_request(
            answer.strip(), (previous or "").strip() or None, (operation, "media.play.query"),
        )
        if completed is not None and effect_intent._named_browser_music_request(completed) is not None:
            explicit = _explicit_arguments_from_evidence(
                operation, completed, application_names, game_catalog,
            )
    if (
        explicit is None
        and operation in ("media.play.youtube", "media.play.query")
        and isinstance(history, list)
    ):
        # MUSIC1571 «poné una canción» → «¿qué música?» → «Bad Bunny»: the
        # answer alone names no request, so the literal reader abstained and
        # the model's extraction decided the turn (H0405 asked «¿qué buscas
        # en YouTube sobre Bad Bunny?»; H0066 «lofi» happened to ground).
        # The decision already read the answer as the completed music
        # request; the arguments read that same surface.
        completed = effect_intent._completed_missing_music_request(
            evidence,
            _previous_user_request(history, evidence),
            ("media.play.query", "media.play.youtube"),
        )
        if completed is not None:
            explicit = _explicit_arguments_from_evidence(
                operation,
                completed,
                application_names,
                game_catalog,
            )
    if explicit is None and operation in ("message.send.test", "message.draft"):
        # MSGCLAR1851 «mandale al grupo Musica: prueba 1 …» → «¿en qué canal?»
        # → «por WhatsApp»: the decision read the answer as the completed
        # message request; the arguments read that same surface (from the
        # history, or from the resumed objective with the trusted prefix).
        previous = _previous_user_request(history, evidence) if isinstance(history, list) else None
        answer = evidence
        folded_evidence = effect_intent._fold(evidence)
        if previous is None and "aclaracion confiable del usuario:" in folded_evidence:
            previous, _, answer = folded_evidence.partition("aclaracion confiable del usuario:")
        completed = effect_intent._completed_missing_message_channel_request(
            answer.strip(), (previous or "").strip() or None, ("message.send", operation),
        ) or effect_intent._completed_missing_message_text_request(
            answer.strip(), (previous or "").strip() or None, ("message.send", operation),
        )
        if completed is not None:
            explicit = _explicit_arguments_from_evidence(
                operation, completed, application_names, game_catalog,
            )
    if explicit is None and operation in _OUTPUT_LEVEL_OPERATIONS:
        # Uso real 2026-09-23 «Brillo 20%», «baja un veinte por ciento», «a 40» after «bajá el brillo»: the
        # decision read the canonical level request (``output_level_request``). The arguments are read from
        # that same request, never from the model's reading of a bare number: brightness 100 became 60
        # because «a 40» was taken as «40 less».
        previous = _previous_user_request(history, evidence) if isinstance(history, list) else None
        answer = evidence
        folded_evidence = effect_intent._fold(evidence)
        if previous is None and "aclaracion confiable del usuario:" in folded_evidence:
            previous, _, answer = folded_evidence.partition("aclaracion confiable del usuario:")
        completed = output_level_request(
            answer.strip(), (previous or "").strip() or None, _OUTPUT_LEVEL_OPERATIONS,
        )
        if completed is not None:
            explicit = _explicit_arguments_from_evidence(
                operation, completed, application_names, game_catalog,
            )
    if explicit is None and operation == "wifi.connect.named":
        # REOPEN1957 H0170/H0376 «conectate al wifi de casa» → «¿cuál de las
        # guardadas es la de casa?» → «Fibertel-2G»: the answer names the
        # profile; the place comes from the previous request in the history.
        answer = effect_intent.wifi_place_answer(evidence, history)
        if answer is not None:
            explicit = {"profileName": answer[0], "place": answer[1]}
    if explicit is None and operation == "audio.app.volume.adjust":
        # AUDIO1791 «subí el volumen de spotify» → «¿cuánto?» → «20»: the
        # decision read the answer as the completed request; the arguments
        # read that same surface (from the history, or from the resumed
        # objective that carries the trusted clarification prefix).
        previous = _previous_user_request(history, evidence) if isinstance(history, list) else None
        answer = evidence
        folded_evidence = effect_intent._fold(evidence)
        if previous is None and "aclaracion confiable del usuario:" in folded_evidence:
            previous, _, answer = folded_evidence.partition("aclaracion confiable del usuario:")
        completed = effect_intent._completed_missing_app_volume_request(
            answer.strip(), (previous or "").strip() or None, (operation,), application_names,
        )
        if completed is not None:
            explicit = _explicit_arguments_from_evidence(
                operation, completed, application_names, game_catalog,
            )
    if explicit is None and isinstance(history, list):
        items = [item for item in history if isinstance(item, dict)]
        recent = [str(item.get("content") or "") for item in reversed(items) if item.get("role") == "user" and item.get("content") != evidence]
        completed = None
        if operation == "browser.navigate":
            # «abrelo en mi navegador» after «qué es X»: the arguments read the completed request.
            completed = effect_intent._completed_browser_search_pronoun_request(evidence, recent)
        if completed is None:
            # «hazla» after a cancelled request: the previous request's own arguments.
            completed = effect_intent._redo_previous_request(
                evidence, recent, frozenset({operation}), application_names, game_catalog,
            )
        if completed is not None:
            explicit = _explicit_arguments_from_evidence(
                operation, completed, application_names, game_catalog,
            )
    if explicit is None:
        return None
    if operation == "notification.schedule" and "recurrence" in explicit:
        # The repeating-event reader owns kind and recurrence (enum values the person need not
        # spell); the title is the person's words and the moment is read back by the clock reader.
        normalized = _normalize_grounded_operation_arguments(operation, explicit, evidence)
        return normalized if normalized is not None and validate_json_schema_instance(normalized, schema) else None
    if (
        operation in {"filesystem.create.directory", "filesystem.write.text", "file.compress", "file.open"}
        and effect_intent.folder_txt_zip_open_mission(evidence) is not None
    ):
        # REOPEN1957 H0542: the unnamed folder and file take Windows' default
        # names, which the person never spelled.
        return explicit if validate_json_schema_instance(explicit, schema) else None
    if operation == "input.key.press" and start_menu_request(effect_intent._fold(evidence)):
        # Tanda 4: the Start menu reader owns the key; the person says the menu, not «win».
        return explicit if validate_json_schema_instance(explicit, schema) else None
    if operation == "web.search" and near_the_person(evidence):
        # Uso real tanda 4c «comida para llevar cerca», «qué pasa en mi ciudad»: near
        # the person is near this PC's city, which the provider adds (``nearby``;
        # the person never spells a flag). The query crosses its usual grounding.
        query_only: dict | None = explicit
        if explicit.get("query") != news_lookup_query(evidence):
            query_only, _ = normalize_objective_arguments(explicit, schema, evidence)
        near = {**query_only, "nearby": True} if query_only is not None else None
        return near if near is not None and validate_json_schema_instance(near, schema) else None
    if operation == "web.search" and explicit.get("query") == news_lookup_query(evidence):
        # WEB1451 «qué pasó hoy en el mundo»: the news reader supplies the
        # word «noticias»; the scope words are the person's own.
        return explicit if validate_json_schema_instance(explicit, schema) else None
    if (
        operation == "web.search"
        and effect_intent.curiosity_request(evidence)
        and explicit.get("query") in effect_intent._CURIOSITY_TOPICS_ES + effect_intent._CURIOSITY_TOPICS_EN
    ):
        # KNOWLEDGE1505/1507 «decime una curiosidad»: the curiosity reader
        # supplies the subject from its own list; the person named none, so
        # the literal check would discard every pick and the turn asked back.
        return explicit if validate_json_schema_instance(explicit, schema) else None
    if operation == "filesystem.known.list" and explicit.get("folder") in (
        effect_intent._known_folder_listing_request(evidence),
        (effect_intent._known_folder_recent_listing(evidence) or (None, None))[0],
    ):
        # The listing reader owns the known-folder enum and the bounded limit;
        # neither is a word the person must spell literally.
        return explicit if validate_json_schema_instance(explicit, schema) else None
    if (
        operation == "filesystem.known.search"
        and effect_intent._literal_known_file_search(evidence) == explicit
    ):
        # The shared positive request grammar owns the known-folder enum;
        # the filename remains literal. Keep the authenticated schema boundary.
        return explicit if validate_json_schema_instance(explicit, schema) else None
    if (
        operation == "calculator.expression.evaluate"
        and effect_intent.calculator_expression_request(evidence) == explicit.get("expression")
    ):
        # UI1725: the expression is composed from the person's own numbers and
        # operator word («6 por 7» -> 6*7); the symbol is not a literal token.
        return explicit if validate_json_schema_instance(explicit, schema) else None
    if (
        operation in {"document.text.read", "document.pdf.read", "filesystem.explorer.count"}
        and (
            effect_intent.known_folder_file_path(evidence) is not None
            or effect_intent.explorer_count_request(evidence) is not None
        )
    ):
        # REOPEN1957 H0299/H0701: the folder enum, the subfolder and the
        # extension come from the path or the count request as read.
        return explicit if validate_json_schema_instance(explicit, schema) else None
    if (
        operation == "document.pdf.read"
        and effect_intent._pdf_summary_request(evidence) is not None
    ):
        # PDF1689: the reader owns the known-folder enum (all_known when no
        # folder is named); the file name remains the person's literal.
        return explicit if validate_json_schema_instance(explicit, schema) else None
    if (
        operation == "filesystem.known.trash.named"
        and effect_intent._file_trash_request(evidence) is not None
    ):
        # The deletion reader owns the known-folder enum, including all_known
        # when no folder is named («borrá el archivo viejo.txt»: FILES1241/002
        # failed as ambiguous because «all_known» has no literal in the text);
        # the file name remains the person's literal.
        return explicit if validate_json_schema_instance(explicit, schema) else None
    if operation == "window.resolve" and not validate_json_schema_instance(
        explicit, schema
    ):
        # A legacy process-only schema cannot represent title identity. Never
        # discard the selector to make this literal fit a different contract.
        return None
    if operation == "window.resolve" and "applicationName" in explicit:
        # The authenticated catalog owns this display name; the provider alone
        # binds it to a live OS application identity and issues a window token.
        return explicit if validate_json_schema_instance(explicit, schema) else None
    if operation == "window.resolve" and explicit.get("process") == "*" and explicit.get("byTitle") is False:
        # The closed inventory request supplies this catalog selector. The
        # person need not spell the provider's wildcard in natural language.
        return explicit
    if operation in {
        "app.installed",
        "app.open",
        "audio.app.volume.adjust",
        "audio.app.volume.set",
        "audio.mute",
        "audio.volume",
        "audio.volume.adjust",
        "browser.control",
        "browser.navigate",
        "browser.navigate.named",
        # Uso real 2026-09-23: the agenda readers own the UTC instants of a
        # window or an event (semantic.temporal); the title is the person's.
        "calendar.event.create",
        "calendar.event.list",
        "client.channel.locate",
        "message.draft",
        "message.send.test",
        "game.launch",
        # REOPEN1993 grupo G/N/W: the readers own the package name (catalog
        # name or the person's), the news topic and the weather place.
        "desktop.wallpaper.set",
        "file.compress",
        "file.open",
        "game.install.named",
        "game.uninstall.named",
        "package.install.prepare",
        "package.uninstall",
        "shell.command.run",
        "web.download",
        "web.news.headlines",
        "weather.current",
        "wifi.connect.named",
        "message.recipient.resolve",
        "email.send",
        "media.control",
        "media.play.query",
        "media.play.youtube",
        # VIDEO1929 H0737 «quiero ver stranger things en nerflix»: el extractor
        # conserva el título literal y aporta el único servicio del catálogo;
        # exigir que «netflix» apareciera escrito tal cual tiraba esa lectura y
        # el turno preguntaba en qué servicio, con el servicio delante.
        "streaming.play.named",
        "system.process.list",
        "system.settings.adjust",
        "system.settings.set",
        "system.settings.status",
        "system.status",
        "system.time",
        "window.application.status",
    }:
        # Core's verified installed application/game snapshots own identity
        # canonicalization. Requiring a canonical display name or opaque AppID
        # to also appear literally in user text would discard that authority.
        # Browser history directions cross a complete-request grammar.
        # Browser destinations cross an equally closed parser: only a literal
        # URL, bare host, named service, or explicitly requested Google query
        # encoded by that parser is canonical. The media
        # query parser preserves the literal query and supplies the catalog's
        # sole provider value. System scopes are enum identities selected by
        # the existing domain parser, not words the user must spell literally.
        # Process ranks use that same closed metric/cardinal parser.
        # Audio's closed quantity parser grounds word-valued levels and
        # relative directions before canonicalizing them to catalog values.
        # Rechecking those values as generic literals would lose that evidence.
        # Every path still crosses the exact catalog JSON
        # Schema here.
        return explicit if validate_json_schema_instance(explicit, schema) else None
    grounded, _ = normalize_objective_arguments(
        explicit,
        schema,
        evidence,
    )
    if grounded is None:
        return None
    normalized = _normalize_grounded_operation_arguments(
        operation,
        grounded,
        evidence,
    )
    return (
        normalized
        if normalized is not None and validate_json_schema_instance(normalized, schema)
        else None
    )


def _fold_with_source_offsets(value: str) -> tuple[str, tuple[int, ...]]:
    """Fold text exactly like the effect resolver while retaining source offsets."""

    expanded: list[tuple[str, int]] = []
    for source_index, source_character in enumerate(value):
        decomposed = unicodedata.normalize("NFKD", source_character.casefold())
        expanded.extend(
            (character, source_index)
            for character in decomposed
            if not unicodedata.combining(character)
        )

    folded: list[str] = []
    offsets: list[int] = []
    pending_space: int | None = None
    for character, source_index in expanded:
        if character.isspace():
            if folded and pending_space is None:
                pending_space = source_index
            continue
        if pending_space is not None:
            folded.append(" ")
            offsets.append(pending_space)
            pending_space = None
        folded.append(character)
        offsets.append(source_index)
    return "".join(folded), tuple(offsets)


def _restore_evidence_surfaces(
    objective: str,
    evidence: tuple[str, ...],
) -> tuple[str, ...]:
    """Map normalized clause evidence back to the user's original literals."""

    folded_objective, offsets = _fold_with_source_offsets(objective)
    if not offsets:
        return evidence
    restored: list[str] = []
    cursor = 0
    for fragment in evidence:
        folded_fragment = effect_intent._fold(fragment)
        position = folded_objective.find(folded_fragment, cursor)
        if position < 0:
            position = folded_objective.find(folded_fragment)
        if position < 0 or not folded_fragment:
            restored.append(fragment)
            continue
        source_start = offsets[position]
        source_end = offsets[position + len(folded_fragment) - 1] + 1
        surface = objective[source_start:source_end].strip(" \t\r\n,;:-")
        restored.append(surface or fragment)
        cursor = position + len(folded_fragment)
    return tuple(restored)


def _normalize_grounded_operation_arguments(
    operation: str,
    arguments: dict[str, Any],
    context: str = "",
    *,
    now_utc: datetime | None = None,
) -> dict[str, Any] | None:
    """Apply closed semantic constraints not expressible by catalog JSON Schema."""

    normalized = dict(arguments)
    if (
        operation == "note.read"
        and isinstance(normalized.get("noteId"), str)
        and normalized.get("noteId")
    ):
        # Core's selector contract is exactly one of noteId or title. A
        # dependency-produced opaque ID is stronger than the repeated title.
        normalized.pop("title", None)
    objective = context
    if operation == "ocr.read" and "language" not in normalized:
        language = literal_ocr_language(objective)
        if language is not None:
            normalized["language"] = language
    if operation == "vision.describe" and "prompt" not in normalized:
        prompt = literal_vision_prompt(objective)
        if prompt is not None:
            normalized["prompt"] = prompt
    if operation in {"notification.schedule", "reminder.create"}:
        raw_due = normalized.get("dueUtc")
        if not isinstance(raw_due, str):
            return None
        due_utc = _canonical_due_utc(
            raw_due,
            context,
            now_utc=now_utc,
        )
        if due_utc is None:
            return None
        normalized["dueUtc"] = due_utc
        if operation == "reminder.create" and isinstance(
            normalized.get("title"),
            str,
        ):
            title = reminder_title_without_que(str(normalized["title"]))
            if not title:
                return None
            normalized["title"] = title
    return normalized


def _expand_effect_plan(
    operations: tuple[str, ...],
    evidence: tuple[str, ...] = (),
) -> tuple[tuple[str, str], ...]:
    """Add only catalog-defined prerequisites while preserving every effect."""

    expanded: list[tuple[str, str]] = []
    seen_effects: set[str] = set()
    for index, operation in enumerate(operations):
        literal_evidence = (
            evidence[index].strip()
            if index < len(evidence) and evidence[index].strip()
            else ""
        )
        if (
            operation == "media.control"
            and "media.play.exact" in seen_effects
            and literal_evidence
            and not names_spotify(literal_evidence)
        ):
            # `media.play.exact` is Spotify-only in the public catalog. Carry
            # that literal source into the subsequent control step so its
            # optional `sourceApp` selector cannot drift to another SMTC app.
            literal_evidence += " en Spotify"
        prerequisites = required_predecessors(operation)
        repeated_identity_consumer = (
            operation in _IDENTITY_CONSUMERS and operation in seen_effects
        )
        if prerequisites and (
            repeated_identity_consumer
            or not any(
                prior_operation in prerequisites for prior_operation, _ in expanded
            )
        ):
            prerequisite = (
                "window.active"
                if operation == "app.close" and closes_the_active_window(literal_evidence)
                else prerequisites[0]
            )
            expanded.append(
                (
                    prerequisite,
                    literal_evidence
                    or f"Obtener el estado verificable requerido para {operation}.",
                )
            )
        purpose = (
            literal_evidence
            if literal_evidence
            else "Conservar y completar este efecto solicitado."
        )
        expanded.append((operation, purpose[:512]))
        seen_effects.add(operation)
    return tuple(expanded)


def _explicit_plan_skeleton(
    operations: tuple[str, ...],
    evidence: tuple[str, ...] = (),
) -> dict[str, object]:
    """Materialize recognized effects and their required dependencies."""

    steps: list[dict[str, object]] = []
    expanded = _expand_effect_plan(operations, evidence)
    for index, (operation, purpose) in enumerate(expanded, 1):
        step_id = f"step_{index}"
        dependencies: list[str] = []
        # A guarding read (tanda 4c, add only if absent) orders the step after it; its arguments stay literal.
        prerequisites = required_predecessors(operation) or conditional_predecessors(
            operation, purpose
        ) or guarding_predecessors(operation, purpose)
        candidate_indexes = [
            prior_index
            for prior_index in range(1, index)
            if expanded[prior_index - 1][0] in prerequisites
        ]
        if candidate_indexes:
            predecessor_index = _select_referenced_predecessor(
                candidate_indexes,
                purpose,
            )
            dependencies.append(f"step_{predecessor_index}")
        steps.append(
            {
                "id": step_id,
                "operation": operation,
                "purpose": purpose,
                "dependsOn": dependencies,
                "argumentsMode": (
                    "after_dependencies"
                    if dependencies
                    and (
                        operation in _IDENTITY_CONSUMERS
                        or bool(conditional_predecessors(operation, purpose))
                    )
                    else "literal"
                ),
            }
        )
    return {"kind": "plan", "question": "", "steps": steps}


def _irrelevant_plan_operations(
    proposal: Any,
    objective: str,
    planner_catalog: PlannerCatalog,
    expected_operations: tuple[str, ...],
) -> list[str]:
    """Apply the semantic veto only to effects that were inferred by plan."""

    if proposal.kind != "plan" or expected_operations:
        return []
    return [
        step.operation
        for step in proposal.steps
        if (
            operation_domain_is_grounded(
                objective,
                step.operation,
            )
            is False
            or not planner_catalog.operation_is_relevant(
                objective,
                step.operation,
            )
        )
        and not is_required_predecessor(step.operation, proposal.steps)
    ]


def _emit_early_turn_signal(
    *,
    path: str,
    objective: str,
    request_id: object,
    on_signal: PendingTurnSignal | None,
    already_signaled: list[bool],
    step_count: int = 1,
    llm: Any = None,
    phase: str = "understanding",
) -> threading.Thread | None:
    """Word the in-progress notice beside the decision, never in front of it.

    Tandas 04f/05 (2026-09-24): composed before the model path, the notice
    delayed every model-path answer by its own decode. It runs on its own thread
    now; the shell shows it only while this request is still pending, so a notice
    that finishes after the result is dropped there. Tanda-06b: it starts only
    when the request is still pending once its channel says the notice is due,
    and the request's end cancels one still being worded (``PendingTurnSignal``),
    so a turn that ends in time spends no decode on it. Returns the thread.
    """

    if already_signaled or on_signal is None:
        return None
    if not should_emit_early(path, step_count):
        return None
    compose = getattr(llm, "compose_user_message", None)
    if compose is None:
        return None
    # Reserved now so a later stage of this attempt does not word a second one;
    # released if no notice could be worded.
    already_signaled.append(True)

    def word() -> object:
        return compose(
            objective,
            "status",
            {
                "traceId": str(request_id or ""),
                "situation": json.dumps(
                    {
                        "kind": "status", "cause": "acting",
                        "polarity": "success", "phase": phase,
                    },
                    ensure_ascii=False,
                ),
            },
            timeout=2.5,
        )

    def word_and_signal() -> None:
        if not on_signal.notice_due():
            return
        cancellation = ChatCompletionCancellation()
        on_signal.on_close(cancellation.cancel)
        cancellable = getattr(llm, "_run_with_completion_cancellation", None)
        try:
            text = cancellable(cancellation, word) if callable(cancellable) else word()
        except Exception as error:  # noqa: BLE001 - optional prose cannot fail the turn
            already_signaled.clear()
            if cancellation.cancelled:
                # The request ended first: nothing is missing.
                return
            _append_turn_audit({
                "schema": "baxy.mind-turn-audit.v1",
                "request_id": request_id,
                "phase": "progress_unavailable",
                "error_type": type(error).__name__,
            })
            return
        if not str(text or "").strip():
            already_signaled.clear()
            return
        on_signal(
            turn_signal_payload(
                request_id,
                str(text).strip(),
            )
        )

    worker = threading.Thread(
        target=word_and_signal, name="baxy-early-signal", daemon=True,
    )
    worker.start()
    return worker


def _rearm_in_context(
    message: dict[str, Any],
    *,
    llm: Any,
    available_operations: tuple[str, ...],
    application_names: tuple[str, ...] | ApplicationCatalogIndex = (),
    game_catalog: GameCatalogIndex = GameCatalogIndex(),
    dialogue_state: dialogue_slot.DialogueState | None = None,
) -> tuple[str, str] | None:
    """Fill the dialogue slot: the request this message completes, or None.

    Returns (rearmed request, how) when the message depends on the previous turns
    (``semantic.dialogue.dependency``) and a rearmed request stays inside what was
    said or verified. The pattern path is tried first (pending request + answer); the
    model rewrites, with the verified dialogue state, what the patterns cannot join.
    Talk is never rewritten.
    """

    objective = str(message.get("text", "")).strip()
    history = message.get("history") or []
    slot = dialogue_slot.read_slot(message, history, objective)
    dependency = dialogue_slot.dependency(objective, slot)
    if dependency is None:
        return None

    def effects_of(candidate: str) -> tuple[str, ...]:
        def resolve(clause: str) -> EffectIntent | None:
            return resolve_explicit_effects(clause, available_operations, application_names, game_catalog)

        found = resolve(candidate)
        if found is None:
            uttered = semantic_reading.utterance_form(candidate, resolve)
            found = uttered[1] if uttered is not None else None
        return tuple(found.operations) if found is not None else ()

    def continued_operations() -> tuple[str, ...]:
        # What the message continues: what the last turn verified or was about (an effect, or the one its question
        # asks for), or what the readers read in the last request (a conversation turn reads none).
        if dialogue_state is not None and (dialogue_state.operations or dialogue_state.intended):
            return dialogue_state.operations or dialogue_state.intended
        previous = (dialogue_state.request if dialogue_state is not None else None) or _previous_user_request(
            history, objective,
        )
        return effects_of(previous) if previous else ()

    def audited(rearmed: str | None, how: str, proposal: str | None = None) -> tuple[str, str] | None:
        _append_turn_audit(
            {
                "schema": "baxy.mind-turn-audit.v1",
                "request_id": message.get("id"),
                "phase": "dialogue_slot",
                "dependency": dependency,
                "rearmed_by": how,
                "rearmed": rearmed,
                "model_proposal": proposal,
            }
        )
        return None if rearmed is None else (rearmed, how)

    def asked_for() -> tuple[str, ...]:
        # The operations the message itself asks for: read, or asked about for a missing value.
        try:
            asked = resolve_explicit_clarification_intent(objective, available_operations, application_names)
        except (TypeError, ValueError):
            asked = None
        return (*effects_of(objective), *(asked.operations if asked is not None else ()))

    def continuing(candidate: str) -> str | None:
        # Tanda 7: a follow-up continues what was done. Its request reads no effect, or only effects of that family
        # (tanda 9: or of what the message itself asks for, «ponme un timer de ese tiempo»); a correction of the
        # alarm or timer just set replaces it instead of setting a second one. None otherwise.
        read = effects_of(candidate)
        if not dialogue_slot.continues(read, (*continued_operations(), *asked_for()), dialogue_state):
            return None
        cancel = (
            dialogue_state.cancel_last_alarm(dialogue_slot.spanish(candidate))
            if dialogue_state is not None and read == ("notification.schedule",)
            and dialogue_slot.followup(objective).replaces_last
            else None
        )
        if cancel is None:
            return candidate
        replaced = f"{cancel} {'y' if dialogue_slot.spanish(candidate) else 'and'} {candidate}"
        return replaced if effects_of(replaced) == ("notification.cancel.latest", "notification.schedule") else None

    level = semantic_levels.read(objective)
    if level is not None and level.setting is not None:
        # «Volume más alto please», «Brillo 20%»: an output level that names its object stands on its own.
        return audited(None, "pattern_kept")
    if level is not None or semantic_levels.answer(objective) is not None:
        # Uso real 2026-09-23: «un 10» after «súbele un poco» was rewritten by the model as «súbele un poco a
        # la canción un 10», and «súbelo a 80» and «bájale» came back as questions about what to raise. An
        # output level is completed from the request it follows, with the object and direction that request
        # carried. A level that is not completed here («bájale», «más bajito») is read as it arrived, and the
        # level readers ask for the amount.
        completed = output_level_request(
            objective, _previous_user_request(history, objective) or slot.pending_request, available_operations,
            asked=slot.last_reply or "",
        )
        if completed is not None and resolve_explicit_effects(
            completed, available_operations, application_names, game_catalog,
        ) is not None:
            return audited(completed, "pattern")
        if level is not None and (
            dependency != "followup"
            or not continued_operations()
            or any(op.startswith(("audio.", "system.settings")) for op in continued_operations())
        ):
            # Tanda 7 «actually make it 9» after a timer is the timer's amount: only a level that follows a level
            # request, or nothing the readers read, stays a level.
            return audited(None, "pattern_kept")

    if (
        dependency == "reference"
        and slot.antecedents
        and dialogue_slot.asks_to_look_up(objective)
        and dialogue_slot.asked_about(slot.antecedents[0])
    ):
        # Fase 3.5 (dueño turn 59): «investigala» after «¿la nueva peli de X es buena?» looks up X.
        # Only words the person said; the rearmed request is classified as usual.
        substituted = dialogue_slot.substituted_reference(objective, slot.antecedents[0])
        if substituted is not None:
            return audited(substituted, "pattern")
    if dependency == "subject":
        # Uso real 2026-09-23: «cuántos años tiene» after «quién es el presidente
        # de chile» is that person's age, looked up, never recited from memory.
        completed = dialogue_slot.subject_completed(objective, slot.antecedents[0])
        if completed is not None:
            return audited(completed, "pattern")
    if dependency == "reference" and slot.antecedents and not dialogue_slot.asks_to_look_up(objective):
        # 2026-09-22: «cerralo» after «abrí el bloc de notas» was read alone as
        # "close the active window" and closed VS Code. With an antecedent, the
        # pronoun is that antecedent's object, never whatever is in front.
        substituted = dialogue_slot.substituted_reference(objective, slot.antecedents[0])
        if substituted is not None and resolve_explicit_effects(
            substituted, available_operations, application_names, game_catalog,
        ) is not None:
            return audited(substituted, "pattern")
        # Tanda 9: «pausalo un toque», «dale, seguí» right after a video — what the last turn acted on, named as the
        # readers name it; the request must read an effect of that family.
        for thing in dialogue_slot.things_acted_on(continued_operations(), read_language(objective) == "es"):
            candidate = dialogue_slot.with_object(objective, thing)
            settled = continuing(candidate) if candidate and effects_of(candidate) else None
            if settled is not None:
                return audited(settled, "pattern")
    if (
        dependency == "answer"
        and slot.pending_request
        and dialogue_slot.is_assent(objective)
        and _explicit_stable_no_effect_turn_decision(
            slot.pending_request, None, pending_clarification=False,
        ) is not None
    ):
        # 0758398ed: a plain «sí» to a yes/no question about a stable no-effect
        # request closes that request; it does not turn the offer into an effect.
        return audited(slot.pending_request, "pattern")
    if dependency == "answer" and slot.pending_request:
        try:
            asked = resolve_explicit_clarification_intent(
                slot.pending_request, available_operations, application_names,
            )
        except (TypeError, ValueError):
            asked = None
        joined = dialogue_slot.joined_answer(
            slot.pending_request,
            objective,
            percentage=asked is not None and bool({"amount", "level"} & set(asked.missing_fields)),
        )
        if joined is not None:
            try:
                resolved = resolve_explicit_effects(
                    joined, available_operations, application_names, game_catalog,
                )
                still_missing = resolve_explicit_clarification_intent(
                    joined, available_operations, application_names,
                )
            except (TypeError, ValueError):
                resolved, still_missing = None, None
            # The answer completes the question that was asked: the joined
            # request must land in the family of that question, never next to it.
            same_family = asked is None or (
                resolved is not None and bool(set(resolved.operations) & set(asked.operations))
            )
            if resolved is not None and still_missing is None and same_family:
                return audited(joined, "pattern")
    last_request = (dialogue_state.request if dialogue_state is not None else None) or (
        slot.antecedents[0] if slot.antecedents else None
    )
    if dependency == "destination" and last_request:
        # Fase 3.5 (held-out turn 18 «en YouTube mejor» after «tengo ganas de
        # escuchar reggaetón»): only the destination of the last request changes.
        # The model read «mejor» as «mejorar»; the pattern joins the destination
        # to the request as said and keeps it when the readers read it in the family
        # of that request. Tanda 7 «¿y en Mar del Plata?»: the last request is the
        # last turn's as completed («¿va a llover el finde?»), not the previous message.
        joined = dialogue_slot.joined_answer(last_request, objective)
        if (
            joined is not None
            and dialogue_slot.differs(joined, last_request)
            and effects_of(joined)
            and dialogue_slot.same_family(effects_of(joined), effects_of(last_request))
        ):
            return audited(joined, "pattern")
    if dependency == "followup":
        said = dialogue_slot.followup(objective)
        if (said.continued or said.corrected) and not dialogue_slot.refers_back(objective) and effects_of(said.said):
            # Tanda 7 «and remind me at 7:30 to call grandma»: after the connector, a complete request is itself.
            return audited(said.said, "pattern")
        # Tanda 7b: what the person's words already say with the last turn is not left to the model — a new amount,
        # hour or day for the last request, the song a music turn left playing, what was just set.
        music = any(op.startswith("media.") for op in continued_operations())
        for candidate in (
            dialogue_slot.corrected_request(last_request, objective),
            dialogue_slot.as_the_song(objective) if music else None,
            dialogue_state.listing_request(objective) if dialogue_state is not None else None,
            dialogue_slot.again(last_request, objective),
        ):
            settled = continuing(candidate) if candidate and effects_of(candidate) else None
            if settled is not None:
                return audited(settled, "pattern")
        # Tanda 9: «ponme un timer de ese tiempo» — only the value BAXY just gave is put in; the order is the
        # person's own, so whatever it reads is what they asked for.
        valued = dialogue_slot.value_from_reply(objective, slot.last_reply)
        if valued is not None and effects_of(valued):
            return audited(valued, "pattern")
        if not (said.continued or said.corrected) and not dialogue_slot.refers_back(objective) and effects_of(objective):
            # Verification 2026-09-25 (layer A log:147): «para la canción» (stop it) had the form of a place
            # («para la X», for the X), was rewritten and looked up. What reads a request by itself is that request.
            return audited(None, "pattern_kept")
    verified = dialogue_state.lines() if dialogue_state is not None else []
    try:
        rewritten = llm.rewrite_in_context(
            objective, slot.context_lines(), dependency=dependency, verified=verified,
            shape=dialogue_slot.shape(objective, dependency),
        )
    except Exception:  # noqa: BLE001 - a failed rewrite leaves the message as it arrived
        rewritten = None
    if rewritten is not None and not dialogue_slot.differs(rewritten, objective):
        return audited(None, "model_kept", rewritten)
    if rewritten and dialogue_slot.rewrite_stays_in_context(rewritten, objective, slot, verified):
        if dependency not in {"followup", "destination"}:
            return audited(rewritten, "model", rewritten)
        settled = continuing(rewritten)
        return audited(settled, "model" if settled else "model_rejected", rewritten)
    if dependency == "answer" and slot.held and slot.pending_request and rewritten is None:
        # The model was unavailable: the pending request the shell holds and its answer travel together in the
        # form the grounding readers already join (AUDIO1789). A question read only from the history is not held.
        return audited(f"{slot.pending_request}\nAclaración confiable del usuario: {objective}", "joined")
    return audited(None, "model_rejected" if rewritten else "model_failed", rewritten)


def _prepare_turn_result(
    message: dict[str, Any],
    *,
    llm: Any,
    planner_catalog: PlannerCatalog,
    turn_evidence: TurnEvidenceService,
    encoder: Callable[[Any], Any],
    tool_by_name: dict[str, dict],
    application_names: tuple[str, ...] | ApplicationCatalogIndex = (),
    game_catalog: GameCatalogIndex = GameCatalogIndex(),
    on_signal: PendingTurnSignal | None = None,
    dialogue_state: dialogue_slot.DialogueState | None = None,
) -> dict[str, Any]:
    """Prepare one side-effect-free turn result, after filling the dialogue slot.

    ``dialogue_state`` is what the conversation left so far (the serve loop owns it); it is read, never written,
    here.
    """

    rearmed = _rearm_in_context(
        message,
        llm=llm,
        available_operations=tuple(tool.name for tool in planner_catalog.tools),
        application_names=application_names,
        game_catalog=game_catalog,
        dialogue_state=dialogue_state,
    )
    if rearmed is not None:
        request = rearmed[0]
        history = list(message.get("history") or [])
        if (
            history
            and isinstance(history[-1], dict)
            and history[-1].get("role") == "user"
            and history[-1].get("content") == message.get("text")
        ):
            history[-1] = {**history[-1], "content": request}
        message = {**message, "text": request, "history": history, "pendingObjective": None}
    result = _decide_turn_result(
        message,
        llm=llm,
        planner_catalog=planner_catalog,
        turn_evidence=turn_evidence,
        encoder=encoder,
        tool_by_name=tool_by_name,
        application_names=application_names,
        game_catalog=game_catalog,
        on_signal=on_signal,
    )
    if rearmed is not None:
        # A partial offer's objective (the proved clauses) outranks the rearmed request.
        result.setdefault("objective", rearmed[0])
    return result


def _decide_turn_result(
    message: dict[str, Any],
    *,
    llm: Any,
    planner_catalog: PlannerCatalog,
    turn_evidence: TurnEvidenceService,
    encoder: Callable[[Any], Any],
    tool_by_name: dict[str, dict],
    application_names: tuple[str, ...] | ApplicationCatalogIndex = (),
    game_catalog: GameCatalogIndex = GameCatalogIndex(),
    on_signal: PendingTurnSignal | None = None,
    served_surface: tuple[str, ...] | None = None,
    already_signaled: list[bool] | None = None,
) -> dict[str, Any]:
    """Decide one side-effect-free turn result from the (rearmed) request.

    ``served_surface`` is None on the request as said; on the re-read of its canonical surface
    (``_served_surface_reread``) it holds the served operation that only the rewrite named, if any.
    """
    already_signaled = [] if already_signaled is None else already_signaled

    objective = str(message.get("text", ""))
    history = message.get("history") or []
    rewritten_objective = _with_session_alarm_selector(objective, history)
    if (
        rewritten_objective != objective
        and isinstance(history, list)
        and history
        and isinstance(history[-1], dict)
        and history[-1].get("role") == "user"
        and history[-1].get("content") == objective
    ):
        # The readers compare the last user turn with the objective by text.
        history = [*history[:-1], {**history[-1], "content": rewritten_objective}]
    objective = rewritten_objective
    routing_objective = effect_intent._strip_request_envelope(objective).strip()
    if not routing_objective:
        routing_objective = objective
    available_operations = tuple(tool.name for tool in planner_catalog.tools)
    authenticated_operations = tuple(tool_by_name)
    non_target_language = confident_non_target_language(objective)
    explicit_non_action = effect_intent.explicit_non_action_frame(objective)
    content_drafting = conversation_only_content_request(objective)
    # Preguntar por lo que hace o por lo que no hace el producto se contesta con
    # el catálogo, y pedir que siga la conversación sin abrir nada es un
    # encargo completo: en ninguno de los dos casos hay algo que aclarar.
    # Cuando salían por aquí, la persona recibía su propia pregunta de vuelta
    # —«¿Qué específicamente no puedes hacer en este PC?»—, vocabulario del
    # planificador, o una pregunta sobre el turno anterior —«Would you like to
    # hear a fun fact about Peru?»— (limites-14/003..006, limites-20/009,
    # panel-opus-13/038, /052).
    # cien-37 030 «send flowers to Deimos»: a place no operation reaches
    # has nothing to clarify either; the question asked for the detail of
    # something that cannot be done at all.
    # tanda-02 «¿cuál es tu lugar de origen?» came back as «¿Te refieres a un
    # lugar geográfico…?»: a question about BAXY himself has nothing to clarify.
    nothing_to_clarify = bool(
        read_request(objective).intents
        & {INTENT_IDENTITY, INTENT_CAPABILITY, INTENT_REFUSE, INTENT_CONTINUE_CONSTRAINT}
    ) or effect_intent.out_of_world_request(objective)
    # AUDIO858 H0067 «subí el volumen y decime qué fecha es», H0527 «listá
    # las ventanas y enfocá la mejor»: the read clause runs now and the
    # final ends with the question the other clause needs; the turn is not
    # a clarification and the input is not unresolved.
    deferred_clarification = (
        None
        if non_target_language is not None
        or content_drafting
        or explicit_non_action
        or nothing_to_clarify
        else effect_intent.deferred_clarification_split(
            objective,
            authenticated_operations,
            application_names,
            game_catalog,
        )
    )
    explicit_clarification = (
        None
        if non_target_language is not None
        or content_drafting
        or explicit_non_action
        or nothing_to_clarify
        or deferred_clarification is not None
        else resolve_explicit_clarification_intent(
            objective,
            authenticated_operations,
            application_names,
            previous_user_text=_previous_user_request(history, objective),
        )
    )
    missing_open_referent = (
        non_target_language is None
        and not content_drafting
        and not explicit_non_action
        and not nothing_to_clarify
        and not _history_has_pending_clarification(history, message.get("pendingClarification"))
        and _previous_user_request(history, objective) is None
        and _deictic_open_request(objective)
    )
    unresolved_input_kind = (
        None
        if non_target_language is not None
        or explicit_clarification is not None
        or deferred_clarification is not None
        or missing_open_referent
        or _history_has_pending_clarification(history, message.get("pendingClarification"))
        # AUDIO1789 «subí el volumen de spotify» → «¿cuánto?» → «20»: the shell
        # consumes its pending objective before this call, so the flag is
        # false; an answer the readers complete against the previous request
        # is that request, never noise.
        or _completes_previous_request(
            objective, history, authenticated_operations, application_names, game_catalog,
        )
        else _unresolved_input_kind(objective, application_names)
    )
    if unresolved_input_kind == "overheard_speech" and (
        _conversation_in_progress(history)
        # Uso real 2026-09-23 «por favor añade práctica el cuatro de febrero en el
        # parque del retiro a las dos de la tarde», «dame una notificación de
        # recordatorio para la reunión de mañana a las diez a. m.»: fifteen words
        # with no listed order verb at a clause start, yet a request the readers
        # prove. What they read is addressed to BAXY, not overheard; so is a request
        # said in one of the utterance forms they read (uso real 2026-09-24 «vamos a
        # oír algo de country y salsa que no sea de los estados unidos»).
        or resolve_explicit_effects(objective, authenticated_operations, application_names, game_catalog)
        is not None
        or semantic_reading.utterance_form(
            objective,
            lambda clause: resolve_explicit_effects(clause, authenticated_operations, application_names, game_catalog),
        )
        is not None
    ):
        # Fase 3.5 (owner 2026-09-21, turns 156–167, 208): a long message right
        # after BAXY spoke is the person talking to BAXY, not a conversation the
        # microphone overheard (DIALOGUE1513's rows all arrive with no dialogue).
        unresolved_input_kind = None
    if unresolved_input_kind == "bare_path":
        known_path = effect_intent.known_folder_file_path(objective)
        if known_path is not None and known_path[0] in available_operations:
            # REOPEN1957 H0299: a pasted path under a known folder is read, not asked about.
            unresolved_input_kind = None
    if unresolved_input_kind == "deictic_look" and _previous_user_request(history, objective) is None:
        # REOPEN1993 H0528: with nothing said before, the screen is what to look at.
        unresolved_input_kind = None
    if unresolved_input_kind == "deictic_text" and effect_intent.deictic_text_to_type(
        objective, _previous_user_request(history, objective), application_names,
    ) is not None:
        # REOPEN1993 H0097: the application just opened is where the text goes.
        unresolved_input_kind = None
    # APPS1495 «abres team», «Abre stea,»: an open order naming a near miss of
    # one or two catalog applications, with no context, asks which one.
    near_application_candidates = (
        ()
        if non_target_language is not None
        or explicit_clarification is not None
        or missing_open_referent
        or unresolved_input_kind is not None
        or explicit_non_action
        or _history_has_pending_clarification(history, message.get("pendingClarification"))
        or _previous_user_request(history, objective) is not None
        # LIMITS1677 «ejecuta pytest» → «¿Querés que abra Test Patterns?»: a
        # known unsupported effect names no application to near-match.
        or known_unsupported_effect_request(objective, available_operations)
        # REOPEN1993: exactly one installed candidate is opened by the effect
        # readers («abre Steel.» → Steam); only two candidates are asked about.
        or effect_intent.near_single_open_candidate(objective, application_names, game_catalog) is not None
        else (
            effect_intent.near_catalog_application_candidates(objective, application_names)
            # GAMES1533 «Ve a Mad de Rivals.»: an installed game almost named
            # is asked about the same way as an application.
            or effect_intent.near_catalog_game_candidates(objective, game_catalog)
        )
    )
    if (
        explicit_clarification is not None
        or missing_open_referent
        or unresolved_input_kind is not None
        or near_application_candidates
    ):
        if missing_open_referent or unresolved_input_kind is not None or near_application_candidates:
            intent_operations = []
            clarification_timeout = (
                DEICTIC_CLARIFICATION_CPU_BUDGET_SECONDS
                if os.environ.get("BAXY_MIND_NGL", "").strip() == "0"
                else TURN_DECIDE_RECOVERY_BUDGET_SECONDS
            )
            if near_application_candidates:
                question = llm.clarify_near_application(
                    objective,
                    near_application_candidates,
                    timeout=clarification_timeout,
                )
                if not _recovery_question_is_valid(question):
                    raise PlannerContractError("aclaración de aplicación aproximada inválida")
            elif unresolved_input_kind is not None:
                question = llm.clarify_unresolved_input(
                    objective,
                    unresolved_input_kind,
                    timeout=clarification_timeout,
                )
                if not _recovery_question_is_valid(question):
                    raise PlannerContractError("aclaración de entrada inválida")
            else:
                question = llm.clarify_missing_referent(
                    objective,
                    timeout=clarification_timeout,
                )
                if not _recovery_question_is_valid(question):
                    raise PlannerContractError("aclaración de referente inválida")
        else:
            assert explicit_clarification is not None
            intent_operations = list(explicit_clarification.operations)
            question = llm.formulate_explicit_clarification_question(
                objective,
                explicit_clarification.operations,
                explicit_clarification.missing_fields,
            )
        result = {
            "type": "turn.result",
            "id": message.get("id"),
            "kind": "clarify",
            "operation": None,
            "intentOperations": intent_operations,
            "effectOperations": [],
            "question": question,
            "reply": "",
        }
        if not missing_open_referent and unresolved_input_kind is None and not near_application_candidates:
            # APPS1495: the near-miss application question has no missing
            # field of an explicit clarification; asserting one failed the turn.
            assert explicit_clarification is not None
            result["missingFields"] = list(explicit_clarification.missing_fields)
        if effect_request_is_authoritative(objective):
            # A new command can lack a value without supplying one for the
            # preceding request. Keep its own objective for the next answer.
            result["startsNewObjective"] = True
        if unresolved_input_kind in {"overheard_speech", "noise", "echoed_words"}:
            # Nothing in it was a request: there is no objective for the next
            # message to complete, so talk after it is never joined to it.
            result["preserveObjective"] = False
        clarification_path = (
            "near_application_clarification"
            if near_application_candidates
            else "unresolved_input_clarification"
            if unresolved_input_kind is not None
            else "deictic_referent_clarification"
            if missing_open_referent
            else "explicit_clarification"
        )
        _append_turn_audit(
            {
                "schema": "baxy.mind-turn-audit.v1",
                "request_id": message.get("id"),
                "phase": "final",
                "decision_path": clarification_path,
                "candidate_operations": [],
                "raw_decision": None,
                "stages": [
                    {
                        "name": clarification_path,
                        "mode": "clarify",
                        "operation": None,
                        "effect_operations": [],
                        "effect_verification": "not_applicable",
                    }
                ],
                "final": {
                    "kind": result["kind"],
                    "intent_operations": result["intentOperations"],
                    "effect_operations": result["effectOperations"],
                    "question": question,
                    "missing_fields": result.get("missingFields", []),
                },
            }
        )
        return result
    recalled_literal = _literal_recall_reference(history, objective)
    # Uso real tanda 5 «roll that dice, ai» was looked up on the web: a die, a coin or a number is drawn by
    # the mind and said in conversation (llm.random_draw_request), with no dialogue behind it.
    drawn = recalled_literal is None and random_draw_request(objective) is not None
    literal_recall_decision = (
        {
            "mode": "conversation",
            "operation": None,
            "question": "",
            "conversation_kind": "social" if drawn else "followup",
            "effect_count": "zero",
            "effect_operations": [],
            "effect_verification": "not_applicable",
            "response_language": _explicit_response_language(objective),
        }
        if recalled_literal is not None or drawn
        else None
    )
    stable_no_effect_decision = (
        literal_recall_decision
        or _explicit_stable_no_effect_turn_decision(
            objective,
            history,
            pending_clarification=message.get("pendingClarification"),
        )
    )
    stable_no_effect_is_closed = (
        explicit_non_action
        or literal_recall_decision is not None
        or (
            stable_no_effect_decision is not None
            and (
                _assistant_capability_aspiration(objective)
                or _general_factoid_prompt(objective)
                or _personal_checkin_statement(objective)
                or _closed_unsupported_request(objective)
            )
        )
    )
    live_public_intent = effect_intent._weather_read_intent(
        effect_intent._strip_request_envelope(objective), available_operations
    ) or effect_intent._news_read_intent(
        effect_intent._strip_request_envelope(objective), available_operations
    ) or (
        EffectIntent(("web.search",), (objective,))
        if "web.search" in available_operations
        and effect_intent._public_live_lookup_request(
            effect_intent._strip_request_envelope(effect_intent._fold(objective))
        )
        else None
    )
    accepted_wifi_offer = effect_intent.accepted_wifi_offer(
        objective, history, available_operations
    )
    # REOPEN1957 H0170/H0376: the name answered after «¿cuál es la de casa?».
    wifi_place_answer = effect_intent.wifi_place_answer_intent(
        objective, history, available_operations
    )
    browser_search_pronoun = effect_intent.browser_search_pronoun_intent(
        objective, history, available_operations
    )
    redo_previous_request = effect_intent.redo_previous_request_intent(
        objective, history, available_operations, application_names, game_catalog
    )
    # Fase 3.5: the reading gate. The pattern and the utterance forms it does not
    # read alone come back as one Reading; the contextual readers above (a
    # pending offer, a pronoun, «repetilo») still come first.
    turn_reading = semantic_reading.read(
        objective,
        available_operations=available_operations,
        application_names=application_names,
        game_catalog=game_catalog,
        previous_user_text=_previous_user_request(history, objective),
    )
    explicit_intent = (
        None
        if non_target_language is not None or stable_no_effect_is_closed
        else accepted_wifi_offer
        or wifi_place_answer
        or browser_search_pronoun
        or redo_previous_request
        or live_public_intent
        or turn_reading.effects
        or (
            EffectIntent(("window.application.status",), (objective,))
            if "window.application.status" in available_operations
            and _window_query_reference_name(objective, history, application_names)
            is not None
            else None
        )
    )
    # rec5e2e6: the 4B identity verifier withdrew six true colloquial leaves
    # (app.open, note.create, task.create) after the grammar already named
    # them, and only one false sister (audio.status for a volume request).
    # Domain grounding still vetoes ungrounded families. Keep the recogniser.
    recogniser_declined: list[str] = []
    unresolved_compound_effects = unresolved_compound_contract(
        objective,
        available_operations,
        application_names,
        game_catalog,
        resolved_intent=explicit_intent,
        previous_user_text=_previous_user_request(history, objective),
    )
    # Fase 3.5: the catalog closes a single app/game name that is not installed.
    # A compound is not a name: «abre Spotify y baja el volumen» was read whole
    # as a game title, missed the library and became «no puedo abrir Spotify ni
    # bajar el volumen». Each clause of a compound is proved by its own path.
    compound_clauses = (
        None
        if non_target_language is not None
        else _leading_proved_clauses(
            objective,
            unresolved_compound_effects,
            lambda clause: resolve_explicit_effects(
                clause, available_operations, application_names, game_catalog
            ),
        )
    )
    catalog_unavailable_decision = (
        None
        # «lanza una moneda» is a draw, not a program named «moneda» that is not installed.
        if unresolved_compound_effects is not None or compound_clauses is not None
        or literal_recall_decision is not None
        else _catalog_unavailable_turn_decision(
            objective,
            explicit_intent,
            application_names,
            game_catalog,
        )
    )
    talk_act_decision = (
        None
        if non_target_language is not None
        else _talk_act_turn_decision(objective, explicit_intent, turn_reading.clarification)
    )
    # A request the readers prove has no operation (the known unsupported contracts).
    known_limit_requested = effect_request_is_authoritative(objective) and known_unsupported_effect_request(
        objective, available_operations,
    )
    explicit_conversation_decision = (
        _explicit_unsupported_turn_decision(objective)
        if non_target_language is not None
        # Fase 3.5: an incomplete compound («abre Steam y busca Batman») used to
        # become a flat «no puedo abrir Steam ni…», denying the clause BAXY can do.
        # It now reaches the model with the recognized operations forced into the
        # shortlist; compound conservation still vetoes a partial plan. Only a
        # request to demonstrate an unsupported effect is a limit here.
        or (
            unresolved_compound_effects is not None
            and unsupported_effect_demonstration_request(objective)
        )
        or known_limit_requested
        else catalog_unavailable_decision
        or _explicit_social_turn_decision(
            objective,
            history,
            pending_clarification=message.get("pendingClarification"),
        )
        or _explicit_nonunderstanding_turn_decision(
            objective,
            history,
            pending_clarification=message.get("pendingClarification"),
        )
        or talk_act_decision
        or stable_no_effect_decision
    )
    # Resolve the speech act before catalog candidates can prime a related
    # effect. The existing candidate-free guard includes personal/live reads
    # and compound actions; only agreement on stable knowledge closes here.
    # The inherited prohibition reader already distinguishes negative commands
    # from statements, questions and compounds, using the shared action heads.
    # Reclassifying its closed no-effect result against nearby tools can turn
    # an acknowledgement into an unsolicited observation. Keep its authority
    # identical to the prose contract: no operation and no asserted PC state.
    closed_no_effect_conversation = (
        stable_no_effect_decision is not None
        and effect_intent.explicit_negative_constraint(objective)
    )
    closed_conversation = (
        stable_no_effect_decision if closed_no_effect_conversation else explicit_conversation_decision
    )
    if (
        explicit_intent is None
        and closed_conversation is not None
        and not (
            non_target_language is None
            and closed_conversation.get("conversation_kind") == "unsupported"
            and catalog_unavailable_decision is not None
        )
    ):
        # Tandas 04f/05: a closed conversation still waited for the effect
        # guard and the catalogue probe before its reply began to decode. The
        # reply now decodes beside them; either one withdrawing the closure
        # retires it (``LlmRuntime.prepare_chat``).
        closed_kind = (
            "unsupported_language"
            if non_target_language is not None
            else str(closed_conversation.get("conversation_kind"))
        )
        _prepare_conversation_reply(
            llm,
            objective,
            _conversation_reply_arguments(
                history,
                conversation_kind=closed_kind,
                response_language=str(closed_conversation.get("response_language")),
                scoped=closed_kind == "social" and closed_conversation is not talk_act_decision,
                intent_operations=[],
                available_operations=available_operations,
            ),
        )
    verify_shape = getattr(llm, "_verify_semantic_effect_shape", None)
    if (
        not closed_no_effect_conversation
        and explicit_intent is None
        and non_target_language is None
        and stable_no_effect_decision is not None
        and stable_no_effect_decision.get("conversation_kind") == "knowledge"
        # Dev corpus 2026-09-23 «what is mom's email address»: a «what is» question the readers prove is a
        # request with no operation keeps its limit; the shape verifier answered it from memory.
        and not known_limit_requested
        and callable(verify_shape)
    ):
        try:
            closed_no_effect_conversation = verify_shape(objective) == ("no_effect", "zero")
        except Exception:  # noqa: BLE001 - retain normal interpretation on failure
            pass
    if closed_no_effect_conversation:
        explicit_conversation_decision = stable_no_effect_decision
    withdrawn_closed_refusal = ""
    if (
        not closed_no_effect_conversation
        and explicit_conversation_decision is not None
        and non_target_language is None
        and explicit_conversation_decision.get("conversation_kind")
        in {"unsupported", "knowledge"}
        # LIMITS1677 «cerrá todas las pestañas de chrome», «subí el volumen de
        # spotify»: a known unsupported contract is the root's finding that no
        # operation serves the request; the verifier withdrew it for a nearby
        # operation (browser.tabs.list, app.close, audio.volume.adjust) that
        # does not, and the model then asked or confirmed.
        and not known_unsupported_effect_request(objective, available_operations)
    ):
        # This is still interpretation, not an execution milestone. Composing
        # progress here spent the same deadline needed to decide and answer.
        withdrawn_closed_refusal = _catalog_answers_the_request(
            routing_objective,
            objective,
            planner_catalog,
            tool_by_name,
            llm,
            application_names,
            history=history,
        )
        if withdrawn_closed_refusal:
            explicit_conversation_decision = None
    if explicit_intent is not None:
        _emit_early_turn_signal(
            path=PATH_RECOGNIZER
            if len(explicit_intent.operations) <= 1
            else PATH_MODEL,
            objective=objective,
            request_id=message.get("id"),
            on_signal=on_signal,
            already_signaled=already_signaled,
            step_count=len(explicit_intent.operations),
            llm=llm,
        )
        shortlist = _shortlist_with_required_effects(
            (),
            explicit_intent.operations,
            planner_catalog,
        )
    elif explicit_conversation_decision is not None:
        # Neither deterministic conversation variant consumes candidates,
        # evidence or semantic scores. Avoid crossing the E5 process for data
        # that cannot influence the already-closed decision.
        shortlist = ()
    else:
        evidence_query = _turn_evidence_query(routing_objective, history)
        _emit_early_turn_signal(
            path=PATH_MODEL,
            objective=objective,
            request_id=message.get("id"),
            on_signal=on_signal,
            already_signaled=already_signaled,
            llm=llm,
        )
        # Retrieval ranks operations, not families. Ranking families and then
        # handing out a window inside the winner is a coarser question than the
        # one being asked, and the leaf the person meant lost its place to
        # siblings of a family that merely scored well. Measured end to end on
        # the fresh paraphrase corpus of goal 03 with the same decider, the
        # expected operation reached the decider in 73 turns of 124 that way and
        # in 102 this way. The compound contract still forces its own proved
        # identities in below.
        shortlist = planner_catalog.shortlist(routing_objective)
        if unresolved_compound_effects is not None:
            required = tuple(
                operation
                for sequence in unresolved_compound_effects.required_clause_sequences
                for operation in sequence
            )
            shortlist = _shortlist_with_required_effects(
                shortlist,
                required,
                planner_catalog,
            )
        elif (
            effect_intent._direct_public_search_query(routing_objective) is not None
            and getattr(planner_catalog, "get", None) is not None
            and planner_catalog.get("web.search") is not None
        ):
            # SEARCH2011 «dale, buscame recetas de pizza»: the retrieval left
            # web.search out of the shortlist and the decider took
            # filesystem.search, vetoed as unsupported. A direct public search
            # the reader recognizes keeps web.search visible to the decider.
            shortlist = _shortlist_with_required_effects(
                shortlist,
                ("web.search",),
                planner_catalog,
            )
        clause_shortlist = _compound_clause_shortlist(
            routing_objective,
            planner_catalog,
        )
        if clause_shortlist:
            clauses = compound_retrieval_clauses(routing_objective)
            advisory_operations = compound_retrieval_operation_hints(
                routing_objective,
                available_operations,
                application_names,
            )
            advisory_tools = tuple(
                tool
                for operation in advisory_operations
                if (tool := planner_catalog.get(operation)) is not None
            )
            if len(advisory_tools) == len(clauses) and len(clauses) >= 2:
                # Every isolated clause has exactly one closed-catalog match.
                # Keep only those advisory identities so unrelated leaves
                # cannot tempt the semantic selector to add an extra effect.
                # This remains retrieval-only: conservation and grounding
                # still decide whether the proposal can retain authority.
                shortlist = advisory_tools
            else:
                shortlist = tuple(
                    {
                        tool.name: tool
                        for tool in (
                            *advisory_tools,
                            *clause_shortlist,
                            *shortlist,
                        )
                    }.values()
                )[:MAX_SHORTLIST_OPERATIONS]
            if unresolved_compound_effects is not None:
                required = tuple(
                    operation
                    for sequence in unresolved_compound_effects.required_clause_sequences
                    for operation in sequence
                )
                shortlist = _shortlist_with_required_effects(
                    shortlist,
                    required,
                    planner_catalog,
                )
        if recogniser_declined:
            # The identity verifier may withdraw a true colloquial leaf that
            # E5 never ranked. Keep that leaf visible to the model path so a
            # decline cannot become a retrieval hole.
            shortlist = _shortlist_with_required_effects(
                shortlist,
                tuple(recogniser_declined),
                planner_catalog,
            )
    candidates = [
        {
            "name": tool.name,
            "description": tool.description,
            "arguments_schema": tool.schema,
        }
        for tool in shortlist
    ]
    evidence = (
        []
        if explicit_intent is not None or explicit_conversation_decision is not None
        else turn_evidence.retrieve(
            evidence_query,
            encoder,
            [tool.name for tool in shortlist],
        )
    )
    native_selection = (
        explicit_intent is None
        and explicit_conversation_decision is None
        and bool(candidates)
        and bool(getattr(llm, "_native_tool_policy_enabled", False))
    )
    if native_selection:
        # Tandas 04f/05: model-path conversations took 5–6 s, five serial calls
        # before the reply began. The native selector writes no reply of its own
        # (its prose is authored under tool-selection instructions, measured in
        # astra-audio-mind505); when it selects nothing the turn answers as
        # knowledge, and that reply now decodes beside the selection.
        _prepare_conversation_reply(
            llm,
            objective,
            _conversation_reply_arguments(
                history,
                conversation_kind="knowledge",
                response_language=_read_reply_language(objective, history),
                scoped=False,
                intent_operations=[],
                available_operations=available_operations,
            ),
        )
    raw_decision = (
        explicit_conversation_decision
        if explicit_conversation_decision is not None
        else _explicit_turn_decision(explicit_intent, objective)
        if explicit_intent is not None
        else llm.decide_turn(
            routing_objective,
            candidates,
            history=history,
            evidence=evidence,
        )
    )
    # Which of the three producers owned this decision. Without it a split by
    # cause cannot tell a recogniser hit from a retrieval hit: both publish a
    # candidate list that already contains the answer.
    decision_path = (
        "explicit_effects"
        if explicit_intent is not None
        else "explicit_conversation"
        if explicit_conversation_decision is not None
        else "model"
    )
    # The operations the native selector saw and declined, all of them.
    selector_declined = (
        frozenset(candidate["name"] for candidate in candidates)
        if decision_path == "model"
        and native_selection
        and isinstance(raw_decision, dict)
        and not raw_decision.get("effect_operations")
        else frozenset()
    )
    turn_audit: dict[str, Any] = {
        "schema": "baxy.mind-turn-audit.v1",
        "request_id": message.get("id"),
        "phase": "final",
        "decision_path": decision_path,
        "retrieval": ("semantic" if planner_catalog.ranks_semantically else "lexical"),
        "candidate_operations": [tool.name for tool in shortlist],
        "raw_decision": raw_decision,
        "stages": [
            stage
            for stage in (
                {
                    "name": "recogniser_declined",
                    "mode": "",
                    "operation": None,
                    "effect_operations": list(recogniser_declined),
                    "effect_verification": "not_applicable",
                }
                if recogniser_declined
                else None,
                {
                    "name": "closed_refusal_withdrawn",
                    "mode": "",
                    "operation": None,
                    "effect_operations": [withdrawn_closed_refusal],
                    "effect_verification": "not_applicable",
                }
                if withdrawn_closed_refusal
                else None,
            )
            if stage is not None
        ],
    }
    _append_turn_audit(
        {
            "schema": "baxy.mind-turn-audit.v1",
            "request_id": message.get("id"),
            "phase": "raw_attempt",
            "decision_path": decision_path,
            "retrieval": turn_audit["retrieval"],
            "candidate_operations": list(turn_audit["candidate_operations"]),
            "raw_decision": raw_decision,
            "stages": [],
        }
    )
    raw_intent_operations: object = None
    if isinstance(raw_decision, dict) and "intent_operations" in raw_decision:
        raw_decision = dict(raw_decision)
        raw_intent_operations = raw_decision.pop("intent_operations")
    decision = validate_turn_decision(
        raw_decision,
        {tool.name for tool in shortlist},
    )
    turn_audit["stages"].append(_turn_audit_stage("validated_raw", decision))
    if raw_intent_operations is None:
        intent_operations = list(decision["effect_operations"])
    elif (
        isinstance(raw_intent_operations, list)
        and len(raw_intent_operations) <= 8
        and all(
            isinstance(value, str) and value in {tool.name for tool in shortlist}
            for value in raw_intent_operations
        )
    ):
        intent_operations = (
            []
            if decision["mode"] == "conversation"
            and not effect_request_is_authoritative(objective)
            else list(raw_intent_operations)
        )
    else:
        raise PlannerContractError("lista de intenciones inválida")
    decision = apply_explicit_effect_contract(decision, explicit_intent)
    if explicit_intent is not None:
        # The explicit contract is the final operation-level interpretation,
        # even when an advisory no-effect classifier also noticed a tense word
        # inside payload text (for example “I will arrive” in a message). Keep
        # the diagnostic intent identity aligned with the effect contract that
        # actually owns the turn.
        intent_operations = list(explicit_intent.operations)
    decision = validate_turn_decision(
        decision,
        {tool.name for tool in shortlist},
    )
    turn_audit["stages"].append(_turn_audit_stage("explicit_contract", decision))
    effects_before_information_veto = tuple(decision["effect_operations"])
    decision_before_veto = decision
    decision = apply_information_question_effect_veto(
        decision,
        objective,
        planner_catalog,
        explicit_intent,
    )
    decision = validate_turn_decision(
        decision,
        {tool.name for tool in shortlist},
    )
    turn_audit["stages"].append(_turn_audit_stage("information_question", decision))
    effects_before_domain_grounding = tuple(decision["effect_operations"])
    app_identity_audit = {} if os.environ.get(TURN_AUDIT_ENV, "").strip() else None
    decision = apply_operation_domain_grounding_veto(
        decision,
        objective,
        explicit_intent,
        application_names,
        unresolved_compound_effects,
        game_catalog,
        previous_user_text=_previous_user_request(history, objective),
        available_operations=available_operations,
        app_identity_audit=app_identity_audit,
    )
    if app_identity_audit:
        turn_audit["app_open_identity"] = app_identity_audit
    decision = validate_turn_decision(
        decision,
        {tool.name for tool in shortlist},
    )
    turn_audit["stages"].append(_turn_audit_stage("domain_grounding", decision))
    withdrawn_effects = (
        effects_before_information_veto or effects_before_domain_grounding
    )
    if (
        withdrawn_effects
        and not decision["effect_operations"]
        and decision["mode"] == "conversation"
        and non_target_language is None
        and all(
            ((tool_by_name.get(operation) or {}).get("function") or {}).get("risk") == "read_only"
            for operation in withdrawn_effects
        )
        and _public_lookup_applies(
            objective, routing_objective, llm, available_operations, planner_catalog,
        )
    ):
        # Uso real 2026-09-23 «qué hora es en tokio» (system.time reads only this
        # PC's clock), «cuánto está el dólar hoy en chile», «dime alguna noticia de
        # negocios»: a withdrawn read of public information is looked up on the
        # web instead of offered back as «¿Quieres que…?».
        shortlist = _shortlist_with_required_effects(shortlist, ("web.search",), planner_catalog)
        decision = validate_turn_decision(
            _recovered_action_decision("web.search", decision.get("response_language")),
            {tool.name for tool in shortlist},
        )
        intent_operations = ["web.search"]
        turn_audit["stages"].append(_turn_audit_stage("public_lookup", decision))
    if (
        withdrawn_effects
        and not decision["effect_operations"]
        and decision["mode"] == "conversation"
    ):
        # Two stages withdraw an effect the model proposed, and both of them
        # publish the withdrawal as a *conversation* -- which the presentation
        # then words as "no puedo". Neither stage is entitled to that claim.
        # The curated gate is one-sided and lexical: it can only tell that the
        # request does not *name* the domain this operation consumes. The
        # information-question veto only knows that the sentence was phrased as
        # a question. Publishing either as an inability is how "No puedo apagar
        # el bluetooth" and "No puedo proporcionar tu dirección IP" reached the
        # screen about capabilities that are in the catalogue.
        #
        # Offering the withdrawn proposal back as «¿Quieres que …?» was the
        # repair until tanda 4 (2026-09-24): «let me know what today's date is»
        # and «please put the meeting with carla on my to do list» were complete
        # requests answered with a yes/no question that asks for no value, which
        # D3 forbids (confirm only what destroys data). The proposal now acts
        # when ``_acts_without_asking`` finds evidence stronger than its identity;
        # when only its identity holds, BAXY is unsure, not unable, and asks once
        # naming the operation it would run; identified by neither, "unsupported"
        # is the honest word (``_withheld_operation_verdict``).
        app_evidence = (
            explicit_intent.evidence
            if explicit_intent is not None
            and explicit_intent.operations == effects_before_domain_grounding
            else (objective,)
        )
        if (
            effects_before_domain_grounding == ("app.open",)
            and unresolved_compound_effects is None
            and effect_request_is_authoritative(objective)
            and len(app_evidence) == 1
            and isinstance(app_evidence[0], str)
            and app_evidence[0].strip()
            and resolve_application_catalog_app_id(app_evidence[0], application_names)
            is None
            and _withheld_invocation_operations(
                withdrawn_effects, objective, tool_by_name, llm, application_names,
            ) == ("app.open",)
        ):
            # This is the same single identity operand that withheld execution.
            # Ask for the missing target, not permission to repeat its opening.
            try:
                question = str(
                    llm.formulate_missing_argument_question(
                        objective,
                        "The requested application has no uniquely resolved catalog "
                        "identity. The missing detail is its identity, not permission "
                        "to open it. Installation absence has not been established.",
                        tool_by_name["app.open"],
                        ("appId",),
                    )
                )
                if not _recovery_question_is_valid(question, objective):
                    question = ""
            except Exception:  # noqa: BLE001 - no identity question grants authority
                question = ""
            if question:
                decision = validate_turn_decision(
                    {
                        "mode": "clarify",
                        "operation": None,
                        "question": question,
                        "conversation_kind": "",
                        "effect_count": "zero",
                        "effect_operations": [],
                        "effect_verification": "not_applicable",
                        "response_language": decision["response_language"],
                    },
                    {tool.name for tool in shortlist},
                )
                intent_operations = ["app.open"]
                turn_audit["stages"].append(
                    _turn_audit_stage("app_identity_question", decision)
                )
            else:
                intent_operations = []
        else:
            verdict, question = _withheld_operation_verdict(
                objective, withdrawn_effects, tool_by_name, llm, application_names,
            )
            if verdict == "act":
                decision = validate_turn_decision(
                    decision_before_veto,
                    {tool.name for tool in shortlist},
                )
                intent_operations = list(withdrawn_effects)
                turn_audit["stages"].append(
                    _turn_audit_stage("withheld_effect_grounded", decision)
                )
            elif verdict == "ask":
                decision = validate_turn_decision(
                    _operation_question_decision(question, decision["response_language"]),
                    {tool.name for tool in shortlist},
                )
                intent_operations = list(withdrawn_effects)
                turn_audit["stages"].append(
                    _turn_audit_stage("withheld_effect_question", decision)
                )
            else:
                intent_operations = []
    decision = apply_compound_effect_conservation_veto(
        decision,
        unresolved_compound_effects,
        tool_by_name,
        llm,
        application_names,
    )
    decision = validate_turn_decision(
        decision,
        {tool.name for tool in shortlist},
    )
    turn_audit["stages"].append(_turn_audit_stage("compound_conservation", decision))
    decision = apply_turn_action_relevance_veto(
        decision,
        objective,
        planner_catalog,
    )
    turn_audit["stages"].append(_turn_audit_stage("action_relevance", decision))
    decision = apply_turn_action_grounding_gate(
        decision,
        objective,
        tool_by_name,
        llm,
        ground_recovered=explicit_intent is None,
    )
    decision = validate_turn_decision(
        decision,
        {tool.name for tool in shortlist},
    )
    turn_audit["stages"].append(_turn_audit_stage("action_grounding", decision))
    decision = apply_conversation_effect_presentation(
        decision,
        objective,
        llm,
        explicit_conversation_contract=(explicit_conversation_decision is not None),
        history=history,
        pending_clarification=message.get("pendingClarification"),
        retired_catalog_effect=bool(
            effects_before_information_veto or effects_before_domain_grounding
        ),
        audit=turn_audit["stages"],
    )
    decision = apply_non_effect_conversation_classification(
        decision,
        objective,
        # Tanda 4 2026-09-24 «Cuál es la edad promedio que vive un ser humano?»: the decider proposed a web
        # search, the domain gate withdrew it and the question was published as «Eso no lo hago». A withdrawn
        # public lookup observed nothing of this machine, so it keeps no question from being answered.
        retired_catalog_effect=bool(
            set(effects_before_information_veto or effects_before_domain_grounding) - {"web.search"}
            and not decision["effect_operations"]
        ),
        available_operations=available_operations,
    )
    decision = validate_turn_decision(
        decision,
        {tool.name for tool in shortlist},
    )
    # After the non-effect classification, which rewrites the kind of a
    # question or an observation and would otherwise undo this boundary.
    decision = apply_out_of_world_boundary(
        decision, objective, audit=turn_audit["stages"],
    )
    turn_audit["stages"].append(
        _turn_audit_stage("conversation_presentation", decision)
    )
    # Extending the same rule to every ``unsupported`` conversation was measured
    # and rejected. When the *decider itself* answers "conversation,
    # unsupported" -- "No puedo dar enter" with ``input.key.press`` sitting in
    # the shortlist it was handed -- asking the catalogue again there looks like
    # the same repair. It is not: the candidates at that point are this
    # request's own retrieval, and for an out-of-catalogue request they are its
    # nearest plausible neighbours. On the goal 03 corpus it turned 8 of 36
    # honest abstentions into questions (28 -> 20) and recovered nothing in
    # catalogue (85 -> 84).
    #
    # A verdict that answers from what the model knows -- ``knowledge`` or
    # ``social`` -- is the one place where it is not optional, and it is not
    # about accuracy. Answering a question about the current state of *this
    # machine* from what the model knows is an invented observation presented as
    # an observed one: "con que usuario estoy entrado" came back as a social
    # reply asserting the account name, and "what does this page actually say"
    # as knowledge asserting the page contents, both with the operation that
    # would have observed it sitting in the shortlist. Goal 03 found three of
    # these and closed them with the retired-effect guard; these two are the
    # shape that guard cannot see, because no effect was ever proposed. Nothing
    # out of catalogue reaches this branch -- an out-of-catalogue request is
    # refused as ``unsupported``, never answered as knowledge -- so the
    # abstention it could cost is not on this path.
    #
    # Uso real 2026-09-23: «cuál es la tasa de cambio entre los pesos y el yen»,
    # «qué películas salen esta semana», «cómo está el tráfico» were answered
    # from memory («no tengo información en tiempo real») or refused. What the
    # person asks about the public world is looked up (00_IDENTIDAD: «si no sabe
    # algo, lo busca»); the guard alone decides it is public, never the person's
    # own data, and the search runs on the words the person said. It is read
    # before the catalogue probe below: «qué hora es en tokio» and «qué eventos
    # se celebran en la ciudad de nueva york» reached that probe first, which
    # named this PC's clock and the person's calendar and turned both into
    # «¿Quieres que te diga…?» about something that answers neither.
    if (
        decision["mode"] == "conversation"
        and decision.get("conversation_kind") in {"knowledge", "unsupported"}
        and non_target_language is None
        and _public_lookup_applies(
            objective, routing_objective, llm, available_operations, planner_catalog,
        )
    ):
        shortlist = _shortlist_with_required_effects(shortlist, ("web.search",), planner_catalog)
        decision = validate_turn_decision(
            _recovered_action_decision("web.search", decision.get("response_language")),
            {tool.name for tool in shortlist},
        )
        intent_operations = ["web.search"]
        turn_audit["stages"].append(_turn_audit_stage("public_lookup", decision))
    if (
        decision["mode"] == "conversation"
        and decision["conversation_kind"] in {"knowledge", "social"}
        and not decision["effect_operations"]
        and shortlist
    ):
        observing = _catalog_answers_the_request(
            routing_objective,
            objective,
            planner_catalog,
            tool_by_name,
            llm,
            application_names,
            history=history,
            already_declined=selector_declined,
        )
        # Tanda 4 2026-09-24 «find instructions on how to play taboo»: the probe
        # named routine.read and the turn asked «Want me to show you how to play
        # Taboo?». What the probe names is observed only on the evidence
        # ``_acts_without_asking`` demands; unsure, BAXY asks once naming the
        # operation it would run, never restating the request; named by neither
        # verifier, the model's own answer stands (``_withheld_operation_verdict``).
        verdict, question = (
            _withheld_operation_verdict(
                objective, (observing,), tool_by_name, llm, application_names,
            )
            if observing
            else ("", "")
        )
        if verdict == "act":
            shortlist = _shortlist_with_required_effects(shortlist, (observing,), planner_catalog)
            decision = validate_turn_decision(
                _recovered_action_decision(observing, decision["response_language"]),
                {tool.name for tool in shortlist},
            )
            intent_operations = [observing]
            turn_audit["stages"].append(
                _turn_audit_stage("observation_grounded", decision)
            )
        elif verdict == "ask":
            decision = validate_turn_decision(
                _operation_question_decision(question, decision["response_language"]),
                {tool.name for tool in shortlist},
            )
            intent_operations = [observing]
            turn_audit["stages"].append(
                _turn_audit_stage("observation_question", decision)
            )
    if (
        raw_intent_operations is not None
        and intent_operations
        and not decision["effect_operations"]
        and decision["mode"] == "conversation"
    ):
        question = llm.clarify_after_turn_failure(
            objective,
            history=history,
            timeout=TURN_DECIDE_RECOVERY_BUDGET_SECONDS,
        )
        if not _recovery_question_is_valid(question, objective, history):
            raise PlannerContractError("aclaración de intención inválida")
        decision = {
            "mode": "clarify",
            "operation": None,
            "question": question,
            "conversation_kind": "",
            "effect_count": "zero",
            "effect_operations": [],
            "effect_verification": "not_applicable",
            "response_language": decision["response_language"],
        }
    if _standalone_deictic_conversation_needs_clarification(
        objective, decision, history, message.get("pendingClarification"),
    ):
        question = llm.clarify_missing_referent(
            objective,
            timeout=(
                DEICTIC_CLARIFICATION_CPU_BUDGET_SECONDS
                if os.environ.get("BAXY_MIND_NGL", "").strip() == "0"
                else TURN_DECIDE_RECOVERY_BUDGET_SECONDS
            ),
        )
        if not _recovery_question_is_valid(question):
            raise PlannerContractError("aclaración de referente inválida")
        decision = {
            "mode": "clarify",
            "operation": None,
            "question": question,
            "conversation_kind": "",
            "effect_count": "zero",
            "effect_operations": [],
            "effect_verification": "not_applicable",
            "response_language": decision["response_language"],
        }
        intent_operations = []
        turn_audit["stages"].append(
            _turn_audit_stage("deictic_referent_clarification", decision)
        )

    partial_offer = (
        _compound_partial_offer(
            objective,
            compound_clauses,
            _decisive_request_language(objective) or str(decision.get("response_language") or ""),
        )
        if decision["mode"] == "conversation"
        and decision.get("conversation_kind") == "unsupported"
        and non_target_language is None
        else None
    )
    if partial_offer is not None:
        decision = {
            "mode": "clarify",
            "operation": None,
            "question": partial_offer[0],
            "conversation_kind": "",
            "effect_count": "zero",
            "effect_operations": [],
            "effect_verification": "not_applicable",
            "response_language": decision.get("response_language"),
        }
        intent_operations = []
        turn_audit["stages"].append(
            _turn_audit_stage("compound_partial_offer", decision)
        )

    # Tanda 3 2026-09-24: «Pausa el speaker.», «me apetece que hagas sonar algo
    # alegre», «Muéstrame mi Gallery.» were published as «no hago eso» about
    # things the catalog serves, named with words no reader knows. Before a limit
    # is published the request is re-read in its canonical surface; on that
    # re-read, a served operation only the rewrite named is done, never denied
    # (00_IDENTIDAD: dice que no sólo a lo que no sabe hacer) and, since tanda 4,
    # never offered back as «¿Quieres que…?» (D3); when its risk forbids acting
    # unasked, one question names the operation (``_withheld_operation_verdict``).
    if (
        decision["mode"] == "conversation"
        and decision.get("conversation_kind") == "unsupported"
        and non_target_language is None
    ):
        if served_surface is None:
            reread = _served_surface_reread(
                message,
                objective,
                history,
                llm=llm,
                planner_catalog=planner_catalog,
                turn_evidence=turn_evidence,
                encoder=encoder,
                tool_by_name=tool_by_name,
                application_names=application_names,
                game_catalog=game_catalog,
                on_signal=on_signal,
                already_signaled=already_signaled,
            )
            if reread is not None:
                # The re-read writes its own final row; this one records the limit it replaced.
                turn_audit["phase"] = "served_surface_reread"
                turn_audit["reread_objective"] = reread.get("objective")
                _append_turn_audit(turn_audit)
                return reread
        elif served_surface:
            verdict, question = _withheld_operation_verdict(
                objective, served_surface, tool_by_name, llm, application_names, rewrite_grounded=True,
            )
            if verdict == "act":
                shortlist = _shortlist_with_required_effects(shortlist, served_surface, planner_catalog)
                decision = validate_turn_decision(
                    _recovered_action_decision(served_surface[0], decision.get("response_language")),
                    {tool.name for tool in shortlist},
                )
                intent_operations = list(served_surface)
                turn_audit["stages"].append(
                    _turn_audit_stage("served_surface_grounded", decision)
                )
            elif verdict == "ask":
                decision = validate_turn_decision(
                    _operation_question_decision(question, decision.get("response_language")),
                    {tool.name for tool in shortlist},
                )
                intent_operations = list(served_surface)
                turn_audit["stages"].append(
                    _turn_audit_stage("served_surface_question", decision)
                )

    reply_text = ""
    # El idioma con el que se redacta la respuesta viaja con ella: el shell no
    # vuelve a adivinarlo para vetarla.
    response_language: str | None = None
    if decision["mode"] == "conversation":
        presentation_conversation_kind = (
            "unsupported_language"
            if non_target_language is not None
            else str(decision["conversation_kind"])
        )
        if explicit_conversation_decision is not None:
            # These closed ES/EN patterns already own a deterministic language
            # result. Calling the independent detector cannot change routing
            # and only repeats work before the same social/follow-up response.
            response_language = str(decision["response_language"])
        else:
            response_language = _read_reply_language(objective, history)
            if response_language is not None:
                # La lectura decide: la inferencia especulativa se retira sin
                # consumirse, igual que en una ruta sin conversación.
                retire_decided = getattr(
                    llm,
                    "retire_deferred_response_language",
                    None,
                )
                if callable(retire_decided):
                    retire_decided(objective)
            else:
                consumed_deferred_language = False
                consume_deferred = getattr(
                    llm,
                    "consume_deferred_response_language",
                    None,
                )
                if callable(consume_deferred):
                    (
                        consumed_deferred_language,
                        response_language,
                    ) = consume_deferred(objective)
                if not consumed_deferred_language or response_language is None:
                    try:
                        response_language = llm.detect_response_language(objective)
                    except ValueError:
                        response_language = None
        if (
            presentation_conversation_kind == "unsupported"
            and catalog_unavailable_decision is not None
        ):
            # The catalog established a capability boundary, not a failed
            # provider operation or proof that a named object does not exist.
            # Use the same typed error composer as the shell; the separate
            # conversational refusal inferred absence from the target name.
            reply_text = llm.compose_user_message(
                objective,
                "error",
                {
                    "situation": json.dumps(
                        {
                            "kind": "failure",
                            "polarity": "failure",
                            "cause": "out_of_catalog",
                        }
                    )
                },
            )
        else:
            reply_text, _ = llm.chat(
                objective,
                **_conversation_reply_arguments(
                    history,
                    conversation_kind=presentation_conversation_kind,
                    response_language=response_language,
                    scoped=(
                        explicit_conversation_decision is not None
                        and presentation_conversation_kind == "social"
                        # Talk about the dialogue («no lo hiciste», «odio estos
                        # fallos») is about the earlier turns: it keeps them.
                        and explicit_conversation_decision is not talk_act_decision
                    ),
                    intent_operations=intent_operations,
                    available_operations=available_operations,
                ),
            )
        reply_text = reply_text.strip()
        if not reply_text:
            raise PlannerContractError(
                "no se pudo preparar una respuesta conversacional"
            )
        # Tanda 1 2026-09-23 «¿Conoces el lenguaje de programación Monkey C?» →
        # «No, no conozco…»: what BAXY says he does not know about the public
        # world is looked up (00_IDENTIDAD: «si no sabe algo, lo busca»); never
        # the person's own things, BAXY himself or what he can do.
        if (
            presentation_conversation_kind in {"knowledge", "followup"}
            and non_target_language is None
            and _ADMITS_NOT_KNOWING.search(effect_intent._fold(reply_text)) is not None
            and not read_request(objective).intents
            & {INTENT_IDENTITY, INTENT_CAPABILITY, INTENT_REFUSE}
            and "web.search" in available_operations
            and planner_catalog.get("web.search") is not None
            and not not_a_public_lookup(objective)
            # «rate five», «tuitea a Vodafone…»: a known limit is an order, not something to look up.
            and not known_unsupported_effect_request(objective, available_operations)
            # Tanda 4e «oye compárteme algún chiste para hacerme feliz» was searched and answered with joke
            # sites: a joke, a story or a poem asked for is written, never looked up.
            and _conversation_presentation_shape(
                objective, conversation_kind=presentation_conversation_kind, has_history=False,
            ) not in _WRITTEN_CONTENT_SHAPES
        ):
            shortlist = _shortlist_with_required_effects(shortlist, ("web.search",), planner_catalog)
            decision = validate_turn_decision(
                _recovered_action_decision("web.search", decision.get("response_language")),
                {tool.name for tool in shortlist},
            )
            intent_operations = ["web.search"]
            turn_audit["stages"].append(_turn_audit_stage("unknown_looked_up", decision))
            reply_text = ""
        # Una explicación que sólo devuelve otra pregunta no contesta nada:
        # «para qué lo necesita el PC» salió como «¿Para qué necesita el PC
        # para ejecutar tareas específicas?» (seguimiento-13/020), y «cuáles
        # son tus límites aquí» como «¿Cuáles son los límites de esta PC?»
        # (limites-14/003). Un turno social sí puede terminar preguntando; uno
        # que se contesta con el catálogo, no.
        if (
            (
                presentation_conversation_kind in {"knowledge", "followup"}
                or read_request(objective).intents
                & {INTENT_CAPABILITY, INTENT_REFUSE, INTENT_CONTINUE_CONSTRAINT}
            )
            and visible_reply_is_only_questions(reply_text)
        ):
            raise PlannerContractError("una explicación no puede ser sólo una pregunta")
    else:
        # P may finish before the independent language inference.  Keep L alive
        # through every outer veto, then cancel it only once the final result is
        # known to be non-conversational.  Cancellation closes the local HTTP
        # request and deliberately does not join the discarded decode.
        retire_deferred = getattr(
            llm,
            "retire_deferred_response_language",
            None,
        )
        if callable(retire_deferred):
            retire_deferred(objective)
    # Preguntar por lo que hace o por lo que no hace el producto se contesta
    # con el catálogo; no hay nada que aclarar. Cuando salía por aquí, la
    # pregunta devuelta se construía con vocabulario del planificador: «¿Cuáles
    # son los campos necesarios para crear un recordatorio futuro local y
    # duradero?» ante «cuáles son tus límites aquí» (panel-opus-13/052, /038).
    if decision["mode"] == "clarify" and nothing_to_clarify:
        raise PlannerContractError(
            "una pregunta por las capacidades o los límites no se aclara"
        )
    if decision["mode"] == "clarify" and not _recovery_question_is_valid(
        decision["question"],
        objective,
        history,
    ):
        # The decision already asks for missing information with zero effects.
        # Reword its invalid prose before retrying the whole interpretation:
        # that retry changed a valid clarification into an unsupported request.
        reword = getattr(llm, "clarify_after_turn_failure", None)
        question = (
            reword(
                objective, history=history, timeout=TURN_DECIDE_RECOVERY_BUDGET_SECONDS
            )
            if callable(reword)
            else ""
        )
        if not _recovery_question_is_valid(question, objective, history):
            raise PlannerContractError("aclaración que repite un turno anterior")
        decision = {**decision, "question": question}
        turn_audit["stages"].append(
            _turn_audit_stage("clarification_reworded", decision)
        )
    result = {
        "type": "turn.result",
        "id": message.get("id"),
        "kind": decision["mode"],
        "operation": decision["operation"],
        "intentOperations": intent_operations,
        "effectOperations": decision["effect_operations"],
        "question": decision["question"],
        "reply": reply_text,
    }
    if partial_offer is not None:
        result["objective"] = partial_offer[1]
    if decision["mode"] == "conversation":
        result["conversationKind"] = presentation_conversation_kind
        if (
            (
                stable_no_effect_decision is not None
                and stable_no_effect_decision.get("conversation_kind") == "knowledge"
                and presentation_conversation_kind == "knowledge"
            )
            or read_request(objective).intents
            & {INTENT_IDENTITY, INTENT_CAPABILITY, INTENT_REFUSE}
            # ctx-dueno-06 (2026-09-22, turn 50 after the «sin pedido» guard):
            # a known limit closed for an authoritative request («cierra BAXY»)
            # is a request of its own; resumed onto the earlier clarification it
            # was re-decided as knowledge and «Entendido, cierro BAXY» went out.
            or (
                presentation_conversation_kind == "unsupported"
                and effect_request_is_authoritative(objective)
            )
        ):
            # A closed standalone explanation or negative constraint is a new
            # request, not a value for an earlier clarification. Reuse the
            # existing protocol flag; elliptical fragments retain its default.
            result["preserveObjective"] = False
    if response_language is None and decision["mode"] != "conversation":
        # An action or plan reply also travels with the language the reading
        # decided: the shell confirms a reviewed effect in that language, so
        # the final answer keeps it (CLOSE1219/007, CLOSE1221/007 answered an
        # English close in Spanish after «confirmar»). Deterministic reading
        # only; an undecided language stays absent.
        response_language = _decisive_request_language(objective)
    if response_language in {"es", "en", "mixed"}:
        result["responseLanguage"] = response_language
    turn_audit["final"] = {
        "kind": result["kind"],
        "intent_operations": result["intentOperations"],
        "effect_operations": result["effectOperations"],
    }
    turn_audit["honesty"] = {
        "offered_before_veto": list(effects_before_information_veto),
        "proposed_before_veto": list(effects_before_domain_grounding),
        "visible_text": reply_text or str(decision.get("question") or ""),
    }
    _append_turn_audit(turn_audit)
    return result


def _retry_side_effect_free_turn(
    operation: Callable[[], dict[str, Any]],
    *,
    before_attempt: Callable[[int], None] | None = None,
) -> dict[str, Any]:
    """Retry one transient turn failure without ever executing an effect."""

    last_error: Exception | None = None
    for attempt in range(2):
        try:
            if before_attempt is not None:
                before_attempt(attempt)
            result = dict(operation())
            result["turn_attempts"] = attempt + 1
            return result
        except Exception as error:  # noqa: BLE001 - bounded local recovery
            last_error = error
            # Tandas 5e/6: a limit whose wording failed its contract fails again on the second attempt —
            # the same decision, the same seeded drafts (identical in every measured turn) — after paying
            # the whole cascade once more (3-4 s). The recovery says the limit instead.
            if _turn_failure_kind(error) == LIMIT_WORDING_FAILURE:
                break
    assert last_error is not None
    raise last_error


_RECOVERY_PROMPT_VOCABULARY = (
    "mensaje actual",
    "current message",
    "pedido actual",
    "current request",
    "la frase que",
    "the sentence you",
    "situacion del turno",
)


def _recovery_question_repeats_a_previous_turn(
    question: str,
    history: object,
) -> bool:
    """La pregunta devuelve una petición que la persona ya hizo antes."""

    if not isinstance(history, list) or len(history) < 2:
        return False
    asked = set(re.findall(r"[a-z]{4,}", read_fold(question)))
    if len(asked) < 2:
        return False
    for item in history[:-1]:
        if not isinstance(item, dict) or item.get("role") != "user":
            continue
        previous = set(
            re.findall(r"[a-z]{4,}", read_fold(str(item.get("content") or "")))
        )
        if len(previous) < 2:
            continue
        shared = asked & previous
        if len(shared) >= 2 and len(shared) / len(asked) >= 0.6:
            return True
    return False


def _recovery_question_is_valid(
    value: object,
    objective: str = "",
    history: object = None,
) -> bool:
    """Accept exactly one compact question, never an action-bearing object.

    Además no nombra el vocabulario del encargo ni devuelve una petición
    anterior, que es lo que hacía cuando un turno de conocimiento fallaba.
    """

    if not isinstance(value, str):
        return False
    if not (
        bool(value)
        and len(value) <= 512
        and value == value.strip()
        and "\n" not in value
        and "\r" not in value
        and not any(
            unicodedata.category(character) in {"Cc", "Cs"} for character in value
        )
        and value.endswith("?")
        and value.count("?") == 1
    ):
        return False
    folded = read_fold(value)
    if any(term in folded for term in _RECOVERY_PROMPT_VOCABULARY):
        return False
    _ = objective
    return not _recovery_question_repeats_a_previous_turn(value, history)


def _standalone_deictic_conversation_needs_clarification(
    objective: str,
    decision: dict[str, Any],
    history: object = None,
    pending_clarification: bool | None = None,
) -> bool:
    """Ask for a referent when a bare deictic command lacks a direct action."""

    if decision.get("mode") not in {"conversation", "plan"}:
        return False
    if _deictic_open_request(objective) and _history_has_pending_clarification(
        history, pending_clarification,
    ):
        return False
    return _standalone_deictic_request(objective, history)


def _recover_failed_turn(
    message: dict[str, Any],
    llm: Any | None,
    *,
    attempts: int = 2,
    failure_kinds: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Return a total, fail-closed clarification after two turn failures.

    The semantic recovery receives dialogue only. If local generation is
    unavailable or violates its schema, the protocol keeps the transport alive
    with empty user-facing fields and zero action authority. The shell may make
    one separately bounded ``message.compose`` attempt, but deterministic
    protocol prose must never be presented as model-authored text.
    """

    objective = str(message.get("text", ""))[:2_048]
    history = message.get("history") or []
    failure_code = (
        "turn_contract_failure"
        if failure_kinds and set(failure_kinds) == {"contract"}
        else "turn_unavailable"
        if not failure_kinds
        else "turn_runtime_failure"
    )

    def audited(result: dict[str, Any]) -> dict[str, Any]:
        _append_turn_audit(
            {
                "schema": "baxy.mind-turn-audit.v1",
                "request_id": message.get("id"),
                "phase": "recovery",
                "candidate_operations": [],
                "raw_decision": None,
                "stages": [
                    {
                        "name": "total_recovery",
                        "mode": result.get("kind"),
                        "operation": result.get("operation"),
                        "effect_operations": list(result.get("effectOperations") or []),
                        "effect_verification": "not_applicable",
                    }
                ],
                "final": {
                    "kind": result.get("kind"),
                    "intent_operations": list(result.get("intentOperations") or []),
                    "effect_operations": list(result.get("effectOperations") or []),
                },
                "recovery": {
                    "turn_attempts": result.get("turn_attempts"),
                    "kind": result.get("turn_recovery"),
                    "failure_code": result.get("failure_code"),
                    "failure_kinds": list(failure_kinds),
                },
            }
        )
        return result

    # Un turno fallido no convierte una pregunta por las capacidades o los
    # límites en algo que aclarar: eso se contesta con el catálogo. Devolverla
    # como pregunta era el último sitio por donde salía —«¿Qué específicamente
    # no puedes hacer en este PC?», «¿Qué acción específica te niega la política
    # de seguridad de BAXY?»— (limites-16/003..006).
    # cien-37 030 «send flowers to Deimos»: a place no operation reaches
    # has nothing to clarify either; the question asked for the detail of
    # something that cannot be done at all.
    # Uso real 2026-09-23 «prepárame una taza de café»: the turn had already
    # decided this is something BAXY does not do, and only the wording of that
    # limit failed twice. The recovery keeps the verdict — it says the limit —
    # instead of asking an invented question about coffee.
    is_limit = (
        bool(failure_kinds) and set(failure_kinds) == {LIMIT_WORDING_FAILURE}
    ) or effect_intent.out_of_world_request(objective)
    # tanda-02: an identity answer that failed its wording twice is not turned
    # into a question about the question («¿Te refieres a un lugar geográfico?»).
    nothing_to_clarify = bool(
        read_request(objective).intents
        & {INTENT_IDENTITY, INTENT_CAPABILITY, INTENT_REFUSE, INTENT_CONTINUE_CONSTRAINT}
    ) or is_limit
    if llm is not None:
        try:
            if nothing_to_clarify:
                raise ValueError("capability_question_is_not_clarified")
            question = llm.clarify_after_turn_failure(
                objective,
                history=history,
                timeout=2.5,
            )
            if not _recovery_question_is_valid(question):
                raise ValueError("invalid_recovery_question")
            return audited(
                {
                    "type": "turn.result",
                    "id": message.get("id"),
                    "kind": "clarify",
                    "operation": None,
                    "intentOperations": [],
                    "effectOperations": [],
                    "preserveObjective": False,
                    "question": question,
                    "reply": "",
                    "turn_attempts": max(0, attempts),
                    "turn_recovery": "semantic_clarification",
                    "recovery_attempts": 1,
                    "failure_code": failure_code,
                }
            )
        except Exception:  # noqa: BLE001 - use the protocol safety floor
            pass
        kind, text = _recovery_visible_from_compose(llm, objective, limit=is_limit)
        if kind == "clarify" and not nothing_to_clarify:
            return audited(
                {
                    "type": "turn.result",
                    "id": message.get("id"),
                    "kind": "clarify",
                    "operation": None,
                    "intentOperations": [],
                    "effectOperations": [],
                    "preserveObjective": False,
                    "question": text,
                    "reply": "",
                    "turn_attempts": max(0, attempts),
                    "turn_recovery": "semantic_clarification",
                    "recovery_attempts": 1,
                    "failure_code": failure_code,
                }
            )
        return audited(
            {
                "type": "turn.result",
                "id": message.get("id"),
                "kind": "conversation",
                "operation": None,
                "intentOperations": [],
                "effectOperations": [],
                "preserveObjective": False,
                "question": "",
                # With nothing to clarify, a composed question is not published
                # as the answer either (tanda-02 «¿cuál es tu lugar de origen?»).
                "reply": text if kind == "conversation" else "",
                # cien-38 060 «ship a piano to Charon»: the recovery composed
                # «I can't ship a piano to Charon—that's outside what I do»
                # and the App refused it as looks_like_failure, because the
                # boundary did not travel with the reply, then published its
                # own «I couldn't understand the request properly», which is
                # false. A limit is a limit also when it is recovered.
                "conversationKind": "unsupported" if is_limit else None,
                "turn_attempts": max(0, attempts),
                "turn_recovery": "protocol_fallback",
                "recovery_attempts": 1,
                "failure_code": failure_code,
            }
        )

    return audited(
        {
            "type": "turn.result",
            "id": message.get("id"),
            "kind": "conversation",
            "operation": None,
            "intentOperations": [],
            "effectOperations": [],
            "preserveObjective": False,
            "question": "",
            "reply": "",
            "turn_attempts": max(0, attempts),
            "turn_recovery": "protocol_fallback",
            "recovery_attempts": 0,
            "failure_code": failure_code,
        }
    )


def _recovery_visible_from_compose(
    llm: Any, objective: str, *, limit: bool = False,
) -> tuple[str, str]:
    """Use model-authored recovery text. A question is a question, not silence.

    Returns ``("clarify", question)``, ``("conversation", reply)`` or
    ``("conversation", "")`` when the model produces nothing usable.
    """

    compose = getattr(llm, "compose_user_message", None)
    if not callable(compose):
        return "conversation", ""
    try:
        text = str(
            compose(
                objective,
                # A place no operation reaches, or a limit the turn already
                # decided, is a boundary, not a failed reading: «I couldn't
                # understand the request to send flowers to Deimos» is false.
                # Tanda 3 and 4 2026-09-24: anything else is asked about — the
                # one thing missing to do it —, never answered with «no pude
                # entender bien la solicitud, explícalo de nuevo».
                "error" if limit else "clarification",
                {
                    "situation": json.dumps(
                        {"kind": "failure", "cause": "out_of_catalog", "polarity": "failure"}
                        if limit
                        else {"kind": "clarification", "cause": "ambiguous_request", "polarity": "pending"},
                        ensure_ascii=False,
                    )
                },
            )
            or ""
        ).strip()
    except Exception:  # noqa: BLE001 - empty reply is the honest floor
        return "conversation", ""
    if not text or len(text) > 4_096:
        return "conversation", ""
    if _recovery_question_is_valid(text):
        return "clarify", text
    return "conversation", text


class _SidecarLifecycle:
    """Own sidecar resources and release each one once in dependency order."""

    def __init__(self) -> None:
        self._ownership_lock = threading.Lock()
        self._voice_engine: Any | None = None
        self._voice_cancel_pending = False
        self._llm: Any | None = None
        self._turn_evidence: Any | None = None
        self._planner_promotion_thread: threading.Thread | None = None
        self._planner_promotion_stop: threading.Event | None = None
        self._dispatch_thread: threading.Thread | None = None
        self._router: Any | None = None
        self._closed = False

    def _claim(
        self,
        current: Any | None,
        resource: Any,
        name: str,
    ) -> Any:
        if self._closed:
            raise RuntimeError("sidecar lifecycle is already closed")
        if current is not None:
            raise RuntimeError(f"{name} already has an owner")
        return resource

    def own_voice_engine(self, voice_engine: Any) -> Any:
        ownership_error: RuntimeError | None = None
        cleanup_rejected_candidate = False
        apply_pending_cancel = False
        with self._ownership_lock:
            try:
                self._voice_engine = self._claim(
                    self._voice_engine,
                    voice_engine,
                    "voice engine",
                )
            except RuntimeError as error:
                ownership_error = error
                cleanup_rejected_candidate = self._voice_engine is not voice_engine
            else:
                apply_pending_cancel = self._voice_cancel_pending
                self._voice_cancel_pending = False
        if ownership_error is not None:
            if cleanup_rejected_candidate:
                try:
                    voice_engine.shutdown()
                except BaseException as cleanup_error:
                    _report_secondary_cleanup_failure(cleanup_error)
            raise ownership_error
        if apply_pending_cancel:
            try:
                voice_engine.cancel_speech()
            except Exception as cancel_error:  # noqa: BLE001 - retry by barrier
                _report_deferred_voice_cancel_failure(cancel_error)
        return voice_engine

    def own_llm(self, llm: Any) -> Any:
        with self._ownership_lock:
            self._llm = self._claim(self._llm, llm, "LLM runtime")
        return llm

    def own_turn_evidence(self, turn_evidence: Any) -> Any:
        with self._ownership_lock:
            self._turn_evidence = self._claim(
                self._turn_evidence,
                turn_evidence,
                "turn evidence service",
            )
        return turn_evidence

    def own_planner_promotion(
        self,
        thread: threading.Thread,
        stop_event: threading.Event,
    ) -> threading.Thread:
        with self._ownership_lock:
            self._planner_promotion_thread = self._claim(
                self._planner_promotion_thread,
                thread,
                "planner promotion thread",
            )
            self._planner_promotion_stop = self._claim(
                self._planner_promotion_stop,
                stop_event,
                "planner promotion stop event",
            )
        return thread

    def own_dispatch_thread(
        self,
        thread: threading.Thread,
    ) -> threading.Thread:
        with self._ownership_lock:
            self._dispatch_thread = self._claim(
                self._dispatch_thread,
                thread,
                "request dispatch thread",
            )
        return thread

    def own_router(self, router: Any) -> Any:
        with self._ownership_lock:
            self._router = self._claim(
                self._router,
                router,
                "intent router",
            )
        return router

    def request_voice_cancel(
        self,
        *,
        defer_if_unowned: bool,
    ) -> bool:
        """Cancel owned TTS or record one intent for lazy voice ownership."""

        with self._ownership_lock:
            if self._closed:
                return False
            voice_engine = self._voice_engine
            if voice_engine is None and defer_if_unowned:
                self._voice_cancel_pending = True
                return True
        if voice_engine is None:
            return False
        voice_engine.cancel_speech()
        return True

    def close(self) -> None:
        with self._ownership_lock:
            if self._closed:
                return
            self._closed = True
            self._voice_cancel_pending = False

        cleanup_errors: list[BaseException] = []

        def attempt(callback: Callable[[], Any]) -> tuple[bool, Any]:
            try:
                return True, callback()
            except BaseException as error:  # noqa: BLE001 - finish teardown
                cleanup_errors.append(error)
                return False, None

        def observed_reap_status(
            attempt_succeeded: bool,
            resource_stopped: bool,
        ) -> ReapStatus:
            if resource_stopped:
                return ReapStatus.REAPED
            return ReapStatus.TIMED_OUT if attempt_succeeded else ReapStatus.FAILED

        if self._planner_promotion_stop is not None:
            self._planner_promotion_stop.set()
        evidence_stopped = True
        evidence_reap_status = ReapStatus.ABSENT
        if self._turn_evidence is not None:
            ok, result = attempt(lambda: self._turn_evidence.stop(timeout=0.0))
            evidence_stopped = ok and bool(result)
            evidence_reap_status = observed_reap_status(
                ok,
                evidence_stopped,
            )

        voice_shutdown_errors: list[BaseException] = []
        voice_shutdown_thread: threading.Thread | None = None
        voice_shutdown_error_collected = False
        voice_shutdown_started = False
        voice_stopped = True
        voice_reap_status = ReapStatus.ABSENT
        voice_engine = self._voice_engine

        def shutdown_voice() -> None:
            try:
                voice_engine.shutdown()
            except BaseException as error:  # noqa: BLE001 - relay to owner
                voice_shutdown_errors.append(error)

        def collect_voice_shutdown_error() -> None:
            nonlocal voice_shutdown_error_collected, voice_reap_status
            if (
                voice_shutdown_error_collected
                or not voice_stopped
                or not voice_shutdown_errors
            ):
                return
            voice_shutdown_error_collected = True
            voice_reap_status = ReapStatus.FAILED
            cleanup_errors.append(voice_shutdown_errors[0])

        if voice_engine is not None:
            voice_shutdown_thread = threading.Thread(
                target=shutdown_voice,
                name="baxy-voice-shutdown",
                daemon=True,
            )
            ok, _ = attempt(voice_shutdown_thread.start)
            voice_shutdown_started = ok
            if ok:
                ok, _ = attempt(
                    lambda: voice_shutdown_thread.join(
                        timeout=BACKGROUND_WORKER_JOIN_TIMEOUT_SECONDS,
                    )
                )
                voice_stopped = not voice_shutdown_thread.is_alive()
                voice_reap_status = observed_reap_status(
                    ok,
                    voice_stopped,
                )
                collect_voice_shutdown_error()
            else:
                voice_stopped = False
                voice_reap_status = ReapStatus.FAILED
        if self._llm is not None:
            attempt(self._llm.close)

        if self._turn_evidence is not None:
            ok, result = attempt(
                lambda: self._turn_evidence.stop(
                    timeout=BACKGROUND_WORKER_JOIN_TIMEOUT_SECONDS,
                )
            )
            evidence_stopped = ok and bool(result)
            evidence_reap_status = observed_reap_status(
                ok,
                evidence_stopped,
            )

        planner_stopped = True
        planner_reap_status = ReapStatus.ABSENT
        planner_thread = self._planner_promotion_thread
        if (
            planner_thread is not None
            and planner_thread is not threading.current_thread()
            and planner_thread.is_alive()
        ):
            ok, _ = attempt(
                lambda: planner_thread.join(
                    timeout=BACKGROUND_WORKER_JOIN_TIMEOUT_SECONDS,
                )
            )
            planner_stopped = not planner_thread.is_alive()
            planner_reap_status = observed_reap_status(
                ok,
                planner_stopped,
            )
        elif planner_thread is not None:
            planner_stopped = not planner_thread.is_alive()
            planner_reap_status = (
                ReapStatus.REAPED if planner_stopped else ReapStatus.TIMED_OUT
            )

        dispatch_stopped = True
        dispatch_reap_status = ReapStatus.ABSENT
        dispatch_thread = self._dispatch_thread
        if (
            dispatch_thread is not None
            and dispatch_thread is not threading.current_thread()
            and dispatch_thread.is_alive()
        ):
            ok, _ = attempt(
                lambda: dispatch_thread.join(
                    timeout=BACKGROUND_WORKER_JOIN_TIMEOUT_SECONDS,
                )
            )
            dispatch_stopped = not dispatch_thread.is_alive()
            dispatch_reap_status = observed_reap_status(
                ok,
                dispatch_stopped,
            )
        elif dispatch_thread is not None:
            dispatch_stopped = not dispatch_thread.is_alive()
            dispatch_reap_status = (
                ReapStatus.REAPED if dispatch_stopped else ReapStatus.TIMED_OUT
            )

        # Normal shutdown remains graceful when the optional workers observed
        # their stop signals. If a worker is still inside model/encoder I/O,
        # abort the transport without waiting for its serialized request lock.
        if self._router is not None and (
            not evidence_stopped or not planner_stopped or not dispatch_stopped
        ):
            request_close = getattr(self._router, "request_close", None)
            if callable(request_close):
                attempt(request_close)
            if self._turn_evidence is not None and not evidence_stopped:
                ok, result = attempt(
                    lambda: self._turn_evidence.stop(
                        timeout=BACKGROUND_WORKER_ABORT_JOIN_SECONDS,
                    )
                )
                evidence_stopped = ok and bool(result)
                evidence_reap_status = observed_reap_status(
                    ok,
                    evidence_stopped,
                )
            if (
                planner_thread is not None
                and planner_thread is not threading.current_thread()
                and planner_thread.is_alive()
            ):
                ok, _ = attempt(
                    lambda: planner_thread.join(
                        timeout=BACKGROUND_WORKER_ABORT_JOIN_SECONDS,
                    )
                )
                planner_stopped = not planner_thread.is_alive()
                planner_reap_status = observed_reap_status(
                    ok,
                    planner_stopped,
                )
            if (
                dispatch_thread is not None
                and dispatch_thread is not threading.current_thread()
                and dispatch_thread.is_alive()
            ):
                ok, _ = attempt(
                    lambda: dispatch_thread.join(
                        timeout=BACKGROUND_WORKER_ABORT_JOIN_SECONDS,
                    )
                )
                dispatch_stopped = not dispatch_thread.is_alive()
                dispatch_reap_status = observed_reap_status(
                    ok,
                    dispatch_stopped,
                )

        if (
            voice_shutdown_thread is not None
            and voice_shutdown_started
            and voice_shutdown_thread.is_alive()
        ):
            ok, _ = attempt(
                lambda: voice_shutdown_thread.join(
                    timeout=BACKGROUND_WORKER_ABORT_JOIN_SECONDS,
                )
            )
            voice_stopped = not voice_shutdown_thread.is_alive()
            voice_reap_status = observed_reap_status(
                ok,
                voice_stopped,
            )
            collect_voice_shutdown_error()

        if self._router is not None:
            attempt(self._router.close)

        if self._turn_evidence is not None and not evidence_stopped:
            ok, result = attempt(lambda: self._turn_evidence.stop(timeout=0.0))
            evidence_stopped = ok and bool(result)
            evidence_reap_status = observed_reap_status(
                ok,
                evidence_stopped,
            )
        if (
            planner_thread is not None
            and planner_thread is not threading.current_thread()
        ):
            planner_stopped = not planner_thread.is_alive()
            if planner_stopped:
                planner_reap_status = ReapStatus.REAPED
        if (
            dispatch_thread is not None
            and dispatch_thread is not threading.current_thread()
        ):
            dispatch_stopped = not dispatch_thread.is_alive()
            if dispatch_stopped:
                dispatch_reap_status = ReapStatus.REAPED
        if voice_shutdown_thread is not None and voice_shutdown_started:
            voice_stopped = not voice_shutdown_thread.is_alive()
            if voice_stopped and voice_reap_status is not ReapStatus.FAILED:
                voice_reap_status = ReapStatus.REAPED
            collect_voice_shutdown_error()

        report_incomplete_reap(
            ReapResource.TURN_EVIDENCE_THREAD,
            evidence_reap_status,
        )
        report_incomplete_reap(
            ReapResource.PLANNER_PROMOTION_THREAD,
            planner_reap_status,
        )
        report_incomplete_reap(
            ReapResource.REQUEST_DISPATCH_THREAD,
            dispatch_reap_status,
        )
        report_incomplete_reap(
            ReapResource.VOICE_ENGINE_SHUTDOWN,
            voice_reap_status,
        )

        if cleanup_errors:
            raise cleanup_errors[0]


def _run_sidecar(
    lifecycle: _SidecarLifecycle,
    *,
    read_message: Callable[[], dict[str, Any] | None] | None = None,
    write_message: Callable[[dict], Any] | None = None,
    request_finished: Callable[[dict[str, Any]], None] | None = None,
) -> int:
    read_message = read_message or protocol.read_message
    write_message = write_message or _write
    models = {"router": "intfloat/multilingual-e5-small"}
    llm = None
    if os.environ.get("BAXY_MIND_LLM_GGUF"):
        llm = lifecycle.own_llm(LlmRuntime())
        llm.start_warmup()
        models["llm"] = Path(os.environ["BAXY_MIND_LLM_GGUF"]).name
    router = lifecycle.own_router(ProcessIntentRouter())
    interactive_encoder = RequestBudgetEncoder(router)
    background_encoder = RequestBudgetEncoder(
        router,
        offline_timeout=BACKGROUND_ENCODER_TIMEOUT_SECONDS,
    )
    tools: list[dict] = []
    tool_by_name: dict[str, dict] = {}
    application_names: tuple[str, ...] = ()
    application_catalog = build_application_catalog_index(application_names)
    game_entries: tuple[tuple[str, str, str], ...] = ()
    game_catalog = build_game_catalog_index(game_entries)
    # What the conversation left for the next follow-up (tanda 7/8): the last turn's request, told by turn.decide,
    # and the facts of verified results, told by message.compose.
    dialogue_state = dialogue_slot.DialogueState()
    planner_catalog = None
    skill_registry = None
    planner_resources_lock = threading.Lock()
    planner_promotion_stop = threading.Event()
    planner_promotion_thread: threading.Thread | None = None
    turn_evidence = lifecycle.own_turn_evidence(TurnEvidenceService())
    voice_engine = None

    def ready_planner_catalog() -> PlannerCatalog:
        with planner_resources_lock:
            current = planner_catalog
        if current is None:
            raise PlannerContractError("the plannable catalog is not available")
        return current

    def promote_planner_resources() -> None:
        """Add E5 retrieval only after its optional corpus build leaves the path."""

        nonlocal planner_catalog, skill_registry

        def promotion_encoder(texts: Any, *, prefix: str = "query") -> Any:
            if planner_promotion_stop.is_set():
                raise RuntimeError("planner promotion was cancelled")
            encoded = background_encoder(texts, prefix=prefix)
            if planner_promotion_stop.is_set():
                raise RuntimeError("planner promotion was cancelled")
            return encoded

        deadline = time.monotonic() + 185.0
        while turn_evidence.state == "building" and time.monotonic() < deadline:
            if planner_promotion_stop.wait(timeout=0.1):
                return
        if planner_promotion_stop.is_set():
            return
        # The worker spawns 3 s after start and needs ~11 s to load E5. Polling
        # it for 0.5 s and giving up left the catalogue lexical for the entire
        # process: measured end to end on the fresh paraphrase corpus of goal
        # 03, retrieval offered the expected operation in 73/124 turns that way
        # and in 102/124 once the promotion actually lands. This thread is a
        # daemon with its own deadline; waiting here costs no turn, because
        # every turn until the swap keeps using the lexical snapshot already
        # published.
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            if router.try_ready(min(1.0, remaining)):
                break
            # A permanently failed worker answers instantly, so the wait has to
            # live here and not inside try_ready.
            if planner_promotion_stop.wait(timeout=0.5):
                return
        else:
            return
        if planner_promotion_stop.is_set():
            return
        try:
            promoted_catalog, promoted_skills = _create_planner_resources(
                tools,
                promotion_encoder,
            )
        except Exception:  # noqa: BLE001 - lexical resources remain available
            return
        if planner_promotion_stop.is_set():
            return
        with planner_resources_lock:
            planner_catalog = promoted_catalog
            skill_registry = promoted_skills

    write_message(protocol.hello(models))

    while True:
        try:
            message = read_message()
        except protocol.ProtocolViolation as violation:
            write_message(protocol.error_reply(None, violation.code, violation.detail))
            return 65
        if message is None:
            break
        if not message:
            if request_finished is not None:
                request_finished(message)
            continue
        request_id = message.get("id")
        kind = message.get("type")
        internal_replay = isinstance(message, _AcknowledgedVoiceCancel)

        def write_request_message(reply: dict) -> Any:
            if internal_replay:
                return False
            return write_message(reply)

        # Open from the request's arrival until its result is written (finally below).
        request_signal = PendingTurnSignal(write_request_message)
        interactive_request = str(kind) in {"turn.decide", "plan"}
        owns_llm_request_scope = llm is not None and not internal_replay
        llm_scope_attempted = False
        encoder_scope_attempted = False
        try:
            if owns_llm_request_scope:
                compose_budget = 3.25
                if kind == "message.compose":
                    compose_budget = _message_composition_budget(
                        message.get("budgetSeconds", 3.25)
                    )
                request_budget = {
                    "catalog.configure": CATALOG_REQUEST_BUDGET_SECONDS,
                    "arguments": ARGUMENT_REQUEST_BUDGET_SECONDS,
                    # Turn inference is side-effect-free and has one bounded retry.
                    # Normal attempts share 17 s; a separate 2.5 s fail-closed
                    # recovery leaves 2.5 s for scheduling and JSONL delivery
                    # below the 22 s desktop transport SLA.
                    "turn.decide": TURN_DECIDE_NORMAL_BUDGET_SECONDS,
                    "plan.ground": 28.0,
                    "plan": 55.0,
                    "narrate": 18.0,
                    "message.compose": compose_budget,
                }.get(str(kind), 55.0)
                llm_scope_attempted = True
                llm.begin_request(
                    request_budget,
                    identity=str(request_id or ""),
                )
            if interactive_request:
                encoder_scope_attempted = True
                interactive_encoder.begin_request(
                    (
                        TURN_DECIDE_NORMAL_BUDGET_SECONDS
                        if kind == "turn.decide"
                        else 55.0
                    )
                )
        except BaseException:
            try:
                _finish_request_scope(
                    interactive_encoder=interactive_encoder,
                    llm=llm,
                    encoder_scope_attempted=encoder_scope_attempted,
                    llm_scope_attempted=llm_scope_attempted,
                    request_finished=request_finished,
                    message=message,
                )
            except BaseException as cleanup_error:
                _report_secondary_cleanup_failure(cleanup_error)
            raise
        try:
            if kind == "catalog.configure":
                if tools:
                    raise PlannerContractError("el catálogo ya fue configurado")
                tools = configure_tools(message.get("capabilities"))
                application_names = configure_application_catalog(
                    message.get("applicationCatalog")
                )
                application_catalog = build_application_catalog_index(
                    application_names,
                )
                game_entries = configure_game_catalog(message.get("gameCatalog"))
                game_catalog = build_game_catalog_index(game_entries)
                tool_by_name = {
                    tool["function"]["canonical_name"]: tool for tool in tools
                }
                # Publish a complete lexical snapshot synchronously. E5 is an
                # optional ranking improvement and must never make the first
                # user turn wait for the router or the corpus cache.
                lexical_catalog, lexical_skills = _create_planner_resources(tools)
                with planner_resources_lock:
                    planner_catalog = lexical_catalog
                    skill_registry = lexical_skills
                # Corpus embeddings are advisory and build in the background.
                # They must never delay the ready handshake or become a
                # prerequisite for an otherwise valid local turn.
                turn_evidence.start(
                    background_encoder,
                    lambda: router.try_ready(0.5),
                )
                planner_promotion_thread = threading.Thread(
                    target=promote_planner_resources,
                    name="baxy-planner-e5-promotion",
                    daemon=True,
                )
                lifecycle.own_planner_promotion(
                    planner_promotion_thread,
                    planner_promotion_stop,
                )
                planner_promotion_thread.start()
                if llm is not None:
                    # A catalog-ready reply promises that the optional model
                    # can serve the next turn.  CPU-only cold starts can take
                    # longer than 45 seconds; 90 seconds remains inside the
                    # shell's 120-second authenticated handshake boundary.
                    _require_catalog_llm_ready(llm)
                write_request_message(
                    {
                        "type": "catalog.ready",
                        "id": request_id,
                        "count": len(tools),
                    }
                )
            elif kind == "turn.evidence.status":
                write_request_message(
                    {
                        "type": "turn.evidence.status.result",
                        "id": request_id,
                        **turn_evidence.diagnostics,
                    }
                )
            elif kind in {
                "voice.start",
                "voice.stop",
                "voice.status",
                "voice.speak",
                "voice.cancel",
            }:
                if voice_engine is None:
                    voice_engine = lifecycle.own_voice_engine(
                        VoiceEngine(
                            lambda text: write_message(
                                {"type": "voice.transcript", "text": text}
                            ),
                            lambda event: write_message(
                                {"type": "voice.event", **event}
                            ),
                            correction_terms=catalog_correction_terms(tools),
                        )
                    )
                if kind == "voice.start":
                    mode = str(message.get("mode") or "direct")
                    voice_engine.start(mode)
                    write_request_message(
                        {
                            "type": "voice.started",
                            "id": request_id,
                            "mode": voice_engine.mode,
                            "status": voice_engine.status(),
                        }
                    )
                elif kind == "voice.stop":
                    voice_engine.stop()
                    write_request_message({"type": "voice.stopped", "id": request_id})
                elif kind == "voice.status":
                    write_request_message(
                        {
                            "type": "voice.status.result",
                            "id": request_id,
                            "status": voice_engine.status(),
                        }
                    )
                elif kind == "voice.speak":
                    accepted = voice_engine.speak(str(message.get("text") or ""))
                    write_request_message(
                        {
                            "type": "voice.speak.result",
                            "id": request_id,
                            "accepted": accepted,
                        }
                    )
                else:
                    voice_engine.cancel_speech()
                    write_request_message({"type": "voice.cancelled", "id": request_id})
            elif kind == "shutdown":
                write_request_message({"type": "shutdown.ack", "id": request_id})
                break
            elif kind == "turn.decide":
                turn_failure_kinds: list[str] = []
                if llm is None:
                    turn_result = _recover_failed_turn(
                        message,
                        None,
                        attempts=0,
                    )
                    write_request_message(turn_result)
                    continue
                try:
                    planner_catalog = ready_planner_catalog()
                except Exception:  # noqa: BLE001 - total turn UX boundary
                    llm.begin_request(
                        TURN_DECIDE_RECOVERY_BUDGET_SECONDS,
                        attempt=2,
                    )
                    turn_result = _recover_failed_turn(
                        message,
                        llm,
                        attempts=0,
                        failure_kinds=("runtime",),
                    )
                    write_request_message(turn_result)
                    continue

                if not dialogue_slot.read_slot({}, message.get("history") or [], str(message.get("text", ""))).antecedents:
                    # A conversation's first message: nothing verified before it belongs to it.
                    dialogue_state.reset()

                def prepare_turn() -> dict[str, Any]:
                    try:
                        return _prepare_turn_result(
                            message,
                            llm=llm,
                            planner_catalog=planner_catalog,
                            turn_evidence=turn_evidence,
                            encoder=interactive_encoder,
                            tool_by_name=tool_by_name,
                            application_names=application_catalog,
                            game_catalog=game_catalog,
                            on_signal=request_signal,
                            dialogue_state=dialogue_state,
                        )
                    except PlannerContractError as error:
                        turn_failure_kinds.append("contract")
                        _audit_turn_attempt_failure(message, error, "contract")
                        raise
                    except Exception as error:  # noqa: BLE001 - stable telemetry only
                        failure_kind = _turn_failure_kind(error)
                        turn_failure_kinds.append(failure_kind)
                        _audit_turn_attempt_failure(message, error, failure_kind)
                        raise

                try:
                    turn_result = _retry_side_effect_free_turn(
                        prepare_turn,
                        before_attempt=lambda attempt: llm.begin_request_attempt(
                            TURN_DECIDE_ATTEMPT_BUDGET_SECONDS,
                            attempt=attempt,
                        ),
                    )
                except Exception:  # noqa: BLE001 - fail-closed clarification
                    llm.begin_request(
                        TURN_DECIDE_RECOVERY_BUDGET_SECONDS,
                        attempt=2,
                    )
                    turn_result = _recover_failed_turn(
                        message,
                        llm,
                        # One attempt when a limit's wording failed (it is not retried).
                        attempts=len(turn_failure_kinds) or 2,
                        failure_kinds=tuple(turn_failure_kinds),
                    )
                # The request this turn decided is the last one now; its operations (the effects, or those a
                # question is about) wait for their verified results (message.compose).
                dialogue_state.expect(
                    turn_result.get("objective") or message.get("text", ""),
                    turn_result.get("effectOperations") or turn_result.get("intentOperations"),
                )
                write_request_message(turn_result)
            elif kind == "plan":
                if llm is None:
                    raise RuntimeError("LLM no disponible")
                objective = str(message.get("text", ""))
                planner_catalog = ready_planner_catalog()
                history = message.get("history") or []
                raw_expected_operations = message.get("expectedOperations")
                expected_operations: tuple[str, ...] = ()
                if raw_expected_operations is not None:
                    if (
                        not isinstance(raw_expected_operations, list)
                        or not 1 <= len(raw_expected_operations) <= 8
                        or any(
                            not isinstance(operation, str)
                            or planner_catalog.get(operation) is None
                            for operation in raw_expected_operations
                        )
                    ):
                        raise PlannerContractError(
                            "los efectos esperados del turno son inválidos"
                        )
                    expected_operations = tuple(raw_expected_operations)
                recognized_expected = (
                    resolve_explicit_effects(
                        objective,
                        (tool.name for tool in planner_catalog.tools),
                        application_catalog,
                        game_catalog,
                        previous_user_text=_previous_user_request(history, objective),
                    )
                    if expected_operations
                    else None
                )
                if (
                    recognized_expected is None
                    and expected_operations == ("wifi.radio.set", "wifi.scan")
                ):
                    # NETWORK1737 «qué redes wifi hay» → «la radio está apagada,
                    # ¿la enciendo y busco redes?» → «sí»: the answer alone names no
                    # effect; the accepted offer (read from the history the App
                    # sends) is the evidence of both steps, so the radio state is
                    # grounded from it instead of being asked again.
                    recognized_expected = effect_intent.accepted_wifi_offer(
                        objective,
                        history,
                        (tool.name for tool in planner_catalog.tools),
                    )
                expected_evidence = (
                    (objective,)
                    if len(expected_operations) == 1
                    else _restore_evidence_surfaces(
                        objective,
                        recognized_expected.evidence,
                    )
                    if recognized_expected is not None
                    and recognized_expected.operations == expected_operations
                    else ()
                )
                expected_plan_operations = tuple(
                    operation
                    for operation, _ in _expand_effect_plan(
                        expected_operations,
                        expected_evidence,
                    )
                )
                shortlist, skill_guidance = _prepare_plan_prompt_resources(
                    objective,
                    expected_plan_operations,
                    planner_catalog,
                    skill_registry,
                )
                if not expected_operations:
                    _emit_early_turn_signal(
                        path=PATH_MODEL,
                        objective=objective,
                        request_id=request_id,
                        on_signal=request_signal,
                        already_signaled=[],
                        llm=llm,
                        phase="preparing_steps",
                    )
                recovery_contract = message.get("recovery")
                if (
                    not expected_operations
                    and isinstance(recovery_contract, dict)
                    and recovery_contract.get("errorCode") in _NO_REPLAN_ERROR_CODES
                ):
                    # REOPEN1957 H0170/H0376: the failed step already carries the
                    # question for the person (which saved network is the home
                    # one); repeating the same step cannot answer it.
                    raw = {"kind": "conversation", "question": "", "steps": []}
                else:
                    raw = (
                    _explicit_plan_skeleton(
                        expected_operations,
                        expected_evidence,
                    )
                    if expected_operations
                    else llm.propose_plan_skeleton(
                        objective,
                        planner_catalog.compact_prompt(shortlist),
                        [tool.name for tool in shortlist],
                        skill_guidance,
                        history=history,
                        recovery=message.get("recovery"),
                    )
                    )
                proposal = validate_skeleton(
                    raw,
                    planner_catalog,
                    shortlist,
                    objective,
                )
                if (
                    not expected_operations
                    and proposal.kind == "plan"
                    and len(proposal.steps) > 1
                ):
                    # Una sola revisión acotada sustituye el antiguo voto de
                    # dos o tres generaciones completas. La propuesta y la
                    # revisión atraviesan el mismo contrato determinista; una
                    # tercera muestra no aporta autoridad ni evidencia y
                    # multiplicaba la latencia de cada misión compuesta.
                    refined = llm.refine_plan_skeleton(
                        objective,
                        planner_catalog.compact_prompt(shortlist),
                        [tool.name for tool in shortlist],
                        proposal.as_dict(),
                        skill_guidance,
                    )
                    proposal = validate_skeleton(
                        refined,
                        planner_catalog,
                        shortlist,
                        objective,
                    )
                if (
                    expected_operations
                    and tuple(step.operation for step in proposal.steps)
                    != expected_plan_operations
                ):
                    raise PlannerContractError(
                        "el plan perdió efectos ya reconocidos por el turno"
                    )
                irrelevant = _irrelevant_plan_operations(
                    proposal,
                    objective,
                    planner_catalog,
                    expected_operations,
                )
                if irrelevant:
                    raise PlannerContractError(
                        "el plan contiene operaciones sin evidencia semántica suficiente: "
                        + ", ".join(irrelevant)
                    )
                arguments_by_step: dict[str, dict] = {}
                argument_requests: list[dict] = []
                enumerated_note_arguments = _fully_enumerated_note_create_arguments(
                    objective
                )
                note_create_steps = tuple(
                    step for step in proposal.steps if step.operation == "note.create"
                )
                note_arguments_by_step = (
                    {
                        step.step_id: arguments
                        for step, arguments in zip(
                            note_create_steps,
                            enumerated_note_arguments,
                            strict=True,
                        )
                    }
                    if enumerated_note_arguments
                    and len(note_create_steps) == len(enumerated_note_arguments)
                    else {}
                )
                for step in proposal.steps:
                    if step.arguments_mode != "literal":
                        continue
                    tool = tool_by_name.get(step.operation)
                    if tool is None:
                        raise PlannerContractError(
                            f"tool desconocida al materializar {step.step_id}"
                        )
                    schema = tool["function"]["parameters"]
                    if schema.get("properties") == {}:
                        arguments_by_step[step.step_id] = {}
                        continue
                    enumerated_arguments = note_arguments_by_step.get(step.step_id)
                    if enumerated_arguments is not None:
                        grounded, _ = normalize_objective_arguments(
                            enumerated_arguments,
                            schema,
                            objective,
                        )
                        if grounded is not None:
                            grounded = _normalize_grounded_operation_arguments(
                                step.operation,
                                grounded,
                                objective,
                            )
                        if grounded is None or not validate_json_schema_instance(
                            grounded, schema
                        ):
                            raise PlannerContractError(
                                "la lista enumerada de notas no valida contra el catálogo"
                            )
                        arguments_by_step[step.step_id] = grounded
                        continue
                    if expected_operations:
                        explicit_arguments = _ground_explicit_arguments(
                            step.operation,
                            step.purpose,
                            schema,
                            application_names,
                            game_catalog,
                        )
                        if explicit_arguments is not None:
                            arguments_by_step[step.step_id] = explicit_arguments
                            continue
                        if step.operation == "document.presentation.create":
                            # REOPEN1957 H0188: the local model writes the slides.
                            authored = _presentation_arguments(llm, step.purpose)
                            if authored is not None and validate_json_schema_instance(authored, schema):
                                arguments_by_step[step.step_id] = authored
                                continue
                    argument_requests.append(
                        {
                            "id": step.step_id,
                            "operation": step.operation,
                            "purpose": step.purpose,
                            "tool": tool,
                        }
                    )

                extracted_arguments = (
                    llm.extract_plan_arguments_batch(objective, argument_requests)
                    if argument_requests
                    else {}
                )
                for request in argument_requests:
                    step_id = request["id"]
                    tool = request["tool"]
                    schema = tool["function"]["parameters"]
                    arguments = extracted_arguments.get(step_id)
                    grounded, fields = normalize_objective_arguments(
                        arguments,
                        schema,
                        objective,
                    )
                    if grounded is not None:
                        grounded = _normalize_grounded_operation_arguments(
                            str(request["operation"]),
                            grounded,
                            objective,
                        )
                        if grounded is None and "dueUtc" in schema.get("required", []):
                            fields = ("dueUtc",)
                    if grounded is None:
                        raise PlannerClarification(
                            llm.formulate_missing_argument_question(
                                objective,
                                str(request["purpose"]),
                                tool,
                                fields,
                            )
                        )
                    arguments_by_step[step_id] = grounded
                proposal = attach_arguments(
                    proposal,
                    arguments_by_step,
                    planner_catalog,
                )
                write_request_message(
                    {
                        "type": "plan.result",
                        "id": request_id,
                        **proposal.as_dict(),
                    }
                )
            elif kind == "plan.ground":
                if llm is None:
                    raise RuntimeError("LLM no disponible")
                operation = str(message.get("operation", ""))
                tool = tool_by_name.get(operation)
                if tool is None or operation.startswith("memory."):
                    raise ValueError(f"tool no groundeable: {operation}")
                objective = str(message.get("objective", ""))
                observations = message.get("observations") or []
                arguments = (
                    (
                        _verified_message_send_arguments(objective, observations)
                        if operation == "message.send"
                        else None
                    )
                    or _verified_dependency_identity_arguments(
                        operation,
                        objective,
                        observations,
                        tool,
                        application_names,
                        game_catalog,
                    )
                    or llm.ground_plan_arguments(
                        objective,
                        str(message.get("purpose", "")),
                        observations,
                        tool,
                    )
                )
                schema = tool["function"]["parameters"]
                if not validate_json_schema_instance(arguments, schema):
                    raise PlannerContractError("argumentos groundeados inválidos")
                grounding_source = trusted_plan_grounding_source(
                    objective,
                    observations,
                )
                grounded = normalize_grounded_arguments(
                    arguments,
                    schema,
                    grounding_source,
                )
                if grounded is None:
                    raise PlannerContractError(
                        "argumentos groundeados sin evidencia confiable"
                    )
                arguments = _normalize_grounded_operation_arguments(
                    operation,
                    grounded,
                    objective,
                )
                if arguments is None or not validate_json_schema_instance(
                    arguments, schema
                ):
                    raise PlannerContractError(
                        "argumentos groundeados semánticamente inválidos"
                    )
                write_request_message(
                    {
                        "type": "plan.ground.result",
                        "id": request_id,
                        "operation": operation,
                        "arguments": arguments,
                    }
                )
            elif kind == "arguments":
                if llm is None:
                    raise RuntimeError("LLM no disponible")
                operation = str(message.get("operation", ""))
                tool = tool_by_name.get(operation)
                if tool is None:
                    raise ValueError(f"tool desconocida: {operation}")
                objective = _with_session_alarm_selector(
                    str(message.get("text", "")), message.get("history"),
                )
                arguments = _ground_explicit_arguments(
                    operation,
                    objective,
                    tool["function"]["parameters"],
                    application_names,
                    game_catalog,
                    history=message.get("history"),
                )
                question = ""
                if arguments is None:
                    extraction = llm.extract_direct_arguments(
                        objective,
                        tool,
                        stated_fields=_stated_argument_fields(
                            operation, objective, tool["function"]["parameters"],
                        ),
                    )
                    arguments, question = prepare_direct_argument_result(
                        llm,
                        objective,
                        tool,
                        extraction.arguments,
                        extraction.fallback_question,
                    )
                write_request_message(
                    {
                        "type": "arguments.result",
                        "id": request_id,
                        "operation": operation,
                        "arguments": arguments,
                        "ok": arguments is not None,
                        "question": question,
                    }
                )
            elif kind == "narrate":
                if llm is None:
                    raise RuntimeError("LLM no disponible")
                text = llm.narrate(
                    str(message.get("userText", "")),
                    str(message.get("operation", "")),
                    message.get("outcome") or {},
                )
                write_request_message(
                    {
                        "type": "narrate.result",
                        "id": request_id,
                        "text": text,
                    }
                )
            elif kind == "message.compose":
                if llm is None:
                    raise RuntimeError("LLM no disponible")
                facts = message.get("facts")
                if not isinstance(facts, dict):
                    raise ValueError("facts debe ser un objeto")
                # Una respuesta de capacidades describe el catálogo servido
                # hoy, no una lista fija elegida para el corpus.
                facts = {
                    **facts,
                    "capabilities": served_capability_families(
                        [tool["function"]["canonical_name"] for tool in tools]
                    ),
                }
                situation = _situation_from_facts(facts)
                # Only a verified result of the operation the last turn decided is kept for the next follow-up,
                # and a result of it answers the request as the turn understood it (tanda 7b «¿y el finde?»).
                dialogue_state.record(situation)
                user_text = dialogue_state.understood(str(message.get("userText", "")), situation)[:4096]
                observed = _merged_observed(situation)
                opening_name = effect_intent.unresolved_application_open_name(
                    user_text, application_names,
                ) if situation.get("operation") == "app.installed" else None
                approximate_identity = False
                if (
                    opening_name is not None
                    and situation.get("verified") is True
                    and situation.get("succeeded") is True
                ):
                    if observed.get("requestedName") != opening_name:
                        raise ValueError("application lookup result does not bind the request")
                    candidate_name = observed.get("displayName")
                    approximate_identity = (
                        observed.get("installed") is True
                        and isinstance(candidate_name, str)
                        and effect_intent._application_name_key(candidate_name)
                        != effect_intent._application_name_key(opening_name)
                    )
                if approximate_identity:
                    # A presence read may suggest a different catalog name.
                    # Ask about identity without treating that suggestion as
                    # an authorized destination or adding an opening step.
                    text = llm.formulate_missing_argument_question(
                        user_text,
                        "Clarify application identity, not opening permission. "
                        "No opening occurred. This verified presence candidate "
                        "differs from the name in the original request: "
                        + json.dumps(
                            {"displayName": candidate_name},
                            ensure_ascii=False,
                        ),
                        tool_by_name["app.open"],
                        ("appId",),
                    )
                    if not _recovery_question_is_valid(text, user_text):
                        raise ValueError("invalid application identity question")
                    if not text:
                        raise RuntimeError("respuesta vacía")
                    reply = {"type": "message.compose.result", "id": request_id}
                else:
                    try:
                        text = llm.compose_user_message(
                            user_text,
                            str(message.get("intent", "status"))[:32],
                            facts,
                        )
                    except TimeoutError:
                        # The budget ran out before a draft was accepted: that
                        # is the writer's answer, not a lost request. The shell
                        # repeats only what the mind never answered.
                        text = ""
                    reply = {
                        "type": "message.compose.result",
                        "id": request_id,
                        "reproducible": llm.composition_is_reproducible(facts),
                    }
                write_request_message({**reply, "text": text[:4096]})
            else:
                write_request_message(
                    protocol.error_reply(
                        request_id,
                        "unknown_request",
                        f"type={kind}",
                    )
                )
        except PlannerClarification as error:
            if kind == "turn.decide":
                write_request_message(
                    _recover_failed_turn(
                        message,
                        None,
                        attempts=0,
                        failure_kinds=("contract",),
                    )
                )
            elif kind == "plan":
                write_request_message(
                    {
                        "type": "plan.result",
                        "id": request_id,
                        "version": 1,
                        "kind": "clarify",
                        "question": error.question,
                        "steps": [],
                    }
                )
            else:
                write_request_message(
                    protocol.error_reply(
                        request_id,
                        "request_failed",
                        technical_failure_message(kind, "contract"),
                    )
                )
        except PlannerContractError:
            if kind == "turn.decide":
                write_request_message(
                    _recover_failed_turn(
                        message,
                        None,
                        attempts=0,
                        failure_kinds=("contract",),
                    )
                )
            else:
                write_request_message(
                    protocol.error_reply(
                        request_id,
                        "request_failed",
                        technical_failure_message(kind, "contract"),
                    )
                )
        except Exception as error:  # noqa: BLE001 — fail-closed boundary
            if internal_replay:
                _report_internal_replay_failure(error)
            if kind == "turn.decide":
                write_request_message(
                    _recover_failed_turn(
                        message,
                        None,
                        attempts=0,
                        failure_kinds=("runtime",),
                    )
                )
            else:
                write_request_message(
                    protocol.error_reply(
                        request_id,
                        "request_failed",
                        technical_failure_message(kind, "runtime"),
                    )
                )
        finally:
            request_signal.close()
            _finish_request_scope(
                interactive_encoder=interactive_encoder,
                llm=llm,
                encoder_scope_attempted=encoder_scope_attempted,
                llm_scope_attempted=llm_scope_attempted,
                request_finished=request_finished,
                message=message,
            )

    return 0


def _receive_protocol_messages(
    events: queue.Queue[_InboundMessage | _ReadFailure | _DispatchFinished],
    read_message: Callable[[], dict[str, Any] | None],
) -> None:
    """Read the one owned stdin stream without executing request handlers."""

    while True:
        try:
            message = read_message()
        except BaseException as error:  # noqa: BLE001 - relay to owner thread
            events.put(_ReadFailure(error))
            return
        events.put(_InboundMessage(message))
        if message is None or (message and str(message.get("type")) == "shutdown"):
            return


def _open_protocol_reader() -> Callable[[], dict[str, Any] | None]:
    """Own one incremental raw-stdin reader for the receiver lifetime."""

    descriptor = sys.stdin.fileno()
    if os.name == "nt" and stat.S_ISFIFO(os.fstat(descriptor).st_mode):
        # A synchronous pipe read can stall cold native DSP loading on Windows.
        # Python 3.12 supports nonblocking pipes; the bounded reader waits only
        # when no bytes are available, leaving EOF and real errors distinct.
        os.set_blocking(descriptor, False)
    stream = protocol._BoundedFileDescriptorLineReader(descriptor)
    return partial(protocol.read_message, stream)


def _run_control_plane(lifecycle: _SidecarLifecycle) -> int:
    """Receive controls independently while keeping all model work serial."""

    events: queue.Queue[_InboundMessage | _ReadFailure | _DispatchFinished] = (
        queue.Queue(maxsize=CONTROL_EVENT_QUEUE_LIMIT)
    )
    request_lane = _SerialRequestLane()
    writer = _TerminalProtocolWriter(_write)

    def dispatch_requests() -> None:
        try:
            result = _run_sidecar(
                lifecycle,
                read_message=request_lane.read_message,
                write_message=writer.write,
                request_finished=request_lane.finish,
            )
        except BaseException as error:  # noqa: BLE001 - relay exact failure
            events.put(_DispatchFinished(error=error))
        else:
            events.put(_DispatchFinished(result=result))

    dispatch_thread = threading.Thread(
        target=dispatch_requests,
        name="baxy-mind-request-dispatch",
        daemon=True,
    )
    lifecycle.own_dispatch_thread(dispatch_thread)
    dispatch_thread.start()
    while not writer.wait_until_hello(0.05):
        try:
            startup_event = events.get_nowait()
        except queue.Empty:
            continue
        if not isinstance(startup_event, _DispatchFinished):
            raise RuntimeError("unexpected control event before hello")
        if startup_event.error is not None:
            raise startup_event.error
        return int(startup_event.result or 0)

    receiver_thread = threading.Thread(
        target=_receive_protocol_messages,
        args=(events, _open_protocol_reader()),
        name="baxy-mind-protocol-receiver",
        daemon=True,
    )
    # The receiver intentionally has process lifetime. Windows pipe reads are
    # nonblocking and never hold BufferedReader's shutdown lock. Normal
    # EOF/shutdown returns; after a dispatch failure, process teardown is the
    # cancellation boundary, including for other stdin descriptor types.
    receiver_thread.start()

    while True:
        event = events.get()
        if isinstance(event, _DispatchFinished):
            if event.error is not None:
                raise event.error
            return int(event.result or 0)
        if isinstance(event, _ReadFailure):
            request_lane.submit(event)
            request_lane.close(drop_pending=False)
            continue

        message = event.message
        if message is None:
            request_lane.close(drop_pending=False)
            continue
        kind = str(message.get("type"))
        blocking_work = False
        replay_token: int | None = None
        if kind == "voice.cancel":
            blocking_work, replay_token = request_lane.voice_cancel_snapshot()
        if kind == "voice.cancel" and blocking_work:
            try:
                cancelled = lifecycle.request_voice_cancel(
                    defer_if_unowned=replay_token is not None,
                )
            except Exception:  # noqa: BLE001 - serial handler keeps old error path
                cancelled = False
            if cancelled:
                writer.write(
                    {
                        "type": "voice.cancelled",
                        "id": message.get("id"),
                    }
                )
                if replay_token is not None:
                    request_lane.schedule_voice_cancel_replay(replay_token)
                continue
        if kind == "shutdown" and request_lane.has_blocking_work():
            writer.write_terminal(
                {
                    "type": "shutdown.ack",
                    "id": message.get("id"),
                }
            )
            request_lane.close(drop_pending=True)
            return 0

        submission = request_lane.submit(
            message,
            reserved=kind == "shutdown",
        )
        if submission is _LaneSubmission.FULL:
            writer.write(
                protocol.error_reply(
                    message.get("id"),
                    "request_failed",
                    technical_failure_message(kind, "runtime"),
                )
            )
        elif submission is _LaneSubmission.ACCEPTED and kind == "shutdown":
            request_lane.close(drop_pending=False)


def _report_secondary_cleanup_failure(error: BaseException) -> None:
    """Emit only a stable local type; stdout remains reserved for JSONL."""

    try:
        sys.stderr.write(f"baxy_mind_cleanup_failure:{type(error).__name__}\n")
        sys.stderr.flush()
    except Exception:  # noqa: BLE001 - diagnostics cannot change shutdown
        pass


def _report_internal_replay_failure(error: BaseException) -> None:
    """Keep a silent control replay observable without exposing request data."""

    try:
        sys.stderr.write(f"baxy_mind_control_replay_failure:{type(error).__name__}\n")
        sys.stderr.flush()
    except Exception:  # noqa: BLE001 - diagnostics cannot change control flow
        pass


def _report_deferred_voice_cancel_failure(error: BaseException) -> None:
    """Report a failed lazy cancel intent without leaking request content."""

    try:
        sys.stderr.write(
            f"baxy_mind_deferred_voice_cancel_failure:{type(error).__name__}\n"
        )
        sys.stderr.flush()
    except Exception:  # noqa: BLE001 - diagnostics cannot change control flow
        pass


def main() -> int:
    lifecycle = _SidecarLifecycle()
    primary_error: BaseException | None = None
    result: int | None = None
    completed = False
    try:
        result = _run_control_plane(lifecycle)
        completed = True
        return result
    except BaseException as error:
        primary_error = error
        raise
    finally:
        try:
            lifecycle.close()
        except BaseException as cleanup_error:
            _report_secondary_cleanup_failure(cleanup_error)
            if primary_error is None and not (completed and result == 65):
                raise


if __name__ == "__main__":
    sys.exit(main())
