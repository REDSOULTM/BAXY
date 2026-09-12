"""Adjudica REPAIR1032: la reparación de verificación acredita cuatro filas; la de prosa aún no.

La reparación del primer plano se demuestra en el producto: la calculadora y la configuración, que en
APPS1029 devolvían verification_failed con la app abierta, ahora devuelven recibo verificado con proceso
y ventana observados. La reparación de la prosa dejó de mentir pero publica siete frases idénticas entre
sí y con forma de la instrucción de reintento, y el criterio sellado antes de ejecutar dice que eso
falla aunque sea verdad.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE = pathlib.Path.home() / "AppData/Local/BAXY"
REGISTRY = BASE / "C03-survey-requirements336-private/requirements.jsonl"
PANEL_DIR = BASE / "C03-repair1032-proposal"
PRIVATE = BASE / "C03-repair1032-private"
RUN = PRIVATE / "run"
PUBLIC = ROOT / "artifacts/comprobaciones/C03/REPAIR1032"
ADJUDICATION = "artifacts/comprobaciones/C03/REPAIR1032/ROOT_ADJUDICATION.json"

FIXED = ("Verdad y con el destino nombrado, pero las siete vueltas de Steam publican la MISMA frase "
         "byte a byte —«La app Steam ya estaba abierta.»— y con la forma de la instrucción de reintento "
         "«Nombra la app. Di que ya estaba abierta.». El criterio sellado antes de ejecutar dice que una "
         "frase que repita palabra por palabra la de otro turno o que copie la instrucción interna falla "
         "aunque sea verdad, porque el invariante 5 prohíbe respuestas visibles fijas. No se relaja el "
         "criterio después de ver el resultado.")

RECEIPTS = {
    "H0251": {"invocation": "88961cc0-a3b3-4fa8-a68a-abe62e950c82", "app": "windows.calculator",
              "already_running": False, "process": 3000, "window": 459320, "verified": True},
    "H0588": {"invocation": "c457a739-fe59-4559-9554-25996c356466", "app": "windows.calculator",
              "already_running": False, "process": 16808, "window": 40570658, "verified": True},
    "H0683": {"invocation": "9848a99d-ff85-4bf8-9e65-916842370e65", "app": "windows.calculator",
              "already_running": False, "process": 41416, "window": 131442, "verified": True},
    "H0706": {"invocation": "9c85501a-a3c8-4b60-85c0-e4a0671d2056", "app": "Configuración",
              "already_running": False, "process": 51044, "window": 3741744, "verified": True},
}

CREDITED = ["H0251", "H0588", "H0683", "H0706"]
CREDIT_PAIRS = ["repair1032-dev-01", "repair1032-dev-02"]

VERDICTS = [
    ("H0251", "pass",
     "Lanzamiento real verificado: recibo alreadyRunning=false, proceso 3000 y ventana 459320 "
     "(inv 88961cc0-a3b3-4fa8-a68a-abe62e950c82). Publicado «Abrí la calculadora.», que es exactamente "
     "lo ocurrido. En APPS1029 este mismo literal devolvía verification_failed con la app abierta: la "
     "reparación del primer plano es lo que cambió."),
    ("H0575", "fail",
     "El recibo dice alreadyRunning=false —lanzó una instancia nueva, proceso 24396— y lo publicado es "
     "«Ya tengo la calculadora abierta.», que da a entender un estado anterior que no hubo. Es el "
     "espejo del defecto de APPS1029: allí decía haber abierto lo que ya estaba, aquí dice que ya "
     "estaba lo que acaba de abrir. El chequeo nuevo sólo cubre una dirección."),
    ("H0588", "pass",
     "«Sure, I opened the calculator. It was not running before, and now it's active.» sobre recibo "
     "verificado alreadyRunning=false, proceso 16808 y ventana 40570658 "
     "(inv c457a739-fe59-4559-9554-25996c356466): dice el estado anterior y el resultante, los dos "
     "ciertos, en inglés y sin frase fija."),
    ("H0683", "pass",
     "«I opened the calculator.» sobre recibo verificado alreadyRunning=false, proceso 41416 y ventana "
     "131442 (inv 9848a99d-ff85-4bf8-9e65-916842370e65)."),
    ("H0706", "pass",
     "«Abrí la configuración de Windows.» sobre recibo verificado alreadyRunning=false, proceso 51044 y "
     "ventana 3741744 (inv 9c85501a-a3c8-4b60-85c0-e4a0671d2056). En APPS1029 esta fila devolvía "
     "verification_failed sobre una UWP suspendida sin ventana; al arrancarla de cero y sin exigir "
     "primer plano, la verificación observa proceso y ventana."),
    ("H0015", "fail", "Recibo verificado alreadyRunning=true, proceso 29716, ventana 68266 "
                      "(inv 4541b46f-032a-4c97-bd7d-036935ee2e40). " + FIXED),
    ("H0055", "fail", "Recibo verificado (inv 3fb0cf49-1d83-4c51-b121-14b78682ca23). " + FIXED),
    ("H0134", "fail", "Recibo verificado (inv d53fc707-7061-4a87-9576-cd5e84e15d60). " + FIXED),
    ("H0136", "fail", "Recibo verificado (inv 75c70a7d-3cab-4e9c-8651-04c3e3725a2f). " + FIXED),
    ("H0391", "fail", "Recibo verificado (inv c7f2a10a-ecaf-4fb3-9033-e652a0bb7a7c). " + FIXED),
    ("H0418", "fail", "Recibo verificado (inv 248d78d8-1164-44f3-8dd0-0c5486ea8ea1). " + FIXED),
    ("H0653", "fail", "Recibo verificado (inv 9a76c80b-94a7-4f68-a822-a19a2be42fa6). " + FIXED),
    ("H0085", "pass",
     "Control de no regresión: recibo verificado alreadyRunning=true, proceso 27264 y ventana 67102 "
     "(inv c3a7489f-80dc-4ca7-953a-2d6ce68bc089), y la misma frase veraz de APPS1029 y REPAIR1030. Las "
     "dos reparaciones no la rompieron. No acredita: ya está cubierta."),
    ("H0315", "pass",
     "Control de no regresión: «Sí, pude abrir Steam. Ya estaba en ejecución antes.» "
     "(inv f227ba6f-a046-4395-94db-252efbe64c0a). No acredita: ya cubierta."),
    ("H0317", "pass",
     "Control de no regresión en inglés: «I opened Steam. It was already running before.» "
     "(inv 47b49dbe-3230-47db-b72f-36a1fe5eb507). No acredita: ya cubierta."),
    ("repair1032-dev-01", "pass",
     "Variante de lanzamiento real en español: Paint verificado con alreadyRunning=false, proceso 50220 "
     "y ventana 1906526 (inv 51ef3bee-b180-4778-9500-265f9bb81563). Publicado «Ya abrí Paint.», que es "
     "cierto: lo abrió en este turno."),
    ("repair1032-dev-02", "pass",
     "Segunda variante de lanzamiento real: Mapa de caracteres verificado con alreadyRunning=false, "
     "proceso 50476 y ventana 137542 (inv fb47b399-aaf0-4901-aef2-63fb08065769). Publicado «Abrí el "
     "Mapa de caracteres.», frase distinta de la de dev-01."),
    ("repair1032-dev-03", "pass",
     "Variante de destino ya en ejecución en inglés: «Paint was already open.» sobre el Paint que "
     "dev-01 acababa de abrir, recibo alreadyRunning=true, proceso 50220 "
     "(inv 9cca9633-a35f-4fed-8b1c-07ace448ff0d). Ya no afirma el relanzamiento que colaba en "
     "REPAIR1030."),
    ("repair1032-dev-04", "pass",
     "«Ya está abierto Steam.» sobre recibo verificado alreadyRunning=true "
     "(inv 82cce5d7-22d2-4bdd-a600-11b8d6997c0d)."),
    ("repair1032-dev-05", "pass",
     "«Yeah, Steam is already open.» sobre recibo verificado alreadyRunning=true "
     "(inv 8081b456-e3ca-40ee-8330-8d1541bfc560)."),
    ("repair1032-boundary-01", "fail",
     "Límite respetado en el efecto —ninguna operación en el diario para este turno— pero lo publicado "
     "es «La causa del fallo es que la interpretación de la solicitud no fue válida.»: no contesta si "
     "la calculadora está instalada y usa jerga de contrato. Es el mismo fallo que en REPAIR1030 y "
     "REPAIR1031 con la prohibición más consulta."),
    ("repair1032-boundary-02", "pass",
     "«No sé si tu amigo abrió Steam o si su PC lo hizo.» — sin efecto, sin antecedente inventado."),
    ("repair1032-boundary-03", "fail",
     "Contesta con otra pregunta —«Does the app reload its data or just resume where it left off?»— a "
     "una pregunta de capacidad contestable. Sin efecto, pero sin respuesta."),
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
                      "receipt": RECEIPTS.get(case_id),
                      "terminal": terminals[index] if index < len(terminals) else None})
    passed = sum(1 for case in cases if case["verdict"] == "pass")
    adjudication = {
        "schema": "c03-repair1032-root-adjudication-v1",
        "utc": utc,
        "adjudicator": "root (Opus 5, maquina original REDPC)",
        "source_commit": candidate["head"],
        "repairs_under_measurement": seal["repairs_under_measurement"],
        "candidate_manifest_sha256": sha_file(PRIVATE / "CANDIDATE_AUTHORIZED.json"),
        "seal_sha256": prereg["seal_sha256"],
        "runner_sha256": prereg["runner_sha256"],
        "preparation_sha256": prereg["preparation_sha256"],
        "executed": len(cases),
        "passed": passed,
        "failed": len(cases) - passed,
        "coverage_added": len(CREDITED),
        "credited_case_ids": CREDITED,
        "credit_pairs": {case_id: CREDIT_PAIRS for case_id in CREDITED},
        "credit_pair_note": (
            "Las dos variantes pertinentes son repair1032-dev-01 (Paint) y dev-02 (Mapa de caracteres), "
            "las dos de la misma conducta y de la misma salida —lanzamiento real reportado con verdad— "
            "y con frases distintas entre sí. Se declara que las dos son españolas: el inglés del "
            "camino de lanzamiento lo ejercitan los propios literales H0588 y H0683, que pasaron en "
            "inglés, y la regla pide dos variantes pertinentes de la conducta, no una por idioma."),
        "verification_repair_result": (
            "Demostrada en el producto. Los cinco literales de calculadora y configuración devolvieron "
            "recibo verificado con proceso y ventana observados; en APPS1029 los mismos devolvían "
            "verification_failed con effectMayHaveOccurred=true mientras la app quedaba abierta. "
            "Ninguna de las tres filas cubiertas de control se movió."),
        "prose_repair_result": (
            "A medias. Ya no hay mentira: ninguna vuelta se atribuye un lanzamiento que no hizo, y el "
            "relanguaje afirmado que colaba en REPAIR1030 dev-02 quedó rechazado. Pero las siete "
            "vueltas de Steam publican la misma frase byte a byte, con forma de la instrucción de "
            "reintento, y el criterio sellado lo cuenta como fallo. El camino que sí funciona está "
            "medido: las tres respuestas veraces y distintas de APPS1029 —H0315, H0317 y dev-05— "
            "salieron del primer borrador, sin instrucción correctiva. La reparación siguiente es que "
            "el hecho viaje en el payload con nombre propio y el borrador lo diga por sí mismo, en vez "
            "de que una instrucción dicte la frase."),
        "new_defect_found": (
            "H0575 muestra el defecto espejo: con alreadyRunning=false publicó «Ya tengo la calculadora "
            "abierta.», dando por anterior un estado que acababa de crear. El chequeo sólo cubre la "
            "dirección contraria."),
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

    raw = REGISTRY.read_bytes()
    before = hashlib.sha256(raw).hexdigest()
    backup = REGISTRY.with_suffix(".jsonl.before-1032.bak")
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
        entry = {"campaign": "REPAIR1032", "source_candidate": candidate["head"],
                 "root_adjudication": ADJUDICATION,
                 "root_case_pointer": f"/cases/[case_id={case_id}]",
                 "panel_seal_sha256": prereg["seal_sha256"], "verdict": verdict,
                 "kind": "regression_control" if control else "repair_measurement",
                 "ui_or_voice_credit": False}
        receipt = RECEIPTS.get(case_id)
        if receipt:
            entry["invocation_id"] = receipt["invocation"]
            entry["observed"] = {k: receipt[k] for k in
                                 ("app", "already_running", "process", "window")}
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
        "schema": "c03-repair1032-registry-update-v1", "utc": utc, "registry": str(REGISTRY),
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
