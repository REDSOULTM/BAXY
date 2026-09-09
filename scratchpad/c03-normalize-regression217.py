"""All63 existing development PCM through both decoders with normalization fix."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

import numpy as np
from scipy.io import wavfile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts/comprobaciones/C03"
OUT = BASE / "astra-normalize-regression217"
OUT.mkdir(exist_ok=False)
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):
    return json.loads(path.read_text(encoding="utf-8"))
def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
bundle = Path("D:/BAXYRuntime/experiments/voice/sherpa205/bundle-normalize216")
build = read(BASE / "astra-normalize216/BUILD_COMPLETE.json")
assert all(sha(Path(r["path"])) == r["sha256"] for r in build["binaries"])
dll_handle = os.add_dll_directory(str(bundle))
pyd = next(bundle.glob("_sherpa_onnx*.pyd"))
name = "sherpa_onnx.lib._sherpa_onnx"
spec = importlib.util.spec_from_file_location(name, pyd)
native = importlib.util.module_from_spec(spec)
sys.modules[name] = native
spec.loader.exec_module(native)
import sherpa_onnx
sys.path.insert(0, str(ROOT / "src"))
from baxy_mind.voice import _compile_contextual_hotwords, WakePhraseMatcher

old_greedy = read(BASE / "astra-greedy203/RESULTS.json")
old_beam = read(BASE / "astra-native205-baseline/RESULTS.json")
segments = read(BASE / "astra-segment201-retry/RESULTS.json")
humans = read(BASE / "astra-human195/DOWNLOADS.json")
recent = read(BASE / "astra-raw-human213/RESULTS.json")
audio_inputs = []
labels = []
for row in segments:
    path = Path(row["privateOutput"])
    assert sha(path) == row["sha256"]
    with np.load(path) as data:
        for segment in row["segments"]:
            audio_inputs.append(data[f'segment{segment["index"]}'].copy())
            labels.append({"source": "201", "case": row.get("case"), "segment": segment["index"]})
for row in humans:
    path = Path(row["asset"])
    assert sha(path) == row["sha256"]
    rate, audio = wavfile.read(path)
    assert rate == 16000
    audio_inputs.append(np.r_[np.zeros(16000, np.float32), audio, np.zeros(16000, np.float32)])
    labels.append({"source": "195", "humanId": row["id"]})
audio_inputs.append(np.zeros(32000, np.float32))
labels.append({"source": "silence"})
assert len(audio_inputs) == len(old_greedy) == len(old_beam) == 47
for row in recent:
    path = Path(os.environ["LOCALAPPDATA"]) / "BAXY/C03-raw-human213-private" / f'h{row["human"]}-{row["condition"]}.npz'
    assert sha(path) == row["sha256"]
    audio_inputs.append(np.load(path)["window"].copy())
    labels.append({"source": "213", "human": row["human"], "condition": row["condition"]})
assert len(audio_inputs) == 63
save(OUT / "PREREG.json", {"scriptSha256": sha(Path(__file__)), "nativeSha256": sha(pyd),
    "method": "All47 original203/205 development controls plus all16 fixed213 windows, both greedy and beam in one shared model. Same CPU6/paths8/hotwords5, no trace requested. Record all126 outputs and compare known prior outputs. No assumption that differences are improvements. Context rejection/mixed batch checks retain206 contract.",
    "inputs": [{**label, "pcmSha256": hashlib.sha256(audio.tobytes()).hexdigest()} for label, audio in zip(labels, audio_inputs)]})
manifest = read(Path(os.environ["LOCALAPPDATA"]) / "BAXYRuntime/mind-runtime-v1.json")
stt = Path(manifest["stt_dir"])
recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
    encoder=str(stt / "encoder.int8.onnx"), decoder=str(stt / "decoder.int8.onnx"),
    joiner=str(stt / "joiner.int8.onnx"), tokens=str(stt / "tokens.txt"),
    num_threads=6, model_type="nemo_transducer", decoding_method="modified_beam_search",
    max_active_paths=8, hotwords_score=5)
def make_stream(audio, method, hotwords=""):
    stream = recognizer.create_stream(hotwords=hotwords) if hotwords else recognizer.create_stream()
    if method != "modified_beam_search":
        stream.set_option("decoding_method", method)
    stream.accept_waveform(16000, audio)
    return stream
results = []
for index, audio in enumerate(audio_inputs):
    for method in ["greedy_search", "modified_beam_search"]:
        stream = make_stream(audio, method)
        start = time.monotonic()
        recognizer.decode_stream(stream)
        previous = ((old_greedy if method == "greedy_search" else old_beam)[index]["text"]
                    if index < 47 else recent[index - 47]["text"] if method == "greedy_search" else None)
        text = stream.result.text.strip()
        row = {"index": index, **labels[index], "method": method, "text": text,
            "previous": previous, "changed": text != previous if previous is not None else None,
            "seconds": time.monotonic() - start, "applied": stream.get_option("applied_decoding_method")}
        assert row["applied"] == method
        results.append(row)
        save(OUT / "RESULTS.json", results)
    if index % 10 == 0:
        print(f"Completed {index + 1}/63 PCM in both decoders", flush=True)
hotwords = _compile_contextual_hotwords(stt / "tokens.txt", WakePhraseMatcher().aliases)
rejections = []
for method, context in [("greedy_search", hotwords), ("unknown_decoder", "")]:
    stream = make_stream(audio_inputs[42], method, context)
    try:
        recognizer.decode_stream(stream)
    except ValueError as error:
        rejections.append({"method": method, "context": bool(context), "error": str(error)})
    else:
        raise AssertionError("invalid decoding accepted")
mixed = [make_stream(audio_inputs[42], method) for method in ["greedy_search", "modified_beam_search"]]
recognizer.decode_streams(mixed)
assert [s.result.text.strip() for s in mixed] == [r["text"] for r in results if r["index"] == 42]
save(OUT / "COMPLETE.json", {"readings": len(results), "rejections": rejections, "mixedBatchPassed": True,
    "greedyChanges": sum(r["changed"] is True for r in results if r["method"] == "greedy_search"),
    "beamChanges": sum(r["changed"] is True for r in results if r["method"] == "modified_beam_search"), "exitCode": 0})
print(json.dumps(read(OUT / "COMPLETE.json")), flush=True)
