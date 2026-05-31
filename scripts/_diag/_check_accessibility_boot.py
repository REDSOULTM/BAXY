"""Verify the accessibility-mode boot fix (CLAUDE.md #3.5 — observe real behavior):
 - backend /accessibility (persisted "last config") wins over stale localStorage
 - reconciling the backend value does NOT fire a redundant PUT (no spurious
   'accessibility · X' activity entry on boot)

Seeds localStorage with a STALE 'no_vidente', mocks GET /accessibility -> 'normal',
counts PUT /accessibility calls, and reads the highlighted profile chip.
"""
from __future__ import annotations
import json
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[2]
DIST = REPO / "gemma4_agent" / "ui_field" / "dist"

REST_GET = {
    "/model": {"family": "gemma 4", "params": "7.2b", "runtime": "local",
               "quant": "q4_k_m", "size_bytes": 1, "name_full": "g",
               "context_size": 16384, "mmproj": False},
    "/metrics": {"cpu": 10, "mem": 10, "gpu": 5, "net": 0, "dsk": 20, "tmp": 40,
                 "uptime": "00:00:01", "placeholder": {}},
    "/surfaces": {"sessions": 0, "memory": 0, "triggers": 0, "tools": 0},
    "/profile": {"active": "vram4"},
    "/accessibility": {"active": "normal", "modes": []},   # backend = normal
    "/agent/status": {"built": True, "healthy": True, "ready": True},
    "/voice/status": {"running": False},
}

PUT_LOG = []  # records PUT /accessibility bodies


class H(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, o):
        b = json.dumps(o).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        p = self.path.split("?")[0]
        if p in REST_GET:
            self._json(REST_GET[p]); return
        super().do_GET()

    def do_PUT(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode() if length else ""
        if self.path.split("?")[0] == "/accessibility":
            PUT_LOG.append(body)
        self._json({"ok": True, "active": "normal", "display_name": "Normal"})

    def do_POST(self):
        self._json({"ok": True})


def main():
    port = 8764
    srv = ThreadingHTTPServer(("127.0.0.1", port), partial(H, directory=str(DIST)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{port}/index.html"
    ok = True
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            ctx = b.new_context(viewport={"width": 1080, "height": 640})
            pg = ctx.new_page()
            # seed a STALE localStorage value BEFORE the app script runs
            pg.add_init_script(
                "try{localStorage.setItem('field.accessMode','no_vidente');}catch(e){}"
            )
            pg.goto(url, wait_until="networkidle")
            pg.wait_for_timeout(1500)  # let mount + GET reconcile + any PUT settle

            # which accessibility row is highlighted (.prow.on)?
            active = pg.evaluate(
                "(() => { const el = document.querySelector('.prow.on .prow-lbl');"
                " return el ? el.textContent.trim() : null; })()"
            )
            puts = list(PUT_LOG)
            b.close()

        print("PUT /accessibility calls during boot:", puts)
        print("highlighted profile row:", repr(active))
        # backend value (normal) must win over stale localStorage (no_vidente)
        c1 = active == "normal"
        print(f"  [{'PASS' if c1 else 'FAIL'}] UI adopts backend 'normal' (not stale 'no vidente')")
        ok = ok and c1
        # no PUT should have fired (reconcile suppressed; user didn't change anything)
        c2 = len(puts) == 0
        print(f"  [{'PASS' if c2 else 'FAIL'}] no redundant PUT on boot (got {len(puts)})")
        ok = ok and c2
    finally:
        srv.shutdown()
    print("RESULT:", "ALL PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
