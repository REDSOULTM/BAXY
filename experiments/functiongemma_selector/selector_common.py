"""Shared, side-effect-free helpers for the FunctionGemma selector spike."""

from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Iterable

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.measure_mind_budget import (  # noqa: E402
    DEFAULT_CORE_CANDIDATES,
    current_core_capabilities,
    discover_core,
)

NO_ACTION_OPERATION = "__no_action__"
TOOL_PREFIX = "baxy_"
CALL_PATTERN = re.compile(
    r"<start_function_call>\s*call:([A-Za-z0-9_]+)\{.*?\}"
    r"<end_function_call>",
    flags=re.DOTALL,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_text(text: str) -> str:
    value = unicodedata.normalize("NFKD", text.casefold())
    value = "".join(character for character in value if not unicodedata.combining(character))
    return " ".join(re.findall(r"[a-z0-9]+", value))


def operation_family(operation: str) -> str:
    return operation.split(".", 1)[0]


def tool_name(operation: str) -> str:
    if operation == NO_ACTION_OPERATION:
        return f"{TOOL_PREFIX}no_action"
    return TOOL_PREFIX + operation.replace(".", "__")


def operation_name(name: str) -> str | None:
    if name == f"{TOOL_PREFIX}no_action":
        return NO_ACTION_OPERATION
    if not name.startswith(TOOL_PREFIX):
        return None
    return name[len(TOOL_PREFIX) :].replace("__", ".")


def load_catalog() -> list[dict[str, Any]]:
    capabilities = current_core_capabilities(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES))
    )
    if not capabilities:
        raise RuntimeError("Core returned an empty catalog")
    return capabilities


def catalog_by_name() -> dict[str, dict[str, Any]]:
    return {str(row["name"]): row for row in load_catalog()}


def family_operations(
    catalog: dict[str, dict[str, Any]], family: str
) -> list[str]:
    return sorted(
        name for name in catalog if operation_family(name) == family
    )


def selection_tools(
    catalog: dict[str, dict[str, Any]], operations: Iterable[str]
) -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    for operation in operations:
        if operation == NO_ACTION_OPERATION:
            description = (
                "Select this only when the message requests no concrete action or "
                "external read covered by the other declared BAXY operations."
            )
        else:
            capability = catalog[operation]
            description = str(capability.get("description") or operation)
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool_name(operation),
                    "description": description,
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        )
    return tools


def assistant_selection(operation: str) -> dict[str, Any]:
    return {
        "role": "assistant",
        "tool_calls": [
            {
                "type": "function",
                "function": {"name": tool_name(operation), "arguments": {}},
            }
        ],
    }


def parse_operations(generated: str) -> list[str]:
    operations: list[str] = []
    for name in CALL_PATTERN.findall(generated):
        operation = operation_name(name)
        if operation is not None:
            operations.append(operation)
    return operations


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
    )
    path.write_text(rendered, encoding="utf-8", newline="\n")

