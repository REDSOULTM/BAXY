"""Check integrated DTLN512 against all ten frozen development outputs238."""
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
from baxy_mind.dtln_aec import EchoCanceller
from baxy_mind.voice import _looks_like_echo

BASE = ROOT / "artifacts/comprobaciones/C03"
OUT = BASE / "astra-integration242"
PRIVATE = Path(os.environ["LOCALAPPDATA"]) / "BAXY"

def read(path):
    return json.loads(path.read_text(encoding="utf-8"))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

assert importlib.metadata.version("ai-edge-litert") == "2.2.0"
assert importlib.metadata.version("sherpa-onnx") == "1.13.4+baxy.2"
assert not any("experiments" in path for path in sys.path)
cases = read(BASE / "astra-dsp238/PREREG.json")["cases"]
prior = {row["case"]: row for row in read(BASE / "astra-dsp238/RESULTS.json")}
save("PARITY_PREREG.json", {"scriptSha256": sha(Path(__file__)), "baseline": "astra-dsp238", "cases": [c["id"] for c in cases], "source": {p: sha(ROOT / p) for p in ["src/baxy_mind/dtln_aec.py", "src/baxy_mind/voice.py", "pylock.runtime-win-x64.toml"]}, "acceptance": "Every cleaned sample and actual returned-pair echo guard must equal frozen238. This is DSP integration parity, not ASR or full C03 acceptance."})
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
    expected = prior[case["id"]]
    expected_path = Path(expected["privatePath"])
    assert sha(expected_path) == expected["sha256"]
    frozen = np.load(expected_path)
    engine = EchoCanceller()
    elapsed = []
    try:
        for i in range(len(mic)):
            started = time.perf_counter()
            clean, paired_mic, paired_ref = engine.process(mic[i], ref[i])
            elapsed.append((time.perf_counter() - started) * 1000)
            assert np.array_equal(clean, frozen["clean"][i]), (case["id"], i, "clean")
            assert _looks_like_echo(paired_mic, paired_ref) == frozen["guards"][i], (case["id"], i, "guard")
    finally:
        engine.close()
    results.append({"case": case["id"], "frames": len(mic), "cleanExact": True, "guardsExact": True, "modelSha256": engine.sha256, "baselineSha256": expected["sha256"], "dspMs": {"mean": float(np.mean(elapsed)), "p99": float(np.quantile(elapsed, .99)), "max": max(elapsed)}})
    save("PARITY_RESULTS.json", results)
    print(case["id"], len(mic), "exact", flush=True)
save("PARITY_COMPLETE.json", {"exitCode": 0, "cases": len(results), "frames": sum(r["frames"] for r in results)})
