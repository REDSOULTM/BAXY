"""Photo Library domain tool — extracted from domain_tools.py (R2 sprint
2026-05-28).

Librería de fotos/videos local. Acciones: scan + EXIF + group_by_date
(copy/move/symlink/dry_run) + thumbnails (PIL) + find_by_date.

Funciones extraídas (8) + 1 constante:
  photo_library_tool             (entry, 6 acciones)
  _photo_scan
  _photo_open_exif
  _photo_exif
  _photo_extract_date            (EXIF DateTimeOriginal/Digitized/DateTime ->
                                  fallback file mtime)
  _photo_group_by_date           (granularity: year/month/day)
  _photo_thumbnails              (PIL Resampling.LANCZOS)
  _photo_find_by_date

Constants: _PHOTO_EXTS (.jpg/.png/.heic/.tif/.webp/.bmp/.gif).

Helpers desde domain_tools (lazy):
  _next_available_path (vive en domain_tools_backup_sync, re-exportado por dt)."""
from __future__ import annotations

import importlib.util
import shutil
import time
from pathlib import Path
from typing import Any

from ._shared import _err, _ok
from .state import AgentState


__all__ = [
    "photo_library_tool",
    "_photo_scan",
    "_photo_open_exif",
    "_photo_exif",
    "_photo_extract_date",
    "_photo_group_by_date",
    "_photo_thumbnails",
    "_photo_find_by_date",
    "_PHOTO_EXTS",
]


_PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".tif", ".tiff", ".webp", ".bmp", ".gif"}


def photo_library_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    """Compound tool for local photo/video libraries.

    Actions: status, scan, exif, group_by_date, thumbnails, find_by_date.
    Requires Pillow (PIL). Defers any face-recognition/embedding work.
    """
    action = str(args.get("action") or "status").casefold()
    pil_available = importlib.util.find_spec("PIL") is not None
    if action == "status":
        return _ok(
            pillow=pil_available,
            install_hint="python -m pip install Pillow",
            note="EXIF parsing and thumbnails require Pillow; scan/find_by_date work without it for filename listings only.",
        )
    if action == "scan":
        return _photo_scan(args)
    if not pil_available:
        return _err(
            "Pillow is not installed",
            status="needs_dependency", verified=False,
            install_hint="python -m pip install Pillow",
        )
    if action == "exif":
        return _photo_exif(args)
    if action == "group_by_date":
        return _photo_group_by_date(args, state)
    if action == "thumbnails":
        return _photo_thumbnails(args, state)
    if action == "find_by_date":
        return _photo_find_by_date(args)
    return _err(
        "unknown photo_library action", action=action,
        valid_actions=[
            "status", "scan", "exif", "group_by_date", "group_by_location",
            "find_duplicates", "thumbnail",
        ],
        status="needs_user",
    )


def _photo_scan(args: dict[str, Any]) -> dict[str, Any]:
    root_raw = str(args.get("root") or args.get("path") or "").strip()
    if not root_raw:
        root = Path.home() / "Pictures"
    else:
        root = Path(root_raw).expanduser()
    if not root.exists():
        return _err("root not found", root=str(root))
    limit = int(args.get("limit", 1000))
    photos: list[dict[str, Any]] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.casefold() not in _PHOTO_EXTS:
            continue
        try:
            stat = path.stat()
            photos.append({"path": str(path), "name": path.name, "size": stat.st_size, "mtime": stat.st_mtime})
        except OSError:
            continue
        if len(photos) >= limit:
            break
    return _ok(root=str(root), count=len(photos), photos=photos[:200], note=f"{len(photos)} photos found (preview limited to 200).")


def _photo_open_exif(path: Path) -> dict[str, Any]:
    try:
        from PIL import Image, ExifTags
    except ImportError:
        return {"error": "PIL not available"}
    try:
        with Image.open(path) as img:
            # _getexif is a private method only on JPEG/TIFF ImageFile subclasses;
            # Pillow doesn't expose it on the base ImageFile type.
            exif_raw = img._getexif() or {}  # type: ignore[attr-defined]
            named: dict[str, Any] = {}
            for tag_id, value in exif_raw.items():
                tag_name = ExifTags.TAGS.get(tag_id, f"Tag{tag_id}")
                if isinstance(value, bytes):
                    try:
                        value = value.decode("utf-8", errors="replace")
                    except Exception:
                        value = repr(value)
                if isinstance(value, dict):
                    # nested (GPS, etc); flatten one level
                    nested = {}
                    for k, v in value.items():
                        name = ExifTags.GPSTAGS.get(k, f"GPS{k}") if tag_name == "GPSInfo" else str(k)
                        nested[name] = str(v) if not isinstance(v, (int, float, str, bool, type(None))) else v
                    value = nested
                if not isinstance(value, (int, float, str, bool, dict, list, type(None))):
                    value = str(value)
                named[tag_name] = value
            return {"size": img.size, "format": img.format, "mode": img.mode, "exif": named}
    except Exception as exc:
        return {"error": f"failed to read: {exc}"}


