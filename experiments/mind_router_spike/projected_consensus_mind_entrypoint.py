"""Development-only product-first consensus with completeness projection.

The production deterministic recognizers retain first refusal.  Only turns
that reach the model-owned boundary receive a closed operation nomination.
The nomination has no execution authority: a candidate-free semantic guard
and an independent operation verifier must agree before an action is emitted.
Incomplete effects become model-authored clarification, while no-effect turns
remain conversations.  This entrypoint is restricted to side-effect-free
``turn.decide`` probes and is never the installed product entrypoint.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Iterable

import baxy_mind.__main__ as mind_main_module
import baxy_mind.family_classifier as family_module
import baxy_mind.llm as llm_module
from baxy_mind.__main__ import _explicit_response_language, main
from experiments.mind_router_spike import consensus_mind_entrypoint as base


_INCOMPLETE_COMPATIBILITY_PROMPT = (
    "Verifica si la unica operacion suministrada corresponde exactamente al "
    "tipo de efecto que la persona intenta pedir. Ignora solamente valores "
    "humanos esenciales que aun falten y que puedan obtenerse con una "
    "aclaracion; compatible=true si, al aportar esos valores, la operacion "
    "cubriria directamente todo el efecto. Usa false para otro dominio, otro "
    "objetivo, restricciones incompatibles, negacion, hipotesis o cobertura "
    "parcial. No inventes los valores ausentes ni propongas otra operacion."
)


def _closed_consensus(
    runtime: base._REAL_LLM_RUNTIME,
    text: str,
    candidates: list[dict[str, Any]],
) -> tuple[str | None, str]:
    """Return the frozen safe consensus nomination, never authority."""

    specialist = base._SPECIALIST.predict(text)
    baseline = specialist.operations[0]
    if baseline == base.NO_ACTION:
        return None, "specialist-no-action"
    top3 = tuple(
        operation
        for operation in specialist.operations[:3]
        if operation != base.NO_ACTION
    )
    selected = baseline
    gate = "specialist"
    if (
        base._family(baseline) == "notification"
        and "notification.cancel.latest" in top3
        and base._notification_cancel_contract(text)
    ):
        return "notification.cancel.latest", "notification-contract"

    full = base._FULL.predict(text)
    lexical = base._LEXICAL.predict(text)
    if (
        full.operations[0] == lexical.operations[0]
        and full.operations[0] in top3
        and base._family(full.operations[0]) == base._family(baseline)
    ):
        return full.operations[0], "full+lexical"

    if (
        lexical.operations[0] in top3
        and lexical.operations[0] != baseline
        and base._family(lexical.operations[0]) == base._family(baseline)
    ):
        by_name = {
            str(candidate.get("name", "")): candidate
            for candidate in candidates
        }
        shortlist = [by_name[name] for name in top3 if name in by_name]
        if lexical.operations[0] in by_name and len(shortlist) >= 2:
            native, no_match = base._select(
                runtime,
                text,
                shortlist,
                no_match_mode="sentinel",
                tool_choice="required",
            )
            if not no_match and native == (lexical.operations[0],):
                selected = lexical.operations[0]
                gate = "native+lexical"
    return selected, gate


def _tool_contract(
    operation: str,
    candidate: dict[str, Any],
) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": operation,
            "canonical_name": operation,
            "description": str(candidate.get("description") or "").strip(),
            "parameters": candidate.get("arguments_schema"),
        },
    }


def _clarification_question(
    runtime: base._REAL_LLM_RUNTIME,
    text: str,
    operation: str,
    candidate: dict[str, Any],
) -> str:
    tool = _tool_contract(operation, candidate)
    try:
        extraction = runtime.extract_direct_arguments(text, tool)
        if extraction.fallback_question:
            return extraction.fallback_question
    except ValueError:
        pass
    schema = candidate.get("arguments_schema")
    required = schema.get("required") if isinstance(schema, dict) else None
    fields = tuple(
        field
        for field in (required if isinstance(required, list) else ())
        if isinstance(field, str)
    )
    if not fields:
        fields = ("request_details",)
    return runtime.formulate_explicit_clarification_question(
        text,
        (operation,),
        fields,
    )


class ProjectedConsensusFamilyClassifier:
    """Close retrieval around the specialist without granting a leaf."""

    def predict(
        self,
        text: str,
        available_families: Iterable[str],
    ) -> family_module.FamilyPrediction | None:
        prediction = base._SPECIALIST.predict(text)
        operation = prediction.operations[0]
        if operation == base.NO_ACTION:
            return None
        family = base._family(operation)
        if family not in set(available_families):
            return None
        return family_module.FamilyPrediction(
            family=family,
            margin=prediction.margin,
        )


class ProjectedConsensusLlmRuntime(base._REAL_LLM_RUNTIME):
    """Project a verified nomination onto effect completeness."""

    def decide_turn(
        self,
        text: str,
        candidates: list[dict[str, Any]],
        *,
        history: list[dict[str, Any]] | None = None,
        evidence: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        selected, gate = _closed_consensus(self, text, candidates)
        response_language = _explicit_response_language(text)
        if selected is None:
            guard_state, effect_count = self._verify_semantic_effect_shape(text)
            if guard_state == "no_effect":
                return {
                    "mode": "conversation",
                    "operation": None,
                    "question": "",
                    "conversation_kind": "knowledge",
                    "effect_count": "zero",
                    "effect_operations": [],
                    "effect_verification": "not_applicable",
                    "response_language": response_language,
                    "intent_operations": [],
                    "diagnostic_consensus_gate": gate,
                }
            return super().decide_turn(
                text,
                candidates,
                history=history,
                evidence=evidence,
            )

        by_name = {
            str(candidate.get("name", "")): candidate
            for candidate in candidates
        }
        candidate = by_name.get(selected)
        if candidate is None:
            return super().decide_turn(
                text,
                candidates,
                history=history,
                evidence=evidence,
            )

        with ThreadPoolExecutor(
            max_workers=2,
            thread_name_prefix="baxy-projected-consensus",
        ) as executor:
            shape_future = executor.submit(
                self._verify_semantic_effect_shape,
                text,
            )
            compatible_future = executor.submit(
                self._operation_is_fully_compatible,
                text,
                selected,
                candidate,
            )
            guard_state, effect_count = shape_future.result()
            compatible = bool(compatible_future.result())

        if guard_state == "no_effect":
            return {
                "mode": "conversation",
                "operation": None,
                "question": "",
                "conversation_kind": "knowledge",
                "effect_count": "zero",
                "effect_operations": [],
                "effect_verification": "not_applicable",
                "response_language": response_language,
                "intent_operations": [],
                "diagnostic_consensus_gate": gate,
            }
        if guard_state == "not_complete" and effect_count == "one":
            incomplete_compatible = self._operation_is_fully_compatible(
                text,
                selected,
                candidate,
                _system_prompt=_INCOMPLETE_COMPATIBILITY_PROMPT,
            )
            if incomplete_compatible:
                return {
                    "mode": "clarify",
                    "operation": None,
                    "question": _clarification_question(
                        self,
                        text,
                        selected,
                        candidate,
                    ),
                    "conversation_kind": "",
                    "effect_count": "zero",
                    "effect_operations": [],
                    "effect_verification": "not_applicable",
                    "response_language": response_language,
                    "intent_operations": [selected],
                    "diagnostic_consensus_gate": gate,
                }
        if guard_state == "complete" and effect_count == "one" and compatible:
            return {
                "mode": "action",
                "operation": selected,
                "question": "",
                "conversation_kind": "",
                "effect_count": "one",
                "effect_operations": [selected],
                "effect_verification": "recovered",
                "response_language": response_language,
                "intent_operations": [selected],
                "diagnostic_consensus_gate": gate,
            }
        return super().decide_turn(
            text,
            candidates,
            history=history,
            evidence=evidence,
        )


# Importing the shared rankers also imports the previous experimental pulse.
# Restore every production-first recognizer, then install only this experiment.
mind_main_module.resolve_explicit_clarification_intent = (
    base._REAL_RESOLVE_CLARIFICATION
)
mind_main_module.resolve_explicit_effects = base._REAL_RESOLVE_EFFECTS
mind_main_module._explicit_stable_no_effect_turn_decision = (
    base._REAL_STABLE_NO_EFFECT
)
family_module.FamilyClassifier = ProjectedConsensusFamilyClassifier
llm_module.LlmRuntime = ProjectedConsensusLlmRuntime


if __name__ == "__main__":
    raise SystemExit(main())
