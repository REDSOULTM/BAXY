"""Diagnose all73 product turns while explicitly retaining the red adoption gate."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import psutil

root = Path(__file__).resolve().parents[1]
base = root / "artifacts/comprobaciones/C03"
candidate_path = base / "astra-catalog-source712/CANDIDATE.json"
candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
assert all(sha(root / name) == value for name, value in candidate["sources"].items())
for name, value in {
    "tests/test_product_packaging.py": "5ba170a05a877e31a9d023468856b3403fdda066ebd75b432a7cf7166730501f",
    "tests/test_sidecar_lifecycle.py": "4ac312b869624d261e047521bc918d9ff025194d8c9186dd9b5fae5a8959656d",
}.items():
    assert sha(root / name) == value, "Original acceptance test must stay restored"
full_path = base / "astra-catalog-source712/FULL5_RESULT.json"
full = json.loads(full_path.read_text(encoding="utf-8"))
assert full["exit_code"] == 1 and full["dotnet"]["failed"] == 0
assert set(full["python"]["failures"]) == {
    "tests/test_product_packaging.py::ProductPackagingTests::test_detached_head_snapshot_is_exact_and_cleanup_removes_it",
    "tests/test_sidecar_lifecycle.py::test_dispatch_crash_exits_while_redirected_stdin_remains_open",
}
for process in psutil.process_iter(["name", "cmdline"]):
    name = (process.info["name"] or "").lower()
    assert name not in {"llama-server.exe", "testhost.exe", "baxy-core.exe"}, "Another workload is active"
    assert "pytest" not in (process.info["cmdline"] or []), "Do not infer alongside tests"
assert psutil.virtual_memory().available >= 2700 * 2**20
hook = root / "scratchpad/c03-status706-hook/sitecustomize.py"
assert sha(hook) == "b3e13ecbb96d6e60950ae546202c7b46529bcc02aae61def3a606fe3bd9cf10b"
target_hook = root / "scratchpad/c03-status728-hook"
target_hook.mkdir(exist_ok=False)
(target_hook / "sitecustomize.py").write_bytes(hook.read_bytes())
assert sha(target_hook / "sitecustomize.py") == sha(hook)
sequence = {
    "utc": datetime.now(timezone.utc).isoformat(),
    "status": "diagnostic_before_adoption", "candidate": str(candidate_path.relative_to(root)),
    "candidate_sha256": sha(candidate_path), "full5_sha256": sha(full_path),
    "full_gate_passed": False, "adopted": False, "goal_complete": False,
    "decision": "Move product diagnosis before the next Full to advance C03 without mistaking two infrastructure timeouts for model quality. Full remains mandatory before source adoption and final delivery.",
    "differences_from_prepared706": "Only run tag and scheduling precondition; same73 panel, criteria, source712, model/backend/presets, resource limits and observer bytes",
    "scope": "Read-only hidden product diagnosis; no UI/voice/survey completion credit",
}
(base / "STATUS_BATCH728_SEQUENCE.json").write_text(json.dumps(sequence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
source = (root / "scratchpad/c03-status-batch694.py").read_text(encoding="utf-8").replace("694", "728")
gate = "gate=(Path(os.environ['TEMP'])/'c03-shared-status693-full.log').read_text(encoding='utf-8-sig')\nassert 'source_quality_gate_passed: mode=Full' in gate, 'Full693 must pass before product evaluation'\n"
assert source.count(gate) == 1
source = source.replace(gate, "# Diagnostic sequencing explicitly declared in STATUS_BATCH728_SEQUENCE.json; adoption remains blocked.\n")
source = source.replace(
    "Shared source693: decimal measurement projection, independent installed RAM observation and wifi.status read-only policy.",
    "Unadopted candidate705+712: verified observed-name spans are opaque only to vocabulary/code/capitalization checks; original facts/prose unchanged. Catalog uses one Shell enumeration. Full5 remains red for two infrastructure timeouts.",
)
source = source.replace("No clearing pending state between turns.",
                        "No conductor clearing of pending state; existing source703 owns confirmation continuity.")
source = source.replace("Shared candidate source693 product after Full693",
                        "Diagnostic of unadopted source705+712 before a new Full; Full5 remains red")
source = source.replace("Exact regression689 after shared quantities, installed RAM and wifi read policy changes;",
                        "Exact regression689/694/702/704 of observed-name and startup catalog changes before adoption;")
source = source.replace("'src/baxy_mind/measurement_prose_projection.py',",
    "'src/Baxy.App/ObservedResponseLiterals.cs', 'src/Baxy.App/UserMessagePolicy.cs', 'src/Baxy.Providers.Windows/Applications/WindowsInstalledApplicationOpenProvider.cs', 'src/baxy_mind/observed_response_literals.py', 'src/baxy_mind/measurement_prose_projection.py',")
marker = "(base/'STATUS_BATCH728_PLAN.json').write_text"
assert source.count(marker) == 1
source = source.replace(marker,
    "plan['acceptance_gate'] = {'full_passed': False, 'adopted': False, 'sequence_record': 'STATUS_BATCH728_SEQUENCE.json'}\n" + marker)
exec(compile(source, __file__, "exec"))
