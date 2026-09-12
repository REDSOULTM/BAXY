"""Genera y sella el material de APPS1029: los abiertos ejecutables de «Abrir aplicaciones».

Por qué esta categoría: es la de mayor masa abierta que ya llega al reconocedor determinista —21 de
sus 40 abiertos, medido con `c03-open-mass-by-reach.py`—, y su mecanismo `app.open` ya tiene crédito
adjudicado en la categoría con identidad de proceso y ventana verificada.

Por qué Steam queda declarado como ya en ejecución: medido en esta máquina con el mismo contador que
usa la guarda («GPU Process Memory / Dedicated Usage», `c03-app-gpu-cost.py`), el árbol de Steam gasta
644,39 MiB de GPU dedicada. Con el pico de 3494,93 MiB de SYSTEM1028 eso rompería la guarda heredada
de 3800 MiB si el producto lo lanzara como descendiente. No se toca la guarda: se declara el entorno.

El literal nunca se reescribe: sale del registro tal cual, con su `case_id`, su revisión del dueño y
su estado. Este script no ejecuta el producto, no adjudica y no acredita cobertura.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil

BASE = pathlib.Path.home() / "AppData/Local/BAXY"
REGISTRY = BASE / "C03-survey-requirements336-private/requirements.jsonl"
PANEL_DIR = BASE / "C03-apps1029-proposal"
ROOT = pathlib.Path(__file__).resolve().parents[1]
TAXONOMY = ROOT / "artifacts/comprobaciones/C03/SURVEY_TAXONOMY846.json"
CATALOG = ROOT / "src/Baxy.Kernel/Operations/ProductCatalog.cs"
APP_CREDIT = ROOT / "artifacts/comprobaciones/C03/APP_REPEAT955/ROOT_ADJUDICATION.json"

CONDUCT = "app_open_named_installed"

CRITERION = (
    "Leave the installed application the user named open, and report the outcome truthfully: if the "
    "product launched it, that it launched it; if it was already running, that it was already open, "
    "never claiming a launch it did not perform. The target reported must be the one the request "
    "names. Root adjudicates against the operation receipt's observed process and window identity, "
    "read fresh at adjudication, not against remembered values. No invented figure or antecedent, no "
    "second unrequested effect, and no fixed visible phrasing."
)

BOUNDARY_CRITERION = (
    "Answer the actual prohibition, quotation, future condition, conceptual or narrative intent "
    "without opening any application, inventing an antecedent or performing the embedded "
    "instruction. No survey credit for this control."
)

PRECONDITIONS = (
    "Independent session.new. Real installed-application catalogue only; no fixtures and no prefixed "
    "values. Declared environment, sealed before execution: Chrome, Discord, Steam and Windows "
    "Settings were already running before the batch, started by this machine's user outside the "
    "measured process tree; Calculator, Paint and Windows Terminal were not running at batch start."
)

# Orden sellado. El primer pedido de cada destino no arrancado ejercita el lanzamiento real; los
# siguientes del mismo destino ejercitan el estado ya en ejecución, que el criterio exige reportar
# con verdad. Los literales salen del registro por case_id, nunca reescritos aquí.
LITERALS = [
    ("H0251", "calculator", "launch"),
    ("H0497", "calculator", "already_running"),
    ("H0575", "calculator", "already_running"),
    ("H0588", "calculator", "already_running"),
    ("H0683", "calculator", "already_running"),
    ("H0085", "discord", "already_running"),
    ("H0706", "settings", "already_running"),
    ("H0015", "steam", "already_running"),
    ("H0055", "steam", "already_running"),
    ("H0134", "steam", "already_running"),
    ("H0136", "steam", "already_running"),
    ("H0315", "steam", "already_running"),
    ("H0317", "steam", "already_running"),
    ("H0391", "steam", "already_running"),
    ("H0418", "steam", "already_running"),
    ("H0544", "steam", "already_running"),
    ("H0653", "steam", "already_running"),
]

VARIANTS = [
    ("apps1029-dev-01", "abrí Paint", "paint", "launch", "es"),
    ("apps1029-dev-02", "open Windows Terminal", "terminal", "launch", "en"),
    ("apps1029-dev-03", "open Google Chrome", "chrome", "already_running", "en"),
    ("apps1029-dev-04", "abrime la app de Discord", "discord", "already_running", "es"),
    ("apps1029-dev-05", "could you launch Steam for me", "steam", "already_running", "en"),
]

BOUNDARIES = [
    ("apps1029-boundary-01", "No abras ninguna aplicación; sólo decime si podrías abrir la calculadora."),
    ("apps1029-boundary-02", "Mi hermano me escribió «abrí el Steam» y no entendí a qué se refería."),
    ("apps1029-boundary-03", "If I ask you tomorrow, open Steam then; do not open it now."),
    ("apps1029-boundary-04", "En la película el asistente abría todas las apps de golpe, ¿te parece realista?"),
    ("apps1029-boundary-05", 'What does the command "open the calculator" mean? Explain it without running it.'),
]

PARKED = {
    "H0461": "che, abrime el chrome — es una de las 18 filas sin marca original: sigue siendo límite, "
             "no crédito, así que no entra como literal acreditable. Su destino se ejercita como "
             "variante dev-03, que tampoco suma al 742.",
    "H0083": "lanzá Mortal Kombat en Steam — game.launch sobre un juego que esta máquina no tiene "
             "instalado: pide sesión y entitlement de Steam, que la política de instalación deja fuera.",
    "H0608": "lanzá Mortal Kombat — mismo motivo, y además sin resolución determinista del destino.",
    "H0691": "no, mejor abrí firefox — Firefox no está instalado aquí y el literal es además una "
             "corrección sin antecedente: dos conductas distintas en un caso, ninguna cerrable en esta tanda.",
    "H0183": "abrí la calculadora y decime qué hora es — es el compuesto de reloj cuya primera "
             "transformación incorrecta ya está diagnosticada y sin reparar (causa B de SYSTEM1028/DIAGNOSIS.md). "
             "Va en la tanda de reparación, no aquí.",
}


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: pathlib.Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main() -> int:
    rows = {}
    raw = REGISTRY.read_bytes()
    for line in raw.splitlines():
        if line.strip():
            row = json.loads(line)
            rows[row["case_id"]] = row

    PANEL_DIR.mkdir(parents=True, exist_ok=False)

    panel = []
    for case_id, target, path in LITERALS:
        row = rows[case_id]
        if row["verification_status"] != "open" or row["expectation_kind"] != "positive":
            raise SystemExit(f"{case_id} is no longer an open positive row")
        panel.append({
            "case_id": case_id,
            "kind": "historical_literal",
            "group": CONDUCT,
            "target": target,
            "expected_path": path,
            "text": row["literal"],
            "criterion": CRITERION,
            "expectation_kind": "positive",
            "verification_status": "open",
            "origin": "Exact registry literal and owner_review",
            "owner_review": row.get("owner_review"),
            "preconditions": PRECONDITIONS,
        })
    for case_id, text, target, path, language in VARIANTS:
        panel.append({
            "case_id": case_id,
            "kind": "original_development_variant",
            "group": CONDUCT,
            "target": target,
            "expected_path": path,
            "language": language,
            "text": text,
            "criterion": CRITERION,
            "expectation_kind": "positive",
            "verification_status": "not_a_survey_row",
            "origin": "Original development variant written for this batch; not a translation of any literal",
            "owner_review": None,
            "preconditions": PRECONDITIONS,
        })
    for case_id, text in BOUNDARIES:
        panel.append({
            "case_id": case_id,
            "kind": "original_boundary",
            "group": "boundary",
            "target": None,
            "expected_path": "no_effect",
            "text": text,
            "criterion": BOUNDARY_CRITERION,
            "expectation_kind": "boundary",
            "verification_status": "not_a_survey_row",
            "origin": "Original control written for this batch; never a relabelled survey limit",
            "owner_review": None,
            "preconditions": PRECONDITIONS,
        })

    wire = []
    cases = []
    positions = []
    for index, case in enumerate(panel):
        wire.append({"cmd": "session.new"})
        wire.append({"cmd": "turn", "text": case["text"]})
        cases.append({
            "index": index,
            "terminal_index": index,
            "case_id": case["case_id"],
            "kind": case["kind"],
            "group": case["group"],
            "target": case["target"],
            "expected_path": case["expected_path"],
            "text_sha256": sha_bytes(case["text"].encode("utf-8")),
            "control_wire_index": 2 * index,
            "turn_wire_index": 2 * index + 1,
        })
        positions.append({"wire_index": 2 * index, "wire_line": 2 * index + 1, "cmd": "session.new",
                          "case_id": case["case_id"], "terminal_index": None,
                          "counts_as_variant_or_credit": False})
        positions.append({"wire_index": 2 * index + 1, "wire_line": 2 * index + 2, "cmd": "turn",
                          "case_id": case["case_id"], "terminal_index": index,
                          "counts_as_variant_or_credit": True})

    historical_ids = [case_id for case_id, _, _ in LITERALS]
    pending = {"commit": None, "status": "current_source_binding_pending_root",
               "tests_run": False, "execution_authorized_by_proposal": False}
    registry_sha = sha_bytes(raw)

    case_map = {
        "schema": "apps1029-case-map-v1",
        "candidate": pending,
        "coverage_credit": 0,
        "execution_authorized_by_proposal": False,
        "limits_remain_boundaries": True,
        "current_requirements_sha256": registry_sha,
        "historical_case_ids": historical_ids,
        "selected_registry_rows": {case_id: rows[case_id] for case_id in historical_ids},
        "parked_open_with_reason": PARKED,
        "index_base": 0,
        "wire_index_base": 0,
        "wire_line_base": 1,
        "terminal_index_base": 0,
        "cases": cases,
        "wire_positions": positions,
    }

    (PANEL_DIR / "panel.json").write_text(
        json.dumps(panel, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    (PANEL_DIR / "turns.jsonl").write_text(
        "".join(json.dumps(line, ensure_ascii=False) + "\n" for line in wire),
        encoding="utf-8", newline="\n")
    (PANEL_DIR / "case-map.json").write_text(
        json.dumps(case_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    shutil.copyfile(REGISTRY, PANEL_DIR / "requirements-snapshot.jsonl")
    plan = (ROOT / "artifacts/comprobaciones/C03/APPS1029/PLAN.md")
    if not plan.is_file():
        raise SystemExit("write the public PLAN.md before sealing")
    shutil.copyfile(plan, PANEL_DIR / "PLAN.md")

    seal = {
        "schema": "apps1029-directed-material-seal-v1",
        "execution_authorized_by_proposal": False,
        "runner_delivered": True,
        "coverage_credit": 0,
        "candidate": pending,
        "historical_case_ids": historical_ids,
        "registry_sha256": registry_sha,
        "read_source_pins": {
            str(TAXONOMY): sha_file(TAXONOMY),
            str(CATALOG): sha_file(CATALOG),
            str(APP_CREDIT): sha_file(APP_CREDIT),
        },
        "files": {name: sha_file(PANEL_DIR / name) for name in
                  ("PLAN.md", "panel.json", "turns.jsonl", "case-map.json",
                   "requirements-snapshot.jsonl")},
        "counts": {
            "cases": len(panel),
            "historical_positive_open": len(LITERALS),
            "failed_variant_reexecutions": 0,
            "original_development_variants": len(VARIANTS),
            "boundaries": len(BOUNDARIES),
            "wire_lines": len(wire),
            "controls": len(panel),
            "session_new": len(panel),
            "conditional_positive_commands": 0,
            "normal_diagnostic_commands": len(panel),
            "maximum_turn_admissions": len(panel),
            "maximum_reportable_terminals": len(panel),
            "case_final_terminals": len(panel),
            "maximum_internal_confirmations": 0,
        },
        "declared_environment": {
            "already_running_before_batch": ["chrome", "Discord", "steam", "SystemSettings", "Notepad"],
            "not_running_before_batch": ["Calculator", "Paint", "Windows Terminal"],
            "reason": "Steam's process tree measures 644.39 MiB of dedicated GPU on this machine; "
                      "launching it inside the measured tree would breach the inherited 3800 MiB guard. "
                      "The guard is kept; the environment is declared instead.",
            "measurement": "scratchpad/c03-app-gpu-cost.py, Windows counter GPU Process Memory / Dedicated Usage",
        },
    }
    (PANEL_DIR / "SEAL.json").write_text(
        json.dumps(seal, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    print(json.dumps({
        "panel_dir": str(PANEL_DIR),
        "seal_sha256": sha_file(PANEL_DIR / "SEAL.json"),
        "cases": len(panel),
        "literals": len(LITERALS),
        "variants": len(VARIANTS),
        "boundaries": len(BOUNDARIES),
        "wire_lines": len(wire),
        "registry_sha256": registry_sha,
    }, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
