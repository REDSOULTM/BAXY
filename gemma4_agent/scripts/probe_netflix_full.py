"""Netflix full flow: select profile -> search -> click result -> find play."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:9222"
PROFILE_NAME = "Emmanuel"  # adjust if different


def main() -> int:
    out = Path(__file__).parent.parent / "docs" / "netflix_full_flow.json"
    f = {"steps": []}
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP)
        ctx = browser.contexts[0]
        page = ctx.new_page()
        page.goto("https://www.netflix.com/search?q=Stranger+Things",
                   wait_until="domcontentloaded", timeout=30000)
        time.sleep(7.0)
        f["url_initial"] = page.url
        f["steps"].append(f"goto:{f['url_initial']}")

        # Detect profile picker.
        picker_visible = False
        try:
            picker_visible = page.locator(
                "[data-uia='profile-gate'], [data-uia='action-select-profile+secondary']"
            ).count() > 0
        except Exception:
            pass
        f["profile_picker_visible"] = picker_visible

        if picker_visible:
            # Scan profiles list.
            profiles = page.evaluate(
                "() => Array.from(document.querySelectorAll('[data-uia=\"action-select-profile+secondary\"]'))"
                ".map(a => ({"
                "href: a.getAttribute('href') || '', "
                "text: (a.innerText || '').trim().slice(0, 40)"
                "}))"
            )
            f["available_profiles"] = profiles
            # Click the first profile (or named one if matches).
            target = None
            for pr in profiles:
                if PROFILE_NAME.lower() in (pr.get("text", "") or "").lower():
                    target = pr
                    break
            if not target and profiles:
                target = profiles[0]
            if target:
                # Click by href.
                f["picked_profile"] = target
                page.locator(
                    f"a[data-uia='action-select-profile+secondary'][href='{target['href']}']"
                ).first.click()
                f["steps"].append(f"clicked_profile:{target['text']}")
                time.sleep(8.0)  # Netflix loads search after profile pick
                f["url_after_profile"] = page.url

        # Now scan for search result cards. Netflix uses many selector shapes.
        # Look at all visible anchors with /watch/ in href.
        time.sleep(3.0)
        try:
            anchors = page.evaluate(
                "() => Array.from(document.querySelectorAll('a[href*=\"/watch/\"]'))"
                ".filter(a => a.offsetParent !== null)"
                ".slice(0, 15).map(a => ({"
                "href: a.getAttribute('href') || '', "
                "uia: a.getAttribute('data-uia') || '', "
                "aria: a.getAttribute('aria-label') || '', "
                "testid: a.getAttribute('data-testid') || ''"
                "}))"
            )
            f["watch_anchors"] = anchors
        except Exception as exc:
            f["anchors_error"] = str(exc)

        # Try clicking first watch link.
        try:
            wl = page.locator("a[href*='/watch/']").first
            href = wl.get_attribute("href") or ""
            f["first_watch_href"] = href
            wl.click(timeout=8000)
            f["steps"].append(f"clicked_watch:{href}")
            time.sleep(8.0)
            f["url_after_watch_click"] = page.url
        except Exception as exc:
            f["click_error"] = str(exc)

        # Scan play buttons on the page we landed on.
        try:
            buttons = page.evaluate(
                "() => Array.from(document.querySelectorAll('button, [role=\"button\"]'))"
                ".filter(e => e.offsetParent !== null)"
                ".slice(0, 30).map(e => ({"
                "tag: e.tagName, "
                "uia: e.getAttribute('data-uia') || '', "
                "testid: e.getAttribute('data-testid') || '', "
                "aria: e.getAttribute('aria-label') || '', "
                "text: (e.innerText || '').trim().slice(0, 60)"
                "})).filter(b => /play|watch|reproducir|ver/i.test((b.uia || '') + ' ' + (b.testid || '') + ' ' + (b.aria || '') + ' ' + (b.text || '')))"
            )
            f["play_candidates"] = buttons
        except Exception as exc:
            f["btn_error"] = str(exc)

        page.close()

    out.write_text(json.dumps(f, indent=2, ensure_ascii=False), encoding="utf-8")
    import sys as _s
    _s.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(f, indent=2, ensure_ascii=False)[:5000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
