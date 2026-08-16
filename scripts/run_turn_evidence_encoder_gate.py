"""Measure the promoted turn-evidence corpus with BAXY's real E5 encoder.

This is a read-only product gate: it loads the same ``IntentRouter`` and
``TurnEvidenceIndex`` used by the mind, builds a new isolated cache, reloads
that cache, and exercises retrieval.  It never starts the core or dispatches
an operation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import sys
import threading
import time
import unicodedata
import uuid
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Sequence

import numpy as np


REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
DEFAULT_CORPUS = REPO / "tests" / "data" / "turn_evidence_runtime.v1.jsonl"
DEFAULT_HOLDOUT = (
    REPO / "tests" / "data" / "turn_evidence_public_holdout.v1.jsonl"
)
DEFAULT_OUTPUT = REPO / "artifacts" / "product" / "turn_evidence_encoder_gate.json"
DEFAULT_CACHE_ROOT = (
    REPO / "artifacts" / "product" / "turn_evidence_encoder_gate_cache"
)
DEFAULT_POLICY_OUTPUT = (
    REPO
    / "src"
    / "baxy_mind"
    / "data"
    / "turn_evidence_abstention_policy.v1.json"
)

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from baxy_mind.router import IntentRouter  # noqa: E402
from baxy_mind.turn_evidence import (  # noqa: E402
    CACHE_ENVIRONMENT_VARIABLE,
    TurnEvidenceAbstentionPolicy,
    TurnEvidenceConfidence,
    TurnEvidenceIndex,
    TurnEvidenceMatch,
    TurnEvidenceThresholds,
    load_private_corpus,
    summarize_match_confidence,
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def report_path(path: Path) -> str:
    """Use a portable identity in versionable evidence, never a user path."""

    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return resolved.name


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def percentile(values: Sequence[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = max(0.0, min(1.0, fraction)) * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def current_rss_bytes() -> int:
    try:
        import psutil

        return int(psutil.Process(os.getpid()).memory_info().rss)
    except (ImportError, OSError):
        return 0


class RssSampler:
    def __init__(self, interval_seconds: float = 0.05) -> None:
        self._interval = interval_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.start_bytes = 0
        self.peak_bytes = 0
        self.end_bytes = 0

    def __enter__(self) -> "RssSampler":
        self.start_bytes = current_rss_bytes()
        self.peak_bytes = self.start_bytes
        self._thread = threading.Thread(target=self._sample, daemon=True)
        self._thread.start()
        return self

    def _sample(self) -> None:
        while not self._stop.wait(self._interval):
            self.peak_bytes = max(self.peak_bytes, current_rss_bytes())

    def __exit__(self, *_: object) -> None:
        self.end_bytes = current_rss_bytes()
        self.peak_bytes = max(self.peak_bytes, self.end_bytes)
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1)

    def report(self) -> dict[str, float]:
        return {
            "start_mib": round(self.start_bytes / (1024**2), 3),
            "end_mib": round(self.end_bytes / (1024**2), 3),
            "peak_mib": round(self.peak_bytes / (1024**2), 3),
            "peak_delta_mib": round(
                max(0, self.peak_bytes - self.start_bytes) / (1024**2), 3
            ),
        }


class CountingEncoder:
    def __init__(self, encoder: Callable[[Sequence[str]], Any]) -> None:
        self._encoder = encoder
        self.calls = 0
        self.texts = 0

    def __call__(self, texts: Sequence[str]) -> Any:
        self.calls += 1
        self.texts += len(texts)
        return self._encoder(texts)


@contextmanager
def configured_cache(path: Path) -> Iterator[None]:
    previous = os.environ.get(CACHE_ENVIRONMENT_VARIABLE)
    os.environ[CACHE_ENVIRONMENT_VARIABLE] = str(path)
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(CACHE_ENVIRONMENT_VARIABLE, None)
        else:
            os.environ[CACHE_ENVIRONMENT_VARIABLE] = previous


def deterministic_queries(records: Sequence[Any], count: int) -> list[Any]:
    if count < 1:
        return []
    ranked = sorted(
        records,
        key=lambda record: hashlib.sha256(
            f"baxy-encoder-gate-v1\0{record.source_id}".encode("utf-8")
        ).digest(),
    )
    return ranked[: min(count, len(ranked))]


def _normalized_identity(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).casefold().split())


def load_holdout(path: Path, runtime_records: Sequence[Any]) -> list[dict[str, Any]]:
    runtime_texts = {_normalized_identity(record.text) for record in runtime_records}
    seen_texts: set[str] = set()
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"{path}:{line_number}: JSONL inválido") from error
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_number}: fila de holdout no objeto")
            text = row.get("text")
            mode = row.get("mode")
            families = row.get("families")
            if (
                row.get("schema") != "baxy.turn-evidence-record.v1"
                or not isinstance(text, str)
                or not text.strip()
                or mode not in {"conversation", "clarify", "action", "plan"}
                or not isinstance(families, list)
                or not all(isinstance(value, str) and value for value in families)
                or not isinstance(row.get("provenance"), dict)
            ):
                raise ValueError(f"{path}:{line_number}: fila de holdout inválida")
            identity = _normalized_identity(text)
            if identity in seen_texts:
                raise ValueError("el holdout contiene textos normalizados duplicados")
            if identity in runtime_texts:
                raise ValueError("se detectó fuga de texto runtime/holdout")
            seen_texts.add(identity)
            rows.append(row)
    return rows


def source_language(row: dict[str, Any]) -> str:
    parts = str(row.get("source_id") or "").split(":")
    return parts[1] if len(parts) >= 3 else "unknown"


def macro_f1(expected: Sequence[str], predicted: Sequence[str]) -> float:
    labels = sorted(set(expected) | set(predicted))
    if not labels:
        return 0.0
    scores: list[float] = []
    for label in labels:
        true_positive = sum(
            wanted == label and actual == label
            for wanted, actual in zip(expected, predicted, strict=True)
        )
        false_positive = sum(
            wanted != label and actual == label
            for wanted, actual in zip(expected, predicted, strict=True)
        )
        false_negative = sum(
            wanted == label and actual != label
            for wanted, actual in zip(expected, predicted, strict=True)
        )
        denominator = 2 * true_positive + false_positive + false_negative
        scores.append(2 * true_positive / denominator if denominator else 0.0)
    return statistics.fmean(scores)


def _weighted_winner(votes: dict[str, float]) -> str:
    return max(votes, key=lambda label: (votes[label], label)) if votes else ""


def wilson_interval(
    successes: int,
    trials: int,
    *,
    z: float = 1.6448536269514722,
) -> tuple[float, float]:
    """One-sided 95% Wilson bounds without an optional scipy dependency."""

    if trials < 0 or successes < 0 or successes > trials:
        raise ValueError("conteos inválidos para el intervalo de Wilson")
    if trials == 0:
        return 0.0, 1.0
    proportion = successes / trials
    z_squared = z * z
    denominator = 1.0 + z_squared / trials
    center = (proportion + z_squared / (2.0 * trials)) / denominator
    radius = (
        z
        * math.sqrt(
            proportion * (1.0 - proportion) / trials
            + z_squared / (4.0 * trials * trials)
        )
        / denominator
    )
    return max(0.0, center - radius), min(1.0, center + radius)


def summarize_knn_rows(rows: Sequence[dict[str, Any]], prefix: str) -> dict[str, Any]:
    if not rows:
        return {
            "rows": 0,
            "mode_accuracy": 0.0,
            "mode_macro_f1": 0.0,
            "family_accuracy": 0.0,
            "family_recall_at_k": 0.0,
            "conversation_false_action_rate": 0.0,
        }
    expected_modes = [str(row["expected_mode"]) for row in rows]
    predicted_modes = [str(row[f"{prefix}_mode"]) for row in rows]
    family_rows = [row for row in rows if row["expected_families"]]
    conversation_rows = [
        row for row in rows if row["expected_mode"] in {"conversation", "clarify"}
    ]
    family_correct_key = f"{prefix}_family_correct"
    family_recall_key = f"{prefix}_family_recall_at_k"
    return {
        "rows": len(rows),
        "mode_accuracy": round(
            sum(
                row[f"{prefix}_mode"] == row["expected_mode"]
                for row in rows
            )
            / len(rows),
            6,
        ),
        "mode_macro_f1": round(
            macro_f1(expected_modes, predicted_modes),
            6,
        ),
        "family_accuracy": round(
            sum(bool(row[family_correct_key]) for row in family_rows)
            / len(family_rows)
            if family_rows
            else 1.0,
            6,
        ),
        "family_recall_at_k": round(
            sum(bool(row[family_recall_key]) for row in family_rows)
            / len(family_rows)
            if family_rows
            else 1.0,
            6,
        ),
        "family_rows": len(family_rows),
        "conversation_false_action_rate": round(
            sum(
                row[f"{prefix}_mode"] in {"action", "plan"}
                for row in conversation_rows
            )
            / len(conversation_rows)
            if conversation_rows
            else 0.0,
            6,
        ),
        "conversation_rows": len(conversation_rows),
    }


def _confidence_from_row(row: dict[str, Any]) -> TurnEvidenceConfidence:
    raw = row.get("confidence")
    if not isinstance(raw, dict):
        raise ValueError("fila sin señales de confianza")
    return TurnEvidenceConfidence.from_dict(raw)


def summarize_selective_rows(
    rows: Sequence[dict[str, Any]],
    policy: TurnEvidenceAbstentionPolicy,
) -> dict[str, Any]:
    """Measure the advisory evidence retained by a frozen abstention policy."""

    selected = [
        row for row in rows if policy.accepts(_confidence_from_row(row))
    ]
    conversation_rows = [
        row
        for row in selected
        if row["expected_mode"] in {"conversation", "clarify"}
    ]
    false_action_rows = [
        row
        for row in conversation_rows
        if row["knn_mode"] in {"action", "plan"}
    ]
    actionable_rows = [
        row
        for row in rows
        if row["expected_mode"] in {"action", "plan"}
    ]
    selected_actionable_rows = [
        row
        for row in selected
        if row["expected_mode"] in {"action", "plan"}
    ]
    family_rows = [row for row in rows if row["expected_families"]]
    selected_family_rows = [
        row for row in selected if row["expected_families"]
    ]
    family_predictions = [
        row for row in selected if bool(row["knn_family"])
    ]
    correct_family_predictions = [
        row
        for row in family_predictions
        if row["knn_family"] in row["expected_families"]
    ]
    correct_family_rows = [
        row
        for row in selected_family_rows
        if row["knn_family"] in row["expected_families"]
    ]
    correct_modes = sum(
        row["knn_mode"] == row["expected_mode"] for row in selected
    )
    coverage_lower, coverage_upper = wilson_interval(
        len(selected),
        len(rows),
    )
    actionable_coverage_lower, actionable_coverage_upper = wilson_interval(
        len(selected_actionable_rows),
        len(actionable_rows),
    )
    false_action_lower, false_action_upper = wilson_interval(
        len(false_action_rows),
        len(conversation_rows),
    )
    family_precision_lower, family_precision_upper = wilson_interval(
        len(correct_family_predictions),
        len(family_predictions),
    )
    family_recall_lower, family_recall_upper = wilson_interval(
        len(correct_family_rows),
        len(family_rows),
    )
    return {
        "rows": len(rows),
        "selected_rows": len(selected),
        "abstained_rows": len(rows) - len(selected),
        "coverage": round(len(selected) / len(rows) if rows else 0.0, 6),
        "coverage_wilson": {
            "lower": round(coverage_lower, 6),
            "upper": round(coverage_upper, 6),
        },
        "mode_accuracy_on_selected": round(
            correct_modes / len(selected) if selected else 0.0,
            6,
        ),
        "actionable_rows": len(actionable_rows),
        "selected_actionable_rows": len(selected_actionable_rows),
        "actionable_coverage": round(
            len(selected_actionable_rows) / len(actionable_rows)
            if actionable_rows
            else 0.0,
            6,
        ),
        "actionable_coverage_wilson": {
            "lower": round(actionable_coverage_lower, 6),
            "upper": round(actionable_coverage_upper, 6),
        },
        "conversation_selected_rows": len(conversation_rows),
        "conversation_false_action_rows": len(false_action_rows),
        "conversation_false_action_rate_on_selected": round(
            len(false_action_rows) / len(conversation_rows)
            if conversation_rows
            else 0.0,
            6,
        ),
        "conversation_false_action_wilson": {
            "lower": round(false_action_lower, 6),
            "upper": round(false_action_upper, 6),
        },
        "family_rows": len(family_rows),
        "selected_family_rows": len(selected_family_rows),
        "family_predictions": len(family_predictions),
        "correct_family_predictions": len(correct_family_predictions),
        "family_precision": round(
            len(correct_family_predictions) / len(family_predictions)
            if family_predictions
            else 0.0,
            6,
        ),
        "family_precision_wilson": {
            "lower": round(family_precision_lower, 6),
            "upper": round(family_precision_upper, 6),
        },
        "family_recall": round(
            len(correct_family_rows) / len(family_rows)
            if family_rows
            else 0.0,
            6,
        ),
        "family_recall_wilson": {
            "lower": round(family_recall_lower, 6),
            "upper": round(family_recall_upper, 6),
        },
    }


def _derived_thresholds(
    rows: Sequence[dict[str, Any]],
    quantile: float,
) -> TurnEvidenceThresholds:
    """Derive one monotone profile from observed, unlabeled confidence signals."""

    if not rows:
        return TurnEvidenceThresholds.permissive()
    confidence = [_confidence_from_row(row) for row in rows]
    epsilon = 1e-9
    return TurnEvidenceThresholds(
        minimum_top1_score=percentile(
            [item.top1_score for item in confidence],
            quantile,
        )
        - epsilon,
        minimum_score_margin=max(
            0.0,
            percentile(
                [item.score_margin for item in confidence],
                quantile,
            )
            - epsilon,
        ),
        minimum_mode_agreement=max(
            0.0,
            percentile(
                [item.mode_agreement for item in confidence],
                quantile,
            )
            - epsilon,
        ),
        maximum_mode_entropy=min(
            1.0,
            percentile(
                [item.mode_entropy for item in confidence],
                1.0 - quantile,
            )
            + epsilon,
        ),
        minimum_family_agreement=max(
            0.0,
            percentile(
                [item.family_agreement for item in confidence],
                quantile,
            )
            - epsilon,
        ),
        maximum_family_entropy=min(
            1.0,
            percentile(
                [item.family_entropy for item in confidence],
                1.0 - quantile,
            )
            + epsilon,
        ),
    )


def _calibration_fingerprint(rows: Sequence[dict[str, Any]]) -> str:
    payload = [
        {
            "source_id": row["source_id"],
            "expected_mode": row["expected_mode"],
            "expected_families": list(row["expected_families"]),
            "confidence": row["confidence"],
        }
        for row in sorted(rows, key=lambda value: str(value["source_id"]))
    ]
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _constraint_failures(
    metrics: dict[str, Any],
    *,
    maximum_conversation_false_action_upper: float,
    minimum_family_precision_lower: float,
    minimum_family_recall_lower: float,
    minimum_actionable_coverage_lower: float,
) -> list[str]:
    failures: list[str] = []
    if (
        metrics["conversation_false_action_wilson"]["upper"]
        > maximum_conversation_false_action_upper
    ):
        failures.append("conversation_false_action_upper")
    if (
        metrics["family_precision_wilson"]["lower"]
        < minimum_family_precision_lower
    ):
        failures.append("family_precision_lower")
    if metrics["family_recall_wilson"]["lower"] < minimum_family_recall_lower:
        failures.append("family_recall_lower")
    if (
        metrics["actionable_coverage_wilson"]["lower"]
        < minimum_actionable_coverage_lower
    ):
        failures.append("actionable_coverage_lower")
    return failures


def calibrate_abstention_policy(
    validation_rows: Sequence[dict[str, Any]],
    *,
    runtime_source_sha256: str,
    encoder_identity: str,
    neighbors: int,
    maximum_conversation_false_action_upper: float,
    minimum_family_precision_lower: float,
    minimum_family_recall_lower: float,
    minimum_actionable_coverage_lower: float,
) -> tuple[TurnEvidenceAbstentionPolicy, dict[str, Any]]:
    """Fit only on validation via a deterministic monotone quantile sweep."""

    if not validation_rows or any(
        row.get("split") != "validation" for row in validation_rows
    ):
        raise ValueError("la calibración acepta exclusivamente filas validation")
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
    actionable_rows = [
        row
        for row in validation_rows
        if row["knn_mode"] in {"action", "plan"}
    ]
    conversational_rows = [
        row
        for row in validation_rows
        if row["knn_mode"] not in {"action", "plan"}
    ]
    actionable_profiles = {
        quantile: _derived_thresholds(actionable_rows, quantile)
        for quantile in quantiles
    }
    conversational_profiles = {
        quantile: _derived_thresholds(conversational_rows, quantile)
        for quantile in quantiles
    }
    fingerprint = _calibration_fingerprint(validation_rows)
    candidates: list[
        tuple[
            TurnEvidenceAbstentionPolicy,
            dict[str, Any],
            float,
            float,
            list[str],
        ]
    ] = []
    for actionable_quantile in quantiles:
        for conversational_quantile in quantiles:
            policy = TurnEvidenceAbstentionPolicy(
                runtime_source_sha256=runtime_source_sha256,
                encoder_identity=encoder_identity,
                neighbors=neighbors,
                actionable=actionable_profiles[actionable_quantile],
                conversational=conversational_profiles[
                    conversational_quantile
                ],
                calibration_fingerprint=fingerprint,
                calibration_rows=len(validation_rows),
            )
            metrics = summarize_selective_rows(validation_rows, policy)
            failures = _constraint_failures(
                metrics,
                maximum_conversation_false_action_upper=(
                    maximum_conversation_false_action_upper
                ),
                minimum_family_precision_lower=minimum_family_precision_lower,
                minimum_family_recall_lower=minimum_family_recall_lower,
                minimum_actionable_coverage_lower=(
                    minimum_actionable_coverage_lower
                ),
            )
            candidates.append(
                (
                    policy,
                    metrics,
                    actionable_quantile,
                    conversational_quantile,
                    failures,
                )
            )

    feasible = [candidate for candidate in candidates if not candidate[4]]
    pool = feasible or candidates

    def rank_candidate(
        candidate: tuple[
            TurnEvidenceAbstentionPolicy,
            dict[str, Any],
            float,
            float,
            list[str],
        ],
    ) -> tuple[float, ...]:
        _, metrics, actionable_quantile, conversational_quantile, failures = candidate
        constraint_penalty = -float(len(failures))
        if feasible:
            constraint_penalty = 0.0
        return (
            constraint_penalty,
            float(metrics["coverage"]),
            float(metrics["family_recall"]),
            float(metrics["family_precision"]),
            -float(
                metrics["conversation_false_action_wilson"]["upper"]
            ),
            -actionable_quantile,
            -conversational_quantile,
        )

    chosen = max(pool, key=rank_candidate)
    policy, metrics, actionable_quantile, conversational_quantile, failures = chosen
    return policy, {
        "algorithm": "validation_monotone_quantile_grid_v1",
        "fit_split": "validation",
        "rows": len(validation_rows),
        "fingerprint_sha256": fingerprint,
        "candidate_count": len(candidates),
        "feasible_candidate_count": len(feasible),
        "feasible": not failures,
        "selected_quantiles": {
            "actionable": actionable_quantile,
            "conversational": conversational_quantile,
        },
        "constraints": {
            "maximum_conversation_false_action_wilson_upper": (
                maximum_conversation_false_action_upper
            ),
            "minimum_family_precision_wilson_lower": (
                minimum_family_precision_lower
            ),
            "minimum_family_recall_wilson_lower": minimum_family_recall_lower,
            "minimum_actionable_coverage_wilson_lower": (
                minimum_actionable_coverage_lower
            ),
        },
        "metrics": metrics,
        "constraint_failures": failures,
        "policy": policy.to_dict(),
    }


def evaluate_holdout_knn(
    index: TurnEvidenceIndex,
    holdout: Sequence[dict[str, Any]],
    encoder: Callable[[Sequence[str]], Any],
    *,
    batch_size: int,
    neighbors: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Batch exact cosine kNN over the same normalized vectors as retrieval."""

    # This gate intentionally inspects the immutable in-memory diagnostic
    # representation so 9k queries can be evaluated in bounded matrix batches;
    # calling ``search`` once per row would repeat 9k model invocations.
    train_records = tuple(index._records)  # type: ignore[attr-defined]
    train_vectors = np.asarray(index._vectors, dtype=np.float32)  # type: ignore[attr-defined]
    mode_prior = Counter(record.mode for record in train_records)
    family_prior: Counter[str] = Counter(
        family for record in train_records for family in record.families
    )
    prior_mode = _weighted_winner(
        {label: float(count) for label, count in mode_prior.items()}
    )
    prior_family = _weighted_winner(
        {label: float(count) for label, count in family_prior.items()}
    )
    results: list[dict[str, Any]] = []
    candidate_count = min(len(train_records), max(neighbors * 8, 32))
    for start in range(0, len(holdout), batch_size):
        batch = holdout[start : start + batch_size]
        queries = np.asarray(
            encoder([str(row["text"]) for row in batch]),
            dtype=np.float32,
        )
        if (
            queries.ndim != 2
            or queries.shape != (len(batch), train_vectors.shape[1])
            or not np.isfinite(queries).all()
        ):
            raise ValueError("el encoder devolvió un batch de holdout inválido")
        similarities = queries @ train_vectors.T
        partition = np.argpartition(
            similarities,
            similarities.shape[1] - candidate_count,
            axis=1,
        )[:, -candidate_count:]
        for batch_index, row in enumerate(batch):
            ranked = sorted(
                (int(value) for value in partition[batch_index]),
                key=lambda index_value: (
                    float(similarities[batch_index, index_value]),
                    train_records[index_value].source_id,
                ),
                reverse=True,
            )
            selected: list[int] = []
            seen_missions: set[str] = set()
            for train_index in ranked:
                mission_id = train_records[train_index].mission_id
                if mission_id in seen_missions:
                    continue
                selected.append(train_index)
                seen_missions.add(mission_id)
                if len(selected) >= neighbors:
                    break
            neighbor_families: set[str] = set()
            for train_index in selected:
                record = train_records[train_index]
                for family in record.families:
                    neighbor_families.add(family)
            expected_families = tuple(str(value) for value in row["families"])
            matches = [
                TurnEvidenceMatch(
                    record=train_records[train_index],
                    score=float(similarities[batch_index, train_index]),
                    candidate_family_match=False,
                )
                for train_index in selected
            ]
            confidence = summarize_match_confidence(matches)
            predicted_family = confidence.predicted_family
            results.append(
                {
                    "source_id": str(row["source_id"]),
                    "expected_mode": str(row["mode"]),
                    "expected_families": expected_families,
                    "knn_mode": confidence.predicted_mode,
                    "knn_family": predicted_family,
                    "knn_family_correct": (
                        not expected_families
                        or predicted_family in expected_families
                    ),
                    "knn_family_recall_at_k": (
                        not expected_families
                        or bool(set(expected_families) & neighbor_families)
                    ),
                    "prior_mode": prior_mode,
                    "prior_family": prior_family,
                    "prior_family_correct": (
                        not expected_families or prior_family in expected_families
                    ),
                    "prior_family_recall_at_k": (
                        not expected_families or prior_family in expected_families
                    ),
                    "split": str(row.get("split") or "unknown"),
                    "language": source_language(row),
                    "dataset": str(
                        (row.get("provenance") or {}).get("dataset") or "unknown"
                    ),
                    "top_score": (
                        round(
                            float(similarities[batch_index, selected[0]]),
                            6,
                        )
                        if selected
                        else 0.0
                    ),
                    "confidence": confidence.to_dict(),
                }
            )
    overall_knn = summarize_knn_rows(results, "knn")
    overall_prior = summarize_knn_rows(results, "prior")
    slices: dict[str, dict[str, Any]] = {}
    for dimension in ("split", "language", "dataset"):
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for result in results:
            groups[str(result[dimension])].append(result)
        slices[dimension] = {
            value: {
                "knn": summarize_knn_rows(group_rows, "knn"),
                "prior": summarize_knn_rows(group_rows, "prior"),
            }
            for value, group_rows in sorted(groups.items())
        }
    summary = {
        "rows": len(results),
        "neighbors": neighbors,
        "batch_size": batch_size,
        "prior": {
            "mode": prior_mode,
            "family": prior_family,
            **overall_prior,
        },
        "knn": overall_knn,
        "full_coverage_knn": overall_knn,
        "delta": {
            "mode_accuracy": round(
                overall_knn["mode_accuracy"] - overall_prior["mode_accuracy"],
                6,
            ),
            "mode_macro_f1": round(
                overall_knn["mode_macro_f1"] - overall_prior["mode_macro_f1"],
                6,
            ),
            "family_accuracy": round(
                overall_knn["family_accuracy"] - overall_prior["family_accuracy"],
                6,
            ),
            "conversation_false_action_rate": round(
                overall_knn["conversation_false_action_rate"]
                - overall_prior["conversation_false_action_rate"],
                6,
            ),
        },
        "mean_top_score": round(
            statistics.fmean(result["top_score"] for result in results)
            if results
            else 0.0,
            6,
        ),
        "slices": slices,
    }
    return results, summary


