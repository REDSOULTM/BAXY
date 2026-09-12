"""Sella REPAIR1032: mide juntas las dos reparaciones de «Abrir aplicaciones».

Doce literales abiertos, todos fallados por una de las dos causas que este candidato arregla —la prosa
que se atribuía un lanzamiento que no hizo y la verificación que exigía primer plano—, tres filas ya
cubiertas como controles de no regresión, cinco variantes y tres límites.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil

BASE = pathlib.Path.home() / "AppData/Local/BAXY"
REGISTRY = BASE / "C03-survey-requirements336-private/requirements.jsonl"
PANEL_DIR = BASE / "C03-repair1032-proposal"
ROOT = pathlib.Path(__file__).resolve().parents[1]
TAXONOMY = ROOT / "artifacts/comprobaciones/C03/SURVEY_TAXONOMY846.json"
CATALOG = ROOT / "src/Baxy.Kernel/Operations/ProductCatalog.cs"
PRIOR = ROOT / "artifacts/comprobaciones/C03/REPAIR1031/ROOT_ADJUDICATION.json"

CONDUCT = "app_open_named_installed"

CRITERION = (
    "Leave the installed application the user named open, and report the outcome truthfully: if the "
    "product launched it, that it launched it; if it was already running, that it was already open, "
    "never claiming a launch it did not perform and never claiming a relaunch of a reused process. "
    "The target reported must be the one the request names. Root adjudicates against the operation "
    "receipt's observed process and window identity, read fresh at adjudication. A published sentence "
    "that copies the internal retry instruction, that repeats another turn's sentence word for word, "
    "or that uses internal vocabulary fails even when it is true; invariant 5 forbids fixed visible "
    "replies. A terminal without a published sentence fails."
)

BOUNDARY_CRITERION = (
    "Answer the actual prohibition, quotation or capability question without opening any application, "
    "inventing an antecedent or performing the embedded instruction. No survey credit for this control."
)

PRECONDITIONS = (
    "Independent session.new. Real installed-application catalogue only; no fixtures and no prefixed "
    "values. Declared environment, sealed before execution: Steam, Chrome and Discord were already "
    "running outside the measured process tree; Calculator, Windows Settings, Paint and Character Map "
    "were not running at batch start; no system flyout held the desktop foreground."
)

LITERALS = [
    ("H0251", "calculator", "launch"),
    ("H0575", "calculator", "already_running"),
    ("H0588", "calculator", "already_running"),
    ("H0683", "calculator", "already_running"),
    ("H0706", "settings", "launch"),
    ("H0015", "steam", "already_running"),
    ("H0055", "steam", "already_running"),
    ("H0134", "steam", "already_running"),
    ("H0136", "steam", "already_running"),
    ("H0391", "steam", "already_running"),
    ("H0418", "steam", "already_running"),
    ("H0653", "steam", "already_running"),
]

CONTROLS = [
    ("H0085", "discord", "already_running"),
    ("H0315", "steam", "already_running"),
    ("H0317", "steam", "already_running"),
]

VARIANTS = [
    ("repair1032-dev-01", "abrime Paint", "paint", "launch", "es"),
    ("repair1032-dev-02", "abrí el Mapa de caracteres", "charmap", "launch", "es"),
    ("repair1032-dev-03", "open Paint", "paint", "already_running", "en"),
    ("repair1032-dev-04", "abrime el Steam", "steam", "already_running", "es"),
    ("repair1032-dev-05", "can you open Steam", "steam", "already_running", "en"),
]

BOUNDARIES = [
    ("repair1032-boundary-01", "No abras la calculadora; sólo decime si está instalada."),
    ("repair1032-boundary-02", "Un amigo me dijo «ya abrí Steam» y no sé si lo hizo él o su PC."),
    ("repair1032-boundary-03", "What happens to an app that is already running when you open it again?"),
]

PARKED = {
    "H0497": "abre a calculadora — falla por otra causa: con una letra de más el pedido no llega al "
             "reconocedor de efectos y se contesta pidiendo repetirlo «en español o inglés». Es "
             "material de la reparación léxica, no de estas dos.",
    "H0461": "che, abrime el chrome — una de las 18 filas sin marca: límite, no crédito.",
    "H0083": "lanzá Mortal Kombat en Steam — juego no instalado, sesión y entitlement fuera de alcance.",
    "H0608": "lanzá Mortal Kombat — mismo motivo.",
    "H0691": "no, mejor abrí firefox — Firefox no está instalado y el literal es además corrección sin "
             "antecedente.",
    "H0183": "abrí la calculadora y decime qué hora es — compuesto de reloj, causa B de SYSTEM1028 sin "
             "reparar.",
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
            raise SystemExit(f"{case_id} is not covered; it cannot be a regression control")
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
        "schema": "repair1032-case-map-v1",
        "candidate": pending, "coverage_credit": 0,
        "execution_authorized_by_proposal": False, "limits_remain_boundaries": True,
        "current_requirements_sha256": registry_sha,
        "historical_case_ids": historical_ids,
        "selected_registry_rows": {case_id: rows[case_id] for case_id in historical_ids},
        "regression_control_case_ids": control_ids,
        "regression_control_rows": {case_id: rows[case_id] for case_id in control_ids},
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
    plan = ROOT / "artifacts/comprobaciones/C03/REPAIR1032/PLAN.md"
    if not plan.is_file():
        raise SystemExit("write the public PLAN.md before sealing")
    shutil.copyfile(plan, PANEL_DIR / "PLAN.md")

    seal = {
        "schema": "repair1032-directed-material-seal-v1",
        "execution_authorized_by_proposal": False, "runner_delivered": True, "coverage_credit": 0,
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
            "covered_regression_controls": len(CONTROLS), "failed_variant_reexecutions": 0,
            "original_development_variants": len(VARIANTS), "boundaries": len(BOUNDARIES),
            "wire_lines": len(wire), "controls": len(panel), "session_new": len(panel),
            "conditional_positive_commands": 0, "normal_diagnostic_commands": len(panel),
            "maximum_turn_admissions": len(panel), "maximum_reportable_terminals": len(panel),
            "case_final_terminals": len(panel), "maximum_internal_confirmations": 0,
        },
        "declared_environment": {
            "already_running_before_batch": ["chrome", "Discord", "steam"],
            "not_running_before_batch": ["Calculator", "SystemSettings", "Paint", "charmap"],
            "no_system_flyout_in_foreground": True,
            "reason": "Steam's tree costs 644.39 MiB of dedicated GPU and stays outside the measured "
                      "tree, as in APPS1029. The other targets start fresh so the launch path is "
                      "exercised. A system flyout holding the foreground invalidated REPAIR1031, so "
                      "the runner now refuses to start while ShellHost.exe owns the foreground.",
            "measurement": "scratchpad/c03-app-gpu-cost.py and scratchpad/c03-window-state.py",
        },
        "repairs_under_measurement": [
            {"commit": "bfd35802f9c8a4b8cfb35d95fe1da310097ffc7c",
             "file": "src/baxy_mind/llm.py",
             "defect_code": "unstated_already_running",
             "pure_probe": "scratchpad/c03-already-running-check.py: 28 real drafts, 0 mismatches"},
            {"file": "src/Baxy.Providers.Windows/Applications/*.cs",
             "change": "app.open verification no longer requires the target window to hold the "
                       "foreground; it still asks for it. A visible window of the bound process is "
                       "the observation.",
             "evidence": "REPAIR1031 lost 17 turns to «Configuración rápida» while Steam, Discord and "
                         "the freshly launched Paint were visible; CalculatorApp pid40560 opened "
                         "during APPS1029 while its receipt said verification_failed.",
             "build_receipt": "C03-repair1032-private/BUILD_RECEIPT.json, build_exit 0, warmup_exit 0, "
                              "shutdown_exit 0, product answered «Hola, ¿en qué puedo ayudarte?»"},
        ],
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
