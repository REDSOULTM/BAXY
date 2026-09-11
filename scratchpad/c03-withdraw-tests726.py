"""Preserve rejected test prototypes and restore the original acceptance scope."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import subprocess

root = Path(__file__).resolve().parents[1]
base = root / "artifacts/comprobaciones/C03"
out = base / "astra-test-fidelity726"
out.mkdir(exist_ok=False)
candidate = json.loads((base / "astra-full5-timeout-repair724/CANDIDATE.json").read_text(encoding="utf-8"))
originals = {
    "tests/test_product_packaging.py": "5ba170a05a877e31a9d023468856b3403fdda066ebd75b432a7cf7166730501f",
    "tests/test_sidecar_lifecycle.py": "4ac312b869624d261e047521bc918d9ff025194d8c9186dd9b5fae5a8959656d",
}
restored = []
for relative, original_hash in originals.items():
    path = root / relative
    current = path.read_bytes()
    assert hashlib.sha256(current).hexdigest() == candidate["sources"][relative]
    original = subprocess.check_output(["git", "show", "HEAD:" + relative], cwd=root)
    assert hashlib.sha256(original).hexdigest() == original_hash
    archived = out / ("REJECTED724_" + path.name)
    archived.write_bytes(current)
    assert archived.read_bytes() == current
    path.write_bytes(original)
    assert path.read_bytes() == original
    restored.append({"path": relative, "restored_sha256": original_hash,
                     "rejected_sha256": hashlib.sha256(current).hexdigest(),
                     "prototype": archived.name})
product = json.loads((base / "astra-catalog-source712/CANDIDATE.json").read_text(encoding="utf-8"))
assert all(hashlib.sha256((root / name).read_bytes()).hexdigest() == value for name, value in product["sources"].items())
(out / "RESULT.json").write_text(json.dumps({
    "utc": dt.datetime.now(dt.timezone.utc).isoformat(), "restored": restored,
    "reason": "Goal requires full validation without narrowing or relaxing; controlled smaller repository and shifted3s origin cannot replace the original acceptance tests",
    "status": "candidate724_withdrawn", "candidate712_unchanged": True,
    "new_coverage": 0, "goal_complete": False,
}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("Both original test files restored exactly;724 withdrawn,712 preserved.")
