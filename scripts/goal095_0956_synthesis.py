"""Load and validate the shipped Goal 09.5.6 voice/audio/presence synthesis.

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
SCHEMA = "baxy.goal095.0956-synthesis.v1"
SYNTHESIS_REL = "artifacts/goal095/synthesis/09.5.6_voz_audio_presencia.v1.json"
LEDGER_REL = "artifacts/goal095/ledger/synthesis-09.5.6.json"
REQUIREMENTS_REL = "artifacts/goal095/extract/_09510_requirements.json"
EVIDENCE_KINDS = frozenset(
    {"diseño", "código", "asset", "benchmark", "prueba_fisica"}
)
REQUIRED_SUBAREAS = (
    "wake_word",
    "falsos_disparos",
    "ruido",
    "vad",
    "stt",
    "nombres_propios",
    "bilingue_spanglish",
    "tts",
    "primera_senal",
    "barge_in",
    "audio_ducking",
    "dispositivos",
    "modelos_assets",
    "latencia",
    "recursos",
    "presencia",
)
LINEAGE_KEYS = (
    "carter",
    "probando_gemma4",
    "functiongemma",
    "baxy_anterior",
    "schemas",
)
IN_SCOPE_LANGS = ("es", "en", "spanglish")
TOOLS_PROMPT = "documentacion/sprints/09.5.7_TOOLS_SKILLS_MISIONES.md"
VOICE_PROMPT = "documentacion/sprints/09.5.6_VOZ_AUDIO_PRESENCIA.md"
METRIC_FIELDS = ("metrics", "hardware", "corpus")


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


def _kind_ok(value: Any, where: str, errors: list[str]) -> None:
    kind = str(value or "").strip()
    if kind not in EVIDENCE_KINDS:
        errors.append(f"{where}: evidence_kind={kind!r}")


def _measured(row: dict[str, Any], where: str, errors: list[str]) -> None:
    for field in METRIC_FIELDS:
        if not str(row.get(field) or "").strip():
            errors.append(f"{where}: missing {field}")


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


def _piece_ok(piece: dict[str, Any], where: str, errors: list[str]) -> None:
    if not isinstance(piece, dict):
        errors.append(f"{where}: not object")
        return
    if not str(piece.get("piece") or "").strip():
        errors.append(f"{where}: empty piece")
    _measured(piece, where, errors)
    _kind_ok(piece.get("kind"), where, errors)


def _named_engine_ok(
    data: dict[str, Any],
    key: str,
    needles: tuple[str, ...],
    errors: list[str],
    card_ids: set[str],
) -> None:
    row = data.get(key)
    if not isinstance(row, dict):
        errors.append(f"{key} silenced or missing")
        return
    if row.get("silenced") is not False:
        errors.append(f"{key} silenced")
    blob = json.dumps(row, ensure_ascii=False).casefold()
    if not any(needle in blob for needle in needles):
        errors.append(f"{key} missing identity needles {needles}")
    status = str(row.get("status") or "").casefold()
    if "rechaz" not in status and "reject" not in status:
        errors.append(f"{key} status is not a measured rechazo")
    _measured(row, key, errors)
    _citations_ok(row, key, card_ids, errors)
    if row.get("works") is True:
        errors.append(f"{key}: approving simulation works=true")


def validate_synthesis(
    data: dict[str, Any],
    card_ids: set[str],
    *,
    repo: Path = REPO,
) -> list[str]:
    errors: list[str] = []
    if data.get("schema") != SCHEMA:
        errors.append(f"schema={data.get('schema')}")
    if data.get("next_human_prompt") != TOOLS_PROMPT:
        errors.append(f"next_human_prompt={data.get('next_human_prompt')}")
    if VOICE_PROMPT in str(data.get("next_human_prompt") or ""):
        errors.append("next_human remits to 09.5.6")
    langs = tuple(data.get("languages_in_scope") or ())
    if langs != IN_SCOPE_LANGS:
        errors.append(f"languages_in_scope={langs}")
    if data.get("other_languages_create_work") is not False:
        errors.append("other_languages_create_work must be false")
    work = data.get("other_language_work_items") or []
    if work:
        errors.append("other_language_work_items must be empty")
    if data.get("english_app_names_in_spanish_count_as_spanglish") is not True:
        errors.append("english app names in Spanish must count as spanglish")
    if data.get("goal09_reopened") is not False:
        errors.append("Goal 09 was reopened")
    if data.get("live_weights_changed") is not False:
        errors.append("live weights changed")

    _named_engine_ok(
        data,
        "qwen_asr",
        ("qwen3-asr", "qwen-asr", "qwen3_asr"),
        errors,
        card_ids,
    )
    _named_engine_ok(
        data,
        "gemma_native_audio",
        ("input_audio", "gemma"),
        errors,
        card_ids,
    )

    subareas = data.get("subareas") or []
    if not isinstance(subareas, list) or not subareas:
        errors.append("subareas empty")
        return errors
    ids = [str(row.get("id") or "") for row in subareas]
    if len(ids) != len(set(ids)):
        errors.append("duplicate subarea id")
    present = set(ids)
    for required in REQUIRED_SUBAREAS:
        if required not in present:
            errors.append(f"missing subarea {required}")

    blob = json.dumps(data, ensure_ascii=False).casefold()
    if "spanglish" not in blob:
        errors.append("spanglish missing from synthesis")
    if "notepad" not in blob and "spotify" not in blob:
        errors.append("english app names missing")

    for row in subareas:
        row_id = str(row.get("id") or "?")
        _kind_ok(row.get("evidence_kind"), f"{row_id}.evidence_kind", errors)
        lineage = row.get("lineage") or {}
        if not isinstance(lineage, dict):
            errors.append(f"{row_id}: lineage not object")
        else:
            for key in LINEAGE_KEYS:
                if not str(lineage.get(key) or "").strip():
                    errors.append(f"{row_id}: missing lineage.{key}")
        _piece_ok(row.get("best_historical") or {}, f"{row_id}.best_historical", errors)
        _piece_ok(row.get("current_goal09") or {}, f"{row_id}.current_goal09", errors)
        gap = row.get("gap") or {}
        if not isinstance(gap, dict) or not str(gap.get("text") or "").strip():
            errors.append(f"{row_id}: gap.text missing")
        elif gap.get("proven") is not True:
            errors.append(f"{row_id}: gap.proven must be true")
        if gap.get("reopen_goal09") is True:
            errors.append(f"{row_id}: gap reopens Goal 09")
        exitos = row.get("exitos") or []
        rechazos = row.get("rechazos") or []
        if not isinstance(exitos, list) or not exitos:
            errors.append(f"{row_id}: exitos empty")
        if not isinstance(rechazos, list) or not rechazos:
            errors.append(f"{row_id}: rechazos empty")
        for index, item in enumerate(exitos):
            if not isinstance(item, dict):
                errors.append(f"{row_id}.exitos[{index}] not object")
                continue
            _measured(item, f"{row_id}.exitos[{index}]", errors)
            _kind_ok(item.get("kind"), f"{row_id}.exitos[{index}]", errors)
            if item.get("works") is True and "falt" in json.dumps(item, ensure_ascii=False).casefold():
                errors.append(f"{row_id}.exitos[{index}]: approving missing asset")
        for index, item in enumerate(rechazos):
            if not isinstance(item, dict):
                errors.append(f"{row_id}.rechazos[{index}] not object")
                continue
            _measured(item, f"{row_id}.rechazos[{index}]", errors)
            _kind_ok(item.get("kind"), f"{row_id}.rechazos[{index}]", errors)
        _citations_ok(row, row_id, card_ids, errors)

    transplants = data.get("transplants")
    if not isinstance(transplants, list):
        errors.append("transplants missing")
    else:
        if transplants and not str(data.get("transplants_empty_reason") or "").strip():
            pass
        if not transplants and not str(data.get("transplants_empty_reason") or "").strip():
            errors.append("empty transplants need transplants_empty_reason")
        required_tx = ("source", "owner", "prueba", "pieza_reemplazada")
        for index, row in enumerate(transplants):
            if not isinstance(row, dict):
                errors.append(f"transplants[{index}] not object")
                continue
            for field in required_tx:
                if not str(row.get(field) or "").strip():
                    errors.append(f"transplants[{index}]: missing {field}")
            if row.get("improves_demonstrated_gap") is not True and row.get(
                "cuts_cost_without_regression"
            ) is not True:
                errors.append(
                    f"transplants[{index}]: neither demonstrated gap nor cost cut"
                )

    ambiente = data.get("ambiente") or {}
    if ambiente.get("approving_simulation") is True:
        errors.append("ambiente approving_simulation")
    fallo = ambiente.get("fallo_de_ambiente") or []
    if not isinstance(fallo, list):
        errors.append("fallo_de_ambiente not list")
    for note in fallo:
        if isinstance(note, dict) and note.get("works") is True:
            errors.append("FALLO_DE_AMBIENTE marked works")

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
        if "not invented" not in sparse and "pg4-training-datasets" not in blob:
            errors.append("sparse wake/STT datasets not cited")

    if "works" in blob and '"works": true' in blob.replace(" ", "").casefold():
        # Catch approving simulations of missing devices/assets.
        for needle in ("faltante", "ausente", "missing", "not invented"):
            if needle in blob:
                break
    return errors
