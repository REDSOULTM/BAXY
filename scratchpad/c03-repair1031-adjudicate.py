"""Adjudica REPAIR1031: tanda invalidada por el escritorio, con la causa medida, y sin cobertura.

Las diecisiete vueltas cayeron por lo mismo: `app.open` devolvió `verification_failed` en todas, hasta
en Steam y Discord, que ocho minutos antes habían verificado con recibo. La causa no es el producto ni
la reparación: «Configuración rápida» (ShellHost.exe) tenía el primer plano y no lo cede, así que el
verificador —que exige ventana en primer plano— no podía confirmar nada. Medido, no supuesto:
`scratchpad/c03-window-state.py` leyó handle 65862 de ShellHost.exe como ventana de primer plano, con
Steam, Discord y el Paint recién abierto visibles y sin foco.

Esto convierte una sospecha de APPS1029 en un hecho: la exigencia de primer plano hace que `app.open`
sea infalsificable pero también inverificable en cuanto cualquier ventana del sistema retiene el foco,
y eso no depende de si el destino es UWP.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE = pathlib.Path.home() / "AppData/Local/BAXY"
REGISTRY = BASE / "C03-survey-requirements336-private/requirements.jsonl"
PANEL_DIR = BASE / "C03-repair1031-proposal"
PRIVATE = BASE / "C03-repair1031-private"
RUN = PRIVATE / "run"
PUBLIC = ROOT / "artifacts/comprobaciones/C03/REPAIR1031"
ADJUDICATION = "artifacts/comprobaciones/C03/REPAIR1031/ROOT_ADJUDICATION.json"

INVALID = (
    "Invalidado por el escritorio, no por el producto: en esta tanda `app.open` devolvió "
    "verification_failed en las diecisiete vueltas, incluidas Steam y Discord, que verificaron con "
    "recibo ocho minutos antes en REPAIR1030 sobre el mismo proceso y la misma ventana. La ventana de "
    "primer plano era «Configuración rápida» de ShellHost.exe (handle 65862), que no cede el foco, y "
    "el verificador exige primer plano. No hay juicio de conducta posible sobre este material y no se "
    "acredita nada."
)


def sha_file(path) -> str:
    with pathlib.Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main() -> int:
    utc = datetime.now(timezone.utc).isoformat()
    panel = json.loads((PANEL_DIR / "panel.json").read_text(encoding="utf-8"))
    events = [json.loads(line) for line in
              (RUN / "capture/events.jsonl").read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    terminals = [row for row in events if row.get("type") == "terminal"]
    prereg = json.loads((PUBLIC / "PREREG.json").read_text(encoding="utf-8"))
    candidate = json.loads((PRIVATE / "CANDIDATE_AUTHORIZED.json").read_text(encoding="utf-8"))
    journal = [json.loads(line)["payload"] for line in
               (BASE / "C03-repair1031-profile/journal/missions.jsonl").read_text(encoding="utf-8-sig").splitlines()
               if line.strip()]
    app_open = [row for row in journal
                if row["phase"] == "completed" and row.get("operation") == "app.open"]
    failed = [row for row in app_open
              if (row.get("response") or {}).get("errorCode") == "verification_failed"]

    cases = []
    for index, case in enumerate(panel):
        boundary = case["kind"] == "original_boundary"
        cases.append({
            "index": index, "case_id": case["case_id"], "kind": case["kind"],
            "group": case["group"], "target": case["target"],
            "expected_path": case["expected_path"], "literal": case["text"],
            "criterion": case["criterion"],
            "verdict": "invalid_environment" if not boundary else "invalid_environment_boundary",
            "reason": INVALID if not boundary else (
                "Los límites no acreditan en ningún caso, y en esta tanda tampoco informan: el mismo "
                "escritorio bloqueado afecta a todo el material. boundary-02 volvió a respetar el "
                "límite y boundary-01 y -03 repitieron sus fallos de REPAIR1030."),
            "coverage_added": False,
            "terminal": terminals[index] if index < len(terminals) else None,
        })

    adjudication = {
        "schema": "c03-repair1031-root-adjudication-v1",
        "utc": utc,
        "adjudicator": "root (Opus 5, maquina original REDPC)",
        "source_commit": candidate["head"],
        "repair_under_measurement": json.loads((PANEL_DIR / "SEAL.json").read_text(encoding="utf-8"))["repair_under_measurement"],
        "candidate_manifest_sha256": sha_file(PRIVATE / "CANDIDATE_AUTHORIZED.json"),
        "seal_sha256": prereg["seal_sha256"],
        "runner_sha256": prereg["runner_sha256"],
        "preparation_sha256": prereg["preparation_sha256"],
        "executed": len(cases),
        "passed": 0,
        "failed": 0,
        "invalid": len(cases),
        "coverage_added": 0,
        "credited_case_ids": [],
        "validity": {
            "verdict": "invalid_environment",
            "app_open_invocations": len(app_open),
            "app_open_verification_failed": len(failed),
            "foreground_window_at_diagnosis": {
                "handle": 65862, "process": "ShellHost.exe", "title": "Configuración rápida",
                "instrument": "scratchpad/c03-window-state.py",
            },
            "targets_visible_without_focus": ["steamwebhelper.exe pid29716 handle68266",
                                              "Discord.exe pid27264 handle67102",
                                              "mspaint.exe pid50736 handle20975418"],
            "contrast": "REPAIR1030, ocho minutos antes y con el mismo Steam pid29716 y ventana 68266, "
                        "verificó las diez vueltas de app.open con recibo completo.",
            "restored": "scratchpad/c03-dismiss-flyout.py devolvió el primer plano a explorer.exe "
                        "antes de cualquier medición nueva.",
        },
        "what_this_proves": (
            "La causa A de APPS1029 deja de ser una sospecha limitada a apps UWP: mientras cualquier "
            "ventana del sistema retenga el foco, `app.open` no puede verificar ni un destino Win32 "
            "corriente. Exigir primer plano para afirmar «la app está abierta» convierte una "
            "condición del escritorio en un fallo de producto, y la app sí quedó abierta: el Paint que "
            "lanzó dev-01 estaba visible con pid50736 mientras el recibo decía verification_failed."),
        "next": (
            "Retirar la exigencia de primer plano de la verificación de app.open —conservando el "
            "intento de traerla al frente— y volver a medir el mismo subconjunto exacto con los mismos "
            "controles. Es un cambio .NET, así que exige compilación y recibo de build propio."),
        "resources": json.loads((PUBLIC / "RESOURCES.json").read_text(encoding="utf-8")),
        "exit": json.loads((PUBLIC / "EXIT.json").read_text(encoding="utf-8")),
        "tests_run": False,
        "validation_policy": "owner_directed_no_tests",
        "cases": cases,
    }
    target = PUBLIC / "ROOT_ADJUDICATION.json"
    if target.exists():
        raise SystemExit("adjudication already written")
    target.write_text(json.dumps(adjudication, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8", newline="\n")

    # El registro no se toca: una tanda invalidada no cambia el estado de ninguna fila. Se anota
    # sólo la evidencia de que se ejecutó y por qué no cuenta.
    raw = REGISTRY.read_bytes()
    rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    by_id = {row["case_id"]: row for row in rows}
    touched = []
    for case in cases:
        case_id = case["case_id"]
        if not case_id.startswith("H"):
            continue
        row = by_id[case_id]
        row["verification_evidence"] = list(row.get("verification_evidence") or []) + [{
            "campaign": "REPAIR1031", "source_candidate": candidate["head"],
            "root_adjudication": ADJUDICATION,
            "root_case_pointer": f"/cases/[case_id={case_id}]",
            "panel_seal_sha256": prereg["seal_sha256"], "verdict": "invalid_environment",
            "kind": "invalidated_run_no_status_change", "ui_or_voice_credit": False,
        }]
        touched.append({"case_id": case_id, "status": row["verification_status"],
                        "kind": "invalidated_run_no_status_change"})
    REGISTRY.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
                        encoding="utf-8", newline="\n")
    counts = {status: sum(1 for row in rows if row["verification_status"] == status)
              for status in ("covered", "open", "not_applicable")}
    (PUBLIC / "REGISTRY_UPDATE.json").write_text(json.dumps({
        "schema": "c03-repair1031-registry-update-v1", "utc": utc, "registry": str(REGISTRY),
        "registry_sha256_before": hashlib.sha256(raw).hexdigest(),
        "registry_sha256_after": sha_file(REGISTRY), "rows": len(rows), "counts": counts,
        "coverage_added": 0, "credited_case_ids": [], "status_changes": 0,
        "rows_touched": touched, "adjudication": ADJUDICATION, "tests_run": False,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"invalid": len(cases), "app_open_invocations": len(app_open),
                      "verification_failed": len(failed), "counts": counts}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
