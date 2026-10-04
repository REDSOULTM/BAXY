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
import math
import re
import stat
import sys
import threading
import time
import unicodedata
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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
from .semantic import decider as semantic_decider
from .semantic import dialogue as dialogue_slot
from .semantic import knowledge as semantic_knowledge
from .semantic.apps import (
    bare_close_pronoun,
    close_request_for_opened,
    deictic_close_request,
    names_the_active_window,
    names_the_window_in_front,
)
from .semantic.notes import (
    asks_overdue_notifications,
    conversation_note_title,
    list_creation_said,
    names_own_event,
    names_a_note,
    note_addition,
    note_content_unsaid,
    note_title_given,
    pointed_note_content,
    task_change,
    question_with_context,
    question_with_its_reason,
)
from .semantic import levels as semantic_levels
from .semantic.memory import explicit_memory_request
from .semantic import reading as semantic_reading
from .semantic import surface as semantic_surface
from .semantic import temporal as semantic_temporal
from .semantic import ui as semantic_ui
from .semantic.system import names_this_place, weather_destination_there
from .semantic.patterns import (
    application_shown_media_name,
    clarification_awaits_decider,
    list_entries_said_before,
    names_a_kind_of_music,
    output_level_request,
)
from .semantic.web import (
    asks_for_information,
    asks_latest_release,
    asks_to_watch_the_news,
    asks_what_a_cinema_shows,
    currency_conversion_request,
    names_own_data,
    near_the_person,
    news_lookup_query,
    place_fixed_by_conversation,
    place_query_in_conversation,
    search_has_typed_reads,
    typed_read_over_search,
)
from .semantic.windows import said_snap_side, start_menu_request
from .semantic.files import named_file_meant, named_file_operation, named_file_request
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
    _previous_reply_fields,
    _single_fenced_code,
    _situation_from_facts,
    served_capability_families,
    talk_reply_tells_a_failure,
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
    enum_member_named,
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
    asks_for_code,
    catalog_unavailable,
    first_person_observation,
    names_a_question_word,
    nonunderstanding,
    random_draw_request,
    social_act,
    stable_no_effect,
    stable_no_effect_preempts,
)
from .semantic.arguments import (
    _canonical_due_utc,
    _explicit_arguments_from_evidence,
    _fully_enumerated_note_create_arguments,
    _presentation_arguments,
    _select_referenced_predecessor,
    closes_the_active_window,
    conversation_file_folder,
    conversation_pdf,
    conversation_text_file,
    corrected_song_title,
    due_before_said_moment,
    literal_ocr_language,
    literal_vision_prompt,
    names_spotify,
    partial_explicit_arguments,
    reminder_title_without_que,
    window_snap_plan_split,
    window_snap_side_for_step,
)
from .semantic.messaging import (
    chat_message_dispatch,
    latest_mail_reply_without_words,
    message_body,
    social_network_request,
)
from .semantic.arguments import (  # noqa: F401 - moved to baxy_mind.semantic.arguments; callers migrate
    _SYSTEM_STATUS_SCOPES,
    _explicit_calendar_event_arguments,
    _explicit_calendar_range_arguments,
    _explicit_media_control_arguments,
    _explicit_notification_schedule_arguments,
    _explicit_system_status_scope,
)
from .semantic.web import (
    common_concept_definition,
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
        "note.update",
        "notification.dismiss",
        "ocr.read",
        "package.install.commit",
        "peripheral.print",
        "peripheral.scan",
        "reminder.delete",
        "task.complete",
        "task.delete",
        "task.reopen",
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
        # (llm.talk_reply_tells_a_limit); the turn did not understand it as talk, it met a limit.
        or reason == "told_limit"
    ):
        return LIMIT_WORDING_FAILURE
    if isinstance(error, ConversationReplyContractError):
        return CONVERSATION_WORDING_FAILURE
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


def _said_optional_arguments(arguments: object, schema: dict, trusted_source: str) -> dict:
    """The optional fields of ``arguments`` each grounded in what was said, alone (M76); none when there are none."""

    properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    kept: dict = {}
    for name, value in (arguments.items() if isinstance(arguments, dict) else ()):
        contract = properties.get(name)
        if not isinstance(contract, dict):
            continue
        field_schema = {"type": "object", "properties": {name: contract}, "required": [name], "additionalProperties": False}
        if validate_argument_grounding({name: value}, field_schema, trusted_source):
            kept[name] = value
    return kept


def prepare_direct_argument_result(
    llm: object,
    objective: str,
    tool: dict,
    arguments: object,
    fallback_question: str = "",
    response_language: str | None = None,
    *,
    trusted_source: str | None = None,
) -> tuple[dict | None, str]:
    """Return only grounded arguments or one schema-grounded clarification.

    ``response_language`` is the turn's language decided upstream (M47); the question is formulated in it rather
    than in the objective's. ``trusted_source`` widens the evidence to what the person and BAXY said in the
    conversation (M43) when the values came from the decider, which read it; the question still asks from the
    objective.
    """

    schema = tool["function"]["parameters"]
    if not schema.get("required"):
        # M76 (DEV-D v3l D-s014, D-s054, D-s080: the weather asked «¿En qué ciudad…?»): with every field optional
        # there is nothing to ask. A value the person did not say (a town the model brought, this PC's own) is left
        # out and the operation's default applies; what was said is kept.
        arguments = _said_optional_arguments(
            arguments, schema, objective if trusted_source is None else trusted_source,
        )
    grounded, fields = normalize_objective_arguments(
        arguments,
        schema,
        objective if trusted_source is None else trusted_source,
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
        **({"response_language": response_language} if response_language else {}),
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
    # M160: the rest of a note.update (revision, title, what it says) is the read's too (``_note_addition_arguments``).
    "note.update": ("noteId",),
    "notification.dismiss": ("reminderId", "expectedVersion"),
    "ocr.read": ("captureId",),
    "office.document.read": ("documentId",),
    "peripheral.print": ("deviceId",),
    "reminder.delete": ("reminderId", "expectedVersion", "reviewLabel"),
    "task.delete": ("taskId", "expectedVersion", "reviewLabel"),
    # M76 (DEV-D v3l D-w17-t2): identity and version from task.resolve.exact.
    "task.complete": ("taskId", "expectedVersion"),
    "task.reopen": ("taskId", "expectedVersion"),
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
    *,
    purpose: str = "",
) -> dict[str, object] | None:
    """Copy a complete unique identity from permitted verified producers.

    This is the sidecar equivalent of the App boundary's deterministic
    projector.  It removes stochastic model extraction only when the selected
    dependency already proves every argument required by the exact schema.
    """

    if not isinstance(observations, list):
        return None
    if operation == "note.update":
        return _note_addition_arguments(objective, purpose, observations, tool)
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
        if explicit is None and operation == "window.snap":
            # M55: a request that docks several windows gives each its own side; the step's purpose
            # picks which of the request's pairs this window is, the side stays the person's.
            explicit = window_snap_side_for_step(objective, purpose, application_names)
        if explicit is None and operation == "window.snap" and names_the_window_in_front(objective):
            # M145 (DEV-G v4p G-s041, G-s082, G-s102; DEV-H H-s028): the window in front has no name to read the
            # side beside; the side is the one half the request says.
            side = said_snap_side(objective)
            explicit = {"side": side} if side is not None else None
        if not isinstance(explicit, dict):
            return None
        merged = {**explicit, **arguments}
        if not validate_json_schema_instance(merged, schema):
            return None
        return merged
    return arguments


def _note_addition_arguments(
    objective: str, purpose: str, observations: list[object], tool: dict[str, object],
) -> dict[str, object] | None:
    """M160 (DEV-G v4w G-w12-t2 «agrégale que quiero comprarle un ramo de flores» after the note was made → «¿Cuál es
    el título de la nota que deseas editar?»): note.update replaces a note chosen by its identity and revision with a
    whole title and content; for an addition («Agrega «X» a la nota «Y».») they are the verified read's, and the content
    is what the note says followed by what the request adds (``semantic.notes.note_addition``), never rewritten. None
    when the request adds nothing it can say (a new title, a whole new text): the model grounds those as before."""

    reads = [
        observation["result"]
        for observation in observations
        if isinstance(observation, dict)
        and observation.get("operation") == "note.read"
        and observation.get("verified") is True
        and observation.get("status") == "completed"
        and isinstance(observation.get("result"), dict)
    ]
    added = note_addition(objective) or note_addition(purpose)
    if len(reads) != 1 or added is None:
        return None
    note = reads[0]
    if (
        not isinstance(note.get("noteId"), str)
        or not isinstance(note.get("title"), str)
        or isinstance(note.get("revision"), bool)
        or not isinstance(note.get("revision"), int)
        or note.get("isTrashed")
    ):
        return None
    said = str(note.get("content") or "").rstrip()
    candidate = {
        "noteId": note["noteId"],
        "expectedRevision": note["revision"],
        "expectedTitle": note["title"],
        "title": note["title"],
        "content": f"{said}\n{added}" if said else added,
    }
    function = tool.get("function")
    schema = function.get("parameters") if isinstance(function, dict) else None
    return candidate if isinstance(schema, dict) and validate_json_schema_instance(candidate, schema) else None


def _conversation_note_selector(
    operation: str,
    plan_operations: tuple[str, ...],
    person: str,
    dialogue_state: dialogue_slot.DialogueState,
    schema: dict[str, object],
) -> dict[str, str] | None:
    """M160 (DEV-G v4w G-w12-t2 «agrégale que quiero comprarle un ramo de flores» right after «He guardado la nota con
    el título "ideas para el cumpleaños de juliana".»): the read before a note.update is of the note this conversation
    just made, read or changed (``DialogueState.edited_note_title``), by the title the store verified, when the person
    names no note of their own. None otherwise: with no note in the conversation, the step is read and asked as before."""

    if operation != "note.read" or "note.update" not in plan_operations or names_a_note(person):
        return None
    title = dialogue_state.edited_note_title()
    selector = {"title": title} if title else None
    return selector if selector is not None and validate_json_schema_instance(selector, schema) else None


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
        and (
            effect_intent.known_unsupported_effect_request(objective, available_operations)
            # M94 (DEV-D D-p02-t2 «¿Serías capaz de hacer foto ahora?» → «No, no puedo hacer fotos» told as knowledge):
            # a request no operation serves keeps its limit when it is asked as a question.
            or effect_intent.unserved_personal_request(objective)
        )
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
    """

    shortlist = planner_catalog.shortlist(routing_objective)[:depth]
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
    encoder: Callable[[Any], Any],
    tool_by_name: dict[str, dict],
    application_names: tuple[str, ...] | ApplicationCatalogIndex,
    game_catalog: GameCatalogIndex,
    on_signal: PendingTurnSignal | None,
    already_signaled: list[bool],
    decided_request: str | None = None,
) -> dict[str, Any] | None:
    """The turn decided again on the canonical surface of a request about to be refused, or None.

    Only when the rewrite (``semantic.surface``) reads as a served request: the readers prove an effect or
    a missing value in it (Fase 3.5b M13: whether the limit came from a reader or from the contextual
    decider). The domain gate over the shortlist that also re-decided a rewrite it grounded was retired
    with the model path. Asking the catalogue about every refusal was measured and rejected (see the public
    lookup comment in ``_decide_turn_result``): the nearest neighbours of an out-of-catalogue request turned
    honest limits into questions. Here the evidence is a word the readers know standing where the person
    said another one; a limit of something BAXY does not have keeps its words and stays a limit.

    M78 (DEV-D v3l s010 «deactivates the speaker now» → «Turn off the speaker.», p12-t2 «Bring up 24/7 stores near
    me» after «Which request should I cancel?»): a limit the contextual decider gave (``decided_request`` is its
    restatement) is also re-read on the canonical surface of that restatement, and on the message as said when it
    is a complete request: inside a conversation the readers stepped aside for the decider, and «Turn off the
    audio.» (audio.mute) or «Bring up 24/7 stores near me» (web.search) are what they prove.
    """

    candidates = [semantic_surface.canonical(objective)]
    if decided_request is not None:
        restated = decided_request.strip()
        # The restatement itself is not re-read: «Pon la alarma en el celular usando la app del reloj.» (w02-t4, an
        # honest limit) would become a question about an alarm; only its canonical surface, a word the readers know
        # standing where the decider wrote another, is evidence.
        candidates += [
            objective if effect_request_is_authoritative(objective) else None,
            semantic_surface.canonical(restated) if restated else None,
        ]
        if dialogue_slot.dependency(objective, dialogue_slot.read_slot(message, history, objective)) is not None:
            # M112 (DEV-F v4d w52-t2 «sí, dale, bájalo a 30» after the battery was read → the decider's limit re-read
            # as said and the volume set to 30): a message that leans on the conversation names its object there;
            # read alone, the readers fill it with their own default. Only the decider's restatement, which carries
            # it, is re-read.
            candidates = [semantic_surface.canonical(restated) if restated else None]
    previous = _previous_user_request(history if isinstance(history, list) else [], objective)
    canonical = None
    for candidate in dict.fromkeys(text for text in candidates if text):
        reading = semantic_reading.read(
            candidate,
            available_operations=tuple(tool.name for tool in planner_catalog.tools),
            application_names=application_names,
            game_catalog=game_catalog,
            previous_user_text=previous,
        )
        if reading.effects is not None or reading.clarification is not None:
            canonical = candidate
            break
    if canonical is None:
        # Fase 3.5b M13: only what the readers prove on the canonical surface overrides a limit; the
        # domain gate over the shortlist turned honest limits into actions and is retired.
        return None
    turns = list(history) if isinstance(history, list) else []
    if turns and isinstance(turns[-1], dict) and turns[-1].get("role") == "user":
        turns[-1] = {**turns[-1], "content": canonical}
    try:
        result = _decide_turn_result(
            {**message, "text": canonical, "history": turns},
            llm=llm,
            planner_catalog=planner_catalog,
            encoder=encoder,
            tool_by_name=tool_by_name,
            application_names=application_names,
            game_catalog=game_catalog,
            on_signal=on_signal,
            served_surface=(),
            already_signaled=already_signaled,
        )
    except PlannerContractError:
        # A re-read that breaks its own turn contract adds nothing: the limit already decided stands.
        return None
    # The shell plans, confirms and resumes the words that were read.
    result.setdefault("objective", canonical)
    return result


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
) -> bool:
    """Whether operations a stage withheld, or a catalogue probe named, are done instead of offered.

    Tanda 4 2026-09-24: «let me know what today's date is», «please put the meeting
    with carla on my to do list», «find instructions on how to play taboo» were
    answered «Want me to …?». A complete request is done, never offered back as a
    yes/no question that asks for no value. The identity verifier cannot carry
    that authority: it keeps 46 of 48 right proposals but refuses only 21 of 84
    wrong ones (``LlmRuntime.operation_is_the_requested_effect``). Each operation
    acts only on stronger evidence: the strict verifier finds it satisfies the
    whole request. A near miss, a risk outside ``_ACTS_WITHOUT_ASKING_RISKS``, a
    silent verifier or a failed one keeps the stricter side: nothing acts.
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

    if _acts_without_asking(objective, operations, tool_by_name, llm, application_names):
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
        elif field in partial_explicit_arguments(operation, objective, schema):
            # M76 (DEV-D v3l D-p19-t1): a title the readers know is not asked with the service that is missing.
            stated.append(field)
    return tuple(stated)


# Fase 3.5b M42 (D33): the values the decider read in the conversation reach the arguments step of the same turn,
# keyed by the restated request the App sends back. Spent FINAL: 12 well-decided actions asked again for a time, a
# name or a folder the person had given; the decider had read them (DEV-A: 55 of 57).
_DECIDED_ARGUMENTS: dict[str, tuple[tuple[str, ...], tuple[tuple[str, Any], ...]]] = {}
_DECIDED_ARGUMENTS_KEPT = 32


def _remember_decided_arguments(
    objective: str, operations: tuple[str, ...], arguments: tuple[tuple[str, Any], ...],
) -> None:
    key = " ".join(objective.split())
    if not key or not arguments:
        return
    _DECIDED_ARGUMENTS.pop(key, None)
    _DECIDED_ARGUMENTS[key] = (tuple(operations), tuple(arguments))
    while len(_DECIDED_ARGUMENTS) > _DECIDED_ARGUMENTS_KEPT:
        _DECIDED_ARGUMENTS.pop(next(iter(_DECIDED_ARGUMENTS)))


def _prior_user_texts(history: object, current: str) -> tuple[str, ...]:
    """The person's earlier messages, oldest first, without the current one when the history already ends in it."""

    items = [item for item in history if isinstance(item, dict)] if isinstance(history, list) else []
    if items and items[-1].get("role") == "user" and items[-1].get("content") == current:
        items = items[:-1]
    return tuple(str(item.get("content") or "") for item in items if item.get("role") == "user" and item.get("content"))


def _reference_lookup(objective: str, history: object) -> "semantic_knowledge.ReferenceLookup | None":
    """M53 (step 6 of goal v3, D35): a named dish's recipe or a named work's plot is looked up, never recited.

    ``semantic.knowledge`` reads the kind of fact from the person's words; the decider (its LoRA) is unchanged: its
    «talk» for these kinds becomes ``web.search`` with the query the reader writes, the same one the arguments step
    reads back from the same request.
    """

    # M88: BAXY's last answer is the referent of «¿cuánto sería eso de harina en gramos?».
    last_reply = next(
        (
            str(item.get("content") or "")
            for item in reversed(history if isinstance(history, list) else [])
            if isinstance(item, dict) and item.get("role") == "assistant"
        ),
        "",
    )
    return semantic_knowledge.reference_lookup(objective, _prior_user_texts(history, objective), last_reply)


def _decided_value(value: Any, contract: dict[str, Any]) -> Any:
    """The decider's scalar in the field's JSON type, or None when it cannot be one."""

    declared = contract.get("type")
    types = set(declared if isinstance(declared, list) else [declared])
    enum = contract.get("enum")
    if isinstance(enum, list):
        # M118 (D58): the decider may name the member in the person's language («Descargas» → downloads).
        return enum_member_named(value, enum)
    if "integer" in types and not isinstance(value, bool):
        if isinstance(value, int):
            return value
        text = str(value).strip()
        return int(text) if re.fullmatch(r"-?\d{1,9}", text) else None
    if "number" in types and not isinstance(value, bool):
        try:
            number = float(str(value).strip().replace(",", "."))
        except ValueError:
            return None
        return number if math.isfinite(number) else None
    if "boolean" in types:
        return value if isinstance(value, bool) else None
    if "string" in types:
        if isinstance(value, (list, dict)):
            # M141: a list or an object is never one text; its rendering («['Spotify', 'Discord']») grounds by words.
            return None
        if isinstance(value, str) and (
            len(value) >= semantic_decider.ARGUMENT_VALUE_CHARACTERS
            # M118 (DEV-F F-w42-t3, code cut at «…dni[-1].upper()\n    if \n»): lines left open at the end are cut too.
            # M141 (DEV-G v4n G-w06-t3 «guárdalo en un archivo que se llame suma.py» → «def sumar(a, b):\n    return
            # a + b\n»): a closed last line followed by its line break is whole, not open.
            or ("\n" in value and value.rstrip("\r\n") != value.rstrip())
        ):
            # M67 (FINAL F-w14-t3): a text at the decider's bound is the start of a longer one (a query, a list BAXY
            # wrote), grounded but cut; the extraction reads it whole instead.
            return None
        text = " ".join(str(value).split())
        return text or None
    return None


def _with_decided_arguments(
    operation: str,
    request: str,
    arguments: object,
    schema: dict[str, object],
    trusted_source: str,
    *,
    serves: tuple[str, ...] = (),
    previous_reply: str | None = None,
) -> dict[str, Any] | None:
    """Fill what the extraction left out or could not ground with what the decider read.

    Each value must be grounded in the trusted text like any model-proposed literal; identifiers stay with the
    kernel's dependencies and times with ``temporal`` (the decider's own ISO dates are not trusted). None when the
    decider gave nothing new for this operation. ``serves`` and ``previous_reply``: see ``_decided_fields``.
    """

    decided = _decided_fields(
        operation, request, schema, trusted_source, serves=serves, previous_reply=previous_reply,
    )
    if decided is None:
        return None
    merged = dict(arguments) if isinstance(arguments, dict) else {}
    added = False
    for name, value, field_schema in decided:
        if name in merged and validate_argument_grounding({name: merged[name]}, field_schema, trusted_source):
            continue
        if not validate_argument_grounding({name: value}, field_schema, trusted_source):
            value = _said_part_of_a_name(name, value, field_schema, trusted_source) or (
                # M136: a folder the decider chose and nobody said is every known folder, when that grounds.
                "all_known" if "all_known" in (field_schema["properties"][name].get("enum") or []) else None
            )
        if value is not None and validate_argument_grounding({name: value}, field_schema, trusted_source):
            merged[name] = value
            added = True
    return merged if added else None


