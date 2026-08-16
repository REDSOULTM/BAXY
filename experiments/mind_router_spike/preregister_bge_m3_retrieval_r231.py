"""Freeze the isolated BGE-M3 retrieval candidate before acquiring its weights.

This is deliberately an acquisition preregistration, not a measurement.  It
does not import a model package or load a model, and leaves the registered Mind
runtime untouched.  A later runner must separately freeze its OOS population,
raw decision, veto and visible-text instrumentation before it may open R228.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.baxy_runtime_config import DEFAULT_RUNTIME_MANIFEST  # noqa: E402


CORPUS = REPO / "artifacts/holdout/situated_cut_b_r228.jsonl"
SOURCE_PREREGISTRATION = REPO / "artifacts/holdout/situated_cut_b_r228.preregistration.json"
RECOGNISER_REACH = REPO / "artifacts/audit/situated_cut_b_r228_recogniser_reach_r229.json"
CATALOG = REPO / "artifacts/development/current_core_catalog_snapshot_r219.json"
OUTPUT = REPO / "artifacts/holdout/situated_cut_b_r228.bge_m3_r231.preregistration.json"

MODEL_ID = "BAAI/bge-m3"
MODEL_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
CANDIDATE_ROOT = Path(r"D:\BAXYRuntime\candidates\BAAI--bge-m3")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict[str, object]:
    rows = [line for line in CORPUS.read_text(encoding="utf-8").splitlines() if line]
    source = json.loads(SOURCE_PREREGISTRATION.read_text(encoding="utf-8"))
    reach = json.loads(RECOGNISER_REACH.read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    if len(rows) != 93 or source["population"]["rows"] != 93:
        raise ValueError("r231_requires_unchanged_r228")
    if reach["recogniser"]["overall"]["reach"] >= 0.5:
        raise ValueError("r231_requires_non_majority_recogniser_reach")
    if catalog["catalogue"]["operations"] != 174:
        raise ValueError("r231_requires_r219_catalogue_snapshot")
    if not DEFAULT_RUNTIME_MANIFEST.is_file():
        raise ValueError("r231_requires_registered_runtime_identity")
    return {
        "schema": "baxy.situated-cut-b.bge-m3.r231-acquisition-preregistration.v1",
        "authority": "sealed_before_external_weight_acquisition_or_model_start",
        "candidate": {
            "model_id": MODEL_ID,
            "revision": MODEL_REVISION,
            "storage": str(CANDIDATE_ROOT),
            "runtime_integration": "none",
            "retrieval_hypothesis": (
                "dense multilingual semantic ranking of the frozen typed catalogue "
                "documents; no lexical gate, operation authority, provider or dispatch"
            ),
            "catalogue_document_fields": [
                "name",
                "description",
                "argumentsSchema",
                "risk",
            ],
            "ranking": {
                "representation": "dense_normalized_embedding_cosine",
                "top_k": 8,
                "threshold": "none; ranking remains a non-authoritative shortlist",
            },
        },
        "population": {
            "r228_rows": 93,
            "families": 31,
            "languages": {"es": 31, "en": 31, "spanglish": 31},
            "recogniser_reach": reach["recogniser"]["overall"]["reach"],
        },
        "required_before_opening_r228": {
            "fresh_oos_population": True,
            "runner_preregistration": True,
            "raw_retrieval_retained": True,
            "raw_decision_before_veto_retained": True,
            "visible_text_audit_retained": True,
            "hard_zeros": [
                "unsolicited_effects",
                "unverified_successes",
                "fixed_visible_replies",
                "external_effects_executed",
            ],
        },
        "constraints": {
            "model_started": False,
            "registered_runtime_modified": False,
            "providers_enabled": False,
            "effects_executed": 0,
            "opened_v9": False,
            "v9_reserved": True,
            "voice_stt_wake_exercised": False,
        },
        "identities": {
            "r228_corpus_sha256": sha256(CORPUS),
            "r228_preregistration_sha256": sha256(SOURCE_PREREGISTRATION),
            "r229_reach_sha256": sha256(RECOGNISER_REACH),
            "catalog_snapshot_sha256": sha256(CATALOG),
            "catalog_capabilities_sha256": catalog["catalogue"]["capabilities_sha256"],
            "registered_runtime_manifest_sha256": sha256(DEFAULT_RUNTIME_MANIFEST),
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
