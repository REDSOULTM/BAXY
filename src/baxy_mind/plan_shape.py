"""The shape of a plan: the catalog's prerequisites around the recognized effects, the semantic veto of inferred
steps, a retimed step, and the plan.result the shell parses.
"""

from __future__ import annotations

from datetime import timezone
from typing import Any

from . import argument_grounding
from . import cu_model_calls
from .semantic import dialogue as dialogue_slot
from .semantic.apps import names_the_window_in_front, present_state_condition
from .semantic import missions as semantic_missions
from .semantic import reading as semantic_reading
from .effect_intent import (
    ApplicationCatalogIndex,
    EffectIntent,
    GameCatalogIndex,
    operation_domain_is_grounded,
    resolve_explicit_effects,
)
from .planner import (
    MAX_SHORTLIST_OPERATIONS,
    PlanProposal,
    PlannerCatalog,
    PlannerContractError,
    PlannerTool,
    conditional_predecessors,
    guarding_predecessors,
    is_required_predecessor,
    required_predecessors,
    validate_json_schema_instance,
)
from .skill_registry import SkillRegistry
from .semantic.dialogue import _previous_user_request
from .semantic.arguments import _select_referenced_predecessor, closes_the_active_window, names_spotify
from .turn_history import _person_message
from .argument_grounding import _ground_explicit_arguments


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


def _the_plans_only_opening(
    operation: str,
    plan_operations: tuple[str, ...],
    objective: str,
    schema: dict[str, object],
    application_names: tuple[str, ...] = (),
    game_catalog: GameCatalogIndex = GameCatalogIndex(),
) -> dict[str, object] | None:
    """The application of a plan's only app.open, read from the whole order by the one resolver; None otherwise.

    v3-19 (pasada r15b): the decider planned app.open + system.process.list for «abre el adminsitrador de tareas y
    ordena los procesos por memoria»; no reader read that pair, so the step's purpose was the placeholder of
    ``_expand_effect_plan`` and the one resolver (``missions.opened_application``) never saw the name: BAXY asked which
    application. The plan's only opening is the one the order's open verb names, read from its slot up to the next
    clause; with two openings each step keeps its own clause (no guess between them).
    """

    if operation != "app.open" or plan_operations.count("app.open") != 1:
        return None
    return _ground_explicit_arguments(operation, objective, schema, application_names, game_catalog)


def _plan_condition_marks(kind: object, history: object, objective: str) -> dict[str, bool]:
    """Ronda 19 (revisión, MUSIC1675, CLOSE1371): the marks a plan.result carries about the request's conditions.
    «si tengo word abierto, ponelo a la izquierda» / «snap chrome to the right if it's open» / «sin abrirlo»: the plan's
    window read is the check of a condition on what is open now, so the shell never opens an absent application to
    satisfy it (``presentStateCondition``). The reading lives in semantic/apps.py; nothing is marked otherwise.
    Only a plan carries it (revisión 2): a clarify or conversation answer has no window read to condition, and the
    shell refuses the mark outside a plan, so «si tengo el chrome abierto, movelo» asking where keeps its question."""

    if kind != "plan":
        return {}
    if present_state_condition(_person_message(history, objective)) or present_state_condition(objective):
        return {"presentStateCondition": True}
    return {}


def _plan_result_message(request_id: object, proposal: PlanProposal, history: object, objective: str) -> dict:
    """The plan.result the shell parses (MindSidecarClient.ParsePlanResult): the proposal and, only on a plan, the
    marks about the request's conditions (``_plan_condition_marks``)."""

    return {
        "type": "plan.result",
        "id": request_id,
        **proposal.as_dict(),
        **_plan_condition_marks(proposal.kind, history, objective),
    }


