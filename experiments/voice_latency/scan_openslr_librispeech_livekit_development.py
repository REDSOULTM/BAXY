"""Run the product-equivalent LiveKit proposal scan on LibriSpeech dev-clean."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
import time

import numpy as np


SAMPLE_RATE = 16_000
WINDOW_SECONDS = 2.0
STEP_SECONDS = 0.25
OVERLAP_EXACT_RESCORE_GUARD = 0.005


class BatchedLiveKitPredictor:
    """Exact LiveKit frontend/classifier math with batched ONNX calls."""

    def __init__(
        self,
        model_path: Path,
        batch_size: int = 32,
        mel_batch_model_path: Path | None = None,
        mel_overlap_raw_path: Path | None = None,
        mel_overlap_post_path: Path | None = None,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("livekit_batch_size_invalid")
        import onnxruntime as ort
        from livekit.wakeword.models.feature_extractor import (
            MelSpectrogramFrontend,
            SpeechEmbedding,
        )
        from livekit.wakeword.resources import (
            get_embedding_model_path,
            get_mel_model_path,
        )

        self.batch_size = batch_size
        self.mel_path = get_mel_model_path().resolve(strict=True)
        self.embedding_path = get_embedding_model_path().resolve(strict=True)
        self._mel = MelSpectrogramFrontend(self.mel_path)
        self._embedding = SpeechEmbedding(self.embedding_path)
        self.mel_batch_path = (
            mel_batch_model_path.resolve(strict=True)
            if mel_batch_model_path is not None
            else None
        )
        self._mel_batch_session = None
        self._mel_batch_input_name = None
        if self.mel_batch_path is not None:
            self._mel_batch_session = ort.InferenceSession(
                str(self.mel_batch_path), providers=["CPUExecutionProvider"]
            )
            self._mel_batch_input_name = self._mel_batch_session.get_inputs()[
                0
            ].name
        if (mel_overlap_raw_path is None) != (mel_overlap_post_path is None):
            raise ValueError("livekit_mel_overlap_contract_incomplete")
        self.mel_overlap_raw_path = (
            mel_overlap_raw_path.resolve(strict=True)
            if mel_overlap_raw_path is not None
            else None
        )
        self.mel_overlap_post_path = (
            mel_overlap_post_path.resolve(strict=True)
            if mel_overlap_post_path is not None
            else None
        )
        self._mel_overlap_raw_session = None
        self._mel_overlap_post_session = None
        if self.mel_overlap_raw_path is not None:
            assert self.mel_overlap_post_path is not None
            self._mel_overlap_raw_session = ort.InferenceSession(
                str(self.mel_overlap_raw_path), providers=["CPUExecutionProvider"]
            )
            self._mel_overlap_post_session = ort.InferenceSession(
                str(self.mel_overlap_post_path), providers=["CPUExecutionProvider"]
            )
        self._classifier = ort.InferenceSession(
            str(model_path), providers=["CPUExecutionProvider"]
        )
        self._input_name = self._classifier.get_inputs()[0].name
        self.embedding_windows_total = 0
        self.embedding_windows_unique = 0
        self.overlap_windows_scored = 0
        self.exact_rescore_windows = 0

    @property
    def overlap_acceleration_active(self) -> bool:
        return self._mel_overlap_raw_session is not None

    @staticmethod
    def _embedding_windows(mel: np.ndarray) -> np.ndarray:
        """Flatten LiveKit's exact 16 overlapping 76-frame windows."""

        values = np.asarray(mel, dtype=np.float32)
        if values.ndim != 3 or values.shape[1:] != (197, 32):
            raise ValueError(f"livekit_mel_batch_shape_invalid:{values.shape}")
        indices = np.arange(16)[:, None] * 8 + np.arange(76)[None, :]
        return np.ascontiguousarray(
            values[:, indices, :].reshape(len(values) * 16, 76, 32)
        )

    def extract_features(self, windows: np.ndarray) -> np.ndarray:
        """Return the exact 16x96 product embeddings for each audio window."""
        values = np.asarray(windows, dtype=np.float32)
        if values.ndim != 2 or values.shape[1] != round(
            WINDOW_SECONDS * SAMPLE_RATE
        ):
            raise ValueError(f"livekit_window_batch_shape_invalid:{values.shape}")
        features = []
        for start in range(0, len(values), self.batch_size):
            chunk = values[start : start + self.batch_size]
            if self._mel_batch_session is None:
                mel = self._mel(chunk)
                features.append(self._features_from_mel(mel))
                continue
            # LiveKit 0.2.1's wrappers iterate over the audio batch even
            # though both bundled ONNX graphs expose a dynamic batch axis.
            # The supplied graph changes amplitude-to-dB's global ReduceMax
            # into a per-example reduction and is accepted only after an
            # external exact-equivalence report has been produced.
            assert self._mel_batch_input_name is not None
            raw_mel = self._mel_batch_session.run(
                None, {self._mel_batch_input_name: chunk}
            )[0]
            if raw_mel.shape != (len(chunk), 1, 197, 32):
                raise ValueError(
                    f"livekit_raw_mel_batch_shape_invalid:{raw_mel.shape}"
                )
            mel = raw_mel[:, 0, :, :] / np.float32(10.0) + np.float32(2.0)
            features.append(self._features_from_mel(mel))
        output = np.concatenate(features)
        if output.shape != (len(values), 16, 96):
            raise ValueError(f"livekit_feature_batch_shape_invalid:{output.shape}")
        return output

    def _features_from_mel(
        self, mel: np.ndarray, *, deduplicate: bool = False
    ) -> np.ndarray:
        embedding_windows = self._embedding_windows(mel)
        inverse: np.ndarray | None = None
        if deduplicate:
            unique: list[np.ndarray] = []
            locations: dict[bytes, int] = {}
            indices = []
            for window in embedding_windows:
                key = window.tobytes()
                location = locations.get(key)
                if location is None:
                    location = len(unique)
                    locations[key] = location
                    unique.append(window)
                indices.append(location)
            inverse = np.asarray(indices, dtype=np.int64)
            embedding_windows = np.ascontiguousarray(np.stack(unique))
            self.embedding_windows_total += len(indices)
            self.embedding_windows_unique += len(unique)
        embedding_parts = []
        # Keep LiveKit's physical embedding batch; larger batches are
        # equivalent but slower on the reference CPU.
        for start in range(0, len(embedding_windows), 16):
            embedding_parts.append(self._embedding(embedding_windows[start : start + 16]))
        embeddings = np.concatenate(embedding_parts)
        if inverse is not None:
            embeddings = embeddings[inverse]
        return embeddings.reshape(len(mel), 16, 96).astype(np.float32, copy=False)

    def predict_features(self, features: np.ndarray) -> np.ndarray:
        values = np.asarray(features, dtype=np.float32)
        if values.ndim != 3 or values.shape[1:] != (16, 96):
            raise ValueError(f"livekit_classifier_feature_shape_invalid:{values.shape}")
        scores = []
        for start in range(0, len(values), self.batch_size):
            classifier_input = values[start : start + self.batch_size]
            scores.append(
                np.asarray(
                    self._classifier.run(
                        None, {self._input_name: classifier_input}
                    )[0]
                ).reshape(-1)
            )
        return np.concatenate(scores).astype(np.float64)

    def predict_windows(self, windows: np.ndarray) -> np.ndarray:
        return self.predict_features(self.extract_features(windows))

    def predict_overlapping_windows(
        self, padded: np.ndarray, ends: list[int], window_samples: int
    ) -> np.ndarray:
        """Reuse exact linear mel frames across the runtime's overlapping windows."""

        if self._mel_overlap_raw_session is None:
            windows = np.stack(
                [padded[end - window_samples : end] for end in ends]
            )
            return self.predict_windows(windows)
        assert self._mel_overlap_post_session is not None
        if not ends or window_samples != 32_000:
            raise ValueError("livekit_overlap_window_schedule_invalid")
        windows = [np.asarray(padded[ends[0] - window_samples : ends[0]])]
        raw_input = self._mel_overlap_raw_session.get_inputs()[0].name
        first_raw = self._mel_overlap_raw_session.run(
            None, {raw_input: windows[0][None, :]}
        )[0]
        raw_windows = [first_raw]
        if len(ends) > 1:
            deltas = np.diff(ends[1:])
            if (len(deltas) and not np.all(deltas == 2_560)) or any(
                (end - ends[1]) % 160 for end in ends[1:]
            ):
                raise ValueError("livekit_overlap_hop_schedule_invalid")
            segment = np.asarray(
                padded[ends[1] - window_samples : ends[-1]], dtype=np.float32
            )
            raw = self._mel_overlap_raw_session.run(
                None, {raw_input: segment[None, :]}
            )[0]
            raw_windows.extend(
                raw[:, :, index * 16 : index * 16 + 197, :]
                for index in range(len(ends) - 1)
            )
        combined = np.concatenate(raw_windows)
        if combined.shape != (len(ends), 1, 197, 32):
            raise ValueError(
                f"livekit_overlap_raw_shape_invalid:{combined.shape}"
            )
        post_input = self._mel_overlap_post_session.get_inputs()[0].name
        post = np.concatenate(
            [
                self._mel_overlap_post_session.run(
                    None, {post_input: combined[start : start + self.batch_size]}
                )[0]
                for start in range(0, len(combined), self.batch_size)
            ]
        )
        mel = post[:, 0, :, :] / np.float32(10.0) + np.float32(2.0)
        self.overlap_windows_scored += len(ends)
        return self.predict_features(
            self._features_from_mel(mel, deduplicate=True)
        )

    def rescore_windows_exact(
        self, padded: np.ndarray, ends: list[int], indices: list[int], window_samples: int
    ) -> np.ndarray:
        windows = np.stack(
            [
                padded[ends[index] - window_samples : ends[index]]
                for index in indices
            ]
        )
        self.exact_rescore_windows += len(indices)
        return self.predict_windows(windows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"json_root_is_not_object:{path}")
    return value


