"""Fit a room-robust QbyT direction from opened development audio.

Every training record is scored in its original form and after deterministic
convolution with a measured non-speech room impulse response.  The candidate
must separate positives from negatives in both views.  This remains opened
development evidence and cannot authorize product wake activation.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
import time
import wave

import numpy as np
from scipy.signal import fftconvolve


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import build_wav2vec2_qbyt_wake_candidate_v1 as base  # noqa: E402
from audit_wav2vec2_hidden_wake_expanded_development_v1 import (  # noqa: E402
    selected_records,
)
from audit_wav2vec2_hidden_wake_product_scan_v1 import (  # noqa: E402
    sliding_vectors,
)
from audit_wav2vec2_hidden_wake_separability_v1 import (  # noqa: E402
    frame_mask,
    normalize_audio,
    pool_hidden,
    read_wav,
    sha256,
)


def read_rir(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as source:
        if (
            source.getnchannels() != 1
            or source.getsampwidth() != 2
            or source.getframerate() != 16_000
        ):
            raise ValueError("wake_qbyt_rir_format_invalid")
        values = np.frombuffer(source.readframes(source.getnframes()), dtype="<i2")
    impulse = values.astype(np.float32) / 32768.0
    if (
        not impulse.size
        or impulse.size > 32_000
        or not np.isfinite(impulse).all()
        or float(np.max(np.abs(impulse))) < 0.1
    ):
        raise ValueError("wake_qbyt_rir_audio_invalid")
    direct_index = int(np.argmax(np.abs(impulse)))
    return impulse, direct_index


def apply_room_impulse_response(audio: np.ndarray, impulse: np.ndarray) -> np.ndarray:
    values = np.asarray(audio, dtype=np.float32).reshape(-1)
    rir = np.asarray(impulse, dtype=np.float32).reshape(-1)
    if (
        not values.size
        or not rir.size
        or not np.isfinite(values).all()
        or not np.isfinite(rir).all()
    ):
        raise ValueError("wake_qbyt_rir_convolution_invalid")
    convolved = fftconvolve(values, rir, mode="full").astype(np.float32)
    return normalize_audio(convolved)


def _view_metrics(
    scores: np.ndarray,
    labels: np.ndarray,
    threshold: float,
) -> dict[str, float | int | bool]:
    values = np.asarray(scores, dtype=np.float64)
    targets = np.asarray(labels, dtype=np.int64)
    positives = values[targets == 1]
    negatives = values[targets == 0]
    if (
        not len(positives)
        or not len(negatives)
        or not np.isfinite(values).all()
    ):
        raise ValueError("wake_qbyt_rir_metrics_invalid")
    positive_accepted = int(np.count_nonzero(positives >= threshold))
    negative_false_accepts = int(np.count_nonzero(negatives >= threshold))
    return {
        "positiveAccepted": positive_accepted,
        "positiveTotal": int(len(positives)),
        "negativeFalseAccepts": negative_false_accepts,
        "negativeTotal": int(len(negatives)),
        "minimumPositiveMargin": float(np.min(positives - threshold)),
        "maximumNegativeMargin": float(np.max(negatives - threshold)),
        "gatePassed": positive_accepted == len(positives)
        and negative_false_accepts == 0,
    }


def fit_multiview_candidate(
    *,
    aligned_positive_vectors: np.ndarray,
    product_vectors: list[np.ndarray],
    labels: np.ndarray,
) -> tuple[np.ndarray, float, np.ndarray, dict[str, object]]:
    targets = np.asarray(labels, dtype=np.int64)
    aligned = base.normalize_rows(aligned_positive_vectors)
    scans = [base.normalize_rows(values) for values in product_vectors]
    positive_records = int(np.count_nonzero(targets == 1))
    if (
        len(scans) != len(targets)
        or set(targets.tolist()) != {0, 1}
        or positive_records < 1
        or len(aligned) < positive_records
        or len(aligned) % positive_records != 0
    ):
        raise ValueError("wake_qbyt_rir_fit_alignment_invalid")
    positive_centroid = base._normalize(aligned.mean(axis=0))
    negative_centroid = base._normalize(
        np.concatenate(
            [
                values
                for values, label in zip(scans, targets, strict=True)
                if label == 0
            ],
            axis=0,
        ).mean(axis=0)
    )
    direction = np.asarray(positive_centroid - negative_centroid, dtype=np.float32)
    scores = np.asarray(
        [float(np.max(values @ direction)) for values in scans],
        dtype=np.float64,
    )
    negative_scores = scores[targets == 0]
    threshold = float(np.nextafter(negative_scores.max(), math.inf))
    metrics = _view_metrics(scores, targets, threshold)
    return direction, threshold, scores, {
        **metrics,
        "developmentFitGatePassed": metrics["gatePassed"],
        "alignedViewsPerPositive": len(aligned) // positive_records,
    }


def build(
    *,
    legacy_manifest_path: Path,
    expanded_manifest_path: Path,
    hidden_sweep_path: Path,
    model_directory: Path,
    room_impulse_path: Path,
    output_path: Path,
    device: str,
) -> dict[str, object]:
    if output_path.exists() or device not in {"cpu", "cuda"}:
        raise ValueError("wake_qbyt_rir_schedule_invalid")
    legacy_manifest_path = legacy_manifest_path.resolve(strict=True)
    expanded_manifest_path = expanded_manifest_path.resolve(strict=True)
    hidden_sweep_path = hidden_sweep_path.resolve(strict=True)
    model_directory = model_directory.resolve(strict=True)
    room_impulse_path = room_impulse_path.resolve(strict=True)
    output_path = output_path.resolve()
    legacy = json.loads(legacy_manifest_path.read_text(encoding="utf-8-sig"))
    expanded = json.loads(expanded_manifest_path.read_text(encoding="utf-8-sig"))
    sweep = json.loads(hidden_sweep_path.read_text(encoding="utf-8-sig"))
    winner = sweep.get("winner") if isinstance(sweep, dict) else None
    if (
        not isinstance(legacy, dict)
        or not isinstance(expanded, dict)
        or sweep.get("schema")
        != "baxy.wav2vec2-hidden-wake-expanded-layer-sweep.v1"
        or not isinstance(winner, dict)
        or winner.get("layer") != 2
        or winner.get("window_offset_seconds") != 0.0
        or winner.get("window_duration_seconds") != 0.9
        or winner.get("pooling") != "max"
        or sweep.get("blind_human_audio_accessed") is not False
    ):
        raise ValueError("wake_qbyt_rir_selection_evidence_invalid")
    records = selected_records(legacy, expanded)
    if (
        len(records) != 30
        or sum(record["label"] == "positive" for record in records) != 18
        or any(record.get("partition") != "development" for record in records)
    ):
        raise ValueError("wake_qbyt_rir_human_boundary_invalid")
    impulse, direct_index = read_rir(room_impulse_path)

    import torch
    from transformers import Wav2Vec2ForCTC

    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("wake_qbyt_rir_cuda_unavailable")
    torch_device = torch.device(device)
    model = Wav2Vec2ForCTC.from_pretrained(
        str(model_directory), local_files_only=True
    ).eval().to(torch_device)
    roots = {
        "legacy": legacy_manifest_path.parent,
        "expanded": expanded_manifest_path.parent,
    }
    clean_vectors: list[np.ndarray] = []
    rir_vectors: list[np.ndarray] = []
    aligned: list[np.ndarray] = []
    labels: list[int] = []
    started = time.perf_counter()
    with torch.inference_mode():
        for record in records:
            path = roots[str(record["corpus"])] / str(
                record["output_relative_path"]
            )
            wav = record.get("wav")
            if not isinstance(wav, dict) or sha256(path) != wav.get("sha256"):
                raise ValueError("wake_qbyt_rir_audio_hash_mismatch")
            original = read_wav(path)
            variants = (
                normalize_audio(original),
                apply_room_impulse_response(original, impulse),
            )
            hidden_variants: list[np.ndarray] = []
            product_variants: list[np.ndarray] = []
            for audio in variants:
                hidden = model.wav2vec2(
                    torch.from_numpy(audio).unsqueeze(0).to(torch_device),
                    output_hidden_states=True,
                ).hidden_states[2][0].detach().float().cpu().numpy()
                hidden_variants.append(hidden)
                vectors, _ = sliding_vectors(
                    hidden,
                    duration_seconds=0.9,
                    pooling="max",
                )
                product_variants.append(vectors)
            clean_vectors.append(product_variants[0])
            rir_vectors.append(product_variants[1])
            positive = record["label"] == "positive"
            labels.append(1 if positive else 0)
            if positive:
                onset = float(record["target_onset_in_clip_seconds"])
                for hidden, delay_seconds in zip(
                    hidden_variants,
                    (0.0, direct_index / 16_000.0),
                    strict=True,
                ):
                    mask = frame_mask(
                        hidden.shape[0],
                        onset_seconds=onset + delay_seconds,
                        offset_seconds=0.0,
                        duration_seconds=0.9,
                    )
                    aligned.append(pool_hidden(hidden, mask, "max"))
    combined_vectors = [
        np.concatenate((clean, augmented), axis=0)
        for clean, augmented in zip(clean_vectors, rir_vectors, strict=True)
    ]
    label_array = np.asarray(labels, dtype=np.int64)
    direction, threshold, _, combined_metrics = fit_multiview_candidate(
        aligned_positive_vectors=np.stack(aligned),
        product_vectors=combined_vectors,
        labels=label_array,
    )
    clean_scores = np.asarray(
        [float(np.max(base.normalize_rows(values) @ direction)) for values in clean_vectors]
    )
    rir_scores = np.asarray(
        [float(np.max(base.normalize_rows(values) @ direction)) for values in rir_vectors]
    )
    clean_metrics = _view_metrics(clean_scores, label_array, threshold)
    rir_metrics = _view_metrics(rir_scores, label_array, threshold)
    gate_passed = bool(
        combined_metrics["developmentFitGatePassed"]
        and clean_metrics["gatePassed"]
        and rir_metrics["gatePassed"]
    )
    report: dict[str, object] = {
        "schema": "baxy.wav2vec2-qbyt-wake-candidate.v3",
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "opened_human_clean_and_measured_room_rir_development_fit",
        "sources": {
            "legacyManifestSha256": sha256(legacy_manifest_path),
            "expandedManifestSha256": sha256(expanded_manifest_path),
            "hiddenSweepSha256": sha256(hidden_sweep_path),
            "roomImpulseResponseSha256": sha256(room_impulse_path),
            "modelWeightsSha256": sha256(model_directory / "pytorch_model.bin"),
            "modelConfigSha256": sha256(model_directory / "config.json"),
        },
        "policy": {
            "layer": 2,
            "windowOffsetSeconds": 0.0,
            "windowDurationSeconds": 0.9,
            "pooling": "max",
            "query": "maximum_20ms_sliding_window_score",
            "threshold": threshold,
            "normalization": "l2_per_window",
        },
        "augmentation": {
            "method": "measured_room_impulse_response_convolution",
            "sampleRate": 16_000,
            "directDelaySeconds": direct_index / 16_000.0,
            "rawRoomCaptureRetained": False,
            "containsSpeech": False,
        },
        "parameters": {"direction": direction.astype(float).tolist()},
        "metrics": {
            "combined": combined_metrics,
            "clean": clean_metrics,
            "roomRir": rir_metrics,
            "developmentFitGatePassed": gate_passed,
        },
        "runtimeSeconds": time.perf_counter() - started,
        "developmentOnly": True,
        "blindHumanAudioAccessed": False,
        "audioOrRecordIdentitiesRetained": False,
        "candidateFrozen": False,
        "productOperatingPoint": False,
        "freshHoldoutClaimSupported": False,
        "effectsExecuted": 0,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-manifest", type=Path, required=True)
    parser.add_argument("--expanded-manifest", type=Path, required=True)
    parser.add_argument("--hidden-sweep", type=Path, required=True)
    parser.add_argument("--model-directory", type=Path, required=True)
    parser.add_argument("--room-impulse", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = build(
        legacy_manifest_path=arguments.legacy_manifest,
        expanded_manifest_path=arguments.expanded_manifest,
        hidden_sweep_path=arguments.hidden_sweep,
        model_directory=arguments.model_directory,
        room_impulse_path=arguments.room_impulse,
        output_path=arguments.output,
        device=arguments.device,
    )
    print(json.dumps(report["metrics"], sort_keys=True))
    return 0 if report["metrics"]["developmentFitGatePassed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
