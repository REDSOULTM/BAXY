"""Load and validate the shipped Goal 09.5.7 tools/skills/missions synthesis.

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
SCHEMA = "baxy.goal095.0957-synthesis.v1"
SYNTHESIS_REL = "artifacts/goal095/synthesis/09.5.7_tools_skills_misiones.v1.json"
LEDGER_REL = "artifacts/goal095/ledger/synthesis-09.5.7.json"
REQUIREMENTS_REL = "artifacts/goal095/extract/_09510_requirements.json"
RUNTIME_PROMPT = "documentacion/sprints/09.5.8_RUNTIME_UI_RECURSOS.md"
TOOLS_PROMPT = "documentacion/sprints/09.5.7_TOOLS_SKILLS_MISIONES.md"
VOICE_PROMPT = "documentacion/sprints/09.5.6_VOZ_AUDIO_PRESENCIA.md"
MODELS_PROMPT = "documentacion/sprints/09.5.5_MODELOS_ROUTER_IDIOMAS.md"
EVIDENCE_PROMPT = "documentacion/sprints/09.5.4_AUDITAR_EVIDENCIA_LOTE.md"

REQUIRED_CAPABILITIES = (
    "catalogos_67_31_16_158",
    "tools",
    "skills",
    "microagentes",
    "uia_ocr_vision",
    "adapters_providers",
    "planes",
    "confirmacion",
    "verificacion",
    "steam_media",
    "archivos",
    "apps",
    "navegador",
    "office",
    "comunicacion",
    "sistema",
    "conectividad",
    "mision_compuesta",
)

REJECTED_PATTERNS = (
    "routers_en_serie",
    "listas_hardcodeadas_por_app",
    "respuestas_fijas",
    "exitos_no_verificados",
)

INVARIANT_FLAGS = (
    "catalogo_unico",
    "kernel_authorization",
    "invocation_bound_confirmation",
    "independent_postcondition",
    "skill_does_not_replace_kernel",
)

BEST_PIECE_FIELDS = ("piece", "evidence", "coste", "mecanismo_de_fracaso")
LINEAGE_COUNTS = ("67", "31", "16", "158")
MISSION_KINDS = frozenset({"simple", "chained"})


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


def _best_piece_ok(piece: dict[str, Any], where: str, errors: list[str]) -> None:
    if not isinstance(piece, dict):
        errors.append(f"{where}: best_piece not object")
        return
    for field in BEST_PIECE_FIELDS:
        if not str(piece.get(field) or "").strip():
            errors.append(f"{where}: missing {field}")


def _owning_or_gap(row: dict[str, Any], row_id: str, errors: list[str]) -> None:
    operation = str(row.get("current_operation") or "").strip()
    test = str(row.get("owning_test") or "").strip()
    gap = row.get("proven_gap")
    if not operation:
        errors.append(f"{row_id}: missing current_operation")
    if test:
        if ".." in test.replace("\\", "/"):
            errors.append(f"{row_id}: owning_test escapes tree")
        return
    if not isinstance(gap, dict) or gap.get("proven") is not True:
        errors.append(f"{row_id}: missing owning_test and proven_gap")
        return
    if not str(gap.get("text") or "").strip():
        errors.append(f"{row_id}: proven_gap.text missing")


def validate_synthesis(
    data: dict[str, Any],
    card_ids: set[str],
    *,
    repo: Path = REPO,
) -> list[str]:
    errors: list[str] = []
    if data.get("schema") != SCHEMA:
        errors.append(f"schema={data.get('schema')}")
    if data.get("next_human_prompt") != RUNTIME_PROMPT:
        errors.append(f"next_human_prompt={data.get('next_human_prompt')}")
    next_human = str(data.get("next_human_prompt") or "")
    for forbidden in (TOOLS_PROMPT, VOICE_PROMPT, MODELS_PROMPT, EVIDENCE_PROMPT):
        if forbidden in next_human:
            errors.append(f"next_human remits to {forbidden}")
    if data.get("live_catalog_changed") is not False:
        errors.append("live catalog changed")
    if data.get("live_providers_changed") is not False:
        errors.append("live providers changed")
    if data.get("live_mission_engine_changed") is not False:
        errors.append("live MissionEngine changed")
    if data.get("goal09_reopened") is not False:
        errors.append("Goal 09 was reopened")

    lineage = str(data.get("catalog_lineage") or "")
    blob = json.dumps(data, ensure_ascii=False)
    blob_cf = blob.casefold()
    for count in LINEAGE_COUNTS:
        if count not in lineage and count not in blob:
            errors.append(f"catalog lineage missing {count}")
    if "169" not in blob and "170" not in blob:
        errors.append("live catalog count missing")
    if "alcanz" not in blob_cf and "reachable" not in blob_cf:
        errors.append("158 reachable not distinguished from live shrink")

    _invariants_ok(data, "root", errors)
    skill_flag = (data.get("invariants") or {}).get("skill_does_not_replace_kernel")
    if skill_flag is not True:
        errors.append("skill_does_not_replace_kernel missing at root")

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
        if "r-023" not in json.dumps(qwen, ensure_ascii=False).casefold():
            errors.append("qwen_vl missing R-023")

    capabilities = data.get("capabilities") or []
    if not isinstance(capabilities, list) or not capabilities:
        errors.append("capabilities empty")
        return errors
    ids = [str(row.get("id") or "") for row in capabilities]
    if len(ids) != len(set(ids)):
        errors.append("duplicate capability id")
    present = set(ids)
    for required in REQUIRED_CAPABILITIES:
        if required not in present:
            errors.append(f"missing capability {required}")

    for row in capabilities:
        row_id = str(row.get("id") or "?")
        _owning_or_gap(row, row_id, errors)
        _best_piece_ok(row.get("best_piece") or {}, f"{row_id}.best_piece", errors)
        _invariants_ok(row, row_id, errors)
        _citations_ok(row, row_id, card_ids, errors)
        if row_id == "skills":
            text = json.dumps(row, ensure_ascii=False).casefold()
            if "kernel" not in text:
                errors.append("skills row does not mention kernel")
            if row.get("invariants", {}).get("skill_does_not_replace_kernel") is not True:
                errors.append("skills row drops skill_does_not_replace_kernel")
        if row_id == "mision_compuesta":
            text = json.dumps(row, ensure_ascii=False).casefold()
            if "steam" not in text or "biblioteca" not in text:
                errors.append("mision_compuesta missing Steam library chain")

    missions = data.get("missions") or []
    if not isinstance(missions, list) or not missions:
        errors.append("missions empty")
    else:
        kinds = {str(row.get("kind") or "") for row in missions}
        if "simple" not in kinds:
            errors.append("missions missing simple")
        if "chained" not in kinds:
            errors.append("missions missing chained")
        complete = False
        steam_chain = False
        for index, row in enumerate(missions):
            if not isinstance(row, dict):
                errors.append(f"missions[{index}] not object")
                continue
            if str(row.get("kind") or "") not in MISSION_KINDS:
                errors.append(f"missions[{index}]: kind not simple|chained")
            ops = row.get("operations") or []
            if not isinstance(ops, list) or not ops:
                errors.append(f"missions[{index}]: operations empty")
            if not str(row.get("owning_test") or row.get("evidence") or "").strip():
                errors.append(f"missions[{index}]: missing owning_test/evidence")
            if row.get("complete") is True:
                complete = True
            blob_m = json.dumps(row, ensure_ascii=False).casefold()
            if "steam" in blob_m and "biblioteca" in blob_m:
                steam_chain = True
            if row.get("reconstructed") is True:
                errors.append(f"missions[{index}]: reconstructed instead of inventoried")
        if not complete:
            errors.append("no complete mission inventoried")
        if not steam_chain:
            errors.append("Steam library chained mission missing")

    rejections = data.get("rejections") or []
    if not isinstance(rejections, list):
        errors.append("rejections missing")
    else:
        patterns = {str(row.get("pattern") or "") for row in rejections if isinstance(row, dict)}
        for pattern in REJECTED_PATTERNS:
            if pattern not in patterns:
                errors.append(f"missing rejection {pattern}")
        for index, row in enumerate(rejections):
            if not isinstance(row, dict):
                errors.append(f"rejections[{index}] not object")
                continue
            if row.get("proposed") is True:
                errors.append(f"rejections[{index}]: rejected pattern proposed")
            if not str(row.get("evidence") or "").strip():
                errors.append(f"rejections[{index}]: missing evidence")
            _citations_ok(row, f"rejections[{index}]", card_ids, errors)

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
            if not str(row.get("eliminated_layer") or "").strip():
                errors.append(f"transplants[{index}]: missing eliminated_layer")
            _invariants_ok(row, f"transplants[{index}]", errors)
            if row.get("second_live_path") is True:
                errors.append(f"transplants[{index}]: second live path")

    for needle in ("router en serie", "routers en serie", "tres routers"):
        if needle in blob_cf and "rejec" not in blob_cf and "rechaz" not in blob_cf:
            errors.append("routers en serie mentioned without rechazo")

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

    if '"works":true' in blob.replace(" ", "").casefold():
        errors.append("approving works=true")
    return errors
