"""Record root's independent reading of all73 finals and facts before baseline comparison."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / "artifacts/comprobaciones/C03"
out = base / "astra-status-batch729"
private = Path(os.environ["LOCALAPPDATA"]) / "BAXY/C03-status-batch729-private"
read = lambda path: json.loads(path.read_text(encoding="utf-8-sig"))
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
rows = read(private / "review.json")
assert len(rows) == 73
assert read(out / "EXIT.json") == {"exitCode": 0, "manifest_unchanged": True}
assert read(base / "STATUS_BATCH729_OBSERVER_PREFLIGHT.json")["passed"]
assert all(sha(root / name) == value for name, value in read(base / "astra-catalog-source712/CANDIDATE.json")["sources"].items())
assert (private / "panel.json").read_bytes() == (private.parent / "C03-status-batch689-private/panel.json").read_bytes()

# Manual verdicts, based on this run alone. No old verdict file is read here.
failures = {}
def fail(ids, category, reason):
    for case_id in ids.split():
        assert case_id not in failures
        failures[case_id] = {"category": category, "reason": reason}

fail("H0023 H0103 H0209 H0663 windows-all-en", "global_window_inventory_missing",
     "No enumeration occurred. Existing window.resolve requires a process/title; global inventory is absent. Clarification does not fulfill the explicit list. The English variant also receives Spanish.")
fail("windows-focus-mixed", "focus_composition_identity",
     "window.active verified Notepad and its literal title. Drafts instead say bloque de notas; repeated missing_fact rejection leaves no final. Read selection succeeded; composition did not.")
fail("disk-used-es H0532 H0675", "no_fresh_read",
     "The final gives a current PC quantity/ranking using conversation history without a fresh requested read. Native decide boundary selected knowledge; a plausible historical value is not fresh evidence.")
fail("H0539 H0655 H0508", "memory_total_labelled_available",
     "The draft labels 16.54GB total usable RAM as disponible; fresh availableBytes is only about1.49–1.63GB and installed capacity17.18GB. It does not distinguish the requested capacity from available memory.")
fail("H0359 cpu-order-es H0450 H0499 H0602 clock-date-en audio-order-es", "supported_read_not_selected",
     "No requested operation reached Core. Existing battery/CPU/time/date/audio reading is not fulfilled; interpretation failure or unsupported prose is not successful completion. Native knowledge classification is observed where captured; deepest cause remains unproved.")
fail("H0732", "network_scope",
     "network.status online is derived from connected interfaces; this does not verify the Internet connectivity asked for.")
fail("network-wifi-en", "network_scope",
     "wifi.status proves no WLAN connection. The final extends that to no network connection of any kind, which the observation does not establish.")
fail("network-internet-es", "network_scope",
     "No network operation ran. The final nevertheless asserts no Internet and a failed connection attempt; the observed failure was request interpretation before an attempt.")
fail("H0364 processes-top2-es", "cpu_ranking_metric_and_membership",
     "The provider ranks cumulative totalProcessorSeconds, not current CPU consumption. The final also drops distinct ChatGPT processes and names other members as if they were the requested ranking.")
assert len(failures) == 24 and set(failures) <= {row["case_id"] for row in rows}

pass_reasons = {
    "windows": "Fresh foreground observation and final identify the observed Notepad window.",
    "disk": "Fresh disk observation; requested free/used amount agrees with the measured bytes expressed in decimal GB.",
    "gpu": "Fresh GPU observation supports named adapter and requested dedicated capacity/usage; partial unrelated adapters are not represented as measured.",
    "memory": "Fresh memory observation supports requested installed/free/used amount with matching label and decimal units.",
    "battery": "Fresh battery state supports percentage, charging and AC state as requested.",
    "cpu": "Final reports the freshly observed current CPU usage percentage.",
    "clock": "Fresh UTC plus measured local offset supports the local time/date in the final.",
    "network": "Fresh WLAN observation supports the narrowly worded absence of a Wi-Fi connection.",
    "processes": "Fresh memory-sorted process inventory supports the requested top count, names and working-set amounts; these are process entries, not aggregate application memory.",
    "audio": "Fresh default output endpoint observation supports volume100 and unmuted state; no change was requested or executed.",
}
verdicts = []
for row in rows:
    failure = failures.get(row["case_id"])
    verdicts.append({"case_id": row["case_id"], "group": row["group"], "turn_id": row["turn_id"],
                     "correct": failure is None,
                     **(failure or {"category": "verified_answer", "reason": pass_reasons[row["group"]]})})
assert sum(row["correct"] for row in verdicts) == 49
log_counts = {}
for name in ["http-posts.jsonl", "decision-boundary.jsonl"]:
    events = [json.loads(line) for line in (private / name).read_text(encoding="utf-8").splitlines()]
    stages = Counter(row["stage"] for row in events)
    grouped = {}
    for row in events:
        grouped.setdefault((row["pid"], row["id"]), []).append(row["stage"])
    assert all(stages_ in (["request", "response"], ["request", "failure"], ["input", "output"], ["input", "failure"]) for stages_ in grouped.values())
    log_counts[name] = {"stages": dict(stages), "calls": len(grouped), "pids": sorted({row["pid"] for row in events})}

result = {"utc": datetime.now(timezone.utc).isoformat(), "status": "diagnostic_adjudicated",
          "cases": 73, "correct": 49, "failed": 24, "adopted": False,
          "full_gate_passed": False, "coverage_added": 0,
          "survey": {"covered": 26, "open": 716, "not_applicable": 0},
          "method": "Root read all73 finals, requested criteria, fresh typed facts, failure decisions and rejected drafts before reading the704 baseline verdicts. Single live diagnostic; changing PC state and generation variation prevent causal attribution of a score difference alone.",
          "failure_categories": dict(Counter(row["category"] for row in verdicts if not row["correct"])),
          "resources": read(out / "resources.json"), "resource_scope": "Owned hidden conductor tree; no UI/physical voice, not combined product acceptance.",
          "observer": log_counts, "panel_sha256": sha(private / "panel.json"),
          "candidate_sha256": sha(base / "astra-catalog-source712/CANDIDATE.json"),
          "evidence_sha256": {name: sha(private / name) for name in ["review.json", "capture/events.jsonl", "shell-trace.jsonl", "turn-audit.jsonl", "compose-audit.jsonl", "http-posts.jsonl", "decision-boundary.jsonl"]},
          "verdicts": verdicts}
assert not (out / "RESULT.json").exists()
(out / "RESULT.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
(private / "adjudication.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
report = ["# Revisión independiente729", "", "49 respuestas correctas;24 fallos. Sin adopción ni crédito automático de encuesta.", ""]
for row, verdict in zip(rows, verdicts):
    report.extend([f"## {row['case_id']} — {'correcto' if verdict['correct'] else 'fallo'}", "",
                   "Entrada: " + row["text"], "", "Respuesta: " + str(row["terminal"]["final"]), "",
                   "Criterio: " + row["criterion"], "", "Adjudicación: " + verdict["reason"], "",
                   "Operaciones: " + json.dumps(row["core_calls"]), "",
                   "Payloads y borradores de este turno: `review.json`, " + row["turn_id"], ""])
(private / "REPORT.md").write_text("\n".join(report), encoding="utf-8")
print(json.dumps({key: value for key, value in result.items() if key not in {"verdicts", "evidence_sha256"}}, ensure_ascii=False))
