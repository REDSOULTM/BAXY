"""The reading every pattern reader returns (EffectIntent) and the helpers that append and negate one. Moved from effect_intent (Fase 3.5).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from .grammar import _fold, _has, _negative_state_question_body


@dataclass(frozen=True, slots=True)
class EffectIntent:
    operations: tuple[str, ...]
    evidence: tuple[str, ...] = ()

    @property
    def kind(self) -> str:
        return "action" if len(self.operations) == 1 else "plan"


def _entity_key(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", _fold(value)))


def _is_negated_match(text: str, found: re.Match[str]) -> bool:
    """Treat a nearby clause-local negation as a veto, never as an effect."""

    state_question = _negative_state_question_body(text)
    if state_question is not None:
        # Keep character offsets: the matched observation belongs to the
        # original evidence, and any later prohibition remains visible.
        text = " " * (len(text) - len(state_question)) + state_question
    prefix = text[max(0, found.start() - 80) : found.start()]
    boundary = max(
        prefix.rfind(","),
        prefix.rfind(";"),
        prefix.rfind("."),
        prefix.rfind("?"),
        prefix.rfind("!"),
        prefix.rfind(":"),
    )
    clause_prefix = prefix[boundary + 1 :]
    return _has(
        clause_prefix,
        (
            r"(?:\bno\b|\bnunca\b|\bjamas\b|\bnever\b|"
            r"\bdon'?t\b|\bdo\s+not\b|\bsin\b|\bwithout\b)"
            r"(?:\s+[a-z0-9_-]+){0,4}\s*$"
        ),
    )


def _append(
    matches: list[tuple[int, int, str]],
    text: str,
    operation: str,
    pattern: str,
    *,
    priority: int = 0,
) -> bool:
    for found in re.finditer(pattern, text, re.IGNORECASE):
        if _is_negated_match(text, found):
            continue
        matches.append((found.start(), priority, operation))
        return True
    return False


def _append_all(
    matches: list[tuple[int, int, str]],
    text: str,
    operation: str,
    pattern: str,
    *,
    priority: int = 0,
) -> int:
    """Append each distinct, non-negated verb/object occurrence in order."""

    count = 0
    for found in re.finditer(pattern, text, re.IGNORECASE):
        if _is_negated_match(text, found):
            continue
        matches.append((found.start(), priority, operation))
        count += 1
    return count
