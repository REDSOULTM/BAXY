"""Export and benchmark loss-aware ONNX variants of the MTOP specialist.

The experiment uses only the frozen MTOP development checkpoint and the
already-open R4 development sample.  It creates FP32 and dynamic INT8 ONNX
models outside the repository, then measures top-k identity and CPU latency.
No blind corpus is opened, no runtime manifest is changed, and no operation is
dispatched.
"""

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


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts", Path(__file__).parent):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import measure_turn_policy_v52_mtop_validation as mtop  # noqa: E402
import train_mtop_operation_classifier as trainer  # noqa: E402
from scripts.measure_mind_budget import write_json_atomic  # noqa: E402


DEFAULT_CHECKPOINT = Path(
    r"D:\BAXYRuntime\experiments\mtop-operation-classifier-v8-mdeberta"
)
DEFAULT_OUTPUT = Path(
    r"D:\BAXYRuntime\experiments\mtop-operation-classifier-v8-onnx"
)
DEFAULT_ONNX_TOOLS = Path(r"D:\BAXYRuntime\experiments\onnx-export-tools-v1")
DEFAULT_SOURCE = (
    REPO / "artifacts/fixes/mtop_product_validation_development_r4_current.json"
)
DEFAULT_REPORT = REPO / "artifacts/research/mdeberta_onnx_quantization_r2.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, int(percentile * len(ordered) + 0.999) - 1))
    return ordered[rank]


def _top_k(scores: Any, truth: Any, count: int) -> float:
    import numpy as np

    order = np.argsort(-scores, axis=1)[:, :count]
    return float(np.mean([truth[index] in row for index, row in enumerate(order)]))


