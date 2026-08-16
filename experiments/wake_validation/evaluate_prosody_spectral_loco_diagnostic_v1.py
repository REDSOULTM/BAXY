"""Explore whether prosodic/spectral cues generalize across opened wake corpora.

This is a research-only diagnostic.  It performs leave-one-corpus-out (LOCO)
evaluation, selects every operating threshold from the two training corpora,
and never treats a compared model as a promotable candidate.  Results retain
audio hashes and scores, but no filenames or transcript text.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import time
from typing import Any
import wave

import numpy as np


SCHEMA = "baxy.prosody-spectral-loco-diagnostic.v1"
BINDING_SCHEMA = "baxy.prosody-spectral-loco-diagnostic-binding.v1"
FEATURE_DIMENSION = 85


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("prosody_loco_json_object_required")
    return value


def forbid_v17(paths: list[Path]) -> None:
    if any("v17" in str(path).lower() for path in paths):
        raise ValueError("prosody_loco_physical_v17_forbidden")


def safe_corpus_path(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("prosody_loco_manifest_path_escape") from exc
    if candidate.suffix.lower() != ".wav" or not candidate.is_file():
        raise ValueError("prosody_loco_manifest_wav_missing")
    return candidate


def read_pcm16(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as source:
        if source.getnchannels() != 1 or source.getsampwidth() != 2:
            raise ValueError("prosody_loco_pcm16_mono_required")
        sample_rate = source.getframerate()
        values = np.frombuffer(
            source.readframes(source.getnframes()), dtype="<i2"
        ).astype(np.float32)
    if sample_rate != 16_000:
        raise ValueError("prosody_loco_16khz_required")
    return values / 32768.0, sample_rate


def distribution(values: np.ndarray) -> list[float]:
    if not len(values):
        return [0.0] * 7
    return [
        float(np.mean(values)),
        float(np.std(values)),
        *[float(value) for value in np.quantile(values, [0.1, 0.25, 0.5, 0.75, 0.9])],
    ]


def extract_features(values: np.ndarray, sample_rate: int) -> np.ndarray:
    """Return amplitude-normalized rhythm, pitch, and spectral descriptors."""

    from scipy.fft import dct

    if sample_rate != 16_000 or values.ndim != 1 or not len(values):
        raise ValueError("prosody_loco_waveform_invalid")
    values = values.astype(np.float32, copy=False) - float(np.mean(values))
    values = values / (float(np.max(np.abs(values))) + 1e-8)
    frame_size = 400
    hop = 160
    if len(values) < frame_size:
        values = np.pad(values, (0, frame_size - len(values)))
    frames = np.lib.stride_tricks.sliding_window_view(values, frame_size)[::hop].copy()
    windowed = frames * np.hanning(frame_size).astype(np.float32)
    rms = np.sqrt(np.mean(frames * frames, axis=1) + 1e-10)
    log_rms = 20.0 * np.log10(rms + 1e-8)
    speech = log_rms > max(float(np.max(log_rms)) - 30.0, -55.0)
    active = np.flatnonzero(speech)
    if len(active):
        selection = slice(active[0], active[-1] + 1)
        frames = frames[selection]
        windowed = windowed[selection]
        rms = rms[selection]
        log_rms = log_rms[selection]
        speech = speech[selection]

    spectrum = np.abs(np.fft.rfft(windowed, axis=1)) + 1e-8
    frequencies = np.fft.rfftfreq(frame_size, 1.0 / sample_rate)
    normalized_spectrum = spectrum / spectrum.sum(axis=1, keepdims=True)
    centroid = (normalized_spectrum * frequencies).sum(axis=1) / 8000.0
    flatness = np.exp(np.mean(np.log(spectrum), axis=1)) / (
        np.mean(spectrum, axis=1) + 1e-8
    )
    cumulative = np.cumsum(normalized_spectrum, axis=1)
    rolloff = frequencies[np.argmax(cumulative >= 0.85, axis=1)] / 8000.0
    zero_crossing = np.mean(np.abs(np.diff(np.signbit(frames), axis=1)), axis=1)

    power = spectrum * spectrum
    edges = np.linspace(0, len(frequencies) - 1, 27).astype(int)
    bands = [
        np.log(np.mean(power[:, start : max(start + 1, end)], axis=1) + 1e-8)
        for start, end in zip(edges[:-1], edges[1:], strict=True)
    ]
    coefficients = dct(np.stack(bands, axis=1), type=2, norm="ortho", axis=1)[:, 1:13]

    pitches: list[float] = []
    pitch_correlations: list[float] = []
    minimum_lag = int(sample_rate / 400)
    maximum_lag = int(sample_rate / 60)
    for frame, is_active in zip(frames[::2], speech[::2], strict=True):
        if not is_active:
            continue
        centered = frame - float(np.mean(frame))
        correlation = np.correlate(centered, centered, mode="full")[frame_size - 1 :]
        correlation = correlation / (float(correlation[0]) + 1e-8)
        lag = minimum_lag + int(np.argmax(correlation[minimum_lag : maximum_lag + 1]))
        strength = float(correlation[lag])
        pitch_correlations.append(strength)
        if strength >= 0.28:
            pitches.append(math.log(sample_rate / lag))

    active_seconds = len(frames) * hop / sample_rate
    energy_positions = np.arange(len(rms), dtype=np.float64)
    energy_center = float(np.sum(energy_positions * rms) / (np.sum(rms) + 1e-8))
    features = [
        len(values) / sample_rate,
        active_seconds,
        float(np.mean(speech)),
        energy_center * hop / sample_rate / max(active_seconds, 1e-6),
        *distribution(log_rms - float(np.max(log_rms))),
        *distribution(np.diff(log_rms)),
        *distribution(centroid),
        *distribution(flatness),
        *distribution(rolloff),
        *distribution(zero_crossing),
        *distribution(np.asarray(pitches)),
        *distribution(np.asarray(pitch_correlations)),
        len(pitches) / max(1, len(pitch_correlations)),
        *[float(value) for value in np.mean(coefficients, axis=0)],
        *[float(value) for value in np.std(coefficients, axis=0)],
    ]
    result = np.asarray(features, dtype=np.float64)
    if result.shape != (FEATURE_DIMENSION,) or not np.all(np.isfinite(result)):
        raise ValueError("prosody_loco_features_invalid")
    return result


def threshold_above_training_negatives(scores: np.ndarray, labels: np.ndarray) -> float:
    negatives = scores[labels == 0]
    if not len(negatives):
        raise ValueError("prosody_loco_training_negatives_required")
    return float(np.nextafter(float(np.max(negatives)), np.inf))


def _load_records(binding: dict[str, Any]) -> list[dict[str, Any]]:
    corpora = binding.get("corpora")
    if not isinstance(corpora, list) or len(corpora) != 3:
        raise ValueError("prosody_loco_three_corpora_required")
    records: list[dict[str, Any]] = []
    seen_hashes: set[str] = set()
    for corpus in corpora:
        if not isinstance(corpus, dict):
            raise ValueError("prosody_loco_corpus_invalid")
        name = corpus.get("name")
        root = Path(str(corpus.get("root"))).resolve()
        manifest_path = root / "manifest.v1.json"
        expected_hash = corpus.get("manifestSha256")
        expected_counts = corpus.get("counts")
        if (
            not isinstance(name, str)
            or not isinstance(expected_hash, str)
            or not isinstance(expected_counts, dict)
            or sha256(manifest_path) != expected_hash
        ):
            raise ValueError("prosody_loco_corpus_binding_mismatch")
        manifest = read_object(manifest_path)
        if manifest.get("counts") != expected_counts:
            raise ValueError("prosody_loco_manifest_counts_mismatch")
        for raw in manifest.get("records", []):
            if not isinstance(raw, dict):
                raise ValueError("prosody_loco_manifest_record_invalid")
            record_id = raw.get("recordId")
            relative = raw.get("output")
            audio_hash = raw.get("outputSha256")
            if not all(
                isinstance(item, str) for item in (record_id, relative, audio_hash)
            ):
                raise ValueError("prosody_loco_manifest_record_invalid")
            label_name = record_id.split("/", 1)[0]
            if label_name not in {"positive", "negative"} or not relative.replace(
                "\\", "/"
            ).startswith(f"{label_name}/"):
                raise ValueError("prosody_loco_manifest_label_invalid")
            path = safe_corpus_path(root, relative)
            if sha256(path) != audio_hash or audio_hash in seen_hashes:
                raise ValueError("prosody_loco_audio_identity_invalid")
            seen_hashes.add(audio_hash)
            waveform, sample_rate = read_pcm16(path)
            records.append(
                {
                    "corpus": name,
                    "label": 1 if label_name == "positive" else 0,
                    "audioSha256": audio_hash,
                    "features": extract_features(waveform, sample_rate),
                }
            )
    return records


def _models(seed: int) -> dict[str, Any]:
    from sklearn.ensemble import ExtraTreesClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.svm import SVC

    return {
        "logistic_c0p1": make_pipeline(
            StandardScaler(),
            LogisticRegression(
                C=0.1, max_iter=3000, class_weight="balanced", random_state=seed
            ),
        ),
        "logistic_c1": make_pipeline(
            StandardScaler(),
            LogisticRegression(
                C=1.0, max_iter=3000, class_weight="balanced", random_state=seed
            ),
        ),
        "rbf_svc_c1": make_pipeline(
            StandardScaler(),
            SVC(C=1.0, gamma="scale", class_weight="balanced", random_state=seed),
        ),
        "extra_trees": ExtraTreesClassifier(
            n_estimators=500,
            min_samples_leaf=3,
            max_features=0.7,
            class_weight="balanced",
            random_state=seed,
            n_jobs=-1,
        ),
    }


def run(binding_path: Path, output_path: Path) -> dict[str, Any]:
    from sklearn.metrics import roc_auc_score

    binding_path = binding_path.resolve()
    output_path = output_path.resolve()
    forbid_v17([binding_path, output_path])
    if output_path.exists():
        raise ValueError("prosody_loco_output_exists")
    binding = read_object(binding_path)
    if binding.get("schema") != BINDING_SCHEMA:
        raise ValueError("prosody_loco_binding_schema_invalid")
    program_path = Path(__file__).resolve()
    if binding.get("programSha256") != sha256(program_path):
        raise ValueError("prosody_loco_program_hash_mismatch")
    if Path(str(binding.get("plannedOutput"))).resolve() != output_path:
        raise ValueError("prosody_loco_output_binding_mismatch")
    paths = [Path(str(item.get("root"))) for item in binding.get("corpora", [])]
    forbid_v17(paths)

    started = time.perf_counter()
    records = _load_records(binding)
    feature_seconds = time.perf_counter() - started
    values = np.stack([record["features"] for record in records])
    labels = np.asarray([record["label"] for record in records], dtype=np.int64)
    groups = np.asarray([record["corpus"] for record in records])
    seed = int(binding.get("seed"))
    model_results: dict[str, Any] = {}
    for model_name, model in _models(seed).items():
        folds = []
        for held_corpus in sorted(set(groups)):
            training = groups != held_corpus
            held = ~training
            model.fit(values[training], labels[training])
            if hasattr(model, "decision_function"):
                scores = np.asarray(model.decision_function(values), dtype=np.float64)
            else:
                scores = np.asarray(model.predict_proba(values)[:, 1], dtype=np.float64)
            threshold = threshold_above_training_negatives(
                scores[training], labels[training]
            )
            accepted = scores[held] >= threshold
            held_labels = labels[held]
            held_records = [
                record for record, include in zip(records, held, strict=True) if include
            ]
            folds.append(
                {
                    "heldCorpus": held_corpus,
                    "thresholdSelection": "nextafter_maximum_training_negative_score",
                    "threshold": threshold,
                    "positiveAccepted": int(np.sum(accepted & (held_labels == 1))),
                    "positiveFiles": int(np.sum(held_labels == 1)),
                    "negativeFalseActivations": int(
                        np.sum(accepted & (held_labels == 0))
                    ),
                    "negativeFiles": int(np.sum(held_labels == 0)),
                    "auc": float(roc_auc_score(held_labels, scores[held])),
                    "records": [
                        {
                            "audioSha256": record["audioSha256"],
                            "label": "positive" if record["label"] else "negative",
                            "score": float(score),
                            "accepted": bool(decision),
                        }
                        for record, score, decision in zip(
                            held_records, scores[held], accepted, strict=True
                        )
                    ],
                }
            )
        model_results[model_name] = {
            "folds": folds,
            "positiveAccepted": sum(fold["positiveAccepted"] for fold in folds),
            "positiveFiles": sum(fold["positiveFiles"] for fold in folds),
            "negativeFalseActivations": sum(
                fold["negativeFalseActivations"] for fold in folds
            ),
            "negativeFiles": sum(fold["negativeFiles"] for fold in folds),
        }

    result = {
        "schema": SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "opened_development_exploratory_leave_one_corpus_out",
        "bindingSha256": sha256(binding_path),
        "programSha256": sha256(program_path),
        "contract": {
            "featureDimension": FEATURE_DIMENSION,
            "amplitudeNormalized": True,
            "outerEvaluation": "leave_one_complete_corpus_out",
            "thresholdUsesHeldCorpus": False,
            "modelsComparedOnHeldCorpora": True,
            "modelSelectionAllowed": False,
            "physicalV17Read": False,
            "filenamesRetained": False,
            "transcriptTextRetained": False,
        },
        "counts": {
            "records": len(records),
            "positive": int(np.sum(labels == 1)),
            "negative": int(np.sum(labels == 0)),
            "uniqueAudioHashes": len({record["audioSha256"] for record in records}),
        },
        "models": model_results,
        "runtime": {
            "featureExtractionSeconds": feature_seconds,
            "totalSeconds": time.perf_counter() - started,
            "numpy": importlib.metadata.version("numpy"),
            "scipy": importlib.metadata.version("scipy"),
            "scikitLearn": importlib.metadata.version("scikit-learn"),
        },
        "diagnosticPassed": False,
        "candidateFrozen": False,
        "productOperatingPoint": False,
        "freshHoldoutClaimSupported": False,
        "promotionEligible": False,
        "effectsExecuted": 0,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binding", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    result = run(arguments.binding, arguments.output)
    for name, metrics in result["models"].items():
        print(
            "BAXY_PROSODY_LOCO|"
            f"{name}|positive={metrics['positiveAccepted']}/{metrics['positiveFiles']}|"
            f"false={metrics['negativeFalseActivations']}/{metrics['negativeFiles']}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
