"""Prepare the unopened current-tree compound execution campaign R6.

R4 and R5 are consumed. R6 is a fresh, objective-disjoint seal over the same
population shape: ES/EN/spanglish dependent clauses, reversible named effects,
production planner → grounded args → production core.
"""

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

from experiments.mind_router_spike import (  # noqa: E402
    build_compound_execution_current_tree_r4 as r4,
)
from experiments.mind_router_spike import (  # noqa: E402
    build_compound_execution_current_tree_r5 as r5,
)
from scripts import build_compound_execution_holdout_r1 as common  # noqa: E402
from scripts import build_compound_execution_holdout_r2 as r2  # noqa: E402
from scripts import build_compound_execution_holdout_r3 as r3  # noqa: E402
from scripts.measure_mind_budget import write_json_atomic  # noqa: E402


OUTPUT = REPO / "artifacts/holdout/compound_execution_current_tree_r6.json"
PREREGISTRATION = REPO / (
    "artifacts/holdout/compound_execution_current_tree_r6.preregistration.json"
)
RUNNER = REPO / (
    "experiments/mind_router_spike/run_compound_execution_current_tree_r6.py"
)
EXECUTION_GATE = REPO / "scripts/run_llm_plan_execution_gate.py"
BUILDER_DEPENDENCIES = (
    REPO / "scripts/build_compound_execution_holdout_r1.py",
    REPO / "scripts/build_compound_execution_holdout_r2.py",
    REPO / "scripts/build_compound_execution_holdout_r3.py",
    REPO / "experiments/mind_router_spike/build_compound_execution_current_tree_r4.py",
    REPO / "experiments/mind_router_spike/build_compound_execution_current_tree_r5.py",
)
POLICY_SOURCES = common.POLICY_SOURCES
MEASUREMENT_SOURCES = (RUNNER, EXECUTION_GATE)
ALLOWED_OPERATIONS = r3.ALLOWED_OPERATIONS


def build_cases(run_id: str, _document_prefix: str) -> list[dict[str, Any]]:
    return [
        {
            "name": "r6_readonly_sequencing_tail_es",
            "planner_path": "real_llm_current_tree_readonly_plan",
            "objective": (
                "Lista los periféricos conectados, reporta el estado del "
                "audio y termina con el estado del sistema."
            ),
            "expected": [
                "peripheral.list",
                "audio.status",
                "system.status",
            ],
            "dependency_positions": [[], [], []],
            "confirm": set(),
        },
        {
            "name": "r6_two_notes_elided_then_ordinal_es",
            "planner_path": "real_llm_current_tree_mixed_dependency_plan",
            "objective": (
                f"Crea una nota Bruma {run_id} con contenido niebla {run_id} y "
                f"otra nota Cima {run_id} con contenido nieve {run_id}; "
                "después lee la segunda, luego lee la primera."
            ),
            "expected": [
                "note.create",
                "note.create",
                "note.read",
                "note.read",
            ],
            "dependency_positions": [[], [], [1], [0]],
            "confirm": {"note.create"},
        },
        {
            "name": "r6_two_notes_participle_en",
            "planner_path": "real_llm_current_tree_mixed_dependency_plan",
            "ui_language": "en",
            "objective": (
                f"Create two local notes: Onyx {run_id} containing dusk "
                f"{run_id} and Pearl {run_id} containing dawn {run_id}. Then "
                "read the second note and the first note."
            ),
            "expected": [
                "note.create",
                "note.create",
                "note.read",
                "note.read",
            ],
            "dependency_positions": [[], [], [1], [0]],
            "confirm": {"note.create"},
        },
        {
            "name": "r6_note_then_coordinated_status_spanglish",
            "planner_path": "real_llm_current_tree_mixed_dependency_plan",
            "objective": (
                f"Create una nota Muelle {run_id} con content amarre {run_id}, "
                "read esa misma nota, then check system status y network status."
            ),
            "expected": [
                "note.create",
                "note.read",
                "system.status",
                "network.status",
            ],
            "dependency_positions": [[], [0], [], []],
            "confirm": {"note.create"},
        },
        {
            "name": "r6_readonly_finish_by_en",
            "planner_path": "real_llm_current_tree_readonly_plan",
            "ui_language": "en",
            "objective": (
                "List connected peripherals, report audio status, and finish "
                "by reporting system status."
            ),
            "expected": [
                "peripheral.list",
                "audio.status",
                "system.status",
            ],
            "dependency_positions": [[], [], []],
            "confirm": set(),
        },
        {
            "name": "r6_interleaved_pairs_spanglish",
            "planner_path": "real_llm_current_tree_mixed_dependency_plan",
            "objective": (
                f"Crea una nota Duna {run_id} con content arena {run_id} y "
                f"léela; then create una nota Marea {run_id} con content sal "
                f"{run_id} and read esa última nota."
            ),
            "expected": [
                "note.create",
                "note.read",
                "note.create",
                "note.read",
            ],
            "dependency_positions": [[], [0], [], [2]],
            "confirm": {"note.create"},
        },
    ]


