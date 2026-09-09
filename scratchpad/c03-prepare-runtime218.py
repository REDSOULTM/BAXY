"""Freeze integration intent and extract only the proven normalization patch."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts/comprobaciones/C03"
OUT = BASE / "astra-runtime218"
OUT.mkdir(exist_ok=False)
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
combined = (BASE / "astra-normalize216/combined-observer.patch").read_bytes()
sections = combined.split(b"diff --git ")[1:]
owners = [b"sherpa-onnx/csrc/math-test.cc", b"sherpa-onnx/csrc/math.cc"]
selected = [b"diff --git " + part for part in sections if any(part.startswith(b"a/" + name + b" b/" + name + b"\n") for name in owners)]
assert len(selected) == 2
patch = ROOT / "runtime_wheels/sherpa-nemo-normalization.patch"
assert not patch.exists()
patch.write_bytes(b"".join(selected))
record = {"utc": datetime.now(timezone.utc).isoformat(), "scriptSha256": sha(Path(__file__)),
    "method": "Integrate exact math.cc/math-test.cc backport3857 atop207 per-stream decoder. Build baxy.2 with strict source/patch checks and native math tests; no observer source. Verify owner/Fast/lock/package then install via complete hashed lock and compare actual product63greedy outputs to217.",
    "knownOpenQuality": "217 has numeric content and echo regressions. Integration is a candidate, not final ASR/audio/C03 acceptance. No change to models or registered manifest; preserve baxy.1 rollback.",
    "patchSha256": sha(patch), "regression217Sha256": sha(BASE / "astra-normalize-regression217/RESULTS.json"),
    "before": {name: sha(ROOT / name) for name in ["scripts/build_sherpa_runtime.py", "constraints-runtime-win-x64.txt", "src/baxy_mind/requirements-voice.txt", "pylock.runtime-win-x64.toml", "tests/test_sherpa_runtime_package.py", "runtime_wheels/README.md"]}}
(OUT / "PREREG.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(record["patchSha256"])
