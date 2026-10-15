"""Valida el lock reproducible y el entorno Python activo de BAXY."""

from __future__ import annotations

import argparse
import importlib.metadata
import platform
import re
import sys
import tomllib
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse


EXPECTED_ENVIRONMENT = (
    "implementation_name == 'cpython' and "
    "sys_platform == 'win32' and platform_machine == 'AMD64'"
)
EXPECTED_REQUIRES_PYTHON = "==3.12.*"
PIN_PATTERN = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)==(?P<version>[^\s;]+)$"
)
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_TOP_LEVEL_FIELDS = {
    "lock-version",
    "environments",
    "requires-python",
    "created-by",
    "packages",
}


class RuntimeLockError(ValueError):
    """Fallo estable de estructura o correspondencia del runtime."""


def normalize_distribution_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def load_constraints(path: Path) -> dict[str, str]:
    constraints: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise RuntimeLockError("constraints_unreadable") from error
    for line in lines:
        candidate = line.strip()
        if not candidate or candidate.startswith("#"):
            continue
        match = PIN_PATTERN.fullmatch(candidate)
        if match is None:
            raise RuntimeLockError("constraint_not_exact")
        name = normalize_distribution_name(match.group("name"))
        if name in constraints:
            raise RuntimeLockError("constraint_duplicate")
        constraints[name] = match.group("version")
    if not constraints:
        raise RuntimeLockError("constraints_empty")
    return constraints


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as stream:
            payload = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise RuntimeLockError("lock_unreadable") from error
    if not isinstance(payload, dict):
        raise RuntimeLockError("lock_invalid")
    return payload


def _validate_wheel_tags(wheel_name: str) -> None:
    parts = wheel_name.removesuffix(".whl").rsplit("-", 3)
    if len(parts) != 4:
        raise RuntimeLockError("lock_wheel_tags")
    python_tag, abi_tag, platform_tag = parts[1:]
    python_tags = set(python_tag.split("."))
    platform_tags = set(platform_tag.split("."))

    if platform_tags == {"any"}:
        if abi_tag != "none" or not python_tags <= {"py2", "py3"}:
            raise RuntimeLockError("lock_wheel_tags")
        if "py3" not in python_tags:
            raise RuntimeLockError("lock_wheel_tags")
        return

    if platform_tags != {"win_amd64"}:
        raise RuntimeLockError("lock_wheel_tags")
    if python_tags == {"cp312"} and abi_tag in {"cp312", "abi3"}:
        return
    if abi_tag == "abi3" and len(python_tags) == 1:
        match = re.fullmatch(r"cp3(?P<minor>[0-9]+)", python_tag)
        if match is not None and 2 <= int(match.group("minor")) <= 12:
            return
    if abi_tag == "none" and "py3" in python_tags:
        return
    raise RuntimeLockError("lock_wheel_tags")


