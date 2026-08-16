"""Seal the feasible direct abstain CUDA successor before importing its model."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from experiments.mind_router_spike import attest_direct_abstain_r248 as r248
from experiments.mind_router_spike import preregister_direct_abstain_classifier_r247 as r247


RUNNER = REPO / "experiments/mind_router_spike/run_direct_abstain_classifier_r250.py"
OUTPUT = REPO / "artifacts/development/direct_abstain_classifier_r249.preregistration.json"
ENV_PYTHON = Path(r"D:\BAXYRuntime\experiments\r242-cuda\Scripts\python.exe")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict[str, object]:
    rejection = json.loads(r248.OUTPUT.read_text(encoding="utf-8"))
    if rejection["verdict"] != "rejected_preexecution_insufficient_fresh_oos_for_registered_balance" or not RUNNER.is_file() or not ENV_PYTHON.is_file():
        raise RuntimeError("R249 requires the completed R248 pre-execution rejection and isolated CUDA interpreter")
    return {
        "schema": "baxy.direct-abstain-classifier.r249-preregistration.v1",
        "authority": "sealed_after_r248_preexecution_rejection_before_model_import_or_training",
        "hypothesis": {
            "base": "BAAI/bge-reranker-v2-m3@953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e",
            "architecture": "frozen multilingual encoder with a float32 query-only 32-way classifier: one authenticated class per typed family plus an explicit abstain class",
            "difference_from_r246": "a direct mutually exclusive abstain class replaces R246's maximum independent family relevance score; it is not a threshold adjustment or rerun",
            "difference_from_r247": "uses all 1,479 demonstrably fresh OOS rows available after protected evaluations and inverse-frequency loss weights rather than an unavailable one-to-one OOS sample",
            "device": "isolated_cuda_bf16_development_environment",
        },
        "training": {"sources": ["R207 positive development queries labelled by current typed family", "all fresh public PRESTO/MASSIVE OOS queries labelled explicit abstain"], "base_frozen": True, "inverse_frequency_class_weighted_loss": True, "no_r228": True, "no_public_holdout": True},
        "development_evaluation": {"inside": 256, "outside": 256, "selection": "SHA-256 ordered public rows disjoint from every R236/R241/R243/R246 train or evaluation source id", "finite_scores_required": True, "acceptance": {"inside_rows_lost": 0, "inside_family_mismatches": 0, "outside_zero_candidates": 256}},
        "constraints": {"r228_opened": False, "public_holdout_opened": False, "registered_runtime_modified": False, "providers_enabled": False, "effects_executed": 0, "opened_v9": False, "voice_stt_wake_exercised": False},
        "identities": {"r247_sha256": sha256(r247.OUTPUT), "r248_sha256": sha256(r248.OUTPUT), "runner_sha256": sha256(RUNNER), "program_sha256": sha256(Path(__file__))},
    }


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing to overwrite preregistration: {OUTPUT}")
    OUTPUT.write_bytes((json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
