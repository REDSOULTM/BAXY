"""Reject the completed R243 probe when its sealed output is non-finite."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
R243 = REPO / "artifacts/development/supervised_reranker_domain_r243.json"
OUTPUT = REPO / "artifacts/audit/supervised_reranker_domain_r243_nonfinite_rejection_r244.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _nonfinite(value: Any, path: str = "$") -> list[str]:
    if isinstance(value, float) and not math.isfinite(value):
        return [path]
    if isinstance(value, dict):
        return [issue for key, item in value.items() for issue in _nonfinite(item, f"{path}.{key}")]
    if isinstance(value, list):
        return [issue for index, item in enumerate(value) for issue in _nonfinite(item, f"{path}[{index}]")]
    return []


def build() -> dict[str, object]:
    report = json.loads(R243.read_text(encoding="utf-8"))
    fields = _nonfinite(report)
    if not fields:
        raise RuntimeError("R244 only attests a non-finite R243 result")
    return {
        "schema": "baxy.supervised-reranker-domain.r244-nonfinite-rejection.v1",
        "authority": "read_only_attestation_of_completed_r243_result",
        "verdict": "rejected_invalid_nonfinite_training",
        "reason": "R243 contains non-finite training loss, threshold and score quantiles; its mechanically derived zero-candidate count is not admissible evidence.",
        "nonfinite_fields": fields,
        "constraints": {"model_started": False, "providers_enabled": False, "effects_executed": 0, "opened_v9": False, "voice_stt_wake_exercised": False, "r228_opened": False},
        "identities": {"r243_sha256": sha256(R243), "program_sha256": sha256(Path(__file__))},
        "next_requirement": "Do not tune or rerun R243. A successor must change numerical training stability under a new preregistration and retain finite-score validation before any OOS claim.",
    }


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing to overwrite attestation: {OUTPUT}")
    OUTPUT.write_bytes((json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
