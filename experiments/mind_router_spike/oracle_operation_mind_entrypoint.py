"""Development-only sidecar with a perfect R4 operation nominator.

Only the raw catalog-operation identity is injected.  Argument extraction,
domain grounding, relevance, conservation, clarification, presentation, and
every product veto remain the real implementation.  This module has no Core
or provider interface and is valid only under side-effect-free ``turn.decide``
probes.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable

import baxy_mind.__main__ as mind_main_module
import baxy_mind.family_classifier as family_module
import baxy_mind.llm as llm_module
from baxy_mind.__main__ import _explicit_response_language, main


ORACLE_ENV = "BAXY_EXPERIMENT_MTOP_OPERATION_ORACLE"
VERIFICATION_ENV = "BAXY_EXPERIMENT_MTOP_ORACLE_VERIFICATION"
ORACLE_SCHEMA = "baxy.mtop-r4-operation-oracle.development.v1"
MAX_ORACLE_BYTES = 2 * 1024 * 1024


def _load_oracle() -> dict[str, tuple[str, ...]]:
    path = Path(os.environ[ORACLE_ENV]).resolve(strict=True)
    if path.stat().st_size > MAX_ORACLE_BYTES:
        raise RuntimeError("the development operation oracle is unexpectedly large")
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload.get("cases") if isinstance(payload, dict) else None
    if (
        payload.get("schema") != ORACLE_SCHEMA
        or payload.get("scope")
        != "development_validation_only_mtop_test_remains_sealed"
        or payload.get("side_effect_free") is not True
        or not isinstance(cases, list)
        or len(cases) != 198
    ):
        raise RuntimeError("the development operation oracle contract is invalid")
    by_text: dict[str, tuple[str, ...]] = {}
    for case in cases:
        if not isinstance(case, dict):
            raise RuntimeError("the development operation oracle case is invalid")
        text = case.get("text")
        operations = case.get("intent_operations")
        if (
            not isinstance(text, str)
            or not isinstance(operations, list)
            or len(operations) > 1
            or any(not isinstance(value, str) for value in operations)
        ):
            raise RuntimeError("the development operation nomination is invalid")
        value = tuple(operations)
        previous = by_text.setdefault(text, value)
        if previous != value:
            raise RuntimeError("the operation oracle has an ambiguous request text")
    return by_text


_ORACLE = _load_oracle()
_ORACLE_VERIFICATION = os.environ.get(
    VERIFICATION_ENV,
    "grounding_required",
).strip()
if _ORACLE_VERIFICATION not in {"grounding_required", "recovered"}:
    raise RuntimeError("the development oracle verification mode is invalid")
_REAL_LLM_RUNTIME = llm_module.LlmRuntime
_REAL_NON_TARGET_LANGUAGE = mind_main_module.confident_non_target_language
_REAL_RESOLVE_CLARIFICATION = mind_main_module.resolve_explicit_clarification_intent
_REAL_RESOLVE_EFFECTS = mind_main_module.resolve_explicit_effects
_REAL_UNRESOLVED_COMPOUND = mind_main_module.unresolved_compound_contract
_REAL_KNOWN_UNSUPPORTED = mind_main_module.known_unsupported_effect_request
_REAL_SOCIAL = mind_main_module._explicit_social_turn_decision
_REAL_NONUNDERSTANDING = mind_main_module._explicit_nonunderstanding_turn_decision
_REAL_STABLE_NO_EFFECT = mind_main_module._explicit_stable_no_effect_turn_decision


def _is_measured(text: str) -> bool:
    return text in _ORACLE


def _oracle_non_target_language(text: str) -> str | None:
    if _is_measured(text):
        return None
    return _REAL_NON_TARGET_LANGUAGE(text)


def _oracle_resolve_clarification(
    text: str,
    available_operations: Iterable[str],
) -> Any:
    if _is_measured(text):
        return None
    return _REAL_RESOLVE_CLARIFICATION(text, available_operations)


def _oracle_resolve_effects(
    text: str,
    available_operations: Iterable[str],
    application_names: Iterable[str] = (),
    game_catalog: Iterable[tuple[str, str, str]] = (),
) -> Any:
    if _is_measured(text):
        return None
    return _REAL_RESOLVE_EFFECTS(
        text,
        available_operations,
        application_names,
        game_catalog,
    )


def _oracle_unresolved_compound(
    objective: str,
    *args: Any,
    **kwargs: Any,
) -> Any:
    if _is_measured(objective):
        return None
    return _REAL_UNRESOLVED_COMPOUND(objective, *args, **kwargs)


def _oracle_known_unsupported(
    objective: str,
    *args: Any,
    **kwargs: Any,
) -> bool:
    if _is_measured(objective):
        return False
    return bool(_REAL_KNOWN_UNSUPPORTED(objective, *args, **kwargs))


def _oracle_social(objective: str, history: object = None) -> Any:
    if _is_measured(objective):
        return None
    return _REAL_SOCIAL(objective, history)


def _oracle_nonunderstanding(objective: str, history: object = None) -> Any:
    if _is_measured(objective):
        return None
    return _REAL_NONUNDERSTANDING(objective, history)


def _oracle_stable_no_effect(objective: str, history: object = None) -> Any:
    if _is_measured(objective):
        return None
    return _REAL_STABLE_NO_EFFECT(objective, history)


class OracleFamilyClassifier:
    """Retrieve the exact authenticated family but grant no leaf authority."""

    def predict(
        self,
        text: str,
        available_families: Iterable[str],
    ) -> family_module.FamilyPrediction | None:
        operations = _ORACLE.get(text)
        if not operations:
            return None
        family = operations[0].split(".", 1)[0]
        if family not in set(available_families):
            raise RuntimeError("the oracle operation family is absent from the catalog")
        return family_module.FamilyPrediction(family=family, margin=float("inf"))


class OracleLlmRuntime(_REAL_LLM_RUNTIME):
    """Inject one raw operation identity; delegate every non-R4 request."""

    def decide_turn(
        self,
        text: str,
        candidates: list[dict[str, Any]],
        *,
        history: list[dict[str, Any]] | None = None,
        evidence: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        operations = _ORACLE.get(text)
        if operations is None:
            return super().decide_turn(
                text,
                candidates,
                history=history,
                evidence=evidence,
            )
        response_language = _explicit_response_language(text)
        if not operations:
            return {
                "mode": "conversation",
                "operation": None,
                "question": "",
                "conversation_kind": "unsupported",
                "effect_count": "zero",
                "effect_operations": [],
                "effect_verification": "not_applicable",
                "response_language": response_language,
                "intent_operations": [],
            }
        operation = operations[0]
        candidate_names = {
            str(candidate.get("name", "")) for candidate in candidates
        }
        if operation not in candidate_names:
            raise RuntimeError(
                "the exact-family shortlist omitted the oracle operation"
            )
        return {
            "mode": "action",
            "operation": operation,
            "question": "",
            "conversation_kind": "",
            "effect_count": "one",
            "effect_operations": [operation],
            "effect_verification": _ORACLE_VERIFICATION,
            "response_language": response_language,
            "intent_operations": [operation],
        }


family_module.FamilyClassifier = OracleFamilyClassifier
llm_module.LlmRuntime = OracleLlmRuntime
mind_main_module.confident_non_target_language = _oracle_non_target_language
mind_main_module.resolve_explicit_clarification_intent = (
    _oracle_resolve_clarification
)
mind_main_module.resolve_explicit_effects = _oracle_resolve_effects
mind_main_module.unresolved_compound_contract = _oracle_unresolved_compound
mind_main_module.known_unsupported_effect_request = _oracle_known_unsupported
mind_main_module._explicit_social_turn_decision = _oracle_social
mind_main_module._explicit_nonunderstanding_turn_decision = (
    _oracle_nonunderstanding
)
mind_main_module._explicit_stable_no_effect_turn_decision = (
    _oracle_stable_no_effect
)


if __name__ == "__main__":
    raise SystemExit(main())
