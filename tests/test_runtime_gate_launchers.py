"""Structural guards for opt-in LLM gates; these tests never launch a model."""

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.run_llm_plan_execution_gate import (
    build_cases,
    dependency_authority_matches,
    known_documents_root,
    project,
    select_verified_dependency_observations,
)


ROOT = Path(__file__).resolve().parents[1]
EXHAUSTIVE_LAUNCHERS = (
    ROOT / "scripts" / "run_exhaustive_runtime_model_gate.py",
    ROOT / "scripts" / "run_exhaustive_runtime_model_gate_parallel.py",
)
LAUNCHERS = (
    ROOT / "scripts" / "measure_mind_budget.py",
    ROOT / "scripts" / "run_planner_corpus_gate.py",
    ROOT / "scripts" / "run_llm_plan_execution_gate.py",
    *EXHAUSTIVE_LAUNCHERS,
)


def test_llm_gate_launchers_share_fail_closed_runtime_resolution() -> None:
    for launcher in LAUNCHERS:
        source = launcher.read_text(encoding="utf-8")
        assert "add_runtime_arguments" in source, launcher.name
        assert "resolve_runtime_from_args" in source, launcher.name
        assert "runtime.python" in source, launcher.name
        assert "runtime.python_path" in source, launcher.name
        assert "runtime.gguf" in source, launcher.name
        assert "runtime.llama_server" in source, launcher.name
        assert "runtime.gpu_layers" in source, launcher.name


def test_llm_gate_launchers_have_no_repository_legacy_model_default() -> None:
    for launcher in LAUNCHERS:
        source = launcher.read_text(encoding="utf-8")
        assert "legacy/models" not in source, launcher.name
        assert "legacy\\models" not in source, launcher.name


def test_shared_resolver_requires_registered_or_all_explicit_components() -> None:
    source = (
        ROOT / "scripts" / "baxy_runtime_config.py"
    ).read_text(encoding="utf-8")

    assert "baxy-mind-runtime-v1" in source
    assert "all_explicit" in source
    assert "resolve(strict=True)" in source
    assert "legacy/models" not in source


