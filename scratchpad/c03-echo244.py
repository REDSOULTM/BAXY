"""Reproduce physical243 using both integrated and frozen experimental DTLN512."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from baxy_mind.dtln_aec import EchoCanceller
from baxy_mind.voice import _looks_like_echo
from dtln_stream182 import EchoCanceller as Original

BASE = ROOT / "artifacts/comprobaciones/C03"
OUT = BASE / "astra-echo244"
PRIVATE_ROOT = Path(os.environ["LOCALAPPDATA"]) / "BAXY"
PRIVATE = PRIVATE_ROOT / "C03-echo244-private"
OUT.mkdir(exist_ok=False)
PRIVATE.mkdir(exist_ok=False)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

source = PRIVATE_ROOT / "C03-voice243-private/tap243.npz"
prior = json.loads((BASE / "astra-voice243/RESULTS.json").read_text(encoding="utf-8"))
assert sha(source) == next(row["sha256"] for row in prior["privateFiles"] if Path(row["path"]) == source)
save(OUT / "PREREG.json", {"method": "Exact full1317frames243 through fresh integrated DTLN512 and frozen adapter182(512), compare all clean samples and returned microphone/reference pairs. Compare recorded actual guard calls. No model, thresholds, gain or alignment change. Save pairs for real segmentation replay.", "inputSha256": sha(source), "scriptSha256": sha(Path(__file__)), "sourceSha256": sha(ROOT / "src/baxy_mind/dtln_aec.py"), "adapterSha256": sha(ROOT / "scratchpad/dtln_stream182.py")})
data = np.load(source)
mic, ref, clean, observations = [data[k] for k in ["microphone", "reference", "clean", "observations"]]
paired_mic = np.empty_like(mic)
paired_ref = np.empty(ref.shape, np.float32)
guards = np.zeros(len(mic), bool)
current, original = EchoCanceller(), Original(512)
try:
    for i in range(len(mic)):
        result = current.process(mic[i], ref[i])
        baseline = original.process(mic[i], ref[i])
        for a, b in zip(result, baseline):
            assert np.array_equal(a, b), (i, "adapter parity")
        assert np.array_equal(result[0], clean[i]), (i, "physical parity")
        paired_mic[i], paired_ref[i] = result[1:]
        guards[i] = _looks_like_echo(result[1], result[2])
        if observations[i, 5] != -1:
            assert guards[i] == bool(observations[i, 5]), (i, "guard")
finally:
    current.close()
    original.close()

def correlation(near, history):
    near = near.astype(np.float64); history = history.astype(np.float64)
    near -= near.mean()
    products = np.correlate(history, near, mode="valid")
    totals = np.r_[0., np.cumsum(history)]; squares = np.r_[0., np.cumsum(history * history)]
    n = len(near); sums = totals[n:] - totals[:-n]
    energy = squares[n:] - squares[:-n] - sums * sums / n
    denominator = np.linalg.norm(near) * np.sqrt(np.maximum(energy, 0))
    scores = np.divide(np.abs(products), denominator, out=np.zeros_like(products), where=denominator > 1e-6)
    best = int(np.argmax(scores))
    return {"score": float(scores[best]), "lagSamples": int(len(history) - n - best)}

events = json.loads((PRIVATE_ROOT / "C03-voice243-private/EVENTS.json").read_text(encoding="utf-8"))
frames = [int(np.argmin(abs(observations[:, 0] - e["time"]))) for e in events["events"] if e["event"] == "barge_in"]
rows = []
for frame in frames:
    for i in range(frame - 4, frame + 2):
        rows.append({"frame": i, "vad": float(observations[i, 4]), "guard": bool(guards[i]), "cleanRms": float(np.sqrt(np.mean(clean[i] ** 2))), "micRms": float(np.sqrt(np.mean(mic[i] ** 2))), "referenceRms": float(np.sqrt(np.mean(ref[i].astype(np.float64) ** 2))), "correlation": correlation(paired_mic[i], paired_ref[i])})
target = PRIVATE / "pairs244.npz"
np.savez(target, microphone=paired_mic, reference=paired_ref, guards=guards)
save(OUT / "RESULTS.json", {"frames": len(mic), "freshPhysicalExact": True, "frozenAdapterExact": True, "actualGuardsExact": True, "cancelFrames": frames, "triggerRows": rows, "privatePath": str(target), "privateSha256": sha(target)})
save(OUT / "COMPLETE.json", {"exitCode": 0})
print("Physical243 and original182 exactly reproduced; frames",len(mic),"cancellations",frames,flush=True)
