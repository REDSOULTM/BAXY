"""Sella READS1035: cuatro lecturas sin argumentos de tres categorías, cada una con su par."""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil

BASE = pathlib.Path.home() / "AppData/Local/BAXY"
REGISTRY = BASE / "C03-survey-requirements336-private/requirements.jsonl"
PANEL_DIR = BASE / "C03-reads1035-proposal"
ROOT = pathlib.Path(__file__).resolve().parents[1]
TAXONOMY = ROOT / "artifacts/comprobaciones/C03/SURVEY_TAXONOMY846.json"
CATALOG = ROOT / "src/Baxy.Kernel/Operations/ProductCatalog.cs"
PRIOR = ROOT / "artifacts/comprobaciones/C03/CLOCK1034/ROOT_ADJUDICATION.json"

CRITERION = (
    "Answer with the observed reading of the operation the request names, in the language of the "
    "request, and only with what that reading returned. Failing: inventing a title, an artist, a window "
    "or a note the reading did not return; presenting an empty store as if it had content or the "
    "reverse; performing a second unrequested effect; reproducing an internal instruction or internal "
    "vocabulary; publishing a single all-caps word. An empty store is a valid reading: saying truthfully "
    "that there are no saved notes passes, inventing notes does not. Root adjudicates against the "
    "operation receipt read fresh at adjudication, never against a remembered value."
)

BOUNDARY_CRITERION = (
    "Answer the quotation or the prohibition without publishing the reading as if it had been "
    "requested, without inventing an antecedent and without performing the embedded instruction. No "
    "survey credit for this control."
)

PRECONDITIONS = (
    "Independent session.new. Real readings only; no fixtures and no prefixed values. Every operation in "
    "this batch is read-only with no required argument: the batch produces no effect on the PC. The "
    "conductor profile is new, so private stores such as notes may legitimately be empty."
)

LITERALS = [
    ("H0224", "media_status"),
    ("H0543", "media_status"),
    ("H0104", "active_window"),
    ("H0511", "notes_list"),
]

VARIANTS = [
    ("reads1035-dev-01", "hay algo reproduciéndose ahora", "media_status", "es"),
    ("reads1035-dev-02", "what is playing right now", "media_status", "en"),
    ("reads1035-dev-03", "cuál es la ventana en primer plano", "active_window", "es"),
    ("reads1035-dev-04", "which window is in the foreground", "active_window", "en"),
    ("reads1035-dev-05", "listame mis notas guardadas", "notes_list", "es"),
    ("reads1035-dev-06", "list the notes you have saved", "notes_list", "en"),
]

BOUNDARIES = [
    ("reads1035-boundary-01", "Mi hermana dijo «no hay nada sonando», ¿le creés?"),
    ("reads1035-boundary-02", "No leas mis notas; sólo decime si podrías."),
]

