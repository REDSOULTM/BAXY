"""Deep dive Netflix + HBO Max: wait longer for cards, scan all anchors."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:9222"


def scan_anchors(page, n_max=20):
    """Return a sample of all anchors visible on page."""
    out = []
    try:
        anchors = page.locator("a[href]")
        cnt = min(anchors.count(), n_max)
        for i in range(cnt):
            try:
                a = anchors.nth(i)
                if not a.is_visible():
                    continue
                href = a.get_attribute("href") or ""
                if not href or href.startswith("#") or href.startswith("javascript"):
                    continue
                aria = a.get_attribute("aria-label") or ""
                testid = a.get_attribute("data-testid") or ""
                uia = a.get_attribute("data-uia") or ""
                if href and (aria or testid or uia or "watch" in href or "title" in href
                              or "feature" in href or "movie" in href or "series" in href):
                    out.append({
                        "href": href[:100], "aria": aria[:60], "testid": testid,
                        "data-uia": uia,
                    })
            except Exception:
                continue
    except Exception:
        pass
    return out


def main() -> int:
    out_path = Path(__file__).parent.parent / "docs" / "netflix_hbo_deep.json"
    f = {}
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP)
        ctx = browser.contexts[0]

        # NETFLIX
        print("=== Netflix ===", file=sys.stderr)
        page = ctx.new_page()
        page.goto("https://www.netflix.com/search?q=Stranger+Things",
                   wait_until="domcontentloaded", timeout=30000)
        time.sleep(10.0)  # Netflix is heavy
        f["netflix_url"] = page.url
        f["netflix_title"] = page.title()
        f["netflix_anchors_sample"] = scan_anchors(page, 25)
        # Also try data-uia attribute scan.
        try:
            uias = page.evaluate(
                "() => Array.from(document.querySelectorAll('[data-uia]'))"
                ".slice(0, 30).map(e => ({tag: e.tagName, "
                "uia: e.getAttribute('data-uia'), "
                "href: e.getAttribute('href') || '', "
                "aria: e.getAttribute('aria-label') || ''}))"
            )
            f["netflix_data_uia_samples"] = uias
        except Exception as exc:
            f["netflix_uia_error"] = str(exc)
        page.close()

        # HBO Max
        print("=== HBO Max ===", file=sys.stderr)
        page = ctx.new_page()
        page.goto("https://play.hbomax.com/search?q=House+of+Dragon",
                   wait_until="domcontentloaded", timeout=30000)
        time.sleep(8.0)
        f["hbo_search_url"] = page.url
        f["hbo_search_title"] = page.title()
        f["hbo_anchors_sample"] = scan_anchors(page, 25)
        page.close()

        # HBO Max detail (House of Dragon).
        print("=== HBO Max detail ===", file=sys.stderr)
        page = ctx.new_page()
        page.goto("https://play.hbomax.com/movie/aad8e3ff-05d9-4325-a1eb-585ee5057ccf",
                   wait_until="domcontentloaded", timeout=30000)
        time.sleep(8.0)
        f["hbo_detail_url"] = page.url
        f["hbo_detail_title"] = page.title()
        # Scan for buttons that look like play.
        try:
            btn_info = page.evaluate(
                "() => Array.from(document.querySelectorAll('button, a, [role=\"button\"]'))"
                ".filter(e => e.offsetParent !== null)"  # visible
                ".slice(0, 40).map(e => ({"
                "tag: e.tagName, "
                "testid: e.getAttribute('data-testid') || '', "
                "aria: e.getAttribute('aria-label') || '', "
                "text: (e.innerText || '').trim().slice(0, 50), "
                "href: e.getAttribute('href') || ''"
                "})).filter(b => /play|watch|reproducir|ver/i.test(b.testid + ' ' + b.aria + ' ' + b.text))"
            )
            f["hbo_play_candidates"] = btn_info
        except Exception as exc:
            f["hbo_btn_error"] = str(exc)
        page.close()

    out_path.write_text(json.dumps(f, indent=2, ensure_ascii=False),
                          encoding="utf-8")
    print(json.dumps(f, indent=2, ensure_ascii=False)[:6000], file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
