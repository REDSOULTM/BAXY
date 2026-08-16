"""Score a conditional full-catalog mDeBERTa checkpoint on opened MTOP R4."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer


ROOT = Path(__file__).resolve().parents[2]
CHECKPOINT = Path(
    r"D:\BAXYRuntime\experiments\full-catalog-operation-classifier-v2-mdeberta"
)
SOURCE = ROOT / "artifacts/fixes/mtop_product_validation_development_r4_current.json"
REPORT = ROOT / "artifacts/research/full_catalog_mdeberta_v2_mtop_r4.json"


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((len(ordered) - 1) * percentile)))
    return ordered[index]


def probe(args: argparse.Namespace) -> dict[str, Any]:
    source = json.loads(args.source.read_text(encoding="utf-8"))
    tokenizer = AutoTokenizer.from_pretrained(args.checkpoint, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        args.checkpoint,
        local_files_only=True,
    ).to(args.device).eval()
    labels = [
        str(model.config.id2label[index]) for index in range(model.config.num_labels)
    ]
    label_set = set(labels)
    rows = [
        row
        for row in source["samples"]
        if row["expected"]["intent_operations"]
        and set(str(value) for value in row["expected"]["intent_operations"])
        <= label_set
    ]
    score_batches = []
    latencies = []
    with torch.inference_mode():
        for offset in range(0, len(rows), args.batch_size):
            started = time.perf_counter()
            encoded = tokenizer(
                [str(row["text"]) for row in rows[offset : offset + args.batch_size]],
                padding=True,
                truncation=True,
                max_length=96,
                return_tensors="pt",
            )
            encoded = {key: value.to(args.device) for key, value in encoded.items()}
            logits = model(**encoded).logits.float().cpu().numpy()
            elapsed = time.perf_counter() - started
            score_batches.append(logits)
            latencies.extend([elapsed / len(logits)] * len(logits))
    scores = np.concatenate(score_batches, axis=0)
    rankings = np.argsort(-scores, axis=1)
    details = []
    for index, row in enumerate(rows):
        expected = frozenset(str(value) for value in row["expected"]["intent_operations"])
        ranked = [labels[int(value)] for value in rankings[index]]
        details.append(
            {
                "source_id": row["source_id"],
                "text": row["text"],
                "disposition": row["projection"]["disposition"],
                "expected": sorted(expected),
                "top_5": ranked[:5],
                "top_1_correct": ranked[0] in expected,
                "top_3_correct": bool(expected & set(ranked[:3])),
                "margin": round(
                    float(
                        scores[index, rankings[index, 0]]
                        - scores[index, rankings[index, 1]]
                    ),
                    6,
                ),
            }
        )
    result = {
        "schema": "baxy.full-catalog-mdeberta-mtop-r4-probe.v1",
        "scope": "opened_development_conditional_shortlist_no_promotion",
        "source": source["source"],
        "checkpoint": str(args.checkpoint),
        "device": args.device,
        "cases": len(details),
        "excluded_no_effect_or_unavailable": len(source["samples"]) - len(details),
        "top_1_accuracy": round(
            sum(bool(row["top_1_correct"]) for row in details) / len(details),
            6,
        ),
        "top_3_accuracy": round(
            sum(bool(row["top_3_correct"]) for row in details) / len(details),
            6,
        ),
        "latency_seconds_per_case": {
            "p50": round(_percentile(latencies, 0.5), 6),
            "p95": round(_percentile(latencies, 0.95), 6),
        },
        "rows": details,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=CHECKPOINT)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args()
    args.checkpoint = args.checkpoint.resolve(strict=True)
    args.source = args.source.resolve(strict=True)
    args.report = args.report.resolve()
    result = probe(args)
    print(
        json.dumps(
            {
                "cases": result["cases"],
                "top_1_accuracy": result["top_1_accuracy"],
                "top_3_accuracy": result["top_3_accuracy"],
                "latency_seconds_per_case": result["latency_seconds_per_case"],
                "report": str(args.report),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
