"""Freeze original AEC3 on11current fixed controls before any ASR."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time

import numpy as np
from scipy.io import wavfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from baxy_mind.voice import _looks_like_echo
from webrtc_stream248 import EchoCanceller

BASE = ROOT / "artifacts/comprobaciones/C03"
OUT = BASE / "astra-webrtc248"
PRIVATE_ROOT = Path(os.environ["LOCALAPPDATA"]) / "BAXY"
PRIVATE = PRIVATE_ROOT / "C03-webrtc248-private"
PRIVATE.mkdir(exist_ok=False)

def read(path):
    return json.loads(path.read_text(encoding="utf-8"))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

for path, expected in read(BASE / "astra-source242-snapshot/FILES.json").items():
    assert sha(ROOT / path) == expected
assert read(OUT / "TIMING.json")["bridgeExact"]
cases = read(BASE / "astra-dsp238/PREREG.json")["cases"]
prior = {r["case"]: r for r in read(BASE / "astra-dsp238/RESULTS.json")}
tap = PRIVATE_ROOT / "C03-voice243-private/tap243.npz"
record = read(BASE / "astra-voice243/RESULTS.json")
expected = next(r["sha256"] for r in record["privateFiles"] if Path(r["path"]) == tap)
cases.append({"id": "echo243", "sourcePath": str(tap), "sourceSha256": expected, "human": None, "referenceText": None})
save("DSP_PREREG.json", {"scriptSha256": sha(Path(__file__)), "adapterSha256": sha(ROOT / "scratchpad/webrtc_stream248.py"), "cases": cases, "method": "Exactly238mic/ref and speaking masks, plus actual243. Original174AEC3 fresh per timeline. No source edits/ASR until11outputs frozen. Cold bridge and native delay validated first. Same raw-pair guard and normalized audio.", "next": "Real source242 segmentation/Silero and baxy.2 final ASR for11timelines plus8fixedhumanwindows; compare239 literal outputs; no echo-only acceptance."})
results = []
for case in cases:
    source = Path(case["sourcePath"])
    assert sha(source) == case["sourceSha256"]
    data = np.load(source)
    mic, ref = data["microphone"], data["reference"]
    if case["human"] is not None:
        original = Path(case["originalPath"])
        assert sha(original) == case["originalSha256"]
        rate, audio = wavfile.read(original)
        assert rate == 16000
        near = np.zeros(mic.size, np.float32)
        near[case["onset"]:case["onset"] + len(audio)] = audio * case["gain"]
        mixed = case["id"].endswith("raw")
        mic = near.reshape(mic.shape) + (mic if mixed else 0)
        if not mixed:
            ref = np.zeros_like(ref)
    if case["id"] in prior:
        previous = prior[case["id"]]
        frozen = Path(previous["privatePath"])
        assert sha(frozen) == previous["sha256"]
        speaking = np.load(frozen)["speaking"]
    else:
        speaking = data["observations"][:, 3].astype(bool)
    engine = EchoCanceller()
    clean = np.empty_like(mic)
    guards = np.zeros(len(mic), bool)
    elapsed = []
    try:
        for i in range(len(mic)):
            started = time.perf_counter()
            frame, near, history = engine.process(mic[i], ref[i])
            elapsed.append((time.perf_counter() - started) * 1000)
            clean[i] = frame
            guards[i] = _looks_like_echo(near, history)
    finally:
        engine.close()
    target = PRIVATE / f'{case["id"]}-aec3.npz'
    np.savez(target, clean=clean, guards=guards, speaking=speaking, dspMs=elapsed)
    row = {"case": case["id"], "backend": "aec3", "human": case["human"], "referenceText": case["referenceText"], "frames": len(mic), "engineSha256": engine.sha256, "privatePath": str(target), "sha256": sha(target), "dspMs": {"mean": float(np.mean(elapsed)), "p99": float(np.quantile(elapsed, .99)), "max": max(elapsed)}}
    if case.get("humanWindowSamples") is not None:
        row["humanWindowSamples"] = case["humanWindowSamples"]
    results.append(row)
    save("RESULTS.json", results)
    print(case["id"], row["dspMs"], flush=True)
save("COMPLETE.json", {"exitCode": 0, "cases": len(cases), "outputs": len(results)})
