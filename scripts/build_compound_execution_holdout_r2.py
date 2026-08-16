"""Preregister the post-R1 blind compound execution campaign."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts import build_compound_execution_holdout_r1 as base  # noqa: E402
from scripts.measure_mind_budget import write_json_atomic  # noqa: E402


OUTPUT = REPO / "artifacts/holdout/compound_execution_holdout_r2.json"
PREREGISTRATION = (
    REPO / "artifacts/holdout/compound_execution_holdout_r2.preregistration.json"
)
RUNNER = REPO / "experiments/mind_router_spike/run_compound_execution_holdout_r2.py"
EXECUTION_GATE = REPO / "scripts/run_llm_plan_execution_gate.py"
BUILDER_DEPENDENCIES = (
    REPO / "scripts/build_compound_execution_holdout_r1.py",
)
POLICY_SOURCES = base.POLICY_SOURCES
MEASUREMENT_SOURCES = (RUNNER, EXECUTION_GATE)
ALLOWED_OPERATIONS = frozenset(
    {
        "audio.status",
        "bluetooth.device.list",
        "input.keyboard.status",
        "network.status",
        "note.create",
        "note.read",
        "peripheral.list",
        "system.status",
    }
)


def build_cases(run_id: str, _document_prefix: str) -> list[dict[str, Any]]:
    return [
        {
            "name": "r2_note_dual_interleaved_en",
            "planner_path": "real_llm_blind_interleaved_dependency_dag",
            "ui_language": "en",
            "objective": (
                f"Create a note titled Harbor {run_id} with content east {run_id} "
                "and read that note before continuing; then create a note titled "
                f"Beacon {run_id} with content west {run_id} and read the second note."
            ),
            "expected": ["note.create", "note.read", "note.create", "note.read"],
            "dependency_positions": [[], [0], [], [2]],
            "confirm": {"note.create"},
        },
        {
            "name": "r2_note_three_permuted_es",
            "planner_path": "real_llm_blind_six_step_dependency_dag",
            "objective": (
                f"Crea tres notas: la primera titulada Cobre {run_id} con contenido "
                f"rojo {run_id}, la segunda titulada Plata {run_id} con contenido "
                f"gris {run_id} y la tercera titulada Oro {run_id} con contenido "
                f"amarillo {run_id}. Después lee la tercera nota, la primera nota "
                "y la segunda nota."
            ),
            "expected": [
                "note.create", "note.create", "note.create",
                "note.read", "note.read", "note.read",
            ],
            "dependency_positions": [[], [], [], [2], [0], [1]],
            "confirm": {"note.create"},
        },
        {
            "name": "r2_note_four_named_spanglish",
            "planner_path": "real_llm_blind_eight_step_named_dependency_dag",
            "objective": (
                f"Create cuatro notas: Río {run_id} con contenido alpha {run_id}, "
                f"Bosque {run_id} con contenido beta {run_id}, Cielo {run_id} con "
                f"contenido gamma {run_id} y Tierra {run_id} con contenido delta "
                f"{run_id}. Después read, en orden, la nota Tierra, la nota Río, "
                "la nota Cielo y la nota Bosque."
            ),
            "expected": [
                "note.create", "note.create", "note.create", "note.create",
                "note.read", "note.read", "note.read", "note.read",
            ],
            "dependency_positions": [[], [], [], [], [3], [0], [2], [1]],
            "confirm": {"note.create"},
        },
        {
            "name": "r2_readonly_status_triad_en",
            "planner_path": "real_llm_blind_cross_family_readonly_plan",
            "ui_language": "en",
            "objective": (
                "Check in one ordered mission: first system status, then network "
                "status, and finally audio status."
            ),
            "expected": ["system.status", "network.status", "audio.status"],
            "dependency_positions": [[], [], []],
            "confirm": set(),
        },
        {
            "name": "r2_readonly_hardware_triad_en",
            "planner_path": "real_llm_blind_cross_family_readonly_plan",
            "ui_language": "en",
            "objective": (
                "Check these hardware views in order: first keyboard status, then "
                "attached peripherals, and finally Bluetooth devices visible."
            ),
            "expected": [
                "input.keyboard.status",
                "peripheral.list",
                "bluetooth.device.list",
            ],
            "dependency_positions": [[], [], []],
            "confirm": set(),
        },
        {
            "name": "r2_note_read_then_network_spanglish",
            "planner_path": "real_llm_blind_mixed_dependency_plan",
            "objective": (
                f"Crea una nota titulada Enlace {run_id} con contenido mixed "
                f"{run_id}, read esa misma nota y después revisa el estado de la red."
            ),
            "expected": ["note.create", "note.read", "network.status"],
            "dependency_positions": [[], [0], []],
            "confirm": {"note.create"},
        },
    ]


def case_contract_sha256() -> str:
    import hashlib

    return hashlib.sha256(base._canonical(build_cases("RUNID", "DOCUMENT"))).hexdigest()


def validate_cases(cases: list[dict[str, Any]]) -> None:
    if len(cases) != 6 or len({str(case["name"]) for case in cases}) != len(cases):
        raise RuntimeError("compound R2 requires six unique cases")
    if sum(len(case["expected"]) for case in cases) != 27:
        raise RuntimeError("compound R2 step count changed")
    for case in cases:
        expected = case.get("expected")
        dependencies = case.get("dependency_positions")
        confirmations = case.get("confirm")
        if (
            not isinstance(expected, list)
            or not expected
            or set(expected) - ALLOWED_OPERATIONS
            or not isinstance(dependencies, list)
            or len(dependencies) != len(expected)
            or not isinstance(confirmations, set)
            or confirmations - {"note.create"}
        ):
            raise RuntimeError(f"compound R2 case is unsafe: {case.get('name')}")


def build() -> dict[str, Any]:
    if PREREGISTRATION.exists() or OUTPUT.exists():
        raise RuntimeError("refusing to overwrite compound execution R2 state")
    cases = build_cases("RUNID", "DOCUMENT")
    validate_cases(cases)
    runtime_manifest = (
        Path(os.environ["LOCALAPPDATA"]) / "BAXYRuntime/mind-runtime-v1.json"
    ).resolve(strict=True)
    core = base.load_build_layout(REPO).core_executable(REPO).resolve(strict=True)
    manifest = {
        "schema": "baxy.compound-execution-holdout-r2.preregistration.v1",
        "blind_holdout": True,
        "preregistered_before_measurement": True,
        "measurement_status": "unopened",
        "authority": (
            "temporary_private_note_namespace_and_read_only_machine_status_only"
        ),
        "method": {
            "minimum_exact_case_accuracy": 1.0,
            "maximum_ambiguous_effects": 0,
            "maximum_failed_cases": 0,
            "required_real_llm_cases": 6,
        },
        "population": {
            "cases": len(cases),
            "steps": sum(len(case["expected"]) for case in cases),
            "languages": ["en", "es", "spanglish"],
            "case_contract_sha256": case_contract_sha256(),
            "exact_r1_objective_overlap": 0,
        },
        "sources": {
            "builder": str(Path(__file__).resolve().relative_to(REPO)),
            "builder_sha256": base._sha256(Path(__file__).resolve()),
            "builder_dependencies_sha256": {
                str(path.relative_to(REPO)): base._sha256(path)
                for path in BUILDER_DEPENDENCIES
            },
            "measurement_sha256": {
                str(path.relative_to(REPO)): base._sha256(path)
                for path in MEASUREMENT_SOURCES
            },
            "policy_sha256": {
                str(path.relative_to(REPO)): base._sha256(path)
                for path in POLICY_SOURCES
            },
            "runtime_manifest_sha256": base._sha256(runtime_manifest),
            "core_sha256": base._sha256(core),
        },
        "planned_output": str(OUTPUT.relative_to(REPO)),
        "effects": {
            "applications_opened": 0,
            "external_messages": 0,
            "persistent_user_files": 0,
            "temporary_notes_cleaned_by_gate": True,
        },
    }
    write_json_atomic(PREREGISTRATION, manifest)
    return manifest


def main() -> int:
    manifest = build()
    print(json.dumps(manifest["population"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
