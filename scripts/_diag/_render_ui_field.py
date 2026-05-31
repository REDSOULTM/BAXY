"""Render the ui_field React build at the launcher's exact viewport and
screenshot it, so visual changes can be diffed against the target PNG WITHOUT
booting the whole agent. (CLAUDE.md #3 "medí, no celebres" / #3.5 "ver el render".)

It serves dist/ statically, intercepts the REST endpoints with realistic values
(matching comodeberiaverse.png), and injects a fake WebSocket so the activity
log / model / surfaces / state populate exactly like the live UI. No GPU, no LLM.

Usage:
    python scripts/_diag/_render_ui_field.py [out.png] [--state idle]

The viewport (1080x640) and the dark page bg (#0A0E14) mirror launcher.py's
webview.create_window(width=1080, height=640, background_color="#0A0E14").
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[2]
DIST = REPO / "gemma4_agent" / "ui_field" / "dist"

# ---- REST mocks: numbers chosen to match comodeberiaverse.png ----
MODEL = {
    "family": "gemma 4", "params": "7.2b", "runtime": "local", "quant": "q4_k_m",
    "size_bytes": 4_800_000_000, "name_full": "gemma-4-7.2b-q4_k_m",
    "context_size": 16384, "mmproj": True,
}
METRICS = {
    "cpu": 43, "mem": 41, "mem_used_gb": 13.1, "gpu": 33, "net": 1.2,
    "dsk": 37, "tmp": 50, "uptime": "01:34:16",
    "placeholder": {},
}
SURFACES = {"sessions": 16, "memory": 1, "triggers": 6, "tools": 68}
PROFILE = {"active": "vram4"}
ACCESS = {"active": "normal"}
AGENT = {"built": True, "healthy": True, "ready": True}
VOICE = {"running": True}

REST = {
    "/model": MODEL, "/metrics": METRICS, "/surfaces": SURFACES,
    "/profile": PROFILE, "/accessibility": ACCESS, "/agent/status": AGENT,
    "/voice/status": VOICE,
}

# Activity entries mirroring the target's colored-tag list.
NOW = "21:25"
ACTIVITY = [
    ("BOOT", "loading semantic router · BertModel + tool embeddings (background)", "21:24:30"),
    ("SYSTEM", "agent ready · 68 tools loaded", "21:24:30"),
    ("BOOT", "building agent · loading tools and memory…", "21:24:30"),
    ("SYSTEM", "llama-server online · http://127.0.0.1:8080", "21:24:30"),
    ("SYSTEM", "KV prewarm done in 1.4s (16738 chars)", "21:24:30"),
    ("CONTEXT", "1 tools · session", "21:24:43"),
    ("YOU", "Hola.", "21:24:37"),
    ("GEMMA", "Hola. ¿En qué puedo ayudarte hoy?", "21:24:45"),
    ("MEMORY", "consolidated 6 short-term traces into long-term.", "21:24:50"),
    ("TRIGGER", "calendar · no pending alerts.", "21:24:55"),
    ("THOUGHT", "watching · nothing demands attention.", "21:25:00"),
]


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *a):  # silence
        pass

    def _json(self, obj):
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in REST:
            self._json(REST[path])
            return
        super().do_GET()

    def do_POST(self):
        self._json({"ok": True})


def serve(port: int) -> ThreadingHTTPServer:
    h = partial(Handler, directory=str(DIST))
    srv = ThreadingHTTPServer(("127.0.0.1", port), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


# Fake WebSocket installed before the app's JS runs, so useEventStream gets a
# live feed (state + model + ctx + surfaces + activity) without a real backend.
def ws_shim(state: str) -> str:
    events = [{"type": "model", "info": MODEL},
              {"type": "ctx", "used": 15564, "budget": 16384},
              {"type": "surfaces", **SURFACES},
              {"type": "session", "id": "526fef04df07", "label": "session"},
              {"type": "agent", **AGENT},
              {"type": "state", "value": state}]
    for tag, msg, ts in ACTIVITY:
        events.append({"type": "activity", "entry": {
            "id": f"{tag}-{ts}", "src": tag, "msg": msg, "ts": ts}})
    payload = json.dumps(events)
    return """
    (function() {
      const EVENTS = %s;
      const RealWS = window.WebSocket;
      class FakeWS {
        constructor(url) {
          this.url = url; this.readyState = 0;
          this.onopen=null; this.onmessage=null; this.onerror=null; this.onclose=null;
          setTimeout(() => {
            this.readyState = 1;
            if (this.onopen) this.onopen({});
            for (const ev of EVENTS) {
              if (this.onmessage) this.onmessage({ data: JSON.stringify(ev) });
            }
          }, 30);
        }
        send() {}
        close() { this.readyState = 3; if (this.onclose) this.onclose({}); }
        addEventListener(t, cb) { this['on'+t] = cb; }
        removeEventListener() {}
      }
      FakeWS.CONNECTING=0; FakeWS.OPEN=1; FakeWS.CLOSING=2; FakeWS.CLOSED=3;
      window.WebSocket = FakeWS;
    })();
    """ % payload


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out", nargs="?", default=str(REPO / "_render_ui_field.png"))
    ap.add_argument("--state", default="idle")
    ap.add_argument("--port", type=int, default=8757)
    ap.add_argument("--freeze", action="store_true",
                    help="pause animations + fix border angle for a fair diff")
    args = ap.parse_args()

    if not (DIST / "index.html").exists():
        print(f"FATAL: no build at {DIST}; run `pnpm build` first", file=sys.stderr)
        return 1

    srv = serve(args.port)
    url = f"http://127.0.0.1:{args.port}/index.html"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(
                viewport={"width": 1080, "height": 640},
                device_scale_factor=2,  # crisp for diffing
            )
            page.add_init_script(ws_shim(args.state))
            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(900)  # let metrics poll + WS events settle
            if args.freeze:
                page.add_style_tag(content=(
                    "*,*::before,*::after{animation-play-state:paused!important;"
                    "animation-duration:0s!important;transition:none!important;}"
                    ".app-frame{--bd-angle:90deg!important;}"
                ))
                page.wait_for_timeout(300)
            page.screenshot(path=args.out)
            browser.close()
        print(f"OK wrote {args.out}")
        return 0
    finally:
        srv.shutdown()


if __name__ == "__main__":
    sys.exit(main())
