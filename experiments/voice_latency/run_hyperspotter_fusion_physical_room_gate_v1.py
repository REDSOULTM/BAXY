"""Smoke the frozen HyperSpotter/phoneme-CTC wake fusion through the room.

This development gate exists because the fusion candidate consumes a 3-second
log-mel tensor plus a separate CTC model; it is not a LiveKit embedding model.
It therefore must not be passed to ``AcousticWakeDetector`` as though the two
ONNX contracts were interchangeable.  The gate plays explicit source WAVs,
captures an explicit microphone, keeps no captured audio, and never promotes a
runtime asset.  A later blind, statistically sufficient physical gate remains
mandatory before installation.
"""

from __future__ import annotations

import argparse
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
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

import audit_baxy_hyperspotter_fusion_product_candidate_v1 as fusion  # noqa: E402
import run_wakeword_physical_room_gate as room  # noqa: E402
from baxy_mind import wake_verifier as wake  # noqa: E402
from baxy_mind.wakeword import WakeWordDetection, WakeWordRuntimeError  # noqa: E402


REPORT_SCHEMA = "baxy.hyperspotter-fusion-physical-room-development.v1"


@dataclass(frozen=True)
class FusionDetectorConfig:
    hop_samples: int
    debounce_seconds: float
    window_samples: int = fusion.AUDIO_SAMPLES


def _sigmoid(value: float) -> float:
    if value >= 0.0:
        factor = math.exp(-value)
        return 1.0 / (1.0 + factor)
    factor = math.exp(value)
    return factor / (1.0 + factor)


def combined_decision_margin(
    hyper_logits: np.ndarray,
    ctc_margin: float,
    policy: dict[str, float],
) -> float:
    logits = np.asarray(hyper_logits, dtype=np.float64)
    if logits.shape != (1, len(fusion.ALIASES)) or not np.isfinite(logits).all():
        raise WakeWordRuntimeError("wake_fusion_hyper_logits_invalid")
    values = (
        float(policy.get("ctc_center", math.nan)),
        float(policy.get("ctc_scale", math.nan)),
        float(policy.get("ctc_weight", math.nan)),
        float(policy.get("decision_threshold", math.nan)),
        float(ctc_margin),
    )
    if not all(math.isfinite(value) for value in values) or values[1] <= 1e-9:
        raise WakeWordRuntimeError("wake_fusion_policy_invalid")
    center, scale, weight, threshold, margin = values
    combined = float(np.max(logits)) + weight * ((margin - center) / scale)
    return combined - threshold


def _margin_summary(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"scores": 0, "minimum": None, "p50": None, "maximum": None}
    array = np.asarray(values, dtype=np.float64)
    return {
        "scores": len(values),
        "minimum": float(np.min(array)),
        "p50": float(np.percentile(array, 50)),
        "maximum": float(np.max(array)),
    }


