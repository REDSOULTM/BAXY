"""Utilidades de texto de bajo nivel, compartidas por el paquete tools_pkg.
Extraído para de-duplicar: tools.py, ops_tools.py y web_text.py tenían cada uno
una copia idéntica de `_truncate`. Sin dependencias (módulo leaf, no cicla).
"""
from __future__ import annotations


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + f"...<truncated {len(text) - limit} chars>"
