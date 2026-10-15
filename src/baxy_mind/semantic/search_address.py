"""The search-results page an address is (review r10a, finding 7): the engine's name and the words searched.

The engines live in data/search_addresses.v1.json (site, host, results paths, the parameter that carries the query);
nothing here names one. Reads an address, never the person's words.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qs, urlparse

_DATA = Path(__file__).resolve().parent.parent / "data" / "search_addresses.v1.json"


@lru_cache(maxsize=1)
def engines() -> tuple[dict, ...]:
    return tuple(json.loads(_DATA.read_text(encoding="utf-8"))["engines"])


def search_of_address(value: str) -> tuple[str, str] | None:
    """(site, query) of a search-results address; None for any other page or an address without a query."""

    try:
        parts = urlparse(value if "://" in value else "https://" + value)
    except ValueError:
        return None
    host = (parts.hostname or "").casefold()
    host = host[4:] if host.startswith("www.") else host
    params = parse_qs(parts.query)
    for engine in engines():
        own = str(engine["host"]).casefold()
        if not (host == own or (engine.get("hostSuffix") and host.endswith("." + own))):
            continue
        if parts.path not in engine["paths"]:
            continue
        query = " ".join(params.get(engine["param"]) or ()).strip()
        if query:
            return str(engine["site"]), query
    return None
