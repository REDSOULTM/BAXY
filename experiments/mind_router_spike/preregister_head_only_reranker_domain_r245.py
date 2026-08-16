"""Seal a numerically stable, fresh-split supervised reranker probe."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from experiments.mind_router_spike import attest_bge_reranker_r238 as r238


R242 = REPO / "artifacts/development/supervised_reranker_domain_r242.preregistration.json"
R244 = REPO / "artifacts/audit/supervised_reranker_domain_r243_nonfinite_rejection_r244.json"
RUNNER = REPO / "experiments/mind_router_spike/run_head_only_reranker_domain_r246.py"
OUTPUT = REPO / "artifacts/development/head_only_reranker_domain_r245.preregistration.json"
ENV_PYTHON = Path(r"D:\BAXYRuntime\experiments\r242-cuda\Scripts\python.exe")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict[str, object]:
    prior = json.loads(R244.read_text(encoding="utf-8"))
    if prior["verdict"] != "rejected_invalid_nonfinite_training" or not RUNNER.is_file() or not ENV_PYTHON.is_file():
        raise RuntimeError("R245 requires the completed R244 rejection and isolated CUDA interpreter")
    return {
        "schema": "baxy.head-only-reranker-domain.r245-preregistration.v1",
        "authority": "sealed_after_r243_rejection_before_model_import_or_training",
        "hypothesis": {
            "base": "BAAI/bge-reranker-v2-m3@953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e",
            "architecture": "frozen multilingual encoder with trainable sequence-classification head over query-to-typed-family-document pairs",
            "difference_from_r243": "frozen base, BF16 autocast, float32 classifier/optimizer and finite-value gate; it does not rerun R243 or reuse its evaluation partition",
            "device": "isolated_cuda_development_environment",
        },
        "training": {"sources": ["R207 development pairs", "fresh public PRESTO/MASSIVE OOS negatives"], "no_r228": True, "no_public_holdout": True},
        "development_evaluation": {"inside": 256, "outside": 256, "selection": "SHA-256 ordered rows disjoint from every R236/R241/R243 train or evaluation source id", "finite_scores_required": True, "acceptance": {"inside_rows_lost": 0, "outside_zero_candidates": 256}},
        "constraints": {"r228_opened": False, "public_holdout_opened": False, "registered_runtime_modified": False, "providers_enabled": False, "effects_executed": 0, "opened_v9": False, "voice_stt_wake_exercised": False},
        "identities": {"r238_sha256": sha256(r238.OUTPUT), "r242_sha256": sha256(R242), "r244_sha256": sha256(R244), "runner_sha256": sha256(RUNNER), "program_sha256": sha256(Path(__file__))},
    }


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing to overwrite preregistration: {OUTPUT}")
    OUTPUT.write_bytes((json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
