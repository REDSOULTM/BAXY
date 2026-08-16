"""Create a blind v2 final seal after a declared evaluation contamination.

The holdout is scanned with a selective byte parser.  Only the top-level
``split`` and ``source_id`` string values are decoded; every other value is
skipped as opaque bytes.  In particular, this script never decodes test text,
labels, families, provenance, or model outputs.

The v2 selection rule is deliberately fixed in source before the production
artifact is generated:

1. Reconstruct the predecessor v1 exploratory complement from source IDs.
2. Remove every source ID in the immutable contamination declaration.
3. Rank the eligible IDs by a new salted SHA-256 digest.
4. Take the first 2,728 IDs, preserving the predecessor final-set size.

This script seals IDs and provenance only.  It never evaluates the selected
subset.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO = Path(__file__).resolve().parents[1]
DEFAULT_HOLDOUT = (
    REPO / "tests" / "data" / "turn_evidence_public_holdout.v1.jsonl"
)
DEFAULT_OLD_SEAL = (
    REPO / "tests" / "data" / "turn_evidence_final_seal.v1.json"
)
DEFAULT_OUTPUT = (
    REPO / "tests" / "data" / "turn_evidence_final_seal.v2.json"
)

SCHEMA = "baxy.turn-evidence-final-seal.v2"
INCIDENT = "baxy.turn-evidence-test-contamination.2026-07-24.v1"

OLD_SCHEMA = "baxy.turn-evidence-final-seal.v1"
OLD_SALT = "baxy-linear-probe-final-v1"
OLD_THRESHOLD = 128
OLD_RULE = {
    "algorithm": "sha256_first_byte",
    "predicate": "digest[0] >= threshold",
    "salt": OLD_SALT,
    "source_split": "test",
    "threshold": OLD_THRESHOLD,
}

CONTAMINATED_SOURCE_IDS = (
    "massive-v1.1:en-US:0",
    "massive-v1.1:en-US:100",
    "massive-v1.1:en-US:10016",
    "massive-v1.1:en-US:10019",
    "massive-v1.1:en-US:10023",
)
EXPECTED_OLD_FINAL_CONTAMINATED_ROWS = 2
EXPECTED_OLD_COMPLEMENT_CONTAMINATED_ROWS = 3

PRODUCTION_RULE = {
    "algorithm": "sha256_rank_ascending_take_n",
    "digest_input": "utf8(salt) || 0x00 || utf8(source_id)",
    "ordering": "digest_bytes_ascending_then_source_id_utf8",
    "salt": "baxy-turn-evidence-final-reset-v2",
    "source_pool": (
        "predecessor_v1_exploratory_complement_minus_declared_contamination"
    ),
    "take_rows": 2728,
}
PRODUCTION_RULE_DECLARATION_SHA256 = (
    "b06a8ac18cc2bea2b29f628aa5a9a3cf51cede896e50cbf98c8850a0ea27d61d"
)

_JSON_WHITESPACE = frozenset(b" \t\r\n")
_TARGET_HOLDOUT_FIELDS = frozenset(("split", "source_id"))


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def list_sha256(values: Sequence[str]) -> str:
    payload = "".join(f"{value}\n" for value in values).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def repo_identity(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return resolved.name


def _skip_whitespace(raw: bytes, index: int) -> int:
    while index < len(raw) and raw[index] in _JSON_WHITESPACE:
        index += 1
    return index


def _skip_json_string(raw: bytes, index: int, *, line_number: int) -> int:
    if index >= len(raw) or raw[index] != 0x22:
        raise ValueError(
            f"se esperaba string JSON en línea {line_number}, byte {index}"
        )
    index += 1
    while index < len(raw):
        value = raw[index]
        if value == 0x22:
            return index + 1
        if value == 0x5C:
            index += 2
            continue
        if value < 0x20:
            raise ValueError(
                f"control inválido en string JSON, línea {line_number}"
            )
        index += 1
    raise ValueError(f"string JSON truncado en línea {line_number}")


def _skip_json_compound(raw: bytes, index: int, *, line_number: int) -> int:
    opening = raw[index]
    expected = 0x7D if opening == 0x7B else 0x5D
    stack = [expected]
    index += 1
    while index < len(raw) and stack:
        value = raw[index]
        if value == 0x22:
            index = _skip_json_string(raw, index, line_number=line_number)
            continue
        if value == 0x7B:
            stack.append(0x7D)
        elif value == 0x5B:
            stack.append(0x5D)
        elif value in (0x7D, 0x5D):
            if value != stack[-1]:
                raise ValueError(
                    f"contenedor JSON desbalanceado en línea {line_number}"
                )
            stack.pop()
        index += 1
    if stack:
        raise ValueError(f"contenedor JSON truncado en línea {line_number}")
    return index


def _skip_json_value(raw: bytes, index: int, *, line_number: int) -> int:
    index = _skip_whitespace(raw, index)
    if index >= len(raw):
        raise ValueError(f"valor JSON ausente en línea {line_number}")
    if raw[index] == 0x22:
        return _skip_json_string(raw, index, line_number=line_number)
    if raw[index] in (0x7B, 0x5B):
        return _skip_json_compound(raw, index, line_number=line_number)
    start = index
    while index < len(raw) and raw[index] not in (0x2C, 0x7D):
        index += 1
    if not raw[start:index].strip():
        raise ValueError(f"valor JSON vacío en línea {line_number}")
    return index


def _decode_selected_json_string(
    raw: bytes,
    start: int,
    end: int,
    *,
    field: str,
    line_number: int,
) -> str:
    try:
        value = json.loads(raw[start:end].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(
            f"{field} inválido en línea {line_number}"
        ) from error
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} vacío o no-string en línea {line_number}")
    return value


def _extract_selected_top_level_fields(
    raw: bytes,
    *,
    line_number: int,
) -> dict[str, str]:
    """Decode target fields while leaving every non-target value opaque."""

    index = _skip_whitespace(raw, 0)
    if index >= len(raw) or raw[index] != 0x7B:
        raise ValueError(f"fila no objeto en línea {line_number}")
    index += 1
    selected: dict[str, str] = {}
    seen_keys: set[str] = set()
    while True:
        index = _skip_whitespace(raw, index)
        if index < len(raw) and raw[index] == 0x7D:
            index += 1
            break
        key_start = index
        key_end = _skip_json_string(raw, key_start, line_number=line_number)
        try:
            key = json.loads(raw[key_start:key_end].decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError(
                f"clave JSON inválida en línea {line_number}"
            ) from error
        if not isinstance(key, str):
            raise ValueError(f"clave JSON no-string en línea {line_number}")
        if key in seen_keys:
            raise ValueError(
                f"clave JSON duplicada {key!r} en línea {line_number}"
            )
        seen_keys.add(key)
        index = _skip_whitespace(raw, key_end)
        if index >= len(raw) or raw[index] != 0x3A:
            raise ValueError(f"falta ':' tras clave en línea {line_number}")
        value_start = _skip_whitespace(raw, index + 1)
        value_end = _skip_json_value(
            raw,
            value_start,
            line_number=line_number,
        )
        if key in _TARGET_HOLDOUT_FIELDS:
            selected[key] = _decode_selected_json_string(
                raw,
                value_start,
                value_end,
                field=key,
                line_number=line_number,
            )
        index = _skip_whitespace(raw, value_end)
        if index >= len(raw):
            raise ValueError(f"objeto JSON truncado en línea {line_number}")
        if raw[index] == 0x2C:
            index += 1
            continue
        if raw[index] == 0x7D:
            index += 1
            break
        raise ValueError(
            f"se esperaba ',' o '}}' en línea {line_number}, byte {index}"
        )
    if _skip_whitespace(raw, index) != len(raw):
        raise ValueError(f"bytes extra tras objeto en línea {line_number}")
    return selected


def extract_holdout_row_identity(
    raw: bytes,
    *,
    line_number: int,
) -> tuple[str, str]:
    """Decode only ``split`` and ``source_id`` from one holdout row.

    The caller may use the returned identity to decide whether the complete
    row is in scope before decoding any other value.
    """

    fields = _extract_selected_top_level_fields(
        raw.strip(),
        line_number=line_number,
    )
    split = fields.get("split")
    source_id = fields.get("source_id")
    if split is None:
        raise ValueError(f"falta split en línea {line_number}")
    if source_id is None:
        raise ValueError(f"falta source_id en línea {line_number}")
    return split, source_id


def extract_test_source_ids(path: Path) -> list[str]:
    """Return sorted test IDs without decoding any other holdout values."""

    source_ids: list[str] = []
    with path.open("rb") as handle:
        for line_number, line in enumerate(handle, 1):
            raw = line.strip()
            if not raw:
                continue
            split, source_id = extract_holdout_row_identity(
                raw,
                line_number=line_number,
            )
            if split != "test":
                continue
            source_ids.append(source_id)
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("source_id duplicado en split test")
    return sorted(source_ids)


def old_source_id_digest(source_id: str) -> bytes:
    return hashlib.sha256(
        OLD_SALT.encode("utf-8") + b"\0" + source_id.encode("utf-8")
    ).digest()


def v2_source_id_digest(source_id: str, *, salt: str) -> bytes:
    return hashlib.sha256(
        salt.encode("utf-8") + b"\0" + source_id.encode("utf-8")
    ).digest()


def _require_mapping(value: Any, *, name: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} no es objeto")
    return value


def _validate_predecessor(
    old_seal: Mapping[str, Any],
    *,
    holdout_sha256: str,
    source_ids: Sequence[str],
) -> tuple[list[str], list[str]]:
    if old_seal.get("schema") != OLD_SCHEMA:
        raise ValueError("schema del sello predecesor inesperado")
    if old_seal.get("contains_text_or_labels") is not False:
        raise ValueError("el sello predecesor no acredita ausencia de contenido")
    if old_seal.get("rule") != OLD_RULE:
        raise ValueError("regla del sello predecesor inesperada")

    holdout = _require_mapping(old_seal.get("holdout"), name="holdout")
    if holdout.get("sha256") != holdout_sha256:
        raise ValueError("el holdout no coincide con el sello predecesor")
    if holdout.get("test_rows") != len(source_ids):
        raise ValueError("el conteo test no coincide con el sello predecesor")
    if old_seal.get("partition_source_ids_sha256") != list_sha256(source_ids):
        raise ValueError("la partición test no coincide con el sello predecesor")

    selected = [
        source_id
        for source_id in source_ids
        if old_source_id_digest(source_id)[0] >= OLD_THRESHOLD
    ]
    complement = [
        source_id
        for source_id in source_ids
        if old_source_id_digest(source_id)[0] < OLD_THRESHOLD
    ]
    final = _require_mapping(old_seal.get("final"), name="final")
    stored_ids = final.get("source_ids")
    if not isinstance(stored_ids, list) or not all(
        isinstance(source_id, str) for source_id in stored_ids
    ):
        raise ValueError("IDs finales predecesores inválidos")
    if stored_ids != selected:
        raise ValueError("IDs finales predecesores no reproducibles")
    if final.get("rows") != len(selected):
        raise ValueError("conteo final predecesor inválido")
    if final.get("source_ids_sha256") != list_sha256(selected):
        raise ValueError("hash final predecesor inválido")

    old_complement = _require_mapping(
        old_seal.get("exploratory_complement"),
        name="exploratory_complement",
    )
    if old_complement.get("rows") != len(complement):
        raise ValueError("conteo del complemento predecesor inválido")
    if old_complement.get("source_ids_sha256") != list_sha256(complement):
        raise ValueError("hash del complemento predecesor inválido")
    if set(selected) & set(complement):
        raise AssertionError("overlap interno en la partición predecesora")
    if len(selected) + len(complement) != len(source_ids):
        raise AssertionError("la partición predecesora perdió IDs")
    return selected, complement


def validate_rule(rule: Mapping[str, Any]) -> None:
    expected_shape = {
        key: value
        for key, value in PRODUCTION_RULE.items()
        if key != "take_rows"
    }
    actual_shape = {
        key: value
        for key, value in rule.items()
        if key != "take_rows"
    }
    if actual_shape != expected_shape:
        raise ValueError("regla v2 no soportada")
    take_rows = rule.get("take_rows")
    if not isinstance(take_rows, int) or isinstance(take_rows, bool):
        raise ValueError("take_rows v2 inválido")
    if take_rows <= 0:
        raise ValueError("take_rows v2 debe ser positivo")


def build_reset_seal(
    holdout_path: Path,
    old_seal_path: Path,
    *,
    contaminated_source_ids: Sequence[str] = CONTAMINATED_SOURCE_IDS,
    rule: Mapping[str, Any] = PRODUCTION_RULE,
    expected_old_final_contaminated_rows: int = (
        EXPECTED_OLD_FINAL_CONTAMINATED_ROWS
    ),
    expected_old_complement_contaminated_rows: int = (
        EXPECTED_OLD_COMPLEMENT_CONTAMINATED_ROWS
    ),
) -> dict[str, Any]:
    holdout_path = holdout_path.resolve(strict=True)
    old_seal_path = old_seal_path.resolve(strict=True)
    validate_rule(rule)

    contaminated = sorted(contaminated_source_ids)
    if not contaminated or len(contaminated) != len(set(contaminated)):
        raise ValueError("declaración de contaminación vacía o duplicada")

    source_ids = extract_test_source_ids(holdout_path)
    source_id_set = set(source_ids)
    missing_contaminated = set(contaminated) - source_id_set
    if missing_contaminated:
        raise ValueError(
            "la declaración de contaminación contiene IDs fuera de test"
        )

    old_seal = json.loads(old_seal_path.read_text(encoding="utf-8"))
    old_seal = _require_mapping(old_seal, name="old_seal")
    holdout_sha256 = file_sha256(holdout_path)
    old_final, old_complement = _validate_predecessor(
        old_seal,
        holdout_sha256=holdout_sha256,
        source_ids=source_ids,
    )

    contaminated_set = set(contaminated)
    old_final_contaminated = sorted(set(old_final) & contaminated_set)
    old_complement_contaminated = sorted(
        set(old_complement) & contaminated_set
    )
    if (
        len(old_final_contaminated)
        != expected_old_final_contaminated_rows
    ):
        raise ValueError("conteo contaminado en final v1 inesperado")
    if (
        len(old_complement_contaminated)
        != expected_old_complement_contaminated_rows
    ):
        raise ValueError("conteo contaminado en complemento v1 inesperado")
    if (
        set(old_final_contaminated)
        | set(old_complement_contaminated)
        != contaminated_set
    ):
        raise ValueError("la contaminación no está totalmente auditada")

    eligible = sorted(set(old_complement) - contaminated_set)
    take_rows = int(rule["take_rows"])
    if len(eligible) < take_rows:
        raise ValueError("el complemento elegible no alcanza take_rows")
    salt = str(rule["salt"])
    ranked = sorted(
        eligible,
        key=lambda source_id: (
            v2_source_id_digest(source_id, salt=salt),
            source_id.encode("utf-8"),
        ),
    )
    selected_ranked = ranked[:take_rows]
    reserve_ranked = ranked[take_rows:]
    selected = sorted(selected_ranked)
    reserve = sorted(reserve_ranked)

    old_final_set = set(old_final)
    selected_set = set(selected)
    reserve_set = set(reserve)
    if selected_set & old_final_set:
        raise AssertionError("el sello v2 tiene overlap con el final v1")
    if selected_set & contaminated_set:
        raise AssertionError("el sello v2 contiene contaminación declarada")
    if reserve_set & contaminated_set:
        raise AssertionError("la reserva v2 contiene contaminación declarada")
    if selected_set & reserve_set:
        raise AssertionError("el sello v2 tiene overlap con su reserva")
    if selected_set | reserve_set != set(eligible):
        raise AssertionError("la partición v2 perdió IDs elegibles")

    rule_value = dict(rule)
    rule_hash = canonical_sha256(rule_value)
    if (
        rule_value == PRODUCTION_RULE
        and rule_hash != PRODUCTION_RULE_DECLARATION_SHA256
    ):
        raise AssertionError("cambió la declaración criptográfica v2")

    predecessor_final = _require_mapping(old_seal["final"], name="final")
    predecessor_complement = _require_mapping(
        old_seal["exploratory_complement"],
        name="exploratory_complement",
    )
    cutoff_digest = v2_source_id_digest(
        selected_ranked[-1],
        salt=salt,
    ).hex()
    return {
        "schema": SCHEMA,
        "generator": "scripts/blind_reset_turn_evidence_final_seal.py",
        "rule": rule_value,
        "rule_declaration_sha256": rule_hash,
        "holdout": {
            "repo_path": repo_identity(holdout_path),
            "sha256": holdout_sha256,
            "test_rows": len(source_ids),
            "partition_source_ids_sha256": list_sha256(source_ids),
        },
        "predecessor": {
            "repo_path": repo_identity(old_seal_path),
            "sha256": file_sha256(old_seal_path),
            "schema": old_seal["schema"],
            "final_rows": predecessor_final["rows"],
            "final_source_ids_sha256": predecessor_final[
                "source_ids_sha256"
            ],
            "exploratory_complement_rows": predecessor_complement["rows"],
            "exploratory_complement_source_ids_sha256": (
                predecessor_complement["source_ids_sha256"]
            ),
        },
        "contamination": {
            "incident": INCIDENT,
            "declared_rows": len(contaminated),
            "declared_source_ids": contaminated,
            "declared_source_ids_sha256": list_sha256(contaminated),
            "old_final_overlap_rows": len(old_final_contaminated),
            "old_final_overlap_source_ids_sha256": list_sha256(
                old_final_contaminated
            ),
            "old_complement_overlap_rows": len(
                old_complement_contaminated
            ),
            "old_complement_overlap_source_ids_sha256": list_sha256(
                old_complement_contaminated
            ),
            "excluded_from_v2_pool_rows": len(
                old_complement_contaminated
            ),
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
        },
        "audit": {
            "all_declared_contamination_found_in_test": True,
            "old_final_v1_overlap_rows": len(
                selected_set & old_final_set
            ),
            "declared_contamination_overlap_rows": len(
                selected_set & contaminated_set
            ),
            "selected_reserve_overlap_rows": len(
                selected_set & reserve_set
            ),
            "eligible_partition_complete": (
                selected_set | reserve_set == set(eligible)
            ),
            "only_predecessor_unevaluated_complement_used": (
                selected_set <= set(old_complement)
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
            "Resella ciegamente el complemento no evaluado v1, sin "
            "decodificar texto ni labels del holdout."
        )
    )
    parser.add_argument("--holdout", type=Path, default=DEFAULT_HOLDOUT)
    parser.add_argument("--old-seal", type=Path, default=DEFAULT_OLD_SEAL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    seal = build_reset_seal(args.holdout, args.old_seal)
    output = args.output.resolve()
    if args.check:
        if not output.is_file():
            raise SystemExit("falta el sello final v2")
        existing = json.loads(output.read_text(encoding="utf-8"))
        if existing != seal:
            raise SystemExit("el sello final v2 no coincide")
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
                "old_final_v1_overlap_rows": seal["audit"][
                    "old_final_v1_overlap_rows"
                ],
                "declared_contamination_overlap_rows": seal["audit"][
                    "declared_contamination_overlap_rows"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if canonical_sha256(PRODUCTION_RULE) != PRODUCTION_RULE_DECLARATION_SHA256:
    raise RuntimeError("la regla v2 predeclarada no coincide con su hash")


if __name__ == "__main__":
    raise SystemExit(main())
