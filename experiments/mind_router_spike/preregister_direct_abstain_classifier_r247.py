"""Seal the direct typed-family plus abstain CUDA probe before it runs."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from experiments.mind_router_spike import preregister_head_only_reranker_domain_r245 as r245


R246 = REPO / "artifacts/development/head_only_reranker_domain_r246.json"
RUNNER = REPO / "experiments/mind_router_spike/run_direct_abstain_classifier_r248.py"
OUTPUT = REPO / "artifacts/development/direct_abstain_classifier_r247.preregistration.json"
ENV_PYTHON = Path(r"D:\BAXYRuntime\experiments\r242-cuda\Scripts\python.exe")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict[str, object]:
    prior = json.loads(R246.read_text(encoding="utf-8"))
    if prior["verdict"] != "rejected_development_oos_separation" or not RUNNER.is_file() or not ENV_PYTHON.is_file():
        raise RuntimeError("R247 requires the completed R246 rejection and isolated CUDA interpreter")
    return {
        "schema": "baxy.direct-abstain-classifier.r247-preregistration.v1",
        "authority": "sealed_after_r246_rejection_before_model_import_or_training",
        "hypothesis": {
            "base": "BAAI/bge-reranker-v2-m3@953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e",
            "architecture": "frozen multilingual encoder with a float32 query-only 32-way classifier: one authenticated class per typed family plus an explicit abstain class",
            "difference_from_r246": "a direct mutually exclusive abstain class replaces R246's maximum independent family relevance score; it is not a threshold adjustment or rerun",
            "device": "isolated_cuda_bf16_development_environment",
        },
        "training": {
            "sources": ["R207 positive development queries labelled by current typed family", "fresh public PRESTO/MASSIVE OOS queries labelled explicit abstain"],
            "base_frozen": True,
            "class_balanced_loss": True,
            "no_r228": True,
            "no_public_holdout": True,
        },
        "development_evaluation": {
            "inside": 256,
            "outside": 256,
            "selection": "SHA-256 ordered public rows disjoint from every R236/R241/R243/R246 train or evaluation source id",
            "finite_scores_required": True,
            "acceptance": {"inside_rows_lost": 0, "inside_family_mismatches": 0, "outside_zero_candidates": 256},
        },
        "constraints": {"r228_opened": False, "public_holdout_opened": False, "registered_runtime_modified": False, "providers_enabled": False, "effects_executed": 0, "opened_v9": False, "voice_stt_wake_exercised": False},
        "identities": {"r245_sha256": sha256(r245.OUTPUT), "r246_sha256": sha256(R246), "runner_sha256": sha256(RUNNER), "program_sha256": sha256(Path(__file__))},
    }


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing to overwrite preregistration: {OUTPUT}")
    OUTPUT.write_bytes((json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
