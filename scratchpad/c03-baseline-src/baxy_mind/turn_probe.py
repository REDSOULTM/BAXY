"""Safe, JSON-serializable one-sided linear probe for turn evidence."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np


POLICY_SCHEMA = "baxy.turn-evidence-one-sided-policy.v1"
MAX_CLASSES = 4
MAX_DIMENSIONS = 4_096
MAX_ABSOLUTE_WEIGHT = 1_000_000.0


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _valid_sha256(value: str) -> bool:
    return len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )


@dataclass(frozen=True, slots=True)
class TurnModeLinearProbe:
    """Frozen softmax weights plus validation-only temperature/threshold."""

    classes: tuple[str, ...]
    coefficients: tuple[tuple[float, ...], ...]
    intercepts: tuple[float, ...]
    temperature: float
    conversation_threshold: float
    implementation: str
    training_rows: int
    training_split_fingerprint: str

    def __post_init__(self) -> None:
        if (
            len(self.classes) < 2
            or len(self.classes) > MAX_CLASSES
            or len(set(self.classes)) != len(self.classes)
            or "conversation" not in self.classes
            or any(
                label not in {"conversation", "clarify", "action", "plan"}
                for label in self.classes
            )
        ):
            raise ValueError("clases inválidas para el probe")
        if (
            len(self.coefficients) != len(self.classes)
            or len(self.intercepts) != len(self.classes)
        ):
            raise ValueError("shape de clases inválido")
        dimensions = len(self.coefficients[0]) if self.coefficients else 0
        if not 1 <= dimensions <= MAX_DIMENSIONS or any(
            len(row) != dimensions for row in self.coefficients
        ):
            raise ValueError("shape de coeficientes inválido")
        values = [
            *self.intercepts,
            *(value for row in self.coefficients for value in row),
        ]
        if any(
            not math.isfinite(value)
            or abs(value) > MAX_ABSOLUTE_WEIGHT
            for value in values
        ):
            raise ValueError("pesos no finitos o fuera de límite")
        if not math.isfinite(self.temperature) or not 0.05 <= self.temperature <= 20.0:
            raise ValueError("temperatura fuera de límite")
        if not 0.0 <= self.conversation_threshold <= 1.0:
            raise ValueError("umbral conversacional fuera de límite")
        if (
            not self.implementation
            or len(self.implementation) > 128
            or self.training_rows < 1
            or not _valid_sha256(self.training_split_fingerprint)
        ):
            raise ValueError("procedencia de entrenamiento inválida")

    @property
    def dimensions(self) -> int:
        return len(self.coefficients[0])

    def _weights_payload(self) -> dict[str, Any]:
        return {
            "classes": list(self.classes),
            "coefficients": [list(row) for row in self.coefficients],
            "intercepts": list(self.intercepts),
        }

    @property
    def weights_sha256(self) -> str:
        return _canonical_sha256(self._weights_payload())

    def distribution(self, embedding: Sequence[float] | np.ndarray) -> dict[str, float]:
        vector = np.asarray(embedding, dtype=np.float64)
        if (
            vector.ndim != 1
            or vector.shape[0] != self.dimensions
            or not np.isfinite(vector).all()
        ):
            raise ValueError("embedding incompatible con el probe")
        weights = np.asarray(self.coefficients, dtype=np.float64)
        intercepts = np.asarray(self.intercepts, dtype=np.float64)
        logits = (weights @ vector + intercepts) / self.temperature
        logits -= float(np.max(logits))
        probabilities = np.exp(logits)
        probabilities /= float(np.sum(probabilities))
        return {
            label: float(probability)
            for label, probability in zip(
                self.classes,
                probabilities,
                strict=True,
            )
        }

    def emits_conversation(
        self,
        embedding: Sequence[float] | np.ndarray,
    ) -> tuple[bool, dict[str, float]]:
        distribution = self.distribution(embedding)
        probability = distribution["conversation"]
        return probability >= self.conversation_threshold, distribution

    def to_dict(self) -> dict[str, Any]:
        return {
            **self._weights_payload(),
            "weights_sha256": self.weights_sha256,
            "temperature": self.temperature,
            "conversation_threshold": self.conversation_threshold,
            "implementation": self.implementation,
            "training_rows": self.training_rows,
            "training_split_fingerprint": self.training_split_fingerprint,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TurnModeLinearProbe":
        classes = value.get("classes")
        coefficients = value.get("coefficients")
        intercepts = value.get("intercepts")
        if (
            not isinstance(classes, list)
            or not isinstance(coefficients, list)
            or not isinstance(intercepts, list)
            or not isinstance(value.get("weights_sha256"), str)
        ):
            raise ValueError("probe JSON incompleto")
        probe = cls(
            classes=tuple(str(label) for label in classes),
            coefficients=tuple(
                tuple(float(weight) for weight in row)
                for row in coefficients
                if isinstance(row, list)
            ),
            intercepts=tuple(float(item) for item in intercepts),
            temperature=float(value.get("temperature")),
            conversation_threshold=float(value.get("conversation_threshold")),
            implementation=str(value.get("implementation") or ""),
            training_rows=int(value.get("training_rows") or 0),
            training_split_fingerprint=str(
                value.get("training_split_fingerprint") or ""
            ),
        )
        if probe.weights_sha256 != value["weights_sha256"]:
            raise ValueError("hash de pesos del probe no coincide")
        return probe


@dataclass(frozen=True, slots=True)
class ConversationKnnSignals:
    neighbor_count: int
    top1_score: float
    score_margin: float
    conversation_agreement: float
    mode_entropy: float
    conversation_fraction: float


@dataclass(frozen=True, slots=True)
class ConversationKnnThresholds:
    minimum_top1_score: float
    minimum_score_margin: float
    minimum_conversation_agreement: float
    maximum_mode_entropy: float
    minimum_conversation_fraction: float

    def __post_init__(self) -> None:
        values = (
            self.minimum_top1_score,
            self.minimum_score_margin,
            self.minimum_conversation_agreement,
            self.maximum_mode_entropy,
            self.minimum_conversation_fraction,
        )
        if any(not math.isfinite(value) for value in values):
            raise ValueError("umbrales kNN no finitos")
        if not -1.0 <= self.minimum_top1_score <= 1.0:
            raise ValueError("top1 kNN fuera de rango")
        if not 0.0 <= self.minimum_score_margin <= 2.0:
            raise ValueError("margen kNN fuera de rango")
        if not 0.0 <= self.minimum_conversation_agreement <= 1.0:
            raise ValueError("acuerdo kNN fuera de rango")
        if not 0.0 <= self.maximum_mode_entropy <= 1.0:
            raise ValueError("entropía kNN fuera de rango")
        if not 0.0 <= self.minimum_conversation_fraction <= 1.0:
            raise ValueError("fracción kNN fuera de rango")

    def accepts(
        self,
        signals: ConversationKnnSignals | dict[str, Any],
    ) -> bool:
        def value(name: str) -> float:
            if isinstance(signals, dict):
                return float(signals[name])
            return float(getattr(signals, name))

        return (
            value("top1_score") >= self.minimum_top1_score
            and value("score_margin") >= self.minimum_score_margin
            and value("conversation_agreement")
            >= self.minimum_conversation_agreement
            and value("mode_entropy") <= self.maximum_mode_entropy
            and value("conversation_fraction")
            >= self.minimum_conversation_fraction
        )

    def to_dict(self) -> dict[str, float]:
        return {
            "minimum_top1_score": self.minimum_top1_score,
            "minimum_score_margin": self.minimum_score_margin,
            "minimum_conversation_agreement": (
                self.minimum_conversation_agreement
            ),
            "maximum_mode_entropy": self.maximum_mode_entropy,
            "minimum_conversation_fraction": (
                self.minimum_conversation_fraction
            ),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ConversationKnnThresholds":
        expected = {
            "minimum_top1_score",
            "minimum_score_margin",
            "minimum_conversation_agreement",
            "maximum_mode_entropy",
            "minimum_conversation_fraction",
        }
        if set(value) != expected:
            raise ValueError("umbrales kNN incompletos")
        return cls(**{name: float(value[name]) for name in expected})


def summarize_conversation_neighbors(
    neighbors: Sequence[tuple[float, str]],
) -> ConversationKnnSignals:
    if not neighbors:
        return ConversationKnnSignals(0, -1.0, 0.0, 0.0, 1.0, 0.0)
    ranked = sorted(neighbors, key=lambda item: item[0], reverse=True)
    weights: dict[str, float] = {}
    conversation_count = 0
    for score, mode in ranked:
        weight = max(0.0, float(score)) + 1e-9
        weights[mode] = weights.get(mode, 0.0) + weight
        conversation_count += int(mode == "conversation")
    total = sum(weights.values())
    conversation_agreement = weights.get("conversation", 0.0) / total
    positive = [value for value in weights.values() if value > 0.0]
    if len(positive) <= 1:
        mode_entropy = 0.0
    else:
        mode_entropy = -sum(
            (value / total) * math.log(value / total) for value in positive
        ) / math.log(len(positive))
    scores = [float(score) for score, _ in ranked]
    return ConversationKnnSignals(
        neighbor_count=len(ranked),
        top1_score=scores[0],
        score_margin=(scores[0] - scores[1] if len(scores) >= 2 else 0.0),
        conversation_agreement=conversation_agreement,
        mode_entropy=min(1.0, max(0.0, mode_entropy)),
        conversation_fraction=conversation_count / len(ranked),
    )


@dataclass(frozen=True, slots=True)
class OneSidedTurnEvidencePolicy:
    """Policy that can emit conversation evidence or abstain, never action."""

    runtime_source_sha256: str
    encoder_identity: str
    probe: TurnModeLinearProbe
    neighbors: int
    conversation_knn: ConversationKnnThresholds
    validation_fingerprint: str
    validation_rows: int
    final_seal_source_ids_sha256: str
    historical_index_rows: int

    def __post_init__(self) -> None:
        if (
            not _valid_sha256(self.runtime_source_sha256)
            or not _valid_sha256(self.validation_fingerprint)
            or not _valid_sha256(self.final_seal_source_ids_sha256)
            or not self.encoder_identity
            or len(self.encoder_identity) > 512
            or not 2 <= self.neighbors <= 32
            or self.validation_rows < 1
            or self.historical_index_rows < 0
        ):
            raise ValueError("binding de política one-sided inválido")
        if self.probe.dimensions < 1:
            raise ValueError("probe vacío")

    def is_compatible(
        self,
        *,
        source_sha256: str,
        encoder_identity: str,
        dimensions: int | None = None,
    ) -> bool:
        return (
            self.runtime_source_sha256 == source_sha256
            and self.encoder_identity == encoder_identity
            and (
                dimensions is None
                or self.probe.dimensions == dimensions
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": POLICY_SCHEMA,
            "authority": "conversation_signal_or_abstain_only",
            "runtime_source_sha256": self.runtime_source_sha256,
            "encoder_identity": self.encoder_identity,
            "neighbors": self.neighbors,
            "probe": self.probe.to_dict(),
            "conversation_knn": self.conversation_knn.to_dict(),
            "calibration": {
                "fit_split": "validation",
                "fingerprint_sha256": self.validation_fingerprint,
                "rows": self.validation_rows,
            },
            "final_seal_source_ids_sha256": (
                self.final_seal_source_ids_sha256
            ),
            "historical_usage": {
                "rows": self.historical_index_rows,
                "probe_training_rows": 0,
                "reason": "weak_or_noisy_labels",
                "role": "index_and_conversation_retrieval_only",
                "text_sent_to_llm": False,
            },
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "OneSidedTurnEvidencePolicy":
        calibration = value.get("calibration")
        probe = value.get("probe")
        conversation_knn = value.get("conversation_knn")
        historical_usage = value.get("historical_usage")
        if (
            value.get("schema") != POLICY_SCHEMA
            or value.get("authority")
            != "conversation_signal_or_abstain_only"
            or not isinstance(calibration, dict)
            or calibration.get("fit_split") != "validation"
            or not isinstance(probe, dict)
            or not isinstance(conversation_knn, dict)
            or not isinstance(historical_usage, dict)
            or historical_usage.get("probe_training_rows") != 0
            or historical_usage.get("reason") != "weak_or_noisy_labels"
            or historical_usage.get("text_sent_to_llm") is not False
        ):
            raise ValueError("política one-sided inválida")
        return cls(
            runtime_source_sha256=str(
                value.get("runtime_source_sha256") or ""
            ),
            encoder_identity=str(value.get("encoder_identity") or ""),
            probe=TurnModeLinearProbe.from_dict(probe),
            neighbors=int(value.get("neighbors") or 0),
            conversation_knn=ConversationKnnThresholds.from_dict(
                conversation_knn
            ),
            validation_fingerprint=str(
                calibration.get("fingerprint_sha256") or ""
            ),
            validation_rows=int(calibration.get("rows") or 0),
            final_seal_source_ids_sha256=str(
                value.get("final_seal_source_ids_sha256") or ""
            ),
            historical_index_rows=int(
                historical_usage.get("rows") or 0
            ),
        )
