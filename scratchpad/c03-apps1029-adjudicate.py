"""Adjudica APPS1029 y escribe el crédito en el registro. Un solo escritor: raíz.

Los veredictos son juicio de raíz contra el criterio sellado antes de ejecutar, y cada uno cita su
evidencia: el terminal publicado, el recibo del diario (identidad de proceso y ventana observada) y,
cuando importa, el payload que recibió el compositor. Preserva la evidencia anterior de cada fila y
sólo toca `verification_status`, `verification_evidence`, `verification_reason` y
`verification_updated_at`.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE = pathlib.Path.home() / "AppData/Local/BAXY"
REGISTRY = BASE / "C03-survey-requirements336-private/requirements.jsonl"
PANEL_DIR = BASE / "C03-apps1029-proposal"
PRIVATE = BASE / "C03-apps1029-private"
RUN = PRIVATE / "run"
PUBLIC = ROOT / "artifacts/comprobaciones/C03/APPS1029"

ADJUDICATION = "artifacts/comprobaciones/C03/APPS1029/ROOT_ADJUDICATION.json"

# Recibo verificado por invocación, leído del diario en la adjudicación.
RECEIPTS = {
    "H0085": {"invocation": "4932ed1b-a64d-4874-8c53-6946e5cf7705", "app": "Discord",
              "already_running": True, "process": 27264, "window": 67102, "verified": True},
    "H0315": {"invocation": "3dbea569-838f-4907-ba6b-8638b43f062f", "app": "Steam",
              "already_running": True, "process": 29716, "window": 68266, "verified": True},
    "H0317": {"invocation": "f5d0642f-6550-485a-ab01-4f0f5f8aa88d", "app": "Steam",
              "already_running": True, "process": 29716, "window": 68266, "verified": True},
}

CAUSE_A = ("app_open_verification_requires_visible_foreground_window: el recibo vuelve "
           "verification_failed con effectMayHaveOccurred=true aunque la app quedó abierta. "
           "CalculatorApp pid40560 arrancó a las 01:50:51 locales, dentro de la ventana de la tanda "
           "(04:50:34–04:51:56 UTC). WindowsCalculatorOpenProvider.cs:44-56 exige que la ventana sea "
           "la del primer plano y sólo intenta ShowWindowAsync+SetForegroundWindow (:118), sin el "
           "traspaso AttachThreadInput que sí usa WindowsInstalledApplicationOpenProvider.cs:1176-1197 "
           "para los destinos que en esta misma tanda verificaron.")

CAUSE_B = ("already_running_dropped_in_prose: el payload de las once vueltas de app.open sobre Steam "
           "es idéntico y lleva was_running_before_open=true; el compositor lo publica en tres y lo "
           "omite en ocho, afirmando un lanzamiento que el producto no hizo. required_fact_count=0 "
           "para ese payload: el hecho no está declarado obligatorio.")

VERDICTS: list[tuple[str, str, str]] = [
    ("H0251", "fail",
     "app.open invocado (inv 4409f036-9939-4436-9cc0-743a98a6737a) y devuelto failed/"
     "verification_failed con effectMayHaveOccurred=true. La calculadora sí quedó abierta, así que el "
     "producto no miente, pero tampoco cumple lo pedido: publica «La causa del fallo es que el "
     "resultado no se ha verificado.». " + CAUSE_A),
    ("H0497", "fail",
     "«abre a calculadora» no llegó al reconocedor de efectos: decision_path explicit_conversation y "
     "respuesta pidiendo repetir el pedido «en español o inglés», cuando el pedido ya está en español "
     "con una letra de más. Ninguna operación invocada. Causa distinta de las demás de su grupo: el "
     "camino de idioma/no comprendido se dispara por una desviación de una letra."),
    ("H0575", "fail",
     "Mismo relato de fallo que H0251 —el compositor recibió situation cause=result_unverified— sin "
     "invocación nueva en el diario para este turno. " + CAUSE_A),
    ("H0588", "fail",
     "Igual que H0575 en inglés: «I can't open the calculator because the result is unverified.». "
     + CAUSE_A),
    ("H0683", "fail",
     "Igual que H0575 en inglés: «I couldn't verify the result of opening the calculator.». " + CAUSE_A),
    ("H0085", "pass",
     "app.open verificado, alreadyRunning=true, proceso 27264 y ventana 67102 observados "
     "(inv 4932ed1b-a64d-4874-8c53-6946e5cf7705). Publicado: «Abrí Discord. La aplicación ya estaba en "
     "ejecución antes de abrirla.» — destino correcto y estado resultante dicho con verdad, sin "
     "afirmar un lanzamiento que no hizo."),
    ("H0706", "fail",
     "app.open sobre la configuración de Windows devolvió verification_failed con "
     "effectMayHaveOccurred=true (inv ef6d18fe-3f52-4b30-a1f8-5260cf6944c6). SystemSettings pid20500 "
     "llevaba en ejecución desde el 2026-09-11 16:14 como aplicación UWP suspendida, sin ventana "
     "visible que el verificador pueda observar. " + CAUSE_A),
    ("H0015", "fail",
     "Recibo verificado con alreadyRunning=true (inv e2c6f476-28d3-437e-b1e2-6005df2c1cba), pero lo "
     "publicado es «Ya abrí Steam.»: atribuye a BAXY un lanzamiento que no ocurrió y omite que ya "
     "estaba en ejecución. " + CAUSE_B),
    ("H0055", "fail",
     "Recibo verificado alreadyRunning=true (inv 59e3825d-e1c6-430e-9c8e-ae449cb4eeed); publicado "
     "«Abrí Steam.». " + CAUSE_B),
    ("H0134", "fail",
     "Recibo verificado alreadyRunning=true (inv fce04e73-1f0c-40d5-8cb5-550f10b83c98); publicado "
     "«Ya abrí Steam.». " + CAUSE_B),
    ("H0136", "fail",
     "Recibo verificado alreadyRunning=true (inv ca512084-d5c3-4fae-9658-2e0484022af7); publicado "
     "«Ya abrí Steam.». " + CAUSE_B),
    ("H0315", "pass",
     "app.open verificado, alreadyRunning=true, proceso 29716 y ventana 68266 "
     "(inv 3dbea569-838f-4907-ba6b-8638b43f062f). Publicado: «Sí, pude abrir Steam. Ya estaba en "
     "ejecución antes.» — contesta la pregunta y dice el estado real sin inventar un lanzamiento."),
    ("H0317", "pass",
     "app.open verificado, alreadyRunning=true, proceso 29716 y ventana 68266 "
     "(inv f5d0642f-6550-485a-ab01-4f0f5f8aa88d). Publicado en inglés: «I opened Steam. It was already "
     "running before.» — el hecho de que ya estaba en ejecución queda dicho."),
    ("H0391", "fail",
     "Recibo verificado alreadyRunning=true (inv ebcdf7af-08bc-4212-8bcc-57d1d8806b06); publicado "
     "«Abrí Steam.». " + CAUSE_B),
    ("H0418", "fail",
     "Recibo verificado alreadyRunning=true (inv 64c97506-3612-4d36-b699-55aebf629776); publicado "
     "«Abrí Steam.». " + CAUSE_B),
    ("H0544", "fail",
     "Recibo verificado alreadyRunning=true (inv adf3bd8e-c545-4d09-aa1e-f717fac0a272); publicado "
     "«Abrí Steam.». " + CAUSE_B),
    ("H0653", "fail",
     "Recibo verificado alreadyRunning=true (inv 277500b6-5554-490e-9c54-aae1a4c69684); publicado "
     "«Ya abrí Steam.». " + CAUSE_B),
    ("apps1029-dev-01", "pass",
     "Lanzamiento real: app.open verificado con alreadyRunning=false, proceso 20488 y ventana 137262 "
     "(inv aa54ac5e-6a03-4ab6-86ea-a1c121332f99); mspaint pid20488 arrancó a las 01:51:12, dentro de "
     "la ventana de la tanda. Publicado «Abrí Paint.», que es exactamente lo ocurrido."),
    ("apps1029-dev-02", "fail",
     "«open Windows Terminal» cayó al camino del modelo (decision_path model, 28 operaciones "
     "candidatas) y respondió «¿Cuál es el nombre exacto de la aplicación que deseas abrir en Windows "
     "Terminal?»: leyó el destino como contenedor de otra app. Ninguna invocación, y Windows Terminal "
     "no quedó en ejecución. Hueco del reconocedor, no del compositor."),
    ("apps1029-dev-03", "pass",
     "app.open verificado alreadyRunning=true, proceso 23456 y ventana 2823766 "
     "(inv 47617c6c-0fea-4b5e-a2c3-ceefaba20453). Publicado: «I opened Google Chrome. It was already "
     "running, so no new instance was started.»"),
    ("apps1029-dev-04", "fail",
     "«abrime la app de Discord» eligió app.installed en vez de app.open y con requestedName «de "
     "Discord», con la preposición dentro del nombre: el recibo devuelve installed=false "
     "(inv bfb55379-8867-4bde-b82a-41680a6bf646) y lo publicado niega que Discord esté en el catálogo "
     "de inicio, contradiciendo a H0085 en la misma tanda, que sí lo abrió. Dos fallos encadenados: "
     "operación elegida y segmentación de la evidencia."),
    ("apps1029-dev-05", "pass",
     "app.open verificado alreadyRunning=true, proceso 29716 y ventana 68266 "
     "(inv a68de9fd-509d-41ed-990a-9ad0f1802d70). Publicado: «Sure, Steam is already running.»"),
    ("apps1029-boundary-01", "fail",
     "Límite respetado en el efecto —ninguna operación en el diario— pero sin respuesta: dos "
     "PlannerContractError apply_compound_effect_conservation_veto:1873 en compound_conservation, "
     "recuperación semantic_clarification y terminal composition_failed "
     "(no_response;recovery:no_response;retry_exhausted). Una prohibición con pregunta de capacidad "
     "dispara el veto de conservación de efecto compuesto y muere sin publicar."),
    ("apps1029-boundary-02", "pass",
     "Ninguna apertura y ningún antecedente inventado: explica la cita del hermano. La prosa es pobre "
     "—«Abrió el Steam, que es la app de juegos para PC.» usa un pasado que confunde— pero el límite "
     "se respeta y no hay efecto."),
    ("apps1029-boundary-03", "pass",
     "Ninguna apertura, ni ahora ni programada: el límite se respeta. La respuesta «This is outside "
     "what I do on this PC.» no contesta la condición futura, así que se anota como límite respetado "
     "con respuesta poco útil; los límites no acreditan cobertura en ningún caso."),
    ("apps1029-boundary-04", "pass",
     "Contesta la pregunta narrativa sin abrir nada y sin inventar antecedente."),
    ("apps1029-boundary-05", "pass",
     "Explica qué significa la orden sin ejecutarla y sin abrir la calculadora."),
]

CREDIT_PAIRS = ["apps1029-dev-03", "apps1029-dev-05"]
CREDITED = ["H0085", "H0315", "H0317"]


def sha_file(path) -> str:
    with pathlib.Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main() -> int:
    utc = datetime.now(timezone.utc).isoformat()
    panel = json.loads((PANEL_DIR / "panel.json").read_text(encoding="utf-8"))
    events = [json.loads(line) for line in
              (RUN / "capture/events.jsonl").read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    terminals = [row for row in events if row.get("type") == "terminal"]
    exit_receipt = json.loads((PUBLIC / "EXIT.json").read_text(encoding="utf-8"))
    resources = json.loads((PUBLIC / "RESOURCES.json").read_text(encoding="utf-8"))
    prereg = json.loads((PUBLIC / "PREREG.json").read_text(encoding="utf-8"))
    candidate = json.loads((PRIVATE / "CANDIDATE_AUTHORIZED.json").read_text(encoding="utf-8"))

    if [case["case_id"] for case in panel] != [case_id for case_id, _, _ in VERDICTS]:
        raise SystemExit("verdict order does not match the sealed panel")

    cases = []
    for index, (case, (case_id, verdict, reason)) in enumerate(zip(panel, VERDICTS)):
        credited = case_id in CREDITED
        cases.append({
            "index": index,
            "case_id": case_id,
            "kind": case["kind"],
            "group": case["group"],
            "target": case["target"],
            "expected_path": case["expected_path"],
            "literal": case["text"],
            "criterion": case["criterion"],
            "verdict": verdict,
            "reason": reason,
            "coverage_added": credited,
            "receipt": RECEIPTS.get(case_id),
            "terminal": terminals[index] if index < len(terminals) else None,
        })

    passed = sum(1 for case in cases if case["verdict"] == "pass")
    adjudication = {
        "schema": "c03-apps1029-root-adjudication-v1",
        "utc": utc,
        "adjudicator": "root (Opus 5, maquina original REDPC)",
        "source_commit": candidate["head"],
        "product_source_commit": "20dab7edcd34ce87eff2d176613bb5ae4e968e1b",
        "candidate_manifest_sha256": sha_file(PRIVATE / "CANDIDATE_AUTHORIZED.json"),
        "seal_sha256": prereg["seal_sha256"],
        "runner_sha256": prereg["runner_sha256"],
        "preparation_sha256": prereg["preparation_sha256"],
        "executed": len(cases),
        "passed": passed,
        "failed": len(cases) - passed,
        "literal_passes": sum(1 for case in cases
                              if case["kind"] == "historical_literal" and case["verdict"] == "pass"),
        "variant_passes": sum(1 for case in cases
                              if case["kind"] == "original_development_variant" and case["verdict"] == "pass"),
        "boundary_passes": sum(1 for case in cases
                               if case["kind"] == "original_boundary" and case["verdict"] == "pass"),
        "coverage_added": len(CREDITED),
        "credited_case_ids": CREDITED,
        "credit_pairs": {case_id: CREDIT_PAIRS for case_id in CREDITED},
        "credit_pair_note": (
            "Las dos variantes pertinentes que sostienen el crédito son apps1029-dev-03 (Chrome) y "
            "apps1029-dev-05 (Steam), las dos de la misma conducta y de la misma salida —destino ya en "
            "ejecución reportado con verdad— y las dos en inglés. Se declara: la variante española de "
            "esa salida, dev-04, falló por otra causa (segmentación de la evidencia y operación "
            "elegida), así que el par es inglés. El español de la conducta queda evidenciado por los "
            "propios literales H0085 y H0315, que pasaron en español."),
        "parked_in_category": json.loads((PANEL_DIR / "case-map.json").read_text(encoding="utf-8"))["parked_open_with_reason"],
        "fresh_readings": {
            "journal": str(BASE / "C03-apps1029-profile/journal/missions.jsonl"),
            "journal_app_open_invocations": 16,
            "calculator_process_observed_after_run": "CalculatorApp pid40560, arranque 2026-09-12 01:50:51 local",
            "paint_process_observed_after_run": "mspaint pid20488, arranque 2026-09-12 01:51:12 local",
            "terminal_absent_after_run": "WindowsTerminal no quedó en ejecución tras dev-02",
            "settings_process": "SystemSettings pid20500, arranque 2026-09-11 16:14:35 local, UWP suspendida",
        },
        "causes": {
            "A_verification_requires_foreground": CAUSE_A,
            "B_already_running_dropped_in_prose": CAUSE_B,
            "C_recogniser_gap_windows_terminal": (
                "«open Windows Terminal» no resuelve en el reconocedor determinista y el modelo lo lee "
                "como contenedor: pide el nombre de la app a abrir «en Windows Terminal»."),
            "D_preposition_inside_app_name": (
                "«abrime la app de Discord» produce requestedName «de Discord» y elige app.installed en "
                "lugar de app.open; el resultado niega la app que otro turno de la misma tanda abrió."),
            "E_prohibition_with_capability_question_vetoes": (
                "boundary-01 muere en apply_compound_effect_conservation_veto:1873 sin publicar."),
        },
        "resources": resources,
        "exit": exit_receipt,
        "tests_run": False,
        "validation_policy": "owner_directed_no_tests",
        "cases": cases,
    }
    target = PUBLIC / "ROOT_ADJUDICATION.json"
    if target.exists():
        raise SystemExit("adjudication already written; root reviews instead of overwriting")
    target.write_text(json.dumps(adjudication, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8", newline="\n")

    # --- registro ---
    raw = REGISTRY.read_bytes()
    before = hashlib.sha256(raw).hexdigest()
    backup = REGISTRY.with_suffix(".jsonl.before-1029.bak")
    if not backup.exists():
        shutil.copyfile(REGISTRY, backup)
    rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    by_id = {row["case_id"]: row for row in rows}
    verdict_by_id = {case_id: (verdict, reason) for case_id, verdict, reason in VERDICTS}
    touched = []
    for case_id, (verdict, reason) in verdict_by_id.items():
        if not case_id.startswith("H"):
            continue
        row = by_id[case_id]
        evidence = list(row.get("verification_evidence") or [])
        entry = {
            "campaign": "APPS1029",
            "source_candidate": candidate["head"],
            "root_adjudication": ADJUDICATION,
            "root_case_pointer": f"/cases/[case_id={case_id}]",
            "panel_seal_sha256": prereg["seal_sha256"],
            "verdict": verdict,
            "ui_or_voice_credit": False,
        }
        receipt = RECEIPTS.get(case_id)
        if receipt:
            entry["invocation_id"] = receipt["invocation"]
            entry["observed"] = {k: receipt[k] for k in ("app", "already_running", "process", "window")}
            entry["variants"] = CREDIT_PAIRS
        evidence.append(entry)
        row["verification_evidence"] = evidence
        row["verification_status"] = "covered" if verdict == "pass" else "open"
        row["verification_reason"] = reason
        row["verification_updated_at"] = utc
        touched.append({"case_id": case_id, "status": row["verification_status"]})

    REGISTRY.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
                        encoding="utf-8", newline="\n")
    after = sha_file(REGISTRY)
    counts = {"covered": sum(1 for row in rows if row["verification_status"] == "covered"),
              "open": sum(1 for row in rows if row["verification_status"] == "open"),
              "not_applicable": sum(1 for row in rows
                                    if row["verification_status"] == "not_applicable")}
    update = {
        "schema": "c03-apps1029-registry-update-v1",
        "utc": utc,
        "registry": str(REGISTRY),
        "registry_sha256_before": before,
        "registry_sha256_after": after,
        "backup": str(backup),
        "rows": len(rows),
        "counts": counts,
        "coverage_added": len(CREDITED),
        "credited_case_ids": CREDITED,
        "rows_touched": sorted(touched, key=lambda item: item["case_id"]),
        "adjudication": ADJUDICATION,
        "tests_run": False,
    }
    (PUBLIC / "REGISTRY_UPDATE.json").write_text(
        json.dumps(update, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"passed": passed, "failed": len(cases) - passed,
                      "coverage_added": len(CREDITED), "counts": counts,
                      "registry_sha256_after": after}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
