"""Freeze a no-dispatch registered-runtime model-path probe for R270."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
CORPUS = REPO / "artifacts/development/independent_clarification_cut_b_r270.jsonl"
R270_PREREGISTRATION = (
    REPO
    / "artifacts/development/independent_clarification_cut_b_r270.preregistration.json"
)
R274_RESULT = (
    REPO / "artifacts/audit/independent_clarification_cut_b_entry_path_r274.json"
)
SNAPSHOT = REPO / "artifacts/development/current_core_catalog_snapshot_r219.json"
RUNTIME_MANIFEST = Path(os.environ["LOCALAPPDATA"]) / "BAXYRuntime/mind-runtime-v1.json"
RUNNER = (
    REPO
    / "experiments/mind_router_spike/run_independent_clarification_cut_b_model_path_r276.py"
)
SCORER = (
    REPO
    / "experiments/mind_router_spike/score_independent_clarification_cut_b_model_path_r276.py"
)
RUNTIME_RESOLVER = REPO / "scripts/baxy_runtime_config.py"
MEASUREMENT_HELPERS = REPO / "scripts/measure_mind_budget.py"
OUTPUT = (
    REPO
    / "artifacts/development/independent_clarification_cut_b_r275.model-path.preregistration.json"
)
MEASUREMENT_OUTPUT = (
    REPO / "artifacts/audit/independent_clarification_cut_b_model_path_r276.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict[str, object]:
    required = (
        CORPUS,
        R270_PREREGISTRATION,
        R274_RESULT,
        SNAPSHOT,
        RUNTIME_MANIFEST,
        RUNNER,
        SCORER,
        RUNTIME_RESOLVER,
        MEASUREMENT_HELPERS,
    )
    if any(not path.is_file() for path in required):
        raise RuntimeError("R275 requires sealed R270/R274 inputs, runtime, and R276 code")
    if MEASUREMENT_OUTPUT.exists():
        raise RuntimeError("R275 is invalid after an R276 model-path measurement")
    r270 = json.loads(R270_PREREGISTRATION.read_text(encoding="utf-8"))
    r274 = json.loads(R274_RESULT.read_text(encoding="utf-8"))
    runtime = json.loads(RUNTIME_MANIFEST.read_text(encoding="utf-8"))
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    if r270["identities"]["corpus_sha256"] != sha256(CORPUS):
        raise RuntimeError("R275 requires the sealed R270 corpus")
    if not r274["interpretation"]["population_can_exercise_raw_model_decision"]:
        raise RuntimeError("R275 requires R274 model-decision reach")
    if r274["constraints"]["model_started"] or r274["constraints"]["effects_executed"]:
        raise RuntimeError("R275 requires the zero-effect, pre-model R274 result")
    if (
        runtime.get("schema") != "baxy-mind-runtime-v1"
        or runtime.get("wake_on_start") is not False
        or len(snapshot["catalogue"]["capabilities"]) != 174
    ):
        raise RuntimeError("R275 requires the registered no-wake runtime and R219")
    return {
        "schema": "baxy.independent-clarification-cut-b.model-path-r275-preregistration.v1",
        "authority": "sealed_before_registered_local_model_start_or_product_turn",
        "candidate": {
            "path": "unmodified_registered_baxy_mind_turn_decide",
            "runtime": "registered_local_manifest_gpu_profile_no_wake",
            "catalogue": "current_Core_must_match_R219_174_operation_snapshot",
            "dispatch": "not_called",
            "population": "R270 rows that remain after the two R274 deterministic effect gates",
        },
        "source": {
            "all_r270_rows": r270["population"]["rows"],
            "model_decision_candidate_rows": r274["observed"]["model_decision_candidate_after_two_effect_gates"],
            "r270_corpus_sha256": sha256(CORPUS),
            "r270_preregistration_sha256": sha256(R270_PREREGISTRATION),
            "r274_result_sha256": sha256(R274_RESULT),
            "snapshot_sha256": sha256(SNAPSHOT),
            "runtime_manifest_sha256": sha256(RUNTIME_MANIFEST),
        },
        "acceptance": {
            "retrieval_expected_complete_recall": 1.0,
            "raw_decision_effect_free_minimum": 0.95,
            "natural_missing_fact_clarification_minimum": 0.95,
            "gpu_first_signal_p50_seconds_maximum": 1.0,
            "gpu_first_signal_p95_seconds_maximum": 2.0,
            "hard_zeros": [
                "unsolicited_effects",
                "unverified_successes",
                "fixed_visible_replies",
                "external_effects_executed",
            ],
            "diagnostic_cause_buckets": ["retrieval", "decision", "veto_or_presentation"],
        },
        "measurement": {
            "one_shot": True,
            "retry_allowed": False,
            "raw_decision_retained_before_veto": True,
            "turn_audit_retained": True,
            "visible_reply_audit_retained": True,
            "manual_visible_text_review_required": True,
            "dispatch": "not_called",
        },
        "constraints": {
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
        "next_step": "Commit R275 unchanged, freeze the worktree, then invoke the R276 no-dispatch runner exactly once and manually audit its visible text.",
        "identities": {
            "corpus_sha256": sha256(CORPUS),
            "r270_preregistration_sha256": sha256(R270_PREREGISTRATION),
            "r274_result_sha256": sha256(R274_RESULT),
            "snapshot_sha256": sha256(SNAPSHOT),
            "runtime_manifest_sha256": sha256(RUNTIME_MANIFEST),
            "runtime_resolver_sha256": sha256(RUNTIME_RESOLVER),
            "measurement_helpers_sha256": sha256(MEASUREMENT_HELPERS),
            "runner_sha256": sha256(RUNNER),
            "scorer_sha256": sha256(SCORER),
            "program_sha256": sha256(Path(__file__)),
        },
    }


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"R275 preregistration exists: {OUTPUT}")
    OUTPUT.write_bytes(
        (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
