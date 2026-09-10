"""Replay the shared domain veto against three captured native decisions."""
from pathlib import Path
import hashlib
import json
import os
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))
from baxy_mind.__main__ import _previous_user_request, apply_operation_domain_grounding_veto

private = Path(os.environ["LOCALAPPDATA"]) / "BAXY/C03-native-product736-k2-private"
events = [json.loads(line) for line in (private / "decision-boundary.jsonl").open(encoding="utf-8-sig")]
outputs = {row["id"]: row for row in events if row["stage"] == "output"}
panel = json.loads((private / "panel.json").read_text(encoding="utf-8"))
targets = {row["text"]: row["case_id"] for row in panel if row["case_id"] in {
    "H0023", "H0103", "disk-used-es"}}
results = []
for row in events:
    if row.get("text") not in targets or row["stage"] != "input":
        continue
    raw = outputs[row["id"]]["result"]
    assert raw["mode"] == "action" and raw["effect_verification"] in {"primary", "grounding_required"}
    after = apply_operation_domain_grounding_veto(raw, row["text"],
        previous_user_text=_previous_user_request(row["history"], row["text"]),
        available_operations=tuple(candidate["name"] for candidate in row["candidates"]))
    assert after["mode"] == "conversation" and after["effect_operations"] == []
    results.append({"case_id": targets[row["text"]], "boundary_id": row["id"],
                    "text": row["text"], "before": raw, "after": after})
assert len(results) == 3
(private / "domain-attribution-replay.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
public = root / "artifacts/comprobaciones/C03/NATIVE_PRODUCT736/k2/DOMAIN_ATTRIBUTION.json"
public.write_text(json.dumps({
    "method": "Pure shared veto replay; actual decision/text/history and candidate names. No LLM or Core calls.",
    "scope": "No explicit/compound contract supplied, consistent with these model-path single operations. App/game catalogs omitted; the window.resolve and system.status lexical branches do not depend on their contents. Candidate operations are the captured shortlist, not an assertion of full catalog capture.",
    "cases": [{"case_id": row["case_id"], "native_operation": row["before"]["operation"],
               "after_mode": row["after"]["mode"], "after_operations": row["after"]["effect_operations"]}
              for row in results],
    "sources": {str(path): hashlib.sha256((root / path).read_bytes()).hexdigest()
                for path in ["src/baxy_mind/__main__.py", "src/baxy_mind/effect_intent.py"]},
    "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "conclusion": "Domain veto can reproduce removal of all three valid native proposals before Core. The recorded conversation timeout is downstream, not the first demonstrated semantic loss. No evidence that the required process argument itself invalidates '*'.",
    "adopted": False, "survey_coverage_added": 0,
}, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
print(public)
