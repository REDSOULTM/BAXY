"""Record the completed baseline and index the existing private survey ledger."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts/comprobaciones/C03"
ART = BASE / "astra-baseline-state527"
PRIVATE = Path(os.environ["LOCALAPPDATA"]) / "BAXY/C03-baseline-state527-private"
ART.mkdir(exist_ok=False)
PRIVATE.mkdir(exist_ok=False)
NOW = datetime.now(timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


summary_path = BASE / "SURVEY_REQUIREMENTS336.json"
summary = json.loads(summary_path.read_text(encoding="utf-8"))
ledger = Path(summary["private_requirements"])
assert digest(ledger) == summary["requirements_sha256"]
shutil.copy2(ledger, PRIVATE / "requirements336-before.jsonl")
rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
assert len(rows) == 742 and len({row["case_id"] for row in rows}) == 742
assert Counter(row["expected_capability"] for row in rows) == {True: 721, False: 3, None: 18}
assert all(row["verification_status"] == "not_individually_adjudicated_against_current_candidate" for row in rows)
for row in rows:
    row["verification_status_before527"] = row["verification_status"]
    row["verification_status"] = "open"
    row["verification_evidence"] = []
    row["verification_reason"] = "Current candidate behavior and generalizing variants have not yet been individually linked and adjudicated for this case. Open does not mean the behavior failed."
    row["expectation_kind"] = "positive" if row["expected_capability"] is True else "negative_limit" if row["expected_capability"] is False else "unmarked_limit"
    row["verification_updated_at"] = NOW
ledger.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
counts = {"covered": 0, "open": 742, "not_applicable": 0}
summary.update(requirements_sha256=digest(ledger), verification_counts=counts,
               negative_limits=3, unmarked_limits=18, updated_at=NOW,
               status_meaning="Counts are evidence adjudications, not an estimated product completion rate. No inferred coverage or automatic exclusion by authorship.")
write_json(summary_path, summary)
write_json(ART / "SURVEY_COUNTS.json", {**summary, "backup": str(PRIVATE / "requirements336-before.jsonl")})

log_path = BASE / "astra-baseline-full526/full.log"
log = log_path.read_text(encoding="utf-8-sig")
dotnet = []
for line in log.splitlines():
    match = re.search(r"Con error:\s+(\d+), Superado:\s+(\d+), Omitido:\s+(\d+), Total:\s+(\d+), Duración: (.+) - (Baxy\..+?\.dll)", line)
    if match:
        dotnet.append(dict(zip(("failed", "passed", "skipped", "total"), map(int, match.groups()[:4])), duration=match[5], suite=match[6]))
result = {"utc": NOW, "command": "scripts/test_source_quality.ps1 -Mode Full", "exit_code": 1,
          "head": "892c506cdd1a583048ed80af8e63703ec329a236", "status": "FAILED", "log_sha256": digest(log_path),
          "source_changed_during_run": False, "static_and_release": "passed; 0 warnings, 0 errors; 23.46 seconds",
          "dotnet": dotnet, "dotnet_skipped_messages": len(re.findall(r"^  Omitidas ", log, re.M)),
          "skip_reporting_note": "VSTest prints additional opt-in skipped messages beyond its aggregate skipped count. Neither kind is counted as demonstrated hardware/UI coverage.",
          "python": {"failed": 25, "passed": 9984, "skipped": 3, "subtests_passed": 466, "seconds": 676.16},
          "failures": [line[7:] for line in log.splitlines() if line.startswith("FAILED ")],
          "goal": "EN_CURSO", "next": "Diagnose failures without suppressing tests or changing sealed historical evidence to match the current tree."}
write_json(BASE / "astra-baseline-full526/RESULT.json", result)
(BASE / "astra-baseline-full526/RESULT.md").write_text(
    "# Full de línea base 526: rojo\n\n"
    "Commit de control `892c506cdd1a583048ed80af8e63703ec329a236`; comando `scripts/test_source_quality.ps1 -Mode Full`; salida 1. No hubo cambios de fuente durante la ejecución.\n\n"
    "Estática y build Release aprobados, 0 advertencias y 0 errores. .NET: 4427 aprobadas, 0 fallos y 1 omisión en los resúmenes; el log también imprime otras omisiones opt-in que no acreditan ejecución. Python: 9984 aprobadas, 25 fallos, 3 omisiones y 466 subpruebas aprobadas en 676,16 s.\n\n"
    "El resultado completo está en `full.log`; `RESULT.json` conserva las cinco suites y los 25 identificadores fallidos. No se declara C03 terminado ni se presenta esta línea base como verde.\n",
    encoding="utf-8")
for name in ("CHECKPOINT.md", "HANDOFF.md", "ESTADO_PARA_DUENO_2026-09-08.md"):
    shutil.copy2(BASE / name, ART / (name.removesuffix(".md") + "-before.md"))
shutil.copy2(summary_path, ART / "SURVEY_REQUIREMENTS336-current.json")
print(json.dumps({"survey_counts": counts, "dotnet": dotnet, "dotnet_skip_messages": result["dotnet_skipped_messages"], "python": result["python"]}))
