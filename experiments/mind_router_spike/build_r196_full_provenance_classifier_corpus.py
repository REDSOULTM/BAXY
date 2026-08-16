"""Freeze all provenance-preserved selector rows for the R196 warm-start test."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / "artifacts" / "research" / "functiongemma_training_corpus.v3.jsonl"
R186 = REPO / "artifacts" / "development" / "bge_qwen_embedding_cascade_r186_preregistration.json"
OUT = REPO / "artifacts" / "development" / "r196_full_provenance_classifier_training.jsonl"
AUDIT = REPO / "artifacts" / "audit" / "r196_full_provenance_classifier_corpus_admission.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return " ".join("".join(char for char in decomposed if not unicodedata.combining(char)).split())


def rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def build(output: Path, audit_output: Path) -> dict[str, Any]:
    source, evaluation = rows(SOURCE), json.loads(R186.read_text(encoding="utf-8"))["rows"]
    forbidden = {normalized(str(row["text"])) for row in evaluation}
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, Any]] = []
    for row in source:
        text, label = str(row["text"]), str(row["operation"])
        key = (normalized(text), label)
        if key in seen:
            continue
        if key[0] in forbidden:
            raise ValueError("r196_training_overlaps_frozen_evaluation")
        seen.add(key)
        result.append({"schema": "baxy.r196-full-provenance-classifier-row.v1", "case_id": f"r196-{row['case_id']}", "text": text, "language": row["language"], "label": label, "source": row["source"], "human_semantic_audit": False, "execution_authority": False})
    counts = Counter(str(row["label"]) for row in result)
    if len(result) != 4740 or len(counts) != 170 or counts["__no_action__"] != 41:
        raise ValueError("r196_requires_complete_4740_row_170_label_provenance_contract")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in result) + "\n").encode("utf-8"))
    report = {"schema": "baxy.r196-full-provenance-classifier-corpus-admission.v1", "authority": "development_only_full_provenance_corpus_build", "identities": {"program_sha256": sha256(Path(__file__).resolve()), "corpus_sha256": sha256(output), "source_sha256": sha256(SOURCE), "r186_sha256": sha256(R186)}, "counts": {"rows": len(result), "labels": len(counts), "catalog_operation_labels": 169, "learned_abstention_rows": counts["__no_action__"], "evaluation_exact_text_overlap": 0, "human_semantic_audit_claimed": 0}, "admission": {"exploratory_local_training": True, "human_audited_training": False, "certification_or_holdout": False, "model_started": False, "runtime_modified": False, "opened_v9": False}}
    audit_output.parent.mkdir(parents=True, exist_ok=True)
    audit_output.write_bytes((json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    return report


def main() -> int:
    report = build(OUT, AUDIT); print(json.dumps(report["counts"], sort_keys=True)); return 0


if __name__ == "__main__": raise SystemExit(main())
