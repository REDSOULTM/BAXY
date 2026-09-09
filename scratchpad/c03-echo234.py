"""Reproduce Speex exactly and measure the physical232 interruption windows."""
import hashlib
import json
import os
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from baxy_mind.speex_aec import EchoCanceller
from baxy_mind.voice import _rms

BASE = ROOT / "artifacts/comprobaciones/C03"
OUT = BASE / "astra-echo234"
OUT.mkdir(exist_ok=False)
PRIVATE = Path(os.environ["LOCALAPPDATA"]) / "BAXY"

def read(p):
    return json.loads(p.read_text(encoding="utf-8"))

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def save(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def correlation(microphone, reference):
    mic, ref = np.asarray(microphone, np.float64), np.asarray(reference, np.float64)
    mic = mic - mic.mean()
    products = np.correlate(ref, mic, mode="valid")
    totals = np.r_[0., np.cumsum(ref)]
    squares = np.r_[0., np.cumsum(ref * ref)]
    sums = totals[len(mic):] - totals[:-len(mic)]
    energy = squares[len(mic):] - squares[:-len(mic)] - sums * sums / len(mic)
    divisor = np.linalg.norm(mic) * np.sqrt(np.maximum(energy, 0))
    scores = np.divide(np.abs(products), divisor, out=np.zeros_like(products), where=divisor > 1e-6)
    best = int(np.argmax(scores))
    return {"score": float(scores[best]), "lagSamples": len(ref) - len(mic) - best}

save(OUT / "PREREG.json", {
    "method": "Fresh exact product Speex replay of every221/232 recorded microphone/reference frame; compare every cleaned sample to physical trace. At fixed actual232 barge windows133–135 and440–442, measure the existing512-frame centered guard score and lag, plus longer1024/2048/4096 evidence windows within the same250ms lag range. Longer windows are diagnostics only, no proposed thresholds or product edits.",
    "criterion": "Determine whether scheduling/DSP nondeterminism changed the signal and whether short-frame reference correlation explains the physical guard decisions. No repeated physical capture or parameter sweep.",
    "scriptSha256": sha(Path(__file__)), "speexSourceSha256": sha(ROOT / "src/baxy_mind/speex_aec.py"),
    "voiceSourceSha256": sha(ROOT / "src/baxy_mind/voice.py"),
})
results = []
for stage in [221, 232]:
    path = PRIVATE / f"C03-voice{stage}-private/tap{stage}.npz"
    manifest = read(BASE / f"astra-voice{stage}/RESULTS.json")
    assert sha(path) == next(r["sha256"] for r in manifest["privateFiles"] if Path(r["path"]) == path)
    data = np.load(path)
    microphone, reference, clean, observed = [data[k] for k in ["microphone", "reference", "clean", "observations"]]
    canceller = EchoCanceller()
    replay = np.empty_like(clean)
    try:
        for i in range(len(clean)):
            replay[i] = canceller.process(microphone[i], reference[i])[0]
    finally:
        canceller.close()
    differences = np.abs(replay - clean)
    result = {"stage": stage, "frames": len(clean), "identicalFrames": int(np.all(replay == clean, axis=1).sum()),
        "maximumSampleDifference": float(differences.max()), "inputSha256": sha(path)}
    if stage == 232:
        assert np.array_equal(reference[1:, :-512], reference[:-1, 512:])
        played = reference[:, -512:].ravel()
        raw = microphone.ravel()
        details = []
        for i in [133, 134, 135, 440, 441, 442]:
            end = i * 512  # Speex returns the previous microphone/reference pair.
            windows = []
            for length in [512, 1024, 2048, 4096]:
                near = raw[end - length:end] * 32768
                ref = played[end - length - 4000:end]
                windows.append({"samples": length, **correlation(near, ref)})
            details.append({"frame": i, "monotonic": float(observed[i, 0]),
                "vad": float(observed[i, 4]), "guard": float(observed[i, 5]),
                "micRms": _rms(microphone[i - 1]), "cleanRms": _rms(clean[i]),
                "referenceRmsPcm": _rms(reference[i - 1]), "correlations": windows})
        result["bargeWindows"] = details
    results.append(result)
    save(OUT / "RESULTS.json", results)
    print(json.dumps(result), flush=True)
save(OUT / "COMPLETE.json", {"captures": 2, "exitCode": 0})
