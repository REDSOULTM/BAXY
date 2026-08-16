"""Preregister the post-R2 blind compound execution campaign."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts import build_compound_execution_holdout_r1 as common  # noqa: E402
from scripts import build_compound_execution_holdout_r2 as prior  # noqa: E402
from scripts.measure_mind_budget import write_json_atomic  # noqa: E402


OUTPUT = REPO / "artifacts/holdout/compound_execution_holdout_r3.json"
PREREGISTRATION = (
    REPO / "artifacts/holdout/compound_execution_holdout_r3.preregistration.json"
)
RUNNER = REPO / "experiments/mind_router_spike/run_compound_execution_holdout_r3.py"
EXECUTION_GATE = REPO / "scripts/run_llm_plan_execution_gate.py"
BUILDER_DEPENDENCIES = (
    REPO / "scripts/build_compound_execution_holdout_r1.py",
    REPO / "scripts/build_compound_execution_holdout_r2.py",
)
POLICY_SOURCES = common.POLICY_SOURCES
MEASUREMENT_SOURCES = (RUNNER, EXECUTION_GATE)
ALLOWED_OPERATIONS = prior.ALLOWED_OPERATIONS


def build_cases(run_id: str, _document_prefix: str) -> list[dict[str, Any]]:
    return [
        {
            "name": "r3_note_dual_interleaved_es",
            "planner_path": "real_llm_blind_interleaved_dependency_dag",
            "objective": (
                f"Crea una nota titulada Norte {run_id} con contenido arriba "
                f"{run_id} y léela antes de continuar; luego crea una nota titulada "
                f"Sur {run_id} con contenido abajo {run_id} y lee la segunda nota."
            ),
            "expected": ["note.create", "note.read", "note.create", "note.read"],
            "dependency_positions": [[], [0], [], [2]],
            "confirm": {"note.create"},
        },
        {
            "name": "r3_note_three_local_permuted_en",
            "planner_path": "real_llm_blind_six_step_dependency_dag",
            "ui_language": "en",
            "objective": (
                f"Create three local notes: the first titled Quartz {run_id} with "
                f"content white {run_id}, the second titled Amber {run_id} with "
                f"content orange {run_id}, and the third titled Jade {run_id} with "
                f"content green {run_id}. Then read the last note, the first note, "
                "and the middle note."
            ),
            "expected": [
                "note.create", "note.create", "note.create",
                "note.read", "note.read", "note.read",
            ],
            "dependency_positions": [[], [], [], [2], [0], [1]],
            "confirm": {"note.create"},
        },
        {
            "name": "r3_note_four_named_es",
            "planner_path": "real_llm_blind_eight_step_named_dependency_dag",
            "objective": (
                f"Crea cuatro notas: Alba {run_id} con contenido amanecer {run_id}, "
                f"Brisa {run_id} con contenido viento {run_id}, Nube {run_id} con "
                f"contenido lluvia {run_id} y Valle {run_id} con contenido tierra "
                f"{run_id}. Después lee, en orden, la nota Nube, la nota Valle, "
                "la nota Alba y la nota Brisa."
            ),
            "expected": [
                "note.create", "note.create", "note.create", "note.create",
                "note.read", "note.read", "note.read", "note.read",
            ],
            "dependency_positions": [[], [], [], [], [2], [3], [0], [1]],
            "confirm": {"note.create"},
        },
        {
            "name": "r3_readonly_status_triad_es",
            "planner_path": "real_llm_blind_cross_family_readonly_plan",
            "objective": (
                "Revisa en una sola misión: primero el estado del audio, después "
                "el estado del sistema y finalmente el estado de la red."
            ),
            "expected": ["audio.status", "system.status", "network.status"],
            "dependency_positions": [[], [], []],
            "confirm": set(),
        },
        {
            "name": "r3_readonly_hardware_triad_es",
            "planner_path": "real_llm_blind_cross_family_readonly_plan",
            "objective": (
                "Revisa estas vistas de hardware en orden: primero el estado del "
                "teclado, después los periféricos conectados y finalmente los "
                "dispositivos Bluetooth visibles."
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
            "name": "r3_note_read_then_audio_en",
            "planner_path": "real_llm_blind_mixed_dependency_plan",
            "ui_language": "en",
            "objective": (
                f"Create a note titled Signal {run_id} with content checked "
                f"{run_id}, read that same note, and then report audio status."
            ),
            "expected": ["note.create", "note.read", "audio.status"],
            "dependency_positions": [[], [0], []],
            "confirm": {"note.create"},
        },
    ]


def case_contract_sha256() -> str:
    return hashlib.sha256(
        common._canonical(build_cases("RUNID", "DOCUMENT"))
    ).hexdigest()


def validate_cases(cases: list[dict[str, Any]]) -> None:
    if len(cases) != 6 or len({str(case["name"]) for case in cases}) != len(cases):
        raise RuntimeError("compound R3 requires six unique cases")
    if sum(len(case["expected"]) for case in cases) != 27:
        raise RuntimeError("compound R3 step count changed")
    for case in cases:
        if (
            set(case.get("expected", ())) - ALLOWED_OPERATIONS
            or len(case.get("dependency_positions", ()))
            != len(case.get("expected", ()))
            or set(case.get("confirm", ())) - {"note.create"}
        ):
            raise RuntimeError(f"compound R3 case is unsafe: {case.get('name')}")


def build() -> dict[str, Any]:
    if PREREGISTRATION.exists() or OUTPUT.exists():
        raise RuntimeError("refusing to overwrite compound execution R3 state")
    cases = build_cases("RUNID", "DOCUMENT")
    validate_cases(cases)
    previous_objectives = {
        " ".join(str(case["objective"]).casefold().split())
        for builder in (common.build_cases, prior.build_cases)
        for case in builder("RUNID", "DOCUMENT")
    }
    current_objectives = {
        " ".join(str(case["objective"]).casefold().split()) for case in cases
    }
    if current_objectives & previous_objectives:
        raise RuntimeError("compound R3 overlaps a prior objective")
    runtime_manifest = (
        Path(os.environ["LOCALAPPDATA"]) / "BAXYRuntime/mind-runtime-v1.json"
    ).resolve(strict=True)
    core = common.load_build_layout(REPO).core_executable(REPO).resolve(strict=True)
    manifest = {
        "schema": "baxy.compound-execution-holdout-r3.preregistration.v1",
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
            "steps": 27,
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
