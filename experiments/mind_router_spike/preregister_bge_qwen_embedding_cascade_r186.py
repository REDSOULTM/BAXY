"""Freeze a retrieval-union/native-decision cascade before model inference."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / "artifacts/development/catalog_vocabulary_snapshot.json"
BGE = REPO / "artifacts/development/bge_m3_operation_recovery_r160_attested.json"
QWEN = REPO / "artifacts/development/qwen3_embedding_operation_recovery_r184_attested.json"
OUTPUT = REPO / "artifacts/development/bge_qwen_embedding_cascade_r186_preregistration.json"
BGE_MODES = ("dense", "sparse", "colbert")
QWEN_TOP_K = 5


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(path: Path) -> dict[str, dict[str, Any]]:
    return {str(row["case_id"]): row for row in json.loads(path.read_text(encoding="utf-8"))["rows"]}


def shortlists(catalog: list[dict[str, Any]], bge_path: Path = BGE, qwen_path: Path = QWEN) -> list[dict[str, Any]]:
    order = [str(row["name"]) for row in catalog]
    bge, qwen = _rows(bge_path), _rows(qwen_path)
    if set(bge) != set(qwen):
        raise ValueError("r186_requires_identical_attested_row_keys")
    result: list[dict[str, Any]] = []
    for case_id in sorted(bge):
        left, right = bge[case_id], qwen[case_id]
        if left["text"] != right["text"] or left["population"] != right["population"]:
            raise ValueError("r186_retrieval_rows_are_not_identical")
        bge_names = set().union(*(set(left["top10_operations"][mode]) for mode in BGE_MODES))
        ranked_qwen = sorted(right["raw_operation_scores"], key=lambda name: (-float(right["raw_operation_scores"][name]), name))[:QWEN_TOP_K]
        offered = [name for name in order if name in bge_names or name in ranked_qwen]
        result.append({"case_id": case_id, "language": left["language"], "text": left["text"], "population": left["population"], "expected_operations": left["expected_operations"], "offered_operations": offered, "expected_offered": bool(set(left["expected_operations"]) & set(offered)) if left["expected_operations"] else None})
    known = [row for row in result if row["population"] == "r146_model_owned"]
    oos = [row for row in result if row["population"] == "oos_control"]
    if len(known) != 77 or len(oos) != 9:
        raise ValueError("r186_requires_77_model_owned_and_9_shared_oos_rows")
    return result


def build(repository_root: Path) -> dict[str, Any]:
    catalog_path = repository_root / CATALOG.relative_to(REPO)
    bge_path = repository_root / BGE.relative_to(REPO)
    qwen_path = repository_root / QWEN.relative_to(REPO)
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))["capabilities"]
    rows = shortlists(catalog, bge_path, qwen_path)
    counts = [len(row["offered_operations"]) for row in rows]
    return {"schema": "baxy.bge-qwen-embedding-native-cascade-preregistration.r186.v1", "authority": "preregistration_only_no_decision_model_or_runtime_start", "candidate": {"retrieval": {"bge_top_k": 10, "bge_modes": list(BGE_MODES), "qwen_embedding_top_k": QWEN_TOP_K, "merge": "set_union_then_authenticated_catalog_order"}, "decision": "active_qwen3_native_openai_tools_tool_choice_auto", "catalog_operations": len(catalog)}, "population": {"model_owned_rows": 77, "shared_oos_rows": 9, "offered_operations_min": min(counts), "offered_operations_max": max(counts), "offered_operations_median": sorted(counts)[len(counts)//2]}, "acceptance": {"retrieval_reachable_rows_minimum": 74, "raw_decision_exact_rate_required": .95, "oos_zero_candidates_required": 9, "raw_output_retained_before_veto": True, "visible_text_audit_required": True, "p95_seconds_maximum": 2.0}, "constraints": {"no_threshold": True, "no_lexical_gate": True, "no_runtime_integration": True, "providers_enabled": False, "external_effects_executed": 0, "opened_v9": False, "v9_reserved": True}, "identities": {"program_sha256": sha256(Path(__file__)), "catalog_sha256": sha256(catalog_path), "bge_r160_sha256": sha256(bge_path), "qwen_r184_sha256": sha256(qwen_path)}, "rows": rows}


def main() -> int:
    report = build(REPO)
    OUTPUT.write_bytes((json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