@pytest.mark.parametrize(
    "launcher",
    EXHAUSTIVE_LAUNCHERS,
    ids=lambda path: path.stem,
)
def test_exhaustive_launchers_keep_explicit_runtime_overrides(
    launcher: Path,
) -> None:
    completed = subprocess.run(
        [sys.executable, "-B", str(launcher), "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr
    for option in (
        "--runtime-manifest",
        "--python",
        "--python-path",
        "--gguf",
        "--llama-server",
        "--gpu-layers",
        "--ngl",
    ):
        assert option in completed.stdout


@pytest.mark.parametrize(
    "launcher",
    EXHAUSTIVE_LAUNCHERS,
    ids=lambda path: path.stem,
)
def test_exhaustive_launchers_fail_closed_with_a_stable_diagnostic(
    launcher: Path,
    tmp_path: Path,
) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            str(launcher),
            "--runtime-manifest",
            str(tmp_path / "missing-runtime.json"),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )

    assert completed.returncode == 2
    assert "baxy_runtime_configuration_invalid:" in completed.stderr
    assert "Traceback" not in completed.stderr


def test_mind_shell_gate_replaces_all_canonical_artifacts_atomically() -> None:
    source = (
        ROOT / "scripts" / "run_mind_shell_e2e_gate.ps1"
    ).read_text(encoding="utf-8")

    assert "function Move-AtomicGateFile" in source
    assert "[IO.File]::Replace($sourceFull, $destinationFull, $backupPath, $true)" in source
    assert "[IO.File]::Replace($temporary, $Path, $null" not in source
    assert source.count("Move-AtomicGateFile -Source") == 3
    assert (
        "elseif (Test-Path -LiteralPath $trxOutputPath -PathType Leaf)"
        in source
    )
    assert (
        "elseif (Test-Path -LiteralPath $attestationOutputPath -PathType Leaf)"
        in source
    )
    assert "$operationCounts['memory.status'] -eq 1" in source
    assert "$operationCounts['system.time'] -eq 5" in source
    assert "$operationCounts['system.status'] -eq 2" in source
    assert "$operationCounts['system.process.list'] -eq 3" in source
    assert "$operationCounts['task.list'] -eq 2" in source
    assert "$operationCounts['note.list'] -eq 2" in source
    assert "[int]$attestation.journal_records -eq 30" in source
    assert "[int]$attestation.started_records -eq 15" in source
    assert "[int]$attestation.completed_records -eq 15" in source
    assert "[int]$attestation.operation_counts.system_process_list -eq 3" in source
    assert "[int]$attestation.operation_counts.task_list -eq 2" in source
    assert "[int]$attestation.operation_counts.note_list -eq 2" in source
    assert "$attestation.journal_structure_valid -eq $true" in source
    assert "exactly_four_tests_executed" not in source
    assert "exactly_four_tests_passed" not in source
    assert "$selectionTrxName = 'mind-shell-selection.trx'" in source
    assert "$dotnetRoot = [IO.Path]::GetDirectoryName($dotnet)" in source
    assert "'DOTNET_ROOT_X64'" in source
    assert "$env:DOTNET_ROOT_X64 = $dotnetRoot" in source
    assert "function Get-TrxTestRecords" in source
    assert "$definitionsById.ContainsKey($testId)" in source
    assert "duplicate test definition identity" in source
    assert "a result without a matching test definition" in source
    assert "Strict ExplicitMode" in source
    assert "BAXY_RUN_REAL_MIND_SHELL_GATE" not in source
    assert "'--no-build'" in source
    assert "$physicalTestName =" in source
    assert "$physicalSelectionRecords.Count -eq 0" in source
    assert "$expectedTests + $physicalTestName" in source
    assert "$physicalWasOmitted" in source
    assert "$selectionCounters.total -eq $expectedSelectionRecordCount" in source
    assert "$selectionRecords.Count -eq $expectedSelectionRecordCount" in source
    assert "$selectionUnexpectedOutcomes.Count -eq 0" in source
    assert "$executionExpectedTests = @($physicalTestName)" in source
    assert "$counters.executed -eq $executionExpectedTests.Count" in source
    assert "$counters.passed -eq $executionExpectedTests.Count" in source
    assert "$actualUnexpectedOutcomes.Count -eq 0" in source
    assert "selection_result_outcomes = [ordered]@{" in source
    assert "selection_not_executed_tests = @(" in source
    assert "Compare-Object" in source
    assert "test_assembly_unchanged = $testAssemblyUnchanged" in source


def test_plan_execution_gate_scopes_private_dotnet_to_child_processes() -> None:
    source = (
        ROOT / "scripts" / "run_llm_plan_execution_gate.py"
    ).read_text(encoding="utf-8")

    assert "dotnet_executable" in source
    assert "environment_for_dotnet" in source
    assert "environment = environment_for_dotnet(dotnet_executable())" in source
    assert "environment.update(" in source
    assert "os.environ.update(" not in source


def test_plan_execution_gate_uses_the_redirected_windows_documents_folder() -> None:
    expected = Path(
        subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "[Environment]::GetFolderPath('MyDocuments')",
            ],
            text=True,
            encoding="utf-8",
        ).strip()
    ).resolve()

    assert known_documents_root() == expected


def test_plan_execution_gate_exercises_the_product_turn_boundary_first() -> None:
    source = (
        ROOT / "scripts" / "run_llm_plan_execution_gate.py"
    ).read_text(encoding="utf-8")

    assert '"type": "turn.decide"' in source
    assert '"effectOperations"' in source
    assert '"expectedOperations": effect_operations' in source
    assert source.index('"type": "turn.decide"') < source.index(
        '"type": "plan"', source.index("def run_case(")
    )
    assert "turn decision did not exactly cover the bounded objective" in source
    assert "if grounded" in source
    assert "else None" in source


def test_plan_execution_gate_covers_four_step_note_dependency_topologies() -> None:
    cases = {case["name"]: case for case in build_cases("runid", "document")}
    expected = {
        "llm_note_parallel_pair_dependencies": [[], [], [0], [1]],
        "llm_note_reverse_pair_dependencies": [[], [], [1], [0]],
        "llm_note_interleaved_pair_dependencies": [[], [0], [], [2]],
    }

    for name, dependency_positions in expected.items():
        case = cases[name]
        assert case["dependency_positions"] == dependency_positions
        assert len(case["expected"]) == 4
        assert set(case["expected"]) == {"note.create", "note.read"}
        assert case["confirm"] == {"note.create"}