# M136 (DEV-G v4n G-s097 «baxy abreme el obs…» → the decider's «OBS Studio» → «¿Cuál es el nombre exacto de la
# aplicación…?»): an application's name the decider completed with words nobody said keeps the words the person said.
_SAID_NAME_FIELDS = frozenset({"appId", "name"})
# M147: the fields that carry a name to look up or play as the person wrote it, for the services whose own search
# forgives a typo of the person's. Web search sources forgive none (D-w08-t1). M157: an application's name is resolved
# in the catalog of installed applications, for which the readers already chose the name the person's spelling meant
# («abreme el exel» → Excel, M127), so it keeps that name.
_AS_SPELLED_FIELDS = frozenset({"query", "title", "artist"})
_AS_SPELLED_LOOKUPS = ("media.play", "streaming.play")


def _as_the_person_spelled(operation: str, arguments: Any, person: str, history: object) -> Any:
    """M147 (DEV-F F-w05-t5 «pone algo de javiera mena en spotify» → the decider's «Javier Mené», every round, and
    another artist played): a name a service looks up, respelled by the model a letter or two off from what the person
    wrote, is looked up as the person wrote it (``semantic.decider.as_the_person_spelled``).

    M157 (DEV-F v4u/v4v F-w05-t5, the same row: seen.query «Javier Mené» in both runs): M147 ran on the decider's values
    against the grounding source, whose first line is the objective — the decider's own restatement «Pon algo de Javier
    Mené en Spotify.» —, so the name was always «said as it is» there; and the readers had already read it from that
    restatement, so the decider's values were never looked at. The respelling now runs once, on the arguments the step
    returns whoever read them, against what the person and BAXY said in the conversation, never the restatement.
    """

    if not isinstance(arguments, dict) or not operation.startswith(_AS_SPELLED_LOOKUPS):
        return arguments
    said = _conversation_grounding_source(person, history).splitlines()
    respelled = dict(arguments)
    for name in _AS_SPELLED_FIELDS & set(arguments):
        if isinstance(arguments[name], str):
            respelled[name] = semantic_decider.as_the_person_spelled(arguments[name], said) or arguments[name]
    return respelled


def _said_part_of_a_name(name: str, value: Any, field_schema: dict[str, Any], trusted_source: str) -> Any:
    """The longest run of the decider's words for an application's name that grounds on its own; None when none does."""

    if name not in _SAID_NAME_FIELDS or not isinstance(value, str):
        return None
    words = value.split()
    for size in range(len(words) - 1, 0, -1):
        for start in range(len(words) - size + 1):
            part = " ".join(words[start:start + size])
            if len(part) >= 2 and validate_argument_grounding({name: part}, field_schema, trusted_source):
                return part
    return None


def _schema_field_of(name: str, operation: str, properties: dict[str, Any], required: list[Any]) -> str | None:
    """M136 (DEV-G v4n G-s040 «open Notepad and put it on the left half» → {"app": "Notepad"}; G-s116 «abrí spotify y
    ponime algo de jazz» → {"app.open": "Spotify", "media.play.query": "jazz tranquilo"}): the field of this
    operation's schema a decider's value names — the field itself, the operation's one free required text when the
    value is keyed by the operation, or the one field whose name begins with the decider's («app» → «appId»)."""

    if name in properties:
        return name
    if name == operation:
        free = [
            field for field in required
            if isinstance(properties.get(field), dict)
            and properties[field].get("type") == "string"
            and "enum" not in properties[field]
            and "const" not in properties[field]
        ]
        return free[0] if len(free) == 1 else None
    if len(name) < 3:
        return None
    named = [field for field in properties if field.casefold().startswith(name.casefold())]
    return named[0] if len(named) == 1 else None


def _decided_fields(
    operation: str,
    request: str,
    schema: dict[str, object],
    trusted_source: str,
    *,
    serves: tuple[str, ...] = (),
    previous_reply: str | None = None,
) -> list[tuple[str, Any, dict[str, Any]]] | None:
    """The decider's values for ``operation`` that a field may take, each with its one-field schema; None when the
    decider gave none for this request. Identifiers stay with the kernel's dependencies and times with ``temporal``.

    ``serves``: the decided operations this one is the catalog's prerequisite of (M141, a plan's ``window.resolve``
    before the decided ``window.snap``), whose values it may take too. ``previous_reply``: BAXY's last reply, whole; a
    free text the decider wrote that is that reply (or its one code block) in the same words is the reply verbatim."""

    remembered = _DECIDED_ARGUMENTS.get(" ".join(request.split()))
    properties = schema.get("properties")
    if (
        remembered is None
        or not ({operation, *serves} & set(remembered[0]))
        or not isinstance(properties, dict)
    ):
        return None
    identities = set(_DETERMINISTIC_DEPENDENCY_FIELDS.get(operation, ()))
    required = schema.get("required") if isinstance(schema.get("required"), list) else []
    given = {name for name, _ in remembered[1]}
    fields: list[tuple[str, Any, dict[str, Any]]] = []
    for decided_name, raw in remembered[1]:
        name = _schema_field_of(decided_name, operation, properties, required)
        if name is None or (name != decided_name and name in given):
            continue
        contract = properties.get(name)
        if (
            not isinstance(contract, dict)
            or name in identities
            or (name.endswith("Id") and name != "appId")
            or name.endswith("Utc")
            or contract.get("format") in {"date-time", "date", "time"}
        ):
            continue
        if name == "due":
            raw = semantic_temporal.said_day_of(raw, trusted_source) or raw
        verbatim = (
            _reply_the_decider_wrote(raw, previous_reply)
            if previous_reply and _free_text_field(name, contract)
            else None
        )
        value = verbatim if verbatim is not None else _decided_value(raw, contract)
        if value is None:
            continue
        fields.append(
            (name, value, {"type": "object", "properties": {name: contract}, "required": [name], "additionalProperties": False})
        )
    return fields


def _reply_the_decider_wrote(value: Any, previous_reply: str) -> str | None:
    """M141 (DEV-G v4o G-w06-t3 «guárdalo en un archivo que se llame suma.py» after BAXY's ```python block → the
    decider's ``text`` «def sumar(a, b):\\n    return a + b\\n» → «¿Cuál es el código…?»): BAXY's previous reply, or its
    one code block, verbatim when the decider's free text is it in the same words (or, cut at the decider's bound, its
    start). The decider's values are whitespace-folded and bounded, so code and lists travel only through here (M67)."""

    if not isinstance(value, str) or not value.strip():
        return None
    written = " ".join(value.split())
    cut = len(value) >= semantic_decider.ARGUMENT_VALUE_CHARACTERS
    for candidate in (_single_fenced_code(previous_reply), previous_reply.strip()):
        if not candidate:
            continue
        said = " ".join(candidate.split())
        if said == written or (cut and said.startswith(written)):
            return candidate
    return None


def _decided_reply_field(operation: str, request: str, schema: dict[str, object], previous_reply: str | None) -> bool:
    """M141: the decider wrote BAXY's previous reply (``_reply_the_decider_wrote``) into one of this operation's fields."""

    if not previous_reply:
        return False
    reply = previous_reply.strip()
    candidates = {reply, _single_fenced_code(reply) or reply}
    return any(
        value in candidates
        for _, value, _ in _decided_fields(operation, request, schema, "", previous_reply=reply) or ()
    )


def _said_single_members(schema: dict[str, object], trusted_source: str) -> dict[str, Any]:
    """M141: each required field with one possible value (a one-member enum, a const) that was said — Spotify for
    ``media.play.query``'s provider. Nothing is chosen: the field can take no other value."""

    properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    required = schema.get("required") if isinstance(schema.get("required"), list) else []
    said: dict[str, Any] = {}
    for field in required:
        contract = properties.get(field)
        if not isinstance(contract, dict):
            continue
        members = contract.get("enum") if isinstance(contract.get("enum"), list) else (
            [contract["const"]] if "const" in contract else []
        )
        if len(members) != 1:
            continue
        field_schema = {"type": "object", "properties": {field: contract}, "required": [field], "additionalProperties": False}
        if validate_argument_grounding({field: members[0]}, field_schema, trusted_source):
            said[field] = members[0]
    return said


def _plan_step_decided_arguments(
    operation: str,
    plan_operations: tuple[str, ...],
    objective: str,
    tool: dict,
    history: object,
    *,
    extracted: object = None,
    after_extraction: bool = False,
) -> dict[str, Any] | None:
    """M141 (DEV-G v4o G-s040 «open Notepad and put it on the left half of the screen please» → the decider's
    {"app": "Notepad", "side": "left"}; G-s116 «abrí spotify y ponime algo de jazz tranqui…» → {"app.open":
    "Spotify", "media.play.query": "jazz tranquilo"}; both → «¿Cuál es el nombre… de la aplicación…?»): a plan step
    takes what the decider read, as one operation does (M42b, M136), so the planner's extraction runs only for what
    is still missing and asks only for that.

    Before the extraction, only a step whose operation the decider decided, and only when its values (with each
    one-valued field that was said) fill the whole step. After the extraction failed, its values are completed with
    the decider's, and a catalog prerequisite of a decided effect (``window.resolve`` before ``window.snap``) may take
    them too. An operation that is two steps of the plan takes none: the decider's values cannot say which step is
    whose. Every value grounds in what was said in this conversation (M43); the arguments, or None."""

    if plan_operations.count(operation) != 1:
        return None
    schema = tool["function"]["parameters"]
    served: tuple[str, ...] = ()
    if after_extraction:
        served = tuple(dict.fromkeys(
            effect for effect in plan_operations if operation in required_predecessors(effect)
        ))
        if len(served) != 1 or plan_operations.count(served[0]) != 1:
            served = ()
    elif _previous_reply_may_be_content(tool, history):
        # As M42b: a content that may be BAXY's last reply is read by the extraction, not by the decider alone.
        return None
    said = _conversation_grounding_source(objective, history)
    said = _with_decided_restatements(operation, objective, schema, said)
    said = _with_every_known_folder_unsaid(operation, schema, said)
    read = dict(extracted) if isinstance(extracted, dict) else {}
    base = {**_said_single_members(schema, said), **read}
    decided = _with_decided_arguments(operation, objective, base, schema, said, serves=served)
    if decided is None:
        if not after_extraction or base == read:
            return None
        # The extraction's values completed with a one-valued field that was said.
        decided = base
    grounded = normalize_grounded_arguments(decided, schema, said)
    if grounded is None:
        return None
    normalized = _normalize_grounded_operation_arguments(operation, grounded, objective)
    if normalized is None or not validate_json_schema_instance(normalized, schema):
        return None
    # M147/M157: a plan step's name to look up goes as the person spelled it too (``_as_the_person_spelled``).
    return _as_the_person_spelled(operation, normalized, _person_message(history, objective), history)


# M136 (DEV-G v4n G-s123 «resúmeme el pdf ese que se llama contrato_arriendo_2026…», G-w40-t1 «busca un archivo que se
# llama cotizacion_mudanza» → the decider's folder «Documentos»/«Descargas», nobody's → «¿En qué carpeta…?»): a read of a
# named file where the person names no folder looks in every known folder, as the readers do (PDF1689); a write or a
# deletion keeps asking.
_EVERY_KNOWN_FOLDER_READS = frozenset({"document.pdf.read", "document.text.read", "filesystem.known.search"})


def _with_every_known_folder_unsaid(operation: str, schema: dict[str, object], trusted_source: str) -> str:
    """The trusted source with «all known» when this read's folder enum holds it and no member of it was said."""

    if operation not in _EVERY_KNOWN_FOLDER_READS:
        return trusted_source
    properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    for field, contract in properties.items():
        members = contract.get("enum") if isinstance(contract, dict) else None
        if not isinstance(members, list) or "all_known" not in members:
            continue
        field_schema = {"type": "object", "properties": {field: contract}, "required": [field], "additionalProperties": False}
        if not any(validate_argument_grounding({field: member}, field_schema, trusted_source) for member in members):
            return f"{trusted_source}\nall known"
    return trusted_source


# M118 (D58): the fields whose value is the person's words (a message, a note, a title, a search), where a restatement
# may say the same thing differently; names of people, places in the catalog, paths and addresses stay literal.
_LITERAL_ONLY_FIELDS = frozenset({"appId", "recipient", "url", "resourceUri", "relativePath", "path", "host", "name"})


def _free_text_field(name: str, contract: dict[str, Any]) -> bool:
    declared = contract.get("type")
    types = set(declared if isinstance(declared, list) else [declared])
    return (
        "string" in types
        and "enum" not in contract
        and "const" not in contract
        and name not in _LITERAL_ONLY_FIELDS
    )


def _with_decided_restatements(operation: str, request: str, schema: dict[str, object], trusted_source: str) -> str:
    """M118 (D58): the trusted source with each free text the decider wrote that says what was said in other words
    (``semantic.decider.said_in_other_words``): the literal grounding dropped them and the turn asked again for what the
    person gave. What the decider brought that nobody said (a number, a name) still grounds nothing."""

    decided = _decided_fields(operation, request, schema, trusted_source) or []
    lines = trusted_source.splitlines()
    restated = [
        value
        for name, value, field_schema in decided
        if (
            _free_text_field(name, field_schema["properties"][name])
            and semantic_decider.said_in_other_words(value, lines)
            # M143 (DEV-H v4o H-w21-t1 «che baxy, tirá algún tema de charly garcia de los ochenta, el que sea» → the
            # decider's media.play.query {"provider": "Spotify"} → «¿Qué proveedor de música debo usar…?»): a field
            # with one possible member is no choice of the person's; the decider that chose this operation and gave
            # that member said the only value the field can take (M141 ``_said_single_members`` needs it said).
            or field_schema["properties"][name].get("enum") == [value]
        )
        and not validate_argument_grounding({name: value}, field_schema, trusted_source)
    ]
    return "\n".join([trusted_source, *restated]) if restated else trusted_source


# M118 (D58): the fields whose words are what the operation delivers (a message, a note, what a reminder says); the
# decider's wording of them stands over the readers'. A task's title and details keep the list model (M113: the entry,
# the list it goes on), a search its query (D32, M53) and a song its title: there the readers' value is the operation's
# own shape, not a reading of the person's words.
_DECIDER_WORDING_FIELDS = frozenset({"text", "content", "body", "subject", "message"})
_DECIDER_TITLED_OPERATIONS = ("note.", "notification.schedule", "reminder.create", "calendar.event.")


def _with_decider_values_kept(
    operation: str, request: str, arguments: dict[str, Any], schema: dict[str, object], trusted_source: str,
) -> dict[str, Any]:
    """M118 (D58, DEV-F F-w55-t5 «eso mandalo a una nota, titulala dentista» → the readers' title ««Dentista»» with
    its quotes, F-w12-t1 «…una alarma pa las 6 y 40 mañana, que tengo que ir a buscar a la Trini al aeropuerto» → the
    readers' title «alarma mañana a las 6:40»): the words the decider gave for what the operation delivers, grounded
    in what was said, are never replaced by the readers' reading of the same field; what the decider left out keeps
    the readers' value. The readers' arguments when the result would not hold the schema."""

    decided = _decided_fields(operation, request, schema, trusted_source)
    if not decided:
        return arguments
    merged = dict(arguments)
    for name, value, field_schema in decided:
        if (
            name in merged
            and merged[name] != value
            and (
                name in _DECIDER_WORDING_FIELDS
                or (name == "title" and operation.startswith(_DECIDER_TITLED_OPERATIONS))
            )
            and _free_text_field(name, field_schema["properties"][name])
            and validate_argument_grounding({name: value}, field_schema, trusted_source)
        ):
            merged[name] = value
    if merged != arguments and validate_json_schema_instance(merged, schema):
        return merged
    return arguments


