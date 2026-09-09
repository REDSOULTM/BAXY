"""Inspect frozen loopback against the PCM actually generated in240 and243."""
import hashlib
import json
import os
from pathlib import Path

import numpy as np
from scipy.signal import correlate, resample_poly

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts/comprobaciones/C03"
PRIVATE = Path(os.environ["LOCALAPPDATA"]) / "BAXY"
OUT = BASE / "astra-reference246"
OUT.mkdir(exist_ok=False)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    return json.loads(path.read_text(encoding="utf-8"))

def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def best_match(signal, template):
    signal = signal.astype(np.float64)
    template = template.astype(np.float64)
    template -= template.mean()
    n = template.size
    products = correlate(signal, template, mode="valid", method="fft")
    sums = np.r_[0., np.cumsum(signal)]
    squares = np.r_[0., np.cumsum(signal ** 2)]
    mean_sums = sums[n:] - sums[:-n]
    energy = squares[n:] - squares[:-n] - mean_sums ** 2 / n
    denominator = np.linalg.norm(template) * np.sqrt(np.maximum(energy, 0))
    scores = np.divide(np.abs(products), denominator, out=np.zeros_like(products), where=denominator > 1e-9)
    index = int(np.argmax(scores))
    return {"index": index, "correlation": float(scores[index]), "gain": float(products[index] / np.dot(template, template))}

save("PREREG.json", {"scriptSha256": sha(Path(__file__)), "previousTurn": "progress: integrated242 and isolated physical243 failure in244245", "method": "Frozen240/243 only; validate overlapping reference windows, reconstruct recent reference samples, compare to each actual generated Piper PCM resampled22050->16000. Locate the first0.5s high-energy template within each recording, then inspect consecutive0.25s sections at the same content offset. Search local +/-64sample deviations only for measurement, not compensation. No output regeneration, physical effects, source edits, ASR or parameter sweep.", "limits": "Observation monotonic times are not saved native ADC times. Signal analysis can detect reference corruption/drift but does not directly measure the native clock origin. PCM resampling differs from Windows device conversion, so equality is not assumed.", "stages": [240, 243]})
results = []
for stage in (240, 243):
    record = read(BASE / f"astra-voice{stage}/RESULTS.json")
    paths = {name: PRIVATE / f"C03-voice{stage}-private/{name}{stage}.npz" for name in ["tap", "generated"]}
    for path in paths.values():
        assert sha(path) == next(row["sha256"] for row in record["privateFiles"] if Path(row["path"]) == path)
    data = np.load(paths["tap"])
    generated = np.load(paths["generated"])
    reference = data["reference"]
    overlaps_equal = np.array_equal(reference[1:, :-512], reference[:-1, 512:])
    ref = reference[:, -512:].ravel().astype(np.float64) / 32768
    mic = data["microphone"].ravel().astype(np.float64)
    obs = data["observations"]
    state = read(PRIVATE / f"C03-voice{stage}-private/EVENTS.json")
    speaking_times = [e["time"] for e in state["states"] if e["speaking"] and e["changed"]]
    row = {"stage": stage, "inputHashes": {str(p): sha(p) for p in paths.values()}, "referenceOverlapExact": bool(overlaps_equal), "clips": []}
    for i in range(4):
        wave = resample_poly(generated[f"audio{i}"], 320, 441).astype(np.float64)
        # Independent template selection uses energy in the generated PCM only.
        offsets = range(0, min(len(wave) - 8000, 8000) + 1, 1600)
        offset = max(offsets, key=lambda j: np.dot(wave[j:j + 8000], wave[j:j + 8000]))
        template = wave[offset:offset + 8000]
        ref_match = best_match(ref, template)
        mic_match = best_match(mic, template)
        origin = ref_match["index"] - offset
        sections = []
        for start in range(0, len(wave) - 4000 + 1, 4000):
            left, right = max(0, origin + start - 64), min(len(ref), origin + start + 4000 + 64)
            match = best_match(ref[left:right], wave[start:start + 4000])
            sections.append({"startSeconds": start / 16000, "correlation": match["correlation"], "gain": match["gain"], "shiftSamples": match["index"] + left - (origin + start)})
        frame = min(len(obs) - 1, max(0, origin // 512))
        row["clips"].append({"index": i, "generatedSamples": int(len(wave)), "templateOffset": offset, "referenceMatch": ref_match, "microphoneMatch": mic_match, "microphoneVsReferenceLagSamples": mic_match["index"] - ref_match["index"], "referenceContentOriginSamples": origin, "observationDelayFromSpeakingSecondsApprox": float(obs[frame, 0] - speaking_times[i]), "sections": sections})
    results.append(row)
save("RESULTS.json", results)
save("COMPLETE.json", {"exitCode": 0})
for row in results:
    print(row["stage"], "overlap", row["referenceOverlapExact"])
    for clip in row["clips"]:
        print(clip["index"], "reference",clip["referenceMatch"],"mic",clip["microphoneMatch"],"lag",clip["microphoneVsReferenceLagSamples"])