def test_plan_execution_gate_covers_eight_step_note_dependency_topologies() -> None:
    cases = {case["name"]: case for case in build_cases("runid", "document")}
    expected = {
        "llm_note_eight_step_interleaved_dependencies": [
            [], [0], [], [2], [], [4], [], [6],
        ],
        "llm_note_eight_step_permuted_dependencies": [
            [], [], [], [], [2], [0], [3], [1],
        ],
        "llm_note_eight_step_permuted_dependencies_en": [
            [], [], [], [], [3], [1], [0], [2],
        ],
    }

    for name, dependency_positions in expected.items():
        case = cases[name]
        assert case["dependency_positions"] == dependency_positions
        assert len(case["expected"]) == 8
        assert case["expected"].count("note.create") == 4
        assert case["expected"].count("note.read") == 4
        assert case["confirm"] == {"note.create"}

    assert cases["llm_note_eight_step_permuted_dependencies_en"]["ui_language"] == "en"


def test_plan_execution_gate_reports_narrow_environmental_preconditions() -> None:
    source = (
        ROOT / "scripts" / "run_llm_plan_execution_gate.py"
    ).read_text(encoding="utf-8")

    assert '"environmental_errors": {"outlook_profile_not_configured"}' in source
    assert 'result["status"] = "environment_blocked"' in source
    assert 'response.get("effectMayHaveOccurred", False) is False' in source
    assert '"passed_with_environment_blocks"' in source


def test_plan_execution_gate_grounding_is_scoped_to_exact_verified_dependencies() -> None:
    step = {
        "id": "read",
        "argumentsMode": "after_dependencies",
        "dependsOn": ["wanted"],
    }
    observations = [
        {
            "stepId": "decoy",
            "verified": True,
            "status": "completed",
            "result": {"noteId": "decoy_note"},
        },
        {
            "stepId": "wanted",
            "verified": True,
            "status": "completed",
            "result": {"noteId": "wanted_note"},
        },
    ]

    selected = select_verified_dependency_observations(step, observations)
    observations[1]["result"]["noteId"] = "mutated_after_selection"

    assert selected == [
        {
            "stepId": "wanted",
            "verified": True,
            "status": "completed",
            "result": {"noteId": "wanted_note"},
        }
    ]


def test_plan_execution_gate_uses_the_app_observation_projection_contract() -> None:
    projected = project(
        {
            "authority": "must_not_cross_grounding_boundary",
            "recipientId": "recipient_opaque",
            "textSha256": "audit_only_not_grounding_authority",
            "title": "Verified page title",
            "text": "Verified page text",
            "url": "https://example.com/result",
        },
        "browser.page.read",
    )

    assert projected == {
        "recipientId": "recipient_opaque",
        "url": "https://example.com/result",
    }


def test_plan_execution_gate_rejects_authority_outside_selected_dependency() -> None:
    observations = [
        {
            "stepId": "first",
            "verified": True,
            "status": "completed",
            "result": {"noteId": "first_note"},
        }
    ]

    assert dependency_authority_matches(
        {"noteId": "first_note"},
        observations,
    ) is True
    assert dependency_authority_matches(
        {"noteId": "second_note"},
        observations,
    ) is False
    assert dependency_authority_matches(
        {"title": "Alfa"},
        observations,
    ) is None


@pytest.mark.parametrize(
    "observations",
    [
        [],
        [{"stepId": "create", "verified": False, "status": "completed"}],
        [
            {"stepId": "create", "verified": True, "status": "completed"},
            {"stepId": "create", "verified": True, "status": "completed"},
        ],
    ],
)
def test_plan_execution_gate_rejects_untrusted_dependency_sets(
    observations: list[dict[str, object]],
) -> None:
    step = {
        "id": "read",
        "argumentsMode": "after_dependencies",
        "dependsOn": ["create"],
    }

    assert select_verified_dependency_observations(step, observations) is None
