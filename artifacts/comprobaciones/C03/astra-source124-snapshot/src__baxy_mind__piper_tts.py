"""Local Piper provider; its reference frontend owns phonemes and sentence boundaries."""

from __future__ import annotations

from collections.abc import Callable
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

import numpy as np

from .assets import AssetDescriptorError, resolve_asset


def resolve_piper_executable() -> Path | None:
    try:
        resolution = resolve_asset("piper_runtime")
    except AssetDescriptorError:
        return None
    return resolution.path / "piper.exe" if resolution.path is not None else None


def resolve_neural_tts_model(language: str = "es") -> Path | None:
    """Resolve each supported language independently; never use Spanish for missing English."""
    if language not in {"es", "en"}:
        raise ValueError("tts_language_unsupported")
    variable = "BAXY_NEURAL_TTS_MODEL" if language == "es" else "BAXY_NEURAL_TTS_ENGLISH_MODEL"
    configured = os.environ.get(variable, "").strip()
    if configured:
        candidate = Path(configured).expanduser()
        return candidate if candidate.is_file() else None
    asset = "neural_tts_voice" if language == "es" else "neural_tts_english_voice"
    try:
        resolution = resolve_asset(asset)
    except AssetDescriptorError:
        resolution = None
    directories = []
    if resolution is not None:
        if resolution.path is not None:
            directories.append(resolution.path)
        directories.extend(resolution.candidates)
    if language == "es":
        directories.append(Path.home() / ".gemma4" / "models" / "piper")
    default_name = "es_MX-claude-high.onnx" if language == "es" else "en_US-john-medium.onnx"
    for directory in directories:
        if not directory.is_dir():
            continue
        direct = directory / default_name
        if direct.is_file():
            return direct
        candidates = sorted(directory.glob("*.onnx"))
        if len(candidates) == 1:
            return candidates[0]
    return None


def neural_tts_identity(model_path: Path | None = None) -> tuple[str, str] | None:
    path = model_path or resolve_neural_tts_model()
    if path is None or not path.is_file():
        return None
    with path.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    return path.name, digest


class PiperEngine:
    """One owned child per synthesis; cancellation reaps it before returning to the queue."""

    def __init__(self, model_path: Path) -> None:
        self.model_path = model_path
        self._exe = resolve_piper_executable()
        if self._exe is None:
            raise FileNotFoundError("piper_runtime_missing")
        config_path = model_path.with_suffix(".onnx.json")
        if not model_path.is_file() or not config_path.is_file():
            raise FileNotFoundError("piper_voice_missing")
        if config_path.stat().st_size > 64 * 1024:
            raise ValueError("piper_config_too_large")
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        self.sample_rate = int(payload["audio"]["sample_rate"])
        if self.sample_rate <= 0:
            raise ValueError("piper_sample_rate_invalid")
        self.identity = neural_tts_identity(model_path)

    def generate(
        self, text: str, cancelled: Callable[[], bool] | None = None
    ) -> np.ndarray:
        is_cancelled = cancelled or (lambda: False)
        if is_cancelled():
            raise InterruptedError("tts_cancelled")
        command = [
            str(self._exe), "--model", str(self.model_path),
            "--espeak_data", str(self._exe.parent / "espeak-ng-data"),
            "--json-input", "--output_raw", "--quiet",
        ]
        # JSON keeps embedded newlines within one synthesis request. No shell is involved.
        request = (json.dumps({"text": text}, ensure_ascii=False) + "\n").encode("utf-8")
        process = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        deadline = time.monotonic() + 30.0
        try:
            while True:
                if is_cancelled():
                    raise InterruptedError("tts_cancelled")
                if time.monotonic() >= deadline:
                    raise TimeoutError("tts_synthesis_deadline")
                try:
                    audio, _diagnostic = process.communicate(input=request, timeout=0.1)
                    break
                except subprocess.TimeoutExpired:
                    request = None
            if process.returncode != 0:
                raise RuntimeError(f"piper_exit_{process.returncode}")
            if not audio or len(audio) % 2:
                raise ValueError("piper_pcm_invalid")
            return np.frombuffer(audio, dtype="<i2").astype(np.float32) / 32768.0
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5.0)
