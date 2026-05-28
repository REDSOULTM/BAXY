"""Dependency catalog domain tool — extracted from domain_tools.py (R2 sprint
2026-05-28).

Reporta qué dependencias opcionales están instaladas (Python modules + binarios
externos). NO instala — install action devuelve needs_user con el hint;
instalación va por terminal/package tools explícitos.

Funciones extraídas (4):
  dependency_tool                 (entry, 4 acciones)
  _dependency_catalog             (lista completa de deps soportadas)
  _module_dep                     (find_spec wrapper)
  _binary_dep                     (shutil.which wrapper)

Helpers desde domain_tools (lazy): _find_soundvolumeview."""
from __future__ import annotations

import importlib.util
import shutil
from typing import Any

from ._shared import _err, _ok
from .tool_result import ToolResult


__all__ = [
    "dependency_tool",
    "_dependency_catalog",
    "_module_dep",
    "_binary_dep",
]


# R4 sprint 2026-05-28: este handler está MIGRADO a ToolResult internamente,
# pero exporta dict via `.to_dict()` para back-compat con consumers viejos.
# Sirve como ejemplo de referencia para la migración handler-por-handler.
def dependency_tool(args: dict[str, Any]) -> dict[str, Any]:
    action = str(args.get("action") or "status").casefold()
    catalog = _dependency_catalog()
    if action in {"status", "list"}:
        return ToolResult.ok_result(
            dependencies=list(catalog.values()),
            missing=[d for d in catalog.values() if not d["available"]],
        ).to_dict()
    if action in {"verify", "explain_missing"}:
        name = str(args.get("name") or args.get("dependency") or "").strip().casefold()
        matches = [item for key, item in catalog.items() if name in {key, item["name"].casefold()}] if name else [d for d in catalog.values() if not d["available"]]
        return ToolResult.ok_result(matches=matches, count=len(matches)).to_dict()
    if action in {"install", "repair"}:
        name = str(args.get("name") or args.get("dependency") or "").strip().casefold()
        item = catalog.get(name)
        return ToolResult.err(
            "dependency.install is advisory in this local tool",
            status="needs_user",
            verified=False,
            completion_status="needs_user_install",
            dependency=item or name,
            install_hint=(item or {}).get("install_hint") or "Use package/terminal explicitly if you want installation.",
        ).to_dict()
    return ToolResult.err(
        "unknown dependency action", action=action,
        valid_actions=["status", "list", "verify", "explain_missing"],
        status="needs_user",
    ).to_dict()


def _dependency_catalog() -> dict[str, dict[str, Any]]:
    from .domain_tools_helpers import _find_soundvolumeview
    items = [
        _module_dep("playwright", "Playwright", "python -m pip install playwright && python -m playwright install chromium"),
        _module_dep("pptx", "python-pptx", "python -m pip install python-pptx"),
        _module_dep("docx", "python-docx", "python -m pip install python-docx"),
        _module_dep("openpyxl", "openpyxl", "python -m pip install openpyxl"),
        _module_dep("pyautogui", "pyautogui", "python -m pip install pyautogui"),
        _module_dep("pycaw", "pycaw", "python -m pip install pycaw comtypes"),
        _binary_dep("tesseract", "Tesseract OCR", "winget install UB-Mannheim.TesseractOCR"),
        _binary_dep("ffmpeg", "FFmpeg", "winget install Gyan.FFmpeg"),
        _binary_dep("git", "Git", "winget install Git.Git"),
        _binary_dep("winget", "winget", "Install App Installer from Microsoft Store"),
        _binary_dep("soffice", "LibreOffice", "winget install TheDocumentFoundation.LibreOffice"),
        {
            "name": "SoundVolumeView",
            "key": "soundvolumeview",
            "type": "binary",
            "available": _find_soundvolumeview() is not None,
            "path": str(_find_soundvolumeview()) if _find_soundvolumeview() else None,
            "install_hint": "Download SoundVolumeView from NirSoft and set GEMMA4_SOUNDVOLUMEVIEW.",
        },
    ]
    return {item["key"]: item for item in items}


def _module_dep(module: str, name: str, hint: str) -> dict[str, Any]:
    available = importlib.util.find_spec(module) is not None
    return {"name": name, "key": module, "type": "python_module", "available": available, "install_hint": hint}


def _binary_dep(binary: str, name: str, hint: str) -> dict[str, Any]:
    path = shutil.which(binary) or shutil.which(f"{binary}.exe")
    return {"name": name, "key": binary, "type": "binary", "available": bool(path), "path": path, "install_hint": hint}
