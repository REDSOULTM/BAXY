"""Export the calibrated compatibility verifier and prove ONNX parity."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
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


DEFAULT_CHECKPOINT = Path(
    "D:/BAXYRuntime/experiments/mtop-operation-compatibility-verifier-v16"
)
DEFAULT_OUTPUT = Path(
    "D:/BAXYRuntime/experiments/mtop-operation-compatibility-verifier-v16-onnx"
)
DEFAULT_ONNX_TOOLS = Path("D:/BAXYRuntime/experiments/onnx-export-tools-v1")
DEFAULT_CALIBRATION = (
    REPO
    / "artifacts/research/mtop_operation_compatibility_verifier_v16_calibration.json"
)
DEFAULT_REPORT = (
    REPO
    / "artifacts/research/mtop_operation_compatibility_verifier_v16_onnx.json"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(len(ordered) * fraction)))
    return ordered[index]


def run(args: argparse.Namespace) -> dict[str, Any]:
    if not args.onnx_tools.is_dir():
        raise RuntimeError("isolated ONNX export tools are unavailable")
    sys.path.insert(0, str(args.onnx_tools))

    import onnx
    import onnxruntime as ort
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    if (
        args.output.exists()
        and any(args.output.iterdir())
        and not args.resume_fp32
    ):
        raise RuntimeError(f"output already exists: {args.output}")
    calibration = json.loads(args.calibration.read_text(encoding="utf-8"))
    if calibration.get("status") != "candidate":
        raise RuntimeError("compatibility calibration did not pass")
    threshold = float(calibration["selected"]["threshold"])
    rows, manifest, identity = trainer.mtop._load_development(
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
    compatible_rows = [
        (row, "compatible")
        for row, operation in operations
        if row["split"] == "validation"
        and operation not in {None, trainer.NO_ACTION}
    ]
    incompatible_rows = trainer._wrong_operation_pairs(
        compatible_rows,
        condition_operations,
        count=1,
        negative_label="incompatible",
    )
    measured_rows = [*compatible_rows, *incompatible_rows]
    tokenizer = AutoTokenizer.from_pretrained(args.checkpoint, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        args.checkpoint,
        local_files_only=True,
    ).to("cpu").eval()
    compatible_id = int(model.config.label2id["compatible"])
    dummy = tokenizer(
        [str(row["text"]) for row, _label in measured_rows[:2]],
        text_pair=[
            "authenticated operation nomination: "
            + str(trainer._conditioned_operation(row))
            for row, _label in measured_rows[:2]
        ],
        padding=True,
        truncation=True,
        max_length=args.max_length,
        return_tensors="pt",
    )

    class ExportWrapper(torch.nn.Module):
        def __init__(self, classifier: Any) -> None:
            super().__init__()
            self.classifier = classifier

        def forward(
            self,
            input_ids: Any,
            token_type_ids: Any,
            attention_mask: Any,
        ) -> Any:
            return self.classifier(
                input_ids=input_ids,
                token_type_ids=token_type_ids,
                attention_mask=attention_mask,
            ).logits

    args.output.mkdir(parents=True, exist_ok=True)
    fp32 = args.output / "model.fp32.onnx"
    export_seconds = 0.0
    if args.resume_fp32:
        if not fp32.is_file():
            raise RuntimeError("resume requested without an FP32 ONNX model")
    else:
        export_started = time.perf_counter()
        torch.onnx.export(
            ExportWrapper(model),
            (dummy["input_ids"], dummy["token_type_ids"], dummy["attention_mask"]),
            str(fp32),
            input_names=["input_ids", "token_type_ids", "attention_mask"],
            output_names=["logits"],
            dynamic_axes={
                "input_ids": {0: "batch", 1: "sequence"},
                "token_type_ids": {0: "batch", 1: "sequence"},
                "attention_mask": {0: "batch", 1: "sequence"},
                "logits": {0: "batch"},
            },
            opset_version=17,
            do_constant_folding=True,
            dynamo=False,
        )
        export_seconds = time.perf_counter() - export_started
    onnx.checker.check_model(str(fp32))
    # ``torch.onnx.export`` traces through the live module. Reload the frozen
    # checkpoint before parity so the reference cannot inherit exporter state.
    del model
    model = AutoModelForSequenceClassification.from_pretrained(
        args.checkpoint,
        local_files_only=True,
    ).to("cpu").eval()
    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    options.intra_op_num_threads = args.threads
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    session = ort.InferenceSession(
        str(fp32),
        sess_options=options,
        providers=["CPUExecutionProvider"],
    )
    input_names = {item.name for item in session.get_inputs()}
    torch_probabilities: list[np.ndarray] = []
    onnx_probabilities: list[np.ndarray] = []
    for start in range(0, len(measured_rows), args.batch_size):
        batch = measured_rows[start : start + args.batch_size]
        encoded = tokenizer(
            [str(row["text"]) for row, _label in batch],
            text_pair=[
                "authenticated operation nomination: "
                + str(trainer._conditioned_operation(row))
                for row, _label in batch
            ],
            padding=True,
            truncation=True,
            max_length=args.max_length,
            return_tensors="np",
        )
        feeds = {
            key: np.asarray(value, dtype=np.int64)
            for key, value in encoded.items()
            if key in input_names
        }
        with torch.inference_mode():
            torch_logits = model(
                **{
                    key: torch.from_numpy(value)
                    for key, value in feeds.items()
                }
            ).logits.numpy()
        onnx_logits = np.asarray(session.run(["logits"], feeds)[0])
        for logits, destination in (
            (torch_logits, torch_probabilities),
            (onnx_logits, onnx_probabilities),
        ):
            shifted = logits - np.max(logits, axis=1, keepdims=True)
            probabilities = np.exp(shifted) / np.exp(shifted).sum(
                axis=1,
                keepdims=True,
            )
            destination.append(probabilities[:, compatible_id])
    torch_scores = np.concatenate(torch_probabilities).astype(np.float64)
    onnx_scores = np.concatenate(onnx_probabilities).astype(np.float64)
    torch_decisions = torch_scores >= threshold
    onnx_decisions = onnx_scores >= threshold

    latency_rows = measured_rows[: min(args.latency_cases, len(measured_rows))]
    latencies: list[float] = []
    for row, _label in latency_rows:
        encoded = tokenizer(
            str(row["text"]),
            text_pair=(
                "authenticated operation nomination: "
                + str(trainer._conditioned_operation(row))
            ),
            truncation=True,
            max_length=args.max_length,
            return_tensors="np",
        )
        feeds = {
            key: np.asarray(value, dtype=np.int64)
            for key, value in encoded.items()
            if key in input_names
        }
        started = time.perf_counter()
        session.run(["logits"], feeds)
        latencies.append(time.perf_counter() - started)
    split = len(compatible_rows)
    report = {
        "schema": "baxy.mtop-operation-compatibility-onnx.v1",
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "scope": "development_validation_only_mtop_test_remains_sealed",
        "source": {
            "checkpoint": str(args.checkpoint.resolve()),
            "calibration": str(args.calibration.relative_to(REPO)),
            "calibration_sha256": _sha256(args.calibration),
            "mtop_development_sha256": identity.corpus.sha256,
            "mtop_manifest_sha256": identity.manifest.sha256,
            "mtop_map_sha256": manifest["source"]["map_sha256"],
            "mtop_test_content_read": False,
        },
        "model": {
            "path": str(fp32.resolve()),
            "bytes": fp32.stat().st_size,
            "sha256": _sha256(fp32),
            "checker_passed": True,
            "export_seconds": round(export_seconds, 6),
        },
        "parity": {
            "cases": len(measured_rows),
            "argmax_equal": int(
                np.sum((torch_scores >= 0.5) == (onnx_scores >= 0.5))
            ),
            "threshold_decision_equal": int(np.sum(torch_decisions == onnx_decisions)),
            "maximum_compatible_probability_delta": round(
                float(np.max(np.abs(torch_scores - onnx_scores))),
                9,
            ),
        },
        "calibrated_onnx": {
            "threshold": threshold,
            "compatible_accuracy": round(float(np.mean(onnx_decisions[:split])), 9),
            "incompatible_accuracy": round(
                float(np.mean(~onnx_decisions[split:])),
                9,
            ),
        },
        "cpu_latency_seconds": {
            "cases": len(latencies),
            "mean": round(statistics.fmean(latencies), 6),
            "p50": round(_percentile(latencies, 0.5), 6),
            "p95": round(_percentile(latencies, 0.95), 6),
            "maximum": round(max(latencies), 6),
            "threads": args.threads,
        },
        "status": (
            "candidate"
            if np.all(torch_decisions == onnx_decisions)
            and float(np.mean(onnx_decisions[:split])) >= 0.99
            and float(np.mean(~onnx_decisions[split:])) >= 0.99
            else "rejected"
        ),
    }
    trainer.mtop._assert_input_identity_stable(identity)
    write_json_atomic(args.report, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--onnx-tools", type=Path, default=DEFAULT_ONNX_TOOLS)
    parser.add_argument("--calibration", type=Path, default=DEFAULT_CALIBRATION)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--max-length", type=int, default=112)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--latency-cases", type=int, default=198)
    parser.add_argument("--resume-fp32", action="store_true")
    args = parser.parse_args()
    args.checkpoint = args.checkpoint.resolve(strict=True)
    args.onnx_tools = args.onnx_tools.resolve(strict=True)
    args.calibration = args.calibration.resolve(strict=True)
    args.output = args.output.resolve()
    args.report = args.report.resolve()
    report = run(args)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
