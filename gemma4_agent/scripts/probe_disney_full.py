"""Full Disney+ flow: search -> click result -> find play button on detail."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:9222"


def main() -> int:
    out = Path(__file__).parent.parent / "docs" / "disney_full_flow.json"
    f = {"steps": []}
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP)
        ctx = browser.contexts[0]
        page = ctx.new_page()

        page.goto("https://www.disneyplus.com/es-419/browse/search",
                   wait_until="domcontentloaded", timeout=25000)
        time.sleep(5.0)
        f["steps"].append(f"on_search:{page.url}")

        page.fill("input[type='search']", "Loki")
        time.sleep(4.5)
        f["steps"].append("filled_Loki")

        # Use the correct card selector: data-testid='set-item'.
        # First sample card href contains '/browse/entity-'.
        card_sel = "a[data-testid='set-item']"
        count = page.locator(card_sel).count()
        f["cards_found"] = count
        if count == 0:
            # Fallback: any anchor with /browse/entity- in href.
            card_sel = "a[href*='/browse/entity-']"
            count = page.locator(card_sel).count()
            f["cards_found_fallback"] = count

        if count == 0:
            f["error"] = "no result cards"
            page.close()
        else:
            # Click first.
            first = page.locator(card_sel).first
            href = first.get_attribute("href") or ""
            aria = first.get_attribute("aria-label") or ""
            f["first_card_href"] = href
            f["first_card_aria"] = aria

            first.click()
            f["steps"].append(f"clicked_card:{card_sel}")
            time.sleep(6.0)  # detail page load
            f["url_after_card_click"] = page.url
            f["title_after_card_click"] = page.title()

            # Now scan ALL buttons/divs on detail page for play.
            play_sels = [
                # Disney+ uses generated class names, so target by role+text/aria.
                "button[data-testid='play']",
                "button[data-testid*='play' i]",
                "[data-testid*='play-button' i]",
                "[data-testid*='play_button' i]",
                "[data-testid*='play' i]",
                "[data-gv2elementkey*='play' i]",
                "button[aria-label*='Reproducir' i]",
                "button[aria-label*='Play' i]",
                "a[aria-label*='Reproducir' i]",
                "[role='button'][aria-label*='Reproducir' i]",
            ]
            playb = []
            for sel in play_sels:
                try:
                    cnt = page.locator(sel).count()
                    if cnt:
                        el = page.locator(sel).first
                        playb.append({
                            "sel": sel, "count": cnt,
                            "aria-label": el.get_attribute("aria-label") or "",
                            "data-testid": el.get_attribute("data-testid") or "",
                            "visible": el.is_visible(),
                            "text": (el.inner_text(timeout=500) or "")[:60],
                        })
                except Exception:
                    pass
            f["play_buttons_found"] = playb

            # Also grab a chunk of the detail page main element so we can see
            # what the play button looks like.
            try:
                main_html = page.locator("main").first.inner_html(timeout=3000)[:5000]
            except Exception:
                try:
                    main_html = page.locator("body").first.inner_html(timeout=3000)[:5000]
                except Exception:
                    main_html = ""
            f["main_html_excerpt"] = main_html

            # Don't click play (could start playback). Stop here.
            page.close()

    out.write_text(json.dumps(f, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(f, indent=2, ensure_ascii=False)[:5000], file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
