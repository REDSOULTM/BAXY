"""Development QbyT verifier used by the bounded wake experiments."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from audit_wav2vec2_hidden_wake_product_scan_v1 import sliding_vectors  # noqa: E402
from audit_wav2vec2_hidden_wake_separability_v1 import (  # noqa: E402
    normalize_audio,
    sha256,
)


def load_candidate(path: Path, model_directory: Path) -> dict[str, object]:
    candidate_path = path.resolve(strict=True)
    model_root = model_directory.resolve(strict=True)
    value = json.loads(candidate_path.read_text(encoding="utf-8-sig"))
    policy = value.get("policy") if isinstance(value, dict) else None
    parameters = value.get("parameters") if isinstance(value, dict) else None
    direction = parameters.get("direction") if isinstance(parameters, dict) else None
    if (
        value.get("schema")
        not in {
            "baxy.wav2vec2-qbyt-wake-candidate.v1",
            "baxy.wav2vec2-qbyt-wake-candidate.v2",
            "baxy.wav2vec2-qbyt-wake-candidate.v3",
        }
        or value.get("developmentOnly") is not True
        or not isinstance(policy, dict)
        or policy.get("layer") != 2
        or policy.get("windowDurationSeconds") != 0.9
        or policy.get("pooling") != "max"
        or not isinstance(policy.get("threshold"), (int, float))
        or not isinstance(direction, list)
        or len(direction) != 1024
        or not np.isfinite(np.asarray(direction, dtype=np.float64)).all()
        or value.get("sources", {}).get("modelWeightsSha256")
        != sha256(model_root / "pytorch_model.bin")
        or value.get("sources", {}).get("modelConfigSha256")
        != sha256(model_root / "config.json")
    ):
        raise ValueError("wake_qbyt_candidate_invalid")
    return {
        "path": candidate_path,
        "model_directory": model_root,
        "layer": int(policy["layer"]),
        "duration": float(policy["windowDurationSeconds"]),
        "pooling": str(policy["pooling"]),
        "threshold": float(policy["threshold"]),
        "direction": np.asarray(direction, dtype=np.float32),
    }


class Wav2Vec2QbyTVerifier:
    def __init__(self, candidate: dict[str, object], *, device: str) -> None:
        if device not in {"cpu", "cuda"}:
            raise ValueError("wake_qbyt_device_invalid")
        import torch
        from transformers import Wav2Vec2ForCTC

        if device == "cuda" and not torch.cuda.is_available():
            raise ValueError("wake_qbyt_cuda_unavailable")
        self._torch = torch
        self._device = torch.device(device)
        self._candidate = candidate
        self._model = Wav2Vec2ForCTC.from_pretrained(
            str(candidate["model_directory"]), local_files_only=True
        ).eval().to(self._device)

    def score(self, audio: np.ndarray) -> float:
        values = np.asarray(audio, dtype=np.float32)
        if values.ndim != 1 or not len(values) or not np.isfinite(values).all():
            raise ValueError("wake_qbyt_audio_invalid")
        with self._torch.inference_mode():
            hidden = self._model.wav2vec2(
                self._torch.from_numpy(normalize_audio(values))
                .unsqueeze(0)
                .to(self._device),
                output_hidden_states=True,
            ).hidden_states[int(self._candidate["layer"])][0]
            hidden = hidden.detach().float().cpu().numpy()
        vectors, _ = sliding_vectors(
            hidden,
            duration_seconds=float(self._candidate["duration"]),
            pooling=str(self._candidate["pooling"]),
        )
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        if np.any(norms <= 0.0):
            raise ValueError("wake_qbyt_embedding_invalid")
        normalized = vectors / norms
        return float(np.max(normalized @ self._candidate["direction"]))

    def accepts(self, audio: np.ndarray) -> tuple[bool, float]:
        score = self.score(audio)
        return score >= float(self._candidate["threshold"]), score