def matrix_finiteness(path: Path, batch_rows: int = 4096) -> tuple[bool, tuple[int, ...]]:
    matrix = np.load(path, mmap_mode="r", allow_pickle=False)
    shape = tuple(int(value) for value in matrix.shape)
    if matrix.ndim != 2 or matrix.shape[0] < 1 or matrix.shape[1] < 1:
        return False, shape
    for start in range(0, matrix.shape[0], batch_rows):
        if not np.isfinite(matrix[start : start + batch_rows]).all():
            return False, shape
    return True, shape


def run_gate(args: argparse.Namespace) -> dict[str, Any]:
    corpus = args.corpus.resolve(strict=True)
    holdout_path = args.holdout.resolve(strict=True)
    records, corpus_report = load_private_corpus(corpus)
    holdout = load_holdout(holdout_path, records)
    corpus_hash = file_sha256(corpus)
    run_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "-"
        + uuid.uuid4().hex[:8]
    )
    print(f"run_id={run_id}", flush=True)
    cache_dir = (
        args.cache_root.resolve()
        if args.reuse_cache or args.migrate_cache
        else args.cache_root.resolve() / run_id
    )
    cache_dir.mkdir(
        parents=True,
        exist_ok=args.reuse_cache or args.migrate_cache,
    )

    started = time.perf_counter()
    rss_before = current_rss_bytes()
    encoder_started = time.perf_counter()
    with RssSampler() as encoder_rss:
        router = IntentRouter(device=args.device)
    encoder_seconds = time.perf_counter() - encoder_started

    probe = np.asarray(router.encode([records[0].text]), dtype=np.float32)
    probe_finite = bool(
        probe.ndim == 2
        and probe.shape[0] == 1
        and probe.shape[1] > 0
        and np.isfinite(probe).all()
    )
    dimensions = int(probe.shape[1]) if probe.ndim == 2 else 0

    cold_encoder = CountingEncoder(router.encode)
    cold_started = time.perf_counter()
    with configured_cache(cache_dir), RssSampler() as cold_rss:
        cold_index = TurnEvidenceIndex.from_corpus(corpus, cold_encoder)
    cold_seconds = time.perf_counter() - cold_started

    warm_encoder = CountingEncoder(router.encode)
    warm_started = time.perf_counter()
    with configured_cache(cache_dir), RssSampler() as warm_rss:
        warm_index = TurnEvidenceIndex.from_corpus(corpus, warm_encoder)
    warm_seconds = time.perf_counter() - warm_started

    metadata_files = sorted(cache_dir.glob("*.json"))
    matching_metadata: list[Path] = []
    for metadata_path in metadata_files:
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (
            metadata.get("source_sha256") == corpus_hash
            and metadata.get("encoder_identity") == warm_index.encoder_identity
            and metadata_path.with_suffix(".npy").is_file()
        ):
            matching_metadata.append(metadata_path)
    vector_files = [path.with_suffix(".npy") for path in matching_metadata]
    vectors_finite = False
    vector_shape: tuple[int, ...] = ()
    if len(vector_files) == 1:
        vectors_finite, vector_shape = matrix_finiteness(vector_files[0])

    holdout_encoder = CountingEncoder(router.encode)
    holdout_started = time.perf_counter()
    with RssSampler() as holdout_rss:
        holdout_rows, holdout_summary = evaluate_holdout_knn(
            warm_index,
            holdout,
            holdout_encoder,
            batch_size=args.holdout_batch_size,
            neighbors=args.neighbors,
        )
    holdout_seconds = time.perf_counter() - holdout_started

    validation_rows = [
        row for row in holdout_rows if row["split"] == "validation"
    ]
    test_rows = [row for row in holdout_rows if row["split"] == "test"]
    policy, calibration = calibrate_abstention_policy(
        validation_rows,
        runtime_source_sha256=corpus_hash,
        encoder_identity=warm_index.encoder_identity,
        neighbors=args.neighbors,
        maximum_conversation_false_action_upper=(
            args.maximum_conversation_false_action_upper
        ),
        minimum_family_precision_lower=args.minimum_family_precision_lower,
        minimum_family_recall_lower=args.minimum_family_recall_lower,
        minimum_actionable_coverage_lower=(
            args.minimum_actionable_coverage_lower
        ),
    )
    test_selective = summarize_selective_rows(test_rows, policy)
    full_coverage_policy = TurnEvidenceAbstentionPolicy.permissive(
        runtime_source_sha256=corpus_hash,
        encoder_identity=warm_index.encoder_identity,
        neighbors=args.neighbors,
        calibration_fingerprint="full-coverage-diagnostic-baseline",
        calibration_rows=0,
    )
    full_coverage_validation = summarize_selective_rows(
        validation_rows,
        full_coverage_policy,
    )
    full_coverage_test = summarize_selective_rows(
        test_rows,
        full_coverage_policy,
    )
    validation_full_knn = summarize_knn_rows(validation_rows, "knn")
    test_full_knn = summarize_knn_rows(test_rows, "knn")
    test_constraint_failures = _constraint_failures(
        test_selective,
        maximum_conversation_false_action_upper=(
            args.maximum_conversation_false_action_upper
        ),
        minimum_family_precision_lower=args.minimum_family_precision_lower,
        minimum_family_recall_lower=args.minimum_family_recall_lower,
        minimum_actionable_coverage_lower=(
            args.minimum_actionable_coverage_lower
        ),
    )

    query_seconds: list[float] = []
    query_counts: list[int] = []
    query_encoder = CountingEncoder(router.encode)
    with RssSampler() as query_rss:
        for record in deterministic_queries(records, args.query_count):
            candidates = [f"{family}.gate_probe" for family in record.families]
            before = time.perf_counter()
            cards = warm_index.retrieve(
                record.text,
                query_encoder,
                candidates,
                policy=policy,
                limit=args.retrieval_limit,
            )
            query_seconds.append(time.perf_counter() - before)
            query_counts.append(len(cards))

    cache_metadata_omits_text = False
    if len(matching_metadata) == 1:
        try:
            cache_payload = json.loads(
                matching_metadata[0].read_text(encoding="utf-8")
            )
            cached_records = cache_payload.get("records")
            cache_metadata_omits_text = bool(cached_records) and all(
                isinstance(item, dict) and "text" not in item
                for item in cached_records
            )
        except (OSError, json.JSONDecodeError):
            cache_metadata_omits_text = False

    required_batches = math.ceil(len(records) / 256)
    if args.reuse_cache:
        cold_cache_check = cold_encoder.calls == 0
        cold_cache_check_name = "reused_cache_without_reencoding"
        cold_mode = "cache_reuse"
    elif args.migrate_cache:
        cold_cache_check = (
            (cold_encoder.calls == 0 and cold_encoder.texts == 0)
            or (
                cold_encoder.texts == len(records)
                and cold_encoder.calls == required_batches
            )
        )
        cold_cache_check_name = "cache_reused_or_migrated_exactly_once"
        cold_mode = (
            "cache_reuse"
            if cold_encoder.calls == 0
            else "schema_migration_rebuild"
        )
    else:
        cold_cache_check = (
            cold_encoder.texts == len(records)
            and cold_encoder.calls == required_batches
        )
        cold_cache_check_name = "cold_encoded_every_row_once"
        cold_mode = "isolated_cold_build"
    checks = {
        "accepted_rows_at_least_minimum": len(records) >= args.minimum_rows,
        "holdout_rows_at_least_minimum": (
            len(holdout) >= args.minimum_holdout_rows
        ),
        "cold_index_matches_corpus": cold_index.count == len(records),
        "warm_index_matches_corpus": warm_index.count == len(records),
        "real_encoder_dimensions_positive": dimensions > 0,
        "probe_is_finite": probe_finite,
        "cached_vectors_are_finite": vectors_finite,
        "cached_vector_shape_matches": vector_shape == (len(records), dimensions),
        cold_cache_check_name: cold_cache_check,
        "warm_load_used_cache": warm_encoder.calls == 0 and warm_encoder.texts == 0,
        "cache_has_one_matching_atomic_pair": (
            len(vector_files) == 1 and len(matching_metadata) == 1
        ),
        "cache_metadata_omits_source_text": cache_metadata_omits_text,
        "queries_apply_frozen_abstention_policy": (
            bool(query_counts)
            and (
                sum(count > 0 for count in query_counts) / len(query_counts)
                >= args.minimum_actionable_coverage_lower
            )
        ),
        "evaluated_every_holdout_row": holdout_summary["rows"] == len(holdout),
        "calibration_uses_validation_only": (
            bool(validation_rows)
            and len(validation_rows) + len(test_rows) == len(holdout_rows)
            and calibration["fit_split"] == "validation"
        ),
        "calibration_found_feasible_policy": calibration["feasible"],
        "test_was_not_used_for_calibration": (
            bool(test_rows)
            and calibration["rows"] == len(validation_rows)
            and calibration["fingerprint_sha256"]
            == _calibration_fingerprint(validation_rows)
        ),
        "frozen_policy_matches_runtime_and_encoder": policy.is_compatible(
            source_sha256=warm_index.report.source_sha256,
            encoder_identity=warm_index.encoder_identity,
        ),
        "test_selective_constraints_pass": not test_constraint_failures,
        "validation_raw_family_recall_at_k_passes": (
            validation_full_knn["family_recall_at_k"]
            >= args.minimum_raw_family_recall_at_k
        ),
        "test_raw_family_recall_at_k_passes": (
            test_full_knn["family_recall_at_k"]
            >= args.minimum_raw_family_recall_at_k
        ),
        "selective_test_false_action_not_worse_than_full_knn": (
            test_selective["conversation_false_action_rate_on_selected"]
            <= full_coverage_test[
                "conversation_false_action_rate_on_selected"
            ]
        ),
        "knn_mode_signal_beats_prior": (
            holdout_summary["delta"]["mode_accuracy"] > 0
            and holdout_summary["delta"]["mode_macro_f1"] > 0
        ),
        "knn_family_signal_beats_prior": (
            holdout_summary["delta"]["family_accuracy"] > 0
        ),
        "holdout_slices_reported": all(
            holdout_summary["slices"].get(dimension)
            for dimension in ("split", "language", "dataset")
        ),
    }
    status = "passed" if all(checks.values()) else "failed"
    report = {
        "schema": "baxy.turn-evidence-encoder-gate.v2",
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "scope": (
            "real_multilingual_e5_cache_selective_calibration_and_heldout_test"
        ),
        "corpus": {
            "path": report_path(corpus),
            "sha256": corpus_hash,
            "source_rows": corpus_report.source_rows,
            "accepted_rows": len(records),
            "minimum_rows": args.minimum_rows,
        },
        "holdout": {
            "path": report_path(holdout_path),
            "sha256": file_sha256(holdout_path),
            "rows": len(holdout),
            "minimum_rows": args.minimum_holdout_rows,
            "normalized_text_overlap": 0,
        },
        "encoder": {
            "implementation": "baxy_mind.router.IntentRouter",
            "model": "intfloat/multilingual-e5-small",
            "device": args.device,
            "startup_seconds": round(encoder_seconds, 4),
            "dimensions": dimensions,
            "probe_finite": probe_finite,
            "rss": encoder_rss.report(),
        },
        "cold_build": {
            "mode": cold_mode,
            "seconds": round(cold_seconds, 4),
            "encoder_calls": cold_encoder.calls,
            "encoded_texts": cold_encoder.texts,
            "rows_per_second": round(
                len(records) / cold_seconds if cold_seconds else 0.0, 3
            ),
            "rss": cold_rss.report(),
        },
        "warm_cache": {
            "seconds": round(warm_seconds, 4),
            "encoder_calls": warm_encoder.calls,
            "encoded_texts": warm_encoder.texts,
            "cache_directory": report_path(cache_dir),
            "metadata_files": [path.name for path in metadata_files],
            "matching_metadata_files": [
                path.name for path in matching_metadata
            ],
            "vector_files": [path.name for path in vector_files],
            "vector_shape": list(vector_shape),
            "vectors_finite": vectors_finite,
            "stores_source_text": not cache_metadata_omits_text,
            "rss": warm_rss.report(),
        },
        "queries": {
            "count": len(query_seconds),
            "retrieval_limit": args.retrieval_limit,
            "encoder_calls": query_encoder.calls,
            "p50_ms": round(percentile(query_seconds, 0.50) * 1000, 3),
            "p95_ms": round(percentile(query_seconds, 0.95) * 1000, 3),
            "max_ms": round(max(query_seconds, default=0.0) * 1000, 3),
            "mean_ms": round(
                statistics.fmean(query_seconds) * 1000 if query_seconds else 0.0,
                3,
            ),
            "rss": query_rss.report(),
        },
        "holdout_knn": {
            **holdout_summary,
            "seconds": round(holdout_seconds, 4),
            "rows_per_second": round(
                len(holdout) / holdout_seconds if holdout_seconds else 0.0,
                3,
            ),
            "encoder_calls": holdout_encoder.calls,
            "encoded_texts": holdout_encoder.texts,
            "rss": holdout_rss.report(),
        },
        "selective_evidence": {
            "authority": (
                "advisory_only; abstention controls prompt evidence and never "
                "selects or executes an operation"
            ),
            "policy_output": report_path(args.policy_output),
            "calibration": calibration,
            "test": {
                "split": "test",
                "metrics": test_selective,
                "constraint_failures": test_constraint_failures,
            },
            "full_coverage_knn_baseline": {
                "role": "primary comparator before abstention",
                "validation": {
                    "classification": validation_full_knn,
                    "selective_view": full_coverage_validation,
                },
                "test": {
                    "classification": test_full_knn,
                    "selective_view": full_coverage_test,
                },
                "minimum_raw_family_recall_at_k": (
                    args.minimum_raw_family_recall_at_k
                ),
            },
            "empirical_prior_baseline": {
                "role": "secondary context only",
                "metrics": holdout_summary["prior"],
            },
        },
        "process": {
            "run_id": run_id,
            "rss_before_mib": round(rss_before / (1024**2), 3),
            "rss_after_mib": round(current_rss_bytes() / (1024**2), 3),
            "total_seconds": round(time.perf_counter() - started, 4),
        },
        "checks": checks,
    }
    if status == "passed":
        write_json_atomic(args.policy_output.resolve(), policy.to_dict())
    write_json_atomic(args.output.resolve(), report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gate del encoder E5 y caché de evidencia de turnos."
    )
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--holdout", type=Path, default=DEFAULT_HOLDOUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--policy-output",
        type=Path,
        default=DEFAULT_POLICY_OUTPUT,
        help=(
            "Política calibrada portable; solo se reemplaza cuando validation "
            "y el test separado aprueban."
        ),
    )
    parser.add_argument(
        "--cache-root",
        type=Path,
        default=DEFAULT_CACHE_ROOT,
        help="Raíz configurable; cada ejecución crea un hijo nuevo y aislado.",
    )
    cache_mode = parser.add_mutually_exclusive_group()
    cache_mode.add_argument(
        "--reuse-cache",
        action="store_true",
        help="Usa --cache-root como caché exacta y exige cero re-encoding del corpus.",
    )
    cache_mode.add_argument(
        "--migrate-cache",
        action="store_true",
        help=(
            "Usa --cache-root como caché exacta; permite una reconstrucción "
            "v4 y verifica que el warm load no vuelva a codificar."
        ),
    )
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--minimum-rows", type=int, default=20_000)
    parser.add_argument("--minimum-holdout-rows", type=int, default=9_000)
    parser.add_argument("--query-count", type=int, default=24)
    parser.add_argument("--retrieval-limit", type=int, default=4)
    parser.add_argument("--holdout-batch-size", type=int, default=64)
    parser.add_argument("--neighbors", type=int, default=5)
    parser.add_argument(
        "--maximum-conversation-false-action-upper",
        type=float,
        default=0.01,
        help="Máximo Wilson unilateral 95%% de falso-action selectivo.",
    )
    parser.add_argument(
        "--minimum-family-precision-lower",
        type=float,
        default=0.95,
        help="Mínimo Wilson unilateral 95%% de precisión de familia.",
    )
    parser.add_argument(
        "--minimum-family-recall-lower",
        type=float,
        default=0.30,
        help="Mínimo Wilson unilateral 95%% de recall de familia.",
    )
    parser.add_argument(
        "--minimum-actionable-coverage-lower",
        type=float,
        default=0.30,
        help="Mínimo Wilson unilateral 95%% de cobertura actionable.",
    )
    parser.add_argument(
        "--minimum-raw-family-recall-at-k",
        type=float,
        default=0.98,
        help="Mínimo recall@k de familia del kNN sin abstención.",
    )
    args = parser.parse_args()
    if args.minimum_rows < 1:
        parser.error("--minimum-rows debe ser positivo")
    if args.query_count < 1:
        parser.error("--query-count debe ser positivo")
    if args.retrieval_limit < 1:
        parser.error("--retrieval-limit debe ser positivo")
    if args.minimum_holdout_rows < 1:
        parser.error("--minimum-holdout-rows debe ser positivo")
    if args.holdout_batch_size < 1:
        parser.error("--holdout-batch-size debe ser positivo")
    if args.neighbors < 2:
        parser.error("--neighbors debe ser al menos 2 para medir margen")
    for argument in (
        "maximum_conversation_false_action_upper",
        "minimum_family_precision_lower",
        "minimum_family_recall_lower",
        "minimum_actionable_coverage_lower",
        "minimum_raw_family_recall_at_k",
    ):
        value = getattr(args, argument)
        if not 0.0 <= value <= 1.0:
            parser.error(f"--{argument.replace('_', '-')} debe estar entre 0 y 1")
    return args


def main() -> int:
    report = run_gate(parse_args())
    print(json.dumps(report["checks"], ensure_ascii=False, indent=2))
    print(f"status={report['status']} -> {report['warm_cache']['cache_directory']}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
