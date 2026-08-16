"""Prepare the unopened current-tree Cut-C compound execution campaign."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts import build_compound_execution_holdout_r1 as common  # noqa: E402
from scripts import build_compound_execution_holdout_r2 as r2  # noqa: E402
from scripts import build_compound_execution_holdout_r3 as r3  # noqa: E402
from scripts.measure_mind_budget import write_json_atomic  # noqa: E402


OUTPUT = REPO / "artifacts/holdout/compound_execution_current_tree_r4.json"
PREREGISTRATION = REPO / (
    "artifacts/holdout/compound_execution_current_tree_r4.preregistration.json"
)
RUNNER = REPO / (
    "experiments/mind_router_spike/run_compound_execution_current_tree_r4.py"
)
EXECUTION_GATE = REPO / "scripts/run_llm_plan_execution_gate.py"
BUILDER_DEPENDENCIES = (
    REPO / "scripts/build_compound_execution_holdout_r1.py",
    REPO / "scripts/build_compound_execution_holdout_r2.py",
    REPO / "scripts/build_compound_execution_holdout_r3.py",
)
POLICY_SOURCES = common.POLICY_SOURCES
MEASUREMENT_SOURCES = (RUNNER, EXECUTION_GATE)
ALLOWED_OPERATIONS = r3.ALLOWED_OPERATIONS


def build_cases(run_id: str, _document_prefix: str) -> list[dict[str, Any]]:
    return [
        {
            "name": "r4_three_notes_interleaved_es",
            "planner_path": "real_llm_current_tree_six_step_dependency_dag",
            "objective": (
                f"Crea una nota Faro {run_id} con contenido luz {run_id} y lee esa "
                f"misma nota; luego crea una nota Lago {run_id} con contenido agua "
                f"{run_id} y léela; finalmente crea una nota Monte {run_id} con "
                f"contenido piedra {run_id} y lee esa última nota."
            ),
            "expected": [
                "note.create",
                "note.read",
                "note.create",
                "note.read",
                "note.create",
                "note.read",
            ],
            "dependency_positions": [[], [0], [], [2], [], [4]],
            "confirm": {"note.create"},
        },
        {
            "name": "r4_four_notes_permuted_en",
            "planner_path": "real_llm_current_tree_eight_step_dependency_dag",
            "ui_language": "en",
            "objective": (
                f"Create four local notes: Cedar {run_id} containing north {run_id}, "
                f"Willow {run_id} containing south {run_id}, Maple {run_id} containing "
                f"east {run_id}, and Birch {run_id} containing west {run_id}. Then "
                "read the second note, the fourth note, the first note, and the third "
                "note, in that exact order."
            ),
            "expected": [
                "note.create",
                "note.create",
                "note.create",
                "note.create",
                "note.read",
                "note.read",
                "note.read",
                "note.read",
            ],
            "dependency_positions": [[], [], [], [], [1], [3], [0], [2]],
            "confirm": {"note.create"},
        },
        {
            "name": "r4_two_notes_reverse_then_system_spanglish",
            "planner_path": "real_llm_current_tree_mixed_dependency_plan",
            "objective": (
                f"Create una nota Luna {run_id} con content claro {run_id} y otra "
                f"nota Sol {run_id} con content brillante {run_id}; después read la "
                "segunda, luego read la primera y finally check system status."
            ),
            "expected": [
                "note.create",
                "note.create",
                "note.read",
                "note.read",
                "system.status",
            ],
            "dependency_positions": [[], [], [1], [0], []],
            "confirm": {"note.create"},
        },
        {
            "name": "r4_readonly_cross_family_en",
            "planner_path": "real_llm_current_tree_readonly_plan",
            "ui_language": "en",
            "objective": (
                "Check system status, list connected peripherals, report audio status, "
                "and finish by reporting network status."
            ),
            "expected": [
                "system.status",
                "peripheral.list",
                "audio.status",
                "network.status",
            ],
            "dependency_positions": [[], [], [], []],
            "confirm": set(),
        },
        {
            "name": "r4_readonly_hardware_es",
            "planner_path": "real_llm_current_tree_readonly_plan",
            "objective": (
                "Revisa el teclado, enumera los dispositivos Bluetooth visibles, "
                "lista los periféricos conectados y termina con el estado de la red."
            ),
            "expected": [
                "input.keyboard.status",
                "bluetooth.device.list",
                "peripheral.list",
                "network.status",
            ],
            "dependency_positions": [[], [], [], []],
            "confirm": set(),
        },
        {
            "name": "r4_note_then_dual_status_spanglish",
            "planner_path": "real_llm_current_tree_mixed_dependency_plan",
            "objective": (
                f"Create una nota Puente {run_id} con content listo {run_id}, read esa "
                "misma nota, then check audio status y network status."
            ),
            "expected": [
                "note.create",
                "note.read",
                "audio.status",
                "network.status",
            ],
            "dependency_positions": [[], [0], [], []],
            "confirm": {"note.create"},
        },
    ]


def case_contract_sha256() -> str:
    return hashlib.sha256(
        common._canonical(build_cases("RUNID", "DOCUMENT"))
    ).hexdigest()


def validate_cases(cases: list[dict[str, Any]]) -> None:
    if len(cases) != 6 or len({str(case["name"]) for case in cases}) != 6:
        raise RuntimeError("current-tree compound R4 requires six unique cases")
    if sum(len(case["expected"]) for case in cases) != 31:
        raise RuntimeError("current-tree compound R4 step count changed")
    if {case.get("ui_language", "es") for case in cases} != {"en", "es"}:
        raise RuntimeError("current-tree compound R4 language routing changed")
    for case in cases:
        if (
            set(case.get("expected", ())) - ALLOWED_OPERATIONS
            or len(case.get("dependency_positions", ()))
            != len(case.get("expected", ()))
            or set(case.get("confirm", ())) - {"note.create"}
        ):
            raise RuntimeError(
                f"current-tree compound R4 case is unsafe: {case.get('name')}"
            )


def _prior_objectives() -> set[str]:
    return {
        " ".join(str(case["objective"]).casefold().split())
        for campaign in (common, r2, r3)
        for case in campaign.build_cases("RUNID", "DOCUMENT")
    }


def build() -> dict[str, Any]:
    if PREREGISTRATION.exists() or OUTPUT.exists():
        raise RuntimeError("refusing to overwrite current-tree compound R4 state")
    cases = build_cases("RUNID", "DOCUMENT")
    validate_cases(cases)
    current_objectives = {
        " ".join(str(case["objective"]).casefold().split()) for case in cases
    }
    if current_objectives & _prior_objectives():
        raise RuntimeError("current-tree compound R4 overlaps a prior objective")
    runtime_manifest = (
        Path(os.environ["LOCALAPPDATA"]) / "BAXYRuntime/mind-runtime-v1.json"
    ).resolve(strict=True)
    core = common.load_build_layout(REPO).core_executable(REPO).resolve(strict=True)
    manifest = {
        "schema": "baxy.compound-execution-current-tree-r4.preregistration.v1",
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
            "cases": 6,
            "steps": 31,
            "languages": ["en", "es", "spanglish"],
            "case_contract_sha256": case_contract_sha256(),
            "exact_prior_objective_overlap": 0,
        },
        "sources": {
            "builder": str(Path(__file__).resolve().relative_to(REPO)),
            "builder_sha256": common._sha256(Path(__file__).resolve()),
            "builder_dependencies_sha256": {
                str(path.relative_to(REPO)): common._sha256(path)
                for path in BUILDER_DEPENDENCIES
            },
            "measurement_sha256": {
                str(path.relative_to(REPO)): common._sha256(path)
                for path in MEASUREMENT_SOURCES
            },
            "policy_sha256": {
                str(path.relative_to(REPO)): common._sha256(path)
                for path in POLICY_SOURCES
            },
            "runtime_manifest_sha256": common._sha256(runtime_manifest),
            "core_sha256": common._sha256(core),
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