def streaming_scores(
    model: object,
    audio: np.ndarray,
    *,
    retention_threshold: float,
    hop_samples: int | None = None,
    frame_samples: int | None = None,
) -> dict[str, object]:
    """Score exact 2 s/250 ms product windows and retain the useful tail."""

    if not 0.0 < retention_threshold < 1.0:
        raise ValueError("livekit_retention_threshold_invalid")
    window_samples = round(WINDOW_SECONDS * SAMPLE_RATE)
    step_samples = round(STEP_SECONDS * SAMPLE_RATE)
    flattened = np.asarray(audio, dtype=np.float32).reshape(-1)
    padded = np.concatenate(
        [
            np.zeros(window_samples, np.float32),
            flattened,
            np.zeros(window_samples, np.float32),
        ]
    )
    if (hop_samples is None) != (frame_samples is None):
        raise ValueError("livekit_runtime_schedule_incomplete")
    maximum = -math.inf
    maximum_end = 0.0
    retained = []
    if hop_samples is None:
        ends = list(range(window_samples, len(padded) + 1, step_samples))
    else:
        assert frame_samples is not None
        if hop_samples <= 0 or frame_samples <= 0:
            raise ValueError("livekit_runtime_schedule_invalid")
        padded = np.pad(
            padded,
            (0, (-len(padded)) % frame_samples),
            mode="constant",
        )
        ends = []
        buffered = 0
        since_score = 0
        for end in range(frame_samples, len(padded) + 1, frame_samples):
            buffered = min(window_samples, buffered + frame_samples)
            since_score += frame_samples
            if buffered >= window_samples and since_score >= hop_samples:
                ends.append(end)
                since_score %= hop_samples
    if hasattr(model, "predict_overlapping_windows"):
        raw_scores = np.asarray(
            model.predict_overlapping_windows(padded, ends, window_samples)
        ).reshape(-1)
        if len(raw_scores) != len(ends):
            raise ValueError("livekit_window_score_count_mismatch")
    elif hasattr(model, "predict_windows"):
        windows = np.stack(
            [padded[end - window_samples : end] for end in ends]
        )
        raw_scores = np.asarray(model.predict_windows(windows)).reshape(-1)
        if len(raw_scores) != len(ends):
            raise ValueError("livekit_window_score_count_mismatch")
    else:
        raw_scores = []
        for end in ends:
            scores = model.predict(padded[end - window_samples : end])
            if len(scores) != 1:
                raise ValueError("livekit_expected_one_classifier")
            raw_scores.append(float(next(iter(scores.values()))))
    raw_scores = np.asarray(raw_scores, dtype=np.float64)
    if getattr(model, "overlap_acceleration_active", False):
        candidates = set(
            np.flatnonzero(
                raw_scores >= retention_threshold - OVERLAP_EXACT_RESCORE_GUARD
            ).tolist()
        )
        candidates.update(
            np.argsort(raw_scores)[-min(3, len(raw_scores)) :].tolist()
        )
        indices = sorted(candidates)
        exact = model.rescore_windows_exact(
            padded, ends, indices, window_samples
        )
        if len(exact) != len(indices):
            raise ValueError("livekit_exact_rescore_count_mismatch")
        raw_scores[indices] = exact
    count = 0
    for end, raw_score in zip(ends, raw_scores, strict=True):
        score = float(raw_score)
        if not 0.0 <= score <= 1.0:
            raise ValueError("livekit_score_out_of_range")
        window_end = (end - window_samples) / SAMPLE_RATE
        count += 1
        if score > maximum:
            maximum = score
            maximum_end = window_end
        if score >= retention_threshold:
            retained.append(
                {
                    "window_end_seconds": round(window_end, 6),
                    "score": score,
                }
            )
    return {
        "max_score": maximum,
        "max_window_end_seconds": maximum_end,
        "windows_scored": count,
        "retained_windows": retained,
    }


