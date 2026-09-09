"""Freeze Speex/DTLN128 outputs on RAW physical and fixed human controls."""
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
from baxy_mind.speex_aec import EchoCanceller as Speex
from baxy_mind.voice import _looks_like_echo
from dtln_stream182 import EchoCanceller as Dtln

BASE = ROOT / "artifacts/comprobaciones/C03"
OUT = BASE / "astra-dsp236"
PRIVATE_ROOT = Path(os.environ["LOCALAPPDATA"]) / "BAXY"
PRIVATE = PRIVATE_ROOT / "C03-dsp236-private"
OUT.mkdir(exist_ok=False)
PRIVATE.mkdir(exist_ok=False)

def read(path):
    return json.loads(path.read_text(encoding="utf-8"))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

assert importlib.metadata.version("sherpa-onnx") == "1.13.4+baxy.2"
for relative, expected in read(BASE / "astra-source230-snapshot/FILES.json").items():
    assert sha(ROOT / relative) == expected, relative
cases = []
for stage in [221, 232]:
    path = PRIVATE_ROOT / f"C03-voice{stage}-private/tap{stage}.npz"
    rows = read(BASE / f"astra-voice{stage}/RESULTS.json")["privateFiles"]
    assert sha(path) == next(row["sha256"] for row in rows if Path(row["path"]) == path)
    data = np.load(path)
    cases.append({"id": f"echo{stage}", "mic": data["microphone"], "ref": data["reference"],
        "speaking": data["observations"][:, 3].astype(bool), "sourcePath": str(path), "sourceSha256": sha(path),
        "expectedSpeex": data["clean"], "human": None, "referenceText": None})
capture = read(BASE / "astra-raw-capture211/RESULTS.json")
raw_path = PRIVATE_ROOT / "C03-raw-capture211-private/raw.npz"
assert sha(raw_path) == next(row["sha256"] for row in capture["streams"] if row["mode"] == "raw")
data = np.load(raw_path)
mic, ref, timing = [data[k] for k in ["microphone", "reference", "timing"]]
origin = capture["playback"]["streamTime"] + capture["playback"]["latency"]
intervals = np.asarray(read(BASE / "astra-raw-capture211/PREREG.json")["intervalsSeconds"]) + origin
mask_time = timing[:, 0] - .032
speaking = np.any((mask_time[:, None] >= intervals[None, :, 0]) & (mask_time[:, None] < intervals[None, :, 1]), axis=1)
humans = read(BASE / "astra-human195/DOWNLOADS.json")
for row in read(BASE / "astra-raw-human213/RESULTS.json"):
    if row["condition"] not in {"near_speex", "raw_speex"}:
        continue
    human = humans[row["human"]]
    original_path = Path(human["asset"])
    assert sha(original_path) == human["sha256"]
    rate, original = wavfile.read(original_path)
    assert rate == 16000
    near = np.zeros(mic.size, np.float32)
    near[row["onset"]:row["onset"] + len(original)] = original * row["gain"]
    mixed = row["condition"] == "raw_speex"
    prior_path = PRIVATE_ROOT / "C03-raw-human213-private" / f'h{row["human"]}-{row["condition"]}.npz'
    assert sha(prior_path) == row["sha256"]
    cases.append({"id": f'h{row["human"]}-{"raw" if mixed else "near"}',
        "mic": near.reshape(mic.shape) + (mic if mixed else 0), "ref": ref if mixed else np.zeros_like(ref),
        "speaking": speaking if mixed else np.zeros(len(mic), bool), "human": row["human"],
        "referenceText": human["rawTranscription"], "sourcePath": str(raw_path), "sourceSha256": sha(raw_path),
        "originalPath": str(original_path), "originalSha256": human["sha256"], "gain": row["gain"],
        "onset": row["onset"], "expectedSpeex": np.load(prior_path)["clean"],
        "humanWindowSamples": [row["onset"] - 16000, row["onset"] + len(original) + 16000]})
save(OUT / "PREREG.json", {
    "utc": datetime.now(timezone.utc).isoformat(), "scriptSha256": sha(Path(__file__)),
    "method": "Ten fixed timelines times fresh Speex or unchanged DTLN128 adapter182. Exact physical221/232 plus eight constructed human RAW213 timelines, no new gain/delay/model search. Save full cleaned frames and actual returned-pair guard results. Every Speex output must reproduce its existing capture213/221/232 exactly. No ASR until outputs frozen.",
    "newEvidenceJustifyingComparison": "Earlier DTLN rejection preceded RAW bypass of Windows adaptive AEC/NS and numerical normalization fix baxy.2. Current comparison isolates backend under these corrected conditions.",
    "next": "All20 outputs through source230 real segmentation/Silero and installed baxy.2 without hints; compare full literals and interruption decisions. Four human fixed windows additionally isolate segmentation from ASR if needed.",
    "limitations": "Fixed speaking mask for both algorithms. Physical masks are actual221/232; constructed-human mask is approximate212 and does not change after counterfactual cancellation. No physical human acceptance or runtime promotion.",
    "source230": read(BASE / "astra-source230-snapshot/FILES.json"),
    "adapterSha256": sha(ROOT / "scratchpad/dtln_stream182.py"),
    "dtlnDownloads": read(BASE / "astra-dtln179/DOWNLOADS.json"),
    "cases": [{k: v for k, v in case.items() if not isinstance(v, np.ndarray)} for case in cases],
})
results = []
for case in cases:
    for name, factory in [("speex", Speex), ("dtln128", Dtln)]:
        engine = factory()
        frames = len(case["mic"])
        clean = np.empty((frames, 512), np.float32)
        guards = np.zeros(frames, bool)
        elapsed = np.zeros(frames, np.float64)
        try:
            for i in range(frames):
                start = time.perf_counter()
                frame, paired_mic, paired_ref = engine.process(case["mic"][i], case["ref"][i])
                elapsed[i] = (time.perf_counter() - start) * 1000
                clean[i] = frame
                guards[i] = _looks_like_echo(paired_mic, paired_ref)
        finally:
            engine.close()
        assert np.isfinite(clean).all()
        if name == "speex":
            assert np.array_equal(clean, case["expectedSpeex"]), case["id"]
        target = PRIVATE / f'{case["id"]}-{name}.npz'
        np.savez(target, clean=clean, guards=guards, speaking=case["speaking"], dspMs=elapsed)
        row = {"case": case["id"], "backend": name, "human": case["human"],
            "referenceText": case["referenceText"], "frames": frames, "engineSha256": engine.sha256,
            "privatePath": str(target), "sha256": sha(target),
            "dspMs": {"mean": float(elapsed.mean()), "p99": float(np.quantile(elapsed, .99)), "max": float(elapsed.max())}}
        if case.get("humanWindowSamples") is not None:
            row["humanWindowSamples"] = case["humanWindowSamples"]
        results.append(row)
        save(OUT / "RESULTS.json", results)
        print(json.dumps({k: row[k] for k in ["case", "backend", "frames", "dspMs"]}), flush=True)
save(OUT / "COMPLETE.json", {"cases": len(cases), "outputs": len(results), "speexExactParities": len(cases), "exitCode": 0})