def _photo_exif(args: dict[str, Any]) -> dict[str, Any]:
    path_raw = str(args.get("path") or "").strip()
    if not path_raw:
        return _err("missing path")
    path = Path(path_raw).expanduser()
    if not path.is_file():
        return _err("file not found", path=str(path))
    info = _photo_open_exif(path)
    if info.get("error"):
        return _err(info["error"], path=str(path))
    return _ok(path=str(path), **info)


def _photo_extract_date(path: Path) -> str | None:
    """Try EXIF DateTimeOriginal/DateTime, fallback to file mtime."""
    info = _photo_open_exif(path)
    exif = info.get("exif") or {}
    for key in ("DateTimeOriginal", "DateTimeDigitized", "DateTime"):
        raw = exif.get(key)
        if isinstance(raw, str) and len(raw) >= 10:
            # EXIF format: "YYYY:MM:DD HH:MM:SS"
            return raw[:10].replace(":", "-")
    try:
        return time.strftime("%Y-%m-%d", time.localtime(path.stat().st_mtime))
    except OSError:
        return None


def _photo_group_by_date(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    from .domain_tools import _next_available_path
    root_raw = str(args.get("root") or "").strip()
    if not root_raw:
        return _err("missing root")
    root = Path(root_raw).expanduser()
    if not root.is_dir():
        return _err("root not a directory", root=str(root))
    out_raw = str(args.get("output") or args.get("dst") or "").strip()
    if not out_raw:
        out = state.path.parent / "photos_by_date"
    else:
        out = Path(out_raw).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    mode = str(args.get("mode") or "copy").casefold()  # copy|move|symlink|dry_run
    granularity = str(args.get("granularity") or "month").casefold()  # year|month|day
    dry_run = mode == "dry_run"
    moved = 0
    skipped = 0
    plan: list[dict[str, str]] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.casefold() not in _PHOTO_EXTS:
            continue
        date = _photo_extract_date(path)
        if not date:
            skipped += 1
            continue
        if granularity == "year":
            subdir_name = date[:4]
        elif granularity == "day":
            subdir_name = date
        else:
            subdir_name = date[:7]  # YYYY-MM
        target_dir = out / subdir_name
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / path.name
        if target.exists():
            target = _next_available_path(target)
        plan.append({"src": str(path), "dst": str(target), "date": date})
        if dry_run:
            moved += 1
            continue
        try:
            if mode == "move":
                shutil.move(str(path), str(target))
            elif mode == "symlink":
                target.symlink_to(path)
            else:
                shutil.copy2(str(path), str(target))
            moved += 1
        except (OSError, shutil.Error):
            skipped += 1
    return _ok(root=str(root), output=str(out), mode=mode, granularity=granularity, processed=moved, skipped=skipped, plan_preview=plan[:30], total_plan=len(plan))


def _photo_thumbnails(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    from PIL import Image
    root_raw = str(args.get("root") or "").strip()
    if not root_raw:
        return _err("missing root")
    root = Path(root_raw).expanduser()
    if not root.exists():
        return _err("root not found", root=str(root))
    out_raw = str(args.get("output") or args.get("dst") or "").strip()
    if not out_raw:
        out = state.path.parent / "thumbnails"
    else:
        out = Path(out_raw).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    size_arg: Any = args.get("size", 256)
    if isinstance(size_arg, (list, tuple)) and len(size_arg) == 2:
        size = (int(size_arg[0] or 0), int(size_arg[1] or 0))
    else:
        n: int = int(size_arg) if isinstance(size_arg, (int, float, str)) else 256
        size = (n, n)
    created: list[str] = []
    failed: list[dict[str, str]] = []
    limit = int(args.get("limit", 1000))
    sources = [path for path in root.rglob("*") if path.is_file() and path.suffix.casefold() in _PHOTO_EXTS]
    for path in sources[:limit]:
        target = out / f"{path.stem}_thumb.jpg"
        try:
            with Image.open(path) as img:
                img.thumbnail(size, Image.Resampling.LANCZOS)
                img.convert("RGB").save(target, "JPEG", quality=85)
            created.append(str(target))
        except Exception as exc:
            failed.append({"src": str(path), "error": str(exc)})
    return _ok(root=str(root), output=str(out), size=size, created=len(created), failed=len(failed), failed_details=failed[:10])


def _photo_find_by_date(args: dict[str, Any]) -> dict[str, Any]:
    root_raw = str(args.get("root") or "").strip()
    if not root_raw:
        return _err("missing root")
    year = args.get("year")
    month = args.get("month")
    if year is None:
        return _err("missing year")
    target_prefix = f"{int(year):04d}"
    if month is not None:
        target_prefix += f"-{int(month):02d}"
    root = Path(root_raw).expanduser()
    matches: list[dict[str, Any]] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.casefold() not in _PHOTO_EXTS:
            continue
        date = _photo_extract_date(path)
        if date and date.startswith(target_prefix):
            matches.append({"path": str(path), "date": date})
        if len(matches) >= int(args.get("limit", 500)):
            break
    return _ok(root=str(root), filter=target_prefix, count=len(matches), photos=matches[:200])
