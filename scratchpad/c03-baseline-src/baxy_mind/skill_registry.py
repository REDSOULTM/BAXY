"""Versioned procedural skills for BAXY's planner.

Skills are trusted, read-only guidance shipped with the product.  They may
explain how public primitives compose, but they never add operations, execute
effects, see private memory, or change risk/confirmation policy.
"""

from __future__ import annotations

from collections import Counter
import math
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

MAX_SKILL_BYTES = 32_768
MAX_SELECTED_SKILLS = 3
MAX_SKILL_PROMPT_CHARS = 12_000
_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_SCALAR_FIELDS = frozenset({"name", "description", "priority"})
_LIST_FIELDS = frozenset({"operations"})
_BM25_K1 = 1.2
_BM25_B = 0.75
_LEXICAL_MIN_WINNER_SHARE = 0.55


class SkillContractError(ValueError):
    """A shipped skill violates the closed planner boundary."""


@dataclass(frozen=True, slots=True)
class PlannerSkill:
    name: str
    description: str
    operations: tuple[str, ...]
    priority: int
    body: str
    source: str

    @property
    def retrieval_document(self) -> str:
        return f"{self.name}. {self.description}. {' '.join(self.operations)}"


Encoder = Callable[[Sequence[str]], Any]


class SkillRegistry:
    def __init__(
        self,
        skills: Iterable[PlannerSkill],
        public_operations: Iterable[str],
        encoder: Encoder | None = None,
    ):
        allowed = frozenset(public_operations)
        parsed = tuple(sorted(skills, key=lambda item: item.name))
        if len({item.name for item in parsed}) != len(parsed):
            raise SkillContractError("duplicate skill name")
        for skill in parsed:
            unknown = set(skill.operations) - allowed
            if unknown:
                raise SkillContractError(
                    f"skill {skill.name} references unknown operations: {sorted(unknown)}"
                )
            if any(name.startswith("memory.") for name in skill.operations):
                raise SkillContractError("private memory cannot enter planner skills")
        self._skills = parsed
        self._encoder = encoder
        self._documents = tuple(item.retrieval_document for item in parsed)
        self._vectors = (
            encoder(self._documents, prefix="passage")
            if encoder is not None and parsed
            else None
        )
        lexical_documents = self._documents
        self._lexical_term_counts = tuple(
            Counter(_token_sequence(document))
            for document in lexical_documents
        )
        self._average_lexical_document_length = (
            sum(sum(counts.values()) for counts in self._lexical_term_counts)
            / len(self._lexical_term_counts)
            if self._lexical_term_counts
            else 0.0
        )
        reference_documents = (
            *(
                f"{item.retrieval_document}. {item.body}"
                for item in parsed
            ),
            *(name.replace(".", " ") for name in sorted(allowed)),
        )
        reference_tokens = tuple(
            frozenset(_token_sequence(document))
            for document in reference_documents
        )
        document_frequency: Counter[str] = Counter(
            token
            for tokens in reference_tokens
            for token in tokens
        )
        document_count = len(reference_tokens)
        self._inverse_document_frequency = {
            token: math.log(
                1.0
                + (
                    document_count
                    - frequency
                    + 0.5
                )
                / (frequency + 0.5)
            )
            for token, frequency in document_frequency.items()
        }

    @classmethod
    def load_default(
        cls,
        public_operations: Iterable[str],
        encoder: Encoder | None = None,
    ) -> "SkillRegistry":
        root = Path(__file__).with_name("skills")
        skills = [parse_skill(path) for path in sorted(root.glob("*/SKILL.md"))]
        return cls(skills, public_operations, encoder)

    @property
    def skills(self) -> tuple[PlannerSkill, ...]:
        return self._skills

    def select(
        self,
        objective: str,
        shortlisted_operations: Iterable[str],
    ) -> tuple[PlannerSkill, ...]:
        visible = frozenset(shortlisted_operations)
        candidates = [skill for skill in self._skills if visible & set(skill.operations)]
        if not candidates:
            return ()
        semantic = self._semantic_scores(objective)
        lexical = self._lexical_scores(objective)
        visible_lexical = sorted(
            (
                (lexical.get(skill.name, 0.0), skill)
                for skill in candidates
                if lexical.get(skill.name, 0.0) > 0.0
            ),
            key=lambda item: (item[0], item[1].name),
            reverse=True,
        )
        lexical_candidates: list[PlannerSkill] = []
        if visible_lexical:
            best_score = visible_lexical[0][0]
            total_score = sum(score for score, _ in visible_lexical)
            if (
                total_score > 0.0
                and best_score / total_score >= _LEXICAL_MIN_WINNER_SHARE
            ):
                lexical_candidates = [visible_lexical[0][1]]
        # Prefer statistically discriminative surface evidence. Terms present
        # across many documents distribute their BM25 mass and cannot reach
        # the required winner share. If lexical evidence is ambiguous,
        # semantic retrieval remains a single fail-closed advisory fallback.
        if not lexical_candidates and not semantic:
            return ()
        candidates = lexical_candidates or candidates
        selection_limit = MAX_SELECTED_SKILLS if lexical_candidates else 1
        best_lexical = max(
            (lexical.get(item.name, 0.0) for item in candidates),
            default=0.0,
        )
        ranked = sorted(
            candidates,
            key=lambda item: (
                semantic.get(item.name, 0.0)
                + (
                    0.04 * lexical.get(item.name, 0.0) / best_lexical
                    if best_lexical > 0.0
                    else 0.0
                )
                + 0.005 * item.priority,
                item.name,
            ),
            reverse=True,
        )
        return tuple(ranked[:selection_limit])

    @staticmethod
    def compact_prompt(skills: Sequence[PlannerSkill]) -> str:
        chunks: list[str] = []
        used = 0
        for skill in skills:
            chunk = (
                f"SKILL {skill.name}\n"
                f"Operations: {', '.join(skill.operations)}\n"
                f"{skill.body.strip()}"
            )
            remaining = MAX_SKILL_PROMPT_CHARS - used
            if remaining <= 0:
                break
            chunk = chunk[:remaining]
            chunks.append(chunk)
            used += len(chunk)
        return "\n\n".join(chunks)

    def _semantic_scores(self, objective: str) -> dict[str, float]:
        if self._encoder is None or self._vectors is None:
            return {}
        try:
            query = self._encoder([objective])
            scores = query @ self._vectors.T
            row = scores[0]
            return {
                skill.name: float(row[index])
                for index, skill in enumerate(self._skills)
                if math.isfinite(float(row[index]))
            }
        except Exception:
            return {}

    def _lexical_scores(self, objective: str) -> dict[str, float]:
        """BM25 scores from corpus-derived inverse document frequency.

        IDF observes installed skill documents and the authenticated public
        operation vocabulary. No language-specific stopword or trigger list
        participates.
        """

        query_terms = {
            token
            for token in _token_sequence(objective)
            if token in self._inverse_document_frequency
        }
        if (
            not query_terms
            or self._average_lexical_document_length <= 0.0
        ):
            return {}
        scores: dict[str, float] = {}
        for skill, term_counts in zip(
            self._skills,
            self._lexical_term_counts,
            strict=True,
        ):
            document_length = sum(term_counts.values())
            normalization = _BM25_K1 * (
                1.0
                - _BM25_B
                + _BM25_B
                * document_length
                / self._average_lexical_document_length
            )
            score = sum(
                self._inverse_document_frequency[term]
                * (
                    term_counts[term]
                    * (_BM25_K1 + 1.0)
                    / (term_counts[term] + normalization)
                )
                for term in query_terms
                if term_counts.get(term, 0) > 0
            )
            if math.isfinite(score) and score > 0.0:
                scores[skill.name] = score
        return scores


