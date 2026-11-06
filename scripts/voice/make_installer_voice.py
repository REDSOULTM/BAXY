"""Records what BAXY says in its installer (src/Baxy.Installer/Assets/voice/lines.json) with BAXY's own voice, the way the
mind says it (speech_text.spoken, voice_output's speed, trim and loudness). The installer cannot run the voice: it plays
before anything is installed, so it carries these files. Run again when a line changes:

    <mind-runtime python> -X utf8 scripts/voice/make_installer_voice.py <voice folder>"""
from __future__ import annotations

import json
import re
import sys
import wave
from fractions import Fraction
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import sherpa_onnx  # noqa: E402
from scipy.signal import resample_poly  # noqa: E402

from baxy_mind import speech_text, voice_output  # noqa: E402

VOICE = ROOT / "src" / "Baxy.Installer" / "Assets" / "voice"
SAMPLE_RATE = 22050


def _engine(folder: Path) -> sherpa_onnx.OfflineTts:
    return sherpa_onnx.OfflineTts(sherpa_onnx.OfflineTtsConfig(model=sherpa_onnx.OfflineTtsModelConfig(
        supertonic=sherpa_onnx.OfflineTtsSupertonicModelConfig(
            duration_predictor=str(folder / "duration_predictor.int8.onnx"),
            text_encoder=str(folder / "text_encoder.int8.onnx"),
            vector_estimator=str(folder / "vector_estimator.int8.onnx"),
            vocoder=str(folder / "vocoder.int8.onnx"), tts_json=str(folder / "tts.json"),
            unicode_indexer=str(folder / "unicode_indexer.bin"), voice_style=str(folder / "voice.bin")),
        num_threads=voice_output.THREADS, provider="cpu")))


def _sentence(tts: sherpa_onnx.OfflineTts, recipe: dict, shift: Fraction, text: str, lang: str) -> np.ndarray:
    said = speech_text.spoken(text, lang)
    config = sherpa_onnx.GenerationConfig()
    config.sid = 0
    config.num_steps = int(recipe["steps"])
    config.speed = float(recipe["speed"]) * voice_output._speed(said) / float(shift)
    config.extra = {"lang": lang, "seed": str(recipe["seed"])}
    audio = np.asarray(tts.generate(said, config).samples, dtype=np.float32)
    if shift != 1:
        audio = resample_poly(audio, shift.denominator, shift.numerator).astype(np.float32)
    audio = voice_output._trim(audio, tts.sample_rate).copy()
    rms = float(np.sqrt(np.mean(audio ** 2)))
    audio *= min(voice_output.LOUDNESS / rms, voice_output.PEAK / float(np.max(np.abs(audio))))
    fade = min(int(tts.sample_rate * voice_output.FADE_S), audio.size // 2)
    audio[:fade] *= np.linspace(0, 1, fade, dtype=np.float32)
    audio[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)
    return audio


def main() -> None:
    folder = Path(sys.argv[1])
    recipe = json.loads((folder / "baxy-voice.json").read_text(encoding="utf-8"))
    shift = Fraction(2 ** (float(recipe.get("shift", 0)) / 12)).limit_denominator(100)
    tts = _engine(folder)
    gap = np.zeros(int(tts.sample_rate * float(recipe["gap_s"])), dtype=np.float32)
    lines = json.loads((VOICE / "lines.json").read_text(encoding="utf-8"))
    for lang, said in lines.items():
        for line, text in said.items():
            takes: list[np.ndarray] = []
            for sentence in re.findall(r"[^.?!]+[.?!]", text):
                takes += [_sentence(tts, recipe, shift, sentence.strip(), lang), gap]
            audio = resample_poly(np.concatenate(takes[:-1]), SAMPLE_RATE, tts.sample_rate)
            samples = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
            with wave.open(str(VOICE / f"{lang}_{line}.wav"), "wb") as file:
                file.setnchannels(1)
                file.setsampwidth(2)
                file.setframerate(SAMPLE_RATE)
                file.writeframes(samples.tobytes())
            print(f"{lang}_{line}: {samples.size / SAMPLE_RATE:.1f} s")


if __name__ == "__main__":
    main()
