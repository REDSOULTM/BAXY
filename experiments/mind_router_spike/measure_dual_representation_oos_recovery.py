"""Measure a compact dual-representation OOS gate without changing runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
from scipy.sparse import hstack
from sklearn.linear_model import LogisticRegression
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler

from baxy_mind.family_classifier import FamilyClassifier
from baxy_mind.router import ProcessIntentRouter, RequestBudgetEncoder
from experiments.mind_router_spike.measure_multicluster_oos_recovery import (
    PUBLIC_VALIDATION,
    _encode_batches,
    _oracle_rows_and_texts,
    load_public_validation_rows,
    price_gate_against_oracles,
)
from scripts.baxy_runtime_config import (
    DEFAULT_RUNTIME_MANIFEST,
    public_runtime_identity,
    resolve_runtime,
)
from scripts.measure_mind_budget import (
    DEFAULT_CORE_CANDIDATES,
    PROFILE_LIMITS,
    current_core_capabilities,
    discover_core,
    sidecar_environment,
)

REPO = Path(__file__).resolve().parents[2]
PUBLIC_TRAINING = REPO / "tests/data/turn_evidence_runtime.v1.jsonl"
DEFAULT_OUTPUT = (
    REPO
    / "artifacts/development/dual_representation_oos_recovery_candidate_20260813.json"
)
RANDOM_STATE = 20_260_814
SYNTHETIC_OUTLIERS = 3_015


@dataclass(frozen=True, slots=True)
class DualRepresentationGate:
    scaler: StandardScaler
    classifier: LogisticRegression | MLPClassifier

    def inside_probability(self, features: np.ndarray) -> np.ndarray:
        rows = np.asarray(features, dtype=np.float64)
        return self.classifier.predict_proba(self.scaler.transform(rows))[:, 1]


@dataclass(frozen=True, slots=True)
class PublicTrainingRow:
    text: str
    inside_catalogue: bool
    family: str


def load_public_training_rows(path: Path) -> tuple[PublicTrainingRow, ...]:
    rows: list[PublicTrainingRow] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            provenance = payload.get("provenance")
            if not isinstance(provenance, dict) or provenance.get("dataset") not in {
                "MASSIVE v1.1",
                "PRESTO v1",
            }:
                continue
            text = payload.get("text")
            families = payload.get("families")
            if (
                not isinstance(text, str)
                or not text.strip()
                or not isinstance(families, list)
                or not all(isinstance(family, str) for family in families)
            ):
                raise ValueError(f"invalid public training row {line_number}")
            rows.append(
                PublicTrainingRow(
                    text=text,
                    inside_catalogue=bool(families),
                    family=str(families[0]) if families else "",
                )
            )
    return tuple(rows)


def zero_inside_loss_threshold(inside_probabilities: np.ndarray) -> float:
    values = np.asarray(inside_probabilities, dtype=np.float64).reshape(-1)
    if values.size == 0 or not np.isfinite(values).all():
        raise ValueError("inside calibration probabilities must be finite")
    return float(np.nextafter(values.min(), -np.inf))


def synthetic_cross_family_outliers(
    features: np.ndarray,
    families: Sequence[str],
    *,
    count: int,
    random_state: int,
) -> np.ndarray:
    rows = np.asarray(features, dtype=np.float64)
    labels = tuple(str(family) for family in families)
    if rows.ndim != 2 or rows.shape[0] != len(labels):
        raise ValueError("features and families must align")
    if count < 0:
        raise ValueError("count cannot be negative")
    by_family = {
        family: np.asarray(
            [index for index, label in enumerate(labels) if label == family],
            dtype=np.int64,
        )
        for family in sorted(set(labels))
    }
    if len(by_family) < 2:
        raise ValueError("synthetic outliers require at least two families")
    rng = np.random.default_rng(random_state)
    family_names = np.asarray(tuple(by_family), dtype=object)
    synthetic: list[np.ndarray] = []
    for _ in range(count):
        first_family, second_family = rng.choice(
            family_names,
            size=2,
            replace=False,
        )
        first = rows[int(rng.choice(by_family[str(first_family)]))]
        second = rows[int(rng.choice(by_family[str(second_family)]))]
        weight = float(rng.uniform(0.0, 1.0))
        synthetic.append(weight * first + (1.0 - weight) * second)
    if not synthetic:
        return np.empty((0, rows.shape[1]), dtype=np.float64)
    return np.stack(synthetic, axis=0)


def fit_dual_representation_gate(
    inside_features: np.ndarray,
    outside_features: np.ndarray,
    *,
    random_state: int,
) -> DualRepresentationGate:
    inside = np.asarray(inside_features, dtype=np.float64)
    outside = np.asarray(outside_features, dtype=np.float64)
    if (
        inside.ndim != 2
        or outside.ndim != 2
        or inside.shape[1] != outside.shape[1]
        or not len(inside)
        or not len(outside)
    ):
        raise ValueError("inside and outside features must be aligned matrices")
    features = np.vstack((inside, outside))
    labels = np.concatenate(
        (
            np.ones(len(inside), dtype=np.int8),
            np.zeros(len(outside), dtype=np.int8),
        )
    )
    scaler = StandardScaler()
    scaled = scaler.fit_transform(features)
    classifier = LogisticRegression(
        C=10.0,
        class_weight="balanced",
        max_iter=1_000,
        random_state=random_state,
        solver="lbfgs",
    )
    classifier.fit(scaled, labels)
    return DualRepresentationGate(scaler=scaler, classifier=classifier)


def fit_nonlinear_dual_representation_gate(
    inside_features: np.ndarray,
    outside_features: np.ndarray,
    *,
    random_state: int,
    solver: str = "adam",
) -> DualRepresentationGate:
    inside = np.asarray(inside_features, dtype=np.float64)
    outside = np.asarray(outside_features, dtype=np.float64)
    if (
        inside.ndim != 2
        or outside.ndim != 2
        or inside.shape[1] != outside.shape[1]
        or not len(inside)
        or not len(outside)
    ):
        raise ValueError("inside and outside features must be aligned matrices")
    features = np.vstack((inside, outside))
    labels = np.concatenate(
        (
            np.ones(len(inside), dtype=np.int8),
            np.zeros(len(outside), dtype=np.int8),
        )
    )
    scaler = StandardScaler()
    scaled = scaler.fit_transform(features)
    classifier = MLPClassifier(
        hidden_layer_sizes=(128, 64),
        activation="relu",
        alpha=1e-4,
        batch_size=256,
        early_stopping=solver == "adam",
        learning_rate_init=1e-3,
        max_iter=1_000 if solver == "lbfgs" else 100,
        n_iter_no_change=10,
        random_state=random_state,
        solver=solver,
    )
    classifier.fit(scaled, labels)
    return DualRepresentationGate(scaler=scaler, classifier=classifier)


def candidate_verdict(
    *,
    public_inside_rejected: int,
    served_rows_lost: Sequence[str],
    outside_rows_newly_zero: Sequence[str],
) -> str:
    if public_inside_rejected or served_rows_lost:
        return "rejected_inside_loss"
    if not outside_rows_newly_zero:
        return "rejected_no_target_gain"
    return "promising_not_promoted"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _lexical_family_features(
    texts: Sequence[str],
) -> tuple[np.ndarray, tuple[str, ...]]:
    classifier = FamilyClassifier()
    (
        characters,
        words,
        classes,
        coefficients,
        intercept,
    ) = classifier._resources
    batches: list[np.ndarray] = []
    for offset in range(0, len(texts), 2_048):
        batch = texts[offset : offset + 2_048]
        sparse = hstack(
            (
                characters.transform(batch),
                words.transform(batch) * 1.5,
            ),
            format="csr",
        )
        scores = np.asarray(
            sparse @ coefficients.T + intercept,
            dtype=np.float64,
        )
        ordered = np.sort(scores, axis=1)
        confidence = np.column_stack(
            (
                ordered[:, -1],
                ordered[:, -2],
                ordered[:, -1] - ordered[:, -2],
            )
        )
        batches.append(np.hstack((scores, confidence)))
    return np.vstack(batches), tuple(classes)


def _dual_features(
    encoder: RequestBudgetEncoder,
    texts: Sequence[str],
) -> tuple[np.ndarray, tuple[str, ...]]:
    semantic = np.asarray(_encode_batches(encoder, texts), dtype=np.float64)
    lexical, classes = _lexical_family_features(texts)
    return np.hstack((semantic, lexical)), classes


def _quantiles(values: np.ndarray) -> dict[str, float]:
    rows = np.asarray(values, dtype=np.float64)
    return {
        "minimum": float(rows.min()),
        "p50": float(np.quantile(rows, 0.50)),
        "p95": float(np.quantile(rows, 0.95)),
        "maximum": float(rows.max()),
    }


def _array_sha256(array: np.ndarray) -> str:
    contiguous = np.ascontiguousarray(array)
    return hashlib.sha256(contiguous.tobytes()).hexdigest()


def _write_report(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def run(output: Path = DEFAULT_OUTPUT) -> dict[str, object]:
    training_rows = load_public_training_rows(PUBLIC_TRAINING)
    if (
        len(training_rows) != 17_784
        or sum(row.inside_catalogue for row in training_rows) != 14_769
        or sum(not row.inside_catalogue for row in training_rows) != 3_015
    ):
        raise RuntimeError("public training split identity changed")
    capabilities = current_core_capabilities(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES))
    )
    available_families = {
        str(capability["name"]).split(".", 1)[0]
        for capability in capabilities
    }
    public_rows = load_public_validation_rows(
        PUBLIC_VALIDATION,
        available_families,
    )
    oracle_rows, oracle_texts = _oracle_rows_and_texts()

    runtime = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    os.environ.update(
        sidecar_environment(
            runtime,
            gpu_layers=runtime.gpu_layers,
            llm_http_timeout=PROFILE_LIMITS["gpu"]["llm_http"],
        )
    )
    router = ProcessIntentRouter()
    try:
        if not router.try_ready(180.0):
            raise RuntimeError("the attested E5 encoder did not become ready")
        encoder = RequestBudgetEncoder(router)
        training_features, lexical_classes = _dual_features(
            encoder,
            [row.text for row in training_rows],
        )
        public_features, public_classes = _dual_features(
            encoder,
            [row.text for row in public_rows],
        )
        oracle_features, oracle_classes = _dual_features(
            encoder,
            oracle_texts,
        )
    finally:
        router.close()
    if lexical_classes != public_classes or lexical_classes != oracle_classes:
        raise RuntimeError("lexical family feature identity changed")

    inside_indexes = np.asarray(
        [
            index
            for index, row in enumerate(training_rows)
            if row.inside_catalogue
        ],
        dtype=np.int64,
    )
    outside_indexes = np.asarray(
        [
            index
            for index, row in enumerate(training_rows)
            if not row.inside_catalogue
        ],
        dtype=np.int64,
    )
    inside_training = training_features[inside_indexes]
    outside_training = training_features[outside_indexes]
    synthetic = synthetic_cross_family_outliers(
        inside_training,
        [training_rows[index].family for index in inside_indexes],
        count=SYNTHETIC_OUTLIERS,
        random_state=RANDOM_STATE,
    )
    gate = fit_dual_representation_gate(
        inside_training,
        np.vstack((outside_training, synthetic)),
        random_state=RANDOM_STATE,
    )

    public_probabilities = gate.inside_probability(public_features)
    public_inside_mask = np.asarray(
        [row.inside_catalogue for row in public_rows],
        dtype=bool,
    )
    threshold = zero_inside_loss_threshold(
        public_probabilities[public_inside_mask]
    )
    public_accepted = public_probabilities >= threshold
    oracle_probabilities = gate.inside_probability(oracle_features)
    oracle_accepted = oracle_probabilities >= threshold

    public_inside_rejected = np.flatnonzero(
        public_inside_mask & ~public_accepted
    )
    public_outside_mask = ~public_inside_mask
    public_outside_rejected = np.flatnonzero(
        public_outside_mask & ~public_accepted
    )
    oracle_pricing = price_gate_against_oracles(
        oracle_rows,
        accepted=oracle_accepted.tolist(),
    )
    verdict = candidate_verdict(
        public_inside_rejected=len(public_inside_rejected),
        served_rows_lost=oracle_pricing["served_rows_lost"],
        outside_rows_newly_zero=oracle_pricing["outside_rows_newly_zero"],
    )
    coefficients = np.asarray(gate.classifier.coef_, dtype=np.float64)
    report: dict[str, object] = {
        "schema": "baxy.dual-representation-oos-recovery-candidate.v1",
        "authority": "development_diagnostic_not_for_promotion",
        "verdict": verdict,
        "runtime_modified": False,
        "effects_executed": 0,
        "opened_v8": False,
        "v9_reserved": True,
        "mechanism": {
            "architecture": (
                "binary OOS gate over existing multilingual E5 embeddings "
                "plus lexical closed-family logits"
            ),
            "semantic_dimensions": 384,
            "lexical_family_logits": len(lexical_classes),
            "lexical_confidence_features": 3,
            "classifier": "balanced logistic regression",
            "classifier_c": 10.0,
            "synthetic_outliers": SYNTHETIC_OUTLIERS,
            "synthetic_rule": (
                "uniform convex mixtures of different supported families"
            ),
            "threshold_rule": (
                "next representable value below the minimum public validation "
                "inside probability; outside labels are not used for selection"
            ),
            "selected_threshold": threshold,
            "consumed_population_tuning": False,
        },
        "research_basis": {
            "title": "DROID: Dual Representation for Out-of-Scope Intent Detection",
            "url": "https://arxiv.org/abs/2510.14110",
            "adaptation": (
                "DROID's dual representation, open-domain negatives, synthetic "
                "feature outliers and calibrated gate are retained. Existing "
                "E5 and lexical logits replace USE+TSDAE, and a linear head is "
                "used first to price the mechanism before adding a resident model."
            ),
        },
        "training": {
            "rows": len(training_rows),
            "inside_rows": len(inside_indexes),
            "open_domain_outside_rows": len(outside_indexes),
            "synthetic_outside_rows": len(synthetic),
            "datasets": ["MASSIVE v1.1", "PRESTO v1"],
            "historical_or_private_rows": 0,
        },
        "public_validation": {
            "rows": len(public_rows),
            "inside_rows": int(public_inside_mask.sum()),
            "inside_rejected": int(len(public_inside_rejected)),
            "inside_accepted": int(
                public_inside_mask.sum() - len(public_inside_rejected)
            ),
            "outside_rows": int(public_outside_mask.sum()),
            "outside_rejected": int(len(public_outside_rejected)),
            "outside_accepted": int(
                public_outside_mask.sum() - len(public_outside_rejected)
            ),
            "outside_rejection_rate": (
                len(public_outside_rejected) / public_outside_mask.sum()
            ),
            "inside_probability_quantiles": _quantiles(
                public_probabilities[public_inside_mask]
            ),
            "outside_probability_quantiles": _quantiles(
                public_probabilities[public_outside_mask]
            ),
            "inside_rejected_source_ids": [
                public_rows[index].source_id
                for index in public_inside_rejected
            ],
            "outside_accepted_source_ids": [
                public_rows[index].source_id
                for index in np.flatnonzero(
                    public_outside_mask & public_accepted
                )
            ],
        },
        "oracle_pricing": oracle_pricing,
        "oracle_scores": [
            {
                "population": row.population,
                "row_id": row.row_id,
                "inside_probability": float(probability),
                "inside_boundary": bool(accepted),
            }
            for row, probability, accepted in zip(
                oracle_rows,
                oracle_probabilities,
                oracle_accepted,
                strict=True,
            )
        ],
        "population_refutability": {
            "inside_loss": [
                "MASSIVE/PRESTO public validation inside rows",
                *oracle_pricing["refuting_populations"]["served_loss"],
            ],
            "outside_rejection": [
                "MASSIVE/PRESTO public validation outside rows",
                *oracle_pricing["refuting_populations"]["outside_non_empty"],
            ],
        },
        "comparison_to_rejected_lexical_only_gate": {
            "artifact": (
                "artifacts/development/"
                "open_catalogue_candidate_rejected_20260812.json"
            ),
            "lexical_only_validation_inside_loss": 0,
            "lexical_only_validation_outside_recall": 0.133086876155268,
            "lexical_only_consumed_served_rows_lost": 2,
        },
        "identities": {
            "program_sha256": _sha256(Path(__file__)),
            "public_training_sha256": _sha256(PUBLIC_TRAINING),
            "public_validation_sha256": _sha256(PUBLIC_VALIDATION),
            "lexical_classes": list(lexical_classes),
            "classifier_coefficients_sha256": _array_sha256(coefficients),
            "classifier_intercept_sha256": _array_sha256(
                np.asarray(gate.classifier.intercept_, dtype=np.float64)
            ),
            "runtime": public_runtime_identity(runtime),
        },
        "rejection_rule": (
            "reject on any public validation inside loss or any oracle row "
            "whose baseline-recalled expected operation would be removed"
        ),
    }
    _write_report(output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = run(args.output)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "verdict": report["verdict"],
                "threshold": report["mechanism"]["selected_threshold"],
                "public_validation": {
                    key: report["public_validation"][key]
                    for key in (
                        "inside_rows",
                        "inside_rejected",
                        "outside_rows",
                        "outside_rejected",
                    )
                },
                "oracle_pricing": {
                    key: report["oracle_pricing"][key]
                    for key in (
                        "expected_operation_recall",
                        "outside_zero_candidates",
                        "served_rows_lost",
                    )
                },
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
