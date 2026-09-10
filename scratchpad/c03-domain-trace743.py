"""Locate false domain vetoes without changing the source under Full6."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from baxy_mind import effect_intent

OUT = ROOT/"artifacts/comprobaciones/C03/DOMAIN_TRACE743"
PRIVATE = Path(os.environ["LOCALAPPDATA"])/"BAXY/C03-domain-trace743-private"
OUT.mkdir(exist_ok=False)
PRIVATE.mkdir(exist_ok=False)
SOURCE = ROOT/"src/baxy_mind/effect_intent.py"
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
source_hash = sha(SOURCE)
captured_path = Path(os.environ["LOCALAPPDATA"])/"BAXY/C03-native-product736-k2-private/domain-attribution-replay.json"
captured = json.loads(captured_path.read_text(encoding="utf-8"))
prior_path = ROOT/"artifacts/comprobaciones/C03/astra-window-domain-probe707/RESULT.json"
prior = json.loads(prior_path.read_text(encoding="utf-8"))
cases = [{"id": row["case_id"], "text": row["text"], "operation": row["before"]["operation"], "expected": True}
    for row in captured]
cases += [{"id": "707-"+row["id"], "text": row["text"], "operation": "window.resolve", "expected": row["expected_domain"]}
    for row in prior["rows"]]
names = ["operation_identity_is_a_near_miss", "_curated_domain_is_grounded", "_window_domain",
         "has_named_window_target", "_system_status_domain", "_machine_status_scope",
         "_is_machine_knowledge_or_diagnosis", "_is_past_or_hypothetical_state", "_has"]
originals = {name: getattr(effect_intent, name) for name in names}
trace = []


def wrap(name, original):
    def call(*args, **kwargs):
        value = original(*args, **kwargs)
        record = {"function": name, "result": value}
        if name == "_has":
            record["pattern"] = args[1]
        trace.append(record)
        return value
    return call


rows = []
try:
    for name, original in originals.items():
        setattr(effect_intent, name, wrap(name, original))
    for case in cases:
        trace = []
        result = effect_intent.operation_domain_is_grounded(case["text"], case["operation"])
        rows.append({**case, "actual": result, "trace": trace})
finally:
    for name, original in originals.items():
        setattr(effect_intent, name, original)
assert sha(SOURCE) == source_hash
(PRIVATE/"traces.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
summary = {
    "utc": datetime.now(timezone.utc).isoformat(), "source_sha256": source_hash,
    "inputs": {"captured736": sha(captured_path), "controls707": sha(prior_path)},
    "cases": len(rows), "correct": sum(row["actual"]==row["expected"] for row in rows),
    "captured": [{"id": row["id"], "operation": row["operation"], "actual": row["actual"],
        "predicates": [r for r in row["trace"] if r["function"] != "_has"]} for row in rows[:3]],
    "private_sha256": sha(PRIVATE/"traces.json"), "source_changed": False,
    "model_calls": 0, "adopted": False, "survey_coverage_added": 0,
}
(OUT/"RESULT.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False))
