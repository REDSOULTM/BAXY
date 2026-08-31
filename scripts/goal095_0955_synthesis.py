"""Load and validate the shipped Goal 09.5.5 models/router/languages synthesis.

The JSON under artifacts/goal095/synthesis/ is the source of truth. This
module does not re-derive decisions, does not read biblioteca bodies, and
does not walk historical source trees. Citations must resolve to existing
09.5.2–09.5.4 ledger card_id values or extract refs already in the tree.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
SCHEMA = "baxy.goal095.0955-synthesis.v1"
SYNTHESIS_REL = "artifacts/goal095/synthesis/09.5.5_modelos_router_idiomas.v1.json"
LEDGER_REL = "artifacts/goal095/ledger/synthesis-09.5.5.json"
REQUIREMENTS_REL = "artifacts/goal095/extract/_09510_requirements.json"
DECISIONS = frozenset({"conservar", "medir", "reemplazar_candidato"})
AXES = (
    "comprension",
    "conversacion",
    "tool_call_valido",
    "abstencion",
    "prosa",
    "latencia",
    "ram_vram",
    "arranque",
    "facilidad_catalogo",
)
REQUIRED_FAMILIES = (
    "qwen_vigente",
    "functiongemma",
    "gemma4",
    "encoder_tool2vec",
    "abstencion",
    "agent_function_schema",
)
FORBIDDEN_DECISIONS = frozenset({"review", "pendiente", "", "none", "null"})
IN_SCOPE_LANGS = ("es", "en", "spanglish")
VOICE_PROMPT = "documentacion/sprints/09.5.6_VOZ_AUDIO_PRESENCIA.md"
MODELS_PROMPT = "documentacion/sprints/09.5.5_MODELOS_ROUTER_IDIOMAS.md"


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


def _axis_ok(axis: dict[str, Any], name: str, row_id: str, errors: list[str]) -> None:
    if not isinstance(axis, dict):
        errors.append(f"{row_id}.{name}: axis not object")
        return
    if "comparable" not in axis:
        errors.append(f"{row_id}.{name}: missing comparable")
        return
    comparable = axis["comparable"]
    if comparable not in (True, False):
        errors.append(f"{row_id}.{name}: comparable not bool")
    value = str(axis.get("value") or "").strip()
    if not value:
        errors.append(f"{row_id}.{name}: empty value")
    # Row-level comparabilidad_razon covers why; axis.note is optional.


def _citations_ok(
    row: dict[str, Any],
    row_id: str,
    card_ids: set[str],
    repo: Path,
    errors: list[str],
) -> None:
    citations = row.get("citations") or []
    if not citations:
        errors.append(f"{row_id}: missing citations")
        return
    extract_root = repo / "artifacts" / "goal095"
    for cite in citations:
        if not isinstance(cite, dict):
            errors.append(f"{row_id}: citation not object")
            continue
        cid = cite.get("card_id")
        extract_ref = cite.get("extract_ref")
        if cid:
            if cid not in card_ids:
                errors.append(f"{row_id}: unknown card_id {cid}")
        elif extract_ref:
            rel = str(extract_ref).split("#", 1)[0]
            if not (repo / rel).is_file() and not (extract_root / Path(rel).name).is_file():
                target = repo / rel
                if not target.is_file():
                    errors.append(f"{row_id}: missing extract_ref {extract_ref}")
        else:
            errors.append(f"{row_id}: citation lacks card_id and extract_ref")
        path = str(cite.get("path") or "")
        if "biblioteca/" in path.replace("\\", "/"):
            errors.append(f"{row_id}: citation reopens biblioteca")
        if any(
            needle in path.replace("\\", "/")
            for needle in (
                "Programacion/BAXY/",
                "Programacion/Carter OS AI/",
                "Programacion/FunctionGemma/",
                "Programacion/Probando Gemma 4/",
            )
        ):
            errors.append(f"{row_id}: citation reopens source tree {path}")


def _row_text(row: dict[str, Any]) -> str:
    parts = [
        str(row.get("id") or ""),
        str(row.get("family") or ""),
        str(row.get("evidencia_a_favor") or ""),
        str(row.get("evidencia_en_contra") or ""),
        str(row.get("comparabilidad_razon") or ""),
    ]
    return "\n".join(parts).casefold()


def validate_synthesis(
    data: dict[str, Any],
    card_ids: set[str],
    *,
    repo: Path = REPO,
) -> list[str]:
    errors: list[str] = []
    if data.get("schema") != SCHEMA:
        errors.append(f"schema={data.get('schema')}")
    if data.get("next_human_prompt") != VOICE_PROMPT:
        errors.append(f"next_human_prompt={data.get('next_human_prompt')}")
    if MODELS_PROMPT in str(data.get("next_human_prompt") or ""):
        errors.append("next_human remits to 09.5.5")
    constraint = str(data.get("catalog_constraint") or "")
    if "datos tipados" not in constraint.casefold() and "typed" not in constraint.casefold():
        errors.append("catalog_constraint missing typed-data binding")
    if "cocid" not in constraint.casefold() and "pesos" not in constraint.casefold():
        errors.append("catalog_constraint missing baked-weights ban")
    langs = tuple(data.get("languages_in_scope") or ())
    if langs != IN_SCOPE_LANGS:
        errors.append(f"languages_in_scope={langs}")
    if data.get("other_languages_create_work") is not False:
        errors.append("other_languages_create_work must be false")

    candidates = data.get("candidates") or []
    if not isinstance(candidates, list) or not candidates:
        errors.append("candidates empty")
        return errors
    ids = [str(row.get("id") or "") for row in candidates]
    if len(ids) != len(set(ids)):
        errors.append("duplicate candidate id")
    families = {str(row.get("family") or "") for row in candidates}
    for fam in REQUIRED_FAMILIES:
        if fam not in families:
            errors.append(f"missing required family {fam}")
    claimed = list(data.get("inventory_claimed_ids") or [])
    present = set(ids)
    for extra in claimed:
        if extra not in present:
            errors.append(f"silent drop of claimed candidate {extra}")

    fg_contra = ""
    qwen_current = False
    sparse_cited = False
    for row in candidates:
        row_id = str(row.get("id") or "?")
        if not str(row.get("evidencia_a_favor") or "").strip():
            errors.append(f"{row_id}: missing evidencia_a_favor")
        if not str(row.get("evidencia_en_contra") or "").strip():
            errors.append(f"{row_id}: missing evidencia_en_contra")
        comparable = row.get("comparabilidad")
        if comparable not in ("si", "no"):
            errors.append(f"{row_id}: comparabilidad not si|no")
        if comparable == "no" and not str(row.get("comparabilidad_razon") or "").strip():
            errors.append(f"{row_id}: non-comparable needs reason")
        axes = row.get("axes") or {}
        for name in AXES:
            if name not in axes:
                errors.append(f"{row_id}: missing axis {name}")
            else:
                _axis_ok(axes[name], name, row_id, errors)
        _citations_ok(row, row_id, card_ids, repo, errors)
        if row.get("other_language_work_items"):
            errors.append(f"{row_id}: other-language work items forbidden")
        text = _row_text(row)
        if row.get("family") == "functiongemma":
            fg_contra = str(row.get("evidencia_en_contra") or "").casefold()
        if row.get("family") == "qwen_vigente" and row.get("current_choice") is True:
            qwen_current = True
        if "09510" in json.dumps(row, ensure_ascii=False) or "pg4-gguf" in text:
            sparse_cited = True

    if not qwen_current:
        errors.append("Qwen vigente is not marked current_choice")
    if "no conversa" not in fg_contra and "0/3" not in fg_contra:
        errors.append("FunctionGemma evidencia_en_contra missing no-conversa")
    if "cocid" not in fg_contra:
        errors.append("FunctionGemma evidencia_en_contra missing catalogo cocido")
    if "primer split" not in fg_contra and "0/3" not in fg_contra:
        errors.append("FunctionGemma evidencia_en_contra missing primer split abstencion")

    req_path = repo / REQUIREMENTS_REL
    if not req_path.is_file():
        errors.append("missing _09510_requirements.json")
    else:
        req = load_json(req_path)
        for item in req.get("requirements") or []:
            if item.get("individual_hashes") not in ("not invented", None):
                if str(item.get("individual_hashes") or "").strip() not in {
                    "not invented",
                    "",
                }:
                    errors.append("invented sparse hash in _09510_requirements.json")
        if not sparse_cited:
            errors.append("sparse GGUF omission not cited from _09510_requirements")

    stack = data.get("current_stack") or []
    if not stack:
        errors.append("current_stack empty")
    for piece in stack:
        pid = str(piece.get("id") or "?")
        decision = piece.get("decision")
        if decision in FORBIDDEN_DECISIONS or decision is None:
            errors.append(f"{pid}: forbidden decision {decision!r}")
        if decision not in DECISIONS:
            errors.append(f"{pid}: decision not conservar|medir|reemplazar_candidato")
        if not str(piece.get("umbrales") or "").strip():
            errors.append(f"{pid}: empty umbrales")
        if not str(piece.get("coste") or "").strip():
            errors.append(f"{pid}: empty coste")
        if decision in {"medir", "reemplazar_candidato"}:
            if not str(piece.get("benchmark_ciego") or "").strip():
                errors.append(f"{pid}: medir/reemplazar missing benchmark_ciego")
            if not str(piece.get("presupuesto") or "").strip():
                errors.append(f"{pid}: medir/reemplazar missing presupuesto")
            bench = str(piece.get("benchmark_ciego") or "").casefold()
            if "spanglish" not in bench or ("es" not in bench and "español" not in bench):
                errors.append(f"{pid}: benchmark_ciego must name ES/EN/spanglish")

    for row in candidates:
        decision = row.get("decision")
        if decision in FORBIDDEN_DECISIONS:
            errors.append(f"{row.get('id')}: forbidden decision")
        if decision in {"medir", "reemplazar_candidato"}:
            if not str(row.get("benchmark_ciego") or "").strip():
                errors.append(f"{row.get('id')}: medir missing benchmark_ciego")
            if not str(row.get("presupuesto") or "").strip():
                errors.append(f"{row.get('id')}: medir missing presupuesto")

    work = data.get("other_language_work_items") or []
    if work:
        errors.append("other_language_work_items must be empty")
    return errors
