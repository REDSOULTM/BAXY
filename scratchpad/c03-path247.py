"""Offline linear path identification with held-out samples; never a live filter."""
import hashlib
import json
import os
from pathlib import Path

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from scipy.linalg import solve
from scipy.signal import resample_poly
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts/comprobaciones/C03"
PRIVATE = Path(os.environ["LOCALAPPDATA"]) / "BAXY"
OUT = BASE / "astra-path247"
OUT.mkdir(exist_ok=False)

def read(path):
    return json.loads(path.read_text(encoding="utf-8"))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

TAPS = 512
save("PREREG.json", {"scriptSha256": sha(Path(__file__)), "purpose": "Distinguish linear path coloration from missing/changed reference in frozen240243. Diagnose only, not an AEC candidate or semantic acceptance.", "method": "One512tap/32ms offline FIR centered on measured246 content lag. Fit alternate4000sample blocks and predict held-out4000sample blocks; remove128edge samples. Fixed ridge1e-6*mean Gram diagonal. Use all uninterrupted clips1,2,3 separately at both stages. No filter/lag/regularization search. Generator->loopback and loopback->microphone measured separately.", "limitations": "Noncausal local fitting uses future signal and pure echo controls; cannot establish a deployable filter or double-talk preservation. Measured template offsets include pitch ambiguity. First clipped243 greeting excluded from fitting because too little held-out audio is available.", "source246Sha256": sha(BASE / "astra-reference246/RESULTS.json")})

def identify(source, target, start, stop):
    start = max(start, TAPS // 2)
    stop = min(stop, len(target), len(source) - TAPS // 2)
    indices = np.arange(start + 128, stop - 128)
    # Windows centered around each target sample; diagnostic is intentionally noncausal.
    x = sliding_window_view(source, TAPS)[indices - TAPS // 2].copy()
    y = target[indices]
    train = ((indices - start) // 4000) % 2 == 0
    a, b = x[train], y[train]
    gram = a.T @ a
    gram.flat[::TAPS + 1] += 1e-6 * np.trace(gram) / TAPS
    weights = solve(gram, a.T @ b, assume_a="pos")
    predicted = x[~train] @ weights
    actual = y[~train]
    error = actual - predicted
    return {"trainingSamples": int(train.sum()), "heldoutSamples": int((~train).sum()), "heldoutR2": float(1 - np.dot(error, error) / np.dot(actual - actual.mean(), actual - actual.mean())), "residualRms": float(np.sqrt(np.mean(error ** 2))), "targetRms": float(np.sqrt(np.mean(actual ** 2))), "correlation": float(np.corrcoef(predicted, actual)[0, 1])}

results = []
with threadpool_limits(limits=1):
    for stage_record in read(BASE / "astra-reference246/RESULTS.json"):
        stage = stage_record["stage"]
        tap = PRIVATE / f"C03-voice{stage}-private/tap{stage}.npz"
        generated = PRIVATE / f"C03-voice{stage}-private/generated{stage}.npz"
        for path in [tap, generated]:
            assert sha(path) == stage_record["inputHashes"][str(path)]
        data, waves = np.load(tap), np.load(generated)
        ref = data["reference"][:, -512:].ravel().astype(np.float64) / 32768
        mic = data["microphone"].ravel().astype(np.float64)
        for clip in stage_record["clips"][1:]:
            i = clip["index"]
            wave = resample_poly(waves[f"audio{i}"], 320, 441).astype(np.float64)
            origin = clip["referenceContentOriginSamples"]
            first = 1600
            last = len(wave) - 1600
            loopback = ref[origin:origin + len(wave)]
            lag = clip["microphoneVsReferenceLagSamples"]
            microphone = mic[origin + lag:origin + lag + len(wave)]
            row = {"stage": stage, "clip": i, "generatorToLoopback": identify(wave, loopback, first, last), "loopbackToMicrophone": identify(loopback, microphone, first, last)}
            results.append(row)
            print(stage, i, "heldoutR2", row["generatorToLoopback"]["heldoutR2"], row["loopbackToMicrophone"]["heldoutR2"], flush=True)
save("RESULTS.json", results)
save("COMPLETE.json", {"exitCode": 0})
