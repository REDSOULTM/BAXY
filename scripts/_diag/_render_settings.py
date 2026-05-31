"""Render the settings modal (app build) open on the 'toggles' tab so I can
verify the STCheck checkmark glyph renders. Reuses the WS/REST mocks pattern."""
from __future__ import annotations
import sys
from pathlib import Path
# import the mock server + ws_shim from the sibling render harness
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _render_ui_field as R  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

REPO = Path(__file__).resolve().parents[2]


def main():
    out = str(REPO / "_render_settings.png")
    tab = sys.argv[1] if len(sys.argv) > 1 else "toggles"
    srv = R.serve(8762)
    url = "http://127.0.0.1:8762/index.html"
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(viewport={"width": 1080, "height": 640}, device_scale_factor=2)
            pg.add_init_script(R.ws_shim("idle"))
            pg.goto(url, wait_until="networkidle")
            pg.wait_for_timeout(800)
            # open settings via the labeled toolbar button
            pg.click("text=settings")
            pg.wait_for_timeout(400)
            # click the requested tab
            try:
                pg.click(f".settings-tabs >> text={tab}")
                pg.wait_for_timeout(300)
            except Exception as e:  # noqa: BLE001
                print("tab click failed:", e)
            pg.screenshot(path=out)
            b.close()
        print("OK wrote", out)
        return 0
    finally:
        srv.shutdown()


if __name__ == "__main__":
    sys.exit(main())
