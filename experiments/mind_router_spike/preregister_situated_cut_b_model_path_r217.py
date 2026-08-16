"""Freeze the unmodified local model-path opening for situated Cut B R215."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
CORPUS = REPO / "artifacts/holdout/situated_cut_b_r215.jsonl"
SOURCE_PREREGISTRATION = (
    REPO / "artifacts/holdout/situated_cut_b_r215.preregistration.json"
)
RECOGNISER_REACH = (
    REPO / "artifacts/audit/situated_cut_b_r215_recogniser_reach_r216.json"
)
CATALOG = REPO / "artifacts/development/catalog_vocabulary_snapshot.json"
RUNNER = REPO / "experiments/mind_router_spike/run_situated_cut_b_model_path_r218.py"
SCORER = REPO / "experiments/mind_router_spike/score_situated_cut_b_model_path_r218.py"
OUTPUT = (
    REPO / "artifacts/holdout/situated_cut_b_r215.model_path_r217.preregistration.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def build() -> dict[str, Any]:
    rows = _rows(CORPUS)
    source = json.loads(SOURCE_PREREGISTRATION.read_text(encoding="utf-8"))
    reach = json.loads(RECOGNISER_REACH.read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    if len(rows) != 93 or source["population"]["rows"] != len(rows):
        raise ValueError("r217_requires_the_unchanged_93_row_r215_population")
    if reach["recogniser"]["overall"]["reach"] >= 0.5:
        raise ValueError("r217_requires_non_majority_recogniser_reach")
    if len(catalog["capabilities"]) != 169:
        raise ValueError("r217_requires_the_169_operation_authenticated_snapshot")
    if not RUNNER.is_file() or not SCORER.is_file():
        raise ValueError("r217_requires_frozen_r218_instrument_and_scorer")
    return {
        "schema": "baxy.situated-cut-b.model-path.r217-preregistration.v1",
        "authority": "sealed_before_local_model_start_or_product_turn",
        "candidate": {
            "path": "unmodified_baxy_mind_turn_decide",
            "retrieval": "current_turn_evidence_and_planner_shortlist",
            "decision": "registered_local_qwen3_native_or_structured_turn_policy",
            "selection_limit": 28,
            "runtime": "registered_local_runtime_only",
            "catalogue": "current_core_catalog_must_match_169_operation_snapshot",
        },
        "population": {
            "rows": len(rows),
            "families": 31,
            "languages": {"es": 31, "en": 31, "spanglish": 31},
            "source": "situated_cut_b_r215_unchanged",
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
            "catalog_snapshot_sha256": sha256(CATALOG),
            "runner_sha256": sha256(RUNNER),
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
