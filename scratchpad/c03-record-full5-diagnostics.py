"""Persist terminal Full5 owner results and the captured pre-hello phase."""
from pathlib import Path
import datetime as dt
import json
import os
import shutil

root = Path(__file__).resolve().parents[1]
base = root / "artifacts/comprobaciones/C03"
target = base / "astra-catalog-source712"
for name, output in (("c03-full5-timeout-owners.log", "FULL5_OWNER_REPRO.log"),
                     ("c03-full5-timeout-owners-exit.json", "FULL5_OWNER_REPRO_EXIT.json")):
    shutil.copyfile(Path(os.environ["TEMP"]) / name, target / output)
path = base / "RELEVO_ACTIVO.json"
state = json.loads(path.read_text(encoding="utf-8"))
state["confirmedAtUtc"] = dt.datetime.now(dt.timezone.utc).isoformat()
state["checkpoint"] = (
    "Full5/65777 terminó exit1: .NET4532 pass/0 fail/1 skip agregado; "
    "Python11135 pass/2 fail/3 skip. Owners7487 terminó exit1, mismos dos timeouts. "
    "717 capturó el intérprete dentro de prepare_resampler/scipy.signal antes de hello. "
    "705+712 congelados sin adoptar. Encuesta26/716/0."
)
state["continuation"] = (
    "Resolver los dos timeouts antes de otra compuerta. Sonda718 attempt2 en21773 mide "
    "fases del snapshot con plazo original45s. Evaluar primera carga DSP con lector raw "
    "sin cambiar resample_poly, calidad ni plazos. Producto706 no ejecutado; su guard "
    "requiere todavía Full5 verde y deberá apuntar deliberadamente al nuevo candidato validado."
)
state["workStatus"] = "full5_timeouts_prehello_scipy_captured_packaging_phases_running"
state["activeOwnerDiagnostics"] = {
    "owner_repro_session": 7487, "status": "terminal_failed", "exit_code": 1,
    "passed": 0, "failed": 2, "seconds": 57.96,
    "sidecar717": {"deadline_passed": False, "phase": "prepare_resampler -> scipy.signal -> interpolate/optimize/_trlib",
                   "hello_seen": False, "forced_dispatch_crash_seen": False,
                   "owned_processes_disposed": True,
                   "evidence": "astra-full5-sidecar717/RESULT.json"},
    "packaging718_attempt2_session": 21773,
    "coverage_added": 0,
}
path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("Terminal owners and pre-hello evidence persisted; no source adoption or coverage.")
