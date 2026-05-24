"""Best-effort discovery of installed apps on the operator's machine.

Used to augment STATIC_INVENTORY with the actual apps available, so
fuzzy correction handles names like "Counter-Strike 2" (the user
actually has it installed) without us hardcoding every Steam title.

Sources (in priority order):
  1. cached_apps()  — ~/.gemma4/app_discovery_cache.json (manual hints)
  2. windows_get_start_apps() if platform == Windows
  3. macos_mdfind() if platform == Darwin
  4. linux_desktop_files() if platform == Linux

ALL functions fail open: if discovery fails for any reason, return
an empty list. The voice pipeline still works on STATIC_INVENTORY
alone.

This module never raises: it logs and returns []. STT/wake never
crash because we couldn't enumerate Start Menu shortcuts.
"""
from __future__ import annotations

import json
import logging
import platform
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def discover_apps() -> list[str]:
    """Returns a deduplicated list of installed app display names."""
    names: list[str] = []
    # 1. Operator cache (fast path, user-editable hints).
    names.extend(_cached_apps())
    # 2. Platform-specific.
    sys = platform.system()
    try:
        if sys == "Windows":
            names.extend(_windows_get_start_apps())
        elif sys == "Darwin":
            names.extend(_macos_apps())
        elif sys == "Linux":
            names.extend(_linux_apps())
    except Exception as exc:
        logger.warning("app discovery (%s) failed: %s", sys, exc)
    # Deduplicate preserving order.
    seen = set()
    out: list[str] = []
    for n in names:
        key = n.lower().strip()
        if key and key not in seen:
            seen.add(key)
            out.append(n.strip())
    return out


# ---------- per-platform implementations ------------------------------

def _cached_apps() -> list[str]:
    """User-editable list at ~/.gemma4/app_discovery_cache.json.

    Schema: {"apps": ["Chrome", "Spotify", ...]}
    """
    path = Path.home() / ".gemma4" / "app_discovery_cache.json"
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict) and isinstance(data.get("apps"), list):
            return [str(x) for x in data["apps"] if isinstance(x, str)]
    except Exception as exc:
        logger.warning("app_discovery_cache.json malformed: %s", exc)
    return []


def _windows_get_start_apps() -> list[str]:
    """Use PowerShell's Get-StartApps to list Start Menu entries.

    Fast (<200 ms typical). Returns display names like 'Chrome',
    'Visual Studio Code', 'Counter-Strike 2'.
    """
    try:
        # `-NoProfile` skips user profile load (~300 ms speedup).
        # `-Command` evaluates the cmdlet directly.
        # ENCODING (bug 2026-05-23): nombres de apps del menú Inicio traen chars
        # fuera de cp1252 (comillas tipográficas, símbolos: byte 0x9d crasheaba el
        # _readerthread con UnicodeDecodeError y dejaba la lista VACÍA). Forzamos
        # a PowerShell a emitir UTF-8 y decodificamos UTF-8 con errors=replace.
        # NO usar text=True (default cp1252 en Windows). Mismo tipo que el bug de
        # la tilde de WhatsApp.
        result = subprocess.run(
            [
                "powershell", "-NoProfile", "-Command",
                "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
                "Get-StartApps | Select-Object -ExpandProperty Name",
            ],
            capture_output=True, timeout=8,
            encoding="utf-8", errors="replace",
        )
        if result.returncode != 0:
            logger.warning("Get-StartApps non-zero: %s", result.stderr[:200])
            return []
        names = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        return names
    except FileNotFoundError:
        logger.debug("powershell not available; skipping windows app discovery")
        return []
    except subprocess.TimeoutExpired:
        logger.warning("Get-StartApps timed out (8s)")
        return []
    except Exception as exc:
        logger.warning("Get-StartApps failed: %s", exc)
        return []


def _macos_apps() -> list[str]:
    """Enumerate /Applications and ~/Applications for .app bundles."""
    out: list[str] = []
    for base in (Path("/Applications"), Path.home() / "Applications"):
        if not base.is_dir():
            continue
        try:
            for entry in base.iterdir():
                if entry.suffix == ".app":
                    out.append(entry.stem)
        except Exception as exc:
            logger.debug("scanning %s failed: %s", base, exc)
    return out


def _linux_apps() -> list[str]:
    """Parse .desktop files in standard XDG locations."""
    out: list[str] = []
    candidates = [
        Path("/usr/share/applications"),
        Path("/usr/local/share/applications"),
        Path.home() / ".local/share/applications",
        Path.home() / ".var/app",  # Flatpak
        Path("/var/lib/snapd/desktop/applications"),  # Snap
    ]
    for base in candidates:
        if not base.is_dir():
            continue
        try:
            for entry in base.glob("*.desktop"):
                name = _read_desktop_name(entry)
                if name:
                    out.append(name)
        except Exception as exc:
            logger.debug("scanning %s failed: %s", base, exc)
    return out


def _read_desktop_name(path: Path) -> str | None:
    """Read the Name= line from a .desktop file. Returns None on error."""
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                if line.startswith("Name=") and "=" in line:
                    return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return None