def _with_decided_part_of_day(operation: str, request: str, arguments: Any) -> Any:
    """M144 (D58; DEV-H v4p H-w45-t1 «tengo dentista el jueves a las 4:30, so ponme un reminder» → set at 04:30, where
    the isolated decider set 16:30): a clock written on the dial («a las 4:30», no part of the day said) is read as
    written, 04:30; the decider read its part of the day from what it is for (a dentist at 16:30, an alarm before a
    flight at 04:50). When the decider's own moment is that same clock twelve hours away, its part of the day is the
    one meant, on the day the readers read."""

    if operation not in _REMINDER_OPERATIONS or not isinstance(arguments, dict):
        return arguments
    due = arguments.get("dueUtc")
    clocks = semantic_temporal.spoken_clocks(effect_intent._fold(request))
    if not isinstance(due, str) or len(clocks) != 1 or not clocks[0].on_the_dial:
        return arguments
    remembered = _DECIDED_ARGUMENTS.get(" ".join(request.split()))
    decided_due = dict(remembered[1]).get("dueUtc") if remembered is not None else None
    written = re.search(r"T(?P<hour>\d{2}):(?P<minute>\d{2})", decided_due) if isinstance(decided_due, str) else None
    try:
        moment = datetime.fromisoformat(due.replace("Z", "+00:00")).astimezone()
    except ValueError:
        return arguments
    if written is None or int(written["minute"]) != moment.minute or int(written["hour"]) != (moment.hour + 12) % 24:
        return arguments
    shifted = moment + timedelta(hours=12 if moment.hour < 12 else -12)
    if shifted <= datetime.now().astimezone():
        return arguments
    return {**arguments, "dueUtc": shifted.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")}


def _with_pointed_reminder_title(operation: str, person: str, history: object, arguments: Any) -> Any:
    """M148 (DEV-F v4q F-w48-t4 «recuérdame eso el domingo a las 3 de la tarde» after «…; mejor lleva paraguas.» →
    titled «Voy a estar en Zapopan el domingo.»; DEV-D v4q D-w07-t4 «…que le devuelva eso a mi carnal» after
    «Redondeado hacia arriba, 265.» → «Devolverle eso a mi amigo.»): a reminder that points with «eso» is titled with
    what the conversation gave (``semantic.dialogue.pointed_reminder_title``); a title that already says it stays."""

    if operation not in _REMINDER_OPERATIONS or not isinstance(arguments, dict):
        return arguments
    title = arguments.get("title")
    if not isinstance(title, str) or not title.strip():
        return arguments
    said_before = _prior_user_texts(history, person)
    pointed = dialogue_slot.pointed_reminder_title(person, _previous_reply(history), title, said_before)
    return {**arguments, "title": pointed} if pointed else arguments


def _conversation_grounding_source(objective: str, history: object) -> str:
    """M43: the request, the person's recent turns and BAXY's last reply, the text a decided value may come from.

    Spent FINAL: «Abre el Calendar» restated «Abre el Calendario»; the folder of a PDF said one turn earlier; «save
    that as a note» whose content was BAXY's previous answer. Only what was said in this conversation counts.
    """

    parts = [objective]
    if isinstance(history, list):
        turns = [item for item in history if isinstance(item, dict) and item.get("content")]
        parts.extend(
            str(item["content"])[:1500] for item in turns[-semantic_decider.HISTORY_TURNS:]
            if item.get("role") == "user"
        )
        last_reply = next((item for item in reversed(turns) if item.get("role") == "assistant"), None)
        if last_reply is not None:
            parts.append(str(last_reply["content"])[:1500])
    return "\n".join(parts)


def _previous_reply(history: object) -> str | None:
    """M67 (FINAL F-w14-t3, F-w15-t4): BAXY's reply right before the current message, whole, or None.

    The decider's values are bounded and the grounding source cuts each turn, so a content that is that reply (a SQL
    query, a packing list) travels only through here. Only the history's last assistant turn counts, with at most
    the current message after it.
    """

    if not isinstance(history, list):
        return None
    turns = [item for item in history if isinstance(item, dict) and str(item.get("content") or "").strip()]
    if turns and turns[-1].get("role") == "user":
        turns = turns[:-1]
    if not turns or turns[-1].get("role") != "assistant":
        return None
    return str(turns[-1]["content"]).strip()


def _previous_reply_may_be_content(tool: dict, history: object) -> bool:
    """M67b: BAXY's previous reply fits a long free-text field of the operation, so it may be the content.

    The decider's values are bounded and may restate the content («el query de SQL») instead of carrying it; then
    the extraction, which reads the reply, decides (M67), not the decider's values alone.
    """

    reply = _previous_reply(history)
    if not reply:
        return False
    schema = tool.get("function", {}).get("parameters") if isinstance(tool, dict) else None
    properties = schema.get("properties") if isinstance(schema, dict) else None
    if not isinstance(properties, dict):
        return False
    strings = tuple(
        name for name, contract in properties.items()
        if isinstance(contract, dict) and contract.get("type") == "string" and "enum" not in contract
    )
    return bool(_previous_reply_fields(schema, strings, reply))


def _conversation_exchanges(history: object) -> list[tuple[str, str]]:
    """M160: each of BAXY's replies with the person's message it answered, oldest first, without the current message."""

    turns = [item for item in history if isinstance(item, dict)] if isinstance(history, list) else []
    if turns and turns[-1].get("role") == "user":
        turns = turns[:-1]
    exchanges: list[tuple[str, str]] = []
    asked = ""
    for item in turns:
        content = str(item.get("content") or "")
        if item.get("role") == "user":
            asked = content
        elif item.get("role") == "assistant" and content.strip():
            exchanges.append((asked, content))
            asked = ""
    return exchanges


def _pointed_note_content(
    operation: str, request: str, person: str, history: object, schema: dict[str, object], said: str,
    arguments: object,
) -> tuple[str, str | None] | None:
    """M160 (DEV-H v4w H-w11-t3 «save that whole thing as a note called banana bread», DEV-I v4w I-w18-t3 «¿me la
    guardas en una nota con esas cantidades?», DEV-F v4w F-w34-t3, DEV-G v4w G-w29-t4): the content of a note that
    points at BAXY's words other than its last reply alone (``semantic.notes.pointed_note_content``), verbatim, with
    the note's title when one is known and said — the decider's, the readers', or the one the person wrote. None when
    the last reply is the one meant: M67 offers it to the extraction as before."""

    if operation != "note.create":
        return None
    properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    contract = properties.get("title")
    title_schema = {"type": "object", "properties": {"title": contract}, "required": ["title"], "additionalProperties": False}
    decided = [value for name, value, _ in _decided_fields(operation, request, schema, said) or () if name == "title"]
    read = [arguments["title"]] if isinstance(arguments, dict) and isinstance(arguments.get("title"), str) else []
    titles = [
        title for title in (*decided, *read, note_title_given(person))
        if isinstance(title, str) and title.strip() and isinstance(contract, dict)
        and validate_argument_grounding({"title": title}, title_schema, said)
    ]
    title = titles[0] if titles else None
    content = pointed_note_content(person, title or "", _conversation_exchanges(history))
    return (content, title) if content is not None else None


def _decided_arguments_alone(
    operation: str, request: str, tool: dict, trusted_source: str, *, previous_reply: str | None = None,
) -> dict[str, Any] | None:
    """The decider's values when they ground every required field and the operation's own normalization."""

    schema = tool["function"]["parameters"]
    decided = _with_decided_arguments(
        operation, request, {}, schema, trusted_source, previous_reply=previous_reply,
    )
    if decided is None:
        return None
    grounded = normalize_grounded_arguments(decided, schema, trusted_source)
    if grounded is None:
        return None
    return _normalize_grounded_operation_arguments(operation, grounded, request)


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

    if operation == "notification.schedule" and (change := semantic_temporal.notification_change(evidence)) is not None:
        # M58 (v3d-final F-s019, F-s044, F-s095): the new time of a moved alarm, timer or reminder, its kind and what
        # it is for, read from the change the person asked for; the cancellation is its own step. M62 (v3e2-final
        # F-s044 «…from 3 to 4»): with neither clock saying its part of the day, the new one takes the part of the day
        # the old one was said with earlier in this conversation; with none said, it is asked.
        said_before = [
            str(item.get("content") or "")
            for item in reversed(history if isinstance(history, list) else [])
            if isinstance(item, dict) and item.get("content") != evidence
        ]
        part_of_day = semantic_temporal.change_part_of_day(change, said_before)
        if part_of_day is None and change.clocks_lack_the_part_of_day():
            # D61 sets a new hour without its part of the day at the next time it comes; a moved one is read against
            # the old one, so with neither said it is still asked (M62), never moved by the clock.
            return None
        moved = change.schedule_arguments(part_of_day)
        moved = _normalize_grounded_operation_arguments(operation, moved, moved["dueUtc"])
        return moved if moved is not None and validate_json_schema_instance(moved, schema) else None
    if operation == "web.search":
        reference = _reference_lookup(evidence, history)
        if reference is not None:
            # M53: the reader supplies the class word the provider reads («receta», «resumen»), as the news reader
            # supplies «noticias» below; the referent is the person's own words.
            looked_up = {"query": reference.query}
            if validate_json_schema_instance(looked_up, schema):
                return looked_up
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
    if explicit is None and operation in {"notification.schedule", "reminder.create"}:
        return _timed_task_arguments(operation, evidence, history, schema)
    if operation == "weather.current" and explicit is not None and explicit.get("location") is None:
        # M58 (v3d-final F-w15-t1): the weather clause says «allá»; the place is the one the whole message says the
        # person is going to («me voy a San Antonio»). Never this PC's town in its place.
        there = weather_destination_there(evidence)
        if there is not None:
            explicit = {**explicit, "location": there}
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
    if operation == "web.search" and explicit.get("query") == effect_intent.public_opinion_query(evidence):
        # M96 (held-out conv-v3v t14 «averiguá qué dijo la crítica» after «anoche vi Oppenheimer…», restated «¿Qué
        # dijo la crítica de Oppenheimer?»): the opinion reader supplies «opiniones»/«reviews» like the news reader
        # supplies «noticias», and the work is the person's words; the literal check dropped the query and the turn
        # asked the restatement back («¿Qué crítica específica…?»).
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
    if operation == "notification.list" and explicit == {"limit": 50} and semantic_temporal.plural_alarm_cancellation(
        evidence
    ):
        # M62 (v3e2-final F-s040): the offer of every alarm reads as many as the catalog lets it; the bound is the
        # reader's, not a number the person says.
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
        "media.play.exact",
        "media.play.query",
        "media.play.youtube",
        # D39 (M58): the clock reader of a cancellation owns hour, minute and period; «las 7:05» grounded
        # its minute as the literal «5», which «05» never is, and the minute was dropped (7:00 cancelled).
        "notification.cancel.at",
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


def _timed_task_arguments(
    operation: str, evidence: str, history: object, schema: dict[str, object],
) -> dict[str, object] | None:
    """M58 (v3d-final F-s011 «Reanudar el ejercicio en 5 minutos, mejor en 10 minutos» → «¿cuándo y en qué
    formato?»): a thing to do at a time, said with no alarm or reminder noun, for an operation already decided to be a
    notification. It is a reminder of that thing at the one time kept (the last of a corrected pair), read from the
    request or, when the restatement lost it, from the person's own message."""

    said = [evidence]
    if isinstance(history, list):
        said += [
            str(item.get("content") or "") for item in reversed(history)
            if isinstance(item, dict) and item.get("role") == "user"
        ][:1]
    found_in, task = next(
        (
            (text, found) for text in said
            # M76 (DEV-D v3l D-s120): a rest of a stated length is timed too («un descanso de 14 minutos»).
            if (found := semantic_temporal.timed_task(text) or semantic_temporal.timed_break(text)) is not None
        ),
        ("", None),
    )
    if task is None:
        return None
    arguments: dict[str, object] = {"dueUtc": task.due, "title": task.title}
    if operation == "notification.schedule":
        arguments["kind"] = task.kind
    # M137 (DEV-G v4n G-s016, DEV-F v4m F-w55-t1): the advance «recordámelo una hora antes» is read from the message.
    arguments = _normalize_grounded_operation_arguments(operation, arguments, task.due, said=found_in)
    return arguments if arguments is not None and validate_json_schema_instance(arguments, schema) else None


def _person_message(history: object, objective: str) -> str:
    """The person's own message of this turn: the history's last turn when it is theirs (the shell sends it last),
    otherwise the objective."""

    last = history[-1] if isinstance(history, list) and history else None
    if isinstance(last, dict) and last.get("role") == "user" and str(last.get("content") or "").strip():
        return str(last["content"])
    return objective


def _unschedulable_time_question(
    llm: object,
    operation: str,
    objective: str,
    person: str,
    tool: dict,
    response_language: str | None,
    *,
    now: datetime | None = None,
) -> str:
    """M80 (DEV-D v3m D-s104 «Programa una alarma nueva para la cena a las 18:00 hoy.» at 19:35 → «¿Cuál es la hora
    exacta, qué tipo de recordatorio y qué título…?»; D-s108 «Set a 'wake-up' alarm for Monday, Tuesday and Wednesday of
    this week for 7am» on a Tuesday → «What time… and what should the title be?»): the time, the kind and what it is for
    were said; one notification cannot ring at that moment (today's clock already past, several days). Only when it
    rings is asked, saying why. Empty when the moment said is one a notification holds."""

    if operation not in {"notification.schedule", "reminder.create"}:
        return ""
    now = now or datetime.now().astimezone()
    unschedulable = next(
        (found for text in dict.fromkeys((objective, person))
         if (found := semantic_temporal.unschedulable_time(text, now)) is not None),
        None,
    )
    if unschedulable is None:
        return ""
    clock = unschedulable.clock
    if not unschedulable.ahead and len(unschedulable.passed) == 1:
        ask = (
            f"only when it should ring instead: the {clock} of {unschedulable.passed[0]} the person asked for already "
            f"passed (it is {now:%H:%M} now); say that first, then ask for another day or another time; "
            "the time, the kind and what it is for were already said, never ask them"
        )
    else:
        days = ", ".join((*unschedulable.passed, *unschedulable.ahead))
        passed = (
            f"; {', '.join(unschedulable.passed)} of this week already passed (it is {now:%A %H:%M} now)"
            if unschedulable.passed else ""
        )
        ask = (
            f"only which one day it should ring: one alarm or reminder rings at a single moment and the person named "
            f"several days ({days}) at {clock}{passed}; say that first; the time, the kind and what it is for were "
            "already said, never ask them"
        )
    language = {"response_language": response_language} if response_language else {}
    question = llm.formulate_missing_argument_question(objective, "", tool, ("dueUtc",), **language, ask_as={"dueUtc": ask})
    several = bool(unschedulable.ahead) or len(unschedulable.passed) != 1
    if question and not _says_why_unschedulable(question, several=several):
        # M93 (DEV-D v3u D-s104 at 19:23 → «¿A qué día o hora diferente te gustaría que suene la alarma?»): the question
        # did not say that 18:00 had passed, and «diferente» of what was never said. Asked again once, told so.
        retried = llm.formulate_missing_argument_question(
            objective, "", tool, ("dueUtc",), **language,
            ask_as={"dueUtc": f"{ask}. Your question «{question}» did not say why: open with that short reason, "
                              "then ask"},
        )
        if retried:
            question = retried
    return question


# M93: a question about when that says why the moment said cannot hold (folded).
_UNSCHEDULABLE_PASSED = (
    r"\bya\s+pas\w*|\bpas(?:o|aron|ado|ada|ados|adas)\b|\balready\b|\bpassed\b|\bis\s+(?:past|over|gone)\b|"
    r"\bhas\s+gone\b|\bearlier\s+than\s+now\b"
)
_UNSCHEDULABLE_SEVERAL = (
    r"\bvari[oa]s\s+dias\b|\bmas\s+de\s+un\s+dia\b|\bun\s+solo\b|\bsolo\s+(?:un|una|puede)\b|\bsolo\s+suena\b|"
    r"\bseveral\s+days\b|\bmore\s+than\s+one\s+day\b|\bsingle\b|\bonly\s+(?:one|once|rings)\b|\bone\s+(?:day|time|moment)\b"
)


def _says_why_unschedulable(question: str, *, several: bool) -> bool:
    folded = read_fold(question)
    pattern = _UNSCHEDULABLE_PASSED + ("|" + _UNSCHEDULABLE_SEVERAL if several else "")
    return re.search(pattern, folded) is not None


_TASK_CHANGE_FIELDS = ("title", "details", "due")


def _edited_task_arguments(
    llm: object,
    objective: str,
    person: str,
    tool: dict,
    edited: dict[str, object],
    said: str,
    response_language: str | None,
) -> tuple[dict | None, str]:
    """M80 (DEV-D v3m D-p06-t2, D-p06-t3 «Change that from bacon to eggs.» → «Which task…?», D-p08-t3 «No, cámbialo
    a la lista Comida» → «¿Cuál es el título de la tarea y cuál es la fecha límite?»): task.update replaces every
    editable field, so a change of the task this conversation just made or changed takes its identity, its version
    and every field the person did not change from what the store verified (``DialogueState.edited_task``); only what
    changes is read from what was said (the readers first, else the model, each value grounded in what was said).
    (None, "") when nothing here decides it; (None, question) asks what to change."""

    schema = tool["function"]["parameters"]
    properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    changes: dict[str, object] = {}
    for text in dict.fromkeys((person, objective)):
        changes = dict(task_change(text, str(edited["title"])))
        if changes:
            break
    if not changes:
        changes_schema = {
            "type": "object",
            "properties": {name: properties[name] for name in _TASK_CHANGE_FIELDS if name in properties},
            "required": [],
            "additionalProperties": False,
        }
        changes_tool = {"type": "function", "function": {**tool["function"], "parameters": changes_schema}}
        extraction = llm.extract_direct_arguments(
            objective, changes_tool, **({"response_language": response_language} if response_language else {}),
        )
        changes = _said_optional_arguments(extraction.arguments, changes_schema, said)
    if isinstance(changes.get("due"), str):
        # M115: a day said with no clock is the task's day, as the store reads it.
        due = _canonical_due_utc(str(changes["due"]), objective) or semantic_temporal.task_due_date(str(changes["due"]))
        if due is None:
            changes.pop("due")
        else:
            changes["due"] = due
    changes = {name: value for name, value in changes.items() if value != edited.get(name)}
    if not changes:
        return None, llm.formulate_missing_argument_question(
            objective, "", tool, ("title",),
            **({"response_language": response_language} if response_language else {}),
            ask_as={"title": (
                f"only what to change in «{edited['title']}» (its name or the list it is on); the task is the one "
                "just made, never ask which one"
            )},
        )
    arguments = {name: edited[name] for name in ("taskId", "expectedVersion", *_TASK_CHANGE_FIELDS)} | changes
    return (arguments, "") if validate_json_schema_instance(arguments, schema) else (None, "")


def _retimed_step_arguments(
    operation: str, retimed: dialogue_slot.RetimedNotification, schema: dict[str, object],
) -> dict[str, object] | None:
    """M76: the arguments of one step of moving the notification just set, or None for another step."""

    if operation == "notification.cancel.latest":
        arguments: dict[str, object] | None = {"kind": retimed.kind}
    elif operation == "notification.cancel.at" and retimed.cancel_at_request:
        # The clock is read as a cancellation reads it; the kind is the one verified (a reminder is not an alarm).
        arguments = _ground_explicit_arguments(operation, retimed.cancel_at_request, schema)
        arguments = {**arguments, "kind": retimed.kind} if arguments is not None else None
    elif operation == "notification.schedule":
        due = retimed.schedule_arguments["dueUtc"]
        read_at = retimed.read_at.astimezone(timezone.utc) if retimed.read_at is not None else None
        arguments = _normalize_grounded_operation_arguments(
            operation, dict(retimed.schedule_arguments), due, now_utc=read_at,
        )
    else:
        return None
    return arguments if arguments is not None and validate_json_schema_instance(arguments, schema) else None


def _with_conversation_place(
    operation: str, arguments: object, history: object, schema: dict[str, object],
) -> object:
    """M58 (v3d-final F-p05-t3, F-p06-t3): a place named alone in a place search or a weather read carries the town
    the conversation already fixed for it (``semantic.web.place_fixed_by_conversation``); what the message names with
    its own town, or anything else, is left as it came."""

    if not isinstance(arguments, dict) or not isinstance(history, list):
        return arguments
    # The last message of the person is this turn's own; the town comes from the ones before it.
    said_before = [
        str(item.get("content") or "") for item in reversed(history)
        if isinstance(item, dict) and item.get("role") == "user"
    ][1:]
    placed = dict(arguments)
    if operation == "web.search" and isinstance(arguments.get("query"), str) and not arguments.get("nearby"):
        query = place_query_in_conversation(arguments["query"], said_before)
        if query is None:
            return arguments
        placed["query"] = query
    elif operation == "weather.current" and isinstance(arguments.get("location"), str):
        town = place_fixed_by_conversation(arguments["location"], said_before)
        if town is None:
            return arguments
        placed["location"] = f"{arguments['location']}, {town}"
    else:
        return arguments
    return placed if validate_json_schema_instance(placed, schema) else arguments


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
    said: str | None = None,
) -> dict[str, Any] | None:
    """Apply closed semantic constraints not expressible by catalog JSON Schema. ``said``: the person's message the
    moment was read from, when ``context`` is only that moment (M137)."""

    normalized = dict(arguments)
    if operation == "weather.current" and isinstance(normalized.get("location"), str) and names_this_place(
        normalized["location"]
    ):
        # M76 (DEV-D v3l D-s054): «aquí» is this PC's place, read by the weather with no place named.
        del normalized["location"]
    if operation == "window.resolve":
        # M55 (v3b F-w06-t1, F-w08-t1 «invalid selector»): Core's selector contract is exactly one of
        # applicationName or process, and an application name takes neither byTitle nor offset. A neutral
        # byTitle=false or offset=0 beside a name is dropped; two selectors (two windows read into one
        # step) or none is never sent to fail in the Core.
        if "applicationName" in normalized:
            if normalized.get("byTitle") is False:
                normalized.pop("byTitle")
            if normalized.get("offset") == 0:
                normalized.pop("offset")
        if ("applicationName" in normalized) == ("process" in normalized) or (
            "applicationName" in normalized and ("byTitle" in normalized or "offset" in normalized)
        ):
            return None
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
    if operation == "task.create" and isinstance(normalized.get("due"), str):
        # M115 (DEV-F v4e2 F-s022, v4d F-w39-t3 «…para el jueves» → «el sistema la considera inválida»): the store reads
        # a day or a moment; what was said of it is written so, and a day nobody can tell is left out.
        due = _canonical_due_utc(normalized["due"], context, now_utc=now_utc) or semantic_temporal.task_due_date(
            normalized["due"], today=now_utc.astimezone().date() if now_utc is not None else None,
        )
        if due is None:
            normalized.pop("due")
        else:
            normalized["due"] = due
    if operation in {"notification.schedule", "reminder.create"}:
        raw_due = normalized.get("dueUtc")
        if not isinstance(raw_due, str):
            return None
        # M137 (DEV-G v4n G-s016, G-s019; DEV-F v4m F-w55-t1): «remind me an hour before» of the moment said in the
        # same message rings that long before it, titled with what happens then; the readers read the event's moment.
        advanced = due_before_said_moment(
            raw_due, normalized.get("title"), context, context if said is None else said, now_utc=now_utc,
        )
        if advanced is not None and advanced[0] is None:
            return None
        if advanced is not None:
            due_utc = advanced[0]
            if isinstance(advanced[1], str) and advanced[1]:
                normalized["title"] = advanced[1]
        else:
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


def _evidence_of_expected_operations(
    expected: tuple[str, ...],
    recognized: tuple[str, ...],
    evidence: tuple[str, ...],
) -> tuple[str, ...] | None:
    """The readers' clause for each effect the turn decided, or None when they read another request."""

    if recognized == expected:
        return evidence
    # M103 (owner script t36 «abre steam y ve a la biblioteca»): the readers add a look before the click
    # (input.visible.controls, H0096) on the click's own clause; the turn decided open + click. Dropping a step that
    # only repeats a kept step's clause loses nothing the person said, so the kept clauses still ground the steps.
    kept: list[str] = []
    cursor = 0
    for index, operation in enumerate(recognized):
        if cursor < len(expected) and operation == expected[cursor]:
            kept.append(evidence[index])
            cursor += 1
    if cursor != len(expected):
        return None
    dropped = [evidence[index] for index, operation in enumerate(recognized) if operation not in expected]
    if any(clause not in kept for clause in dropped) or len(dropped) + len(kept) != len(recognized):
        return None
    return tuple(kept)


