"""Human controls for RAW211: fixed level/time, no parameter search."""
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time

import numpy as np
from scipy.io import wavfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import baxy_mind.voice as voice
from baxy_mind.speex_aec import EchoCanceller

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    return json.loads(path.read_text(encoding="utf-8"))

def save(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

base = ROOT / "artifacts/comprobaciones/C03"
out = base / "astra-raw-human213"
out.mkdir(exist_ok=False)
private_root = Path(os.environ["LOCALAPPDATA"]) / "BAXY"
private = private_root / "C03-raw-human213-private"
private.mkdir(exist_ok=False)
capture = read(base / "astra-raw-capture211/RESULTS.json")
humans = read(base / "astra-human195/DOWNLOADS.json")
signals = {}
origin = capture["playback"]["streamTime"] + capture["playback"]["latency"]
for row in capture["streams"]:
    path = private_root / "C03-raw-capture211-private" / f'{row["mode"]}.npz'
    assert digest(path) == row["sha256"]
    signals[row["mode"]] = np.load(path)
assert importlib.metadata.version("sherpa-onnx") == "1.13.4+baxy.1"
save(out / "PREREG.json", {
    "utc": datetime.now(timezone.utc).isoformat(), "scriptSha256": digest(Path(__file__)),
    "method": "Four fixed195 humans RMS0.01 inserted at playback time3s, independently aligned to each211 capture ADC origin. Conditions near-only unchanged, near-only Speex, normal-mic mix Speex, RAW-mic mix Speex. No new gains/delays/models.16 decoded fixed windows through installed VoiceEngine public transcribe_pcm, inert output.",
    "window": "Human onset minus1s through human end plus1s; known Speex32ms delay covered. Process entire captured timeline before slicing. No hints or expected text sent to recognizer.",
    "limitation": "Constructed double-talk adds human after Windows preprocessing; cannot measure OS processing of real simultaneous human. Necessary software-filter control, not physical acceptance.",
    "humans": humans, "capture": capture["streams"],
    "sources": {name: digest(ROOT / f"src/baxy_mind/{name}.py") for name in ["voice", "speex_aec"]},
})

class InertOutput:
    speaking = False
    available = False
    def start(self):
        pass

voice.create_speech_output = lambda callback: InertOutput()
recognizer = voice.VoiceEngine(lambda text: None, lambda event: None)
recognizer.load()
results = []
for human_index, human in enumerate(humans):
    path = Path(human["asset"])
    assert digest(path) == human["sha256"]
    rate, original = wavfile.read(path)
    assert rate == 16000 and original.dtype == np.float32
    gain = .01 / float(np.sqrt(np.mean(original.astype(np.float64) ** 2)))
    for condition in ["near_none", "near_speex", "default_speex", "raw_speex"]:
        mode = "default" if condition == "default_speex" else "raw"
        signal = signals[mode]
        mic, ref, timing = [signal[k] for k in ["microphone", "reference", "timing"]]
        onset = round((origin + 3 - timing[0, 0]) * 16000)
        near = np.zeros(mic.size, np.float32)
        near[onset:onset + len(original)] = original * gain
        assert onset > 16000 and onset + len(original) + 16000 < len(near)
        mixed = condition.startswith(("raw_", "default_"))
        incoming = near.reshape(mic.shape) + (mic if mixed else 0)
        reference = ref if mixed else np.zeros_like(ref)
        assert np.abs(incoming).max() < 1
        clean = np.empty_like(incoming)
        engine = EchoCanceller() if condition != "near_none" else None
        try:
            for i in range(len(mic)):
                clean[i] = engine.process(incoming[i], reference[i])[0] if engine else incoming[i]
        finally:
            if engine:
                engine.close()
        window = clean.ravel()[onset - 16000:onset + len(original) + 16000].copy()
        output = private / f"h{human_index}-{condition}.npz"
        np.savez(output, clean=clean, window=window)
        start = time.monotonic()
        text = recognizer.transcribe_pcm(window)
        delay = 512 if engine else 0
        recovered = clean.ravel()[onset + delay:onset + delay + len(original)].astype(np.float64)
        target = original.astype(np.float64) * gain
        row = {"human": human_index, "id": human["id"], "condition": condition,
            "gain": gain, "onset": onset, "text": text, "referenceText": human["rawTranscription"],
            "seconds": time.monotonic() - start, "sha256": digest(output),
            "waveCorrelation": float(np.corrcoef(target, recovered)[0, 1]),
            "waveProjectionGain": float(np.dot(target, recovered) / np.dot(target, target))}
        results.append(row)
        save(out / "RESULTS.json", results)
        print(json.dumps(row, ensure_ascii=True), flush=True)
save(out / "COMPLETE.json", {"readings": len(results), "exitCode": 0})
