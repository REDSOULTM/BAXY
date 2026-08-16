"""Seal a BGE-M3 exemplar-family plus learned OOS-boundary GPU probe."""

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
RUNNER = REPO / "experiments/mind_router_spike/run_bge_m3_prototype_domain_r253.py"
OUTPUT = REPO / "artifacts/development/bge_m3_prototype_domain_r252.preregistration.json"
ENV_PYTHON = Path(r"D:\BAXYRuntime\experiments\r242-cuda\Scripts\python.exe")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict[str, object]:
    prior = json.loads(R250.read_text(encoding="utf-8"))
    source = json.loads(r251.OUTPUT.read_text(encoding="utf-8"))
    if prior["verdict"] != "rejected_development_family_or_oos_separation" or source["test_seal"]["members_decoded"] or not RUNNER.is_file() or not ENV_PYTHON.is_file():
        raise RuntimeError("R252 requires R250 rejection, intact CLINC test seal, runner and CUDA interpreter")
    return {
        "schema": "baxy.bge-m3-prototype-domain.r252-preregistration.v1",
        "authority": "sealed_after_family_score_rejections_before_model_import_or_training",
        "hypothesis": {"base": "BAAI/bge-m3@5617a9f61b028005a4858fdac845db406aefb181", "architecture": "frozen BGE-M3 query embeddings; authenticated family centroids built from R207 operation exemplars; separate class-balanced learned binary domain boundary", "difference_from_r236_r241_r246_r250": "retrieves against many observed operation exemplars and learns domain membership independently instead of maximum score against catalogue documents or a cross-encoder family head", "device": "isolated_cuda_bf16_development_environment"},
        "training": {"inside": "R207 positive development queries mapped to current typed families", "outside": "CLINC oos_train only", "oos_train_rows": 250, "base_frozen": True, "no_r228": True, "no_public_holdout": True},
        "development_evaluation": {"inside": 256, "outside": "CLINC oos_val 100", "inside_selection": "balanced SHA-256 selection disjoint from R236/R241/R243/R246/R250 public partitions", "acceptance": {"inside_rows_lost": 0, "inside_family_mismatches": 0, "outside_zero_candidates": 100}, "finite_embeddings_required": True},
        "constraints": {"r228_opened": False, "public_holdout_opened": False, "registered_runtime_modified": False, "providers_enabled": False, "effects_executed": 0, "opened_v9": False, "voice_stt_wake_exercised": False},
        "identities": {"bge_m3_r232_sha256": sha256(r232.OUTPUT), "clinc_r251_sha256": sha256(r251.OUTPUT), "r250_sha256": sha256(R250), "runner_sha256": sha256(RUNNER), "program_sha256": sha256(Path(__file__))},
    }


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing to overwrite preregistration: {OUTPUT}")
    OUTPUT.write_bytes((json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
