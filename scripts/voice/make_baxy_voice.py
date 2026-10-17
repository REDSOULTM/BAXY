"""BAXY's spoken voice, built from Supertonic 3 (sherpa-onnx's INT8 release, sherpa-onnx-supertonic-3-tts-int8-2026-05-11).

Supertonic ships ten adult voices; BAXY's (chosen by the owner by ear, 2026-10-17, take «G» of the listening rounds) is
a blend of three of its male styles: 50 % M1 (sid 5, «lively, upbeat»), 30 % M2 (sid 6, «deep, calm, composed») and 20 %
M4 (sid 8, «youthful, friendly»). A style is 50×256 timbre rows (style_ttl) and 8×16 pacing rows (style_dp), every row
of unit length, so the blend is a weighted sum renormalized row by row. voice_output.py then makes it a touch smaller
(shift, in semitones) and reads the rest of the recipe from baxy-voice.json.

make_baxy_voice.py <supertonic release folder> <out folder>
"""
import json
import shutil
import sys
from pathlib import Path

import numpy as np

MODEL_FILES = ["duration_predictor.int8.onnx", "text_encoder.int8.onnx", "vector_estimator.int8.onnx",
               "vocoder.int8.onnx", "tts.json", "unicode_indexer.bin"]
BLEND = {5: 0.5, 6: 0.3, 8: 0.2}
RECIPE = {
    "lang": "es",
    "steps": 10,      # flow-matching steps: 8 is near the paper's plateau (Supertonic v1, NFE sweep), 10 a little cleaner
    "speed": 1.0,     # sherpa's 1.0 is the demo's «0.95x»: calm, not slow
    "shift": 0.5,     # semitones up, pitch and formants together: the small robot, barely
    "seed": 7,        # fixed noise: the same sentence always sounds the same
    "gap_s": 0.2,     # silence after each sentence
}


def read_styles(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """sherpa-onnx's voice.bin: int64 (n, 50, 256) and (n, 8, 16), then float32 style_ttl and style_dp of every voice."""
    data = path.read_bytes()
    dims = np.frombuffer(data[:48], dtype="<i8")
    size = int(np.prod(dims[:3])) * 4
    ttl = np.frombuffer(data[48:48 + size], dtype="<f4").reshape(dims[:3])
    dp = np.frombuffer(data[48 + size:], dtype="<f4").reshape(dims[3:])
    return ttl, dp


def blend(table: np.ndarray) -> np.ndarray:
    mixed = sum(table[sid] * weight for sid, weight in BLEND.items())
    return mixed / np.linalg.norm(mixed, axis=-1, keepdims=True)


def main(source: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for name in MODEL_FILES:
        shutil.copyfile(source / name, out / name)
    ttl, dp = read_styles(source / "voice.bin")
    voice_ttl, voice_dp = blend(ttl)[None], blend(dp)[None]
    (out / "voice.bin").write_bytes(np.array(voice_ttl.shape, dtype="<i8").tobytes()
                                    + np.array(voice_dp.shape, dtype="<i8").tobytes()
                                    + voice_ttl.astype("<f4").tobytes() + voice_dp.astype("<f4").tobytes())
    (out / "baxy-voice.json").write_text(json.dumps(
        {**RECIPE, "source": source.name, "blend": {f"sid{sid}": weight for sid, weight in BLEND.items()},
         "licence": "Supertonic 3 model: OpenRAIL-M (https://huggingface.co/Supertone/supertonic-3/blob/main/LICENSE); "
                    "its use restrictions apply and speech must be disclosed as synthetic."},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
