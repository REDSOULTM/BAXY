"""Preserve and validate inherited process output-budget candidate802 once."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/comprobaciones/C03/PROCESS_BUDGET802"
PRIVATE = Path(os.environ["LOCALAPPDATA"]) / "BAXY/C03-process-budget802-private"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(path, value):
    Path(path).write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


assert not (OUT / "CANDIDATE.json").exists()
assert not PRIVATE.exists()
PRIVATE.mkdir()
old_pins_path = ROOT / "artifacts/comprobaciones/C03/PROCESS_SCOPE800/SOURCE_PINS.json"
old_pins_sha = sha(old_pins_path)
old_pins = read(old_pins_path)
llm_hash = sha(ROOT / "src/baxy_mind/llm.py")
test_path = ROOT / "tests/test_price_v8_veto_damage_by_cause.py"
content = test_path.read_text(encoding="utf-8")
assert old_pins["src/baxy_mind/llm.py"] in content
test_path.write_bytes(content.replace(old_pins["src/baxy_mind/llm.py"], llm_hash).encode("utf-8"))

# Same program-tree algorithm as the current STT evaluators. Their historical
# receipts and the survey remain unchanged; this declares the changed program.
roots = ["experiments/voice_latency", "scripts", "src/baxy_mind"]
files = {path.relative_to(ROOT).as_posix(): path for name in roots
         for path in (ROOT / name).rglob("*.py") if path.is_file() and not path.is_symlink()}
digest = hashlib.sha256()
for name in sorted(files):
    digest.update((name + "\n" + sha(files[name]) + "\n").encode("utf-8"))
program = {"schema": "baxy.wake-validation-program-tree.v1", "roots": roots,
           "pythonFiles": len(files), "sha256": digest.hexdigest()}
for name in ("evaluate_reserved_stt.py", "audit_fresh_postweight_stt_sources.py"):
    path = ROOT / "experiments/stt_quality" / name
    content = path.read_text(encoding="utf-8")
    content, count = re.subn(r'(EXPECTED_PROGRAM_TREE_SHA256 = \(\s*")[0-9a-f]{64}("\s*\))',
                            lambda m: m[1] + program["sha256"] + m[2], content)
    assert count == 1
    path.write_bytes(content.encode("utf-8"))
write(OUT / "PROGRAM.json", program)
paths = [*old_pins, "tests/test_c03_process_output_budget.py"]
pins = {name: sha(ROOT / name) for name in paths}
for name in paths:
    target = PRIVATE / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / name, target)
write(OUT / "SOURCE_PINS.json", pins)
runner = (ROOT / "scratchpad/c03-process-batch801.py").read_text(encoding="utf-8")
runner = runner.replace("801", "803").replace("800", "802")
runner = runner.replace("PROCESS_SCOPE802", "PROCESS_BUDGET802")
runner = runner.replace("['py', 'main.py'", "[sys.executable, 'main.py'")
# Preserve the inherited resource ceiling; numeric tranche renaming must not
# turn 3800 MiB into 3802 MiB.
runner = runner.replace("3802", "3800")
(ROOT / "scratchpad/c03-process-batch803.py").write_bytes(runner.encode("utf-8"))
write(OUT / "CANDIDATE.json", {
    "utc": datetime.now(timezone.utc).isoformat(), "source": 802, "adopted": False,
    "base_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    "hypothesis": "Reuse existing 512-token dense allowance for projected process rows; keep 256 for count-only answers. Five length cuts in801, inherited implementation passes30 focused controls.",
    "runtime_changes": ["src/baxy_mind/llm.py"],
    "declarations_only": ["tests/test_price_v8_veto_damage_by_cause.py",
                          "experiments/stt_quality/evaluate_reserved_stt.py",
                          "experiments/stt_quality/audit_fresh_postweight_stt_sources.py"],
    "baseline": "Inherited baseline.log:6 failed/13 passed; implemented WIP already preserved in9ea1ce56. Focused current test30 passed/0 skips.",
    "prior_evidence": ["PROCESS_BATCH801/REPORT.md", "INVENTORY_BUDGET786/REPORT.md", "INVENTORY_BUDGET787/REPORT.md"],
    "source800_pins_sha256": old_pins_sha, "private_snapshot": str(PRIVATE),
    "acceptance": "Same sealed50 panel795; root reviews against fresh facts, preserves prior valid behavior and seeks complete uncropped lists. No automatic survey credit.",
    "environment_recovery": "Bare py selects incomplete Python313 without pytest. Use existing registered BAXY Python for validation and same main.py product entry. No installation or runtime registration change.",
    "full_scope": "Python-only budget addition to source800. Owners and Fast now; Full798 remains prior baseline and global final Full remains required."
})
plan = read(ROOT / "artifacts/comprobaciones/C03/PROCESS_SCOPE800/VALIDATION_PLAN.json")
command = plan["python_command"]
command.insert(-1, "tests/test_c03_process_output_budget.py")
plan["fast_command"] = [shutil.which("pwsh"), "-NoProfile", "-File", "scripts/test_source_quality.ps1",
                        "-QualityPython", sys.executable]
assert plan["fast_command"][0]
write(OUT / "VALIDATION_PLAN.json", plan)
for label, command in (("owners", command), ("fast", plan["fast_command"])):
    log_path = Path(os.environ["TEMP"]) / f"c03-process-budget802-{label}.log"
    with log_path.open("wb") as log:
        result = subprocess.run(command, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log,
                                stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    shutil.copyfile(log_path, OUT / f"{label}.log")
    write(OUT / f"{label.upper()}_EXIT.json", {"exit_code": result.returncode, "log_sha256": sha(log_path)})
    print(json.dumps({"stage": label, "exit_code": result.returncode, "log": str(log_path)}), flush=True)
    if result.returncode:
        write(OUT / "VALIDATION_EXIT.json", {"exit_code": result.returncode, "stage": label})
        raise SystemExit(result.returncode)
assert sha(old_pins_path) == old_pins_sha
assert all(sha(ROOT / name) == value for name, value in pins.items())
write(OUT / "VALIDATION_EXIT.json", {"exit_code": 0, "pins_unchanged": True, "source800_receipt_unchanged": True})
