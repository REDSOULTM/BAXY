"""Attest only CLINC150 development OOS members without decoding its test data."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
SOURCE = Path(r"D:\BAXYRuntime\datasets\clinc150-v1\source\data_oos_plus.json")
OUTPUT = REPO / "artifacts/audit/clinc_oos_development_r251.json"
SOURCE_SHA256 = "bfcca9ae515623541dc1983c94c4ed7cae9d26b42ae47d74b972e51bb6f7a21f"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _array_bytes(raw: bytes, key: bytes) -> bytes:
    marker = b'"' + key + b'"'
    start = raw.find(marker)
    if start < 0:
        raise RuntimeError(f"CLINC key missing: {key.decode('ascii')}")
    start = raw.find(b"[", start + len(marker))
    if start < 0:
        raise RuntimeError(f"CLINC array missing: {key.decode('ascii')}")
    depth = 0
    quoted = False
    escaped = False
    for index in range(start, len(raw)):
        character = raw[index]
        if quoted:
            if escaped:
                escaped = False
            elif character == 92:
                escaped = True
            elif character == 34:
                quoted = False
            continue
        if character == 34:
            quoted = True
        elif character == 91:
            depth += 1
        elif character == 93:
            depth -= 1
            if depth == 0:
                return raw[start : index + 1]
    raise RuntimeError(f"CLINC array is not closed: {key.decode('ascii')}")


def development_rows(path: Path = SOURCE) -> dict[str, list[list[str]]]:
    raw = path.read_bytes()
    positions = {key: raw.find(b'"' + key + b'"') for key in (b"oos_val", b"val", b"train", b"oos_test", b"test", b"oos_train")}
    if any(position < 0 for position in positions.values()) or not (
        positions[b"oos_val"] < positions[b"val"] < positions[b"train"] < positions[b"oos_test"] < positions[b"test"] < positions[b"oos_train"]
    ):
        raise RuntimeError("CLINC member order does not permit opaque-test extraction")
    selected = {
        key.decode("ascii"): json.loads(_array_bytes(raw, key).decode("utf-8"))
        for key in (b"oos_train", b"oos_val")
    }
    if not all(
        isinstance(value, list)
        and all(
            isinstance(row, list)
            and len(row) == 2
            and isinstance(row[0], str)
            and row[1] == "oos"
            for row in value
        )
        for value in selected.values()
    ):
        raise RuntimeError("CLINC development OOS members are malformed")
    return selected


def build(path: Path = SOURCE) -> dict[str, Any]:
    if not path.is_file() or sha256(path) != SOURCE_SHA256:
        raise RuntimeError("CLINC source bytes are absent or do not match the pinned identity")
    rows = development_rows(path)
    if len(rows["oos_train"]) != 250 or len(rows["oos_val"]) != 100:
        raise RuntimeError("unexpected CLINC OOS development cardinality")
    return {
        "schema": "baxy.clinc-oos-development.r251.v1",
        "authority": "read_only_external_development_source_attestation_not_model_training_or_evaluation",
        "source": {"url": "https://raw.githubusercontent.com/clinc/oos-eval/master/data/data_oos_plus.json", "license": "CC-BY-4.0", "path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)},
        "development": {"members_decoded": ["oos_train", "oos_val"], "oos_train_rows": len(rows["oos_train"]), "oos_validation_rows": len(rows["oos_val"]), "texts_retained": False},
        "test_seal": {"members_decoded": False, "test_rows_read": False, "method": "only development arrays are structurally located and UTF-8 decoded; test arrays remain opaque bytes"},
        "constraints": {"model_started": False, "r228_opened": False, "public_holdout_opened": False, "registered_runtime_modified": False, "providers_enabled": False, "effects_executed": 0, "opened_v9": False, "voice_stt_wake_exercised": False},
        "identities": {"program_sha256": sha256(Path(__file__))},
        "next_requirement": "Any candidate must seal its model, new in-catalog development selection, and CLINC train-versus-validation role before importing model weights; CLINC test remains unavailable.",
    }


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing to overwrite attestation: {OUTPUT}")
    OUTPUT.write_bytes((json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
