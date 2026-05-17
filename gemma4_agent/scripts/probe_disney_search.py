"""Investiga cómo disparar search desde Disney+ home SPA (logueado).

Carga la home, espera render, escanea por:
  - Botones con icono de busqueda (svg/aria 'search'/'buscar').
  - Links a search.
  - Inputs que aparecen tras click en lupa.
  - Estructura del search bar dentro de la SPA.

Reporta HTML excerpt de los matches.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:9222"


def main() -> int:
    out = Path(__file__).parent.parent / "docs" / "disney_search_probe.json"
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP)
        ctx = browser.contexts[0]
        page = ctx.new_page()
        page.goto("https://www.disneyplus.com/es-419/home",
                   wait_until="domcontentloaded", timeout=25000)
        time.sleep(6.0)  # SPA is slow

        findings = {}

        # 1. Search buttons / links visibles.
        button_candidates = [
            "button[aria-label*='search' i]",
            "button[aria-label*='buscar' i]",
            "a[aria-label*='search' i]",
            "a[aria-label*='buscar' i]",
            "a[href*='/search']",
            "[data-testid*='search' i]",
            "[data-gv2elementkey*='search' i]",
            "[data-test*='search' i]",
            "[data-uia*='search' i]",
            "nav button",
            "nav a",
            "[role='button'][aria-label*='buscar' i]",
            "[role='link'][aria-label*='buscar' i]",
            # Disney+ usa una nav con icons.
            "header button",
            "header a",
        ]
        buttons_found = []
        for sel in button_candidates:
            try:
                loc = page.locator(sel)
                cnt = loc.count()
                if cnt and cnt < 30:  # filtrar nav-button generico que mete mucho
                    for i in range(min(cnt, 10)):
                        try:
                            el = loc.nth(i)
                            aria = el.get_attribute("aria-label") or ""
                            txt = (el.inner_text(timeout=500) or "").strip()[:50]
                            href = el.get_attribute("href") or ""
                            data_testid = el.get_attribute("data-testid") or ""
                            if "search" in (aria + txt + href + data_testid).lower() \
                                    or "buscar" in (aria + txt + href + data_testid).lower() \
                                    or "lupa" in (aria + txt + data_testid).lower():
                                buttons_found.append({
                                    "selector_used": sel,
                                    "aria-label": aria,
                                    "text": txt,
                                    "href": href,
                                    "data-testid": data_testid,
                                })
                        except Exception:
                            pass
            except Exception:
                pass
        findings["buttons_matching_search"] = buttons_found

        # 2. Mirar HTML de la nav.
        try:
            nav_html = page.locator("nav").first.inner_html(timeout=3000)[:3000]
        except Exception:
            nav_html = ""
        findings["nav_html_excerpt"] = nav_html[:2500]

        # 3. Mirar HTML del header.
        try:
            hdr_html = page.locator("header").first.inner_html(timeout=3000)[:3000]
        except Exception:
            hdr_html = ""
        findings["header_html_excerpt"] = hdr_html[:2500]

        # 4. URL actual.
        findings["url"] = page.url
        findings["title"] = page.title()

        page.close()

    out.write_text(json.dumps(findings, indent=2, ensure_ascii=False),
                    encoding="utf-8")
    # Print summary.
    print(f"URL: {findings['url']}", file=sys.stderr)
    print(f"Title: {findings['title']}", file=sys.stderr)
    print(f"\n--- Buttons matching search ({len(findings['buttons_matching_search'])}) ---",
            file=sys.stderr)
    for b in findings["buttons_matching_search"]:
        print(f"  {b}", file=sys.stderr)
    print(f"\n--- Nav excerpt (2500c) ---\n{findings['nav_html_excerpt']}",
            file=sys.stderr)
    print(f"\n\nFull JSON: {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
