"""Calidad de fuentes web: clasifica resultados de búsqueda por la FORMA de la
fuente (foro/discusión vs estándar), sin lista positiva de dominios confiables.

Extraído de tools.py (2026-06-08, ratchet archivo-dios): un resultado de
foro/Reddit/discusión sirve para opiniones o pistas, NO como fuente factual
primaria salvo que el usuario pida explícitamente discusión. La clasificación es
ESTRUCTURAL (regex sobre la shape de la URL/título), no por idioma ni por una
allowlist de dominios — cumple el constraint de producto.
"""
from __future__ import annotations

import re
from typing import Any

_DISCUSSION_SOURCE_RE = re.compile(
    r"(?i)("
    r"\br/[\w.-]+|"
    r"(?:^|[/:._ -])(?:forum|forums|thread|threads|discussion|discussions|"
    r"comments|community|communities|board|boards|topic|topics)(?:[/:._ -]|$)|"
    r"/(?:r|u|user)/[^/]+/comments/"
    r")"
)


def web_source_kind(url: str, title: str = "") -> str:
    """Classify by source shape, not by a positive list of trusted domains."""
    blob = f"{url or ''} {title or ''}"
    if _DISCUSSION_SOURCE_RE.search(blob):
        return "discussion"
    return "standard"


def annotate_web_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    annotated: list[dict[str, Any]] = []
    for rank, item in enumerate(results or [], start=1):
        if not isinstance(item, dict):
            continue
        out = dict(item)
        out["rank"] = rank
        out["source_kind"] = web_source_kind(
            str(out.get("url") or ""),
            str(out.get("title") or ""),
        )
        if out["source_kind"] == "discussion":
            out["source_warning"] = (
                "discussion/forum result: use for opinions or leads, not as the "
                "primary factual source unless the user asked for discussion."
            )
        annotated.append(out)
    return annotated


def primary_web_results(results: list[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
    primary: list[dict[str, Any]] = []
    for item in results:
        if item.get("source_kind") == "discussion":
            continue
        primary.append({
            "rank": item.get("rank"),
            "title": item.get("title"),
            "url": item.get("url"),
            "snippet": item.get("snippet"),
            "source_kind": item.get("source_kind"),
        })
        if len(primary) >= limit:
            break
    return primary


__all__ = ["web_source_kind", "annotate_web_results", "primary_web_results"]