# M145: the window changes that lose nothing and may act on the window in front; closing is never one (M118).
_FRONT_WINDOW_CHANGES = frozenset(
    {"window.maximize", "window.minimize", "window.move", "window.restore", "window.snap"}
)


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
                if (operation == "app.close" and closes_the_active_window(literal_evidence))
                # M145 (DEV-G v4p G-s041 «pasame esta ventana a la mitad izquierda», decided «Coloca la ventana
                # activa en la mitad izquierda…», G-s082, G-s102; DEV-H H-s028): a change that loses nothing of the
                # window in front reads that window (window.active), as «maximizá esta ventana» already did; a
                # window.resolve had no application to look for, and the plan ended «no se pudo determinar cómo».
                or (operation in _FRONT_WINDOW_CHANGES and names_the_window_in_front(literal_evidence))
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
        # D61: «no, mejor a las 7:20» to a question about «ponme una alarma a las 7 pa mañana» replaces the hour the
        # request said; joined after it, the hour of 1 to 12 left without its part of the day (no longer asked) would
        # stand next to the new one.
        replaced = dialogue_slot.corrected_request(slot.pending_request, objective)
        replaced_effects = effects_of(replaced) if replaced is not None else ()
        if replaced_effects and dialogue_slot.same_family(replaced_effects, effects_of(slot.pending_request)):
            return audited(replaced, "pattern")
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


# M84: the operations a moment counted from BAXY's last answer is set with (``semantic.temporal.anchored_offset_request``).
_ANCHORED_SCHEDULE_OPERATIONS = frozenset({"notification.schedule", "reminder.create", "calendar.event.create"})
# M89: the reads of what is installed on this PC (never the newest published release).
_INSTALLED_SOFTWARE_READS = frozenset({"software.python.status", "software.python.package.status", "app.installed"})
# M103: the reads a decider chooses for «¿qué estoy viendo en <reproductor>?» (the media session, a window state).
_SHOWN_MEDIA_READS = frozenset({"media.status", "window.application.status", "window.active", "window.resolve"})


def _clock_read_request(text: str, history: object) -> str | None:
    """The request as a read of this PC's clock, when the readers prove one (M85): the time of another place (with
    «allá» said as the place of the person's last clock question) or this clock some minutes or hours later."""

    folded = effect_intent._fold(text)
    if semantic_temporal.clock_elsewhere(folded) is not None or semantic_temporal.clock_later_asked(text) is not None:
        return text
    prior = [
        str(turn.get("content") or "")
        for turn in (history if isinstance(history, list) else [])
        if isinstance(turn, dict) and turn.get("role") == "user" and str(turn.get("content") or "").strip() != text.strip()
    ]
    return semantic_temporal.clock_there_request(text, prior)


def _close_of_the_just_opened(
    text: str,
    history: object,
    available_operations: tuple[str, ...],
    application_names: tuple[str, ...] | ApplicationCatalogIndex,
) -> semantic_decider.ContextDecision | None:
    """M96 (held-out t11 «cerralo» after «abrí el bloc de notas», 28/30 oscillating: the decider asked «¿Quieres que
    cierre el Bloc de notas?» in five of seven runs). A bare close pronoun right after the person asked to open one
    application closes that application, by its name; with two or more opened it asks which. Never the window in
    front (2026-09-22: «cerralo» read as the active window closed VS Code). None when the request before it opened
    nothing: the decider reads the turn as before."""

    pronoun, english = bare_close_pronoun(effect_intent._fold(text))
    if not pronoun or "app.close" not in available_operations:
        return None
    slot = dialogue_slot.read_slot({}, history, text)
    antecedent = next((said for said in slot.antecedents if not dialogue_slot.is_social(said)), None)
    read = resolve_explicit_effects(antecedent, available_operations, application_names) if antecedent else None
    opened = [said for operation, said in zip(read.operations, read.evidence) if operation == "app.open"] if read else []
    if not opened:
        return None
    # With one opened: the person's own words for it («el bloc de notas») first, then the name the open reader kept.
    named_forms = (dialogue_slot.antecedent_object(antecedent), opened[0]) if len(opened) == 1 else ()
    for named in dict.fromkeys(filter(None, named_forms)):
        request = close_request_for_opened(named, english)
        closing = resolve_explicit_effects(request, available_operations, application_names)
        if closing is not None and closing.operations == ("app.close",):
            return semantic_decider.ContextDecision(request=request, decision="action", operations=("app.close",),
                                                    question="")
    return semantic_decider.ContextDecision(request=text, decision="clarify", operations=(), question="")


# M99: the operations whose object is a part of this PC that a request has to name (the keyboard's language, the
# desktop's background, a routine that fires on a phrase): the decider bringing it is not the person asking for it
# («hazme saber cuando escuches sobre España» restated as a routine that takes screenshots). Measured on the reserve
# replay; a wider set (the family gates of every operation) refused hundreds of reads the decider got right.
_OBJECT_NAMED_OPERATIONS = frozenset({"input.keyboard.layout", "desktop.wallpaper.set", "routine.phrase.create"})
_CLOCK_SET_OPERATIONS = frozenset({"notification.schedule", "reminder.create", "calendar.event.create", "timer.start"})
_REMINDER_OPERATIONS = frozenset({"notification.schedule", "reminder.create"})


def _decider_says_the_anchored_moment(decided: semantic_decider.ContextDecision, anchored: str) -> bool:
    """M144 (DEV-H v4p H-w44-t2 «remind me twenty minutes before that» after «Kick-off is at 8pm.»: the decider's «Remind
    me at 7:40pm tonight about the Arsenal match.» was replaced by «remind me at 19:40», titled «remind me»): when the
    decider's action says the same one clock and the same day the count from the conversation gives, its request stands
    (D58) and keeps what the reminder is for; the count only overrules a moment it does not confirm."""

    if decided.decision != "action" or not decided.operations or not set(decided.operations) <= _ANCHORED_SCHEDULE_OPERATIONS:
        return False

    def moment(request: str) -> tuple[list[tuple[int, int]], str | None]:
        clocks = semantic_temporal.spoken_clocks(effect_intent._fold(request))
        return [(clock.hour, clock.minute) for clock in clocks if clock.resolved], semantic_temporal.task_due_date(request)

    said, counted = moment(decided.request), moment(anchored)
    # «tonight» and no day said are the same day.
    today = {None, datetime.now().astimezone().date().isoformat()}
    return len(said[0]) == 1 and said[0] == counted[0] and (said[1] == counted[1] or {said[1], counted[1]} <= today)


def _clock_completes_the_last_request(text: str, history: object, available_operations: tuple[str, ...]) -> bool:
    """M144 (DEV-H v4p H-w06-t4 «a las 3» after «recuérdame comprar tinto para la oficina», which BAXY answered by
    noting a task, → «¿Qué quieres que haga exactamente a las 3?»): the person's last message asked for a reminder or an
    alarm without its hour (what the readers would ask of it, ``due_time``/``alarm_time``); a clock said alone next is
    that hour, whether or not BAXY asked for it."""

    earlier = _prior_user_texts(history, text)
    if not earlier:
        return False
    asked = resolve_explicit_clarification_intent(earlier[-1], available_operations)
    return (
        asked is not None
        and bool({"due_time", "alarm_time"} & set(asked.missing_fields))
        and set(asked.operations) <= _CLOCK_SET_OPERATIONS
    )


def _reminder_day_without_clock(
    decided: semantic_decider.ContextDecision, text: str, available_operations: tuple[str, ...],
) -> effect_intent.ClarificationIntent | None:
    """M144: the hour a reminder the decider set lacks, when its restatement says the day and what it is for and neither
    it, the message nor the decider's values say a clock or a delay: what the readers ask of the same request said
    first (``due_time``). None otherwise."""

    if not decided.operations or not set(decided.operations) <= _REMINDER_OPERATIONS:
        return None
    folded = effect_intent._fold(text)
    if (
        semantic_temporal.spoken_clocks(folded)
        or semantic_temporal.said_only_a_clock(text)
        or semantic_temporal.said_durations(text)
        or semantic_temporal.alarm_for_hour(folded) is not None
    ):
        return None
    if any(
        # A moment the decider gave at an hour other than midnight was read from somewhere («a la misma hora»).
        isinstance(value, str) and re.search(r"T(?!00:00)\d{2}:\d{2}", value)
        for _, value in decided.arguments
    ):
        return None
    asked = resolve_explicit_clarification_intent(decided.request, available_operations)
    if asked is None or asked.missing_fields != ("due_time",) or not set(asked.operations) <= _REMINDER_OPERATIONS:
        return None
    return asked


def _decided_domain_unnamed(
    operations: tuple[str, ...],
    text: str,
    history: object,
    application_names: tuple[str, ...] | ApplicationCatalogIndex,
    available_operations: tuple[str, ...],
) -> bool:
    """M99 (reserva A6 «empezar ted en español» → «Cambia el idioma del teclado a español.», «enséñame un color suave» →
    «Cambia el fondo de escritorio…»): the decider's restatement named the thing its operation acts on, and neither the
    message nor anything the person said before names it. The curated family gates (``operation_domain_is_grounded``,
    one-sided) are the readers' measure of that; False on every message of the person is an act nobody asked for."""

    said = [text, *(
        str(turn.get("content") or "")
        for turn in (history if isinstance(history, list) else [])
        if isinstance(turn, dict) and turn.get("role") == "user"
    )]
    previous = next((item for item in reversed(said[1:]) if item.strip() and item.strip() != text.strip()), None)
    return bool(operations) and any(
        operation in _OBJECT_NAMED_OPERATIONS
        and all(
            operation_domain_is_grounded(
                item, operation, application_names,
                previous_user_text=previous, available_operations=available_operations,
            ) is False
            for item in dict.fromkeys(said)
        )
        for operation in operations
    )


def _decider_catalog(
    planner_catalog: PlannerCatalog,
) -> tuple[tuple[tuple[str, str], ...], dict[str, tuple[str, ...]]]:
    """The operations the contextual decider reads, and the argument fields of each."""

    tools = planner_catalog.decider_tools
    return (
        tuple((tool.name, tool.description) for tool in tools),
        {tool.name: semantic_decider.argument_signature(tool.schema) for tool in tools},
    )


def _warm_context_decider(llm: Any, planner_catalog: PlannerCatalog) -> None:
    """M117: the decider's catalog prompt is read into its slot when the catalog is configured (``warm_decider``)."""

    warm = getattr(llm, "warm_decider", None)
    if warm is None:
        return
    decider_tools, signatures = _decider_catalog(planner_catalog)
    warm(decider_tools, signatures=signatures)


def _prepare_context_decision(llm: Any, message: dict[str, Any], planner_catalog: PlannerCatalog) -> None:
    """M117: ask the contextual decider for this message now, beside the readers (``LlmRuntime.prepare_decision``).

    ``_context_decided_result`` sends the same message with the same catalog, so the prepared reply is the one it
    would have waited for; a turn a conversation reader keeps never reads it.
    """

    prepare = getattr(llm, "prepare_decision", None)
    if prepare is None:
        return
    decider_tools, signatures = _decider_catalog(planner_catalog)
    prepare(str(message.get("text", "")), message.get("history") or [], decider_tools, signatures=signatures)


# M151 (DEV-F/G/H v4s F-w18-t2, F-w22-t3, F-w24-t3, G-w40-t2, G-w40-t3, G-w44-t5, H-w23-t3, H-w32-t2): what the decider
# chose to open, find or read a file with when the file is the one BAXY's last reply named.
_NAMED_FILE_OPERATIONS = frozenset({
    "file.open", "filesystem.file.open.latest", "filesystem.known.search", "document.pdf.read", "document.text.read",
})


def _conversation_named_file(
    decided: semantic_decider.ContextDecision,
    text: str,
    history: list[Any],
    available_operations: tuple[str, ...],
) -> semantic_decider.ContextDecision | None:
    """M151 (D58): the file BAXY's last reply named by its file name, when the person asks what it says or picks it
    from the ones it listed (``semantic.files.named_file_meant``), is read with the reader its extension takes, or
    opened, where the conversation said it is — not opened when what it says was asked, nor the newest file, nor a
    search, nor another file of a similar name. Only a decision that opens, finds or reads a file changes, and only to
    that one file; a decision of that operation on that same file stays the decider's. None when nothing changes."""

    if decided.decision != "action" or not decided.operations or not set(decided.operations) <= _NAMED_FILE_OPERATIONS:
        return None
    earlier = _prior_user_texts(history, text)
    meant = named_file_meant(text, _previous_reply(history) or "", earlier[-1] if earlier else "")
    operation = named_file_operation(meant) if meant is not None else None
    if meant is None or operation is None or operation not in available_operations:
        return None
    conversation = [str(item.get("content") or "") for item in history if isinstance(item, dict)]
    folder = conversation_file_folder(meant.name, conversation)
    if folder is None or (operation == "file.open" and folder == "all_known"):
        return None
    stem = effect_intent._fold(meant.name.rsplit(".", 1)[0])
    if decided.operations == (operation,) and any(
        isinstance(value, str) and effect_intent._fold(value).strip() in {stem, effect_intent._fold(meant.name)}
        for _, value in decided.arguments
    ):
        return None
    language = _read_reply_language(text, history) or _decisive_request_language(_previous_reply(history) or "")
    return semantic_decider.ContextDecision(
        named_file_request(meant, folder, language or "es"), "action", (operation,), "",
    )


