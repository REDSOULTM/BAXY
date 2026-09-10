"""Local replay: separate word order from subject binding, without model calls."""
from pathlib import Path
import hashlib
import json
import os
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))
from baxy_mind.window_prose_facts import window_focus_feedback

private = Path(os.environ["LOCALAPPDATA"]) / "BAXY/C03-native-product736-k2-private"
drafts = [json.loads(line) for line in (private / "compose-audit.jsonl").open(encoding="utf-8-sig")]
draft = next(row for row in drafts if row.get("trace") == "t3" and row.get("stage") == "first")
window = draft["payload"]["seen"]["windows"][0]
title, process = window["title"], window["processName"]
assert draft["draft"].startswith("Activa está ")
variants = {
    "observed_original": draft["draft"],
    "copula_order_only": draft["draft"].replace("Activa está", "Está activa", 1),
    "observed_process_immediately_after_predicate": f'Está activa {process}, con título "{title}".',
    "observed_title_in_nominal_identity": f'La ventana activa es "{title}".',
}
results = [{"variant": name, "draft": text,
            "feedback": window_focus_feedback(text, draft["payload"], "qué ventana está activa")}
           for name, text in variants.items()]
assert results[0]["feedback"] and results[1]["feedback"]
assert results[2]["feedback"] is None and results[3]["feedback"] is None
(private / "focus-attribution-replay.json").write_text(
    json.dumps({"payload": draft["payload"], "results": results}, ensure_ascii=False, indent=2)+"\n",
    encoding="utf-8")
public = root / "artifacts/comprobaciones/C03/NATIVE_PRODUCT736/k2/FOCUS_ATTRIBUTION.json"
public.write_text(json.dumps({
    "case_id": "H0104", "turn_id": "t3", "method": "Exact observed payload and validator; no LLM or product mutation",
    "validator_sha256": hashlib.sha256((root / "src/baxy_mind/window_prose_facts.py").read_bytes()).hexdigest(),
    "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "variants": [{"name": row["variant"], "accepted": row["feedback"] is None} for row in results],
    "conclusion": "Correct observed draft rejected. Copula reordering alone still rejected: subject binding also restricts accepted phrasing. This replay does not adopt a repair or add survey coverage.",
    "adopted": False, "survey_coverage_added": 0,
}, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
print(public)
