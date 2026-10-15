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
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable

# PyTorch otherwise sizes its CPU pools for the whole machine. On a 16 GiB
# notebook that creates dozens of workers and can turn startup into minutes of
# paging. Keep explicit operator overrides, but use a small production default.
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from . import protocol
from . import computer_use, effect_intent
from .semantic import cu_semejanza
from .llm_startup import LlmStartupFailure
from .semantic import dialogue as dialogue_slot
from .semantic import arguments as semantic_arguments
from .semantic import captures as semantic_captures
from .semantic import limits as semantic_limits
from .semantic import temporal as semantic_temporal
from .corrector import catalog_correction_terms
from .first_signal import PATH_MODEL, PendingTurnSignal
from .effect_intent import build_application_catalog_index, build_game_catalog_index
from .llm import LlmRuntime
from .compose_situation import _merged_observed, _situation_from_facts
from .capability_families import served_capability_families
from .planner import (
    PlannerCatalog,
    PlannerContractError,
    attach_arguments,
    normalize_grounded_arguments,
    validate_json_schema_instance,
    validate_skeleton,
)
from .router import ProcessIntentRouter, RequestBudgetEncoder
from .voice import VoiceEngine, prewarm_voice_runtime
from .semantic.arguments import (
    _fully_enumerated_note_create_arguments,
    _presentation_arguments,
    partial_explicit_arguments,
    window_snap_plan_split,
)
from . import argument_grounding
from . import turn_audit as turn_audit_module
from .sidecar_budgets import (
    _message_composition_budget,
    ARGUMENT_REQUEST_BUDGET_SECONDS,
    BACKGROUND_ENCODER_TIMEOUT_SECONDS,
    CATALOG_REQUEST_BUDGET_SECONDS,
    TURN_DECIDE_ATTEMPT_BUDGET_SECONDS,
    TURN_DECIDE_NORMAL_BUDGET_SECONDS,
    TURN_DECIDE_RECOVERY_BUDGET_SECONDS,
)
from .turn_audit import _computer_use_witness_audit, _turn_failure_kind
from .request_lane import (
    _AcknowledgedVoiceCancel,
    _DispatchFinished,
    _InboundMessage,
    _LaneSubmission,
    _open_protocol_reader,
    _ReadFailure,
    _receive_protocol_messages,
    _SerialRequestLane,
    _TerminalProtocolWriter,
)
from .sidecar_lifecycle import _report_secondary_cleanup_failure, _SidecarLifecycle
from .tool_catalog import (
    _create_planner_resources,
    _require_catalog_llm_ready,
    configure_application_catalog,
    configure_game_catalog,
    configure_tools,
)
from .turn_history import _decisive_request_language, _person_message
from .argument_grounding import (
    _ground_explicit_arguments,
    _restore_evidence_surfaces,
    normalize_objective_arguments,
    trusted_plan_grounding_source,
)
from .plan_dependencies import (
    _conversation_note_selector,
    _verified_dependency_identity_arguments,
    _verified_message_send_arguments,
)
from .decided_arguments import _plan_step_decided_arguments
from .plan_shape import (
    _evidence_of_expected_operations,
    _expand_effect_plan,
    _explicit_plan_skeleton,
    _irrelevant_plan_operations,
    _mission_split_by_the_model,
    _plan_effects_read,
    _plan_result_message,
    _prepare_plan_prompt_resources,
    _retimed_step_arguments,
    _the_plans_only_opening,
)
from .direct_arguments import _direct_arguments_result
from .turn_recovery import _recover_failed_turn, _recovery_question_is_valid, _retry_side_effect_free_turn
from .engine_handoff import _asks_when_the_antecedent_failed, _asks_which_window, _engine_for_an_unserved_order
from .compose_facts import (
    _count_read_beside_the_named_place,
    _read_the_page_on_show,
    _told_where_it_was_made,
    _with_asked_listing,
    _with_listing_and_repetition_facts,
    _with_made_in_store,
    _with_unreceived_parts,
)
from .send_offer import _expect_decided_turn, _with_send_offer
from .turn_followups import _NOTICE_CANCELS, _NOTICE_SETS, _retimed_conversation_notice, _undelivered_done_again
from .context_decision import _warm_context_decider
from .turn_decide import _emit_early_turn_signal, _prepare_turn_result, _readers_send, _start_readers_warmup


