import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREREGISTRATION = (
    ROOT
    / "artifacts"
    / "development"
    / "physical_dependent_missions_preregistration_20260811.json"
)


def _load() -> dict[str, object]:
    return json.loads(PREREGISTRATION.read_text(encoding="utf-8"))


def test_physical_dependent_missions_cover_text_voice_and_three_languages() -> None:
    payload = _load()
    missions = payload["missions"]
    matrix = payload["measurementMatrix"]

    assert len(missions) == 3
    assert {mission["language"] for mission in missions} == {"es", "en", "spanglish"}
    assert matrix["text"]["missions"] == matrix["text"]["requiredPassed"] == 3
    assert matrix["voice"]["missions"] == matrix["voice"]["requiredPassed"] == 3
    assert matrix["voice"]["inputDevice"] == 6
    assert matrix["voice"]["outputDevice"] == 9


def test_every_mission_has_a_real_backward_dependency_and_bounded_operations() -> None:
    payload = _load()
    allowed = {"note.create", "note.read", "audio.status", "system.status"}
    total_steps = 0

    for mission in payload["missions"]:
        operations = mission["expectedOperations"]
        dependencies = mission["dependencyPositions"]
        assert len(operations) == len(dependencies)
        assert set(operations) <= allowed
        assert any(dependencies)
        for index, positions in enumerate(dependencies):
            assert all(0 <= dependency < index for dependency in positions)
        total_steps += len(operations)

    assert total_steps == 10
    assert payload["acceptance"]["verifiedSteps"] == "20/20 total across text and voice"


def test_preregistration_cannot_grant_external_authority_or_claim_cut_c() -> None:
    payload = _load()
    safety = payload["safety"]
    matrix = payload["measurementMatrix"]
    identity = payload["sourceIdentityBeforeImplementation"]

    assert "not a blind cut-C" in payload["authority"]
    assert safety["personalBaxyDataReadable"] is False
    assert safety["personalBaxyDataWritable"] is False
    assert safety["externalEffectsAllowed"] is False
    assert safety["maximumAmbiguousEffects"] == 0
    assert payload["effectsExecuted"] == 0
    assert payload["audioPlayedOrCaptured"] is False
    # The campaign is bound to the tree it will actually measure. The v17
    # identity is retained beside it as provenance: that capture is consumed
    # and terminal, so it can gate nothing further.
    assert identity["wakeProgramTreeSha256"] == (
        "d0cf265cfe6b8379637a893da9fc5b9bf05c73f1dbeb5cc77d973ad604db49d2"
    )
    assert identity["wakeV17HistoricalProgramTreeSha256"] == (
        "756a5b311b20ed833da182595766c9d577cca89f20d7a4355eb972576f0f90c0"
    )
    assert identity["wakeProgramTreeSha256"] != (
        identity["wakeV17HistoricalProgramTreeSha256"]
    )
    # A re-seal is only honest while nothing has been measured.
    reseal = payload["resealReason"]
    assert reseal["measurementStatusWhenResealed"] == "unopened"
    assert reseal["plannedReceiptsExisted"] is False
    assert all(len(value) == 64 for value in identity.values())
    outputs = {
        matrix["text"]["output"],
        matrix["voice"]["output"],
        matrix["combinedOutput"],
    }
    assert len(outputs) == 3
    assert all(path.startswith("artifacts/product/") for path in outputs)