def case_contract_sha256() -> str:
    return hashlib.sha256(
        common._canonical(build_cases("RUNID", "DOCUMENT"))
    ).hexdigest()


def validate_cases(cases: list[dict[str, Any]]) -> None:
    if len(cases) != 6 or len({str(case["name"]) for case in cases}) != 6:
        raise RuntimeError("current-tree compound R6 requires six unique cases")
    if sum(len(case["expected"]) for case in cases) != 22:
        raise RuntimeError("current-tree compound R6 step count changed")
    for case in cases:
        if (
            set(case.get("expected", ())) - ALLOWED_OPERATIONS
            or len(case.get("dependency_positions", ()))
            != len(case.get("expected", ()))
            or set(case.get("confirm", ())) - {"note.create"}
        ):
            raise RuntimeError(
                f"current-tree compound R6 case is unsafe: {case.get('name')}"
            )


def _prior_objectives() -> set[str]:
    return {
        " ".join(str(case["objective"]).casefold().split())
        for campaign in (common, r2, r3, r4, r5)
        for case in campaign.build_cases("RUNID", "DOCUMENT")
    }


def build() -> dict[str, Any]:
    if PREREGISTRATION.exists() or OUTPUT.exists():
        raise RuntimeError("refusing to overwrite current-tree compound R6 state")
    cases = build_cases("RUNID", "DOCUMENT")
    validate_cases(cases)
    current_objectives = {
        " ".join(str(case["objective"]).casefold().split()) for case in cases
    }
    if current_objectives & _prior_objectives():
        raise RuntimeError("current-tree compound R6 overlaps a prior objective")
    runtime_manifest = (
        Path(os.environ["LOCALAPPDATA"]) / "BAXYRuntime/mind-runtime-v1.json"
    ).resolve(strict=True)
    core = common.load_build_layout(REPO).core_executable(REPO).resolve(strict=True)
    manifest = {
        "schema": "baxy.compound-execution-current-tree-r6.preregistration.v1",
        "blind_holdout": True,
        "preregistered_before_measurement": True,
        "measurement_status": "unopened",
        "supersedes": {
            "campaign": "current-tree compound R5",
            "result": "opened once and passed 6/6 cases and 25/25 steps",
            "reuse_for_promotion_forbidden": True,
        },
        "authority": (
            "temporary_private_note_namespace_and_read_only_machine_status_only"
        ),
        "method": {
            "minimum_exact_case_accuracy": 0.9,
            "maximum_ambiguous_effects": 0,
            "maximum_orphan_steps": 0,
            "required_real_llm_cases": 6,
        },
        "population": {
            "cases": 6,
            "steps": 22,
            "languages": ["en", "es", "spanglish"],
            "dependent_clause_shapes": [
                "sequencing_head",
                "elided_verb",
                "bare_ordinal",
                "participle_note_body",
                "coordinated_status_nominals",
                "enclitic_read",
            ],
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
