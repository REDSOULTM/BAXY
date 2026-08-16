"""Create the blind v4 turn-policy seal from the untouched v3 reserve.

Only source identifiers and frozen attempt metadata are decoded.  Holdout
text, labels, expected outcomes, and model-facing result payloads remain
opaque.  The complete predecessor chain is rebuilt before the 1,032-ID v3
reserve is ranked into an 848-ID v4 final set and a 184-ID blind reserve.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence

from blind_reset_turn_evidence_final_seal import (
    DEFAULT_HOLDOUT,
    canonical_sha256,
    file_sha256,
    list_sha256,
    repo_identity,
)
from blind_reset_turn_evidence_final_seal_v3 import (
    DEFAULT_FAILED_JOURNAL as DEFAULT_V2_FAILED_JOURNAL,
    DEFAULT_FAILED_REPORT as DEFAULT_V2_FAILED_REPORT,
    DEFAULT_OUTPUT as DEFAULT_V3_SEAL,
    DEFAULT_V1_SEAL,
    DEFAULT_V2_SEAL,
    PRODUCTION_RULE as V3_PRODUCTION_RULE,
    SCHEMA as V3_SCHEMA,
    _after_object_value,
    _decode_string,
    _read_key,
    _skip_json_value,
    _skip_whitespace,
    build_reset_seal as build_v3_seal,
    extract_failed_attempt_case_ids,
    extract_journal_identity,
    v3_source_id_digest,
)


REPO = Path(__file__).resolve().parents[1]
DEFAULT_FAILED_REPORT = (
    REPO
    / "artifacts"
    / "product"
    / "turn_policy_gate.v3-final-technical-failure.json"
)
DEFAULT_FAILED_JOURNAL = (
    REPO
    / "artifacts"
    / "product"
    / "turn_policy_gate.v3-final-technical-failure.jsonl"
)
DEFAULT_OUTPUT = (
    REPO / "tests" / "data" / "turn_evidence_final_seal.v4.json"
)

SCHEMA = "baxy.turn-evidence-final-seal.v4"
INCIDENT = "baxy.turn-policy-final-v3-technical-failure.2026-07-24.v1"

PRODUCTION_RULE = {
    "algorithm": (
        "verified_predecessor_blind_reserve_then_"
        "sha256_rank_ascending_take_n"
    ),
    "digest_input": "utf8(salt) || 0x00 || utf8(source_id)",
    "failed_attempt_report_sha256": (
        "47e61fea7399be5898ed3a24d10197c986cff93c7c37822c4c2183896636fef1"
    ),
    "failed_attempt_report_schema": "baxy.turn-policy-ab-gate.v1",
    "failed_attempt_report_complete": False,
    "failed_attempt_report_completed_measured_calls": 310,
    "failed_attempt_expected_measured_calls": 1720,
    "failed_attempt_journal_sha256": (
        "d99534074936aeb99e4b65d70fb1ad4c034e2d46f28263aba18460ece8c5df6f"
    ),
    "failed_attempt_fingerprint": (
        "00532ca64b048b885157e762f2e0affab958baa8a6bcca4cfbb5ec61cc837c4f"
    ),
    "failed_attempt_journal_rows": 313,
    "failed_attempt_journal_schema": "baxy.turn-policy-ab-result.v1",
    "failed_attempt_journal_arms": ["baseline"],
    "failed_attempt_nonempty_error_rows": 1,
    "failed_attempt_selected_holdout_rows": 848,
    "failed_attempt_selected_holdout_source_ids_sha256": (
        "87c2f9e0bfcadf29d172e0c5a498bba3b517ce10bdcea55c50670f83df2bcc1b"
    ),
    "failed_attempt_selected_contextual_rows": 12,
    "ordering": "digest_bytes_ascending_then_source_id_utf8",
    "predecessor_v3_seal_sha256": (
        "ba5c9c488286295607aaaaafab9e99dc9b192fa7e8e9ccb71a05c6eec0e5788e"
    ),
    "predecessor_v3_final_source_ids_sha256": (
        "87c2f9e0bfcadf29d172e0c5a498bba3b517ce10bdcea55c50670f83df2bcc1b"
    ),
    "predecessor_v3_blind_reserve_source_ids_sha256": (
        "de36d3762d9dbbcbfdd6fbb06c926178aa6fc84eac5824f26bf05580f22d45d8"
    ),
    "salt": "baxy-turn-policy-final-reset-v4",
    "source_pool": "verified_v3_blind_reserve",
    "take_rows": 848,
}
PRODUCTION_RULE_DECLARATION_SHA256 = (
    "76f77061330729426e5fd0b063c37991aed4d63c7b83665d4c369cbe4e979807"
)

_REPORT_SELECTION_FIELDS: Mapping[str, type] = {
    "expected_measured_calls": int,
    "completed_measured_calls": int,
    "selected_holdout": int,
    "selected_contextual": int,
}
_REPORT_CLEANLINESS_FIELDS: Mapping[str, type] = {
    "selection_scope": str,
    "seal_schema": str,
    "seal_sha256": str,
    "sealed_final_source_ids_sha256": str,
    "evaluated_holdout_source_ids_sha256": str,
    "blind_manifest_rebuilt": bool,
}


def v4_source_id_digest(source_id: str, *, salt: str) -> bytes:
    return hashlib.sha256(
        salt.encode("utf-8") + b"\0" + source_id.encode("utf-8")
    ).digest()


def _require_mapping(value: Any, *, name: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} no es objeto")
    return value


def _decode_selected_scalar(
    raw: bytes,
    start: int,
    end: int,
    *,
    field: str,
    expected_type: type,
) -> Any:
    if expected_type is str:
        return _decode_string(
            raw,
            start,
            end,
            field=field,
            line_number=1,
        )
    try:
        value = json.loads(raw[start:end].decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{field} inválido en reporte fallido") from error
    if expected_type is int:
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"{field} no es entero en reporte fallido")
    elif expected_type is bool:
        if not isinstance(value, bool):
            raise ValueError(f"{field} no es booleano en reporte fallido")
    else:
        raise TypeError(f"tipo selectivo no soportado: {expected_type}")
    return value


def _extract_selected_object(
    raw: bytes,
    index: int,
    *,
    name: str,
    fields: Mapping[str, type],
) -> tuple[dict[str, Any], int]:
    index = _skip_whitespace(raw, index)
    if index >= len(raw) or raw[index] != 0x7B:
        raise ValueError(f"{name} no es objeto en reporte fallido")
    index += 1
    selected: dict[str, Any] = {}
    seen: set[str] = set()
    while True:
        index = _skip_whitespace(raw, index)
        if index < len(raw) and raw[index] == 0x7D:
            index += 1
            break
        key, index = _read_key(raw, index)
        if key in seen:
            raise ValueError(f"clave duplicada en {name}: {key}")
        seen.add(key)
        index = _skip_whitespace(raw, index)
        if index >= len(raw) or raw[index] != 0x3A:
            raise ValueError(f"falta ':' en {name}")
        value_start = _skip_whitespace(raw, index + 1)
        value_end = _skip_json_value(raw, value_start, line_number=1)
        if key in fields:
            selected[key] = _decode_selected_scalar(
                raw,
                value_start,
                value_end,
                field=f"{name}.{key}",
                expected_type=fields[key],
            )
        index, finished = _after_object_value(
            raw,
            value_end,
            line_number=1,
        )
        if finished:
            break
    missing = set(fields) - set(selected)
    if missing:
        raise ValueError(
            f"faltan campos selectivos en {name}: {sorted(missing)}"
        )
    return selected, index


def extract_failed_report_identity(path: Path) -> dict[str, Any]:
    """Decode attempt identity while every case expectation stays opaque."""

    raw = path.read_bytes()
    index = _skip_whitespace(raw, 0)
    if index >= len(raw) or raw[index] != 0x7B:
        raise ValueError("el reporte fallido no es objeto")
    index += 1
    selected: dict[str, Any] = {}
    seen: set[str] = set()
    while True:
        index = _skip_whitespace(raw, index)
        if index < len(raw) and raw[index] == 0x7D:
            index += 1
            break
        key, index = _read_key(raw, index)
        if key in seen:
            raise ValueError(f"clave duplicada en reporte: {key}")
        seen.add(key)
        index = _skip_whitespace(raw, index)
        if index >= len(raw) or raw[index] != 0x3A:
            raise ValueError("falta ':' tras clave del reporte")
        value_start = _skip_whitespace(raw, index + 1)
        if key == "selection":
            value, value_end = _extract_selected_object(
                raw,
                value_start,
                name="selection",
                fields=_REPORT_SELECTION_FIELDS,
            )
            selected["selection"] = value
        elif key == "cleanliness":
            value, value_end = _extract_selected_object(
                raw,
                value_start,
                name="cleanliness",
                fields=_REPORT_CLEANLINESS_FIELDS,
            )
            selected["cleanliness"] = value
        else:
            value_end = _skip_json_value(raw, value_start, line_number=1)
            if key in {"schema", "fingerprint"}:
                selected[key] = _decode_string(
                    raw,
                    value_start,
                    value_end,
                    field=key,
                    line_number=1,
                )
            elif key == "complete":
                selected[key] = _decode_selected_scalar(
                    raw,
                    value_start,
                    value_end,
                    field=key,
                    expected_type=bool,
                )
        index, finished = _after_object_value(
            raw,
            value_end,
            line_number=1,
        )
        if finished:
            break
    if _skip_whitespace(raw, index) != len(raw):
        raise ValueError("bytes extra tras el reporte fallido")
    required = {"schema", "fingerprint", "complete", "selection", "cleanliness"}
    if set(selected) != required:
        raise ValueError("identidad incompleta en reporte fallido")
    return selected


def validate_failed_journal(
    journal_lines: Sequence[bytes],
    *,
    selected_case_ids: set[str],
    rule: Mapping[str, Any],
) -> list[dict[str, str]]:
    """Authenticate journal identity without decoding model-facing payloads."""

    rows = [
        extract_journal_identity(line, line_number=line_number)
        for line_number, line in enumerate(journal_lines, 1)
    ]
    pairs = [(row["arm"], row["case_id"]) for row in rows]
    expected_arms = set(rule["failed_attempt_journal_arms"])
    if (
        len(rows) != int(rule["failed_attempt_journal_rows"])
        or len(pairs) != len(set(pairs))
        or any(
            row["schema"] != rule["failed_attempt_journal_schema"]
            or row["fingerprint"] != rule["failed_attempt_fingerprint"]
            or row["arm"] not in expected_arms
            or row["case_id"] not in selected_case_ids
            for row in rows
        )
        or {row["arm"] for row in rows} != expected_arms
        or sum(bool(row["error"]) for row in rows)
        != int(rule["failed_attempt_nonempty_error_rows"])
    ):
        raise ValueError("el journal no acredita el intento v3 congelado")
    return rows


def validate_rule(rule: Mapping[str, Any]) -> None:
    if dict(rule) != PRODUCTION_RULE:
        raise ValueError("regla v4 no soportada")
    if canonical_sha256(rule) != PRODUCTION_RULE_DECLARATION_SHA256:
        raise ValueError("hash de declaración v4 inesperado")


def _load_source_ids(
    value: Any,
    *,
    name: str,
    expected_rows: int | None = None,
    expected_sha256: str | None = None,
) -> list[str]:
    section = _require_mapping(value, name=name)
    raw = section.get("source_ids")
    if not isinstance(raw, list) or not all(
        isinstance(source_id, str) and source_id for source_id in raw
    ):
        raise ValueError(f"IDs inválidos en {name}")
    source_ids = sorted(raw)
    if len(source_ids) != len(set(source_ids)):
        raise ValueError(f"IDs duplicados en {name}")
    if expected_rows is not None and len(source_ids) != expected_rows:
        raise ValueError(f"conteo inesperado en {name}")
    stored_hash = section.get("source_ids_sha256")
    if list_sha256(source_ids) != stored_hash:
        raise ValueError(f"hash de IDs inválido en {name}")
    if expected_sha256 is not None and stored_hash != expected_sha256:
        raise ValueError(f"identidad de IDs inesperada en {name}")
    return source_ids


def build_reset_seal(
    holdout_path: Path,
    v3_seal_path: Path,
    *,
    v2_seal_path: Path = DEFAULT_V2_SEAL,
    v1_seal_path: Path = DEFAULT_V1_SEAL,
    v2_failed_report_path: Path = DEFAULT_V2_FAILED_REPORT,
    v2_failed_journal_path: Path = DEFAULT_V2_FAILED_JOURNAL,
    failed_report_path: Path = DEFAULT_FAILED_REPORT,
    failed_journal_path: Path = DEFAULT_FAILED_JOURNAL,
    rule: Mapping[str, Any] = PRODUCTION_RULE,
) -> dict[str, Any]:
    """Rebuild v3 and derive v4 solely from authenticated identifiers."""

    holdout_path = holdout_path.resolve(strict=True)
    v1_seal_path = v1_seal_path.resolve(strict=True)
    v2_seal_path = v2_seal_path.resolve(strict=True)
    v3_seal_path = v3_seal_path.resolve(strict=True)
    v2_failed_report_path = v2_failed_report_path.resolve(strict=True)
    v2_failed_journal_path = v2_failed_journal_path.resolve(strict=True)
    failed_report_path = failed_report_path.resolve(strict=True)
    failed_journal_path = failed_journal_path.resolve(strict=True)
    validate_rule(rule)

    if file_sha256(v3_seal_path) != rule["predecessor_v3_seal_sha256"]:
        raise ValueError("cambiaron los bytes del sello v3")
    if file_sha256(failed_report_path) != rule["failed_attempt_report_sha256"]:
        raise ValueError("cambiaron los bytes del reporte fallido v3")
    if file_sha256(failed_journal_path) != rule["failed_attempt_journal_sha256"]:
        raise ValueError("cambiaron los bytes del journal fallido v3")

    rebuilt_v3 = build_v3_seal(
        holdout_path,
        v2_seal_path,
        v1_seal_path=v1_seal_path,
        failed_report_path=v2_failed_report_path,
        failed_journal_path=v2_failed_journal_path,
    )
    stored_v3 = json.loads(v3_seal_path.read_text(encoding="utf-8"))
    if stored_v3 != rebuilt_v3:
        raise ValueError("el sello v3 no coincide con su reconstrucción")
    if (
        stored_v3.get("schema") != V3_SCHEMA
        or stored_v3.get("contains_text_or_labels") is not False
        or stored_v3.get("evaluation", {}).get("performed_by_generator")
        is not False
    ):
        raise ValueError("identidad del sello v3 inválida")

    v3_final_ids = _load_source_ids(
        stored_v3.get("final"),
        name="v3.final",
        expected_rows=848,
        expected_sha256=rule[
            "predecessor_v3_final_source_ids_sha256"
        ],
    )
    v3_reserve_identity = _require_mapping(
        stored_v3.get("blind_reserve"),
        name="v3.blind_reserve",
    )
    if (
        v3_reserve_identity.get("rows") != 1032
        or v3_reserve_identity.get("source_ids_sha256")
        != rule["predecessor_v3_blind_reserve_source_ids_sha256"]
    ):
        raise ValueError("identidad de la reserva ciega v3 inválida")

    # Reconstruct the reserve IDs without ever opening holdout row content.
    stored_v2 = json.loads(v2_seal_path.read_text(encoding="utf-8"))
    v2_final_ids = _load_source_ids(
        stored_v2.get("final"),
        name="v2.final",
        expected_rows=2728,
    )
    v2_attempted_ids, _ = extract_failed_attempt_case_ids(
        v2_failed_report_path
    )
    v3_eligible = sorted(set(v2_final_ids) - set(v2_attempted_ids))
    if len(v3_eligible) != 1880:
        raise ValueError("el pool elegible v3 no contiene 1.880 IDs")
    v3_ranked = sorted(
        v3_eligible,
        key=lambda source_id: (
            v3_source_id_digest(
                source_id,
                salt=str(V3_PRODUCTION_RULE["salt"]),
            ),
            source_id.encode("utf-8"),
        ),
    )
    expected_v3_final = sorted(
        v3_ranked[: int(V3_PRODUCTION_RULE["take_rows"])]
    )
    v3_reserve_ranked = v3_ranked[
        int(V3_PRODUCTION_RULE["take_rows"]) :
    ]
    v3_reserve = sorted(v3_reserve_ranked)
    if expected_v3_final != v3_final_ids:
        raise ValueError("el final v3 no coincide con su ranking ciego")
    if (
        len(v3_reserve) != 1032
        or list_sha256(v3_reserve)
        != v3_reserve_identity.get("source_ids_sha256")
        or list_sha256(v3_reserve_ranked)
        != v3_reserve_identity.get("ranked_source_ids_sha256")
    ):
        raise ValueError("la reserva v3 no coincide con su reconstrucción")

    attempted_ids, contextual_ids = extract_failed_attempt_case_ids(
        failed_report_path
    )
    attempted_set = set(attempted_ids)
    v3_final_set = set(v3_final_ids)
    v3_reserve_set = set(v3_reserve)
    if (
        len(attempted_ids)
        != int(rule["failed_attempt_selected_holdout_rows"])
        or list_sha256(attempted_ids)
        != rule["failed_attempt_selected_holdout_source_ids_sha256"]
        or len(contextual_ids)
        != int(rule["failed_attempt_selected_contextual_rows"])
        or attempted_set != v3_final_set
        or attempted_set & v3_reserve_set
    ):
        raise ValueError("el intento v3 no coincide exactamente con su final")

    report_identity = extract_failed_report_identity(failed_report_path)
    selection = report_identity["selection"]
    cleanliness = report_identity["cleanliness"]
    if (
        report_identity["schema"] != rule["failed_attempt_report_schema"]
        or report_identity["fingerprint"]
        != rule["failed_attempt_fingerprint"]
        or report_identity["complete"]
        is not rule["failed_attempt_report_complete"]
        or selection["expected_measured_calls"]
        != int(rule["failed_attempt_expected_measured_calls"])
        or selection["completed_measured_calls"]
        != int(rule["failed_attempt_report_completed_measured_calls"])
        or selection["selected_holdout"] != len(attempted_ids)
        or selection["selected_contextual"] != len(contextual_ids)
        or cleanliness["selection_scope"] != "sealed_final_v3_only"
        or cleanliness["seal_schema"] != V3_SCHEMA
        or cleanliness["seal_sha256"]
        != rule["predecessor_v3_seal_sha256"]
        or cleanliness["sealed_final_source_ids_sha256"]
        != rule["predecessor_v3_final_source_ids_sha256"]
        or cleanliness["evaluated_holdout_source_ids_sha256"]
        != rule["predecessor_v3_final_source_ids_sha256"]
        or cleanliness["blind_manifest_rebuilt"] is not True
    ):
        raise ValueError("el reporte no acredita el intento v3 congelado")

    selected_case_ids = {
        *(f"holdout:{source_id}" for source_id in attempted_ids),
        *contextual_ids,
    }
    journal_lines = [
        line.strip()
        for line in failed_journal_path.read_bytes().splitlines()
        if line.strip()
    ]
    journal_rows = validate_failed_journal(
        journal_lines,
        selected_case_ids=selected_case_ids,
        rule=rule,
    )
    journal_pairs = sorted(
        f"{row['arm']}\0{row['case_id']}" for row in journal_rows
    )

    salt = str(rule["salt"])
    ranked = sorted(
        v3_reserve,
        key=lambda source_id: (
            v4_source_id_digest(source_id, salt=salt),
            source_id.encode("utf-8"),
        ),
    )
    take_rows = int(rule["take_rows"])
    selected_ranked = ranked[:take_rows]
    reserve_ranked = ranked[take_rows:]
    selected = sorted(selected_ranked)
    reserve = sorted(reserve_ranked)
    selected_set = set(selected)
    reserve_set = set(reserve)
    if (
        len(selected) != 848
        or len(reserve) != 184
        or selected_set & reserve_set
        or selected_set | reserve_set != v3_reserve_set
        or selected_set & v3_final_set
    ):
        raise AssertionError("la partición v4 no preserva la reserva v3")

    rule_value = dict(rule)
    cutoff_digest = v4_source_id_digest(
        selected_ranked[-1],
        salt=salt,
    ).hex()
    v2_predecessor = _require_mapping(
        stored_v3.get("predecessor"),
        name="v3.predecessor",
    )
    return {
        "schema": SCHEMA,
        "generator": (
            "scripts/blind_reset_turn_evidence_final_seal_v4.py"
        ),
        "rule": rule_value,
        "rule_declaration_sha256": canonical_sha256(rule_value),
        "holdout": dict(
            _require_mapping(stored_v3.get("holdout"), name="v3.holdout")
        ),
        "predecessor": {
            "repo_path": repo_identity(v3_seal_path),
            "sha256": file_sha256(v3_seal_path),
            "schema": stored_v3["schema"],
            "final_rows": len(v3_final_ids),
            "final_source_ids_sha256": list_sha256(v3_final_ids),
            "blind_reserve_rows": len(v3_reserve),
            "blind_reserve_source_ids_sha256": list_sha256(v3_reserve),
        },
        "policy_calibration": {
            "repo_path": v2_predecessor["repo_path"],
            "sha256": v2_predecessor["sha256"],
            "schema": v2_predecessor["schema"],
            "final_rows": v2_predecessor["final_rows"],
            "final_source_ids_sha256": v2_predecessor[
                "final_source_ids_sha256"
            ],
        },
        "failed_attempt": {
            "incident": INCIDENT,
            "report_repo_path": repo_identity(failed_report_path),
            "report_sha256": file_sha256(failed_report_path),
            "report_checkpoint_completed_measured_calls": selection[
                "completed_measured_calls"
            ],
            "expected_measured_calls": selection[
                "expected_measured_calls"
            ],
            "journal_repo_path": repo_identity(failed_journal_path),
            "journal_sha256": file_sha256(failed_journal_path),
            "journal_rows": len(journal_rows),
            "journal_schema": rule["failed_attempt_journal_schema"],
            "journal_fingerprint": rule["failed_attempt_fingerprint"],
            "journal_arms": sorted({row["arm"] for row in journal_rows}),
            "journal_unique_case_arm_pairs": len(journal_pairs),
            "journal_case_arm_pairs_sha256": list_sha256(journal_pairs),
            "journal_nonempty_error_rows": sum(
                bool(row["error"]) for row in journal_rows
            ),
            "selected_holdout_rows": len(attempted_ids),
            "selected_holdout_source_ids_sha256": list_sha256(
                attempted_ids
            ),
            "selected_contextual_rows": len(contextual_ids),
            "selected_contextual_source_ids_sha256": list_sha256(
                contextual_ids
            ),
        },
        "eligible_pool": {
            "definition": rule_value["source_pool"],
            "rows": len(v3_reserve),
            "source_ids_sha256": list_sha256(v3_reserve),
        },
        "final": {
            "rows": len(selected),
            "source_ids_sha256": list_sha256(selected),
            "ranked_source_ids_sha256": list_sha256(selected_ranked),
            "selection_cutoff_digest_sha256": cutoff_digest,
            "source_ids": selected,
        },
        "blind_reserve": {
            "rows": len(reserve),
            "source_ids_sha256": list_sha256(reserve),
            "ranked_source_ids_sha256": list_sha256(reserve_ranked),
        },
        "audit": {
            "predecessor_chain_rebuilt": True,
            "failed_v3_selection_equals_predecessor_final": (
                attempted_set == v3_final_set
            ),
            "failed_v3_selection_reserve_overlap_rows": len(
                attempted_set & v3_reserve_set
            ),
            "final_predecessor_final_overlap_rows": len(
                selected_set & v3_final_set
            ),
            "selected_reserve_overlap_rows": len(
                selected_set & reserve_set
            ),
            "eligible_partition_complete": (
                selected_set | reserve_set == v3_reserve_set
            ),
            "only_predecessor_blind_reserve_used": (
                selected_set <= v3_reserve_set
            ),
        },
        "evaluation": {
            "performed_by_generator": False,
            "scores_present": False,
        },
        "contains_text_or_labels": False,
    }


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(
        f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    )
    try:
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Resella ciegamente la reserva v3 intacta sin decodificar "
            "texto, labels ni expected del holdout."
        )
    )
    parser.add_argument("--holdout", type=Path, default=DEFAULT_HOLDOUT)
    parser.add_argument("--v1-seal", type=Path, default=DEFAULT_V1_SEAL)
    parser.add_argument("--v2-seal", type=Path, default=DEFAULT_V2_SEAL)
    parser.add_argument("--v3-seal", type=Path, default=DEFAULT_V3_SEAL)
    parser.add_argument(
        "--v2-failed-report",
        type=Path,
        default=DEFAULT_V2_FAILED_REPORT,
    )
    parser.add_argument(
        "--v2-failed-journal",
        type=Path,
        default=DEFAULT_V2_FAILED_JOURNAL,
    )
    parser.add_argument(
        "--failed-report",
        type=Path,
        default=DEFAULT_FAILED_REPORT,
    )
    parser.add_argument(
        "--failed-journal",
        type=Path,
        default=DEFAULT_FAILED_JOURNAL,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    seal = build_reset_seal(
        args.holdout,
        args.v3_seal,
        v2_seal_path=args.v2_seal,
        v1_seal_path=args.v1_seal,
        v2_failed_report_path=args.v2_failed_report,
        v2_failed_journal_path=args.v2_failed_journal,
        failed_report_path=args.failed_report,
        failed_journal_path=args.failed_journal,
    )
    output = args.output.resolve()
    if args.check:
        if not output.is_file():
            raise SystemExit("falta el sello final v4")
        existing = json.loads(output.read_text(encoding="utf-8"))
        if existing != seal:
            raise SystemExit("el sello final v4 no coincide")
    else:
        write_json_atomic(output, seal)
    print(
        json.dumps(
            {
                "schema": seal["schema"],
                "rows": seal["final"]["rows"],
                "source_ids_sha256": seal["final"][
                    "source_ids_sha256"
                ],
                "blind_reserve_rows": seal["blind_reserve"]["rows"],
                "blind_reserve_source_ids_sha256": seal[
                    "blind_reserve"
                ]["source_ids_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if canonical_sha256(PRODUCTION_RULE) != PRODUCTION_RULE_DECLARATION_SHA256:
    raise RuntimeError("la regla v4 predeclarada no coincide con su hash")


if __name__ == "__main__":
    raise SystemExit(main())
