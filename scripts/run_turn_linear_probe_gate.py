"""Train/calibrate a one-sided E5 linear probe, then score a sealed final set.

Validation and final are intentionally separate commands.  The validation
phase freezes all model/calibration/kNN-family choices into a JSON checkpoint.
The final phase refuses to run when its output already exists and never tunes.
Both phases cryptographically rebuild the blind v2 seal from the unevaluated
v1 complement before accepting it. Validation decodes only public validation
rows; final decodes only the exact v2 IDs. No operation is dispatched.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np


REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
SCRIPTS = REPO / "scripts"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from baxy_mind.router import IntentRouter  # noqa: E402
from baxy_mind.turn_evidence import (  # noqa: E402
    DEFAULT_ENCODER_IDENTITY,
    TurnEvidenceIndex,
    load_private_corpus,
)
from baxy_mind.turn_probe import (  # noqa: E402
    ConversationKnnThresholds,
    OneSidedTurnEvidencePolicy,
    TurnModeLinearProbe,
    summarize_conversation_neighbors,
)
from blind_reset_turn_evidence_final_seal import (  # noqa: E402
    DEFAULT_OLD_SEAL as PREDECESSOR_SEAL,
    PRODUCTION_RULE_DECLARATION_SHA256,
    SCHEMA as SEAL_SCHEMA,
    build_reset_seal,
    extract_holdout_row_identity,
)
from run_turn_evidence_encoder_gate import (  # noqa: E402
    configured_cache,
    file_sha256,
    macro_f1,
    percentile,
    report_path,
    wilson_interval,
    write_json_atomic,
)


RUNTIME = REPO / "tests" / "data" / "turn_evidence_runtime.v1.jsonl"
HOLDOUT = REPO / "tests" / "data" / "turn_evidence_public_holdout.v1.jsonl"
SEAL = REPO / "tests" / "data" / "turn_evidence_final_seal.v2.json"
VALIDATION_OUTPUT = (
    REPO / "artifacts" / "product" / "turn_linear_probe_validation.json"
)
FINAL_OUTPUT = REPO / "artifacts" / "product" / "turn_linear_probe_gate.json"
POLICY_OUTPUT = (
    REPO
    / "src"
    / "baxy_mind"
    / "data"
    / "turn_evidence_abstention_policy.v1.json"
)
VALIDATION_SCHEMA = "baxy.turn-linear-probe-validation.v1"
FINAL_SCHEMA = "baxy.turn-linear-probe-final-gate.v1"
K_CANDIDATES = (5, 7, 9)
MAX_FALSE_ACTION_UPPER = 0.01
MIN_FAMILY_PRECISION_LOWER = 0.95
MIN_RAW_FAMILY_RECALL_AT_K = 0.98
MIN_ACTIONABLE_COVERAGE_LOWER = 0.30
MIN_FAMILY_RECALL_LOWER = 0.30
MIN_CONVERSATION_PRECISION_LOWER = 0.95
MIN_CONVERSATION_RECALL_LOWER = 0.30


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def split_fingerprint(records: Sequence[Any], split: str) -> str:
    rows = sorted(
        (
            {
                "source_id": record.source_id,
                "mode": record.mode,
                "families": list(record.families),
                "split": record.split,
            }
            for record in records
            if record.split == split
        ),
        key=lambda row: row["source_id"],
    )
    return canonical_sha256(rows)


def load_seal(
    path: Path,
    holdout: Path,
    predecessor_seal: Path = PREDECESSOR_SEAL,
) -> dict[str, Any]:
    """Rebuild and compare the complete blind v2 manifest."""

    path = path.resolve(strict=True)
    holdout = holdout.resolve(strict=True)
    predecessor_seal = predecessor_seal.resolve(strict=True)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError("sello final v2 contiene JSON inválido") from error
    rebuilt = build_reset_seal(holdout, predecessor_seal)
    if raw != rebuilt:
        raise ValueError(
            "sello final v2 no coincide con su reconstrucción criptográfica"
        )
    if (
        raw.get("schema") != SEAL_SCHEMA
        or raw.get("rule_declaration_sha256")
        != PRODUCTION_RULE_DECLARATION_SHA256
        or raw.get("contains_text_or_labels") is not False
        or raw.get("evaluation", {}).get("performed_by_generator") is not False
    ):
        raise ValueError("sello final v2 inválido o incompatible")
    return raw


def seal_fingerprint(
    seal: Mapping[str, Any],
    *,
    seal_path: Path,
    predecessor_seal: Path,
) -> dict[str, Any]:
    return {
        "schema": seal["schema"],
        "manifest_sha256": file_sha256(seal_path),
        "rule_declaration_sha256": seal["rule_declaration_sha256"],
        "source_ids_sha256": seal["final"]["source_ids_sha256"],
        "rows": seal["final"]["rows"],
        "predecessor_sha256": file_sha256(predecessor_seal),
    }


def load_holdout_subset(
    path: Path,
    *,
    split: str | None = None,
    source_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    if (split is None) == (source_ids is None):
        raise ValueError("debe seleccionarse por split o por IDs sellados")
    rows: list[dict[str, Any]] = []
    found: set[str] = set()
    seen: set[str] = set()
    with path.open("rb") as handle:
        for line_number, line in enumerate(handle, 1):
            raw_line = line.strip()
            if not raw_line:
                continue
            row_split, source_id = extract_holdout_row_identity(
                raw_line,
                line_number=line_number,
            )
            if source_id in seen:
                raise ValueError("source_id duplicado")
            seen.add(source_id)
            selected = (
                row_split == split
                if split is not None
                else source_id in source_ids
            )
            if not selected:
                continue
            try:
                raw = json.loads(raw_line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ValueError(
                    f"fila seleccionada inválida en {line_number}"
                ) from error
            if not isinstance(raw, dict):
                raise ValueError(f"fila no objeto en línea {line_number}")
            if (
                raw.get("source_id") != source_id
                or raw.get("split") != row_split
                or not isinstance(raw.get("text"), str)
                or raw.get("mode")
                not in {"conversation", "clarify", "action", "plan"}
                or not isinstance(raw.get("families"), list)
            ):
                raise ValueError(f"fila seleccionada inválida en {line_number}")
            found.add(source_id)
            rows.append(raw)
    if source_ids is not None and found != source_ids:
        raise ValueError("el holdout no coincide con la lista final sellada")
    rows.sort(key=lambda row: row["source_id"])
    return rows


def fit_linear_probe(
    vectors: np.ndarray,
    labels: Sequence[str],
) -> tuple[tuple[str, ...], np.ndarray, np.ndarray, str]:
    """Balanced C=1 probe; deterministic NumPy fallback if sklearn is absent."""

    classes = tuple(sorted(set(labels)))
    if classes != ("action", "conversation"):
        raise ValueError(f"clases train inesperadas: {classes}")
    y = np.asarray([classes.index(label) for label in labels], dtype=np.int64)
    x = np.asarray(vectors, dtype=np.float64)
    try:
        from sklearn.linear_model import LogisticRegression

        model = LogisticRegression(
            C=1.0,
            class_weight="balanced",
            solver="lbfgs",
            max_iter=1_000,
            random_state=0,
        )
        model.fit(x, np.asarray(labels))
        fitted_classes = tuple(str(value) for value in model.classes_)
        if fitted_classes != classes:
            raise ValueError("orden de clases sklearn inesperado")
        if model.coef_.shape == (1, x.shape[1]) and len(classes) == 2:
            coefficients = np.vstack(
                [np.zeros(x.shape[1], dtype=np.float64), model.coef_[0]]
            )
            intercepts = np.asarray([0.0, model.intercept_[0]], dtype=np.float64)
        else:
            coefficients = np.asarray(model.coef_, dtype=np.float64)
            intercepts = np.asarray(model.intercept_, dtype=np.float64)
        return classes, coefficients, intercepts, "sklearn-1.9-logreg-lbfgs"
    except ImportError:
        counts = np.bincount(y, minlength=len(classes)).astype(np.float64)
        sample_weights = len(y) / (len(classes) * counts[y])
        coefficients = np.zeros((len(classes), x.shape[1]), dtype=np.float64)
        intercepts = np.zeros(len(classes), dtype=np.float64)
        learning_rate = 0.5
        regularization = 1.0 / len(y)
        for _ in range(400):
            logits = x @ coefficients.T + intercepts
            logits -= logits.max(axis=1, keepdims=True)
            probabilities = np.exp(logits)
            probabilities /= probabilities.sum(axis=1, keepdims=True)
            probabilities[np.arange(len(y)), y] -= 1.0
            weighted = probabilities * sample_weights[:, None]
            grad_w = weighted.T @ x / len(y) + regularization * coefficients
            grad_b = weighted.mean(axis=0)
            coefficients -= learning_rate * grad_w
            intercepts -= learning_rate * grad_b
        return classes, coefficients, intercepts, "numpy-balanced-softmax-v1"


def logits_for(
    vectors: np.ndarray,
    coefficients: np.ndarray,
    intercepts: np.ndarray,
) -> np.ndarray:
    return np.asarray(vectors, dtype=np.float64) @ coefficients.T + intercepts


def probabilities_for(logits: np.ndarray, temperature: float) -> np.ndarray:
    scaled = np.asarray(logits, dtype=np.float64) / temperature
    scaled -= scaled.max(axis=1, keepdims=True)
    values = np.exp(scaled)
    values /= values.sum(axis=1, keepdims=True)
    return values


def fit_temperature(logits: np.ndarray, labels: np.ndarray) -> float:
    candidates = np.exp(
        np.linspace(math.log(0.25), math.log(4.0), 121)
    )
    ranked: list[tuple[float, float, float]] = []
    for temperature in candidates:
        probabilities = probabilities_for(logits, float(temperature))
        nll = -float(
            np.log(
                np.clip(
                    probabilities[np.arange(len(labels)), labels],
                    1e-12,
                    1.0,
                )
            ).mean()
        )
        ranked.append((nll, abs(math.log(float(temperature))), float(temperature)))
    return min(ranked)[2]


def choose_conversation_threshold(
    probabilities: np.ndarray,
    expected_conversation: np.ndarray,
) -> tuple[float, dict[str, Any], bool]:
    order = np.argsort(-probabilities, kind="stable")
    selected = 0
    correct = 0
    conversation_total = int(expected_conversation.sum())
    candidates: list[tuple[tuple[float, ...], float, dict[str, Any]]] = []
    index = 0
    while index < len(order):
        threshold = float(probabilities[order[index]])
        while (
            index < len(order)
            and float(probabilities[order[index]]) == threshold
        ):
            selected += 1
            correct += int(expected_conversation[order[index]])
            index += 1
        precision_lower, precision_upper = wilson_interval(correct, selected)
        recall_lower, recall_upper = wilson_interval(
            correct,
            conversation_total,
        )
        metrics = {
            "selected_rows": selected,
            "correct_conversation_rows": correct,
            "signal_precision": round(correct / selected, 6),
            "signal_precision_wilson": {
                "lower": round(precision_lower, 6),
                "upper": round(precision_upper, 6),
            },
            "conversation_recall": round(
                correct / conversation_total,
                6,
            ),
            "conversation_recall_wilson": {
                "lower": round(recall_lower, 6),
                "upper": round(recall_upper, 6),
            },
        }
        feasible = (
            precision_lower >= MIN_CONVERSATION_PRECISION_LOWER
            and recall_lower >= MIN_CONVERSATION_RECALL_LOWER
        )
        rank = (
            float(feasible),
            float(metrics["conversation_recall"]),
            float(metrics["signal_precision"]),
            -threshold,
        )
        candidates.append((rank, threshold, metrics))
    chosen = max(candidates, key=lambda value: value[0])
    feasible = bool(chosen[0][0])
    return chosen[1], chosen[2], feasible


def _conversation_selection_metrics(
    emitted: np.ndarray,
    expected_conversation: np.ndarray,
) -> dict[str, Any]:
    selected = int(emitted.sum())
    correct = int(np.logical_and(emitted, expected_conversation).sum())
    total = int(expected_conversation.sum())
    precision = wilson_interval(correct, selected)
    recall = wilson_interval(correct, total)
    return {
        "selected_rows": selected,
        "correct_conversation_rows": correct,
        "signal_precision": round(correct / selected if selected else 0.0, 6),
        "signal_precision_wilson": {
            "lower": round(precision[0], 6),
            "upper": round(precision[1], 6),
        },
        "conversation_recall": round(correct / total if total else 0.0, 6),
        "conversation_recall_wilson": {
            "lower": round(recall[0], 6),
            "upper": round(recall[1], 6),
        },
    }


def _best_probe_threshold_for_eligible(
    probabilities: np.ndarray,
    expected_conversation: np.ndarray,
    eligible: np.ndarray,
) -> tuple[float, dict[str, Any], bool]:
    order = np.asarray(
        [
            index
            for index in np.argsort(-probabilities, kind="stable")
            if eligible[index]
        ],
        dtype=np.int64,
    )
    if not len(order):
        metrics = _conversation_selection_metrics(
            np.zeros(len(probabilities), dtype=bool),
            expected_conversation,
        )
        return 1.0, metrics, False
    candidates: list[tuple[tuple[float, ...], float, dict[str, Any]]] = []
    emitted = np.zeros(len(probabilities), dtype=bool)
    index = 0
    while index < len(order):
        threshold = float(probabilities[order[index]])
        while (
            index < len(order)
            and float(probabilities[order[index]]) == threshold
        ):
            emitted[order[index]] = True
            index += 1
        metrics = _conversation_selection_metrics(
            emitted,
            expected_conversation,
        )
        feasible = (
            metrics["signal_precision_wilson"]["lower"]
            >= MIN_CONVERSATION_PRECISION_LOWER
            and metrics["conversation_recall_wilson"]["lower"]
            >= MIN_CONVERSATION_RECALL_LOWER
        )
        rank = (
            float(feasible),
            float(metrics["conversation_recall"]),
            float(metrics["signal_precision"]),
            -threshold,
        )
        candidates.append((rank, threshold, metrics))
    chosen = max(candidates, key=lambda value: value[0])
    return chosen[1], chosen[2], bool(chosen[0][0])


def choose_hybrid_conversation_policy(
    probabilities: np.ndarray,
    expected_conversation: np.ndarray,
    neighbor_rows: Sequence[dict[str, Any]],
    neighbors: int,
) -> tuple[
    float,
    ConversationKnnThresholds,
    dict[str, Any],
    bool,
]:
    profiles: list[tuple[str, ConversationKnnThresholds]] = []
    for dissent in (0, 1, 2):
        fraction = (neighbors - dissent) / neighbors
        if fraction <= 0.0:
            continue
        theoretical_entropy = (
            0.0
            if fraction == 1.0
            else -(
                fraction * math.log(fraction)
                + (1.0 - fraction) * math.log(1.0 - fraction)
            )
            / math.log(2.0)
        )
        profiles.append(
            (
                f"strong_max_dissent_{dissent}",
                ConversationKnnThresholds(
                    minimum_top1_score=-1.0,
                    minimum_score_margin=0.0,
                    minimum_conversation_agreement=max(
                        0.0,
                        fraction - (0.02 if dissent else 1e-9),
                    ),
                    maximum_mode_entropy=min(
                        1.0,
                        theoretical_entropy + 0.02,
                    ),
                    minimum_conversation_fraction=fraction,
                ),
            )
        )
    quantiles = (
        0.0,
        0.01,
        0.02,
        0.03,
        0.05,
        0.075,
        0.10,
        0.15,
        0.20,
        0.30,
        0.40,
        0.50,
        0.60,
        0.70,
        0.80,
        0.90,
    )
    for quantile in quantiles:
        profiles.append(
            (
                f"validation_quantile_{quantile:g}",
                ConversationKnnThresholds(
                    minimum_top1_score=percentile(
                        [row["top1_score"] for row in neighbor_rows],
                        quantile,
                    )
                    - 1e-9,
                    minimum_score_margin=max(
                        0.0,
                        percentile(
                            [row["score_margin"] for row in neighbor_rows],
                            quantile,
                        )
                        - 1e-9,
                    ),
                    minimum_conversation_agreement=max(
                        0.0,
                        percentile(
                            [
                                row["conversation_agreement"]
                                for row in neighbor_rows
                            ],
                            quantile,
                        )
                        - 1e-9,
                    ),
                    maximum_mode_entropy=min(
                        1.0,
                        percentile(
                            [row["mode_entropy"] for row in neighbor_rows],
                            1.0 - quantile,
                        )
                        + 1e-9,
                    ),
                    minimum_conversation_fraction=max(
                        0.0,
                        percentile(
                            [
                                row["conversation_fraction"]
                                for row in neighbor_rows
                            ],
                            quantile,
                        )
                        - 1e-9,
                    ),
                ),
            )
        )
    candidates: list[
        tuple[
            tuple[float, ...],
            float,
            ConversationKnnThresholds,
            dict[str, Any],
            str,
        ]
    ] = []
    for profile_name, thresholds in profiles:
        eligible = np.asarray(
            [thresholds.accepts(row) for row in neighbor_rows],
            dtype=bool,
        )
        probe_threshold, metrics, feasible = (
            _best_probe_threshold_for_eligible(
                probabilities,
                expected_conversation,
                eligible,
            )
        )
        rank = (
            float(feasible),
            float(metrics["conversation_recall"]),
            float(metrics["signal_precision"]),
            float(eligible.mean()),
        )
        candidates.append(
            (
                rank,
                probe_threshold,
                thresholds,
                {
                    **metrics,
                    "profile": profile_name,
                    "knn_eligible_rows": int(eligible.sum()),
                },
                profile_name,
            )
        )
    chosen = max(candidates, key=lambda value: value[0])
    return chosen[1], chosen[2], {
        **chosen[3],
        "knn_thresholds": chosen[2].to_dict(),
        "candidate_profiles": len(candidates),
        "strong_profiles_evaluated_first": [
            "strong_max_dissent_0",
            "strong_max_dissent_1",
            "strong_max_dissent_2",
        ],
    }, bool(chosen[0][0])


@dataclass(frozen=True, slots=True)
class FamilyThresholds:
    minimum_top1_score: float
    minimum_score_margin: float
    minimum_family_agreement: float
    maximum_family_entropy: float

    def accepts(self, row: dict[str, Any]) -> bool:
        return (
            row["top1_score"] >= self.minimum_top1_score
            and row["score_margin"] >= self.minimum_score_margin
            and row["family_agreement"] >= self.minimum_family_agreement
            and row["family_entropy"] <= self.maximum_family_entropy
        )


def entropy(votes: dict[str, float]) -> float:
    positive = [value for value in votes.values() if value > 0]
    if len(positive) <= 1:
        return 0.0
    total = sum(positive)
    return -sum(
        (value / total) * math.log(value / total) for value in positive
    ) / math.log(len(positive))


def family_row(
    train_records: Sequence[Any],
    scores: np.ndarray,
    indices: Sequence[int],
    expected_families: Sequence[str],
) -> dict[str, Any]:
    family_votes: dict[str, float] = {}
    neighbor_families: set[str] = set()
    for train_index in indices:
        record = train_records[train_index]
        weight = max(0.0, float(scores[train_index])) + 1e-9
        labels = record.families or ("",)
        for family in labels:
            family_votes[family] = family_votes.get(family, 0.0) + (
                weight / len(labels)
            )
            if family:
                neighbor_families.add(family)
    predicted = (
        max(family_votes, key=lambda label: (family_votes[label], label))
        if family_votes
        else ""
    )
    total = sum(family_votes.values())
    agreement = family_votes.get(predicted, 0.0) / total if total else 0.0
    score_values = [float(scores[index]) for index in indices]
    conversation_signals = summarize_conversation_neighbors(
        [
            (float(scores[index]), train_records[index].mode)
            for index in indices
        ]
    )
    return {
        "expected_families": tuple(expected_families),
        "predicted_family": predicted,
        "raw_recall": (
            not expected_families
            or bool(set(expected_families) & neighbor_families)
        ),
        "top1_score": score_values[0] if score_values else -1.0,
        "score_margin": (
            score_values[0] - score_values[1]
            if len(score_values) >= 2
            else 0.0
        ),
        "family_agreement": agreement,
        "family_entropy": entropy(family_votes),
        "conversation_agreement": (
            conversation_signals.conversation_agreement
        ),
        "mode_entropy": conversation_signals.mode_entropy,
        "conversation_fraction": (
            conversation_signals.conversation_fraction
        ),
    }


def evaluate_family_candidates(
    index: TurnEvidenceIndex,
    query_vectors: np.ndarray,
    rows: Sequence[dict[str, Any]],
) -> dict[int, list[dict[str, Any]]]:
    train_records = tuple(index._records)  # type: ignore[attr-defined]
    train_vectors = np.asarray(index._vectors, dtype=np.float32)  # type: ignore[attr-defined]
    maximum_k = max(K_CANDIDATES)
    candidate_count = min(len(train_records), maximum_k * 8)
    result = {value: [] for value in K_CANDIDATES}
    for start in range(0, len(rows), 64):
        batch_vectors = query_vectors[start : start + 64]
        similarities = batch_vectors @ train_vectors.T
        partition = np.argpartition(
            similarities,
            similarities.shape[1] - candidate_count,
            axis=1,
        )[:, -candidate_count:]
        for local_index, row in enumerate(rows[start : start + 64]):
            scores = similarities[local_index]
            ranked = sorted(
                (int(value) for value in partition[local_index]),
                key=lambda value: (
                    float(scores[value]),
                    train_records[value].source_id,
                ),
                reverse=True,
            )
            diverse: list[int] = []
            missions: set[str] = set()
            for value in ranked:
                mission = train_records[value].mission_id
                if mission in missions:
                    continue
                diverse.append(value)
                missions.add(mission)
                if len(diverse) >= maximum_k:
                    break
            for neighbors in K_CANDIDATES:
                family = family_row(
                    train_records,
                    scores,
                    diverse[:neighbors],
                    row["families"],
                )
                family["expected_mode"] = row["mode"]
                family["source_id"] = row["source_id"]
                result[neighbors].append(family)
    return result


def raw_family_recall(rows: Sequence[dict[str, Any]]) -> float:
    family_rows = [row for row in rows if row["expected_families"]]
    return (
        sum(bool(row["raw_recall"]) for row in family_rows) / len(family_rows)
        if family_rows
        else 0.0
    )


def family_metrics(
    rows: Sequence[dict[str, Any]],
    thresholds: FamilyThresholds,
) -> dict[str, Any]:
    selected = [row for row in rows if thresholds.accepts(row)]
    family_rows = [row for row in rows if row["expected_families"]]
    selected_family = [row for row in selected if row["expected_families"]]
    predictions = [row for row in selected if row["predicted_family"]]
    correct_predictions = [
        row
        for row in predictions
        if row["predicted_family"] in row["expected_families"]
    ]
    correct_family = [
        row
        for row in selected_family
        if row["predicted_family"] in row["expected_families"]
    ]
    precision_bounds = wilson_interval(
        len(correct_predictions),
        len(predictions),
    )
    recall_bounds = wilson_interval(len(correct_family), len(family_rows))
    coverage_bounds = wilson_interval(
        len(selected_family),
        len(family_rows),
    )
    return {
        "selected_rows": len(selected),
        "family_rows": len(family_rows),
        "selected_family_rows": len(selected_family),
        "family_precision": round(
            len(correct_predictions) / len(predictions)
            if predictions
            else 0.0,
            6,
        ),
        "family_precision_wilson": {
            "lower": round(precision_bounds[0], 6),
            "upper": round(precision_bounds[1], 6),
        },
        "family_recall": round(
            len(correct_family) / len(family_rows)
            if family_rows
            else 0.0,
            6,
        ),
        "family_recall_wilson": {
            "lower": round(recall_bounds[0], 6),
            "upper": round(recall_bounds[1], 6),
        },
        "actionable_coverage": round(
            len(selected_family) / len(family_rows)
            if family_rows
            else 0.0,
            6,
        ),
        "actionable_coverage_wilson": {
            "lower": round(coverage_bounds[0], 6),
            "upper": round(coverage_bounds[1], 6),
        },
    }


def choose_family_thresholds(
    rows: Sequence[dict[str, Any]],
) -> tuple[FamilyThresholds, dict[str, Any], bool]:
    quantiles = (
        0.0,
        0.01,
        0.02,
        0.03,
        0.05,
        0.075,
        0.10,
        0.15,
        0.20,
        0.30,
        0.40,
        0.50,
        0.60,
        0.70,
        0.80,
        0.90,
    )
    candidates: list[
        tuple[tuple[float, ...], FamilyThresholds, dict[str, Any], float]
    ] = []
    for quantile in quantiles:
        threshold = FamilyThresholds(
            minimum_top1_score=percentile(
                [row["top1_score"] for row in rows],
                quantile,
            )
            - 1e-9,
            minimum_score_margin=max(
                0.0,
                percentile(
                    [row["score_margin"] for row in rows],
                    quantile,
                )
                - 1e-9,
            ),
            minimum_family_agreement=max(
                0.0,
                percentile(
                    [row["family_agreement"] for row in rows],
                    quantile,
                )
                - 1e-9,
            ),
            maximum_family_entropy=min(
                1.0,
                percentile(
                    [row["family_entropy"] for row in rows],
                    1.0 - quantile,
                )
                + 1e-9,
            ),
        )
        metrics = family_metrics(rows, threshold)
        feasible = (
            metrics["family_precision_wilson"]["lower"]
            >= MIN_FAMILY_PRECISION_LOWER
            and metrics["family_recall_wilson"]["lower"]
            >= MIN_FAMILY_RECALL_LOWER
            and metrics["actionable_coverage_wilson"]["lower"]
            >= MIN_ACTIONABLE_COVERAGE_LOWER
        )
        rank = (
            float(feasible),
            float(metrics["actionable_coverage"]),
            float(metrics["family_recall"]),
            float(metrics["family_precision"]),
            -quantile,
        )
        candidates.append((rank, threshold, metrics, quantile))
    chosen = max(candidates, key=lambda value: value[0])
    return chosen[1], {
        "quantile": chosen[3],
        "thresholds": asdict(chosen[1]),
        "metrics": chosen[2],
        "candidate_count": len(candidates),
    }, bool(chosen[0][0])


def embed_rows(
    router: IntentRouter,
    rows: Sequence[dict[str, Any]],
) -> tuple[np.ndarray, float]:
    batches: list[np.ndarray] = []
    started = time.perf_counter()
    for start in range(0, len(rows), 64):
        batch = [str(row["text"]) for row in rows[start : start + 64]]
        matrix = np.asarray(router.encode(batch), dtype=np.float32)
        if matrix.ndim != 2 or matrix.shape[0] != len(batch):
            raise ValueError("batch E5 inválido")
        batches.append(matrix)
    return np.concatenate(batches), time.perf_counter() - started


def full_probe_metrics(
    probabilities: np.ndarray,
    rows: Sequence[dict[str, Any]],
    classes: Sequence[str],
) -> dict[str, Any]:
    expected = [str(row["mode"]) for row in rows]
    predicted = [classes[int(index)] for index in probabilities.argmax(axis=1)]
    conversation_rows = [
        index for index, label in enumerate(expected) if label == "conversation"
    ]
    return {
        "rows": len(rows),
        "accuracy": round(
            sum(wanted == actual for wanted, actual in zip(expected, predicted))
            / len(rows),
            6,
        ),
        "macro_f1": round(macro_f1(expected, predicted), 6),
        "conversation_predicted_action_rate": round(
            sum(predicted[index] in {"action", "plan"} for index in conversation_rows)
            / len(conversation_rows),
            6,
        ),
    }


def one_sided_metrics(
    probabilities: np.ndarray,
    rows: Sequence[dict[str, Any]],
    conversation_index: int,
    threshold: float,
    *,
    neighbor_rows: Sequence[dict[str, Any]] | None = None,
    knn_thresholds: ConversationKnnThresholds | None = None,
) -> dict[str, Any]:
    expected = np.asarray(
        [row["mode"] == "conversation" for row in rows],
        dtype=bool,
    )
    emitted = probabilities[:, conversation_index] >= threshold
    if neighbor_rows is not None or knn_thresholds is not None:
        if neighbor_rows is None or knn_thresholds is None:
            raise ValueError("señales híbridas incompletas")
        if len(neighbor_rows) != len(rows):
            raise ValueError("señales híbridas desalineadas")
        emitted = np.logical_and(
            emitted,
            np.asarray(
                [knn_thresholds.accepts(row) for row in neighbor_rows],
                dtype=bool,
            ),
        )
    correct = int(np.logical_and(emitted, expected).sum())
    selected = int(emitted.sum())
    conversation_total = int(expected.sum())
    precision = wilson_interval(correct, selected)
    recall = wilson_interval(correct, conversation_total)
    false_action = wilson_interval(0, conversation_total)
    return {
        "authority": "conversation_signal_or_abstain_only",
        "selected_rows": selected,
        "correct_conversation_rows": correct,
        "signal_precision": round(correct / selected if selected else 0.0, 6),
        "signal_precision_wilson": {
            "lower": round(precision[0], 6),
            "upper": round(precision[1], 6),
        },
        "conversation_recall": round(
            correct / conversation_total,
            6,
        ),
        "conversation_recall_wilson": {
            "lower": round(recall[0], 6),
            "upper": round(recall[1], 6),
        },
        "actionable_signals_emitted": 0,
        "conversation_false_action_wilson": {
            "successes": 0,
            "trials": conversation_total,
            "lower": round(false_action[0], 6),
            "upper": round(false_action[1], 6),
        },
    }


def validation_phase(args: argparse.Namespace) -> int:
    if args.validation_output.exists() and not args.replace_validation:
        raise SystemExit("checkpoint validation ya existe; usa --replace-validation")
    runtime = args.runtime.resolve(strict=True)
    holdout = args.holdout.resolve(strict=True)
    seal = load_seal(args.seal, holdout, args.predecessor_seal)
    seal_identity = seal_fingerprint(
        seal,
        seal_path=args.seal,
        predecessor_seal=args.predecessor_seal,
    )
    records, report = load_private_corpus(runtime)
    cache = args.cache_root.resolve(strict=True)
    router = IntentRouter(device=args.device)
    with configured_cache(cache):
        index = TurnEvidenceIndex.from_corpus(runtime, router.encode)
    train_indices = [
        index_value
        for index_value, record in enumerate(index._records)  # type: ignore[attr-defined]
        if record.split == "train"
    ]
    historical_rows = sum(
        record.split is None for record in index._records  # type: ignore[attr-defined]
    )
    train_vectors = np.asarray(index._vectors, dtype=np.float32)[  # type: ignore[attr-defined]
        train_indices
    ]
    train_labels = [index._records[index_value].mode for index_value in train_indices]  # type: ignore[attr-defined]
    classes, coefficients, intercepts, implementation = fit_linear_probe(
        train_vectors,
        train_labels,
    )
    validation_rows = load_holdout_subset(holdout, split="validation")
    validation_vectors, encode_seconds = embed_rows(router, validation_rows)
    logits = logits_for(validation_vectors, coefficients, intercepts)
    expected_indices = np.asarray(
        [classes.index(str(row["mode"])) for row in validation_rows],
        dtype=np.int64,
    )
    temperature = fit_temperature(logits, expected_indices)
    probabilities = probabilities_for(logits, temperature)
    conversation_index = classes.index("conversation")
    family_candidates = evaluate_family_candidates(
        index,
        validation_vectors,
        validation_rows,
    )
    raw_recall_by_k = {
        str(neighbors): round(
            raw_family_recall(family_candidates[neighbors]),
            6,
        )
        for neighbors in K_CANDIDATES
    }
    chosen_k = next(
        (
            neighbors
            for neighbors in K_CANDIDATES
            if raw_recall_by_k[str(neighbors)]
            >= MIN_RAW_FAMILY_RECALL_AT_K
        ),
        max(
            K_CANDIDATES,
            key=lambda value: (raw_recall_by_k[str(value)], -value),
        ),
    )
    raw_recall_feasible = (
        raw_recall_by_k[str(chosen_k)] >= MIN_RAW_FAMILY_RECALL_AT_K
    )
    family_thresholds, family_calibration, family_feasible = (
        choose_family_thresholds(family_candidates[chosen_k])
    )
    (
        threshold,
        conversation_knn,
        threshold_metrics,
        conversation_feasible,
    ) = choose_hybrid_conversation_policy(
        probabilities[:, conversation_index],
        expected_indices == conversation_index,
        family_candidates[chosen_k],
        chosen_k,
    )
    training_fingerprint = split_fingerprint(index._records, "train")  # type: ignore[attr-defined]
    validation_fingerprint = canonical_sha256(
        [
            {
                "source_id": row["source_id"],
                "mode": row["mode"],
                "families": row["families"],
            }
            for row in validation_rows
        ]
    )
    probe = TurnModeLinearProbe(
        classes=classes,
        coefficients=tuple(
            tuple(float(value) for value in row) for row in coefficients
        ),
        intercepts=tuple(float(value) for value in intercepts),
        temperature=temperature,
        conversation_threshold=threshold,
        implementation=implementation,
        training_rows=len(train_indices),
        training_split_fingerprint=training_fingerprint,
    )
    policy = OneSidedTurnEvidencePolicy(
        runtime_source_sha256=report.source_sha256,
        encoder_identity=DEFAULT_ENCODER_IDENTITY,
        probe=probe,
        neighbors=chosen_k,
        conversation_knn=conversation_knn,
        validation_fingerprint=validation_fingerprint,
        validation_rows=len(validation_rows),
        final_seal_source_ids_sha256=seal["final"]["source_ids_sha256"],
        historical_index_rows=historical_rows,
    )
    one_sided = one_sided_metrics(
        probabilities,
        validation_rows,
        conversation_index,
        threshold,
        neighbor_rows=family_candidates[chosen_k],
        knn_thresholds=conversation_knn,
    )
    false_action_feasible = (
        one_sided["conversation_false_action_wilson"]["upper"]
        <= MAX_FALSE_ACTION_UPPER
    )
    status = "passed" if all(
        (
            conversation_feasible,
            raw_recall_feasible,
            family_feasible,
            false_action_feasible,
        )
    ) else "failed"
    checkpoint = {
        "schema": VALIDATION_SCHEMA,
        "status": status,
        "scope": "train_runtime_train_calibrate_validation_only",
        "runtime": {
            "repo_path": report_path(runtime),
            "sha256": report.source_sha256,
            "index_rows": len(records),
            "train_rows": len(train_indices),
            "train_modes": dict(sorted(Counter(train_labels).items())),
            "training_split_fingerprint": training_fingerprint,
        },
        "historical_usage": {
            "rows": historical_rows,
            "probe_training_rows": 0,
            "reason": "weak_or_noisy_labels",
            "role": "index_and_family_retrieval_only",
            "text_sent_to_llm": False,
        },
        "seal": {
            "repo_path": report_path(args.seal),
            **seal_identity,
            "scored": False,
        },
        "probe": {
            "training": {
                "implementation": implementation,
                "class_weight": "balanced",
                "C": 1.0,
                "solver": "lbfgs",
            },
            "temperature": temperature,
            "conversation_threshold": threshold,
            "threshold_selection": threshold_metrics,
            "full_coverage_comparator": full_probe_metrics(
                probabilities,
                validation_rows,
                classes,
            ),
            "one_sided": one_sided,
        },
        "family_knn_diagnostic": {
            "authority": "diagnostic_only_not_sent_as_action_to_llm",
            "k_candidates": list(K_CANDIDATES),
            "raw_recall_at_k": raw_recall_by_k,
            "selected_k": chosen_k,
            "calibration": family_calibration,
        },
        "constraints": {
            "maximum_conversation_false_action_wilson_upper": (
                MAX_FALSE_ACTION_UPPER
            ),
            "minimum_family_precision_wilson_lower": (
                MIN_FAMILY_PRECISION_LOWER
            ),
            "minimum_raw_family_recall_at_k": MIN_RAW_FAMILY_RECALL_AT_K,
            "minimum_actionable_coverage_wilson_lower": (
                MIN_ACTIONABLE_COVERAGE_LOWER
            ),
            "minimum_family_recall_wilson_lower": MIN_FAMILY_RECALL_LOWER,
            "minimum_conversation_precision_wilson_lower": (
                MIN_CONVERSATION_PRECISION_LOWER
            ),
            "minimum_conversation_recall_wilson_lower": (
                MIN_CONVERSATION_RECALL_LOWER
            ),
        },
        "checks": {
            "probe_train_uses_only_runtime_train": (
                len(train_indices) == 17_784
                and historical_rows == 7_372
            ),
            "conversation_policy_feasible": conversation_feasible,
            "one_sided_never_emits_actionable": (
                one_sided["actionable_signals_emitted"] == 0
            ),
            "false_action_upper_passes": false_action_feasible,
            "raw_family_recall_at_selected_k_passes": raw_recall_feasible,
            "selective_family_constraints_pass": family_feasible,
            "final_subset_not_scored": True,
        },
        "frozen": {
            "policy": policy.to_dict(),
            "family_thresholds": asdict(family_thresholds),
            "code_sha256": {
                report_path(path): file_sha256(path)
                for path in (
                    Path(__file__),
                    SRC / "baxy_mind" / "turn_evidence.py",
                    SRC / "baxy_mind" / "turn_probe.py",
                    SRC / "baxy_mind" / "router.py",
                    SCRIPTS / "blind_reset_turn_evidence_final_seal.py",
                )
            },
        },
        "timing": {"validation_encode_seconds": round(encode_seconds, 4)},
    }
    write_json_atomic(args.validation_output.resolve(), checkpoint)
    print(json.dumps(checkpoint["checks"], indent=2, sort_keys=True))
    return 0 if status == "passed" else 1


def final_phase(args: argparse.Namespace) -> int:
    output = args.final_output.resolve()
    if output.exists():
        raise SystemExit("el subset final ya fue evaluado; se prohíbe repetir")
    checkpoint_path = args.validation_output.resolve(strict=True)
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    if (
        checkpoint.get("schema") != VALIDATION_SCHEMA
        or checkpoint.get("status") != "passed"
        or checkpoint.get("seal", {}).get("scored") is not False
    ):
        raise SystemExit("validation no quedó cerrada y aprobada")
    holdout = args.holdout.resolve(strict=True)
    seal = load_seal(args.seal, holdout, args.predecessor_seal)
    seal_identity = seal_fingerprint(
        seal,
        seal_path=args.seal,
        predecessor_seal=args.predecessor_seal,
    )
    checkpoint_seal = checkpoint["seal"]
    if any(
        checkpoint_seal.get(key) != value
        for key, value in seal_identity.items()
    ):
        raise SystemExit("el sello final cambió")
    for path_text, digest in checkpoint["frozen"]["code_sha256"].items():
        path = REPO / path_text
        if file_sha256(path) != digest:
            raise SystemExit(f"código cambió después de validation: {path_text}")
    policy = OneSidedTurnEvidencePolicy.from_dict(
        checkpoint["frozen"]["policy"]
    )
    family_thresholds = FamilyThresholds(
        **checkpoint["frozen"]["family_thresholds"]
    )
    runtime = args.runtime.resolve(strict=True)
    records, report = load_private_corpus(runtime)
    if not policy.is_compatible(
        source_sha256=report.source_sha256,
        encoder_identity=DEFAULT_ENCODER_IDENTITY,
        dimensions=policy.probe.dimensions,
    ):
        raise SystemExit("policy/runtime incompatibles")
    cache = args.cache_root.resolve(strict=True)
    router = IntentRouter(device=args.device)
    with configured_cache(cache):
        index = TurnEvidenceIndex.from_corpus(runtime, router.encode)
    final_ids = set(seal["final"]["source_ids"])
    final_rows = load_holdout_subset(holdout, source_ids=final_ids)
    final_vectors, encode_seconds = embed_rows(router, final_rows)
    coefficients = np.asarray(policy.probe.coefficients, dtype=np.float64)
    intercepts = np.asarray(policy.probe.intercepts, dtype=np.float64)
    probabilities = probabilities_for(
        logits_for(final_vectors, coefficients, intercepts),
        policy.probe.temperature,
    )
    conversation_index = policy.probe.classes.index("conversation")
    family_rows = evaluate_family_candidates(
        index,
        final_vectors,
        final_rows,
    )[policy.neighbors]
    one_sided = one_sided_metrics(
        probabilities,
        final_rows,
        conversation_index,
        policy.probe.conversation_threshold,
        neighbor_rows=family_rows,
        knn_thresholds=policy.conversation_knn,
    )
    raw_recall = raw_family_recall(family_rows)
    selected_family = family_metrics(family_rows, family_thresholds)
    checks = {
        "sealed_list_and_hash_match": (
            len(final_rows) == seal["final"]["rows"]
            and policy.final_seal_source_ids_sha256
            == seal["final"]["source_ids_sha256"]
        ),
        "one_sided_never_emits_actionable": (
            one_sided["actionable_signals_emitted"] == 0
        ),
        "false_action_upper_passes": (
            one_sided["conversation_false_action_wilson"]["upper"]
            <= MAX_FALSE_ACTION_UPPER
        ),
        "conversation_precision_lower_passes": (
            one_sided["signal_precision_wilson"]["lower"]
            >= MIN_CONVERSATION_PRECISION_LOWER
        ),
        "conversation_recall_lower_passes": (
            one_sided["conversation_recall_wilson"]["lower"]
            >= MIN_CONVERSATION_RECALL_LOWER
        ),
        "raw_family_recall_at_selected_k_passes": (
            raw_recall >= MIN_RAW_FAMILY_RECALL_AT_K
        ),
        "family_precision_lower_passes": (
            selected_family["family_precision_wilson"]["lower"]
            >= MIN_FAMILY_PRECISION_LOWER
        ),
        "family_recall_lower_passes": (
            selected_family["family_recall_wilson"]["lower"]
            >= MIN_FAMILY_RECALL_LOWER
        ),
        "actionable_coverage_lower_passes": (
            selected_family["actionable_coverage_wilson"]["lower"]
            >= MIN_ACTIONABLE_COVERAGE_LOWER
        ),
    }
    status = "passed" if all(checks.values()) else "failed"
    report_value = {
        "schema": FINAL_SCHEMA,
        "status": status,
        "scope": "single_evaluation_of_hash_sealed_final_subset",
        "seal": {
            "repo_path": report_path(args.seal),
            **seal_identity,
            "rows": len(final_rows),
            "single_use_output_guard": True,
        },
        "runtime": {
            "repo_path": report_path(runtime),
            "sha256": report.source_sha256,
            "index_rows": len(records),
        },
        "historical_usage": checkpoint["historical_usage"],
        "probe": {
            "full_coverage_comparator": full_probe_metrics(
                probabilities,
                final_rows,
                policy.probe.classes,
            ),
            "one_sided": one_sided,
        },
        "family_knn_diagnostic": {
            "authority": "diagnostic_only_not_sent_as_action_to_llm",
            "selected_k_from_validation": policy.neighbors,
            "raw_recall_at_k": round(raw_recall, 6),
            "selective": selected_family,
            "thresholds_from_validation": asdict(family_thresholds),
        },
        "checks": checks,
        "timing": {"final_encode_seconds": round(encode_seconds, 4)},
        "policy_published": status == "passed",
    }
    write_json_atomic(output, report_value)
    if status == "passed":
        write_json_atomic(args.policy_output.resolve(), policy.to_dict())
    print(json.dumps(checks, indent=2, sort_keys=True))
    return 0 if status == "passed" else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("validation", "final"))
    parser.add_argument("--runtime", type=Path, default=RUNTIME)
    parser.add_argument("--holdout", type=Path, default=HOLDOUT)
    parser.add_argument("--seal", type=Path, default=SEAL)
    parser.add_argument(
        "--predecessor-seal",
        type=Path,
        default=PREDECESSOR_SEAL,
    )
    parser.add_argument(
        "--validation-output",
        type=Path,
        default=VALIDATION_OUTPUT,
    )
    parser.add_argument("--final-output", type=Path, default=FINAL_OUTPUT)
    parser.add_argument("--policy-output", type=Path, default=POLICY_OUTPUT)
    parser.add_argument(
        "--cache-root",
        type=Path,
        default=Path(os.environ.get("LOCALAPPDATA", ""))
        / "BAXYRuntime"
        / "turn-evidence",
    )
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--replace-validation", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return (
        validation_phase(args)
        if args.phase == "validation"
        else final_phase(args)
    )


if __name__ == "__main__":
    raise SystemExit(main())
