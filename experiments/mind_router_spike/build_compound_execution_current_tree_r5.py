"""Prepare the unopened current-tree Cut-C compound execution campaign R5.

R4 was opened once and closed 2/6 because dependent clauses lost the head their
governing clause supplied. That corpus is consumed and may never promote its own
repair, so R5 is a fresh, objective-disjoint seal over the same population.

Two design rules were applied case by case, both learned from R4:

* Every expectation must be defensible from the catalogue surface alone. R4
  expected ``revisa el teclado`` to mean ``input.keyboard.status`` while that
  operation reports the focused window's keyboard layout; an underspecified
  surface is a clarification, not a mission step. R5 states each read target
  explicitly.
* Every dependent clause shape that R4 exposed is exercised again here --
  sequencing heads, elided verbs, bare ordinals, participle note bodies and
  coordinated status nominals -- so the repair is measured, not assumed.
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
from scripts import build_compound_execution_holdout_r1 as common  # noqa: E402
from scripts import build_compound_execution_holdout_r2 as r2  # noqa: E402
from scripts import build_compound_execution_holdout_r3 as r3  # noqa: E402
from scripts.measure_mind_budget import write_json_atomic  # noqa: E402


OUTPUT = REPO / "artifacts/holdout/compound_execution_current_tree_r5.json"
PREREGISTRATION = REPO / (
    "artifacts/holdout/compound_execution_current_tree_r5.preregistration.json"
)
RUNNER = REPO / (
    "experiments/mind_router_spike/run_compound_execution_current_tree_r5.py"
)
EXECUTION_GATE = REPO / "scripts/run_llm_plan_execution_gate.py"
BUILDER_DEPENDENCIES = (
    REPO / "scripts/build_compound_execution_holdout_r1.py",
    REPO / "scripts/build_compound_execution_holdout_r2.py",
    REPO / "scripts/build_compound_execution_holdout_r3.py",
    REPO / "experiments/mind_router_spike/build_compound_execution_current_tree_r4.py",
)
POLICY_SOURCES = common.POLICY_SOURCES
MEASUREMENT_SOURCES = (RUNNER, EXECUTION_GATE)
ALLOWED_OPERATIONS = r3.ALLOWED_OPERATIONS


def build_cases(run_id: str, _document_prefix: str) -> list[dict[str, Any]]:
    return [
        {
            # Sequencing head: the last clause is introduced by "termina con".
            "name": "r5_readonly_sequencing_tail_es",
            "planner_path": "real_llm_current_tree_readonly_plan",
            "objective": (
                "Reporta el estado del sistema, enumera los dispositivos "
                "Bluetooth visibles, lista los periféricos conectados y "
                "termina con el estado de la red."
            ),
            "expected": [
                "system.status",
                "bluetooth.device.list",
                "peripheral.list",
                "network.status",
            ],
            "dependency_positions": [[], [], [], []],
            "confirm": set(),
        },
        {
            # Elided verb plus bare ordinal anaphora, in Spanish.
            "name": "r5_two_notes_elided_then_ordinal_es",
            "planner_path": "real_llm_current_tree_mixed_dependency_plan",
            "objective": (
                f"Crea una nota Rio {run_id} con contenido cauce {run_id} y "
                f"otra nota Valle {run_id} con contenido hondo {run_id}; "
                "después lee la primera, luego lee la segunda."
            ),
            "expected": [
                "note.create",
                "note.create",
                "note.read",
                "note.read",
            ],
            "dependency_positions": [[], [], [0], [1]],
            "confirm": {"note.create"},
        },
        {
            # Participle note bodies with a serial comma before the last title.
            "name": "r5_three_notes_participle_permuted_en",
            "planner_path": "real_llm_current_tree_six_step_dependency_dag",
            "objective": (
                f"Create three local notes: Amber {run_id} containing dawn "
                f"{run_id}, Cobalt {run_id} containing dusk {run_id}, and "
                f"Jade {run_id} containing noon {run_id}. Then read the third "
                "note, the first note, and the second note."
            ),
            "expected": [
                "note.create",
                "note.create",
                "note.create",
                "note.read",
                "note.read",
                "note.read",
            ],
            "dependency_positions": [[], [], [], [2], [0], [1]],
            "confirm": {"note.create"},
        },
        {
            # Coordinated status nominals joined by a spanglish conjunction.
            "name": "r5_note_then_coordinated_status_spanglish",
            "planner_path": "real_llm_current_tree_mixed_dependency_plan",
            "objective": (
                f"Create una nota Faro {run_id} con content guia {run_id}, "
                "read esa misma nota, then check audio status y system status."
            ),
            "expected": [
                "note.create",
                "note.read",
                "audio.status",
                "system.status",
            ],
            "dependency_positions": [[], [0], [], []],
            "confirm": {"note.create"},
        },
        {
            # English sequencing head, read-only, no note involved.
            "name": "r5_readonly_finish_by_en",
            "planner_path": "real_llm_current_tree_readonly_plan",
            "objective": (
                "Check system status, report audio status, and finish by "
                "reporting network status."
            ),
            "expected": [
                "system.status",
                "audio.status",
                "network.status",
            ],
            "dependency_positions": [[], [], []],
            "confirm": set(),
        },
        {
            # Interleaved create/read chain with an enclitic Spanish read.
            "name": "r5_interleaved_pairs_es",
            "planner_path": "real_llm_current_tree_six_step_dependency_dag",
            "objective": (
                f"Crea una nota Nieve {run_id} con contenido frio {run_id} y "
                f"léela; luego crea una nota Brasa {run_id} con contenido "
                f"calor {run_id} y lee esa última nota."
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
        raise RuntimeError("current-tree compound R5 requires six unique cases")
    if sum(len(case["expected"]) for case in cases) != 25:
        raise RuntimeError("current-tree compound R5 step count changed")
    for case in cases:
        if (
            set(case.get("expected", ())) - ALLOWED_OPERATIONS
            or len(case.get("dependency_positions", ()))
            != len(case.get("expected", ()))
            or set(case.get("confirm", ())) - {"note.create"}
        ):
            raise RuntimeError(
                f"current-tree compound R5 case is unsafe: {case.get('name')}"
            )


def _prior_objectives() -> set[str]:
    return {
        " ".join(str(case["objective"]).casefold().split())
        for campaign in (common, r2, r3, r4)
        for case in campaign.build_cases("RUNID", "DOCUMENT")
    }


def build() -> dict[str, Any]:
    if PREREGISTRATION.exists() or OUTPUT.exists():
        raise RuntimeError("refusing to overwrite current-tree compound R5 state")
    cases = build_cases("RUNID", "DOCUMENT")
    validate_cases(cases)
    current_objectives = {
        " ".join(str(case["objective"]).casefold().split()) for case in cases
    }
    if current_objectives & _prior_objectives():
        raise RuntimeError("current-tree compound R5 overlaps a prior objective")
    runtime_manifest = (
        Path(os.environ["LOCALAPPDATA"]) / "BAXYRuntime/mind-runtime-v1.json"
    ).resolve(strict=True)
    core = common.load_build_layout(REPO).core_executable(REPO).resolve(strict=True)
    manifest = {
        "schema": "baxy.compound-execution-current-tree-r5.preregistration.v1",
        "blind_holdout": True,
        "preregistered_before_measurement": True,
        "measurement_status": "unopened",
        "supersedes": {
            "campaign": "current-tree compound R4",
            "result": "opened once and failed 2/6 cases and 10/31 steps",
            "reuse_for_promotion_forbidden": True,
        },
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
            "steps": 25,
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
