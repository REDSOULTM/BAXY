"""Load and validate the shipped Goal 09.5.9 heritage decision matrix.

The JSON under artifacts/goal095/synthesis/ is the source of truth. This
module does not re-derive decisions, does not read biblioteca bodies, and
does not walk historical source trees. Card citations resolve to existing
09.5.2–09.5.4 ledger card_id values. Transplant lots are emitted from the
matrix rather than a second handwritten queue.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
SCHEMA = "baxy.goal095.0959-matrix.v1"
CAMPAIGN_SCHEMA = "baxy.goal095.campaign.v1"
SYNTHESIS_REL = "artifacts/goal095/synthesis/09.5.9_decidir_herencia.v1.json"
ASSIGNMENT_REL = "artifacts/goal095/synthesis/09.5.9_card_assignment.v1.json"
CAMPAIGN_REL = "artifacts/goal095/campaigns/transplant.json"
LEDGER_REL = "artifacts/goal095/ledger/synthesis-09.5.9.json"
LEDGER_09510_REL = "artifacts/goal095/ledger/transplant-09.5.10.json"
HANDOFF_REL = "artifacts/goal095/HANDOFF.md"
MARKDOWN_09510_REL = "documentacion/herencia/09_5_10_TRASPLANTAR.md"
REQUIREMENTS_REL = "artifacts/goal095/extract/_09510_requirements.json"
SYNTHESIS_0955 = "artifacts/goal095/synthesis/09.5.5_modelos_router_idiomas.v1.json"
SYNTHESIS_0956 = "artifacts/goal095/synthesis/09.5.6_voz_audio_presencia.v1.json"
SYNTHESIS_0957 = "artifacts/goal095/synthesis/09.5.7_tools_skills_misiones.v1.json"
SYNTHESIS_0958 = "artifacts/goal095/synthesis/09.5.8_runtime_ui_recursos.v1.json"

TERMINALS = frozenset(
    {"reusar_exacto", "adaptar", "conservar_actual", "medir_antes", "rechazar"}
)
FORBIDDEN_TERMINALS = frozenset(
    {
        "review",
        "pendiente",
        "conservar",
        "medir",
        "reusar",
        "reemplazar_candidato",
        "none",
        "null",
        "",
    }
)
TRANSPLANT_TERMINALS = frozenset({"reusar_exacto", "adaptar", "medir_antes"})
REUSE_ADAPT = frozenset({"reusar_exacto", "adaptar"})
COMPARE_FIELDS = ("conducta", "pruebas", "recursos", "arquitectura")
REUSE_FIELDS = (
    "source_hash",
    "destino_owner",
    "archivos_maximos",
    "pruebas_dueno",
    "presupuesto",
    "riesgo",
    "pieza_que_se_retira",
    "transplant_batch",
)
MEASURE_FIELDS = ("instrument", "corpus", "presupuesto", "stop_rule")
REJECT_FIELDS = ("mecanismo_de_fracaso", "coste", "invariante")
PROTECTED_REJECTS = (
    "functiongemma-270m-ft",
    "qwen-vl",
    "ollama-runtime",
    "auto_approve",
    "soak-24h-as-requirement",
    "gemma-native-audio",
)
AUDIT_KINDS = frozenset({"docs", "code_tests", "evidence_assets"})
TRANSPLANT_PROMPT = "documentacion/sprints/09.5.10_TRASPLANTAR_LOTE.md"
REVALIDATE_PROMPT = "documentacion/sprints/09.5.11A_REVALIDAR_01_03C.md"
DECIDE_PROMPT = "documentacion/sprints/09.5.9_DECIDIR_HERENCIA.md"
BATCH_CAP = 300_000
ALLOWED_NEXT = frozenset({TRANSPLANT_PROMPT, REVALIDATE_PROMPT})


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def matrix_path(repo: Path = REPO) -> Path:
    return repo / SYNTHESIS_REL


def assignment_path(repo: Path = REPO) -> Path:
    return repo / ASSIGNMENT_REL


def campaign_path(repo: Path = REPO) -> Path:
    return repo / CAMPAIGN_REL


def synthesis_ledger_path(repo: Path = REPO) -> Path:
    return repo / LEDGER_REL


def transplant_ledger_path(repo: Path = REPO) -> Path:
    return repo / LEDGER_09510_REL


def load_matrix(repo: Path = REPO) -> dict[str, Any]:
    path = matrix_path(repo)
    if not path.is_file():
        raise FileNotFoundError(path)
    return load_json(path)


def load_assignment(repo: Path = REPO) -> dict[str, Any]:
    path = assignment_path(repo)
    if not path.is_file():
        raise FileNotFoundError(path)
    return load_json(path)


def load_campaign(repo: Path = REPO) -> dict[str, Any]:
    path = campaign_path(repo)
    if not path.is_file():
        raise FileNotFoundError(path)
    return load_json(path)


def load_transplant_ledger(repo: Path = REPO) -> dict[str, Any]:
    path = transplant_ledger_path(repo)
    if not path.is_file():
        raise FileNotFoundError(path)
    return load_json(path)


def campaign_is_drained(campaign: dict[str, Any]) -> bool:
    counts = campaign_counts(campaign)
    return counts["pending"] == 0 and counts["claimed"] == 0


def closeout_next_human_prompt(campaign: dict[str, Any]) -> str:
    """Empty-queue and last-lot closeout share this pointer.

    A drained campaign (pending=0, claimed=0) names 09.5.11A. A live
    campaign keeps 09.5.10 as the owner prompt to resume, never as a
    second human launch.
    """
    if campaign_is_drained(campaign):
        return REVALIDATE_PROMPT
    return TRANSPLANT_PROMPT


def apply_transplant_closeout(
    campaign: dict[str, Any],
    *,
    updated_utc: str,
) -> dict[str, Any]:
    """Return campaign accounting after drain. Does not touch src/."""
    out = json.loads(json.dumps(campaign))
    lots = list(out.get("lots") or [])
    out["lots"] = lots
    counts = campaign_counts(out)
    out["counts"] = {
        "pending": counts["pending"],
        "claimed": counts["claimed"],
        "complete": counts["complete"],
        "total": len(lots),
    }
    out["required_human_launches"] = 1
    out["owner_prompt"] = TRANSPLANT_PROMPT
    out["next_human_prompt"] = closeout_next_human_prompt(out)
    if campaign_is_drained(out):
        out["cursor_status"] = "complete"
        out["cursor_batch_id"] = None
    out["updated_utc"] = updated_utc
    return out


def index_orphan_transplant_claims(repo: Path = REPO) -> list[str]:
    claims_dir = repo / "artifacts" / "goal095" / "claims"
    if not claims_dir.is_dir():
        return []
    orphans: list[str] = []
    for path in sorted(claims_dir.glob("transplant*.json")):
        rec = load_json(path)
        if rec.get("status") == "claimed":
            orphans.append(path.name)
    return orphans


def index_audit_card_ids(repo: Path = REPO) -> set[str]:
    cards: set[str] = set()
    ledger_dir = repo / "artifacts" / "goal095" / "ledger"
    for path in ledger_dir.glob("*.json"):
        data = load_json(path)
        if data.get("kind") not in AUDIT_KINDS:
            continue
        for card in data.get("cards") or []:
            cid = card.get("card_id")
            if cid:
                cards.add(str(cid))
    return cards


def index_synthesis_responsibility_ids(repo: Path = REPO) -> set[str]:
    ids: set[str] = set()
    s55 = load_json(repo / SYNTHESIS_0955)
    for row in s55.get("current_stack") or []:
        ids.add(f"09.5.5:{row['id']}")
    for row in s55.get("candidates") or []:
        ids.add(f"09.5.5:{row['id']}")
    s56 = load_json(repo / SYNTHESIS_0956)
    for row in s56.get("subareas") or []:
        ids.add(f"09.5.6:{row['id']}")
    ids.add("09.5.6:qwen_asr")
    ids.add("09.5.6:gemma_native_audio")
    s57 = load_json(repo / SYNTHESIS_0957)
    for row in s57.get("capabilities") or []:
        ids.add(f"09.5.7:{row['id']}")
    for row in s57.get("rejections") or []:
        ids.add(f"09.5.7:{row['pattern']}")
    for row in s57.get("missions") or []:
        ids.add(f"09.5.7:{row['id']}")
    ids.add("09.5.7:qwen_vl")
    s58 = load_json(repo / SYNTHESIS_0958)
    for row in s58.get("areas") or []:
        ids.add(f"09.5.8:{row['id']}")
    ids.add("09.5.8:qwen_vl")
    return ids


def campaign_counts(campaign: dict[str, Any]) -> dict[str, int]:
    lots = campaign.get("lots") or []
    pending = claimed = complete = 0
    for lot in lots:
        status = lot.get("status")
        if status == "pending":
            pending += 1
        elif status == "claimed":
            claimed += 1
        elif status == "complete":
            complete += 1
    total = int(campaign.get("counts", {}).get("total") or len(lots))
    return {
        "pending": pending,
        "claimed": claimed,
        "complete": complete,
        "total": total,
    }


def lots_from_matrix(matrix: dict[str, Any]) -> list[dict[str, Any]]:
    lots: list[dict[str, Any]] = []
    for row in matrix.get("responsibilities") or []:
        decision = str(row.get("decision") or "")
        if decision not in TRANSPLANT_TERMINALS:
            continue
        lots.append(
            {
                "lot_id": f"transplant-{row['id']}",
                "responsibility_id": row["id"],
                "decision": decision,
                "status": "pending",
                "order": int(row.get("order") or 0),
                "valor_10_11": str(row.get("valor_10_11") or ""),
                "depends_on": list(row.get("depends_on") or []),
                "destino_owner": str(row.get("destino_owner") or row.get("live_owner") or ""),
                "pieza_que_se_retira": str(row.get("pieza_que_se_retira") or ""),
                "transplant_batch": row.get("transplant_batch"),
                "pruebas_dueno": str(row.get("pruebas_dueno") or row.get("owning_test") or ""),
                "instrument": str(row.get("instrument") or ""),
                "corpus": str(row.get("corpus") or ""),
                "presupuesto": str(row.get("presupuesto") or ""),
                "stop_rule": str(row.get("stop_rule") or ""),
                "source_hash": str(row.get("source_hash") or ""),
                "archivos_maximos": row.get("archivos_maximos"),
                "riesgo": str(row.get("riesgo") or ""),
            }
        )
    lots.sort(key=lambda item: (item["order"], item["responsibility_id"]))
    return lots


def _batch_tokens(value: Any) -> int | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, dict):
        for key in ("tokens", "estimated_tokens", "input_tokens"):
            if key in value:
                try:
                    return int(value[key])
                except (TypeError, ValueError):
                    return None
    if isinstance(value, str):
        digits = "".join(ch for ch in value if ch.isdigit())
        if digits:
            return int(digits)
    return None


def validate_matrix(
    data: dict[str, Any],
    card_ids: set[str],
    synthesis_ids: set[str],
    assignment: dict[str, Any],
    *,
    repo: Path = REPO,
) -> list[str]:
    errors: list[str] = []
    if data.get("schema") != SCHEMA:
        errors.append(f"schema={data.get('schema')}")
    next_human = str(data.get("next_human_prompt") or "")
    if next_human not in ALLOWED_NEXT:
        errors.append(f"next_human_prompt={next_human}")
    if DECIDE_PROMPT in next_human:
        errors.append("next_human remits to 09.5.9")
    blob = json.dumps(data, ensure_ascii=False)
    blob_cf = blob.casefold()
    if "review" in blob_cf and '"decision": "review"' in blob_cf:
        errors.append("forbidden terminal review")
    if '"pendiente"' in blob_cf:
        errors.append("forbidden terminal pendiente")
    if "biblioteca/" in blob.replace("\\", "/"):
        errors.append("matrix cites biblioteca path")

    rows = data.get("responsibilities") or []
    if not isinstance(rows, list) or not rows:
        errors.append("responsibilities empty")
        return errors

    row_ids: list[str] = []
    assigned_synth: set[str] = set()
    transplant_row_ids: set[str] = set()
    protected_seen: set[str] = set()
    decisions_present: set[str] = set()

    for row in rows:
        if not isinstance(row, dict):
            errors.append("responsibility not object")
            continue
        row_id = str(row.get("id") or "")
        if not row_id:
            errors.append("empty responsibility id")
            continue
        row_ids.append(row_id)
        decision = str(row.get("decision") or "")
        decisions_present.add(decision)
        if decision in FORBIDDEN_TERMINALS or decision not in TERMINALS:
            errors.append(f"{row_id}: decision={decision!r}")
        for field in COMPARE_FIELDS:
            if not str(row.get(field) or "").strip():
                errors.append(f"{row_id}: missing {field}")
        refs = row.get("synthesis_refs") or []
        if not isinstance(refs, list):
            errors.append(f"{row_id}: synthesis_refs not list")
            refs = []
        for ref in refs:
            ref_s = str(ref)
            if ref_s in assigned_synth:
                errors.append(f"{row_id}: duplicate synthesis_ref {ref_s}")
            assigned_synth.add(ref_s)
            if ref_s not in synthesis_ids:
                errors.append(f"{row_id}: unknown synthesis_ref {ref_s}")
        if decision in REUSE_ADAPT:
            transplant_row_ids.add(row_id)
            for field in REUSE_FIELDS:
                if field == "archivos_maximos":
                    value = row.get(field)
                    if value in (None, "", []):
                        errors.append(f"{row_id}: missing {field}")
                elif field == "transplant_batch":
                    tokens = _batch_tokens(row.get(field))
                    if tokens is None:
                        errors.append(f"{row_id}: missing transplant_batch")
                    elif tokens >= BATCH_CAP:
                        errors.append(f"{row_id}: transplant_batch {tokens} >= {BATCH_CAP}")
                elif not str(row.get(field) or "").strip():
                    errors.append(f"{row_id}: missing {field}")
            if not str(row.get("pieza_que_se_retira") or "").strip():
                errors.append(f"{row_id}: missing pieza_que_se_retira")
        if decision == "medir_antes":
            transplant_row_ids.add(row_id)
            for field in MEASURE_FIELDS:
                if not str(row.get(field) or "").strip():
                    errors.append(f"{row_id}: missing {field}")
        if decision == "rechazar":
            for field in REJECT_FIELDS:
                if not str(row.get(field) or "").strip():
                    errors.append(f"{row_id}: missing {field}")
        if row_id in PROTECTED_REJECTS:
            protected_seen.add(row_id)
            if decision != "rechazar":
                errors.append(f"{row_id}: protected reject is {decision}")
            if row.get("protected") is not True:
                errors.append(f"{row_id}: protected flag missing")

    if len(row_ids) != len(set(row_ids)):
        errors.append("duplicate responsibility id")
    missing_synth = synthesis_ids - assigned_synth
    extra_synth = assigned_synth - synthesis_ids
    if missing_synth:
        errors.append(f"unassigned synthesis ids {sorted(missing_synth)[:12]}")
    if extra_synth:
        errors.append(f"unknown synthesis ids {sorted(extra_synth)[:12]}")
    missing_protected = [name for name in PROTECTED_REJECTS if name not in protected_seen]
    if missing_protected:
        errors.append(f"missing protected rejects {missing_protected}")

    mapping = assignment.get("card_to_row") or assignment.get("assignment") or assignment
    if not isinstance(mapping, dict) or not mapping:
        errors.append("card assignment missing")
        mapping = {}
    mapped_cards = {str(key) for key in mapping.keys()}
    missing_cards = card_ids - mapped_cards
    extra_cards = mapped_cards - card_ids
    if missing_cards:
        errors.append(f"unassigned cards {len(missing_cards)}")
    if extra_cards:
        errors.append(f"unknown assigned cards {len(extra_cards)}")
    reverse: dict[str, int] = {}
    known_rows = set(row_ids)
    for cid, rid in mapping.items():
        rid_s = str(rid)
        reverse[rid_s] = reverse.get(rid_s, 0) + 1
        if rid_s not in known_rows:
            errors.append(f"assignment points at unknown row {rid_s}")
            break
    declared = data.get("card_counts") or {}
    if declared and int(declared.get("total") or 0) != len(card_ids):
        errors.append(f"card_counts.total {declared.get('total')} != {len(card_ids)}")

    req_path = repo / REQUIREMENTS_REL
    if not req_path.is_file():
        errors.append("missing _09510_requirements.json")
    else:
        req = load_json(req_path)
        for item in req.get("requirements") or []:
            hashes = str(item.get("individual_hashes") or "").strip()
            if hashes not in {"not invented", ""}:
                errors.append("invented sparse hash in _09510_requirements.json")
        if "not invented" not in json.dumps(data.get("sparse_assets") or {}, ensure_ascii=False).casefold():
            errors.append("sparse hashes not cited as not invented")

    if data.get("estado_del_arte_added") is True:
        errors.append("estado del arte added while historical piece fulfills")
    return errors


def validate_campaign(
    campaign: dict[str, Any],
    matrix: dict[str, Any],
    *,
    repo: Path | None = None,
) -> list[str]:
    errors: list[str] = []
    if campaign.get("schema") != CAMPAIGN_SCHEMA:
        errors.append(f"campaign schema={campaign.get('schema')}")
    if campaign.get("campaign_id") != "transplant":
        errors.append("campaign_id is not transplant")
    if campaign.get("kind") != "transplant":
        errors.append("kind is not transplant")
    if campaign.get("required_human_launches") != 1:
        errors.append("required_human_launches")
    owner = str(campaign.get("owner_prompt") or "")
    if owner != TRANSPLANT_PROMPT:
        errors.append(f"owner_prompt={owner}")
    expected = lots_from_matrix(matrix)
    expected_ids = [lot["responsibility_id"] for lot in expected]
    lots = campaign.get("lots") or []
    actual_ids = [str(lot.get("responsibility_id") or "") for lot in lots]
    if actual_ids != expected_ids:
        errors.append(f"lots != matrix transplant rows {actual_ids} vs {expected_ids}")
    counts = campaign_counts(campaign)
    declared = campaign.get("counts") or {}
    for key in ("pending", "claimed", "complete"):
        if key not in declared or int(declared[key]) != counts[key]:
            errors.append(f"counts.{key} {declared.get(key)} != {counts[key]}")
    if int(declared.get("total") or 0) != len(lots):
        errors.append(f"counts.total {declared.get('total')} != {len(lots)}")
    if not lots:
        if not str(campaign.get("empty_reason") or matrix.get("transplants_empty_reason") or "").strip():
            errors.append("empty campaign needs empty_reason")
    order_ids = [str(lot.get("responsibility_id") or "") for lot in lots]
    sorted_ids = [
        str(lot.get("responsibility_id") or "")
        for lot in sorted(lots, key=lambda item: (int(item.get("order") or 0), str(item.get("responsibility_id") or "")))
    ]
    if order_ids != sorted_ids:
        errors.append("lots not ordered by dependencia/valor")
    protected = set(PROTECTED_REJECTS)
    drained = campaign_is_drained(campaign)
    for lot in lots:
        rid = str(lot.get("responsibility_id") or "")
        if rid in protected:
            errors.append(f"protected reject {rid} re-entered transplant queue")
        if lot.get("status") not in {"pending", "claimed", "complete"}:
            errors.append(f"{rid}: lot status {lot.get('status')!r}")
        if drained and lot.get("status") != "complete":
            errors.append(f"{rid}: drained campaign lot not complete")
        if drained and lot.get("status") == "complete":
            if not str(lot.get("terminal") or "").strip():
                errors.append(f"{rid}: complete lot missing terminal")
        if str(lot.get("decision") or "") in REUSE_ADAPT:
            if not str(lot.get("pieza_que_se_retira") or "").strip():
                errors.append(f"{rid}: lot missing pieza_que_se_retira")
        tokens = _batch_tokens(lot.get("transplant_batch"))
        if str(lot.get("decision") or "") in REUSE_ADAPT and tokens is not None and tokens >= BATCH_CAP:
            errors.append(f"{rid}: lot transplant_batch {tokens} >= {BATCH_CAP}")
    next_human = str(campaign.get("next_human_prompt") or "")
    expected_next = closeout_next_human_prompt(campaign)
    if next_human != expected_next:
        errors.append(f"campaign next_human_prompt={next_human} expected {expected_next}")
    if DECIDE_PROMPT in next_human:
        errors.append("campaign remits to 09.5.9")
    if drained and TRANSPLANT_PROMPT in next_human:
        errors.append("campaign remits to 09.5.10")
    if counts["claimed"] and not lots:
        errors.append("orphan claimed lots on empty campaign")
    if repo is not None:
        orphans = index_orphan_transplant_claims(repo)
        if orphans:
            errors.append(f"orphan claimed {orphans[:8]}")
    return errors


def validate_transplant_closeout(
    campaign: dict[str, Any],
    matrix: dict[str, Any],
    *,
    repo: Path = REPO,
) -> list[str]:
    """09.5.10 terminal: drained campaign, next is 11A, no self-remit."""
    errors = validate_campaign(campaign, matrix, repo=repo)
    if str(matrix.get("next_human_prompt") or "") != closeout_next_human_prompt(campaign):
        if campaign_is_drained(campaign):
            errors.append(
                f"matrix next_human_prompt={matrix.get('next_human_prompt')} "
                f"expected {REVALIDATE_PROMPT}"
            )
    ledger_path = transplant_ledger_path(repo)
    if not ledger_path.is_file():
        errors.append("missing transplant-09.5.10 ledger")
    else:
        ledger = load_json(ledger_path)
        next_prompt = str(ledger.get("next_prompt") or "")
        if next_prompt != REVALIDATE_PROMPT:
            errors.append(f"ledger next_prompt={next_prompt}")
        if TRANSPLANT_PROMPT in next_prompt:
            errors.append("ledger remits to 09.5.10")
        if ledger.get("status") != "complete":
            errors.append(f"ledger status={ledger.get('status')}")
        raw = ledger_path.read_text(encoding="utf-8").casefold()
        if "c:\\users\\" in raw or "d:\\perfil\\" in raw:
            errors.append("ledger contains absolute personal path")
    handoff = repo / HANDOFF_REL
    if not handoff.is_file():
        errors.append("missing HANDOFF.md")
    else:
        text = handoff.read_text(encoding="utf-8")
        if REVALIDATE_PROMPT not in text.replace("\\", "/"):
            errors.append("handoff does not name 09.5.11A")
        siguiente = text
        marker = "## Siguiente accion recomendada"
        if marker in text:
            siguiente = text.split(marker, 1)[1]
        if "09.5.10_TRASPLANTAR_LOTE.md" in siguiente.replace("\\", "/"):
            errors.append("handoff next remits to 09.5.10")
    return errors
