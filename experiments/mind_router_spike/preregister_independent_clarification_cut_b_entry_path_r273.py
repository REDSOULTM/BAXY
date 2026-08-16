"""Seal a path-partition measurement before a model-decision probe for R270."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
CORPUS = REPO / "artifacts/development/independent_clarification_cut_b_r270.jsonl"
R270_PREREGISTRATION = (
    REPO
    / "artifacts/development/independent_clarification_cut_b_r270.preregistration.json"
)
R272_RESULT = (
    REPO / "artifacts/audit/independent_clarification_cut_b_recogniser_r272.json"
)
CATALOGUE = REPO / "artifacts/development/current_core_catalog_snapshot_r219.json"
RUNNER = (
    REPO
    / "experiments/mind_router_spike/measure_independent_clarification_cut_b_entry_path_r274.py"
)
OUTPUT = (
    REPO
    / "artifacts/development/independent_clarification_cut_b_r273.entry-path.preregistration.json"
)
MEASUREMENT_OUTPUT = (
    REPO / "artifacts/audit/independent_clarification_cut_b_entry_path_r274.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict[str, object]:
    required = (CORPUS, R270_PREREGISTRATION, R272_RESULT, CATALOGUE, RUNNER)
    if any(not path.is_file() for path in required):
        raise RuntimeError("R273 requires sealed R270/R272 inputs, R219, and R274")
    if MEASUREMENT_OUTPUT.exists():
        raise RuntimeError("R273 is invalid after an R274 entry-path measurement")
    r270 = json.loads(R270_PREREGISTRATION.read_text(encoding="utf-8"))
    r272 = json.loads(R272_RESULT.read_text(encoding="utf-8"))
    catalogue = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    if r270["identities"]["corpus_sha256"] != sha256(CORPUS):
        raise RuntimeError("R273 requires the sealed R270 corpus")
    if r272["identities"]["r270_corpus_sha256"] != sha256(CORPUS):
        raise RuntimeError("R273 requires the R272 result for this R270 corpus")
    if not r272["interpretation"]["population_can_exercise_model_path"]:
        raise RuntimeError("R273 requires R272 below its deterministic-effect limit")
    if r272["constraints"]["model_started"] or r272["constraints"]["effects_executed"]:
        raise RuntimeError("R273 requires the no-model, zero-effect R272 result")
    if len(catalogue["catalogue"]["capabilities"]) != 174:
        raise RuntimeError("R273 requires the complete R219 operation catalogue")
    return {
        "schema": "baxy.independent-clarification-cut-b.entry-path-r273-preregistration.v1",
        "authority": "sealed_before_model_start_and_before_r270_entry_path_measurement",
        "source": {
            "r270_rows": r270["population"]["rows"],
            "r270_corpus_sha256": sha256(CORPUS),
            "r270_preregistration_sha256": sha256(R270_PREREGISTRATION),
            "r272_result_sha256": sha256(R272_RESULT),
            "catalogue_sha256": sha256(CATALOGUE),
            "catalogue_operations": len(catalogue["catalogue"]["capabilities"]),
        },
        "scoring": {
            "runner": RUNNER.relative_to(REPO).as_posix(),
            "runner_sha256": sha256(RUNNER),
            "ordered_gates": [
                "resolve_explicit_clarification_intent",
                "resolve_explicit_effects",
            ],
            "outcomes": [
                "explicit_clarification",
                "explicit_effect",
                "model_decision_candidate_after_two_effect_gates",
            ],
            "model_decision_candidate_reach": "model_decision_candidate_after_two_effect_gates / rows",
            "model_decision_candidate_reach_limit": 0.5,
            "cuts": ["overall", "family", "language", "operation"],
            "request_texts_retained": False,
            "request_identifiers_retained": False,
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
        "next_step": "Commit R273 unchanged, freeze the worktree, then run R274 once before designing a full model-decision probe.",
        "identities": {"program_sha256": sha256(Path(__file__))},
    }


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"R273 preregistration exists: {OUTPUT}")
    OUTPUT.write_bytes(
        (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
