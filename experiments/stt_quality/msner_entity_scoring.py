"""Deterministic transcript/entity scoring for the MSNER evaluation corpus."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Callable, Sequence


# This reproduces the corpus token boundary contract: Unicode letters, digits,
# and contiguous punctuation are separate tokens.  It is deliberately not an
# ASR tokenizer and is used only after a candidate transcript already exists.
TOKEN_PATTERN = re.compile(r"[^\W\d_]+|\d+|[^\w\s_]+|_+", re.UNICODE)

_ENTITY_TYPES = (
    "cell_line",
    "character_name",
    "language",
    "disease",
    "event",
    "organization",
    "character",
    "origin",
    "other",
    "dish",
    "relationship",
    "artifact",
    "work_of_art",
    "facility",
    "product",
    "amenity",
    "rating",
    "actor",
    "date",
    "ratings_average",
    "quantity",
    "dna",
    "quote",
    "title",
    "song",
    "genre",
    "cuisine",
    "soundtrack",
    "ordinal_number",
    "protein",
    "collection",
    "money",
    "person",
    "project",
    "group",
    "review",
    "percent",
    "law",
    "director",
    "award",
    "chemical",
    "geopolitical_area",
    "rna",
    "restaurant",
    "location",
    "opinion",
    "cell_type",
    "trailer",
    "cardinal_number",
    "plot",
    "corporation",
    "time",
)
UNIFIED_ENTITY_LABELS = tuple(
    [*(f"B-{name}" for name in _ENTITY_TYPES), *(f"I-{name}" for name in _ENTITY_TYPES), "O"]
)


@dataclass(frozen=True)
class CorpusToken:
    text: str
    start: int
    end: int


@dataclass(frozen=True)
class EntitySpan:
    entity_type: str
    surface: str
    token_start: int
    token_end: int


def corpus_tokens(text: str) -> tuple[CorpusToken, ...]:
    """Return the corpus tokens together with exact character offsets."""

    return tuple(
        CorpusToken(match.group(0), match.start(), match.end())
        for match in TOKEN_PATTERN.finditer(text)
    )


def extract_entities(reference: str, label_ids: Sequence[int]) -> tuple[EntitySpan, ...]:
    """Reconstruct entity surfaces from the frozen BIO label sequence."""

    tokens = corpus_tokens(reference)
    if len(tokens) != len(label_ids):
        raise ValueError(
            f"msner_entity_token_label_mismatch:{len(tokens)}:{len(label_ids)}"
        )
    labels: list[str] = []
    for label_id in label_ids:
        if not isinstance(label_id, int) or not 0 <= label_id < len(UNIFIED_ENTITY_LABELS):
            raise ValueError(f"msner_entity_label_invalid:{label_id}")
        labels.append(UNIFIED_ENTITY_LABELS[label_id])

    entities: list[EntitySpan] = []
    index = 0
    while index < len(labels):
        label = labels[index]
        if label == "O":
            index += 1
            continue
        if not label.startswith("B-"):
            raise ValueError(f"msner_entity_bio_invalid:{index}:{label}")
        entity_type = label[2:]
        end = index + 1
        while end < len(labels) and labels[end] == f"I-{entity_type}":
            end += 1
        if end < len(labels) and labels[end].startswith("I-"):
            raise ValueError(f"msner_entity_bio_invalid:{end}:{labels[end]}")
        entities.append(
            EntitySpan(
                entity_type=entity_type,
                surface=reference[tokens[index].start : tokens[end - 1].end],
                token_start=index,
                token_end=end,
            )
        )
        index = end
    return tuple(entities)


def _aligned_reference_matches(
    reference: Sequence[str], hypothesis: Sequence[str]
) -> tuple[bool, ...]:
    rows = len(reference) + 1
    columns = len(hypothesis) + 1
    distances = [[0] * columns for _ in range(rows)]
    operations = [[""] * columns for _ in range(rows)]
    for index in range(1, rows):
        distances[index][0] = index
        operations[index][0] = "delete"
    for index in range(1, columns):
        distances[0][index] = index
        operations[0][index] = "insert"
    for ref_index in range(1, rows):
        for hyp_index in range(1, columns):
            substitution = distances[ref_index - 1][hyp_index - 1] + (
                reference[ref_index - 1] != hypothesis[hyp_index - 1]
            )
            deletion = distances[ref_index - 1][hyp_index] + 1
            insertion = distances[ref_index][hyp_index - 1] + 1
            best = min(substitution, deletion, insertion)
            distances[ref_index][hyp_index] = best
            if best == substitution:
                operations[ref_index][hyp_index] = (
                    "match"
                    if reference[ref_index - 1] == hypothesis[hyp_index - 1]
                    else "substitute"
                )
            elif best == deletion:
                operations[ref_index][hyp_index] = "delete"
            else:
                operations[ref_index][hyp_index] = "insert"

    matches = [False] * len(reference)
    ref_index = len(reference)
    hyp_index = len(hypothesis)
    while ref_index or hyp_index:
        operation = operations[ref_index][hyp_index]
        if operation in {"match", "substitute"}:
            matches[ref_index - 1] = operation == "match"
            ref_index -= 1
            hyp_index -= 1
        elif operation == "delete":
            ref_index -= 1
        elif operation == "insert":
            hyp_index -= 1
        else:
            raise RuntimeError("msner_entity_alignment_failed")
    return tuple(matches)


def score_entity_preservation(
    *,
    reference: str,
    label_ids: Sequence[int],
    hypothesis: str,
    normalize_tokens: Callable[[str], list[str]],
) -> dict[str, object]:
    """Measure entity phrase and token preservation without altering ASR output."""

    tokens = corpus_tokens(reference)
    entities = extract_entities(reference, label_ids)
    hypothesis_tokens = normalize_tokens(hypothesis)

    normalized_reference: list[str] = []
    normalized_entity_owner: list[int | None] = []
    entity_by_corpus_token: list[int | None] = [None] * len(tokens)
    for entity_index, entity in enumerate(entities):
        for token_index in range(entity.token_start, entity.token_end):
            entity_by_corpus_token[token_index] = entity_index
    for token_index, token in enumerate(tokens):
        normalized = normalize_tokens(token.text)
        normalized_reference.extend(normalized)
        normalized_entity_owner.extend(
            [entity_by_corpus_token[token_index]] * len(normalized)
        )
    matches = _aligned_reference_matches(normalized_reference, hypothesis_tokens)

    exact_matches: list[bool] = []
    used_hypothesis = [False] * len(hypothesis_tokens)
    for entity in entities:
        expected = normalize_tokens(entity.surface)
        found: int | None = None
        if expected:
            width = len(expected)
            for start in range(len(hypothesis_tokens) - width + 1):
                if (
                    hypothesis_tokens[start : start + width] == expected
                    and not any(used_hypothesis[start : start + width])
                ):
                    found = start
                    break
        exact_matches.append(found is not None)
        if found is not None:
            for index in range(found, found + len(expected)):
                used_hypothesis[index] = True

    per_type: dict[str, dict[str, int]] = {}
    for entity_index, entity in enumerate(entities):
        row = per_type.setdefault(
            entity.entity_type,
            {
                "entities": 0,
                "entitiesExactlyPreserved": 0,
                "entityTokens": 0,
                "entityTokensPreserved": 0,
            },
        )
        row["entities"] += 1
        row["entitiesExactlyPreserved"] += int(exact_matches[entity_index])
    for owner, matched in zip(normalized_entity_owner, matches, strict=True):
        if owner is None:
            continue
        row = per_type[entities[owner].entity_type]
        row["entityTokens"] += 1
        row["entityTokensPreserved"] += int(matched)

    entity_tokens = sum(owner is not None for owner in normalized_entity_owner)
    entity_tokens_preserved = sum(
        owner is not None and matched
        for owner, matched in zip(normalized_entity_owner, matches, strict=True)
    )
    return {
        "entities": len(entities),
        "entitiesExactlyPreserved": sum(exact_matches),
        "entityTokens": entity_tokens,
        "entityTokensPreserved": entity_tokens_preserved,
        "allEntitiesExactlyPreserved": all(exact_matches),
        "perType": per_type,
        "entityCommitments": [
            {
                "type": entity.entity_type,
                "surface": entity.surface,
                "exactlyPreserved": exact_matches[index],
            }
            for index, entity in enumerate(entities)
        ],
    }