def _retimed_step_arguments(
    operation: str, retimed: dialogue_slot.RetimedNotification, schema: dict[str, object],
) -> dict[str, object] | None:
    """M76: the arguments of one step of moving the notification just set, or None for another step."""

    if retimed.set_by == "reminder.create" and operation.startswith("notification."):
        # M173: a reminder of the store is in no Task Scheduler; notification.cancel.* never takes it.
        return None
    if operation == "notification.cancel.latest":
        arguments: dict[str, object] | None = {"kind": retimed.kind}
    elif operation == "reminder.resolve.exact" and retimed.set_by == "reminder.create":
        # M173: the reminder of the store just made, found by its exact title as verified, to be deleted after it.
        # r19b: and by the id reminder.create verified, when the catalog takes it, so others of its title never make
        # the move ambiguous.
        arguments = {"title": retimed.set_title}
        if retimed.set_id and "reminderId" in (schema.get("properties") or {}):
            arguments["reminderId"] = retimed.set_id
    elif operation == "reminder.create" and retimed.set_by == "reminder.create":
        # M173: made again with what it was for and the new moment.
        due = retimed.schedule_arguments["dueUtc"]
        read_at = retimed.read_at.astimezone(timezone.utc) if retimed.read_at is not None else None
        arguments = argument_grounding._normalize_grounded_operation_arguments(
            operation, {"dueUtc": due, "title": retimed.schedule_arguments["title"]}, due, now_utc=read_at,
        )
    elif operation == "notification.cancel.at" and retimed.cancel_at_request:
        # The clock is read as a cancellation reads it; the kind is the one verified (a reminder is not an alarm).
        arguments = _ground_explicit_arguments(operation, retimed.cancel_at_request, schema)
        arguments = {**arguments, "kind": retimed.kind} if arguments is not None else None
    elif operation == "notification.schedule":
        due = retimed.schedule_arguments["dueUtc"]
        read_at = retimed.read_at.astimezone(timezone.utc) if retimed.read_at is not None else None
        arguments = argument_grounding._normalize_grounded_operation_arguments(
            operation, dict(retimed.schedule_arguments), due, now_utc=read_at,
        )
    else:
        return None
    return arguments if arguments is not None and validate_json_schema_instance(arguments, schema) else None


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


def _plan_effects_read(
    objective: str,
    expected_operations: tuple[str, ...],
    available: tuple[str, ...],
    history: object,
    application_names: tuple[str, ...] | ApplicationCatalogIndex = (),
    game_catalog: GameCatalogIndex = GameCatalogIndex(),
) -> EffectIntent | None:
    """What the readers read in the objective of a plan the turn decided, for each step's clause; None when nothing."""

    found = resolve_explicit_effects(
        objective, available, application_names, game_catalog,
        previous_user_text=_previous_user_request(history if isinstance(history, list) else [], objective),
    )
    if found is None and len(expected_operations) > 1:
        # M174 (DEV-H v5c H-s116 «Ey, anótame en la lista del mercado plátano maduro, arepas de chócolo y queso costeño,
        # ¿sí?» → three task.create decided, then «¿Qué título le darías a esta lista…?»): the decision read the order
        # inside the address and the tag (the reading gate's utterance forms); each step's clause is read from that same
        # order, as the argument binder of one operation does (``_ground_explicit_arguments``).
        uttered = semantic_reading.utterance_form(
            objective, lambda clause: resolve_explicit_effects(clause, available, application_names, game_catalog),
        )
        found = uttered[1] if uttered is not None else None
    return found


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


def _mission_split_by_the_model(
    llm: Any,
    evidence: str,
    application_names: tuple[str, ...] | ApplicationCatalogIndex,
) -> dict[str, object] | None:
    """v3 ronda 5 (lectura M6, diseño 5): the chain of a request the deterministic segments leave with one segment of
    two or more order verbs, as the local model splits it (``cu_model_calls.split_request_clauses``) and the readers
    read it; only a split of the person's own words that keeps what was ordered (``semantic.missions.model_clauses_fit``)
    is used. None when the mission reader already reads the request, when no segment asks for it, or with no split."""

    if llm is None or not evidence:
        return None
    if semantic_missions.mission_request(evidence, application_names) is not None:
        return None
    if not semantic_missions.asks_for_a_model_split(evidence, application_names):
        return None
    clauses = cu_model_calls.split_request_clauses(llm, evidence)
    mission = semantic_missions.mission_from_model_clauses(evidence, clauses, application_names) if clauses else None
    return mission.arguments() if mission is not None else None
