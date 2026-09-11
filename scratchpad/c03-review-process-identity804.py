"""Compare a candidate checker to inherited root801 verdicts; no adjudication."""
from pathlib import Path
import json
import os
import re
import sys

worktree = Path(sys.argv[1])
destination = Path(sys.argv[2])
assert not destination.exists()
sys.path.insert(0, str(worktree / "src"))
from baxy_mind.process_prose_facts import process_fact_feedback

private = Path(os.environ["LOCALAPPDATA"]) / "BAXY/C03-process-batch801-private"
review = json.loads((private / "review.json").read_text(encoding="utf-8-sig"))
verdicts = dict(re.findall(r"^## t\d+ · (\S+) · (.+)$",
                         (private / "RESPUESTAS.md").read_text(encoding="utf-8-sig"), re.M))
assert len(review) == len(verdicts) == 50
results = []
for case in review:
    attempt = next((draft for draft in case["compose"]
                    if isinstance(draft.get("payload"), dict)
                    and draft["payload"].get("operation") == "system.process.list"), None)
    assert attempt is not None
    feedback = process_fact_feedback(case["terminal"]["final"], attempt["payload"], case["text"])
    results.append({"case_id": case["case_id"], "inherited_root_pass": verdicts[case["case_id"]] == "VÁLIDO",
                    "checker_rejects": feedback is not None, "feedback": feedback})
false_rejects = [row["case_id"] for row in results if row["inherited_root_pass"] and row["checker_rejects"]]
summary = {"method": "Mechanical comparison to inherited801 root verdicts, no inference or re-adjudication.",
           "inherited_valid": sum(row["inherited_root_pass"] for row in results),
           "false_rejects": false_rejects,
           "rejects_among_uncredited": sum(not row["inherited_root_pass"] and row["checker_rejects"] for row in results)}
destination.write_text(json.dumps({"summary": summary, "cases": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary))
