"""Measure a dual OOS gate trained with disjoint MTOP development negatives."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from baxy_mind.family_classifier import MIN_PREDICTION_MARGIN
from baxy_mind.router import ProcessIntentRouter, RequestBudgetEncoder
from experiments.mind_router_spike.measure_dual_representation_oos_recovery import (
    PUBLIC_TRAINING,
    _array_sha256,
    _dual_features,
    _quantiles,
    _sha256,
    candidate_verdict,
    fit_dual_representation_gate,
    fit_nonlinear_dual_representation_gate,
    load_public_training_rows,
    synthetic_cross_family_outliers,
    zero_inside_loss_threshold,
)
from experiments.mind_router_spike.measure_multicluster_oos_recovery import (
    PUBLIC_VALIDATION,
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
MTOP_DEVELOPMENT = (
    Path(os.environ["LOCALAPPDATA"])
    / "BAXYRuntime/datasets/mtop-v1/derived/mtop_development.v1.jsonl"
)
EXPECTED_MTOP_SHA256 = (
    "ed1871262bdb78a53e219ac6ebd7b995879c60eba29ec5d9203217480a142802"
)
DEFAULT_OUTPUT = (
    REPO
    / "artifacts/development/mtop_dual_oos_recovery_candidate_20260813.json"
)
RANDOM_STATE = 20_260_815
SYNTHETIC_OUTLIERS = 3_015

INSIDE_DISPOSITIONS = frozenset(
    {
        "candidate",
        "candidate_missing_information",
    }
)
OUTSIDE_DISPOSITIONS = frozenset(
    {
        "conversation_no_effect",
        "ood_no_effect",
    }
)


@dataclass(frozen=True, slots=True)
class MtopDevelopmentRow:
    source_id: str
    split: str
    text: str
    inside_catalogue: bool
    family: str


def load_mtop_development_rows(path: Path) -> tuple[MtopDevelopmentRow, ...]:
    rows: list[MtopDevelopmentRow] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            projection = payload.get("projection")
            text = payload.get("text")
            split = payload.get("split")
            source_id = payload.get("source_id")
            if (
                not isinstance(projection, dict)
                or not isinstance(text, str)
                or not text.strip()
                or split not in {"train", "validation"}
                or not isinstance(source_id, str)
                or not source_id
            ):
                raise ValueError(f"invalid MTOP development row {line_number}")
            disposition = projection.get("disposition")
            if disposition in INSIDE_DISPOSITIONS:
                inside = True
            elif disposition in OUTSIDE_DISPOSITIONS:
                inside = False
            else:
                raise ValueError(
                    f"unknown MTOP disposition at row {line_number}"
                )
            families = projection.get("families")
            if not isinstance(families, list) or not all(
                isinstance(family, str) for family in families
            ):
                raise ValueError(f"invalid MTOP families at row {line_number}")
            rows.append(
                MtopDevelopmentRow(
                    source_id=source_id,
                    split=split,
                    text=text,
                    inside_catalogue=inside,
                    family=str(families[0]) if families else "",
                )
            )
    return tuple(rows)


def routed_hard_negative_mask(
    *,
    inside_mask: np.ndarray,
    lexical_margins: np.ndarray,
    minimum_margin: float,
) -> np.ndarray:
    inside = np.asarray(inside_mask, dtype=bool)
    margins = np.asarray(lexical_margins, dtype=np.float64)
    if inside.shape != margins.shape:
        raise ValueError("inside mask and lexical margins must align")
    return ~inside & (margins >= minimum_margin)


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


def _partition_metrics(
    probabilities: np.ndarray,
    inside_mask: np.ndarray,
    accepted: np.ndarray,
) -> dict[str, object]:
    outside_mask = ~inside_mask
    inside_rejected = int(np.sum(inside_mask & ~accepted))
    outside_rejected = int(np.sum(outside_mask & ~accepted))
    return {
        "rows": int(len(probabilities)),
        "inside_rows": int(inside_mask.sum()),
        "inside_rejected": inside_rejected,
        "inside_accepted": int(inside_mask.sum()) - inside_rejected,
        "outside_rows": int(outside_mask.sum()),
        "outside_rejected": outside_rejected,
        "outside_accepted": int(outside_mask.sum()) - outside_rejected,
        "outside_rejection_rate": (
            outside_rejected / outside_mask.sum() if outside_mask.any() else None
        ),
        "inside_probability_quantiles": _quantiles(probabilities[inside_mask]),
        "outside_probability_quantiles": _quantiles(probabilities[outside_mask]),
    }


def run(output: Path = DEFAULT_OUTPUT) -> dict[str, object]:
    if _sha256(MTOP_DEVELOPMENT) != EXPECTED_MTOP_SHA256:
        raise RuntimeError("MTOP development corpus identity changed")
    mtop_rows = load_mtop_development_rows(MTOP_DEVELOPMENT)
    if len(mtop_rows) != 29_976:
        raise RuntimeError("MTOP development row count changed")
    mtop_train = [row for row in mtop_rows if row.split == "train"]
    mtop_validation = [row for row in mtop_rows if row.split == "validation"]
    public_training = load_public_training_rows(PUBLIC_TRAINING)

    capabilities = current_core_capabilities(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES))
    )
    available_families = {
        str(capability["name"]).split(".", 1)[0]
        for capability in capabilities
    }
    public_validation = load_public_validation_rows(
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
        public_training_features, classes_a = _dual_features(
            encoder,
            [row.text for row in public_training],
        )
        mtop_training_features, classes_b = _dual_features(
            encoder,
            [row.text for row in mtop_train],
        )
        public_validation_features, classes_c = _dual_features(
            encoder,
            [row.text for row in public_validation],
        )
        mtop_validation_features, classes_d = _dual_features(
            encoder,
            [row.text for row in mtop_validation],
        )
        oracle_features, classes_e = _dual_features(
            encoder,
            oracle_texts,
        )
    finally:
        router.close()
    if len({classes_a, classes_b, classes_c, classes_d, classes_e}) != 1:
        raise RuntimeError("lexical family feature identity changed")

    training_features = np.vstack(
        (public_training_features, mtop_training_features)
    )
    training_inside = np.asarray(
        [
            row.inside_catalogue
            for row in (*public_training, *mtop_train)
        ],
        dtype=bool,
    )
    training_families = tuple(
        row.family for row in (*public_training, *mtop_train)
    )
    inside_features = training_features[training_inside]
    outside_features = training_features[~training_inside]
    synthetic = synthetic_cross_family_outliers(
        inside_features,
        [
            family
            for family, inside in zip(
                training_families,
                training_inside,
                strict=True,
            )
            if inside
        ],
        count=SYNTHETIC_OUTLIERS,
        random_state=RANDOM_STATE,
    )
    gate = fit_dual_representation_gate(
        inside_features,
        np.vstack((outside_features, synthetic)),
        random_state=RANDOM_STATE,
    )

    public_probabilities = gate.inside_probability(public_validation_features)
    public_inside = np.asarray(
        [row.inside_catalogue for row in public_validation],
        dtype=bool,
    )
    mtop_probabilities = gate.inside_probability(mtop_validation_features)
    mtop_inside = np.asarray(
        [row.inside_catalogue for row in mtop_validation],
        dtype=bool,
    )
    calibration_inside = np.concatenate(
        (
            public_probabilities[public_inside],
            mtop_probabilities[mtop_inside],
        )
    )
    threshold = zero_inside_loss_threshold(calibration_inside)
    public_accepted = public_probabilities >= threshold
    mtop_accepted = mtop_probabilities >= threshold
    oracle_probabilities = gate.inside_probability(oracle_features)
    oracle_accepted = oracle_probabilities >= threshold

    public_metrics = _partition_metrics(
        public_probabilities,
        public_inside,
        public_accepted,
    )
    mtop_metrics = _partition_metrics(
        mtop_probabilities,
        mtop_inside,
        mtop_accepted,
    )
    oracle_pricing = price_gate_against_oracles(
        oracle_rows,
        accepted=oracle_accepted.tolist(),
    )
    all_oos_verdict = candidate_verdict(
        public_inside_rejected=(
            int(public_metrics["inside_rejected"])
            + int(mtop_metrics["inside_rejected"])
        ),
        served_rows_lost=oracle_pricing["served_rows_lost"],
        outside_rows_newly_zero=oracle_pricing["outside_rows_newly_zero"],
    )

    hard_negative_mask = routed_hard_negative_mask(
        inside_mask=training_inside,
        lexical_margins=training_features[:, -1],
        minimum_margin=MIN_PREDICTION_MARGIN,
    )
    hard_gate = fit_dual_representation_gate(
        inside_features,
        np.vstack((training_features[hard_negative_mask], synthetic)),
        random_state=RANDOM_STATE,
    )
    hard_public_probabilities = hard_gate.inside_probability(
        public_validation_features
    )
    hard_mtop_probabilities = hard_gate.inside_probability(
        mtop_validation_features
    )
    hard_threshold = zero_inside_loss_threshold(
        np.concatenate(
            (
                hard_public_probabilities[public_inside],
                hard_mtop_probabilities[mtop_inside],
            )
        )
    )
    hard_public_accepted = hard_public_probabilities >= hard_threshold
    hard_mtop_accepted = hard_mtop_probabilities >= hard_threshold
    hard_oracle_probabilities = hard_gate.inside_probability(oracle_features)
    hard_oracle_accepted = hard_oracle_probabilities >= hard_threshold
    hard_public_metrics = _partition_metrics(
        hard_public_probabilities,
        public_inside,
        hard_public_accepted,
    )
    hard_mtop_metrics = _partition_metrics(
        hard_mtop_probabilities,
        mtop_inside,
        hard_mtop_accepted,
    )
    hard_oracle_pricing = price_gate_against_oracles(
        oracle_rows,
        accepted=hard_oracle_accepted.tolist(),
    )
    hard_verdict = candidate_verdict(
        public_inside_rejected=(
            int(hard_public_metrics["inside_rejected"])
            + int(hard_mtop_metrics["inside_rejected"])
        ),
        served_rows_lost=hard_oracle_pricing["served_rows_lost"],
        outside_rows_newly_zero=hard_oracle_pricing[
            "outside_rows_newly_zero"
        ],
    )

    nonlinear_gate = fit_nonlinear_dual_representation_gate(
        inside_features,
        np.vstack((outside_features, synthetic)),
        random_state=RANDOM_STATE,
    )
    nonlinear_public_probabilities = nonlinear_gate.inside_probability(
        public_validation_features
    )
    nonlinear_mtop_probabilities = nonlinear_gate.inside_probability(
        mtop_validation_features
    )
    nonlinear_threshold = zero_inside_loss_threshold(
        np.concatenate(
            (
                nonlinear_public_probabilities[public_inside],
                nonlinear_mtop_probabilities[mtop_inside],
            )
        )
    )
    nonlinear_public_accepted = (
        nonlinear_public_probabilities >= nonlinear_threshold
    )
    nonlinear_mtop_accepted = (
        nonlinear_mtop_probabilities >= nonlinear_threshold
    )
    nonlinear_oracle_probabilities = nonlinear_gate.inside_probability(
        oracle_features
    )
    nonlinear_oracle_accepted = (
        nonlinear_oracle_probabilities >= nonlinear_threshold
    )
    nonlinear_public_metrics = _partition_metrics(
        nonlinear_public_probabilities,
        public_inside,
        nonlinear_public_accepted,
    )
    nonlinear_mtop_metrics = _partition_metrics(
        nonlinear_mtop_probabilities,
        mtop_inside,
        nonlinear_mtop_accepted,
    )
    nonlinear_oracle_pricing = price_gate_against_oracles(
        oracle_rows,
        accepted=nonlinear_oracle_accepted.tolist(),
    )
    nonlinear_verdict = candidate_verdict(
        public_inside_rejected=(
            int(nonlinear_public_metrics["inside_rejected"])
            + int(nonlinear_mtop_metrics["inside_rejected"])
        ),
        served_rows_lost=nonlinear_oracle_pricing["served_rows_lost"],
        outside_rows_newly_zero=nonlinear_oracle_pricing[
            "outside_rows_newly_zero"
        ],
    )
    report: dict[str, object] = {
        "schema": "baxy.mtop-dual-oos-recovery-candidate.v1",
        "authority": "development_diagnostic_not_for_promotion",
        "verdict": nonlinear_verdict,
        "runtime_modified": False,
        "effects_executed": 0,
        "opened_v8": False,
        "v9_reserved": True,
        "mechanism": {
            "architecture": (
                "dual E5 plus lexical OOS gate trained with public and MTOP "
                "contract-projected hard negatives"
            ),
            "classifier": "balanced logistic regression",
            "synthetic_cross_family_outliers": SYNTHETIC_OUTLIERS,
            "selected_threshold": threshold,
            "threshold_selection": (
                "next float below minimum inside probability over public and "
                "MTOP validation; outside labels unused"
            ),
            "consumed_population_tuning": False,
        },
        "training": {
            "public_rows": len(public_training),
            "mtop_rows": len(mtop_train),
            "inside_rows": int(training_inside.sum()),
            "outside_rows": int((~training_inside).sum()),
            "synthetic_rows": len(synthetic),
            "historical_or_private_rows": 0,
        },
        "public_validation": public_metrics,
        "mtop_validation": mtop_metrics,
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
        "all_oos_reference_variant": {
            "verdict": all_oos_verdict,
            "selected_threshold": threshold,
            "training_outside_rows": int((~training_inside).sum()),
            "public_validation": public_metrics,
            "mtop_validation": mtop_metrics,
            "oracle_pricing": oracle_pricing,
        },
        "routed_hard_negative_variant": {
            "verdict": hard_verdict,
            "minimum_family_margin": MIN_PREDICTION_MARGIN,
            "training_outside_rows": int(hard_negative_mask.sum()),
            "selected_threshold": hard_threshold,
            "public_validation": hard_public_metrics,
            "mtop_validation": hard_mtop_metrics,
            "oracle_pricing": hard_oracle_pricing,
            "classifier_coefficients_sha256": _array_sha256(
                np.asarray(hard_gate.classifier.coef_, dtype=np.float64)
            ),
            "classifier_intercept_sha256": _array_sha256(
                np.asarray(hard_gate.classifier.intercept_, dtype=np.float64)
            ),
            "oracle_scores": [
                {
                    "population": row.population,
                    "row_id": row.row_id,
                    "inside_probability": float(probability),
                    "inside_boundary": bool(accepted),
                }
                for row, probability, accepted in zip(
                    oracle_rows,
                    hard_oracle_probabilities,
                    hard_oracle_accepted,
                    strict=True,
                )
            ],
        },
        "nonlinear_all_oos_variant": {
            "verdict": nonlinear_verdict,
            "classifier": "MLP 128x64 ReLU with early stopping",
            "training_outside_rows": int((~training_inside).sum()),
            "selected_threshold": nonlinear_threshold,
            "iterations": int(nonlinear_gate.classifier.n_iter_),
            "loss": float(nonlinear_gate.classifier.loss_),
            "public_validation": nonlinear_public_metrics,
            "mtop_validation": nonlinear_mtop_metrics,
            "oracle_pricing": nonlinear_oracle_pricing,
            "classifier_coefficients_sha256": [
                _array_sha256(np.asarray(weights, dtype=np.float64))
                for weights in nonlinear_gate.classifier.coefs_
            ],
            "classifier_intercepts_sha256": [
                _array_sha256(np.asarray(biases, dtype=np.float64))
                for biases in nonlinear_gate.classifier.intercepts_
            ],
            "oracle_scores": [
                {
                    "population": row.population,
                    "row_id": row.row_id,
                    "inside_probability": float(probability),
                    "inside_boundary": bool(accepted),
                }
                for row, probability, accepted in zip(
                    oracle_rows,
                    nonlinear_oracle_probabilities,
                    nonlinear_oracle_accepted,
                    strict=True,
                )
            ],
        },
        "population_refutability": {
            "inside_loss": [
                "MASSIVE/PRESTO public validation inside rows",
                "MTOP validation candidate and missing-information rows",
                *oracle_pricing["refuting_populations"]["served_loss"],
            ],
            "outside_rejection": [
                "MASSIVE/PRESTO public validation outside rows",
                "MTOP validation ood_no_effect rows",
                *oracle_pricing["refuting_populations"]["outside_non_empty"],
            ],
        },
        "identities": {
            "program_sha256": _sha256(Path(__file__)),
            "public_training_sha256": _sha256(PUBLIC_TRAINING),
            "public_validation_sha256": _sha256(PUBLIC_VALIDATION),
            "mtop_development_sha256": _sha256(MTOP_DEVELOPMENT),
            "classifier_coefficients_sha256": _array_sha256(
                np.asarray(gate.classifier.coef_, dtype=np.float64)
            ),
            "classifier_intercept_sha256": _array_sha256(
                np.asarray(gate.classifier.intercept_, dtype=np.float64)
            ),
            "runtime": public_runtime_identity(runtime),
        },
        "source_contract": {
            "mtop_license": "CC-BY-SA-4.0",
            "mtop_test_opened": False,
            "development_split_only": True,
            "execution_authority": False,
        },
        "rejection_rule": (
            "reject on any public/MTOP validation inside loss, any consumed "
            "served identity loss, or zero newly-empty consumed outside rows"
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
                "threshold": report["nonlinear_all_oos_variant"][
                    "selected_threshold"
                ],
                "public_validation": {
                    key: report["nonlinear_all_oos_variant"][
                        "public_validation"
                    ][key]
                    for key in (
                        "inside_rows",
                        "inside_rejected",
                        "outside_rows",
                        "outside_rejected",
                    )
                },
                "mtop_validation": {
                    key: report["nonlinear_all_oos_variant"][
                        "mtop_validation"
                    ][key]
                    for key in (
                        "inside_rows",
                        "inside_rejected",
                        "outside_rows",
                        "outside_rejected",
                    )
                },
                "oracle_pricing": {
                    key: report["nonlinear_all_oos_variant"][
                        "oracle_pricing"
                    ][key]
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
