"""The gates and vetoes a turn decision passes before the shell sees it: its contract, literal grounding, relevance,
domain, compound conservation and the conversation's presentation.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from . import effect_intent
from .semantic.web import asks_for_information
from .effect_intent import (
    ApplicationCatalogIndex,
    CompoundEffectContract,
    EffectIntent,
    GameCatalogIndex,
    confident_non_target_language,
    conversation_only_content_request,
    effect_request_is_authoritative,
    operation_domain_is_grounded,
    resolve_application_catalog_app_id,
    resolve_game_catalog_app_id,
    reassurance_statement,
    unsupported_effect_demonstration_request,
    unsupported_live_machine_query,
    visual_content_request,
)
from .planner import PlannerCatalog, PlannerContractError, required_predecessors
from .semantic.request import (
    INTENT_CAPABILITY,
    INTENT_CONTINUE_CONSTRAINT,
    INTENT_IDENTITY,
    INTENT_REFUSE,
    is_elliptical_followup,
    read_request,
)
from .semantic.dialogue import _history_has_pending_clarification, _previous_user_request
from .semantic.conversation import (
    _current_public_role_question,
    _reads_as_an_observation,
    first_person_observation,
    names_a_question_word,
)
from .semantic.messaging import chat_message_dispatch
from .sidecar_budgets import TURN_DECIDE_RECOVERY_BUDGET_SECONDS
from .argument_grounding import _ground_explicit_arguments, _stated_argument_fields, normalize_objective_arguments
from .turn_recovery import _recovery_question_is_valid
from .operation_contract import _turn_operation_contract


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
