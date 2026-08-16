from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROGRAM = ROOT / "scripts" / "assemble_mvp_catalog_routing_matrix.py"
SPEC = importlib.util.spec_from_file_location("assemble_mvp_catalog_matrix", PROGRAM)
assert SPEC is not None and SPEC.loader is not None
assembler = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(assembler)


def test_memory_trx_has_exactly_eleven_passing_app_routes() -> None:
    results = assembler.load_memory_results(assembler.MEMORY_TRX)

    assert len(results) == 11
    assert {row["outcome"] for row in results.values()} == {"Passed"}


def test_joined_matrix_is_complete_but_does_not_overclaim_execution() -> None:
    report = assembler.build_report(assembler.MIND_REPORT, assembler.MEMORY_TRX)

    assert report["metrics"]["operations"] == 169
    assert report["metrics"]["routing_passed"] == 169
    assert report["metrics"]["routing_failed"] == 0
    assert report["metrics"]["unsafe_effects"] == 0
    assert report["metrics"]["by_language"] == {
        "en": 42,
        "es": 85,
        "spanglish": 42,
    }
    assert report["routing_gate_passed"] is True
    assert report["provider_execution_gate_passed"] is False
    assert report["overall_mvp_gate_passed"] is False
    assert all(
        row["provider_execution"] == "pending_separate_safe_execution_gate"
        for row in report["rows"]
    )
