"""Create grouped train/validation inputs from the public runtime-train pool.

This preparation step deliberately reads only rows already marked ``train`` in
the promoted runtime corpus. Rows without a public split (the local historical
index) are excluded, and any validation/test/final row makes the build fail.
Mission groups and exact-text components stay together so neither translations
nor duplicate wording can cross the development boundary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROW_SCHEMA = "baxy.turn-evidence-record.v1"
MANIFEST_SCHEMA = "baxy.turn-policy-runtime-development-manifest.v1"
PARTITION_ID = "baxy.public-runtime-train-group-split.v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PUBLIC_LICENSES = frozenset({"CC-BY-4.0", "CC-BY-SA-4.0"})


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(value: object, *, pretty: bool = False) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2 if pretty else None,
            separators=None if pretty else (",", ":"),
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _write_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_bytes(payload)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _normalized_text(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("runtime text is not a string")
    normalized = " ".join(
        unicodedata.normalize("NFC", value).casefold().split()
    )
    if not normalized or len(normalized) > 4_096:
        raise ValueError("runtime text is empty or outside bounds")
    return normalized


def _identity(value: object, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 1_024
        or any(unicodedata.category(character) in {"Cc", "Cs"} for character in value)
    ):
        raise ValueError(f"{field} is invalid")
    return value


def _target_signature(row: dict[str, Any]) -> tuple[str, tuple[str, ...]]:
    mode = row.get("mode")
    families = row.get("families")
    if (
        mode not in {"action", "conversation", "plan"}
        or not isinstance(families, list)
        or not all(
            isinstance(family, str)
            and family.isidentifier()
            and family != "memory"
            for family in families
        )
        or families != sorted(set(families))
        or (mode in {"action", "plan"}) != bool(families)
    ):
        raise ValueError("runtime target is not a canonical public turn label")
    return str(mode), tuple(families)


def _load_public_train(path: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    records: list[dict[str, Any]] = []
    excluded: Counter[str] = Counter()
    source_ids: set[str] = set()
    with path.open("r", encoding="utf-8", newline="") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            if not raw_line.strip():
                continue
            try:
                row = json.loads(raw_line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"runtime corpus has invalid JSONL at line {line_number}"
                ) from error
            if not isinstance(row, dict) or row.get("schema") != ROW_SCHEMA:
                raise ValueError("runtime corpus row schema is invalid")
            split = row.get("split")
            provenance = row.get("provenance")
            license_name = (
                provenance.get("license")
                if isinstance(provenance, dict)
                else None
            )
            if split is None:
                excluded["historical_without_public_split"] += 1
                continue
            if split != "train":
                raise ValueError(
                    "runtime source contains a non-train held-out row"
                )
            if license_name not in _PUBLIC_LICENSES:
                raise ValueError("runtime train row is not public evidence")
            source_id = _identity(row.get("source_id"), "source_id")
            _identity(row.get("mission_id"), "mission_id")
            _normalized_text(row.get("text"))
            _target_signature(row)
            if source_id in source_ids:
                raise ValueError("runtime source_id is duplicated")
            source_ids.add(source_id)
            records.append(row)
    if not records:
        raise ValueError("runtime source has no public train rows")
    return records, dict(sorted(excluded.items()))


class _DisjointSet:
    def __init__(self, values: set[str]) -> None:
        self._parent = {value: value for value in values}

    def find(self, value: str) -> str:
        parent = self._parent[value]
        while parent != self._parent[parent]:
            parent = self._parent[parent]
        while value != parent:
            next_value = self._parent[value]
            self._parent[value] = parent
            value = next_value
        return parent

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        first, second = sorted((left_root, right_root))
        self._parent[second] = first


def partition_rows(
    records: list[dict[str, Any]],
    *,
    seed: str,
    validation_fraction: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Partition connected mission/text components deterministically."""

    if (
        not seed
        or not math.isfinite(validation_fraction)
        or not 0.05 <= validation_fraction <= 0.4
    ):
        raise ValueError("development split parameters are invalid")
    missions = {
        _identity(row["mission_id"], "mission_id") for row in records
    }
    groups = _DisjointSet(missions)
    first_mission_for_text: dict[str, str] = {}
    mission_targets: dict[str, set[tuple[str, tuple[str, ...]]]] = defaultdict(set)
    text_targets: dict[str, set[tuple[str, tuple[str, ...]]]] = defaultdict(set)
    text_by_source: dict[str, str] = {}
    for row in records:
        mission_id = str(row["mission_id"])
        text = _normalized_text(row["text"])
        source_id = str(row["source_id"])
        signature = _target_signature(row)
        mission_targets[mission_id].add(signature)
        text_targets[text].add(signature)
        text_by_source[source_id] = text
        previous = first_mission_for_text.setdefault(text, mission_id)
        groups.union(previous, mission_id)
    if any(len(targets) != 1 for targets in mission_targets.values()):
        raise ValueError("parallel rows in one mission disagree on target")
    if any(len(targets) != 1 for targets in text_targets.values()):
        raise ValueError("exact public text has conflicting turn labels")

    components: dict[str, list[str]] = defaultdict(list)
    for mission_id in missions:
        components[groups.find(mission_id)].append(mission_id)
    split_for_mission: dict[str, str] = {}
    for members in components.values():
        component_id = min(members)
        digest = hashlib.sha256(
            PARTITION_ID.encode("ascii")
            + b"\0"
            + seed.encode("utf-8")
            + b"\0"
            + component_id.encode("utf-8")
        ).digest()
        ratio = int.from_bytes(digest[:8], "big") / float(1 << 64)
        split = "validation" if ratio < validation_fraction else "train"
        for mission_id in members:
            split_for_mission[mission_id] = split

    outputs: dict[str, list[dict[str, Any]]] = {
        "train": [],
        "validation": [],
    }
    for source in records:
        row = dict(source)
        row["split"] = split_for_mission[str(row["mission_id"])]
        outputs[str(row["split"])].append(row)
    for rows in outputs.values():
        rows.sort(key=lambda row: (str(row["mission_id"]), str(row["source_id"])))
    if not outputs["train"] or not outputs["validation"]:
        raise ValueError("development partition produced an empty split")

    mission_splits: dict[str, set[str]] = defaultdict(set)
    text_splits: dict[str, set[str]] = defaultdict(set)
    for split, rows in outputs.items():
        for row in rows:
            mission_splits[str(row["mission_id"])].add(split)
            text_splits[text_by_source[str(row["source_id"])]].add(split)
    if any(len(values) != 1 for values in mission_splits.values()):
        raise ValueError("mission group crosses development splits")
    if any(len(values) != 1 for values in text_splits.values()):
        raise ValueError("exact text crosses development splits")

    diagnostics = {
        "components": len(components),
        "missions": len(missions),
        "mission_split_overlap": 0,
        "normalized_text_split_overlap": 0,
        "modes": {
            split: dict(
                sorted(Counter(str(row["mode"]) for row in rows).items())
            )
            for split, rows in outputs.items()
        },
        "rows": {split: len(rows) for split, rows in outputs.items()},
    }
    return outputs["train"], outputs["validation"], diagnostics


