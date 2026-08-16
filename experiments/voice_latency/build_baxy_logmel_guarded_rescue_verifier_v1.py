"""Fuse a stable wake verifier with a negative guard and bounded rescue."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np


SCHEMA = "baxy.logmel-guarded-rescue-verifier.v1"
INPUT_NAME = "logmel"
OUTPUT_NAME = "wake_logit"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def guarded_rescue_score(
    base_score: np.ndarray,
    guard_score: np.ndarray,
    *,
    deployment_threshold: float,
    rescue_threshold: float,
) -> np.ndarray:
    """Return a score whose deployment cut implements the exact policy."""

    base = np.asarray(base_score, dtype=np.float32)
    guard = np.asarray(guard_score, dtype=np.float32)
    if (
        base.shape != guard.shape
        or not np.isfinite(base).all()
        or not np.isfinite(guard).all()
        or not math.isfinite(deployment_threshold)
        or not math.isfinite(rescue_threshold)
        or rescue_threshold <= deployment_threshold
    ):
        raise ValueError("baxy_guarded_rescue_score_invalid")
    rescue_offset = np.float32(rescue_threshold - deployment_threshold)
    return np.maximum(np.minimum(base, guard), base - rescue_offset)


def _contract(model: Any) -> tuple[int, tuple[object, ...], tuple[object, ...]]:
    graph = model.graph
    if len(graph.input) != 1 or len(graph.output) != 1:
        raise ValueError("baxy_guarded_rescue_onnx_contract_invalid")

    def shape(value: Any) -> tuple[object, ...]:
        dimensions = value.type.tensor_type.shape.dim
        return tuple(
            dimension.dim_value
            if dimension.HasField("dim_value")
            else dimension.dim_param
            for dimension in dimensions
        )

    return graph.input[0].type.tensor_type.elem_type, shape(graph.input[0]), shape(
        graph.output[0]
    )


def build(
    *,
    base_verifier: Path,
    guard_verifier: Path,
    output_directory: Path,
    deployment_threshold: float,
    rescue_threshold: float,
) -> dict[str, Any]:
    if (
        not math.isfinite(deployment_threshold)
        or not math.isfinite(rescue_threshold)
        or rescue_threshold <= deployment_threshold
    ):
        raise ValueError("baxy_guarded_rescue_threshold_invalid")
    base_path = base_verifier.resolve(strict=True)
    guard_path = guard_verifier.resolve(strict=True)
    output = output_directory.resolve()
    partial = output.with_name(output.name + ".partial")
    if output.exists() or partial.exists():
        raise FileExistsError("baxy_guarded_rescue_output_exists")
    if base_path.suffix.casefold() != ".onnx" or guard_path.suffix.casefold() != ".onnx":
        raise ValueError("baxy_guarded_rescue_asset_invalid")

    import onnx
    from onnx import compose, helper, numpy_helper

    base = onnx.load(base_path, load_external_data=False)
    guard = onnx.load(guard_path, load_external_data=False)
    expected = (1, ("batch", 300, 80), ("batch", 1))
    if _contract(base) != expected or _contract(guard) != expected:
        raise ValueError("baxy_guarded_rescue_onnx_contract_invalid")
    if (
        base.ir_version != guard.ir_version
        or [(item.domain, item.version) for item in base.opset_import]
        != [(item.domain, item.version) for item in guard.opset_import]
    ):
        raise ValueError("baxy_guarded_rescue_onnx_version_mismatch")

    base = compose.add_prefix(base, "base_")
    guard = compose.add_prefix(guard, "guard_")
    merged = compose.merge_models(base, guard, io_map=[])
    for node in merged.graph.node:
        for index, name in enumerate(node.input):
            if name in {"base_logmel", "guard_logmel"}:
                node.input[index] = INPUT_NAME

    input_value = helper.make_tensor_value_info(
        INPUT_NAME, onnx.TensorProto.FLOAT, ["batch", 300, 80]
    )
    output_value = helper.make_tensor_value_info(
        OUTPUT_NAME, onnx.TensorProto.FLOAT, ["batch", 1]
    )
    del merged.graph.input[:]
    merged.graph.input.extend([input_value])
    del merged.graph.output[:]
    merged.graph.output.extend([output_value])
    offset_name = "rescue_offset"
    merged.graph.initializer.extend(
        [
            numpy_helper.from_array(
                np.asarray(
                    rescue_threshold - deployment_threshold, dtype=np.float32
                ),
                name=offset_name,
            )
        ]
    )
    merged.graph.node.extend(
        [
            helper.make_node(
                "Min",
                ["base_wake_logit", "guard_wake_logit"],
                ["guarded_score"],
                name="guarded_minimum",
            ),
            helper.make_node(
                "Sub",
                ["base_wake_logit", offset_name],
                ["rescue_score"],
                name="bounded_rescue_shift",
            ),
            helper.make_node(
                "Max",
                ["guarded_score", "rescue_score"],
                [OUTPUT_NAME],
                name="guarded_rescue_maximum",
            ),
        ]
    )
    merged.graph.name = "baxy_logmel_guarded_rescue_verifier_v1"
    merged.producer_name = "BAXY"
    merged.producer_version = "1"
    onnx.checker.check_model(merged)

    partial.mkdir(parents=True)
    graph_path = partial / "baxy-logmel-guarded-rescue-verifier-v1.onnx"
    onnx.save_model(merged, graph_path)
    report = {
        "schema": SCHEMA,
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "base_verifier_sha256": sha256(base_path),
            "guard_verifier_sha256": sha256(guard_path),
        },
        "contract": {
            "input": {"name": INPUT_NAME, "shape": ["batch", 300, 80]},
            "output": {"name": OUTPUT_NAME, "shape": ["batch", 1]},
            "deployment_threshold": deployment_threshold,
            "rescue_threshold": rescue_threshold,
            "acceptance": (
                "base>=deployment AND "
                "(guard>=deployment OR base>=rescue)"
            ),
            "score": "max(min(base,guard),base-(rescue-deployment))",
        },
        "files": {
            "graph": graph_path.name,
            "graph_sha256": sha256(graph_path),
        },
        "development_only": True,
        "effects_executed": 0,
    }
    (partial / "build.report.v1.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    partial.replace(output)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-verifier", type=Path, required=True)
    parser.add_argument("--guard-verifier", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--deployment-threshold", type=float, default=3.0)
    parser.add_argument("--rescue-threshold", type=float, required=True)
    arguments = parser.parse_args()
    report = build(
        base_verifier=arguments.base_verifier,
        guard_verifier=arguments.guard_verifier,
        output_directory=arguments.output_directory,
        deployment_threshold=arguments.deployment_threshold,
        rescue_threshold=arguments.rescue_threshold,
    )
    print(json.dumps(report["files"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
