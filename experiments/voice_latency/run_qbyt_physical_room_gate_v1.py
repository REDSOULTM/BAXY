"""Measure the frozen Wav2Vec2 query-by-template wake verifier in the room.

The QbyT candidate is a development-only secondary guard.  This script tests
whether its score survives speaker/room/microphone distortion.  It does not
grant standalone wake authority, does not retain captured audio, and cannot
produce a promotable product report.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
for path in (ROOT / "src", ROOT / "scripts", HERE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import qbyt_wake_verifier as qbyt  # noqa: E402
import run_hyperspotter_fusion_physical_room_gate_v1 as physical  # noqa: E402
import run_wakeword_physical_room_gate as room  # noqa: E402


REPORT_SCHEMA = "baxy.qbyt-physical-room-development.v1"


def qbyt_decision_margin(score: float, threshold: float) -> float:
    if not np.isfinite(score) or not np.isfinite(threshold):
        raise ValueError("wake_qbyt_score_invalid")
    return float(score - threshold)


class QbyTPhysicalDetector(physical.HyperspotterFusionDetector):
    """Reuse the audited rolling-window schedule with a QbyT scorer."""

    def __init__(
        self,
        *,
        candidate_path: Path,
        model_directory: Path,
        model_name: str,
        phrase: str,
        hop_samples: int,
        debounce_seconds: float,
        device: str,
    ) -> None:
        if not 256 <= hop_samples <= physical.fusion.AUDIO_SAMPLES:
            raise ValueError("wake_qbyt_schedule_invalid")
        if not 0.5 <= debounce_seconds <= 10.0:
            raise ValueError("wake_qbyt_schedule_invalid")
        candidate = qbyt.load_candidate(candidate_path, model_directory)
        self._qbyt_verifier = qbyt.Wav2Vec2QbyTVerifier(
            candidate,
            device=device,
        )
        self._qbyt_candidate = candidate
        self._qbyt_device = device
        self.model_name = model_name
        self.phrase = phrase
        self.config = physical.FusionDetectorConfig(
            hop_samples=hop_samples,
            debounce_seconds=debounce_seconds,
        )
        self.window_samples = self.config.window_samples
        from collections import deque

        self._frames = deque()
        self._frame_samples = 0
        self._samples_since_score = 0
        self._last_detection_at = float("-inf")
        self.scored_last_frame = False
        self.last_prediction_seconds = None
        self.last_decision_margin = None
        self._observed_decision_margins = []
        self.reset()

    @property
    def backend(self) -> str:
        return "wav2vec2-layer2-query-by-template"

    @property
    def source_identities(self) -> dict[str, object]:
        candidate = self._qbyt_candidate
        return {
            "candidateSha256": qbyt.sha256(candidate["path"]),
            "modelWeightsSha256": qbyt.sha256(
                Path(candidate["model_directory"]) / "pytorch_model.bin"
            ),
            "modelConfigSha256": qbyt.sha256(
                Path(candidate["model_directory"]) / "config.json"
            ),
            "layer": candidate["layer"],
            "windowDurationSeconds": candidate["duration"],
            "pooling": candidate["pooling"],
            "scoreThreshold": candidate["threshold"],
            "device": self._qbyt_device,
        }

    def _score(self, audio: np.ndarray) -> float:
        score = self._qbyt_verifier.score(audio)
        return qbyt_decision_margin(
            score,
            float(self._qbyt_candidate["threshold"]),
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--physical-output", action="store_true")
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--model-directory", type=Path, required=True)
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--phrase", default="Baxy")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--positive", type=Path, required=True)
    parser.add_argument("--negative", type=Path, required=True)
    parser.add_argument("--positive-limit", type=room._positive_int)
    parser.add_argument("--negative-limit", type=room._positive_int)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--input-device", type=room._device, required=True)
    parser.add_argument("--output-device", type=room._device, required=True)
    parser.add_argument("--gain", type=room._finite_float, default=0.25)
    parser.add_argument("--pre-roll-seconds", type=room._finite_float, default=0.5)
    parser.add_argument("--post-roll-seconds", type=room._finite_float, default=0.75)
    parser.add_argument(
        "--minimum-path-correlation", type=room._finite_float, default=0.02
    )
    parser.add_argument(
        "--minimum-captured-snr-db", type=room._finite_float, default=3.0
    )
    parser.add_argument("--hop-samples", type=room._positive_int, default=8_000)
    parser.add_argument("--debounce-seconds", type=room._finite_float, default=2.0)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if not args.physical_output:
        raise SystemExit("Refusing acoustic playback without --physical-output.")
    if not 0.01 <= args.gain <= 0.95:
        raise SystemExit("--gain must be between 0.01 and 0.95.")
    output_path = args.output.resolve()
    if output_path.exists():
        raise SystemExit("Output already exists.")
    positive_root = args.positive.resolve(strict=True)
    negative_root = args.negative.resolve(strict=True)
    positive_paths = room._wav_paths(positive_root, args.positive_limit)
    negative_paths = room._wav_paths(negative_root, args.negative_limit)
    if not positive_paths or not negative_paths:
        raise SystemExit("Both physical corpus groups require WAV files.")

    detector = QbyTPhysicalDetector(
        candidate_path=args.candidate,
        model_directory=args.model_directory,
        model_name=args.model_name,
        phrase=args.phrase,
        hop_samples=args.hop_samples,
        debounce_seconds=args.debounce_seconds,
        device=args.device,
    )
    import sounddevice as sd

    hardware_rate = room._resolve_hardware_rate(
        sd,
        args.input_device,
        args.output_device,
    )
    input_info = sd.query_devices(args.input_device, "input")
    output_info = sd.query_devices(args.output_device, "output")
    started = time.perf_counter()
    positives, timeline = room._measure_group(
        paths=positive_paths,
        detector=detector,
        sounddevice=sd,
        input_device=args.input_device,
        output_device=args.output_device,
        hardware_rate=hardware_rate,
        gain=args.gain,
        pre_roll_seconds=args.pre_roll_seconds,
        post_roll_seconds=args.post_roll_seconds,
        minimum_correlation=args.minimum_path_correlation,
        minimum_snr_db=args.minimum_captured_snr_db,
        timeline=0.0,
    )
    positive_margins = detector.drain_decision_margins()
    negatives, _ = room._measure_group(
        paths=negative_paths,
        detector=detector,
        sounddevice=sd,
        input_device=args.input_device,
        output_device=args.output_device,
        hardware_rate=hardware_rate,
        gain=args.gain,
        pre_roll_seconds=args.pre_roll_seconds,
        post_roll_seconds=args.post_roll_seconds,
        minimum_correlation=args.minimum_path_correlation,
        minimum_snr_db=args.minimum_captured_snr_db,
        timeline=timeline,
    )
    negative_margins = detector.drain_decision_margins()
    recall = int(positives["matched_files"]) / int(positives["files"])
    false_activations = int(negatives["activations"])
    smoke_passed = (
        int(positives["invalid_acoustic_paths"]) == 0
        and int(negatives["invalid_acoustic_paths"]) == 0
        and int(positives["matched_files"]) > 0
        and false_activations == 0
    )
    report: dict[str, Any] = {
        "schema": REPORT_SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "explicit_speaker_room_microphone_qbyt_development_smoke",
        "candidate": detector.source_identities,
        "model": {
            "backend": detector.backend,
            "model": detector.model_name,
            "phrase": detector.phrase,
            "sampleRate": 16_000,
            "windowSamples": detector.window_samples,
            "hopSamples": detector.config.hop_samples,
            "debounceSeconds": detector.config.debounce_seconds,
        },
        "physicalPath": {
            "topology": "explicit speaker -> room -> explicit microphone",
            "inputDevice": str(input_info["name"]),
            "outputDevice": str(output_info["name"]),
            "hardwareSampleRate": hardware_rate,
            "playbackGain": args.gain,
            "capturedAudioRetained": False,
        },
        "corpus": {
            "positiveFiles": len(positive_paths),
            "negativeFiles": len(negative_paths),
            "positiveSha256": room._corpus_sha256(positive_paths, positive_root),
            "negativeSha256": room._corpus_sha256(negative_paths, negative_root),
            "filenamesOrTranscriptsRetained": False,
        },
        "positive": positives,
        "negative": negatives,
        "positiveDecisionMargins": physical._margin_summary(positive_margins),
        "negativeDecisionMargins": physical._margin_summary(negative_margins),
        "recall": recall,
        "falseActivations": false_activations,
        "elapsedWallSeconds": time.perf_counter() - started,
        "smokePassed": smoke_passed,
        "standaloneAuthorityClaimSupported": False,
        "promotable": False,
        "promotionBlockedBy": [
            "development_corpus",
            "secondary_guard_evaluated_outside_full_pipeline",
            "insufficient_positive_population",
            "insufficient_negative_exposure",
            "blind_human_physical_holdout_not_run",
        ],
        "effectsExecuted": 0,
        "developmentOnly": True,
        "capturedAudioRetained": False,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "smokePassed": smoke_passed,
                "recall": recall,
                "falseActivations": false_activations,
                "positiveMaximumMargin": report["positiveDecisionMargins"]["maximum"],
                "negativeMaximumMargin": report["negativeDecisionMargins"]["maximum"],
            },
            sort_keys=True,
        )
    )
    return 0 if smoke_passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