def load_checkpoint(
    path: Path,
    *,
    corpus_manifest_sha256: str,
    model_sha256: str,
    mel_batch_model_sha256: str | None,
    mel_overlap_raw_sha256: str | None,
    mel_overlap_post_sha256: str | None,
    retention_threshold: float,
    proposal_threshold: float,
    hop_samples: int | None,
    frame_samples: int | None,
    preregistration_sha256: str | None,
    source_records: list[dict[str, object]],
) -> list[dict[str, object]]:
    if not path.is_file():
        return []
    value = read_json(path)
    if value.get("schema") != "baxy.openslr-livekit-scan-checkpoint.v1":
        raise ValueError("unsupported_openslr_scan_checkpoint_schema")
    expected = {
        "corpus_manifest_sha256": corpus_manifest_sha256,
        "model_sha256": model_sha256,
        "mel_batch_model_sha256": mel_batch_model_sha256,
        "mel_overlap_raw_sha256": mel_overlap_raw_sha256,
        "mel_overlap_post_sha256": mel_overlap_post_sha256,
        "retention_threshold": retention_threshold,
        "proposal_threshold": proposal_threshold,
        "hop_samples": hop_samples,
        "frame_samples": frame_samples,
        "preregistration_sha256": preregistration_sha256,
    }
    for field, expected_value in expected.items():
        if value.get(field) != expected_value:
            raise ValueError(f"openslr_scan_checkpoint_mismatch:{field}")
    records = value.get("records")
    if not isinstance(records, list) or len(records) > len(source_records):
        raise ValueError("openslr_scan_checkpoint_records_invalid")
    for index, record in enumerate(records):
        if (
            not isinstance(record, dict)
            or record.get("utterance_id")
            != source_records[index].get("utterance_id")
        ):
            raise ValueError("openslr_scan_checkpoint_order_mismatch")
    return records


