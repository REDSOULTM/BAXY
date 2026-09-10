"""Compare the structural status repair with the published source, without inference."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from baxy_mind import effect_intent as current
from baxy_mind.__main__ import _explicit_system_status_scope

BASE = "65282f2cdd6824bbe9095ab4ed54950a4938013b"
OUT = ROOT / "artifacts/comprobaciones/C03/FRONTED_STATUS750"
OUT.mkdir(exist_ok=True)
source_path = "src/baxy_mind/effect_intent.py"
original = subprocess.run(
    ["git", "show", f"{BASE}:{source_path}"], cwd=ROOT,
    check=True, capture_output=True,
).stdout
baseline = types.ModuleType("baxy_mind._effect_baseline750")
baseline.__package__ = "baxy_mind"
sys.modules[baseline.__name__] = baseline
exec(compile(original, source_path, "exec"), baseline.__dict__)
panel_path = ROOT / "artifacts/comprobaciones/C03/FRONTED_STATUS747/PREREG.json"
panel = json.loads(panel_path.read_text(encoding="utf-8"))["cases"]
rows = []
for case in panel:
    text = case["text"]
    old = baseline.resolve_explicit_effects(text, {"system.status"})
    new = current.resolve_explicit_effects(text, {"system.status"})
    rows.append({
        **case,
        "before_domain": baseline.operation_domain_is_grounded(text, "system.status"),
        "after_domain": current.operation_domain_is_grounded(text, "system.status"),
        "before_operations": list(old.operations) if old else [],
        "after_operations": list(new.operations) if new else [],
        "before_evidence": list(old.evidence) if old else [],
        "after_evidence": list(new.evidence) if new else [],
        "after_scope_original": _explicit_system_status_scope(text) if new else None,
        "after_scope_evidence": _explicit_system_status_scope(new.evidence[0]) if new else None,
    })

def write(name, data):
    (OUT / name).write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n",
    )

counts = {"cases": len(rows)}
for phase in ("before", "after"):
    counts[f"{phase}_correct_domain"] = sum(
        row[f"{phase}_domain"] == row["expected"] for row in rows
    )
    counts[f"{phase}_correct_resolution"] = sum(
        bool(row[f"{phase}_operations"]) == row["expected"] for row in rows
    )
counts["after_arguments_preserved"] = sum(
    row["after_scope_original"] is not None
    and row["after_scope_original"] == row["after_scope_evidence"]
    for row in rows if row["expected"]
)
write("RESULT.json", {
    "utc": datetime.now(timezone.utc).isoformat(), "baseline_commit": BASE,
    "baseline_source_sha256": hashlib.sha256(original).hexdigest(),
    "source_sha256": hashlib.sha256((ROOT / source_path).read_bytes()).hexdigest(),
    "panel": str(panel_path.relative_to(ROOT)),
    "panel_sha256": hashlib.sha256(panel_path.read_bytes()).hexdigest(),
    "counts": counts, "rows": rows,
    "scope": "Pure development comparison: no model, provider, UI, voice or survey credit.",
    "initial_development": (
        "First integrated patch:64/70 domain,70/70 resolution; then fixed stacked "
        "envelopes and topic-leading English negation. First owner run:2669pass/1fail "
        "on lost GPU identity in evidence; repaired whole status-clause evidence. "
        "These are development iterations, not preregistered acceptance campaigns."
    ),
    "coverage_added": 0, "model_promoted": False,
})
write("SOURCE_PINS.json", {
    name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    for name in (
        source_path,
        "tests/test_c03_fronted_machine_status.py",
        "experiments/stt_quality/audit_fresh_postweight_stt_sources.py",
        "experiments/stt_quality/evaluate_reserved_stt.py",
    )
})
assert counts["after_correct_domain"] == counts["after_correct_resolution"] == 70
assert counts["after_arguments_preserved"] == 50
print(json.dumps(counts))
