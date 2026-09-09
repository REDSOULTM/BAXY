"""Declarative, non-downloading discovery of BAXY's machine-local assets."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DESCRIPTOR = REPOSITORY_ROOT / "assets.manifest.json"
_MAX_DESCRIPTOR_BYTES = 64 * 1024
_TOKEN_RE = re.compile(r"\$\{([A-Z_]+)\}")


class AssetDescriptorError(ValueError):
    """The versioned descriptor or the machine-local override is invalid."""


@dataclass(frozen=True)
class AssetResolution:
    name: str
    path: Path | None
    candidates: tuple[Path, ...]
    required: bool
    repair: str

    @property
    def found(self) -> bool:
        return self.path is not None


def _read_object(path: Path, *, maximum_bytes: int) -> dict[str, Any]:
    try:
        if path.stat().st_size <= 0 or path.stat().st_size > maximum_bytes:
            raise AssetDescriptorError(f"asset_descriptor_size_invalid:{path}")
        value = json.loads(path.read_text(encoding="utf-8"))
    except AssetDescriptorError:
        raise
    except (OSError, UnicodeError, ValueError) as error:
        raise AssetDescriptorError(f"asset_descriptor_invalid:{path}") from error
    if not isinstance(value, dict):
        raise AssetDescriptorError(f"asset_descriptor_not_object:{path}")
    return value


def _token_values(repository_root: Path) -> dict[str, str | None]:
    return {
        "REPOSITORY_ROOT": str(repository_root),
        "LOCALAPPDATA": os.environ.get("LOCALAPPDATA"),
        "USERPROFILE": os.environ.get("USERPROFILE") or str(Path.home()),
        "BAXY_ASSETS_ROOT": os.environ.get("BAXY_ASSETS_ROOT"),
    }


def _expand_candidate(template: str, repository_root: Path) -> Path | None:
    values = _token_values(repository_root)
    unresolved = False

    def replace(match: re.Match[str]) -> str:
        nonlocal unresolved
        value = values.get(match.group(1))
        if not value:
            unresolved = True
            return ""
        return value

    expanded = _TOKEN_RE.sub(replace, template)
    if unresolved or _TOKEN_RE.search(expanded):
        return None
    try:
        return Path(expanded).expanduser().resolve(strict=False)
    except (OSError, RuntimeError, ValueError):
        return None


def _override_path(
    descriptor: dict[str, Any],
    repository_root: Path,
) -> tuple[Path | None, str]:
    local = descriptor.get("local_override")
    if not isinstance(local, dict):
        raise AssetDescriptorError("asset_descriptor_local_override_invalid")
    environment = local.get("environment")
    template = local.get("default")
    schema = local.get("schema")
    if not all(isinstance(value, str) and value for value in (environment, template, schema)):
        raise AssetDescriptorError("asset_descriptor_local_override_invalid")
    configured = os.environ.get(environment)
    if configured:
        return Path(configured).expanduser().resolve(strict=False), schema
    return _expand_candidate(template, repository_root), schema


def load_asset_descriptor(
    descriptor_path: Path = DEFAULT_DESCRIPTOR,
    *,
    repository_root: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    descriptor_path = descriptor_path.resolve(strict=False)
    repository_root = (repository_root or descriptor_path.parent).resolve(strict=False)
    descriptor = _read_object(descriptor_path, maximum_bytes=_MAX_DESCRIPTOR_BYTES)
    if descriptor.get("schema") != "baxy-assets-v1" or descriptor.get("version") != 1:
        raise AssetDescriptorError("asset_descriptor_schema_invalid")
    assets = descriptor.get("assets")
    if not isinstance(assets, dict) or not assets:
        raise AssetDescriptorError("asset_descriptor_assets_invalid")

    override_path, override_schema = _override_path(descriptor, repository_root)
    override_assets: dict[str, Any] = {}
    if override_path is not None and override_path.is_file():
        override = _read_object(override_path, maximum_bytes=_MAX_DESCRIPTOR_BYTES)
        if set(override) != {"schema", "assets"} or override.get("schema") != override_schema:
            raise AssetDescriptorError(f"asset_override_schema_invalid:{override_path}")
        raw_assets = override.get("assets")
        if not isinstance(raw_assets, dict):
            raise AssetDescriptorError(f"asset_override_assets_invalid:{override_path}")
        unknown = set(raw_assets) - set(assets)
        if unknown:
            raise AssetDescriptorError(
                "asset_override_unknown_assets:" + ",".join(sorted(unknown))
            )
        override_assets = raw_assets
    return descriptor, override_assets


def resolve_asset(
    name: str,
    *,
    descriptor_path: Path = DEFAULT_DESCRIPTOR,
    repository_root: Path | None = None,
    explicit: str | Path | None = None,
) -> AssetResolution:
    repository_root = (repository_root or descriptor_path.resolve().parent).resolve(
        strict=False
    )
    descriptor, overrides = load_asset_descriptor(
        descriptor_path,
        repository_root=repository_root,
    )
    definition = descriptor["assets"].get(name)
    if not isinstance(definition, dict):
        raise AssetDescriptorError(f"asset_unknown:{name}")
    kind = definition.get("kind")
    required = definition.get("required")
    environment = definition.get("environment")
    templates = definition.get("candidates")
    repair = definition.get("repair")
    required_files = definition.get("required_files", [])
    if (
        kind not in {"file", "directory"}
        or not isinstance(required, bool)
        or not isinstance(environment, str)
        or not isinstance(templates, list)
        or not all(isinstance(item, str) and item for item in templates)
        or not isinstance(repair, str)
        or not isinstance(required_files, list)
        or not all(isinstance(item, str) and item for item in required_files)
    ):
        raise AssetDescriptorError(f"asset_definition_invalid:{name}")

    raw_candidates: list[str | Path] = []
    if explicit is not None and str(explicit).strip():
        raw_candidates.append(explicit)
    configured = os.environ.get(environment)
    if configured:
        raw_candidates.append(configured)
    local = overrides.get(name, [])
    if isinstance(local, str):
        raw_candidates.append(local)
    elif isinstance(local, list) and all(isinstance(item, str) for item in local):
        raw_candidates.extend(local)
    elif local:
        raise AssetDescriptorError(f"asset_override_value_invalid:{name}")
    raw_candidates.extend(templates)

    candidates: list[Path] = []
    seen: set[str] = set()
    for raw in raw_candidates:
        candidate = (
            _expand_candidate(str(raw), repository_root)
            if "${" in str(raw)
            else Path(raw).expanduser().resolve(strict=False)
        )
        if candidate is None:
            continue
        key = os.path.normcase(str(candidate))
        if key in seen:
            continue
        seen.add(key)
        candidates.append(candidate)

    selected: Path | None = None
    for candidate in candidates:
        valid = candidate.is_file() if kind == "file" else candidate.is_dir()
        if valid and kind == "directory":
            valid = all((candidate / relative).is_file() for relative in required_files)
        if valid:
            selected = candidate.resolve(strict=True)
            break
    return AssetResolution(name, selected, tuple(candidates), required, repair)


__all__ = [
    "AssetDescriptorError",
    "AssetResolution",
    "DEFAULT_DESCRIPTOR",
    "load_asset_descriptor",
    "resolve_asset",
]
