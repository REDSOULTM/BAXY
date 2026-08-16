"""Freeze the corrected R266 scorer after R265 failed before recogniser import."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
CORPUS = REPO / "artifacts/development/fresh_independent_cut_b_r264.jsonl"
R264_PREREGISTRATION = (
    REPO / "artifacts/development/fresh_independent_cut_b_r264.preregistration.json"
)
R265_PREREGISTRATION = (
    REPO / "artifacts/development/fresh_independent_cut_b_r265.recogniser.preregistration.json"
)
R265_OUTPUT = REPO / "artifacts/audit/fresh_independent_cut_b_recogniser_r265.json"
RUNNER = REPO / "experiments/mind_router_spike/run_fresh_independent_cut_b_recogniser_r266.py"
OUTPUT = (
    REPO
    / "artifacts/development/fresh_independent_cut_b_r266.recogniser.preregistration.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict[str, object]:
    required = (CORPUS, R264_PREREGISTRATION, R265_PREREGISTRATION, RUNNER)
    if any(not path.is_file() for path in required):
        raise RuntimeError("R266 requires R264, failed-R265 evidence, and corrected runner")
    if R265_OUTPUT.exists():
        raise RuntimeError("R266 is invalid if R265 produced a measurement result")
    r264 = json.loads(R264_PREREGISTRATION.read_text(encoding="utf-8"))
    r265 = json.loads(R265_PREREGISTRATION.read_text(encoding="utf-8"))
    if r264["identities"]["corpus_sha256"] != sha256(CORPUS):
        raise RuntimeError("R266 requires the sealed R264 corpus hash")
    if r264["constraints"]["recogniser_measured"] is not False:
        raise RuntimeError("R266 requires R264 before its first recogniser measurement")
    if "runner_sha256" not in r265["scoring"]:
        raise RuntimeError("R266 requires the recorded R265 schema defect")
    return {
        "schema": "baxy.fresh-independent-cut-b-recogniser-r266-preregistration.v1",
        "authority": "sealed_before_first_successful_r264_recogniser_measurement",
        "predecessor": {
            "r265_preregistration_sha256": sha256(R265_PREREGISTRATION),
            "r265_output_created": False,
            "r265_failure": "KeyError: runner_sha256 during preflight before recogniser import",
        },
        "source": {
            "r264_rows": r264["population"]["rows"],
            "r264_corpus_sha256": sha256(CORPUS),
            "r264_preregistration_sha256": sha256(R264_PREREGISTRATION),
        },
        "scoring": {
            "runner": RUNNER.relative_to(REPO).as_posix(),
            "runner_sha256": sha256(RUNNER),
            "expected_operation_match": "resolve_explicit_effects operations equal the complete expected_operations tuple",
            "outcomes": ["resolved_expected", "resolved_other", "unresolved"],
            "cuts": ["overall", "family", "language", "expected_operation"],
            "recogniser_majority_limit": 0.5,
            "alias_surface_reported": True,
            "runner_hash_location_validated": "scoring.runner_sha256",
        },
        "constraints": {
            "recogniser_measured": False,
            "model_started": False,
            "registered_runtime_modified": False,
            "providers_enabled": False,
            "effects_executed": 0,
            "r228_opened": False,
            "clinc_opened": False,
            "public_holdout_opened": False,
            "opened_v9": False,
            "voice_stt_wake_exercised": False,
        },
        "next_step": "Commit this corrected scorer and preregistration unchanged, freeze the worktree, then invoke the R266 runner exactly once.",
        "identities": {"program_sha256": sha256(Path(__file__))},
    }


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"R266 preregistration exists: {OUTPUT}")
    OUTPUT.write_bytes(
        (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
