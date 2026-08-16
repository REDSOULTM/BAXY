"""Development-only consensus projected through the semantic effect guard.

Compared with the rejected compatibility pulse, this arm does not ask a
full-coverage verifier to judge an intentionally incomplete request.  The
three-head closed selector nominates one authenticated operation; the
candidate-free guard independently decides no-effect, incomplete, complete,
or multiple.  Product deterministic effects remain first, and every emitted
action still crosses grounding, risk, confirmation, Core authorization, and
provider verification.  This module is only for side-effect-free probes.
"""

from __future__ import annotations

from typing import Any, Iterable

import baxy_mind.__main__ as mind_main_module
import baxy_mind.family_classifier as family_module
import baxy_mind.llm as llm_module
from baxy_mind.__main__ import _explicit_response_language, main
from experiments.mind_router_spike import projected_consensus_mind_entrypoint as v1


base = v1.base


def _specialist_operation(text: str) -> str | None:
    operation = base._SPECIALIST.predict(text).operations[0]
    return None if operation == base.NO_ACTION else operation


def _projected_clarification(
    text: str,
    available_operations: Iterable[str],
) -> Any:
    """Preserve product-proven missing slots before learned disposition.

    Agreement on an operation family does not imply that its required literal
    arguments exist. The candidate-free semantic guard remains useful for
    model-owned turns, but it cannot promote an action after the closed product
    recognizer has already proved a missing slot (for example an alarm at a
    culturally variable meal time or a reminder with no title).
    """

    return base._REAL_RESOLVE_CLARIFICATION(
        text,
        available_operations,
    )


def _projected_stable_no_effect(
    objective: str,
    history: object = None,
) -> dict[str, object] | None:
    """Re-open only stable turns with a supported specialist nomination."""

    decision = base._REAL_STABLE_NO_EFFECT(objective, history)
    if decision is not None and _specialist_operation(objective) is not None:
        return None
    return decision


class ConsensusProjectionV2FamilyClassifier:
    """Close the primary family around the specialist nomination."""

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


class ConsensusProjectionV2LlmRuntime(base._REAL_LLM_RUNTIME):
    """Use consensus for identity and the guard for effect disposition."""

    def decide_turn(
        self,
        text: str,
        candidates: list[dict[str, Any]],
        *,
        history: list[dict[str, Any]] | None = None,
        evidence: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        selected, _gate = v1._closed_consensus(self, text, candidates)
        guard_state, effect_count = self._verify_semantic_effect_shape(text)
        response_language = _explicit_response_language(text)
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
            }

        by_name = {
            str(candidate.get("name", "")): candidate
            for candidate in candidates
        }
        candidate = by_name.get(selected) if selected is not None else None
        if candidate is not None and effect_count == "one":
            if guard_state == "not_complete":
                return {
                    "mode": "clarify",
                    "operation": None,
                    "question": v1._clarification_question(
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
                }
            if guard_state == "complete":
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
                }
        return super().decide_turn(
            text,
            candidates,
            history=history,
            evidence=evidence,
        )


mind_main_module.resolve_explicit_clarification_intent = (
    _projected_clarification
)
mind_main_module.resolve_explicit_effects = base._REAL_RESOLVE_EFFECTS
mind_main_module._explicit_stable_no_effect_turn_decision = (
    _projected_stable_no_effect
)
family_module.FamilyClassifier = ConsensusProjectionV2FamilyClassifier
llm_module.LlmRuntime = ConsensusProjectionV2LlmRuntime


if __name__ == "__main__":
    raise SystemExit(main())
