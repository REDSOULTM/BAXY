"""Calibrate stage-one consensus on an opened physical RAW corpus.

All ONNX inference is shared across the threshold grid.  The report retains
only record indexes, hashes, logits and decisions; no audio or transcript.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
for path in (ROOT / "src", HERE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import evaluate_baxy_wake_cascade_runtime_raw_v1 as runtime  # noqa: E402
from baxy_mind.wake_cascade import (  # noqa: E402
    EXPECTED_ACOUSTIC_ALIASES,
    WINDOW_SAMPLES,
    load_wake_cascade_candidate_config,
    numpy_log_mel_spectrogram,
)


PRIMARY_GRID = (0.5, 0.4, 0.3, 0.2, 0.1, 0.0, -0.25, -0.5, -1.0)
SECONDARY_GRID = (0.3, 0.2, 0.1, 0.0, -0.25, -0.5, -1.0)


def candidate_index(
    model_logits: list[np.ndarray], *, primary: float, secondary: float
) -> int | None:
    for index, logits in enumerate(model_logits):
        for values in logits:
            ordered = np.sort(np.asarray(values, dtype=np.float32))
            if ordered[-1] >= primary and ordered[-2] >= secondary:
                return index
    return None


def score_group(
    paths: list[Path],
    *,
    mel_filters: np.ndarray,
    upstream_sessions: list[object],
    verifier_session: object,
    hop_samples: int,
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for record_index, path in enumerate(paths):
        audio, sample_rate = runtime.room._read_pcm16(path)
        audio = runtime.room._resample(audio, sample_rate, runtime.SAMPLE_RATE)
        streamed = runtime.stream_audio(audio)
        windows = [
            streamed[end - WINDOW_SAMPLES : end]
            for end in range(WINDOW_SAMPLES, len(streamed) + 1, hop_samples)
        ]
        logmels = np.stack(
            [numpy_log_mel_spectrogram(window, mel_filters) for window in windows]
        ).astype(np.float32)
        model_logits = [
            np.concatenate(
                [
                    np.asarray(
                        session.run(
                            ["logits"], {"logmel": logmel[None, :, :]}
                        )[0],
                        dtype=np.float32,
                    )
                    for logmel in logmels
                ],
                axis=0,
            )
            for session in upstream_sessions
        ]
        if any(
            values.shape != (len(logmels), len(EXPECTED_ACOUSTIC_ALIASES))
            for values in model_logits
        ):
            raise ValueError("baxy_wake_upstream_calibration_logits_invalid")
        verifier = np.asarray(
            verifier_session.run(["wake_logit"], {"logmel": logmels})[0],
            dtype=np.float32,
        ).reshape(-1)
        if len(verifier) != len(logmels) or not np.isfinite(verifier).all():
            raise ValueError("baxy_wake_upstream_calibration_verifier_invalid")
        result.append(
            {
                "record": record_index,
                "audioSha256": runtime.room._sha256(path),
                "windows": len(logmels),
                "modelLogits": [values.tolist() for values in model_logits],
                "verifierPrefixMaximum": np.maximum.accumulate(verifier).tolist(),
            }
        )
    return result


def evaluate_grid(
    positive: list[dict[str, object]],
    negative: list[dict[str, object]],
    *,
    verifier_threshold: float,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for primary in PRIMARY_GRID:
        for secondary in SECONDARY_GRID:
            if secondary > primary:
                continue

            def metrics(records: list[dict[str, object]]) -> tuple[int, int]:
                proposed = 0
                accepted = 0
                for record in records:
                    models = [
                        np.asarray(values, dtype=np.float32)
                        for values in record["modelLogits"]
                    ]
                    per_window = [
                        np.stack([model[index] for model in models])
                        for index in range(len(models[0]))
                    ]
                    index = candidate_index(
                        per_window, primary=primary, secondary=secondary
                    )
                    if index is None:
                        continue
                    proposed += 1
                    prefix = record["verifierPrefixMaximum"]
                    if float(prefix[index]) >= verifier_threshold:
                        accepted += 1
                return proposed, accepted

            positive_proposed, positive_accepted = metrics(positive)
            negative_proposed, negative_accepted = metrics(negative)
            rows.append(
                {
                    "primary": primary,
                    "secondary": secondary,
                    "positiveProposed": positive_proposed,
                    "positiveAccepted": positive_accepted,
                    "negativeProposed": negative_proposed,
                    "negativeAccepted": negative_accepted,
                }
            )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cascade-manifest", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit("Output already exists.")
    config = load_wake_cascade_candidate_config(
        args.cascade_manifest.resolve(strict=True)
    )
    corpus = args.corpus.resolve(strict=True)
    manifest = (corpus / "manifest.v1.json").resolve(strict=True)
    source = json.loads(manifest.read_text(encoding="utf-8"))
    if source.get("blindHumanPartitionAccessed") is not False:
        raise ValueError("baxy_wake_upstream_calibration_corpus_invalid")

    import onnxruntime as ort

    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    options.inter_op_num_threads = 1
    upstream = [
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
    mel = np.asarray(np.load(config.mel_filters_path), dtype=np.float32)
    started = time.perf_counter()
    positive = score_group(
        runtime.room._wav_paths(corpus / "positive", None),
        mel_filters=mel,
        upstream_sessions=upstream,
        verifier_session=verifier,
        hop_samples=config.hop_samples,
    )
    negative = score_group(
        runtime.room._wav_paths(corpus / "negative", None),
        mel_filters=mel,
        upstream_sessions=upstream,
        verifier_session=verifier,
        hop_samples=config.hop_samples,
    )
    grid = evaluate_grid(
        positive, negative, verifier_threshold=config.verifier_threshold
    )
    report = {
        "schema": "baxy.wake-cascade-upstream-raw-calibration.v1",
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "opened_physical_raw_stage1_grid",
        "assets": {
            "cascadeManifestSha256": runtime.room._sha256(
                args.cascade_manifest.resolve(strict=True)
            ),
            "upstreamGraphSha256": list(config.upstream_graph_sha256),
            "logmelVerifierSha256": config.verifier_graph_sha256,
        },
        "corpusManifestSha256": runtime.room._sha256(manifest),
        "contract": {
            "primaryGrid": list(PRIMARY_GRID),
            "secondaryGrid": list(SECONDARY_GRID),
            "verifierThreshold": config.verifier_threshold,
            "historyWindows": config.history_windows,
        },
        "grid": grid,
        "positive": positive,
        "negative": negative,
        "runtimeSeconds": time.perf_counter() - started,
        "blindHumanPartitionAccessed": False,
        "developmentOnly": True,
        "effectsExecuted": 0,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    best = max(
        grid,
        key=lambda row: (
            -int(row["negativeAccepted"]),
            int(row["positiveAccepted"]),
            -int(row["negativeProposed"]),
            float(row["primary"]),
            float(row["secondary"]),
        ),
    )
    print(json.dumps({"best": best, "runtimeSeconds": report["runtimeSeconds"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
