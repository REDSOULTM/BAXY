from __future__ import annotations

import json
from pathlib import Path

from sealed_evidence import assert_sealed

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/development/cross_encoder_r208_preregistration.json"
ARTIFACT_SEAL = "5e4016de10a3ed2b7e536b7728c4c654513065e51c3cbbad7cea64248551ca49"


def test_r208_preregistration_freezes_binary_all_operation_abstention() -> None:
    # The builder needs the fine-tuned checkpoint it froze, at
    # D:\BAXYRuntime\experiments\mtop-operation-compatibility-verifier-v16.
    # That checkpoint is no longer on this machine and was never published, so
    # the preregistration it produced is read and sealed instead (§7).
    assert_sealed(ARTIFACT, ARTIFACT_SEAL)
    report = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert report["candidate"]["decision"] == {"compatible_label": "compatible", "candidate_probability_threshold": 0.5, "all_170_labels_scored": True, "threshold_calibrated_on_r186": False}
    assert report["data_contract"]["r186_evaluation_only"] is True
    assert report["constraints"]["no_lexical_gate"] is True
    assert report["constraints"]["no_posthoc_threshold"] is True
    assert report["evaluation"]["model_owned_rows"] == 77
    assert report["evaluation"]["oos_controls"] == 9
