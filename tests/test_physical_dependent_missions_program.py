from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.mission_validation import run_physical_dependent_missions_v1 as gate
from experiments.mission_validation import certify_post_wake_repairs_v1 as certifier


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _passing_result(mission: dict[str, object]) -> dict[str, object]:
    operations = list(mission["expectedOperations"])
    dependencies = list(mission["dependencyPositions"])
    return {
        "status": "passed",
        "turn_response_type": "turn.result",
        "intent_operations": operations,
        "effect_operations": operations,
        "response_type": "plan.result",
        "kind": "plan",
        "operations": operations,
        "dependency_positions": dependencies,
        "steps": [
            {
                "operation": operation,
                "status": "completed",
                "verified": True,
                "effect_may_have_occurred": False,
                # note.create is low_reversible and RiskPolicy maps Reversible to
            # Allow, so the kernel issues no challenge and nothing is confirmed.
            # This mirrors what the product actually returns.
            "confirmed": False,
                "grounded": bool(dependencies[index]),
                "dependency_authority_match": (True if dependencies[index] else None),
            }
            for index, operation in enumerate(operations)
        ],
        "isolated_data_removed": True,
        "owned_processes_remaining": 0,
    }


def test_program_binds_exact_preregistered_safe_missions() -> None:
    contract = gate.load_contract()

    assert [mission["language"] for mission in contract["missions"]] == [
        "es",
        "en",
        "spanglish",
    ]
    assert (
        sum(len(mission["expectedOperations"]) for mission in contract["missions"])
        == 10
    )
    assert {
        operation
        for mission in contract["missions"]
        for operation in mission["expectedOperations"]
    } <= gate.ALLOWED_OPERATIONS
    assert gate.ALLOWED_MUTATIONS == {"note.create"}


def test_program_requires_exact_order_confirmation_and_dependency_authority() -> None:
    mission = gate.load_contract()["missions"][1]
    result = _passing_result(mission)

    assert gate._mission_passed(mission, result) is True

    wrong_order = dict(result)
    wrong_order["operations"] = list(reversed(result["operations"]))
    assert gate._mission_passed(mission, wrong_order) is False

    # The harness may confirm nothing outside the single allowed mutation. It
    # must NOT demand that the kernel challenge that mutation: the preregistered
    # acceptance block never asked for it, and note.create is deliberately
    # allowed without a challenge, so requiring one rejected two missions the
    # product had performed correctly.
    unconfirmed_mutation = json.loads(json.dumps(result))
    assert unconfirmed_mutation["steps"][0]["operation"] == "note.create"
    assert unconfirmed_mutation["steps"][0]["confirmed"] is False
    assert gate._mission_passed(mission, unconfirmed_mutation) is True

    confirmed_non_mutation = json.loads(json.dumps(result))
    confirmed_non_mutation["steps"][2]["confirmed"] = True
    assert confirmed_non_mutation["steps"][2]["operation"] not in gate.ALLOWED_MUTATIONS
    assert gate._mission_passed(mission, confirmed_non_mutation) is False

    wrong_authority = json.loads(json.dumps(result))
    wrong_authority["steps"][2]["dependency_authority_match"] = False
    assert gate._mission_passed(mission, wrong_authority) is False


def test_program_requires_wake_and_post_wake_receipts(tmp_path: Path) -> None:
    wake = tmp_path / "wake.json"
    _write(
        wake,
        {
            "schema": "baxy.wake-v17-combined-validation-receipt.v2",
            "supplementSha256": gate.WAKE_SUPPLEMENT_SHA256,
            # The terminal consumed receipt, which is what the re-sealed
            # preregistration requires: v17 was opened once, rejected at 46/48,
            # and can never pass, so demanding a promoted receipt froze the
            # campaign permanently.
            "validationPassed": False,
            "promotionEligible": False,
            "promotionExecuted": False,
            "effectsExecuted": 0,
            "metrics": {
                "positiveHits": 46,
                "positiveFiles": 48,
                "negativeFalseActivations": 0,
                "negativeFiles": 96,
                "latencyP50Seconds": 1.0,
                "latencyP95Seconds": 1.5,
            },
            "checks": {
                "positiveHitsExact": False,
                "allFrozenSourcesMatched": True,
            },
        },
    )
    gate._assert_wake_receipt(wake)

    # A promoted receipt is now refused: only the terminal rejected one counts,
    # so a newer or more favourable receipt cannot be substituted for history.
    promoted = json.loads(wake.read_text(encoding="utf-8"))
    promoted["validationPassed"] = True
    promoted["promotionEligible"] = True
    promoted["metrics"]["positiveHits"] = 48
    promoted["checks"]["positiveHitsExact"] = True
    substituted = tmp_path / "promoted.json"
    _write(substituted, promoted)
    with pytest.raises(ValueError, match="terminal consumed"):
        gate._assert_wake_receipt(substituted)

    post = tmp_path / "post.json"
    _write(
        post,
        {
            "schema": "baxy.post-wake-repairs-receipt.v1",
            "status": "passed",
            "wakeReceiptSha256": gate._sha256(wake),
            "effectsExecuted": 0,
            "checks": {
                "focusedRegressions": True,
                "sourceQualityFast": True,
                "gpuBudget": True,
                "cpuBudget": True,
                "socialClosureEquivalence": True,
            },
        },
    )
    gate._assert_post_wake_receipt(post, wake)

    invalid = json.loads(post.read_text(encoding="utf-8"))
    invalid["checks"]["cpuBudget"] = False
    _write(post, invalid)
    with pytest.raises(ValueError, match="not fully certified"):
        gate._assert_post_wake_receipt(post, wake)


