"""Diagnose batch versus individual parity without persisting utterances."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiments.mind_router_spike import (  # noqa: E402
    train_mtop_operation_classifier as trainer,
)
from scripts.measure_mind_budget import write_json_atomic  # noqa: E402


def _probability(logits: np.ndarray, compatible_id: int) -> np.ndarray:
    shifted = logits - np.max(logits, axis=1, keepdims=True)
    probabilities = np.exp(shifted) / np.exp(shifted).sum(axis=1, keepdims=True)
    return probabilities[:, compatible_id].astype(np.float64)


def _rows() -> list[tuple[dict[str, Any], str]]:
    rows, _manifest, _identity = trainer.mtop._load_development(
        trainer.mtop.DEVELOPMENT_CORPUS,
        trainer.mtop.MANIFEST,
    )
    operations = [(row, trainer.operation_label(row)) for row in rows]
    condition_operations = tuple(
        sorted(
            {
                str(operation)
                for _row, operation in operations
                if operation not in {None, trainer.NO_ACTION}
            }
        )
    )
    compatible = [
        (row, "compatible")
        for row, operation in operations
        if row["split"] == "validation"
        and operation not in {None, trainer.NO_ACTION}
    ]
    incompatible = trainer._wrong_operation_pairs(
        compatible,
        condition_operations,
        count=1,
        negative_label="incompatible",
    )
    return [*compatible, *incompatible]


def run(args: argparse.Namespace) -> dict[str, Any]:
    import onnxruntime as ort
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(args.checkpoint, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        args.checkpoint,
        local_files_only=True,
    ).to("cpu").eval()
    compatible_id = int(model.config.label2id["compatible"])
    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    session = ort.InferenceSession(
        str(args.onnx),
        sess_options=options,
        providers=["CPUExecutionProvider"],
    )
    input_names = {item.name for item in session.get_inputs()}
    all_rows = _rows()
    indices = (
        np.arange(len(all_rows), dtype=np.int64)
        if args.cases <= 0
        else np.linspace(
            0,
            len(all_rows) - 1,
            num=min(args.cases, len(all_rows)),
            dtype=np.int64,
        )
    )
    measured = [all_rows[int(index)] for index in indices]

    def encode(batch: list[tuple[dict[str, Any], str]]) -> dict[str, np.ndarray]:
        encoded = tokenizer(
            [str(row["text"]) for row, _label in batch],
            text_pair=[
                "authenticated operation nomination: "
                + str(trainer._conditioned_operation(row))
                for row, _label in batch
            ],
            padding=True,
            truncation=True,
            max_length=112,
            return_tensors="np",
        )
        return {
            key: np.asarray(value, dtype=np.int64)
            for key, value in encoded.items()
            if key in input_names
        }

    torch_batches: list[np.ndarray] = []
    onnx_batches: list[np.ndarray] = []
    for start in range(0, len(measured), args.batch_size):
        feeds = encode(measured[start : start + args.batch_size])
        with torch.inference_mode():
            torch_batches.append(
                _probability(
                    model(
                        **{
                            key: torch.from_numpy(value)
                            for key, value in feeds.items()
                        }
                    ).logits.numpy(),
                    compatible_id,
                )
            )
        onnx_batches.append(
            _probability(
                np.asarray(session.run(["logits"], feeds)[0]),
                compatible_id,
            )
        )
    torch_batch = np.concatenate(torch_batches)
    onnx_batch = np.concatenate(onnx_batches)
    threshold = args.threshold
    diagnostic_positions = np.arange(len(measured), dtype=np.int64)
    if args.mismatches_only:
        diagnostic_positions = np.flatnonzero(
            ((torch_batch >= 0.5) != (onnx_batch >= 0.5))
            | ((torch_batch >= threshold) != (onnx_batch >= threshold))
            | (np.abs(torch_batch - onnx_batch) >= args.delta_threshold)
        )
    diagnostic_rows = [measured[int(index)] for index in diagnostic_positions]
    torch_single: list[float] = []
    onnx_single: list[float] = []
    for item in diagnostic_rows:
        feeds = encode([item])
        with torch.inference_mode():
            torch_logits = model(
                **{key: torch.from_numpy(value) for key, value in feeds.items()}
            ).logits.numpy()
        onnx_logits = np.asarray(session.run(["logits"], feeds)[0])
        torch_single.append(float(_probability(torch_logits, compatible_id)[0]))
        onnx_single.append(float(_probability(onnx_logits, compatible_id)[0]))
    torch_one = np.asarray(torch_single)
    onnx_one = np.asarray(onnx_single)
    torch_subset = torch_batch[diagnostic_positions]
    onnx_subset = onnx_batch[diagnostic_positions]

    def comparison(left: np.ndarray, right: np.ndarray) -> dict[str, Any]:
        return {
            "maximum_probability_delta": round(
                float(np.max(np.abs(left - right))) if len(left) else 0.0,
                9,
            ),
            "argmax_equal": int(np.sum((left >= 0.5) == (right >= 0.5))),
            "threshold_equal": int(
                np.sum((left >= threshold) == (right >= threshold))
            ),
        }

    report = {
        "schema": "baxy.mtop-compatibility-onnx-parity-diagnostic.v1",
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "scope": "development_validation_only_no_text_persisted",
        "scanned_cases": len(measured),
        "individual_cases": len(diagnostic_rows),
        "threshold": threshold,
        "torch_batch_vs_single": comparison(torch_subset, torch_one),
        "onnx_batch_vs_single": comparison(onnx_subset, onnx_one),
        "torch_vs_onnx_batch_all": comparison(torch_batch, onnx_batch),
        "torch_vs_onnx_single": comparison(torch_one, onnx_one),
        "status": "diagnostic_only",
    }
    write_json_atomic(args.output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=Path(
            "D:/BAXYRuntime/experiments/mtop-operation-compatibility-verifier-v16"
        ),
    )
    parser.add_argument(
        "--onnx",
        type=Path,
        default=Path(
            "D:/BAXYRuntime/experiments/mtop-operation-compatibility-verifier-v16-onnx/model.fp32.onnx"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            REPO
            / "artifacts/research/mtop_operation_compatibility_v16_onnx_parity_diagnostic.json"
        ),
    )
    parser.add_argument("--cases", type=int, default=256)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--mismatches-only", action="store_true")
    parser.add_argument("--delta-threshold", type=float, default=0.001)
    parser.add_argument("--threshold", type=float, default=0.906282544)
    args = parser.parse_args()
    args.checkpoint = args.checkpoint.resolve(strict=True)
    args.onnx = args.onnx.resolve(strict=True)
    args.output = args.output.resolve()
    report = run(args)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
