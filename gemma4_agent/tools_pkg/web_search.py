"""Búsqueda web por scraping HTML: DuckDuckGo (primario HTML) + Bing (fallback
independiente). Extraído de tools.py (2026-06-08, ratchet archivo-dios).

El primario real (ddgs metasearch) y la resolución de sitio viven en
site_resolver.py; acá quedan los scrapers HTML de respaldo y el selector de
proveedor con su degradación limpia (ddgs -> DDG-HTML -> Bing). Los scrapers son
best-effort: si el HTML no matchea el regex devuelven [] (sin daño, ya veníamos
en blanco). Regex verificados contra el HTML real de cada motor.

Las utilidades HTTP/HTML (`_http_get_text`, `_clean_html_text`) viven en
web_text.py (módulo de bajo nivel, sin dependencias del paquete); se importan a
nivel de función por consistencia histórica.
"""
from __future__ import annotations

import base64
import html
import os
import re
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

DEFAULT_WEB_SEARCH_PROVIDER = "duckduckgo_html"


def decode_duckduckgo_href(href: str) -> str:
    href = html.unescape(href)
    parsed = urlparse(href)
    query = parse_qs(parsed.query)
    if "uddg" in query and query["uddg"]:
        return unquote(query["uddg"][0])
    return href


def duckduckgo_search(query: str, limit: int = 6, timeout: int | None = None) -> list[dict[str, str]]:
    from .web_text import _http_get_text, _clean_html_text
    page = _http_get_text(
        f"https://html.duckduckgo.com/html/?q={quote_plus(query)}",
        timeout=max(1, min(int(timeout or 12), 12)),
    )["text"]
    results: list[dict[str, str]] = []
    for link in re.finditer(r"(?is)<a[^>]+class=\"result__a\"[^>]+href=\"([^\"]+)\"[^>]*>(.*?)</a>", page):
        chunk = page[link.end(): link.end() + 3000]
        snippet = re.search(r"(?is)<a[^>]+class=\"result__snippet\"[^>]*>(.*?)</a>", chunk)
        url = decode_duckduckgo_href(link.group(1))
        title = _clean_html_text(link.group(2), limit=300)
        item = {"title": title, "url": url}
        if snippet:
            item["snippet"] = _clean_html_text(snippet.group(1), limit=700)
        results.append(item)
        if len(results) >= limit:
            break
    return results


def bing_decode_redirect(href: str) -> str:
    """Bing envuelve el URL real en un redirect de tracking
    (`.../ck/a?...&u=a1<base64>`). Desenvuelve el `u=a1<base64>` al URL real.
    Si no es un redirect (link directo), devuelve el href tal cual. Verificado
    contra HTML real de Bing."""
    m = re.search(r"[?&]u=a1([A-Za-z0-9_\-]+)", href)
    if not m:
        return href
    raw = m.group(1).replace("-", "+").replace("_", "/")
    raw += "=" * (-len(raw) % 4)
    try:
        dec = base64.b64decode(raw).decode("utf-8", "replace")
        return dec if dec.startswith("http") else href
    except Exception:
        return href


def bing_search(query: str, limit: int = 6, timeout: int | None = None) -> list[dict[str, str]]:
    """Búsqueda fallback vía Bing HTML — motor INDEPENDIENTE de DDG. Best-effort
    scraping; si el HTML no matchea el regex, devuelve [] (sin daño: ya veníamos
    en blanco). Sólo se usa cuando DDG falló/vino vacío. Regex verificado contra
    el HTML real de Bing: <h2 class=""><a href="redirect base64">."""
    from .web_text import _http_get_text, _clean_html_text
    page = _http_get_text(
        f"https://www.bing.com/search?q={quote_plus(query)}",
        timeout=max(1, min(int(timeout or 12), 12)),
    )["text"]
    results: list[dict[str, str]] = []
    for block in re.finditer(r"(?is)<li class=\"b_algo\".*?(?=<li class=\"b_algo\"|</ol>|$)", page):
        chunk = block.group(0)
        a = re.search(r"(?is)<h2[^>]*>\s*<a[^>]+href=\"([^\"]+)\"[^>]*>(.*?)</a>", chunk)
        if not a:
            continue
        url = bing_decode_redirect(html.unescape(a.group(1)))
        if not url.startswith("http") or "/ck/a" in url:  # redirect no resuelto -> descartar
            continue
        title = _clean_html_text(a.group(2), limit=300)
        item = {"title": title, "url": url}
        snip = re.search(r"(?is)<p[^>]*>(.*?)</p>", chunk)
        if snip:
            item["snippet"] = _clean_html_text(snip.group(1), limit=700)
        results.append(item)
        if len(results) >= limit:
            break
    return results


