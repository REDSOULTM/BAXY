"""Seal the R207-split BGE-M3 prototype/domain probe before model import."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from experiments.mind_router_spike import attest_bge_m3_acquisition_r232 as r232
from experiments.mind_router_spike import attest_clinc_oos_development_r251 as r251


R250 = REPO / "artifacts/development/direct_abstain_classifier_r250.json"
R207 = REPO / "artifacts/development/r207_cross_encoder_pairs.jsonl"
CATALOG = REPO / "artifacts/development/current_core_catalog_snapshot_r219.json"
RUNNER = REPO / "experiments/mind_router_spike/run_bge_m3_r207_prototype_domain_r255.py"
OUTPUT = REPO / "artifacts/development/bge_m3_r207_prototype_domain_r254.preregistration.json"
ENV_PYTHON = Path(r"D:\BAXYRuntime\experiments\r242-cuda\Scripts\python.exe")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict[str, object]:
    prior = json.loads(R250.read_text(encoding="utf-8"))
    clinc = json.loads(r251.OUTPUT.read_text(encoding="utf-8"))
    if (
        prior["verdict"] != "rejected_development_family_or_oos_separation"
        or clinc["test_seal"]["members_decoded"]
        or not R207.is_file()
        or not CATALOG.is_file()
        or not RUNNER.is_file()
        or not ENV_PYTHON.is_file()
    ):
        raise RuntimeError("R254 requires R250 rejection, R207/catalogue, CLINC test seal, runner and CUDA interpreter")
    return {
        "schema": "baxy.bge-m3-r207-prototype-domain.r254-preregistration.v1",
        "authority": "sealed_before_bge_m3_import_or_cuda_execution",
        "hypothesis": {
            "base": "BAAI/bge-m3@5617a9f61b028005a4858fdac845db406aefb181",
            "architecture": "frozen BGE-M3 query embeddings, one normalized R207 prototype centroid per typed family, and a separately trained class-balanced binary domain head",
            "difference_from_r236_r241_r243_r246_r250_r253": "uses a strict query-disjoint R207 train/evaluation split for all 31 families rather than any reused PRESTO/MASSIVE partition, catalogue-document maximum, cross-encoder family head, or the R253-infeasible source selection",
            "device": "isolated_cuda_bf16_development_environment",
        },
        "selection": {
            "inside": "deduplicate R207 positive query/family pairs; reserve SHA-256 first one per family then SHA-256 remainder to exactly 256 evaluation queries; every remaining normalized query is prototype/domain training only",
            "overlap_rule": "no normalized query may occur in both prototype training and inside evaluation, even under a different operation label",
            "families_required": 31,
        },
        "training": {
            "inside": "R207 positive queries from the training side of the split",
            "outside": "CLINC oos_train only (250 rows)",
            "base_frozen": True,
            "domain_loss": "binary cross entropy with positive class weight calculated from frozen split counts",
            "no_r228": True,
            "no_public_holdout": True,
        },
        "development_evaluation": {
            "inside": 256,
            "outside": "CLINC oos_val only (100 rows)",
            "acceptance": {
                "inside_rows_lost": 0,
                "inside_family_mismatches": 0,
                "outside_zero_candidates": 100,
            },
            "not_a_blind_or_runtime_measurement": True,
        },
        "constraints": {
            "r228_opened": False,
            "public_holdout_opened": False,
            "registered_runtime_modified": False,
            "providers_enabled": False,
            "effects_executed": 0,
            "opened_v9": False,
            "voice_stt_wake_exercised": False,
        },
        "identities": {
            "bge_m3_r232_sha256": sha256(r232.OUTPUT),
            "clinc_r251_sha256": sha256(r251.OUTPUT),
            "r250_sha256": sha256(R250),
            "r207_sha256": sha256(R207),
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
