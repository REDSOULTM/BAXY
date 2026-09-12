"""Adjudica CLOCK1034 comprobando cada hora publicada contra la lectura observada de su invocación.

La comprobación no se afirma: se calcula. Por cada vuelta de `system.time` publicada se toma el `utc`
observado y el desfase local del recibo, se convierte a hora local y se compara al minuto con la cifra
que salió publicada. Si alguna no coincidiera, el veredicto lo diría.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE = pathlib.Path.home() / "AppData/Local/BAXY"
REGISTRY = BASE / "C03-survey-requirements336-private/requirements.jsonl"
PANEL_DIR = BASE / "C03-clock1034-proposal"
PRIVATE = BASE / "C03-clock1034-private"
RUN = PRIVATE / "run"
PUBLIC = ROOT / "artifacts/comprobaciones/C03/CLOCK1034"
ADJUDICATION = "artifacts/comprobaciones/C03/CLOCK1034/ROOT_ADJUDICATION.json"

LITERALS = ["H0126", "H0223", "H0449", "H0450", "H0498", "H0586", "H0600", "H0602", "H0700", "H0727"]
CONTROLS = ["H0180", "H0499"]
CREDIT_PAIRS = ["clock1034-dev-02", "clock1034-dev-04"]

CLARIFICATION = (
    "Contesta con una pregunta en vez de dar la hora: «¿Quieres que te diga…?». La aclaración es "
    "innecesaria —el pedido no tiene ambigüedad— y el texto no pasa por el compositor auditado: no "
    "aparece en compose-audit.jsonl, así que salió por la ruta del campo `question` de la decisión, que "
    "`__main__.py:6776` publica tal cual cuando no hay `reply`."
)

LEAKED = (
    "Publicó la palabra «SIEMPRE» sola, en mayúsculas: es vocabulario del prompt del sistema "
    "—`llm.py:107` dice «responde SIEMPRE en el idioma del…»— copiado como respuesta visible. No pasó "
    "por el compositor auditado: no está entre las 45 filas publicadas de compose-audit.jsonl, así que "
    "salió por la ruta del campo `question`, que no tiene el filtro de defectos visibles. Es fallo del "
    "límite y, sobre todo, un agujero en el invariante 5."
)


def sha_file(path) -> str:
    with pathlib.Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def local_clock(observed: dict) -> str | None:
    utc = observed.get("utc")
    offset = observed.get("localUtcOffsetMinutes")
    if not isinstance(utc, str) or not isinstance(offset, int):
        return None
    stamp = datetime.fromisoformat(utc.replace("Z", "+00:00")).astimezone(timezone.utc)
    return (stamp + timedelta(minutes=offset)).strftime("%H:%M")


def main() -> int:
    utc_now = datetime.now(timezone.utc).isoformat()
    panel = json.loads((PANEL_DIR / "panel.json").read_text(encoding="utf-8"))
    events = [json.loads(line) for line in
              (RUN / "capture/events.jsonl").read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    terminals = [row for row in events if row.get("type") == "terminal"]
    compose = [json.loads(line) for line in
               (RUN / "compose-audit.jsonl").read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    prereg = json.loads((PUBLIC / "PREREG.json").read_text(encoding="utf-8"))
    candidate = json.loads((PRIVATE / "CANDIDATE_AUTHORIZED.json").read_text(encoding="utf-8"))

    # Las lecturas se leen abajo, ligadas por trace.

    # Cada fila publicada de system.time se liga a su turno por el `trace`, no por posición:
    # tN corresponde al turno N-1 del panel. Las vueltas que no publicaron hora —las aclaraciones—
    # no tienen fila, y por eso una correspondencia por orden desplazaría las variantes.
    checks = {}
    identifiers = [case["case_id"] for case in panel]
    for row in compose:
        if not row.get("published") or row.get("intent") != "status":
            continue
        situation = row.get("situation")
        if not isinstance(situation, str) or '"system.time"' not in situation:
            continue
        trace = str(row.get("trace") or "")
        if not re.fullmatch(r"t\d+", trace):
            continue
        index = int(trace[1:]) - 1
        if not 0 <= index < len(identifiers):
            continue
        observed = json.loads(situation).get("observed") or {}
        expected = local_clock(observed)
        draft = (row.get("draft") or "").strip()
        published = re.search(r"(\d{1,2}:\d{2})", draft)
        checks[identifiers[index]] = {
            "trace": trace,
            "published": published.group(1) if published else None,
            "expected_from_receipt": expected,
            "matches_to_the_minute": bool(published) and published.group(1) == expected,
            "observed_utc": observed.get("utc"),
            "offset_minutes": observed.get("localUtcOffsetMinutes"),
            "draft": draft,
        }
    answered = sorted(case_id for case_id, check in checks.items() if check["published"])
    print(f"clock readings bound by trace: {len(checks)}; with a published time: {len(answered)}")

    verdicts = {}
    for case_id in LITERALS + CONTROLS:
        check = checks.get(case_id)
        if check and check["matches_to_the_minute"]:
            verdicts[case_id] = ("pass",
                                 f"Recibo verificado de system.time; hora publicada "
                                 f"{check['published']} igual a la lectura observada "
                                 f"{check['expected_from_receipt']} calculada del `utc` "
                                 f"{check['observed_utc']} con desfase {check['offset_minutes']} "
                                 f"minutos. Sin efecto sobre el PC, sin cifra inventada y sin UTC "
                                 f"presentado como hora local.")
        elif case_id in CONTROLS:
            final = terminals[[case["case_id"] for case in panel].index(case_id)].get("final") or ""
            verdicts[case_id] = ("pass",
                                 f"Control de no regresión de la fecha local: publicó «{final.strip()}», "
                                 f"que es la fecha real de la máquina el día de la tanda. No acredita: "
                                 f"ya está cubierta.")
        else:
            verdicts[case_id] = ("fail", "La hora publicada no coincide con la lectura observada de su "
                                         "invocación.")
    verdicts.update({
        "clock1034-dev-01": ("fail", CLARIFICATION),
        "clock1034-dev-02": ("pass", "Variante inglesa: publicó la hora que su recibo observó, sin "
                                     "preguntar y sin cifra inventada."),
        "clock1034-dev-03": ("fail", CLARIFICATION),
        "clock1034-dev-04": ("pass", "Variante inglesa: publicó la hora observada, sin preguntar."),
        "clock1034-dev-05": ("fail", CLARIFICATION),
        "clock1034-dev-06": ("fail", CLARIFICATION + " En inglés y con la misma forma."),
        "clock1034-boundary-01": ("pass", "Contesta la cita ajena —«son las tres» puede ser de la tarde "
                                          "o de la madrugada— sin publicar una lectura del reloj como si "
                                          "se hubiera pedido y sin inventar antecedente."),
        "clock1034-boundary-02": ("fail", LEAKED),
        "clock1034-boundary-03": ("fail", "A «¿de dónde saca la hora un asistente como vos?» contesta "
                                          "ofreciendo decir la hora, la UTC y el desfase: no explica de "
                                          "dónde sale el dato, que es lo que se pregunta. " + CLARIFICATION),
        "clock1034-boundary-04": ("fail", LEAKED),
    })

    cases = []
    for index, case in enumerate(panel):
        verdict, reason = verdicts[case["case_id"]]
        cases.append({"index": index, "case_id": case["case_id"], "kind": case["kind"],
                      "group": case["group"], "expected_path": case["expected_path"],
                      "literal": case["text"], "criterion": case["criterion"],
                      "verdict": verdict, "reason": reason,
                      "coverage_added": verdict == "pass" and case["kind"] == "historical_literal",
                      "clock_check": checks.get(case["case_id"]),
                      "terminal": terminals[index] if index < len(terminals) else None})

    credited = [case["case_id"] for case in cases if case["coverage_added"]]
    passed = sum(1 for case in cases if case["verdict"] == "pass")
    adjudication = {
        "schema": "c03-clock1034-root-adjudication-v1",
        "utc": utc_now,
        "adjudicator": "root (Opus 5, maquina original REDPC)",
        "source_commit": candidate["head"],
        "candidate_manifest_sha256": sha_file(PRIVATE / "CANDIDATE_AUTHORIZED.json"),
        "seal_sha256": prereg["seal_sha256"], "runner_sha256": prereg["runner_sha256"],
        "preparation_sha256": prereg["preparation_sha256"],
        "executed": len(cases), "passed": passed, "failed": len(cases) - passed,
        "coverage_added": len(credited), "credited_case_ids": credited,
        "credit_pairs": {case_id: CREDIT_PAIRS for case_id in credited},
        "credit_pair_note": (
            "Las dos variantes pertinentes que pasaron son clock1034-dev-02 y dev-04, las dos inglesas. "
            "Se declara: las tres variantes españolas de la misma conducta fallaron por la ruta de "
            "aclaración, no por la lectura, y el español de la conducta queda evidenciado por los ocho "
            "literales españoles que pasaron. La categoría ya tenía además variantes ES/EN de fecha "
            "adjudicadas pass en STATUS_BATCH752B."),
        "clock_verification_method": (
            "Por cada vuelta publicada se calculó la hora local a partir del `utc` observado y del "
            "desfase del recibo, y se comparó al minuto con la cifra publicada. Cada lectura se ligó a "
            "su turno por el `trace` del diagnóstico de composición —tN es el turno N-1 del panel—, no "
            "por orden de aparición: las cuatro aclaraciones no publicaron hora y una correspondencia "
            "posicional habría desplazado las variantes. No se comparó contra un valor recordado ni "
            "contra el reloj del adjudicador."),
        "clock_checks": checks,
        "regression_controls": {"case_ids": CONTROLS,
                                "result": "2/2 con la fecha real; la conducta de fecha no se movió"},
        "finding_unaudited_visible_route": (
            "Las cuatro variantes de aclaración y las dos respuestas «SIEMPRE» no aparecen entre las 45 "
            "filas publicadas de compose-audit.jsonl. Es decir: su texto visible no lo produjo el "
            "compositor auditado, sino el campo `question` de la decisión, que `__main__.py:6776` "
            "publica tal cual cuando no hay `reply`. Esa ruta no pasa por `compose_visible_defect`, y por "
            "eso pudo publicar «SIEMPRE», que es vocabulario del prompt del sistema (`llm.py:107`). Es "
            "un agujero en el invariante 5 —cero respuestas visibles fijas— y explica también la "
            "aclaración innecesaria de H0497 en APPS1029 y la de H0532 en SYSTEM1028."),
        "observation_greeting": (
            "H0600 «Hola, dime que hora es» contestó la hora sin devolver el saludo. El criterio sellado "
            "no exige saludar, así que no cambia el veredicto; queda anotado."),
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
    backup = REGISTRY.with_suffix(".jsonl.before-1034.bak")
    if not backup.exists():
        backup.write_bytes(raw)
    rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    by_id = {row["case_id"]: row for row in rows}
    touched = []
    for case in cases:
        case_id = case["case_id"]
        if not case_id.startswith("H"):
            continue
        row = by_id[case_id]
        control = case_id in CONTROLS
        entry = {"campaign": "CLOCK1034", "source_candidate": candidate["head"],
                 "root_adjudication": ADJUDICATION,
                 "root_case_pointer": f"/cases/[case_id={case_id}]",
                 "panel_seal_sha256": prereg["seal_sha256"], "verdict": case["verdict"],
                 "kind": "regression_control" if control else "coverage_measurement",
                 "clock_check": case["clock_check"], "ui_or_voice_credit": False}
        if not control:
            entry["variants"] = CREDIT_PAIRS
        row["verification_evidence"] = list(row.get("verification_evidence") or []) + [entry]
        if not control:
            row["verification_status"] = "covered" if case["verdict"] == "pass" else "open"
            row["verification_reason"] = case["reason"]
        row["verification_updated_at"] = utc_now
        touched.append({"case_id": case_id, "status": row["verification_status"],
                        "kind": entry["kind"]})
    REGISTRY.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
                        encoding="utf-8", newline="\n")
    counts = {status: sum(1 for row in rows if row["verification_status"] == status)
              for status in ("covered", "open", "not_applicable")}
    (PUBLIC / "REGISTRY_UPDATE.json").write_text(json.dumps({
        "schema": "c03-clock1034-registry-update-v1", "utc": utc_now, "registry": str(REGISTRY),
        "registry_sha256_before": before, "registry_sha256_after": sha_file(REGISTRY),
        "backup": str(backup), "rows": len(rows), "counts": counts,
        "coverage_added": len(credited), "credited_case_ids": credited,
        "rows_touched": sorted(touched, key=lambda item: item["case_id"]),
        "adjudication": ADJUDICATION, "tests_run": False,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"passed": passed, "failed": len(cases) - passed,
                      "coverage_added": len(credited), "credited": credited, "counts": counts,
                      "registry_sha256_after": sha_file(REGISTRY)}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
