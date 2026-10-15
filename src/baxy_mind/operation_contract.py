"""The Core's contract of each operation in a turn, and what an operation a stage withheld becomes: done, asked
about, or dropped.
"""

from __future__ import annotations

from . import effect_intent
from .effect_intent import ApplicationCatalogIndex, build_application_catalog_index
from .native_selection import _native_selection_description
from .planner import PlannerCatalog
from .sidecar_budgets import TURN_DECIDE_RECOVERY_BUDGET_SECONDS
from .turn_recovery import _recovery_question_is_valid


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
