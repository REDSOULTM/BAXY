from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "scan_openslr_librispeech_livekit_development.py"
)
SPEC = importlib.util.spec_from_file_location(
    "scan_openslr_librispeech_livekit_development", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PeakPredictor:
    def predict(self, audio: np.ndarray) -> dict[str, float]:
        return {"baxy": float(np.max(audio))}


class BatchedPeakPredictor:
    def predict_windows(self, windows: np.ndarray) -> np.ndarray:
        return np.max(windows, axis=1)


class GuardedOverlapPredictor:
    overlap_acceleration_active = True

    def __init__(self) -> None:
        self.approximate: np.ndarray | None = None
        self.rescored: list[int] = []

    def predict_overlapping_windows(
        self, _padded: np.ndarray, ends: list[int], _window_samples: int
    ) -> np.ndarray:
        self.approximate = np.zeros(len(ends), dtype=np.float64)
        self.approximate[2] = 0.01749
        return self.approximate.copy()

    def rescore_windows_exact(
        self,
        _padded: np.ndarray,
        _ends: list[int],
        indices: list[int],
        _window_samples: int,
    ) -> np.ndarray:
        assert self.approximate is not None
        self.rescored = indices
        exact = self.approximate[indices].copy()
        exact[indices.index(2)] = 0.01751
        return exact


def test_streaming_scores_uses_product_window_and_hop() -> None:
    audio = np.ones(3 * 16_000, np.float32) * 0.7

    result = MODULE.streaming_scores(
        PeakPredictor(), audio, retention_threshold=0.2
    )

    assert result["max_score"] == pytest.approx(0.7)
    assert result["windows_scored"] == 21
    assert result["retained_windows"]


def test_batched_streaming_scores_preserve_window_contract() -> None:
    audio = np.zeros(3 * 16_000, np.float32)
    audio[16_000 : 17_000] = 0.7

    scalar = MODULE.streaming_scores(
        PeakPredictor(), audio, retention_threshold=0.2
    )
    batched = MODULE.streaming_scores(
        BatchedPeakPredictor(), audio, retention_threshold=0.2
    )

    assert batched == scalar


def test_runtime_schedule_uses_real_audio_frame_quantization() -> None:
    audio = np.ones(3 * 16_000, np.float32) * 0.7

    result = MODULE.streaming_scores(
        BatchedPeakPredictor(),
        audio,
        retention_threshold=0.2,
        hop_samples=2_560,
        frame_samples=512,
    )

    assert result["windows_scored"] > 0
    assert result["retained_windows"]
    assert result["retained_windows"][0]["window_end_seconds"] == pytest.approx(
        0.016
    )


def test_embedding_windows_preserve_livekit_stride_and_batch_order() -> None:
    mel = np.arange(2 * 197 * 32, dtype=np.float32).reshape(2, 197, 32)

    windows = MODULE.BatchedLiveKitPredictor._embedding_windows(mel)

    assert windows.shape == (32, 76, 32)
    np.testing.assert_array_equal(windows[0], mel[0, 0:76])
    np.testing.assert_array_equal(windows[1], mel[0, 8:84])
    np.testing.assert_array_equal(windows[16], mel[1, 0:76])
    np.testing.assert_array_equal(windows[-1], mel[1, 120:196])


def test_overlap_guard_rescores_near_threshold_before_retention() -> None:
    model = GuardedOverlapPredictor()

    result = MODULE.streaming_scores(
        model,
        np.zeros(3 * 16_000, np.float32),
        retention_threshold=0.0175,
        hop_samples=2_560,
        frame_samples=512,
    )

    assert 2 in model.rescored
    assert result["retained_windows"] == [
        {"window_end_seconds": 0.24, "score": 0.01751}
    ]


def test_checkpoint_rejects_model_change(tmp_path: Path) -> None:
    path = tmp_path / "scan.partial.json"
    sources = [{"utterance_id": "1-2-3"}]
    MODULE.write_checkpoint(
        path,
        corpus_manifest_sha256="a" * 64,
        model_sha256="b" * 64,
        mel_batch_model_sha256=None,
        mel_overlap_raw_sha256=None,
        mel_overlap_post_sha256=None,
        retention_threshold=0.02,
        proposal_threshold=0.05,
        hop_samples=2_560,
        frame_samples=512,
        preregistration_sha256=None,
        records=[{"utterance_id": "1-2-3"}],
    )

    with pytest.raises(ValueError, match="model_sha256"):
        MODULE.load_checkpoint(
            path,
            corpus_manifest_sha256="a" * 64,
            model_sha256="c" * 64,
            mel_batch_model_sha256=None,
            mel_overlap_raw_sha256=None,
            mel_overlap_post_sha256=None,
            retention_threshold=0.02,
            proposal_threshold=0.05,
            hop_samples=2_560,
            frame_samples=512,
            preregistration_sha256=None,
            source_records=sources,
        )


def test_holdout_preregistration_binds_overlap_assets_and_scanner(
    tmp_path: Path,
) -> None:
    corpus_root = tmp_path / "corpus"
    corpus_root.mkdir()
    corpus_manifest = tmp_path / "corpus.json"
    corpus_manifest.write_text(
        json.dumps(
            {
                "schema": "baxy.openslr-librispeech-negative-holdout.v1",
                "corpus_root": str(corpus_root),
                "records": [{"utterance_id": "1-2-3"}],
            }
        ),
        encoding="utf-8",
    )
    model = tmp_path / "stage1.onnx"
    raw = tmp_path / "raw.onnx"
    post = tmp_path / "post.onnx"
    model.write_bytes(b"model")
    raw.write_bytes(b"raw")
    post.write_bytes(b"post")
    preregistration = tmp_path / "preregistration.json"
    preregistration.write_text(
        json.dumps(
            {
                "schema": (
                    "baxy.wake-verifier-negative-holdout-preregistration.v1"
                ),
                "candidate_frozen": True,
                "negative_corpus_manifest_sha256": MODULE.sha256(
                    corpus_manifest
                ),
                "stage1_model_sha256": MODULE.sha256(model),
                "scan_script_sha256": MODULE.sha256(SCRIPT),
                "mel_overlap_raw_sha256": "0" * 64,
                "mel_overlap_post_sha256": MODULE.sha256(post),
                "broad_threshold": 0.0175,
                "strong_threshold": 0.035,
                "stage1_hop_samples": 2_560,
                "audio_frame_samples": 512,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError, match="openslr_holdout_preregistration_mismatch"
    ):
        MODULE.scan(
            corpus_manifest_path=corpus_manifest,
            model_path=model,
            retention_threshold=0.0175,
            proposal_threshold=0.035,
            output_path=tmp_path / "output.json",
            checkpoint_interval=25,
            hop_samples=2_560,
            frame_samples=512,
            preregistration_path=preregistration,
            mel_overlap_raw_path=raw,
            mel_overlap_post_path=post,
        )