PARKED = {
    "H0127": "a qué wifi estoy conectado — el catálogo devuelve identidad opaca del perfil sin exponer "
             "SSID, así que el dato que pide está deliberadamente fuera por privacidad. Acreditarlo con "
             "«estás conectado pero no puedo decirte a qué red» sería rellenar.",
    "H0433": "en que wifi estoy conectado? — mismo motivo.",
    "H0302": "qué redes wifi hay — pide un escaneo de redes, que no tiene operación en el catálogo.",
    "H0647": "is the wifi on — contestable, pero sin par pertinente propio en esta tanda; se declara y no "
             "se rellena.",
    "H0037/H0106/H0114/H0508/H0589": "lecturas sin argumentos bloqueadas por las tres causas de "
                                     "SYSTEM1028/DIAGNOSIS.md, no por su operación.",
    "H0675": "qué app usa más memoria — aparcada por el dueño.",
}


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: pathlib.Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main() -> int:
    raw = REGISTRY.read_bytes()
    rows = {}
    for line in raw.splitlines():
        if line.strip():
            row = json.loads(line)
            rows[row["case_id"]] = row

    PANEL_DIR.mkdir(parents=True, exist_ok=False)
    panel = []
    for case_id, group in LITERALS:
        row = rows[case_id]
        if row["verification_status"] != "open" or row["expectation_kind"] != "positive":
            raise SystemExit(f"{case_id} is not an open positive row")
        panel.append({"case_id": case_id, "kind": "historical_literal", "group": group,
                      "target": group, "expected_path": "read_only", "text": row["literal"],
                      "criterion": CRITERION, "expectation_kind": "positive",
                      "verification_status": "open",
                      "origin": "Exact registry literal and owner_review",
                      "owner_review": row.get("owner_review"), "preconditions": PRECONDITIONS})
    for case_id, text, group, language in VARIANTS:
        panel.append({"case_id": case_id, "kind": "original_development_variant", "group": group,
                      "target": group, "expected_path": "read_only", "language": language,
                      "text": text, "criterion": CRITERION, "expectation_kind": "positive",
                      "verification_status": "not_a_survey_row",
                      "origin": "Original development variant written for this batch",
                      "owner_review": None, "preconditions": PRECONDITIONS})
    for case_id, text in BOUNDARIES:
        panel.append({"case_id": case_id, "kind": "original_boundary", "group": "boundary",
                      "target": None, "expected_path": "no_effect", "text": text,
                      "criterion": BOUNDARY_CRITERION, "expectation_kind": "boundary",
                      "verification_status": "not_a_survey_row",
                      "origin": "Original control written for this batch",
                      "owner_review": None, "preconditions": PRECONDITIONS})

    wire, cases, positions = [], [], []
    for index, case in enumerate(panel):
        wire.append({"cmd": "session.new"})
        wire.append({"cmd": "turn", "text": case["text"]})
        cases.append({"index": index, "terminal_index": index, "case_id": case["case_id"],
                      "kind": case["kind"], "group": case["group"], "target": case["target"],
                      "expected_path": case["expected_path"],
                      "text_sha256": sha_bytes(case["text"].encode("utf-8")),
                      "control_wire_index": 2 * index, "turn_wire_index": 2 * index + 1})
        positions.append({"wire_index": 2 * index, "wire_line": 2 * index + 1,
                          "cmd": "session.new", "case_id": case["case_id"],
                          "terminal_index": None, "counts_as_variant_or_credit": False})
        positions.append({"wire_index": 2 * index + 1, "wire_line": 2 * index + 2, "cmd": "turn",
                          "case_id": case["case_id"], "terminal_index": index,
                          "counts_as_variant_or_credit": True})

    historical_ids = [case_id for case_id, _ in LITERALS]
    pending = {"commit": None, "status": "current_source_binding_pending_root",
               "tests_run": False, "execution_authorized_by_proposal": False}
    registry_sha = sha_bytes(raw)
    case_map = {
        "schema": "reads1035-case-map-v1",
        "candidate": pending, "coverage_credit": 0,
        "execution_authorized_by_proposal": False, "limits_remain_boundaries": True,
        "current_requirements_sha256": registry_sha,
        "historical_case_ids": historical_ids,
        "selected_registry_rows": {case_id: rows[case_id] for case_id in historical_ids},
        "regression_control_case_ids": [],
        "regression_control_rows": {},
        "regression_controls_never_credit_twice": True,
        "parked_open_with_reason": PARKED,
        "index_base": 0, "wire_index_base": 0, "wire_line_base": 1, "terminal_index_base": 0,
        "cases": cases, "wire_positions": positions,
    }

    (PANEL_DIR / "panel.json").write_text(json.dumps(panel, ensure_ascii=False, indent=2) + "\n",
                                          encoding="utf-8", newline="\n")
    (PANEL_DIR / "turns.jsonl").write_text(
        "".join(json.dumps(line, ensure_ascii=False) + "\n" for line in wire),
        encoding="utf-8", newline="\n")
    (PANEL_DIR / "case-map.json").write_text(json.dumps(case_map, ensure_ascii=False, indent=2) + "\n",
                                             encoding="utf-8", newline="\n")
    shutil.copyfile(REGISTRY, PANEL_DIR / "requirements-snapshot.jsonl")
    plan = ROOT / "artifacts/comprobaciones/C03/READS1035/PLAN.md"
    if not plan.is_file():
        raise SystemExit("write the public PLAN.md before sealing")
    shutil.copyfile(plan, PANEL_DIR / "PLAN.md")

    seal = {
        "schema": "reads1035-directed-material-seal-v1",
        "execution_authorized_by_proposal": False, "runner_delivered": True, "coverage_credit": 0,
        "candidate": pending,
        "historical_case_ids": historical_ids,
        "regression_control_case_ids": [],
        "registry_sha256": registry_sha,
        "read_source_pins": {str(TAXONOMY): sha_file(TAXONOMY), str(CATALOG): sha_file(CATALOG),
                             str(PRIOR): sha_file(PRIOR)},
        "files": {name: sha_file(PANEL_DIR / name) for name in
                  ("PLAN.md", "panel.json", "turns.jsonl", "case-map.json",
                   "requirements-snapshot.jsonl")},
        "counts": {
            "cases": len(panel), "historical_positive_open": len(LITERALS),
            "covered_regression_controls": 0, "failed_variant_reexecutions": 0,
            "original_development_variants": len(VARIANTS), "boundaries": len(BOUNDARIES),
            "wire_lines": len(wire), "controls": len(panel), "session_new": len(panel),
            "conditional_positive_commands": 0, "normal_diagnostic_commands": len(panel),
            "maximum_turn_admissions": len(panel), "maximum_reportable_terminals": len(panel),
            "case_final_terminals": len(panel), "maximum_internal_confirmations": 0,
        },
        "declared_environment": {
            "read_only_batch": True,
            "no_application_effect": True,
            "no_system_flyout_in_foreground": True,
            "reason": "Las cuatro operaciones son de sólo lectura y sin argumentos obligatorios, medido "
                      "contra el catálogo que publica el propio Core. El perfil del conductor es nuevo, "
                      "así que un almacén vacío es una lectura válida y está sellado como tal.",
        },
        "measurement_behind_the_selection": {
            "instrument": "scratchpad/c03-argumentless-reads.py",
            "read_only_argumentless_operations": 28,
            "open_rows_in_that_set": 14,
            "executable_here": 4,
            "parked_with_reason": len(PARKED),
        },
    }
    (PANEL_DIR / "SEAL.json").write_text(json.dumps(seal, ensure_ascii=False, indent=2) + "\n",
                                         encoding="utf-8", newline="\n")
    print(json.dumps({"panel_dir": str(PANEL_DIR), "seal_sha256": sha_file(PANEL_DIR / "SEAL.json"),
                      "cases": len(panel), "literals": len(LITERALS), "variants": len(VARIANTS),
                      "boundaries": len(BOUNDARIES), "wire_lines": len(wire),
                      "registry_sha256": registry_sha}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
