"""Read-only diagnosis of remaining Full526 failures."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


audit = module("r278", "experiments/mind_router_spike/audit_line_ending_seal_damage_r278.py").classify(ROOT)
print(json.dumps({"restorable": audit["restorable"], "restorableCount": audit["restorableCount"]}))
old = json.loads((ROOT / "artifacts/runtime/registered_runtime_expectation_r281.json").read_text())
runtime = module("r281", "experiments/mind_router_spike/attest_registered_runtime_r281.py")
manifest = runtime.read_manifest()
actual = runtime.describe(manifest)
print(json.dumps({"runtime_diff": {key: {"old": old["expected"].get(key), "current": value} for key, value in actual.items() if value != old["expected"].get(key)}}))
for line in (ROOT / "artifacts/holdout/generalization_product_holdout_v6.jsonl").read_text(encoding="utf-8").splitlines():
    row = json.loads(line)
    if row["case_id"].startswith("r6-out-of-scope-28-"):
        print(json.dumps(row, ensure_ascii=False))
from scripts.goal095_09511c_revalidate import live_mission_chains
try:
    live_mission_chains()
except Exception as exc:
    import traceback
    traceback.print_exc(limit=5)
