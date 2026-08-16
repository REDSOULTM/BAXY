"""Build exact proposal aliases from the reviewed seen-operation surfaces."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable


REPO = Path(__file__).resolve().parents[1]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from baxy_mind.effect_intent import _fold, _strip_request_envelope  # noqa: E402
from baxy_mind.planner import required_predecessors  # noqa: E402
from scripts.catalog_seen_scenarios_v1 import SEEN_UTTERANCES  # noqa: E402
from scripts.measure_mind_budget import (  # noqa: E402
    DEFAULT_CORE_CANDIDATES,
    current_core_capabilities,
    discover_core,
    write_json_atomic,
)


OUTPUT = REPO / "src/baxy_mind/data/catalog_operation_aliases.v1.json"
_OPERATION_NAME = re.compile(r"^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*)+$")


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _plan(operation: str) -> tuple[str, ...]:
    predecessors = required_predecessors(operation)
    return (*predecessors[:1], operation)


def build_payload(capabilities: Iterable[dict[str, Any]]) -> dict[str, Any]:
    catalog = sorted(
        (
            {
                key: capability[key]
                for key in ("name", "description", "argumentsSchema", "risk")
            }
            for capability in capabilities
        ),
        key=lambda capability: str(capability["name"]),
    )
    names = {str(capability["name"]) for capability in catalog}
    if len(names) != len(catalog) or names != set(SEEN_UTTERANCES):
        raise ValueError("reviewed aliases do not match the authenticated catalogue")
    aliases: list[dict[str, Any]] = []
    normalized_seen: set[str] = set()
    for operation in sorted(names):
        if operation.startswith("memory."):
            continue
        _language, text = SEEN_UTTERANCES[operation]
        normalized = _strip_request_envelope(_fold(text)).strip()
        operations = _plan(operation)
        if (
            not normalized
            or normalized in normalized_seen
            or _OPERATION_NAME.fullmatch(operation) is None
            or not set(operations) <= names
        ):
            raise ValueError(f"invalid or duplicate reviewed alias: {operation}")
        normalized_seen.add(normalized)
        aliases.append(
            {
                "normalized_text": normalized,
                "operations": list(operations),
                "target_operation": operation,
                "text": text,
            }
        )
    return {
        "schema": "baxy.catalog-operation-aliases.v1",
        "authority": "proposal_only_authenticated_catalog_intersection",
        "catalog_operations": len(catalog),
        "catalog_sha256": _canonical_hash(catalog),
        "alias_count": len(aliases),
        "excluded_app_memory_operations": sorted(
            name for name in names if name.startswith("memory.")
        ),
        "aliases": aliases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--core", type=Path)
    args = parser.parse_args()
    capabilities = current_core_capabilities(
        discover_core(args.core, candidates=reversed(DEFAULT_CORE_CANDIDATES))
    )
    payload = build_payload(capabilities)
    write_json_atomic(args.output, payload)
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "aliases": payload["alias_count"],
                "catalog_operations": payload["catalog_operations"],
                "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