def write_checkpoint(
    path: Path,
    *,
    corpus_manifest_sha256: str,
    model_sha256: str,
    mel_batch_model_sha256: str | None,
    mel_overlap_raw_sha256: str | None,
    mel_overlap_post_sha256: str | None,
    retention_threshold: float,
    proposal_threshold: float,
    hop_samples: int | None,
    frame_samples: int | None,
    preregistration_sha256: str | None,
    records: list[dict[str, object]],
) -> None:
    path.write_text(
        json.dumps(
            {
                "schema": "baxy.openslr-livekit-scan-checkpoint.v1",
                "corpus_manifest_sha256": corpus_manifest_sha256,
                "model_sha256": model_sha256,
                "mel_batch_model_sha256": mel_batch_model_sha256,
                "mel_overlap_raw_sha256": mel_overlap_raw_sha256,
                "mel_overlap_post_sha256": mel_overlap_post_sha256,
                "retention_threshold": retention_threshold,
                "proposal_threshold": proposal_threshold,
                "hop_samples": hop_samples,
                "frame_samples": frame_samples,
                "preregistration_sha256": preregistration_sha256,
                "records": records,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def scan(
    *,
    corpus_manifest_path: Path,
    model_path: Path,
    retention_threshold: float,
    proposal_threshold: float,
    output_path: Path,
    checkpoint_interval: int,
    hop_samples: int | None = None,
    frame_samples: int | None = None,
    preregistration_path: Path | None = None,
    mel_batch_model_path: Path | None = None,
    mel_overlap_raw_path: Path | None = None,
    mel_overlap_post_path: Path | None = None,
) -> dict[str, object]:
    if not 0.0 < retention_threshold <= proposal_threshold < 1.0:
        raise ValueError("livekit_scan_thresholds_invalid")
    if checkpoint_interval <= 0:
        raise ValueError("livekit_checkpoint_interval_invalid")
    corpus_manifest_path = corpus_manifest_path.resolve(strict=True)
    model_path = model_path.resolve(strict=True)
    if mel_batch_model_path is not None:
        mel_batch_model_path = mel_batch_model_path.resolve(strict=True)
    if (mel_overlap_raw_path is None) != (mel_overlap_post_path is None):
        raise ValueError("openslr_mel_overlap_contract_incomplete")
    if mel_overlap_raw_path is not None:
        mel_overlap_raw_path = mel_overlap_raw_path.resolve(strict=True)
        assert mel_overlap_post_path is not None
        mel_overlap_post_path = mel_overlap_post_path.resolve(strict=True)
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    corpus = read_json(corpus_manifest_path)
    corpus_schema = corpus.get("schema")
    supported_schemas = {
        "baxy.openslr-librispeech-negative-development.v1",
        "baxy.openslr-librispeech-negative-holdout.v1",
    }
    if corpus_schema not in supported_schemas:
        raise ValueError("unsupported_openslr_corpus_schema")
    source_records = corpus.get("records")
    if not isinstance(source_records, list) or not source_records:
        raise ValueError("openslr_corpus_records_missing")
    corpus_root = Path(str(corpus["corpus_root"])).resolve(strict=True)
    corpus_hash = sha256(corpus_manifest_path)
    model_hash = sha256(model_path)
    mel_batch_model_hash = (
        sha256(mel_batch_model_path) if mel_batch_model_path is not None else None
    )
    mel_overlap_raw_hash = (
        sha256(mel_overlap_raw_path) if mel_overlap_raw_path is not None else None
    )
    mel_overlap_post_hash = (
        sha256(mel_overlap_post_path) if mel_overlap_post_path is not None else None
    )
    holdout = corpus_schema == "baxy.openslr-librispeech-negative-holdout.v1"
    preregistration_hash = None
    if holdout:
        if preregistration_path is None or hop_samples is None or frame_samples is None:
            raise ValueError("openslr_holdout_preregistration_required")
        preregistration_path = preregistration_path.resolve(strict=True)
        preregistration_hash = sha256(preregistration_path)
        preregistration = read_json(preregistration_path)
        expected = {
            "negative_corpus_manifest_sha256": corpus_hash,
            "stage1_model_sha256": model_hash,
            "scan_script_sha256": sha256(Path(__file__).resolve()),
            "mel_overlap_raw_sha256": mel_overlap_raw_hash,
            "mel_overlap_post_sha256": mel_overlap_post_hash,
            "broad_threshold": retention_threshold,
            "strong_threshold": proposal_threshold,
            "stage1_hop_samples": hop_samples,
            "audio_frame_samples": frame_samples,
        }
        if (
            preregistration.get("schema")
            != "baxy.wake-verifier-negative-holdout-preregistration.v1"
            or preregistration.get("candidate_frozen") is not True
            or any(preregistration.get(name) != value for name, value in expected.items())
        ):
            raise ValueError("openslr_holdout_preregistration_mismatch")
    elif preregistration_path is not None:
        raise ValueError("openslr_development_preregistration_unexpected")
    checkpoint_path = output_path.with_suffix(output_path.suffix + ".partial.json")
    records = load_checkpoint(
        checkpoint_path,
        corpus_manifest_sha256=corpus_hash,
        model_sha256=model_hash,
        mel_batch_model_sha256=mel_batch_model_hash,
        mel_overlap_raw_sha256=mel_overlap_raw_hash,
        mel_overlap_post_sha256=mel_overlap_post_hash,
        retention_threshold=retention_threshold,
        proposal_threshold=proposal_threshold,
        hop_samples=hop_samples,
        frame_samples=frame_samples,
        preregistration_sha256=preregistration_hash,
        source_records=source_records,
    )

    import soundfile as sf
    load_started = time.perf_counter()
    model = BatchedLiveKitPredictor(
        model_path,
        mel_batch_model_path=mel_batch_model_path,
        mel_overlap_raw_path=mel_overlap_raw_path,
        mel_overlap_post_path=mel_overlap_post_path,
    )
    load_seconds = time.perf_counter() - load_started
    scan_started = time.perf_counter()
    for index in range(len(records), len(source_records)):
        source = source_records[index]
        if not isinstance(source, dict):
            raise ValueError("openslr_corpus_record_invalid")
        path = corpus_root / str(source["relative_path"])
        actual_hash = sha256(path)
        if actual_hash != source.get("sha256"):
            raise ValueError(f"openslr_audio_hash_mismatch:{path}")
        audio, sample_rate = sf.read(str(path), dtype="float32")
        if sample_rate != SAMPLE_RATE or audio.ndim != 1:
            raise ValueError(f"openslr_audio_contract_invalid:{path}")
        started = time.perf_counter()
        result = streaming_scores(
            model,
            audio,
            retention_threshold=retention_threshold,
            hop_samples=hop_samples,
            frame_samples=frame_samples,
        )
        records.append(
            {
                "utterance_id": source["utterance_id"],
                "relative_path": source["relative_path"],
                "wav_sha256": actual_hash,
                "duration_seconds": source["duration_seconds"],
                "transcript": source["transcript"],
                **result,
                "proposal": float(result["max_score"]) >= proposal_threshold,
                "scan_wall_seconds": round(time.perf_counter() - started, 6),
            }
        )
        if (
            len(records) % checkpoint_interval == 0
            or len(records) == len(source_records)
        ):
            write_checkpoint(
                checkpoint_path,
                corpus_manifest_sha256=corpus_hash,
                model_sha256=model_hash,
                mel_batch_model_sha256=mel_batch_model_hash,
                mel_overlap_raw_sha256=mel_overlap_raw_hash,
                mel_overlap_post_sha256=mel_overlap_post_hash,
                retention_threshold=retention_threshold,
                proposal_threshold=proposal_threshold,
                hop_samples=hop_samples,
                frame_samples=frame_samples,
                preregistration_sha256=preregistration_hash,
                records=records,
            )
            print(f"PROGRESS|{len(records)}/{len(source_records)}", flush=True)
    scan_seconds = time.perf_counter() - scan_started
    total_audio_seconds = sum(
        float(record["duration_seconds"]) for record in records
    )
    report: dict[str, object] = {
        "schema": (
            "baxy.openslr-librispeech-livekit-holdout-scan.v1"
            if holdout
            else "baxy.openslr-librispeech-livekit-development-scan.v1"
        ),
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": (
            "frozen_raw_negative_product_calibration_holdout"
            if holdout
            else "independent_raw_negative_architecture_development"
        ),
        "corpus_manifest": corpus_manifest_path.as_posix(),
        "corpus_manifest_sha256": corpus_hash,
        "model": model_path.as_posix(),
        "model_sha256": model_hash,
        "preregistration": (
            preregistration_path.as_posix() if preregistration_path else None
        ),
        "preregistration_sha256": preregistration_hash,
        "window_seconds": WINDOW_SECONDS,
        "step_seconds": STEP_SECONDS if hop_samples is None else None,
        "hop_samples": hop_samples,
        "audio_frame_samples": frame_samples,
        "retention_threshold": retention_threshold,
        "proposal_threshold": proposal_threshold,
        "product_runtime_equivalent_window_math": True,
        "product_runtime_equivalent_schedule": hop_samples is not None,
        "metrics": {
            "utterances": len(records),
            "audio_seconds": total_audio_seconds,
            "audio_hours": total_audio_seconds / 3600.0,
            "windows_scored": sum(
                int(record["windows_scored"]) for record in records
            ),
            "utterances_at_retention_threshold": sum(
                float(record["max_score"]) >= retention_threshold
                for record in records
            ),
            "utterances_at_proposal_threshold": sum(
                bool(record["proposal"]) for record in records
            ),
            "retained_windows": sum(
                len(record["retained_windows"]) for record in records
            ),
        },
        "runtime": {
            "model_load_seconds": round(load_seconds, 6),
            "scan_seconds": round(scan_seconds, 6),
            "audio_realtime_factor": scan_seconds / total_audio_seconds,
            "window_batch_size": model.batch_size,
            "batched_math_equivalence": (
                "same_mel_embedding_last16_and_classifier_graphs_as_WakeWordModel"
            ),
            "mel_model": model.mel_path.as_posix(),
            "mel_model_sha256": sha256(model.mel_path),
            "mel_batch_model": (
                model.mel_batch_path.as_posix()
                if model.mel_batch_path is not None
                else None
            ),
            "mel_batch_model_sha256": mel_batch_model_hash,
            "mel_overlap_raw_model": (
                model.mel_overlap_raw_path.as_posix()
                if model.mel_overlap_raw_path is not None
                else None
            ),
            "mel_overlap_raw_sha256": mel_overlap_raw_hash,
            "mel_overlap_post_model": (
                model.mel_overlap_post_path.as_posix()
                if model.mel_overlap_post_path is not None
                else None
            ),
            "mel_overlap_post_sha256": mel_overlap_post_hash,
            "embedding_model": model.embedding_path.as_posix(),
            "embedding_model_sha256": sha256(model.embedding_path),
            "overlap_exact_rescore_guard": (
                OVERLAP_EXACT_RESCORE_GUARD
                if model.overlap_acceleration_active
                else None
            ),
            "overlap_windows_scored": model.overlap_windows_scored,
            "exact_rescore_windows": model.exact_rescore_windows,
            "embedding_windows_total": model.embedding_windows_total,
            "embedding_windows_unique": model.embedding_windows_unique,
        },
        "records": records,
        "candidate_development_use": not holdout,
        "candidate_scored": holdout,
        "product_far_claim_supported": False,
        "blind_human_partition_accessed": False,
        "effects_executed": 0,
    }
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    checkpoint_path.unlink(missing_ok=True)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--retention-threshold", type=float, default=0.02)
    parser.add_argument("--proposal-threshold", type=float, default=0.05)
    parser.add_argument("--checkpoint-interval", type=int, default=10)
    parser.add_argument("--hop-samples", type=int)
    parser.add_argument("--frame-samples", type=int)
    parser.add_argument("--preregistration", type=Path)
    parser.add_argument("--mel-batch-model", type=Path)
    parser.add_argument("--mel-overlap-raw", type=Path)
    parser.add_argument("--mel-overlap-post", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = scan(
        corpus_manifest_path=args.corpus_manifest,
        model_path=args.model,
        retention_threshold=args.retention_threshold,
        proposal_threshold=args.proposal_threshold,
        output_path=args.output,
        checkpoint_interval=args.checkpoint_interval,
        hop_samples=args.hop_samples,
        frame_samples=args.frame_samples,
        preregistration_path=args.preregistration,
        mel_batch_model_path=args.mel_batch_model,
        mel_overlap_raw_path=args.mel_overlap_raw,
        mel_overlap_post_path=args.mel_overlap_post,
    )
    print(json.dumps({"output": args.output.resolve().as_posix(), "metrics": report["metrics"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
