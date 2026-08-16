"""Assemble one immutable, hash-bound two-stage wake candidate bundle."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile


SAMPLE_RATE = 16_000
WINDOW_SAMPLES = 32_000
HOP_SAMPLES = 2_560
DEBOUNCE_SECONDS = 2.0
PRE_ROLL_SECONDS = 5.0
BROAD_THRESHOLD = 0.0175
STRONG_THRESHOLD = 0.035
VERIFICATION_SAMPLES = 48_000
MAXIMUM_TURN_SAMPLES = 480_000
PRIMARY_VIEW_START_SAMPLES = 64_000
ACTIVITY_LOOKBACK_SAMPLES = 2_560
ACTIVITY_ALIGNMENT_SAMPLES = 320
ACTIVITY_VAD_THRESHOLD = 0.1


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def hardlink(source: Path, destination: Path) -> None:
    source = source.resolve(strict=True)
    if not source.is_file() or destination.exists():
        raise ValueError("wake_candidate_asset_invalid")
    os.link(source, destination)


def assemble(
    *,
    stage1_model: Path,
    verifier_graph: Path,
    vocabulary: Path,
    output_directory: Path,
) -> dict[str, object]:
    stage1_model = stage1_model.resolve(strict=True)
    verifier_graph = verifier_graph.resolve(strict=True)
    vocabulary = vocabulary.resolve(strict=True)
    graph_data = verifier_graph.with_name(verifier_graph.name + ".data").resolve(
        strict=True
    )
    output_directory = output_directory.resolve()
    output_directory.parent.mkdir(parents=True, exist_ok=True)
    if output_directory.exists():
        raise FileExistsError(f"wake_candidate_output_exists:{output_directory}")
    temporary = Path(
        tempfile.mkdtemp(
            prefix=f".{output_directory.name}.", dir=output_directory.parent
        )
    )
    try:
        sources = (stage1_model, verifier_graph, graph_data, vocabulary)
        destinations = tuple(temporary / source.name for source in sources)
        if len({destination.name.casefold() for destination in destinations}) != len(
            destinations
        ):
            raise ValueError("wake_candidate_asset_name_collision")
        for source, destination in zip(sources, destinations, strict=True):
            hardlink(source, destination)
        stage1_target, graph_target, data_target, vocabulary_target = destinations
        hashes = {
            "stage1_model_sha256": sha256(stage1_target),
            "graph_sha256": sha256(graph_target),
            "graph_data_sha256": sha256(data_target),
            "vocabulary_sha256": sha256(vocabulary_target),
        }
        wake_manifest = {
            "schema": "baxy-wakeword-v1",
            "sampleRate": SAMPLE_RATE,
            "windowSamples": WINDOW_SAMPLES,
            "modelName": "baxy",
            "phrase": "Baxy",
            "model": stage1_target.name,
            "sha256": hashes["stage1_model_sha256"],
            "hopSamples": HOP_SAMPLES,
            "debounceSeconds": DEBOUNCE_SECONDS,
            "threshold": STRONG_THRESHOLD,
            "calibration": {"approved": False},
        }
        verifier_manifest = {
            "schema": "baxy-wake-verifier-v1",
            "backend": "onnxruntime-phoneme-ctc",
            "graph": graph_target.name,
            "graphData": data_target.name,
            "vocabulary": vocabulary_target.name,
            "graphSha256": hashes["graph_sha256"],
            "graphDataSha256": hashes["graph_data_sha256"],
            "vocabularySha256": hashes["vocabulary_sha256"],
            "stage1ModelSha256": hashes["stage1_model_sha256"],
            "stage1Phrase": "Baxy",
            "stage1HopSamples": HOP_SAMPLES,
            "stage1DebounceSeconds": DEBOUNCE_SECONDS,
            "stage1PreRollSeconds": PRE_ROLL_SECONDS,
            "primaryViewStartSamples": PRIMARY_VIEW_START_SAMPLES,
            "activityLookbackSamples": ACTIVITY_LOOKBACK_SAMPLES,
            "activityAlignmentSamples": ACTIVITY_ALIGNMENT_SAMPLES,
            "activityVadThreshold": ACTIVITY_VAD_THRESHOLD,
            "sampleRate": SAMPLE_RATE,
            "minimumSamples": SAMPLE_RATE,
            "maximumSamples": VERIFICATION_SAMPLES,
            "maximumTurnSamples": MAXIMUM_TURN_SAMPLES,
            "broadThreshold": BROAD_THRESHOLD,
            "strongThreshold": STRONG_THRESHOLD,
            "decisionMargin": 0.3,
            "anchorMargin": 0.5,
            "calibration": {"approved": False},
        }
        wake_manifest_path = temporary / "baxy-wakeword-v1.json"
        verifier_manifest_path = temporary / "baxy-wake-verifier-v1.json"
        write_json(wake_manifest_path, wake_manifest)
        write_json(verifier_manifest_path, verifier_manifest)
        report: dict[str, object] = {
            "schema": "baxy.wake-verifier-candidate-bundle.v1",
            "assembled_at_utc": datetime.now(timezone.utc).isoformat(),
            "assets": {
                **hashes,
                "wake_manifest_sha256": sha256(wake_manifest_path),
                "verifier_manifest_sha256": sha256(verifier_manifest_path),
            },
            "contract": {
                "sample_rate": SAMPLE_RATE,
                "window_samples": WINDOW_SAMPLES,
                "hop_samples": HOP_SAMPLES,
                "audio_frame_samples": 512,
                "debounce_seconds": DEBOUNCE_SECONDS,
                "pre_roll_seconds": PRE_ROLL_SECONDS,
                "primary_view_start_samples": PRIMARY_VIEW_START_SAMPLES,
                "activity_lookback_samples": ACTIVITY_LOOKBACK_SAMPLES,
                "activity_alignment_samples": ACTIVITY_ALIGNMENT_SAMPLES,
                "activity_vad_threshold": ACTIVITY_VAD_THRESHOLD,
                "broad_threshold": BROAD_THRESHOLD,
                "strong_threshold": STRONG_THRESHOLD,
                "verification_samples": VERIFICATION_SAMPLES,
                "maximum_turn_samples": MAXIMUM_TURN_SAMPLES,
                "decision_margin": 0.3,
                "anchor_margin": 0.5,
            },
            "candidate_frozen": False,
            "blind_human_partition_accessed": False,
            "negative_holdout_scored": False,
            "effects_executed": 0,
        }
        write_json(temporary / "candidate.bundle.v1.json", report)
        temporary.rename(output_directory)
        return report
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage1-model", type=Path, required=True)
    parser.add_argument("--verifier-graph", type=Path, required=True)
    parser.add_argument("--vocabulary", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = assemble(
        stage1_model=arguments.stage1_model,
        verifier_graph=arguments.verifier_graph,
        vocabulary=arguments.vocabulary,
        output_directory=arguments.output_directory,
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
