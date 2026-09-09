"""Run four fixed214 windows through isolated native boundary observation."""
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts/comprobaciones/C03"
OUT = BASE / "astra-native-trace215-retry"
PRIVATE = Path(os.environ["LOCALAPPDATA"]) / "BAXY/C03-native-trace215-retry-private"
EXP = Path("D:/BAXYRuntime/experiments/voice/sherpa205")
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):
    return json.loads(path.read_text(encoding="utf-8"))
def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")

build = read(OUT / "BUILD_COMPLETE.json")
assert all(sha(Path(row["path"])) == row["sha256"] for row in build["binaries"])
assert not (OUT / "RESULTS.json").exists()
bundle = EXP / "bundle-trace215"
pyd = next(bundle.glob("_sherpa_onnx*.pyd"))
dll_handle = os.add_dll_directory(str(bundle))
name = "sherpa_onnx.lib._sherpa_onnx"
spec = importlib.util.spec_from_file_location(name, pyd)
native = importlib.util.module_from_spec(spec)
sys.modules[name] = native
spec.loader.exec_module(native)
import sherpa_onnx

inputs = read(OUT / "PREREG.json")["inputs"]
expected = [r for r in read(BASE / "astra-native-boundary214/RESULTS.json") if r["recognizer"] == "parakeet_native"]
manifest_path = Path(os.environ["LOCALAPPDATA"]) / "BAXYRuntime/mind-runtime-v1.json"
stt = Path(read(manifest_path)["stt_dir"])
save(OUT / "RUN_PREREG.json", {"scriptSha256": sha(Path(__file__)), "nativeSha256": sha(pyd),
    "method": "Four214 exact windows, isolated native trace, same beam8 model with per-stream greedy option. Assert text/ack parity214. No product or recording.",
    "runtimeSha256": sha(manifest_path)})
recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
    encoder=str(stt / "encoder.int8.onnx"), decoder=str(stt / "decoder.int8.onnx"),
    joiner=str(stt / "joiner.int8.onnx"), tokens=str(stt / "tokens.txt"),
    num_threads=6, model_type="nemo_transducer", decoding_method="modified_beam_search",
    max_active_paths=8, hotwords_score=5)

def stats(prefix, stage):
    path = Path(str(prefix) + f".{stage}.f32")
    shape = tuple(map(int, Path(str(prefix) + f".{stage}.shape").read_text().split()))
    data = np.fromfile(path, dtype=np.float32).reshape(shape)
    finite = np.isfinite(data)
    values = data[finite].astype(np.float64)
    return {"shape": list(shape), "nonfinite": int((~finite).sum()),
        "min": float(values.min()) if len(values) else None,
        "max": float(values.max()) if len(values) else None,
        "mean": float(values.mean()) if len(values) else None,
        "std": float(values.std()) if len(values) else None, "sha256": sha(path)}

results = []
for index, row in enumerate(inputs):
    path = Path(os.environ["LOCALAPPDATA"]) / "BAXY/C03-raw-human213-private" / f'h{row["human"]}-{row["condition"]}.npz'
    assert sha(path) == row["sha256"]
    audio = np.load(path)["window"]
    prefix = PRIVATE / f"case{index}"
    stream = recognizer.create_stream()
    stream.set_option("decoding_method", "greedy_search")
    stream.set_option("baxy_trace_prefix", str(prefix))
    stream.accept_waveform(16000, audio)
    start = time.monotonic()
    recognizer.decode_stream(stream)
    text = stream.result.text.strip()
    with Path(str(prefix) + ".joiner.tsv").open() as file:
        decisions = list(csv.DictReader(file, delimiter="\t"))
    result = {"index": index, "human": row["human"], "condition": row["condition"], "text": text,
        "expected": expected[index]["nativeText"], "seconds": time.monotonic() - start,
        "applied": stream.get_option("applied_decoding_method"),
        "features": stats(prefix, "features"), "encoder": stats(prefix, "encoder"),
        "joiner": {"decisions": len(decisions),
            "nonfiniteValues": sum(int(r["nonfinite"]) for r in decisions),
            "blankDecisions": sum(int(r["y"]) == int(r["vocab"]) - 1 for r in decisions),
            "tokenIds": sorted({int(r["y"]) for r in decisions}),
            "sha256": sha(Path(str(prefix) + ".joiner.tsv"))}}
    results.append(result)
    save(OUT / "RESULTS.json", results)
    print(json.dumps(result, ensure_ascii=True), flush=True)
    assert result["applied"] == "greedy_search" and text == expected[index]["nativeText"]
save(OUT / "COMPLETE.json", {"readings": len(results), "parity214": len(results), "exitCode": 0})
