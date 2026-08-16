from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/mind_router_spike/snapshot_current_core_catalog_r219.py"
ARTIFACT = ROOT / "artifacts/development/current_core_catalog_snapshot_r219.json"


def test_r219_published_snapshot_is_current_core_read_only_evidence() -> None:
    artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    catalogue = artifact["catalogue"]
    names = [row["name"] for row in catalogue["capabilities"]]

    assert artifact["schema"] == "baxy.current-core-catalog-snapshot.r219.v1"
    assert catalogue["operations"] == 174
    assert len(names) == len(set(names)) == 174
    assert (
        hashlib.sha256(
            json.dumps(
                names, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()
        == catalogue["operation_names_sha256"]
    )
    assert artifact["constraints"] == {
        "model_started": False,
        "providers_enabled": False,
        "effects_executed": 0,
        "opened_v9": False,
        "voice_stt_wake_exercised": False,
    }


def test_r219_source_has_no_model_runtime_dependency() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert "LlmRuntime" not in source
    assert "resolve_runtime" not in source
    assert "turn.decide" not in source
    assert "current_core_catalog_snapshot" in source