_write_lock = threading.Lock()
# Failures whose final is a question to the person: a replan of the same
# suffix would only repeat the failed step (REOPEN1957 H0170/H0376).
_NO_REPLAN_ERROR_CODES = frozenset({"wifi_place_unknown"})
# Protocol lines may be 1 MiB. Bound both read-ahead stages so a stalled
# model request cannot turn a cooperative desktop transport into a memory sink.
CONTROL_EVENT_QUEUE_LIMIT = 4


def _write(message: dict) -> None:
    with _write_lock:
        protocol.write_message(message)


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
    turn_audit_module._append_turn_audit(record)


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


class PlannerClarification(PlannerContractError):
    """Typed semantic abstention; only validated LLM text can enter this path."""

    def __init__(self, question: str) -> None:
        super().__init__("semantic_clarification")
        self.question = question


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


def _startup_failure_reply(request_id: object, failure: LlmStartupFailure) -> dict[str, Any]:
    """The catalog's runtime failure with the model's startup cause beside it."""

    reply = protocol.error_reply(
        request_id,
        "request_failed",
        technical_failure_message("catalog.configure", "runtime"),
    )
    reply["startup"] = failure.report()
    try:
        exit_label = "" if failure.exit_code is None else f":{failure.exit_code}"
        sys.stderr.write(f"baxy_mind_startup_failure:{failure.cause}{exit_label}\n")
        for line in failure.tail:
            sys.stderr.write(f"baxy_mind_startup_tail:{line}\n")
        sys.stderr.flush()
    except Exception:  # noqa: BLE001 - diagnostics cannot change the reply
        pass
    return reply


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
        # The worker spawns with the mind (3 s after it until lat-e5,
        # router.ROUTER_START_DELAY_SECONDS) and needs ~11 s to load E5. Polling
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
        # A computer-use step reads the encoder too (the goal's place matched by meaning, goal v3 P1), within a
        # short budget of its own: past it the step is the literal one. The step's SemanticMatcher renews this
        # deadline before each encoding to what the encoder alone has spent, so a label translation by the model
        # earlier in the same step never uses it up.
        interactive_request = str(kind) in {"turn.decide", "plan", "computer.use.step"}
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
                    "computer.use.step": 30.0,
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
                        else cu_semejanza.ENCODER_BUDGET_SECONDS
                        if kind == "computer.use.step"
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
                    readers_warmup = _start_readers_warmup(
                        lexical_catalog, tool_by_name, application_catalog, game_catalog,
                    )
                    # A catalog-ready reply promises that the optional model
                    # can serve the next turn.  CPU-only cold starts can take
                    # longer than 45 seconds; 90 seconds remains inside the
                    # shell's 120-second authenticated handshake boundary.
                    try:
                        _require_catalog_llm_ready(llm)
                    except LlmStartupFailure as failure:
                        write_request_message(_startup_failure_reply(request_id, failure))
                        continue
                    # The first turn starts after the warm-up, never beside it: a model ready before the readers
                    # finished had the turn compile the same expressions as the warm-up at the same time.
                    readers_warmup.join()
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
                # Revisión B2 H3: an offer told in the last final is read by this turn only, whatever comes of it.
                dialogue_state.begin_turn()
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
                turn_result = _engine_for_an_unserved_order(turn_result, message, tool_by_name, application_catalog)
                turn_result = _asks_which_window(turn_result, message, application_catalog)
                turn_result = _asks_when_the_antecedent_failed(
                    turn_result, message, dialogue_state, application_catalog,
                )
                turn_result = _read_the_page_on_show(turn_result, message, dialogue_state, tool_by_name)
                # Ronda 19: a reproach of what a failed turn was asked does it again instead of asking for it.
                turn_result = _undelivered_done_again(turn_result, message, dialogue_state)
                # The request this turn decided is the last one now; its operations (the effects, or those a
                # question is about) wait for their verified results (message.compose).
                _expect_decided_turn(dialogue_state, turn_result, message, planner_catalog, application_catalog)
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
                    _plan_effects_read(
                        objective,
                        expected_operations,
                        tuple(tool.name for tool in planner_catalog.tools),
                        history,
                        application_catalog,
                        game_catalog,
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
                    if set(expected_operations) & _NOTICE_SETS
                    else None
                )
                if (
                    retimed is None
                    and set(expected_operations) & _NOTICE_SETS
                    and set(expected_operations) & _NOTICE_CANCELS
                ):
                    # M115 (DEV-F v4e2 F-w12-t2, F-w15-t4, F-w07-t4): the plan already moves the notification just set;
                    # its new time is the one clock the person said, or else the one the restatement says, and the
                    # rest (its kind, what it is for, the old time to cancel) is what was verified setting it.
                    # M173: or the reminder of the store just made, and the moment counted from what BAXY said.
                    retimed = _retimed_conversation_notice(dialogue_state, history, objective)
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
                    if step.operation in semantic_captures.CAPTURE_OPERATIONS:
                        # Ronda 22: a capture step is kept where the request says to keep it, read from the whole
                        # request (the step's purpose may leave the keeping out); else it stays private. Never the
                        # model's extraction: «captura y dime qué ves» writes no file.
                        arguments_by_step[step.step_id] = semantic_captures.capture_save_arguments(objective)
                        continue
                    enumerated_arguments = note_arguments_by_step.get(step.step_id)
                    if enumerated_arguments is not None:
                        grounded, _ = normalize_objective_arguments(
                            enumerated_arguments,
                            schema,
                            objective,
                        )
                        if grounded is not None:
                            grounded = argument_grounding._normalize_grounded_operation_arguments(
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
                    if step.operation == "mission.computer.use":
                        split_mission = _mission_split_by_the_model(llm, step.purpose, application_catalog)
                        if split_mission is not None and validate_json_schema_instance(split_mission, schema):
                            arguments_by_step[step.step_id] = split_mission
                            continue
                    if expected_operations:
                        explicit_arguments = _ground_explicit_arguments(
                            step.operation,
                            step.purpose,
                            schema,
                            application_names,
                            game_catalog,
                            # M62 (F-s044): a moved alarm takes its part of the day from what was said before.
                            # v3 destino: a free goal with no application said happens in the conversation's.
                            history=history if step.operation in {"notification.schedule", "mission.computer.use"} else None,
                        )
                        if explicit_arguments is None and step.operation == "notification.cancel.latest":
                            # M145: a cancellation made the latest one's (``_own_notification_cancellation``) takes
                            # its kind from the request that named it («Cambia la alarma de las 7:00 a las 7:15.»).
                            explicit_arguments = _ground_explicit_arguments(step.operation, objective, schema)
                        if explicit_arguments is None:
                            explicit_arguments = _the_plans_only_opening(
                                step.operation, plan_operations, objective, schema, application_names, game_catalog,
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
                        grounded = argument_grounding._normalize_grounded_operation_arguments(
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
                for step in proposal.steps:
                    if step.operation == "app.open" and step.step_id in arguments_by_step:
                        # cu-v3-documento-nuevo: «un bloc de notas nuevo» opens a new document, never the open one.
                        # Only the person's words decide it (review, finding 8).
                        arguments_by_step[step.step_id] = semantic_arguments.with_new_document(
                            arguments_by_step[step.step_id],
                            (_person_message(history, objective),),
                            application_names,
                        )
                    if step.operation == "mission.computer.use" and step.step_id in arguments_by_step:
                        # Estabilización L: the sub-goal that is a declared limit, or whose place needs a device, is marked.
                        arguments_by_step[step.step_id] = semantic_limits.with_declared_limits(
                            arguments_by_step[step.step_id]
                        )
                    if step.operation == "web.search" and step.step_id in arguments_by_step:
                        arguments_by_step[step.step_id] = _with_asked_listing(
                            step.operation, arguments_by_step[step.step_id], step.purpose or objective,
                            tool_by_name[step.operation]["function"]["parameters"],
                        )
                proposal = attach_arguments(
                    proposal,
                    arguments_by_step,
                    planner_catalog,
                )
                write_request_message(_plan_result_message(request_id, proposal, history, objective))
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
                arguments = argument_grounding._normalize_grounded_operation_arguments(
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
            elif kind == "computer.use.step":
                # Computer use (CONTRATO_VISTA_ACCION.md §4.4): one step over the
                # compact view, strict JSON at temperature 0, checked against the
                # view without the model before it reaches the shell.
                if llm is None:
                    raise RuntimeError("LLM no disponible")
                # lat-e5: while the mission lasts, the catalog's promotion
                # leaves the E5 worker to its steps (renewed by each step).
                hold_background = getattr(router, "hold_background", None)
                if callable(hold_background):
                    hold_background()
                view = message.get("view") if isinstance(message.get("view"), dict) else {}
                history = [
                    step for step in (message.get("history") or []) if isinstance(step, dict)
                ]
                decision = computer_use.decide_step(
                    llm,
                    objective=str(message.get("objective", "")),
                    goal=str(message.get("goal", "")),
                    application=(
                        str(message.get("application"))
                        if message.get("application") else None
                    ),
                    success_check=(
                        str(message.get("successCheck"))
                        if message.get("successCheck") else None
                    ),
                    view=view,
                    history=history,
                    budget_left=int(message.get("budgetLeft") or 0),
                    application_names=application_catalog,
                    subgoal=int(message.get("subgoal") or 0),
                    subgoal_count=int(message.get("subgoalCount") or 1),
                    # The shell's cache entry for the goal's label (§4.4.1).
                    label_translations=message.get("labelTranslations"),
                    # Ronda 20b, revisión 2: the check of the whole form the sub-goal belongs to.
                    form_check=(
                        str(message.get("formCheck"))
                        if message.get("formCheck") else None
                    ),
                    # The goal's place matched by meaning (goal v3 P1), within the step's encoder budget.
                    encoder=interactive_encoder,
                    # Estabilización, encargo C: a game's page by its identifier in the installed games.
                    game_catalog=game_catalog,
                )
                step_result = {
                    "type": computer_use.STEP_RESULT,
                    "id": request_id,
                    "operation": decision["operation"],
                    "arguments": decision["arguments"],
                    "reason": decision.get("reason", ""),
                    # Why there is no step (a «none»), or what the shell
                    # should wait for after this one.
                    "code": decision.get("code", ""),
                }
                # A click on a translated name, and the translation looked up
                # for the shell's cache (§4.4.1).
                for field in ("alias", "translation"):
                    if isinstance(decision.get(field), dict):
                        step_result[field] = decision[field]
                # Ronda 21: the goal's words the view was ranked by, for the
                # sub-goal's next look (input.visible.controls «wanted»).
                if isinstance(decision.get("wanted"), list) and decision["wanted"]:
                    step_result["wanted"] = decision["wanted"]
                # Where the step came from (model, rule, semantic) and what the
                # encoder was when the step asked it, for the shell's trace.
                for field in ("source", "encoder"):
                    if isinstance(decision.get(field), str) and decision[field]:
                        step_result[field] = decision[field]
                # The step's time in the encoder (lat-e5), so the shell's
                # model time is the model's.
                encoder_ms = decision.get("encoderMs")
                if isinstance(encoder_ms, int) and not isinstance(encoder_ms, bool) and encoder_ms > 0:
                    step_result["encoderMs"] = encoder_ms
                release_background = getattr(router, "release_background", None)
                if computer_use.ends_mission(
                    decision, int(message.get("subgoal") or 0), int(message.get("subgoalCount") or 1),
                ) and callable(release_background):
                    # The mission ends with this step (a «none», or «done» on
                    # its last sub-goal): the catalog's promotion goes on at
                    # once; a step the shell still asks (a redrawn screen, a
                    # refused citation) holds the worker again.
                    release_background()
                elif callable(hold_background):
                    # Counted from the step's end: the act and the next look
                    # come before the next step.
                    hold_background()
                write_request_message(step_result)
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
                arguments = _with_asked_listing(
                    operation, arguments, str(message.get("text", "")), tool["function"]["parameters"],
                )
                if operation == "mission.computer.use":
                    # Estabilización L: the sub-goal that is a declared limit, or whose place needs a device, is marked.
                    arguments = semantic_limits.with_declared_limits(arguments)
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
                if _count_read_beside_the_named_place(
                    situation, str(message.get("userText", "")), dialogue_state.understood(
                        str(message.get("userText", "")), situation,
                    ),
                ):
                    raise ValueError("count result does not bind the place the request named")
                # Only a verified result of the operation the last turn decided is kept for the next follow-up,
                # and a result of it answers the request as the turn understood it (tanda 7b «¿y el finde?»).
                dialogue_state.record(situation)
                user_text = dialogue_state.understood(str(message.get("userText", "")), situation)[:4096]
                facts = _with_listing_and_repetition_facts(
                    facts, situation, dialogue_state, user_text, str(message.get("userText", "")),
                )
                facts = _with_made_in_store(
                    facts, _situation_from_facts(facts), str(message.get("userText", "")), application_names,
                )
                facts = _with_unreceived_parts(facts, str(message.get("userText", "")), tool_by_name)
                told_situation = situation
                situation = _situation_from_facts(facts)
                observed = _merged_observed(situation)
                witnessed = _computer_use_witness_audit(message.get("id"), situation)
                if witnessed is not None:
                    turn_audit_module._append_turn_audit(witnessed)
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
                    text = _told_where_it_was_made(
                        text, situation, _decisive_request_language(text) == "en",
                    )
                    text = _with_send_offer(
                        text, dialogue_state, lambda request: _readers_send(
                            {"id": request_id, "text": request}, request, llm=llm,
                            planner_catalog=ready_planner_catalog(), encoder=interactive_encoder,
                            tool_by_name=tool_by_name, application_names=application_catalog, game_catalog=game_catalog,
                        ) is not None,
                    )
                    dialogue_state.told(told_situation, text)
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


def _report_internal_replay_failure(error: BaseException) -> None:
    """Keep a silent control replay observable without exposing request data."""

    try:
        sys.stderr.write(f"baxy_mind_control_replay_failure:{type(error).__name__}\n")
        sys.stderr.flush()
    except Exception:  # noqa: BLE001 - diagnostics cannot change control flow
        pass


def _prewarm_voice() -> threading.Thread | None:
    """Load the voice stack while the model warms, never inside the first turn.

    Tanda t4-r6 (2026-10-08): the shell's first ``voice.status`` arrived right
    after ``catalog.ready`` and spent 5.3 s importing the voice runtime (STT,
    VAD, wake word, audio devices) on the serial request lane, so the person's
    first message waited behind it. The import started here at process start
    overlaps the model warmup. A later ``voice.status`` never waits for it: it
    answers ``pending`` while the import runs and the shell reads it again
    (2026-10-08, v2-v3-04). The rest of the probe costs 0.03-0.08 s, so only
    the import is warmed. It opens no microphone and starts no speech.
    """

    return prewarm_voice_runtime()


def main() -> int:
    lifecycle = _SidecarLifecycle()
    primary_error: BaseException | None = None
    result: int | None = None
    completed = False
    if os.environ.get("BAXY_MIND_LLM_GGUF"):
        # The served product (a model is configured): warm the voice beside it.
        _prewarm_voice()
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
