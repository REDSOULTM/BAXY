"""The catalog the Core sends in ``catalog.configure``: operations, installed applications and games, validated, and
the planner resources built from them.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Callable

from .llm_startup import LlmStartupFailure
from .effect_intent import build_game_catalog_index
from .planner import PlannerCatalog, PlannerContractError
from .skill_registry import SkillRegistry
from .sidecar_budgets import CATALOG_LLM_WARMUP_SECONDS


_OPERATION_NAME = re.compile(r"^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*)+$")
_KNOWN_RISKS = {
    "external_communication",
    "forbidden_destructive",
    "installation",
    "low_reversible",
    "monetary",
    "privacy_sensitive",
    "read_only",
    "recoverable_delete",
    "session_disruption",
    "work_loss",
}


def configure_tools(capabilities: object) -> list[dict]:
    """Valida el catálogo recibido del hello autenticado del core."""
    if not isinstance(capabilities, list) or not 1 <= len(capabilities) <= 256:
        raise PlannerContractError("catálogo ausente o fuera de límite")
    names: set[str] = set()
    tools: list[dict] = []
    for capability in capabilities:
        if not isinstance(capability, dict) or set(capability) != {
            "argumentsSchema",
            "description",
            "name",
            "risk",
        }:
            raise PlannerContractError("capacidad con forma no canónica")
        name = capability.get("name")
        description = capability.get("description")
        schema = capability.get("argumentsSchema")
        risk = capability.get("risk")
        if (
            not isinstance(name, str)
            or _OPERATION_NAME.fullmatch(name) is None
            or name in names
            or not isinstance(description, str)
            or not description.strip()
            or len(description) > 4096
            or not isinstance(schema, dict)
            or risk not in _KNOWN_RISKS
        ):
            raise PlannerContractError("capacidad inválida o duplicada")
        names.add(name)
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": name.replace(".", "_"),
                    "canonical_name": name,
                    "description": description,
                    "parameters": schema,
                    "risk": risk,
                },
            },
        )
    return tools


def configure_application_catalog(value: object) -> tuple[str, ...]:
    """Validate a bounded OS-authenticated app-name snapshot."""

    if value is None:
        return ()
    if not isinstance(value, dict) or set(value) != {
        "version",
        "verified",
        "complete",
        "names",
    }:
        raise PlannerContractError("catálogo de aplicaciones con forma inválida")
    if (
        type(value.get("version")) is not int
        or value.get("version") != 1
        or value.get("verified") is not True
        or value.get("complete") is not True
        or not isinstance(value.get("names"), list)
    ):
        raise PlannerContractError("catálogo de aplicaciones inválido")
    names = value["names"]
    if len(names) > 2_048:
        raise PlannerContractError("catálogo de aplicaciones fuera de límite")
    retained: list[str] = []
    normalized: set[str] = set()
    total_bytes = 0
    for name in names:
        if (
            not isinstance(name, str)
            or not name.strip()
            or any(character.isspace() and character not in " \t" for character in name)
            or any(unicodedata.category(character) == "Cc" for character in name)
        ):
            raise PlannerContractError("nombre de aplicación inválido")
        encoded = name.encode("utf-8")
        total_bytes += len(encoded)
        if len(encoded) > 512 or total_bytes > 262_144:
            raise PlannerContractError("catálogo de aplicaciones fuera de límite")
        key = " ".join(
            "".join(
                character
                for character in unicodedata.normalize(
                    "NFKD",
                    name.casefold(),
                )
                if not unicodedata.combining(character)
            ).split()
        )
        if not key or key in normalized:
            continue
        normalized.add(key)
        retained.append(name)
    return tuple(retained)


def configure_game_catalog(value: object) -> tuple[tuple[str, str, str], ...]:
    """Validate a bounded Core-authenticated installed-game snapshot."""

    if value is None:
        return ()
    if not isinstance(value, dict) or set(value) != {
        "version",
        "verified",
        "complete",
        "entries",
    }:
        raise PlannerContractError("catálogo de juegos con forma inválida")
    entries = value.get("entries")
    if type(value.get("version")) is not int or value.get("version") != 1:
        raise PlannerContractError("versión de catálogo de juegos inválida")
    if not isinstance(entries, list) or len(entries) > 4_096:
        raise PlannerContractError("catálogo de juegos fuera de límite")
    if value.get("verified") is False:
        if value.get("complete") is not False or entries:
            raise PlannerContractError("catálogo de juegos no verificado inválido")
        return ()
    if value.get("verified") is not True or value.get("complete") is not True:
        raise PlannerContractError("catálogo de juegos incompleto")
    retained: list[tuple[str, str, str]] = []
    total_bytes = 0
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {
            "provider",
            "appId",
            "name",
        }:
            raise PlannerContractError("entrada de catálogo de juegos inválida")
        provider = entry.get("provider")
        app_id = entry.get("appId")
        name = entry.get("name")
        if not all(isinstance(item, str) for item in (provider, app_id, name)):
            raise PlannerContractError("identidad de juego inválida")
        total_bytes += sum(
            len(item.encode("utf-8")) for item in (provider, app_id, name)
        )
        if total_bytes > 512 * 1024:
            raise PlannerContractError("catálogo de juegos fuera de límite")
        retained.append((provider, app_id, name))
    try:
        build_game_catalog_index(retained)
    except (TypeError, ValueError) as error:
        raise PlannerContractError("catálogo de juegos inválido") from error
    return tuple(retained)


def _create_planner_resources(
    tools: list[dict],
    encoder: Callable[..., Any] | None = None,
) -> tuple[PlannerCatalog, SkillRegistry]:
    """Build a usable lexical snapshot, optionally promoted with E5 vectors."""

    catalog = PlannerCatalog(tools, encoder=encoder)
    skills = SkillRegistry.load_default(
        [tool.name for tool in catalog.tools],
        encoder=encoder,
    )
    return catalog, skills


def _require_catalog_llm_ready(
    llm: Any | None,
    timeout: float = CATALOG_LLM_WARMUP_SECONDS,
) -> None:
    """Authenticate catalog readiness against the model warmup result.

    r22: a failed warmup raises with its cause (VRAM, RAM, the server's exit,
    time) so the catalog reply carries it instead of a bare runtime failure.
    """

    if llm is not None and not llm.wait_warmup(timeout):
        failure_reader = getattr(llm, "startup_failure", None)
        failure = failure_reader() if callable(failure_reader) else None
        if failure is None:
            failure = LlmStartupFailure("tiempo", "the LLM was not available for the catalog")
        raise failure
