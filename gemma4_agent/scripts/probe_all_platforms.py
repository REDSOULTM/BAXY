"""For each platform, do the full search->card->detail flow and report
the actual selectors that worked. Does NOT click play (avoid playback).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:9222"

PLATFORMS = [
    {
        "name": "netflix",
        "search_url": "https://www.netflix.com/search?q=Stranger+Things",
        "needs_fill": False,
        "card_sels": [
            "[data-uia='search-title-card-container'] a[href*='/watch/']",
            "[data-uia='title-card-container-wrapper'] a[href*='/watch/']",
            "[data-uia='search-title-card'] a[href*='/watch/']",
            "a[href*='/watch/']",
            "a[href*='/title/']",
        ],
    },
    {
        "name": "disney",
        "search_url": "https://www.disneyplus.com/es-419/browse/search",
        "needs_fill": True,
        "input_sel": "input[type='search']",
        "fill_value": "Loki",
        "card_sels": ["a[data-testid='set-item']"],
    },
    {
        "name": "hbo_max",
        "search_url": "https://play.hbomax.com/search?q=House+of+Dragon",
        "needs_fill": False,
        "card_sels": [
            "a[href*='/feature/']",
            "a[href*='/series/']",
            "a[href*='/movie/']",
            "a[href*='/video/watch/']",
            "a[href*='/show/']",
            "a[data-testid*='card']",
        ],
    },
    {
        "name": "prime_video",
        "search_url": "https://www.primevideo.com/search/ref=atv_nb_sr?phrase=The+Boys",
        "needs_fill": False,
        "card_sels": [
            "article a[href*='/detail/']",
            "a[href*='/detail/']",
        ],
    },
]

PLAY_SELS = [
    # Disney+
    "[data-testid='playback-action-button']",
    # Netflix
    "[data-uia='play-button']",
    "button[data-uia*='play' i]",
    # HBO Max
    "button[data-testid='playButton']",
    "[data-testid*='play' i]",
    # Prime Video
    "button[data-automation-id='playButton']",
    "[data-automation-id*='play' i]",
    # Generic
    "button[aria-label*='Reproducir' i]",
    "button[aria-label*='Ver ahora' i]",
    "button[aria-label*='Play' i]",
    "button[aria-label*='Watch' i]",
]


def main() -> int:
    out = Path(__file__).parent.parent / "docs" / "all_platforms_flow.json"
    results = []
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP)
        ctx = browser.contexts[0]

        for plat in PLATFORMS:
            print(f"\n=== {plat['name']} ===", file=sys.stderr)
            r = {"platform": plat["name"], "steps": []}
            page = ctx.new_page()
            try:
                page.goto(plat["search_url"], wait_until="domcontentloaded",
                          timeout=25000)
                time.sleep(5.0)
                r["url_after_search_load"] = page.url
                r["title"] = page.title()
                r["steps"].append(f"goto:{plat['search_url']}")

                if plat["needs_fill"]:
                    try:
                        page.fill(plat["input_sel"], plat["fill_value"])
                        time.sleep(4.5)
                        r["steps"].append(f"filled:{plat['input_sel']}")
                    except Exception as exc:
                        r["fill_error"] = str(exc)

                # Try each card selector.
                card_sel_used = None
                for sel in plat["card_sels"]:
                    try:
                        cnt = page.locator(sel).count()
                        if cnt > 0:
                            # Filter to actually-clickable results — first sample.
                            first = page.locator(sel).first
                            href = first.get_attribute("href") or ""
                            aria = first.get_attribute("aria-label") or ""
                            r[f"card_{sel}"] = {
                                "count": cnt, "first_href": href[:120],
                                "first_aria": aria[:120],
                            }
                            if card_sel_used is None:
                                card_sel_used = sel
                    except Exception:
                        pass

                if card_sel_used is None:
                    r["error"] = "no card selector matched"
                else:
                    r["card_sel_used"] = card_sel_used
                    try:
                        page.locator(card_sel_used).first.click(timeout=8000)
                        r["steps"].append(f"clicked_card:{card_sel_used}")
                        time.sleep(6.0)
                        r["url_after_card"] = page.url
                        r["title_after_card"] = page.title()

                        # Scan for play.
                        plays = []
                        for psel in PLAY_SELS:
                            try:
                                cnt = page.locator(psel).count()
                                if cnt:
                                    el = page.locator(psel).first
                                    plays.append({
                                        "sel": psel, "count": cnt,
                                        "aria-label": el.get_attribute("aria-label") or "",
                                        "data-testid": el.get_attribute("data-testid") or "",
                                        "visible": el.is_visible(),
                                        "text": (el.inner_text(timeout=500) or "")[:60],
                                    })
                            except Exception:
                                pass
                        r["play_buttons"] = plays
                    except Exception as exc:
                        r["click_error"] = str(exc)

            except Exception as exc:
                r["error"] = f"{type(exc).__name__}: {exc}"
            page.close()
            results.append(r)

    out.write_text(json.dumps(results, indent=2, ensure_ascii=False),
                    encoding="utf-8")
    # Summary.
    print("\n========== SUMMARY ==========", file=sys.stderr)
    for r in results:
        print(f"\n{r['platform']}:", file=sys.stderr)
        print(f"  search loaded -> {r.get('url_after_search_load', '?')[:90]}",
                file=sys.stderr)
        print(f"  card selector  -> {r.get('card_sel_used', 'NONE')}", file=sys.stderr)
        print(f"  detail URL    -> {r.get('url_after_card', '?')[:90]}", file=sys.stderr)
        for pb in (r.get("play_buttons") or []):
            print(f"  PLAY: {pb['sel']}  aria={pb['aria-label']!r:40}  "
                    f"testid={pb['data-testid']!r}  visible={pb['visible']}",
                    file=sys.stderr)
        if not r.get("play_buttons"):
            print("  PLAY: NONE FOUND", file=sys.stderr)
    print(f"\nJSON: {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
