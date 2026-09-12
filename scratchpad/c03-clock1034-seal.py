"""Sella CLOCK1034: los diez abiertos ejecutables de «Hora y fecha», sin ningún efecto sobre el PC.

Elegida por masa abierta ejecutable: los diez resuelven `system.time` en el reconocedor determinista, la
operación es de sólo lectura y la categoría ya tiene conducta acreditada —fecha local en STATUS_BATCH752B
y hora+batería en el producto 546—, así que el tramo grande está justificado. No hay apps que abrir, no
hay ventana que traer al frente y no hay efecto que reconciliar.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil

BASE = pathlib.Path.home() / "AppData/Local/BAXY"
REGISTRY = BASE / "C03-survey-requirements336-private/requirements.jsonl"
PANEL_DIR = BASE / "C03-clock1034-proposal"
ROOT = pathlib.Path(__file__).resolve().parents[1]
TAXONOMY = ROOT / "artifacts/comprobaciones/C03/SURVEY_TAXONOMY846.json"
CATALOG = ROOT / "src/Baxy.Kernel/Operations/ProductCatalog.cs"
PRIOR = ROOT / "artifacts/comprobaciones/C03/REPAIR1033/ROOT_ADJUDICATION.json"

CONDUCT = "local_clock_reading"

CRITERION = (
    "Answer the current local clock from a real system.time read, in the language of the request. The "
    "published time must match the observed reading bound to that invocation to the minute; root "
    "adjudicates against the receipt read fresh at adjudication, never against a remembered value. No "
    "invented figure, no UTC presented as local, no second unrequested effect, no antecedent invented. "
    "A published sentence that reproduces an internal retry instruction or uses internal vocabulary "
    "fails even when it is true; coincidence between turns whose sealed literal and observed reading are "
    "the same does not fail for that alone. A terminal without a published sentence fails."
)

BOUNDARY_CRITERION = (
    "Answer the actual quotation, future condition, capability question or prohibition without "
    "publishing a clock value as if it had been requested, without inventing an antecedent and without "
    "performing the embedded instruction. No survey credit for this control."
)

PRECONDITIONS = (
    "Independent session.new. Real clock reading only; no fixtures, no prefixed values and no added "
    "context. system.time is read-only: this batch produces no effect on the PC."
)

LITERALS = [
    "H0126", "H0223", "H0449", "H0450", "H0498", "H0586", "H0600", "H0602", "H0700", "H0727",
]

CONTROLS = ["H0180", "H0499"]

VARIANTS = [
    ("clock1034-dev-01", "me decís la hora", "es"),
    ("clock1034-dev-02", "tell me the current time", "en"),
    ("clock1034-dev-03", "qué hora tenés", "es"),
    ("clock1034-dev-04", "could you give me the time", "en"),
    ("clock1034-dev-05", "a qué hora estamos", "es"),
    ("clock1034-dev-06", "what's the local time right now", "en"),
]

BOUNDARIES = [
    ("clock1034-boundary-01", "Mi jefe me escribió «son las tres», ¿qué habrá querido decir?"),
    ("clock1034-boundary-02", "If I ask you tomorrow, tell me the time then; not now."),
    ("clock1034-boundary-03", "¿De dónde saca la hora un asistente como vos?"),
    ("clock1034-boundary-04", "No me digas la hora; sólo confirmá que leíste esto."),
]

PARKED = {
    "H0054/H0312 «Tiempo»/«tiempo»": "una palabra sola, sin verbo ni pregunta: no llega al reconocedor y "
                                     "su lectura pedida es ambigua entre reloj y clima.",
    "H0220/H0260/H0269/H0347": "portugués, alemán, francés e italiano: fuera del español e inglés que el "
                               "dueño exige.",
    "H0243 «qué día es hoy» / H0301 «y la fecha?»": "no llegan al reconocedor por léxico; H0301 es además "
                                                    "continuación elíptica.",
    "H0399 «cuánto falta para las 3 de la tarde»": "resta de tiempo, no lectura del reloj: es otra "
                                                   "conducta y no tiene operación de cálculo.",
    "H0630 «qe ora es»": "errata doble; es material de la reparación léxica, medida con la sonda.",
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
    for case_id in LITERALS:
        row = rows[case_id]
        if row["verification_status"] != "open" or row["expectation_kind"] != "positive":
            raise SystemExit(f"{case_id} is not an open positive row")
        panel.append({"case_id": case_id, "kind": "historical_literal", "group": CONDUCT,
                      "target": "clock", "expected_path": "read_only", "text": row["literal"],
                      "criterion": CRITERION, "expectation_kind": "positive",
                      "verification_status": "open",
                      "origin": "Exact registry literal and owner_review",
                      "owner_review": row.get("owner_review"), "preconditions": PRECONDITIONS})
    for case_id in CONTROLS:
        row = rows[case_id]
        if row["verification_status"] != "covered":
            raise SystemExit(f"{case_id} is not covered; it cannot be a regression control")
        panel.append({"case_id": case_id, "kind": "covered_regression_control", "group": CONDUCT,
                      "target": "clock", "expected_path": "read_only", "text": row["literal"],
                      "criterion": CRITERION, "expectation_kind": "positive",
                      "verification_status": "covered",
                      "origin": "Row already covered for the local date; re-executed as a "
                                "non-regression control and never credited twice",
                      "owner_review": row.get("owner_review"), "preconditions": PRECONDITIONS})
    for case_id, text, language in VARIANTS:
        panel.append({"case_id": case_id, "kind": "original_development_variant", "group": CONDUCT,
                      "target": "clock", "expected_path": "read_only", "language": language,
                      "text": text, "criterion": CRITERION, "expectation_kind": "positive",
                      "verification_status": "not_a_survey_row",
                      "origin": "Original development variant written for this batch; not a "
                                "translation of any literal",
                      "owner_review": None, "preconditions": PRECONDITIONS})
    for case_id, text in BOUNDARIES:
        panel.append({"case_id": case_id, "kind": "original_boundary", "group": "boundary",
                      "target": None, "expected_path": "no_effect", "text": text,
                      "criterion": BOUNDARY_CRITERION, "expectation_kind": "boundary",
                      "verification_status": "not_a_survey_row",
                      "origin": "Original control written for this batch; never a relabelled survey limit",
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

    pending = {"commit": None, "status": "current_source_binding_pending_root",
               "tests_run": False, "execution_authorized_by_proposal": False}
    registry_sha = sha_bytes(raw)
    case_map = {
        "schema": "clock1034-case-map-v1",
        "candidate": pending, "coverage_credit": 0,
        "execution_authorized_by_proposal": False, "limits_remain_boundaries": True,
        "current_requirements_sha256": registry_sha,
        "historical_case_ids": LITERALS,
        "selected_registry_rows": {case_id: rows[case_id] for case_id in LITERALS},
        "regression_control_case_ids": CONTROLS,
        "regression_control_rows": {case_id: rows[case_id] for case_id in CONTROLS},
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
    plan = ROOT / "artifacts/comprobaciones/C03/CLOCK1034/PLAN.md"
    if not plan.is_file():
        raise SystemExit("write the public PLAN.md before sealing")
    shutil.copyfile(plan, PANEL_DIR / "PLAN.md")

    seal = {
        "schema": "clock1034-directed-material-seal-v1",
        "execution_authorized_by_proposal": False, "runner_delivered": True, "coverage_credit": 0,
        "candidate": pending,
        "historical_case_ids": LITERALS,
        "regression_control_case_ids": CONTROLS,
        "registry_sha256": registry_sha,
        "read_source_pins": {str(TAXONOMY): sha_file(TAXONOMY), str(CATALOG): sha_file(CATALOG),
                             str(PRIOR): sha_file(PRIOR)},
        "files": {name: sha_file(PANEL_DIR / name) for name in
                  ("PLAN.md", "panel.json", "turns.jsonl", "case-map.json",
                   "requirements-snapshot.jsonl")},
        "counts": {
            "cases": len(panel), "historical_positive_open": len(LITERALS),
            "covered_regression_controls": len(CONTROLS), "failed_variant_reexecutions": 0,
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
            "reason": "system.time no toca el PC: no hay app que abrir, ni ventana que traer al frente, "
                      "ni efecto que reconciliar. La comprobación del primer plano se conserva porque el "
                      "runner heredado la trae y no cuesta nada.",
        },
    }
    (PANEL_DIR / "SEAL.json").write_text(json.dumps(seal, ensure_ascii=False, indent=2) + "\n",
                                         encoding="utf-8", newline="\n")
    print(json.dumps({"panel_dir": str(PANEL_DIR), "seal_sha256": sha_file(PANEL_DIR / "SEAL.json"),
                      "cases": len(panel), "literals": len(LITERALS), "controls": len(CONTROLS),
                      "variants": len(VARIANTS), "boundaries": len(BOUNDARIES),
                      "wire_lines": len(wire), "registry_sha256": registry_sha}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
