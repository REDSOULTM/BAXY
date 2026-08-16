"""Seal a deterministic final subset without reading labels or model scores."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import uuid
from pathlib import Path
from typing import Any, Sequence


REPO = Path(__file__).resolve().parents[1]
DEFAULT_HOLDOUT = (
    REPO / "tests" / "data" / "turn_evidence_public_holdout.v1.jsonl"
)
DEFAULT_OUTPUT = (
    REPO / "tests" / "data" / "turn_evidence_final_seal.v1.json"
)
SCHEMA = "baxy.turn-evidence-final-seal.v1"
SALT = "baxy-linear-probe-final-v1"
THRESHOLD = 128


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_id_digest(source_id: str) -> bytes:
    return hashlib.sha256(
        SALT.encode("utf-8") + b"\0" + source_id.encode("utf-8")
    ).digest()


def list_sha256(values: Sequence[str]) -> str:
    payload = "".join(f"{value}\n" for value in values).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_seal(path: Path) -> dict[str, Any]:
    path = path.resolve(strict=True)
    source_ids: list[str] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"JSONL inválido en línea {line_number}") from error
            if not isinstance(row, dict):
                raise ValueError(f"fila no objeto en línea {line_number}")
            # Deliberately do not inspect text, mode, families or provenance.
            if row.get("split") != "test":
                continue
            source_id = row.get("source_id")
            if not isinstance(source_id, str) or not source_id:
                raise ValueError(f"source_id inválido en línea {line_number}")
            source_ids.append(source_id)
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("source_id duplicado en split test")
    source_ids.sort()
    selected = [
        source_id
        for source_id in source_ids
        if source_id_digest(source_id)[0] >= THRESHOLD
    ]
    complement = [
        source_id
        for source_id in source_ids
        if source_id_digest(source_id)[0] < THRESHOLD
    ]
    if set(selected) & set(complement):
        raise AssertionError("la partición sellada tiene overlap")
    if len(selected) + len(complement) != len(source_ids):
        raise AssertionError("la partición sellada perdió filas")
    return {
        "schema": SCHEMA,
        "rule": {
            "algorithm": "sha256_first_byte",
            "salt": SALT,
            "source_split": "test",
            "predicate": "digest[0] >= threshold",
            "threshold": THRESHOLD,
        },
        "holdout": {
            "repo_path": "tests/data/turn_evidence_public_holdout.v1.jsonl",
            "sha256": file_sha256(path),
            "test_rows": len(source_ids),
        },
        "final": {
            "rows": len(selected),
            "source_ids_sha256": list_sha256(selected),
            "source_ids": selected,
        },
        "exploratory_complement": {
            "rows": len(complement),
            "source_ids_sha256": list_sha256(complement),
        },
        "partition_source_ids_sha256": list_sha256(source_ids),
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
        description="Sella el subset final sin consultar labels ni scores."
    )
    parser.add_argument("--holdout", type=Path, default=DEFAULT_HOLDOUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    seal = build_seal(args.holdout)
    output = args.output.resolve()
    if args.check:
        if not output.is_file():
            raise SystemExit("falta el sello final")
        existing = json.loads(output.read_text(encoding="utf-8"))
        if existing != seal:
            raise SystemExit("el sello final no coincide")
    else:
        write_json_atomic(output, seal)
    print(
        json.dumps(
            {
                "schema": seal["schema"],
                "rows": seal["final"]["rows"],
                "source_ids_sha256": seal["final"]["source_ids_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
