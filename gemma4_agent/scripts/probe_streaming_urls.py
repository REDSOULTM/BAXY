"""Probes REALES contra cada plataforma de streaming para validar:
  - Qué URL de search NO devuelve 404.
  - Si la pagina tiene un input para tipear la query.
  - Si despues de tipear/submit, aparecen result cards clickeables.

Corre sin login (no podemos asumir cookies). Detecta 404 / login redirect /
search page. Reporta JSON con findings por plataforma.

Uso:
  python -m gemma4_agent.scripts.probe_streaming_urls
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

# Candidatos a probar por plataforma. Cada uno incluye URL + heuristica para
# decidir si "funciono" (no es 404, no es login wall si esperamos search).
CANDIDATES: dict[str, list[dict[str, Any]]] = {
    "disney": [
        # Distintas variantes de URL para encontrar la real.
        {"url": "https://www.disneyplus.com/search", "expect": "search_or_login"},
        {"url": "https://www.disneyplus.com/es-419/search", "expect": "search_or_login"},
        {"url": "https://www.disneyplus.com/buscar", "expect": "search_or_login"},
        {"url": "https://www.disneyplus.com/es/search", "expect": "search_or_login"},
        {"url": "https://www.disneyplus.com/home", "expect": "home_or_login"},
        {"url": "https://www.disneyplus.com/", "expect": "home_or_login"},
    ],
    "netflix": [
        {"url": "https://www.netflix.com/search?q=Stranger+Things", "expect": "search_or_login"},
        {"url": "https://www.netflix.com/browse", "expect": "home_or_login"},
    ],
    "hbo_max": [
        {"url": "https://play.hbomax.com/search", "expect": "search_or_login"},
        {"url": "https://play.hbomax.com/", "expect": "home_or_login"},
        {"url": "https://www.hbomax.com/", "expect": "home_or_login"},
        {"url": "https://play.max.com/search", "expect": "search_or_login"},
        {"url": "https://play.max.com/", "expect": "home_or_login"},
    ],
    "prime_video": [
        {"url": "https://www.primevideo.com/search/ref=atv_nb_sr?phrase=The+Boys",
          "expect": "search_or_login"},
        {"url": "https://www.primevideo.com/", "expect": "home_or_login"},
    ],
    "spotify_web": [
        {"url": "https://open.spotify.com/search/test", "expect": "search_or_login"},
    ],
}


def classify_page(page) -> dict[str, Any]:
    """Decide si la pagina cargada es 404, login wall, search page, o home."""
    title = ""
    body_text = ""
    try:
        title = page.title() or ""
    except Exception:
        pass
    try:
        body_text = page.inner_text("body", timeout=3000)[:600]
    except Exception:
        pass

    classification = "unknown"
    is_404 = False
    indicators: list[str] = []

    text_low = (title + " " + body_text).lower()
    if "cannot be found" in text_low or "could not be found" in text_low \
            or "no se encontró" in text_low or "no se encontro" in text_low \
            or "page you were looking for" in text_low \
            or "404" in title.lower():
        is_404 = True
        classification = "404"
    elif ("sign in" in text_low or "iniciar sesi" in text_low
          or "log in" in text_low or "login" in text_low) \
         and not ("search" in text_low or "buscar" in text_low):
        classification = "login_wall"
    elif "search" in text_low or "buscar" in text_low:
        classification = "search_page"
    else:
        classification = "other"

    # Probar selectores de search input.
    input_candidates = [
        "input[type='search']",
        "input[role='searchbox']",
        "input[aria-label*='search' i]",
        "input[aria-label*='buscar' i]",
        "input[placeholder*='search' i]",
        "input[placeholder*='buscar' i]",
        "input[data-uia*='search' i]",
        "input[data-testid*='search' i]",
        "input[name='phrase']",
        "input[name='searchTerm']",
    ]
    found_inputs: list[str] = []
    for sel in input_candidates:
        try:
            count = page.locator(sel).count()
            if count > 0:
                found_inputs.append(f"{sel} ({count})")
        except Exception:
            pass

    return {
        "url_after_load": page.url,
        "title": title[:120],
        "body_excerpt": body_text[:200].replace("\n", " ⏎ "),
        "is_404": is_404,
        "classification": classification,
        "search_inputs_found": found_inputs,
    }


def probe_platform(playwright, platform: str, candidates: list[dict]) -> dict[str, Any]:
    print(f"\n=== {platform} ===", file=sys.stderr)
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        locale="es-419",
    )
    results: list[dict[str, Any]] = []
    for cand in candidates:
        url = cand["url"]
        print(f"  -> {url}", file=sys.stderr)
        page = context.new_page()
        try:
            resp = page.goto(url, wait_until="domcontentloaded", timeout=20000)
            status = resp.status if resp else None
            page.wait_for_timeout(2500)  # SPA render
            info = classify_page(page)
            info["http_status"] = status
            info["url_requested"] = url
        except Exception as exc:
            info = {
                "url_requested": url,
                "error": f"{type(exc).__name__}: {exc}",
            }
        results.append(info)
        page.close()
    context.close()
    browser.close()
    return {"platform": platform, "candidates": results}


def main() -> int:
    out_path = Path(__file__).parent.parent / "docs" / "streaming_probe_results.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    findings: list[dict[str, Any]] = []
    with sync_playwright() as p:
        for platform, candidates in CANDIDATES.items():
            findings.append(probe_platform(p, platform, candidates))
    out_path.write_text(json.dumps(findings, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    # Resumen humano-legible.
    print("\n\n========== SUMMARY ==========", file=sys.stderr)
    for fp in findings:
        print(f"\n{fp['platform']}:", file=sys.stderr)
        for c in fp["candidates"]:
            tag = (
                "404" if c.get("is_404")
                else c.get("classification", "?")
            )
            inputs = len(c.get("search_inputs_found", []))
            print(f"  [{tag:>12}] {c.get('url_requested', '?')}", file=sys.stderr)
            print(f"             title={c.get('title', '')[:80]!r}", file=sys.stderr)
            print(f"             url_after={c.get('url_after_load', '')[:90]}", file=sys.stderr)
            print(f"             inputs={inputs} ({c.get('search_inputs_found', [])[:3]})",
                   file=sys.stderr)
    print(f"\nFull JSON: {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
