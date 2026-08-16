"""Export a local Hugging Face sequence classifier to validated FP32 ONNX."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CHECKPOINT = Path(
    r"D:\BAXYRuntime\experiments\full-catalog-operation-classifier-v2-mdeberta"
)
DEFAULT_OUTPUT = Path(
    r"D:\BAXYRuntime\experiments\full-catalog-operation-classifier-v2-onnx"
)
DEFAULT_ONNX_TOOLS = Path(r"D:\BAXYRuntime\experiments\onnx-export-tools-v1")
DEFAULT_REPORT = ROOT / "artifacts/research/full_catalog_mdeberta_v2_onnx.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.output.exists():
        raise RuntimeError(f"refusing to overwrite output: {args.output}")
    if args.report.exists():
        raise RuntimeError(f"refusing to overwrite report: {args.report}")
    if not args.onnx_tools.is_dir():
        raise RuntimeError("isolated ONNX validation tools are unavailable")
    sys.path.insert(0, str(args.onnx_tools))

    import onnx
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(args.checkpoint, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        args.checkpoint,
        local_files_only=True,
    ).to("cpu").eval()
    dummy = tokenizer(
        ["Cancel my latest alarm.", "Pon música en vivo de Tesla."],
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
    model_path = args.output / "model.fp32.onnx"
    started = time.perf_counter()
    torch.onnx.export(
        ExportWrapper(model),
        (dummy["input_ids"], dummy["token_type_ids"], dummy["attention_mask"]),
        str(model_path),
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
    export_seconds = time.perf_counter() - started
    onnx.checker.check_model(str(model_path))
    report = {
        "schema": "baxy.sequence-classifier-onnx-export.v1",
        "scope": "development_only_not_promoted",
        "authority": "offline_classification_only_no_core_plan_or_provider",
        "checkpoint": str(args.checkpoint),
        "checkpoint_config_sha256": _sha256(args.checkpoint / "config.json"),
        "model": str(model_path),
        "model_bytes": model_path.stat().st_size,
        "model_sha256": _sha256(model_path),
        "opset": 17,
        "export_seconds": round(export_seconds, 6),
        "onnx_version": onnx.__version__,
        "effects_executed": 0,
        "blind_holdout_opened": False,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--onnx-tools", type=Path, default=DEFAULT_ONNX_TOOLS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    args.checkpoint = args.checkpoint.resolve(strict=True)
    args.output = args.output.resolve()
    args.onnx_tools = args.onnx_tools.resolve(strict=True)
    args.report = args.report.resolve()
    print(json.dumps(run(args), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
