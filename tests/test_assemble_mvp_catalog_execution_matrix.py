from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "assemble_mvp_catalog_execution_matrix.py"
SPEC = importlib.util.spec_from_file_location("assemble_mvp_catalog_execution_matrix", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def assemble() -> dict:
    return MODULE.assemble(
        routing_path=ROOT / "artifacts" / "mvp" / "catalog_routing_matrix_v1.json",
        core_path=ROOT / "artifacts" / "mvp" / "catalog_core_read_only_gate_v1.json",
        external_path=(
            ROOT / "artifacts" / "mvp" / "external_provider_contract_matrix_v1.json"
        ),
        stateful_path=(
            ROOT / "artifacts" / "mvp" / "local_stateful_handler_matrix_v1.json"
        ),
        transient_path=(
            ROOT / "artifacts" / "mvp" / "local_transient_handler_matrix_v2.json"
        ),
        memory_path=ROOT / "artifacts" / "mvp" / "memory_handler_matrix_v1.json",
        expected_operations=169,
    )


def test_current_tree_has_provider_verifier_evidence_for_all_catalog_operations() -> None:
    report = assemble()

    assert report["gatePassed"] is True
    assert report["metrics"]["catalogOperations"] == 169
    assert report["metrics"]["routingPassed"] == 169
    assert report["metrics"]["contractBoundariesPassed"] == 169
    assert report["metrics"]["providerExecutionEvidencePassed"] == 169
    assert report["metrics"]["independentlyVerified"] == 169
    assert report["metrics"]["gaps"] == 0
    assert len({row["operation"] for row in report["rows"]}) == 169


def test_safe_simulation_is_explicit_and_never_claimed_as_physical_execution() -> None:
    report = assemble()
    simulated = [
        row
        for row in report["rows"]
        if "simulation" in row["executionEvidenceKind"]
    ]

    assert simulated
    assert all(row["status"] == "approved_safe_contract_simulation" for row in simulated)
    assert all(row["physicalExternalEffectExecuted"] is False for row in simulated)
    assert report["metrics"]["physicalExternalEffectsExecuted"] == 0
    assert report["metrics"]["actualUserEffectsExecuted"] == 0


def test_memory_uses_real_dpapi_backed_isolated_store() -> None:
    report = assemble()
    memory = [row for row in report["rows"] if row["family"] == "memory"]

    assert len(memory) == 11
    assert all(
        row["executionEvidenceKind"] == "real_isolated_encrypted_store"
        for row in memory
    )
    assert all("WindowsProtectedPayload" in row["provider"] for row in memory)


def test_unique_rows_rejects_duplicate_operations() -> None:
    with pytest.raises(ValueError, match="Duplicate operation system.time"):
        MODULE.unique_rows(
            [{"operation": "system.time"}, {"operation": "system.time"}],
            "operation",
            "fixture",
        )