def parse_skill(path: Path) -> PlannerSkill:
    data = path.read_bytes()
    if len(data) > MAX_SKILL_BYTES:
        raise SkillContractError(f"skill is too large: {path}")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SkillContractError(f"skill is not UTF-8: {path}") from exc
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        raise SkillContractError(f"skill has no closed frontmatter: {path}")
    frontmatter, body = text[4:].split("\n---\n", 1)
    scalar: dict[str, str] = {}
    operations: list[str] = []
    current_list = ""
    for raw_line in frontmatter.splitlines():
        line = raw_line.rstrip()
        if line.startswith("  - ") and current_list == "operations":
            operations.append(line[4:].strip())
            continue
        current_list = ""
        if ":" not in line:
            raise SkillContractError(f"invalid frontmatter line in {path}")
        key, value = (part.strip() for part in line.split(":", 1))
        if key not in _SCALAR_FIELDS | _LIST_FIELDS:
            raise SkillContractError(f"unknown frontmatter field in {path}: {key}")
        if key == "operations" and not value:
            current_list = key
        else:
            if key in scalar:
                raise SkillContractError(f"duplicate frontmatter field in {path}: {key}")
            scalar[key] = value
    name = scalar.get("name", "")
    description = scalar.get("description", "")
    if (
        _NAME.fullmatch(name) is None
        or len(name) > 64
        or path.parent.name != name
        or not description
        or len(description) > 1_024
        or not operations
        or not body.strip()
        or len(body.splitlines()) > 500
    ):
        raise SkillContractError(f"incomplete skill contract: {path}")
    if len(set(operations)) != len(operations):
        raise SkillContractError(f"duplicate operation in skill: {path}")
    try:
        priority = int(scalar.get("priority", "50"))
    except ValueError as exc:
        raise SkillContractError(f"invalid skill priority: {path}") from exc
    if not 0 <= priority <= 100:
        raise SkillContractError(f"skill priority out of bounds: {path}")
    return PlannerSkill(
        name=name,
        description=description,
        operations=tuple(operations),
        priority=priority,
        body=body.strip(),
        source=str(path),
    )


def _token_sequence(value: str) -> tuple[str, ...]:
    folded = unicodedata.normalize("NFKD", value.casefold())
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return tuple(
        token
        for token in re.findall(r"[a-z0-9]+", folded)
        if len(token) >= 3
    )


def _tokens(value: str) -> set[str]:
    return set(_token_sequence(value))
