"""Inventory available retrieval candidates without loading or measuring a model."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SCORECARD = (
    REPO / "experiments/mind_router_spike/results/tournament_encoder_scorecard.json"
)
QWEN_COVERAGE = (
    REPO
    / "experiments/mind_router_spike/results/report_coverage__Qwen__Qwen3-Embedding-0.6B.json"
)
QWEN_LOO = (
    REPO
    / "experiments/mind_router_spike/results/report_loo__Qwen__Qwen3-Embedding-0.6B.json"
)
HF_CACHE = Path.home() / ".cache/huggingface/hub/models--Qwen--Qwen3-Embedding-0.6B"
BGE_CACHE = Path.home() / ".cache/huggingface/hub/models--BAAI--bge-m3"
OUTPUT = REPO / "artifacts/audit/retrieval_candidate_inventory_r227.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict[str, object]:
    scorecard = json.loads(SCORECARD.read_text(encoding="utf-8"))
    coverage = json.loads(QWEN_COVERAGE.read_text(encoding="utf-8"))
    loo = json.loads(QWEN_LOO.read_text(encoding="utf-8"))
    qwen = next(
        row
        for row in scorecard["results"]
        if row["model"] == "Qwen/Qwen3-Embedding-0.6B"
    )
    snapshots = (
        sorted(
            path.name for path in (HF_CACHE / "snapshots").iterdir() if path.is_dir()
        )
        if (HF_CACHE / "snapshots").is_dir()
        else []
    )
    return {
        "schema": "baxy.retrieval-candidate-inventory.r227.v1",
        "authority": "read_only_inventory_of_existing_development_evidence_not_a_new_model_measurement",
        "state_of_art_sources": [
            "https://github.com/QwenLM/Qwen3-Embedding",
            "https://github.com/FlagOpen/FlagEmbedding/blob/master/docs/source/bge/bge_m3.rst",
            "https://www.sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html",
        ],
        "available_locally": {
            "Qwen/Qwen3-Embedding-0.6B": {
                "snapshot_ids": snapshots,
                "cached": bool(snapshots),
            },
            "BAAI/bge-m3": {
                "cached": (BGE_CACHE / "snapshots").is_dir(),
                "reason": "no local Hugging Face snapshot discovered"
                if not (BGE_CACHE / "snapshots").is_dir()
                else "local snapshot exists",
            },
        },
        "existing_qwen_development_evidence": {
            "coverage_accuracy": coverage["overall_accuracy"],
            "loo_accuracy": loo["overall_accuracy"],
            "loo_dangerous_failures": loo["failure_modes"][
                "dangerous_wrong_or_false_route"
            ],
            "single_query_cpu_ms": qwen["single_query_cpu_ms"],
            "process_ram_mib": qwen["process_ram_mib"],
            "scope": "2026-07 frozen encoder tournament; not a fresh Cut B and not usable for tuning",
        },
        "verdict": {
            "qwen_embedding_direct_retriever": "rejected_for_adoption_without_new_evidence",
            "reason": "existing development hard coverage is below one and LOO has 28 dangerous failures; it cannot be promoted or tuned against consumed R215",
            "next_candidate_requirement": "fresh independently generated Cut B plus separated development evidence before any hybrid/re-rank architecture is adopted",
        },
        "constraints": {
            "model_started": False,
            "providers_enabled": False,
            "effects_executed": 0,
            "opened_v9": False,
            "voice_stt_wake_exercised": False,
        },
        "identities": {
            "scorecard_sha256": sha256(SCORECARD),
            "coverage_sha256": sha256(QWEN_COVERAGE),
            "loo_sha256": sha256(QWEN_LOO),
            "program_sha256": sha256(Path(__file__)),
        },
    }


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing to overwrite retrieval inventory: {OUTPUT}")
    OUTPUT.write_bytes(
        (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