def build(args: argparse.Namespace) -> dict[str, Any]:
    source = args.source.resolve(strict=True)
    if _sha256(source) != args.expected_source_sha256:
        raise ValueError("runtime corpus differs from its explicit SHA-256 pin")
    records, excluded = _load_public_train(source)
    if _sha256(source) != args.expected_source_sha256:
        raise ValueError("runtime corpus changed while it was read")
    train, validation, diagnostics = partition_rows(
        records,
        seed=args.seed,
        validation_fraction=args.validation_fraction,
    )
    train_payload = b"".join(_canonical_json(row) for row in train)
    validation_payload = b"".join(
        _canonical_json(row) for row in validation
    )
    _write_atomic(args.train_output, train_payload)
    _write_atomic(args.validation_output, validation_payload)
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "partition_id": PARTITION_ID,
        "source": {
            "file_name": source.name,
            "sha256": args.expected_source_sha256,
            "rows": len(records) + sum(excluded.values()),
        },
        "selection": {
            "public_explicit_train_only": True,
            "historical_rows_used": False,
            "heldout_rows_opened": False,
            "seed_sha256": hashlib.sha256(args.seed.encode("utf-8")).hexdigest(),
            "validation_fraction": args.validation_fraction,
        },
        "excluded": excluded,
        "diagnostics": diagnostics,
        "outputs": {
            "train": {
                "file_name": args.train_output.name,
                "sha256": _sha256(args.train_output),
                "bytes": args.train_output.stat().st_size,
                "rows": len(train),
            },
            "validation": {
                "file_name": args.validation_output.name,
                "sha256": _sha256(args.validation_output),
                "bytes": args.validation_output.stat().st_size,
                "rows": len(validation),
            },
        },
    }
    _write_atomic(args.manifest, _canonical_json(manifest, pretty=True))
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--expected-source-sha256", required=True)
    parser.add_argument("--train-output", type=Path, required=True)
    parser.add_argument("--validation-output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--seed",
        default="baxy-public-runtime-train-development-v1",
    )
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    args = parser.parse_args()
    if (
        _SHA256.fullmatch(args.expected_source_sha256) is None
        or len(
            {
                args.train_output.resolve(),
                args.validation_output.resolve(),
                args.manifest.resolve(),
            }
        )
        != 3
    ):
        parser.error("hash pin or output paths are invalid")
    return args


def main() -> int:
    manifest = build(parse_args())
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
