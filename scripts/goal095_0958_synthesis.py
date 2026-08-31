"""Load and validate the shipped Goal 09.5.8 runtime/UI/resources synthesis.

The JSON under artifacts/goal095/synthesis/ is the source of truth. This
module does not re-derive decisions, does not read biblioteca bodies, and
does not walk historical source trees. Citations must resolve to existing
09.5.2–09.5.4 ledger card_id values.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
SCHEMA = "baxy.goal095.0958-synthesis.v1"
SYNTHESIS_REL = "artifacts/goal095/synthesis/09.5.8_runtime_ui_recursos.v1.json"
LEDGER_REL = "artifacts/goal095/ledger/synthesis-09.5.8.json"
REQUIREMENTS_REL = "artifacts/goal095/extract/_09510_requirements.json"
DECIDE_PROMPT = "documentacion/sprints/09.5.9_DECIDIR_HERENCIA.md"
RUNTIME_PROMPT = "documentacion/sprints/09.5.8_RUNTIME_UI_RECURSOS.md"
TOOLS_PROMPT = "documentacion/sprints/09.5.7_TOOLS_SKILLS_MISIONES.md"
VOICE_PROMPT = "documentacion/sprints/09.5.6_VOZ_AUDIO_PRESENCIA.md"
MODELS_PROMPT = "documentacion/sprints/09.5.5_MODELOS_ROUTER_IDIOMAS.md"
EVIDENCE_PROMPT = "documentacion/sprints/09.5.4_AUDITAR_EVIDENCIA_LOTE.md"

DECISIONS = frozenset(
    {"reusar", "adaptar", "conservar_actual", "medir", "rechazar"}
)
REQUIRED_AREAS = (
    "runtime_servidor",
    "carga_descarga_modelos",
    "vram_ram_cpu",
    "latencia",
    "arranque",
    "watchdog",
    "estabilidad",
    "field_ui_accesibilidad",
    "vision_camara",
    "memoria_proactividad",
    "journal",
    "setup_publish",
    "privacidad",
    "seguridad",
    "diagnosticos",
)
RESOURCE_AREAS = frozenset({"vram_ram_cpu", "latencia", "arranque"})
GOAL10_CONSUMERS = frozenset(
    {
        "10.0_BASE_VERDE.md",
        "10.2_PRESENCIA_Y_RECURSOS.md",
        "10.10_APPS_VENTANAS_VISION.md",
        "10.14_PRODUCTIVIDAD_MEMORIA.md",
        "10.17_IDENTIDAD_VIVA.md",
    }
)
INVARIANT_FLAGS = (
    "privacidad_local",
    "accesibilidad_central",
    "estados_terminales_honestos",
)
CANDIDATE_FIELDS = ("source", "owner", "owning_test", "mecanismo_reemplazado")
MEASUREMENT_FIELDS = ("hardware", "version", "escenario", "denominador")
OVERHEAD_FIELDS = ("own_overhead", "inference")
FORBIDDEN_NEXT = (
    RUNTIME_PROMPT,
    TOOLS_PROMPT,
    VOICE_PROMPT,
    MODELS_PROMPT,
    EVIDENCE_PROMPT,
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def synthesis_path(repo: Path = REPO) -> Path:
    return repo / SYNTHESIS_REL


def synthesis_ledger_path(repo: Path = REPO) -> Path:
    return repo / LEDGER_REL


def load_synthesis(repo: Path = REPO) -> dict[str, Any]:
    path = synthesis_path(repo)
    if not path.is_file():
        raise FileNotFoundError(path)
    return load_json(path)


def index_ledger_card_ids(repo: Path = REPO) -> set[str]:
    cards: set[str] = set()
    ledger_dir = repo / "artifacts" / "goal095" / "ledger"
    for path in ledger_dir.glob("*.json"):
        data = load_json(path)
        for card in data.get("cards") or []:
            cid = card.get("card_id")
            if cid:
                cards.add(str(cid))
    return cards


def _citations_ok(
    row: dict[str, Any],
    row_id: str,
    card_ids: set[str],
    errors: list[str],
) -> None:
    citations = row.get("citations") or []
    if not citations:
        errors.append(f"{row_id}: missing citations")
        return
    for cite in citations:
        if not isinstance(cite, dict):
            errors.append(f"{row_id}: citation not object")
            continue
        cid = cite.get("card_id")
        if not cid:
            errors.append(f"{row_id}: citation lacks card_id")
            continue
        if str(cid) not in card_ids:
            errors.append(f"{row_id}: unknown card_id {cid}")
        path = str(cite.get("path") or "")
        if "biblioteca/" in path.replace("\\", "/"):
            errors.append(f"{row_id}: citation reopens biblioteca")


def _invariants_ok(row: dict[str, Any], where: str, errors: list[str]) -> None:
    flags = row.get("invariants")
    if not isinstance(flags, dict):
        errors.append(f"{where}: invariants not object")
        return
    for name in INVARIANT_FLAGS:
        if flags.get(name) is not True:
            errors.append(f"{where}: {name} is not true")


def _candidate_fields_ok(row: dict[str, Any], where: str, errors: list[str]) -> None:
    for field in CANDIDATE_FIELDS:
        if not str(row.get(field) or "").strip():
            errors.append(f"{where}: missing {field}")


def _goal10_ok(value: Any, row_id: str, errors: list[str]) -> None:
    if isinstance(value, list):
        consumers = [str(item) for item in value]
    else:
        consumers = [str(value or "")]
    if not any(item.strip() for item in consumers):
        errors.append(f"{row_id}: missing goal10_consumer")
        return
    for item in consumers:
        name = item.replace("\\", "/").rsplit("/", 1)[-1]
        if name not in GOAL10_CONSUMERS:
            errors.append(f"{row_id}: goal10_consumer {item!r} not in Goal 10 set")


def _measurement_ok(row: dict[str, Any], row_id: str, errors: list[str]) -> None:
    measurement = row.get("measurement")
    if not isinstance(measurement, dict):
        errors.append(f"{row_id}: measurement not object")
        return
    comparable = measurement.get("comparable")
    if comparable not in {True, False}:
        errors.append(f"{row_id}: comparable not bool")
    if row_id in RESOURCE_AREAS or comparable is True:
        for field in MEASUREMENT_FIELDS:
            if not str(measurement.get(field) or "").strip():
                errors.append(f"{row_id}: missing measurement.{field}")
        for field in OVERHEAD_FIELDS:
            if not str(measurement.get(field) or "").strip():
                errors.append(f"{row_id}: missing {field} (own vs inference)")
    if comparable is False:
        if not str(measurement.get("incomparable_reason") or "").strip():
            errors.append(f"{row_id}: incomparable needs incomparable_reason")
        if row.get("decision") == "reusar":
            errors.append(f"{row_id}: reusar on incomparable numbers")


def validate_synthesis(
    data: dict[str, Any],
    card_ids: set[str],
    *,
    repo: Path = REPO,
) -> list[str]:
    errors: list[str] = []
    if data.get("schema") != SCHEMA:
        errors.append(f"schema={data.get('schema')}")
    if data.get("next_human_prompt") != DECIDE_PROMPT:
        errors.append(f"next_human_prompt={data.get('next_human_prompt')}")
    next_human = str(data.get("next_human_prompt") or "")
    for forbidden in FORBIDDEN_NEXT:
        if forbidden in next_human:
            errors.append(f"next_human remits to {forbidden}")
    if data.get("live_runtime_changed") is not False:
        errors.append("live runtime changed")
    if data.get("live_fieldui_dist_changed") is not False:
        errors.append("live FieldUi dist changed")
    if data.get("live_setup_changed") is not False:
        errors.append("live Setup changed")
    if data.get("goal09_reopened") is not False:
        errors.append("Goal 09 was reopened")
    if data.get("soak_24h_requirement") is not False:
        errors.append("24 h soak converted into a requirement")

    _invariants_ok(data, "root", errors)

    qwen = data.get("qwen_vl")
    if not isinstance(qwen, dict) or qwen.get("silenced") is not False:
        errors.append("qwen_vl silenced or missing")
    else:
        status = str(qwen.get("status") or "").casefold()
        if "rechaz" not in status and "reject" not in status:
            errors.append("qwen_vl status is not a measured rechazo")
        _citations_ok(qwen, "qwen_vl", card_ids, errors)
        if qwen.get("works") is True:
            errors.append("qwen_vl approving simulation works=true")
        blob_q = json.dumps(qwen, ensure_ascii=False).casefold()
        if "r-023" not in blob_q:
            errors.append("qwen_vl missing R-023")

    areas = data.get("areas") or []
    if not isinstance(areas, list) or not areas:
        errors.append("areas empty")
        return errors
    ids = [str(row.get("id") or "") for row in areas]
    if len(ids) != len(set(ids)):
        errors.append("duplicate area id")
    present = set(ids)
    for required in REQUIRED_AREAS:
        if required not in present:
            errors.append(f"missing area {required}")
    if present != set(REQUIRED_AREAS):
        extra = present - set(REQUIRED_AREAS)
        if extra:
            errors.append(f"unexpected areas {sorted(extra)}")

    consumers_seen: set[str] = set()
    for row in areas:
        if not isinstance(row, dict):
            errors.append("area not object")
            continue
        row_id = str(row.get("id") or "?")
        if not str(row.get("historical") or "").strip():
            errors.append(f"{row_id}: missing historical")
        if not str(row.get("live_owner") or "").strip():
            errors.append(f"{row_id}: missing live_owner")
        decision = str(row.get("decision") or "")
        if decision not in DECISIONS:
            errors.append(f"{row_id}: decision={decision!r}")
        _goal10_ok(row.get("goal10_consumer"), row_id, errors)
        consumer = row.get("goal10_consumer")
        if isinstance(consumer, list):
            consumers_seen.update(str(item).replace("\\", "/").rsplit("/", 1)[-1] for item in consumer)
        else:
            consumers_seen.add(str(consumer or "").replace("\\", "/").rsplit("/", 1)[-1])
        _candidate_fields_ok(row, row_id, errors)
        _invariants_ok(row, row_id, errors)
        _citations_ok(row, row_id, card_ids, errors)
        _measurement_ok(row, row_id, errors)
        if row.get("second_live_path") is True:
            errors.append(f"{row_id}: second live path")
        test = str(row.get("owning_test") or "")
        if ".." in test.replace("\\", "/"):
            errors.append(f"{row_id}: owning_test escapes tree")

    for required_consumer in GOAL10_CONSUMERS:
        if required_consumer not in consumers_seen:
            errors.append(f"no area names Goal 10 consumer {required_consumer}")

    transplants = data.get("transplants")
    if not isinstance(transplants, list):
        errors.append("transplants missing")
    else:
        if not transplants and not str(data.get("transplants_empty_reason") or "").strip():
            errors.append("empty transplants need transplants_empty_reason")
        for index, row in enumerate(transplants):
            if not isinstance(row, dict):
                errors.append(f"transplants[{index}] not object")
                continue
            _candidate_fields_ok(row, f"transplants[{index}]", errors)
            _invariants_ok(row, f"transplants[{index}]", errors)
            if row.get("second_live_path") is True:
                errors.append(f"transplants[{index}]: second live path")
            if not str(row.get("mecanismo_reemplazado") or "").strip():
                errors.append(f"transplants[{index}]: missing mecanismo_reemplazado")

    blob = json.dumps(data, ensure_ascii=False)
    blob_cf = blob.casefold()
    if "biblioteca/" in blob.replace("\\", "/"):
        errors.append("synthesis cites biblioteca path")
    if data.get("soak_24h_requirement") is True or (
        "24 h" in blob_cf and "requisito" in blob_cf and "no conviert" not in blob_cf
        and "no es requisito" not in blob_cf and "no hay soak" not in blob_cf
    ):
        if data.get("soak_24h_requirement") is not False:
            errors.append("24 h soak looks like a requirement")
    if '"works":true' in blob.replace(" ", "").casefold():
        errors.append("approving works=true")

    ambiente = data.get("ambiente") or {}
    if ambiente.get("approving_simulation") is True:
        errors.append("ambiente approving_simulation")
    if ambiente.get("fallo_de_ambiente"):
        errors.append("unexpected FALLO_DE_AMBIENTE")

    req_path = repo / REQUIREMENTS_REL
    if not req_path.is_file():
        errors.append("missing _09510_requirements.json")
    else:
        req = load_json(req_path)
        for item in req.get("requirements") or []:
            hashes = str(item.get("individual_hashes") or "").strip()
            if hashes not in {"not invented", ""}:
                errors.append("invented sparse hash in _09510_requirements.json")
        sparse = json.dumps(data.get("sparse_assets") or {}, ensure_ascii=False).casefold()
        if "not invented" not in sparse:
            errors.append("sparse hashes not cited as not invented")
    return errors