def _context_decided_result(
    message: dict[str, Any],
    *,
    llm: Any,
    planner_catalog: PlannerCatalog,
    on_limit: Callable[[str], dict[str, Any] | None] | None = None,
    application_names: tuple[str, ...] | ApplicationCatalogIndex = (),
    overheard: bool = False,
    decided_beforehand: semantic_decider.ContextDecision | None = None,
) -> dict[str, Any]:
    """The turn as the contextual decider reads it (``semantic.decider``), with the whole conversation.

    Fase 3.5b F2–F4: with the conversation in front of it, the model decides a turn better than the readers,
    the shortlist, the native selector and the gates together; the readers keep only the first message of a
    conversation they prove. The restated request travels as ``objective``: the arguments step reads it.
    ``overheard``: the first message reads as talk the microphone caught (``semantic.guards._overheard_speech``);
    only when the decider asks is the question the overheard one (M118). ``decided_beforehand``: the decider was
    already asked about this message (M123: after a reader whose reading it did not confirm); it is not asked twice.
    """

    text = str(message.get("text", ""))
    history = message.get("history") or []
    available_operations = tuple(tool.name for tool in planner_catalog.tools)
    context = dialogue_slot.read_slot({}, history, text)
    antecedent = context.antecedents[0] if context.antecedents else None
    placed = dialogue_slot.place_substituted(text, antecedent)
    placed_read = resolve_explicit_effects(placed, available_operations) if placed is not None else None
    closing = _close_of_the_just_opened(text, history, available_operations, application_names)
    said_before = [
        str(turn.get("content") or "") for turn in reversed(history)
        if isinstance(turn, dict) and str(turn.get("content") or "") != text
    ]
    offered = semantic_temporal.accepted_notification_offer(
        text, context.last_reply,
    ) or semantic_temporal.answered_timer_length(text, context.last_reply, said_before)
    offered_read = resolve_explicit_effects(offered, available_operations) if offered is not None else None
    if offered_read is not None and not set(offered_read.operations) <= _ANCHORED_SCHEDULE_OPERATIONS:
        offered_read = None
    taken_back = (
        semantic_temporal.cancelled_notification_just_set(text, context.last_reply) if offered_read is None else None
    )
    taken_back_read = resolve_explicit_effects(taken_back, available_operations) if taken_back is not None else None
    if taken_back_read is not None and taken_back_read.operations == ("notification.cancel.latest",):
        # M113 (DEV-F v4d F-w45-t4 «scratch the garlic knots one» after «Done, 12-minute timer for the garlic knots.» →
        # task.delete): the notification BAXY just reported setting, taken back by what it is for, is the latest one.
        offered, offered_read = taken_back, taken_back_read
    read_before_decider = (
        closing is not None
        or offered_read is not None
        or (placed_read is not None and placed_read.operations == ("system.time",))
    )
    if closing is not None:
        decided = closing
    elif offered_read is not None:
        # M110 (DEV-F v4d F-w33-t4 «Yeah, go on» after «Shall I move the alarm to 17:00?» → «What time is the Spurs
        # game?»; F-w45-t3 «go with 12…» after «How long for the garlic knots?»): the yes to BAXY's offer of a
        # notification at one time, or the length that answers its «how long?», is that notification, read as one
        # request.
        decided = semantic_decider.ContextDecision(
            request=str(offered), decision="action", operations=tuple(offered_read.operations), question="",
        )
    elif read_before_decider:
        # M84 (DEV-D v3o D-w02-t2 «y si allá son las 10 de la mañana acá qué hora es» after «qué hora es en madrid» →
        # restated «¿Qué hora es en Madrid si allá son las 10…?» and talked): «allá» is the place just asked, and the
        # time said there is converted on the clock read (``_place_clock_facts``), never by the decider.
        decided = semantic_decider.ContextDecision(request=placed, decision="action", operations=("system.time",),
                                                   question="")
    else:
        if decided_beforehand is not None:
            decided = decided_beforehand
        else:
            decider_tools, signatures = _decider_catalog(planner_catalog)
            decided = llm.decide_in_context(text, history, decider_tools, signatures=signatures)
        memory = next((op for op in decided.operations if op.startswith("memory.")), None)
        if memory is not None and not any(
            explicit_memory_request(said) for said in (text, _previous_user_request(history, text) or "")
        ):
            # M118 (reserve v4g after M114 put memory back in the decider's catalog: «mis contactos son mayormente
            # masculinos o femeninos», «lugares de vacaciones», «cuando se acerca el cumpleaños de mi amigo», «give me
            # petey's telephone number» → memory.recall, 9 of 25 breaks): BAXY's memory is the person's explicit request
            # only (memory instrument). A memory choice nobody asked for is not the request: what else the decider chose,
            # else what the readers prove in the message, else it is asked — what only the person knows is asked (M81),
            # and a personal fact said without asking to keep it is asked about before it is kept (the App's AskToSave).
            others = tuple(op for op in decided.operations if not op.startswith("memory."))
            read = resolve_explicit_effects(text, available_operations, application_names) if not others else None
            if others:
                decided = semantic_decider.ContextDecision(
                    decided.request, "action", others, decided.question, decided.arguments,
                )
            elif read is not None and not any(op.startswith("memory.") for op in read.operations):
                decided = semantic_decider.ContextDecision(text, "action", tuple(read.operations), "")
            else:
                decided = semantic_decider.ContextDecision(text, "clarify", (), "")
        elif memory is not None:
            # M114: memory is the App's own path (an explicit request, its confirmation); the mind never plans it with
            # other steps, so the decider's memory choice travels alone and the App answers it.
            decided = semantic_decider.ContextDecision(
                decided.request, "action", (memory,), decided.question, decided.arguments,
            )
    # M64 (v3f-final F-w14-t3): which fields the decider filled, never their values, so a turn whose arguments went
    # wrong can be told apart from one whose decider gave none.
    argument_fields = [name for name, _ in decided.arguments]
    closes_a_pronoun = bare_close_pronoun(effect_intent._fold(text))[0]
    if (
        decided.decision == "action"
        and (_deictic_open_request(text) or deictic_close_request(effect_intent._fold(text)) or closes_a_pronoun)
        and (
            not dialogue_slot.restatement_was_said(
                decided.request,
                [text, *(str(turn.get("content") or "") for turn in history if isinstance(turn, dict))],
            )
            # M118 (safety; cien-113 008 «cierra aquello» with nothing before it → «Cierra la ventana activa.» →
            # window.active and app.close of the Notepad in front, stopped only by the App's confirmation; 2026-09-22
            # «cerralo» closed VS Code): a pronoun is never the window in front.
            or (closes_a_pronoun and names_the_active_window(decided.request))
        )
    ):
        # Fase 3.5b M19 (cien-104 «ábreme eso porfa» after the time → «Abre el navegador» → a browser opened): a
        # pointer with no antecedent in what was said is asked, never filled with an object the model brought.
        decided = semantic_decider.ContextDecision(request=text, decision="clarify", operations=(), question="")
    # M154 (DEV-I v4u I-s053 «…a cuánto cerró el blue hoy que tengo que cambiar unos dólares…», H-s093 «…rate todya,
    # im wiring money to my cousin…», I-s078 «mi viejo me preguntó cuántos habitantes tiene Mar del Plata…»): the need
    # that makes the person ask, said after the question, and who asked or claims it, said before, are its context too.
    question_asked = question_with_context(text) or question_with_its_reason(text)
    if decided.decision == "action" and decided.operations == ("web.search",) and (
        names_own_data(text)
        if question_asked is None
        # M138 (DEV-G v4n G-w42-t1 «when do the Lakers play next? my buddy wants to come over and watch it» → asked
        # what only the person knows, where the isolated decider looked the game up): what is said after the question
        # is its context. Only the question, and what the decider would look up, are read for the person's own data.
        else names_own_data(question_asked)
        or names_own_data(decided.request)
        or any(isinstance(value, str) and names_own_data(value) for _, value in decided.arguments)
    ):
        # M81 (DEV-D v3m D-s020 «It's going to rain en la casa de mamá?», D-s053 «¿Miguel sigue viviendo en
        # Arkansas?»): the person's own data never goes to the web (00_IDENTIDAD, invariant 6). What only the person
        # knows (where mom lives, who Miguel is) is asked, never looked up.
        decided = semantic_decider.ContextDecision(request=text, decision="clarify", operations=(), question="")
    if (
        decided.decision == "action"
        and decided.operations
        and set(decided.operations) <= _INSTALLED_SOFTWARE_READS
        and "web.search" in available_operations
        and asks_latest_release(text)
    ):
        # M89 (DEV-D v3r D-w20-t3 «btw what's the latest version of Python right now?» → «Están instaladas las versiones
        # 3.13.3, 3.12.10 y 3.10.0»): the newest release is public and looked up; the copy on this PC is not it.
        decided = semantic_decider.ContextDecision(request=text, decision="action", operations=("web.search",), question="")
    if (
        decided.decision == "action"
        and decided.operations
        and set(decided.operations) <= {"task.search", "notification.list.due"}
        and "calendar.event.list" in available_operations
        and names_own_event(text)
    ):
        # M100 (reserva A1 «what time is the black tie gala dinner supposed to begin», «con quién me encuentro yo hoy»
        # → task.search; «meeting reminders from three to five» → the internal due step): an event of the person's, or
        # who they meet, is read from their calendar.
        decided = semantic_decider.ContextDecision(
            request=decided.request, decision="action", operations=("calendar.event.list",), question="",
        )
    if (
        decided.decision == "action"
        and decided.operations == ("notification.list.due",)
        and "notification.list" in available_operations
        and not asks_overdue_notifications(text)
    ):
        # M110 (DEV-F v4d F-w45-t5 «and the pizza, how many minutes till I pull it out?» → the reminders already due,
        # «The pizza reminder is not set yet.»): what is still to ring is in the list of what is scheduled; the due
        # read is for the ones that already rang.
        decided = semantic_decider.ContextDecision(
            request=decided.request, decision="action", operations=("notification.list",), question="",
        )
    if (
        "window.resolve" in available_operations
        and (decided.decision in {"talk", "clarify"} or set(decided.operations) <= _SHOWN_MEDIA_READS)
        and application_shown_media_name(text, application_names) is not None
    ):
        # M103 (owner script t22 «¿Sabes qué peli estoy viendo en potplayer?» → media.status read Spotify): what a named
        # player shows is its window's title; with no window of it open, the read says so.
        decided = semantic_decider.ContextDecision(request=text, decision="action", operations=("window.resolve",), question="")
    clock_request = (
        _clock_read_request(text, history)
        if decided.decision in {"talk", "clarify"} and "system.time" in available_operations
        else None
    )
    if clock_request is not None:
        # M85 (DEV-D v3o D-w02-t2 «y si allá son las 10 de la mañana acá qué hora es» after «qué hora es en madrid»,
        # D-s025 «si pasan cuarenta minutos, ¿qué hora será?»): a clock the readers prove — another place's, «allá»
        # being the place of the clock question before, or this clock later on — is this PC's clock read (system.time
        # converts and adds), never an hour the writer says from memory.
        decided = semantic_decider.ContextDecision(
            request=clock_request, decision="action", operations=("system.time",), question="",
        )
    unasked_action: dict[str, Any] | None = None
    if decided.decision == "action":
        slot = dialogue_slot.read_slot({}, history, text)
        unasked = None
        if dialogue_slot.is_social(text):
            # M65 (conv-v3g owner script t37 «Perfecto muy bien» after a question BAXY composed → «Abre Steam y entra
            # a la biblioteca.» and Steam opened): thanks, praise or a closing asks for nothing and answers no
            # question, whatever is pending. An offer BAXY holds is confirmed by the shell, never through here.
            unasked = "social"
        elif "input.text.type" in decided.operations and not semantic_ui.asks_to_type(
            text, slot.last_reply, slot.antecedents[0] if slot.antecedents else None,
        ):
            # M65 (conv-v3g owner script t30 «Di la palabra"algo"» → «Escribe la palabra «algo».»): saying is not
            # typing into the window in front; nothing in the message or the question it answers asks to write.
            unasked = "untyped"
        elif _decided_domain_unnamed(decided.operations, text, history, application_names, available_operations):
            unasked = "unnamed_domain"
        elif dialogue_slot.offers_to_baxy(text):
            # M99 (reserva A6 «quieres netflix and chill» → Netflix opened): something offered to BAXY orders nothing.
            unasked = "offer"
        elif (
            set(decided.operations) & _CLOCK_SET_OPERATIONS
            and semantic_temporal.said_only_a_clock(text)
            and not str(slot.last_reply or "").rstrip().endswith("?")
            and not _history_has_pending_clarification(history, message.get("pendingClarification"))
            and not _clock_completes_the_last_request(text, history, available_operations)
        ):
            # M99 (reserva A6 «las dos menos cuarto» → an alarm at 10:15): a clock said alone, answering no question of
            # BAXY's, sets nothing; what it is for is asked.
            unasked = "bare_clock"
        if unasked is not None:
            unasked_action = {"kind": unasked, "request": decided.request, "operations": list(decided.operations)}
            decided = semantic_decider.ContextDecision(
                # M99 (reserva A6): an act on a thing nobody named, or a clock said alone, is asked about.
                request=text, decision="clarify" if unasked in {"unnamed_domain", "bare_clock"} else "talk",
                operations=(), question="",
            )
    # M64 (v3f-final F-w01-t4 «…el mistral de 35» restated «…Mistral de 350 ml…», F-s054 «…mañana en Santiago?»): a
    # number, unit, date, clock time or name of the restatement nobody said never travels as the objective.
    descriptions = {tool.name: tool.description for tool in planner_catalog.tools}
    fidelity = semantic_decider.faithful_request(
        decided.request,
        text,
        [str(turn.get("content") or "") for turn in history if isinstance(turn, dict)],
        world=[semantic_decider.catalog_line(op, descriptions.get(op, "")) for op in decided.operations],
    )
    decider_request = decided.request
    if fidelity.kind != "kept":
        decided = semantic_decider.ContextDecision(
            fidelity.request, decided.decision, decided.operations, decided.question, decided.arguments,
        )
    edited_draft = (
        effect_intent.edited_draft_request(text, list(_prior_user_texts(history, text)))
        if decided.decision != "action" and "message.draft" in available_operations
        else None
    )
    if edited_draft is not None:
        # M111 (DEV-F v4d F-w01-t4 «mejor cámbialo, ponle que llego como 10 minutos tarde…» → «No puedo cambiar el
        # mensaje…»): new words for the message just left written are that draft again, to the same person in the same
        # client; leaving a message written is never a limit.
        decided = semantic_decider.ContextDecision(
            request=edited_draft, decision="action", operations=("message.draft",), question="",
        )
    if (
        decided.decision == "action"
        and "message.send" in decided.operations
        and "message.draft" in available_operations
        and effect_intent.asks_not_to_send(text)
    ):
        # M155 (safety exception to D58; DEV-I v4u I-s061 «… but leave it for me to send»): a message the person orders
        # not to send is left written, never sent, whoever read it — the readers no longer prove a send for it
        # (``resolve_explicit_effects``), and the decider's send is held the same way. Its words are read again from
        # the message (``message.draft`` arguments).
        decided = semantic_decider.ContextDecision(decided.request, "action", ("message.draft",), decided.question)
    clock_cancelled = (
        semantic_temporal.clock_named_cancellation(text, decided.request)
        if decided.decision == "action"
        and decided.operations == ("notification.cancel.latest",)
        and "notification.cancel.at" in available_operations
        else None
    )
    if clock_cancelled is not None:
        # M158 (safety exception to D58; DEV-I v4u/v4v I-w26-t4 «cancela la de las 7 que mañana no trabajo» after a list
        # of eleven alarms and reminders → «cancela la última alarma», and the last one set, not the one at 7, was
        # cancelled): the alarm or reminder the person names by its clock is the one at that clock
        # (``notification.cancel.at``), never the last one set whatever it is. When the last one this conversation set
        # is the one at that clock, M145 (``_own_notification_cancellation``) makes it the latest again. A move
        # (cancel.latest with schedule) and a cancellation that names no clock stay as decided.
        decided = semantic_decider.ContextDecision(clock_cancelled, "action", ("notification.cancel.at",), "")
    if (
        decided.decision == "action"
        and len(decided.operations) == 1
        # The moments of alarms and reminders keep their own readers (``semantic.temporal``).
        and not set(decided.operations) & (_CLOCK_SET_OPERATIONS | {"notification.cancel.at"})
    ):
        restated = resolve_explicit_effects(decided.request, available_operations, application_names)
        if (
            restated is not None
            and 1 < len(restated.operations) <= 8
            and set(restated.operations) == set(decided.operations)
        ):
            # M111 (DEV-F v4d F-s015 «¿Me abres la calculadora y el Bloc de notas?» → «Abre la Calculadora y el Bloc
            # de notas.» with one app.open, and only the Calculator opened): the restatement names the operation as
            # many times as the readers read it; each one is a step.
            decided = semantic_decider.ContextDecision(
                decided.request, "action", tuple(restated.operations), decided.question, decided.arguments,
            )
    named_file = _conversation_named_file(decided, text, history, available_operations)
    if named_file is not None:
        # M151 (DEV-F v4s F-w18-t2 «Yeah, that's the one, give us the gist of it» after «Downloads is open; I can see
        # «council_tax_2026-27.pdf»…» → file.open; DEV-G v4s G-w40-t2 «abre el segundo» after «Encontré dos: …» → the
        # newest file): the file BAXY just named, or the one of those it listed that the person picked, is the one read
        # or opened.
        decided = named_file
    # M110: the thing named («la junta», «kick-off») may have its moment further back in the conversation.
    anchored = semantic_temporal.anchored_offset_request(
        text, context.last_reply, said_before,
        # M113 (DEV-F v4d F-w18-t3 «Remind me the day before the first one's due, nine in the morning»): days counted
        # from a date said earlier in the conversation.
    ) or semantic_temporal.anchored_day_request(text, context.last_reply, said_before) or (
        # M148 (DEV-G v4r G-w19-t4 «pues salgo sobre las 6 de la tarde…» after «recuérdamelo veinte minutos antes de
        # salir» → «¿A qué hora tienes pensado salir?» → set at 18:00): the moment the answer gives, less the advance the
        # request asked, is when it rings.
        semantic_temporal.answered_advance_request(text, context.pending_request, context.last_reply)
    )
    anchored_read =resolve_explicit_effects(anchored, available_operations) if anchored is not None else None
    if (
        anchored_read is not None
        and set(anchored_read.operations) <= _ANCHORED_SCHEDULE_OPERATIONS
        and not _decider_says_the_anchored_moment(decided, str(anchored))
    ):
        # M84 (DEV-D v3o D-w08-t3 «ponme recordatorio una ora antes d ese partido» → «¿Cuándo es ese partido?», D-w02-t3
        # «ponme una alarma media hora antes de eso» → «Pon una alarma a las 10:30.»): the moment BAXY just gave, less
        # or plus the duration, is the time; the readers read the request that says it, the decider's is not used.
        decided = semantic_decider.ContextDecision(anchored, "action", tuple(anchored_read.operations), "")
    if (
        decided.decision == "action"
        and anchored_read is None
        and set(decided.operations) <= {"notification.schedule", "reminder.create"}
        and (
            (
                fidelity.kind == "person"
                and any(semantic_temporal.spoken_clocks(effect_intent._fold(what)) for what in fidelity.introduced)
                and not semantic_temporal.spoken_clocks(effect_intent._fold(text))
                and not semantic_temporal.said_only_a_clock(text)
                and not semantic_temporal.said_durations(text)
            )
            # M152 (DEV-G v4s G-w19-t3 «vale, pues recuérdamelo veinte minutos antes de salir» restated «Recuérdame en
            # 20 minutos que tengo que ir al aeropuerto.» → set at 21:20, so G-w19-t4 «pues salgo sobre las 6 de la
            # tarde…» answered no question and was set at 21:20 again): the message says a length, but counted from a
            # moment nobody placed; the restatement that made it a delay from now is a time nobody said either.
            or semantic_temporal.advance_restated_as_delay(text, decider_request)
        )
    ):
        # M110 (DEV-F v4d F-w46-t3 «poneme una alarma para ese día bien temprano» restated «…el sábado 2 de octubre a
        # las 5:00» → «¿Cuándo y con qué título…?» as an action): the time was the decider's, not the person's, and the
        # message says none; when it rings is asked.
        decided = semantic_decider.ContextDecision(request=text, decision="clarify", operations=(), question="")
    day_only = (
        _reminder_day_without_clock(decided, text, available_operations)
        if decided.decision == "action" and anchored_read is None
        else None
    )
    if day_only is not None:
        # M144 (DEV-H v4p H-w32-t4 «no era eso, quería que me lo pongas de recordatorio el jueves» restated «Ponme un
        # recordatorio el jueves para inscribirme a las Jornadas…» → «¿Cuándo, día y hora, quieres que te lo
        # recuerde?»): a reminder with its day and what it is for but no hour asks only the hour, as the same request
        # said first asks it (``resolve_explicit_clarification_intent``); the restatement stays the objective, so the
        # answer completes it. Nothing rings at a midnight nobody said.
        decided = semantic_decider.ContextDecision(
            request=decided.request,
            decision="clarify",
            operations=decided.operations,
            question=llm.formulate_explicit_clarification_question(
                decided.request, decided.operations, day_only.missing_fields,
            ),
        )
    if decided.decision == "action" and anchored_read is None:
        asked = resolve_explicit_clarification_intent(text, available_operations)
        if (
            asked is not None
            and "list_entries" in asked.missing_fields
            and set(asked.operations) & set(decided.operations)
            # M89 (DEV-D v3r D-p37-t2): entries the person said just before, which BAXY's question was about, were said.
            and not list_entries_said_before(text, antecedent, context.last_reply)
            # M91 (reserva «haz una nueva lista de la compra»): a list asked for new is complete when it is made; only
            # an entry that names nothing is missing a value.
            and not list_creation_said(effect_intent._fold(text))
        ):
            # M84 (DEV-D v3o D-p17-t3 «nevermind add an item to my swimming list» → «Add swimming to my list.», and
            # «swimming» was added): the readers prove the entry was not said (M80); the list's name is never its
            # entry, and the decider's restatement does not fill it.
            decided = semantic_decider.ContextDecision(request=text, decision="clarify", operations=(), question="")
    if (
        decided.decision == "action"
        and "email.latest.reply" in decided.operations
        and latest_mail_reply_without_words(text)
    ):
        # M100 (reserva A13 «that last email needs to be answer a. s. a. p.» → answered «a. s. a. p.»): a reply goes
        # with the words the person said, never with how soon or with the restatement's; with none, what to answer is
        # asked.
        decided = semantic_decider.ContextDecision(
            request=text, decision="clarify", operations=("email.latest.reply",), question="",
        )
    if decided.decision != "limit" and asks_to_watch_the_news(text):
        # M104 (reserve v3z es631 «establecer notificaciones para las noticias sobre el gasoducto sur peruano» → a
        # notification scheduled for nothing): watching the news to tell when there is some is no operation; the
        # limit says so, never a notice nobody can fill. D59 §6 (owner, 2026-10-02): whatever was decided (today's
        # headlines read, a talk, a question about the time), and the limit offers to search the news now (the
        # «news_watch_limit» shape).
        decided = semantic_decider.ContextDecision(request=text, decision="limit", operations=(), question="")
    if decided.decision == "limit" and dialogue_slot.takes_back(text, antecedent):
        # M84 (DEV-D v3o D-p01-t3 «no, cancel», D-p14-t3 «Cancelar foto» → «No cancelo la foto.»): taking back what was
        # just asked is said to BAXY, never a limit of cancelling.
        decided = semantic_decider.ContextDecision(request=text, decision="talk", operations=(), question="")
    if decided.decision == "limit" and (dialogue_slot.is_assent(text) or dialogue_slot.gives_go_ahead(text)):
        # M102 (DEV-D v3z D-p24-t4 «Yes, do it for me.» after «The streaming of Hustlers failed because Netflix requires a
        # sign-in on this PC…» → «I do not handle tasks outside my scope.»): a yes or a go-ahead asks for nothing new, so
        # it is never a limit; what stands in the way (the failure just told, or nothing waiting for the yes) is said in
        # talk, with the conversation in front of the writer (M88 holds it to saying nothing was done).
        decided = semantic_decider.ContextDecision(request=text, decision="talk", operations=(), question="")
    if decided.decision in {"talk", "limit"} and dialogue_slot.do_that_with_nothing_named(text, context.last_reply):
        # M118 (cien-113 048 «haz eso» after «keep chatting without opening apps»: the decider talked and the writer
        # invented «no tengo la capacidad de mantener conversaciones…»): «do that» with nothing to do named before it
        # is asked («¿Qué es eso?»), never answered or refused.
        decided = semantic_decider.ContextDecision(request=text, decision="clarify", operations=(), question="")
    if decided.decision == "clarify" and dialogue_slot.remate_of_what_was_done(text, context.last_reply):
        # M118 (owner script t57 «al volumen» after «He puesto el volumen en 100…» → «¿Cuánto le subo?»; conv-v3z2
        # talked): naming only what was just done asks nothing again; it is answered as the remate it is.
        decided = semantic_decider.ContextDecision(request=text, decision="talk", operations=(), question="")
    # cien-107 100: with a block of history the decider answered «talk» («Write a letter to Eris.»), the knowledge
    # contract let «…because I do not have access to external communication channels…» through; talk is bounded too.
    if decided.decision in {"clarify", "talk"} and effect_intent.out_of_world_request(text):
        # cien-105/106 «post a letter to Eris» → «What should the letter say?», vetoed by the App as a question about
        # what cannot be done: the boundary of an unreachable place holds here too (apply_out_of_world_boundary).
        decided = semantic_decider.ContextDecision(request=text, decision="limit", operations=(), question="")
    if decided.decision == "limit" and conversation_only_content_request(text):
        # M78 (DEV-D v3l p35-t1 «…análisis de FODA…» refused): content written in the conversation (an analysis, a
        # letter, code) is what BAXY does; a limit on it is false.
        decided = semantic_decider.ContextDecision(request=decided.request, decision="talk", operations=(), question="")
    if (
        decided.decision in {"limit", "talk"}
        and "web.search" in available_operations
        and asks_what_a_cinema_shows(text)
    ):
        # M99 (DEV-D v3x D-p28-t1 «I want to watch a movie at Century 25 Union Landing…» → «I cannot order or buy
        # movies…»): what a cinema shows is looked up; the limit was about buying, which nobody asked.
        decided = semantic_decider.ContextDecision(request=text, decision="action", operations=("web.search",), question="")
    converted = (
        currency_conversion_request(text, decided.request, context.last_reply or "", antecedent or "")
        if decided.decision == "talk" and "web.search" in available_operations and not asks_for_code(text)
        else None
    )
    if converted is not None:
        # M154 (D35, D52; DEV-H v4u H-w05-t4 «and in pesos chilenos?» after «Hoy el Bitcoin está en 85.000 dólares.» →
        # talked «Today Bitcoin is at 1,850,000 Chilean pesos.»; H-s087 «¿cuánto son 350 dólares en euros, más o
        # menos?» → «Son aproximadamente 320 euros.»): an amount in another currency, or an exchange rate, moves every
        # day; it is looked up (the reference rate, ``FrankfurterRateSource``), with the amount and the currencies said
        # in the conversation (``semantic.web.currency_conversion_request``). A rate of what BAXY said in one currency
        # (M118: «¿y eso cuánto es al mes?») names no second currency and stays the decider's.
        decided = semantic_decider.ContextDecision(
            request=converted, decision="action", operations=("web.search",), question="",
        )
    reference = None
    recommended = False
    # M56 (v3c-final F-w14-t1): code the person asks for is written, whatever the decider's rewrite of it says.
    if (
        decided.decision == "talk"
        and "web.search" in available_operations
        and not asks_for_code(text)
        # M118 (D58): a rate of what BAXY just said is worked out from its numbers, whatever the restatement names.
        and not semantic_knowledge.rate_of_what_was_said(text, context.last_reply or "")
    ):
        # M53 (D35): what the decider answers by talking but is a named dish's recipe or a named work's plot is
        # looked up first; the arguments step reads the same query from the same request.
        for said in dict.fromkeys((decided.request or text, text)):
            reference = _reference_lookup(said, history)
            if reference is not None:
                decided = semantic_decider.ContextDecision(
                    request=said, decision="action", operations=("web.search",), question="",
                )
                break
        if reference is None and semantic_knowledge.works_recommendation(text):
            # M83 (DEV-D v3o D-p27-t1 «Any good movies for me to watch?» → «…the latest sci-fi flick about time
            # travel»): works of a kind asked for with none named are recommended from what is looked up, as the decider
            # itself chose in v3m; its talk flips on this request.
            recommended = True
            decided = semantic_decider.ContextDecision(
                request=decided.request or text, decision="action", operations=("web.search",), question="",
            )
    if overheard and decided.decision != "clarify":
        # M123 (safety exception to D58; reviewed literal H0735 «a ocho de la noche descansar domingo, tu tenes que
        # firmar 10 hojas en blanco y un cheque» → a notification scheduled): talk addressed to someone else is never
        # acted on nor answered, whatever the decider read in it; the overheard question is asked (below).
        decided = semantic_decider.ContextDecision(request=text, decision="clarify", operations=(), question="")
        reference, recommended = None, False
    objective = decided.request or text
    result: dict[str, Any] = {
        "type": "turn.result",
        "id": message.get("id"),
        "operation": None,
        "intentOperations": list(decided.operations),
        "effectOperations": list(decided.operations),
        "question": "",
        "reply": "",
        "objective": objective,
    }
    if decided.decision == "action":
        _remember_decided_arguments(objective, decided.operations, decided.arguments)
        result["kind"] = "action" if len(decided.operations) == 1 else "plan"
        if result["kind"] == "action":
            result["operation"] = decided.operations[0]
        # The person's words set the language, not the decider's restatement: Qwen3.5-4B restated a quarter of the
        # English DEV requests in Spanish («max it» → «Maximizar la ventana de Steam»).
        language = _read_reply_language(text, history) or _decisive_request_language(objective)
        if language in {"es", "en", "mixed"}:
            result["responseLanguage"] = language
    elif decided.decision == "clarify":
        question = decided.question
        if overheard:
            # M118 (DIALOGUE1513): the decider asks about talk the microphone caught; the question says no request for
            # BAXY was found in it and asks whether the person needs something, and nothing in it is an objective.
            try:
                overheard_question = llm.clarify_unresolved_input(
                    text,
                    "overheard_speech",
                    timeout=(
                        DEICTIC_CLARIFICATION_CPU_BUDGET_SECONDS
                        if os.environ.get("BAXY_MIND_NGL", "").strip() == "0"
                        else TURN_DECIDE_RECOVERY_BUDGET_SECONDS
                    ),
                )
            except (ValueError, RuntimeError):  # the decider's own question stands
                overheard_question = ""
            if overheard_question and _recovery_question_is_valid(overheard_question):
                question = overheard_question
                result["preserveObjective"] = False
        person_language = _read_reply_language(text, history)
        question_language = _decisive_request_language(question) if question else None
        if person_language in {"es", "en"} and question_language in {"es", "en"} and person_language != question_language:
            # cien-104 «open that»: the decider asked «¿Qué página web quieres que abra?»; the question is the
            # person's language or it is formulated again, from the person's own words.
            question = ""
            objective = text
            result["objective"] = text
        if not (
            _recovery_question_is_valid(question, objective, history) and _recovery_question_is_valid(question, text)
        ):
            question = llm.clarify_after_turn_failure(objective, history=history, timeout=2.5)
            if not (_recovery_question_is_valid(question) and _recovery_question_is_valid(question, text)):
                raise PlannerContractError("aclaración del decisor inválida")
        result["kind"] = "clarify"
        result["question"] = question
    else:
        if decided.decision == "limit" and on_limit is not None:
            # M78: the decider's restatement (after the fidelity check) is re-read with the message.
            reread = on_limit(decided.request or "")
            if reread is not None:
                _append_turn_audit(
                    {
                        "schema": "baxy.mind-turn-audit.v1",
                        "request_id": message.get("id"),
                        "phase": "served_surface_reread",
                        "decision_path": "context_decider",
                        "raw_decision": {"mode": decided.decision, "request": decided.request},
                        "reread_objective": reread.get("objective"),
                    }
                )
                return reread
        kind = "unsupported" if decided.decision == "limit" else "knowledge"
        # Talk and limits have no request for the shell to plan, confirm or resume.
        result.pop("objective", None)
        language = _read_reply_language(text, history)
        if language is None:
            try:
                language = llm.detect_response_language(text)
            except ValueError:
                language = None
        reply, _ = llm.chat(
            text,
            **_conversation_reply_arguments(
                history,
                conversation_kind=kind,
                response_language=language,
                scoped=False,
                intent_operations=[],
                available_operations=available_operations,
            ),
        )
        if not reply.strip():
            raise PlannerContractError("no se pudo preparar una respuesta conversacional")
        result.update(kind="conversation", conversationKind=kind, reply=reply.strip())
        if language in {"es", "en", "mixed"}:
            result["responseLanguage"] = language
    _append_turn_audit(
        {
            "schema": "baxy.mind-turn-audit.v1",
            "request_id": message.get("id"),
            "phase": "final",
            "decision_path": "context_decider",
            "candidate_operations": list(available_operations),
            "raw_decision": {
                "mode": "talk" if reference is not None or recommended else decided.decision,
                "request": decided.request,
                "effect_operations": [] if reference is not None or recommended else list(decided.operations),
                "argument_fields": argument_fields,
                **({} if unasked_action is None else {"unasked_action": unasked_action}),
                **(
                    {}
                    if fidelity.kind == "kept"
                    else {
                        "decider_request": decider_request,
                        "fidelity": {"kind": fidelity.kind, "introduced": list(fidelity.introduced)},
                    }
                ),
            },
            "stages": (
                [{"name": "reference_looked_up", "kind": reference.kind, "query": reference.query}]
                if reference is not None
                else [{"name": "recommendation_looked_up"}] if recommended else []
            ),
            "decider_timings": None if read_before_decider else getattr(llm, "_last_decider_timings", None),
            "final": {
                "kind": result["kind"],
                "intent_operations": result["intentOperations"],
                "effect_operations": result["effectOperations"],
            },
        }
    )
    return result


