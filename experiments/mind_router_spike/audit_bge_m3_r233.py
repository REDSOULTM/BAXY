"""Reject an always-top-k retrieval design before it can consume R228."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from experiments.mind_router_spike import preregister_bge_m3_retrieval_r231 as r231


ATTESTATION = REPO / "artifacts/audit/bge_m3_acquisition_r232.json"
OUTPUT = REPO / "artifacts/audit/bge_m3_r233_structural_abstention_rejection.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict[str, Any]:
    preregistration = json.loads(r231.OUTPUT.read_text(encoding="utf-8"))
    attestation = json.loads(ATTESTATION.read_text(encoding="utf-8"))
    if preregistration != r231.build():
        raise RuntimeError("R231 preregistration identity changed")
    ranking = preregistration["candidate"]["ranking"]
    top_k = ranking.get("top_k")
    threshold = ranking.get("threshold")
    if not isinstance(top_k, int) or top_k < 1:
        raise RuntimeError("R233 requires a positive fixed top-k candidate")
    if threshold != "none; ranking remains a non-authoritative shortlist":
        raise RuntimeError("R233 only audits the sealed threshold-free R231 design")
    if attestation["constraints"]["model_imported"] or attestation["constraints"]["model_started"]:
        raise RuntimeError("R233 requires the candidate to remain unstarted")
    catalog_operations = 174
    return {
        "schema": "baxy.bge-m3.r233-structural-abstention-audit.v1",
        "authority": "deductive_pre_inference_rejection_of_a_sealed_candidate",
        "candidate": {
            "model_id": r231.MODEL_ID,
            "revision": r231.MODEL_REVISION,
            "retrieval": "dense_normalized_embedding_cosine",
            "top_k": top_k,
            "threshold": threshold,
            "catalog_operations": catalog_operations,
        },
        "deduction": {
            "for_every_query": "fixed top-k ranking returns min(top_k, catalog_operations) candidates",
            "candidates_per_query": min(top_k, catalog_operations),
            "oos_requirement": "zero candidates reach the decision",
            "contradiction": True,
            "reason": (
                "A threshold-free ranking has no abstention state; it therefore cannot "
                "produce the required zero-candidate OOS decision input."
            ),
        },
        "verdict": "rejected_before_model_import_or_r228_opening",
        "required_for_any_successor": [
            "independently calibrated semantic abstention mechanism",
            "fresh OOS population disjoint from consumed controls",
            "preregistered retrieval_decision_veto_visible_text runner",
        ],
        "constraints": {
            "model_imported": False,
            "model_started": False,
            "r228_opened": False,
            "registered_runtime_modified": False,
            "providers_enabled": False,
            "effects_executed": 0,
            "opened_v9": False,
            "voice_stt_wake_exercised": False,
        },
        "identities": {
            "r231_preregistration_sha256": sha256(r231.OUTPUT),
            "r232_attestation_sha256": sha256(ATTESTATION),
            "program_sha256": sha256(Path(__file__)),
        },
    }


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing to overwrite audit: {OUTPUT}")
    OUTPUT.write_bytes((json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
