"""Seal a development-only semantic abstention probe before loading BGE-M3."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from experiments.mind_router_spike import attest_bge_m3_acquisition_r232 as r232


R234 = REPO / "artifacts/audit/turn_evidence_restoration_r234.json"
CATALOG = REPO / "artifacts/development/current_core_catalog_snapshot_r219.json"
RUNNER = REPO / "experiments/mind_router_spike/run_bge_m3_semantic_abstention_r236.py"
OUTPUT = REPO / "artifacts/development/bge_m3_semantic_abstention_r235.preregistration.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict[str, object]:
    acquisition = json.loads(r232.OUTPUT.read_text(encoding="utf-8"))
    restoration = json.loads(R234.read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    if acquisition["candidate"]["content_merkle_sha256"] != "c6e5180e517f5ebc90d7a239339f24c449e29511c4acbc7017692f41c11aa142":
        raise RuntimeError("R235 requires the attested BGE-M3 candidate")
    if restoration["runtime_corpus"]["sha256"] != "8abff5805a93615c6f5a655b9af5559063e34226cfc0db58c5547d97a70ee680":
        raise RuntimeError("R235 requires the restored canonical development corpus")
    if catalog["catalogue"]["operations"] != 174 or not RUNNER.is_file():
        raise RuntimeError("R235 requires the frozen catalog and runner")
    return {
        "schema": "baxy.bge-m3-semantic-abstention.r235-preregistration.v1",
        "authority": "development_only_sealed_before_model_import_or_r228_opening",
        "candidate": {
            "model_id": "BAAI/bge-m3",
            "revision": "5617a9f61b028005a4858fdac845db406aefb181",
            "device": "cpu_only_development_probe",
            "domain_documents": "one deterministic document per catalogue family from name, description, argumentsSchema and risk",
            "score": "maximum normalized dense cosine over family documents",
            "abstention": "zero operation candidates when score is below the independently selected threshold",
            "threshold_rule": "next representable value below the minimum selected public in-catalog score",
        },
        "development_population": {
            "source": "restored canonical public PRESTO/MASSIVE rows only",
            "inside_selection": "deterministic balanced family sample of 256 rows",
            "outside_selection": "deterministic SHA-256 ordered sample of 256 rows with no product family",
            "r228_used": False,
            "public_holdout_used": False,
        },
        "acceptance": {
            "selected_inside_rows_lost": 0,
            "oos_rows_with_zero_candidates_reported": True,
            "raw_scores_retained_as_aggregate_only": True,
            "no_runtime_integration": True,
        },
        "constraints": {
            "r228_opened": False,
            "public_holdout_opened": False,
            "providers_enabled": False,
            "effects_executed": 0,
            "opened_v9": False,
            "voice_stt_wake_exercised": False,
        },
        "identities": {
            "bge_acquisition_sha256": sha256(r232.OUTPUT),
            "turn_evidence_restoration_sha256": sha256(R234),
            "catalog_sha256": sha256(CATALOG),
            "runner_sha256": sha256(RUNNER),
            "program_sha256": sha256(Path(__file__)),
        },
    }


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing to overwrite preregistration: {OUTPUT}")
    OUTPUT.write_bytes((json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
