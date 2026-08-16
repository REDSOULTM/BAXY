from __future__ import annotations

import copy
import hashlib
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_turn_policy_e5_selective_gate.py"
SPEC = importlib.util.spec_from_file_location(
    "verify_turn_policy_e5_selective_gate_under_test",
    SCRIPT,
)
assert SPEC is not None and SPEC.loader is not None
gate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = gate
SPEC.loader.exec_module(gate)


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _write_json(path: Path, value: object) -> None:
    gate.write_json_atomic(path, value)


def _head(
    kind: str,
    classes: list[str],
    coefficients: list[list[float]],
) -> dict[str, object]:
    body: dict[str, object] = {
        "kind": kind,
        "classes": classes,
        "dimensions": 2,
        "coefficients": coefficients,
        "intercepts": [0.01 * index for index in range(len(classes))],
    }
    return {
        **body,
        "weights_sha256": _sha(gate.canonical_json_bytes(body)),
    }


def _synthetic_evaluation(
    *,
    runtime_train_sha: str,
    runtime_validation_sha: str,
    mtop_sha: str,
    catalog_sha: str,
    map_sha: str,
) -> dict[str, object]:
    slice_metrics = {
        "accuracy_when_selected": 1.0,
        "selection_rate": 0.2,
        "unsafe_directional_errors": 0,
        "utterances": 10,
    }
    directional_safety = {
        "unsafe_conversation_as_supported": 0,
        "unsafe_conversation_as_supported_rate": 0.0,
        "unsafe_false_supported": 0,
        "unsafe_false_supported_rate": 0.0,
        "unsafe_ood_as_conversation": 0,
        "unsafe_ood_as_conversation_rate": 0.0,
        "unsafe_ood_as_supported": 0,
        "unsafe_ood_as_supported_rate": 0.0,
        "unsafe_supported_as_conversation": 0,
        "unsafe_supported_as_conversation_rate": 0.0,
    }
    artifact: dict[str, object] = {
        "schema": gate.EVALUATION_SCHEMA,
        "status": "development_only_not_runtime_authority",
        "privacy": {
            "contains_text": False,
            "contains_source_ids": False,
            "contains_mission_ids": False,
            "contains_model_responses": False,
            "contains_derived_model_parameters": True,
        },
        "constraints": {
            "used_splits": ["train", "validation"],
            "sealed_final_test_reserve_opened": False,
            "v4_opened": False,
            "mtop_candidate_is_advisory_only": True,
            "execution_authority": False,
            "requires_independent_llm_selection": True,
            "requires_schema_grounding_risk_confirmation_and_core_verification": True,
            "grouped_by_mission_id_before_fit_and_evaluation": True,
            "utterance_level_fit_and_evaluation": True,
            "mission_disjoint_calibration_and_evaluation": True,
            "ood_can_authorize_fast_chat": False,
            "selective_signal_can_authorize_execution": False,
            "normalized_text_split_overlap": 0,
        },
        "sources": [
            {
                "contains_test": False,
                "embedding_array_sha256": "4" * 64,
                "embedding_cache_manifest_sha256": "5" * 64,
                "name": "runtime_train",
                "row_fingerprint_sha256": "6" * 64,
                "rows": 20,
                "sha256": runtime_train_sha,
            },
            {
                "contains_test": False,
                "embedding_array_sha256": "7" * 64,
                "embedding_cache_manifest_sha256": "8" * 64,
                "name": "runtime_validation",
                "row_fingerprint_sha256": "9" * 64,
                "rows": 10,
                "sha256": runtime_validation_sha,
            },
            {
                "contains_test": False,
                "embedding_array_sha256": "a" * 64,
                "embedding_cache_manifest_sha256": "b" * 64,
                "name": "mtop_development",
                "row_fingerprint_sha256": "c" * 64,
                "rows": 30,
                "sha256": mtop_sha,
            },
        ],
        "catalog": {
            "families": 1,
            "mtop_projection_map": {
                "ood_intents": 1,
                "sha256": map_sha,
                "supported_intents": 1,
            },
            "public_operations": 1,
            "sha256": catalog_sha,
        },
        "encoder": {
            "file_count": 1,
            "manifest_algorithm": (
                "sha256(UTF-8/LF/final-LF lines: model, revision, then every file "
                "sorted by relative POSIX path UTF-8 bytes as "
                "path<TAB>size<TAB>sha256)"
            ),
            "manifest_sha256": "d" * 64,
            "model": "intfloat/multilingual-e5-small",
            "normalize_embeddings": True,
            "query_prefix": "query: ",
            "revision": "e" * 40,
            "weights": {"path": "model.safetensors", "sha256": "f" * 64},
        },
        "training": {
            "effect_c": 1.0,
            "family_c": 4.0,
            "fit_unit": "utterance_l2_normalized_mission_disjoint",
            "linear_solver": "lbfgs",
            "maximum_families": 8,
            "maximum_operations": 24,
            "no_effect_c": 1.0,
            "operation_c": 4.0,
            "sample_weight": (
                "equal_head_target_source_mass_then_inverse_mission_variants"
            ),
            "selective_guard_delta": 0.05,
            "validation_seed_sha256": "1" * 64,
        },
        "protocol": {
            "ambiguous_mtop_contract_structure_mismatch": "excluded",
            "calibration_split": (
                "validation_mission_partition_by_outcome_source_stage"
            ),
            "conformal_alpha": 0.05,
            "conformal_calibration": (
                "label_conditional_worst_utterance_per_mission"
            ),
            "conversation_fast_path_requires": (
                "effect_no_effect_singleton_and_conversation_singleton_and_guard"
            ),
            "corrected_missing_information": "supported_effect_requires_clarify",
            "effect_classes": ["no_effect", "supported_effect"],
            "embedding_cache_v1_reuse": (
                "encoder_rows_only_disposition_cannot_change_embeddings"
            ),
            "evaluation_split": (
                "disjoint_validation_missions_evaluated_per_utterance"
            ),
            "hierarchical_disposition_binding": (
                "pinned_source_projection_map_and_v2_group_fingerprint"
            ),
            "hierarchy": "effect_gate_then_no_effect_disposition",
            "mtop_ood_negative_requires": "mapped_intent_in_reviewed_ood_partition",
            "no_effect_classes": ["conversation_no_effect", "unsupported_ood"],
            "outcome_classes": [
                "conversation_no_effect",
                "unsupported_ood",
                "supported_effect",
            ],
            "selective_guard_comparator": "strictly_greater_than",
            "unsupported_ood_fast_path": "forbidden",
        },
        "groups": {
            "calibration": 10,
            "calibration_fingerprint_sha256": "2" * 64,
            "evaluation": 10,
            "evaluation_fingerprint_sha256": "3" * 64,
            "train": 20,
            "train_fingerprint_sha256": "4" * 64,
        },
        "heads": {
            "effect_gate": _head(
                "softmax",
                ["no_effect", "supported_effect"],
                [[0.1, 0.2], [0.3, 0.4]],
            ),
            "family_shortlist": _head(
                "one_vs_rest", ["app"], [[0.1, 0.2]]
            ),
            "no_effect_disposition": _head(
                "softmax",
                ["conversation_no_effect", "unsupported_ood"],
                [[0.2, 0.1], [0.4, 0.3]],
            ),
            "operation_shortlist": _head(
                "one_vs_rest", ["app.open"], [[0.2, 0.1]]
            ),
        },
        "conformal": {
            "effect_gate": {
                "calibration": "label_conditional_by_mission",
                "nonconformity": "mission_max_over_utterances_of_1-p_true",
                "thresholds": {"no_effect": 0.5, "supported_effect": 0.5},
            },
            "no_effect_disposition": {
                "calibration": "label_conditional_by_mission",
                "nonconformity": "mission_max_over_utterances_of_1-p_true",
                "thresholds": {
                    "conversation_no_effect": 0.5,
                    "unsupported_ood": 0.5,
                },
            },
            "family": {
                "nonconformity": (
                    "mission_max_over_utterances_of_1-min_true_probability"
                ),
                "threshold": 0.5,
            },
            "operation": {
                "nonconformity": (
                    "mission_max_over_utterances_of_1-min_true_probability"
                ),
                "threshold": 0.5,
            },
        },
        "selective_guards": {
            "conversation_fast_path": {
                "calibration_false_accepts": 0,
                "calibration_missions": 20,
                "threshold": 0.9,
                "tolerance_delta": 0.05,
                "wilks_upper_rate": 0.005,
            },
            "supported_effect": {
                "calibration_false_accepts": 0,
                "calibration_missions": 20,
                "threshold": 0.9,
                "tolerance_delta": 0.05,
                "wilks_upper_rate": 0.005,
            },
        },
        "exclusions": {
            "cross_split_conflicting_exact_text_missions_removed": 0,
            "cross_split_conflicting_exact_text_rows_removed": 0,
            "mtop_contract_structure_mismatch_ambiguous": 0,
        },
        "metrics": {
            "effect_gate": {
                "mission_all_variants_coverage": 0.95,
                "utterance_coverage": 0.95,
                "utterance_singleton_accuracy": 0.9,
            },
            "family_shortlist": {
                "abstention_rate": 0.04,
                "coverage": 0.96,
                "maximum_size": 1,
                "trials": 10,
            },
            "groups": 10,
            "mission_level": {
                "all_variants_correct": 0.8,
                "any_variant_selected": 0.2,
                "missions": 10,
                "missions_with_directional_error": 0,
            },
            "no_effect_disposition": {
                "mission_all_variants_coverage": 0.95,
                "utterance_coverage": 0.95,
                "utterance_singleton_accuracy": 0.9,
                "utterances": 946,
            },
            "operation_shortlist": {
                "abstention_rate": 0.05,
                "coverage": 0.95,
                "maximum_size": 1,
                "trials": 10,
            },
            "per_dataset": {
                "mtop_official": dict(slice_metrics),
                "runtime_public": dict(slice_metrics),
            },
            "per_locale": {
                "en": dict(slice_metrics),
                "es": dict(slice_metrics),
                "und": dict(slice_metrics),
            },
            "selective_outcome": {
                "abstention_rate": 0.85,
                "accuracy_when_selected": 0.99,
                "correct_utterance_rate": 0.15,
                "directional_safety": directional_safety,
                "per_class": {
                    "conversation_no_effect": {
                        "correct_utterance_rate": 0.2,
                        "selection_rate": 0.2,
                        "utterances": 288,
                    },
                    "supported_effect": {
                        "correct_utterance_rate": round(12 / 2300, 8),
                        "selection_rate": round(12 / 2300, 8),
                        "utterances": 2300,
                    },
                    "unsupported_ood": {
                        "correct_utterance_rate": 0.6,
                        "selection_rate": 0.6,
                        "utterances": 658,
                    },
                },
                "selection_rate": 0.15,
            },
            "utterances": 3246,
            "worst_locale": {
                "accuracy_when_selected": 0.95,
                "maximum_directional_errors": 0,
                "selection_rate": 0.03,
            },
        },
    }
    policy_payload = {
        key: artifact[key]
        for key in (
            "constraints",
            "catalog",
            "encoder",
            "training",
            "protocol",
            "heads",
            "conformal",
            "selective_guards",
        )
    }
    evidence_payload = {
        key: artifact[key]
        for key in ("sources", "groups", "exclusions", "metrics")
    }
    artifact["integrity"] = {
        "algorithm": "sha256_canonical_json_utf8_lf",
        "policy_payload_sha256": _sha(gate.canonical_json_bytes(policy_payload)),
        "evidence_payload_sha256": _sha(gate.canonical_json_bytes(evidence_payload)),
    }
    return artifact


