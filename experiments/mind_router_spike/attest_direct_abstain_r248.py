"""Publish the pre-execution structural rejection of the sealed R247 runner."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
R247 = REPO / "artifacts/development/direct_abstain_classifier_r247.preregistration.json"
RUNNER = REPO / "experiments/mind_router_spike/run_direct_abstain_classifier_r248.py"
OUTPUT = REPO / "artifacts/audit/direct_abstain_classifier_r248_preexecution_rejection.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict[str, object]:
    preregistration = json.loads(R247.read_text(encoding="utf-8"))
    if preregistration["identities"]["runner_sha256"] != sha256(RUNNER):
        raise RuntimeError("R248 requires the sealed R247 runner identity")
    import sys

    sys.path.insert(0, str(REPO))
    from experiments.mind_router_spike import run_direct_abstain_classifier_r248 as runner

    names = runner.family_names()
    inside, outside, fresh_outside = runner.development_rows()
    positives = sum(1 for line in runner.R207.read_text(encoding="utf-8").splitlines() if json.loads(line)["target"] == 1)
    if len(inside) != runner.INSIDE_COUNT or len(outside) != runner.OUTSIDE_COUNT or len(fresh_outside) >= positives:
        raise RuntimeError("R248 only rejects the documented impossible one-to-one sample construction")
    return {
        "schema": "baxy.direct-abstain-classifier.r248-preexecution-rejection.v1",
        "authority": "read_only_preexecution_attestation_no_model_import_or_training",
        "verdict": "rejected_preexecution_insufficient_fresh_oos_for_registered_balance",
        "reason": "R247's sealed runner requires one fresh OOS abstain row per R207 positive. After preserving every R236/R241/R243/R246 partition and R248's 256-row OOS evaluation, 1,479 fresh OOS rows remain for 4,740 R207 positives.",
        "observed": {"typed_families": len(names), "fresh_inside_evaluation_rows": len(inside), "fresh_outside_evaluation_rows": len(outside), "fresh_oos_training_rows_available": len(fresh_outside), "r207_positive_rows_required": positives},
        "constraints": {"model_started": False, "r228_opened": False, "public_holdout_opened": False, "registered_runtime_modified": False, "providers_enabled": False, "effects_executed": 0, "opened_v9": False, "voice_stt_wake_exercised": False},
        "identities": {"r247_sha256": sha256(R247), "runner_sha256": sha256(RUNNER), "program_sha256": sha256(Path(__file__))},
        "next_requirement": "Do not alter or run R248. A successor may use only the demonstrably available fresh OOS rows with a separately sealed inverse-frequency class-weighted loss.",
    }


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing to overwrite attestation: {OUTPUT}")
    OUTPUT.write_bytes((json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
