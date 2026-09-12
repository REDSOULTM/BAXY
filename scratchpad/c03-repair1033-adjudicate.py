"""Adjudica REPAIR1033: siete filas de Steam cobran; H0575 vuelve a fallar por un tercer matiz."""
from __future__ import annotations

import hashlib
import json
import pathlib
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE = pathlib.Path.home() / "AppData/Local/BAXY"
REGISTRY = BASE / "C03-survey-requirements336-private/requirements.jsonl"
PANEL_DIR = BASE / "C03-repair1033-proposal"
PRIVATE = BASE / "C03-repair1033-private"
RUN = PRIVATE / "run"
PUBLIC = ROOT / "artifacts/comprobaciones/C03/REPAIR1033"
ADJUDICATION = "artifacts/comprobaciones/C03/REPAIR1033/ROOT_ADJUDICATION.json"

TRUTHFUL = (
    "Recibo verificado con alreadyRunning=true, proceso 29716 y ventana 68266, leídos frescos del "
    "diario en la adjudicación. Publicado «La app Steam ya estaba abierta.»: nombra el destino, dice el "
    "estado real y no se atribuye un lanzamiento que no hizo. La coincidencia con las otras vueltas de "
    "Steam no la descalifica por el criterio sellado de esta tanda, declarado antes de ejecutar: el "
    "invariante 5 prohíbe respuestas fijadas por código, el modelo formula ésta, y con temperatura 0 un "
    "payload idéntico y siete literales que difieren en tildes y signos no pueden dar siete frases "
    "distintas. No reproduce la instrucción interna ni usa vocabulario interno."
)

RECEIPTS = {
    "H0015": "dbede500-a342-4b19-a5a9-1597c530e958",
    "H0055": "04731422-e0fa-4f16-8dfc-1d8453574400",
    "H0134": "f8c7b99a-45fd-4584-a352-54ebf9514fc7",
    "H0136": "10cc8a39-cee1-471f-b658-349fa7cba57d",
    "H0391": "ff8f039c-7cfc-4cb1-b202-be21d63b251c",
    "H0418": "2a862178-39f2-48c7-a2f3-de2df024cd1c",
    "H0653": "62d88cf4-c14a-423c-ad51-dd1d8c8c4ccb",
}

CREDITED = ["H0015", "H0055", "H0134", "H0136", "H0391", "H0418", "H0653"]
CREDIT_PAIRS = ["repair1033-dev-02", "repair1033-dev-03", "repair1033-dev-04"]