@pytest.fixture
def synthetic_chain(tmp_path: Path) -> SimpleNamespace:
    root = tmp_path / "repo"
    development = root / "artifacts" / "development"
    product = root / "artifacts" / "product"
    data = root / "src" / "baxy_mind" / "data"
    catalog_path = root / "src" / "Baxy.Kernel" / "Operations" / "ProductCatalog.cs"
    trainer_path = root / "scripts" / "train.py"
    trainer_test_path = root / "tests" / "test_train.py"
    for directory in (
        development,
        product,
        data,
        catalog_path.parent,
        trainer_path.parent,
        trainer_test_path.parent,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    map_path = data / "map.json"
    map_path.write_text('{"schema":"synthetic-map"}\n', encoding="utf-8")
    catalog_path.write_text("namespace Synthetic;\n", encoding="utf-8")
    trainer_path.write_text("TRAINER_VERSION = 2\n", encoding="utf-8")
    trainer_test_path.write_text("def test_synthetic(): pass\n", encoding="utf-8")
    runtime_source = root / "src" / "baxy_mind" / "runtime.py"
    runtime_source.write_text("SAFE_RUNTIME = True\n", encoding="utf-8")

    runtime_train_sha = "1" * 64
    runtime_validation_sha = "2" * 64
    mtop_sha = "3" * 64
    map_sha = gate.file_sha256(map_path)
    catalog_sha = gate.file_sha256(catalog_path)

    runtime_manifest_path = development / "runtime_manifest.json"
    _write_json(
        runtime_manifest_path,
        {
            "schema": gate.RUNTIME_MANIFEST_SCHEMA,
            "outputs": {
                "train": {"sha256": runtime_train_sha},
                "validation": {"sha256": runtime_validation_sha},
            },
        },
    )
    mtop_manifest_path = product / "mtop_manifest.json"
    _write_json(
        mtop_manifest_path,
        {
            "schema": gate.MTOP_MANIFEST_SCHEMA,
            "catalog": {"sha256": catalog_sha},
            "output": {"sha256": mtop_sha},
            "source": {"map_sha256": map_sha},
        },
    )

    evaluation_path = development / "evaluation.json"
    evaluation = _synthetic_evaluation(
        runtime_train_sha=runtime_train_sha,
        runtime_validation_sha=runtime_validation_sha,
        mtop_sha=mtop_sha,
        catalog_sha=catalog_sha,
        map_sha=map_sha,
    )
    _write_json(evaluation_path, evaluation)

    prior_artifact_sha = "d" * 64
    rejection_path = development / "prior_rejection.json"
    _write_json(
        rejection_path,
        {
            "schema": gate.REJECTION_SCHEMA,
            "status": "rejected_not_runtime_authority",
            "artifact": {
                "repo_path": "artifacts/development/prior.json",
                "sha256": prior_artifact_sha,
            },
            "constraints": {
                "runtime_loaded": False,
                "execution_authority": False,
                "sealed_final_test_opened": False,
                "mtop_official_test_opened": False,
            },
        },
    )

    preregistration_path = development / "preregistration.json"
    _write_json(
        preregistration_path,
        {
            "schema": gate.PREREGISTRATION_SCHEMA,
            "state": "locked",
            "frozen_inputs": {
                "runtime_train": {"sha256": runtime_train_sha},
                "runtime_validation": {"sha256": runtime_validation_sha},
                "runtime_development_manifest": {
                    "repo_path": "artifacts/development/runtime_manifest.json",
                    "sha256": gate.file_sha256(runtime_manifest_path),
                },
                "mtop_development": {"sha256": mtop_sha},
                "mtop_development_manifest": {
                    "repo_path": "artifacts/product/mtop_manifest.json",
                    "sha256": gate.file_sha256(mtop_manifest_path),
                },
                "mtop_projection_map": {
                    "repo_path": "src/baxy_mind/data/map.json",
                    "sha256": map_sha,
                },
                "product_catalog": {
                    "repo_path": (
                        "src/Baxy.Kernel/Operations/ProductCatalog.cs"
                    ),
                    "sha256": catalog_sha,
                },
                "trainer": {
                    "repo_path": "scripts/train.py",
                    "sha256": gate.file_sha256(trainer_path),
                },
                "unit_tests": {
                    "repo_path": "tests/test_train.py",
                    "sha256": gate.file_sha256(trainer_test_path),
                },
            },
            "acceptance": {
                "exact_zero_counts": [
                    (
                        "metrics.selective_outcome.directional_safety."
                        "unsafe_conversation_as_supported"
                    )
                ],
                "minimums": {
                    (
                        "metrics.selective_outcome.per_class.supported_effect."
                        "selection_rate"
                    ): 0.02
                },
                "maximums": {
                    (
                        "thresholds.selective_guards.supported_effect."
                        "wilks_upper_rate"
                    ): 0.01,
                    (
                        "thresholds.selective_guards.conversation_fast_path."
                        "wilks_upper_rate"
                    ): 0.01,
                },
                "required_constraints": {
                    "constraints.execution_authority": False
                },
            },
            "iteration_control": {
                "prior_binary_artifact_sha256": prior_artifact_sha,
                "official_mtop_test_may_be_opened_by_this_run": False,
                "sealed_public_holdout_may_be_opened_by_this_run": False,
            },
            "output": {
                "repo_path": "artifacts/development/evaluation.json",
                "contains_text": False,
            },
        },
    )

    return SimpleNamespace(
        root=root,
        preregistration_path=preregistration_path,
        evaluation_path=evaluation_path,
        rejection_path=rejection_path,
        evaluation=evaluation,
        trainer_path=trainer_path,
        pins={
            "expected_preregistration_sha256": gate.file_sha256(
                preregistration_path
            ),
            "expected_evaluation_sha256": gate.file_sha256(evaluation_path),
            "expected_prior_rejection_sha256": gate.file_sha256(rejection_path),
        },
    )


def _verify_synthetic(chain: SimpleNamespace) -> dict[str, object]:
    return gate.build_gate_report(
        root=chain.root,
        preregistration_path=chain.preregistration_path,
        evaluation_path=chain.evaluation_path,
        prior_rejection_path=chain.rejection_path,
        **chain.pins,
    )


def test_synthetic_chain_reproduces_the_preregistered_rejection(
    synthetic_chain: SimpleNamespace,
    tmp_path: Path,
) -> None:
    report = _verify_synthetic(synthetic_chain)

    assert report["status"] == "failed_no_runtime_promotion"
    assert report["observed"]["supported_effect"] == {
        "selected": 12,
        "utterances": 2300,
        "selection_rate": round(12 / 2300, 8),
        "minimum_preregistered": 0.02,
        "passed": False,
    }
    assert report["preregistered_evaluation"]["missing_paths"] == [
        "thresholds.selective_guards.conversation_fast_path.wilks_upper_rate",
        "thresholds.selective_guards.supported_effect.wilks_upper_rate",
    ]
    assert not report["checks"]["preregistered_paths_resolve"]
    assert report["checks"]["runtime_policy_promotion_reference_absent"]
    assert report["privacy"]["recursive_allowlist"]

    output = tmp_path / "gate.json"
    gate.write_json_atomic(output, report)
    first = output.read_bytes()
    gate.write_json_atomic(output, report)
    assert output.read_bytes() == first


def test_recursive_privacy_allowlist_rejects_unknown_nested_text(
    synthetic_chain: SimpleNamespace,
) -> None:
    artifact = copy.deepcopy(synthetic_chain.evaluation)
    artifact["metrics"]["effect_gate"]["utterance_text"] = "private phrase"

    with pytest.raises(gate.VerificationError, match="utterance_text"):
        gate.validate_privacy_allowlist(artifact)


def test_recursive_privacy_allowlist_rejects_text_in_numeric_parameters(
    synthetic_chain: SimpleNamespace,
) -> None:
    artifact = copy.deepcopy(synthetic_chain.evaluation)
    artifact["heads"]["effect_gate"]["coefficients"][0][0] = "hidden_text"

    with pytest.raises(gate.VerificationError, match="privacy allowlist"):
        gate.validate_privacy_allowlist(artifact)


def test_changed_preregistered_code_hash_fails_closed(
    synthetic_chain: SimpleNamespace,
) -> None:
    synthetic_chain.trainer_path.write_text(
        "TRAINER_VERSION = 3\n",
        encoding="utf-8",
    )

    with pytest.raises(gate.VerificationError, match="file hash changed"):
        _verify_synthetic(synthetic_chain)


def test_runtime_reference_to_development_candidate_fails_closed(
    synthetic_chain: SimpleNamespace,
) -> None:
    reference = synthetic_chain.root / "src" / "baxy_mind" / "candidate_loader.py"
    reference.write_text(
        f'CANDIDATE = "{synthetic_chain.evaluation_path.name}"\n',
        encoding="utf-8",
    )

    with pytest.raises(gate.VerificationError, match="referenced by runtime"):
        _verify_synthetic(synthetic_chain)


def test_current_aggregate_chain_verifies_without_opening_any_corpus() -> None:
    report = gate.build_gate_report(
        root=ROOT,
        preregistration_path=gate.DEFAULT_PREREGISTRATION,
        evaluation_path=gate.DEFAULT_EVALUATION,
        prior_rejection_path=gate.DEFAULT_PRIOR_REJECTION,
        expected_preregistration_sha256=gate.DEFAULT_PREREGISTRATION_SHA256,
        expected_evaluation_sha256=gate.DEFAULT_EVALUATION_SHA256,
        expected_prior_rejection_sha256=gate.DEFAULT_PRIOR_REJECTION_SHA256,
    )

    assert report["status"] == "failed_no_runtime_promotion"
    assert report["observed"]["supported_effect"]["selected"] == 12
    assert report["observed"]["supported_effect"]["utterances"] == 2300
    assert report["verifier"]["trainer_executed"] is False
    assert report["verifier"]["corpus_or_holdout_opened"] is False
    assert report["promotion_boundary"]["official_mtop_test_opened"] is False
