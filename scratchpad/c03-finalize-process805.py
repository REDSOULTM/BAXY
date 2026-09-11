"""Assemble root's saved50 judgments and latency observations; never grade text."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import math
import re
import statistics

root = Path(__file__).resolve().parents[1]
base = Path("C:/Users/usuario/AppData/Local/BAXY")
private = base / "C03-process-batch805-private"
out = root / "artifacts/comprobaciones/C03/PROCESS_BATCH805"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    assert not path.exists(), path
    path.write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def times(rows):
    values = sorted(row["trace_duration_ms"] / 1000 for row in rows)
    assert values and all(math.isfinite(value) and value >= 0 for value in values)
    return {"count": len(values), "median_seconds": round(statistics.median(values), 3),
            "p95_nearest_rank_seconds": round(values[math.ceil(len(values) * .95) - 1], 3),
            "max_seconds": round(max(values), 3)}


review = read(private / "review.json")
judgments = read(private / "root-adjudication.json")
panel = read(base / "C03-process-panel795-private/panel.json")
prereg = read(out / "PREREG.json")
assert sha(private / "panel.json") == prereg["panel_sha256"]
assert [row["case_id"] for row in review] == [row["case_id"] for row in panel]
assert len(review) == len(judgments) == 50
assert set(judgments) == {row["case_id"] for row in panel}
assert all(type(row["passed"]) is bool and row["reason"].strip() for row in judgments.values())
exit_receipt = read(out / "EXIT.json")
assert exit_receipt["exit_code"] == 0 and all(value is True for key, value in exit_receipt.items()
                                          if key.endswith("_unchanged"))
resources = read(out / "RESOURCES.json")
assert not resources["violations"] and resources["gpu_telemetry_available"] is True
old_text = (base / "C03-process-batch801-private/RESPUESTAS.md").read_text(encoding="utf-8-sig")
old801 = {case: label == "VÁLIDO" for case, label in re.findall(r"^## t\d+ · (\S+) · (.+)$", old_text, re.M)}
old803 = {row["case_id"]: row["passed"] for row in read(
    root / "artifacts/comprobaciones/C03/PROCESS_BATCH803/COMBINED_ROOT_ADJUDICATION.json")["cases"]}
assert len(old801) == len(old803) == 50 and sum(old801.values()) == 35 and sum(old803.values()) == 28
cases = [{"case_id": row["case_id"], "group": row["group"], "turn_id": row["turn_id"],
          "terminal_kind": row["terminal"]["kind"], **judgments[row["case_id"]]} for row in review]
groups = list(dict.fromkeys(row["group"] for row in review))
by_group = {group: dict(Counter("valid" if row["passed"] else "failed"
                               for row in cases if row["group"] == group)) for group in groups}
comparison = {str(batch): {"previous_valid": sum(old.values()),
                         "gains": [row["case_id"] for row in cases if row["passed"] and not old[row["case_id"]]],
                         "losses": [row["case_id"] for row in cases if not row["passed"] and old[row["case_id"]]]}
              for batch, old in ((801, old801), (803, old803))}
previous_rows = read(base / "C03-process-batch803-private/live-review.json") + read(
    base / "C03-process-batch803-resume-private/review.json")
assert len(previous_rows) == 50
latency = {"metric": "Difference between first and last recorded turn-scoped shell event; completed finals only. Not acoustic latency.803 combines9+41 profiles and excludes its interrupted tenth attempt.",
           "805": {"all": times(review), "by_group": {group: times([row for row in review if row["group"] == group]) for group in groups}},
           "803": {"all": times(previous_rows), "by_group": {group: times([row for row in previous_rows if row["group"] == group]) for group in groups}}}
valid = sum(row["passed"] for row in cases)
result = {"method": "Root read every final against its newly observed facts and the sealed criterion; this script assembles only those saved judgments.",
          "candidate": 804, "adopted": False, "continuous_50": True, "valid": valid, "failed": 50 - valid,
          "by_group": by_group, "comparison": comparison, "latency": latency, "resources": resources,
          "cases": cases, "evidence_sha256": {str(path): sha(path) for path in (
              private / "root-adjudication.json", private / "review.json", out / "PREREG.json", out / "EXIT.json")},
          "survey_counts": {"covered": 28, "open": 714, "not_applicable": 0}}
write(out / "ROOT_ADJUDICATION.json", result)
write(out / "VERIFICATION_STATUS.json", {"source_candidate": 804, "source_adopted": False,
      "new_coverage": 0, "survey_counts": result["survey_counts"],
      "cases": [{"case_id": row["case_id"], "verification_status": "open", "candidate_pass": row["passed"],
                 "reason": row["reason"]} for row in cases if row["case_id"].startswith("H")]})
markdown = ["# Respuestas805 — adjudicación raíz", f"{valid}/50 válidas;{50-valid}/50 fallidas. La decisión de adopción se registra aparte."]
for row in review:
    judgment = judgments[row["case_id"]]
    label = "VÁLIDO" if judgment["passed"] else "SIN CRÉDITO"
    markdown.extend([f"## {row['case_id']} · {label}", f"**Entrada:** {row['text']}",
                     f"**Respuesta:** {row['terminal']['final']}", f"**Juicio raíz:** {judgment['reason']}",
                     "```json\n" + json.dumps({"criterion": row["criterion"], "core_calls": row["core_calls"],
                         "decisions": row["decisions"], "compose": row["compose"]}, ensure_ascii=False, indent=2) + "\n```"])
destination = private / "RESPUESTAS_ADJUDICADAS.md"
assert not destination.exists()
destination.write_bytes(("\n\n".join(markdown) + "\n").encode("utf-8"))
print(json.dumps({"valid": valid, "failed": 50-valid, "by_group": by_group,
                  "comparison": comparison, "latency": latency}, ensure_ascii=False))
