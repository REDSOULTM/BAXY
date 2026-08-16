"""Export the proven phoneme CTC verifier to an attested ONNX graph."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time


SAMPLE_RATE = 16_000
WINDOW_SAMPLES = 32_000
REPORT_FILENAME = "export.report.v1.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(
    *,
    teacher_directory: Path,
    output_directory: Path,
    opset: int,
    window_samples: int = WINDOW_SAMPLES,
    dynamic_samples: bool = False,
    dynamic_batch: bool = False,
) -> dict[str, object]:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")
    teacher_directory = teacher_directory.resolve(strict=True)
    output_directory = output_directory.resolve()
    required = ("config.json", "preprocessor_config.json", "pytorch_model.bin", "vocab.json")
    if (
        output_directory.exists()
        or not 17 <= opset <= 23
        or window_samples not in {32_000, 48_000, 64_000}
        or not all((teacher_directory / name).is_file() for name in required)
    ):
        raise ValueError("phoneme_teacher_onnx_export_inputs_invalid")
    output_directory.mkdir(parents=True)
    window_seconds = window_samples // SAMPLE_RATE
    if dynamic_samples:
        contract_name = "dynamic"
    else:
        contract_name = f"fixed{window_seconds}s"
    if dynamic_batch:
        contract_name += "-batch"
    output_path = output_directory / f"wav2vec2-phoneme-ctc-fp32-{contract_name}.onnx"

    import onnx
    import torch
    import transformers
    from transformers import Wav2Vec2ForCTC

    class LogitsOnly(torch.nn.Module):
        def __init__(self, model: object) -> None:
            super().__init__()
            self.model = model

        def forward(self, input_values: object) -> object:
            return self.model(input_values=input_values).logits

    load_started = time.perf_counter()
    model = Wav2Vec2ForCTC.from_pretrained(
        teacher_directory, local_files_only=True
    ).eval().cpu()
    load_seconds = time.perf_counter() - load_started
    wrapper = LogitsOnly(model).eval()
    # A size-one example lets the exporter legally specialize the batch axis
    # even when a dynamic dimension was requested.  Demonstrate variation in
    # that axis so the emitted ONNX contract itself, not only our report,
    # carries the symbolic batch dimension.
    example_batch = 2 if dynamic_batch else 1
    dummy = torch.zeros((example_batch, window_samples), dtype=torch.float32)

    export_started = time.perf_counter()
    dynamic_shapes = None
    dynamic_dimensions = {}
    if dynamic_batch:
        dynamic_dimensions[0] = torch.export.Dim("batch", min=1, max=16)
    if dynamic_samples:
        dynamic_dimensions[1] = torch.export.Dim(
            "samples", min=SAMPLE_RATE, max=SAMPLE_RATE * 10
        )
    if dynamic_dimensions:
        dynamic_shapes = {"input_values": dynamic_dimensions}
    with torch.inference_mode():
        torch.onnx.export(
            wrapper,
            (dummy,),
            output_path,
            input_names=("input_values",),
            output_names=("logits",),
            opset_version=opset,
            dynamo=True,
            external_data=True,
            optimize=True,
            verify=False,
            dynamic_shapes=dynamic_shapes,
        )
    export_seconds = time.perf_counter() - export_started
    onnx.checker.check_model(str(output_path), full_check=False)

    files = []
    for path in sorted(output_directory.iterdir(), key=lambda item: item.name):
        if path.is_file() and path.name != REPORT_FILENAME:
            files.append(
                {
                    "name": path.name,
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256(path),
                }
            )
    report = {
        "schema": "baxy.phoneme-teacher-onnx-export.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "directory": teacher_directory.as_posix(),
            "weights_sha256": sha256(teacher_directory / "pytorch_model.bin"),
        },
        "graph": {
            "opset": opset,
            "sample_rate": SAMPLE_RATE,
            "window_samples": window_samples,
            "input_shape": [
                "batch" if dynamic_batch else 1,
                "samples" if dynamic_samples else window_samples,
            ],
            "dynamic_batch": dynamic_batch,
            "maximum_batch_size": 16 if dynamic_batch else 1,
            "export_example_batch_size": example_batch,
            "dynamic_samples": dynamic_samples,
            "minimum_samples": SAMPLE_RATE if dynamic_samples else window_samples,
            "maximum_samples": SAMPLE_RATE * 10 if dynamic_samples else window_samples,
            "input_dtype": "float32",
            "output": "logits",
            "files": files,
        },
        "runtime": {
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "onnx": onnx.__version__,
            "model_load_seconds": load_seconds,
            "export_seconds": export_seconds,
        },
        "equivalence_verified": False,
        "candidate_frozen": False,
        "product_operating_point": False,
        "blind_human_partition_accessed": False,
        "effects_executed": 0,
    }
    (output_directory / REPORT_FILENAME).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--teacher-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--opset", type=int, default=18)
    parser.add_argument("--window-seconds", type=int, choices=(2, 3, 4), default=2)
    parser.add_argument("--dynamic-samples", action="store_true")
    parser.add_argument("--dynamic-batch", action="store_true")
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = run(
        teacher_directory=arguments.teacher_dir,
        output_directory=arguments.output_dir,
        opset=arguments.opset,
        window_samples=arguments.window_seconds * SAMPLE_RATE,
        dynamic_samples=arguments.dynamic_samples,
        dynamic_batch=arguments.dynamic_batch,
    )
    print(json.dumps(report["runtime"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
