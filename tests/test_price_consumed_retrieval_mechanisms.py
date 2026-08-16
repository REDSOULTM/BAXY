from __future__ import annotations

import json
from pathlib import Path

from baxy_mind import __main__ as mind_main
from experiments.mind_router_spike import price_consumed_retrieval_mechanisms as pricing


def _snapshot(
    *,
    row_id: str,
    expected: tuple[str, ...],
    baseline: tuple[str, ...],
    without_fallback: tuple[str, ...],
    raw: tuple[str, ...],
    final: tuple[str, ...],
) -> pricing.RowSnapshot:
    return pricing.RowSnapshot(
        population="fixture",
        row_id=row_id,
        role="served" if expected else "outside_catalogue",
        expected_operations=expected,
        baseline_candidates=baseline,
        candidates_without={
            "fallback_after_abstention": without_fallback,
            "semantic_family_arbiter": baseline,
            "literal_reference_bridges": baseline,
            "domain_gate": baseline,
            "post_decision_verifiers": baseline,
        },
        raw_operations=raw,
        final_operations=final,
        first_veto="domain_grounding" if raw != final else None,
        candidate_prompt_bytes=pricing.candidate_prompt_bytes(baseline),
    )


def test_report_names_candidate_loss_leak_and_prompt_delta_by_row() -> None:
    served = _snapshot(
        row_id="served-1",
        expected=("audio.status",),
        baseline=("audio.status", "filesystem.read"),
        without_fallback=("filesystem.read",),
        raw=("audio.status",),
        final=("audio.status",),
    )
    outside = _snapshot(
        row_id="outside-1",
        expected=(),
        baseline=("filesystem.read",),
        without_fallback=(),
        raw=("filesystem.read",),
        final=(),
    )

    report = pricing.build_report([served, outside])
    fallback = report["mechanisms"]["fallback_after_abstention"]
    domain = report["mechanisms"]["domain_gate"]

    assert [row["row_id"] for row in fallback["candidate_set_changed_rows"]] == [
        "outside-1",
        "served-1",
    ]
    assert fallback["correct_operation_lost_rows"] == ["served-1"]
    assert fallback["leak_avoided_rows"] == []
    assert fallback["prompt_cost_delta_bytes"] < 0
    assert domain["leak_avoided_rows"] == ["outside-1"]
    assert domain["decision_changed_rows"] == ["outside-1"]
    assert report["metrics"]["candidate_entries"] == 3
    assert report["metrics"]["rows_with_candidates"] == 2
    assert (
        report["recommendations_by_mechanism"]["domain_gate"]["verdict"]
        == "preserve_observed_effect"
    )


def test_every_zero_names_populations_that_could_refute_it() -> None:
    snapshot = _snapshot(
        row_id="served-1",
        expected=("audio.status",),
        baseline=("audio.status",),
        without_fallback=("audio.status",),
        raw=("audio.status",),
        final=("audio.status",),
    )

    report = pricing.build_report([snapshot])

    for mechanism in report["mechanisms"].values():
        for metric_name in pricing.ZERO_AUDITED_METRICS:
            if mechanism[metric_name] in (0, []):
                assert mechanism["zero_refuters"][metric_name] == ["fixture"]


def test_consumed_population_manifest_includes_required_rows_without_v8() -> None:
    manifest = pricing.population_manifest()
    names = {entry.name for entry in manifest}

    assert names == {
        "catalog_surface_current_tree_r2",
        "generalization_product_current_tree_r28",
        "veto_reach_v1",
        "veto_reach_v2",
        "veto_reach_v3",
        "veto_reach_v4",
        "veto_reach_v5",
        "veto_reach_v6",
        "veto_reach_v7",
        "physical_dependent_missions_text_v1",
    }
    assert all("v8" not in entry.name.casefold() for entry in manifest)


def test_write_report_labels_diagnostic_and_is_reproducible(tmp_path: Path) -> None:
    output = tmp_path / "pricing.json"
    tool_payloads = {
        "audio.status": {
            "name": "audio.status",
            "description": "Read audio.",
            "arguments_schema": {},
        }
    }

    def evaluator(
        inputs: list[pricing.PopulationInput],
    ) -> tuple[
        list[pricing.CounterfactualRow],
        dict[str, dict[str, object]],
        dict[str, object],
    ]:
        assert inputs
        return [
            pricing.CounterfactualRow(
                population="fixture",
                row_id="served",
                text="audio",
                expected_operations=("audio.status",),
                variants={
                    "baseline": ("audio.status",),
                    "without_fallback_after_abstention": (),
                },
                decision_variants={},
            )
        ], tool_payloads, {"encoder": "fixture"}

    first = pricing.run(output, evaluator=evaluator)
    first_bytes = output.read_bytes()
    second = pricing.run(output, evaluator=evaluator)

    assert first == second
    assert output.read_bytes() == first_bytes
    assert first["authority"] == "development_diagnostic_not_for_promotion"
    assert first["effects_executed"] == 0
    assert first["opened_v8"] is False
    assert first["source_tree_modified"] is False
    json.loads(first_bytes)


