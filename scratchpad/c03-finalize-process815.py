"""Assemble root's saved50 judgments and latency observations; never grade text."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import math
import re
import statistics

script = Path(__file__).resolve()
root = script.parents[1]
assert script.parent.name == "scratchpad", "Copy proposal into canonical scratchpad before execution"
assert root == Path("D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO").resolve()
assert (root / "Baxy.slnx").is_file() and (root / "main.py").is_file()
base = Path("C:/Users/usuario/AppData/Local/BAXY")
private = base / "C03-process-batch815-private"
out = root / "artifacts/comprobaciones/C03/PROCESS_BATCH815"


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


destinations = (out / "ROOT_ADJUDICATION.json", out / "VERIFICATION_STATUS.json",
                private / "RESPUESTAS_ADJUDICADAS.md")
assert all(not path.exists() for path in destinations), "An output already exists"
exit_receipt = read(out / "EXIT.json")
assert type(exit_receipt["exit_code"]) is int and exit_receipt["exit_code"] == 0
seal_flags = ("manifest_unchanged", "sources_unchanged", "source814_unchanged",
              "runner_unchanged", "app_dll_unchanged")
assert all(exit_receipt[key] is True for key in seal_flags)
assert all(value is True for key, value in exit_receipt.items() if key.endswith("_unchanged"))
capture = read(out / "REVIEW_CAPTURE.json")
assert capture["completed_terminals"] == capture["registered_total"] == 50
assert capture["partial"] is False and capture["truncated_tails"] == []
assert capture["quality_adjudicated"] is False
review = read(private / "review.json")
judgments = read(private / "root-adjudication.json")
panel = read(base / "C03-process-panel795-private/panel.json")
prereg = read(out / "PREREG.json")
assert sha(private / "panel.json") == prereg["panel_sha256"]
assert [row["case_id"] for row in review] == [row["case_id"] for row in panel]
assert len(review) == len(judgments) == len(panel) == 50
assert len({row["case_id"] for row in panel}) == 50
assert [{"case_id": row["case_id"], "group": row["group"]} for row in review] == prereg["cases"]
assert sum(row["case_id"].startswith("H") for row in panel) == 9
assert set(judgments) == {row["case_id"] for row in panel}
assert all(type(row["passed"]) is bool and row["reason"].strip() for row in judgments.values())
resources = read(out / "RESOURCES.json")
assert not resources["violations"] and resources["gpu_telemetry_available"] is True
old_text = (base / "C03-process-batch801-private/RESPUESTAS.md").read_text(encoding="utf-8-sig")
old801 = {case: label == "VÁLIDO" for case, label in re.findall(r"^## t\d+ · (\S+) · (.+)$", old_text, re.M)}
old813 = {row["case_id"]: row["passed"] for row in read(
    root / "artifacts/comprobaciones/C03/PROCESS_BATCH813/ROOT_ADJUDICATION.json")["cases"]}
assert set(old801) == set(old813) == set(judgments)
assert len(old801) == len(old813) == 50 and sum(old801.values()) == 35 and sum(old813.values()) == 39
cases = [{"case_id": row["case_id"], "group": row["group"], "turn_id": row["turn_id"],
          "terminal_kind": row["terminal"]["kind"], **judgments[row["case_id"]]} for row in review]
groups = list(dict.fromkeys(row["group"] for row in review))
by_group = {group: dict(Counter("valid" if row["passed"] else "failed"
                               for row in cases if row["group"] == group)) for group in groups}
comparison = {str(batch): {"previous_valid": sum(old.values()),
                         "gains": [row["case_id"] for row in cases if row["passed"] and not old[row["case_id"]]],
                         "losses": [row["case_id"] for row in cases if not row["passed"] and old[row["case_id"]]]}
              for batch, old in ((801, old801), (813, old813))}
previous_rows = read(base / "C03-process-batch813-private/review.json")
assert len(previous_rows) == 50
assert [{"case_id": row["case_id"], "group": row["group"]} for row in previous_rows] == prereg["cases"]
latency = {"metric": "Difference between first and last recorded turn-scoped shell event; all completed terminals regardless of terminal kind. Not acoustic latency.815 and813 each use their complete continuous50 review.json directly; no interrupted or resumed profiles are combined.",
           "815": {"all": times(review), "by_group": {group: times([row for row in review if row["group"] == group]) for group in groups}},
           "813": {"all": times(previous_rows), "by_group": {group: times([row for row in previous_rows if row["group"] == group]) for group in groups}}}
valid = sum(row["passed"] for row in cases)
result = {"method": "Root read every final against its newly observed facts and the sealed criterion; this script assembles only those saved judgments.",
          "candidate": 814, "adopted": False, "continuous_50": True, "valid": valid, "failed": 50 - valid,
          "by_group": by_group, "comparison": comparison, "latency": latency, "resources": resources,
          "cases": cases, "evidence_sha256": {str(path): sha(path) for path in (
              private / "root-adjudication.json", private / "review.json", out / "PREREG.json", out / "EXIT.json",
              out / "REVIEW_CAPTURE.json", out / "RESOURCES.json",
              base / "C03-process-batch801-private/RESPUESTAS.md",
              root / "artifacts/comprobaciones/C03/PROCESS_BATCH813/ROOT_ADJUDICATION.json",
              base / "C03-process-batch813-private/review.json")},
          "survey_counts": {"covered": 28, "open": 714, "not_applicable": 0}}
write(out / "ROOT_ADJUDICATION.json", result)
write(out / "VERIFICATION_STATUS.json", {"source_candidate": 814, "source_adopted": False,
      "new_coverage": 0, "survey_counts": result["survey_counts"],
      "cases": [{"case_id": row["case_id"], "verification_status": "open", "candidate_pass": row["passed"],
                 "reason": row["reason"]} for row in cases if row["case_id"].startswith("H")]})
markdown = ["# Respuestas815 — adjudicación raíz", f"{valid}/50 válidas;{50-valid}/50 fallidas. La decisión de adopción se registra aparte."]
for row in review:
    judgment = judgments[row["case_id"]]
    label = "VÁLIDO" if judgment["passed"] else "SIN CRÉDITO"
    markdown.extend([f"## {row['case_id']} · {label}", f"**Entrada:** {row['text']}",
                     f"**Respuesta:** {row['terminal']['final']}", f"**Juicio raíz:** {judgment['reason']}",
                     "```json\n" + json.dumps({"criterion": row["criterion"], "core_calls": row["core_calls"],
                         "decisions": row["decisions"], "compose": row["compose"],
                         "complete_review_row": row, "root_judgment": judgment}, ensure_ascii=False, indent=2) + "\n```"])
destination = private / "RESPUESTAS_ADJUDICADAS.md"
assert not destination.exists()
destination.write_bytes(("\n\n".join(markdown) + "\n").encode("utf-8"))
print(json.dumps({"valid": valid, "failed": 50-valid, "by_group": by_group,
                  "comparison": comparison, "latency": latency}, ensure_ascii=False))
