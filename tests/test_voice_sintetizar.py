"""scripts/voice/sintetizar_frases.py's Supertonic lines are BAXY's voice as the product synthesizes it
(src/baxy_mind/voice_output.py, Speech._synthesize): the same phrase goes to the same Supertonic with the same
parameters and comes back the same length. Nothing is played and no model is loaded: a stand-in sherpa_onnx records
what each side asks for; the OneCore voices' files are already there and PowerShell is not run."""
import importlib.util
import json
import subprocess
import sys
import types
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from baxy_mind import voice_output  # noqa: E402

RECIPE = {"lang": "es", "steps": 6, "speed": 1.0, "shift": 0.5, "seed": 7}  # make_baxy_voice.py's
PHRASE = {"id": "t001", "clase": "lista", "texto": "Abre la calculadora.", "nombre": "Calculadora"}


class _Tts:
    sample_rate = 44100

    def __init__(self, asked: list) -> None:
        self.asked = asked

    def generate(self, text: str, config: object) -> types.SimpleNamespace:
        self.asked.append((text, config.sid, config.num_steps, round(config.speed, 6), dict(config.extra)))
        t = np.arange(self.sample_rate) / self.sample_rate
        return types.SimpleNamespace(samples=(0.5 * np.sin(2 * np.pi * 220 * t)).tolist(), sample_rate=self.sample_rate)


def _sherpa(asked: list) -> types.ModuleType:
    module = types.ModuleType("sherpa_onnx")
    module.GenerationConfig = type("GenerationConfig", (), {"sid": 0, "num_steps": 0, "speed": 1.0, "extra": {}})
    for name in ("OfflineTtsConfig", "OfflineTtsModelConfig", "OfflineTtsSupertonicModelConfig"):
        setattr(module, name, lambda **_kw: None)
    module.OfflineTts = lambda _config: _Tts(asked)
    return module


def _wav(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes((np.full(1600, 1000)).astype("<i2").tobytes())


def test_the_set_speaks_with_baxys_live_voice(tmp_path: Path, monkeypatch) -> None:
    # Calidad PC 2026-10-25: the set's Supertonic took the recipe's speed alone, without the product's «shift» (half a
    # semitone up, by resampling) and its speed by the phrase's length (_speed): another voice than BAXY's.
    voice = tmp_path / "voz"
    voice.mkdir()
    for name in voice_output._MODEL_FILES:
        (voice / name).write_text("", encoding="utf-8")
    (voice / "baxy-voice.json").write_text(json.dumps(RECIPE), encoding="utf-8")
    monkeypatch.setenv("BAXY_RENEW_TTS_DIR", str(voice))
    asked: list = []
    monkeypatch.setitem(sys.modules, "sherpa_onnx", _sherpa(asked))
    monkeypatch.setattr(subprocess, "run", lambda *_a, **_kw: None)  # the OneCore files below are already made
    out = tmp_path / "set"
    for name in ("Raul", "Sabina", "Pablo", "Laura"):
        _wav(out / "raw" / name / f"{PHRASE['id']}.wav")
    (tmp_path / "frases.json").write_text(json.dumps({"frases": [PHRASE]}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["sintetizar_frases.py", str(out)])
    spec = importlib.util.spec_from_file_location("sintetizar_frases", ROOT / "scripts" / "voice" / "sintetizar_frases.py")
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    monkeypatch.setattr(script, "PHRASES", tmp_path / "frases.json")
    script.main()
    said = PHRASE["texto"]
    the_set = [a for a in asked if a[0] == said]
    asked.clear()

    speech = voice_output.Speech(lambda _speaking: None, lambda *_spoken: None)
    assert speech._ready.wait(30) and not speech.failure, speech.failure
    asked.clear()  # the load's own «Hola.»
    live = script.to16k(speech._synthesize(said, pause=False), speech.rate)
    speech.close()
    assert the_set == asked
    row = next(r for r in json.loads((out / "manifest.json").read_text(encoding="utf-8"))
               if r["voz"] == "Supertonic" and r["cond"] == "limpio")
    assert len(script.read_wav(Path(row["wav"]))) == len(script.finish(live))
