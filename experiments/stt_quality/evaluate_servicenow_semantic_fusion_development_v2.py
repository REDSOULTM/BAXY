"""Evaluate semantic STT fusion with the measured concurrent-streaming clock.

V1 conservatively but incorrectly treated Nemotron's total streaming CPU time
as serial work after end-of-speech.  The product feeds Nemotron while the user
is speaking.  This evaluator therefore uses its measured endpoint finalization
latency for the secondary arm and keeps Parakeet's offline latency unchanged.
No quality threshold or blind population is changed.
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any


SCHEMA = "baxy.servicenow-codeswitch-semantic-fusion-development.v2"


def _load_v1(repository_root: Path):
    path = (
        repository_root
        / "experiments/stt_quality/evaluate_servicenow_semantic_fusion_development.py"
    )
    specification = importlib.util.spec_from_file_location(
        "baxy_servicenow_semantic_fusion_v1_frozen", path
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("semantic_fusion_v1_import_failed")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def _nearest_rank(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]


def evaluate(arguments: argparse.Namespace) -> dict[str, object]:
    repository_root = arguments.repository_root.resolve(strict=True)
    base = _load_v1(repository_root)
    original_load_source = base._load_source

    def load_with_concurrent_endpoint_clock(
        *, artifact_path: Path, detail_path: Path, engine: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        artifact, detail = original_load_source(
            artifact_path=artifact_path,
            detail_path=detail_path,
            engine=engine,
        )
        if engine != "nemotron_auto":
            return artifact, detail
        endpoint_detail = copy.deepcopy(detail)
        for case in endpoint_detail["cases"]:
            endpoint = case.get("finalizationLatencySeconds")
            maximum_chunk = case.get("maximumChunkDecodeSeconds")
            if endpoint is None or maximum_chunk is None:
                raise RuntimeError("semantic_fusion_streaming_clock_missing")
            if float(endpoint) < 0.0 or float(maximum_chunk) < 0.0:
                raise RuntimeError("semantic_fusion_streaming_clock_invalid")
            case["latencySeconds"] = float(endpoint)
        return artifact, endpoint_detail

    base._load_source = load_with_concurrent_endpoint_clock
    base.SCHEMA = SCHEMA
    # The inherited implementation records and hashes this wrapper, which owns
    # the changed clock semantics, rather than claiming V1 produced V2.
    base.__file__ = str(Path(__file__).resolve(strict=True))
    artifact = base.evaluate(arguments)

    secondary_detail = json.loads(
        arguments.secondary_detail.resolve(strict=True).read_text(encoding="utf-8-sig")
    )
    selected_ids = {
        row["caseId"]
        for row in json.loads(
            arguments.detail_output.resolve(strict=True).read_text(encoding="utf-8")
        )["cases"]
        if row["secondaryTriggered"]
    }
    selected_secondary = [
        row for row in secondary_detail["cases"] if row["caseId"] in selected_ids
    ]
    endpoint_latencies = [
        float(row["finalizationLatencySeconds"]) for row in selected_secondary
    ]
    maximum_chunk_decodes = [
        float(row["maximumChunkDecodeSeconds"]) for row in selected_secondary
    ]
    latency_model = {
        "primary": "parakeet_offline_decode_after_end_of_speech",
        "secondary": "nemotron_streaming_concurrent_with_capture",
        "secondaryFinalizationField": "finalizationLatencySeconds",
        "secondaryTotalCpuTimeExcludedFromEndpointClock": True,
        "selectedCases": len(selected_secondary),
        "secondaryEndpointFinalizationP95Seconds": _nearest_rank(
            endpoint_latencies, 0.95
        ),
        "secondaryMaximumChunkDecodeMaxSeconds": max(
            maximum_chunk_decodes, default=0.0
        ),
        "serialSecondaryDecodeUsed": False,
    }

    detail_path = arguments.detail_output.resolve(strict=True)
    detail = json.loads(detail_path.read_text(encoding="utf-8"))
    detail["latencyModel"] = latency_model
    detail_path.write_text(
        json.dumps(detail, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    predecessor_path = (
        repository_root
        / "artifacts/development/servicenow_codeswitch_semantic_fusion_development_v1.json"
    )
    artifact["latencyModel"] = latency_model
    artifact["predecessor"] = {
        "path": predecessor_path.relative_to(repository_root).as_posix(),
        "sha256": base.sha256(predecessor_path),
        "status": "failed",
        "reason": "secondary_total_streaming_cpu_time_was_counted_as_serial_endpoint_latency",
    }
    artifact["detail"]["sha256"] = base.sha256(detail_path)
    artifact_path = arguments.artifact.resolve()
    artifact_path.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return artifact


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--primary-artifact", type=Path, required=True)
    parser.add_argument("--primary-detail", type=Path, required=True)
    parser.add_argument("--secondary-artifact", type=Path, required=True)
    parser.add_argument("--secondary-detail", type=Path, required=True)
    parser.add_argument("--wordfreq-root", type=Path, required=True)
    parser.add_argument("--detail-output", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    artifact = evaluate(arguments)
    base = _load_v1(arguments.repository_root.resolve(strict=True))
    print(
        json.dumps(
            {
                "artifact": str(arguments.artifact),
                "status": artifact["status"],
                "sha256": base.sha256(arguments.artifact),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
