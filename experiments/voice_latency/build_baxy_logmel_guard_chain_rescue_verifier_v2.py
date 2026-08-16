"""Fuse a stable wake verifier with a monotonic chain of negative guards."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np


SCHEMA = "baxy.logmel-guard-chain-rescue-verifier.v2"
INPUT_NAME = "logmel"
OUTPUT_NAME = "wake_logit"


def _component() -> Any:
    path = Path(__file__).with_name(
        "build_baxy_logmel_guarded_rescue_verifier_v1.py"
    )
    spec = importlib.util.spec_from_file_location(
        "_baxy_logmel_guarded_rescue_builder_v1", path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("baxy_guard_chain_component_invalid")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_V1 = _component()


def guard_chain_rescue_score(
    base_score: np.ndarray,
    guard_scores: list[np.ndarray],
    *,
    deployment_threshold: float,
    rescue_threshold: float,
) -> np.ndarray:
    base = np.asarray(base_score, dtype=np.float32)
    if (
        not guard_scores
        or not np.isfinite(base).all()
        or not math.isfinite(deployment_threshold)
        or not math.isfinite(rescue_threshold)
        or rescue_threshold <= deployment_threshold
    ):
        raise ValueError("baxy_guard_chain_score_invalid")
    guarded = base
    for value in guard_scores:
        guard = np.asarray(value, dtype=np.float32)
        if guard.shape != base.shape or not np.isfinite(guard).all():
            raise ValueError("baxy_guard_chain_score_invalid")
        guarded = np.minimum(guarded, guard)
    offset = np.float32(rescue_threshold - deployment_threshold)
    return np.maximum(guarded, base - offset)


def build(
    *,
    base_verifier: Path,
    guard_verifiers: list[Path],
    output_directory: Path,
    deployment_threshold: float,
    rescue_threshold: float,
) -> dict[str, Any]:
    if (
        not guard_verifiers
        or not math.isfinite(deployment_threshold)
        or not math.isfinite(rescue_threshold)
        or rescue_threshold <= deployment_threshold
    ):
        raise ValueError("baxy_guard_chain_threshold_invalid")
    base_path = base_verifier.resolve(strict=True)
    guard_paths = [path.resolve(strict=True) for path in guard_verifiers]
    if len({str(path).casefold() for path in guard_paths}) != len(guard_paths):
        raise ValueError("baxy_guard_chain_guard_duplicate")
    output = output_directory.resolve()
    partial = output.with_name(output.name + ".partial")
    if output.exists() or partial.exists():
        raise FileExistsError("baxy_guard_chain_output_exists")
    if any(path.suffix.casefold() != ".onnx" for path in [base_path, *guard_paths]):
        raise ValueError("baxy_guard_chain_asset_invalid")

    import onnx
    from onnx import compose, helper, numpy_helper

    models = [onnx.load(path, load_external_data=False) for path in [base_path, *guard_paths]]
    expected = (1, ("batch", 300, 80), ("batch", 1))
    if any(_V1._contract(model) != expected for model in models):
        raise ValueError("baxy_guard_chain_onnx_contract_invalid")
    versions = [
        (
            model.ir_version,
            tuple((item.domain, item.version) for item in model.opset_import),
        )
        for model in models
    ]
    if len(set(versions)) != 1:
        raise ValueError("baxy_guard_chain_onnx_version_mismatch")

    prefixes = ["base_", *[f"guard_{index}_" for index in range(len(guard_paths))]]
    prefixed = [
        compose.add_prefix(model, prefix)
        for model, prefix in zip(models, prefixes, strict=True)
    ]
    merged = prefixed[0]
    for model in prefixed[1:]:
        merged = compose.merge_models(merged, model, io_map=[])
    input_names = {f"{prefix}{INPUT_NAME}" for prefix in prefixes}
    for node in merged.graph.node:
        for index, name in enumerate(node.input):
            if name in input_names:
                node.input[index] = INPUT_NAME
    del merged.graph.input[:]
    merged.graph.input.extend(
        [
            helper.make_tensor_value_info(
                INPUT_NAME, onnx.TensorProto.FLOAT, ["batch", 300, 80]
            )
        ]
    )
    del merged.graph.output[:]
    merged.graph.output.extend(
        [
            helper.make_tensor_value_info(
                OUTPUT_NAME, onnx.TensorProto.FLOAT, ["batch", 1]
            )
        ]
    )
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
    guarded_inputs = [
        "base_wake_logit",
        *[f"guard_{index}_wake_logit" for index in range(len(guard_paths))],
    ]
    merged.graph.node.extend(
        [
            helper.make_node(
                "Min", guarded_inputs, ["guarded_score"], name="guard_chain_minimum"
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
                name="guard_chain_rescue_maximum",
            ),
        ]
    )
    merged.graph.name = "baxy_logmel_guard_chain_rescue_verifier_v2"
    merged.producer_name = "BAXY"
    merged.producer_version = "2"
    onnx.checker.check_model(merged)

    partial.mkdir(parents=True)
    graph_path = partial / "baxy-logmel-guard-chain-rescue-verifier-v2.onnx"
    onnx.save_model(merged, graph_path)
    report = {
        "schema": SCHEMA,
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "base_verifier_sha256": _V1.sha256(base_path),
            "guard_verifier_sha256": [_V1.sha256(path) for path in guard_paths],
        },
        "contract": {
            "input": {"name": INPUT_NAME, "shape": ["batch", 300, 80]},
            "output": {"name": OUTPUT_NAME, "shape": ["batch", 1]},
            "deployment_threshold": deployment_threshold,
            "rescue_threshold": rescue_threshold,
            "acceptance": (
                "base>=deployment AND "
                "(all_guards>=deployment OR base>=rescue)"
            ),
            "score": (
                "max(min(base,*guards),base-(rescue-deployment))"
            ),
            "monotonic_guard_chain": True,
        },
        "files": {
            "graph": graph_path.name,
            "graph_sha256": _V1.sha256(graph_path),
        },
        "development_only": True,
        "effects_executed": 0,
    }
    (partial / "build.report.v2.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    partial.replace(output)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-verifier", type=Path, required=True)
    parser.add_argument("--guard-verifier", type=Path, action="append", required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--deployment-threshold", type=float, default=3.0)
    parser.add_argument("--rescue-threshold", type=float, required=True)
    arguments = parser.parse_args()
    report = build(
        base_verifier=arguments.base_verifier,
        guard_verifiers=arguments.guard_verifier,
        output_directory=arguments.output_directory,
        deployment_threshold=arguments.deployment_threshold,
        rescue_threshold=arguments.rescue_threshold,
    )
    print(json.dumps(report["files"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
