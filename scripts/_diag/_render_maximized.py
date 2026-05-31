"""Render the app at a maximized viewport with data-maximized set, to verify
the instrument FILLS the window (bug fix) instead of staying compact+centered."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _render_ui_field as R  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

REPO = Path(__file__).resolve().parents[2]


def main():
    out = str(REPO / "_render_maximized.png")
    srv = R.serve(8763)
    url = "http://127.0.0.1:8763/index.html"
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            # maximized window size (typical 1080p screen content area)
            pg = b.new_page(viewport={"width": 1920, "height": 1040}, device_scale_factor=1)
            pg.add_init_script(R.ws_shim("idle"))
            pg.goto(url, wait_until="networkidle")
            pg.wait_for_timeout(800)
            # simulate the maximized state the TitleBar would set
            pg.evaluate("document.documentElement.setAttribute('data-maximized','true')")
            pg.wait_for_timeout(300)
            pg.screenshot(path=out)
            b.close()
        print("OK wrote", out)
        return 0
    finally:
        srv.shutdown()


if __name__ == "__main__":
    sys.exit(main())
