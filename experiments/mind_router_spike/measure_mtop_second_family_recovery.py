"""Measure additive second-family recovery when classifiers disagree."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from baxy_mind.family_classifier import (
    MIN_PREDICTION_MARGIN,
    FamilyClassifier,
    FamilyPrediction,
)
from experiments.mind_router_spike import (
    price_consumed_retrieval_mechanisms as pricing,
)
from experiments.mind_router_spike.measure_mtop_dual_oos_recovery import (
    EXPECTED_MTOP_SHA256,
    MTOP_DEVELOPMENT,
)
from experiments.mind_router_spike.measure_mtop_family_recovery import (
    CandidateFamilyClassifier,
    _candidate_training,
    _family_accuracy,
    classify_retrieval_delta,
)
from experiments.mind_router_spike.measure_multicluster_oos_recovery import (
    RETRIEVAL_BASELINE,
    _sha256,
)
from experiments.mind_router_spike.probe_heldout_family_classifier import (
    _fit_lexical,
    _normal_key,
    _qualifying_pool,
    _universal_holdout,
)
from experiments.mind_router_spike.probe_paraphrase_tool_quality import _oracle
from scripts.measure_mind_budget import (
    DEFAULT_CORE_CANDIDATES,
    current_core_capabilities,
    discover_core,
)

REPO = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = (
    REPO
    / "artifacts/development/mtop_second_family_recovery_candidate_20260813.json"
)


def disagree_additive_candidates(
    *,
    baseline: tuple[str, ...],
    existing_prediction: FamilyPrediction | None,
    candidate_prediction: FamilyPrediction | None,
    tools_by_family: dict[str, tuple[str, ...]],
    limit: int,
) -> tuple[str, ...]:
    """Append a second family when MTOP disagrees or fills abstention.

    Never removes baseline candidates. Truncation may still prevent full
    family append when the shortlist is already saturated.
    """
    if candidate_prediction is None:
        return baseline
    if (
        existing_prediction is not None
        and existing_prediction.family == candidate_prediction.family
    ):
        return baseline
    selected = list(baseline)
    for operation in tools_by_family.get(candidate_prediction.family, ()):
        if operation not in selected:
            selected.append(operation)
        if len(selected) >= limit:
            break
    return tuple(selected)


def _tools_by_family(
    tool_payloads: dict[str, dict[str, Any]],
) -> dict[str, tuple[str, ...]]:
    grouped: dict[str, tuple[str, ...]] = {}
    for operation in tool_payloads:
        family = operation.split(".", 1)[0]
        grouped[family] = (*grouped.get(family, ()), operation)
    return grouped


def _additive_report(
    *,
    baseline_payload: dict[str, Any],
    inputs: list[pricing.PopulationInput],
    tool_payloads: dict[str, dict[str, Any]],
    existing_classifier: FamilyClassifier,
    candidate_classifier: CandidateFamilyClassifier,
    available_families: set[str],
) -> dict[str, object]:
    input_by_identity = {(row.population, row.row_id): row for row in inputs}
    tools_by_family = _tools_by_family(tool_payloads)
    recalled = 0
    expected_total = 0
    outside_rows: list[str] = []
    outside_entries = 0
    prompt_bytes = 0
    changed: list[str] = []
    gains: list[str] = []
    losses: list[str] = []
    false_losses: list[str] = []
    disagreement_fires = 0
    abstention_fires = 0
    rows: list[dict[str, object]] = []
    for baseline_row in baseline_payload["row_counterfactuals"]:
        identity = (
            str(baseline_row["population"]),
            str(baseline_row["row_id"]),
        )
        source = input_by_identity[identity]
        baseline = tuple(
            str(value) for value in baseline_row["candidate_sets"]["baseline"]
        )
        existing_prediction = existing_classifier.predict(
            source.text,
            available_families,
        )
        candidate_prediction = candidate_classifier.predict(
            source.text,
            available_families,
        )
        candidate = disagree_additive_candidates(
            baseline=baseline,
            existing_prediction=existing_prediction,
            candidate_prediction=candidate_prediction,
            tools_by_family=tools_by_family,
            limit=pricing.mind.MAX_SHORTLIST_OPERATIONS,
        )
        if candidate != baseline:
            if existing_prediction is None:
                abstention_fires += 1
            else:
                disagreement_fires += 1
        delta = classify_retrieval_delta(
            baseline=baseline,
            candidate=candidate,
            expected=source.expected_operations,
        )
        expected = set(source.expected_operations)
        qualified = f"{source.population}:{source.row_id}"
        expected_total += len(expected)
        recalled += len(expected & set(candidate))
        if source.outside_catalogue and candidate:
            outside_rows.append(qualified)
            outside_entries += len(candidate)
        prompt_bytes += pricing._tool_prompt_bytes(candidate, tool_payloads)
        if candidate != baseline:
            changed.append(qualified)
        if delta.dropped_recalled_operations:
            losses.append(qualified)
        if delta.instrument_false_loss:
            false_losses.append(qualified)
        if delta.newly_complete:
            gains.append(qualified)
        rows.append(
            {
                "population": source.population,
                "row_id": source.row_id,
                "baseline_candidates": list(baseline),
                "candidate_candidates": list(candidate),
                "existing_family": (
                    existing_prediction.family
                    if existing_prediction is not None
                    else None
                ),
                "candidate_family": (
                    candidate_prediction.family
                    if candidate_prediction is not None
                    else None
                ),
            }
        )
    return {
        "metrics": {
            "rows": len(rows),
            "expected_operation_recall": {
                "recalled": recalled,
                "expected": expected_total,
                "ratio": recalled / expected_total if expected_total else None,
            },
            "outside_catalogue_false_candidate_rows": outside_rows,
            "outside_catalogue_false_candidate_entries": outside_entries,
            "prompt_bytes": prompt_bytes,
            "disagreement_fires": disagreement_fires,
            "abstention_fires": abstention_fires,
        },
        "candidate_set_changed_rows": changed,
        "baseline_recalled_rows_lost": losses,
        "instrument_false_loss_rows": false_losses,
        "previously_missing_rows_gained": gains,
        "rows": rows,
    }


def _verdict(report: dict[str, object]) -> str:
    losses = report["baseline_recalled_rows_lost"]
    gains = list(report["previously_missing_rows_gained"])
    v_gains = [row for row in gains if row.startswith("veto_reach_v")]
    if losses:
        return "rejected_regression"
    if not v_gains:
        return "rejected_no_target_gain"
    return "promising_not_promoted"


def run(output: Path = DEFAULT_OUTPUT) -> dict[str, object]:
    if _sha256(MTOP_DEVELOPMENT) != EXPECTED_MTOP_SHA256:
        raise RuntimeError("MTOP development corpus identity changed")
    capabilities = current_core_capabilities(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES))
    )
    catalog_names = tuple(str(item["name"]) for item in capabilities)
    available_families = {name.split(".", 1)[0] for name in catalog_names}
    texts, labels, training = _candidate_training(capabilities)
    pipeline = _fit_lexical(texts, labels, 0.3)
    candidate_classifier = CandidateFamilyClassifier(
        pipeline,
        minimum_margin=MIN_PREDICTION_MARGIN,
    )
    existing_classifier = FamilyClassifier()

    primary_holdout = _oracle(catalog_names)
    qualifying = _qualifying_pool(catalog_names)
    primary_keys = {_normal_key(str(row["text"])) for row in primary_holdout}
    qualifying_training = [
        row
        for row in qualifying
        if _normal_key(str(row["text"])) not in primary_keys
    ]
    universal_holdout = _universal_holdout(
        qualifying_training,
        cases=min(20, len({str(row["family"]) for row in qualifying_training})),
    )
    family_validation = {
        "primary_existing": _family_accuracy(
            existing_classifier,
            primary_holdout,
            available_families,
        ),
        "primary_candidate": _family_accuracy(
            candidate_classifier,
            primary_holdout,
            available_families,
        ),
        "universal_existing": _family_accuracy(
            existing_classifier,
            universal_holdout,
            available_families,
        ),
        "universal_candidate": _family_accuracy(
            candidate_classifier,
            universal_holdout,
            available_families,
        ),
    }

    inputs, unavailable = pricing.load_population_inputs()
    if unavailable:
        raise RuntimeError(f"oracle populations unavailable: {unavailable}")
    # Tool payloads come from a baseline recompute without replacing the classifier.
    _, tool_payloads, identities = pricing.recompute_counterfactual_rows(inputs)
    baseline_payload = json.loads(RETRIEVAL_BASELINE.read_text(encoding="utf-8"))
    baseline_metrics = baseline_payload["variant_metrics"]["baseline"]
    additive = _additive_report(
        baseline_payload=baseline_payload,
        inputs=inputs,
        tool_payloads=tool_payloads,
        existing_classifier=existing_classifier,
        candidate_classifier=candidate_classifier,
        available_families=available_families,
    )
    verdict = _verdict(additive)
    gains = list(additive["previously_missing_rows_gained"])
    v_gains = [row for row in gains if row.startswith("veto_reach_v")]
    coefficients = np.asarray(
        pipeline.named_steps["classifier"].coef_,
        dtype=np.float64,
    )
    report: dict[str, object] = {
        "schema": "baxy.mtop-second-family-recovery-candidate.v1",
        "authority": "development_diagnostic_not_for_promotion",
        "verdict": verdict,
        "runtime_modified": False,
        "effects_executed": 0,
        "opened_v8": False,
        "v9_reserved": True,
        "mechanism": {
            "classifier": "word+character TF-IDF class-balanced LinearSVC",
            "c": 0.3,
            "minimum_prediction_margin": MIN_PREDICTION_MARGIN,
            "delta": (
                "keep every baseline candidate; append MTOP-family operations "
                "when the MTOP-augmented classifier disagrees with the frozen "
                "family classifier or fills its abstention"
            ),
            "consumed_population_training_or_selection": False,
        },
        "training": training,
        "family_validation": family_validation,
        "retrieval": {
            "baseline": baseline_metrics,
            "candidate": additive["metrics"],
            "baseline_recalled_rows_lost": additive["baseline_recalled_rows_lost"],
            "instrument_false_loss_rows": additive["instrument_false_loss_rows"],
            "previously_missing_rows_gained": gains,
            "v1_v7_serviceable_rows_gained": v_gains,
        },
        "disagree_additive_variant": {
            "verdict": verdict,
            **additive,
            "v1_v7_serviceable_rows_gained": v_gains,
        },
        "population_refutability": {
            "family_generalization": [
                "primary family holdout",
                "universal long-tail family holdout",
            ],
            "operation_identity": sorted(
                {
                    str(row["population"])
                    for row in baseline_payload["row_counterfactuals"]
                    if row.get("expected_operations")
                }
            ),
            "outside_non_empty": sorted(
                {
                    str(row["population"])
                    for row in baseline_payload["row_counterfactuals"]
                    if row.get("outside_catalogue")
                }
            ),
            "target_serviceable_gain": [
                "veto_reach_v1",
                "veto_reach_v2",
                "veto_reach_v3",
                "veto_reach_v4",
                "veto_reach_v5",
                "veto_reach_v6",
                "veto_reach_v7",
            ],
        },
        "identities": {
            "program_sha256": _sha256(Path(__file__)),
            "mtop_development_sha256": _sha256(MTOP_DEVELOPMENT),
            "retrieval_baseline_sha256": _sha256(RETRIEVAL_BASELINE),
            "classifier_coefficients_sha256": hashlib.sha256(
                np.ascontiguousarray(coefficients).tobytes()
            ).hexdigest(),
            "pricing_runtime": identities,
        },
        "adoption_rule": (
            "no baseline-recalled expected operation may be dropped; at least "
            "one previously incomplete V1-V7 serviceable expected set must become "
            "complete; frozen family holdout is not replaced"
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
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
                "retrieval": {
                    "baseline": report["retrieval"]["baseline"][
                        "expected_operation_recall"
                    ],
                    "candidate": report["retrieval"]["candidate"][
                        "expected_operation_recall"
                    ],
                    "lost": report["retrieval"]["baseline_recalled_rows_lost"],
                    "gained": report["retrieval"]["previously_missing_rows_gained"],
                    "v1_v7_gained": report["retrieval"][
                        "v1_v7_serviceable_rows_gained"
                    ],
                    "disagreement_fires": report["retrieval"]["candidate"][
                        "disagreement_fires"
                    ],
                    "abstention_fires": report["retrieval"]["candidate"][
                        "abstention_fires"
                    ],
                    "outside_entries": report["retrieval"]["candidate"][
                        "outside_catalogue_false_candidate_entries"
                    ],
                },
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
