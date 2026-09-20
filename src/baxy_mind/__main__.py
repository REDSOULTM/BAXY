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
from datetime import date, datetime, time as datetime_time, timedelta, timezone
from enum import Enum
from functools import partial
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import urlencode, urlsplit

# PyTorch otherwise sizes its CPU pools for the whole machine. On a 16 GiB
# notebook that creates dozens of workers and can turn startup into minutes of
# paging. Keep explicit operator overrides, but use a small production default.
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from . import protocol
from . import effect_intent
from . import corrector
from .corrector import catalog_correction_terms
from .first_signal import (
    PATH_MODEL,
    PATH_RECOGNIZER,
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
    resolve_application_installed_name,
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
    LlmRuntime,
    _literal_recall_reference,
    _merged_observed,
    _native_selection_description,
    _reads_as_an_observation,
    _situation_from_facts,
    served_capability_families,
    visible_reply_is_only_questions,
)
from .planner import (
    MAX_SHORTLIST_OPERATIONS,
    PlannerCatalog,
    PlannerContractError,
    PlannerTool,
    attach_arguments,
    conditional_predecessors,
    is_required_predecessor,
    normalize_grounded_arguments,
    required_predecessors,
    validate_argument_grounding,
    validate_json_schema_instance,
    validate_skeleton,
)
from .request_reading import (
    _INTERROGATIVE,
    fold as read_fold,
    INTENT_AMBIGUOUS_ACTION,
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
            for window in windows:
                if (
                    isinstance(window, dict)
                    and window.get("foreground") is not True
                    and window.get("state") != "minimized"
                    and isinstance(window.get("windowId"), str)
                ):
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
    quoted = re.search(r"[\"“](?P<text>[^\"”]{1,16384})[\"”]", objective)
    if quoted is not None:
        body = quoted.group("text")
    else:
        request_text = objective
        for _ in range(2):
            stripped = effect_intent._strip_request_envelope(request_text).strip()
            if stripped == request_text:
                break
            request_text = stripped
        channel_first_patterns = (
            r"^(?:por|en|via)\s+(?:whatsapp|wsp|discord)\s+"
            r"(?:hazle\s+llegar|cu[eé]ntale)\s+a\s+"
            r"[^,;.!?]{1,80}?\s+(?:que|(?:el\s+)?mensaje)\s+"
            r"(?P<text>.+)$",
            r"^(?:through|on|via)\s+(?:whatsapp|discord)\s+"
            r"let\s+[^,;.!?]{1,80}?\s+know\s+(?P<text>.+)$",
            r"^(?:through|on|via)\s+(?:whatsapp|discord)\s+"
            r"get\s+(?:the\s+)?(?:note|message|update)\s+"
            r"(?P<text>.+?)\s+to\s+[^,;.!?]{1,80}$",
            r"^(?:por|en|via)\s+(?:whatsapp|wsp|discord)\s+"
            r"(?:dile|decile)\s+a\s+[^,;.!?\s]{1,80}\s+"
            r"(?P<text>.+)$",
        )
        channel_first = next(
            (
                match
                for pattern in channel_first_patterns
                if (match := re.match(pattern, request_text, re.IGNORECASE)) is not None
            ),
            None,
        )
        if channel_first is not None:
            body = channel_first.group("text").strip()
        else:
            request = re.match(
                r"^[Â¿?Â¡!\s]*(?:dile|decile|tell|manda|env[ií]a|send|message|"
                r"escr[ií]be(?:le)?|write\s+to|pasa|pass)\b"
                r"(?P<request>.+)$",
                request_text,
                re.IGNORECASE,
            )
            if request is None:
                return None
            separator = re.search(
                r"\b(?:que|that|saying|(?:el|the)\s+(?:texto|text|mensaje|message))"
                r"\s+(?P<text>.+)$",
                request.group("request"),
                re.IGNORECASE,
            )
            if separator is None:
                return None
            body = separator.group("text").strip()
        body = body.rstrip(".!?").rstrip()
        body = re.sub(
            r"\s+(?:en|por|via|on|through)\s+(?:wsp|whatsapp|discord)\s*$",
            "",
            body,
            count=1,
            flags=re.IGNORECASE,
        ).rstrip()
    if not body or len(body.encode("utf-8")) > 16_384:
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
    extraction = llm.extract_direct_arguments(objective, tool)
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
    request_head = effect_intent._request_head(folded)
    information_question = request_head in {
        "are",
        "como",
        "cual",
        "cuando",
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
    }
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
        re.search(
            (
                r"\b(?:estoy|estaba|estuve|tengo|tenia|veo|noto|observo|"
                r"me aparece|me salio|dejo de|"
                r"i am|i m|i was|i have|i ve|i did|i see|i notice|"
                r"i observe|stopped)\b"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
        # The list above only recognises the person talking about themselves.
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
        "knowledge"
        if is_question
        or re.search(
            r"\b(?:que|cual|cuanto|como|por que|what|which|how|why|explain|explica)\b",
            folded,
        )
        else "followup"
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
        operations == ["message.recipient.resolve"]
        and re.search(r"\b(?:whatsapp|discord)\b", effect_intent._fold(objective))
        is not None
        and re.search(
            r"\b(?:avisa|avise|notify|notifica|dile|tell|manda|send|envia|"
            r"escribele|write\s+to|message)\b",
            effect_intent._fold(objective),
        )
        is not None
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
    """Name the invocation a withdrawal may still offer to confirm.

    Every withdrawn operation has to be independently identified as the effect
    the person named. A single unidentified member keeps the whole turn
    ``unsupported``: a confirmation must bind to one exact invocation, never to
    a set with a stranger inside it.
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


def _domain_confirmation_question(
    objective: str,
    operations: tuple[str, ...],
    tool_by_name: dict[str, dict],
    llm: object,
) -> str:
    """Ask the person to confirm the exact invocation, in the model's words."""

    compose = getattr(llm, "confirm_operation_before_acting", None)
    if not callable(compose):
        return ""
    effects: list[tuple[str, str]] = []
    for operation in operations:
        contract = _turn_operation_contract(
            tool_by_name.get(operation),
            operation,
            objective,
            (),
        )
        if contract is None:
            return ""
        effects.append((operation, str(contract["description"])))
    try:
        question = str(
            compose(
                objective,
                tuple(effects),
                timeout=TURN_DECIDE_RECOVERY_BUDGET_SECONDS,
            )
        )
    except Exception:  # noqa: BLE001 - a failed question is an honest refusal
        return ""
    return question if _recovery_question_is_valid(question, objective) else ""


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


def _explicit_unsupported_turn_decision(objective: str) -> dict[str, object]:
    """Close a high-confidence out-of-scope language turn without effects."""

    return {
        "mode": "conversation",
        "operation": None,
        "question": "",
        "conversation_kind": "unsupported",
        "effect_count": "zero",
        "effect_operations": [],
        "effect_verification": "not_applicable",
        "response_language": _explicit_response_language(objective),
    }


# Un acto social completo no pide nada: saludar, despedirse, agradecer o
# preguntar cómo está el asistente no nombra un efecto ni concede autoridad.
# Las alternancias son cerradas y se consumen con `re.fullmatch`, así que
# cualquier cláusula añadida —«hola, pon el volumen al 30»— deja de coincidir y
# vuelve al modelo. Cada rama declara su idioma porque el propio patrón ya lo
# fija; derivarlo de un contador de tokens respondería en español a «hi».
_SOCIAL_SEPARATOR = r"[\s,;:.!¡¿]+"
_SOCIAL_VOCATIVE = r"baxy"
_SOCIAL_ACTS: tuple[tuple[str, dict[str, str]], ...] = (
    (
        "es",
        {
            "acknowledgement": (
                r"(?:muy bien|de una|perfecto|excelente|genial|barbaro|listo)"
            ),
            "greeting": (r"(?:buenos dias|buenas tardes|buenas noches|buenas|hola)"),
            "farewell": (
                r"(?:hasta luego|hasta pronto|hasta manana|nos vemos|"
                r"nos hablamos|adios|chau|chao)"
            ),
            "gratitude": (
                r"(?:muchas gracias|mil gracias|"
                r"gracias(?: por (?:todo|tu ayuda|la ayuda))?|"
                r"te lo agradezco)"
            ),
            "compliment": (r"(?:sos un capo|eres un capo|sos genial|eres genial)"),
            "wellbeing": (
                r"(?:como estas|como andas|como va|que tal todo|que tal|"
                r"todo bien)"
            ),
        },
    ),
    (
        "en",
        {
            "acknowledgement": (r"(?:very well|perfect|excellent|great|awesome|nice)"),
            "greeting": (
                r"(?:good morning|good afternoon|good evening|"
                r"(?:hello|hey|hi)(?: there)?)"
            ),
            "farewell": (
                r"(?:see you later|see you|good night|goodbye|good bye|"
                r"take care|bye)"
            ),
            "gratitude": (
                r"(?:thanks(?: a lot| so much)?|"
                r"thank you(?: very much| so much)?)"
            ),
            "compliment": (
                r"(?:you are great|you are awesome|you(?:['’]?re) great|"
                r"you(?:['’]?re) awesome)"
            ),
            "wellbeing": (
                r"(?:how are you doing|how are you|how is it going|"
                r"hows it going|whats up)"
            ),
        },
    ),
)


def _social_turn_pattern(parts: dict[str, str]) -> str:
    """Compose one language's closed social envelope."""

    greeting = parts["greeting"]
    core = (
        rf"(?:{greeting}(?:{_SOCIAL_SEPARATOR}{greeting})?"
        rf"|{parts['farewell']}|{parts['gratitude']})"
    )
    wellbeing = parts["wellbeing"]
    return (
        r"[¿?¡!\s]*"
        rf"(?:{parts['acknowledgement']}{_SOCIAL_SEPARATOR})?"
        rf"(?:{core}"
        rf"(?:{_SOCIAL_SEPARATOR}{_SOCIAL_VOCATIVE})?"
        rf"(?:{_SOCIAL_SEPARATOR}{wellbeing})?"
        rf"(?:{_SOCIAL_SEPARATOR}{parts['compliment']})?"
        rf"|{wellbeing})"
        r"[\s?!.]*"
    )


_SOCIAL_TURNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (language, re.compile(_social_turn_pattern(parts), re.IGNORECASE))
    for language, parts in _SOCIAL_ACTS
)


def _explicit_social_turn_decision(
    objective: str,
    history: object = None,
    *,
    pending_clarification: bool | None = None,
) -> dict[str, object] | None:
    """Classify a standalone social act without routing it as an effect."""

    # Una aclaración pendiente convierte cualquier respuesta en parte de ese
    # intercambio. Ante la duda se devuelve el turno al modelo, que es
    # exactamente el comportamiento previo.
    if _history_has_pending_clarification(history, pending_clarification):
        return None
    assistant_preference = False
    folded = unicodedata.normalize("NFKD", objective.casefold())
    folded = "".join(
        character for character in folded if not unicodedata.combining(character)
    )
    folded = " ".join(folded.split())
    language = next(
        (
            candidate
            for candidate, pattern in _SOCIAL_TURNS
            if pattern.fullmatch(folded) is not None
        ),
        None,
    )
    if language is None:
        # The private-memory parser recognizes this declarative form, but it
        # grants no persistence authority. A whole self-introduction belongs
        # to conversation, before PC tools can prime a Windows-account read.
        declaration = re.fullmatch(
            r"(?:(?P<es>(?:yo\s+)?me\s+llamo|mi\s+nombre\s+es)|"
            r"my\s+name\s+is)\s+"
            r"(?P<name>[^\W\d_](?:[^\W\d_]|[ '’\-]){0,79})[.!]*",
            folded,
        )
        if declaration is not None:
            # Do not swallow an unpunctuated question or command after the
            # asserted first name. Reuse the shared vocabulary, not a name list.
            tail = declaration.group("name").strip().partition(" ")[2]
            if (
                _INTERROGATIVE.search(tail) is None
                and re.search(rf"\b{effect_intent._COVERAGE_ACTION_HEAD}\b", tail)
                is None
            ):
                language = "es" if declaration.group("es") is not None else "en"
    if language is None:
        personal_wellbeing_report = (
            (
                "es",
                r"[Â¿?Â¡!\s]*(?:mi\s+)?dia\s+"
                r"(?:fue|ha\s+sido|esta\s+siendo)\s+"
                r"(?:(?:muy|extremadamente|bastante|realmente)\s+)?"
                r"(?:duro|dificil|pesado|terrible|agotador|bueno|genial|"
                r"excelente)[\s?!.]*",
            ),
            (
                "en",
                r"[Â¿?Â¡!\s]*my\s+day\s+"
                r"(?:was|has\s+been|is\s+being)\s+"
                r"(?:(?:very|extremely|quite|really)\s+)?"
                r"(?:hard|difficult|rough|terrible|exhausting|good|great|"
                r"excellent)[\s?!.]*",
            ),
        )
        language = next(
            (
                candidate
                for candidate, pattern in personal_wellbeing_report
                if re.fullmatch(pattern, folded, re.IGNORECASE) is not None
            ),
            None,
        )
    if language is None:
        assistant_preference_question = (
            (
                "es",
                r"[¿?¡!\s]*(?:que|cual)\s+quieres\s+hacer\s+hoy[\s?!.]*",
            ),
            (
                "en",
                r"[¿?¡!\s]*what\s+do\s+you\s+want\s+to\s+do\s+today[\s?!.]*",
            ),
        )
        language = next(
            (
                candidate
                for candidate, pattern in assistant_preference_question
                if re.fullmatch(pattern, folded, re.IGNORECASE) is not None
            ),
            None,
        )
        assistant_preference = language is not None
    if language is None:
        # «Hi again» y «buenas, compa» son saludos completos: la lectura del
        # pedido los reconoce sin ampliar otro patrón por cada variante, y sin
        # tragarse un pedido que venga detrás del saludo.
        greeting = read_request(objective)
        if greeting.greeting_only:
            language = greeting.language
    if language is None:
        return None
    return {
        "mode": "conversation",
        "operation": None,
        "question": "",
        "conversation_kind": "knowledge" if assistant_preference else "social",
        "effect_count": "zero",
        "effect_operations": [],
        "effect_verification": "not_applicable",
        "response_language": language,
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


def _previous_user_request(history: list[object], current_request: str) -> str | None:
    """Read the user antecedent, preserving contiguous clock continuations."""
    previous = history
    if (
        history
        and isinstance(history[-1], dict)
        and history[-1].get("role") == "user"
        and history[-1].get("content") == current_request
    ):
        previous = history[:-1]
    requests = [
        str(item.get("content") or "")
        for item in reversed(previous)
        if isinstance(item, dict) and item.get("role") == "user"
    ]
    if not requests:
        return None
    return effect_intent.datetime_followup_antecedent(current_request, requests) or requests[0]


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


def _history_has_pending_clarification(
    history: object,
    pending_clarification: bool | None = None,
) -> bool:
    """Use shell state; punctuation is only a legacy history-only hint."""

    if isinstance(pending_clarification, bool):
        return pending_clarification

    if not isinstance(history, list):
        return False
    for item in reversed(history):
        if (
            not isinstance(item, dict)
            or item.get("role") != "assistant"
            or not isinstance(item.get("content"), str)
        ):
            continue
        content = str(item["content"]).strip()
        return bool(content) and content.rstrip().endswith("?")
    return False


def _explicit_nonunderstanding_turn_decision(
    objective: str,
    history: object = None,
    *,
    pending_clarification: bool | None = None,
) -> dict[str, object] | None:
    """Classify only a standalone comprehension reaction outside clarification."""

    if _history_has_pending_clarification(history, pending_clarification):
        return None
    folded = unicodedata.normalize("NFKD", objective.casefold())
    folded = "".join(
        character for character in folded if not unicodedata.combining(character)
    )
    folded = " ".join(folded.split())
    explicit_nonunderstanding = (
        re.fullmatch(
            (
                r"[¿?¡!\s]*(?:"
                r"no (?:te )?(?:entendi|entiendo|comprendi|comprendo)|"
                r"no me quedo claro|"
                r"i (?:did not|didn't|do not|don't) "
                r"(?:understand|get it|get that)|"
                r"i(?:'m| am) confused"
                r")[\s?!.]*"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    has_assistant_context = isinstance(history, list) and any(
        isinstance(item, dict)
        and item.get("role") == "assistant"
        and isinstance(item.get("content"), str)
        and bool(str(item["content"]).strip())
        for item in history
    )
    elliptical_reaction = (
        has_assistant_context
        and re.fullmatch(
            (
                r"[¿?¡!\s]*(?:que|como|por\s+que|what|how|why|"
                r"que\s+dijiste|what\s+did\s+you\s+say)[\s?!.]*"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if not explicit_nonunderstanding and not elliptical_reaction:
        return None
    return {
        "mode": "conversation",
        "operation": None,
        "question": "",
        "conversation_kind": "followup",
        "effect_count": "zero",
        "effect_operations": [],
        "effect_verification": "not_applicable",
        "response_language": _explicit_response_language(objective),
    }


def _current_public_role_question(objective: str) -> bool:
    """Recognize a time-sensitive office-holder fact that needs verification."""

    folded = effect_intent._strip_request_envelope(effect_intent._fold(objective))
    return (
        re.match(r"^[¿?¡!\s]*(?:quien|who)\b", folded, re.IGNORECASE) is not None
        and effect_intent._has(
            folded,
            r"\b(?:current|currently|actual|actualmente|ahora|now)\b",
        )
        and effect_intent._has(
            folded,
            r"\b(?:president|presidente|prime\s+minister|primer\s+ministro|"
            r"chancellor|canciller|governor|gobernador|mayor|alcalde|ceo)\b",
        )
    )


def _assistant_capability_aspiration(objective: str) -> bool:
    """Recognize third-person product wishes, never direct user commands."""

    folded = effect_intent._strip_request_envelope(effect_intent._fold(objective))
    if not folded:
        return False
    return (
        re.match(
            (
                r"^(?:"
                r"i\s+(?:want|would\s+like)\s+(?:baxy|the\s+assistant|"
                r"my\s+assistant|it)\s+to\s+(?:be\s+able\s+to|have\s+(?:the\s+)?"
                r"ability\s+to)|"
                r"i(?:'d|\s+would)\s+like\s+(?:baxy|the\s+assistant|my\s+assistant|"
                r"it)\s+to\s+(?:be\s+able\s+to|have\s+(?:the\s+)?ability\s+to)|"
                r"i\s+wish\s+(?:baxy|the\s+assistant|my\s+assistant|it)\s+could|"
                r"(?:baxy|the\s+assistant|my\s+assistant|it)\s+should\s+be\s+able\s+to|"
                r"(?:quiero|me\s+gustaria)\s+que\s+(?:baxy|el\s+asistente|"
                r"mi\s+asistente|este\s+asistente)\s+(?:pueda|pudiera|"
                r"sea\s+capaz\s+de)|"
                r"ojala\s+(?:baxy|el\s+asistente|mi\s+asistente|este\s+asistente)\s+"
                r"(?:pudiera|pueda|fuera\s+capaz\s+de)|"
                r"(?:baxy|el\s+asistente|mi\s+asistente|este\s+asistente)\s+"
                r"deberia\s+(?:poder|ser\s+capaz\s+de)"
                r")\b"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )


def _deictic_open_request(objective: str) -> bool:
    """Recognize an opening whose operand is a reference, not a catalog name."""

    folded = effect_intent._strip_request_envelope(effect_intent._fold(objective))
    if (
        effect_intent.explicit_non_action_frame(objective)
        or not effect_intent._application_desire_is_positive(folded)
        or len(effect_intent._request_clauses(folded)) != 1
    ):
        return False
    opening = effect_intent._application_open_request(folded)
    if opening is None:
        return re.fullmatch(
            r"[¿?¡!\s]*(?:abre|abri)(?:lo|la|los|las)"
            r"(?:\s*,?\s*(?:por favor|please|porfa|porfi|porfis|plis|pls|plz))?[.!?\s]*", folded,
        ) is not None
    target = re.sub(
        # cien-36 096 «ábreme eso porfa»: the colloquial politeness word was not
        # in this list, so the request stopped being a bare deictic and went to
        # the unsupported-effect contract, which answered that it could not
        # understand instead of asking what to open, as «ábreme eso» does.
        r"\s*,?\s*(?:por favor|please|for me|porfa|porfi|porfis|plis|pls|plz)[.!?\s]*$", "",
        opening.group("target"),
    ).strip(" .!?\t\r\n")
    return re.fullmatch(
        r"(?:est[aeo]s?|es[aeo]s?|aquell[ao]s?|it|them|"
        r"(?:this|that|these|those)(?:\s+ones?)?)"
        r"(?:\s*,?\s*(?:el|la|los|las)\s+que\s+"
        r"(?:(?:te|le|les)\s+)?(?:digo|dije|indico|indique|menciono|mencione))?",
        target,
    ) is not None


def _standalone_deictic_request(objective: str, history: object = None) -> bool:
    """Recognize a command whose required referent is entirely absent."""

    if _deictic_open_request(objective):
        return _previous_user_request(
            history if isinstance(history, list) else [], objective,
        ) is None
    if read_request(objective).has(INTENT_AMBIGUOUS_ACTION):
        return True
    folded = effect_intent._fold(objective).strip()
    return (
        re.fullmatch(
            # DIALOGUE1277 H0562 «Si hazlo», «dale, hacelo»: an assent that
            # carries the order itself («hazlo», voseo «hacelo») without any
            # prior request names no action. It went to the model, which said
            # it could not understand instead of asking which action.
            r"(?:(?:si|ok|okay|dale|bueno|vale|ya|yes|yeah|sure)\s*,?\s+)?"
            r"(?:(?:por favor|please)\s*,?\s+)?(?:"
            r"haz(?:lo|\s+(?:eso|esto|aquello))|"
            r"hace(?:lo|\s+(?:eso|esto|aquello))|"
            r"dale(?:\s+con)?\s+(?:eso|esto)|"
            r"do\s+(?:it|that|this)|"
            r"make\s+(?:it|that)\s+happen|"
            r"go\s+ahead(?:\s+with\s+(?:it|that|this))?"
            r")(?:\s*,?\s*(?:por favor|please))?[.!?]*",
            folded,
        )
        is not None
    )


_BARE_PATH = re.compile(
    r"^\s*(?:%[A-Za-z_][A-Za-z0-9_]*%|[A-Za-z]:|\\\\[^\\/:*?\"<>|\r\n]+)"
    r"(?:[\\/][^\\/:*?\"<>|\r\n]+)+\s*$"
)


def bare_path_file_name(objective: str) -> str | None:
    """FILES H0299 «%USERPROFILE%\\Desktop\\…\\ROADMAP.md»: a file path pasted
    alone, with no verb, names no request; the honest turn asks what to do
    with that file. Returns the file name (the last segment) or None."""

    text = objective.strip()
    if _BARE_PATH.match(text) is None or len(text) > 512:
        return None
    name = re.split(r"[\\/]", text.rstrip("\\/"))[-1].strip()
    if not name or "." not in name.strip(".") or re.search(r"\s{2,}", name):
        return None
    return name


_CUT_TAIL_WORDS = frozenset({
    "del", "de", "la", "el", "los", "las", "un", "una", "unos", "unas", "al",
    "y", "e", "o", "u", "con", "para", "por", "en", "que", "mi", "mis", "su",
    "sus", "tu", "tus", "the", "a", "an", "of", "and", "or", "with", "for", "my",
})


def cut_request_tail(objective: str) -> str | None:
    """FILES H0426 «…que contenga la fecha actual, el nombre del»: a request
    of six or more words that stops, without closing punctuation, on an
    article, preposition or conjunction arrived cut there. Returns the last
    three words (what the person will recognise) or None."""

    text = objective.strip()
    if not text or text[-1] in ".!?…»\")" or len(text) > 512:
        return None
    words = re.findall(r"[^\s]+", text)
    # UI1641 H0088 «Ve a Cotele en»: a go-to order whose destination stops on a
    # bare preposition arrived cut there even when short; four words suffice
    # under a go-to head, six otherwise (FILES H0426).
    go_to = re.match(
        r"^[¿?¡!\s]*(?:ve|anda|andate|entra|entrá|abre|abrí|llevame|llévame|navega|navegá|go|open|take\s+me)\s+(?:a|al|to)\b",
        effect_intent._fold(text),
    ) is not None
    if len(words) < (4 if go_to else 6):
        return None
    last = effect_intent._fold(words[-1]).strip(",;:")
    if last not in _CUT_TAIL_WORDS:
        return None
    return " ".join(words[-3:])


def _echoed_words(folded: str) -> bool:
    """CONVERSATION1150 H0410 «Artiro, artiro. Estimado, estimado.»: every
    word arrives at least twice and nothing else does; no assent, negation,
    question or request head. Words alone, however familiar, are not a
    request; the honest turn says so and asks what the person needs."""

    words = re.findall(r"[a-z]{2,}", folded)
    if not 4 <= len(words) <= 12 or len(set(words)) > 4:
        return False
    if any(words.count(word) < 2 for word in set(words)):
        return False
    if re.search(r"\d|[?¿]", folded):
        return False
    if any(
        word in {"si", "no", "dale", "ok", "okay", "bueno", "claro", "vale", "listo",
                 "yes", "yeah", "nope", "never", "nunca", "jamas", "hola", "hello", "baxy"}
        for word in words
    ):
        return False
    return not any(
        effect_intent._head_is(word, effect_intent._COVERAGE_ACTION_HEAD) for word in set(words)
    )


def _unresolved_input_kind(
    objective: str,
    known_names: Iterable[str] = (),
) -> str | None:
    """Name an input that carries no readable request at all.

    DIALOGUE1277 (H0287 «????», H0570 «1234567890», H0581 «a», H0181 «No.»,
    H0336 «no no no…»): with nothing to read, the model answered a generic
    help greeting, refused the letter as outside the catalog, or claimed a
    failure to understand a plain «no». ``"noise"`` is text without a single
    word of two letters; ``"bare_negation"`` is only negation tokens. Both
    are answered by a clarification composed for that situation, never by
    a guess at the meaning. A pending clarification keeps its own answer.
    """

    folded = effect_intent._fold(objective).strip()
    if not folded:
        return None
    names_folded = {
        token.casefold()
        for name in known_names
        if isinstance(name, str)
        for token in (name, *re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ'’-]*", name))
    }
    if (
        re.fullmatch(
            # DIALOGUE1491 H0393 «Ve a portal una.», H0541 «Ve Portal 2 UN»: a
            # go-to order whose destination ends in a bare article or
            # preposition is a message the transcription cut off; the owner
            # asks to understand it from context or to ask. With nothing to
            # complete it, the honest turn asks which portal or site.
            r"[\s¡!¿?]*(?:ve|anda|andate|entra|abre|abri|ir|llevame|navega|go|open|take\s+me)\s+"
            r"(?:(?:a|al|to)\s+)?(?:(?:el|la|the)\s+)?"
            r"(?:portal|pagina|sitio|web|site|page)\b[^.!?]{0,40}?"
            r"\s(?:un|una|unos|unas|el|la|los|las|de|del|en|al|a|y|con|para|por|the|to|of|and|at)"
            r"[\s.!?¿¡]*",
            folded,
        )
        is not None
    ):
        return "cut_destination"
    if (
        re.fullmatch(
            # DIALOGUE1487/1489 H0528 «Quiero que lo veas y de que se trata?»,
            # «Miralo y decime de qué se trata»: a request to look at
            # «it/this/that» and say what it is, with nothing named, has no
            # object to look at; the generic referent clarifier asked back
            # «¿De qué se trata?» or «¿Qué es eso que miraste?», so this kind
            # gets its own question: what should BAXY look at.
            r"[\s¡!¿?]*(?:"
            r"(?:quiero|necesito|quisiera)\s+que\s+(?:lo|la|los|las)\s+(?:veas|mires|revises|leas|chequees)|"
            r"(?:mira|miralo|mirala|ve|velo|vela|fijate|revisa|revisalo|revisala|chequea|chequealo|lee|leelo|leela)"
            r"(?:\s+(?:en\s+)?(?:eso|esto|lo|la|aquello))?|"
            r"(?:look\s+at|check(?:\s+out)?|see|read)\s+(?:it|this|that)(?:\s+out)?"
            r")"
            r"(?:\s*(?:,|y|and)\s*(?:me\s+)?(?:digas|decime|dime|contame|cuentame|tell\s+me)?\s*"
            r"(?:de\s+)?(?:que|what)\s+(?:se\s+trata|es|dice|it(?:'s|\s+is)(?:\s+about)?|it\s+says))?"
            r"[\s.!?¿¡]*",
            folded,
        )
        is not None
    ):
        return "deictic_look"
    if (
        re.fullmatch(
            # AUDIO1375 H0439 «Ponlo a 100 ahora», H0713 «devuelvelo a 100»: a
            # level for «lo» with nothing named before it; the only honest
            # answer asks what to set (volume, brightness…).
            r"[\s¡!¿?]*(?:pon[eé]?lo|ponla|pon[eé]?melo|pon[eé]?mela|dejalo|dejala|dejamelo|"
            r"devolvelo|devuelvelo|devolvela|devuelvela|subilo|subila|subimelo|bajalo|bajala|"
            r"bajamelo|llevalo|llevala|set\s+it|put\s+it|turn\s+it|leave\s+it|bring\s+it)\s+"
            r"(?:a|al|en|to|at|on|back\s+to)\s+(?:el\s+|the\s+)?\d{1,3}\s*(?:%|por\s+ciento|percent)?"
            r"(?:\s+(?:ahora|ya|now|de\s+nuevo|otra\s+vez|again|please|por\s+favor|porfa))*[\s.!?]*",
            folded,
        )
        is not None
    ):
        return "deictic_level"
    if (
        re.fullmatch(
            # UI1643 H0097 «ponle hola»: a text to put «to it» with nothing
            # named before it — no window, field, file or chat; the honest
            # turn asks where to write it.
            r"[\s¡!¿?]*(?:pon[eé]?le|ponele|pon[eé]?melo|put\s+on\s+it|write\s+on\s+it)\s+"
            r"(?!(?:a|al|por|para|que|en)\b)(?P<text>[¿?¡!\w][^.!?]{0,60}?)"
            r"(?:\s+(?:ahora|ya|now|please|por\s+favor|porfa))*[\s.!?]*",
            folded,
        )
        is not None
        and not re.search(
            r"\b(?:en|a|al|del|de)\s+(?:el|la|los|las|mi|mis|tu|tus|un|una|the|my|a)?\s*"
            r"(?:ventana|archivo|nota|chat|grupo|mensaje|correo|mail|documento|campo|titulo|"
            r"nombre|whatsapp|discord|telegram|window|file|note|chat|message|document|field)\b",
            folded,
        )
    ):
        return "deictic_text"
    if (
        re.fullmatch(
            r"[\s¡!¿?.,]*(?:no|nop|nope|nah|nunca|jamas)"
            r"(?:[\s,.!¡]+(?:no|nop|nope|nah|nunca|jamas))*[\s.!?]*",
            folded,
        )
        is not None
    ):
        return "bare_negation"
    if (
        re.search(r"[a-z]{2,}", folded) is None
        # «5+5» or «10*3» is an arithmetic expression, not noise.
        and re.search(r"\d\s*[-+*/x×÷=^%]\s*\d", folded) is None
    ):
        return "noise"
    if re.fullmatch(r"[\[(<][a-z0-9_. -]{1,60}[\])>][\s.!?]*", folded) is not None:
        # UNRES1855 H0639: the whole message is one bracketed token; whatever it
        # stands for, nothing in it is a request (a pasted placeholder, the
        # survey's «[PHONE_REDACTED]»). A shape rule for SHORT text in general
        # was measured and rejected: with no vocabulary it cannot tell
        # «¡Habristín!» from «pausá», «silencio» or «repetí», which the readers
        # do not resolve either and which the model answers correctly today.
        return "noise"
    if _overheard_speech(folded):
        return "overheard_speech"
    if re.fullmatch(r"[¿?¡!\s]*(?:hable|habla|hablame|hableme|hablanos|hablenos|hablalo|hablelo|speak|talk|tell)\s+(?:(?:de|sobre|about|of|me)\s+)?(?:de\s+)?(?:est[aeo]s?|es[aeo]s?|aquell[ao]s?|it|this|that|these|those)[.!?\s]*", folded) is not None:
        # UNRES1945 H0404 «Hable este.»: a speak/talk verb with a bare
        # demonstrative and nothing before it — nothing names what to talk
        # about; the honest turn asks that, never a chat opener.
        return "deictic_speak"
    _bare = re.fullmatch(r"[¿?¡!\s]*(?P<phrase>[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ'’-]+(?:\s+[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ'’-]+){0,2})\s*\?[\s.!?]*", str(objective).strip())
    if (
        _bare is not None
        # cien-83 091 «¿Estás?»: a sentence-initial capital is not a name. Two
        # words at least, none of them a Spanish word («Hola Baxy?», «Buenos
        # Días?» stay conversation) and not an English question opener.
        and len(_bare.group("phrase").split()) >= 2
        and not any(corrector.known_spanish(token) for token in _bare.group("phrase").split())
        and _bare.group("phrase").split()[0].casefold() not in {
            "are", "is", "do", "does", "did", "can", "could", "will", "would", "should", "what",
            "who", "where", "when", "why", "how", "which", "still", "you", "anything", "ready",
            "hello", "hi", "hey", "thanks", "thank", "good", "ok", "okay", "any", "got", "all",
            # «And Spotify?»: a conjunction opens a follow-up on the previous
            # question, which the scoped readers resolve; it is not a bare name.
            "and", "or", "but",
        }
        and not corrector.unknown_words(objective, known_names)
        # «Steam?», «Spotify?» name a catalog application on their own and
        # keep today's path; «Calendar Devil?» only shares a word with one.
        and _bare.group("phrase").casefold() not in names_folded
        and not (
            len(_bare.group("phrase").split()) == 1
            and _bare.group("phrase").casefold() in names_folded
        )
    ):
        # UNRES1945 H0160 «Calendar Devil?»: one to three capitalised words
        # and a question mark, no verb, no catalog name, real words in some
        # language; the model answered as if it were a question about BAXY.
        # The honest turn says it does not know what that refers to and asks.
        return "bare_phrase_question"
    if corrector.unintelligible_input(objective, known_names):
        # UNRES1941 H0210 «¡Habristín!»: every content word of the message is
        # unknown to the Spanish and English dictionaries, the catalog and the
        # product's own terms. The honest turn says that word did not come
        # through and asks to repeat it, never a greeting that fakes
        # understanding. Absent lexicon → never this kind.
        return "unknown_word"
    if _echoed_words(folded):
        return "echoed_words"
    if bare_path_file_name(objective) is not None:
        return "bare_path"
    if cut_request_tail(objective) is not None:
        return "cut_request"
    if (
        effect_intent.INDETERMINATE_WINDOW_CLAUSE.fullmatch(folded) is not None
        # REOPEN1993 H0263: «la otra/anterior/siguiente» is the window behind
        # the foreground one and switches; only «la mejor» and the like ask.
        and not effect_intent.other_window_switch_request(objective)
    ):
        # WINDOWS1537 H0392 «enfocá la mejor»: a window named only by «la
        # mejor» with nothing before it; the honest turn asks which.
        return "indeterminate_window"
    if (
        re.fullmatch(
            # KNOWLEDGE1523 H0424 «¿Cuál es su identidad secreta?», H0645
            # «¿Quién es de verdad?»: the real identity or name of someone
            # never named, with nothing before it; the honest turn asks whom.
            r"[\s¡!¿?]*(?:"
            r"(?:cual|cuales)\s+es\s+su\s+(?:identidad(?:\s+secreta|\s+real|\s+verdadera)?|"
            r"(?:verdadero|verdadera|autentico|autentica)\s+(?:nombre|identidad)|nombre\s+(?:real|verdadero|de\s+verdad))|"
            r"quien\s+es\s+(?:de\s+verdad|realmente|en\s+realidad|en\s+verdad|de\s+veras)|"
            r"what(?:'s|\s+is)\s+(?:his|her|their)\s+(?:secret\s+identity|real\s+(?:name|identity))|"
            r"who\s+(?:is|are)\s+(?:he|she|they)\s+really"
            r")[\s.!?¿¡]*",
            folded,
        )
        is not None
    ):
        return "missing_person_referent"
    if (
        re.fullmatch(
            # DIALOGUE1515 H0562 «Si hazlo»: agreement to do something when
            # nothing was proposed or asked; the honest turn says nothing is
            # pending and asks what to do (DIALOGUE1281: «¿Qué haces?»).
            r"[\s¡!¿?.,]*(?:(?:si|dale|ok|okay|bueno|claro|de\s+acuerdo|yes|yeah|yep|sure|obvio|vale)[\s,.!]*)?"
            r"(?:hazlo|hacelo|hacela|hazla|haz\s+lo|hace\s+lo|procede|do\s+it|go\s+ahead)"
            r"(?:\s+(?:ya|ahora|nomas|now|please|por\s+favor|porfa))*[\s.!?]*",
            folded,
        )
        is not None
    ):
        return "bare_confirmation"
    if (
        re.fullmatch(
            # DIALOGUE1515 H0205 «o en la de siempre.»: the tail of a sentence,
            # an alternative with nothing before it and no request inside;
            # the honest turn says only that part arrived and asks what it
            # refers to (DIALOGUE1281: a greeting).
            r"[\s¡!¿?]*(?:o|u|y|e|pero|sino|ni)\s+"
            r"(?:en|a|al|con|de|del|para|por|sin|sobre|desde|hasta)\s+"
            r"(?:la|el|los|las|lo|una|un|mi|tu|su|esa|ese|esta|este|aquella|aquel)\s+"
            r"[a-z][a-z0-9 ]{0,40}[\s.!?]*",
            folded,
        )
        is not None
        # «y con la calculadora abre algo» carries an order; only a fragment
        # without any order verb is a dangling alternative.
        and re.search(
            r"\b(?:abre|abri|abris|abrir|abrime|pone|pon|poneme|poner|busca|buscame|buscar|cierra|cerra|cerrar|"
            r"reproduce|manda|envia|escribe|crea|guarda|recuerda|recorda|sube|subi|baja|silencia|apaga|prende|"
            r"enciende|lanza|inicia|muestra|mostrame|dime|decime|contame|explica|lee|copia|pega|borra|elimina|"
            r"instala|descarga|toma|saca|captura|open|play|search|close|send|write|set|turn|show|tell|launch|"
            r"start|stop|find|take|click)\b",
            folded,
        )
        is None
    ):
        return "dangling_alternative"
    if (
        re.fullmatch(
            # IDENTITY1323 H0296 «Tú eres como eso»: compared with something
            # never named; the only honest answer asks what «eso» is.
            r"[\s¡!¿?]*(?:(?:tu|vos|usted)\s+)?(?:eres|sos|eri|es)\s+"
            r"(?:como|igual\s+(?:a|que)|parecid[oa]\s+a|lo\s+mismo\s+que)\s+"
            r"(?:eso|esto|aquello|ese|esa|aquel|aquella)[\s.!?]*|"
            r"[\s¡!¿?]*(?:you\s+are|you'?re|u\s+r|ur)\s+(?:just\s+)?"
            r"(?:like|the\s+same\s+as|similar\s+to)\s+(?:that|this|it|those)[\s.!?]*",
            folded,
        )
        is not None
    ):
        return "dangling_comparison"
    return None


_OVERHEARD_ACTION_WORDS = re.compile(
    # An order verb counts where a clause starts: after the beginning, a
    # punctuation mark or a connective («…, toma un screenshot», «y ve que
    # hay»); «si hace bien el trabajo» or «la ve y si no» inside a stretch of
    # talk is not an order to BAXY.
    r"(?:^|[,.;:!¡¿]\s*|\b(?:y|o|e|u|baxy|entonces|luego|despues|ahora|primero|tambien)\s+)"
    r"(?:baxy|abre|abri|abris|abrir|abrime|pone|pon|poneme|pongas|poner|busca|buscame|buscar|"
    r"cierra|cerra|cerrar|reproduce|reproduci|manda|mandame|envia|enviame|escribe|escribi|crea|"
    r"guarda|guardame|recuerda|recorda|recordame|sube|subi|subile|baja|baji|bajale|silencia|"
    r"apaga|prende|enciende|lanza|inicia|muestra|mostrame|dime|decime|contame|cuentame|explica|"
    r"explicame|avisame|avisa|llama|llamame|programa|agenda|calcula|traduce|traducime|lee|leeme|"
    r"copia|pega|borra|elimina|instala|desinstala|descarga|configura|conecta|desconecta|"
    r"toma|tomame|saca|sacame|captura|capturame|identifica|mira|mirame|revisa|revisame|haz|hace|haceme|"
    r"dale|clic|click|clickea|presiona|pulsa|selecciona|elige|escoge|ejecuta|corre|ve|anda|entra|"
    r"screenshot|dime|responde|contesta|resume|resumime|completa|completalo|completala|termina|terminalo|"
    r"confirma|confirmalo|acepta|aceptalo|cancela|cancelalo|"
    r"open|play|search|close|send|write|set|turn|remind|show|tell|launch|start|stop|find|take|click|"
    r"puedes|podes|podrias|puede|quiero\s+que|necesito\s+que|me\s+(?:ayudas|ayudarias|dices|decis|cuentas|contas|explicas))\b"
    # «Mira, bueno, la neta…», «Dale, dale.»: a verb followed by a comma or a
    # period is a discourse marker in talk, not an order with an object.
    r"(?!\s*[,.;])"
)


def _overheard_speech(folded: str) -> bool:
    """DIALOGUE1513: a long stretch of talk with no request for BAXY.

    H0006, H0139, H0332, H0372, H0429, H0441, H0483, H0735: the microphone
    caught other people's conversation or a broadcast (fifteen words or more,
    no question, no order verb, no vocative). Nothing in it is addressed to
    the assistant; DIALOGUE1281 measured the model reconstructing the
    fragment or answering it as if it were. The honest turn says it finds no
    request for it in what arrived and asks whether the person needs
    something."""

    if "?" in folded or "¿" in folded:
        return False
    words = re.findall(r"[a-z0-9]+", folded)
    if len(words) < 15:
        return False
    return _OVERHEARD_ACTION_WORDS.search(folded) is None and "baxy" not in folded


def _general_factoid_prompt(objective: str) -> bool:
    folded = effect_intent._strip_request_envelope(effect_intent._fold(objective))
    return (
        re.fullmatch(
            (
                r"[¿?¡!\s]*(?:"
                r"(?:please\s+)?tell\s+me\s+the\s+score\s+of\s+the\s+game|"
                r"what\s+sound\s+does\s+(?:an?\s+|the\s+)?"
                r"[a-z][a-z .'-]{0,48}\s+make|"
                r"(?:(?:podrias|puedes|can\s+you|could\s+you)\s+)?"
                r"(?:confirmar|confirm)\s+(?:si|whether)\s+"
                r"[a-z][a-z .'-]{0,64}\s+(?:esta\s+casad[oa]|is\s+married)|"
                # «me puedes dar una receta…»: the envelope strip already took
                # «me puedes», so «dar» may stand alone in front of the recipe.
                r"(?:(?:me\s+)?(?:puedes|podrias)\s+)?(?:dar\s+)?"
                r"(?:una\s+)?receta(?:\s+casera)?\s+(?:de|para)\s+\S.+|"
                r"cual\s+es\s+la\s+receta\s+(?:de|del)\s+\S.+|"
                r"what\s+(?:all\s+)?(?:goes|ingredients?\s+go)\s+into\s+"
                r"(?:(?:a|the)\s+)?\S.{0,96}\b(?:cake|dish|recipe)\b|"
                r"(?:necesito|quiero)\s+(?:una\s+)?receta\s+con\s+"
                r"(?:los\s+)?ingredientes\b.{0,120}|"
                r"i\s+need\s+to\s+know\s+more\s+about\s+(?:the\s+)?"
                r"(?:parade|festival|fair|concert)\s+(?:this|next)\s+weekend|"
                r"(?:give|show)\s+(?:me\s+)?details\s+(?:of|about)\s+"
                r"(?!(?:my|this|the)\s+(?:computer|pc|device|order)\b)"
                r"[a-z][a-z .'-]{1,96}|"
                r"(?:cuentame|contame|tell\s+me)\s+(?:todo|all)\s+"
                r"(?:sobre|about)\s+(?!(?:mi|mis|my|this|este|esta)\b)"
                r"[a-z][a-z .'-]{1,96})[\s?!.]*"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )


def _personal_checkin_statement(objective: str) -> bool:
    folded = effect_intent._strip_request_envelope(effect_intent._fold(objective))
    if (
        re.fullmatch(
            (
                r"my\s+day\s+is\s+going\s+(?:well|great|fine|okay|ok)"
                r"(?:\s*[,;]?\s*add\s+a\s+memo)?[\s.!?]*"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    ):
        return True
    # MEMORY1501 H0174 «Me gusta tomar café.»: a first-person taste or
    # preference with nothing asked is a statement to acknowledge, not an
    # order (MEMORY1245 asked where to go for coffee). The reader is shared
    # with the preference_ack presentation shape (MEMORY1503).
    return effect_intent.first_person_preference(objective) is not None


def _closed_unsupported_request(objective: str) -> bool:
    """Close requests whose missing authority cannot be recovered from a tool."""

    folded = effect_intent._strip_request_envelope(effect_intent._fold(objective))
    standalone_speed = (
        re.fullmatch(
            r"(?:rapido|mas\s+rapido|faster|quicker)[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    external_console_correction = (
        re.fullmatch(
            r"i\s+want\s+to\s+play\s+\S.{0,120}\s+on\s+the\s+"
            r"(?:switch|xbox|playstation|wii)\s*[,;]?\s*i\s+mean\s+the\s+"
            r"(?:switch|xbox|playstation|wii)[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    external_console_game_request = (
        re.fullmatch(
            r"(?:quiero|quisiera|i\s+want\s+to)\s+(?:jugar|play)\s+"
            r"\S.{0,160}\s+(?:en|on)\s+(?:(?:la|the)\s+)?"
            r"(?:play|playstation|xbox|switch|wii)\b.{0,96}[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    referential_answer_review = (
        re.fullmatch(
            r"(?:mira|revisa|comprueba|look\s+at|review|check)\s+"
            r"(?:lo\s+que|what)\s+(?:escribiste|wrote)\s+"
            r"(?:para|for|en|in)\s+(?:esta|this)\s+"
            r"(?:pregunta|question|respuesta|answer)[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    nominal_reminder_fragment = re.fullmatch(
        r"(?:recordatorio|reminder)\s+(?:de|for|about)\s+"
        r"\S(?:.{0,80}?\S)?[\s.!?]*",
        folded,
        re.IGNORECASE,
    ) is not None and not effect_intent._reminder_has_actionable_due(folded)
    transactional_purchase_correction = (
        re.fullmatch(
            r"(?:compra|comprar|buy|purchase|order)\b.{0,160}"
            r"\b(?:paga|pagar|pay|paypal|tarjeta|card)\b.{0,120}"
            r"\b(?:no\s+mejor|mejor|i\s+mean|make\s+that)\b.{0,96}"
            r"\b(?:tarjeta|card|paypal|debito|credito|debit|credit)\b"
            r"[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    corrected_payment_purchase = (
        re.fullmatch(
            r"(?:necesito|quiero|i\s+need|i\s+want)\b.{0,160}"
            r"\b(?:conseguir|comprar|buy|get|purchase|pagar|pay)\b.{0,160}"
            r"\b(?:tarjeta|card|visa|mastercard|paypal|bizum)\b.{0,120}"
            r"\b(?:bueno\s+mejor|mejor|actually|i\s+mean|instead)\b.{0,96}"
            r"\b(?:tarjeta|card|visa|mastercard|paypal|bizum)\b"
            r"[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    shopping_list_statement = (
        re.fullmatch(
            r"(?:items?|things?)\s+to\s+get\s+(?:are|include)\s+"
            r"\S.{0,320}[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    vague_food_location = (
        re.fullmatch(
            r"(?:(?:alexa|bax[yi])\s+)?(?:donde\s+esta|where\s+is)\s+"
            r"(?:mi|my)\s+(?:comida|food|order|pedido)[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    providerless_order_status = (
        re.fullmatch(
            r"(?:how\s+is|what(?:'s|\s+is)\s+the\s+status\s+of|"
            r"como\s+va|cual\s+es\s+el\s+estado\s+de)\s+"
            r"(?:mi|my|the)\s+(?:order|pedido)[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    providerless_card_purchase = (
        re.fullmatch(
            r"(?:can|could)\s+i\s+(?:get|buy|order)\s+\S.{0,160}"
            r"\bwith\s+(?:my|a)\s+(?:credit|debit)\s+card\b[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    corrected_unavailable_game = (
        re.fullmatch(
            r"(?:quitar|quita|remove)\b.{0,80}"
            r"\b(?:quiero\s+decir|mejor|i\s+mean|actually)\b.{0,48}"
            r"\b(?:poner|pon|play|launch|open)\b.{0,96}[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    first_person_future_game_statement = (
        re.fullmatch(
            r"(?:voy\s+a|i(?:'m|\s+am)\s+going\s+to)\s+"
            r"(?:echar|jugar|play)\b.{0,200}\b(?:partida|game)\b.{0,160}"
            r"[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    application_inventory_list = (
        re.fullmatch(
            r"(?:muestra|mostrar|muestrame|ensena|ensename|ensenarme|lista|"
            r"listame|show|list|ver)\s+"
            r"(?:(?:me|the|las?|todas?|all|ah)\s+)*(?:apps?|aplicaciones?)"
            r"(?:\s+(?:instalad[oa]s?|descargad[oa]s?|installed|downloaded))?"
            r"(?:\s+(?:hoy|today))?[\s.!?]*|"
            r"(?:ver|show)\s+(?:(?:las?|the)\s+)?(?:apps?|aplicaciones?)\s+"
            r"(?:instalad[oa]s?|installed)\s*[,;]?\s*"
            r"(?:digo|i\s+mean)\s+(?:descargad[oa]s?|downloaded)[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    unsupported_open_game_status = (
        re.fullmatch(
            r"(?:juegos?|games?)\s+(?:abiertos?|open|running|ejecutandose)"
            r"[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    return (
        standalone_speed
        or external_console_correction
        or external_console_game_request
        or referential_answer_review
        or nominal_reminder_fragment
        or transactional_purchase_correction
        or corrected_payment_purchase
        or shopping_list_statement
        or vague_food_location
        or providerless_order_status
        or providerless_card_purchase
        or corrected_unavailable_game
        or first_person_future_game_statement
        or application_inventory_list
        or unsupported_open_game_status
    )


def _explicit_stable_no_effect_turn_decision(
    objective: str,
    history: object = None,
    *,
    pending_clarification: bool | None = None,
) -> dict[str, object] | None:
    """Close only unambiguous non-effect clauses before tool selection.

    The model remains responsible for the natural-language reply.  This
    classifier grants no operation authority; it prevents an erroneous leaf
    proposal from turning a clearly conversational turn into a second, slow
    semantic clarification.  The patterns deliberately cover closed syntactic
    envelopes rather than catalog nouns, and pending clarifications always go
    back to the model with their dialogue context.
    """

    explicit_non_action = effect_intent.explicit_non_action_frame(objective)
    if explicit_non_action:
        return {
            "mode": "conversation",
            "operation": None,
            "question": "",
            "conversation_kind": "knowledge",
            "effect_count": "zero",
            "effect_operations": [],
            "effect_verification": "not_applicable",
            "response_language": _explicit_response_language(objective),
        }
    if _history_has_pending_clarification(history, pending_clarification):
        return None
    folded = effect_intent._strip_request_envelope(effect_intent._fold(objective))
    if not folded:
        return None

    assistant_capability_aspiration = _assistant_capability_aspiration(objective)
    standalone_deictic_request = _standalone_deictic_request(objective, history)
    personal_checkin_statement = _personal_checkin_statement(objective)
    closed_unsupported_request = _closed_unsupported_request(objective)

    definition = re.match(
        (
            r"^[¿?¡!\s]*(?:que\s+es|que\s+son|what\s+(?:is|are|es)|what's|"
            r"para\s+que\s+sirve|explain\s+what)\b"
        ),
        folded,
        re.IGNORECASE,
    ) is not None and not effect_intent._has(
        folded,
        (
            r"\b(?:actual|actualmente|ahora|current|currently|right\s+now|"
            r"volumen|volume|hora|time|fecha|date|estado|status|"
            r"sonando|playing|usando|using)\b"
        ),
    )
    component_description = re.match(
        (
            r"^[¿?¡!\s]*(?:describe(?:\s+about)?|describeme|explain|"
            r"tell\s+me\s+about)\s+"
            r"(?:(?:el|la|un|una|the|a)\s+)?"
            r"(?:(?:computer|pc|ordenador|computador)\s+)?"
            r"(?:disco\s+duro|hard\s+(?:drive|disk)|ssd|hdd|"
            r"procesador|processor|cpu|"
            r"tarjeta\s+grafica|graphics\s+card|gpu|memoria\s+ram|ram)\b"
        ),
        folded,
        re.IGNORECASE,
    ) is not None and not effect_intent._has(
        folded,
        (
            r"\b(?:actual|actualmente|ahora|current|currently|right\s+now|"
            r"estado|status|uso|usage|usando|using|libre|free|capacidad|capacity|"
            r"temperatura|temperature|cuanto|cuanta|how\s+much)\b"
        ),
    )
    geographic_factoid = (
        re.match(
            (
                r"^[Â¿?Â¡!\s]*(?:tell\s+me\s+about|cuentame\s+sobre)\s+"
                r"(?!(?:my|this|the|mi|este|esta)\s+"
                r"(?:computer|pc|device|ordenador|computador|dispositivo)\b)"
                r"[a-z][a-z .'-]{1,80}\s+"
                r"(?:location|geography|ubicacion|geografia)[\s?!.]*$"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    personal_address_request = (
        re.fullmatch(
            (
                r"[¿?¡!\s]*(?:(?:dime|dame)\s+(?:la\s+)?direccion\s+de|"
                r"tell\s+me\s+(?:the\s+)?address\s+of|"
                r"what\s+is\s+(?:the\s+)?address\s+of)\s+"
                r"[a-z][a-z .'-]{1,96}[\s?!.]*"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    nominal_concept_fragment = (
        re.fullmatch(
            (
                r"[Â¿?Â¡!\s]*(?:encontrar|buscar|find|finding)\s+"
                r"(?:(?:una|a)\s+)?(?:ruta|route)[\s?!.]*"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    procedure = (
        re.match(
            (
                r"^[¿?¡!\s]*(?:"
                r"como\s+(?:puedo|podria|debo|deberia|hago\s+para|se)\b|"
                r"(?:explica|explicame|explain)\s+(?:como|how)\b|"
                r"how\s+(?:do|can|could|would|should)\s+"
                r"(?:i|we|you)\b|how\s+to\b|explain\s+how\s+to\b"
                r")"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    content_drafting = conversation_only_content_request(objective)
    stable_knowledge_prompt = (
        re.match(
            (
                r"^[¿?¡!\s]*(?:"
                r"(?:define|explica|explicame|explain)\b|"
                r"(?:por\s+que|why)\b|"
                r"(?:(?:que|what)\s+quiere\s+decir)\b|"
                r"what\s+does\b.{0,96}\b(?:mean|significa|decir)\b|"
                r"(?:que|what(?:\s+is)?)\s+(?:diferencia|difference)\b|"
                r"(?:cuentame|contame|tell\s+me)\b.{0,48}\b(?:historia|history)\b|"
                r"(?:cuentame|contame|tell\s+me)\b.{0,48}\b(?:chiste|joke)\b|"
                r"(?:resume|summarize)\b|"
                r"(?:propon|propone|sugiere|suggest)\b.{0,48}\b(?:nombres?|names?)\b|"
                r"(?:traduce|translate)\b|"
                r"(?:ayudame|help\s+me)\b.{0,64}\b(?:practicar|practice|rehearse)\b"
                r")"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    general_factoid_prompt = _general_factoid_prompt(objective)
    joke_request = (
        re.match(
            (
                r"^[¿?¡!\s]*(?:"
                r"i(?:'d|\s+would)?\s+like\s+to\s+hear|let\s+me\s+hear|"
                r"me\s+gustaria\s+(?:oir|escuchar)|"
                r"(?:find|get|give|tell)\s+me|"
                r"(?:buscame|dame|cuentame|contame))\b.{0,80}"
                r"\b(?:jokes?|chistes?)\b"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    knowledge_after_negated_effect = (
        re.match(
            (
                r"^(?:no|nunca|jamas|do\s+not|don't|never)\b[^;]{1,160};\s*"
                r"(?:(?:solo|solamente|just|only)\s+)?"
                r"(?:explica|explicame|explain|define|dime\s+que|tell\s+me\s+what|"
                r"what\s+does)\b"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
        # Explaining after a prohibition cannot cancel a later requested effect.
        # Reuse the clause reader, which splits at independent action heads.
        and len(effect_intent._request_clauses(folded)) == 1
    )
    opinion_prompt = (
        re.match(
            (
                r"^[¿?¡!\s]*(?:what\s+do\s+you\s+think\s+about|"
                r"que\s+opinas\s+de|cual\s+es\s+tu\s+opinion\s+(?:de|sobre))\b"
                r"\s+\S.+$"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    capability_question = (
        re.fullmatch(
            (
                r"[¿?¡!\s]*(?:what\s+(?:can|can\s*t|cannot)\s+you\s+do|"
                r"que\s+(?:puedes|no\s+puedes)\s+hacer|"
                r"cuales\s+son\s+tus\s+capacidades)"
                r"(?:\s+baxy)?[\s?!.]*"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    # Both detectors below judge a *hypothesis*, and both are anchored to the
    # front of the request. A frame that denies an instruction -- "No assignment
    # for the computer, just answer me: what would happen if ..." -- sits in
    # front of the body and neither `_strip_request_envelope` nor
    # `explicit_non_action_frame` removes it, so the anchor never reaches the
    # hypothesis. Measured on the current tree: 21 of 21 framed surfaces missed
    # across three languages and the seven frames R27 used, against 3 of 3
    # detected bare.
    #
    # The frame also poisons the judgement itself: "This would never be a
    # provision for the PC" contributes its own "would" to the hypothetical
    # test, which is the frame speaking rather than the person.
    #
    # `_strip_explicit_no_action_frame` is the repair R25 already paid for, it
    # is generated from the same cognate groups as the positive instruction
    # frame, and removing a denial can only move a turn toward conversation.
    # It is applied **only here**: the other anchored patterns in this function
    # keep reading the unstripped text on purpose, because `leading_negation`
    # is what closes a denial-framed body that merely quotes an order, and
    # taking that net away would send such a body down to the model.
    hypothesis_folded = effect_intent._strip_explicit_no_action_frame(folded)
    # The strip removing something *is* the recognition: the generated class
    # matched, so the person explicitly denied issuing an instruction. Reading
    # it as its own conversation signal replaces two accidents.
    #
    # `leading_negation` is a short hand-list anchored at the very first token,
    # and it misses a denial that does not open with one of its words: "Ninguna
    # encomienda para el ordenador, contéstame nomás: ..." returned nothing at
    # all before this, and "This would never be a provision for the PC, ..."
    # was held only because the frame's own "would" was being counted as the
    # person's hypothesis -- cover that vanishes the moment that misreading is
    # corrected, as it is two lines below.
    #
    # This is one-sided in the safe direction, unlike stripping the frame for
    # every pattern: it can only close a turn as conversation, never grant an
    # effect. The generated class already requires a negation, an instruction
    # noun and a machine noun before the colon, so an ordinary request cannot
    # trip it.
    explicit_denial_frame = hypothesis_folded != folded
    past_or_hypothetical = effect_intent._is_past_or_hypothetical_state(
        hypothesis_folded
    )
    counterfactual_hypothetical = effect_intent._has(
        hypothesis_folded,
        r"^(?:si|if)\b.{0,160}\b(?:tuviera|tuviese|comprara|comprase|"
        r"compraria|abriria|podria|had|bought|would)\b|"
        r"^(?:que\s+ocurriria\s+si|what\s+(?:would\s+happen|pasaria)\s+"
        r"(?:si|if))\b",
    )
    nominal_effect_observation = (
        re.match(
            (
                r"^[Â¿?Â¡!\s]*(?:(?:el\s+)?cierre\s+de\s+.+?\s+"
                r"(?:podia|podria|puede)\s+(?:hacer\s+)?perder\b|"
                r"(?:closing|the\s+closing\s+of)\s+.+?\s+"
                r"(?:could|might|can)\s+(?:cause\s+)?(?:lose|losing)\b)"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    leading_negation = (
        re.match(
            r"^[¿?¡!\s]*(?:no|nunca|jamas|do\s+not|don't|never)\b",
            folded,
            re.IGNORECASE,
        )
        is not None
        # A negative opening cannot cancel a later positive request. Leave
        # compound turns to the normal selector instead of forcing zero effects.
        # A justification after the separator («No cierres Chrome, lo estoy
        # usando», CLOSE1219-1223/010) is still the same prohibition.
        and len(effect_intent._request_clauses(folded)) == 1
        and (
            not any(separator in folded for separator in (",", ";"))
            or re.match(
                # KNOW1835 «No me contestes nada, solo estaba pensando en voz alta.»:
                # a past-tense or «just …» explanation is the same justification.
                r"^\s*(?:(?:solo|just)\s+)?(?:(?:que\s+)?(?:lo|la|los|las|me|te)\s+)?"
                r"(?:estoy|estamos|esta|estan|estaba|estabamos|era|sigo|seguimos|necesito|necesitamos|"
                r"i'?m|i\s+am|i\s+was|we\s+were|it'?s|it\s+was|we'?re|they'?re|porque|because|ya\s+que)\b",
                re.split(r"[,;]", folded, 1)[1],
                re.IGNORECASE,
            )
            is not None
        )
    )
    other_device = effect_intent._has(
        folded,
        (
            r"\b(?:en|on)\s+(?:(?:el|la|un|una|mi)\s+|"
            r"(?:(?:my|the|a)\s+)?(?:[a-z]+(?:'s)?\s+){0,2})?"
            r"(?:telefono|movil|celular|phone|smartphone|tablet|ipad|"
            r"iphone|reloj|watch|consola|console|xbox|playstation)\b"
        ),
    ) and not effect_intent._has(
        folded,
        (
            r"\b(?:bluetooth|conecta|conectar|connect|empareja|"
            r"emparejar|pair|sincroniza|sincronizar|sync)\b"
        ),
    )
    assistant_silence_preference = (
        re.match(
            (
                r"^[¿?¡!\s]*(?:"
                r"no\s+(?:(?:me\s+)?hables|digas\s+nada|respondas)\s+"
                r"(?:hasta\s+que|a\s+menos\s+que)|"
                r"(?:do\s+not|don't)\s+(?:speak|talk|say\s+anything|respond)\s+"
                r"(?:until|unless)"
                r")\b"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    assistant_command_history_request = (
        re.match(
            (
                r"^[¿?¡!\s]*(?:"
                r"(?:puedes\s+)?(?:mostrarme|muestrame|dime|lista)\b.{0,80}"
                r"\b(?:mis|tus)\s+(?:comandos|ordenes)\s+"
                r"(?:recientes|anteriores|historial)\b|"
                r"(?:can\s+you\s+)?(?:show|tell|list)\b.{0,80}"
                r"\b(?:my|your)\s+(?:recent\s+)?commands?\b"
                r")"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    current_public_role_question = _current_public_role_question(objective)
    underspecified_video_request = effect_intent._underspecified_video_request(folded)
    interactive_play = effect_intent._has(
        folded,
        (
            r"\bplay\b.{0,80}\b(?:with|against)\s+"
            r"(?:me|us|(?!(?:the|a|an|my|computer|cpu|machine|bot)\b)"
            r"[a-z][a-z.'-]{1,40})\b|"
            r"\b(?:juega|jugar|juguemos)\b.{0,80}"
            r"\b(?:conmigo|con nosotros|contra mi|contra nosotros|"
            r"(?:con|contra)\s+(?!(?:el|la|un|una|mi|computador|computadora|"
            r"pc|maquina|bot)\b)[a-z][a-z.'-]{1,40})\b"
        ),
    )
    acknowledged_hearing = (
        re.fullmatch(
            (
                r"[¿?¡!\s]*(?:(?:si\s*[,;:]?\s*){1,2}"
                r"(?:ya\s+)?(?:te\s+)?(?:oigo|escucho)|"
                r"(?:yeah\s*[,;:]?\s*){1,2}i\s+hear\s+you)"
                r"[\s?!.]*"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    if not (
        assistant_capability_aspiration
        or standalone_deictic_request
        or personal_checkin_statement
        or closed_unsupported_request
        or definition
        or component_description
        or geographic_factoid
        or personal_address_request
        or nominal_concept_fragment
        or procedure
        or content_drafting
        or stable_knowledge_prompt
        or general_factoid_prompt
        or joke_request
        or knowledge_after_negated_effect
        or opinion_prompt
        or capability_question
        or past_or_hypothetical
        or counterfactual_hypothetical
        or explicit_denial_frame
        or nominal_effect_observation
        or leading_negation
        or other_device
        or assistant_silence_preference
        or assistant_command_history_request
        or current_public_role_question
        or underspecified_video_request
        or interactive_play
        or acknowledged_hearing
    ):
        return None
    return {
        "mode": "conversation",
        "operation": None,
        "question": "",
        "conversation_kind": (
            "social"
            if acknowledged_hearing or personal_checkin_statement
            else "unsupported"
            if personal_address_request or closed_unsupported_request
            else "knowledge"
            if (
                definition
                or component_description
                or geographic_factoid
                or nominal_concept_fragment
                or procedure
                or content_drafting
                or stable_knowledge_prompt
                or general_factoid_prompt
                or joke_request
                or knowledge_after_negated_effect
                or opinion_prompt
                or capability_question
                or counterfactual_hypothetical
                or (leading_negation and not assistant_silence_preference)
                # A denial of instruction asks to be talked to, not refused.
                # "unsupported" would answer an answerable question with an
                # inability, which is the visible defect R125 measured.
                or explicit_denial_frame
            )
            else "followup"
            if (
                nominal_effect_observation
                or assistant_silence_preference
                or underspecified_video_request
                or standalone_deictic_request
            )
            else "unsupported"
        ),
        "effect_count": "zero",
        "effect_operations": [],
        "effect_verification": "not_applicable",
        "response_language": (
            "en"
            if acknowledged_hearing and re.search(r"\bi\s+hear\s+you\b", folded)
            else _explicit_response_language(objective)
        ),
    }


def _explicit_system_status_scope(evidence: str) -> dict[str, object] | None:
    """Name the `system.status` scope only when the text says it unambiguously.

    The scope is a closed enum of the catalog descriptor, and the effect
    recognizer already decides which measurable domains the request names. When
    it names exactly one —or a pair the enum measures in a single reading— that
    value is a literal supported by the text, not an inference, so it can skip
    the model exactly like every other explicit argument.

    Every other case abstains and keeps the existing grounding: two scopes the
    enum cannot express, a GPU request that does not say whether it asks for
    identity or usage, and anything the domain veto already rejected. Core
    still validates the schema; this only avoids asking the model for a value
    the text already contains.
    """

    folded = effect_intent._fold(evidence)
    if not effect_intent._system_status_domain(folded):
        return None
    named = effect_intent._machine_status_scopes(folded)
    if not named:
        # «cómo anda la pc», «estado del sistema»: el equipo sin un alcance
        # concreto es exactamente el resumen del enum.
        return {"scope": "summary"}
    if named == {"cpu", "memory"}:
        return {"scope": "cpu_memory"}
    if named == {"os", "memory"}:
        return {"scope": "os_memory"}
    if len(named) != 1:
        return None
    only = next(iter(named))
    if only == "gpu":
        usage = effect_intent._has(
            folded,
            r"\b(?:uso|usa|usan|usando|usage|ocupad[oa]|llen[oa]|busy|"
            r"in\s+use|utili[sz]ation|load|tan\s+\w+)\b",
        )
        identity = effect_intent._has(
            folded,
            r"\b(?:que\s+gpu|cual|which|what\s+gpu|modelo|model|tarjeta|"
            r"placa|tengo|tiene|instalad[oa]|have)\b",
        )
        # «cuánto uso tiene la GPU» names usage; its «tiene» is the verb of
        # the usage question, not an identity cue. Abstaining here sent the
        # model to the summary scope, which carries no GPU (SYSTEM1169/005).
        identity_named = effect_intent._has(
            folded,
            r"\b(?:que\s+gpu|cual|which|what\s+gpu|modelo|model|tarjeta|"
            r"placa|instalad[oa])\b",
        )
        if usage and not identity_named:
            return {"scope": "gpu_usage"}
        if identity and not usage:
            return {"scope": "gpu_identity"}
        return None
    return {"scope": only} if only in _SYSTEM_STATUS_SCOPES else None


# Enum cerrado del descriptor `system.status` del catálogo.
_SYSTEM_STATUS_SCOPES = frozenset(
    {
        "battery",
        "cpu",
        "cpu_memory",
        "disk",
        "gpu_identity",
        "gpu_usage",
        "memory",
        "os",
        "os_memory",
        "summary",
    }
)


def _explicit_message_recipient_arguments(
    evidence: str,
) -> dict[str, object] | None:
    """Extract one supported channel and one literal recipient or abstain."""

    folded = effect_intent._fold(evidence)
    channels = {
        "whatsapp" if match in {"whatsapp", "wsp"} else "discord"
        for match in re.findall(r"\b(?:whatsapp|wsp|discord)\b", folded)
    }
    if len(channels) != 1:
        return None
    patterns = (
        (
            r"\b(?:por|en|via)\s+(?:whatsapp|wsp|discord)\s+"
            r"(?:hazle\s+llegar|cu[eé]ntale|dile|decile)\s+a\s+"
            r"(?P<recipient>[^,;.!?]{1,80}?)\s+"
            r"(?:que|(?:el|the)\s+(?:mensaje|message)|the\s+report)\b"
        ),
        (
            r"\b(?:through|on|via)\s+(?:whatsapp|discord)\s+"
            r"let\s+(?P<recipient>[^,;.!?]{1,80}?)\s+know\b"
        ),
        (
            r"\b(?:through|on|via)\s+(?:whatsapp|discord)\s+"
            r"get\s+(?:the\s+)?(?:note|message|update)\s+.+?\s+to\s+"
            r"(?P<recipient>[^,;.!?]{1,80})$"
        ),
        (
            r"\b(?:por|en|via)\s+(?:whatsapp|wsp|discord)\s+"
            r"(?:dile|decile)\s+a\s+"
            r"(?P<recipient>[^,;.!?\s]{1,80})\s+\S"
        ),
        (
            r"\b(?:escr[ií]be(?:le)?|write)\s+(?:en|on|via)\s+"
            r"(?:whatsapp|wsp|discord)\s+(?:a\s+|to\s+)?"
            r"(?P<recipient>[^,;.!?]{1,80}?)\s+(?:que|that)\b"
        ),
        (
            r"\b(?:escr[ií]be(?:le)?|write\s+to)\s+"
            r"(?:a\s+|to\s+)?(?P<recipient>[^,;.!?]{1,80}?)\s+"
            r"(?:en|on|via)\s+(?:whatsapp|wsp|discord)\s+(?:que|that)\b"
        ),
        (
            r"\bpasa\s+(?:por|via)\s+(?:whatsapp|wsp|discord)\s+a\s+"
            r"(?P<recipient>[^,;.!?]{1,80}?)\s+"
            r"(?:(?:el\s+)?(?:texto|mensaje)|que)\b"
        ),
        (
            r"\bpass\s+(?:to\s+)?(?P<recipient>[^,;.!?]{1,80}?)\s+"
            r"(?:the\s+)?message\b"
        ),
        (
            r"\b(?:dile|decile)\s+a\s+(?P<recipient>[^,;.!?]{1,80}?)\s+"
            r"(?:(?:en|por)\s+(?:whatsapp|wsp|discord)\s+)?que\b"
        ),
        (
            r"\btell\s+(?P<recipient>[^,;.!?]{1,80}?)\s+"
            r"(?:on\s+(?:whatsapp|discord)\s+)?that\b"
        ),
        (
            r"\bmessage\s+(?P<recipient>[^,;.!?]{1,80}?)\s+"
            r"(?:on\s+)?(?:whatsapp|discord)\s+(?:that|saying)\b"
        ),
        (
            r"\b(?:env[ií]a|manda|send)\s+(?:en|por|on|via)\s+"
            r"(?:whatsapp|wsp|discord)\s+(?:a\s+|to\s+)?"
            r"(?P<recipient>[^,;.!?]{1,80}?)\s+(?:que|that)\b"
        ),
        (
            r"\b(?:env[ií]a|manda)\s+(?:por\s+)?"
            r"(?:whatsapp|wsp|discord)\s+a\s+"
            r"(?P<recipient>[^,;.!?]{1,80}?)\s+"
            r"(?:el\s+)?mensaje\b"
        ),
        (
            r"\b(?:env[ií]a|manda|send)\s+(?:a\s+)?"
            r"(?P<recipient>[^,;.!?]{1,80}?)\s+"
            r"(?:(?:por|en|on)\s+)?(?:the\s+|el\s+)?"
            r"(?:whatsapp|wsp|discord)\s+"
            r"(?:(?:el|the)\s+)?(?:mensaje|message)\b"
        ),
    )
    recipients: list[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, evidence, re.IGNORECASE):
            recipient = match.group("recipient").strip(" \t\r\n,;:.!?\"'“”‘’«»")
            recipient_key = effect_intent._fold(recipient).strip()
            if (
                not recipient_key
                or re.search(r"\b(?:y|and)\b|[&,/]", recipient_key)
                or recipient_key
                in {
                    "ellos",
                    "ellas",
                    "les",
                    "them",
                    "recipient",
                    "destinatario",
                    "contact",
                    "contacto",
                }
            ):
                continue
            recipients.append(recipient)
    recipient_keys = {effect_intent._fold(value).strip() for value in recipients}
    if len(recipient_keys) != 1:
        return None
    return {
        "channel": next(iter(channels)),
        "recipient": recipients[0],
    }


def _explicit_local_reminder_title(evidence: str) -> str | None:
    """Preserve the original spelling of one explicitly named reminder."""

    nominal = re.match(
        r"^[^\w]*(?:reminders\s+(?:for|about)|"
        r"recordatorios\s+(?:de|para|sobre))\s+"
        r"(?P<title>.+?)[\s.!?]*$",
        evidence,
        re.IGNORECASE,
    )
    if (
        nominal is not None
        and effect_intent._nominal_reminder_lookup_title(evidence) is not None
    ):
        title = nominal.group("title").strip(" \t\r\n.,;:!?\"'“”‘’«»")
        return title or None
    repeated_lookup = re.match(
        r"^[^\w]*(?:can\s+i\s+|puedo\s+)?"
        r"(?:see|show|view|find|ver|ve|muestra|muestrame|ensena)\s+"
        r"(?:(?:me|i)\s+)?(?:(?:the|el|la)\s+)?"
        r"(?:reminder|recordatorio)\s+"
        r"(?:for|about|de|para|sobre)\s+"
        r"(?P<title>.+?)\s+(?:again|otra vez|de nuevo|nuevamente)[\s.!?]*$",
        evidence,
        re.IGNORECASE,
    )
    if repeated_lookup is not None:
        title = repeated_lookup.group("title").strip()
        return title or None
    if effect_intent._exact_local_reminder_title(evidence) is None:
        return None
    patterns = (
        (
            r"^[¿?¡!\s]*(?:(?:please|por favor)\s+)?"
            r"(?:delete|remove|cancel|erase|elimina|eliminar|borra|borrar|"
            r"quita|quitar|cancela|cancelar)\s+"
            r"(?:(?:the|a|an|el|la|un|una)\s+)?"
            r"(?:reminder|recordatorio)\s+"
            r"(?:(?:to|for|about|de|para|sobre)\s+)?"
            r"(?P<title>.+?)[\s.!?]*$"
        ),
        (
            r"^[¿?¡!\s]*(?:(?:the|el|la)\s+)?"
            r"(?:reminder|recordatorio)\s+"
            r"(?:(?:to|for|about|de|para|sobre)\s+)?"
            r"(?P<title>.+?)\s+"
            r"(?:needs?\s+to\s+be|has\s+to\s+be|"
            r"necesita\s+(?:ser\s+)?|se\s+(?:tiene|debe)\s+que\s+)"
            r"\s*"
            r"(?:deleted|removed|cancelled|canceled|eliminad[oa]|borrad[oa]|"
            r"cancelad[oa]|eliminar|borrar|cancelar)[\s.!?]*$"
        ),
        (
            r"^[¿?¡!\s]*(?:find|busca|buscar|encuentra|encontrar)\s+"
            r"(?:(?:the|el|la)\s+)?(?:reminder|recordatorio)\s+"
            r"(?:(?:to|for|about|de|para|sobre)\s+)?"
            r"(?P<title>.+?)\s+(?:and|y)\s+"
            r"(?:delete|remove|cancel|erase|elim[ií]nalo|borrarlo|quitarlo|"
            r"cancelarlo|remove\s+it|delete\s+it|cancel\s+it)[\s.!?]*$"
        ),
        (
            r"^[^\w]*(?:no necesito|i (?:do not|don't) need)\s+"
            r"(?P<title>.+?)[,;]\s*"
            r"(?:cancela|elimina|borra|cancel|delete|remove)\s+"
            r"(?:(?:este|el|this|the)\s+)?(?:recordatorio|reminder)[\s.!?]*$"
        ),
        (
            r"^[^\w]*(?P<title>.+?)\s+"
            r"(?:se\s+(?:cancel[oó]|cancelaron)|(?:was|were)\s+cancelled)\s+"
            r"(?:as[ií] que|por lo que|so)\s+"
            r"(?:(?:este|el|this|the)\s+)?(?:recordatorio|reminder)\s+"
            r"(?:se\s+(?:tiene|debe)\s+que\s+|needs?\s+to\s+be\s+)?"
            r"(?:eliminar|borrar|cancelar|deleted|removed|cancelled)[\s.!?]*$"
        ),
    )
    for pattern in patterns:
        match = re.match(pattern, evidence.strip(), re.IGNORECASE)
        if match is None:
            continue
        title = re.sub(
            r"(?:\s+please|\s+por favor)$",
            "",
            match.group("title").strip(" \t\r\n.,;:!?\"'“”‘’«»"),
            flags=re.IGNORECASE,
        ).strip()
        if title:
            return title
    return None


def _explicit_live_media_query_arguments(evidence: str) -> dict[str, object] | None:
    """Ground the bounded Spanish ``pon <music> en vivo`` request."""

    desired_music = effect_intent._desired_music_query(evidence)
    if desired_music is not None:
        return {"provider": "spotify", "query": desired_music}
    spoken_number_title = effect_intent._bare_spoken_number_media_query(evidence)
    if spoken_number_title is not None:
        return {"provider": "spotify", "query": spoken_number_title}

    match = re.match(
        r"^[^\w]*(?:(?:por favor|please)\s*[,;:]?\s*)?"
        r"(?:pon|ponme|pone|poneme)\s+(?P<query>.+?\s+en\s+vivo)"
        r"(?:\s+(?:por favor|please))?[\s.!?]*$",
        evidence,
        re.IGNORECASE,
    )
    if match is None:
        return None
    query = match.group("query").strip()
    if (
        not query
        or len(query.encode("utf-8")) > 1_024
        or not effect_intent._media_play_domain(effect_intent._fold(evidence))
    ):
        return None
    return {"provider": "spotify", "query": query}


def _explicit_location_search_arguments(evidence: str) -> dict[str, object] | None:
    """Preserve one standalone recommendation query without rewriting it."""

    folded = effect_intent._fold(evidence)
    if not effect_intent._location_recommendation_request(folded):
        return None
    query = evidence.strip(" \t\r\n¿?¡!.,;:\"'“”‘’«»")
    if not query or len(query.encode("utf-8")) > 2_000:
        return None
    return {"query": query}


_TEMPORAL_NUMBER_WORDS = effect_intent._TEMPORAL_NUMBER_WORDS
_TEMPORAL_NUMBER_PATTERN = effect_intent._TEMPORAL_NUMBER_PATTERN


def _temporal_number(token: str) -> int | None:
    folded = effect_intent._fold(token)
    if folded.isdigit():
        return int(folded)
    return _TEMPORAL_NUMBER_WORDS.get(folded)


def _explicit_browser_navigation_arguments(
    operation: str,
    evidence: str,
) -> dict[str, object] | None:
    """Canonicalize literal destinations and searches under public policy."""

    destination = effect_intent._symbolic_web_destination(evidence)
    if destination is not None and re.fullmatch(
        effect_intent._NAMED_PUBLIC_SITE, effect_intent._fold(destination)
    ) is None:
        # Its identity must come from the verified search, never a site-name map.
        # The closed public names below (youtube, gmail, github, chatgpt) are the
        # one exception the effect reader already relies on (WEB1257/1259).
        return None
    browser_music = effect_intent._named_browser_music_request(evidence)
    if browser_music is not None and browser_music[1] is not None:
        # MUSIC1827: YouTube's own results page with the person's literal
        # music words, confirmed as a complete URL in the named browser.
        if operation != "browser.navigate.named":
            return None
        browser, query = browser_music
        return {"browser": browser, "url": "https://www.youtube.com/results?" + urlencode({"search_query": query})}
    named_search = effect_intent._named_browser_search(evidence)
    if named_search is not None:
        if operation != "browser.navigate.named":
            return None
        browser, query = named_search
        # Bing is the product's public-search policy, not a claim about the
        # person's browser preferences. Confirm this complete URL and browser.
        return {"browser": browser, "url": "https://www.bing.com/search?" + urlencode({"q": query})}

    youtube_query = effect_intent._youtube_search_query(evidence)
    if youtube_query is not None:
        # WEB1481 «buscá videos de gatos en youtube»: YouTube's own results
        # page with the person's literal query, confirmed as a complete URL.
        if operation != "browser.navigate":
            return None
        return {"url": "https://www.youtube.com/results?" + urlencode({"search_query": youtube_query})}
    installed_query = effect_intent._installed_browser_search_query(evidence)
    if installed_query is not None:
        # WEB1455 «abre un navegador que tengas instalado y busca …»: the
        # product's public search page (Bing) with the person's literal query,
        # confirmed as a complete URL like the named-browser search.
        if operation != "browser.navigate":
            return None
        return {"url": "https://www.bing.com/search?" + urlencode({"q": installed_query})}
    google_query = effect_intent._explicit_google_search_query(evidence)
    if google_query is not None:
        # Named-browser clauses need their own authenticated browser evidence;
        # abstain here rather than silently opening the generic CDP session.
        if (
            operation != "browser.navigate"
            or effect_intent._named_browser(effect_intent._fold(evidence)) is not None
        ):
            return None
        return {"url": "https://www.google.com/search?" + urlencode({"q": google_query})}

    full_urls = [
        match.group(0).rstrip(".,;:!?)]}»”’")
        for match in re.finditer(r"https?://[^\s]+", evidence, re.IGNORECASE)
    ]
    bare_hosts = [
        match.group(0).rstrip(".,;:!?)]}»”’")
        for match in re.finditer(
            r"(?<![@\w])(?:www\.)?[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?"
            r"(?:\.[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?)+"
            r"(?:/[^\s]*)?",
            evidence,
            re.IGNORECASE,
        )
    ]
    destinations = list(dict.fromkeys(full_urls))
    destinations.extend(
        f"https://{host}"
        for host in bare_hosts
        if not any(host.casefold() in value.casefold() for value in full_urls)
    )
    folded = effect_intent._fold(evidence)
    if not destinations and re.search(r"\byoutube\b", folded):
        destinations.append("https://www.youtube.com/")
    if not destinations:
        named_public_sites = (
            (r"\bgmail\b", "https://mail.google.com/"),
            (r"\bgithub\b", "https://github.com/"),
            (r"\bchatgpt\b", "https://chatgpt.com/"),
            (r"\bwashington\s+post\b", "https://www.washingtonpost.com/"),
            (r"\bnew\s+york\s+times\b", "https://www.nytimes.com/"),
            (r"\bbbc\b", "https://www.bbc.com/"),
            (r"\bcnn\b", "https://www.cnn.com/"),
        )
        destinations.extend(
            url for pattern, url in named_public_sites if re.search(pattern, folded)
        )
    if len(destinations) != 1:
        return None
    arguments: dict[str, object] = {"url": destinations[0]}
    if operation == "browser.navigate.named":
        browser = effect_intent._named_browser(folded)
        if browser not in effect_intent.NAMED_CDP_BROWSERS:
            return None
        arguments["browser"] = browser
    return arguments


def _explicit_wifi_profile_arguments(evidence: str) -> dict[str, object] | None:
    """Preserve one explicitly named saved Wi-Fi profile."""

    patterns = (
        (
            r"^[ż?Ą!\s]*(?:cambia|cambiar|change|switch)\s+"
            r"(?:(?:el|the)\s+)?wi[\s-]?fi\s+(?:a|to)\s+"
            r"(?P<profile>.+?)[\s?!.]*$"
        ),
        (
            r"^[ż?Ą!\s]*(?:conecta|conectar|conectame|con[eé]ctate|connect)\s+"
            r"(?:(?:al|a la|to|to the)\s+)?"
            r"(?:(?:red|network)\s+)?wi[\s-]?fi"
            r"(?:\s+(?:network|red))?\s+"
            r"(?:de|llamad[ao]|named|called)\s+"
            r"(?P<profile>.+?)[\s?!.]*$"
        ),
    )
    matches = [
        match
        for pattern in patterns
        if (match := re.match(pattern, evidence, re.IGNORECASE)) is not None
    ]
    if len(matches) != 1:
        return None
    profile = matches[0].group("profile").strip(" \t\r\n,;:.!?\"'“”‘’«»")
    folded = effect_intent._fold(profile)
    if (
        not folded
        or folded in {"it", "that", "eso", "esa", "esta", "wifi"}
        or re.search(r"\b(?:y|and|or|o)\b|[&,/\\]", folded)
        or len(profile.encode("utf-8")) > 256
    ):
        return None
    return {"profileName": profile}


def _explicit_notification_schedule_arguments(
    evidence: str,
) -> dict[str, object] | None:
    """Extract one audible alarm/timer with a single bounded time literal."""

    folded = effect_intent._fold(evidence)
    wake_request = effect_intent._wake_alarm_request(folded)
    count_request = effect_intent._count_down_request(folded)
    if not wake_request and not count_request and not re.search(
        r"\b(?:alarm|alarma|timer|temporizador)\b", folded
    ):
        return None
    relative_pattern = (
        rf"\b(?P<duration>{effect_intent._RELATIVE_DURATION_PATTERN})\b"
    )
    clock_pattern = (
        rf"\b(?P<clock>(?:(?:tomorrow|manana|maniana)\s+)?"
        rf"(?:(?:for|at|a|para)\s+(?:las?\s+)?)?{_TEMPORAL_NUMBER_PATTERN}"
        r"(?::[0-5][0-9])?\s*(?:a\.?\s*m\.?|p\.?\s*m\.?|"
        r"de la manana|de la maniana|de la tarde|de la noche|"
        r"in the morning|in the afternoon|in the evening)"
        r"(?:\s+(?:tomorrow|manana|maniana))?)\b"
    )
    military_clock_pattern = (
        r"\b(?P<clock24>(?:(?:tomorrow|manana|maniana)\s+)?"
        r"(?:at|a|para)\s+(?:las?\s+)?"
        r"(?:[01]?[0-9]|2[0-3]):[0-5][0-9]"
        r"(?:\s+(?:tomorrow|manana|maniana))?)\b"
    )
    # Time literals are read on the folded text: «9 de la mañana» carries an
    # ñ that the accent-free patterns never matched on the raw evidence
    # (TIME1193 probe). The title below still keeps the person's own words.
    relative = list(re.finditer(relative_pattern, folded, re.IGNORECASE))
    clocks = list(re.finditer(clock_pattern, folded, re.IGNORECASE))
    # «a las 6:30 de la tarde» is one clock with its period, not also a
    # 24-hour clock: the period reading owns the literal when both match.
    military_clocks = (
        [] if clocks else list(re.finditer(military_clock_pattern, folded, re.IGNORECASE))
    )
    if len(relative) + len(clocks) + len(military_clocks) != 1:
        return None
    due_literal = (
        relative[0].group("duration")
        if relative
        else clocks[0].group("clock")
        if clocks
        else military_clocks[0].group("clock24")
    ).strip()
    noun = re.search(
        r"\b(?:alarm|alarma|timer|temporizador)\b", evidence, re.IGNORECASE
    )
    if noun is None and not wake_request and not count_request:
        return None
    title_start = noun.start() if noun is not None else 0
    if noun is None:
        return {
            "dueUtc": due_literal,
            "kind": "alarm",
            "title": evidence[title_start:].strip(),
        }
    title = evidence[noun.start() :].strip(" \t\r\n.,;:!?\"'“”‘’«»")
    if not title:
        return None
    return {
        "dueUtc": due_literal,
        "kind": "alarm",
        "title": title,
    }


def _explicit_relative_reminder_arguments(
    evidence: str,
) -> dict[str, object] | None:
    """Preserve one closed relative reminder's literal time and title."""

    clock = (
        rf"(?:(?:a\s+las?|para\s+las?|at)\s+{_TEMPORAL_NUMBER_PATTERN}(?::[0-5][0-9])?"
        r"(?:\s*(?:a\.?\s*m\.?|p\.?\s*m\.?|de\s+la\s+ma[nñ]ana|de\s+la\s+tarde|"
        r"de\s+la\s+noche|in\s+the\s+morning|in\s+the\s+afternoon|in\s+the\s+evening))?)"
    )
    duration = (
        rf"(?:(?:(?:en|in|dentro\s+de|within)\s+){effect_intent._RELATIVE_DURATION_PATTERN}|{clock})"
    )
    patterns = (
        rf"^[¿?¡!\s]*(?:avisame|recordame|recuerdame|remind\s+me)\s+"
        rf"(?P<due>{duration})\s+(?:(?:que|to|de)\s+)?(?P<title>.+?)[.!?]*$",
        rf"^[¿?¡!\s]*(?:avisame|recordame|recuerdame|remind\s+me)\s+"
        rf"(?:(?:que|to|de)\s+)?(?P<title>.+?)\s+(?P<due>{duration})[.!?]*$",
        rf"^[¿?¡!\s]*(?P<due>{duration}),?\s+"
        rf"(?:avisame|recordame|recuerdame|remind\s+me)\s+"
        rf"(?:(?:que|to|de)\s+)?(?P<title>.+?)[.!?]*$",
        rf"^[¿?¡!\s]*(?:ponme|set)\s+(?:(?:un|a)\s+)?"
        rf"(?:recordatorio|reminder)\s+(?P<due>{duration})\s+"
        rf"(?:para|to)\s+(?P<title>.+?)[.!?]*$",
        rf"^[¿?¡!\s]*(?:recordatorio|reminder)\s+(?:de|to)\s+"
        rf"(?P<title>.+?)\s+(?P<due>{duration})[.!?]*$",
        rf"^[¿?¡!\s]*(?:set\s+)?(?:a\s+)?reminder\s+to\s+"
        rf"(?P<title>.+?)\s+(?P<due>{duration})[.!?]*$",
    )
    matches = [
        match
        for pattern in patterns
        if (match := re.fullmatch(pattern, evidence, re.IGNORECASE)) is not None
    ]
    if len(matches) != 1:
        return None
    due = matches[0].group("due").strip()
    title = matches[0].group("title").strip().rstrip(".!?").rstrip()
    if not due or not title:
        return None
    return {"dueUtc": due, "title": title}


_CALENDAR_MONTH_NUMBERS = {
    "january": 1,
    "enero": 1,
    "february": 2,
    "febrero": 2,
    "march": 3,
    "marzo": 3,
    "april": 4,
    "abril": 4,
    "may": 5,
    "mayo": 5,
    "june": 6,
    "junio": 6,
    "july": 7,
    "julio": 7,
    "august": 8,
    "agosto": 8,
    "september": 9,
    "septiembre": 9,
    "october": 10,
    "octubre": 10,
    "november": 11,
    "noviembre": 11,
    "december": 12,
    "diciembre": 12,
}


def _explicit_calendar_range_arguments(
    evidence: str,
    *,
    now_utc: datetime | None = None,
) -> dict[str, object] | None:
    """Materialize one closed relative calendar window in local civil time."""

    folded = effect_intent._fold(evidence)
    patterns = (
        (
            "after_work_today",
            r"\b(?:after work today|today after work|"
            r"despues del trabajo hoy|hoy despues del trabajo)\b",
        ),
        ("tonight", r"\b(?:esta noche|tonight)\b"),
        (
            "new_year_day",
            r"\b(?:ano nuevo|dia de ano nuevo|new year's day|new year day)\b",
        ),
        ("today", r"\b(?:hoy|today)\b"),
        ("tomorrow", r"\b(?:manana|maniana|tomorrow)\b"),
        ("next_weekend", r"\b(?:el\s+)?proximo fin de semana\b|\bnext weekend\b"),
        ("this_weekend", r"\beste fin de semana\b|\bthis weekend\b"),
        ("next_week", r"\b(?:la\s+)?proxima semana\b|\bnext week\b"),
        ("this_week", r"\besta semana\b|\bthis week\b"),
        ("next_month", r"\b(?:el\s+)?proximo mes\b|\bnext month\b"),
        ("this_month", r"\beste mes\b|\bthis month\b"),
    )
    windows = {name for name, pattern in patterns if re.search(pattern, folded)}
    absolute_range = effect_intent._absolute_calendar_range_parts(folded)
    if "after_work_today" in windows:
        windows.discard("today")
    if absolute_range is None and len(windows) != 1:
        return None

    if now_utc is None:
        local_now = datetime.now().astimezone()
    else:
        if now_utc.tzinfo is None:
            raise ValueError("now_utc must carry timezone authority")
        local_now = now_utc.astimezone(now_utc.tzinfo)
    today = local_now.date()
    window = next(iter(windows)) if windows else ""
    start_hour = 0
    if absolute_range is not None:
        start_month_name, start_day_name, end_month_name, end_day_name = absolute_range
        start_month = _CALENDAR_MONTH_NUMBERS.get(start_month_name)
        end_month = _CALENDAR_MONTH_NUMBERS.get(end_month_name)

        def calendar_day(value: str) -> int | None:
            if value.isdigit():
                parsed = int(value)
            else:
                parsed = effect_intent._PERCENTAGE_WORD_VALUES.get(value)
            return parsed if parsed is not None and 1 <= parsed <= 31 else None

        start_day = calendar_day(start_day_name)
        end_day = calendar_day(end_day_name)
        if (
            start_month is None
            or end_month is None
            or start_day is None
            or end_day is None
        ):
            return None
        try:
            start_date = date(today.year, start_month, start_day)
            end_year = today.year + int((end_month, end_day) < (start_month, start_day))
            # End is exclusive at the provider boundary; include the spoken
            # final civil day by advancing one date before UTC conversion.
            end_date = date(end_year, end_month, end_day) + timedelta(days=1)
        except ValueError:
            return None
    elif window == "after_work_today":
        start_date, end_date = today, today + timedelta(days=1)
        start_hour = 17
    elif window == "tonight":
        start_date, end_date = today, today + timedelta(days=1)
        start_hour = 18
    elif window == "today":
        start_date, end_date = today, today + timedelta(days=1)
    elif window == "tomorrow":
        start_date = today + timedelta(days=1)
        end_date = start_date + timedelta(days=1)
    elif window in {"this_week", "next_week"}:
        monday = today - timedelta(days=today.weekday())
        if window == "next_week":
            monday += timedelta(days=7)
        start_date, end_date = monday, monday + timedelta(days=7)
    elif window in {"this_weekend", "next_weekend"}:
        saturday = (
            today - timedelta(days=1)
            if today.weekday() == 6
            else today + timedelta(days=(5 - today.weekday()) % 7)
        )
        if window == "next_weekend":
            saturday += timedelta(days=7)
        start_date, end_date = saturday, saturday + timedelta(days=2)
    elif window == "new_year_day":
        start_date = date(today.year, 1, 1)
        if start_date < today:
            start_date = date(today.year + 1, 1, 1)
        end_date = start_date + timedelta(days=1)
    else:
        month_offset = 1 if window == "next_month" else 0
        year = today.year + (today.month + month_offset - 1) // 12
        month = (today.month + month_offset - 1) % 12 + 1
        start_date = today.replace(year=year, month=month, day=1)
        next_year = year + month // 12
        next_month = month % 12 + 1
        end_date = start_date.replace(year=next_year, month=next_month, day=1)

    local_zone = local_now.tzinfo
    if local_zone is None:
        return None

    def local_civil_utc(local_date: date, hour: int = 0) -> datetime | None:
        naive = datetime.combine(local_date, datetime_time(hour=hour))
        fold_zero = naive.replace(tzinfo=local_zone, fold=0).astimezone(timezone.utc)
        fold_one = naive.replace(tzinfo=local_zone, fold=1).astimezone(timezone.utc)
        if (
            fold_zero != fold_one
            or fold_zero.astimezone(local_zone).replace(tzinfo=None) != naive
        ):
            return None
        return fold_zero.replace(microsecond=0)

    start_utc = local_civil_utc(start_date, start_hour)
    end_utc = local_civil_utc(end_date)
    if start_utc is None or end_utc is None or end_utc <= start_utc:
        return None
    return {
        "startUtc": start_utc.isoformat().replace("+00:00", "Z"),
        "endUtc": end_utc.isoformat().replace("+00:00", "Z"),
    }


def _explicit_media_control_arguments(evidence: str) -> dict[str, object] | None:
    """Ground one literal playback command without interpreting a media query."""

    folded = effect_intent._fold(evidence)
    resuming = effect_intent._resume_existing_media(folded)
    transport = effect_intent._media_transport_action(folded)
    action_patterns = {
        "next": (
            r"\b(?:skip|salta|saltar|saltea|saltear)\b",
            r"\b(?:next|siguiente)\s+(?:artist|artista|song|cancion|track|pista|"
            r"podcast|episode|episodio)\b",
            (
                r"^[^\w]*(?:(?:por favor|please)\s*[,;:]?\s*)?"
                r"(?:cambia|cambiar|change|switch)\s+"
                r"(?:(?:el|la|the|current|actual)\s+)?(?:artista|artist)"
                r"(?:\s*[,;:]?\s*(?:por favor|please))?[\s.!?]*$"
            ),
        ),
        "previous": (
            r"\b(?:previous|prior)\s+(?:song|track|podcast|episode)\b",
            r"\b(?:cancion|pista|podcast|episodio)\s+anterior\b",
            r"\b(?:go|ve|vuelve)\s+(?:back|atras)\b",
        ),
        "pause": (
            # In a resume request, "en pausa" describes the loaded state.
            # A separate pause verb or leave-in-pause command still conflicts.
            r"(?<!en )\b(?:pause|pausa|pausar|pausalo|pausala|pausame)\b"
            if resuming else r"\b(?:pause|pausa|pausar|pausalo|pausala|pausame)\b",
            r"\b(?:deja|dejar)\s+en\s+pausa\b",
        ),
        "play": (
            rf"\b{effect_intent._MEDIA_RESUME_VERB}\b",
            r"\b(?:play|reproduce|reproducir)\b[^.;!?]*\b(?:paused|pausad[ao])\b",
        ),
        "stop": (r"\b(?:stop|deten|detener)\b",),
        "toggle": (r"\b(?:toggle|alternar)\b",),
    }
    actions = {
        action
        for action, patterns in action_patterns.items()
        if (transport is None or action not in {"next", "previous", "stop"})
        and any(re.search(pattern, folded, re.IGNORECASE) for pattern in patterns)
    }
    if transport is not None:
        actions.add(transport)
    if len(actions) != 1:
        return None
    arguments: dict[str, object] = {"action": next(iter(actions))}
    if re.search(r"\bspotify\b", folded, re.IGNORECASE):
        # The optional source narrows SMTC selection to the session the person
        # actually named.  Without it, Windows' current session may belong to
        # a browser or another player even immediately after Spotify starts.
        arguments["sourceApp"] = "spotify"
    return arguments


def _todays_news_query(text: str) -> str | None:
    """WEB1451 «qué pasó hoy en el mundo»: a news query with the person's own
    scope words; None when the request is not a what-happened-today question."""

    match = re.match(
        r"^[¿?¡!\s]*(?:qué|que|what)\s+"
        r"(?:pasó|paso|pasa|ha\s+pasado|está\s+pasando|esta\s+pasando|ocurrió|ocurrio|ocurre|sucedió|sucedio|"
        r"happened|is\s+happening|has\s+happened)\s+(?P<scope>(?:hoy|today)\b.*?)\s*[.!?]*$",
        text.strip(),
        re.IGNORECASE,
    )
    if match is None:
        return None
    scope = re.sub(r"\s+", " ", match.group("scope")).strip()
    return ("news " if scope.casefold().startswith("today") else "noticias de ") + scope


def _explicit_arguments_from_evidence(
    operation: str,
    evidence: str,
    application_names: tuple[str, ...] = (),
    game_catalog: GameCatalogIndex = GameCatalogIndex(),
) -> dict[str, object] | None:
    """Extract only unambiguous literals from one preserved effect fragment.

    Repeated effects cannot be grounded safely against the whole objective:
    for example, "mute ... then unmute" contains both Boolean cues.  The
    effect recognizer already supplies a bounded clause-local fragment for
    every preserved operation, so a very small extractor can retain those
    identities without asking the model to choose between sibling effects.
    All returned values still cross the authenticated JSON Schema and normal
    grounding boundary before they enter a plan.
    """

    folded = unicodedata.normalize("NFKD", evidence.casefold())
    folded = "".join(
        character for character in folded if not unicodedata.combining(character)
    )
    folded = " ".join(folded.split())
    numbers = [
        int(found.group(0))
        for found in re.finditer(
            r"(?<![0-9])(?:100|[0-9]{1,2})(?![0-9])",
            folded,
        )
    ]

    def clause_literal(value: str) -> str:
        """Remove unquoted clause punctuation that is not part of a literal."""

        return value.strip().rstrip(".!?").rstrip()

    if operation == "browser.control":
        return (effect_intent.browser_back_arguments(evidence)
                or effect_intent.browser_new_tab_arguments(evidence)
                or effect_intent.browser_close_all_tabs_arguments(evidence))

    if operation == "system.status":
        return _explicit_system_status_scope(evidence)

    if operation == "clipboard.write.text":
        # CLIPBOARD1359: the quoted or colon-introduced fragment is the
        # person's literal, case and accents preserved by the reader.
        literal = effect_intent.literal_clipboard_write_text(evidence)
        return {"text": literal} if literal is not None else None

    if operation == "window.close.all":
        # CLOSEALL1733: no argument; the order names every window.
        return {} if effect_intent.close_all_request(effect_intent._fold(evidence)) else None

    if operation == "window.minimize.all":
        # MINALL1687: no arguments; the order over every window is the whole request.
        return {} if effect_intent.minimize_all_request(effect_intent._fold(evidence)) else None

    if operation == "clipboard.read.text":
        # The read takes no literal; naming the clipboard is the whole request.
        return {} if re.search(r"\b(?:portapapeles|clipboard)\b", folded) else None

    if operation == "system.settings.status":
        # BRIGHT1283: the reader owns the setting enum; «brillo» is the literal.
        return {"setting": "brightness"} if effect_intent.brightness_status_request(evidence) else None

    if operation == "system.settings.adjust":
        adjustment = effect_intent._literal_brightness_adjustment(evidence)
        return {**adjustment, "setting": "brightness"} if adjustment is not None else None

    if operation == "system.settings.set":
        level = effect_intent._literal_brightness_level(evidence)
        return {"setting": "brightness", "value": level} if level is not None else None

    if operation == "window.snap":
        # ARRANGE1781: the side is the person's literal; windowId comes from window.resolve.
        snap = effect_intent.resolve_application_snap(evidence, application_names)
        return {"side": snap[1]} if snap is not None else None

    if operation == "window.resolve":
        application_name = effect_intent.resolve_application_snap_name(
            evidence, application_names,
        ) or effect_intent.resolve_application_close_name(
            evidence, application_names,
        ) or effect_intent.resolve_application_focus_name(
            evidence, application_names,
        ) or effect_intent.resolve_application_minimize_name(
            evidence, application_names,
        ) or effect_intent.conditional_open_pause_app(
            evidence, application_names,
        )
        if application_name is not None:
            return {"applicationName": application_name}
        if effect_intent.other_window_switch_request(evidence):
            # REOPEN1993 H0263: every visible window, so the one behind the
            # foreground can be chosen from the verified reading.
            return {"process": "*", "byTitle": False, "limit": 50}
        inventory = effect_intent.window_inventory_arguments(evidence)
        if inventory is not None:
            return inventory
        title = effect_intent.explicit_window_title(evidence)
        return {"process": title, "byTitle": True} if title is not None else None

    if operation == "window.application.status":
        name = effect_intent.resolve_application_window_status_name(
            evidence, application_names,
        )
        return {"name": name} if name is not None else None

    if operation == "app.open":
        app_id = resolve_application_catalog_app_id(evidence, application_names)
        if app_id is None:
            # REOPEN1993 «abre Steel.»: the single installed near name is the
            # target the reader chose; ground it by its catalog name.
            near = effect_intent.near_single_open_candidate(evidence, application_names, game_catalog)
            if near is not None and near[0] == "app.open":
                app_id = resolve_application_catalog_app_id(near[1], application_names)
        return {"appId": app_id} if app_id is not None else None

    if operation == "input.visible.click":
        label = effect_intent._visible_click_label(folded, allow_navigate=True)
        return {"label": label} if label is not None else None

    if operation == "app.installed":
        name = effect_intent.installed_catalog_application_name(
            evidence, application_names,
        ) or resolve_application_installed_name(evidence, application_names)
        return {"name": name} if name is not None else None

    if operation == "client.channel.locate":
        # DISCORD1839: the client and the place are the person's literal.
        located = effect_intent.client_channel_request(evidence)
        return {"client": located[0], "name": located[1]} if located is not None else None

    if operation == "message.draft":
        # MSG1837: channel, recipient and text are the person's literal.
        draft = effect_intent.message_draft_request(evidence)
        return {"channel": draft[0], "recipient": draft[1], "text": draft[2]} if draft is not None else None

    if operation == "message.send.test":
        # MSG §6: channel, the requested recipient and text are the person's
        # literal; the adapter forces the real destination to the owner's test
        # channel, so the requested recipient is recorded but never targeted.
        draft = effect_intent.message_draft_request(evidence)
        return {"channel": draft[0], "requestedRecipient": draft[1], "text": draft[2]} if draft is not None else None

    if operation == "storage.removable.list":
        if effect_intent._removable_storage_request(evidence):
            return {}

    if operation == "software.python.package.status":
        # PIP1817: the package is the person's literal from the request.
        package = effect_intent._python_package_request(evidence)
        return {"package": package} if package is not None else None

    if operation == "game.entitlement.named":
        # INSTALL1617: the title is the person's literal from the request.
        title = effect_intent.steam_library_title(evidence)
        if title is None:
            return None
        # H0578: the store named after the title picks the library that is read.
        store = effect_intent.game_library_store(evidence)
        return {"title": title, "store": store} if store == "epic" else {"title": title}

    if operation == "game.installed.named":
        # APPS1613 H0275: the title is the clause's own literal; the provider
        # is the one the clause names, otherwise every manifest family.
        title = effect_intent.installed_game_title(evidence)
        if title is None:
            return None
        return {"provider": effect_intent.installed_game_provider(evidence), "title": title}

    if operation == "game.launch":
        app_id = resolve_game_catalog_app_id(evidence, game_catalog)
        if app_id is None:
            # REOPEN1993 «Ve a Mad de Rivals.»: the single installed near title.
            near = effect_intent.near_single_open_candidate(evidence, application_names, game_catalog)
            if near is not None and near[0] == "game.launch":
                app_id = resolve_game_catalog_app_id(near[1], game_catalog)
        return {"appId": app_id} if app_id is not None else None

    if operation in {
        "game.install.cancel",
        "game.install.prepare",
        "game.install.status",
    }:
        app_ids = {
            match.group("app_id")
            for match in re.finditer(
                r"\bapp\s*id\s*[:#-]?\s*(?P<app_id>[1-9][0-9]{0,15})\b",
                evidence,
                re.IGNORECASE,
            )
        }
        return {"appId": next(iter(app_ids))} if len(app_ids) == 1 else None

    if operation == "game.catalog.list":
        if re.search(r"\b(?:biblioteca|library)\b", folded) and not numbers:
            return {}
        return None

    if operation == "document.pdf.read":
        # PDF1689 «resumime informe.pdf»: the file name is the person's
        # literal; the folder is a catalog root, or every known folder when
        # none is named (the provider refuses an ambiguous name).
        pdf_match = effect_intent._pdf_summary_request(evidence)
        if pdf_match is None:
            return None
        pdf_name = pdf_match.group("name").strip().strip("\"'").rstrip(".!?,").strip()
        if (
            not pdf_name
            or re.search(r"[\\/:*?\"<>|]", pdf_name)
            or any(ord(character) < 32 for character in pdf_name)
            or len(pdf_name.encode("utf-8")) > 512
        ):
            return None
        pdf_folder = pdf_match.group("folder")
        return {
            "fileName": pdf_name,
            "folder": effect_intent._KNOWN_FOLDER_ENUM[effect_intent._fold(pdf_folder)]
            if pdf_folder else "all_known",
        }

    if operation == "filesystem.known.trash.named":
        # «borra el archivo hola.txt del escritorio»: the file name is the
        # person's literal; the folder is a catalog root, or every known folder
        # when none is named (the provider refuses an ambiguous name).
        trash_match = effect_intent._file_trash_request(evidence)
        if trash_match is None:
            return None
        file_name = trash_match.group("name").strip().strip("\"'").rstrip(".!?,").strip()
        if (
            not file_name
            or re.search(r"[\\/:*?\"<>|]", file_name)
            or any(ord(character) < 32 for character in file_name)
            or len(file_name.encode("utf-8")) > 512
        ):
            return None
        folder_word = trash_match.group("folder")
        return {
            "fileName": file_name,
            "folder": effect_intent._KNOWN_FOLDER_ENUM[effect_intent._fold(folder_word)]
            if folder_word else "all_known",
        }

    if operation == "filesystem.create.directory":
        # «crea una carpeta llamada CarterTest en el escritorio»: the name is
        # the person's, the folder is a catalog root (owner decision, point 2).
        directory_match = effect_intent._directory_creation_request(evidence)
        if directory_match is None:
            return None
        relative_path = directory_match.group("name").strip()
        if (
            len(relative_path) >= 2
            and relative_path[0] == relative_path[-1]
            and relative_path[0] in {'"', "'"}
        ):
            relative_path = relative_path[1:-1].strip()
        path_segments = re.split(r"[\\/]", relative_path)
        if not (
            relative_path
            and not re.match(r"^(?:[A-Za-z]:|[\\/]{1,2})", relative_path)
            and all(segment not in {"", ".", ".."} for segment in path_segments)
            and not any(ord(character) < 32 for character in relative_path)
            and len(relative_path.encode("utf-8")) <= 1_024
        ):
            return None
        folder_word = directory_match.group("folder_a") or directory_match.group("folder_b")
        arguments: dict[str, object] = {"relativePath": relative_path}
        if folder_word:
            arguments["folder"] = effect_intent._KNOWN_FOLDER_ENUM[
                effect_intent._fold(folder_word)
            ]
        return arguments

    if operation == "filesystem.write.text":
        write_match = effect_intent._file_creation_request(evidence) or re.fullmatch(
            r"[¿?¡!\s]*(?:"
            r"(?:crea|crear|guarda|guardar|escribe|escribir)\s+"
            r"(?:(?:un|el)\s+)?archivo|"
            r"(?:create|save|write)\s+(?:(?:a|the)\s+)?file"
            r")\s+"
            r"(?:(?:llamad[oa]|named|called)\s+)?"
            r"(?P<name>\"[^\"]+\"|'[^']+'|\S+?)\s+"
            r"(?:con(?:\s+(?:el\s+)?(?:contenido|texto))?|que\s+diga|"
            r"with(?:\s+(?:the\s+)?(?:content|text))?|containing|saying)\s+"
            r"(?P<content>.+?)[\s]*",
            evidence,
            re.IGNORECASE,
        )
        if write_match is not None:
            relative_path = write_match.group("name").strip()
            text = clause_literal(write_match.group("content"))
            folder_word = (
                write_match.groupdict().get("folder_a")
                or write_match.groupdict().get("folder_b")
            )
            if (
                len(relative_path) >= 2
                and relative_path[0] == relative_path[-1]
                and relative_path[0] in {'"', "'"}
            ):
                relative_path = relative_path[1:-1].strip()
            if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
                text = text[1:-1]
            path_segments = re.split(r"[\\/]", relative_path)
            safe_path = (
                bool(relative_path)
                and not re.match(r"^(?:[A-Za-z]:|[\\/]{1,2})", relative_path)
                and all(segment not in {"", ".", ".."} for segment in path_segments)
                and not any(ord(character) < 32 for character in relative_path)
                and len(relative_path.encode("utf-8")) <= 1_024
            )
            if safe_path and len(text.encode("utf-8")) <= 1_048_576:
                arguments = {"relativePath": relative_path, "text": text}
                if folder_word:
                    arguments["folder"] = effect_intent._KNOWN_FOLDER_ENUM[
                        effect_intent._fold(folder_word)
                    ]
                return arguments
        return None

    if operation == "wifi.connect.named":
        return _explicit_wifi_profile_arguments(evidence)

    if operation in {"browser.navigate", "browser.navigate.named"}:
        return _explicit_browser_navigation_arguments(operation, evidence)

    if operation == "streaming.navigate":
        navigation = _explicit_browser_navigation_arguments(
            "browser.navigate",
            evidence,
        )
        if navigation is None:
            return None
        resource_uri = navigation.get("url")
        if not isinstance(resource_uri, str):
            return None
        host = (urlsplit(resource_uri).hostname or "").casefold().rstrip(".")
        services = {
            service
            for service, suffixes in (
                ("netflix", ("netflix.com",)),
                ("prime_video", ("primevideo.com", "amazon.com")),
                ("youtube", ("youtube.com", "youtu.be")),
            )
            if any(host == suffix or host.endswith("." + suffix) for suffix in suffixes)
        }
        if len(services) == 1:
            return {
                "resourceUri": resource_uri,
                "service": next(iter(services)),
            }
        return None

    if operation == "streaming.play.named":
        # VIDEO1921: sin entrada aquí el planificador rellenaba service y title a
        # ciegas, y con «start Stranger Things on Netflix» o «… en nerflix» se
        # rendía y preguntaba qué servicio y qué título, con los dos escritos
        # delante. El servicio es siempre netflix aunque se escriba mal —lo más
        # probable es que lo escriba mal el oído de BAXY— y el título es lo que
        # hay entre el verbo y «en/on Netflix», tal cual: la búsqueda de Netflix
        # es difusa y el recibo dirá el título que de verdad se puso.
        named = re.search(
            r"^(?:(?:quiero|quisiera|i\s+want\s+to|i\s+wanna|i'd\s+like\s+to)\s+)?"
            r"(?:reproduc[eií]|play|pon[eé]?(?:me)?|ponme|put(?:\s+on)?|busc[aá]|find|"
            r"inici[aá]|start|encuentra|encuentras|localiza|locate|ver|watch)\s+"
            r"(?:(?:la|the)\s+(?:serie|series|pel[ií]cula|peli|movie|film)\s+)?"
            r"(?P<title>.+?)\s+"
            r"(?:en|in|on|desde|from|through|usando|using)\s+"
            r"(?:netflix|nerflix|netlix|netfix|netflis|neflix|"
            r"disney\s*\+|disney\s*plus|disneyplus|disney|dysney|disne|dinsey|dizney)\b",
            clause_literal(evidence),
            re.IGNORECASE,
        )
        if named is None:
            return None
        title = named.group("title").strip().strip("\"'«»“”").strip()
        if not title or len(title.encode("utf-8")) > 512:
            return None
        # VIDEO1947: the service is the one spelled after the title.
        streaming_arguments: dict[str, object] = {
            "service": effect_intent.streaming_service_named(evidence),
            "title": title,
        }
        return streaming_arguments

    if operation == "media.play.query":
        return _explicit_live_media_query_arguments(evidence)

    if operation == "media.play.youtube":
        # MUSIC1553: the person's own words name what to play; the provider
        # searches YouTube with them and the receipt carries the title played.
        youtube_query = effect_intent.youtube_play_query(evidence)
        if youtube_query is None and not re.search(r"\b(?:youtube|spotify)\b", folded):
            # MUSIC1559 «pon música de daft punk», «poneme algo de música tranqui»:
            # the named music, in the person's words, is the YouTube query.
            named = _explicit_live_media_query_arguments(evidence)
            if named is not None and isinstance(named.get("query"), str):
                youtube_query = re.sub(
                    r"^(?:algo\s+de|something\s+like|some)\s+", "", named["query"].strip(), flags=re.IGNORECASE,
                ).strip() or None
        return {"query": youtube_query} if youtube_query is not None else None

    if operation == "calendar.event.list":
        return _explicit_calendar_range_arguments(evidence)

    if operation == "media.control":
        return _explicit_media_control_arguments(evidence)

    if operation == "web.search":
        # H0463 «… usando la API publica»: the declined means is not part of
        # the query (the query «el App ID de Doom Eternal en Steam usando la API
        # publica» still found SteamDB, but the words are the person's directive,
        # not what they are looking for).
        evidence = effect_intent._strip_trailing_means_directive(evidence)
        research_question = effect_intent._research_question_query(evidence)
        if research_question is not None:
            # WEB1831: the engine answers the question in the person's words
            # (the lead-in supplies the subject when the question names none).
            return {"query": research_question}
        destination = effect_intent._symbolic_web_destination(evidence)
        if destination is not None:
            return {"query": destination}
        named_site = effect_intent._named_browser_site_request(evidence)
        if named_site is not None:
            # H0081 «abre opera gx y entra a pivigames»: the site name alone is
            # the query; its URL is the first verified result.
            return {"query": named_site[1]}
        query = ""
        search_evidence = re.split(
            r"\s+(?:(?:y\s+)?(?:despu\S+s|luego)|and\s+then|then|afterwards)"
            r"\s+(?=(?:navega|navegar|abre|abrir|ve|llevame|ll\S+vame|"
            r"reproduce|reproducir|navigate|open|go|play|stream|launch)\b)",
            evidence,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        location = _explicit_location_search_arguments(search_evidence)
        if location is not None:
            return location
        entity = effect_intent._entity_lookup_query(search_evidence)
        if entity is not None:
            # KNOWLEDGE1473 «¿Quién es Daredevil?»: the engine answers the bare
            # name; the question words around it return unrelated pages.
            return {"query": entity}
        curiosity_subject = effect_intent.curiosity_topic(search_evidence)
        if curiosity_subject is not None:
            # KNOWLEDGE1505 «decime una curiosidad»: the engine serves no pages
            # for the word «curiosidad»; it answers a well-known subject with
            # its public page, and the curiosity is what that page states.
            return {"query": curiosity_subject}
        topic = effect_intent._topic_research_query(search_evidence)
        if topic is not None:
            # WEB1451 «Investiga Spider-Man»: the engine answers the topic, not
            # the research verb («investiga» never appears in a result page).
            return {"query": topic}
        news_query = _todays_news_query(search_evidence)
        if news_query is not None:
            # WEB1451 «qué pasó hoy en el mundo»: the engine answers a news
            # query with the person's scope words («noticias de hoy en el
            # mundo»); the question itself returns unrelated pages.
            return {"query": news_query}
        weather_query = effect_intent._weather_lookup_query(search_evidence)
        if weather_query is not None:
            # WEB1445 «qué clima hace hoy», «mostrame el clima», «va a llover
            # mañana»: the engine answers a weather query with the local forecast,
            # but the request verbs («mostrame», «hace») never appear in a result
            # and the relevance filter rejected every item. The query keeps only
            # the weather words the person said, in their order.
            return {"query": weather_query}
        search = list(
            re.finditer(
                (
                    rf"\b(?:{effect_intent._SEARCH}|buscá)(?:\s+for)?\b"
                    r"(?:\s+en\s+(?:google|internet|la\s+web|the\s+web))?"
                    r"\s*[:,-]?\s*(?P<query>.+?)"
                    r"(?=\s+(?:(?:y\s+)?(?:despu[eé]s|luego)|and\s+then|then|"
                    r"afterwards)\s+(?:navega|navegar|abre|abrir|ve|llevame|"
                    r"ll[eé]vame|reproduce|reproducir|navigate|open|go|play|"
                    r"stream|launch)\b|\s*$)"
                ),
                search_evidence,
                re.IGNORECASE,
            )
        )
        if search:
            query = clause_literal(search[-1].group("query"))
            query = re.sub(
                r"^(?:exactamente|exactly)\s+",
                "",
                query,
                count=1,
                flags=re.IGNORECASE,
            )
            query = re.sub(
                r"\s+(?:en\s+la\s+web|on\s+the\s+web)$",
                "",
                query,
                count=1,
                flags=re.IGNORECASE,
            )
        else:
            opened_page = re.match(
                (
                    r"^[Â¿?Â¡!\s]*(?:abre|abrir|open)\s+"
                    r"(?:(?:la|el|the|a)\s+)?(?P<query>.+?)\s*[.!?]*$"
                ),
                evidence,
                re.IGNORECASE,
            )
            query = (
                clause_literal(opened_page.group("query"))
                if opened_page is not None
                else evidence.strip(" \t\r\n")
            )
        return {"query": query} if query and len(query.encode("utf-8")) <= 512 else None

    if operation == "input.text.type":
        quoted = re.search(
            r"[\"“](?P<text>[^\"”]{1,4096})[\"”]",
            evidence,
        )
        if quoted is not None:
            return {"text": quoted.group("text")}
        deictic = re.search(
            # REOPEN1993 H0097 «ponle hola»: the literal after the deictic head.
            r"(?i)^[\s¡!¿?]*(?:pon[eé]?le|ponele|pon[eé]?melo|put\s+on\s+it|write\s+on\s+it)\s+"
            r"(?!(?:a|al|por|para|que|en)\b)(?P<text>.+?)"
            r"(?:\s+(?:ahora|ya|now|please|por\s+favor|porfa))*[\s.!?]*$",
            evidence.strip(),
        )
        if deictic is not None:
            return {"text": deictic.group("text").strip()}
        typed = re.search(
            (
                r"\b(?:escribe|escrib[ií]|escribir|teclea|teclear|write|type)\b"
                r"\s+(?P<text>.+?)"
                r"(?=\s+en\s+(?:la|el|the)\s+(?:b[uú]squeda|search|campo|field|"
                r"cuadro|box)\b|\s*[.!?]*$)"
            ),
            evidence,
            re.IGNORECASE,
        )
        if typed is not None:
            text = clause_literal(typed.group("text"))
            return {"text": text} if text else None

    if operation == "message.recipient.resolve":
        return _explicit_message_recipient_arguments(evidence)

    if operation == "reminder.resolve.exact":
        title = _explicit_local_reminder_title(evidence)
        return {"title": title} if title is not None else None

    if operation == "note.create":
        # This closed form carries both required literals in one atomic effect
        # fragment. Preserve their original spelling and punctuation, then let
        # the authenticated schema and normal grounding boundary validate them.
        note_pattern = (
            r"\b(?:nota|note)\s+"
            r"(?:(?:titulad[ao]|llamad[ao]|titled|named|called)\s+)?"
            r"(?P<title>.+?)\s+"
            r"(?:con\s+(?:el\s+)?(?:contenido|texto)|que\s+diga|"
            r"with\s+(?:the\s+)?content|saying|containing)\s+"
            r"(?P<content>.+?)\s*$"
        )
        matches = list(re.finditer(note_pattern, evidence, re.IGNORECASE))
        if len(matches) == 1:
            title = clause_literal(matches[0].group("title"))
            content = clause_literal(matches[0].group("content"))
            if title and content:
                return {"title": title, "content": content}
        note_request = effect_intent._strip_request_envelope(evidence)
        desired = effect_intent._explicit_desire_request(note_request)
        if desired is not None:
            note_request = desired.group("body")
        shorthand = re.match(
            r"^[¿?¡!\s]*(?:"
            r"(?:anot[aá]|anotar|anotame|note down|write down|"
            r"deja(?:r)?\s+anotad[oa])\s*"
            r"(?:(?:que|that)\b|:|\s(?=[^\W\d_]+(?:ar|er|ir)\b))"
            r"|(?:cre[aá]|crear|create|make|haz|hacer|guard[aá](?:me)?|guardar|"
            r"save|tom[aá](?:me)?|take)\s+"
            r"(?:(?:una?|a)\s+)?(?:nota|note)\s*"
            r"(?:(?:que\s+diga|that\s+says?|saying)\s*:?|:)"
            r"|(?:nota\s+nueva|nueva\s+nota|new\s+note)\s*:"
            r")\s*(?P<content>.+?)[\s.!?]*$",
            note_request,
            re.IGNORECASE,
        )
        if shorthand is not None:
            content = shorthand.group("content").strip()
            title = re.sub(
                r"^(?:tengo que|termine de|terminé de|i need to|i have to)\s+",
                "",
                content,
                count=1,
                flags=re.IGNORECASE,
            ).strip()
            if content and title and len(title.encode("utf-8")) <= 512:
                return {"title": title, "content": content}
        memo_content = effect_intent._literal_memo_payload(evidence)
        if memo_content is not None:
            content = clause_literal(memo_content)
            if content and len(content.encode("utf-8")) <= 512:
                return {"title": content, "content": content}

    if operation == "note.search" and effect_intent._historical_note_search_request(
        evidence
    ):
        query_match = re.search(
            r"\b(?:notas?|apuntes?)\s+(?P<query>.+?)"
            r"(?:\s+(?:del\s+)?pasado)?[\s.!?]*$",
            evidence,
            re.IGNORECASE,
        )
        if query_match is not None:
            query = clause_literal(query_match.group("query"))
            if query and len(query.encode("utf-8")) <= 512:
                return {"query": query}

    if operation == "note.search":
        stored_query = effect_intent._stored_note_search_query(evidence)
        if stored_query is not None:
            query = clause_literal(stored_query)
            if query and len(query.encode("utf-8")) <= 512:
                return {"query": query}

    if operation == "task.create":
        task_pattern = (
            r"\b(?:tarea|task)(?:\s*:\s*|"
            r"\s+(?:llamad[oa]|titulad[oa]|named|called)\s+)"
            r"(?P<title>.+?)"
            r"(?:\s+(?:y|and)\s+(?:una?|an?)\s*)?[.!?]*$"
        )
        task = re.search(
            task_pattern,
            folded,
            re.IGNORECASE,
        )
        original_task = re.search(
            task_pattern,
            evidence,
            re.IGNORECASE,
        )
        if (
            task is not None
            and original_task is not None
            and original_task.group("title").strip()
        ):
            return {"title": clause_literal(original_task.group("title"))}
        alternate_task = re.search(
            (
                r"^[Â¿?Â¡!\s]*(?:crea|crear|create|agrega|agregar|add)\s+"
                r"(?P<title>.+?)\s+(?:como\s+(?:una?\s+)?tarea|"
                r"as\s+(?:a\s+)?task)[.!?]*$"
            ),
            evidence,
            re.IGNORECASE,
        )
        if alternate_task is not None:
            title = clause_literal(alternate_task.group("title"))
            if title:
                return {"title": title}

    if operation == "note.list":
        if numbers:
            return None
        scopes = {
            scope
            for scope, pattern in (
                ("all", r"\b(?:todas|todos|all)\b"),
                ("trashed", r"\b(?:papelera|eliminadas|trashed|deleted)\b"),
                ("active", r"\b(?:activas|active)\b"),
            )
            if re.search(pattern, folded)
        }
        return {"scope": next(iter(scopes))} if len(scopes) == 1 else {}

    if operation == "task.list":
        if numbers or re.search(r"\b(?:eliminadas|deleted|trashed)\b", folded):
            return None
        statuses = {
            status
            for status, pattern in (
                ("all", r"\b(?:todas|todos|all)\b"),
                ("completed", r"\b(?:completadas|terminadas|completed|done)\b"),
            )
            if re.search(pattern, folded)
        }
        return {"status": next(iter(statuses))} if len(statuses) == 1 else {}

    if operation == "system.process.list":
        return effect_intent.process_inventory_arguments(evidence)

    if operation == "reminder.create":
        relative_reminder = _explicit_relative_reminder_arguments(evidence)
        if relative_reminder is not None:
            return relative_reminder
        reminder = re.search(
            (
                r"\b(?:recordatorio|reminder)\s+"
                r"(?:llamad[oa]|titulad[oa]|named|called)\s+"
                r"(?P<title>.+?)(?=\s+(?:para|for)\s+"
                r"(?:manana|tomorrow)\b)"
            ),
            folded,
            re.IGNORECASE,
        )
        original_reminder = re.search(
            (
                r"\b(?:recordatorio|reminder)\s+"
                r"(?:llamad[oa]|titulad[oa]|named|called)\s+"
                r"(?P<title>.+?)(?=\s+(?:para|for)\s+"
                r"(?:mañana|manana|tomorrow)\b)"
            ),
            evidence,
            re.IGNORECASE,
        )
        clock = re.search(
            (
                r"\b(?:a las?|at)\s+(?P<hour>[0-2]?[0-9])"
                r"(?::(?P<minute>[0-5][0-9]))?\s*(?P<period>am|pm)?\b"
            ),
            folded,
            re.IGNORECASE,
        )
        if (
            reminder is not None
            and original_reminder is not None
            and clock is not None
            and re.search(r"\b(?:manana|tomorrow)\b", folded)
        ):
            hour = int(clock.group("hour"))
            minute = int(clock.group("minute") or "0")
            period = (clock.group("period") or "").casefold()
            if period and not 1 <= hour <= 12:
                return None
            if period == "am":
                hour %= 12
            elif period == "pm":
                hour = (hour % 12) + 12
            if not 0 <= hour <= 23:
                return None
            local_today = datetime.now().astimezone().date()
            local_due = datetime.combine(
                local_today + timedelta(days=1),
                datetime_time(hour, minute),
            )
            due_fold_zero = local_due.replace(fold=0).astimezone(timezone.utc)
            due_fold_one = local_due.replace(fold=1).astimezone(timezone.utc)
            if (
                due_fold_zero != due_fold_one
                or due_fold_zero.astimezone().replace(tzinfo=None) != local_due
            ):
                return None
            due_utc = (
                due_fold_zero.replace(microsecond=0).isoformat().replace("+00:00", "Z")
            )
            return {
                "title": original_reminder.group("title").strip(),
                "dueUtc": due_utc,
            }

    if operation == "notification.cancel.latest":
        domain_kinds = {
            kind
            for kind, pattern in (
                ("alarm", r"\b(?:alarma|alarm)s?\b"),
                ("reminder", r"\b(?:recordatorios?|reminders?)\b"),
            )
            if re.search(pattern, folded)
        }
        return {"kind": next(iter(domain_kinds))} if len(domain_kinds) == 1 else None

    if operation == "notification.cancel.at":
        hour_words = {
            "cero": 0,
            "zero": 0,
            "una": 1,
            "uno": 1,
            "one": 1,
            "dos": 2,
            "two": 2,
            "tres": 3,
            "three": 3,
            "cuatro": 4,
            "four": 4,
            "cinco": 5,
            "five": 5,
            "seis": 6,
            "six": 6,
            "siete": 7,
            "seven": 7,
            "ocho": 8,
            "eight": 8,
            "nueve": 9,
            "nine": 9,
            "diez": 10,
            "ten": 10,
            "once": 11,
            "eleven": 11,
            "doce": 12,
            "twelve": 12,
        }
        clock_matches = list(
            re.finditer(
                (
                    r"\b(?P<hour>[0-2]?[0-9]|cero|zero|una|uno|one|dos|two|"
                    r"tres|three|cuatro|four|cinco|five|seis|six|siete|seven|"
                    r"ocho|eight|nueve|nine|diez|ten|once|eleven|doce|twelve)"
                    r"(?::(?P<minute>[0-5][0-9]))?\s*"
                    r"(?P<period>a\.?\s*m\.?|p\.?\s*m\.?|de la manana|"
                    r"de la tarde|de la noche|in the morning|in the afternoon|"
                    r"in the evening)?(?=\s|$|[,.?!])"
                ),
                folded,
                re.IGNORECASE,
            )
        )
        domain_kinds = {
            kind
            for kind, pattern in (
                ("alarm", r"\b(?:alarma|alarm)\b"),
                ("reminder", r"\b(?:recordatorio|reminder)\b"),
            )
            if re.search(pattern, folded)
        }
        if len(clock_matches) != 1 or len(domain_kinds) != 1:
            return None
        clock = clock_matches[0]
        hour_token = clock.group("hour")
        hour = int(hour_token) if hour_token.isdigit() else hour_words[hour_token]
        minute = int(clock.group("minute") or "0")
        raw_period = (clock.group("period") or "").replace(" ", "")
        if raw_period in {"am", "a.m."} or re.search(
            r"\b(?:de la manana|in the morning)\b",
            clock.group("period") or "",
        ):
            period = "am"
        elif raw_period in {"pm", "p.m."} or re.search(
            r"\b(?:de la tarde|de la noche|in the afternoon|in the evening)\b",
            clock.group("period") or "",
        ):
            period = "pm"
        else:
            period = None
        if not 0 <= hour <= 23 or period is not None and not 1 <= hour <= 12:
            return None
        arguments: dict[str, object] = {
            "hour": hour,
            "kind": next(iter(domain_kinds)),
        }
        if minute:
            arguments["minute"] = minute
        if period is not None:
            arguments["period"] = period
        return arguments

    if operation == "notification.schedule":
        return _explicit_notification_schedule_arguments(evidence)

    if operation in {"bluetooth.radio.set", "audio.microphone.mute"}:
        false_signal = bool(
            re.search(
                r"\b(?:off|disable|desactiva|apaga|unmute|reactiva)\w*\b",
                folded,
            )
        )
        true_signal = bool(
            re.search(
                r"\b(?:on|enable|activa|enciende|encende|prende|mutea|silencia)\w*\b",
                folded,
            )
        )
        if true_signal != false_signal:
            return {"state": true_signal}

    if operation == "filesystem.file.open.latest":
        folders = {
            folder
            for folder, pattern in (
                ("desktop", r"\b(?:desktop|escritorio)\b"),
                ("documents", r"\b(?:documents|documentos)\b"),
                (
                    "downloads",
                    r"\b(?:downloads|downloaded|descargas|descargue|descargue)\b",
                ),
                ("pictures", r"\b(?:pictures|photos|imagenes|fotos)\b"),
            )
            if re.search(pattern, folded)
        }
        if len(folders) == 1:
            return {"folder": next(iter(folders))}

    if operation == "notification.list":
        if effect_intent._notification_listing_request(evidence):
            return {}

    if operation == "bluetooth.radio.status":
        if effect_intent._bluetooth_state_question(evidence):
            return {}

    if operation == "weather.current":
        if effect_intent._weather_lookup_query(evidence) is not None:
            return {"location": effect_intent._weather_location(evidence)}

    if operation == "web.news.headlines":
        if effect_intent._news_headlines_request(evidence):
            return {"topic": effect_intent._news_topic(evidence), "limit": 5}

    if operation == "display.status":
        if effect_intent._display_status_question(evidence):
            return {}

    if operation == "software.python.status":
        if effect_intent._python_status_question(evidence):
            return {}

    if operation == "wifi.scan":
        if effect_intent._wifi_scan_question(evidence) or effect_intent._accepted_wifi_offer_evidence(evidence):
            return {}

    if operation == "wifi.radio.set":
        # NETWORK1737: the desired state comes from the order («prendé» / «apagá»)
        # or from the accepted offer to turn the radio on and scan.
        desired = effect_intent.wifi_radio_set_request(evidence)
        if desired is None and effect_intent._accepted_wifi_offer_evidence(evidence):
            desired = True
        return {"state": desired} if desired is not None else None

    if operation == "calculator.expression.evaluate":
        expression = effect_intent.calculator_expression_request(evidence)
        return {"expression": expression} if expression is not None else None

    if operation == "filesystem.known.list":
        recent_listing = effect_intent._known_folder_recent_listing(evidence)
        if recent_listing is not None:
            return {"folder": recent_listing[0], "limit": recent_listing[1], "order": "recent"}
        listed_folder = effect_intent._known_folder_listing_request(evidence)
        if listed_folder is not None:
            return {"folder": listed_folder, "limit": 100}

    if operation == "filesystem.known.search":
        literal_search = effect_intent._literal_known_file_search(evidence)
        if literal_search is not None:
            return literal_search
        query_match = re.search(
            r"\b(?:palabra|word)\s+[\"'“”‘’«»]?(?P<query>[^\"'“”‘’«».,;!?]+)",
            evidence,
            re.IGNORECASE,
        )
        if query_match is not None:
            query = query_match.group("query").strip()
            if query:
                return {"folder": "all_known", "query": query}

    if operation == "audio.volume":
        if (
            not effect_intent._volume_domain(folded)
            or effect_intent._is_negative_effect_clause(folded)
            or effect_intent._is_meta_or_tool_denial(folded)
        ):
            return None
        word_level = effect_intent._literal_percentage_word_value(folded)
        if word_level is not None:
            if numbers:
                return None
            return {"level": word_level}
        if len(numbers) != 1 or not 0 <= numbers[0] <= 100:
            return None
        level = re.search(
            (
                rf"\b{effect_intent._VOLUME_OBJECT}\b\s+"
                r"(?:a(?:l)?|en|to|at)\s*"
                r"(?P<level>100|[0-9]{1,2})(?![0-9])"
                r"(?:\s*(?:%|por\s+ciento|percent))?"
            ),
            folded,
        )
        if level is None:
            # The closed contextual reader retains the two authored surfaces
            # with a sentence boundary. Reprove that the earlier surface has
            # only a missing level and the answer is one numeric clause; a
            # nearby number, another object or an additional effect is not a
            # literal level for this step.
            prior, separator, answer = folded.rpartition(" . ")
            if (
                separator
                and len(effect_intent._request_clauses(answer)) == 1
                and effect_intent._completed_missing_volume_level_request(
                    answer, prior, ("audio.volume",),
                ) is not None
            ):
                return {"level": numbers[0]}
        if level is None or int(level.group("level")) != numbers[0]:
            return None
        return {"level": numbers[0]}

    if operation == "audio.volume.adjust":
        return effect_intent._literal_volume_adjustment(folded)

    if operation == "audio.app.volume.adjust":
        # AUDIO1787: the application, direction and amount are the person's literal.
        app_volume = effect_intent.app_volume_request(evidence, application_names)
        if app_volume is None or app_volume[2] is None:
            return None
        return {"app": app_volume[0], "amount": app_volume[2], "direction": app_volume[1]}

    if operation == "audio.mute":
        false_pattern = (
            rf"\b(?:{effect_intent._UNMUTE_VERB}|reactiva|reactivar)\b|"
            r"\bquita(?:r)?\s+(?:el\s+)?(?:mute|silencio)\b"
        )
        false_signal = bool(re.search(false_pattern, folded))
        # The noun ``mute`` inside "quita el mute" is evidence for the
        # unmute action, not a second request to enable mute. Remove complete
        # negative phrases before looking for an independent positive cue;
        # "mute and unmute" still retains the first cue and therefore remains
        # safely ambiguous.
        positive_surface = re.sub(false_pattern, " ", folded)
        true_signal = bool(
            re.search(r"\b(?:mute|silencia|silenciar)\b", positive_surface)
            or re.search(rf"\b{effect_intent._MUTE_PREDICATIVE_VERB}\b", positive_surface)
            or re.search(
                r"\b(?:pon(?:e|lo|elo|le|eme)?|ponlo|poner|deja(?:lo)?|dejar|leave|put)\b[^.;!?]{0,48}"
                r"\b(?:en|on)\s+(?:mute|mudo|silencio)\b",
                positive_surface,
            )
            or re.fullmatch(
                r"(?:de\s+ahora\s+en\s+adelante|from\s+now\s+on)\s+"
                r"(?:en\s+)?(?:mudo|mute|silent|silencio)[\s.!?]*",
                positive_surface,
                re.IGNORECASE,
            )
        )
        if true_signal == false_signal:
            return None
        return {"state": true_signal}

    return None


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
    if explicit is None:
        return None
    if operation == "web.search" and explicit.get("query") == _todays_news_query(evidence):
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
        "audio.mute",
        "audio.volume",
        "audio.volume.adjust",
        "browser.control",
        "browser.navigate",
        "browser.navigate.named",
        "calendar.event.list",
        "client.channel.locate",
        "message.draft",
        "message.send.test",
        "game.launch",
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


def _fully_enumerated_note_create_arguments(
    objective: str,
) -> tuple[dict[str, str], ...]:
    """Extract every exact title/content pair from one complete note list."""

    requested_order = effect_intent.enumerated_note_dependency_order(objective)
    if not requested_order:
        return ()
    compact = " ".join(objective.split())
    header = re.search(
        r"\b(?:dos|two|tres|three|cuatro|four|cinco|five|seis|six|"
        r"siete|seven|ocho|eight|[2-8])\s+"
        r"(?:(?:private|local|privadas?|locales?)\s+)?(?:notas|notes)\s*:\s*",
        compact,
        re.IGNORECASE,
    )
    if header is None:
        return ()
    create_body = compact[header.end() :]
    boundary = re.search(
        r"[.!?]\s*(?:despu[eé]s|after)\b",
        create_body,
        re.IGNORECASE,
    )
    if boundary is not None:
        create_body = create_body[: boundary.start()]
    content_marker = (
        r"(?:con\s+(?:el\s+)?(?:contenido|texto)|"
        r"with\s+(?:the\s+)?content)"
    )
    item_pattern = re.compile(
        rf"(?:^|,\s*|\s+(?:y|and)\s+)"
        rf"(?P<title>[^,;]{{1,120}}?)\s+{content_marker}\s+"
        rf"(?P<content>.+?)"
        rf"(?=(?:,\s*|\s+(?:y|and)\s+)[^,;]{{1,120}}?\s+"
        rf"{content_marker}\s+|$)",
        re.IGNORECASE,
    )
    ordinal_prefix = re.compile(
        r"^(?:(?:la|el|the)\s+)?(?:primera|primer|first|segunda|second|"
        r"tercera|tercer|third|cuarta|cuarto|fourth|quinta|quinto|fifth|"
        r"sexta|sexto|sixth|septima|septimo|seventh|octava|octavo|eighth)\s+"
        r"(?:titulada|titulado|llamada|llamado|titled|named|called)\s+",
        re.IGNORECASE,
    )
    arguments: list[dict[str, str]] = []
    for found in item_pattern.finditer(create_body):
        title = ordinal_prefix.sub("", found.group("title")).strip(" ,.;:")
        content = found.group("content").strip(" ,.;:")
        if (
            not title
            or not content
            or len(title.encode("utf-8")) > 512
            or len(content.encode("utf-8")) > 512
        ):
            return ()
        arguments.append({"title": title, "content": content})
    if len(arguments) != len(requested_order) or len(
        {item["title"].casefold() for item in arguments}
    ) != len(arguments):
        return ()
    return tuple(arguments)


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


def _canonical_due_utc(
    value: str,
    context: str = "",
    *,
    now_utc: datetime | None = None,
) -> str | None:
    """Convert one exact natural clock literal to an unambiguous future UTC."""

    if not isinstance(value, str) or not value.strip():
        return None
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now_utc must carry timezone authority")
    now = now.astimezone(timezone.utc)
    raw = value.strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        parsed = None
    if parsed is not None and parsed.tzinfo is not None:
        parsed_utc = parsed.astimezone(timezone.utc)
        if parsed_utc > now + timedelta(seconds=5):
            return parsed_utc.isoformat().replace("+00:00", "Z")
        return None

    folded_value = effect_intent._fold(raw)
    relative = re.fullmatch(
        rf"(?:(?:en|in|dentro de|within)\s+)?"
        r"(?:(?P<half>media\s+hora|half\s+an?\s+hour)|"
        rf"(?P<number>{_TEMPORAL_NUMBER_PATTERN})\s*"
        rf"(?P<unit>{effect_intent._RELATIVE_DURATION_UNIT}))"
        r"(?:\s+(?:from now|desde ahora))?",
        folded_value,
        re.IGNORECASE,
    )
    if relative is not None:
        if relative.group("half"):
            amount, unit = 30, "minutes"
        else:
            amount = _temporal_number(relative.group("number"))
            unit = relative.group("unit")
        if amount is None or not 1 <= amount <= 24 * 60:
            return None
        if unit.startswith(("day", "dia")):
            if amount > 365:
                return None
            delta = timedelta(days=amount)
        elif unit.startswith(("hour", "hora", "h")):
            delta = timedelta(hours=amount)
        else:
            delta = timedelta(minutes=amount)
        due = now + delta
        if due.microsecond:
            # The Windows Task Scheduler registers whole seconds only (TIME1139
            # probes: StartBoundary and NextRunTime lose fractions by cmdlet and
            # by XML). Publish the second the task will actually carry, never
            # earlier than the requested moment (owner decision 2026-09-13).
            due = due.replace(microsecond=0) + timedelta(seconds=1)
        return due.isoformat().replace("+00:00", "Z")

    folded_context = effect_intent._fold(context)
    clock_source = f"{folded_value} {folded_context}".strip()
    military_clock = re.search(
        r"\b(?:at|a|para)\s+(?:las?\s+)?"
        r"(?P<hour24>[01]?[0-9]|2[0-3]):(?P<minute24>[0-5][0-9])\b"
        # «6:30 de la tarde» is a 12-hour clock with its period, not 06:30.
        r"(?!\s*(?:a\.?\s*m\.?|p\.?\s*m\.?|de\s+la\s+(?:manana|maniana|tarde|noche)|"
        r"in\s+the\s+(?:morning|afternoon|evening)))",
        clock_source,
        re.IGNORECASE,
    )
    clock = re.search(
        rf"\b(?P<hour>{_TEMPORAL_NUMBER_PATTERN})"
        r"(?::(?P<minute>[0-5][0-9]))?\s*"
        r"(?P<period>a\.?\s*m\.?|p\.?\s*m\.?|de la manana|"
        r"de la maniana|de la tarde|de la noche|in the morning|"
        r"in the afternoon|in the evening)\b",
        clock_source,
        re.IGNORECASE,
    )
    if military_clock is None and clock is None:
        return None
    if military_clock is not None:
        hour = int(military_clock.group("hour24"))
        minute = int(military_clock.group("minute24"))
    else:
        assert clock is not None
        parsed_hour = _temporal_number(clock.group("hour"))
        minute = int(clock.group("minute") or "0")
        if parsed_hour is None or not 1 <= parsed_hour <= 12:
            return None
        period = effect_intent._fold(clock.group("period")).replace(" ", "")
        is_am = period in {"am", "a.m."} or "manana" in period or "maniana" in period
        is_pm = period in {"pm", "p.m."} or any(
            marker in effect_intent._fold(clock.group("period"))
            for marker in ("tarde", "noche", "afternoon", "evening")
        )
        if is_am == is_pm:
            return None
        hour = parsed_hour % 12 if is_am else (parsed_hour % 12) + 12
    local_now = (
        datetime.now().astimezone()
        if now_utc is None
        else now.astimezone(now_utc.tzinfo)
    )
    month_numbers = {
        "enero": 1,
        "january": 1,
        "febrero": 2,
        "february": 2,
        "marzo": 3,
        "march": 3,
        "abril": 4,
        "april": 4,
        "mayo": 5,
        "may": 5,
        "junio": 6,
        "june": 6,
        "julio": 7,
        "july": 7,
        "agosto": 8,
        "august": 8,
        "septiembre": 9,
        "september": 9,
        "octubre": 10,
        "october": 10,
        "noviembre": 11,
        "november": 11,
        "diciembre": 12,
        "december": 12,
    }
    month_names = "|".join(month_numbers)
    month_date = re.search(
        (
            rf"\b(?:(?P<month_first>{month_names})\s+"
            r"(?P<day_after>\d{1,2})(?:st|nd|rd|th)?|"
            r"(?P<day_before>\d{1,2})(?:st|nd|rd|th)?\s+"
            rf"(?:de\s+)?(?P<month_after>{month_names}))"
            r"(?:,?\s+(?P<year>\d{4}))?\b"
        ),
        clock_source,
        re.IGNORECASE,
    )
    day_of_month = None
    if month_date is None:
        day_of_month = re.search(
            r"\b(?:on\s+(?:the\s+)?|el\s+)"
            r"(?P<day>\d{1,2})(?:st|nd|rd|th)?\b",
            clock_source,
            re.IGNORECASE,
        )
    if (month_date is not None or day_of_month is not None) and re.search(
        r"\b(?:tomorrow|manana|maniana)\b", clock_source
    ):
        return None

    def materialize_date(local_date: date) -> datetime | None:
        naive = datetime.combine(local_date, datetime_time(hour, minute))
        if now_utc is None:
            fold_zero = naive.replace(fold=0).astimezone(timezone.utc)
            fold_one = naive.replace(fold=1).astimezone(timezone.utc)
            round_trip = fold_zero.astimezone().replace(tzinfo=None)
        else:
            local_zone = local_now.tzinfo
            if local_zone is None:
                return None
            fold_zero = naive.replace(tzinfo=local_zone, fold=0).astimezone(
                timezone.utc
            )
            fold_one = naive.replace(tzinfo=local_zone, fold=1).astimezone(timezone.utc)
            round_trip = fold_zero.astimezone(local_zone).replace(tzinfo=None)
        if fold_zero != fold_one or round_trip != naive:
            return None
        return fold_zero.replace(microsecond=0)

    explicit_dates: list[date] = []
    if month_date is not None:
        month_name = month_date.group("month_first") or month_date.group("month_after")
        day_text = month_date.group("day_after") or month_date.group("day_before")
        month = month_numbers[month_name.casefold()]
        day = int(day_text)
        year_text = month_date.group("year")
        years = (
            (int(year_text),)
            if year_text is not None
            else (local_now.year, local_now.year + 1)
        )
        for year in years:
            try:
                explicit_dates.append(date(year, month, day))
            except ValueError:
                continue
    elif day_of_month is not None:
        day = int(day_of_month.group("day"))
        year = local_now.year
        month = local_now.month
        for _ in range(24):
            try:
                explicit_dates.append(date(year, month, day))
            except ValueError:
                pass
            month += 1
            if month == 13:
                month = 1
                year += 1

    if month_date is not None or day_of_month is not None:
        for local_date in explicit_dates:
            due = materialize_date(local_date)
            if due is not None and due > now + timedelta(seconds=5):
                return due.isoformat().replace("+00:00", "Z")
        return None

    days = 1 if re.search(r"\b(?:tomorrow|manana|maniana)\b", clock_source) else 0

    def materialize(day_offset: int) -> datetime | None:
        return materialize_date(local_now.date() + timedelta(days=day_offset))

    due = materialize(days)
    if due is None:
        return None
    if days == 0 and due <= now + timedelta(seconds=5):
        due = materialize(1)
    if due is None or due <= now + timedelta(seconds=5):
        return None
    return due.isoformat().replace("+00:00", "Z")


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
        language = re.search(
            r"\b(?:idioma|language)\s+(?:literal(?:mente)?|exact(?:o|a|ly)?)\s+"
            r"[\"'\u201c\u201d]?([a-z][a-z0-9-]{1,31})[\"'\u201c\u201d]?",
            objective,
            re.IGNORECASE,
        )
        if language is not None:
            normalized["language"] = language.group(1)
    if operation == "vision.describe" and "prompt" not in normalized:
        prompt = re.search(
            r"\b(?:prompt\s+exact[oa]|exact\s+prompt)\s*"
            r"[\"\u201c]([^\"\u201d]{1,2000})[\"\u201d]",
            objective,
            re.IGNORECASE,
        )
        if prompt is not None:
            normalized["prompt"] = prompt.group(1)
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
            title = re.sub(
                r"^\s*(?:que|that)\s+",
                "",
                str(normalized["title"]),
                count=1,
                flags=re.IGNORECASE,
            ).strip()
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
            and not re.search(r"\bspotify\b", literal_evidence, re.IGNORECASE)
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
                if operation == "app.close"
                and (
                    re.search(
                        r"\b(?:activa|active|actual|current|cierralo|cierrala|"
                        r"close it|cerrala|cerralo)\b",
                        effect_intent._fold(literal_evidence),
                    )
                    or effect_intent.deictic_close_request(
                        effect_intent._strip_request_envelope(effect_intent._fold(literal_evidence))
                    )
                )
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
        prerequisites = required_predecessors(operation) or conditional_predecessors(
            operation, purpose
        )
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


def _select_referenced_predecessor(
    candidate_indexes: list[int],
    evidence: str,
) -> int:
    """Resolve bounded ordinal coreference; otherwise prefer the latest result."""

    folded = effect_intent._fold(evidence)
    if re.search(
        r"\b(?:(?:la|the)\s+)?(?:primera|primer|first)\s+"
        r"(?:nota|note|documento|document|resultado|result|una|one)\b",
        folded,
    ):
        return candidate_indexes[0]
    if len(candidate_indexes) >= 2 and re.search(
        r"\b(?:(?:la|the)\s+)?(?:segunda|segundo|second)\s+"
        r"(?:nota|note|documento|document|resultado|result|una|one)\b",
        folded,
    ):
        return candidate_indexes[1]
    if re.search(
        r"\b(?:(?:la|the)\s+)?(?:ultima|ultimo|last|latest)\s+"
        r"(?:nota|note|documento|document|resultado|result|una|one)\b",
        folded,
    ):
        return candidate_indexes[-1]
    return candidate_indexes[-1]


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


_COMMON_BARE_APPLICATION_REQUESTS = frozenset(
    {
        "booking",
        "discord",
        "facebook",
        "instagram",
        "snapchat",
        "telegram",
        "tiktok",
        "whatsapp",
    }
)


def _catalog_unavailable_turn_decision(
    objective: str,
    explicit_intent: EffectIntent | None,
    application_names: tuple[str, ...] | ApplicationCatalogIndex,
    game_catalog: GameCatalogIndex,
) -> dict[str, object] | None:
    """Close literal app/game requests that lack an authenticated identity."""

    if explicit_intent is not None or _deictic_open_request(objective):
        return None
    folded = effect_intent._strip_request_envelope(effect_intent._fold(objective))
    if not folded:
        return None
    bare_application = effect_intent._application_name_key(folded.rstrip(" ?!."))
    application_keys = build_application_catalog_index(application_names).keys
    requested_common_applications = tuple(
        name
        for name in _COMMON_BARE_APPLICATION_REQUESTS
        if re.search(rf"\b{re.escape(name)}\b", folded)
    )
    application_request = (
        re.match(
            r"^(?:take\s+me\s+to|go\s+to|get\s+.+?\s+started|open|abre|abrir|"
            r"inicia|iniciar|lanza|launch|ouverture)\b",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    unavailable_application = (
        bare_application in _COMMON_BARE_APPLICATION_REQUESTS
        and bare_application not in application_keys
    ) or (
        application_request
        and len(requested_common_applications) == 1
        and requested_common_applications[0] not in application_keys
    )
    game_request = (
        re.match(
            (
                r"^[¿?¡!\s]*(?:(?:por favor|please)\s*[,;:]?\s*)?"
                r"(?:(?:(?:vamos\s+a|let(?:'s|\s+us))\s+(?:start\s+)?"
                r"(?:juega|jugar|juguemos|play|playing))|"
                r"(?:juega|jugar|juguemos|play|start\s+up)|"
                r"(?:abre|abrir|open|lanza|launch|ejecuta|run))\b\s+"
                r"(?:(?:al|el|the)\s+)?(?:(?:juego|game)\s+)?\S.+$"
            ),
            folded,
            re.IGNORECASE,
        )
        is not None
        or re.fullmatch(
            r"get\s+\S.{0,160}\s+started[\s.!?]*",
            folded,
            re.IGNORECASE,
        )
        is not None
    )
    unavailable_game = (
        game_request
        and effect_intent._authenticated_game_target(folded, game_catalog) is None
    )
    if not unavailable_application and not unavailable_game:
        return None
    return _explicit_unsupported_turn_decision(objective)


def _emit_early_turn_signal(
    *,
    path: str,
    objective: str,
    request_id: object,
    on_signal: Callable[[dict[str, Any]], None] | None,
    already_signaled: list[bool],
    step_count: int = 1,
    llm: Any = None,
    phase: str = "understanding",
) -> None:
    if already_signaled or on_signal is None:
        return
    if not should_emit_early(path, step_count):
        return
    compose = getattr(llm, "compose_user_message", None)
    if compose is None:
        return
    try:
        text = compose(
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
    except Exception as error:  # noqa: BLE001 - optional prose cannot fail the turn
        _append_turn_audit({
            "schema": "baxy.mind-turn-audit.v1",
            "request_id": request_id,
            "phase": "progress_unavailable",
            "error_type": type(error).__name__,
        })
        return
    if not str(text or "").strip():
        return
    on_signal(
        turn_signal_payload(
            request_id,
            str(text).strip(),
        )
    )
    already_signaled.append(True)


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
    on_signal: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Prepare one side-effect-free turn result from the current request."""
    already_signaled: list[bool] = []

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
    nothing_to_clarify = bool(
        read_request(objective).intents
        & {INTENT_CAPABILITY, INTENT_REFUSE, INTENT_CONTINUE_CONSTRAINT}
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
    literal_recall_decision = (
        {
            "mode": "conversation",
            "operation": None,
            "question": "",
            "conversation_kind": "followup",
            "effect_count": "zero",
            "effect_operations": [],
            "effect_verification": "not_applicable",
            "response_language": _explicit_response_language(objective),
        }
        if recalled_literal is not None
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
    explicit_intent = (
        None
        if non_target_language is not None or stable_no_effect_is_closed
        else accepted_wifi_offer
        or live_public_intent
        or resolve_explicit_effects(
            objective,
            available_operations,
            application_names,
            game_catalog,
            previous_user_text=_previous_user_request(history, objective),
        )
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
    catalog_unavailable_decision = _catalog_unavailable_turn_decision(
        objective,
        explicit_intent,
        application_names,
        game_catalog,
    )
    unresolved_compound_effects = unresolved_compound_contract(
        objective,
        available_operations,
        application_names,
        game_catalog,
        resolved_intent=explicit_intent,
        previous_user_text=_previous_user_request(history, objective),
    )
    explicit_conversation_decision = (
        _explicit_unsupported_turn_decision(objective)
        if non_target_language is not None
        or (
            unresolved_compound_effects is not None
            and (
                effect_request_is_authoritative(objective)
                or unsupported_effect_demonstration_request(objective)
            )
        )
        or (
            effect_request_is_authoritative(objective)
            and known_unsupported_effect_request(
                objective,
                available_operations,
            )
        )
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
    verify_shape = getattr(llm, "_verify_semantic_effect_shape", None)
    if (
        not closed_no_effect_conversation
        and explicit_intent is None
        and non_target_language is None
        and stable_no_effect_decision is not None
        and stable_no_effect_decision.get("conversation_kind") == "knowledge"
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
    ):
        # Two stages withdraw an effect the model proposed, and both of them
        # publish the withdrawal as a *conversation* -- which the presentation
        # then words as "no puedo". Neither stage is entitled to that claim.
        # The curated gate is one-sided and lexical: it can only tell that the
        # request does not *name* the domain this operation consumes. The
        # information-question veto only knows that the sentence was phrased as
        # a question. Publishing either as an inability is how "No puedo apagar
        # el bluetooth" and "No puedo proporcionar tu dirección IP" reached the
        # screen about capabilities that are in the catalogue -- 24 of the 27
        # rows these stages cost on the goal 03 corpus, and the identity's
        # inverse fault: BAXY says no only to what he cannot do. It is also why
        # the turn kept dying: the presentation contract for ``unsupported``
        # demands a sentence the model will not write about something it can do,
        # and 22 of 160 turns fell through to total recovery that way.
        #
        # So the verdict stops being binary. A second, independent opinion is
        # asked -- does this operation *identify* the effect the person named --
        # and when it does, the authority is not deleted, it is withheld until
        # the person confirms the exact invocation. No effect is dispatched
        # either way, so the invariant these stages exist for is untouched; what
        # changes is that BAXY asks instead of lying.
        confirmable = _withheld_invocation_operations(
            withdrawn_effects,
            objective,
            tool_by_name,
            llm,
            application_names,
        )
        app_evidence = (
            explicit_intent.evidence
            if explicit_intent is not None
            and explicit_intent.operations == effects_before_domain_grounding
            else (objective,)
        )
        if (
            effects_before_domain_grounding == ("app.open",)
            and unresolved_compound_effects is None
            and confirmable == ("app.open",)
            and effect_request_is_authoritative(objective)
            and len(app_evidence) == 1
            and isinstance(app_evidence[0], str)
            and app_evidence[0].strip()
            and resolve_application_catalog_app_id(app_evidence[0], application_names)
            is None
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
        else:
            question = (
                _domain_confirmation_question(objective, confirmable, tool_by_name, llm)
                if confirmable
                else ""
            )
        if question:
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
            decision = validate_turn_decision(
                decision,
                {tool.name for tool in shortlist},
            )
            intent_operations = list(confirmable)
            turn_audit["stages"].append(
                _turn_audit_stage("domain_confirmation", decision)
            )
        else:
            # Both one-sided guards refused. Now "unsupported" is the honest
            # word, and the raw proposal stays only in the opt-in audit: nobody
            # is asked for fields of an unrelated capability (for example
            # scheduling a notification for a taxi order).
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
        retired_catalog_effect=bool(
            (effects_before_information_veto or effects_before_domain_grounding)
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
        )
        question = (
            _domain_confirmation_question(objective, (observing,), tool_by_name, llm)
            if observing
            else ""
        )
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
            intent_operations = [observing]
            turn_audit["stages"].append(
                _turn_audit_stage("observation_not_recital", decision)
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
            response_language = _decisive_request_language(objective)
            if response_language is None and isinstance(history, list):
                # MUSIC1753 «Play a song on Spotify.» → «Queen»: an answer with
                # no language of its own keeps the language of the request it
                # answers; a proper name is not Spanish evidence.
                previous = _previous_user_request(history, objective)
                if isinstance(previous, str) and previous.strip():
                    response_language = _decisive_request_language(previous)
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
                # A closed social act is a complete new presentation. Replaying
                # an earlier saved-memory result made a new introduction claim
                # another save. Scope this generation; retain the actual dialogue
                # and all context-dependent or model-classified conversations.
                history=(
                    []
                    if explicit_conversation_decision is not None
                    and presentation_conversation_kind == "social"
                    else history
                ),
                tools=None,
                temperature=0.0,
                conversation_kind=presentation_conversation_kind,
                authenticated_operations=tuple(intent_operations),
                # IDENTITY1325: «cómo funciona esto» names what the served
                # catalog does on this PC; the families come from it.
                served_operations=available_operations,
                # Language is independently constrained from the current message.
                # The routing field cannot force the wrong response language.
                response_language=response_language,
            )
        reply_text = reply_text.strip()
        if not reply_text:
            raise PlannerContractError(
                "no se pudo preparar una respuesta conversacional"
            )
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
    nothing_to_clarify = bool(
        read_request(objective).intents
        & {INTENT_CAPABILITY, INTENT_REFUSE, INTENT_CONTINUE_CONSTRAINT}
    ) or effect_intent.out_of_world_request(objective)
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
        kind, text = _recovery_visible_from_compose(llm, objective)
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
                "reply": text,
                # cien-38 060 «ship a piano to Charon»: the recovery composed
                # «I can't ship a piano to Charon—that's outside what I do»
                # and the App refused it as looks_like_failure, because the
                # boundary did not travel with the reply, then published its
                # own «I couldn't understand the request properly», which is
                # false. A limit is a limit also when it is recovered.
                "conversationKind": (
                    "unsupported"
                    if effect_intent.out_of_world_request(objective)
                    else None
                ),
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


def _recovery_visible_from_compose(llm: Any, objective: str) -> tuple[str, str]:
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
                "error",
                {
                    "situation": json.dumps(
                        {
                            "kind": "failure",
                            # A place no operation reaches is a boundary, not a
                            # failed reading: «I couldn't understand the request to
                            # send flowers to Deimos» is false.
                            "cause": (
                                "out_of_catalog"
                                if effect_intent.out_of_world_request(objective)
                                else "request_analysis_failed"
                            ),
                            "polarity": "failure",
                        },
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
                            on_signal=write_request_message,
                        )
                    except PlannerContractError as error:
                        turn_failure_kinds.append("contract")
                        _audit_turn_attempt_failure(message, error, "contract")
                        raise
                    except Exception as error:  # noqa: BLE001 - stable telemetry only
                        turn_failure_kinds.append("runtime")
                        _audit_turn_attempt_failure(message, error, "runtime")
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
                        attempts=2,
                        failure_kinds=tuple(turn_failure_kinds),
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
                        on_signal=write_request_message,
                        already_signaled=[],
                        llm=llm,
                        phase="preparing_steps",
                    )
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
                    extraction = llm.extract_direct_arguments(objective, tool)
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
                user_text = str(message.get("userText", ""))[:4096]
                situation = _situation_from_facts(facts)
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
                else:
                    text = llm.compose_user_message(
                        user_text,
                        str(message.get("intent", "status"))[:32],
                        facts,
                    )
                if not text:
                    raise RuntimeError("respuesta vacía")
                write_request_message(
                    {
                        "type": "message.compose.result",
                        "id": request_id,
                        "text": text[:4096],
                    }
                )
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
