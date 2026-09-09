"""Independent local ASR on the exact DTLN512 segments/windows and four originals."""
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
import time

import numpy as np
import psutil
from scipy.io import wavfile
import sherpa_onnx

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from baxy_mind.voice import resolve_streaming_stt_directory
from test_mind_voice import transcribe_streaming

BASE = ROOT / "artifacts/comprobaciones/C03"
OUT = BASE / "astra-recognizer241"
OUT.mkdir(exist_ok=False)

def read(path):
    return json.loads(path.read_text(encoding="utf-8"))

def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()

def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

assert importlib.metadata.version("sherpa-onnx") == "1.13.4+baxy.2"
assert read(BASE / "astra-product239/COMPLETE.json")["timelines"] == 10
inputs = []
for row in read(BASE / "astra-product239/RESULTS.json"):
    if row["human"] is None:
        continue
    path = Path(row["privatePath"])
    assert sha(path) == row["sha256"]
    data = np.load(path)
    for index, segment in enumerate(row["segments"]):
        inputs.append({"case": row["case"], "kind": "segment", "index": index,
            "audio": data[f"segment{index}"].copy(), "parakeet": segment["text"], "reference": row["referenceText"]})
    inputs.append({"case": row["case"], "kind": "window", "index": 0,
        "audio": data["humanWindow"].copy(), "parakeet": row["humanWindowText"], "reference": row["referenceText"]})
prior219 = read(BASE / "astra-product219/RESULTS.json")
hashes219 = read(BASE / "astra-product219/PREREG.json")["inputs"]
for human, row in enumerate(read(BASE / "astra-human195/DOWNLOADS.json")):
    path = Path(row["asset"])
    assert sha(path) == row["sha256"]
    rate, audio = wavfile.read(path)
    assert rate == 16000
    audio = np.r_[np.zeros(16000, np.float32), audio, np.zeros(16000, np.float32)]
    assert hashlib.sha256(audio.tobytes()).hexdigest() == hashes219[42 + human]
    inputs.append({"case": f"h{human}-original", "kind": "original", "index": 0,
        "audio": audio, "parakeet": prior219[42 + human]["text"], "reference": row["rawTranscription"]})
assert len(inputs) == 20
directory = resolve_streaming_stt_directory()
assert directory is not None
save(OUT / "PREREG.json", {
    "utc": datetime.now(timezone.utc).isoformat(), "scriptSha256": sha(Path(__file__)),
    "method": "Existing independent local Nemotron on exact eight DTLN512239 product segments, eight fixed windows and four original human195 PCM controls already decoded by Parakeet219. Reuse exact Parakeet results, no model/decoder/padding/gain search. Same documented .66s streaming flush and auto language as214; no hints or corrector.",
    "purpose": "Locate remaining word/content differences at recognition vs waveform/endpoint boundaries. An independent transcript proves recoverability only when it actually recovers the content; no automatic runtime promotion.",
    "helperSha256": sha(ROOT / "scripts/test_mind_voice.py"),
    "modelFiles": [{"path": str(directory / name), "sha256": sha(directory / name)} for name in ["encoder.int8.onnx", "decoder.int8.onnx", "joiner.int8.onnx", "tokens.txt"]],
    "inputs": [{**{k: v for k, v in row.items() if k != "audio"},
        "pcmSha256": hashlib.sha256(row["audio"].tobytes()).hexdigest(), "samples": len(row["audio"])} for row in inputs],
})
start = time.perf_counter()
recognizer = sherpa_onnx.OnlineRecognizer.from_transducer(
    encoder=str(directory / "encoder.int8.onnx"), decoder=str(directory / "decoder.int8.onnx"),
    joiner=str(directory / "joiner.int8.onnx"), tokens=str(directory / "tokens.txt"),
    num_threads=6, model_type="nemo_transducer", decoding_method="greedy_search",
    enable_endpoint_detection=False, provider="cpu")
load_seconds = time.perf_counter() - start
results = []
for row in inputs:
    text, seconds = transcribe_streaming(recognizer, np.r_[row["audio"], np.zeros(10560, np.float32)])
    result = {k: v for k, v in row.items() if k != "audio"}
    result.update(nemotron=text, seconds=seconds)
    results.append(result)
    save(OUT / "RESULTS.json", results)
    print(json.dumps({k: result[k] for k in ["case", "kind", "nemotron", "seconds"]}, ensure_ascii=True), flush=True)
save(OUT / "COMPLETE.json", {"readings": len(results), "modelLoadSeconds": load_seconds,
    "rssMiB": psutil.Process().memory_info().rss / 2**20, "exitCode": 0})
