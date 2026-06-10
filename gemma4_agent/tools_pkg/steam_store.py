"""Helpers de Steam: AppID, URIs de protocolo y búsqueda en la tienda.

Extraído de tools.py (ratchet anti-archivo-dios, patrón sibling+shim). Funciones
puras de parsing/formateo + una búsqueda HTTP en la store. `_http_get_text` y
`_clean_html_text` siguen en tools.py y se importan lazy para no ciclar.
"""
from __future__ import annotations

import re
from urllib.parse import quote_plus, unquote


def _acf_value(text: str, key: str) -> str | None:
    match = re.search(rf'"{re.escape(key)}"\s+"([^"]+)"', text)
    return match.group(1) if match else None


def _nearest_steam_appid(data: bytes, appid_markers: list[tuple[int, bytes]], pos: int) -> int | None:
    scan_start = max(0, pos - 200_000)
    best_index = -1
    best_appid: int | None = None
    for appid, marker in appid_markers:
        idx = data.rfind(marker, scan_start, pos)
        if idx > best_index:
            best_index = idx
            best_appid = appid
    return best_appid


def _steam_appid_from_launch(launch: str) -> str | None:
    match = re.search(r"/(\d+)$", launch)
    return match.group(1) if match else None


def _is_placeholder_appid(appid: str) -> bool:
    """True si `appid` parece INVENTADO por el LLM (no un AppID real de Steam).
    El 4B alucina placeholders cuando no conoce el appid real en vez de pasar la
    query (medido 2026-06-10: "1234567890" para Spider-Man 2). Señales: no-dígito,
    secuencia ascendente/repetida obvia ("1234567890", "123456789", "111111111"),
    o longitud absurda. Los AppID reales de Steam son enteros sin patrón obvio,
    típicamente 4-7 dígitos (los más nuevos llegan a 7). ESTRUCTURAL, no una lista.
    """
    a = (appid or "").strip()
    if not a.isdigit():
        return True
    # secuencia ascendente "123456789(0)" o un solo dígito repetido "1111..."
    if a in ("1234567890", "123456789", "12345678", "1234567", "0123456789"):
        return True
    if len(set(a)) == 1:  # "1111111111", "0000000"
        return True
    # appid real de Steam: 1..7 dígitos plausibles; >7 es casi seguro inventado.
    if len(a) > 7 or len(a) < 1:
        return True
    return False


def _steam_store_uri(appid: str) -> str:
    return f"steam://store/{appid}"


def _steam_openurl_uri(url: str) -> str:
    return f"steam://openurl/{url}"


def _steam_store_url(appid: str, name: str | None = None) -> str:
    slug = ""
    if name:
        slug = "/" + re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")
    return f"https://store.steampowered.com/app/{appid}{slug}/"


def _steam_store_first_result(query: str) -> dict[str, str] | None:
    # lazy: _http_get_text / _clean_html_text viven en tools.py (evita ciclo).
    from .tools import _http_get_text, _clean_html_text
    url = f"https://store.steampowered.com/search/?term={quote_plus(query)}"
    try:
        html_text = _http_get_text(url, timeout=12)["text"]
    except Exception:
        return None
    match = re.search(r'href="https://store\.steampowered\.com/app/(\d+)/([^"/?#]+)', html_text)
    if not match:
        match = re.search(r"https://store\.steampowered\.com/app/(\d+)/([^\"'<>?#]+)", html_text)
    if not match:
        return None
    appid = match.group(1)
    raw_slug = unquote(match.group(2)).replace("_", " ").strip()
    title_match = re.search(rf'(?is)data-ds-appid="{re.escape(appid)}".*?<span[^>]+class="title"[^>]*>(.*?)</span>', html_text)
    title = _clean_html_text(title_match.group(1), limit=200) if title_match else raw_slug
    return {"appid": appid, "name": title or raw_slug, "url": _steam_store_url(appid, title or raw_slug)}