VERDICTS = [
    ("H0015", "pass", f"inv {RECEIPTS['H0015']}. " + TRUTHFUL),
    ("H0055", "pass", f"inv {RECEIPTS['H0055']}. " + TRUTHFUL),
    ("H0134", "pass", f"inv {RECEIPTS['H0134']}. " + TRUTHFUL),
    ("H0136", "pass", f"inv {RECEIPTS['H0136']}. " + TRUTHFUL),
    ("H0391", "pass", f"inv {RECEIPTS['H0391']}. " + TRUTHFUL),
    ("H0418", "pass", f"inv {RECEIPTS['H0418']}. " + TRUTHFUL),
    ("H0653", "pass", f"inv {RECEIPTS['H0653']}. " + TRUTHFUL),
    ("H0575", "fail",
     "Tercer intento y tercer matiz. El recibo dice alreadyRunning=false: la calculadora la abrió este "
     "turno, proceso 41528 y ventana 595826 (inv 845b341a-2632-4794-8eee-b2ec813d2d15). Lo publicado es "
     "«Ya está abierta la calculadora.», que presenta el estado como si no hubiera hecho falta actuar y "
     "oculta el efecto que acaba de producir. El criterio sellado de esta tanda prohíbe presentar como "
     "anterior un estado que el turno acaba de crear, así que falla. El chequeo nuevo lo dejó pasar a "
     "propósito: excluye el presente «ya está abierta» porque después de abrirla es cierto sobre el "
     "presente. Lo que falta es más fino: con alreadyRunning=false, «ya» delante del estado sigue "
     "enmarcándolo como preexistente aunque el verbo esté en presente."),
    ("H0085", "pass",
     "Control de no regresión, camino ya-en-ejecución: recibo verificado alreadyRunning=true, proceso "
     "27264 y ventana 67102 (inv 7805f1b0-853d-4e25-94ce-453eae0e7c8e), misma frase veraz de las tres "
     "tandas anteriores. No acredita: ya está cubierta."),
    ("H0315", "pass",
     "Control: «Sí, pude abrir Steam. Ya estaba en ejecución antes.» "
     "(inv da3cb3e4-6945-44e9-b5ab-12eef13c16e8). No acredita: ya cubierta."),
    ("H0317", "pass",
     "Control en inglés: «I opened Steam. It was already running before.» "
     "(inv 92c7a16f-9fdc-40d5-aa2d-ce14d29988fc). No acredita: ya cubierta."),
    ("H0251", "pass",
     "Control del camino de lanzamiento: recibo verificado alreadyRunning=false, calculadora proceso "
     "48304 y ventana 7083774 (inv 61c91480-7fe7-4795-af22-28b91dc7af01), publicado «Abrí la "
     "calculadora.». La dirección nueva del chequeo no rompió el lanzamiento veraz. No acredita."),
    ("H0706", "pass",
     "Control del camino de lanzamiento: Configuración verificada con alreadyRunning=false, proceso "
     "48596 y ventana 1054790 (inv 35f604f4-6f37-4e32-b29e-08863b692a95), publicado «Abrí la "
     "configuración de Windows.». No acredita."),
    ("repair1033-dev-01", "pass",
     "Variante de lanzamiento real: Paint verificado alreadyRunning=false, proceso 50988 y ventana "
     "3020572 (inv 1508ca66-4db6-4aea-b98d-ed5d6bcd0ce3), publicado «Ya abrí Paint.», que se atribuye "
     "un lanzamiento que sí hizo."),
    ("repair1033-dev-02", "pass",
     "Variante de destino ya en ejecución en inglés: «Paint was already open.» sobre el Paint que "
     "dev-01 acababa de abrir, recibo alreadyRunning=true, proceso 50988 "
     "(inv f64f27df-eafe-488d-a3b0-801b7efc3451)."),
    ("repair1033-dev-03", "pass",
     "Variante en español: «Ya está abierto Steam.» sobre recibo verificado alreadyRunning=true "
     "(inv 8f6c69b1-5228-4ef9-a02c-dbfdf2caee79)."),
    ("repair1033-dev-04", "pass",
     "Variante en inglés: «Yeah, Steam is already open.» sobre recibo verificado alreadyRunning=true "
     "(inv f15854c7-a297-4090-a1bf-88625b073646)."),
    ("repair1033-boundary-01", "fail",
     "Cuarta tanda con el mismo fallo: límite respetado en el efecto —ninguna operación en el diario— "
     "y publicado «La causa del fallo es que la interpretación de la solicitud no fue válida.», que no "
     "contesta si la calculadora está instalada y usa jerga de contrato."),
    ("repair1033-boundary-02", "fail",
     "Empeoró respecto a REPAIR1032, donde este mismo límite publicó una frase limpia. Ahora añade «El "
     "intento no fue válido y no se pudo verificar.»: afirma un intento que no existió y filtra "
     "vocabulario de contrato sobre una cita ajena. Sin efecto, pero el límite ya no se contesta bien."),
]


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
    seal = json.loads((PANEL_DIR / "SEAL.json").read_text(encoding="utf-8"))
    if [case["case_id"] for case in panel] != [case_id for case_id, _, _ in VERDICTS]:
        raise SystemExit("verdict order does not match the sealed panel")

    cases = []
    for index, (case, (case_id, verdict, reason)) in enumerate(zip(panel, VERDICTS)):
        cases.append({"index": index, "case_id": case_id, "kind": case["kind"],
                      "group": case["group"], "target": case["target"],
                      "expected_path": case["expected_path"], "literal": case["text"],
                      "criterion": case["criterion"], "verdict": verdict, "reason": reason,
                      "coverage_added": case_id in CREDITED,
                      "invocation_id": RECEIPTS.get(case_id),
                      "terminal": terminals[index] if index < len(terminals) else None})
    passed = sum(1 for case in cases if case["verdict"] == "pass")
    adjudication = {
        "schema": "c03-repair1033-root-adjudication-v1",
        "utc": utc,
        "adjudicator": "root (Opus 5, maquina original REDPC)",
        "source_commit": candidate["head"],
        "repair_under_measurement": seal["repair_under_measurement"],
        "sealed_criterion_narrowing": seal["sealed_criterion_narrowing"],
        "candidate_manifest_sha256": sha_file(PRIVATE / "CANDIDATE_AUTHORIZED.json"),
        "seal_sha256": prereg["seal_sha256"],
        "runner_sha256": prereg["runner_sha256"],
        "preparation_sha256": prereg["preparation_sha256"],
        "executed": len(cases), "passed": passed, "failed": len(cases) - passed,
        "coverage_added": len(CREDITED), "credited_case_ids": CREDITED,
        "credit_pairs": {case_id: CREDIT_PAIRS for case_id in CREDITED},
        "credit_pair_note": (
            "Tres variantes pertinentes de la misma conducta y de la misma salida pasaron en esta tanda: "
            "dev-02 (Paint, inglés), dev-03 (Steam, español) y dev-04 (Steam, inglés). La regla pide dos; "
            "hay tres y en los dos idiomas."),
        "regression_controls": {
            "case_ids": ["H0085", "H0315", "H0317", "H0251", "H0706"],
            "result": "5/5 veraces, dos de ellos del camino de lanzamiento: la dirección nueva del "
                      "chequeo no rompió nada. Ninguno acredita dos veces.",
        },
        "third_refinement_found": (
            "H0575 falló por tercera vez y por un matiz más fino que el anterior: con "
            "alreadyRunning=false publicó «Ya está abierta la calculadora.». El chequeo excluye a "
            "propósito el presente «ya está abierta» porque después de abrirla es cierto, pero «ya» "
            "delante del estado sigue enmarcándolo como preexistente y oculta el efecto. La reparación "
            "siguiente es exigir, cuando el recibo dice que no estaba en ejecución, que la frase "
            "atribuya la apertura en lugar de describir sólo el estado."),
        "boundary_regression_noted": (
            "boundary-02 empeoró respecto a REPAIR1032: la misma cita ajena que allí se contestó limpia "
            "ahora añade «El intento no fue válido y no se pudo verificar.», afirmando un intento que no "
            "hubo. No acredita en ningún caso, pero queda anotado como pérdida de calidad observada."),
        "resources": json.loads((PUBLIC / "RESOURCES.json").read_text(encoding="utf-8")),
        "exit": json.loads((PUBLIC / "EXIT.json").read_text(encoding="utf-8")),
        "tests_run": False, "validation_policy": "owner_directed_no_tests",
        "cases": cases,
    }
    target = PUBLIC / "ROOT_ADJUDICATION.json"
    if target.exists():
        raise SystemExit("adjudication already written")
    target.write_text(json.dumps(adjudication, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8", newline="\n")

    raw = REGISTRY.read_bytes()
    before = hashlib.sha256(raw).hexdigest()
    backup = REGISTRY.with_suffix(".jsonl.before-1033.bak")
    if not backup.exists():
        backup.write_bytes(raw)
    rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    by_id = {row["case_id"]: row for row in rows}
    touched = []
    for case_id, verdict, reason in VERDICTS:
        if not case_id.startswith("H"):
            continue
        row = by_id[case_id]
        control = row["verification_status"] == "covered"
        entry = {"campaign": "REPAIR1033", "source_candidate": candidate["head"],
                 "root_adjudication": ADJUDICATION,
                 "root_case_pointer": f"/cases/[case_id={case_id}]",
                 "panel_seal_sha256": prereg["seal_sha256"], "verdict": verdict,
                 "kind": "regression_control" if control else "repair_measurement",
                 "ui_or_voice_credit": False}
        if case_id in RECEIPTS:
            entry["invocation_id"] = RECEIPTS[case_id]
            entry["observed"] = {"app": "Steam", "already_running": True,
                                 "process": 29716, "window": 68266}
            entry["variants"] = CREDIT_PAIRS
        row["verification_evidence"] = list(row.get("verification_evidence") or []) + [entry]
        if not control:
            row["verification_status"] = "covered" if verdict == "pass" else "open"
            row["verification_reason"] = reason
        row["verification_updated_at"] = utc
        touched.append({"case_id": case_id, "status": row["verification_status"],
                        "kind": entry["kind"]})
    REGISTRY.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
                        encoding="utf-8", newline="\n")
    counts = {status: sum(1 for row in rows if row["verification_status"] == status)
              for status in ("covered", "open", "not_applicable")}
    (PUBLIC / "REGISTRY_UPDATE.json").write_text(json.dumps({
        "schema": "c03-repair1033-registry-update-v1", "utc": utc, "registry": str(REGISTRY),
        "registry_sha256_before": before, "registry_sha256_after": sha_file(REGISTRY),
        "backup": str(backup), "rows": len(rows), "counts": counts,
        "coverage_added": len(CREDITED), "credited_case_ids": CREDITED,
        "rows_touched": sorted(touched, key=lambda item: item["case_id"]),
        "adjudication": ADJUDICATION, "tests_run": False,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"passed": passed, "failed": len(cases) - passed,
                      "coverage_added": len(CREDITED), "counts": counts,
                      "registry_sha256_after": sha_file(REGISTRY)}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
