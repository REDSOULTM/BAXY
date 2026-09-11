"""Seal the diagnosed Full5 blockers without treating probes as product passes."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import os
import shutil

root = Path(__file__).resolve().parents[1]
base = root / "artifacts/comprobaciones/C03"
out = base / "astra-full5-timeout-repair724"
out.mkdir(exist_ok=True)


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


previous = json.loads((base / "astra-catalog-source712/CANDIDATE.json").read_text(encoding="utf-8"))
assert all(sha(root / path) == value for path, value in previous["sources"].items())
sources = dict(previous["sources"])
for path in ("tests/test_product_packaging.py", "tests/test_sidecar_lifecycle.py"):
    sources[path] = sha(root / path)
write(out / "CANDIDATE.json", {
    "utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    "previous_candidate": "astra-catalog-source712/CANDIDATE.json",
    "previous_candidate_sha256": sha(base / "astra-catalog-source712/CANDIDATE.json"),
    "sources": sources,
    "additional_changes": "Two test fixtures only; no further product, model, reader, DSP or Git configuration changes",
    "packaging": "Entire HEAD of a controlled repository, byte/inventory/dirty-source/registration assertions; original PowerShell timeout45s",
    "sidecar": "Hello readiness bounded10s, then explicit crash request and unchanged3s failure-exit deadline; second read must remain blocked",
    "full_required": True, "adopted": False, "coverage_added": 0,
})
for name, output in (
    ("c03-packaging-fixture722-owner.log", "PACKAGING_FIRST_FAILED.log"),
    ("c03-packaging-fixture722-owner2.log", "PACKAGING_OWNER_PASS.log"),
    ("c03-sidecar-phase724-owner.log", "SIDECAR_TWO_OWNERS_PASS.log"),
    ("c03-cold-dsp-probe719.log", "PROBE719_WRAPPER_FAILED.log"),
):
    shutil.copyfile(Path(os.environ["TEMP"]) / name, out / output)
workers = []
for tag in ("pair1-original", "pair1-workers2", "pair2-workers2", "pair2-original"):
    result = json.loads((base / f"astra-packaging-workers720/{tag}/RESULT.json").read_text(encoding="utf-8"))
    workers.append({"profile": tag, **result})
write(base / "astra-packaging-workers720/RESULT.json", {
    "runs": workers, "wrapper_exit_code": 0,
    "decision": "reject: both worker2 runs miss the45s deadline; one pair improves and one worsens",
    "elapsed_note": "Elapsed includes bounded observer join after child completion; deadline_passed records the actual wait45 outcome",
    "product_or_git_config_changed": False, "coverage_added": 0,
})
write(out / "OWNER_STATUS.json", {
    "packaging_first_attempt": {"session": 15067, "exit_code": 1, "passed": 0, "failed": 1,
                                "seconds": 41.70, "reason": "Get-FileHash unavailable; changed assertion to existing Get-BaxySha256"},
    "packaging_second_attempt": {"session": 18099, "exit_code": 0, "passed": 1, "failed": 0, "seconds": 38.67},
    "sidecar_two_tests": {"session": 15643, "exit_code": 0, "passed": 2, "failed": 0, "seconds": 10.34},
    "three_owner_suites": {"session": 62763, "status": "running", "log": "TEMP/c03-full5-timeout-repair724-owners.log"},
    "adopted": False, "coverage_added": 0,
})
path = base / "RELEVO_ACTIVO.json"
state = json.loads(path.read_text(encoding="utf-8"))
state["confirmedAtUtc"] = dt.datetime.now(dt.timezone.utc).isoformat()
state["checkpoint"] = (
    "Full5 sigue rojo histórico. 718 localiza39s en worktree add;720 descarta workers2. "
    "719/721/723 no permiten retirar prewarm ni cambiar reader/BLAS. Candidato724 corrige "
    "fixtures de packaging y temporización por fase del test de crash. Pruebas concretas1+2 pass; "
    "tres suites dueñas corren en62763. Producto705+712 idéntico, sin adoptar. Encuesta26/716/0."
)
state["continuation"] = (
    "Recoger62763 y su log/exit. Si verde, revisar fuente y sellos724 y ejecutar Full6 antes de adoptar "
    "705+712+724. Producto706 sigue sin correr y conserva guard antiguo Full5; deberá actualizarse "
    "al candidato/Full realmente verdes. No repetir719/721/723 ni cambiar resampler/protocolo."
)
state["workStatus"] = "timeout_test_fixtures724_owner_suites_running"
state["activeOwnerDiagnostics"] = {"session": 62763, "status": "running",
    "candidate": "astra-full5-timeout-repair724/CANDIDATE.json",
    "prior_probe_sessions_terminal": [21773, 25850, 92379, 7066, 19435, 15067, 18099, 15643],
    "new_coverage": 0}
path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("Sealed candidate724 and terminal diagnostics; owner suites62763 still pending.")
