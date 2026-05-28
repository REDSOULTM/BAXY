"""Backup & Sync domain tool — extracted from domain_tools.py (R2 sprint
2026-05-28).

Backups locales como archivos ZIP. Restore con políticas overwrite/skip/rename
(default rename, contra zip-slip). Dedupe por SHA-256. Verify con
zipfile.testzip. Gate duro para overwrite (CC-101 / T2-backup_sync-restore-
overwrite).

Funciones extraídas (6):
  backup_sync_tool               (entry, 6 acciones)
  _backup_resolve                (id-or-path -> Path)
  _backup_restore                (zip-slip protected)
  _next_available_path           (helper general, re-exportado para photo lib)
  _backup_dedupe
  _backup_verify

Helpers desde domain_tools (lazy):
  _safe_name, _resources_by_kind, _hard_gate."""
from __future__ import annotations

import shutil
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from ._shared import _err, _ok
from .state import AgentState


__all__ = [
    "backup_sync_tool",
    "_backup_resolve",
    "_backup_restore",
    "_next_available_path",
    "_backup_dedupe",
    "_backup_verify",
]


def backup_sync_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    from .domain_tools import _resources_by_kind, _safe_name
    action = str(args.get("action") or "status").casefold()
    if action == "status":
        return _ok(backend="zipfile", restore_supported=True, dedupe_supported=True, verify_supported=True)
    if action == "list":
        resources = _resources_by_kind(state, "backup", include_closed=bool(args.get("include_closed", False)))
        return _ok(backups=resources, count=len(resources))
    if action == "backup_create":
        src = Path(str(args.get("src") or args.get("path") or "")).expanduser()
        if not src.exists():
            return _err("source path not found", src=str(src))
        out_dir = state.path.parent / "backups"
        out_dir.mkdir(parents=True, exist_ok=True)
        dst = Path(str(args.get("dst") or out_dir / f"{_safe_name(src.name)}_{time.strftime('%Y%m%d_%H%M%S')}.zip")).expanduser()
        dst.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as archive:
            if src.is_file():
                archive.write(src, src.name)
            else:
                for child in src.rglob("*"):
                    if child.is_file():
                        archive.write(child, child.relative_to(src.parent))
        resource = state.register_resource("backup", dst.name, metadata={"src": str(src), "dst": str(dst), "created_at": datetime.now().isoformat(), "size": dst.stat().st_size})
        return _ok(backup=resource.get("resource"), path=str(dst.resolve()), size=dst.stat().st_size)
    if action == "restore":
        return _backup_restore(args, state)
    if action == "dedupe":
        return _backup_dedupe(args)
    if action == "verify":
        return _backup_verify(args, state)
    return _err(
        "unknown backup_sync action", action=action,
        valid_actions=[
            "status", "backup_create", "list", "restore",
            "dedup_scan", "sync",
        ],
        status="needs_user",
    )


def _backup_resolve(args: dict[str, Any], state: AgentState) -> tuple[Path | None, dict[str, Any] | None]:
    """Resolve a backup either from resource id or explicit path."""
    rid = str(args.get("id") or args.get("backup_id") or args.get("resource_id") or "").strip()
    if rid:
        resource = state._load().get("resources", {}).get(rid)
        if resource and resource.get("kind") == "backup":
            path_str = str((resource.get("metadata") or {}).get("dst") or "").strip()
            if path_str:
                p = Path(path_str)
                if p.is_file():
                    return p, resource
    explicit = str(args.get("path") or args.get("backup") or "").strip()
    if explicit:
        p = Path(explicit).expanduser()
        if p.is_file():
            return p, None
    return None, None


