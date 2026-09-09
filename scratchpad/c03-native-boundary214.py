"""Locate the three new213 empty outputs before interpreting acoustic loss."""
from datetime import datetime, timezone
import gc
import hashlib
import json
import os
from pathlib import Path
import sys

import numpy as np
import sherpa_onnx

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
import baxy_mind.voice as voice
from test_mind_voice import transcribe_streaming

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

base = ROOT / "artifacts/comprobaciones/C03"
out = base / "astra-native-boundary214"
out.mkdir(exist_ok=False)
previous = json.loads((base / "astra-raw-human213/RESULTS.json").read_text(encoding="utf-8"))
rows = [r for r in previous if not r["text"]]
rows += [next(r for r in previous if r["human"] == 1 and r["condition"] == "near_none")]
assert len(rows) == 4
private = Path(os.environ["LOCALAPPDATA"]) / "BAXY/C03-raw-human213-private"
signals = []
for row in rows:
    path = private / f'h{row["human"]}-{row["condition"]}.npz'
    assert sha(path) == row["sha256"]
    signals.append(np.load(path)["window"].copy())
save(out / "PREREG.json", {
    "utc": datetime.now(timezone.utc).isoformat(), "scriptSha256": sha(Path(__file__)),
    "method": "Same exact three empty213 PCM windows plus human1 near_none positive control. Inspect native greedy result before/after product corrector and applied decoder acknowledgement. Then independent existing Nemotron on unchanged window plus documented .66s flush. No gain/crop/model downloads/parameter changes or playback.",
    "purpose": "Attribute text loss to decoding or correction boundary; independent decode can establish recoverable voice, not exact original waveform or acceptance.",
    "inputs": rows,
})
class InertOutput:
    speaking = False
    available = False
    def start(self):
        pass

voice.create_speech_output = lambda callback: InertOutput()
engine = voice.VoiceEngine(lambda text: None, lambda event: None)
engine.load()
results = []
for row, audio in zip(rows, signals):
    stream = engine._recognizer.create_stream()
    stream.set_option("decoding_method", "greedy_search")
    stream.accept_waveform(16000, audio)
    engine._recognizer.decode_stream(stream)
    raw = stream.result.text
    result = {"human": row["human"], "condition": row["condition"], "recognizer": "parakeet_native",
        "nativeText": raw, "correctedText": engine._correct_transcript(raw, audio),
        "appliedMethod": stream.get_option("applied_decoding_method"),
        "tokens": list(stream.result.tokens), "timestamps": list(stream.result.timestamps)}
    results.append(result)
    save(out / "RESULTS.json", results)
    print(json.dumps(result, ensure_ascii=True), flush=True)
del stream, engine
gc.collect()
stt = voice.resolve_streaming_stt_directory()
assert stt is not None
recognizer = sherpa_onnx.OnlineRecognizer.from_transducer(
    encoder=str(stt / "encoder.int8.onnx"), decoder=str(stt / "decoder.int8.onnx"),
    joiner=str(stt / "joiner.int8.onnx"), tokens=str(stt / "tokens.txt"),
    num_threads=6, model_type="nemo_transducer", decoding_method="greedy_search",
    enable_endpoint_detection=False, provider="cpu")
for row, audio in zip(rows, signals):
    text, _ = transcribe_streaming(recognizer, np.r_[audio, np.zeros(10560, np.float32)])
    result = {"human": row["human"], "condition": row["condition"], "recognizer": "nemotron", "text": text}
    results.append(result)
    save(out / "RESULTS.json", results)
    print(json.dumps(result, ensure_ascii=True), flush=True)
save(out / "COMPLETE.json", {"readings": len(results), "exitCode": 0})