_MOVED_NOTIFICATION_PLAN = ("notification.cancel.latest", "notification.schedule")


def _moved_notification_result(message: dict[str, Any], request: str) -> dict[str, Any]:
    """M102: the turn that moves the notification just set — cancel the latest of its kind and set it again — as the
    plan the shell runs, with ``request`` (``DialogueState.moved_notification_request``) as its objective."""

    result: dict[str, Any] = {
        "type": "turn.result",
        "id": message.get("id"),
        "kind": "plan",
        "operation": None,
        "intentOperations": list(_MOVED_NOTIFICATION_PLAN),
        "effectOperations": list(_MOVED_NOTIFICATION_PLAN),
        "question": "",
        "reply": "",
        "objective": request,
    }
    language = _read_reply_language(str(message.get("text", "")), message.get("history") or [])
    if language in {"es", "en", "mixed"}:
        result["responseLanguage"] = language
    _append_turn_audit(
        {
            "schema": "baxy.mind-turn-audit.v1",
            "request_id": message.get("id"),
            "phase": "final",
            "decision_path": "moved_notification",
            "raw_decision": {"mode": "action", "request": request, "effect_operations": list(_MOVED_NOTIFICATION_PLAN)},
            "stages": [],
            "final": {
                "kind": "plan",
                "intent_operations": list(_MOVED_NOTIFICATION_PLAN),
                "effect_operations": list(_MOVED_NOTIFICATION_PLAN),
            },
        }
    )
    return result


def _cancelled_clock(text: str, schema: dict[str, object]) -> dict[str, object] | None:
    """M145: the clock and kind a cancellation in ``text`` selects, as ``notification.cancel.at``'s arguments: of a
    move («Cambia la alarma de las 7 a las 7:30»), the old clock; of a cancellation, its own. A move that names no old
    clock is of the last one set: its kind alone, with ``hour`` None. None without a kind and an hour."""

    change = semantic_temporal.notification_change(text)
    if change is not None:
        if change.old is None:
            return {"kind": change.kind, "hour": None}
        text = change.cancel_request()
    selected = _ground_explicit_arguments("notification.cancel.at", text, schema)
    if not isinstance(selected, dict) or not isinstance(selected.get("hour"), int) or selected.get("kind") not in {
        "alarm", "reminder",
    }:
        return None
    return selected


def _own_notification_cancellation(
    result: dict[str, Any],
    message: dict[str, Any],
    dialogue_state: dialogue_slot.DialogueState | None,
    tool_by_name: dict[str, dict],
) -> dict[str, Any]:
    """M145 (DEV-H v4p H-w29-t2 «no espera, mejor a las 7:30» after «…¿me pones una alarma a las 7 porfa?» → «varias
    alarmas o recordatorios a esa misma hora… no se pudieron distinguir»; H-w45-t4 «cancel the 7 one»): the store also
    held alarms of other conversations at 19:00, and ``notification.cancel.at`` refuses two at one clock. When the clock
    this turn cancels (or moves from) is that of the alarm, timer or reminder this conversation set and verified, and
    it is the last one it set of its kind (``DialogueState.own_notification_at``), the cancellation is of that one: the
    latest BAXY set of its kind (``notification.cancel.latest``). Without one of its own there, the turn stays as it
    was decided and the ambiguity is told as before."""

    if dialogue_state is None or result.get("kind") not in {"action", "plan"}:
        return result
    effects = [str(operation) for operation in result.get("effectOperations") or ()]
    tool = tool_by_name.get("notification.cancel.at")
    if (
        effects.count("notification.cancel.at") != 1
        or "notification.cancel.latest" in effects
        or "notification.cancel.latest" not in tool_by_name
        or tool is None
    ):
        return result
    schema = tool["function"]["parameters"]
    selected = next(
        (
            found for found in (
                _cancelled_clock(str(result.get("objective") or ""), schema),
                _cancelled_clock(_person_message(message.get("history"), str(message.get("text", ""))), schema),
            )
            if found is not None
        ),
        None,
    )
    if selected is None or not dialogue_state.own_notification_at(
        str(selected["kind"]), selected["hour"], int(selected.get("minute") or 0),
        selected.get("period") if selected.get("period") in {"am", "pm"} else None,
    ):
        return result

    def own(operations: object) -> list[str]:
        return [
            "notification.cancel.latest" if operation == "notification.cancel.at" else str(operation)
            for operation in operations or ()
        ]

    kept = {**result, "effectOperations": own(effects), "intentOperations": own(result.get("intentOperations"))}
    if kept.get("operation") == "notification.cancel.at":
        kept["operation"] = "notification.cancel.latest"
    _append_turn_audit(
        {
            "schema": "baxy.mind-turn-audit.v1",
            "request_id": message.get("id"),
            "phase": "final",
            "decision_path": "own_notification",
            "raw_decision": {"mode": "action", "request": kept.get("objective"), "effect_operations": kept["effectOperations"]},
            "stages": [],
            "final": {
                "kind": kept["kind"],
                "intent_operations": kept["intentOperations"],
                "effect_operations": kept["effectOperations"],
            },
        }
    )
    return kept


def _direct_arguments_result(
    message: dict[str, Any],
    *,
    llm: Any,
    tool: dict,
    application_names: tuple[str, ...] | ApplicationCatalogIndex = (),
    game_catalog: GameCatalogIndex = GameCatalogIndex(),
    dialogue_state: dialogue_slot.DialogueState,
) -> tuple[dict[str, Any] | None, str]:
    """The «arguments» request: the operation's grounded arguments, or None with the question for what is missing."""

    operation = str(message.get("operation", ""))
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
    said = _conversation_grounding_source(objective, message.get("history"))
    # M118 (D58): what the decider wrote in other words of what was said is said, and what it gave is never replaced by
    # the readers' reading of the same field.
    said = _with_decided_restatements(
        operation, str(message.get("text", "")), tool["function"]["parameters"], said,
    )
    said = _with_every_known_folder_unsaid(operation, tool["function"]["parameters"], said)
    if arguments is not None:
        arguments = _with_decider_values_kept(
            operation, str(message.get("text", "")), arguments, tool["function"]["parameters"], said,
        )
    turn_language = (
        message.get("responseLanguage") if message.get("responseLanguage") in {"es", "en", "mixed"} else None
    )
    person = _person_message(message.get("history"), objective)
    headline = dialogue_state.pointed_headline(person) if operation == "web.search" else None
    if headline is not None and validate_json_schema_instance(
        {"query": headline}, tool["function"]["parameters"],
    ):
        # M83 (DEV-D v3o D-w17-t5 «tell me more about the second one»): the headline pointed at by its
        # place in the news just read is looked up as it was written, never as the decider retold it.
        arguments = {"query": headline}
    if arguments is None:
        # M80 (DEV-D v3m D-s104, D-s108): a moment no notification holds asks only when, saying why.
        question = _unschedulable_time_question(
            llm, operation, objective, person, tool, turn_language,
        )
    if arguments is None and not question and operation == "message.draft":
        # M111 («mándaselo a Ana», «déjaselo escrito a Álvaro por WhatsApp»): the words are those of the message
        # written before in this conversation (the person's last draft, or BAXY's reply the person asked to write);
        # who it goes to is this message's.
        earlier = list(_prior_user_texts(message.get("history"), person))
        forwarded = effect_intent.forwarded_draft(
            person,
            earlier,
            _previous_reply(message.get("history")),
            bool(earlier) and (
                conversation_only_content_request(earlier[-1]) or effect_intent.asks_to_write_a_message(earlier[-1])
            ),
        )
        if forwarded is not None:
            candidate = {"channel": forwarded[0], "recipient": forwarded[1], "text": forwarded[2]}
            if validate_json_schema_instance(candidate, tool["function"]["parameters"]):
                arguments = candidate
    edited = dialogue_state.edited_task() if operation == "task.update" else None
    if arguments is None and not question and edited is not None:
        # M80 (DEV-D v3m D-p06-t2, D-p06-t3, D-p08-t3): what was not changed is kept from the verified task.
        arguments, question = _edited_task_arguments(
            llm, objective, person, tool, edited, said, turn_language,
        )
    # M141 (DEV-G v4o G-w06-t3 «guárdalo en un archivo que se llame suma.py» → «¿Cuál es el código…?»): when the
    # decider wrote BAXY's last reply (its code) as the content, that reply is the content verbatim and is said.
    last_reply = _previous_reply(message.get("history"))
    reply_written = (
        last_reply
        if _decided_reply_field(operation, str(message.get("text", "")), tool["function"]["parameters"], last_reply)
        else None
    )
    if reply_written is not None:
        said = f"{said}\n{reply_written}"
    # M160 (DEV-H v4w H-w11-t3 «save that whole thing as a note called banana bread» after the recipe and a temperature
    # → «What content should be saved…?»; DEV-F v4w F-w34-t3 «Guárdamela en una nota que se llame tortilla» → the
    # decider's «receta … para cuatro personas»): the note keeps BAXY's words the person points at, verbatim, when
    # they are not its last reply alone; with no title known, the extraction reads them in the last reply's place.
    pointed = None
    if not question:
        pointed = _pointed_note_content(
            operation, str(message.get("text", "")), person, message.get("history"), tool["function"]["parameters"],
            said, arguments,
        )
    if pointed is not None:
        said = f"{said}\n{pointed[0]}"
        candidate = {"title": pointed[1], "content": pointed[0]}
        if pointed[1] is not None and validate_json_schema_instance(candidate, tool["function"]["parameters"]):
            arguments = candidate
        else:
            arguments = None
    if arguments is None and not question and pointed is None and (
        reply_written is not None or not _previous_reply_may_be_content(tool, message.get("history"))
    ):
        # M42b: what the decider read, grounded in what was said, is enough on its own; the separate
        # extraction call runs only when a required value is still missing.
        arguments = _decided_arguments_alone(
            operation, str(message.get("text", "")), tool, said, previous_reply=reply_written,
        )
    if arguments is None and not question and operation in {"document.pdf.read", "document.text.read"}:
        # M127 (DEV-C v4i C-w10-t4): the PDF named by its file name earlier in the conversation is read where that
        # conversation said it is, never asked again. M151: a text file too.
        named = (conversation_pdf if operation == "document.pdf.read" else conversation_text_file)(
            objective,
            [str(item.get("content") or "") for item in message.get("history") or [] if isinstance(item, dict)],
        )
        if named is not None and validate_json_schema_instance(named, tool["function"]["parameters"]):
            arguments = named
    if arguments is None and not question:
        # M47 (FINAL F-w09-t5, F-p02-t3): the shell sends the language the turn decision chose; the
        # objective may be the decider's restatement in the other language, so it cannot decide it.
        response_language = message.get("responseLanguage")
        language_argument = (
            {"response_language": response_language}
            if response_language in {"es", "en", "mixed"}
            else {}
        )
        # M67 (FINAL F-w14-t3 «perfect, copialo al clipboard» after a ```sql answer, F-w15-t4 «save that
        # as a note porfa» after a packing list): the model reads BAXY's last reply beside the objective
        # and says whether it is the content; code copies it verbatim into that field.
        previous_reply = pointed[0] if pointed is not None else _previous_reply(message.get("history"))
        extraction = llm.extract_direct_arguments(
            objective,
            tool,
            stated_fields=_stated_argument_fields(
                operation, objective, tool["function"]["parameters"],
            ),
            **language_argument,
            **({"previous_reply": previous_reply} if previous_reply else {}),
        )
        if extraction.previous_reply_field and previous_reply:
            # The reply is literally what BAXY said (M43's trusted source), whole and not cut.
            objective_source = f"{objective}\n{previous_reply}"
            said = f"{said}\n{previous_reply}"
        else:
            objective_source = objective
        extracted = extraction.arguments
        if extracted is None:
            # M76 (DEV-D v3l D-p19-t1): an abstention keeps what the readers know, so what is asked is
            # only what is still missing (the service of a film named by its title).
            extracted = partial_explicit_arguments(
                operation, objective, tool["function"]["parameters"],
            ) or None
        decided_arguments = _with_decided_arguments(
            operation,
            str(message.get("text", "")),
            extracted,
            tool["function"]["parameters"],
            said,
            previous_reply=reply_written,
        )
        arguments, question = prepare_direct_argument_result(
            llm,
            objective,
            tool,
            extracted if decided_arguments is None else decided_arguments,
            # A question written before the decider's values were added may ask for one of them.
            extraction.fallback_question if decided_arguments is None else "",
            trusted_source=objective_source if decided_arguments is None else said,
            **language_argument,
        )
    arguments = _with_conversation_place(
        operation, arguments, message.get("history"), tool["function"]["parameters"],
    )
    arguments = _with_decided_part_of_day(operation, str(message.get("text", "")), arguments)
    arguments = _with_pointed_reminder_title(operation, person, message.get("history"), arguments)
    if operation in {"note.read", "note.trash"} and not (isinstance(arguments, dict) and arguments.get("noteId")):
        # M111 (DEV-F v4d F-w03-t6 «la nota del snippet, léemela» → note «Snippet» not found): a note named by a word
        # of the title it was given earlier in the conversation is that note.
        conversation = [
            str(item.get("content") or "") for item in message.get("history") or [] if isinstance(item, dict)
        ]
        titled = conversation_note_title(objective, conversation) or conversation_note_title(
            person, conversation,
        )
        candidate = {**(arguments if isinstance(arguments, dict) else {}), "title": titled}
        if titled is not None and validate_json_schema_instance(candidate, tool["function"]["parameters"]):
            arguments, question = candidate, ""
    if operation == "media.play.exact":
        arguments, question = _corrected_song_arguments(person, message.get("history"), arguments, question, tool)
    arguments = _as_the_person_spelled(operation, arguments, person, message.get("history"))
    if (
        operation == "note.create"
        and isinstance(arguments, dict)
        and note_content_unsaid(person, str(arguments.get("content") or ""))
    ):
        # M157 (M81; DEV-I v4v I-w37-t3 «oye, de paso, crea una nota de la junta de hoy» → content «Junta de hoy.», the
        # title again): a note the person named only by what it is about gets that as its title, and what it says is
        # asked, whoever wrote the title into the content (the decider, the extraction).
        arguments, question = None, llm.formulate_missing_argument_question(
            objective, "", tool, ("content",), **({"response_language": turn_language} if turn_language else {}),
        )
    return arguments, question


