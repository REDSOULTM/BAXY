"""Install only the declared baxy.2 update and prove the resulting graph."""
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/comprobaciones/C03/astra-install218"
OUT.mkdir(exist_ok=False)
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def save(name, data):
    (OUT / name).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
def versions():
    return {dist.metadata["Name"]: dist.version for dist in importlib.metadata.distributions()}
before = versions()
assert before["sherpa-onnx"] == "1.13.4+baxy.1"
assert before["sherpa-onnx-core"] == "1.13.4"
manifest = Path(os.environ["LOCALAPPDATA"]) / "BAXYRuntime/mind-runtime-v1.json"
manifest_hash = sha(manifest)
sources = ["scripts/build_sherpa_runtime.py", "constraints-runtime-win-x64.txt",
    "src/baxy_mind/requirements-voice.txt", "pylock.runtime-win-x64.toml",
    "tests/test_sherpa_runtime_package.py", "tests/test_python_runtime_lock.py",
    "runtime_wheels/sherpa-nemo-normalization.patch",
    "runtime_wheels/sherpa_onnx-1.13.4+baxy.2-cp312-cp312-win_amd64.whl"]
save("PREREG.json", {"utc": datetime.now(timezone.utc).isoformat(), "scriptSha256": sha(Path(__file__)),
    "before": before, "registrationSha256": manifest_hash,
    "sources": {name: sha(ROOT / name) for name in sources},
    "method": "Complete runtime lock pip install only-binary/require-hashes/no-deps. Expected distribution delta exclusively sherpa-onnx baxy.1 to baxy.2; core/model/registration unchanged. Native math8 and wheel identity1 passed; product219 follows.",
    "rollbackWheel": str(ROOT / "runtime_wheels/sherpa_onnx-1.13.4+baxy.1-cp312-cp312-win_amd64.whl"),
    "knownOpenQuality": "Regressions217 remain open; candidate integration does not certify final ASR/voice/C03."})
with (OUT / "PIP.log").open("w", encoding="utf-8") as log:
    result = subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
        "--only-binary=:all:", "--require-hashes", "--no-deps", "--report", str(OUT / "PIP_REPORT.json"),
        "-r", str(ROOT / "pylock.runtime-win-x64.toml")], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
after = versions()
delta = {name: [before.get(name), after.get(name)] for name in sorted(before.keys() | after.keys()) if before.get(name) != after.get(name)}
save("AFTER.json", {"versions": after, "changed": delta, "pipExitCode": result.returncode,
    "registrationUnchanged": sha(manifest) == manifest_hash})
assert result.returncode == 0
assert delta == {"sherpa-onnx": ["1.13.4+baxy.1", "1.13.4+baxy.2"]}
assert sha(manifest) == manifest_hash
save("COMPLETE.json", {"exitCode": 0, "onlyExpectedDistributionChanged": True, "registrationUnchanged": True})
print(json.dumps(delta), flush=True)
