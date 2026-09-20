"""Load exact, reviewed operation surfaces as proposal-only catalogue aliases."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Mapping


_DATA = Path(__file__).with_name("data") / "catalog_operation_aliases.v1.json"
# The v1 asset keeps the identity sealed by R267 (bound to the R219 catalogue);
# the operations added in C03 carry their aliases in a second asset that is
# loaded with it and bound to the current catalogue by its own test.
_C03_DATA = Path(__file__).with_name("data") / "catalog_operation_aliases.c03.v1.json"
_ASSETS = (_DATA, _C03_DATA)
_OPERATION_NAME = re.compile(r"^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*)+$")


@lru_cache(maxsize=1)
def catalog_operation_aliases() -> Mapping[str, tuple[str, ...]]:
    """Return validated exact aliases; they never add catalogue authority."""

    aliases: dict[str, tuple[str, ...]] = {}
    for asset in _ASSETS:
        _load_alias_asset(asset, aliases)
    return MappingProxyType(aliases)


def _load_alias_asset(asset: Path, aliases: dict[str, tuple[str, ...]]) -> None:
    payload = json.loads(asset.read_text(encoding="utf-8"))
    if (
        not isinstance(payload, dict)
        or payload.get("schema") != "baxy.catalog-operation-aliases.v1"
        or payload.get("authority")
        != "proposal_only_authenticated_catalog_intersection"
    ):
        raise RuntimeError("catalog operation alias asset has an invalid contract")
    rows = payload.get("aliases")
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("catalog operation alias asset is empty")
    loaded = 0
    for row in rows:
        if not isinstance(row, dict) or set(row) != {
            "normalized_text",
            "operations",
            "target_operation",
            "text",
        }:
            raise RuntimeError("catalog operation alias row has an invalid shape")
        normalized = row.get("normalized_text")
        operations = row.get("operations")
        target = row.get("target_operation")
        text = row.get("text")
        if (
            not isinstance(normalized, str)
            or not normalized
            or normalized != " ".join(normalized.split())
            or not isinstance(text, str)
            or not text.strip()
            or not isinstance(target, str)
            or _OPERATION_NAME.fullmatch(target) is None
            or not isinstance(operations, list)
            or not 1 <= len(operations) <= 2
            or not all(
                isinstance(operation, str)
                and _OPERATION_NAME.fullmatch(operation) is not None
                for operation in operations
            )
            or operations[-1] != target
            or normalized in aliases
        ):
            raise RuntimeError("catalog operation alias row is invalid or duplicated")
        aliases[normalized] = tuple(operations)
        loaded += 1
    expected_count = payload.get("alias_count")
    if expected_count != loaded:
        raise RuntimeError("catalog operation alias count changed")


@lru_cache(maxsize=1)
def catalog_operation_alias_pairs() -> tuple[tuple[str, str], ...]:
    """Return ``(target operation, natural text)`` for the validated aliases.

    The domain grounding derived from the catalogue uses these to learn the
    words a person actually says for an operation, which is what lets one
    Spanish description ground an English or code-switched request.
    """

    catalog_operation_aliases()  # validate the asset contract first
    return tuple(
        (str(row["target_operation"]), str(row["text"]))
        for asset in _ASSETS
        for row in json.loads(asset.read_text(encoding="utf-8"))["aliases"]
    )


@lru_cache(maxsize=1)
def _punctuation_invariant_aliases() -> Mapping[str, tuple[str, ...]]:
    aliases: dict[str, tuple[str, ...]] = {}
    for text, operations in catalog_operation_aliases().items():
        key = text.rstrip(" .!?")
        existing = aliases.get(key)
        if existing is not None and existing != operations:
            raise RuntimeError("catalog operation aliases collide without punctuation")
        aliases[key] = operations
    return MappingProxyType(aliases)


def exact_catalog_operation_plan(normalized_text: str) -> tuple[str, ...] | None:
    """Match one complete normalized utterance; prefixes and fuzzy text never match."""

    aliases = catalog_operation_aliases()
    direct = aliases.get(normalized_text)
    if direct is not None:
        return direct
    return _punctuation_invariant_aliases().get(normalized_text.rstrip(" .!?"))