def test_counterfactual_metrics_score_recall_false_candidates_and_prompt_bytes() -> None:
    rows = [
        pricing.CounterfactualRow(
            population="fixture",
            row_id="served",
            text="revisa el audio",
            expected_operations=("audio.status",),
            variants={
                "baseline": ("audio.status", "filesystem.read"),
                "without_fallback_after_abstention": ("filesystem.read",),
            },
            decision_variants={},
        ),
        pricing.CounterfactualRow(
            population="fixture",
            row_id="outside",
            text="riega las plantas",
            expected_operations=(),
            variants={
                "baseline": ("filesystem.read",),
                "without_fallback_after_abstention": (),
            },
            decision_variants={},
            outside_catalogue=True,
        ),
        pricing.CounterfactualRow(
            population="fixture",
            row_id="knowledge",
            text="que es la fotosintesis",
            expected_operations=(),
            variants={
                "baseline": ("filesystem.read",),
                "without_fallback_after_abstention": (),
            },
            decision_variants={},
        ),
    ]

    report = pricing.build_counterfactual_report(rows, tool_payloads={
        "audio.status": {
            "name": "audio.status",
            "description": "Read audio.",
            "arguments_schema": {},
        },
        "filesystem.read": {
            "name": "filesystem.read",
            "description": "Read file.",
            "arguments_schema": {},
        },
    })

    baseline = report["variant_metrics"]["baseline"]
    without = report["variant_metrics"]["without_fallback_after_abstention"]
    fallback = report["mechanisms"]["fallback_after_abstention"]
    assert baseline["expected_operation_recall"] == {
        "recalled": 1,
        "expected": 1,
        "ratio": 1.0,
    }
    assert baseline["outside_catalogue_false_candidate_rows"] == ["fixture:outside"]
    assert baseline["outside_catalogue_false_candidate_entries"] == 1
    assert baseline["prompt_bytes"] > without["prompt_bytes"]
    assert fallback["rows_requiring_preservation"] == ["fixture:served"]
    assert fallback["false_candidate_rows_avoided"] == ["fixture:outside"]


def test_required_population_rows_load_text_and_oracles_without_v8() -> None:
    rows, unavailable = pricing.load_population_inputs()

    assert len(rows) == 1133
    assert all(row.text.strip() for row in rows)
    assert all("v8" not in row.population.casefold() for row in rows)
    assert unavailable == []
    assert {
        row.population for row in rows
    } == {entry.name for entry in pricing.population_manifest()}


def test_consumed_bridge_characterization_supports_pruning() -> None:
    report = json.loads(pricing.DEFAULT_OUTPUT.read_text(encoding="utf-8"))

    assert len(
        report["mechanisms"]["fallback_after_abstention"][
            "rows_requiring_preservation"
        ]
    ) == 12
    assert len(
        report["mechanisms"]["semantic_family_arbiter"][
            "rows_requiring_preservation"
        ]
    ) == 13
    assert (
        report["recommendations_by_mechanism"]["post_decision_verifiers"][
            "verdict"
        ]
        == "preserve_observed_recall"
    )
    assert (
        report["recommendations_by_mechanism"]["domain_gate"]["verdict"]
        == "inconclusive_no_prune"
    )

    for mechanism in (
        "literal_schema_bridge",
        "message_reference_bridge",
        "explicit_ocr_bridge",
    ):
        measurement = report["mechanisms"][mechanism]
        assert measurement["candidate_set_changed_rows"] == []
        assert measurement["rows_requiring_preservation"] == []
        assert measurement["zero_refuters"]

    application = report["mechanisms"]["application_reference_bridge"]
    assert application["candidate_set_changed_rows"]
    assert application["rows_requiring_preservation"] == []
    assert len(application["downstream_comparisons"]) == len(
        application["candidate_set_changed_rows"]
    )
    assert all(row["equivalent"] for row in application["downstream_comparisons"])


def test_redundant_bridge_symbols_are_absent_from_runtime() -> None:
    for symbol in (
        "_families_grounded_by_literal_schema",
        "_application_reference_retrieval_families",
        "_message_reference_retrieval_families",
        "_families_grounded_by_explicit_ocr_language",
    ):
        assert not hasattr(mind_main, symbol)