def validate_lock_structure(
    lock_path: Path,
    constraints_path: Path,
) -> dict[str, str]:
    payload = _load_toml(lock_path)
    if set(payload) != EXPECTED_TOP_LEVEL_FIELDS:
        raise RuntimeLockError("lock_fields")
    if payload.get("lock-version") != "1.0":
        raise RuntimeLockError("lock_version")
    if payload.get("created-by") != "pip":
        raise RuntimeLockError("lock_creator")
    if payload.get("requires-python") != EXPECTED_REQUIRES_PYTHON:
        raise RuntimeLockError("lock_python")
    if payload.get("environments") != [EXPECTED_ENVIRONMENT]:
        raise RuntimeLockError("lock_environment")

    packages = payload.get("packages")
    if not isinstance(packages, list) or not packages:
        raise RuntimeLockError("lock_packages")

    locked: dict[str, str] = {}
    for package in packages:
        if not isinstance(package, dict):
            raise RuntimeLockError("lock_package")
        if set(package) != {"name", "version", "wheels"}:
            raise RuntimeLockError("lock_package_fields")
        raw_name = package.get("name")
        version = package.get("version")
        if not isinstance(raw_name, str) or not isinstance(version, str):
            raise RuntimeLockError("lock_package_identity")
        name = normalize_distribution_name(raw_name)
        if name in locked:
            raise RuntimeLockError("lock_package_duplicate")

        wheels = package.get("wheels")
        if not isinstance(wheels, list) or len(wheels) != 1:
            raise RuntimeLockError("lock_wheel_count")
        wheel = wheels[0]
        if not isinstance(wheel, dict):
            raise RuntimeLockError("lock_wheel")
        if set(wheel) not in (
            {"name", "url", "hashes"}, {"name", "path", "hashes"}
        ):
            raise RuntimeLockError("lock_wheel_fields")
        wheel_name = wheel.get("name")
        wheel_source = wheel.get("url", wheel.get("path"))
        hashes = wheel.get("hashes")
        if (
            not isinstance(wheel_name, str)
            or not wheel_name.endswith(".whl")
            or any(character in wheel_name for character in "/\\:")
            or not isinstance(wheel_source, str)
            or not isinstance(hashes, dict)
            or set(hashes) != {"sha256"}
            or not isinstance(hashes["sha256"], str)
            or SHA256_PATTERN.fullmatch(hashes["sha256"]) is None
        ):
            raise RuntimeLockError("lock_wheel_identity")
        wheel_distribution = re.sub(r"[-_.]+", "_", raw_name).lower()
        wheel_version = version.replace("-", "_").lower()
        if not wheel_name.lower().startswith(
            f"{wheel_distribution}-{wheel_version}-"
        ):
            raise RuntimeLockError("lock_wheel_package_mismatch")
        _validate_wheel_tags(wheel_name)
        if "path" in wheel:
            # Bundled, hash-pinned wheels remain portable with the lock. Only
            # direct children of this repository's wheel directory are allowed.
            if wheel_source != f"runtime_wheels/{wheel_name}":
                raise RuntimeLockError("lock_wheel_source")
        else:
            parsed_url = urlparse(wheel_source)
            if (
                parsed_url.scheme != "https"
                or parsed_url.netloc != "files.pythonhosted.org"
                or parsed_url.params
                or parsed_url.query
                or parsed_url.fragment
                or unquote(parsed_url.path.rsplit("/", 1)[-1]) != wheel_name
            ):
                raise RuntimeLockError("lock_wheel_source")
        locked[name] = version

    constraints = load_constraints(constraints_path)
    if locked != constraints:
        raise RuntimeLockError("lock_constraints_mismatch")
    if list(locked) != sorted(locked) or list(constraints) != sorted(constraints):
        raise RuntimeLockError("lock_order")
    return locked


def validate_current_interpreter() -> None:
    if (
        sys.implementation.name != "cpython"
        or sys.version_info[:2] != (3, 12)
        or sys.platform != "win32"
        or platform.machine().upper() != "AMD64"
    ):
        raise RuntimeLockError("interpreter_unsupported")


def validate_installed_distributions(locked: dict[str, str]) -> None:
    installed: dict[str, str] = {}
    for distribution in importlib.metadata.distributions():
        raw_name = distribution.metadata["Name"]
        if not raw_name:
            continue
        name = normalize_distribution_name(raw_name)
        if name in installed:
            raise RuntimeLockError("installed_duplicate")
        installed[name] = distribution.version
    missing = sorted(set(locked) - set(installed))
    mismatched = sorted(
        name
        for name, version in locked.items()
        if name in installed and installed[name] != version
    )
    if missing:
        raise RuntimeLockError("installed_missing")
    if mismatched:
        raise RuntimeLockError("installed_version_mismatch")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Valida el pylock y, por defecto, el runtime Python activo.",
    )
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--constraints", type=Path, required=True)
    parser.add_argument(
        "--structure-only",
        action="store_true",
        help="Valida estructura, plataforma, wheels, hashes y constraints.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        locked = validate_lock_structure(args.lock, args.constraints)
        if not args.structure_only:
            validate_current_interpreter()
            validate_installed_distributions(locked)
    except RuntimeLockError as error:
        print(f"python_runtime_lock_invalid: {error}", file=sys.stderr)
        return 2
    installed = str(not args.structure_only).lower()
    print(
        f"python_runtime_lock_verified: packages={len(locked)}; "
        f"installed={installed}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