def test_program_combines_only_two_complete_modalities(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gate, "REPO", tmp_path)
    paths: list[Path] = []
    for modality in ("text", "voice"):
        path = tmp_path / f"{modality}.json"
        _write(
            path,
            {
                "schema": gate.SCHEMA,
                "modality": modality,
                "status": "passed",
                "contractSha256": gate.CONTRACT_SHA256,
                "metrics": {
                    "passedMissions": 3,
                    "verifiedSteps": 10,
                    "ambiguousEffects": 0,
                    "externalEffects": 0,
                    "ownedProcessesRemaining": 0,
                },
            },
        )
        paths.append(path)

    result = gate.combine_reports(*paths)

    assert result["status"] == "passed"
    assert result["metrics"]["passedMissions"] == 6
    assert result["metrics"]["verifiedSteps"] == 20
    assert result["capturedAudioRetained"] is False
    assert result["transcriptTextRetained"] is False


def test_physical_text_half_is_measured_and_the_voice_half_is_not() -> None:
    """The campaign is no longer unopened, so this states what it actually is.

    It used to assert that no output existed at all, which was true while the
    runner could not start: it demanded a promoted wake receipt its own
    re-sealed contract had declared unreachable. The text half now passes 3/3
    with 10/10 verified steps; the voice half needs a physical speaker, room and
    microphone and has not been run, so nothing may be claimed about it.
    """
    assert certifier.OUTPUT.is_file()
    assert gate.TEXT_OUTPUT.is_file()
    text = json.loads(gate.TEXT_OUTPUT.read_text(encoding="utf-8"))
    assert text["status"] == "passed"
    assert text["modality"] == "text"
    assert text["contractSha256"] == gate.CONTRACT_SHA256
    assert text["metrics"]["passedMissions"] == 3
    assert text["metrics"]["verifiedSteps"] == 10
    assert text["metrics"]["ambiguousEffects"] == 0
    assert text["metrics"]["externalEffects"] == 0
    assert text["metrics"]["ownedProcessesRemaining"] == 0
    assert text["personalBaxyDataAccessed"] is False

    assert not gate.VOICE_OUTPUT.exists()
    assert not gate.COMBINED_OUTPUT.exists()


def test_post_wake_certifier_requires_both_complete_budget_profiles(
    tmp_path: Path,
) -> None:
    # The deadlines come from the gate that declares them. Hard-coding them here
    # is how this fixture came to hold narrate=20.0 for both profiles, a value
    # from before the CPU timeout contract was repaired to 130 s, which rejected
    # a correctly measured CPU profile as uncertified.
    from scripts import measure_mind_budget

    def profile(name: str) -> dict[str, object]:
        declared = measure_mind_budget.PROFILE_LIMITS[name]
        return {
            "status": "passed",
            "aborted": False,
            "requests_completed": 45,
            "requests_expected": 45,
            "errors": [],
            "gpu_layers": 99 if name == "gpu" else 0,
            "timeouts_seconds": {
                key: declared[key]
                for key in ("llm_http", "turn.decide", "arguments", "narrate")
            },
            "checks": {"zero_errors": True, "all_requests_completed": True},
        }

    report = tmp_path / "budget.json"
    payload = {
        "schema": "baxy-mind-budget-gate-v6",
        "status": "passed",
        "method": {"effects_executed": 0},
        "profiles": {
            "gpu": profile("gpu"),
            "cpu_fallback": profile("cpu_fallback"),
        },
    }
    _write(report, payload)

    assert certifier.validate_budget_report(report)["status"] == "passed"

    payload["profiles"]["cpu_fallback"]["timeouts_seconds"]["llm_http"] = 19.0
    _write(report, payload)
    with pytest.raises(ValueError, match="cpu_fallback profile"):
        certifier.validate_budget_report(report)


def test_post_wake_certifier_binds_the_original_preregistration() -> None:
    assert (
        certifier._sha256(certifier.PREREGISTRATION) == certifier.PREREGISTRATION_SHA256
    )
