"""Build the two private corpora of user turns observed by BAXY/Gemma.

The canonical historical corpus mixes runtime user turns with development prompts,
curated cases, tests and document examples. This projection keeps only user turns
captured by the product runtime or the local Gemma session store. It deliberately
excludes Codex development conversations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tests" / "data"
SOURCE_MESSAGES = DATA / "historical_messages.jsonl"
SOURCE_MAPPING = DATA / "historical_message_mapping.jsonl"
MANIFEST = DATA / "historical_observed_user_corpora.v1.json"

LEVEL_1_NAME = "historical_observed_product_turns.v1.jsonl"
LEVEL_2_NAME = "historical_observed_user_missions.v1.jsonl"
OBSERVED_ORIGIN = "observed_user"
PRODUCT_SOURCE_PREFIXES = ("probando_gemma4/", "gemma4_local/")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_source_rows(path: Path) -> list[tuple[dict[str, Any], bytes]]:
    rows: list[tuple[dict[str, Any], bytes]] = []
    with path.open("rb") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            if not raw_line.strip():
                continue
            try:
                row = json.loads(raw_line)
            except json.JSONDecodeError as error:
                raise RuntimeError(f"Invalid JSON at {path}:{line_number}") from error
            rows.append((row, raw_line))
    return rows


def read_mapping(path: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row, _ in read_source_rows(path):
        message_id = str(row.get("message_id") or "")
        if not message_id or message_id in result:
            raise RuntimeError(f"Missing or duplicate message_id in {path}: {message_id}")
        result[message_id] = row
    return result


def is_observed_product_turn(row: dict[str, Any]) -> bool:
    source = str(row.get("source") or "")
    return row.get("origin") == OBSERVED_ORIGIN and source.startswith(
        PRODUCT_SOURCE_PREFIXES
    )


def contract_signature(message: dict[str, Any], mapping: dict[str, Any]) -> str:
    payload = {
        "acceptance_scope": mapping.get("acceptance_scope"),
        "class": message.get("class"),
        "denied_operations": mapping.get("denied_operations") or [],
        "expected_state": message.get("expected_state"),
        "fallback": message.get("fallback"),
        "historical_operations": mapping.get("historical_operations") or [],
        "natural_response": message.get("natural_response"),
        "operations": mapping.get("operations") or [],
        "outcome_type": mapping.get("outcome_type"),
        "plan": mapping.get("plan") or [],
        "provider_roles": mapping.get("provider_roles") or [],
        "risk": mapping.get("risk") or {},
        "status": mapping.get("status"),
        "success_evidence": message.get("success_evidence") or [],
        "verification": mapping.get("verification") or [],
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def write_projection(path: Path, rows: list[tuple[dict[str, Any], bytes]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        for _, raw_line in rows:
            handle.write(raw_line if raw_line.endswith(b"\n") else raw_line + b"\n")
    temporary.replace(path)


def level_report(
    *,
    logical_path: str,
    output_path: Path,
    rows: list[tuple[dict[str, Any], bytes]],
    mappings: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    messages = [row for row, _ in rows]
    message_ids = [str(row["message_id"]) for row in messages]
    missing_mappings = sorted(set(message_ids).difference(mappings))
    if missing_mappings:
        raise RuntimeError(
            f"Observed corpus has {len(missing_mappings)} messages without mapping"
        )
    return {
        "path": logical_path,
        "row_count": len(messages),
        "unique_message_ids": len(set(message_ids)),
        "unique_text_sha256": len({str(row["text_sha256"]) for row in messages}),
        "class_counts": dict(sorted(Counter(row["class"] for row in messages).items())),
        "language_counts": dict(
            sorted(Counter(row["language"] for row in messages).items())
        ),
        "operation_counts": dict(
            sorted(
                Counter(
                    operation
                    for row in messages
                    for operation in (row.get("operations") or [])
                ).items()
            )
        ),
        "possible_chain_rows": sum(bool(row.get("possible_chain")) for row in messages),
        "source_family_counts": dict(
            sorted(
                Counter(str(row["source"]).split("/", 1)[0] for row in messages).items()
            )
        ),
        "dedup_status_counts": dict(
            sorted(Counter(row["dedup_status"] for row in messages).items())
        ),
        "redacted_rows": sum(bool(row.get("redacted")) for row in messages),
        "message_ids_sha256": hashlib.sha256(
            "\n".join(message_ids).encode("utf-8")
        ).hexdigest(),
        "file_sha256": sha256_file(output_path),
        "bytes": output_path.stat().st_size,
    }


def build(
    *,
    source_messages: Path = SOURCE_MESSAGES,
    source_mapping: Path = SOURCE_MAPPING,
    output_dir: Path = DATA,
    manifest_path: Path = MANIFEST,
) -> dict[str, Any]:
    source_rows = read_source_rows(source_messages)
    mappings = read_mapping(source_mapping)
    level_1 = [(row, raw) for row, raw in source_rows if is_observed_product_turn(row)]
    level_2 = [(row, raw) for row, raw in level_1 if row.get("class") == "user_mission"]

    if len({row["message_id"] for row, _ in level_1}) != len(level_1):
        raise RuntimeError("Level 1 contains duplicate message_id values")

    contract_groups: dict[str, set[str]] = defaultdict(set)
    for row, _ in level_1:
        mapping = mappings.get(str(row["message_id"]))
        if mapping is None:
            raise RuntimeError(f"No acceptance mapping for {row['message_id']}")
        contract_groups[str(row["text_sha256"])].add(contract_signature(row, mapping))
    conflicts = sorted(key for key, values in contract_groups.items() if len(values) > 1)
    if conflicts:
        raise RuntimeError(
            f"{len(conflicts)} identical observed literals have divergent contracts"
        )

    level_1_path = output_dir / LEVEL_1_NAME
    level_2_path = output_dir / LEVEL_2_NAME
    write_projection(level_1_path, level_1)
    write_projection(level_2_path, level_2)

    level_1_ids = {row["message_id"] for row, _ in level_1}
    level_2_ids = {row["message_id"] for row, _ in level_2}
    if not level_2_ids < level_1_ids:
        raise RuntimeError("Level 2 must be a strict subset of level 1")

    manifest = {
        "schema_version": 1,
        "scope": "private_observed_user_turns_addressed_to_baxy_or_gemma",
        "authority": {
            "messages_path": "tests/data/historical_messages.jsonl",
            "messages_file_sha256": sha256_file(source_messages),
            "mapping_path": "tests/data/historical_message_mapping.jsonl",
            "mapping_file_sha256": sha256_file(source_mapping),
            "cutoff_utc": "2026-07-14T10:51:49.1612548Z",
        },
        "selection": {
            "origin": OBSERVED_ORIGIN,
            "included_source_prefixes": list(PRODUCT_SOURCE_PREFIXES),
            "excluded_source_prefix": "codex/",
            "level_2_class": "user_mission",
            "duplicates": "preserved_as_real_occurrences",
        },
        "levels": {
            "level_1_all_observed_product_turns": level_report(
                logical_path=f"tests/data/{LEVEL_1_NAME}",
                output_path=level_1_path,
                rows=level_1,
                mappings=mappings,
            ),
            "level_2_actionable_user_missions": level_report(
                logical_path=f"tests/data/{LEVEL_2_NAME}",
                output_path=level_2_path,
                rows=level_2,
                mappings=mappings,
            ),
        },
        "contract_consistency": {
            "unique_literals_checked": len(contract_groups),
            "conflicting_unique_literals": 0,
            "rule": "contract equality is diagnostic only; every real occurrence requires its own replay and verdict",
        },
        "privacy": {
            "classification": "private_local_project_data",
            "publish_as_dataset": False,
            "generated_jsonl_versioned": False,
        },
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-messages", type=Path, default=SOURCE_MESSAGES)
    parser.add_argument("--source-mapping", type=Path, default=SOURCE_MAPPING)
    parser.add_argument("--output-dir", type=Path, default=DATA)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = build(
        source_messages=args.source_messages.resolve(),
        source_mapping=args.source_mapping.resolve(),
        output_dir=args.output_dir.resolve(),
        manifest_path=args.manifest.resolve(),
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