def web_fallback_enabled() -> bool:
    """Fallback dual de web search (DDG -> Bing). DEFAULT ON.
    Kill-switch GEMMA4_WEB_FALLBACK=0. Seguro: sólo actúa cuando DDG ya falló/vació
    -> nunca regresión (peor caso = sigue en blanco; si Bing cambia su HTML -> [] -> sin daño)."""
    return (os.environ.get("GEMMA4_WEB_FALLBACK", "1") or "1").strip().lower() not in {
        "0", "false", "no", "off"}


def web_search_provider(
    query: str,
    limit: int = 6,
    timeout_sec: int | None = None,
) -> tuple[str, list[dict[str, str]]]:
    from .site_resolver import ddgs_search as _ddgs_search
    provider = os.environ.get("GEMMA4_WEB_SEARCH_PROVIDER", DEFAULT_WEB_SEARCH_PROVIDER).strip().casefold()
    timeout = max(1, min(int(timeout_sec or 12), 12))
    if timeout <= int(os.environ.get("GEMMA4_WEB_SEARCH_FAST_TIMEOUT", "4") or "4"):
        name, results = "duckduckgo_html_fast", []
        try:
            results = duckduckgo_search(query, limit=limit, timeout=timeout) or []
        except Exception:
            results = []
        if results or not web_fallback_enabled():
            return name, results
        try:
            bing = bing_search(query, limit=limit, timeout=timeout)
            if bing:
                return "bing_html_fast_fallback", bing
        except Exception:
            pass
        return name, results
    # PRIMARIO: ddgs (metasearch con Google/Brave/... — 2026-06-07). Da los mismos
    # resultados que el user ve en su navegador (medido: pivigames.blog es #0). Si
    # ddgs no está o falla -> DDG-HTML -> Bing (degradación limpia, nunca rompe).
    # Override del primario con GEMMA4_WEB_SEARCH_PROVIDER (p.ej. 'duckduckgo' para
    # forzar el scraper viejo).
    _ddgs_aliases = {"ddgs", "metasearch", "duckduckgo", "duckduckgo_html", "ddg", DEFAULT_WEB_SEARCH_PROVIDER}
    if provider in _ddgs_aliases:
        try:
            results = _ddgs_search(query, limit=limit) or []
            if results:
                return "ddgs", results
        except Exception:
            pass
    if not web_fallback_enabled():
        # Comportamiento ORIGINAL (sin fallback dual) si ddgs no trajo nada.
        if provider in _ddgs_aliases:
            return "duckduckgo_html", duckduckgo_search(query, limit=limit)
        return provider or DEFAULT_WEB_SEARCH_PROVIDER, []
    # Fallback dual: DDG-HTML -> Bing (independientes), si ddgs vino vacío.
    name, results = "duckduckgo_html", []
    try:
        results = duckduckgo_search(query, limit=limit) or []
    except Exception:
        results = []
    if not results:
        try:
            bing = bing_search(query, limit=limit)
            if bing:
                return "bing_html_fallback", bing
        except Exception:
            pass
    return name, results


__all__ = [
    "DEFAULT_WEB_SEARCH_PROVIDER",
    "decode_duckduckgo_href",
    "duckduckgo_search",
    "bing_decode_redirect",
    "bing_search",
    "web_fallback_enabled",
    "web_search_provider",
]
