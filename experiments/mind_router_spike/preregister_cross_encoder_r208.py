"""Freeze the BAXY-trained all-operation cross-encoder experiment."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PAIRS = REPO / "artifacts/development/r207_cross_encoder_pairs.jsonl"
R186 = REPO / "artifacts/development/bge_qwen_embedding_cascade_r186_preregistration.json"
CATALOG = REPO / "artifacts/development/catalog_vocabulary_snapshot.json"
RUNNER = REPO / "experiments/mind_router_spike/train_evaluate_cross_encoder_r209.py"
OUT = REPO / "artifacts/development/cross_encoder_r208_preregistration.json"
SOURCE = Path(r"D:\BAXYRuntime\experiments\mtop-operation-compatibility-verifier-v16")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(root: Path) -> dict[str, object]:
    pairs_path = root / PAIRS.relative_to(REPO)
    r186_path = root / R186.relative_to(REPO)
    catalog_path = root / CATALOG.relative_to(REPO)
    runner_path = root / RUNNER.relative_to(REPO)
    if not SOURCE.is_dir() or not runner_path.is_file():
        raise FileNotFoundError("r208_requires_local_binary_checkpoint_and_runner")
    pairs = [json.loads(line) for line in pairs_path.read_text(encoding="utf8").splitlines() if line]
    evaluation = json.loads(r186_path.read_text(encoding="utf8"))["rows"]
    catalog = json.loads(catalog_path.read_text(encoding="utf8"))["capabilities"]
    if len(pairs) != 23700 or sum(row["target"] for row in pairs) != 4740:
        raise ValueError("r208_pair_contract_failed")
    if len(catalog) != 169 or len({row["operation"] for row in pairs}) != 170:
        raise ValueError("r208_catalog_contract_failed")
    rows = [{key: row[key] for key in ("case_id", "language", "text", "expected_operations", "population")} for row in evaluation if row["population"] in {"r146_model_owned", "oos_control"}]
    if len(rows) != 86 or sum(row["population"] == "r146_model_owned" for row in rows) != 77 or sum(row["population"] == "oos_control" for row in rows) != 9:
        raise ValueError("r208_evaluation_contract_failed")
    return {
        "schema": "baxy.cross-encoder-r208-preregistration.v1",
        "authority": "preregistration_only_no_training_or_runtime_integration",
        "candidate": {
            "source_checkpoint": str(SOURCE),
            "source_config_sha256": sha(SOURCE / "config.json"),
            "mechanism": "binary_query_operation_cross_encoder_scored_over_all_169_catalog_operations_and_explicit_no_action",
            "training": {"epochs": 3, "batch_size": 4, "gradient_accumulation": 4, "learning_rate": 2e-5, "max_length": 160, "seed": 208, "positive_class_weight": 4.0},
            "decision": {"compatible_label": "compatible", "candidate_probability_threshold": 0.5, "all_170_labels_scored": True, "threshold_calibrated_on_r186": False},
        },
        "data_contract": {"r207_pairs_training_only": True, "r186_evaluation_only": True, "all_catalog_operations_scored": True, "no_action_scored": True},
        "evaluation": {"rows": rows, "model_owned_rows": 77, "oos_controls": 9, "exact_rate_required": 0.95, "oos_zero_candidates_required": 9, "raw_compatibility_scores_retained": True},
        "constraints": {"no_retriever": True, "no_lexical_gate": True, "no_posthoc_threshold": True, "runtime_modified": False, "providers_enabled": False, "external_effects_executed": 0, "opened_v9": False, "v9_reserved": True},
        "identities": {"program_sha256": sha(Path(__file__)), "runner_sha256": sha(runner_path), "pairs_sha256": sha(pairs_path), "r186_sha256": sha(r186_path), "catalog_sha256": sha(catalog_path)},
    }


def main() -> None:
    OUT.write_bytes((json.dumps(build(REPO), ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode())


if __name__ == "__main__":
    main()
