"""Fingerprint every Python source that can influence the physical wake gate."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable


SCHEMA = "baxy.wake-validation-program-tree.v1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fingerprint_program_tree(
    *,
    repository_root: Path,
    source_roots: Iterable[Path],
) -> dict[str, object]:
    """Return a canonical ledger hash for the gate's complete Python tree."""

    repository = repository_root.resolve(strict=True)
    roots: list[str] = []
    files: dict[str, Path] = {}
    for source_root in source_roots:
        resolved_root = source_root.resolve(strict=True)
        try:
            root_label = resolved_root.relative_to(repository).as_posix()
        except ValueError as error:
            raise ValueError("wake_validation_program_root_outside_repository") from error
        if not resolved_root.is_dir() or resolved_root.is_symlink():
            raise ValueError("wake_validation_program_root_invalid")
        roots.append(root_label)
        for path in resolved_root.rglob("*.py"):
            if not path.is_file() or path.is_symlink():
                continue
            resolved = path.resolve(strict=True)
            try:
                relative = resolved.relative_to(repository).as_posix()
            except ValueError as error:
                raise ValueError(
                    "wake_validation_program_source_outside_repository"
                ) from error
            files[relative] = resolved
    if not files:
        raise ValueError("wake_validation_program_tree_empty")

    digest = hashlib.sha256()
    for relative in sorted(files):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\n")
        digest.update(_sha256(files[relative]).encode("ascii"))
        digest.update(b"\n")
    return {
        "schema": SCHEMA,
        "roots": sorted(set(roots)),
        "pythonFiles": len(files),
        "sha256": digest.hexdigest(),
    }
