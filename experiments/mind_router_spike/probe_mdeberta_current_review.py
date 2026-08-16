"""Test the existing mDeBERTa intent checkpoint on BAXY development cases.

Only rows representable by the checkpoint's 15 labels are scored.  This opens
no blind holdout and promotes nothing; it asks whether the transformer result
survives the BAXY domain shift well enough to justify a full-catalog variant.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer


ROOT = Path(__file__).resolve().parents[2]
CORPUS = (
    ROOT
    / "artifacts"
    / "development"
    / "current_catalog_review_development.v1.jsonl"
)
CHECKPOINT = Path(
    r"D:\BAXYRuntime\experiments\mtop-operation-classifier-v8-mdeberta"
)
NO_ACTION = "__none__"


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _single_expected(row: dict[str, object]) -> frozenset[str] | None:
    accepted = {
        str(operations[0])
        for operations in row["compatible_terminal_operation_sets"]
        if len(operations) == 1
    }
    return frozenset(accepted) if accepted else None


def main() -> int:
    rows = _read_jsonl(CORPUS)
    tokenizer = AutoTokenizer.from_pretrained(CHECKPOINT, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        CHECKPOINT,
        local_files_only=True,
        torch_dtype=torch.float16,
    ).to("cuda")
    model.eval()
    labels = tuple(
        str(model.config.id2label[index])
        for index in range(model.config.num_labels)
    )
    eligible: list[tuple[dict[str, object], frozenset[str]]] = []
    for row in rows:
        expected = _single_expected(row)
        if expected is None:
            if row["outcome"] in {"conversation", "unsupported"}:
                eligible.append((row, frozenset({NO_ACTION})))
        elif expected <= set(labels):
            eligible.append((row, expected))

    torch.cuda.reset_peak_memory_stats()
    logits: list[np.ndarray] = []
    started = time.perf_counter()
    for offset in range(0, len(eligible), 32):
        encoded = tokenizer(
            [str(row["text"]) for row, _expected in eligible[offset : offset + 32]],
            padding=True,
            truncation=True,
            max_length=96,
            return_tensors="pt",
        )
        encoded = {key: value.to("cuda") for key, value in encoded.items()}
        with torch.inference_mode():
            batch = model(**encoded).logits.float().cpu().numpy()
        logits.extend(batch)
    elapsed = time.perf_counter() - started
    scores = np.asarray(logits)
    rankings = np.argsort(-scores, axis=1)
    details = []
    for index, ((row, expected), order) in enumerate(zip(eligible, rankings, strict=True)):
        ranked = [labels[int(value)] for value in order]
        details.append(
            {
                "case_id": row["case_id"],
                "outcome": row["outcome"],
                "expected": sorted(expected),
                "top_5": ranked[:5],
                "top_1_correct": ranked[0] in expected,
                "top_3_correct": bool(expected & set(ranked[:3])),
                "margin": round(
                    float(scores[index, order[0]] - scores[index, order[1]]),
                    6,
                ),
                "energy": round(
                    -float(torch.logsumexp(torch.from_numpy(scores[index]), dim=0)),
                    6,
                ),
            }
        )
    identity = [row for row in details if row["expected"] != [NO_ACTION]]
    no_action = [row for row in details if row["expected"] == [NO_ACTION]]

    def accuracy(population: list[dict[str, object]], field: str) -> float:
        return sum(bool(row[field]) for row in population) / len(population)

    result = {
        "schema": "baxy.mdeberta-current-review-probe.v1",
        "scope": "reviewed_development_only_not_blind_representable_labels",
        "labels": list(labels),
        "cases": len(details),
        "identity_cases": len(identity),
        "no_action_cases": len(no_action),
        "top_1_accuracy": round(accuracy(details, "top_1_correct"), 6),
        "top_3_accuracy": round(accuracy(details, "top_3_correct"), 6),
        "identity_top_1_accuracy": round(accuracy(identity, "top_1_correct"), 6),
        "identity_top_3_accuracy": round(accuracy(identity, "top_3_correct"), 6),
        "no_action_accuracy": round(accuracy(no_action, "top_1_correct"), 6),
        "inference_seconds": round(elapsed, 6),
        "peak_reserved_mib": round(torch.cuda.max_memory_reserved() / 2**20, 3),
        "rows": details,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
