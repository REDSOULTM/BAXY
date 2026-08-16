"""Freeze the R241 CPU development runner before it imports the reranker."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from experiments.mind_router_spike import attest_bge_reranker_r238 as r238


R239 = REPO / "artifacts/development/bge_reranker_calibration_r239.preregistration.json"
R234 = REPO / "artifacts/audit/turn_evidence_restoration_r234.json"
CATALOG = REPO / "artifacts/development/current_core_catalog_snapshot_r219.json"
RUNNER = REPO / "experiments/mind_router_spike/run_bge_reranker_r241.py"
OUTPUT = REPO / "artifacts/development/bge_reranker_r240.preregistration.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict[str, object]:
    r239 = json.loads(R239.read_text(encoding="utf-8"))
    r234 = json.loads(R234.read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    if r239 != __import__(
        "experiments.mind_router_spike.preregister_bge_reranker_calibration_r239",
        fromlist=["build"],
    ).build():
        raise RuntimeError("R240 requires the sealed R239 calibration contract")
    if r238.build()["candidate"]["merkle_sha256"] != "50d52ffd408e81baf7d0aa55b1ecbd8be05d7f4091773f1b71833b852e3c4249":
        raise RuntimeError("R240 requires the attested reranker tree")
    if r234["runtime_corpus"]["sha256"] != "8abff5805a93615c6f5a655b9af5559063e34226cfc0db58c5547d97a70ee680":
        raise RuntimeError("R240 requires the restored development corpus")
    if catalog["catalogue"]["operations"] != 174 or not RUNNER.is_file():
        raise RuntimeError("R240 requires the frozen catalog and R241 runner")
    return {
        "schema": "baxy.bge-reranker.r240-preregistration.v1",
        "authority": "sealed_before_reranker_import_or_development_run",
        "candidate": {
            "model": "BAAI/bge-reranker-v2-m3@953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e",
            "device": "cuda_gpu_development_probe",
            "score": "sigmoid cross-encoder relevance query-to-typed-family-document",
            "document": "one deterministic typed document per catalogue family",
            "abstention": "zero candidates below nextafter below the minimum selected inside score",
        },
        "development_population": {
            "inside": 256,
            "outside": 256,
            "sources": ["PRESTO v1", "MASSIVE v1.1"],
            "selection": "deterministic SHA-256 ordering with one initial row per family",
            "r228_used": False,
            "public_holdout_used": False,
        },
        "acceptance": {
            "inside_rows_lost": 0,
            "outside_rows_with_zero_candidates": 256,
            "aggregate_scores_only": True,
            "runtime_integration": False,
            "latency_measurement": "reported as GPU development telemetry only; no product claim",
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
            "r239_sha256": sha256(R239),
            "r238_sha256": sha256(r238.OUTPUT),
            "r234_sha256": sha256(R234),
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
