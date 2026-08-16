"""Create a blind v3 turn-policy seal after a technical final-gate failure.

The failed v2 gate selected 848 holdout IDs but stopped after an opaque
``turn_runtime_failure``.  Its model-facing results are never used here.
This generator:

1. cryptographically rebuilds and verifies the blind v2 seal;
2. decodes only ``case_id`` strings from the frozen failed-attempt report;
3. removes every selected v2 holdout ID, not merely the calls completed;
4. ranks the remaining 1,880 IDs, seals exactly 848, and preserves 1,032 as
   an unopened reserve without decoding holdout text or labels.

The report and journal bytes are pinned by the production rule.  This script
never evaluates either the removed IDs or the new final pool.
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
    DEFAULT_OLD_SEAL as DEFAULT_V1_SEAL,
    SCHEMA as V2_SCHEMA,
    build_reset_seal as build_v2_seal,
    canonical_sha256,
    file_sha256,
    list_sha256,
    repo_identity,
    _skip_json_string,
    _skip_json_value,
    _skip_whitespace,
)


REPO = Path(__file__).resolve().parents[1]
DEFAULT_V2_SEAL = (
    REPO / "tests" / "data" / "turn_evidence_final_seal.v2.json"
)
DEFAULT_FAILED_REPORT = (
    REPO
    / "artifacts"
    / "product"
    / "turn_policy_gate.v2-final-technical-failure.json"
)
DEFAULT_FAILED_JOURNAL = (
    REPO
    / "artifacts"
    / "product"
    / "turn_policy_gate.v2-final-technical-failure.jsonl"
)
DEFAULT_OUTPUT = (
    REPO / "tests" / "data" / "turn_evidence_final_seal.v3.json"
)

SCHEMA = "baxy.turn-evidence-final-seal.v3"
INCIDENT = "baxy.turn-policy-final-v2-technical-failure.2026-07-24.v1"
TECHNICAL_ERROR = "RuntimeError: request_failed: turn_runtime_failure"

PRODUCTION_RULE = {
    "algorithm": "set_difference_then_sha256_rank_ascending_take_n",
    "digest_input": "utf8(salt) || 0x00 || utf8(source_id)",
    "failed_attempt_report_sha256": (
        "0bdf764a604570500b87495b5181a11757307a30351d4d52152939872605c399"
    ),
    "failed_attempt_journal_sha256": (
        "18eee52d779f3ca96b3eb56ce159ea27097cdb5122d5170242f7636530697409"
    ),
    "failed_attempt_fingerprint": (
        "7147096ec832a79d0df1bdfb8d29357bdf9c0eabfa78d84af1734e0d57224ffd"
    ),
    "failed_attempt_journal_rows": 55,
    "failed_attempt_journal_schema": "baxy.turn-policy-ab-result.v1",
    "failed_attempt_selected_holdout_rows": 848,
    "ordering": "digest_bytes_ascending_then_source_id_utf8",
    "salt": "baxy-turn-policy-final-reset-v3",
    "source_pool": "v2_final_minus_failed_v2_selected_holdout",
    "take_rows": 848,
}
PRODUCTION_RULE_DECLARATION_SHA256 = (
    "d3e241eef042b5d34f4879dafc933d0fc95b1fde7d1699cca9e99924728e958c"
)

def v3_source_id_digest(source_id: str, *, salt: str) -> bytes:
    return hashlib.sha256(
        salt.encode("utf-8") + b"\0" + source_id.encode("utf-8")
    ).digest()


def _require_mapping(value: Any, *, name: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} no es objeto")
    return value


def _decode_string(
    raw: bytes,
    start: int,
    end: int,
    *,
    field: str,
    line_number: int = 1,
) -> str:
    try:
        value = json.loads(raw[start:end].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(
            f"{field} inválido en línea {line_number}"
        ) from error
    if not isinstance(value, str):
        raise ValueError(f"{field} no-string en línea {line_number}")
    return value


def _read_key(
    raw: bytes,
    index: int,
    *,
    line_number: int = 1,
) -> tuple[str, int]:
    start = index
    end = _skip_json_string(raw, start, line_number=line_number)
    return (
        _decode_string(
            raw,
            start,
            end,
            field="clave JSON",
            line_number=line_number,
        ),
        end,
    )


def _after_object_value(
    raw: bytes,
    index: int,
    *,
    line_number: int = 1,
) -> tuple[int, bool]:
    index = _skip_whitespace(raw, index)
    if index >= len(raw):
        raise ValueError(f"objeto JSON truncado en línea {line_number}")
    if raw[index] == 0x2C:
        return index + 1, False
    if raw[index] == 0x7D:
        return index + 1, True
    raise ValueError(
        f"se esperaba ',' o '}}' en línea {line_number}, byte {index}"
    )


def _extract_case_object_id(
    raw: bytes,
    index: int,
) -> tuple[str, int]:
    index = _skip_whitespace(raw, index)
    if index >= len(raw) or raw[index] != 0x7B:
        raise ValueError("cada elemento de cases debe ser objeto")
    index += 1
    case_id: str | None = None
    seen: set[str] = set()
    while True:
        index = _skip_whitespace(raw, index)
        if index < len(raw) and raw[index] == 0x7D:
            index += 1
            break
        key, index = _read_key(raw, index)
        if key in seen:
            raise ValueError(f"clave duplicada en case: {key}")
        seen.add(key)
        index = _skip_whitespace(raw, index)
        if index >= len(raw) or raw[index] != 0x3A:
            raise ValueError("falta ':' tras clave de case")
        value_start = _skip_whitespace(raw, index + 1)
        value_end = _skip_json_value(
            raw,
            value_start,
            line_number=1,
        )
        if key == "case_id":
            if case_id is not None:
                raise ValueError("case_id duplicado")
            case_id = _decode_string(
                raw,
                value_start,
                value_end,
                field="case_id",
            )
            if not case_id:
                raise ValueError("case_id vacío")
        index, finished = _after_object_value(raw, value_end)
        if finished:
            break
    if case_id is None:
        raise ValueError("falta case_id en elemento de cases")
    return case_id, index


def _extract_cases_array(
    raw: bytes,
    index: int,
) -> tuple[list[str], int]:
    index = _skip_whitespace(raw, index)
    if index >= len(raw) or raw[index] != 0x5B:
        raise ValueError("cases no es array")
    index += 1
    case_ids: list[str] = []
    while True:
        index = _skip_whitespace(raw, index)
        if index < len(raw) and raw[index] == 0x5D:
            return case_ids, index + 1
        case_id, index = _extract_case_object_id(raw, index)
        case_ids.append(case_id)
        index = _skip_whitespace(raw, index)
        if index >= len(raw):
            raise ValueError("array cases truncado")
        if raw[index] == 0x2C:
            index += 1
            continue
        if raw[index] == 0x5D:
            return case_ids, index + 1
        raise ValueError("se esperaba ',' o ']' en cases")


def extract_failed_attempt_case_ids(path: Path) -> tuple[list[str], list[str]]:
    """Decode only top-level ``/cases/*/case_id`` values."""

    raw = path.read_bytes()
    index = _skip_whitespace(raw, 0)
    if index >= len(raw) or raw[index] != 0x7B:
        raise ValueError("el reporte fallido no es objeto")
    index += 1
    case_ids: list[str] | None = None
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
        if key == "cases":
            if case_ids is not None:
                raise ValueError("cases duplicado")
            case_ids, value_end = _extract_cases_array(raw, value_start)
        else:
            value_end = _skip_json_value(
                raw,
                value_start,
                line_number=1,
            )
        index, finished = _after_object_value(raw, value_end)
        if finished:
            break
    if _skip_whitespace(raw, index) != len(raw):
        raise ValueError("bytes extra tras el reporte fallido")
    if case_ids is None:
        raise ValueError("falta cases en el reporte fallido")
    if len(case_ids) != 860 or len(case_ids) != len(set(case_ids)):
        raise ValueError("la selección fallida no contiene 860 IDs únicos")

    holdout_prefix = "holdout:"
    holdout_ids = sorted(
        case_id[len(holdout_prefix) :]
        for case_id in case_ids
        if case_id.startswith(holdout_prefix)
    )
    contextual_ids = sorted(
        case_id
        for case_id in case_ids
        if not case_id.startswith(holdout_prefix)
    )
    if len(holdout_ids) != 848 or len(contextual_ids) != 12:
        raise ValueError("la selección fallida no coincide con 848+12")
    return holdout_ids, contextual_ids


def _extract_result_error(
    raw: bytes,
    index: int,
    *,
    line_number: int,
) -> tuple[str, int]:
    index = _skip_whitespace(raw, index)
    if index >= len(raw) or raw[index] != 0x7B:
        raise ValueError(f"result no es objeto en línea {line_number}")
    index += 1
    error_value: str | None = None
    seen: set[str] = set()
    while True:
        index = _skip_whitespace(raw, index)
        if index < len(raw) and raw[index] == 0x7D:
            index += 1
            break
        key, index = _read_key(raw, index, line_number=line_number)
        if key in seen:
            raise ValueError(
                f"clave duplicada en result, línea {line_number}: {key}"
            )
        seen.add(key)
        index = _skip_whitespace(raw, index)
        if index >= len(raw) or raw[index] != 0x3A:
            raise ValueError(f"falta ':' en result, línea {line_number}")
        value_start = _skip_whitespace(raw, index + 1)
        value_end = _skip_json_value(
            raw,
            value_start,
            line_number=line_number,
        )
        if key == "error":
            error_value = _decode_string(
                raw,
                value_start,
                value_end,
                field="result.error",
                line_number=line_number,
            )
        index, finished = _after_object_value(
            raw,
            value_end,
            line_number=line_number,
        )
        if finished:
            break
    if error_value is None:
        raise ValueError(f"falta result.error en línea {line_number}")
    return error_value, index


def extract_journal_identity(
    raw: bytes,
    *,
    line_number: int,
) -> dict[str, str]:
    """Decode journal identity and error only; every model output stays opaque."""

    index = _skip_whitespace(raw, 0)
    if index >= len(raw) or raw[index] != 0x7B:
        raise ValueError(f"journal no-objeto en línea {line_number}")
    index += 1
    selected: dict[str, str] = {}
    seen: set[str] = set()
    while True:
        index = _skip_whitespace(raw, index)
        if index < len(raw) and raw[index] == 0x7D:
            index += 1
            break
        key, index = _read_key(raw, index, line_number=line_number)
        if key in seen:
            raise ValueError(
                f"clave duplicada en journal, línea {line_number}: {key}"
            )
        seen.add(key)
        index = _skip_whitespace(raw, index)
        if index >= len(raw) or raw[index] != 0x3A:
            raise ValueError(f"falta ':' en journal, línea {line_number}")
        value_start = _skip_whitespace(raw, index + 1)
        if key == "result":
            selected["error"], value_end = _extract_result_error(
                raw,
                value_start,
                line_number=line_number,
            )
        else:
            value_end = _skip_json_value(
                raw,
                value_start,
                line_number=line_number,
            )
            if key in {"schema", "fingerprint", "case_id", "arm"}:
                selected[key] = _decode_string(
                    raw,
                    value_start,
                    value_end,
                    field=key,
                    line_number=line_number,
                )
        index, finished = _after_object_value(
            raw,
            value_end,
            line_number=line_number,
        )
        if finished:
            break
    if _skip_whitespace(raw, index) != len(raw):
        raise ValueError(f"bytes extra en journal, línea {line_number}")
    required = {"schema", "fingerprint", "case_id", "arm", "error"}
    if set(selected) != required:
        raise ValueError(f"identidad journal incompleta en línea {line_number}")
    return selected


def validate_failed_journal(
    journal_lines: Sequence[bytes],
    *,
    selected_case_ids: set[str],
    rule: Mapping[str, Any],
) -> list[dict[str, str]]:
    """Authenticate journal structure while leaving model outputs opaque."""

    journal_rows = [
        extract_journal_identity(line, line_number=line_number)
        for line_number, line in enumerate(journal_lines, 1)
    ]
    journal_pairs = [(row["arm"], row["case_id"]) for row in journal_rows]
    technical_error_rows = sum(
        row["error"] == TECHNICAL_ERROR for row in journal_rows
    )
    if (
        len(journal_rows) != int(rule["failed_attempt_journal_rows"])
        or len(journal_pairs) != len(set(journal_pairs))
        or any(
            row["schema"] != rule["failed_attempt_journal_schema"]
            or row["fingerprint"] != rule["failed_attempt_fingerprint"]
            or row["arm"] != "baseline"
            or row["case_id"] not in selected_case_ids
            for row in journal_rows
        )
        or sum(bool(row["error"]) for row in journal_rows) != 1
        or technical_error_rows != 1
    ):
        raise ValueError("el journal no acredita el fallo técnico congelado")
    return journal_rows


def validate_rule(rule: Mapping[str, Any]) -> None:
    if dict(rule) != PRODUCTION_RULE:
        raise ValueError("regla v3 no soportada")
    if canonical_sha256(rule) != PRODUCTION_RULE_DECLARATION_SHA256:
        raise ValueError("hash de declaración v3 inesperado")


def build_reset_seal(
    holdout_path: Path,
    v2_seal_path: Path,
    *,
    v1_seal_path: Path = DEFAULT_V1_SEAL,
    failed_report_path: Path = DEFAULT_FAILED_REPORT,
    failed_journal_path: Path = DEFAULT_FAILED_JOURNAL,
    rule: Mapping[str, Any] = PRODUCTION_RULE,
) -> dict[str, Any]:
    """Build v3 using identities only; no holdout text or label is decoded."""

    holdout_path = holdout_path.resolve(strict=True)
    v1_seal_path = v1_seal_path.resolve(strict=True)
    v2_seal_path = v2_seal_path.resolve(strict=True)
    failed_report_path = failed_report_path.resolve(strict=True)
    failed_journal_path = failed_journal_path.resolve(strict=True)
    validate_rule(rule)

    report_sha256 = file_sha256(failed_report_path)
    journal_sha256 = file_sha256(failed_journal_path)
    if report_sha256 != rule["failed_attempt_report_sha256"]:
        raise ValueError("cambiaron los bytes del reporte fallido")
    if journal_sha256 != rule["failed_attempt_journal_sha256"]:
        raise ValueError("cambiaron los bytes del journal fallido")

    attempted_ids, contextual_ids = extract_failed_attempt_case_ids(
        failed_report_path
    )
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
    technical_error_rows = sum(
        row["error"] == TECHNICAL_ERROR for row in journal_rows
    )
    journal_pairs = [(row["arm"], row["case_id"]) for row in journal_rows]

    rebuilt_v2 = build_v2_seal(holdout_path, v1_seal_path)
    stored_v2 = json.loads(v2_seal_path.read_text(encoding="utf-8"))
    if stored_v2 != rebuilt_v2:
        raise ValueError("el sello v2 no coincide con su reconstrucción")
    if (
        stored_v2.get("schema") != V2_SCHEMA
        or stored_v2.get("contains_text_or_labels") is not False
    ):
        raise ValueError("identidad del sello v2 inválida")

    v2_final = _require_mapping(stored_v2.get("final"), name="v2.final")
    v2_ids_raw = v2_final.get("source_ids")
    if not isinstance(v2_ids_raw, list) or not all(
        isinstance(source_id, str) for source_id in v2_ids_raw
    ):
        raise ValueError("IDs finales v2 inválidos")
    v2_ids = sorted(v2_ids_raw)
    if (
        len(v2_ids) != 2728
        or len(v2_ids) != len(set(v2_ids))
        or list_sha256(v2_ids) != v2_final.get("source_ids_sha256")
    ):
        raise ValueError("partición final v2 inválida")

    attempted_set = set(attempted_ids)
    v2_set = set(v2_ids)
    if not attempted_set <= v2_set:
        raise ValueError("el intento fallido contiene IDs fuera del final v2")
    if len(attempted_ids) != rule["failed_attempt_selected_holdout_rows"]:
        raise ValueError("conteo holdout del intento fallido inesperado")

    eligible = sorted(v2_set - attempted_set)
    if len(eligible) != 1880:
        raise ValueError("la reserva v2 intacta no contiene 1.880 IDs")
    take_rows = int(rule["take_rows"])
    if not 0 < take_rows <= len(eligible):
        raise ValueError("take_rows v3 no cabe en la reserva intacta")
    salt = str(rule["salt"])
    ranked = sorted(
        eligible,
        key=lambda source_id: (
            v3_source_id_digest(source_id, salt=salt),
            source_id.encode("utf-8"),
        ),
    )
    selected_ranked = ranked[:take_rows]
    reserve_ranked = ranked[take_rows:]
    selected = sorted(selected_ranked)
    reserve = sorted(reserve_ranked)
    selected_set = set(selected)
    reserve_set = set(reserve)
    if selected_set & attempted_set:
        raise AssertionError("el sello v3 contiene IDs del intento fallido")
    if selected_set & reserve_set:
        raise AssertionError("el sello v3 solapa su reserva ciega")
    if selected_set | reserve_set | attempted_set != v2_set:
        raise AssertionError("la partición v3 perdió IDs finales v2")

    rule_value = dict(rule)
    rule_hash = canonical_sha256(rule_value)
    cutoff_digest = v3_source_id_digest(
        selected_ranked[-1],
        salt=salt,
    ).hex()
    return {
        "schema": SCHEMA,
        "generator": (
            "scripts/blind_reset_turn_evidence_final_seal_v3.py"
        ),
        "rule": rule_value,
        "rule_declaration_sha256": rule_hash,
        "holdout": dict(_require_mapping(stored_v2["holdout"], name="holdout")),
        "predecessor": {
            "repo_path": repo_identity(v2_seal_path),
            "sha256": file_sha256(v2_seal_path),
            "schema": stored_v2["schema"],
            "final_rows": len(v2_ids),
            "final_source_ids_sha256": list_sha256(v2_ids),
        },
        "failed_attempt": {
            "incident": INCIDENT,
            "report_repo_path": repo_identity(failed_report_path),
            "report_sha256": report_sha256,
            "journal_repo_path": repo_identity(failed_journal_path),
            "journal_sha256": journal_sha256,
            "selected_holdout_rows": len(attempted_ids),
            "selected_holdout_source_ids_sha256": list_sha256(
                attempted_ids
            ),
            "selected_contextual_rows": len(contextual_ids),
            "selected_contextual_source_ids_sha256": list_sha256(
                contextual_ids
            ),
            "completed_journal_rows": len(journal_lines),
            "journal_schema": rule["failed_attempt_journal_schema"],
            "journal_fingerprint": rule["failed_attempt_fingerprint"],
            "journal_unique_case_arm_pairs": len(journal_pairs),
            "technical_error": TECHNICAL_ERROR,
            "technical_error_rows": technical_error_rows,
        },
        "eligible_pool": {
            "definition": rule_value["source_pool"],
            "rows": len(eligible),
            "source_ids_sha256": list_sha256(eligible),
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
            "attempted_v2_selection_overlap_rows": len(
                selected_set & attempted_set
            ),
            "selected_reserve_overlap_rows": len(
                selected_set & reserve_set
            ),
            "v2_partition_complete": (
                selected_set | reserve_set | attempted_set == v2_set
            ),
            "only_unattempted_v2_final_ids_used": selected_set <= v2_set,
            "predecessor_v1_overlap_rows": stored_v2["audit"][
                "old_final_v1_overlap_rows"
            ],
            "declared_contamination_overlap_rows": stored_v2["audit"][
                "declared_contamination_overlap_rows"
            ],
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
            "Resella ciegamente los IDs v2 no seleccionados por el intento "
            "técnico fallido, sin decodificar texto ni labels."
        )
    )
    parser.add_argument("--holdout", type=Path, default=DEFAULT_HOLDOUT)
    parser.add_argument("--v1-seal", type=Path, default=DEFAULT_V1_SEAL)
    parser.add_argument("--v2-seal", type=Path, default=DEFAULT_V2_SEAL)
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
        args.v2_seal,
        v1_seal_path=args.v1_seal,
        failed_report_path=args.failed_report,
        failed_journal_path=args.failed_journal,
    )
    output = args.output.resolve()
    if args.check:
        if not output.is_file():
            raise SystemExit("falta el sello final v3")
        existing = json.loads(output.read_text(encoding="utf-8"))
        if existing != seal:
            raise SystemExit("el sello final v3 no coincide")
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
                "attempted_v2_selection_overlap_rows": seal["audit"][
                    "attempted_v2_selection_overlap_rows"
                ],
                "technical_error_rows": seal["failed_attempt"][
                    "technical_error_rows"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
