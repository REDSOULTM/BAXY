"""Render the OFFICIAL design-handoff prototype (design_handoff_carter_field/
prototype/index.html) with Playwright, border animation frozen, so it can be
diffed against the app build. This is the real source of truth (the PNG is just
one animation frame of it). Serves the prototype dir over HTTP so the relative
component scripts + Google fonts/React CDN load.

Usage: python scripts/_diag/_render_handoff_proto.py [out.png]
"""
from __future__ import annotations
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[2]
PROTO = REPO / "design_handoff_carter_field" / "prototype"

# Freeze the traveling border + all animations so two screenshots are comparable.
FREEZE_CSS = """
*, *::before, *::after {
  animation-play-state: paused !important;
  animation-duration: 0s !important;
  transition: none !important;
}
.app-frame { --bd-angle: 90deg !important; }
"""


class H(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else str(REPO / "_render_proto.png")
    port = 8761
    srv = ThreadingHTTPServer(("127.0.0.1", port), partial(H, directory=str(PROTO)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(viewport={"width": 1080, "height": 640}, device_scale_factor=2)
            pg.goto(f"http://127.0.0.1:{port}/index.html", wait_until="networkidle")
            pg.wait_for_timeout(1500)  # babel compile + fonts + first paint
            pg.add_style_tag(content=FREEZE_CSS)
            pg.wait_for_timeout(400)
            pg.screenshot(path=out)
            b.close()
        print(f"OK wrote {out}")
        return 0
    finally:
        srv.shutdown()


if __name__ == "__main__":
    sys.exit(main())