class HyperspotterFusionDetector:
    """Rolling CPU detector matching the frozen product-parity audit."""

    def __init__(
        self,
        *,
        fusion_manifest_path: Path,
        ctc_manifest_path: Path,
        model_name: str,
        phrase: str,
        hop_samples: int,
        debounce_seconds: float,
        threads: int,
    ) -> None:
        if not 256 <= hop_samples <= fusion.AUDIO_SAMPLES or not 0.5 <= debounce_seconds <= 10.0:
            raise ValueError("wake_fusion_schedule_invalid")
        if not 1 <= threads <= 32:
            raise ValueError("wake_fusion_threads_invalid")
        candidate = fusion.load_fusion_candidate(
            fusion_manifest_path,
            ctc_manifest_path,
        )
        import onnxruntime as ort

        options = ort.SessionOptions()
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        self._hyper_session = ort.InferenceSession(
            str(candidate["graph_path"]),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        ctc_config = wake.load_wake_verifier_candidate_config(
            candidate["ctc_manifest_path"]
        )
        self._ctc_session = ort.InferenceSession(
            str(ctc_config.graph_path),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        self._verifier = wake.OnnxWakeVerifier(
            ctc_config,
            session=self._ctc_session,
        )
        self._mel_filters = np.asarray(candidate["mel_filters"], dtype=np.float32)
        self._policy = dict(candidate["policy"])
        self._candidate = candidate
        self.model_name = model_name
        self.phrase = phrase
        self.config = FusionDetectorConfig(
            hop_samples=hop_samples,
            debounce_seconds=debounce_seconds,
        )
        self.window_samples = self.config.window_samples
        self._frames: deque[np.ndarray] = deque()
        self._frame_samples = 0
        self._samples_since_score = 0
        self._last_detection_at = float("-inf")
        self.scored_last_frame = False
        self.last_prediction_seconds: float | None = None
        self.last_decision_margin: float | None = None
        self._observed_decision_margins: list[float] = []
        self.reset()
        self._score(np.zeros(self.window_samples, dtype=np.float32))
        self.reset()

    @property
    def backend(self) -> str:
        return "onnxruntime-hyperspotter-phoneme-ctc-fusion"

    @property
    def source_identities(self) -> dict[str, object]:
        candidate = self._candidate
        return {
            "fusionManifestSha256": fusion.sha256(candidate["manifest_path"]),
            "ctcVerifierManifestSha256": fusion.sha256(
                candidate["ctc_manifest_path"]
            ),
            "hyperGraphSha256": fusion.sha256(candidate["graph_path"]),
            "policy": dict(self._policy),
        }

    def reset(self) -> None:
        self._frames.clear()
        self._frame_samples = 0
        self._samples_since_score = 0
        self._last_detection_at = float("-inf")
        self.scored_last_frame = False
        self.last_prediction_seconds = None
        self.last_decision_margin = None

    def drain_decision_margins(self) -> list[float]:
        values = self._observed_decision_margins
        self._observed_decision_margins = []
        return values

    def _score(self, audio: np.ndarray) -> float:
        logmel = fusion.numpy_log_mel_spectrogram(audio, self._mel_filters)
        hyper_logits = self._hyper_session.run(
            ["logits"],
            {"logmel": logmel[None, :, :]},
        )[0]
        normalized = wake.normalize_audio(audio)
        ctc_logits = self._ctc_session.run(
            ["logits"],
            {"input_values": normalized},
        )[0]
        probabilities = wake.compress_category_logits_numpy(
            ctc_logits,
            self._verifier._category_ids,
        )
        ctc_margin = fusion.full_clip_ctc_margin(
            np.log(np.maximum(probabilities, 1e-12)),
            wake,
        )
        return combined_decision_margin(hyper_logits, ctc_margin, self._policy)

    def accept(
        self,
        frame: np.ndarray,
        now: float | None = None,
    ) -> WakeWordDetection | None:
        self.scored_last_frame = False
        audio = np.asarray(frame, dtype=np.float32).reshape(-1)
        if audio.size == 0:
            return None
        owned = np.ascontiguousarray(audio.copy())
        self._frames.append(owned)
        self._frame_samples += owned.size
        self._samples_since_score += owned.size
        while self._frames and self._frame_samples > self.window_samples:
            excess = self._frame_samples - self.window_samples
            oldest = self._frames[0]
            if oldest.size <= excess:
                self._frames.popleft()
                self._frame_samples -= oldest.size
            else:
                self._frames[0] = oldest[excess:]
                self._frame_samples -= excess
        if (
            self._frame_samples < self.window_samples
            or self._samples_since_score < self.config.hop_samples
        ):
            return None
        self._samples_since_score %= self.config.hop_samples
        started = time.perf_counter()
        try:
            decision_margin = self._score(np.concatenate(tuple(self._frames)))
        except WakeWordRuntimeError:
            raise
        except Exception as error:  # noqa: BLE001 - stable experimental code
            raise WakeWordRuntimeError(
                f"wake_fusion_predict_failed:{type(error).__name__}"
            ) from error
        self.last_prediction_seconds = time.perf_counter() - started
        self.last_decision_margin = decision_margin
        self._observed_decision_margins.append(decision_margin)
        self.scored_last_frame = True
        detected_at = time.monotonic() if now is None else float(now)
        if not math.isfinite(detected_at):
            raise WakeWordRuntimeError("wake_fusion_timestamp_invalid")
        if (
            decision_margin < 0.0
            or detected_at - self._last_detection_at < self.config.debounce_seconds
        ):
            return None
        self._last_detection_at = detected_at
        return WakeWordDetection(
            model_name=self.model_name,
            phrase=self.phrase,
            confidence=_sigmoid(decision_margin),
            timestamp=detected_at,
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--physical-output", action="store_true")
    parser.add_argument("--fusion-manifest", type=Path, required=True)
    parser.add_argument("--ctc-verifier-manifest", type=Path, required=True)
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--phrase", default="Baxy")
    parser.add_argument("--positive", type=Path, required=True)
    parser.add_argument("--negative", type=Path, required=True)
    parser.add_argument("--positive-limit", type=room._positive_int)
    parser.add_argument("--negative-limit", type=room._positive_int)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--input-device", type=room._device, required=True)
    parser.add_argument("--output-device", type=room._device, required=True)
    parser.add_argument("--gain", type=room._finite_float, default=0.20)
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
    parser.add_argument("--threads", type=room._positive_int, default=4)
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

    detector = HyperspotterFusionDetector(
        fusion_manifest_path=args.fusion_manifest,
        ctc_manifest_path=args.ctc_verifier_manifest,
        model_name=args.model_name,
        phrase=args.phrase,
        hop_samples=args.hop_samples,
        debounce_seconds=args.debounce_seconds,
        threads=args.threads,
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
    positive_decision_margins = detector.drain_decision_margins()
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
    negative_decision_margins = detector.drain_decision_margins()
    recall = int(positives["matched_files"]) / int(positives["files"])
    negative_hours = float(negatives["audio_seconds"]) / 3600.0
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
        "scope": "explicit_speaker_room_microphone_development_smoke",
        "candidate": detector.source_identities,
        "model": {
            "backend": detector.backend,
            "model": detector.model_name,
            "phrase": detector.phrase,
            "sampleRate": fusion.SAMPLE_RATE,
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
            "minimumPathCorrelation": args.minimum_path_correlation,
            "minimumCapturedSnrDb": args.minimum_captured_snr_db,
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
        "positiveDecisionMargins": _margin_summary(positive_decision_margins),
        "negativeDecisionMargins": _margin_summary(negative_decision_margins),
        "recall": recall,
        "falseActivationsPerHourObserved": (
            false_activations / negative_hours if negative_hours else None
        ),
        "elapsedWallSeconds": time.perf_counter() - started,
        "smokePassed": smoke_passed,
        "promotable": False,
        "promotionBlockedBy": [
            "development_corpus",
            "insufficient_positive_population",
            "insufficient_negative_exposure",
            "blind_human_physical_holdout_not_run",
            "runtime_backend_not_integrated",
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
                "positiveInvalidPaths": positives["invalid_acoustic_paths"],
                "negativeInvalidPaths": negatives["invalid_acoustic_paths"],
            },
            sort_keys=True,
        )
    )
    return 0 if smoke_passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
