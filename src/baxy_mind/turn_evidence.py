"""Evidencia semántica local para la política de turnos.

El corpus histórico nunca se consulta como una lista de frases ni concede
autoridad. Se filtra de forma conservadora, se vectoriza localmente con el
encoder ya residente y sólo aporta unos pocos ejemplos diversos al LLM que
decide el turno. La ejecución continúa detrás de schemas, riesgo,
confirmaciones y el core.

El módulo también expone un export reproducible por misión para entrenar o
evaluar un router futuro. No entrena pesos ni hace aprendizaje en vivo.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import threading
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, ClassVar, Iterable, Sequence

import numpy as np

from .turn_probe import (
    OneSidedTurnEvidencePolicy,
    summarize_conversation_neighbors,
)
from .turn_evidence_contracts import (
    ABSTENTION_POLICY_SCHEMA_VERSION,
    EVIDENCE_RECORD_SCHEMA_VERSION,
    SCHEMA_VERSION,
    TRAINING_SCHEMA_VERSION,
)


DEFAULT_ENCODER_IDENTITY = (
    "intfloat/multilingual-e5-small|query-prefix|normalize=true|dimensions=384"
)
CORPUS_ENVIRONMENT_VARIABLE = "BAXY_MIND_TURN_CORPUS"
CACHE_ENVIRONMENT_VARIABLE = "BAXY_MIND_TURN_EVIDENCE_CACHE"
POLICY_ENVIRONMENT_VARIABLE = "BAXY_MIND_TURN_EVIDENCE_POLICY"
DISABLE_EVIDENCE_ENVIRONMENT_VARIABLE = "BAXY_MIND_TURN_EVIDENCE_DISABLED"
MAX_CORPUS_BYTES = 160 * 1024 * 1024
MAX_POLICY_BYTES = 64 * 1024
MAX_EVIDENCE_TEXT_CHARS = 384
MAX_RETRIEVED_EVIDENCE = 4
MAX_CANDIDATE_FAMILIES = 12
DEFAULT_CANDIDATE_NEIGHBORS = 31
ENCODER_READY_TIMEOUT_SECONDS = 180
_ACTIONABLE_MODES = frozenset({"action", "plan"})
_LIVE_CLASSES = frozenset(
    {
        "conversation_question",
        "feedback_failure",
        "no_action_constraint",
        "user_mission",
    }
)

Encoder = Callable[[Sequence[str]], Any]
CancellationProbe = Callable[[], bool]


class _TurnEvidenceBuildCancelled(RuntimeError):
    """Internal cooperative cancellation; never exposed through diagnostics."""


def _raise_if_build_cancelled(is_cancelled: CancellationProbe | None) -> None:
    if is_cancelled is not None and is_cancelled():
        raise _TurnEvidenceBuildCancelled("turn evidence build cancelled")


@dataclass(frozen=True, slots=True)
class TurnEvidenceRecord:
    """A screened, non-authoritative local observation."""

    text: str
    mode: str
    families: tuple[str, ...]
    mission_id: str
    source_id: str
    split: str | None = None
    dataset: str = "BAXY historical evidence (privacy-screened)"
    license: str = "private-local"

    def prompt_card(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "families": list(self.families),
            "example": self.text[:MAX_EVIDENCE_TEXT_CHARS],
        }


@dataclass(frozen=True, slots=True)
class CorpusEvidenceReport:
    source_sha256: str
    source_rows: int
    accepted_rows: int
    excluded_private: int
    excluded_noncanonical: int
    excluded_ambiguous: int
    excluded_out_of_scope: int


@dataclass(frozen=True, slots=True)
class TurnEvidenceMatch:
    """One scored observation returned for diagnostics or prompt retrieval."""

    record: TurnEvidenceRecord
    score: float
    candidate_family_match: bool

    def prompt_card(self) -> dict[str, Any]:
        # Literal corpus text stays outside the generator prompt. The encoder
        # still retrieves by that text, while the LLM receives only advisory
        # aggregate-ready labels and bounded similarity diagnostics.
        return {
            "mode": self.record.mode,
            "families": list(self.record.families),
            "score": round(self.score, 6),
            "candidate_family_match": self.candidate_family_match,
        }


@dataclass(frozen=True, slots=True)
class TurnEvidenceConfidence:
    """Signals used only to decide whether advisory evidence is shown."""

    neighbor_count: int
    top1_score: float
    score_margin: float
    predicted_mode: str
    mode_agreement: float
    mode_entropy: float
    predicted_family: str
    family_agreement: float
    family_entropy: float

    def __post_init__(self) -> None:
        if self.neighbor_count < 0:
            raise ValueError("neighbor_count inválido")
        if self.predicted_mode not in {
            "",
            "conversation",
            "clarify",
            "action",
            "plan",
        }:
            raise ValueError("predicted_mode inválido")
        for name in (
            "top1_score",
            "score_margin",
            "mode_agreement",
            "mode_entropy",
            "family_agreement",
            "family_entropy",
        ):
            if not math.isfinite(float(getattr(self, name))):
                raise ValueError(f"{name} debe ser finito")
        for name in (
            "mode_agreement",
            "mode_entropy",
            "family_agreement",
            "family_entropy",
        ):
            if not 0.0 <= float(getattr(self, name)) <= 1.0:
                raise ValueError(f"{name} fuera de rango")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TurnEvidenceConfidence":
        required = {
            "neighbor_count",
            "top1_score",
            "score_margin",
            "predicted_mode",
            "mode_agreement",
            "mode_entropy",
            "predicted_family",
            "family_agreement",
            "family_entropy",
        }
        if set(value) != required:
            raise ValueError("señales de confianza incompletas")
        return cls(
            neighbor_count=int(value["neighbor_count"]),
            top1_score=float(value["top1_score"]),
            score_margin=float(value["score_margin"]),
            predicted_mode=str(value["predicted_mode"]),
            mode_agreement=float(value["mode_agreement"]),
            mode_entropy=float(value["mode_entropy"]),
            predicted_family=str(value["predicted_family"]),
            family_agreement=float(value["family_agreement"]),
            family_entropy=float(value["family_entropy"]),
        )


@dataclass(frozen=True, slots=True)
class TurnEvidenceThresholds:
    """Monotone confidence requirements learned outside the runtime."""

    minimum_top1_score: float
    minimum_score_margin: float
    minimum_mode_agreement: float
    maximum_mode_entropy: float
    minimum_family_agreement: float
    maximum_family_entropy: float

    def __post_init__(self) -> None:
        for name in (
            "minimum_top1_score",
            "minimum_score_margin",
            "minimum_mode_agreement",
            "maximum_mode_entropy",
            "minimum_family_agreement",
            "maximum_family_entropy",
        ):
            if not math.isfinite(float(getattr(self, name))):
                raise ValueError(f"{name} debe ser finito")
        if not -1.0 <= self.minimum_top1_score <= 1.0:
            raise ValueError("minimum_top1_score fuera de rango")
        if not 0.0 <= self.minimum_score_margin <= 2.0:
            raise ValueError("minimum_score_margin fuera de rango")
        for name in (
            "minimum_mode_agreement",
            "maximum_mode_entropy",
            "minimum_family_agreement",
            "maximum_family_entropy",
        ):
            if not 0.0 <= float(getattr(self, name)) <= 1.0:
                raise ValueError(f"{name} fuera de rango")

    @classmethod
    def permissive(cls) -> "TurnEvidenceThresholds":
        return cls(-1.0, 0.0, 0.0, 1.0, 0.0, 1.0)

    def accepts(self, confidence: TurnEvidenceConfidence) -> bool:
        return (
            confidence.top1_score >= self.minimum_top1_score
            and confidence.score_margin >= self.minimum_score_margin
            and confidence.mode_agreement >= self.minimum_mode_agreement
            and confidence.mode_entropy <= self.maximum_mode_entropy
            and confidence.family_agreement >= self.minimum_family_agreement
            and confidence.family_entropy <= self.maximum_family_entropy
        )

    def to_dict(self) -> dict[str, float]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TurnEvidenceThresholds":
        required = {
            "minimum_top1_score",
            "minimum_score_margin",
            "minimum_mode_agreement",
            "maximum_mode_entropy",
            "minimum_family_agreement",
            "maximum_family_entropy",
        }
        if set(value) != required:
            raise ValueError("perfil de umbrales incompleto")
        return cls(**{name: float(value[name]) for name in required})


@dataclass(frozen=True, slots=True)
class TurnEvidenceAbstentionPolicy:
    """A corpus/encoder-bound gate; it never chooses an operation or mode."""

    SCHEMA: ClassVar[str] = ABSTENTION_POLICY_SCHEMA_VERSION

    runtime_source_sha256: str
    encoder_identity: str
    neighbors: int
    actionable: TurnEvidenceThresholds
    conversational: TurnEvidenceThresholds
    calibration_fingerprint: str
    calibration_rows: int

    def __post_init__(self) -> None:
        if (
            len(self.runtime_source_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.runtime_source_sha256
            )
        ):
            raise ValueError("runtime_source_sha256 inválido")
        if not self.encoder_identity or len(self.encoder_identity) > 512:
            raise ValueError("encoder_identity inválido")
        if not 2 <= self.neighbors <= 32:
            raise ValueError("neighbors fuera de rango")
        if (
            not self.calibration_fingerprint
            or len(self.calibration_fingerprint) > 128
        ):
            raise ValueError("calibration_fingerprint inválido")
        if self.calibration_rows < 0:
            raise ValueError("calibration_rows inválido")

    @classmethod
    def permissive(
        cls,
        *,
        runtime_source_sha256: str,
        encoder_identity: str,
        neighbors: int,
        calibration_fingerprint: str,
        calibration_rows: int,
    ) -> "TurnEvidenceAbstentionPolicy":
        profile = TurnEvidenceThresholds.permissive()
        return cls(
            runtime_source_sha256=runtime_source_sha256,
            encoder_identity=encoder_identity,
            neighbors=neighbors,
            actionable=profile,
            conversational=profile,
            calibration_fingerprint=calibration_fingerprint,
            calibration_rows=calibration_rows,
        )

    def thresholds_for(
        self,
        confidence: TurnEvidenceConfidence,
    ) -> TurnEvidenceThresholds:
        return (
            self.actionable
            if confidence.predicted_mode in _ACTIONABLE_MODES
            else self.conversational
        )

    def accepts(self, confidence: TurnEvidenceConfidence) -> bool:
        return (
            confidence.neighbor_count >= self.neighbors
            and self.thresholds_for(confidence).accepts(confidence)
        )

    def is_compatible(
        self,
        *,
        source_sha256: str,
        encoder_identity: str,
    ) -> bool:
        return (
            self.runtime_source_sha256 == source_sha256
            and self.encoder_identity == encoder_identity
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "runtime_source_sha256": self.runtime_source_sha256,
            "encoder_identity": self.encoder_identity,
            "neighbors": self.neighbors,
            "actionable": self.actionable.to_dict(),
            "conversational": self.conversational.to_dict(),
            "calibration": {
                "fingerprint_sha256": self.calibration_fingerprint,
                "rows": self.calibration_rows,
                "fit_split": "validation",
            },
            "authority": "advisory_prompt_evidence_only",
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TurnEvidenceAbstentionPolicy":
        if value.get("schema") != cls.SCHEMA:
            raise ValueError("schema de política de abstención incompatible")
        calibration = value.get("calibration")
        actionable = value.get("actionable")
        conversational = value.get("conversational")
        if (
            not isinstance(calibration, dict)
            or calibration.get("fit_split") != "validation"
            or not isinstance(actionable, dict)
            or not isinstance(conversational, dict)
            or value.get("authority") != "advisory_prompt_evidence_only"
        ):
            raise ValueError("política de abstención inválida")
        return cls(
            runtime_source_sha256=str(value.get("runtime_source_sha256") or ""),
            encoder_identity=str(value.get("encoder_identity") or ""),
            neighbors=int(value.get("neighbors") or 0),
            actionable=TurnEvidenceThresholds.from_dict(actionable),
            conversational=TurnEvidenceThresholds.from_dict(conversational),
            calibration_fingerprint=str(
                calibration.get("fingerprint_sha256") or ""
            ),
            calibration_rows=int(calibration.get("rows") or 0),
        )


def _normalized_entropy(votes: dict[str, float]) -> float:
    positive = [float(value) for value in votes.values() if value > 0.0]
    if len(positive) <= 1:
        return 0.0
    total = sum(positive)
    entropy = -sum(
        (value / total) * math.log(value / total) for value in positive
    )
    return min(1.0, max(0.0, entropy / math.log(len(positive))))


def _vote_summary(votes: dict[str, float]) -> tuple[str, float, float]:
    if not votes:
        return "", 0.0, 1.0
    winner = max(votes, key=lambda label: (votes[label], label))
    total = sum(votes.values())
    agreement = votes[winner] / total if total > 0.0 else 0.0
    return winner, agreement, _normalized_entropy(votes)


def summarize_match_confidence(
    matches: Sequence[TurnEvidenceMatch],
) -> TurnEvidenceConfidence:
    """Summarize semantic confidence without producing an authoritative route."""

    if not matches:
        return TurnEvidenceConfidence(
            0,
            -1.0,
            0.0,
            "",
            0.0,
            1.0,
            "",
            0.0,
            1.0,
        )
    ranked = sorted(matches, key=lambda match: match.score, reverse=True)
    scores = [float(match.score) for match in ranked]
    mode_votes: dict[str, float] = {}
    family_votes: dict[str, float] = {}
    for match in ranked:
        weight = max(0.0, float(match.score)) + 1e-9
        mode_votes[match.record.mode] = (
            mode_votes.get(match.record.mode, 0.0) + weight
        )
        labels = match.record.families or ("",)
        label_weight = weight / len(labels)
        for family in labels:
            family_votes[family] = family_votes.get(family, 0.0) + label_weight
    predicted_mode, mode_agreement, mode_entropy = _vote_summary(mode_votes)
    predicted_family, family_agreement, family_entropy = _vote_summary(
        family_votes
    )
    return TurnEvidenceConfidence(
        neighbor_count=len(ranked),
        top1_score=scores[0],
        score_margin=(scores[0] - scores[1] if len(scores) >= 2 else 0.0),
        predicted_mode=predicted_mode,
        mode_agreement=mode_agreement,
        mode_entropy=mode_entropy,
        predicted_family=predicted_family,
        family_agreement=family_agreement,
        family_entropy=family_entropy,
    )


def load_abstention_policy(
    path: Path | None = None,
) -> OneSidedTurnEvidencePolicy | None:
    configured = os.environ.get(POLICY_ENVIRONMENT_VARIABLE, "").strip()
    candidate = (
        Path(configured).expanduser()
        if configured
        else (
            path
            or Path(__file__).resolve().parent
            / "data"
            / "turn_evidence_abstention_policy.v1.json"
        )
    )
    if not candidate.is_file():
        return None
    if candidate.stat().st_size > MAX_POLICY_BYTES:
        raise ValueError("la política de abstención supera el límite local")
    try:
        raw = json.loads(candidate.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError("la política de abstención contiene JSON inválido") from error
    if not isinstance(raw, dict):
        raise ValueError("la política de abstención no es un objeto")
    return OneSidedTurnEvidencePolicy.from_dict(raw)


def resolve_corpus_path() -> Path | None:
    """Locate an explicitly configured corpus or the private development copy."""

    configured = os.environ.get(CORPUS_ENVIRONMENT_VARIABLE, "").strip()
    if configured:
        candidate = Path(configured).expanduser()
        return candidate if candidate.is_file() else None
    # Development checkouts retain the canonical source under tests/. Installed
    # product bundles normally do not, so this cannot accidentally ship or
    # download historical messages to another machine.
    development_data = Path(__file__).resolve().parents[2] / "tests" / "data"
    promoted_copy = development_data / "turn_evidence_runtime.v1.jsonl"
    if promoted_copy.is_file():
        return promoted_copy
    development_copy = development_data / "historical_messages.jsonl"
    return development_copy if development_copy.is_file() else None


def _normalized_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = " ".join(unicodedata.normalize("NFC", value).split())
    if not normalized or len(normalized) > 4_096:
        return None
    if any(ord(character) < 32 and character not in {"\t", "\n", "\r"} for character in normalized):
        return None
    return normalized


def _mode_for_row(row: dict[str, Any]) -> str | None:
    row_class = row.get("class")
    if row_class in {"conversation_question", "feedback_failure", "no_action_constraint"}:
        return "conversation"
    if row_class != "user_mission":
        return None
    operations = row.get("operations")
    if not isinstance(operations, list) or not operations:
        return None
    if bool(row.get("possible_chain")) or len(operations) > 1:
        return "plan"
    return "action"


def _families_for_row(row: dict[str, Any]) -> tuple[str, ...] | None:
    operations = row.get("operations") or []
    if not isinstance(operations, list) or not all(isinstance(item, str) for item in operations):
        return None
    families = tuple(sorted({item.split(".", 1)[0] for item in operations if item}))
    return families


def _is_private(row: dict[str, Any], families: tuple[str, ...]) -> bool:
    if bool(row.get("redacted")) or bool(row.get("data_or_preferences")):
        return True
    return "memory" in families


def _normalized_evidence_record(row: dict[str, Any]) -> TurnEvidenceRecord | None:
    """Validate an already screened, provenance-carrying evidence record."""

    if row.get("schema") != EVIDENCE_RECORD_SCHEMA_VERSION:
        return None
    text = _normalized_text(row.get("text"))
    mode = row.get("mode")
    families_raw = row.get("families")
    mission_id = row.get("mission_id")
    source_id = row.get("source_id")
    split = row.get("split")
    provenance = row.get("provenance")
    if (
        text is None
        or mode not in {"conversation", "clarify", "action", "plan"}
        or not isinstance(families_raw, list)
        or not all(isinstance(family, str) and family.isidentifier() for family in families_raw)
        or "memory" in families_raw
        or not isinstance(mission_id, str)
        or not mission_id
        or not isinstance(source_id, str)
        or not source_id
        or split not in {None, "train", "validation", "test"}
        or not isinstance(provenance, dict)
        or not isinstance(provenance.get("dataset"), str)
        or not provenance["dataset"].strip()
        or not isinstance(provenance.get("license"), str)
        or not provenance["license"].strip()
    ):
        return None
    families = tuple(sorted(set(families_raw)))
    if mode in {"action", "plan"} and not families:
        return None
    return TurnEvidenceRecord(
        text,
        mode,
        families,
        mission_id,
        source_id,
        split,
        provenance["dataset"].strip(),
        provenance["license"].strip(),
    )


def _stable_identity(record: TurnEvidenceRecord) -> str:
    return "\u241f".join(
        (
            " ".join(record.text.casefold().split()),
            record.mode,
            ",".join(record.families),
        )
    )


def load_private_corpus(path: Path) -> tuple[list[TurnEvidenceRecord], CorpusEvidenceReport]:
    """Load screened historical rows or provenance-carrying promoted records."""

    path = path.resolve(strict=True)
    if path.stat().st_size > MAX_CORPUS_BYTES:
        raise ValueError("el corpus de evidencia supera el límite local")

    source_digest = hashlib.sha256()
    raw_records: list[TurnEvidenceRecord] = []
    source_rows = 0
    excluded_private = 0
    excluded_noncanonical = 0
    excluded_out_of_scope = 0
    with path.open("rb") as handle:
        for raw_line in handle:
            source_digest.update(raw_line)
            if not raw_line.strip():
                continue
            source_rows += 1
            try:
                row = json.loads(raw_line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ValueError("el corpus de evidencia contiene JSONL inválido") from error
            if not isinstance(row, dict):
                raise ValueError("el corpus de evidencia contiene una fila no objeto")
            normalized_record = _normalized_evidence_record(row)
            if normalized_record is not None:
                raw_records.append(normalized_record)
                continue
            if row.get("schema") == EVIDENCE_RECORD_SCHEMA_VERSION:
                excluded_out_of_scope += 1
                continue
            if row.get("dedup_status") != "canonical_source":
                excluded_noncanonical += 1
                continue
            if row.get("class") not in _LIVE_CLASSES:
                excluded_out_of_scope += 1
                continue
            mode = _mode_for_row(row)
            families = _families_for_row(row)
            text = _normalized_text(row.get("text_literal"))
            mission_id = row.get("canonical_mission_id")
            source_id = row.get("message_id")
            if (
                mode is None
                or families is None
                or text is None
                or not isinstance(mission_id, str)
                or not mission_id
                or not isinstance(source_id, str)
                or not source_id
            ):
                excluded_out_of_scope += 1
                continue
            if _is_private(row, families):
                excluded_private += 1
                continue
            raw_records.append(
                TurnEvidenceRecord(text, mode, families, mission_id, source_id)
            )

    by_text: dict[str, list[TurnEvidenceRecord]] = {}
    for record in raw_records:
        by_text.setdefault(" ".join(record.text.casefold().split()), []).append(record)
    accepted: list[TurnEvidenceRecord] = []
    excluded_ambiguous = 0
    for records in by_text.values():
        signatures = {_stable_identity(record) for record in records}
        if len(signatures) != 1:
            excluded_ambiguous += len(records)
            continue
        # The canonical-source rule means this is usually one row. Retain one
        # deterministic representative if sources produced an exact duplicate.
        accepted.append(min(records, key=lambda record: record.source_id))
    accepted.sort(key=lambda record: (record.mission_id, record.source_id))
    return accepted, CorpusEvidenceReport(
        source_digest.hexdigest(),
        source_rows,
        len(accepted),
        excluded_private,
        excluded_noncanonical,
        excluded_ambiguous,
        excluded_out_of_scope,
    )


def split_for_mission(mission_id: str) -> str:
    """Hash split by mission, never by individual paraphrase or message."""

    digest = hashlib.sha256(mission_id.encode("utf-8")).digest()[0]
    if digest < 204:  # 79.7 % train
        return "train"
    if digest < 230:  # 10.2 % validation
        return "validation"
    return "test"


def _training_provenance(record: TurnEvidenceRecord) -> dict[str, str]:
    """Preserve attribution when exporting the normalized training view."""

    return {"dataset": record.dataset, "license": record.license}


def training_examples(records: Iterable[TurnEvidenceRecord]) -> list[dict[str, Any]]:
    """Produce train/validation/test records with no execution authority."""

    rows = [
        {
            "schema": TRAINING_SCHEMA_VERSION,
            "split": record.split or split_for_mission(record.mission_id),
            "group": record.mission_id,
            "input": {"text": record.text},
            "target": {"mode": record.mode, "families": list(record.families)},
            "source_id": record.source_id,
            "provenance": _training_provenance(record),
        }
        for record in records
    ]
    rows.sort(key=lambda row: (str(row["split"]), str(row["group"]), str(row["source_id"])))
    return rows


def _as_matrix(value: Any, expected_rows: int | None = None) -> np.ndarray:
    matrix = np.asarray(value, dtype=np.float32)
    if matrix.ndim == 1:
        matrix = matrix.reshape(1, -1)
    if matrix.ndim != 2 or matrix.shape[0] == 0:
        raise ValueError("el encoder no devolvió una matriz de embeddings")
    if expected_rows is not None and matrix.shape[0] != expected_rows:
        raise ValueError("el encoder devolvió un número de embeddings inesperado")
    if not np.isfinite(matrix).all():
        raise ValueError("el encoder devolvió embeddings no finitos")
    return matrix


def _exact_top_k_indices(
    scores: np.ndarray,
    indices: np.ndarray | None,
    *,
    limit: int,
    suffix_key: Callable[[int], tuple[Any, ...]],
) -> list[int]:
    """Match the historical stable full sort while selecting only its top-k.

    The score is the first and dominant sort field.  A linear partition finds
    its exact top-k boundary; every row above it is retained and every row on
    it is ranked by the remaining fields.  ``-position`` makes the historical
    stable-input tie break explicit, including duplicate source identifiers.

    Non-finite scores do not define a total numeric order.  They deliberately
    use the former ``sorted(..., reverse=True)`` path byte-for-byte instead of
    assigning new NaN or infinity semantics.
    """

    score_vector = np.asarray(scores)
    local_scores = score_vector if indices is None else score_vector[indices]
    count = int(local_scores.size)
    if limit < 1 or count == 0:
        return []

    def index_at(position: int) -> int:
        return position if indices is None else int(indices[position])

    def historical_sort() -> list[int]:
        return sorted(
            (index_at(position) for position in range(count)),
            key=lambda index: (float(score_vector[index]), *suffix_key(index)),
            reverse=True,
        )[:limit]

    if count <= limit or not np.isfinite(local_scores).all():
        return historical_sort()

    boundary_position = count - limit
    boundary_score = np.partition(local_scores, boundary_position)[
        boundary_position
    ]
    above_positions = [
        int(position)
        for position in np.flatnonzero(local_scores > boundary_score)
    ]
    boundary_positions = [
        int(position)
        for position in np.flatnonzero(local_scores == boundary_score)
    ]
    boundary_needed = limit - len(above_positions)
    boundary_positions.sort(
        key=lambda position: (
            *suffix_key(index_at(position)),
            -position,
        ),
        reverse=True,
    )
    selected_positions = [
        *above_positions,
        *boundary_positions[:boundary_needed],
    ]
    selected_positions.sort(
        key=lambda position: (
            float(local_scores[position]),
            *suffix_key(index_at(position)),
            -position,
        ),
        reverse=True,
    )
    return [index_at(position) for position in selected_positions]


def _cache_directory() -> Path | None:
    configured = os.environ.get(CACHE_ENVIRONMENT_VARIABLE, "").strip()
    if configured:
        return Path(configured).expanduser()
    local_data = os.environ.get("LOCALAPPDATA", "").strip()
    return Path(local_data) / "BAXYRuntime" / "turn-evidence" if local_data else None


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _cache_key(path: Path, encoder_identity: str) -> tuple[str, str]:
    """Bind cached vectors to exact corpus bytes and an explicit encoder profile."""

    source_sha256 = _file_sha256(path)
    material = (
        f"{SCHEMA_VERSION}\u241f{path.resolve()}\u241f{source_sha256}"
        f"\u241f{encoder_identity}"
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:24], source_sha256


def _write_atomic(path: Path, payload: str) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        temporary.write_text(payload, encoding="utf-8")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink(missing_ok=True)


def _is_candidate_training_record(record: TurnEvidenceRecord) -> bool:
    """Accept only canonical actionable family labels from the train split."""

    families = record.families
    return (
        record.split == "train"
        and record.mode in _ACTIONABLE_MODES
        and bool(families)
        and families == tuple(sorted(set(families)))
        and all(
            isinstance(family, str)
            and family.isidentifier()
            and family != "memory"
            for family in families
        )
    )


class TurnEvidenceIndex:
    """In-memory vectors plus diverse retrieval for one screened local corpus."""

    def __init__(
        self,
        records: Sequence[TurnEvidenceRecord],
        vectors: Any,
        report: CorpusEvidenceReport,
        *,
        encoder_identity: str = DEFAULT_ENCODER_IDENTITY,
    ) -> None:
        self._records = tuple(records)
        self._vectors = _as_matrix(vectors, len(self._records))
        self._candidate_training_indices = tuple(
            index
            for index, record in enumerate(self._records)
            if _is_candidate_training_record(record)
        )
        self._candidate_training_index_array = np.asarray(
            self._candidate_training_indices,
            dtype=np.intp,
        )
        self._candidate_training_index_array.flags.writeable = False
        self.report = report
        self.encoder_identity = encoder_identity

    @property
    def count(self) -> int:
        return len(self._records)

    @property
    def dimensions(self) -> int:
        return int(self._vectors.shape[1])

    @classmethod
    def from_corpus(
        cls,
        path: Path,
        encoder: Encoder,
        *,
        encoder_identity: str = DEFAULT_ENCODER_IDENTITY,
        is_cancelled: CancellationProbe | None = None,
    ) -> "TurnEvidenceIndex":
        _raise_if_build_cancelled(is_cancelled)
        path = path.resolve(strict=True)
        if not encoder_identity.strip():
            raise ValueError("la identidad del encoder no puede estar vacía")
        cache_dir = _cache_directory()
        cache_key, source_sha256 = _cache_key(path, encoder_identity)
        _raise_if_build_cancelled(is_cancelled)
        if cache_dir is not None:
            cached = cls._load_cache(
                cache_dir,
                cache_key,
                source_sha256=source_sha256,
                encoder_identity=encoder_identity,
            )
            if cached is not None:
                _raise_if_build_cancelled(is_cancelled)
                return cached

        records, report = load_private_corpus(path)
        _raise_if_build_cancelled(is_cancelled)
        if not records:
            raise ValueError("el corpus no dejó evidencia pública elegible")
        if report.source_sha256 != source_sha256:
            raise ValueError("el corpus cambió mientras se construía el índice")
        vectors = cls._encode_records(
            records,
            encoder,
            is_cancelled=is_cancelled,
        )
        _raise_if_build_cancelled(is_cancelled)
        index = cls(
            records,
            vectors,
            report,
            encoder_identity=encoder_identity,
        )
        if cache_dir is not None:
            _raise_if_build_cancelled(is_cancelled)
            index._store_cache(
                cache_dir,
                cache_key,
                is_cancelled=is_cancelled,
            )
        return index

    @staticmethod
    def _encode_records(
        records: Sequence[TurnEvidenceRecord],
        encoder: Encoder,
        *,
        is_cancelled: CancellationProbe | None = None,
    ) -> np.ndarray:
        batches: list[np.ndarray] = []
        for start in range(0, len(records), 256):
            _raise_if_build_cancelled(is_cancelled)
            batch = [record.text for record in records[start : start + 256]]
            batches.append(_as_matrix(encoder(batch), len(batch)))
            _raise_if_build_cancelled(is_cancelled)
        return np.concatenate(batches, axis=0)

    @classmethod
    def _load_cache(
        cls,
        directory: Path,
        cache_key: str,
        *,
        source_sha256: str,
        encoder_identity: str,
    ) -> "TurnEvidenceIndex | None":
        metadata_path = directory / f"{cache_key}.json"
        vectors_path = directory / f"{cache_key}.npy"
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if (
                not isinstance(metadata, dict)
                or metadata.get("schema") != SCHEMA_VERSION
                or metadata.get("contains_text") is not False
                or metadata.get("source_sha256") != source_sha256
                or metadata.get("encoder_identity") != encoder_identity
                or metadata.get("vectors_sha256") != _file_sha256(vectors_path)
            ):
                return None
            raw_records = metadata.get("records")
            raw_report = metadata.get("report")
            if not isinstance(raw_records, list) or not isinstance(raw_report, dict):
                return None
            if any(
                not isinstance(item, dict) or "text" in item
                for item in raw_records
            ):
                return None
            records = tuple(
                TurnEvidenceRecord(
                    text="",
                    mode=str(item["mode"]),
                    families=tuple(str(value) for value in item["families"]),
                    mission_id=str(item["mission_id"]),
                    source_id=str(item["source_id"]),
                    split=(str(item["split"]) if item.get("split") is not None else None),
                    dataset=str(
                        item.get(
                            "dataset",
                            "BAXY historical evidence (privacy-screened)",
                        )
                    ),
                    license=str(item.get("license", "private-local")),
                )
                for item in raw_records
                if isinstance(item, dict)
            )
            if len(records) != len(raw_records) or not records:
                return None
            report = CorpusEvidenceReport(**raw_report)
            if report.source_sha256 != source_sha256:
                return None
            vectors = np.load(vectors_path, allow_pickle=False)
            return cls(
                records,
                vectors,
                report,
                encoder_identity=encoder_identity,
            )
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            return None

    def _store_cache(
        self,
        directory: Path,
        cache_key: str,
        *,
        is_cancelled: CancellationProbe | None = None,
    ) -> None:
        _raise_if_build_cancelled(is_cancelled)
        directory.mkdir(parents=True, exist_ok=True)
        metadata_path = directory / f"{cache_key}.json"
        vectors_path = directory / f"{cache_key}.npy"
        temporary_vectors = vectors_path.with_name(
            f".{vectors_path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
        )
        try:
            _raise_if_build_cancelled(is_cancelled)
            with temporary_vectors.open("wb") as handle:
                np.save(handle, self._vectors, allow_pickle=False)
            _raise_if_build_cancelled(is_cancelled)
            os.replace(temporary_vectors, vectors_path)
            vectors_sha256 = _file_sha256(vectors_path)
            _raise_if_build_cancelled(is_cancelled)
            _write_atomic(
                metadata_path,
                json.dumps(
                    {
                        "schema": SCHEMA_VERSION,
                        "contains_text": False,
                        "source_sha256": self.report.source_sha256,
                        "encoder_identity": self.encoder_identity,
                        "vectors_sha256": vectors_sha256,
                        "report": asdict(self.report),
                        "records": [
                            {
                                "mode": record.mode,
                                "families": list(record.families),
                                "mission_id": record.mission_id,
                                "source_id": record.source_id,
                                "split": record.split,
                                "dataset": record.dataset,
                                "license": record.license,
                            }
                            for record in self._records
                        ],
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            )
            _raise_if_build_cancelled(is_cancelled)
            verified = self._load_cache(
                directory,
                cache_key,
                source_sha256=self.report.source_sha256,
                encoder_identity=self.encoder_identity,
            )
            if verified is None:
                raise ValueError("el cache v4 no superó su verificación")
            _raise_if_build_cancelled(is_cancelled)
            self._remove_stale_sensitive_cache(
                directory,
                current_metadata=metadata_path,
            )
        finally:
            if temporary_vectors.exists():
                temporary_vectors.unlink(missing_ok=True)

    def _remove_stale_sensitive_cache(
        self,
        directory: Path,
        *,
        current_metadata: Path,
    ) -> None:
        """Rotate an older literal-bearing pair only after v4 is durable."""

        for metadata_path in directory.glob("*.json"):
            if metadata_path == current_metadata:
                continue
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                records = metadata.get("records")
                if (
                    not isinstance(metadata, dict)
                    or metadata.get("source_sha256")
                    != self.report.source_sha256
                    or metadata.get("encoder_identity") != self.encoder_identity
                    or not isinstance(records, list)
                    or not any(
                        isinstance(record, dict) and "text" in record
                        for record in records
                    )
                ):
                    continue
                vectors_path = metadata_path.with_suffix(".npy")
                metadata_path.unlink(missing_ok=True)
                vectors_path.unlink(missing_ok=True)
            except (OSError, AttributeError, json.JSONDecodeError):
                continue

    def search(
        self,
        text: str,
        encoder: Encoder,
        candidate_operations: Sequence[str],
        *,
        limit: int = 32,
    ) -> list[TurnEvidenceMatch]:
        """Rank semantic observations without granting them authority."""

        normalized = _normalized_text(text)
        if normalized is None or limit < 1:
            return []
        query = _as_matrix(encoder([normalized]), expected_rows=1)
        if query.shape[1] != self._vectors.shape[1]:
            return []
        return self._rank_query(
            query[0],
            candidate_operations,
            limit=limit,
        )

    def candidate_families(
        self,
        text: str,
        encoder: Encoder,
        *,
        neighbors: int = DEFAULT_CANDIDATE_NEIGHBORS,
        limit: int = MAX_CANDIDATE_FAMILIES,
    ) -> tuple[str, ...]:
        """Return train-corpus families for candidate expansion only.

        This is a broad union of diverse nearest-neighbor labels. It never
        predicts a turn mode or selects an operation. The authenticated
        catalog still ranks concrete operations, and execution remains behind
        the LLM decision plus deterministic validators.
        """

        if not 1 <= neighbors <= 32 or not 1 <= limit <= MAX_CANDIDATE_FAMILIES:
            return ()
        normalized = _normalized_text(text)
        if normalized is None:
            return ()
        query = _as_matrix(encoder([normalized]), expected_rows=1)
        if query.shape[1] != self._vectors.shape[1]:
            return ()
        ranking = self._rank_candidate_training_query(
            query[0],
            limit=max(neighbors * 8, 64),
        )
        diverse: list[TurnEvidenceMatch] = []
        missions: set[str] = set()
        for match in ranking:
            if match.record.mission_id in missions:
                continue
            diverse.append(match)
            missions.add(match.record.mission_id)
            if len(diverse) >= neighbors:
                break

        votes: dict[str, float] = {}
        best_score: dict[str, float] = {}
        for match in diverse:
            families = match.record.families
            if not families:
                continue
            weight = (max(0.0, float(match.score)) + 1e-9) / len(families)
            for family in families:
                votes[family] = votes.get(family, 0.0) + weight
                best_score[family] = max(
                    best_score.get(family, -1.0),
                    float(match.score),
                )
        return tuple(
            sorted(
                votes,
                key=lambda family: (
                    votes[family],
                    best_score[family],
                    family,
                ),
                reverse=True,
            )[:limit]
        )

    def _rank_candidate_training_query(
        self,
        query: np.ndarray,
        *,
        limit: int,
    ) -> list[TurnEvidenceMatch]:
        """Rank only train-family rows without changing general retrieval."""

        scores = query @ self._vectors.T
        ranking = _exact_top_k_indices(
            scores,
            self._candidate_training_index_array,
            limit=limit,
            suffix_key=lambda index: (self._records[index].source_id,),
        )
        return [
            TurnEvidenceMatch(
                record=self._records[index],
                score=float(scores[index]),
                candidate_family_match=False,
            )
            for index in ranking[:limit]
        ]

    def _rank_query(
        self,
        query: np.ndarray,
        candidate_operations: Sequence[str],
        *,
        limit: int,
    ) -> list[TurnEvidenceMatch]:
        scores = query @ self._vectors.T
        candidate_families = {
            operation.split(".", 1)[0]
            for operation in candidate_operations
            if isinstance(operation, str) and "." in operation
        }
        ranking = _exact_top_k_indices(
            scores,
            None,
            limit=limit,
            suffix_key=lambda index: (
                not candidate_families.isdisjoint(
                    self._records[index].families
                ),
                self._records[index].source_id,
            ),
        )
        return [
            TurnEvidenceMatch(
                record=self._records[index],
                score=float(scores[index]),
                candidate_family_match=bool(
                    candidate_families & set(self._records[index].families)
                ),
            )
            for index in ranking[:limit]
        ]

    def retrieve(
        self,
        text: str,
        encoder: Encoder,
        candidate_operations: Sequence[str],
        *,
        policy: (
            TurnEvidenceAbstentionPolicy
            | OneSidedTurnEvidencePolicy
            | None
        ) = None,
        limit: int = MAX_RETRIEVED_EVIDENCE,
    ) -> list[dict[str, Any]]:
        """Return evidence only when a compatible frozen policy accepts it."""

        if isinstance(policy, OneSidedTurnEvidencePolicy):
            if not policy.is_compatible(
                source_sha256=self.report.source_sha256,
                encoder_identity=self.encoder_identity,
                dimensions=self.dimensions,
            ):
                return []
            normalized = _normalized_text(text)
            if normalized is None or limit < 1:
                return []
            query = _as_matrix(encoder([normalized]), expected_rows=1)
            if query.shape[1] != self.dimensions:
                return []
            emits, distribution = policy.probe.emits_conversation(query[0])
            if not emits:
                return []
            ranking = self._rank_query(
                query[0],
                candidate_operations,
                limit=max(limit * 32, policy.neighbors * 16, 128),
            )
            diverse: list[TurnEvidenceMatch] = []
            diverse_missions: set[str] = set()
            for match in ranking:
                if match.record.mission_id in diverse_missions:
                    continue
                diverse.append(match)
                diverse_missions.add(match.record.mission_id)
                if len(diverse) >= policy.neighbors:
                    break
            signals = summarize_conversation_neighbors(
                [
                    (match.score, match.record.mode)
                    for match in diverse
                ]
            )
            if (
                signals.neighbor_count < policy.neighbors
                or not policy.conversation_knn.accepts(signals)
            ):
                return []
            selected: list[dict[str, Any]] = []
            seen_missions: set[str] = set()
            for match in ranking:
                if match.record.mode != "conversation":
                    continue
                if match.record.mission_id in seen_missions:
                    continue
                selected.append(
                    {
                        "mode": "conversation",
                        "families": [],
                        "score": round(match.score, 6),
                        "candidate_family_match": False,
                        "calibrated_conversation_probability": round(
                            distribution["conversation"],
                            6,
                        ),
                    }
                )
                seen_missions.add(match.record.mission_id)
                if len(selected) >= limit:
                    break
            return selected

        if policy is None or not policy.is_compatible(
            source_sha256=self.report.source_sha256,
            encoder_identity=self.encoder_identity,
        ):
            return []
        ranking = self.search(
            text,
            encoder,
            candidate_operations,
            limit=max(limit * 16, policy.neighbors * 16, 64),
        )
        selected_matches: list[TurnEvidenceMatch] = []
        seen_missions: set[str] = set()
        for match in ranking:
            record = match.record
            if record.mission_id in seen_missions:
                continue
            selected_matches.append(match)
            seen_missions.add(record.mission_id)
            if len(selected_matches) >= max(limit, policy.neighbors):
                break
        confidence = summarize_match_confidence(
            selected_matches[: policy.neighbors]
        )
        if not policy.accepts(confidence):
            return []
        return [
            match.prompt_card() for match in selected_matches[:limit]
        ]


class TurnEvidenceService:
    """Build the semantic evidence index off the turn-critical path."""

    def __init__(
        self,
        corpus_path: Path | None = None,
        *,
        policy: OneSidedTurnEvidencePolicy | None = None,
        policy_path: Path | None = None,
        evidence_enabled: bool | None = None,
    ) -> None:
        self._corpus_path = corpus_path or resolve_corpus_path()
        self._lock = threading.Lock()
        self._index: TurnEvidenceIndex | None = None
        self._state = "unavailable" if self._corpus_path is None else "cold"
        self._failure = ""
        self._policy_failure = ""
        if evidence_enabled is None:
            evidence_enabled = os.environ.get(
                DISABLE_EVIDENCE_ENVIRONMENT_VARIABLE,
                "",
            ).strip().casefold() not in {"1", "true", "yes", "on"}
        self._evidence_enabled = bool(evidence_enabled)
        if policy is not None:
            self._policy = policy
            self._policy_state = "provided"
        else:
            try:
                self._policy = load_abstention_policy(policy_path)
                self._policy_state = (
                    "loaded" if self._policy is not None else "missing"
                )
            except Exception as error:  # noqa: BLE001 - fail closed
                self._policy = None
                self._policy_state = "invalid"
                self._policy_failure = type(error).__name__
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    @property
    def failure(self) -> str:
        with self._lock:
            return self._failure

    @property
    def diagnostics(self) -> dict[str, Any]:
        with self._lock:
            index = self._index
            return {
                "state": self._state,
                "failure": self._failure,
                "count": index.count if index is not None else 0,
                "dimensions": index.dimensions if index is not None else 0,
                "source_sha256": (
                    index.report.source_sha256 if index is not None else ""
                ),
                "encoder_identity": (
                    index.encoder_identity if index is not None else ""
                ),
                "abstention_policy": {
                    "state": self._policy_state,
                    "failure": self._policy_failure,
                    "calibration_fingerprint": (
                        self._policy.validation_fingerprint
                        if self._policy is not None
                        else ""
                    ),
                    "calibration_rows": (
                        self._policy.validation_rows
                        if self._policy is not None
                        else 0
                    ),
                    "authority": "conversation_signal_or_abstain_only",
                    "retrieval_enabled": self._evidence_enabled,
                },
            }

    def start(self, encoder: Encoder, is_encoder_ready: Callable[[], bool]) -> None:
        if self._corpus_path is None:
            return
        with self._lock:
            if self._thread is not None or self._stop_event.is_set():
                return
            self._state = "building"
            self._thread = threading.Thread(
                target=self._build,
                args=(encoder, is_encoder_ready),
                name="baxy-turn-evidence",
                daemon=True,
            )
            self._thread.start()

    def stop(self, timeout: float = 0.0) -> bool:
        """Request cancellation and join the builder for at most ``timeout``."""

        self._stop_event.set()
        with self._lock:
            thread = self._thread
            if self._state == "building":
                self._state = "stopping"
        if (
            thread is not None
            and thread is not threading.current_thread()
            and thread.is_alive()
        ):
            thread.join(timeout=max(0.0, float(timeout)))
        stopped = thread is None or not thread.is_alive()
        if stopped:
            with self._lock:
                if self._state in {"building", "stopping"}:
                    self._state = "stopped"
        return stopped

    def _build(self, encoder: Encoder, is_encoder_ready: Callable[[], bool]) -> None:
        try:
            for _ in range(ENCODER_READY_TIMEOUT_SECONDS):
                if self._stop_event.is_set():
                    return
                if is_encoder_ready():
                    break
                if self._stop_event.wait(timeout=1.0):
                    return
            else:
                raise TimeoutError("el encoder semántico no estuvo listo para el corpus")
            if self._stop_event.is_set():
                return
            index = TurnEvidenceIndex.from_corpus(
                self._corpus_path,
                encoder,
                is_cancelled=self._stop_event.is_set,
            )
            if self._stop_event.is_set():
                return
            with self._lock:
                if self._stop_event.is_set():
                    return
                self._index = index
                self._state = "ready"
                if self._policy is not None and not self._policy.is_compatible(
                    source_sha256=index.report.source_sha256,
                    encoder_identity=index.encoder_identity,
                    dimensions=index.dimensions,
                ):
                    self._policy_state = "incompatible"
        except Exception as error:  # noqa: BLE001 - evidence never blocks BAXY
            with self._lock:
                if not self._stop_event.is_set():
                    self._failure = type(error).__name__
                    self._state = "failed"
        finally:
            if self._stop_event.is_set():
                with self._lock:
                    if self._state in {"building", "stopping"}:
                        self._state = "stopped"

    def retrieve(
        self,
        text: str,
        encoder: Encoder,
        candidate_operations: Sequence[str],
    ) -> list[dict[str, Any]]:
        if not self._evidence_enabled:
            return []
        with self._lock:
            index = self._index
            policy = self._policy
        if index is None or policy is None:
            return []
        try:
            return index.retrieve(
                text,
                encoder,
                candidate_operations,
                policy=policy,
            )
        except Exception:  # noqa: BLE001 - retrieval is advisory only
            return []

    def candidate_families(
        self,
        text: str,
        encoder: Encoder,
    ) -> tuple[str, ...]:
        """Expand catalog candidates identically with or without A/B evidence."""

        with self._lock:
            index = self._index
        if index is None:
            return ()
        try:
            return index.candidate_families(text, encoder)
        except Exception:  # noqa: BLE001 - candidate expansion is advisory
            return ()