def _benchmark_session(
    path: Path,
    encoded_rows: list[dict[str, Any]],
    truth: Any,
    *,
    threads: int,
) -> dict[str, Any]:
    import numpy as np
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    options.intra_op_num_threads = threads
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    started = time.perf_counter()
    session = ort.InferenceSession(
        str(path),
        sess_options=options,
        providers=["CPUExecutionProvider"],
    )
    load_seconds = time.perf_counter() - started
    input_names = {item.name for item in session.get_inputs()}

    def infer(row: dict[str, Any]) -> Any:
        feeds = {
            key: np.asarray(value, dtype=np.int64)
            for key, value in row.items()
            if key in input_names
        }
        return session.run(["logits"], feeds)[0]

    for row in encoded_rows[:3]:
        infer(row)
    latencies: list[float] = []
    scores: list[Any] = []
    for row in encoded_rows:
        started = time.perf_counter()
        scores.append(infer(row))
        latencies.append(time.perf_counter() - started)
    matrix = np.concatenate(scores, axis=0)
    return {
        "file_name": path.name,
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "load_seconds": round(load_seconds, 6),
        "top_1_accuracy": round(_top_k(matrix, truth, 1), 6),
        "top_3_accuracy": round(_top_k(matrix, truth, 3), 6),
        "top_5_accuracy": round(_top_k(matrix, truth, 5), 6),
        "seconds_p50": statistics.median(latencies),
        "seconds_p95": _percentile(latencies, 0.95),
        "seconds_max": max(latencies),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.report.exists():
        raise RuntimeError(f"refusing to overwrite report: {args.report}")
    fp32 = args.output / "model.fp32.onnx"
    if args.output.exists() and any(args.output.iterdir()) and not args.resume_fp32:
        raise RuntimeError(f"refusing to overwrite model output: {args.output}")
    if args.resume_fp32 and not fp32.is_file():
        raise RuntimeError("resume requested without an existing FP32 ONNX model")
    if not args.onnx_tools.is_dir():
        raise RuntimeError("the isolated ONNX export tools are unavailable")
    sys.path.insert(0, str(args.onnx_tools))

    import numpy as np
    import onnx
    import torch
    from onnxruntime.quantization import QuantType, quantize_dynamic
    from onnxruntime.quantization.shape_inference import quant_pre_process
    from transformers import (
        AutoConfig,
        AutoModelForSequenceClassification,
        AutoTokenizer,
    )

    development_rows, manifest, identity = mtop._load_development(
        mtop.DEVELOPMENT_CORPUS,
        mtop.MANIFEST,
    )
    row_by_source = {
        str(row["source_id"]): row
        for row in development_rows
    }
    source = json.loads(args.source.read_text(encoding="utf-8"))
    samples = source.get("samples") if isinstance(source, dict) else None
    if not isinstance(samples, list) or not samples:
        raise ValueError("the R4 development source has no samples")
    rows: list[dict[str, Any]] = []
    expected_labels: list[str] = []
    for sample in samples:
        row = row_by_source.get(str(sample.get("source_id", "")))
        if row is None or str(sample.get("text")) != str(row["text"]):
            raise ValueError("the R4 sample escaped hash-bound MTOP development")
        label = trainer.operation_label(row)
        if label is None:
            raise ValueError("an unscorable projection entered ONNX measurement")
        rows.append(row)
        expected_labels.append(str(label))

    tokenizer = AutoTokenizer.from_pretrained(
        args.checkpoint,
        local_files_only=True,
    )
    config = AutoConfig.from_pretrained(args.checkpoint, local_files_only=True)
    labels = tuple(
        str(config.id2label[index])
        for index in range(config.num_labels)
    )
    label_to_id = {label: index for index, label in enumerate(labels)}
    truth = np.asarray([label_to_id[label] for label in expected_labels], dtype=np.int64)
    encoded_rows = [
        {
            key: np.asarray(value)
            for key, value in tokenizer(
                str(row["text"]),
                truncation=True,
                max_length=96,
                return_tensors="np",
            ).items()
        }
        for row in rows
    ]
    export_seconds = 0.0
    if not args.resume_fp32:
        model = AutoModelForSequenceClassification.from_pretrained(
            args.checkpoint,
            local_files_only=True,
        ).to("cpu").eval()
        dummy = tokenizer(
            [str(row["text"]) for row in rows[:2]],
            padding=True,
            truncation=True,
            max_length=96,
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

        args.output.mkdir(parents=True, exist_ok=False)
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

    preprocessed = args.output / "model.preprocessed.onnx"
    quant_pre_process(
        input_model=str(fp32),
        output_model_path=str(preprocessed),
        skip_optimization=False,
        skip_onnx_shape=False,
        skip_symbolic_shape=False,
        auto_merge=True,
    )
    onnx.checker.check_model(str(preprocessed))
    variants: list[tuple[str, Path]] = [
        ("fp32", fp32),
        ("fp32_preprocessed", preprocessed),
    ]
    for name, per_channel in (
        ("int8_per_tensor", False),
        ("int8_per_channel", True),
    ):
        output = args.output / f"model.preprocessed_{name}.onnx"
        quantize_dynamic(
            model_input=str(preprocessed),
            model_output=str(output),
            per_channel=per_channel,
            reduce_range=False,
            weight_type=QuantType.QInt8,
        )
        onnx.checker.check_model(str(output))
        variants.append((name, output))

    measurements = {
        name: _benchmark_session(
            path,
            encoded_rows,
            truth,
            threads=args.threads,
        )
        for name, path in variants
    }
    result = {
        "schema": "baxy.mdeberta-onnx-quantization-development.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "development_only_mtop_test_and_baxy_blind_reserve_sealed",
        "authority": "offline_classification_only_no_core_plan_or_provider",
        "effects_executed": 0,
        "contains_utterance_text": False,
        "source": {
            "checkpoint": str(args.checkpoint.resolve()),
            "checkpoint_config_sha256": _sha256(args.checkpoint / "config.json"),
            "r4_probe": str(args.source.relative_to(REPO)),
            "r4_probe_sha256": _sha256(args.source),
            "mtop_development_sha256": identity.corpus.sha256,
            "mtop_manifest_sha256": identity.manifest.sha256,
            "mtop_map_sha256": manifest["source"]["map_sha256"],
            "mtop_test_content_read": False,
            "baxy_blind_reserve_opened": False,
            "onnx_version": onnx.__version__,
        },
        "configuration": {
            "cases": len(rows),
            "classes": len(labels),
            "opset": 17,
            "cpu_threads": args.threads,
            "dynamic_int8": True,
            "quantization_preprocessed": True,
            "resumed_existing_fp32": args.resume_fp32,
            "export_seconds": round(export_seconds, 6),
        },
        "measurements": measurements,
    }
    mtop._assert_input_identity_stable(identity)
    write_json_atomic(args.report, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--onnx-tools", type=Path, default=DEFAULT_ONNX_TOOLS)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--resume-fp32", action="store_true")
    args = parser.parse_args()
    result = run(args)
    print(json.dumps(result["measurements"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
