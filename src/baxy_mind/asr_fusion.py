"""Fail-closed semantic selection between independent ASR hypotheses."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable
import unicodedata

from .effect_intent import (
    ApplicationCatalogIndex,
    GameCatalogIndex,
    compound_retrieval_clauses,
    conversation_only_content_request,
    resolve_explicit_clarification_intent,
    resolve_explicit_effects,
    unresolved_compound_contract,
)


@dataclass(frozen=True, slots=True)
class TranscriptSelection:
    text: str | None
    source: str
    reason: str

    @property
    def requires_clarification(self) -> bool:
        return self.text is None


def _effect_contract(
    text: str,
    available_operations: frozenset[str],
    application_names: Iterable[str] | ApplicationCatalogIndex,
    game_catalog: GameCatalogIndex,
):
    intent = resolve_explicit_effects(
        text,
        available_operations,
        application_names,
        game_catalog,
    )
    unresolved = unresolved_compound_contract(
        text,
        available_operations,
        application_names,
        game_catalog,
        resolved_intent=intent,
    )
    return intent, unresolved


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    return "".join(character for character in normalized if not unicodedata.combining(character))


def _exhaustive_report_language(text: str) -> str | None:
    folded = _fold(text)
    if (
        re.search(r"\bsin\s+omitir\s+ninguno\b", folded)
        and re.search(r"\brevisa\s+(?:en|in)\s+(?:este\s+)?orden\b", folded)
    ):
        return "es"
    if (
        re.search(r"\bwithout\s+skipping\s+(?:any|ninguno)\b", folded)
        and re.search(r"\b(?:inspect|revisa)\s+(?:in|en)\s+(?:this\s+)?order\b", folded)
    ):
        return "en"
    return None


def _single_clause_operation(
    clause: str,
    available_operations: frozenset[str],
    application_names: Iterable[str] | ApplicationCatalogIndex,
    game_catalog: GameCatalogIndex,
) -> str | None:
    intent, unresolved = _effect_contract(
        f"check {clause}",
        available_operations,
        application_names,
        game_catalog,
    )
    if intent is None or unresolved is not None or len(intent.operations) != 1:
        return None
    return intent.operations[0]


def _merge_exhaustive_report(
    first: str,
    second: str,
    available_operations: frozenset[str],
    application_names: Iterable[str] | ApplicationCatalogIndex,
    game_catalog: GameCatalogIndex,
) -> str | None:
    """Repair one missing ASR clause only through index-aligned catalogue evidence."""

    language = _exhaustive_report_language(first)
    if language is None or _exhaustive_report_language(second) != language:
        return None
    first_clauses = compound_retrieval_clauses(first)
    second_clauses = compound_retrieval_clauses(second)
    if not 2 <= len(first_clauses) <= 8 or not 2 <= len(second_clauses) <= 8:
        return None

    def annotated(clauses: tuple[str, ...]) -> list[tuple[str, str | None]]:
        return [
            (
                clause,
                _single_clause_operation(
                    clause,
                    available_operations,
                    application_names,
                    game_catalog,
                ),
            )
            for clause in clauses
        ]

    first_items = annotated(first_clauses)
    second_items = annotated(second_clauses)
    first_known = sum(operation is not None for _, operation in first_items)
    second_known = sum(operation is not None for _, operation in second_items)
    if (len(second_items), second_known) > (len(first_items), first_known):
        base, alternative = second_items, first_items
    else:
        base, alternative = first_items, second_items
    merged = list(base)
    replacements = 0
    for index, (_, alternative_operation) in enumerate(alternative):
        if index >= len(merged):
            if alternative_operation is not None:
                return None
            continue
        clause, operation = merged[index]
        if operation is not None and alternative_operation is not None:
            if operation != alternative_operation:
                return None
            continue
        if operation is None and alternative_operation is not None:
            merged[index] = alternative[index]
            replacements += 1
    operations = tuple(operation for _, operation in merged if operation is not None)
    if (
        replacements == 0
        or len(operations) != len(merged)
        or len(set(operations)) != len(operations)
    ):
        return None
    clauses = [clause for clause, _ in merged]
    if language == "es":
        candidate = (
            "sin omitir ninguno, mira en este orden: "
            + "; después, ".join(clauses)
            + ", devolviendo cada resultado por separado"
        )
    else:
        candidate = (
            "without skipping any, inspect in this order: "
            + "; then, ".join(clauses)
            + ", returning each result separately"
        )
    intent, unresolved = _effect_contract(
        candidate,
        available_operations,
        application_names,
        game_catalog,
    )
    if intent is None or unresolved is not None or intent.operations != operations:
        return None
    return candidate


def _terminal_status_effect(
    text: str,
    available_operations: frozenset[str],
    application_names: Iterable[str] | ApplicationCatalogIndex,
    game_catalog: GameCatalogIndex,
) -> tuple[str, str] | None:
    """Recover an explicit final status request without discarding another effect."""

    stripped = text.strip()
    boundaries = tuple(re.finditer(r"[.!?;]+\s+", stripped))
    if not boundaries:
        return None
    boundary = boundaries[-1]
    prefix = stripped[: boundary.start()].strip()
    candidate = stripped[boundary.end() :].strip().rstrip(".!?;").strip()
    if not prefix or not candidate:
        return None
    intent, unresolved = _effect_contract(
        candidate,
        available_operations,
        application_names,
        game_catalog,
    )
    if (
        intent is None
        or unresolved is not None
        or len(intent.operations) != 1
        or not intent.operations[0].endswith(".status")
    ):
        return None
    prefix_intent, prefix_unresolved = _effect_contract(
        prefix,
        available_operations,
        application_names,
        game_catalog,
    )
    if prefix_unresolved is not None:
        return None
    if prefix_intent is not None and prefix_intent.operations != intent.operations:
        return None
    return candidate, intent.operations[0]


def select_transcript(
    parakeet_text: str,
    whisper_text: str,
    available_operations: Iterable[str],
    application_names: Iterable[str] | ApplicationCatalogIndex = (),
    game_catalog: GameCatalogIndex = GameCatalogIndex(),
) -> TranscriptSelection:
    """Choose one transcript using semantic evidence, never evaluation labels.

    Faster-Whisper is the measured default. Parakeet wins only when it carries
    a complete effect or clarification contract that Whisper lost. A
    conversation-only reading outranks an effect to prevent quoted or
    hypothetical content from granting authority. Conflicting complete
    effects fail closed and require a fresh utterance.
    """

    parakeet = parakeet_text.strip()
    whisper = whisper_text.strip()
    if not parakeet and not whisper:
        return TranscriptSelection(None, "none", "both_empty")
    if not whisper:
        return TranscriptSelection(parakeet, "parakeet", "whisper_empty")
    if not parakeet:
        return TranscriptSelection(whisper, "whisper", "parakeet_empty")
    operations = frozenset(available_operations)
    if not operations:
        return TranscriptSelection(whisper, "whisper", "no_catalog_default")

    parakeet_conversation = conversation_only_content_request(parakeet)
    whisper_conversation = conversation_only_content_request(whisper)
    if parakeet_conversation or whisper_conversation:
        if whisper_conversation:
            return TranscriptSelection(
                whisper,
                "whisper",
                "conversation_safety",
            )
        return TranscriptSelection(
            parakeet,
            "parakeet",
            "conversation_safety",
        )

    parakeet_intent, parakeet_unresolved = _effect_contract(
        parakeet,
        operations,
        application_names,
        game_catalog,
    )
    whisper_intent, whisper_unresolved = _effect_contract(
        whisper,
        operations,
        application_names,
        game_catalog,
    )
    parakeet_complete = parakeet_intent is not None and parakeet_unresolved is None
    whisper_complete = whisper_intent is not None and whisper_unresolved is None
    if parakeet_complete and whisper_complete:
        if parakeet_intent.operations != whisper_intent.operations:
            return TranscriptSelection(None, "none", "effect_conflict")
        return TranscriptSelection(whisper, "whisper", "effect_consensus")
    if parakeet_complete:
        return TranscriptSelection(parakeet, "parakeet", "parakeet_complete_effect")
    if whisper_complete:
        return TranscriptSelection(whisper, "whisper", "whisper_complete_effect")

    parakeet_terminal = _terminal_status_effect(
        parakeet,
        operations,
        application_names,
        game_catalog,
    )
    whisper_terminal = _terminal_status_effect(
        whisper,
        operations,
        application_names,
        game_catalog,
    )
    if (
        parakeet_terminal is not None
        and whisper_terminal is not None
        and parakeet_terminal[1] == whisper_terminal[1]
    ):
        return TranscriptSelection(
            whisper_terminal[0],
            "fusion",
            "terminal_status_consensus",
        )

    parakeet_clarification = resolve_explicit_clarification_intent(
        parakeet,
        operations,
    )
    whisper_clarification = resolve_explicit_clarification_intent(
        whisper,
        operations,
    )
    if parakeet_clarification and whisper_clarification:
        if (
            parakeet_clarification.operations != whisper_clarification.operations
            or parakeet_clarification.missing_fields
            != whisper_clarification.missing_fields
        ):
            return TranscriptSelection(None, "none", "clarification_conflict")
        return TranscriptSelection(whisper, "whisper", "clarification_consensus")
    if parakeet_clarification:
        return TranscriptSelection(
            parakeet,
            "parakeet",
            "parakeet_clarification",
        )
    if whisper_clarification:
        return TranscriptSelection(
            whisper,
            "whisper",
            "whisper_clarification",
        )

    merged_report = _merge_exhaustive_report(
        parakeet,
        whisper,
        operations,
        application_names,
        game_catalog,
    )
    if merged_report is not None:
        return TranscriptSelection(merged_report, "fusion", "clause_union")

    def compound_coverage(contract: object) -> tuple[int, int]:
        if contract is None:
            return (0, 0)
        requirements = getattr(contract, "clause_requirements", ())
        recovered = sum(len(leaf) for _, leaf in requirements)
        return (recovered, len(requirements))

    parakeet_coverage = compound_coverage(parakeet_unresolved)
    whisper_coverage = compound_coverage(whisper_unresolved)
    if parakeet_coverage > whisper_coverage:
        return TranscriptSelection(parakeet, "parakeet", "compound_coverage")
    return TranscriptSelection(whisper, "whisper", "quality_default")


def select_transcript_with_pause_safe_redecode(
    parakeet_text: str,
    whisper_text: str,
    pause_safe_parakeet_text: str,
    pause_safe_whisper_text: str,
    available_operations: Iterable[str],
    application_names: Iterable[str] | ApplicationCatalogIndex = (),
    game_catalog: GameCatalogIndex = GameCatalogIndex(),
) -> TranscriptSelection:
    """Preserve the proven route unless a longer capture adds dual-ASR status proof."""

    baseline = select_transcript(
        parakeet_text,
        whisper_text,
        available_operations,
        application_names,
        game_catalog,
    )
    if baseline.requires_clarification or baseline.reason in {
        "conversation_safety",
        "clarification_consensus",
        "parakeet_clarification",
        "whisper_clarification",
    }:
        return baseline
    pause_safe = select_transcript(
        pause_safe_parakeet_text,
        pause_safe_whisper_text,
        available_operations,
        application_names,
        game_catalog,
    )
    if pause_safe.reason != "terminal_status_consensus":
        return baseline
    operations = frozenset(available_operations)
    baseline_intent, baseline_unresolved = _effect_contract(
        baseline.text or "",
        operations,
        application_names,
        game_catalog,
    )
    if baseline_intent is not None and baseline_unresolved is None:
        return baseline
    return TranscriptSelection(
        pause_safe.text,
        "fusion",
        "pause_safe_terminal_status_consensus",
    )
