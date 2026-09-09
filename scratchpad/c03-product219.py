"""Verify installed baxy.2 on every fixed217 greedy input via public product API."""
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time

import numpy as np
import psutil
from scipy.io import wavfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import baxy_mind.voice as voice
import sherpa_onnx

BASE = ROOT / "artifacts/comprobaciones/C03"
OUT = BASE / "astra-product219"
OUT.mkdir(exist_ok=False)
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):
    return json.loads(path.read_text(encoding="utf-8"))
def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

assert importlib.metadata.version("sherpa-onnx") == "1.13.4+baxy.2"
assert importlib.metadata.version("sherpa-onnx-core") == "1.13.4"
native = Path(sys.modules["sherpa_onnx.lib._sherpa_onnx"].__file__)
assert "site-packages" in str(native)
notice = read(native.parents[1] / "baxy_native_build.json")
assert sha(native) == notice["extensionSha256"]
assert b"baxy_trace_prefix" not in native.read_bytes()
expected = [r for r in read(BASE / "astra-normalize-regression217/RESULTS.json") if r["method"] == "greedy_search"]
inputs = []
for row in read(BASE / "astra-segment201-retry/RESULTS.json"):
    path = Path(row["privateOutput"])
    assert sha(path) == row["sha256"]
    with np.load(path) as archive:
        for segment in row["segments"]:
            inputs.append(archive[f'segment{segment["index"]}'].copy())
for row in read(BASE / "astra-human195/DOWNLOADS.json"):
    path = Path(row["asset"])
    assert sha(path) == row["sha256"]
    rate, audio = wavfile.read(path)
    assert rate == 16000
    inputs.append(np.r_[np.zeros(16000, np.float32), audio, np.zeros(16000, np.float32)])
inputs.append(np.zeros(32000, np.float32))
for row in read(BASE / "astra-raw-human213/RESULTS.json"):
    path = Path(os.environ["LOCALAPPDATA"]) / "BAXY/C03-raw-human213-private" / f'h{row["human"]}-{row["condition"]}.npz'
    assert sha(path) == row["sha256"]
    inputs.append(np.load(path)["window"].copy())
assert len(inputs) == len(expected) == 63
manifest = Path(os.environ["LOCALAPPDATA"]) / "BAXYRuntime/mind-runtime-v1.json"
save("PREREG.json", {"utc": datetime.now(timezone.utc).isoformat(), "scriptSha256": sha(Path(__file__)),
    "method": "Actual installed baxy.2 and VoiceEngine public transcribe_pcm on all63 exact217 inputs. Observe unchanged helper return to distinguish native parity from contextual correction. Output factory inert, no native injection/capture/device/calibration bypass. Three recovered213 cases also use real direct utterance callback.",
    "criterion": "Raw helper63/63 must reproduce greedy217; report any public correction separately. This is integration parity, not63 useful/fair transcriptions or acoustic acceptance.",
    "notice": notice, "nativeSha256": sha(native), "registrationSha256": sha(manifest),
    "sourceSha256": sha(ROOT / "src/baxy_mind/voice.py"),
    "inputs": [hashlib.sha256(audio.tobytes()).hexdigest() for audio in inputs]})
class InertOutput:
    speaking = False
    available = False
    def start(self):
        pass

voice.create_speech_output = lambda callback: InertOutput()
calls = []
original_decode = voice._decode_offline_text
def observe_decode(recognizer, audio, *, hotwords=""):
    text = original_decode(recognizer, audio, hotwords=hotwords)
    calls.append({"text": text, "contextual": bool(hotwords)})
    return text
voice._decode_offline_text = observe_decode
published, events = [], []
engine = voice.VoiceEngine(published.append, events.append)
start = time.monotonic()
engine.load()
load_seconds = time.monotonic() - start
results = []
for index, audio in enumerate(inputs):
    calls.clear()
    start = time.monotonic()
    text = engine.transcribe_pcm(audio)
    assert calls and not calls[0]["contextual"]
    result = {"index": index, "nativeText": calls[0]["text"], "text": text,
        "expectedNative": expected[index]["text"], "calls": calls.copy(), "seconds": time.monotonic() - start}
    results.append(result)
    save("RESULTS.json", results)
    assert calls[0]["text"] == expected[index]["text"]
engine._mode = "direct"
direct = []
for index in [50, 52, 54]:
    start = len(published)
    engine._decode_utterance(inputs[index], False)
    assert len(published) == start + 1
    direct.append({"index": index, "text": published[-1], "publicPcmText": results[index]["text"]})
save("DIRECT.json", direct)
save("COMPLETE.json", {"pcmReadings": 63, "nativeParity217": 63,
    "publicCorrections": sum(row["text"] != row["nativeText"] for row in results),
    "directCallbacks": len(direct), "engineLoadSeconds": load_seconds,
    "wakeBackend": engine._wake_backend, "wakeError": engine._wake_error,
    "rssMiB": psutil.Process().memory_info().rss / 2**20,
    "registrationUnchanged": sha(manifest) == read(OUT / "PREREG.json")["registrationSha256"], "exitCode": 0})
print(json.dumps(read(OUT / "COMPLETE.json")), flush=True)
