"""Preregister a blind, reversible compound plan-to-Core execution campaign."""

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

from scripts.build_layout import load_build_layout  # noqa: E402
from scripts.measure_mind_budget import write_json_atomic  # noqa: E402


OUTPUT = REPO / "artifacts/holdout/compound_execution_holdout_r1.json"
PREREGISTRATION = (
    REPO / "artifacts/holdout/compound_execution_holdout_r1.preregistration.json"
)
RUNNER = REPO / "experiments/mind_router_spike/run_compound_execution_holdout_r1.py"
EXECUTION_GATE = REPO / "scripts/run_llm_plan_execution_gate.py"
POLICY_SOURCES = (
    REPO / "src/baxy_mind/__main__.py",
    REPO / "src/baxy_mind/planner.py",
    REPO / "src/baxy_mind/effect_intent.py",
    REPO / "src/baxy_mind/catalog_operation_aliases.py",
    REPO / "src/baxy_mind/data/catalog_operation_aliases.v1.json",
)
MEASUREMENT_SOURCES = (RUNNER, EXECUTION_GATE)
ALLOWED_OPERATIONS = frozenset(
    {
        "audio.status",
        "bluetooth.radio.status",
        "input.keyboard.status",
        "input.mouse.status",
        "network.status",
        "note.create",
        "note.read",
        "system.status",
    }
)


def build_cases(run_id: str, _document_prefix: str) -> list[dict[str, Any]]:
    """Materialize the sealed matrix with a unique private namespace."""

    return [
        {
            "name": "blind_note_dual_interleaved_es",
            "planner_path": "blind_real_llm_interleaved_dependency_dag",
            "objective": (
                f"Crea una nota titulada Faro {run_id} con contenido norte {run_id}, "
                "léela inmediatamente, luego crea una nota titulada Puerto "
                f"{run_id} con contenido sur {run_id} y lee esa segunda nota."
            ),
            "expected": ["note.create", "note.read", "note.create", "note.read"],
            "dependency_positions": [[], [0], [], [2]],
            "confirm": {"note.create"},
        },
        {
            "name": "blind_note_three_permuted_en",
            "planner_path": "blind_real_llm_six_step_dependency_dag",
            "ui_language": "en",
            "objective": (
                f"Create three private notes: the first titled Cedar {run_id} with "
                f"content red {run_id}, the second titled Maple {run_id} with content "
                f"green {run_id}, and the third titled Pine {run_id} with content blue "
                f"{run_id}. After all three exist, read the middle note, then the last "
                "note, and finally the first note."
            ),
            "expected": [
                "note.create", "note.create", "note.create",
                "note.read", "note.read", "note.read",
            ],
            "dependency_positions": [[], [], [], [1], [2], [0]],
            "confirm": {"note.create"},
        },
        {
            "name": "blind_note_four_permuted_spanglish",
            "planner_path": "blind_real_llm_eight_step_dependency_dag",
            "objective": (
                f"Create cuatro notas: Sol {run_id} con contenido one {run_id}, Luna "
                f"{run_id} con contenido two {run_id}, Mar {run_id} con contenido "
                f"three {run_id} y Monte {run_id} con contenido four {run_id}. Después "
                "read, en este orden, la nota Mar, la nota Sol, la nota Monte y la nota Luna."
            ),
            "expected": [
                "note.create", "note.create", "note.create", "note.create",
                "note.read", "note.read", "note.read", "note.read",
            ],
            "dependency_positions": [[], [], [], [], [2], [0], [3], [1]],
            "confirm": {"note.create"},
        },
        {
            "name": "blind_readonly_status_triad_es",
            "planner_path": "blind_real_llm_cross_family_readonly_plan",
            "objective": (
                "En una sola misión revisa primero el estado del sistema, después "
                "el estado del audio y finalmente el estado de la red."
            ),
            "expected": ["system.status", "audio.status", "network.status"],
            "dependency_positions": [[], [], []],
            "confirm": set(),
        },
        {
            "name": "blind_readonly_hardware_triad_en",
            "planner_path": "blind_real_llm_cross_family_readonly_plan",
            "ui_language": "en",
            "objective": (
                "In one mission report keyboard status, then mouse status, and "
                "finally Bluetooth radio status."
            ),
            "expected": [
                "input.keyboard.status",
                "input.mouse.status",
                "bluetooth.radio.status",
            ],
            "dependency_positions": [[], [], []],
            "confirm": set(),
        },
        {
            "name": "blind_note_read_then_system_spanglish",
            "planner_path": "blind_real_llm_mixed_dependency_plan",
            "objective": (
                f"Crea una nota titulada Puente {run_id} con contenido mixed {run_id}, "
                "read esa misma nota y después reporta system status."
            ),
            "expected": ["note.create", "note.read", "system.status"],
            "dependency_positions": [[], [0], []],
            "confirm": {"note.create"},
        },
    ]


def _canonical(value: Any) -> bytes:
    def convert(node: Any) -> Any:
        if isinstance(node, set):
            return sorted(node)
        if isinstance(node, dict):
            return {key: convert(child) for key, child in sorted(node.items())}
        if isinstance(node, list):
            return [convert(child) for child in node]
        return node

    return json.dumps(
        convert(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def case_contract_sha256() -> str:
    return hashlib.sha256(_canonical(build_cases("RUNID", "DOCUMENT"))).hexdigest()


def validate_cases(cases: list[dict[str, Any]]) -> None:
    if len(cases) != 6 or len({str(case["name"]) for case in cases}) != len(cases):
        raise RuntimeError("compound R1 requires six unique cases")
    if sum(len(case["expected"]) for case in cases) != 27:
        raise RuntimeError("compound R1 step count changed")
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
            raise RuntimeError(f"compound R1 case is unsafe: {case.get('name')}")


def build() -> dict[str, Any]:
    if PREREGISTRATION.exists() or OUTPUT.exists():
        raise RuntimeError("refusing to overwrite compound execution R1 state")
    cases = build_cases("RUNID", "DOCUMENT")
    validate_cases(cases)
    runtime_manifest = (
        Path(os.environ["LOCALAPPDATA"]) / "BAXYRuntime/mind-runtime-v1.json"
    ).resolve(strict=True)
    core = load_build_layout(REPO).core_executable(REPO).resolve(strict=True)
    manifest = {
        "schema": "baxy.compound-execution-holdout-r1.preregistration.v1",
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
        },
        "sources": {
            "builder": str(Path(__file__).resolve().relative_to(REPO)),
            "builder_sha256": _sha256(Path(__file__).resolve()),
            "measurement_sha256": {
                str(path.relative_to(REPO)): _sha256(path)
                for path in MEASUREMENT_SOURCES
            },
            "policy_sha256": {
                str(path.relative_to(REPO)): _sha256(path)
                for path in POLICY_SOURCES
            },
            "runtime_manifest_sha256": _sha256(runtime_manifest),
            "core_sha256": _sha256(core),
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
