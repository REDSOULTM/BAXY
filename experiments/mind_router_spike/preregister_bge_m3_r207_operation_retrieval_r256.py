"""Seal a query-disjoint, operation-level BGE-M3 retrieval measurement."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from experiments.mind_router_spike import attest_bge_m3_acquisition_r232 as r232


R255 = REPO / "artifacts/development/bge_m3_r207_prototype_domain_r255.json"
R207 = REPO / "artifacts/development/r207_cross_encoder_pairs.jsonl"
CATALOG = REPO / "artifacts/development/current_core_catalog_snapshot_r219.json"
RUNNER = REPO / "experiments/mind_router_spike/run_bge_m3_r207_operation_retrieval_r257.py"
OUTPUT = REPO / "artifacts/development/bge_m3_r207_operation_retrieval_r256.preregistration.json"
ENV_PYTHON = Path(r"D:\BAXYRuntime\experiments\r242-cuda\Scripts\python.exe")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict[str, object]:
    prior = json.loads(R255.read_text(encoding="utf-8"))
    if (
        prior["verdict"] != "rejected_development_family_or_oos_separation"
        or not R207.is_file()
        or not CATALOG.is_file()
        or not RUNNER.is_file()
        or not ENV_PYTHON.is_file()
    ):
        raise RuntimeError("R256 requires the published R255 rejection, R207/catalogue, runner and CUDA interpreter")
    return {
        "schema": "baxy.bge-m3-r207-operation-retrieval.r256-preregistration.v1",
        "authority": "sealed_before_bge_m3_import_or_cuda_execution",
        "hypothesis": {
            "base": "BAAI/bge-m3@5617a9f61b028005a4858fdac845db406aefb181",
            "architecture": "frozen BGE-M3 dense query embeddings; each typed catalogue operation is ranked by its maximum cosine against its query-disjoint positive R207 exemplars",
            "difference_from_r255": "measures raw operation retrieval only: no family centroids, domain boundary, OOS gate, classifier head, threshold, decision, veto or runtime integration",
            "device": "isolated_cuda_bf16_development_environment",
        },
        "selection": {
            "source": "R207 positive rows whose operation appears in typed catalogue R219",
            "inside": "deduplicate by normalized query; reserve SHA-256 first one per represented operation, then SHA-256 remainder to exactly 256 evaluation queries",
            "overlap_rule": "no normalized query may occur in both exemplar training and evaluation, even if source labels differ",
            "ranking": "maximum cosine over all training queries of each operation; operations with no R207 positive exemplar are reported, never imputed",
        },
        "development_evaluation": {
            "inside": 256,
            "metrics": ["recall_top_1", "recall_top_2", "recall_top_5", "recall_top_8", "per_operation_coverage", "per_family_coverage", "gpu_embedding_and_ranking_latency", "gpu_vram"],
            "minimum_useful_comparison": {
                "top_8": "A 28-to-8 shortlist needs 100% expected-operation recall in this query-disjoint population before it can justify any later full-path experiment.",
                "top_2": "A 28-to-2 shortlist, the R134 latency lever, likewise needs 100% recall here before any later full-path experiment.",
                "limitation": "R207 lacks exemplars for some catalogue operations; even a passing covered-population score cannot justify a production shortlist or claim full catalogue coverage.",
            },
            "not_an_oos_gate_blind_measurement_or_runtime_measurement": True,
        },
        "constraints": {
            "r228_opened": False,
            "clinc_opened": False,
            "public_holdout_opened": False,
            "registered_runtime_modified": False,
            "providers_enabled": False,
            "effects_executed": 0,
            "opened_v9": False,
            "voice_stt_wake_exercised": False,
        },
        "identities": {
            "bge_m3_r232_sha256": sha256(r232.OUTPUT),
            "r255_sha256": sha256(R255),
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
