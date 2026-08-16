"""Freeze the corrected-runtime opening of situated Cut B R215."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
CORPUS = REPO / "artifacts/holdout/situated_cut_b_r215.jsonl"
SOURCE_PREREGISTRATION = (
    REPO / "artifacts/holdout/situated_cut_b_r215.preregistration.json"
)
RECOGNISER_REACH = (
    REPO / "artifacts/audit/situated_cut_b_r215_recogniser_reach_r216.json"
)
SNAPSHOT = REPO / "artifacts/development/current_core_catalog_snapshot_r219.json"
RUNNER = REPO / "experiments/mind_router_spike/run_situated_cut_b_model_path_r225.py"
BASE_RUNNER = (
    REPO / "experiments/mind_router_spike/run_situated_cut_b_model_path_r221.py"
)
SCORER = REPO / "experiments/mind_router_spike/score_situated_cut_b_model_path_r218.py"
RUNTIME_RESOLVER = REPO / "scripts/baxy_runtime_config.py"
OUTPUT = (
    REPO / "artifacts/holdout/situated_cut_b_r215.model_path_r224.preregistration.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _runtime_manifest() -> Path:
    from scripts.baxy_runtime_config import DEFAULT_RUNTIME_MANIFEST

    return DEFAULT_RUNTIME_MANIFEST


def build() -> dict[str, object]:
    rows = [line for line in CORPUS.read_text(encoding="utf-8").splitlines() if line]
    source = json.loads(SOURCE_PREREGISTRATION.read_text(encoding="utf-8"))
    reach = json.loads(RECOGNISER_REACH.read_text(encoding="utf-8"))
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    manifest = _runtime_manifest()
    if len(rows) != 93 or source["population"]["rows"] != 93:
        raise ValueError("r224_requires_unchanged_r215")
    if reach["recogniser"]["overall"]["reach"] >= 0.5:
        raise ValueError("r224_requires_non_majority_recogniser_reach")
    if snapshot["catalogue"]["operations"] != 174 or not manifest.is_file():
        raise ValueError("r224_requires_current_catalogue_and_registered_runtime")
    for path in (RUNNER, BASE_RUNNER, SCORER, RUNTIME_RESOLVER):
        if not path.is_file():
            raise ValueError("r224_requires_frozen_measurement_dependencies")
    return {
        "schema": "baxy.situated-cut-b.model-path.r224-preregistration.v1",
        "authority": "sealed_before_local_model_start_or_product_turn",
        "candidate": {
            "path": "unmodified_baxy_mind_turn_decide",
            "retrieval": "current_turn_evidence_and_planner_shortlist",
            "decision": "registered_local_qwen3_native_or_structured_turn_policy",
            "catalogue": "current_Core_must_match_R219_174_operation_snapshot",
            "runtime": "registered_manifest_and_corrected_per_file_STT_verifier",
            "selection_limit": 28,
        },
        "population": {
            "rows": 93,
            "families": 31,
            "languages": {"es": 31, "en": 31, "spanglish": 31},
            "recogniser_reach": reach["recogniser"]["overall"]["reach"],
        },
        "acceptance": {
            "retrieval_expected_complete_recall": 1.0,
            "raw_decision_exact_minimum": 0.95,
            "end_to_end_exact_or_useful_clarification_minimum": 0.95,
            "gpu_first_signal_p50_seconds_maximum": 1.0,
            "gpu_first_signal_p95_seconds_maximum": 2.0,
            "hard_zeros": [
                "unsolicited_effects",
                "unverified_successes",
                "fixed_visible_replies",
                "external_effects_executed",
            ],
            "diagnostic_cause_buckets": ["retrieval", "decision", "veto"],
        },
        "measurement": {
            "one_shot": True,
            "retry_allowed": False,
            "raw_decision_retained_before_veto": True,
            "turn_audit_retained": True,
            "visible_reply_audit_retained": True,
            "dispatch": "not_called",
        },
        "constraints": {
            "providers_enabled": False,
            "effects_executed": 0,
            "opened_v9": False,
            "v9_reserved": True,
            "voice_stt_wake_exercised": False,
        },
        "identities": {
            "corpus_sha256": sha256(CORPUS),
            "source_preregistration_sha256": sha256(SOURCE_PREREGISTRATION),
            "recogniser_reach_sha256": sha256(RECOGNISER_REACH),
            "current_core_snapshot_sha256": sha256(SNAPSHOT),
            "current_core_capabilities_sha256": snapshot["catalogue"][
                "capabilities_sha256"
            ],
            "runtime_manifest_sha256": sha256(manifest),
            "runtime_resolver_sha256": sha256(RUNTIME_RESOLVER),
            "runner_sha256": sha256(RUNNER),
            "base_runner_sha256": sha256(BASE_RUNNER),
            "scorer_sha256": sha256(SCORER),
            "program_sha256": sha256(Path(__file__)),
        },
    }


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing to overwrite preregistration: {OUTPUT}")
    OUTPUT.write_bytes(
        (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
