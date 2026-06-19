"""HTTP fetch + HTML→texto, extraído de tools.py (split del archivo-dios,
2026-06-19). steam_store.py y web_search.py los importaban LAZY desde tools.py
(hack anti-ciclo contra el archivo-dios); ahora viven en un módulo de bajo nivel
que NO importa tools.py, así que esos consumidores importan de acá directo.

Funciones puras de red/parseo, sin estado. El SSRF guard vive en safety_pkg.
"""
from __future__ import annotations

import html
import re
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlparse

from ..safety_pkg.ssrf_guard import _is_private_host, _SSRFGuardRedirectHandler
from .text_utils import _truncate  # de-dup: era una copia local del mismo one-liner

WEB_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Gemma4Agent/1.0"


def _http_get_text(url: str, timeout: int = 12, max_bytes: int = 2_000_000, allow_private: bool = False) -> dict[str, Any]:
    # SSRF guard pre-request y en redirects.
    host = urlparse(url).hostname or ""
    if not allow_private and _is_private_host(host):
        raise urllib.error.URLError(f"refused: target host is private/loopback ({host}); pass allow_private=True to override")
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": WEB_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.5",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        },
    )
    opener = urllib.request.build_opener(_SSRFGuardRedirectHandler()) if not allow_private else urllib.request.build_opener()
    with opener.open(req, timeout=timeout) as resp:
        raw = resp.read(max_bytes)
        content_type = resp.headers.get("content-type", "")
        charset_match = re.search(r"charset=([^;\s]+)", content_type, re.I)
        charset = charset_match.group(1) if charset_match else "utf-8"
        text = raw.decode(charset, errors="replace")
        return {
            "url": resp.geturl(),
            "status_code": getattr(resp, "status", None),
            "content_type": content_type,
            "text": text,
        }


def _extract_title(markup: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", markup, re.I | re.S)
    if not match:
        return ""
    return _clean_html_text(match.group(1), limit=300)


def _html_to_text(markup: str, limit: int = 12000) -> str:
    markup = re.sub(r"(?is)<(script|style|noscript|svg|canvas).*?</\1>", " ", markup)
    markup = re.sub(r"(?i)<br\s*/?>", "\n", markup)
    markup = re.sub(r"(?i)</(p|div|section|article|header|footer|li|h[1-6]|tr)>", "\n", markup)
    return _clean_html_text(markup, limit=limit)


def _clean_html_text(text: str, limit: int = 12000) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return _truncate(text.strip(), limit)
