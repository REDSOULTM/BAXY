"""Measure MTOP positive augmentation of the closed-family retriever."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch

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
    load_mtop_development_rows,
)
from experiments.mind_router_spike.measure_multicluster_oos_recovery import (
    RETRIEVAL_BASELINE,
    _family_training_rows,
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
    / "artifacts/development/mtop_family_recovery_candidate_20260813.json"
)
DEFAULT_AUDIT_OUTPUT = (
    REPO
    / "artifacts/audit/mtop_family_recovery_loss_criterion_20260813.json"
)


class CandidateFamilyClassifier:
    def __init__(self, pipeline: Any, *, minimum_margin: float) -> None:
        self._pipeline = pipeline
        self._minimum_margin = float(minimum_margin)

    def predict(
        self,
        text: str,
        available_families: Iterable[str],
    ) -> FamilyPrediction | None:
        allowed = set(available_families)
        classes = tuple(str(value) for value in self._pipeline.classes_)
        scores = np.asarray(
            self._pipeline.decision_function([text]),
            dtype=np.float64,
        ).reshape(-1)
        allowed_indexes = [
            index for index, family in enumerate(classes) if family in allowed
        ]
        if not allowed_indexes:
            return None
        ordered = sorted(
            allowed_indexes,
            key=lambda index: float(scores[index]),
        )
        winner = ordered[-1]
        runner_up = ordered[-2] if len(ordered) > 1 else winner
        margin = float(scores[winner] - scores[runner_up])
        if margin < self._minimum_margin:
            return None
        return FamilyPrediction(family=classes[winner], margin=margin)


@dataclass(frozen=True, slots=True)
class RetrievalDelta:
    dropped_recalled_operations: tuple[str, ...]
    newly_recalled_operations: tuple[str, ...]
    instrument_false_loss: bool
    newly_complete: bool


def classify_retrieval_delta(
    *,
    baseline: Sequence[str],
    candidate: Sequence[str],
    expected: Sequence[str],
) -> RetrievalDelta:
    baseline_set = set(baseline)
    candidate_set = set(candidate)
    expected_set = set(expected)
    dropped = tuple(sorted((expected_set & baseline_set) - candidate_set))
    newly = tuple(sorted((expected_set & candidate_set) - baseline_set))
    incomplete_with_overlap = bool(expected_set & baseline_set) and not expected_set.issubset(
        candidate_set
    )
    return RetrievalDelta(
        dropped_recalled_operations=dropped,
        newly_recalled_operations=newly,
        instrument_false_loss=incomplete_with_overlap and not dropped,
        newly_complete=bool(expected_set)
        and not expected_set.issubset(baseline_set)
        and expected_set.issubset(candidate_set),
    )


def fallback_additive_candidates(
    *,
    baseline: tuple[str, ...],
    existing_prediction: FamilyPrediction | None,
    candidate_prediction: FamilyPrediction | None,
    tools_by_family: dict[str, tuple[str, ...]],
    limit: int,
) -> tuple[str, ...]:
    if existing_prediction is not None or candidate_prediction is None:
        return baseline
    selected = list(baseline)
    for operation in tools_by_family.get(candidate_prediction.family, ()):
        if operation not in selected:
            selected.append(operation)
        if len(selected) >= limit:
            break
    return tuple(selected)


def _family_accuracy(
    classifier: CandidateFamilyClassifier | FamilyClassifier,
    rows: list[dict[str, Any]],
    available_families: set[str],
) -> dict[str, object]:
    correct = 0
    abstained = 0
    failures: list[str] = []
    for index, row in enumerate(rows):
        prediction = classifier.predict(str(row["text"]), available_families)
        if prediction is None:
            abstained += 1
            failures.append(str(row.get("case_id") or index))
        elif prediction.family == row["family"]:
            correct += 1
        else:
            failures.append(str(row.get("case_id") or index))
    return {
        "rows": len(rows),
        "correct": correct,
        "abstained": abstained,
        "accuracy": correct / len(rows) if rows else None,
        "failure_ids": failures,
    }


def _candidate_training(
    capabilities: list[dict[str, Any]],
) -> tuple[list[str], list[str], dict[str, int]]:
    catalog_names = tuple(str(item["name"]) for item in capabilities)
    primary_holdout = _oracle(catalog_names)
    primary_keys = {_normal_key(str(row["text"])) for row in primary_holdout}
    qualifying = _qualifying_pool(catalog_names)
    qualifying_training = [
        row
        for row in qualifying
        if _normal_key(str(row["text"])) not in primary_keys
    ]
    universal_holdout = _universal_holdout(
        qualifying_training,
        cases=min(20, len({str(row["family"]) for row in qualifying_training})),
    )
    holdout_keys = primary_keys | {
        _normal_key(str(row["text"])) for row in universal_holdout
    }
    base_rows = _family_training_rows(capabilities)
    training_by_key = {
        _normal_key(row.text): (row.text, row.family, "base")
        for row in base_rows
    }
    available_families = {
        name.split(".", 1)[0] for name in catalog_names
    }
    mtop_added = 0
    for row in load_mtop_development_rows(MTOP_DEVELOPMENT):
        if (
            row.split != "train"
            or not row.inside_catalogue
            or row.family not in available_families
        ):
            continue
        key = _normal_key(row.text)
        if key in holdout_keys or key in training_by_key:
            continue
        training_by_key[key] = (row.text, row.family, "mtop")
        mtop_added += 1
    values = list(training_by_key.values())
    return (
        [text for text, _, _ in values],
        [family for _, family, _ in values],
        {
            "base_rows": sum(source == "base" for _, _, source in values),
            "mtop_rows_added": mtop_added,
            "rows": len(values),
            "holdout_overlap": 0,
        },
    )


def _row_metrics(
    baseline_payload: dict[str, Any],
    candidate_rows: list[pricing.CounterfactualRow],
) -> dict[str, object]:
    baseline_by_identity = {
        (str(row["population"]), str(row["row_id"])): tuple(
            str(value) for value in row["candidate_sets"]["baseline"]
        )
        for row in baseline_payload["row_counterfactuals"]
    }
    losses: list[str] = []
    false_losses: list[str] = []
    gains: list[str] = []
    changed: list[str] = []
    for row in candidate_rows:
        identity = row.population, row.row_id
        baseline = baseline_by_identity[identity]
        candidate = tuple(str(value) for value in row.variants["baseline"])
        delta = classify_retrieval_delta(
            baseline=baseline,
            candidate=candidate,
            expected=row.expected_operations,
        )
        qualified = f"{row.population}:{row.row_id}"
        if set(baseline) != set(candidate):
            changed.append(qualified)
        if delta.dropped_recalled_operations:
            losses.append(qualified)
        if delta.instrument_false_loss:
            false_losses.append(qualified)
        if delta.newly_complete:
            gains.append(qualified)
    return {
        "candidate_set_changed_rows": changed,
        "baseline_recalled_rows_lost": losses,
        "instrument_false_loss_rows": false_losses,
        "previously_missing_rows_gained": gains,
    }


def _fallback_additive_report(
    *,
    baseline_payload: dict[str, Any],
    inputs: list[pricing.PopulationInput],
    tool_payloads: dict[str, dict[str, Any]],
    existing_classifier: FamilyClassifier,
    candidate_classifier: CandidateFamilyClassifier,
    available_families: set[str],
) -> dict[str, object]:
    input_by_identity = {
        (row.population, row.row_id): row
        for row in inputs
    }
    tools_by_family: dict[str, tuple[str, ...]] = {}
    for operation in tool_payloads:
        family = operation.split(".", 1)[0]
        tools_by_family[family] = (
            *tools_by_family.get(family, ()),
            operation,
        )

    recalled = 0
    expected_total = 0
    outside_rows: list[str] = []
    outside_entries = 0
    prompt_bytes = 0
    changed: list[str] = []
    gains: list[str] = []
    losses: list[str] = []
    false_losses: list[str] = []
    rows: list[dict[str, object]] = []
    for baseline_row in baseline_payload["row_counterfactuals"]:
        identity = (
            str(baseline_row["population"]),
            str(baseline_row["row_id"]),
        )
        source = input_by_identity[identity]
        baseline = tuple(
            str(value)
            for value in baseline_row["candidate_sets"]["baseline"]
        )
        existing_prediction = existing_classifier.predict(
            source.text,
            available_families,
        )
        candidate_prediction = candidate_classifier.predict(
            source.text,
            available_families,
        )
        candidate = fallback_additive_candidates(
            baseline=baseline,
            existing_prediction=existing_prediction,
            candidate_prediction=candidate_prediction,
            tools_by_family=tools_by_family,
            limit=pricing.mind.MAX_SHORTLIST_OPERATIONS,
        )
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
                "ratio": recalled / expected_total,
            },
            "outside_catalogue_false_candidate_rows": outside_rows,
            "outside_catalogue_false_candidate_entries": outside_entries,
            "prompt_bytes": prompt_bytes,
        },
        "candidate_set_changed_rows": changed,
        "baseline_recalled_rows_lost": losses,
        "instrument_false_loss_rows": false_losses,
        "previously_missing_rows_gained": gains,
        "rows": rows,
    }


def run(output: Path = DEFAULT_OUTPUT) -> dict[str, object]:
    if _sha256(MTOP_DEVELOPMENT) != EXPECTED_MTOP_SHA256:
        raise RuntimeError("MTOP development corpus identity changed")
    capabilities = current_core_capabilities(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES))
    )
    catalog_names = tuple(str(item["name"]) for item in capabilities)
    available_families = {
        name.split(".", 1)[0] for name in catalog_names
    }
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
    mtop_validation = [
        {
            "case_id": row.source_id,
            "text": row.text,
            "family": row.family,
        }
        for row in load_mtop_development_rows(MTOP_DEVELOPMENT)
        if row.split == "validation" and row.inside_catalogue and row.family
    ]
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
        "mtop_candidate": _family_accuracy(
            candidate_classifier,
            mtop_validation,
            available_families,
        ),
    }

    inputs, unavailable = pricing.load_population_inputs()
    if unavailable:
        raise RuntimeError(f"oracle populations unavailable: {unavailable}")
    with patch.object(
        pricing,
        "FamilyClassifier",
        return_value=candidate_classifier,
    ):
        candidate_rows, tool_payloads, identities = (
            pricing.recompute_counterfactual_rows(inputs)
        )
    candidate_pricing = pricing.build_counterfactual_report(
        candidate_rows,
        tool_payloads=tool_payloads,
    )
    baseline_payload = json.loads(RETRIEVAL_BASELINE.read_text(encoding="utf-8"))
    baseline_metrics = baseline_payload["variant_metrics"]["baseline"]
    candidate_metrics = candidate_pricing["variant_metrics"]["baseline"]
    row_metrics = _row_metrics(baseline_payload, candidate_rows)
    fallback_additive = _fallback_additive_report(
        baseline_payload=baseline_payload,
        inputs=inputs,
        tool_payloads=tool_payloads,
        existing_classifier=existing_classifier,
        candidate_classifier=candidate_classifier,
        available_families=available_families,
    )

    holdout_regression = any(
        family_validation[candidate]["correct"]
        < family_validation[existing]["correct"]
        for existing, candidate in (
            ("primary_existing", "primary_candidate"),
            ("universal_existing", "universal_candidate"),
        )
    )
    if row_metrics["baseline_recalled_rows_lost"] or holdout_regression:
        replacement_verdict = "rejected_regression"
    elif row_metrics["previously_missing_rows_gained"]:
        replacement_verdict = "promising_not_promoted"
    else:
        replacement_verdict = "rejected_no_recall_gain"
    if fallback_additive["baseline_recalled_rows_lost"]:
        verdict = "rejected_regression"
    elif fallback_additive["previously_missing_rows_gained"]:
        verdict = "promising_not_promoted"
    else:
        verdict = "rejected_no_recall_gain"
    coefficients = np.asarray(
        pipeline.named_steps["classifier"].coef_,
        dtype=np.float64,
    )
    report: dict[str, object] = {
        "schema": "baxy.mtop-family-recovery-candidate.v1",
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
                "add MTOP development candidate and missing-information rows "
                "to the existing positive family training"
            ),
            "consumed_population_training_or_selection": False,
        },
        "training": training,
        "family_validation": family_validation,
        "retrieval": {
            "baseline": baseline_metrics,
            "candidate": candidate_metrics,
            **row_metrics,
        },
        "replacement_variant": {
            "verdict": replacement_verdict,
            "retrieval": {
                "baseline": baseline_metrics,
                "candidate": candidate_metrics,
                **row_metrics,
            },
        },
        "fallback_additive_variant": {
            "verdict": verdict,
            **fallback_additive,
        },
        "population_refutability": {
            "family_generalization": [
                "primary family holdout",
                "universal long-tail family holdout",
                "MTOP validation candidate rows",
            ],
            "operation_identity": sorted(
                {row.population for row in candidate_rows if row.expected_operations}
            ),
            "outside_non_empty": sorted(
                {row.population for row in candidate_rows if row.outside_catalogue}
            ),
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
            "no baseline-recalled expected operation or frozen family-holdout "
            "correct row may be lost; at least one previously missing expected "
            "operation must be gained"
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def audit_published_loss_criterion(
    candidate_path: Path = DEFAULT_OUTPUT,
    baseline_path: Path = RETRIEVAL_BASELINE,
    output: Path = DEFAULT_AUDIT_OUTPUT,
) -> dict[str, object]:
    published = json.loads(candidate_path.read_text(encoding="utf-8"))
    baseline_payload = json.loads(baseline_path.read_text(encoding="utf-8"))
    expected_by_identity = {
        (str(row["population"]), str(row["row_id"])): tuple(
            str(value) for value in row["expected_operations"]
        )
        for row in baseline_payload["row_counterfactuals"]
    }
    outside_by_identity = {
        (str(row["population"]), str(row["row_id"])): bool(row["outside_catalogue"])
        for row in baseline_payload["row_counterfactuals"]
    }
    true_losses: list[str] = []
    false_losses: list[str] = []
    v_misses_abstained: list[str] = []
    v_misses_blocked_wrong: list[str] = []
    v_misses_blocked_same_family: list[str] = []
    for row in published["fallback_additive_variant"]["rows"]:
        identity = str(row["population"]), str(row["row_id"])
        expected = expected_by_identity[identity]
        delta = classify_retrieval_delta(
            baseline=tuple(str(value) for value in row["baseline_candidates"]),
            candidate=tuple(str(value) for value in row["candidate_candidates"]),
            expected=expected,
        )
        qualified = f"{identity[0]}:{identity[1]}"
        if delta.dropped_recalled_operations:
            true_losses.append(qualified)
        if delta.instrument_false_loss:
            false_losses.append(qualified)
        if (
            identity[0].startswith("veto_reach_v")
            and expected
            and not outside_by_identity[identity]
            and not set(expected).issubset(set(row["baseline_candidates"]))
        ):
            existing_family = row["existing_family"]
            expected_families = {item.split(".", 1)[0] for item in expected}
            if existing_family is None:
                v_misses_abstained.append(qualified)
            elif existing_family in expected_families:
                v_misses_blocked_same_family.append(qualified)
            else:
                v_misses_blocked_wrong.append(qualified)
    additive_gains = list(
        published["fallback_additive_variant"]["previously_missing_rows_gained"]
    )
    v_gains = [row for row in additive_gains if row.startswith("veto_reach_v")]
    corrected_verdict = (
        "rejected_regression"
        if true_losses
        else (
            "rejected_no_target_gain"
            if not v_gains
            else "promising_not_promoted"
        )
    )
    try:
        published_artifact = str(candidate_path.resolve().relative_to(REPO)).replace(
            "\\", "/"
        )
    except ValueError:
        published_artifact = str(candidate_path)
    report = {
        "schema": "baxy.mtop-family-recovery-loss-audit.v1",
        "authority": "development_diagnostic_not_for_promotion",
        "published_artifact": published_artifact,
        "published_verdict": published["verdict"],
        "corrected_additive_verdict": corrected_verdict,
        "mechanism_reading": (
            "The published loss list counted rows whose expected set was already "
            "incomplete in the baseline. A true loss requires dropping an expected "
            "operation the baseline had already recalled."
        ),
        "additive": {
            "published_losses": published["fallback_additive_variant"][
                "baseline_recalled_rows_lost"
            ],
            "true_dropped_recalled_rows": true_losses,
            "instrument_false_loss_rows": false_losses,
            "gained_rows": additive_gains,
            "v1_v7_serviceable_rows_gained": v_gains,
            "outside_catalogue_false_candidate_entries": {
                "baseline": published["retrieval"]["baseline"][
                    "outside_catalogue_false_candidate_entries"
                ],
                "candidate": published["fallback_additive_variant"]["metrics"][
                    "outside_catalogue_false_candidate_entries"
                ],
            },
        },
        "replacement": {
            "published_verdict": published["replacement_variant"]["verdict"],
            "holdout_regression": (
                published["family_validation"]["primary_candidate"]["correct"]
                < published["family_validation"]["primary_existing"]["correct"]
            ),
            "primary_existing_correct": published["family_validation"][
                "primary_existing"
            ]["correct"],
            "primary_candidate_correct": published["family_validation"][
                "primary_candidate"
            ]["correct"],
        },
        "v1_v7_serviceable_baseline_misses": {
            "existing_classifier_abstained": v_misses_abstained,
            "existing_classifier_wrong_family": v_misses_blocked_wrong,
            "existing_classifier_same_family": v_misses_blocked_same_family,
        },
        "runtime_modified": False,
        "opened_v8": False,
        "v9_reserved": True,
        "effects_executed": 0,
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
    parser.add_argument("--audit-published", action="store_true")
    args = parser.parse_args()
    if args.audit_published:
        report = audit_published_loss_criterion(candidate_path=args.output)
        print(
            json.dumps(
                {
                    "output": str(DEFAULT_AUDIT_OUTPUT),
                    "published_verdict": report["published_verdict"],
                    "corrected_additive_verdict": report["corrected_additive_verdict"],
                    "true_dropped_recalled_rows": report["additive"][
                        "true_dropped_recalled_rows"
                    ],
                    "instrument_false_loss_rows": report["additive"][
                        "instrument_false_loss_rows"
                    ],
                    "v1_v7_serviceable_rows_gained": report["additive"][
                        "v1_v7_serviceable_rows_gained"
                    ],
                    "v1_v7_miss_counts": {
                        key: len(value)
                        for key, value in report[
                            "v1_v7_serviceable_baseline_misses"
                        ].items()
                    },
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    report = run(args.output)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "verdict": report["verdict"],
                "training": report["training"],
                "family_validation": report["family_validation"],
                "retrieval": {
                    "baseline": report["retrieval"]["baseline"],
                    "candidate": report["fallback_additive_variant"]["metrics"],
                    "lost": report["fallback_additive_variant"][
                        "baseline_recalled_rows_lost"
                    ],
                    "gained": report["fallback_additive_variant"][
                        "previously_missing_rows_gained"
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
