"""Test the REAL Disney+ search URL: /es-419/browse/search.
Fills search, clicks first result, looks for play button.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:9222"


def main() -> int:
    out = Path(__file__).parent.parent / "docs" / "disney_search_real.json"
    findings = {"steps": []}
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP)
        ctx = browser.contexts[0]
        page = ctx.new_page()

        # 1. Go to real search URL.
        url = "https://www.disneyplus.com/es-419/browse/search"
        page.goto(url, wait_until="domcontentloaded", timeout=25000)
        time.sleep(5.0)
        findings["url_after_load"] = page.url
        findings["title"] = page.title()
        findings["steps"].append("goto_search_page")

        # 2. Enumerate inputs visible.
        input_sels = [
            "input[type='search']",
            "input[role='searchbox']",
            "input[aria-label*='search' i]",
            "input[aria-label*='buscar' i]",
            "input[placeholder*='search' i]",
            "input[placeholder*='buscar' i]",
            "input[data-testid*='search' i]",
            "input",  # broad
        ]
        inputs_info = []
        for sel in input_sels:
            try:
                cnt = page.locator(sel).count()
                if cnt:
                    el = page.locator(sel).first
                    inputs_info.append({
                        "sel": sel,
                        "count": cnt,
                        "aria-label": el.get_attribute("aria-label") or "",
                        "placeholder": el.get_attribute("placeholder") or "",
                        "data-testid": el.get_attribute("data-testid") or "",
                        "name": el.get_attribute("name") or "",
                    })
            except Exception:
                pass
        findings["inputs_on_search_page"] = inputs_info

        # 3. Probar tipear en el primer input.
        try:
            search_input = None
            for sel in ["input[type='search']", "input[aria-label*='buscar' i]",
                         "input[placeholder*='buscar' i]",
                         "input[data-testid*='search' i]"]:
                if page.locator(sel).count():
                    search_input = sel
                    break
            if search_input:
                page.fill(search_input, "Loki")
                findings["steps"].append(f"filled:{search_input}")
                time.sleep(4.0)  # esperar resultados
                findings["url_after_fill"] = page.url
            else:
                findings["steps"].append("no_input_found")
        except Exception as exc:
            findings["fill_error"] = str(exc)

        # 4. Buscar result cards.
        card_sels = [
            "[data-testid*='card']",
            "a[href*='/es-419/video/']",
            "a[href*='/es-419/movies/']",
            "a[href*='/es-419/series/']",
            "a[href*='/es-419/browse/']",
            "[role='tab'] a",
            "[data-testid*='search-result']",
        ]
        cards_info = []
        for sel in card_sels:
            try:
                cnt = page.locator(sel).count()
                if cnt:
                    samples = []
                    for i in range(min(cnt, 3)):
                        try:
                            el = page.locator(sel).nth(i)
                            samples.append({
                                "href": el.get_attribute("href") or "",
                                "aria-label": el.get_attribute("aria-label") or "",
                                "data-testid": el.get_attribute("data-testid") or "",
                            })
                        except Exception:
                            pass
                    cards_info.append({"sel": sel, "count": cnt, "samples": samples})
            except Exception:
                pass
        findings["result_cards"] = cards_info

        # 5. Si encontramos card, intentar click + scan detail page.
        clicked_card = None
        for ci in cards_info:
            if ci["count"] > 0 and ci["samples"]:
                first_sel = ci["sel"]
                try:
                    page.locator(first_sel).first.click(timeout=8000)
                    clicked_card = first_sel
                    findings["steps"].append(f"clicked_card:{first_sel}")
                    time.sleep(5.0)  # detail page load
                    findings["url_after_click"] = page.url
                    break
                except Exception as exc:
                    findings["click_errors"] = findings.get("click_errors", [])
                    findings["click_errors"].append({"sel": first_sel, "error": str(exc)})

        # 6. Buscar play button en detail page.
        play_sels = [
            "button[data-testid='play']",
            "button[data-testid*='play' i]",
            "[data-testid='hero-play-cta']",
            "button[aria-label*='Reproducir' i]",
            "button[aria-label*='Play' i]",
            "a[data-testid*='play' i]",
        ]
        play_info = []
        for sel in play_sels:
            try:
                cnt = page.locator(sel).count()
                if cnt:
                    el = page.locator(sel).first
                    play_info.append({
                        "sel": sel,
                        "count": cnt,
                        "aria-label": el.get_attribute("aria-label") or "",
                        "data-testid": el.get_attribute("data-testid") or "",
                        "visible": el.is_visible(),
                    })
            except Exception:
                pass
        findings["play_buttons_on_detail"] = play_info

        page.close()

    out.write_text(json.dumps(findings, indent=2, ensure_ascii=False),
                    encoding="utf-8")
    print(json.dumps(findings, indent=2, ensure_ascii=False), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
