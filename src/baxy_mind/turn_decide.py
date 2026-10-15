"""One side-effect-free turn: the readers first, then the contextual decider and the gates, the early notice, and
the readers' warm-up before the first turn.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Callable

from . import turn_audit as turn_audit_module
from . import effect_intent
from .semantic import decider as semantic_decider
from .semantic import dialogue as dialogue_slot
from .semantic import messaging as semantic_messaging
from .semantic import reading as semantic_reading
from .semantic import surface as semantic_surface
from .semantic.patterns import clarification_awaits_decider, names_a_kind_of_music
from .semantic.web import search_has_typed_reads, typed_read_over_search
from .first_signal import PATH_MODEL, PATH_RECOGNIZER, PendingTurnSignal, should_emit_early, turn_signal_payload
from .effect_intent import (
    ApplicationCatalogIndex,
    EffectIntent,
    GameCatalogIndex,
    confident_non_target_language,
    conversation_only_content_request,
    effect_request_is_authoritative,
    known_unsupported_effect_request,
    resolve_application_catalog_app_id,
    resolve_explicit_clarification_intent,
    resolve_explicit_effects,
    unresolved_compound_contract,
    unsupported_effect_demonstration_request,
)
from .literal_answers import _literal_recall_reference
from .conversation_checks import visible_reply_is_only_questions
from .llm_transport import ChatCompletionCancellation
from .planner import PlannerCatalog, PlannerContractError
from .semantic.request import (
    INTENT_CAPABILITY,
    INTENT_CONTINUE_CONSTRAINT,
    INTENT_IDENTITY,
    INTENT_REFUSE,
    read_request,
)
from .semantic.reading import _leading_proved_clauses, _compound_partial_offer
from .semantic.guards import _unresolved_input_kind, _conversation_in_progress
from .semantic.dialogue import _history_has_pending_clarification, _previous_user_request
from .semantic.conversation import (
    _assistant_capability_aspiration,
    _closed_unsupported_request,
    _deictic_open_request,
    _general_factoid_prompt,
    _personal_checkin_statement,
    _standalone_deictic_request,
    _conversation_presentation_shape,
    random_draw_request,
    stable_no_effect_preempts,
)
from .semantic.arguments import watched_elsewhere
from .semantic.messaging import social_network_request
from .semantic.web import common_concept_definition, not_a_public_lookup
from .sidecar_budgets import DEICTIC_CLARIFICATION_CPU_BUDGET_SECONDS, TURN_DECIDE_RECOVERY_BUDGET_SECONDS
from .turn_audit import _READERS_WARMUP_THREAD, _turn_audit_stage, TURN_AUDIT_ENV
from .turn_history import _decisive_request_language, _explicit_response_language, _read_reply_language
from .argument_grounding import _reference_lookup, _window_query_reference_name
from .plan_shape import _shortlist_with_required_effects
from .direct_arguments import _with_session_alarm_selector
from .turn_recovery import _recovery_question_is_valid
from .operation_contract import (
    _catalog_answers_the_request,
    _withheld_invocation_operations,
    _withheld_operation_verdict,
)
from .turn_gates import (
    apply_compound_effect_conservation_veto,
    apply_conversation_effect_presentation,
    apply_explicit_effect_contract,
    apply_information_question_effect_veto,
    apply_non_effect_conversation_classification,
    apply_operation_domain_grounding_veto,
    apply_out_of_world_boundary,
    apply_turn_action_grounding_gate,
    apply_turn_action_relevance_veto,
    validate_turn_decision,
)
from .turn_decisions import (
    _ADMITS_NOT_KNOWING,
    _catalog_unavailable_turn_decision,
    _completes_previous_request,
    _conversation_reader_keeps_followup,
    _conversation_reply_arguments,
    _conversation_turn_decision,
    _explicit_nonunderstanding_turn_decision,
    _explicit_social_turn_decision,
    _explicit_stable_no_effect_turn_decision,
    _explicit_turn_decision,
    _explicit_unsupported_turn_decision,
    _operation_question_decision,
    _prepare_conversation_reply,
    _public_lookup_applies,
    _recovered_action_decision,
    _talk_act_turn_decision,
    _WRITTEN_CONTENT_SHAPES,
)
from .engine_handoff import _handed_to_the_engine, _self_contained_mission, _the_place_gone_to_again
from .send_offer import _send_said_result
from .turn_followups import (
    _correction_already_held,
    _moved_notification_result,
    _not_the_same_again,
    _own_notice_moved,
    _own_notification_cancellation,
    _rearm_in_context,
    _third_party_named,
)
from .context_decision import (
    _ATTEMPTED_AGAIN,
    _clock_read_request,
    _context_decided_result,
    _decider_catalog,
    _picks_a_named_file,
    _prepare_context_decision,
)


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

    previous = _previous_user_request(history if isinstance(history, list) else [], objective)

    def read(text: str) -> semantic_reading.Reading:
        return semantic_reading.read(
            text,
            available_operations=tuple(tool.name for tool in planner_catalog.tools),
            application_names=application_names,
            game_catalog=game_catalog,
            previous_user_text=previous,
        )

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
        elif restated and objective not in candidates:
            # M171 (DEV-I v5a I-w03-t2 «ugh ok, then al menos ponme el night light en el notebook pa no quemarme los
            # ojos» → decider «Activa la luz nocturna en el notebook.», limit → «Eso no lo hago»; the isolated decider
            # says limit too, so this corrects the decider, D58): a message the readers prove as an order, whose
            # openers («ugh ok, then al menos…») keep it from reading as a complete request, is re-read as said when
            # the decider's own restatement reads as that same order. The two readings agree on an operation of the
            # catalog, and the limit was the decider's error. A restatement the readers do not prove (an Uber, the
            # lights of the house, an alarm moved to the phone) or read as another operation leaves the limit.
            said, decided_reading = read(objective), read(restated)
            if (
                said.effects is not None
                and decided_reading.effects is not None
                and set(said.effects.operations) == set(decided_reading.effects.operations)
            ):
                candidates.append(objective)
        restated_reading = read(restated) if restated else None
        if (
            restated_reading is not None
            and restated_reading.effects is not None
            and tuple(restated_reading.effects.operations) == ("streaming.play.named",)
            and not watched_elsewhere(restated)
            and not watched_elsewhere(objective)
        ):
            # M179 (DEV-G v5a–v5d G-w03-t3 «no, la temporada 2, el primer episodio» after «pon Stranger Things en
            # Netflix» → the decider's «Pon la temporada 2 del primer episodio de Stranger Things en Netflix.», a
            # limit → «Eso no lo hago»; DEV-H v5a H-s074 the same with «para Sofía»): a restatement the readers prove
            # as playing a title on its service is the order the person gave; the season, the episode or who it is
            # for are details of it, never a limit. Only that operation: a restatement read as anything else (an alarm moved to the
            # phone, a pizza ordered from the nearest shop) keeps the limit, and so does a title put on the TV or
            # another device, which BAXY does not reach (``semantic.arguments.watched_elsewhere``).
            candidates.append(restated)
    canonical = None
    for candidate in dict.fromkeys(text for text in candidates if text):
        reading = read(candidate)
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
            turn_audit_module._append_turn_audit({
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


def _warm_turn_readers(
    planner_catalog: PlannerCatalog,
    tool_by_name: dict[str, dict],
    application_names: ApplicationCatalogIndex,
    game_catalog: GameCatalogIndex,
) -> None:
    """Ronda 29: the turn's readers read once before the first turn, not inside it.

    Measured without a model, the first ``_prepare_turn_result`` of a process cost 1 348 ms and the next ones 20–160 ms:
    the first compilation of the expressions of ``semantic`` and the lazy data loads. The test requests of
    ``data/readers_warmup.v1.json`` go through that same function with the configured catalog and no model (a reading
    that would ask it ends there), a conversation state of their own and no signal; the result is thrown away and
    nothing is audited (``_append_turn_audit``)."""

    path = Path(__file__).resolve().parent / "data" / "readers_warmup.v1.json"
    for text in json.loads(path.read_text(encoding="utf-8"))["requests"]:
        try:
            _prepare_turn_result(
                {"text": text, "history": [{"role": "user", "content": text}]},
                llm=object(),
                planner_catalog=planner_catalog,
                encoder=lambda _text: (),
                tool_by_name=tool_by_name,
                application_names=application_names,
                game_catalog=game_catalog,
                dialogue_state=dialogue_slot.DialogueState(),
            )
        except Exception:  # noqa: BLE001 - no model here: the reading that needs one is the turn's own
            continue


def _start_readers_warmup(*resources: Any) -> threading.Thread:
    """The warm-up runs beside the model's load (``catalog.configure`` waits for it): it never holds the request lane."""

    thread = threading.Thread(target=_warm_turn_readers, args=resources, name=_READERS_WARMUP_THREAD, daemon=True)
    thread.start()
    return thread


