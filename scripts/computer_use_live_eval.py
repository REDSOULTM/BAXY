"""Live, local-only computer_use eval.

This is the safe live counterpart to the dry-run mission evals. It opens a
localhost page in the user's real default browser and exercises computer_use
against that disposable surface. It does not use real accounts, purchases,
system settings, personal files, or external websites.
"""
from __future__ import annotations

import argparse
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>localhost CU Live Eval</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 40px; }
    label { display: block; margin: 16px 0 6px; }
    input[type="email"] { font-size: 18px; padding: 8px; width: 320px; }
    .status { margin-top: 24px; font-weight: 700; }
  </style>
</head>
<body>
  <h1>Computer Use Live Eval</h1>
  <p id="ready">Ready</p>
  <label for="email">Email</label>
  <input id="email" name="email" type="email" aria-label="Email" autocomplete="off">
  <label for="terms">
    <input id="terms" name="terms" type="checkbox" aria-label="Terms">
    Terms
  </label>
  <div class="status" id="status">Waiting</div>
  <script>
    const email = document.getElementById("email");
    const terms = document.getElementById("terms");
    const status = document.getElementById("status");
    function update() {
      status.textContent = (email.value && terms.checked) ? "Done" : "Waiting";
    }
    email.addEventListener("input", update);
    terms.addEventListener("change", update);
  </script>
</body>
</html>
"""


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args: Any) -> None:
        return None


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _start_server(root: Path) -> tuple[ThreadingHTTPServer, int]:
    port = _free_port()

    class Handler(_QuietHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(root), **kwargs)

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port


class _Trace:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def event(self, turn_id: str, name: str, **payload: Any) -> None:
        self.events.append({"turn_id": turn_id, "name": name, **payload})


class _Agent:
    def __init__(self, tools: Any) -> None:
        self.tools = tools
        self.trace = _Trace()

    def _window_title_in_text(self, _text: str) -> str:
        return ""

    def _app_window_title(self, _text: str) -> str:
        return ""


def run_live() -> dict[str, Any]:
    from gemma4_agent.memory import MemoryStore
    from gemma4_agent.state import AgentState
    from gemma4_agent.tools import ToolRegistry
    from gemma4_agent.computer_use import PlanExecutor, summarize_result

    with tempfile.TemporaryDirectory(prefix="gemma4_cu_live_") as tmp_s:
        tmp = Path(tmp_s)
        (tmp / "index.html").write_text(HTML, encoding="utf-8")
        server, port = _start_server(tmp)
        try:
            state = AgentState(tmp / "state.json")
            memory = MemoryStore(tmp / "memory.json")
            tools = ToolRegistry(memory, tmp / "captures", state=state, safety_enabled=True)
            agent = _Agent(tools)
            executor = PlanExecutor(agent)
            url = f"http://localhost:{port}/index.html"
            plan = [
                {"op": "open_url", "arg": url},
                {"op": "wait_for", "arg": "Ready"},
                {"op": "fill_field", "arg": "Email=ana@example.com"},
                {"op": "toggle", "arg": "Terms=on"},
                {"op": "wait_for", "arg": "Done"},
            ]
            result = executor.execute(plan, turn_id="cu_live_eval")
            reply = summarize_result("rellenar formulario local descartable", plan, result)
            return {
                "ok": bool(result.get("ok")),
                "verified": result.get("verified") is True,
                "url": url,
                "reply": reply,
                "result": result,
                "trace_events": agent.trace.events,
            }
        finally:
            server.shutdown()
            server.server_close()
            time.sleep(0.2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    data = run_live()
    if args.json:
        print(json.dumps(data, ensure_ascii=True, indent=2))
    else:
        print("COMPUTER_USE_LIVE_EVAL localhost")
        print("ok:", data["ok"])
        print("verified:", data["verified"])
        print("url:", data["url"])
        print("reply:", data["reply"])
        for step in data.get("result", {}).get("steps", []):
            print(
                f" - {step.get('op')}: ok={step.get('ok')} "
                f"verified={step.get('verified')} method={step.get('method')} "
                f"policy={(step.get('capability_policy') or {}).get('primary')}"
            )
    return 0 if data["ok"] and data["verified"] else 1


if __name__ == "__main__":
    sys.exit(main())