def _corrected_song_arguments(
    person: str, history: object, arguments: dict[str, Any] | None, question: str, tool: dict,
) -> tuple[dict[str, Any] | None, str]:
    """M127 (D58; DEV-F v4i F-w36-t2, F-w60-t2): «la otra, la de estudio / la del disco» plays the song the person asked
    for just before (``semantic.arguments.corrected_song_title``); a title that is part of that song, or holds it, is
    the model's and stays."""

    earlier = _prior_user_texts(history, person)
    song = corrected_song_title(person, earlier[-1], _previous_reply(history) or "") if earlier else None
    if song is None:
        return arguments, question
    title = arguments.get("title") if isinstance(arguments, dict) else None
    if isinstance(title, str) and title.strip():
        said, kept = effect_intent._fold(song), effect_intent._fold(title)
        if kept in said or said in kept:
            return arguments, question
    candidate = {**(arguments if isinstance(arguments, dict) else {}), "provider": "spotify", "title": song}
    if not validate_json_schema_instance(candidate, tool["function"]["parameters"]):
        return arguments, question
    return candidate, ""


def _prepare_turn_result(
    message: dict[str, Any],
    *,
    llm: Any,
    planner_catalog: PlannerCatalog,
    encoder: Callable[[Any], Any],
    tool_by_name: dict[str, dict],
    application_names: tuple[str, ...] | ApplicationCatalogIndex = (),
    game_catalog: GameCatalogIndex = GameCatalogIndex(),
    on_signal: PendingTurnSignal | None = None,
    dialogue_state: dialogue_slot.DialogueState | None = None,
) -> dict[str, Any]:
    """Prepare one side-effect-free turn result.

    A message inside a conversation keeps only the conversation readers; the rest is the contextual decider's,
    with the whole conversation. The first message of one goes through every reader first. ``dialogue_state`` is what the
    conversation left so far (the serve loop owns it); it is read, never written, here.
    """

    accepted_cancellation = (
        dialogue_state.accepted_alarm_cancellation(str(message.get("text", "")))
        # M103 (owner script t25): «te dije que investigues algo» after a search is that search again, said whole.
        or dialogue_state.insisted_search(str(message.get("text", "")))
        if dialogue_state is not None
        else None
    )
    if accepted_cancellation is not None:
        # D39 (owner, 2026-09-29): «sí» to «Tienes 3 alarmas (…). ¿Las cancelo todas?» is the cancellation of each
        # alarm read, said as one request («cancela la alarma de las 7:00 de la mañana y …») that every reader reads.
        history = list(message.get("history") or [])
        if history and isinstance(history[-1], dict) and history[-1].get("role") == "user":
            history[-1] = {**history[-1], "content": accepted_cancellation}
        result = _decide_turn_result(
            {**message, "text": accepted_cancellation, "history": history, "pendingObjective": None},
            llm=llm,
            planner_catalog=planner_catalog,
            encoder=encoder,
            tool_by_name=tool_by_name,
            application_names=application_names,
            game_catalog=game_catalog,
            on_signal=on_signal,
        )
        result.setdefault("objective", accepted_cancellation)
        return result
    if dialogue_slot.read_slot({}, message.get("history") or [], str(message.get("text", ""))).antecedents:
        moved = (
            dialogue_state.moved_notification_request(str(message.get("text", "")))
            if dialogue_state is not None
            else None
        )
        if moved is not None:
            # M102 (DEV-D v3z D-w18-t5 «wait no, make it una hora»): the notification the last turn set is moved
            # (cancelled and set again), never a second one beside it; the plan takes its arguments from the dialogue
            # state (``_retimed_step_arguments``).
            return _moved_notification_result(message, moved)
        # M145: a cancellation at the clock of the notification this conversation set is of that one.
        return _own_notification_cancellation(
            _decide_turn_result(
                message,
                llm=llm,
                planner_catalog=planner_catalog,
                encoder=encoder,
                tool_by_name=tool_by_name,
                application_names=application_names,
                game_catalog=game_catalog,
                on_signal=on_signal,
                in_conversation=True,
            ),
            message,
            dialogue_state,
            tool_by_name,
        )
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
    encoder: Callable[[Any], Any],
    tool_by_name: dict[str, dict],
    application_names: tuple[str, ...] | ApplicationCatalogIndex = (),
    game_catalog: GameCatalogIndex = GameCatalogIndex(),
    on_signal: PendingTurnSignal | None = None,
    served_surface: tuple[str, ...] | None = None,
    already_signaled: list[bool] | None = None,
    in_conversation: bool = False,
) -> dict[str, Any]:
    """Decide one side-effect-free turn result from the (rearmed) request.

    ``served_surface`` is None on the request as said and ``()`` on the re-read of its canonical surface
    (``_served_surface_reread``), which is never re-read again.
    ``in_conversation``: the message follows earlier turns. Only the conversation readers (talk,
    social acts, known limits) keep it, and only when what they read stands without the turn before
    (M112, ``_conversation_reader_keeps_followup``); everything else is the contextual decider's, which
    reads the whole conversation (Fase 3.5b F4: with the history, the effect and clarification readers
    lost more follow-ups than they proved).
    """
    already_signaled = [] if already_signaled is None else already_signaled
    if in_conversation:
        # M117: a follow-up is the contextual decider's unless a conversation reader keeps it; its decision starts
        # now, beside those readers. A first message the readers prove spends no decode.
        _prepare_context_decision(llm, message, planner_catalog)

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
    if (
        explicit_clarification is not None
        and served_surface is None
        and not in_conversation
        and set(explicit_clarification.operations) == {"media.play.query"}
        # A bare «pon música» asks what to play (reviewed literals H0009, H0066, H0526): nothing names it.
        and names_a_kind_of_music(objective)
    ):
        # M123 (D58; reserve against the isolated decider: es11335 «reproducir y reproduce aleatoriamente todas las
        # canciones de música lenta», es393 «pon una canción retro en mi playlist» were asked what to play where the
        # decider played what was named): music named by its kind is the contextual decider's to read first. Its
        # known error is to refuse or talk about the person's own music (the radio and the playlists the reader asks
        # about: 20 turns of limit); then the question below is asked. What it plays or asks is its decision, handed
        # over without asking it twice.
        decider_tools, signatures = _decider_catalog(planner_catalog)
        played = llm.decide_in_context(
            str(message.get("text", "")), message.get("history") or [], decider_tools, signatures=signatures,
        )
        if played.decision not in {"talk", "limit"}:
            return _context_decided_result(
                message, llm=llm, planner_catalog=planner_catalog, application_names=application_names,
                decided_beforehand=played,
            )
    if (
        explicit_clarification is not None
        and served_surface is None
        and not in_conversation
        and clarification_awaits_decider(explicit_clarification.missing_fields)
    ):
        # M126 (D58; reserve against the isolated decider, ``clarification_awaits_decider``): a question that never
        # fixed the decider and broke it where it was right waits for it; what it decides is the turn, handed over
        # without asking it twice.
        decider_tools, signatures = _decider_catalog(planner_catalog)
        return _context_decided_result(
            message, llm=llm, planner_catalog=planner_catalog, application_names=application_names,
            decided_beforehand=llm.decide_in_context(
                str(message.get("text", "")), message.get("history") or [], decider_tools, signatures=signatures,
            ),
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
        # M78 (DEV-D v3l p35-t1): content asked for («Has un análisis de FODA…», four sentences long) is addressed to
        # BAXY, never overheard speech to clarify.
        or content_drafting
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
        # M112 (DEV-F v4d w38-t1 «get me a large pepperoni with extra jalapeños from the Domino's on Elm St»): an order
        # addressed to BAXY is never overheard talk; what it asks (here a limit) is the contextual decider's.
        or effect_request_is_authoritative(objective)
    ):
        # Fase 3.5 (owner 2026-09-21, turns 156–167, 208): a long message right
        # after BAXY spoke is the person talking to BAXY, not a conversation the
        # microphone overheard (DIALOGUE1513's rows all arrive with no dialogue).
        unresolved_input_kind = None
    # M123 (safety exception to D58; the 742 reviewed literals on 853d821f: H0006, H0297, H0332, H0372, H0429, H0441,
    # H0483, H0610, H0694 answered as talk and H0735 «a ocho de la noche descansar domingo, tu tenes que firmar 10 hojas
    # en blanco y un cheque» scheduled): talk addressed to someone else is never acted on nor answered; the overheard
    # question is asked before the decider, as reviewed (DIALOGUE1513). The four DEV-D/F requests M118 measured
    # («hazme un ping…», «I'd like to watch…», «I need your help…», «Elabora una lista…») are addressed to BAXY, and
    # the overheard reader now reads them so (``guards._ADDRESSED_REQUEST``).
    overheard = unresolved_input_kind == "overheard_speech"
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
    if not in_conversation and (
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
        if unresolved_input_kind in {"noise", "echoed_words"}:
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
    if (
        in_conversation
        and literal_recall_decision is None
        and stable_no_effect_decision is not None
        and dialogue_slot.asks_attribute_of_the_last(objective)
    ):
        # M83 (DEV-D v3o D-p19-t3 «What's the genre?» after the cast of «After the Wedding»): read alone it is a
        # definition, answered «I don't know» and looked up as «genre». It asks an attribute of what the conversation
        # just named, so the contextual decider, which reads the conversation, decides it.
        stable_no_effect_decision = None
    if (
        literal_recall_decision is None
        and stable_no_effect_decision is not None
        and "system.time" in available_operations
        and _clock_read_request(objective, history) is not None
    ):
        # M114 (reserve es4309 «en cuántas horas será medianoche en londres inglaterra», DEV-D s025 «si pasan cuarenta
        # minutos, ¿qué hora será?» → closed as a future state, «No lo he calculado…»): a clock the readers prove —
        # another place's, or this one later on — is a read of this PC's clock (M85), never a hypothesis to refuse;
        # the contextual decider decides it, and its talk becomes that read.
        stable_no_effect_decision = None
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
                # M90 (cien-110 073 «what is cache memory, one sentence» → web.search, then a definition read off a
                # page): a common concept's definition is stable knowledge, answered in conversation.
                or common_concept_definition(
                    objective, (*application_names, *(entry[3] for entry in game_catalog.entries)),
                )
            )
        )
    )
    # M123 (D58; reserve against the isolated decider: fix 11, break 29, 33 with v2 labels): a stable no-effect reading
    # closes the turn before the decider only where it is certain and the decider is wrong in a known way
    # (``stable_no_effect_preempts``).
    # Any other reading waits for the contextual decider and is kept only as what comes after the same decision (its
    # «talk» for knowledge, a follow-up or a social act; its «limit» for a limit): the reply and its checks (an unknown
    # looked up, a recipe looked up, an answer that only asks back). What it closes still keeps the effect readers off
    # (above).
    stable_awaits_decider = (
        literal_recall_decision is None
        and stable_no_effect_decision is not None
        and not stable_no_effect_preempts(objective)
        # M90 (cien-110 073 «what is cache memory, one sentence»: the decider looked a common concept up and read a
        # definition off a page): a common concept's definition stays the reader's.
        and not common_concept_definition(
            objective, (*application_names, *(entry[3] for entry in game_catalog.entries)),
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
    if (
        live_public_intent is not None
        and live_public_intent.operations == ("web.search",)
        and turn_reading.effects is not None
        and turn_reading.effects.operations == ("weather.current",)
    ):
        # M126 (D58; DEV-F F-w50-t1 «Oye, ¿qué tiempo va a hacer el sábado en Santiago? Que me voy de ruta con la bici»
        # → web.search where the isolated decider read the weather): the public live lookup took a weather question
        # the reading gate reads as the weather read; a live weather question is the typed read (REOPEN1993 group W).
        live_public_intent = None
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
    known_limit_requested = (
        effect_request_is_authoritative(objective) and known_unsupported_effect_request(objective, available_operations)
        # M84 (DEV-D v3o s092, s006, s122, p02-t1, s094): the repeat mode, an order with a shop, the person's own bill
        # and a photo of the camera are requests however they are said («confirmen», «…, no, 20 seconds»); the
        # decider asked about them or served a capture or an alarm nearby.
        or effect_intent.unserved_personal_request(objective)
    )
    social_decision: dict[str, object] | None = None
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
        or (
            social_decision := _explicit_social_turn_decision(
                objective,
                history,
                pending_clarification=message.get("pendingClarification"),
            )
        )
        or _explicit_nonunderstanding_turn_decision(
            objective,
            history,
            pending_clarification=message.get("pendingClarification"),
        )
        or talk_act_decision
        or stable_no_effect_decision
    )
    if (
        non_target_language is None
        and content_drafting
        and explicit_conversation_decision is not None
        and explicit_conversation_decision.get("conversation_kind") == "unsupported"
        # M123 (D58, reserva es15557 «necesito que tuitees una queja» → a complaint written out as if posted): content
        # to be published on a social network is the post BAXY does not make; the limit stands.
        and not social_network_request(objective)
    ):
        # M78 (DEV-D v3l p35-t1 «Has un análisis de FODA sobre la empresa Adidas…» → «No hago análisis de FODA.»):
        # content BAXY writes in the conversation is never beyond what he does.
        explicit_conversation_decision = _conversation_turn_decision(
            "knowledge", _explicit_response_language(objective),
        )
    if (
        in_conversation
        and explicit_conversation_decision is not None
        and not _conversation_reader_keeps_followup(
            objective,
            non_target_language=non_target_language is not None,
            catalog_fact=known_limit_requested
            or known_unsupported_effect_request(objective, available_operations)
            or catalog_unavailable_decision is not None
            or (unresolved_compound_effects is not None and unsupported_effect_demonstration_request(objective)),
            recalled=literal_recall_decision is not None,
            explicit_non_action=explicit_non_action,
            social_act=explicit_conversation_decision is social_decision,
            reaction=explicit_conversation_decision is talk_act_decision
            and semantic_reading.plain_talk(objective, effects=explicit_intent, clarification=turn_reading.clarification)
            == "reaction",
        )
    ):
        # M112 (DEV-F v4d w19-t2 «Ahí tiene que estar el PDF… ¿Me lo resumes?» → «No resumo documentos.», w28-t5 «uf
        # está muy fuerte» after the music started → social talk, w60-t2 «no esa no la otra la del disco» → knowledge):
        # a follow-up is read by the contextual decider, which has the conversation in front of it; a conversation
        # reader that reads the message alone keeps it only when what it reads holds whatever came before.
        explicit_conversation_decision = None
        stable_no_effect_decision = None
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
        # M123: the contextual decider, asked below, is what confirms a knowledge reading.
        and not stable_awaits_decider
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
        # M84 (DEV-D v3o D-p02-t1 «Saca foto ahora» → a screenshot): a photo of the camera is no capture of the screen.
        and not effect_intent.unserved_personal_request(objective)
        # M123: a knowledge reading that waits for the decider is withdrawn or kept by the decider itself.
        and not (stable_awaits_decider and explicit_conversation_decision is stable_no_effect_decision)
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
    public_lookup_read: list[bool] = []

    def public_lookup() -> bool:
        # The public-lookup guard is a model call: read once per turn.
        if not public_lookup_read:
            public_lookup_read.append(
                _public_lookup_applies(objective, routing_objective, llm, available_operations, planner_catalog)
            )
        return public_lookup_read[0]

    if (
        explicit_intent is None
        and explicit_conversation_decision is not None
        and explicit_conversation_decision is stable_no_effect_decision
        and explicit_conversation_decision.get("conversation_kind") == "knowledge"
        and non_target_language is None
        # M123: the decider decides it anyway (below); the guard's model call is not spent.
        and not stable_awaits_decider
        and public_lookup()
    ):
        # M118 (D58; DEV-D/F: the stable-knowledge reader and the public-lookup guard disagreed on 8 first messages, and
        # the guard's search broke D-s096 «¿Cuál es la diferencia entre un Int y Float…?» where the isolated decider
        # talked): two readings that disagree are no proof; the contextual decider decides the turn (and a recipe or a
        # figure it answers by talking is still looked up, D35).
        explicit_conversation_decision = None
    if overheard and explicit_intent is None:
        # M118: talk the microphone may have caught is the contextual decider's, never a conversation reader's reply
        # to it (DIALOGUE1513: answered as if it were addressed to BAXY).
        explicit_conversation_decision = None
    decided_beforehand: semantic_decider.ContextDecision | None = None
    if (
        stable_awaits_decider
        and explicit_intent is None
        and explicit_conversation_decision is not None
        and explicit_conversation_decision is stable_no_effect_decision
    ):
        # M123 (D58): the reading is the contextual decider's to confirm. The same decision («limit» for a limit,
        # «talk» for the rest) keeps the reading's conversation (below); anything else is its decision, handed over
        # without asking it twice.
        decider_tools, signatures = _decider_catalog(planner_catalog)
        decided_beforehand = llm.decide_in_context(
            str(message.get("text", "")), message.get("history") or [], decider_tools, signatures=signatures,
        )
        same_decision = "limit" if explicit_conversation_decision.get("conversation_kind") == "unsupported" else "talk"
        if decided_beforehand.decision != same_decision:
            explicit_conversation_decision = None
    if (
        decided_beforehand is None
        and explicit_intent is not None
        and explicit_intent.operations == ("web.search",)
        and (explicit_intent is live_public_intent or explicit_intent is turn_reading.effects)
        and search_has_typed_reads(available_operations)
        and served_surface is None
        and not in_conversation
        and non_target_language is None
        and not known_limit_requested
        and unresolved_compound_effects is None
    ):
        # M131 (D58; ledger of the first-turn readers against the isolated decider: reserve v1/v2, DEV-D, DEV-F): a first
        # message read as a plain web search waits for the decider. Where the decider chose a typed read that serves the
        # question more specifically (``typed_read_over_search``: the day's headlines, the weather with its later days,
        # what this PC plays), its decision is the turn, handed over without asking it twice. Any other decision keeps
        # the search: its talk, question, limit or a personal read are the decider's errors the search fixed (12 + 7 on
        # the reserve, 0 broken).
        decider_tools, signatures = _decider_catalog(planner_catalog)
        searched = llm.decide_in_context(
            str(message.get("text", "")), message.get("history") or [], decider_tools, signatures=signatures,
        )
        if searched.decision == "action" and typed_read_over_search(searched.operations):
            return _context_decided_result(
                message, llm=llm, planner_catalog=planner_catalog, application_names=application_names,
                decided_beforehand=searched,
            )
    decider_confirmed = decided_beforehand is not None and explicit_conversation_decision is not None
    if explicit_conversation_decision is None and (explicit_intent is None or in_conversation):
        # No reader proved this message, or it follows earlier turns and no conversation reader kept it:
        # the contextual decider decides it (Fase 3.5b F4), not the shortlist, the native selector and
        # the gates.
        def reread_limit(decided_request: str) -> dict[str, Any] | None:
            # Tanda 3 «Pausa el speaker.», «añadir una nueva lista para material escolar»: a limit the decider
            # gives to words the readers prove once they stand in their canonical surface is that request.
            if served_surface is not None or non_target_language is not None:
                return None
            return _served_surface_reread(
                message,
                objective,
                history,
                llm=llm,
                planner_catalog=planner_catalog,
                encoder=encoder,
                tool_by_name=tool_by_name,
                application_names=application_names,
                game_catalog=game_catalog,
                on_signal=on_signal,
                already_signaled=already_signaled,
                decided_request=decided_request,
            )

        return _context_decided_result(
            message, llm=llm, planner_catalog=planner_catalog, on_limit=reread_limit,
            application_names=application_names, overheard=overheard, decided_beforehand=decided_beforehand,
        )
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
    else:
        # A conversation reader closed the turn: neither deterministic conversation variant consumes
        # candidates, evidence or semantic scores. Every other turn went to the contextual decider above.
        shortlist = ()
    raw_decision = (
        explicit_conversation_decision
        if explicit_conversation_decision is not None
        else _explicit_turn_decision(explicit_intent, objective)
    )
    # Which reader owned this decision (the contextual decider's turns never reach here).
    decision_path = "explicit_effects" if explicit_intent is not None else "explicit_conversation"
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
        and public_lookup()
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
    try:
        decision = apply_compound_effect_conservation_veto(
            decision,
            unresolved_compound_effects,
            tool_by_name,
            llm,
            application_names,
        )
    except PlannerContractError:
        if explicit_intent is None or explicit_conversation_decision is not None or served_surface is not None:
            raise
        # M112 (DEV-F v4d w01-t1 «léeme el último correo que me llegó, creo que es de mi jefa… y no lo he abierto» →
        # the readers proved the mail read, «no lo he abierto» left a clause they could not read, the turn failed twice
        # and asked «¿el asunto o el remitente?»): readers that cannot read the whole message are not sure of it; the
        # contextual decider, which reads all of it, decides the turn instead of failing it.
        return _context_decided_result(
            message, llm=llm, planner_catalog=planner_catalog, application_names=application_names,
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
        # M123 (D58, DEV-D D-s096 as in M118): what the contextual decider already confirmed as talk or as a limit is
        # not turned into a search by the guard.
        and not decider_confirmed
        and public_lookup()
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
        # M123: the contextual decider, which had the catalog in front of it, already chose to talk.
        and not decider_confirmed
    ):
        observing = _catalog_answers_the_request(
            routing_objective,
            objective,
            planner_catalog,
            tool_by_name,
            llm,
            application_names,
            history=history,
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

    if (
        decision["mode"] == "conversation"
        and decision.get("conversation_kind") in {"knowledge", "followup"}
        and non_target_language is None
        and "web.search" in available_operations
        and planner_catalog.get("web.search") is not None
        and (looked_up := _reference_lookup(objective, history)) is not None
    ):
        # M53 (D35): a named dish's recipe or a named work's plot is looked up before anything is said about it.
        shortlist = _shortlist_with_required_effects(shortlist, ("web.search",), planner_catalog)
        decision = validate_turn_decision(
            _recovered_action_decision("web.search", decision.get("response_language")),
            {tool.name for tool in shortlist},
        )
        intent_operations = ["web.search"]
        # D61: the kind looked up rides the audit, as on the decider's path (comprension_eval score --d35 reads it).
        turn_audit["stages"].append({**_turn_audit_stage("reference_looked_up", decision), "kind": looked_up.kind})

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
            and not effect_intent.out_of_world_request(objective)
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


# M54 (v3b-final F-p10-t2 «me gustaría que me mostraras el ejemplo de la calculadora científica» → «¿Podrías
# explicarme paso a paso cómo instalar y ejecutar ese código en tu computadora?»): a clarification asks the one thing
# missing; asking the person to explain, teach or show how to do something is their request handed back. Folded.
_RECOVERY_MIRRORED_REQUEST = re.compile(
    r"\b(?:explica|explicame|explicarme|explicas|ensename|ensenarme|ensenas|muestrame|mostrarme|me\s+muestras|"
    r"explain|teach|show)\b(?:\s+\w+){0,5}?\s+(?:como|how)\b|\bpaso\s+a\s+paso\b|\bstep\s+by\s+step\b"
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
    if _RECOVERY_MIRRORED_REQUEST.search(folded) is not None:
        return False
    # M85 (DEV-D v3o D-p04-t1 «Dónde?» → «¿Dónde?»): the person's own question said back asks nothing.
    if objective and dialogue_slot.says_the_message_back(value, objective):
        return False
    # M93 (DEV-D v3u D-s053 «¿Miguel sigue viviendo en Arkansas?» → «¿Te refieres a Miguel o a alguien más?»).
    if objective and dialogue_slot.offers_back_the_named_one(value, objective):
        return False
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
    conversation_kinds: tuple[str | None, ...] = (),
) -> dict[str, Any]:
    """Return a total, fail-closed clarification after two turn failures.

    The semantic recovery receives dialogue only. If local generation is
    unavailable or violates its schema, the protocol keeps the transport alive
    with empty user-facing fields and zero action authority. The shell may make
    one separately bounded ``message.compose`` attempt, but deterministic
    protocol prose must never be presented as model-authored text.

    ``conversation_kinds`` (M104) are the kinds the failed attempts decided: talk whose wording failed is recovered as
    the talk it was understood to be (``conversationKind`` «knowledge», «social», «followup»), never as a conversation
    of no kind.

    D59 §7 (owner, 2026-10-02): when the model ran and still wrote no valid question for a turn it did not understand,
    the question is the one built with the person's own words (``_words_floor_result``).
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
                        # M54 (v3b-devD D-s005, D-s037): a limit recovered after its wording failed is published as
                        # conversationKind «unsupported»; the audit said only «conversation», so the run read it as
                        # talk. The audit carries what the result carries.
                        **(
                            {"conversation_kind": result["conversationKind"]}
                            if result.get("conversationKind")
                            else {}
                        ),
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
    ) or is_limit or (
        # M72: the turn was understood as conversation and only its wording failed; the recovery answers briefly
        # instead of asking «¿qué quieres que haga BAXY?» about a message nobody misread.
        bool(failure_kinds) and set(failure_kinds) == {CONVERSATION_WORDING_FAILURE}
    )
    if llm is not None:
        try:
            if nothing_to_clarify:
                raise ValueError("capability_question_is_not_clarified")
            question = llm.clarify_after_turn_failure(
                objective,
                history=history,
                timeout=2.5,
            )
            # M99 (DEV-D v3x D-s053 «¿Miguel sigue viviendo en Arkansas?» → «¿Te refieres a Miguel o a alguien más?»):
            # the recovery question is judged against the message too, as the decider's is.
            if not _recovery_question_is_valid(question, objective, history):
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
        understood_talk = (
            not is_limit and bool(failure_kinds) and set(failure_kinds) == {CONVERSATION_WORDING_FAILURE}
        )
        # M104 (reserve v3z en13040 «what is the square root of nine» and 17 more → «conversation» with no kind): the
        # kind the attempts decided, when they agree on one talk kind.
        decided_talk_kinds = {kind for kind in conversation_kinds if kind}
        understood_kind = (
            next(iter(decided_talk_kinds))
            if understood_talk and len(decided_talk_kinds) == 1 and decided_talk_kinds <= {"knowledge", "social", "followup"}
            else None
        )
        kind, text = (
            _recovery_visible_from_compose(llm, objective, talk=True, history=history)
            if understood_talk else ("conversation", "")
        )
        if not text:
            kind, text = _recovery_visible_from_compose(llm, objective, limit=is_limit, history=history)
        if kind == "clarify" and (not nothing_to_clarify or understood_talk):
            # M97 (reserve A11, DEV-D v3o–v3x composition_failed): talk whose wording failed twice and whose reply the
            # composer could not write either asks back rather than publishing nothing.
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
        if (
            not text
            # The model ran (its turn attempts failed, its composer answered nothing usable); with the model offline
            # or unavailable, the protocol still writes no prose of its own.
            and failure_kinds
            and callable(getattr(llm, "compose_user_message", None))
            and (floor := _words_floor_result(message, objective, nothing_to_clarify, attempts, failure_code))
        ):
            return audited(floor)
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
                "conversationKind": "unsupported" if is_limit else understood_kind,
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


def _words_floor_result(
    message: dict[str, Any], objective: str, nothing_to_clarify: bool, attempts: int, failure_code: object,
) -> dict[str, Any] | None:
    """D59 §7 (owner, 2026-10-02): a turn not understood whose recovery wrote no valid question asks with the person's
    own words (``semantic.dialogue.words_floor_question``), never a fixed «no pude entender»; None when the turn had
    nothing to clarify (a limit, a capability, talk understood) or the message has no word to quote."""

    if nothing_to_clarify:
        return None
    question = dialogue_slot.words_floor_question(
        objective, "en" if _explicit_response_language(objective) == "en" else "es",
    )
    if not question:
        return None
    return {
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
        "turn_recovery": "words_floor_question",
        "recovery_attempts": 1,
        "failure_code": failure_code,
    }


def _recovery_conversation_facts(history: object, objective: str) -> dict[str, Any]:
    """M109 (DEV-D v4d D-p23-t5, D-p24-t5): what the recovery's composer knows of the conversation — BAXY's last message
    («context») and the person's earlier ones («priorRequests») —, the same data the App's composition carries. Without
    them the writer told «if your earlier messages say you do not do that, say so again» had no earlier message."""

    items = [item for item in history if isinstance(item, dict)] if isinstance(history, list) else []
    last = next(
        (str(item.get("content") or "") for item in reversed(items) if item.get("role") == "assistant"), "",
    ).strip()
    prior = list(_prior_user_texts(history, objective))
    return {**({"context": last} if last else {}), **({"priorRequests": prior} if prior else {})}


def _recovery_visible_from_compose(
    llm: Any, objective: str, *, limit: bool = False, talk: bool = False, history: object = None,
) -> tuple[str, str]:
    """Use model-authored recovery text. A question is a question, not silence.

    Returns ``("clarify", question)``, ``("conversation", reply)`` or
    ``("conversation", "")`` when the model produces nothing usable.

    ``talk`` (M97, reserve A11 «tengo una reunión hoy al mediodía» → «»): the turn understood talk and only the wording
    of its reply failed; the composer answers it as conversation (the App's conversation situation), and a reply that
    asks back is still the reply.
    """

    compose = getattr(llm, "compose_user_message", None)
    if not callable(compose):
        return "conversation", ""
    conversation = _recovery_conversation_facts(history, objective)
    if talk:
        try:
            reply = str(
                compose(
                    objective,
                    "conversation",
                    {
                        **conversation,
                        "situation": json.dumps({"kind": "conversation", "polarity": "success"}, ensure_ascii=False),
                    },
                )
                or ""
            ).strip()
        except Exception:  # noqa: BLE001 - the clarification below is the next floor
            return "conversation", ""
        if (
            not reply
            or len(reply) > 4_096
            or dialogue_slot.says_the_message_back(reply, objective)
            or (reply.endswith("?") and _RECOVERY_MIRRORED_REQUEST.search(read_fold(reply)) is not None)
            # M101 (DEV-D v3z D-p31-t2): a talk reply that tells a failure is refused by the App, whose turn failure
            # then had no final; the clarification below asks back instead.
            or talk_reply_tells_a_failure(reply, objective)
        ):
            return "conversation", ""
        return "conversation", reply
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
                    # M109: the question back asks about this conversation, not about the message alone.
                    **({} if limit else conversation),
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
    if _recovery_question_is_valid(text, objective):
        return "clarify", text
    if text.endswith("?") and (
        _RECOVERY_MIRRORED_REQUEST.search(read_fold(text)) is not None
        # M99 (DEV-D v3x D-s053): a question that offers back the one named asks nothing, here too.
        or (_recovery_question_is_valid(text) and not _recovery_question_is_valid(text, objective))
    ):
        # M54: the person's request handed back is neither a question to publish nor a reply.
        return "conversation", ""
    return "conversation", text


class _SidecarLifecycle:
    """Own sidecar resources and release each one once in dependency order."""

    def __init__(self) -> None:
        self._ownership_lock = threading.Lock()
        self._voice_engine: Any | None = None
        self._voice_cancel_pending = False
        self._llm: Any | None = None
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
            not planner_stopped or not dispatch_stopped
        ):
            request_close = getattr(self._router, "request_close", None)
            if callable(request_close):
                attempt(request_close)
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
    voice_engine = None

    def ready_planner_catalog() -> PlannerCatalog:
        with planner_resources_lock:
            current = planner_catalog
        if current is None:
            raise PlannerContractError("the plannable catalog is not available")
        return current

    def promote_planner_resources() -> None:
        """Add E5 retrieval once the router's E5 worker is ready."""

        nonlocal planner_catalog, skill_registry

        def promotion_encoder(texts: Any, *, prefix: str = "query") -> Any:
            if planner_promotion_stop.is_set():
                raise RuntimeError("planner promotion was cancelled")
            encoded = background_encoder(texts, prefix=prefix)
            if planner_promotion_stop.is_set():
                raise RuntimeError("planner promotion was cancelled")
            return encoded

        deadline = time.monotonic() + 185.0
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
                # user turn wait for the router.
                lexical_catalog, lexical_skills = _create_planner_resources(tools)
                with planner_resources_lock:
                    planner_catalog = lexical_catalog
                    skill_registry = lexical_skills
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
                    _warm_context_decider(llm, lexical_catalog)
                write_request_message(
                    {
                        "type": "catalog.ready",
                        "id": request_id,
                        "count": len(tools),
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
                # M104: the conversation kind each failed attempt had decided (None when it decided none).
                turn_failure_conversation_kinds: list[str | None] = []
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
                        turn_failure_conversation_kinds.append(getattr(error, "conversation_kind", None))
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
                        conversation_kinds=tuple(turn_failure_conversation_kinds),
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
                recognized_evidence = (
                    _evidence_of_expected_operations(
                        expected_operations,
                        recognized_expected.operations,
                        recognized_expected.evidence,
                    )
                    if recognized_expected is not None
                    else None
                )
                expected_evidence = (
                    (objective,)
                    if len(expected_operations) == 1
                    else _restore_evidence_surfaces(objective, recognized_evidence)
                    if recognized_evidence is not None
                    else ()
                )
                snap_split = window_snap_plan_split(
                    expected_operations,
                    expected_evidence,
                    objective,
                    application_catalog,
                )
                if snap_split is not None:
                    # M55: «X a la izquierda e Y a la derecha» is one resolve and one snap per window.
                    expected_operations, expected_evidence = snap_split
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
                plan_operations = tuple(step.operation for step in proposal.steps)
                # M76 (DEV-D v3l D-w16-t2 «Actually, make it 6:30.», D-w04-t4, D-w18-t5): moving the notification the
                # last turn set takes its new time from the person's message and the rest from what was verified.
                retimed = (
                    dialogue_state.retimed_notification(_person_message(history, objective))
                    if "notification.schedule" in expected_operations
                    else None
                )
                if (
                    retimed is None
                    and "notification.schedule" in expected_operations
                    and set(expected_operations) & {"notification.cancel.at", "notification.cancel.latest"}
                ):
                    # M115 (DEV-F v4e2 F-w12-t2, F-w15-t4, F-w07-t4): the plan already moves the notification just set;
                    # its new time is the one clock the person said, or else the one the restatement says, and the
                    # rest (its kind, what it is for, the old time to cancel) is what was verified setting it.
                    retimed = dialogue_state.retimed_notification(
                        _person_message(history, objective), moving=True,
                    ) or dialogue_state.retimed_notification(objective, moving=True)
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
                    moved = (
                        _retimed_step_arguments(step.operation, retimed, schema)
                        if retimed is not None
                        else None
                    )
                    if moved is not None:
                        arguments_by_step[step.step_id] = moved
                        continue
                    pointed = (
                        dialogue_state.pointed_listed_title(_person_message(history, objective))
                        or dialogue_state.pointed_listed_title(objective)
                        if step.operation == "task.resolve.exact"
                        else None
                    )
                    if pointed is not None and validate_json_schema_instance({"title": pointed}, schema):
                        # M76 (DEV-D v3l D-w17-t2 «mark the first one done»): the task pointed at by its place in the
                        # list the turn before read is resolved by the title that list told.
                        arguments_by_step[step.step_id] = {"title": pointed}
                        continue
                    conversation_note = _conversation_note_selector(
                        step.operation, plan_operations, _person_message(history, objective), dialogue_state, schema,
                    )
                    if conversation_note is not None:
                        arguments_by_step[step.step_id] = conversation_note
                        continue
                    if expected_operations:
                        explicit_arguments = _ground_explicit_arguments(
                            step.operation,
                            step.purpose,
                            schema,
                            application_names,
                            game_catalog,
                            # M62 (F-s044): a moved alarm takes its part of the day from what was said before.
                            history=history if step.operation == "notification.schedule" else None,
                        )
                        if explicit_arguments is None and step.operation == "notification.cancel.latest":
                            # M145: a cancellation made the latest one's (``_own_notification_cancellation``) takes
                            # its kind from the request that named it («Cambia la alarma de las 7:00 a las 7:15.»).
                            explicit_arguments = _ground_explicit_arguments(step.operation, objective, schema)
                        if explicit_arguments is not None:
                            arguments_by_step[step.step_id] = explicit_arguments
                            continue
                        if step.operation == "document.presentation.create":
                            # REOPEN1957 H0188: the local model writes the slides.
                            authored = _presentation_arguments(llm, step.purpose)
                            if authored is not None and validate_json_schema_instance(authored, schema):
                                arguments_by_step[step.step_id] = authored
                                continue
                    decided_step = _plan_step_decided_arguments(
                        step.operation, plan_operations, objective, tool, history,
                    )
                    if decided_step is not None:
                        # M141 (DEV-G v4o G-s040, G-s116): what the decider read fills the step; the extraction
                        # call is spent only on the steps still missing a value.
                        arguments_by_step[step.step_id] = decided_step
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
                    partial = partial_explicit_arguments(str(request["operation"]), objective, schema)
                    if partial:
                        # M76 (DEV-D v3l D-w15-t2 «¿En qué carpeta conocida deseas buscar…?» after «…en Documentos»):
                        # what the readers know fills what the extraction left out, so it is never asked again.
                        arguments = {**partial, **(arguments if isinstance(arguments, dict) else {})}
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
                        # M141: what the extraction left out or could not ground is completed with what the decider
                        # read before anything is asked.
                        grounded = _plan_step_decided_arguments(
                            str(request["operation"]), plan_operations, objective, tool, history,
                            extracted=arguments, after_extraction=True,
                        )
                    if grounded is None:
                        change = (
                            semantic_temporal.notification_change(objective)
                            if request["operation"] == "notification.schedule"
                            else None
                        )
                        if change is not None and change.clocks_lack_the_part_of_day() and "dueUtc" in fields:
                            # M62 (v3e2-final F-s044 «change the reminder … from 3 to 4» → «¿Cuándo, en tus
                            # propias palabras, sería el momento adecuado para esta alarma?», in Spanish): what is
                            # missing is only the part of the day of the new time, asked in the person's language.
                            raise PlannerClarification(
                                llm.formulate_missing_argument_question(
                                    objective,
                                    str(request["purpose"]),
                                    tool,
                                    ("dueUtc",),
                                    response_language="en" if change.english else "es",
                                    ask_as={
                                        "dueUtc": (
                                            f"only whether {change.new_literal} is in the morning or in the "
                                            f"afternoon or evening (the {change.noun} at {change.old} was not said "
                                            "with its part of the day); nothing else"
                                        )
                                    },
                                )
                            )
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
                        purpose=str(message.get("purpose", "")),
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
                arguments, question = _direct_arguments_result(
                    message,
                    llm=llm,
                    tool=tool,
                    application_names=application_names,
                    game_catalog=game_catalog,
                    dialogue_state=dialogue_state,
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
                            # M71 (held-out v3j t14): what the person wrote, beside the request as understood.
                            said=str(message.get("userText", ""))[:4096],
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
