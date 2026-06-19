"""Helpers de rutas de ejecutables: nombre "bonito" para mostrar + detección de
uninstaller/instalador. Extraído de tools.py (split del archivo-dios, 2026-06-19).
Lo usan app_resolver y el cluster app/process; vive en un módulo leaf (solo re +
pathlib + name_match._score) para no ciclar con tools.py.
"""
from __future__ import annotations

import re
from pathlib import Path

from .name_match import _score


def _pretty_exe_name(path: Path) -> str:
    parts = [p for p in path.parts[-4:-1] if p and p not in {"bin", "x64", "x86", "Win64", "Win32", "Binaries"}]
    stem = re.sub(r"[_-]+", " ", path.stem).strip()
    if parts:
        parent = re.sub(r"[_-]+", " ", parts[-1]).strip()
        if parent and _score(stem, parent) < 80:
            return f"{parent} {stem}"
    return stem


def _looks_like_uninstaller(path: Path) -> bool:
    lower = path.name.casefold()
    return lower.startswith(("unins", "uninstall", "unwise")) or lower in {
        "setup.exe",
        "install.exe",
        "crashreporter.exe",
        "crashreportclient.exe",
        "vc_redist.exe",
        "vc_redist.x64.exe",
        "vc_redist.x86.exe",
    }
