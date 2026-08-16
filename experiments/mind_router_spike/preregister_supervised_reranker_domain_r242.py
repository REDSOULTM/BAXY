"""Seal supervised domain-abstention training before the reranker is loaded."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from experiments.mind_router_spike import attest_bge_reranker_r238 as r238


R234 = REPO / "artifacts/audit/turn_evidence_restoration_r234.json"
R207 = REPO / "artifacts/development/r207_cross_encoder_pairs.jsonl"
CATALOG = REPO / "artifacts/development/current_core_catalog_snapshot_r219.json"
R228 = REPO / "artifacts/holdout/situated_cut_b_r228.jsonl"
RUNNER = REPO / "experiments/mind_router_spike/run_supervised_reranker_domain_r243.py"
OUTPUT = REPO / "artifacts/development/supervised_reranker_domain_r242.preregistration.json"
ENV_PYTHON = Path(r"D:\BAXYRuntime\experiments\r242-cuda\Scripts\python.exe")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict[str, object]:
    restoration = json.loads(R234.read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    if r238.build()["candidate"]["merkle_sha256"] != "50d52ffd408e81baf7d0aa55b1ecbd8be05d7f4091773f1b71833b852e3c4249":
        raise RuntimeError("R242 requires the attested multilingual reranker")
    if restoration["runtime_corpus"]["sha256"] != "8abff5805a93615c6f5a655b9af5559063e34226cfc0db58c5547d97a70ee680":
        raise RuntimeError("R242 requires the restored public development corpus")
    if catalog["catalogue"]["operations"] != 174 or not RUNNER.is_file():
        raise RuntimeError("R242 requires the current typed catalog and R243 runner")
    if not ENV_PYTHON.is_file():
        raise RuntimeError("R242 requires the isolated CUDA experiment interpreter")
    return {
        "schema": "baxy.supervised-reranker-domain.r242-preregistration.v1",
        "authority": "sealed_before_model_import_training_or_r228_opening",
        "hypothesis": {
            "model": "BAAI/bge-reranker-v2-m3@953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e",
            "architecture": "supervised query-to-typed-family-document cross-encoder",
            "difference_from_r241": "learns explicit positive family pairs and real OOS negative query-family pairs; it is not a threshold adjustment to the zero-shot score",
            "device": "isolated_cuda_development_environment",
            "optimizer": "AdamW full-model fine tuning, one epoch, fixed seed",
        },
        "training": {
            "positive_source": "R207 development pairs, mapped to current typed family documents",
            "negative_source": "deterministic R207 negatives plus public PRESTO/MASSIVE train rows with no BAXY family paired against every family document",
            "no_r228": True,
            "no_public_holdout": True,
        },
        "development_evaluation": {
            "inside": 256,
            "outside": 256,
            "selection": "SHA-256 ordered rows disjoint from the R236/R241 256+256 selections and from training OOS rows",
            "threshold": "nextafter below minimum fresh inside maximum score; OOS excluded from selection",
            "acceptance": {"inside_rows_lost": 0, "outside_zero_candidates": 256},
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
            "r238_sha256": sha256(r238.OUTPUT),
            "r234_sha256": sha256(R234),
            "r207_sha256": sha256(R207),
            "catalog_sha256": sha256(CATALOG),
            "r228_sha256": sha256(R228),
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