def _backup_restore(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    from .domain_tools import _hard_gate
    backup_path, resource = _backup_resolve(args, state)
    if not backup_path:
        return _err("backup not found; pass id (res_*) or path to ZIP")
    if backup_path.suffix.casefold() != ".zip":
        return _err("only .zip backups are supported", path=str(backup_path))
    dst_raw = str(args.get("dst") or args.get("to") or "").strip()
    if dst_raw:
        dst = Path(dst_raw).expanduser()
    else:
        original_src = str((resource or {}).get("metadata", {}).get("src") or "").strip()
        dst = Path(original_src).parent if original_src else Path.cwd()
    dst.mkdir(parents=True, exist_ok=True)
    conflict_policy = str(args.get("conflict") or args.get("on_conflict") or "rename").casefold()
    if conflict_policy not in {"overwrite", "skip", "rename"}:
        return _err("conflict policy must be overwrite|skip|rename")
    preview_only = bool(args.get("preview", False))

    # CC-101 / T2-backup_sync-restore-overwrite: gate duro si overwrite y no es preview.
    if conflict_policy == "overwrite" and not preview_only:
        gate = _hard_gate(
            state,
            tool="backup_sync",
            action="restore",
            args=args,
            reason=f"restore with overwrite will replace existing files at {dst}",
            risk="high",
        )
        if gate is not None:
            return gate

    extracted: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    renamed: list[dict[str, Any]] = []
    overwritten: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    dst_resolved = dst.resolve()

    try:
        with zipfile.ZipFile(backup_path, "r") as archive:
            entries = archive.infolist()
            if preview_only:
                return _ok(
                    preview=True, backup=str(backup_path), dst=str(dst),
                    entries=[{"name": e.filename, "size": e.file_size} for e in entries[:200]],
                    total_entries=len(entries),
                )
            for entry in entries:
                # CC-021 / T2-backup_sync-zip-slip-021: contención bajo dst.
                candidate = (dst / entry.filename).resolve()
                if candidate != dst_resolved and dst_resolved not in candidate.parents:
                    blocked.append({"name": entry.filename, "reason": "zip-slip outside dst"})
                    continue
                if entry.is_dir():
                    candidate.mkdir(parents=True, exist_ok=True)
                    continue
                final_target = candidate
                final_target.parent.mkdir(parents=True, exist_ok=True)
                if final_target.exists():
                    if conflict_policy == "skip":
                        skipped.append({"name": entry.filename})
                        continue
                    if conflict_policy == "rename":
                        final_target = _next_available_path(final_target)
                        renamed.append({"from": entry.filename, "to": str(final_target.relative_to(dst_resolved))})
                    elif conflict_policy == "overwrite":
                        overwritten.append({"name": entry.filename})
                with archive.open(entry, "r") as src_fh, final_target.open("wb") as dst_fh:
                    shutil.copyfileobj(src_fh, dst_fh)
                extracted.append({"name": entry.filename, "size": entry.file_size, "dst": str(final_target)})
    except (zipfile.BadZipFile, OSError) as exc:
        return _err(f"restore failed: {exc}", backup=str(backup_path), dst=str(dst))
    if blocked:
        # Si bloqueamos al menos uno, devolvemos status=failed para que el agente
        # surface el incidente; el resto extraído se reporta igual.
        return _err(
            f"restore blocked {len(blocked)} entries that would escape dst (zip-slip)",
            backup=str(backup_path), dst=str(dst),
            blocked=blocked[:50], extracted_count=len(extracted),
            extracted=extracted[:50], status="failed",
        )

    return _ok(
        backup=str(backup_path), dst=str(dst), conflict_policy=conflict_policy,
        extracted_count=len(extracted), skipped_count=len(skipped),
        renamed_count=len(renamed), overwritten_count=len(overwritten),
        extracted=extracted[:50], skipped=skipped[:50], renamed=renamed[:50], overwritten=overwritten[:50],
        verified=True, evidence={"dst": str(dst), "entries": len(extracted)},
    )


def _next_available_path(path: Path) -> Path:
    """Devolver una ruta libre, agregando _1, _2, ... al stem si ya existe.

    Helper general — usado por backup restore (conflict=rename) Y por
    photo_library (cuando se copia una foto al mismo destino dos veces).
    Por eso vive acá pero domain_tools.py lo re-exporta para callers
    externos."""
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    for n in range(1, 10000):
        candidate = path.with_name(f"{stem}_{n}{suffix}")
        if not candidate.exists():
            return candidate
    return path.with_name(f"{stem}_{int(time.time())}{suffix}")


def _backup_dedupe(args: dict[str, Any]) -> dict[str, Any]:
    import hashlib
    root_raw = str(args.get("path") or args.get("root") or "").strip()
    if not root_raw:
        return _err("dedupe requires path")
    root = Path(root_raw).expanduser()
    if not root.exists() or not root.is_dir():
        return _err("path is not an existing directory", path=str(root))
    min_size = int(args.get("min_size_bytes", 1))
    by_hash: dict[str, list[str]] = {}
    scanned = 0
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            if path.stat().st_size < min_size:
                continue
            scanned += 1
            digest = hashlib.sha256()
            with path.open("rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    digest.update(chunk)
            by_hash.setdefault(digest.hexdigest(), []).append(str(path))
        except OSError:
            continue
    duplicates = {h: paths for h, paths in by_hash.items() if len(paths) > 1}
    duplicate_count = sum(len(paths) - 1 for paths in duplicates.values())
    return _ok(
        root=str(root), scanned=scanned, unique_hashes=len(by_hash),
        duplicate_groups=len(duplicates), duplicate_files=duplicate_count,
        groups=[{"sha256": h, "paths": paths} for h, paths in list(duplicates.items())[:50]],
    )


def _backup_verify(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    backup_path, resource = _backup_resolve(args, state)
    if not backup_path:
        return _err("backup not found")
    try:
        with zipfile.ZipFile(backup_path, "r") as archive:
            bad = archive.testzip()
            return _ok(backup=str(backup_path), size=backup_path.stat().st_size, entries=len(archive.infolist()), corrupted=bool(bad), bad_file=bad, verified=not bad)
    except (zipfile.BadZipFile, OSError) as exc:
        return _err(f"verify failed: {exc}", backup=str(backup_path))
