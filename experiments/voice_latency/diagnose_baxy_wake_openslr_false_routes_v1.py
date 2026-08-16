"""Diagnose exact upstream routes for opened OpenSLR wake false activations."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from baxy_mind.wake_cascade import (  # noqa: E402
    load_wake_cascade_candidate_config,
    numpy_log_mel_spectrogram,
    same_window_consensus,
)


def _load(filename: str, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError("wake_false_route_component_invalid")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_REGRESSION = _load(
    "evaluate_baxy_wake_cascade_openslr_regression_v1.py",
    "_wake_false_route_regression_v1",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("wake_false_route_json_invalid")
    return value


def classify_route(
    outputs: list[np.ndarray],
    *,
    primary_threshold: float,
    secondary_threshold: float,
    rescue_alias_index: int | None,
    rescue_alias_threshold: float | None,
) -> str | None:
    if any(
        same_window_consensus(
            values,
            primary_threshold=primary_threshold,
            secondary_threshold=secondary_threshold,
        )
        for values in outputs
    ):
        return "consensus"
    if (
        rescue_alias_index is not None
        and rescue_alias_threshold is not None
        and any(
            np.asarray(values, dtype=np.float32)[rescue_alias_index]
            >= rescue_alias_threshold
            for values in outputs
        )
    ):
        return "single_alias_rescue"
    return None


def diagnose(args: argparse.Namespace) -> dict[str, Any]:
    import onnxruntime as ort

    cascade_path = args.cascade_manifest.resolve(strict=True)
    corpus_path = args.corpus_manifest.resolve(strict=True)
    false_path = args.false_report.resolve(strict=True)
    ffmpeg = args.ffmpeg.resolve(strict=True)
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError("wake_false_route_output_exists")
    config = load_wake_cascade_candidate_config(cascade_path)
    corpus = read_object(corpus_path)
    false_report = read_object(false_path)
    false_hashes = false_report.get("falseActivationAudioSha256")
    records = corpus.get("records")
    if (
        false_report.get("sources", {}).get("corpusManifestSha256")
        != sha256(corpus_path)
        or not isinstance(false_hashes, list)
        or not false_hashes
        or not isinstance(records, list)
    ):
        raise ValueError("wake_false_route_source_invalid")
    selected = {
        str(record.get("sha256")): record
        for record in records
        if isinstance(record, dict) and record.get("sha256") in false_hashes
    }
    if set(selected) != set(false_hashes):
        raise ValueError("wake_false_route_hash_coverage_invalid")
    root = (corpus_path.parent / str(corpus.get("corpus_root") or "")).resolve(
        strict=True
    )
    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    options.inter_op_num_threads = 1
    sessions = [
        ort.InferenceSession(
            str(path), sess_options=options, providers=["CPUExecutionProvider"]
        )
        for path in config.upstream_graph_paths
    ]
    verifier = ort.InferenceSession(
        str(config.verifier_graph_path),
        sess_options=options,
        providers=["CPUExecutionProvider"],
    )
    filters = np.load(config.mel_filters_path, allow_pickle=False).astype(np.float32)
    results: list[dict[str, Any]] = []
    for audio_hash in sorted(false_hashes):
        record = selected[audio_hash]
        path = (root / str(record.get("relative_path") or "")).resolve(strict=True)
        path.relative_to(root)
        if sha256(path) != audio_hash:
            raise ValueError("wake_false_route_audio_hash_invalid")
        audio = _REGRESSION._AUDIO.decode_flac(ffmpeg, path)
        windows = _REGRESSION.window_views(
            _REGRESSION.stream_audio(audio), config.hop_samples
        )
        features = [numpy_log_mel_spectrogram(window, filters) for window in windows]
        upstream = [
            np.concatenate(
                [
                    session.run(["logits"], {"logmel": feature[None]})[0]
                    for feature in features
                ],
                axis=0,
            )
            for session in sessions
        ]
        verifier_scores = np.asarray(
            verifier.run(
                ["wake_logit"], {"logmel": np.stack(features)}
            )[0],
            dtype=np.float32,
        ).reshape(-1)
        candidates = []
        for index in range(len(features)):
            route = classify_route(
                [values[index] for values in upstream],
                primary_threshold=config.primary_threshold,
                secondary_threshold=config.secondary_threshold,
                rescue_alias_index=config.rescue_alias_index,
                rescue_alias_threshold=config.rescue_alias_threshold,
            )
            if route is None:
                continue
            start = max(0, index - config.history_windows + 1)
            score = float(np.max(verifier_scores[start : index + 1]))
            candidates.append(
                {
                    "window": index,
                    "route": route,
                    "verifierScore": score,
                    "accepted": score >= config.verifier_threshold,
                }
            )
        results.append(
            {
                "audioSha256": audio_hash,
                "candidateWindows": len(candidates),
                "acceptedWindows": sum(item["accepted"] for item in candidates),
                "acceptedRoutes": sorted(
                    {item["route"] for item in candidates if item["accepted"]}
                ),
                "maximumAcceptedScore": max(
                    (item["verifierScore"] for item in candidates if item["accepted"]),
                    default=None,
                ),
                "candidates": candidates,
            }
        )
    report = {
        "schema": "baxy.wake-openslr-false-route-diagnostic.v1",
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "cascadeManifestSha256": sha256(cascade_path),
            "corpusManifestSha256": sha256(corpus_path),
            "falseReportSha256": sha256(false_path),
            "selectionCascadeManifestSha256": false_report["sources"].get(
                "cascadeManifestSha256"
            ),
            "ffmpegSha256": sha256(ffmpeg),
        },
        "records": results,
        "transcriptsOrFilenamesRetained": False,
        "developmentOnly": True,
        "effectsExecuted": 0,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cascade-manifest", type=Path, required=True)
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--false-report", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    report = diagnose(parser.parse_args())
    print(
        json.dumps(
            {
                "records": len(report["records"]),
                "accepted": sum(
                    record["acceptedWindows"] for record in report["records"]
                ),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