class _DeciderNotAsked(RuntimeError):
    """A turn the readers alone decide asked the model to decide or to word a question."""


class _WithoutTheDecider:
    """Estabilización B2 (revisión B2 H2): the model of a turn the readers alone decide; asking it to decide, chat,
    rewrite, clarify or word a question is refused, everything else is the model's."""

    def __init__(self, llm: Any) -> None:
        self._llm = llm

    def __getattr__(self, name: str) -> Any:
        if name in {"decide_in_context", "prepare_decision", "chat", "prepare_chat", "rewrite_in_context"} or (
            name.startswith(("clarify_", "formulate_"))
        ):
            def refused(*_args: Any, **_kwargs: Any) -> Any:
                raise _DeciderNotAsked(name)
            return refused
        return getattr(self._llm, name)


def _readers_send(message: dict[str, Any], request: str, *, llm: Any, **readers: Any) -> dict[str, Any] | None:
    """Estabilización B2: the send ``request`` names (``DialogueState.accepted_send``) as the readers alone decide
    it, the same recipient, client and words; None when they decide anything else or the model would be asked."""

    try:
        result = _decide_turn_result(
            {**message, "text": request, "history": [{"role": "user", "content": request}], "pendingObjective": None},
            llm=_WithoutTheDecider(llm), **readers,
        )
    except Exception:  # noqa: BLE001 - whatever the readers cannot decide alone is not sent
        return None
    said = semantic_messaging.message_request_named_client(request)
    if (
        result.get("effectOperations") != ["message.recipient.resolve", "message.send"]
        or said is None
        or semantic_messaging.message_request_named_client(str(result.get("objective") or request)) != said
    ):
        return None
    result.setdefault("objective", request)
    return result


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
        # Uso real 2026-10-07 «ok pero lo puedes buscar en google…»: that search, opened where the person names.
        or dialogue_state.searched_in_place(str(message.get("text", "")))
        if dialogue_state is not None
        else None
    )
    accepted_send = (
        dialogue_state.accepted_send(str(message.get("text", "")), message.get("history"))
        if dialogue_state is not None
        else None
    )
    if accepted_send is not None:
        # Estabilización B2: «sí» to «¿Le envío a Ron92 «…»?» after a draft is that send, in the person's words, as
        # the readers alone decide it; never the decider's (revisión B2 H2): when they do not, nothing is sent.
        return _readers_send(
            message, accepted_send, llm=llm, planner_catalog=planner_catalog, encoder=encoder,
            tool_by_name=tool_by_name, application_names=application_names, game_catalog=game_catalog,
        ) or _send_said_result(message, "not_sent")
    said = str(message.get("text", ""))
    if dialogue_state is not None and dialogue_state.yes_after_a_send(said, message.get("history")):
        # Encargo E (banco i1 c6): a yes after a send already done and told; nothing waits for it and nothing runs.
        return _send_said_result(message, "already_sent")
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
        # Ronda 19: a correction the last turn's verified result already holds is told, never done again.
        held = _correction_already_held(
            message, dialogue_state, llm,
            lambda operation: ((tool_by_name.get(operation) or {}).get("function") or {}).get("risk"),
        )
        if held is not None:
            return held
        again = dialogue_state.denied_state_again(str(message.get("text", ""))) if dialogue_state is not None else None
        if again is not None:
            # Encargo TZ-CAL (tanda z1 t3-c18 t3): a verified state the person denies and the screen does not hold is
            # the last mission done again on its request, never the reproach's words as the engine's goal.
            language = _read_reply_language(str(message.get("text", "")), message.get("history") or [])
            return _handed_to_the_engine(
                {"responseLanguage": language} if language in {"es", "en", "mixed"} else {},
                message, again, "denied_state_again",
            )
        moved = (
            dialogue_state.moved_notification_request(str(message.get("text", "")))
            if dialogue_state is not None
            else None
        )
        if moved is not None:
            # M102 (DEV-D v3z D-w18-t5 «wait no, make it una hora»): the notification the last turn set is moved
            # (cancelled and set again), never a second one beside it; the plan takes its arguments from the dialogue
            # state (``_retimed_step_arguments``).
            return _moved_notification_result(message, moved, dialogue_state.moving_operations())
        # M145: a cancellation at the clock of the notification this conversation set is of that one.
        # M173: a planned move of the notice the last turn set moves that one, by how it was set.
        # M179: the third party of a search («de ellos») is the one named in what this conversation last searched.
        # Uso real 2026-10-07: a correction decided as exactly the last turn is not done again (_not_the_same_again).
        attempted = dialogue_state.attempted_again(str(message.get("text", ""))) if dialogue_state is not None else None
        if attempted is not None:
            # Ronda 22: a correction naming the provider the failed last request already tried is that try again,
            # with its own arguments (``_contrastive_redecision``).
            message = {**message, _ATTEMPTED_AGAIN: attempted}
        return _not_the_same_again(_third_party_named(
            _own_notice_moved(
                _own_notification_cancellation(
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
                ),
                message,
                dialogue_state,
                tool_by_name,
            ),
            message,
            dialogue_state,
        ), message, dialogue_state, llm)
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
        turn_audit_module._append_turn_audit(
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
        # M164 (DEV-G v4y G-w40-t2 «abre el segundo» after «Encontré dos: «cotizacion_mudanza.pdf» en Descargas y
        # «cotizacion_mudanza_v2.pdf» en Documentos.» → «No abro el segundo.»): a pick among the files BAXY just listed
        # is no game missing from the library; the contextual decider reads it, and M151 opens the file picked.
        or _picks_a_named_file(objective, history)
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
    if explicit_intent is not None and "mission.computer.use" in explicit_intent.operations:
        # Computer use (owner 2026-10-07): a step inside an installed application is done on its screen, so a known
        # limit of BAXY's own («no tengo cronómetro») is not the answer when the person asks for it in an app that
        # has it (measured: «en el Reloj andá a Cronómetro» ended in a contract failure and a question).
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
    # Live 2026-10-07 (warm session «en el Reloj andá a Alarma» → «en el Reloj andá a Cronómetro» → «en Configuración
    # andá a Bluetooth…» → «en la calculadora calculá 9 por 8»): after the first turn every message went to the
    # contextual decider, which chose a lone click or the typed calculation and failed. A message that names an
    # installed application and reads alone as a step inside it needs no context: its own reading is the turn.
    self_contained_mission = (
        in_conversation and decided_beforehand is None
        and _self_contained_mission(objective, explicit_intent, application_names)
    )
    gone_back_to = (
        _the_place_gone_to_again(objective, history, available_operations, application_names)
        if self_contained_mission else None
    )
    if gone_back_to is not None:
        # Ronda 21 (pasada r18, v3-58 «busca cookies ahi en la configuracion» after «abre edge y anda a la
        # configuracion» searched Windows' Settings and ended «Listo»): an application the message names that is the
        # place the request before went to inside the conversation's application (``_in_the_place_gone_to``) makes
        # the message no self-contained one; its reading with the conversation is the turn, the one-turn order «en
        # <app>, <ir allá> y <paso>». Contracasos: a first message, or one after a request that went to no place,
        # stays as said (no reading comes back).
        return _context_decided_result(
            message, llm=llm, planner_catalog=planner_catalog, application_names=application_names,
            overheard=overheard,
            decided_beforehand=semantic_decider.ContextDecision(gone_back_to, "action", ("mission.computer.use",), ""),
        )
    if explicit_conversation_decision is None and (explicit_intent is None or (in_conversation and not self_contained_mission)):
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
    turn_audit_module._append_turn_audit(
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
    if (
        explicit_intent is not None
        and "mission.computer.use" in explicit_intent.operations
        and "mission.computer.use" in (decision.get("effect_operations") or [])
    ):
        # A mission the reader proved covers the whole request (its application frame and every clause, chained or
        # not); no clause is left for the conservation contract (measured: «en el Reloj andá a Cronómetro» kept
        # «cronómetro» as an unresolved timer and the turn fell to a bare click without the Clock).
        unresolved_compound_effects = None
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
                turn_audit_module._append_turn_audit(turn_audit)
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
    turn_audit_module._append_turn_audit(turn_audit)
    return result


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
