"""Sella REPAIR1031: mide en el producto la reparación del hecho «ya estaba en ejecución».

Subconjunto exacto, no panel nuevo: los siete literales de Steam que APPS1029 falló sólo porque la
prosa se atribuyó un lanzamiento que no hizo, más los tres que en esa misma tanda cumplieron, que
entran como **controles de no regresión** y no vuelven a acreditar nada porque ya están cubiertos, más
un par de variantes de lanzamiento real y un par de variantes de destino ya en ejecución, más tres
límites. La sonda pura ya dejó verde el cambio sobre los catorce borradores reales de 1029; esta tanda
comprueba lo que la sonda no puede: que el producto publique una frase útil tras el rechazo.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil

BASE = pathlib.Path.home() / "AppData/Local/BAXY"
REGISTRY = BASE / "C03-survey-requirements336-private/requirements.jsonl"
PANEL_DIR = BASE / "C03-repair1031-proposal"
ROOT = pathlib.Path(__file__).resolve().parents[1]
TAXONOMY = ROOT / "artifacts/comprobaciones/C03/SURVEY_TAXONOMY846.json"
CATALOG = ROOT / "src/Baxy.Kernel/Operations/ProductCatalog.cs"
PRIOR = ROOT / "artifacts/comprobaciones/C03/REPAIR1030/ROOT_ADJUDICATION.json"

CONDUCT = "app_open_named_installed"

CRITERION = (
    "Leave the installed application the user named open, and report the outcome truthfully: if the "
    "product launched it, that it launched it; if it was already running, that it was already open, "
    "never claiming a launch it did not perform. The target reported must be the one the request "
    "names. Root adjudicates against the operation receipt's observed process and window identity, "
    "read fresh at adjudication. A rejected draft is not an excuse for silence: a terminal without a "
    "published sentence fails."
)

BOUNDARY_CRITERION = (
    "Answer the actual prohibition, quotation or capability question without opening any application, "
    "inventing an antecedent or performing the embedded instruction. No survey credit for this control."
)

PRECONDITIONS = (
    "Independent session.new. Real installed-application catalogue only; no fixtures and no prefixed "
    "values. Declared environment, sealed before execution: Steam, Chrome and Discord were already "
    "running before the batch, started outside the measured process tree; Paint was not running at "
    "batch start."
)

LITERALS = [
    ("H0015", "steam", "already_running"),
    ("H0055", "steam", "already_running"),
    ("H0134", "steam", "already_running"),
    ("H0136", "steam", "already_running"),
    ("H0391", "steam", "already_running"),
    ("H0418", "steam", "already_running"),
    ("H0653", "steam", "already_running"),
]

# Filas ya cubiertas en APPS1029. Entran como control: si la reparación las rompiera, se vería aquí.
CONTROLS = [
    ("H0085", "discord", "already_running"),
    ("H0315", "steam", "already_running"),
    ("H0317", "steam", "already_running"),
]

VARIANTS = [
    ("repair1031-dev-01", "abrime Paint", "paint", "launch", "es"),
    ("repair1031-dev-02", "open Paint", "paint", "already_running", "en"),
    ("repair1031-dev-03", "abrime el Steam", "steam", "already_running", "es"),
    ("repair1031-dev-04", "can you open Steam", "steam", "already_running", "en"),
]

BOUNDARIES = [
    ("repair1031-boundary-01", "No abras Steam; sólo decime si está instalado."),
    ("repair1031-boundary-02", "Un amigo me dijo «ya abrí Steam» y no sé si lo hizo él o su PC."),
    ("repair1031-boundary-03", "Could you tell me what happens if an app is already running when you open it?"),
]


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
    for case_id, target, path in LITERALS:
        row = rows[case_id]
        if row["verification_status"] != "open" or row["expectation_kind"] != "positive":
            raise SystemExit(f"{case_id} is not an open positive row")
        panel.append({"case_id": case_id, "kind": "historical_literal", "group": CONDUCT,
                      "target": target, "expected_path": path, "text": row["literal"],
                      "criterion": CRITERION, "expectation_kind": "positive",
                      "verification_status": "open",
                      "origin": "Exact registry literal and owner_review",
                      "owner_review": row.get("owner_review"), "preconditions": PRECONDITIONS})
    for case_id, target, path in CONTROLS:
        row = rows[case_id]
        if row["verification_status"] != "covered":
            raise SystemExit(f"{case_id} is not a covered row; it cannot be a regression control")
        panel.append({"case_id": case_id, "kind": "covered_regression_control", "group": CONDUCT,
                      "target": target, "expected_path": path, "text": row["literal"],
                      "criterion": CRITERION, "expectation_kind": "positive",
                      "verification_status": "covered",
                      "origin": "Row already covered in APPS1029; re-executed as a non-regression "
                                "control and never credited twice",
                      "owner_review": row.get("owner_review"), "preconditions": PRECONDITIONS})
    for case_id, text, target, path, language in VARIANTS:
        panel.append({"case_id": case_id, "kind": "original_development_variant", "group": CONDUCT,
                      "target": target, "expected_path": path, "language": language, "text": text,
                      "criterion": CRITERION, "expectation_kind": "positive",
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

    historical_ids = [case_id for case_id, _, _ in LITERALS]
    control_ids = [case_id for case_id, _, _ in CONTROLS]
    pending = {"commit": None, "status": "current_source_binding_pending_root",
               "tests_run": False, "execution_authorized_by_proposal": False}
    registry_sha = sha_bytes(raw)

    case_map = {
        "schema": "repair1031-case-map-v1",
        "candidate": pending,
        "coverage_credit": 0,
        "execution_authorized_by_proposal": False,
        "limits_remain_boundaries": True,
        "current_requirements_sha256": registry_sha,
        "historical_case_ids": historical_ids,
        "selected_registry_rows": {case_id: rows[case_id] for case_id in historical_ids},
        "regression_control_case_ids": control_ids,
        "regression_control_rows": {case_id: rows[case_id] for case_id in control_ids},
        "regression_controls_never_credit_twice": True,
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
    plan = ROOT / "artifacts/comprobaciones/C03/REPAIR1031/PLAN.md"
    if not plan.is_file():
        raise SystemExit("write the public PLAN.md before sealing")
    shutil.copyfile(plan, PANEL_DIR / "PLAN.md")

    seal = {
        "schema": "repair1031-directed-material-seal-v1",
        "execution_authorized_by_proposal": False,
        "runner_delivered": True,
        "coverage_credit": 0,
        "candidate": pending,
        "historical_case_ids": historical_ids,
        "regression_control_case_ids": control_ids,
        "registry_sha256": registry_sha,
        "read_source_pins": {str(TAXONOMY): sha_file(TAXONOMY), str(CATALOG): sha_file(CATALOG),
                             str(PRIOR): sha_file(PRIOR)},
        "files": {name: sha_file(PANEL_DIR / name) for name in
                  ("PLAN.md", "panel.json", "turns.jsonl", "case-map.json",
                   "requirements-snapshot.jsonl")},
        "counts": {
            "cases": len(panel), "historical_positive_open": len(LITERALS),
            "covered_regression_controls": len(CONTROLS),
            "failed_variant_reexecutions": 0,
            "original_development_variants": len(VARIANTS), "boundaries": len(BOUNDARIES),
            "wire_lines": len(wire), "controls": len(panel), "session_new": len(panel),
            "conditional_positive_commands": 0, "normal_diagnostic_commands": len(panel),
            "maximum_turn_admissions": len(panel), "maximum_reportable_terminals": len(panel),
            "case_final_terminals": len(panel), "maximum_internal_confirmations": 0,
        },
        "declared_environment": {
            "already_running_before_batch": ["chrome", "Discord", "steam"],
            "not_running_before_batch": ["Paint"],
            "reason": "Steam's process tree measures 644.39 MiB of dedicated GPU here; inside the "
                      "measured tree it would breach the inherited 3800 MiB guard. The guard is kept "
                      "and the environment declared, as in APPS1029.",
            "measurement": "scratchpad/c03-app-gpu-cost.py",
        },
        "repair_under_measurement": {
            "commit": "bfd35802f9c8a4b8cfb35d95fe1da310097ffc7c",
            "file": "src/baxy_mind/llm.py",
            "defect_code": "unstated_already_running",
            "change": "The retry instruction is a short imperative instead of a publishable "
                      "declarative sentence, and an asserted relaunch over a reused process is "
                      "rejected too.",
            "pure_probe": "scratchpad/c03-already-running-check.py: 28 real drafts across APPS1029 "
                          "and REPAIR1031, 0 mismatches",
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
