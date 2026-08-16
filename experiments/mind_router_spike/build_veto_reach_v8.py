"""Construct and preregister the fresh veto-reach V8 text population."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Iterable

REPO = Path(__file__).resolve().parents[2]
for import_root in (REPO, REPO / "src"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from baxy_mind.effect_intent import _fold, resolve_explicit_effects
from scripts.baxy_runtime_config import DEFAULT_RUNTIME_MANIFEST, file_sha256
from scripts.build_generalization_surface_holdout import catalog_identity
from scripts.measure_mind_budget import (
    current_core_capabilities,
    discover_core,
)
from scripts.wake_validation_program_tree import fingerprint_program_tree

from experiments.mind_router_spike import score_veto_reach_v8 as scoring


CORPUS = REPO / "artifacts/holdout/veto_reach_v8.corpus.jsonl"
PREREGISTRATION = REPO / "artifacts/holdout/veto_reach_v8.preregistration.json"
OUTPUT = REPO / "artifacts/holdout/veto_reach_v8.json"
TELEMETRY = REPO / "artifacts/holdout/veto_reach_v8.telemetry.jsonl"
CONSUMED = REPO / "artifacts/holdout/veto_reach_v8.consumed.json"
TURN_AUDIT = REPO / "artifacts/holdout/veto_reach_v8.turn-audit.jsonl"
RAW_REPLY_AUDIT = REPO / "artifacts/holdout/veto_reach_v8.raw-replies.jsonl"
RUNNER = REPO / "experiments/mind_router_spike/run_veto_reach_v8.py"
SCORER = REPO / "experiments/mind_router_spike/score_veto_reach_v8.py"
ALIASES = REPO / "src/baxy_mind/data/catalog_operation_aliases.v1.json"
PROGRAM_FILES = (
    Path(__file__).resolve(),
    RUNNER,
    SCORER,
    REPO / "src/baxy_mind/__main__.py",
    REPO / "src/baxy_mind/llm.py",
    REPO / "src/baxy_mind/family_classifier.py",
    ALIASES,
    REPO / "tests/test_veto_reach_v8.py",
)
TREE_ROOTS = (
    REPO / "src/baxy_mind",
    REPO / "experiments/mind_router_spike",
    REPO / "scripts",
    REPO / "tests",
)
PRIOR_JSONL = (
    REPO / "artifacts/holdout/catalog_surface_current_tree_r2.jsonl",
    REPO / "artifacts/holdout/generalization_product_current_tree_r28.jsonl",
    REPO / "tests/data/turn_evidence_runtime.v1.jsonl",
    REPO / "tests/data/turn_evidence_public_holdout.v1.jsonl",
)
PRIOR_BUILDERS = tuple(
    REPO / f"experiments/mind_router_spike/build_veto_reach_v{version}.py"
    for version in range(1, 8)
)


def _case(
    case_id: str,
    pair_id: str,
    language: str,
    role: str,
    text: str,
    expected_operation: str | None = None,
    *,
    legitimate_third_party_assertion: bool = False,
    legitimate_numeric_assertion: bool = False,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "pair_id": pair_id,
        "language": language,
        "role": role,
        "text": text,
        "expected_operation": expected_operation,
        "deterministic_alias_resolution": False,
        "legitimate_third_party_assertion": legitimate_third_party_assertion,
        "legitimate_numeric_assertion": legitimate_numeric_assertion,
    }


CASES: tuple[dict[str, Any], ...] = (
    _case("v8-srv-01-es", "served-time-of-day", "es", "served", "Descubre en qué parte del día cree estar este equipo.", "system.time"),
    _case("v8-srv-01-en", "served-time-of-day", "en", "served", "Find out which part of the day this machine thinks it is in.", "system.time"),
    _case("v8-srv-01-mix", "served-time-of-day", "spanglish", "served", "Descubre which part of the day cree estar este equipo.", "system.time"),
    _case("v8-srv-02-es", "served-running-work", "es", "served", "Enséñame qué trabajos siguen despiertos dentro del equipo.", "system.process.list"),
    _case("v8-srv-02-en", "served-running-work", "en", "served", "Which pieces of work refuse to sleep inside this box?", "system.process.list"),
    _case("v8-srv-02-mix", "served-running-work", "spanglish", "served", "Enséñame which jobs siguen awake dentro del equipo.", "system.process.list"),
    _case("v8-srv-03-es", "served-machine-health", "es", "served", "Cuéntame cómo anda de salud este aparato ahora.", "system.status"),
    _case("v8-srv-03-en", "served-machine-health", "en", "served", "Tell me how healthy this device is doing right now.", "system.status"),
    _case("v8-srv-03-mix", "served-machine-health", "spanglish", "served", "Cuéntame how healthy anda este aparato right now.", "system.status"),
    _case("v8-srv-04-es", "served-screen-copy", "es", "served", "Guarda una copia de lo que tengo delante en el monitor.", "capture.screenshot"),
    _case("v8-srv-04-en", "served-screen-copy", "en", "served", "Keep a copy of what is in front of me on the monitor.", "capture.screenshot"),
    _case("v8-srv-04-mix", "served-screen-copy", "spanglish", "served", "Guarda a copy de lo que tengo delante on the monitor.", "capture.screenshot"),
    _case("v8-out-01-es", "outside-tailor", "es", "outside_catalogue", "Cose el botón suelto del abrigo antes de salir."),
    _case("v8-out-01-en", "outside-tailor", "en", "outside_catalogue", "Sew the loose button on the coat before we leave."),
    _case("v8-out-01-mix", "outside-tailor", "spanglish", "outside_catalogue", "Cose the loose button del abrigo before we leave."),
    _case("v8-out-02-es", "outside-kettle", "es", "outside_catalogue", "Descalcifica la tetera de la cocina esta tarde."),
    _case("v8-out-02-en", "outside-kettle", "en", "outside_catalogue", "Descale the kitchen kettle this afternoon."),
    _case("v8-out-02-mix", "outside-kettle", "spanglish", "outside_catalogue", "Descalcifica the kitchen kettle esta tarde."),
    _case("v8-out-03-es", "outside-bicycle", "es", "outside_catalogue", "Infla la rueda trasera de la bicicleta hasta que quede firme."),
    _case("v8-out-03-en", "outside-bicycle", "en", "outside_catalogue", "Pump up the bicycle's rear tire until it feels firm."),
    _case("v8-out-03-mix", "outside-bicycle", "spanglish", "outside_catalogue", "Infla the rear tire de la bicicleta until it feels firm."),
    _case("v8-know-01-es", "knowledge-third-party-laptop", "es", "knowledge_social_numeric", "Ana dice que su portátil tiene 16 GB de memoria; explícale si eso basta para estudiar.", legitimate_third_party_assertion=True, legitimate_numeric_assertion=True),
    _case("v8-know-01-en", "knowledge-third-party-laptop", "en", "knowledge_social_numeric", "Ana says her laptop has 16 GB of memory; explain whether that is enough for school.", legitimate_third_party_assertion=True, legitimate_numeric_assertion=True),
    _case("v8-know-01-mix", "knowledge-third-party-laptop", "spanglish", "knowledge_social_numeric", "Ana dice her laptop has 16 GB de memoria; explain si basta para estudiar.", legitimate_third_party_assertion=True, legitimate_numeric_assertion=True),
    _case("v8-know-02-es", "knowledge-third-party-train", "es", "knowledge_social_numeric", "El tren de Luis sale a las 7:40; dile cuánto falta si ahora son las 7:10.", legitimate_third_party_assertion=True, legitimate_numeric_assertion=True),
    _case("v8-know-02-en", "knowledge-third-party-train", "en", "knowledge_social_numeric", "Luis's train leaves at 7:40; tell him how long remains if it is now 7:10.", legitimate_third_party_assertion=True, legitimate_numeric_assertion=True),
    _case("v8-know-02-mix", "knowledge-third-party-train", "spanglish", "knowledge_social_numeric", "El train de Luis leaves at 7:40; dile how long falta si son 7:10.", legitimate_third_party_assertion=True, legitimate_numeric_assertion=True),
    _case("v8-know-03-es", "knowledge-generic-battery", "es", "knowledge_social_numeric", "Una batería de móvil suele conservar cerca del 80% tras dos años; resume por qué.", legitimate_numeric_assertion=True),
    _case("v8-know-03-en", "knowledge-generic-battery", "en", "knowledge_social_numeric", "A phone battery usually keeps about 80% after two years; summarize why.", legitimate_numeric_assertion=True),
    _case("v8-know-03-mix", "knowledge-generic-battery", "spanglish", "knowledge_social_numeric", "Una phone battery suele conservar about 80% after dos años; resume por qué.", legitimate_numeric_assertion=True),
    _case("v8-mach-01-es", "machine-inner-name", "es", "machine_identity_state_perception", "Averigua qué nombre interno lleva este cacharro.", "system.identity"),
    _case("v8-mach-01-en", "machine-inner-name", "en", "machine_identity_state_perception", "Find out which internal name this contraption carries.", "system.identity"),
    _case("v8-mach-01-mix", "machine-inner-name", "spanglish", "machine_identity_state_perception", "Averigua which internal name lleva este cacharro.", "system.identity"),
    _case("v8-mach-02-es", "machine-current-time", "es", "machine_identity_state_perception", "Consulta qué hora señala este aparato en este instante.", "system.time"),
    _case("v8-mach-02-en", "machine-current-time", "en", "machine_identity_state_perception", "Check what hour this device indicates at this instant.", "system.time"),
    _case("v8-mach-02-mix", "machine-current-time", "spanglish", "machine_identity_state_perception", "Consulta what hour señala este aparato right this instant.", "system.time"),
    _case("v8-mach-03-es", "machine-current-view", "es", "machine_identity_state_perception", "Mira y conserva lo que ocupa ahora mismo la superficie visual.", "capture.screenshot"),
    _case("v8-mach-03-en", "machine-current-view", "en", "machine_identity_state_perception", "Look and preserve what currently occupies the visual surface.", "capture.screenshot"),
    _case("v8-mach-03-mix", "machine-current-view", "spanglish", "machine_identity_state_perception", "Mira and preserve lo que currently ocupa la visual surface.", "capture.screenshot"),
    _case("v8-ctl-01-es", "everyday-neighbor", "es", "everyday_control", "Mi vecina adoptó dos gatos ayer; ayúdame a felicitarla."),
    _case("v8-ctl-01-en", "everyday-neighbor", "en", "everyday_control", "My neighbor adopted two cats yesterday; help me congratulate her."),
    _case("v8-ctl-01-mix", "everyday-neighbor", "spanglish", "everyday_control", "Mi neighbor adoptó two cats ayer; help me felicitarla."),
)


def _normalized_surface(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value.casefold())
    plain = "".join(character for character in folded if not unicodedata.combining(character))
    return " ".join(re.findall(r"\w+", plain, re.UNICODE))


def build_population_rows() -> list[dict[str, Any]]:
    return [dict(row) for row in CASES]


def _literal_assignment(path: Path, name: str) -> Iterable[tuple[Any, ...]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if any(isinstance(target, ast.Name) and target.id == name for target in targets):
            return ast.literal_eval(node.value)
    return ()


def _jsonl_surfaces(path: Path) -> set[str]:
    surfaces: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        text = row.get("text") or row.get("request_text")
        if isinstance(text, str):
            surfaces.add(_normalized_surface(text))
    return surfaces


def prior_surface_sets() -> dict[str, set[str]]:
    sources = {
        path.relative_to(REPO).as_posix(): _jsonl_surfaces(path)
        for path in PRIOR_JSONL
    }
    for path in PRIOR_BUILDERS:
        values: set[str] = set()
        for assignment in ("CATALOGUE_CONTROLS", "REQUESTS", "CONTROLS"):
            for _case_id, _language, text in _literal_assignment(path, assignment):
                values.add(_normalized_surface(str(text)))
        sources[path.relative_to(REPO).as_posix()] = values
    return sources


def find_reused_surfaces(
    rows: list[dict[str, Any]],
) -> dict[str, list[str]]:
    current = {_normalized_surface(str(row["text"])) for row in rows}
    return {
        source: sorted(current & prior)
        for source, prior in prior_surface_sets().items()
        if current & prior
    }


def _catalogue_operations() -> list[str]:
    payload = json.loads(ALIASES.read_text(encoding="utf-8"))
    return sorted({str(op) for row in payload["aliases"] for op in row["operations"]})


def validate_population() -> None:
    rows = build_population_rows()
    if len(rows) != 42 or len({str(row["case_id"]) for row in rows}) != 42:
        raise RuntimeError("veto-reach V8 population size or identity changed")
    if len({_normalized_surface(str(row["text"])) for row in rows}) != len(rows):
        raise RuntimeError("veto-reach V8 contains duplicate surfaces")
    pairs: dict[str, set[str]] = {}
    for row in rows:
        pairs.setdefault(str(row["pair_id"]), set()).add(str(row["language"]))
    if any(languages != {"es", "en", "spanglish"} for languages in pairs.values()):
        raise RuntimeError("veto-reach V8 language pairs changed")
    expected_roles = {
        "served": 12,
        "outside_catalogue": 9,
        "knowledge_social_numeric": 9,
        "machine_identity_state_perception": 9,
        "everyday_control": 3,
    }
    counts = {
        role: sum(row["role"] == role for row in rows) for role in expected_roles
    }
    if counts != expected_roles:
        raise RuntimeError(f"veto-reach V8 role balance changed: {counts}")
    reused = find_reused_surfaces(rows)
    if reused:
        raise RuntimeError(f"veto-reach V8 reuses consumed surfaces: {reused}")
    available = _catalogue_operations()
    for row in rows:
        expected = row["expected_operation"]
        if expected is None:
            continue
        if expected not in available:
            raise RuntimeError(f"veto-reach V8 operation absent: {row['case_id']}")
        resolved = resolve_explicit_effects(_fold(str(row["text"])), available)
        if resolved is not None:
            raise RuntimeError(
                f"veto-reach V8 uses deterministic alias: {row['case_id']}"
            )


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def population_contract_sha256(rows: list[dict[str, Any]] | None = None) -> str:
    return _canonical_sha256(build_population_rows() if rows is None else rows)


def _program_hashes() -> dict[str, str]:
    return {
        path.relative_to(REPO).as_posix(): file_sha256(path)
        for path in PROGRAM_FILES
    }


def collect_identities() -> dict[str, Any]:
    runtime_manifest = json.loads(DEFAULT_RUNTIME_MANIFEST.read_text(encoding="utf-8"))
    capabilities = current_core_capabilities(discover_core(None))
    catalog_sha256, catalog_operations = catalog_identity(capabilities)
    tree = fingerprint_program_tree(
        repository_root=REPO,
        source_roots=TREE_ROOTS,
    )
    program_files = _program_hashes()
    core = discover_core(None)
    return {
        "program_sha256": _canonical_sha256(program_files),
        "program_files": program_files,
        "model_sha256": str(runtime_manifest["gguf_sha256"]),
        "catalog_sha256": catalog_sha256,
        "catalog_operations": catalog_operations,
        "tree_sha256": tree["sha256"],
        "tree_python_files": tree["pythonFiles"],
        "runtime_manifest_sha256": file_sha256(DEFAULT_RUNTIME_MANIFEST),
        "core_sha256": file_sha256(core),
    }


def _write_exclusive(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def _corpus_bytes(rows: list[dict[str, Any]]) -> bytes:
    return b"".join(
        (
            json.dumps(
                row,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
        for row in rows
    )


def _path_label(path: Path) -> str:
    try:
        return path.relative_to(REPO).as_posix()
    except ValueError:
        return str(path.resolve())


def seal(
    *,
    corpus_path: Path = CORPUS,
    preregistration_path: Path = PREREGISTRATION,
    identities: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if any(
        path.exists()
        for path in (
            corpus_path,
            preregistration_path,
            OUTPUT,
            TELEMETRY,
            CONSUMED,
            TURN_AUDIT,
            RAW_REPLY_AUDIT,
        )
    ):
        raise RuntimeError("refusing to overwrite veto-reach V8 state")
    validate_population()
    rows = build_population_rows()
    corpus_bytes = _corpus_bytes(rows)
    selected_identities = collect_identities() if identities is None else identities
    manifest = {
        "schema": "baxy.veto-reach.preregistration.v8",
        "blind_holdout": True,
        "measurement_status": "unopened",
        "preregistered_before_measurement": True,
        "reuse_prohibited": True,
        "retry_prohibited": True,
        "authority": (
            "turn.decide only; provider dispatch and external effects disabled"
        ),
        "population": {
            "rows": len(rows),
            "roles": {
                role: sum(row["role"] == role for row in rows)
                for role in sorted({str(row["role"]) for row in rows})
            },
            "languages": ["es", "en", "spanglish"],
            "pairing": "every pair contains one ES, EN and spanglish surface",
            "fresh_against": [
                "veto-reach V1-V7",
                "catalog-surface R2",
                "generalization-product R28",
                "MASSIVE/PRESTO runtime train",
                "MASSIVE/PRESTO public holdout",
            ],
            "population_contract_sha256": population_contract_sha256(rows),
            "corpus_sha256": hashlib.sha256(corpus_bytes).hexdigest(),
        },
        "thresholds": scoring.DEFAULT_THRESHOLDS,
        "prediction": {
            "outcome": "fail",
            "statement": (
                "V8 will fail one or more preregistered binary thresholds."
            ),
        },
        "required_reporting": [
            "retrieval",
            "raw_decision",
            "vetos",
            "raw_candidates",
            "raw_proposal_before_veto",
            "visible_text",
            "unsolicited_effects",
            "unverified_successes",
            "served_false_negatives",
            "fabrications",
        ],
        "identities": selected_identities,
        "planned_outputs": {
            "corpus": _path_label(corpus_path),
            "result": str(OUTPUT.relative_to(REPO)),
            "telemetry": str(TELEMETRY.relative_to(REPO)),
            "consumption_receipt": str(CONSUMED.relative_to(REPO)),
        },
    }
    _write_exclusive(corpus_path, corpus_bytes)
    _write_exclusive(
        preregistration_path,
        (
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8"),
    )
    return manifest


def main() -> int:
    manifest = seal()
    print(
        json.dumps(
            {
                "corpus": manifest["planned_outputs"]["corpus"],
                "rows": manifest["population"]["rows"],
                "population_sha256": manifest["population"][
                    "population_contract_sha256"
                ],
                "tree_sha256": manifest["identities"]["tree_sha256"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
