"""Freeze tested inputs and run the unchanged complete source quality gate."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/comprobaciones/C03/FULL6_742"
PRIVATE = Path(os.environ["LOCALAPPDATA"]) / "BAXY/C03-full6-742-private"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


def main():
    OUT.mkdir(exist_ok=False)
    PRIVATE.mkdir(exist_ok=False)
    paths = sorted(set(subprocess.check_output([
        "git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--",
        "src", "scripts", "tests", "experiments/stt_quality/audit_fresh_postweight_stt_sources.py",
        "experiments/stt_quality/evaluate_reserved_stt.py", "Baxy.slnx", "Directory.Build.props",
        "Directory.Build.targets", "global.json", "pyproject.toml", ".gitattributes",
    ], cwd=ROOT).decode("utf-8").strip("\0").split("\0")))
    pins = {path: sha(ROOT/path) for path in paths if (ROOT/path).is_file()}
    write(OUT/"SOURCES.json", pins)
    prereg = {
        "utc": datetime.now(timezone.utc).isoformat(),
        "parent_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "command": "powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test_source_quality.ps1 -Mode Full",
        "source_count": len(pins), "source_manifest_sha256": sha(OUT/"SOURCES.json"),
        "reason": "740 repairs original sidecar3s;741 original packaging45s passed without source change. Shared candidate705+712+730+738+740 requires Full before adoption.",
        "unchanged_acceptance": "No deadline, test, gate threshold, skip or environment opt-in changed for this run.",
        "survey": {"covered": 26, "open": 716, "not_applicable": 0},
        "log": "%LOCALAPPDATA%/BAXY/C03-full6-742-private/full.log",
        "goal_complete": False,
    }
    write(OUT/"PREREG.json", prereg)
    started = time.monotonic()
    with (PRIVATE/"full.log").open("wb") as log:
        process = subprocess.Popen(["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive",
            "-ExecutionPolicy", "Bypass", "-File", str(ROOT/"scripts/test_source_quality.ps1"),
            "-Mode", "Full"], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        write(OUT/"PROCESS.json", {"pid": process.pid, "started_utc": datetime.now(timezone.utc).isoformat()})
        print(json.dumps({"started": True, "pid": process.pid, "source_count": len(pins)}), flush=True)
        code = process.wait()
    changed = [path for path, h in pins.items() if not (ROOT/path).is_file() or sha(ROOT/path) != h]
    result = {"utc": datetime.now(timezone.utc).isoformat(), "exit_code": code,
        "elapsed_seconds": time.monotonic()-started, "sources_unchanged": not changed,
        "changed_sources": changed, "log_sha256": sha(PRIVATE/"full.log"),
        "adopted": False, "goal_complete": False, "coverage_added": 0}
    write(OUT/"RESULT.json", result)
    print(json.dumps(result), flush=True)
    if changed:
        raise RuntimeError("Full candidate changed during validation")
    raise SystemExit(code)


if __name__ == "__main__":
    main()
