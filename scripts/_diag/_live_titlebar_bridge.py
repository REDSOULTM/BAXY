"""LIVE verification of the custom title bar window controls (CLAUDE.md #3.5).

Opens a REAL frameless pywebview window serving the REAL dist/ build, with the
SAME _WindowControls js_api the launcher wires, then exercises the controls
end-to-end and asserts the native window actually reacts. Verifies WITHOUT
synthetic mouse input (forbidden here — SendInput closes VS Code; see memory
feedback_never_run_synthetic_input_*): it drives the window through the exact
controller methods the title-bar buttons call, and inspects the DOM/bridge with
a single guarded evaluate_js.

The static server is a minimal FastAPI app (NOT create_app — no agent/LLM) that
ALSO answers the `/events` WebSocket. That matters: a plain stdlib HTTP server
can't speak WebSocket, and the React app's WS reconnect storm against it wedges
the EdgeChromium renderer (measured: worker thread freezes ~1s after load). A
real WS endpoint keeps the renderer responsive so the bridge can be tested.

No GPU competition (forces --disable-gpu like the launcher), no LLM.
Run:  python scripts/_diag/_live_titlebar_bridge.py    (exit 0 = all passed)
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

# Force CPU compositing BEFORE webview/WebView2 inits (launcher.py does the same
# so the WebView2 GPU process can't crash the window out from under us).
os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = "--disable-gpu --disable-gpu-compositing"

import webview  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
DIST = REPO / "gemma4_agent" / "ui_field" / "dist"
RESULT_FILE = REPO / "_live_titlebar_result.txt"

MODEL = {"family": "gemma 4", "params": "7.2b", "runtime": "local",
         "quant": "q4_k_m", "size_bytes": 1, "name_full": "g",
         "context_size": 16384, "mmproj": False}
SURFACES = {"sessions": 16, "memory": 1, "triggers": 6, "tools": 68}
REST = {
    "/model": MODEL,
    "/metrics": {"cpu": 43, "mem": 41, "mem_used_gb": 13.1, "gpu": 33, "net": 1.2,
                 "dsk": 37, "tmp": 50, "uptime": "01:34:16", "placeholder": {}},
    "/surfaces": SURFACES,
    "/profile": {"active": "vram4"}, "/accessibility": {"active": "normal"},
    "/agent/status": {"built": True, "healthy": True, "ready": True},
    "/voice/status": {"running": False},
}

RESULTS = []


def _emit(line: str):
    print(line, flush=True)
    with open(RESULT_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n"); f.flush()


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    _emit(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


# ---- minimal FastAPI app: static dist + REST mocks + /events WebSocket ----
def build_app():
    from fastapi import FastAPI, WebSocket
    from fastapi.responses import JSONResponse
    from fastapi.staticfiles import StaticFiles

    app = FastAPI()

    for path, payload in REST.items():
        app.add_api_route(path, (lambda p=payload: JSONResponse(p)), methods=["GET"])

    @app.post("/{rest:path}")
    def _any_post(rest: str):
        return JSONResponse({"ok": True, "running": False})

    @app.websocket("/events")
    async def events(ws: WebSocket):
        await ws.accept()
        for ev in (
            {"type": "model", "info": MODEL},
            {"type": "ctx", "used": 15564, "budget": 16384},
            {"type": "surfaces", **SURFACES},
            {"type": "agent", "built": True, "healthy": True, "ready": True},
            {"type": "state", "value": "idle"},
        ):
            await ws.send_text(json.dumps(ev))
        # idle so the client stays connected (no reconnect storm)
        try:
            while True:
                await ws.receive_text()
        except Exception:  # noqa: BLE001
            pass

    app.mount("/", StaticFiles(directory=str(DIST), html=True), name="ui")
    return app


# Same controller as launcher.py _WindowControls (kept in sync intentionally).
# CRITICAL: store the Window as _window (underscore). pywebview's get_functions
# introspects the js_api with dir() and recurses into public non-callable attrs;
# a public self.window=<Window> makes it walk window.native's circular .NET tree
# → RecursionError storm. Underscore names are skipped, so _window is invisible.
class _WindowControls:
    def __init__(self):
        self._window = None
        self._maximized = False

    def win_minimize(self):
        if self._window is not None:
            self._window.minimize()

    def win_toggle_maximize(self) -> bool:
        if self._window is None:
            return self._maximized
        if self._maximized:
            self._window.restore(); self._maximized = False
        else:
            self._window.maximize(); self._maximized = True
        return self._maximized

    def win_is_maximized(self) -> bool:
        return self._maximized

    def win_close(self):
        if self._window is not None:
            self._window.destroy()


def _eval_guarded(window, js, timeout=6.0):
    box = {}

    def _run():
        try:
            box["v"] = window.evaluate_js(js)
        except Exception as e:  # noqa: BLE001
            box["err"] = e
    th = threading.Thread(target=_run, daemon=True)
    th.start(); th.join(timeout)
    if th.is_alive():
        return None, "timeout"
    return box.get("v"), box.get("err")


def run_checks(window, controls: _WindowControls):
    _emit("run_checks started (GUI loop is up)")
    try:
        time.sleep(3.0)  # React mount + pywebview bridge injection

        dom, err = _eval_guarded(window, """
        (function(){
          const tb = document.querySelector('.titlebar');
          const drag = document.querySelector('.pywebview-drag-region');
          const btns = document.querySelectorAll('.titlebar-controls .winbtn');
          const close = document.querySelector('.winbtn-close');
          let inside = false;
          if (drag) btns.forEach(b => { if (drag.contains(b)) inside = true; });
          var apiKeys = (window.pywebview && window.pywebview.api)
            ? Object.keys(window.pywebview.api) : [];
          return JSON.stringify({
            tb: !!tb, drag: !!drag, n: btns.length, close: !!close, inside: inside,
            api: !!(window.pywebview && window.pywebview.api && window.pywebview.api.win_minimize),
            apiKeys: apiKeys
          });
        })()
        """)
        if isinstance(dom, str):
            dom = json.loads(dom)
        if not isinstance(dom, dict):
            check("DOM/bridge evaluate_js returned data", False, f"got {dom!r} err={err}")
            dom = {}
        else:
            check("DOM/bridge evaluate_js returned data", True)
        check("titlebar rendered", dom.get("tb") is True)
        check("drag-region present (.pywebview-drag-region)", dom.get("drag") is True)
        check("exactly 3 window buttons", dom.get("n") == 3, f"n={dom.get('n')}")
        check("close button present", dom.get("close") is True)
        check("buttons NOT inside drag region (click won't drag window)",
              dom.get("inside") is False)
        check("window.pywebview.api.win_minimize exposed to JS", dom.get("api") is True)
        # REGRESSION GUARD: api must expose ONLY the win_* controller methods —
        # NOT a recursively-introspected '_window'/'native' tree (the bug that
        # caused the 'maximum recursion depth' storm). 4 win_* methods, no more.
        api_keys = set(dom.get("apiKeys") or [])
        expected = {"win_minimize", "win_toggle_maximize", "win_is_maximized", "win_close"}
        check("api exposes ONLY the 4 win_* methods (no native-tree recursion)",
              api_keys == expected, f"keys={sorted(api_keys)}")

        # Drive the native window through the SAME methods the JS buttons call.
        w0, h0 = window.width, window.height
        controls.win_toggle_maximize()  # == maximize button
        time.sleep(1.0)
        w1, h1 = window.width, window.height
        check("maximize grows the window (native)", (w1 * h1) > (w0 * h0),
              f"{w0}x{h0} -> {w1}x{h1}")
        check("controller tracks maximized=True", controls.win_is_maximized() is True)

        controls.win_toggle_maximize()  # == restore button
        time.sleep(1.0)
        w2, h2 = window.width, window.height
        check("restore returns to ~original size (native)",
              abs(w2 - w0) <= 48 and abs(h2 - h0) <= 48, f"-> {w2}x{h2} (orig {w0}x{h0})")
        check("controller tracks maximized=False", controls.win_is_maximized() is False)

        try:
            controls.win_minimize()  # == minimize button
            time.sleep(0.6)
            window.restore()
            check("minimize executes without error (native)", True)
        except Exception as e:  # noqa: BLE001
            check("minimize executes without error (native)", False, str(e))

    finally:
        try:
            controls.win_close()  # == close button (destroys window)
            check("close destroys the window (native)", True)
        except Exception as e:  # noqa: BLE001
            check("close destroys the window (native)", False, str(e))
            try:
                window.destroy()
            except Exception:  # noqa: BLE001
                pass


def main():
    import uvicorn

    if not (DIST / "index.html").exists():
        _emit(f"FATAL: no build at {DIST}")
        return 1

    RESULT_FILE.write_text("", encoding="utf-8")
    _emit("opening real frameless pywebview window (real dist build + WS)…")

    port = 8758
    cfg = uvicorn.Config(build_app(), host="127.0.0.1", port=port, log_level="critical")
    server = uvicorn.Server(cfg)
    threading.Thread(target=server.run, daemon=True).start()
    # wait for bind
    import socket
    for _ in range(80):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.05)

    controls = _WindowControls()
    window = webview.create_window(
        "gemma 4 · field [bridge test]",
        f"http://127.0.0.1:{port}/index.html",
        js_api=controls, width=1080, height=640, min_size=(1000, 600),
        background_color="#0A0E14", frameless=True, easy_drag=False,
    )
    controls._window = window

    def watchdog():
        time.sleep(30)
        _emit("watchdog: forcing window destroy")
        try:
            window.destroy()
        except Exception:  # noqa: BLE001
            pass
    threading.Thread(target=watchdog, daemon=True).start()

    webview.start(run_checks, (window, controls), http_server=False)
    server.should_exit = True

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    _emit("=== SUMMARY ===")
    _emit(f"{passed}/{len(RESULTS)} checks passed")
    return 0 if (RESULTS and passed == len(RESULTS)) else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
