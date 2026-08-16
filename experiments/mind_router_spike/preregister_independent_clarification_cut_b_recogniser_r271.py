"""Seal the one-pass R272 recogniser scorer for the R270 clarification cut."""

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
CATALOGUE = REPO / "artifacts/development/current_core_catalog_snapshot_r219.json"
RUNNER = (
    REPO
    / "experiments/mind_router_spike/run_independent_clarification_cut_b_recogniser_r272.py"
)
OUTPUT = (
    REPO
    / "artifacts/development/independent_clarification_cut_b_r271.recogniser.preregistration.json"
)
MEASUREMENT_OUTPUT = (
    REPO / "artifacts/audit/independent_clarification_cut_b_recogniser_r272.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict[str, object]:
    required = (CORPUS, R270_PREREGISTRATION, CATALOGUE, RUNNER)
    if any(not path.is_file() for path in required):
        raise RuntimeError("R271 requires the sealed R270 inputs, R219, and R272 runner")
    if MEASUREMENT_OUTPUT.exists():
        raise RuntimeError("R271 is invalid after an R272 recogniser measurement")
    r270 = json.loads(R270_PREREGISTRATION.read_text(encoding="utf-8"))
    if r270["identities"]["corpus_sha256"] != sha256(CORPUS):
        raise RuntimeError("R271 requires the sealed R270 corpus hash")
    if r270["constraints"]["recogniser_measured"] is not False:
        raise RuntimeError("R271 requires R270 before recogniser measurement")
    if r270["identities"]["catalogue_sha256"] != sha256(CATALOGUE):
        raise RuntimeError("R271 requires the R219 catalogue sealed by R270")
    return {
        "schema": "baxy.independent-clarification-cut-b-recogniser-r271-preregistration.v1",
        "authority": "sealed_before_first_r270_recogniser_measurement",
        "source": {
            "r270_rows": r270["population"]["rows"],
            "r270_semantic_cases": r270["population"]["semantic_cases"],
            "r270_corpus_sha256": sha256(CORPUS),
            "r270_preregistration_sha256": sha256(R270_PREREGISTRATION),
            "catalogue_sha256": sha256(CATALOGUE),
        },
        "scoring": {
            "runner": RUNNER.relative_to(REPO).as_posix(),
            "runner_sha256": sha256(RUNNER),
            "recogniser": "baxy_mind.effect_intent.resolve_explicit_effects",
            "available_operations": "all_current_r219_catalogue_operation_names",
            "outcomes": [
                "resolved_any",
                "resolved_intended",
                "resolved_other",
                "unresolved",
            ],
            "recogniser_effect_reach": "resolved_any / rows",
            "recogniser_effect_reach_limit": 0.5,
            "cuts": ["overall", "family", "language", "intended_operation"],
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
        "next_step": "Commit this R271 scorer and preregistration unchanged, freeze the worktree, then invoke the R272 runner exactly once.",
        "identities": {"program_sha256": sha256(Path(__file__))},
    }


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"R271 preregistration exists: {OUTPUT}")
    OUTPUT.write_bytes(
        (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
