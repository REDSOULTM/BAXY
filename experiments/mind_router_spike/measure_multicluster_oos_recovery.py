"""Measure a multi-cluster open-set gate without changing the BAXY runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np
from sklearn.cluster import KMeans

from baxy_mind.router import ProcessIntentRouter, RequestBudgetEncoder
from experiments.mind_router_spike.price_consumed_retrieval_mechanisms import (
    load_population_inputs,
)
from experiments.mind_router_spike.probe_heldout_family_classifier import (
    _catalog_seed_pool,
    _historical_support_pool,
    _normal_key,
    _qualifying_pool,
    _universal_holdout,
)
from experiments.mind_router_spike.probe_paraphrase_tool_quality import _oracle
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
PUBLIC_VALIDATION = REPO / "tests/data/turn_evidence_public_holdout.v1.jsonl"
RETRIEVAL_BASELINE = (
    REPO
    / "artifacts/development/retrieval_recovery_baseline_current_tree_20260813.json"
)
DEFAULT_OUTPUT = (
    REPO
    / "artifacts/development/multicluster_oos_recovery_candidate_20260813.json"
)
EXPECTED_BASELINE_SHA256 = (
    "af96437b5cb294e0d54a85f07788b1e0270df90c108dcf2079b2a307f2e5a6b4"
)
CLUSTERS_PER_LABEL = 2
RADIUS_SCALE = 1.0
RANDOM_STATE = 20_260_813
ENCODER_BATCH_SIZE = 1_024


@dataclass(frozen=True, slots=True)
class MultiClusterBoundaries:
    labels: tuple[str, ...]
    centroids: np.ndarray
    variances: np.ndarray
    radii: np.ndarray
    epsilon: float


@dataclass(frozen=True, slots=True)
class BoundaryScore:
    accepted: bool
    label: str
    normalized_distance: float


@dataclass(frozen=True, slots=True)
class OracleRetrievalRow:
    population: str
    row_id: str
    expected_operations: tuple[str, ...]
    baseline_candidates: tuple[str, ...]
    outside_catalogue: bool


@dataclass(frozen=True, slots=True)
class PublicValidationRow:
    source_id: str
    text: str
    inside_catalogue: bool


@dataclass(frozen=True, slots=True)
class TrainingRow:
    text: str
    family: str


def load_public_validation_rows(
    path: Path,
    available_families: set[str],
) -> tuple[PublicValidationRow, ...]:
    rows: list[PublicValidationRow] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            text = payload.get("text")
            families = payload.get("families")
            if (
                not isinstance(text, str)
                or not text.strip()
                or not isinstance(families, list)
                or not all(isinstance(family, str) for family in families)
            ):
                raise ValueError(f"invalid public validation row {line_number}")
            rows.append(
                PublicValidationRow(
                    source_id=str(payload.get("source_id") or line_number),
                    text=text,
                    inside_catalogue=bool(set(families) & available_families),
                )
            )
    return tuple(rows)


def _normalized_rows(embeddings: np.ndarray) -> np.ndarray:
    rows = np.asarray(embeddings, dtype=np.float64)
    if rows.ndim != 2 or rows.shape[0] == 0 or rows.shape[1] == 0:
        raise ValueError("embeddings must be a non-empty matrix")
    if not np.isfinite(rows).all():
        raise ValueError("embeddings must be finite")
    norms = np.linalg.norm(rows, axis=1, keepdims=True)
    if np.any(norms <= 0.0):
        raise ValueError("embeddings must have non-zero norm")
    return rows / norms


def fit_multicluster_boundaries(
    embeddings: np.ndarray,
    labels: Sequence[str],
    *,
    clusters_per_label: int,
    radius_scale: float,
    random_state: int,
    epsilon: float = 1e-6,
) -> MultiClusterBoundaries:
    rows = _normalized_rows(embeddings)
    normalized_labels = tuple(str(label) for label in labels)
    if len(normalized_labels) != rows.shape[0]:
        raise ValueError("labels must align with embedding rows")
    if clusters_per_label < 1:
        raise ValueError("clusters_per_label must be positive")
    if radius_scale < 0.0 or epsilon <= 0.0:
        raise ValueError("boundary parameters must be positive")

    cluster_labels: list[str] = []
    centroids: list[np.ndarray] = []
    variances: list[np.ndarray] = []
    radii: list[float] = []
    for label in sorted(set(normalized_labels)):
        indexes = [
            index
            for index, candidate_label in enumerate(normalized_labels)
            if candidate_label == label
        ]
        label_rows = rows[indexes]
        cluster_count = min(clusters_per_label, len(label_rows))
        assignments = KMeans(
            n_clusters=cluster_count,
            n_init=10,
            random_state=random_state,
        ).fit_predict(label_rows)
        for cluster_index in sorted(set(assignments.tolist())):
            assigned = label_rows[assignments == cluster_index]
            centroid = assigned.mean(axis=0)
            variance = assigned.var(axis=0)
            distances = np.sqrt(
                np.sum(
                    np.square(assigned - centroid) / (variance + epsilon),
                    axis=1,
                )
            )
            radius = max(
                float(distances.mean() + radius_scale * distances.std()),
                epsilon,
            )
            cluster_labels.append(label)
            centroids.append(centroid)
            variances.append(variance)
            radii.append(radius)

    return MultiClusterBoundaries(
        labels=tuple(cluster_labels),
        centroids=np.asarray(centroids, dtype=np.float64),
        variances=np.asarray(variances, dtype=np.float64),
        radii=np.asarray(radii, dtype=np.float64),
        epsilon=epsilon,
    )


def score_multicluster_boundaries(
    boundaries: MultiClusterBoundaries,
    embeddings: np.ndarray,
) -> tuple[BoundaryScore, ...]:
    rows = _normalized_rows(embeddings)
    scores: list[BoundaryScore] = []
    for row in rows:
        distances = np.sqrt(
            np.sum(
                np.square(boundaries.centroids - row)
                / (boundaries.variances + boundaries.epsilon),
                axis=1,
            )
        )
        normalized = distances / boundaries.radii
        nearest = int(np.argmin(normalized))
        value = float(normalized[nearest])
        scores.append(
            BoundaryScore(
                accepted=value <= 1.0,
                label=boundaries.labels[nearest],
                normalized_distance=value,
            )
        )
    return tuple(scores)


def price_gate_against_oracles(
    rows: Sequence[OracleRetrievalRow],
    *,
    accepted: Sequence[bool],
) -> dict[str, object]:
    if len(rows) != len(accepted):
        raise ValueError("gate decisions must align with oracle rows")

    baseline_recalled = 0
    candidate_recalled = 0
    expected_total = 0
    outside_total = 0
    outside_baseline_zero = 0
    outside_candidate_zero = 0
    served_rows_lost: list[str] = []
    outside_rows_newly_zero: list[str] = []
    served_populations: set[str] = set()
    outside_populations: set[str] = set()
    for row, is_accepted in zip(rows, accepted, strict=True):
        baseline = set(row.baseline_candidates)
        candidate = baseline if is_accepted else set()
        expected = set(row.expected_operations)
        qualified = f"{row.population}:{row.row_id}"
        if expected:
            served_populations.add(row.population)
            expected_total += len(expected)
            baseline_recalled += len(expected & baseline)
            candidate_recalled += len(expected & candidate)
            if expected.issubset(baseline) and not expected.issubset(candidate):
                served_rows_lost.append(qualified)
        if row.outside_catalogue:
            outside_populations.add(row.population)
            outside_total += 1
            outside_baseline_zero += int(not baseline)
            outside_candidate_zero += int(not candidate)
            if baseline and not candidate:
                outside_rows_newly_zero.append(qualified)

    return {
        "expected_operation_recall": {
            "baseline": f"{baseline_recalled}/{expected_total}",
            "candidate": f"{candidate_recalled}/{expected_total}",
        },
        "served_rows_lost": served_rows_lost,
        "outside_zero_candidates": {
            "baseline": f"{outside_baseline_zero}/{outside_total}",
            "candidate": f"{outside_candidate_zero}/{outside_total}",
        },
        "outside_rows_newly_zero": outside_rows_newly_zero,
        "refuting_populations": {
            "served_loss": sorted(served_populations),
            "outside_non_empty": sorted(outside_populations),
        },
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _family_training_rows(
    capabilities: list[dict[str, Any]],
) -> tuple[TrainingRow, ...]:
    catalog_names = tuple(str(item["name"]) for item in capabilities)
    primary_holdout = _oracle(catalog_names)
    primary_keys = {_normal_key(row["text"]) for row in primary_holdout}
    qualifying = _qualifying_pool(catalog_names)
    qualifying_training = [
        row for row in qualifying if _normal_key(row["text"]) not in primary_keys
    ]
    universal_holdout = _universal_holdout(
        qualifying_training,
        cases=min(20, len({row["family"] for row in qualifying_training})),
    )
    universal_keys = {_normal_key(row["text"]) for row in universal_holdout}
    qualifying_training = [
        row
        for row in qualifying_training
        if _normal_key(row["text"]) not in universal_keys
    ]
    support = _historical_support_pool(catalog_names, primary_keys)
    seeds = _catalog_seed_pool(capabilities, primary_keys)
    training_by_key: dict[str, dict[str, Any]] = {}
    for row in qualifying_training + support + seeds:
        key = _normal_key(row["text"])
        if key in universal_keys:
            continue
        training_by_key.setdefault(key, row)
    if primary_keys & set(training_by_key) or universal_keys & set(training_by_key):
        raise RuntimeError("open-set training overlaps a frozen family holdout")
    return tuple(
        TrainingRow(text=str(row["text"]), family=str(row["family"]))
        for row in training_by_key.values()
    )


def _oracle_rows_and_texts() -> tuple[
    tuple[OracleRetrievalRow, ...],
    tuple[str, ...],
]:
    if _sha256(RETRIEVAL_BASELINE) != EXPECTED_BASELINE_SHA256:
        raise RuntimeError("retrieval baseline identity changed")
    baseline = json.loads(RETRIEVAL_BASELINE.read_text(encoding="utf-8"))
    inputs, unavailable = load_population_inputs()
    if unavailable:
        raise RuntimeError(f"oracle populations unavailable: {unavailable}")
    input_by_identity = {
        (row.population, row.row_id): row
        for row in inputs
    }
    oracle_rows: list[OracleRetrievalRow] = []
    texts: list[str] = []
    for row in baseline["row_counterfactuals"]:
        identity = str(row["population"]), str(row["row_id"])
        source = input_by_identity.get(identity)
        if source is None:
            raise RuntimeError(f"missing oracle input: {identity}")
        text_sha256 = hashlib.sha256(source.text.encode("utf-8")).hexdigest()
        if text_sha256 != row["text_sha256"]:
            raise RuntimeError(f"oracle text identity changed: {identity}")
        expected = tuple(str(value) for value in row["expected_operations"])
        if expected != source.expected_operations:
            raise RuntimeError(f"oracle expected operations changed: {identity}")
        oracle_rows.append(
            OracleRetrievalRow(
                population=identity[0],
                row_id=identity[1],
                expected_operations=expected,
                baseline_candidates=tuple(
                    str(value)
                    for value in row["candidate_sets"]["baseline"]
                ),
                outside_catalogue=bool(row["outside_catalogue"]),
            )
        )
        texts.append(source.text)
    if len(oracle_rows) != baseline["rows"]:
        raise RuntimeError("retrieval baseline row count changed")
    return tuple(oracle_rows), tuple(texts)


def _encode_batches(
    encoder: RequestBudgetEncoder,
    texts: Sequence[str],
) -> np.ndarray:
    batches: list[np.ndarray] = []
    for offset in range(0, len(texts), ENCODER_BATCH_SIZE):
        batch = tuple(texts[offset : offset + ENCODER_BATCH_SIZE])
        batches.append(np.asarray(encoder(batch), dtype=np.float32))
    return np.concatenate(batches, axis=0)


def _score_quantiles(scores: Sequence[BoundaryScore]) -> dict[str, float]:
    values = np.asarray(
        [score.normalized_distance for score in scores],
        dtype=np.float64,
    )
    return {
        "minimum": float(values.min()),
        "p50": float(np.quantile(values, 0.50)),
        "p95": float(np.quantile(values, 0.95)),
        "maximum": float(values.max()),
    }


def _public_validation_metrics(
    rows: Sequence[PublicValidationRow],
    scores: Sequence[BoundaryScore],
) -> dict[str, object]:
    if len(rows) != len(scores):
        raise ValueError("public validation scores must align with rows")
    inside = [
        (row, score)
        for row, score in zip(rows, scores, strict=True)
        if row.inside_catalogue
    ]
    outside = [
        (row, score)
        for row, score in zip(rows, scores, strict=True)
        if not row.inside_catalogue
    ]
    inside_rejected = [
        row.source_id for row, score in inside if not score.accepted
    ]
    outside_accepted = [
        row.source_id for row, score in outside if score.accepted
    ]
    return {
        "rows": len(rows),
        "inside_rows": len(inside),
        "inside_accepted": len(inside) - len(inside_rejected),
        "inside_rejected": len(inside_rejected),
        "inside_acceptance_rate": (
            (len(inside) - len(inside_rejected)) / len(inside)
            if inside
            else None
        ),
        "outside_rows": len(outside),
        "outside_rejected": len(outside) - len(outside_accepted),
        "outside_accepted": len(outside_accepted),
        "outside_rejection_rate": (
            (len(outside) - len(outside_accepted)) / len(outside)
            if outside
            else None
        ),
        "inside_rejected_source_ids": inside_rejected,
        "outside_accepted_source_ids": outside_accepted,
        "inside_score_quantiles": _score_quantiles(
            [score for _, score in inside]
        ),
        "outside_score_quantiles": _score_quantiles(
            [score for _, score in outside]
        ),
    }


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
    capabilities = current_core_capabilities(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES))
    )
    available_families = {
        str(capability["name"]).split(".", 1)[0]
        for capability in capabilities
    }
    training = _family_training_rows(capabilities)
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
        training_embeddings = _encode_batches(
            encoder,
            [row.text for row in training],
        )
        boundaries = fit_multicluster_boundaries(
            training_embeddings,
            [row.family for row in training],
            clusters_per_label=CLUSTERS_PER_LABEL,
            radius_scale=RADIUS_SCALE,
            random_state=RANDOM_STATE,
        )
        public_scores = score_multicluster_boundaries(
            boundaries,
            _encode_batches(encoder, [row.text for row in public_rows]),
        )
        oracle_scores = score_multicluster_boundaries(
            boundaries,
            _encode_batches(encoder, oracle_texts),
        )
    finally:
        router.close()

    public_metrics = _public_validation_metrics(public_rows, public_scores)
    oracle_pricing = price_gate_against_oracles(
        oracle_rows,
        accepted=[score.accepted for score in oracle_scores],
    )
    candidate_rejected = bool(
        public_metrics["inside_rejected"]
        or oracle_pricing["served_rows_lost"]
    )
    report: dict[str, object] = {
        "schema": "baxy.multicluster-oos-recovery-candidate.v1",
        "authority": "development_diagnostic_not_for_promotion",
        "verdict": "rejected" if candidate_rejected else "promising_not_promoted",
        "runtime_modified": False,
        "effects_executed": 0,
        "opened_v8": False,
        "v9_reserved": True,
        "mechanism": {
            "architecture": (
                "one-class multi-cluster boundary gate before closed-set "
                "family routing"
            ),
            "encoder": "existing attested intfloat/multilingual-e5-small",
            "clusters_per_family": CLUSTERS_PER_LABEL,
            "distance": "diagonal Mahalanobis",
            "radius": "mean_distance + radius_scale * standard_deviation",
            "radius_scale": RADIUS_SCALE,
            "acceptance": "minimum normalized cluster distance <= 1",
            "random_state": RANDOM_STATE,
            "parameter_selection": (
                "paper default K=2 and non-CLINC lambda=1.0; no sweep and no "
                "consumed-population tuning"
            ),
        },
        "current_research": [
            {
                "title": (
                    "A Multi-cluster Boundary Learning Method for Out-of-Scope "
                    "Intent Detection via MiniLM Embedding"
                ),
                "published": "2026-07-08",
                "url": "https://arxiv.org/abs/2607.07974",
                "adaptation": (
                    "same one-class cascade, K-means local boundaries, "
                    "diagonal Mahalanobis and normalized radius; existing "
                    "multilingual E5 replaces MiniLM to avoid a new resident model"
                ),
            },
            {
                "title": "Ellipsoid-Based Decision Boundaries for Open Intent Classification",
                "published": "AAAI 2026",
                "url": "https://doi.org/10.1609/aaai.v40i41.40837",
                "adaptation": (
                    "not implemented in this first local test because it "
                    "requires supervised contrastive representation training "
                    "and learned matrices; retained as the higher-complexity boundary"
                ),
            },
            {
                "title": "DROID: Dual Representation for Out-of-Scope Intent Detection",
                "published": "2025-10",
                "url": "https://arxiv.org/abs/2510.14110",
                "adaptation": (
                    "not implemented because it adds a second encoder and "
                    "domain-adapted TSDAE; local evidence must justify that cost"
                ),
            },
        ],
        "training": {
            "rows": len(training),
            "families": len({row.family for row in training}),
            "primary_holdout_overlap": 0,
            "universal_holdout_overlap": 0,
        },
        "boundaries": {
            "clusters": len(boundaries.labels),
            "dimensions": int(boundaries.centroids.shape[1]),
            "radius_minimum": float(boundaries.radii.min()),
            "radius_median": float(np.median(boundaries.radii)),
            "radius_maximum": float(boundaries.radii.max()),
        },
        "public_validation": public_metrics,
        "oracle_pricing": oracle_pricing,
        "oracle_scores": [
            {
                "population": row.population,
                "row_id": row.row_id,
                "inside_boundary": score.accepted,
                "nearest_family": score.label,
                "normalized_distance": score.normalized_distance,
            }
            for row, score in zip(oracle_rows, oracle_scores, strict=True)
        ],
        "population_refutability": {
            "inside_loss": {
                "populations": [
                    "MASSIVE/PRESTO public validation inside rows",
                    *oracle_pricing["refuting_populations"]["served_loss"],
                ],
                "could_refute": (
                    "any boundary that rejects a supported request or removes "
                    "an expected operation currently present"
                ),
            },
            "outside_rejection": {
                "populations": [
                    "MASSIVE/PRESTO public validation outside rows",
                    *oracle_pricing["refuting_populations"]["outside_non_empty"],
                ],
                "could_refute": (
                    "any claimed zero-candidate gain that still accepts a "
                    "labelled outside request"
                ),
            },
        },
        "identities": {
            "program_sha256": _sha256(Path(__file__)),
            "public_validation_sha256": _sha256(PUBLIC_VALIDATION),
            "retrieval_baseline_sha256": _sha256(RETRIEVAL_BASELINE),
            "runtime": public_runtime_identity(runtime),
        },
        "rejection_rule": (
            "reject on any public inside false rejection or any consumed "
            "served row whose baseline-recalled operation would be removed"
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
                "training": report["training"],
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
