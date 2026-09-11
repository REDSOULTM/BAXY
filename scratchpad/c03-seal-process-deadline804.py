"""Seal the existing C# dense-inventory selector repair; do not adopt it."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

root = Path(__file__).resolve().parents[1]
out = root / "artifacts/comprobaciones/C03/PROCESS_DEADLINE804"
private = Path("C:/Users/usuario/AppData/Local/BAXY/C03-process-deadline804-private")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path, data):
    assert not path.exists(), path
    path.write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


assert not (out / "CANDIDATE.json").exists()
assert read(root / "artifacts/comprobaciones/C03/PROCESS_BATCH803_RESUME/EXIT.json")["exit_code"] == 0
assert read(root / "artifacts/comprobaciones/C03/PROCESS_BATCH803/COMBINED_ROOT_ADJUDICATION.json")["valid"] == 28
old_paths = [root / "artifacts/comprobaciones/C03/PROCESS_BUDGET802/SOURCE_PINS.json",
             root / "artifacts/comprobaciones/C03/DENSE_INVENTORY764/SOURCE_PINS.json"]
old = {k: v for path in old_paths for k, v in read(path).items()}
changed = {"src/Baxy.App/MindSidecarClient.cs", "tests/Baxy.Integration.Tests/PlannerAppBoundaryTests.cs"}
assert all(sha(root / name) == digest for name, digest in old.items() if name not in changed)
assert not (root / "src/baxy_mind/process_prose_facts.py").exists()
pins = {name: sha(root / name) for name in sorted(set(old) | changed)}
for name in pins:
    destination = private / "source" / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(root / name, destination)
write(out / "SOURCE_PINS.json", pins)
for name, code, counts in (("baseline", 1, {"passed": 14, "failed": 3, "skipped": 0}),
                           ("owners-dotnet", 0, {"passed": 153, "failed": 0, "skipped": 0})):
    log = private / (name + ".log")
    shutil.copyfile(log, out / log.name)
    write(out / (name.upper().replace("-", "_") + "_EXIT.json"),
          {"exit_code": code, **counts, "log_sha256": sha(log)})
write(out / "CANDIDATE.json", {
    "utc": datetime.now(timezone.utc).isoformat(), "source": 804, "adopted": False,
    "base_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
    "changes": sorted(changed), "hypothesis": "Process inventories already receive512 tokens in Python802 but C# allows only4s. Reuse the existing dense inventory selector and its9s protocol budget for verified process rows.",
    "constraints": "No new timeout constants, prompt, sampler, model, backend or factual checker. Python identity proposal remains outside canonical source.",
    "evidence": "PROCESS_BATCH803/COMBINED_REPORT.md:28/50 valid,2gains/9losses vs801; dense composition repeatedly expires at4s.17 baseline controls:3failed dense cases/14pass. Repaired owning suite153pass/0skip.",
    "prior_receipts": {path.relative_to(root).as_posix(): sha(path) for path in old_paths},
    "private_snapshot": str(private / "source"),
    "required_before_adoption": "Owners, Fast, Full for cumulative Python802+C#804 source, then root adjudication of the same frozen50 panel in805 with new fresh observations.",
    "survey_counts": {"covered": 28, "open": 714, "not_applicable": 0}})
print(json.dumps({"pins": len(pins), "changes": sorted(changed), "adopted": False}))
