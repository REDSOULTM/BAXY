"""Navigate to a local synthetic page and click a visible web button via BAXY."""

from __future__ import annotations

import argparse
import http.server
import json
import os
import queue
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import psutil


PAGE = b"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>BAXY local click audit</title></head>
<body>
<main>
<h1>BAXY local click audit</h1>
<button aria-label="BAXY audit web button"
 onclick="this.disabled=true;this.textContent='Clicked and disabled'">
 BAXY audit web button
</button>
</main>
</body>
</html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(PAGE)))
        self.end_headers()
        self.wfile.write(PAGE)

    def log_message(self, *_: Any) -> None:
        return


def read_line(pipe: Any, timeout: float = 45.0) -> str:
    values: queue.Queue[str] = queue.Queue(maxsize=1)
    threading.Thread(target=lambda: values.put(pipe.readline()), daemon=True).start()
    try:
        line = values.get(timeout=timeout)
    except queue.Empty as exception:
        raise TimeoutError("browser operation timed out") from exception
    if not line:
        raise RuntimeError("core closed before browser response")
    return line


def edge_pids() -> set[int]:
    return {
        process.pid
        for process in psutil.process_iter(["name"])
        if (process.info["name"] or "").lower() == "msedge.exe"
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    core = args.core.resolve(strict=True)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    data_root = (
        Path(os.environ["LOCALAPPDATA"])
        / "BAXY"
        / ("audit-browser-click-" + uuid.uuid4().hex)
    )
    data_root.mkdir(parents=True, exist_ok=False)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    url = f"http://127.0.0.1:{server.server_port}/audit"
    before_edge = edge_pids()
    process = subprocess.Popen(
        [str(core)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env={**os.environ, "BAXY_DATA_DIR": str(data_root)},
    )
    hello_line = read_line(process.stdout, 10)
    hello = json.loads(hello_line)
    cases: list[dict[str, Any]] = []
    errors: list[str] = []

    def invoke(operation: str, arguments: dict[str, Any]) -> dict[str, Any]:
        mission_id = str(uuid.uuid4())
        invocation_id = str(uuid.uuid4())

        def send(token: str | None = None) -> dict[str, Any]:
            request = {
                "type": "operation.request",
                "requestId": str(uuid.uuid4()),
                "missionId": mission_id,
                "invocationId": invocation_id,
                "operation": operation,
                "arguments": arguments,
            }
            if token is not None:
                request["confirmationToken"] = token
            process.stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
            process.stdin.flush()
            return json.loads(read_line(process.stdout))

        started = time.perf_counter()
        responses = [send()]
        if responses[-1].get("errorCode") == "confirmation_required":
            responses.append(send(responses[-1]["result"]["token"]))
        response = responses[-1]
        case = {
            "operation": operation,
            "arguments": arguments,
            "responses": responses,
            "response": response,
            "elapsed_seconds": time.perf_counter() - started,
        }
        cases.append(case)
        if response.get("status") != "completed" or response.get("verified") is not True:
            errors.append(
                operation + ":" + str(response.get("errorCode") or response.get("status"))
            )
        return response

    started = time.perf_counter()
    read_contains_clicked = False
    try:
        navigation = invoke("browser.navigate", {"url": url})
        if navigation.get("verified") is True:
            time.sleep(2)
            clicked = invoke(
                "input.visible.click", {"label": "BAXY audit web button"}
            )
            if clicked.get("verified") is True:
                page = invoke("browser.page.read", {"maximumCharacters": 1000})
                text = str((page.get("result") or {}).get("text") or "")
                read_contains_clicked = "Clicked and disabled" in text
                if page.get("verified") is True and not read_contains_clicked:
                    errors.append("browser.page.read:clicked_text_missing")
    except Exception as exception:
        errors.append(f"{type(exception).__name__}:{exception}")
    finally:
        process.stdin.close()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=5)
        stderr = process.stderr.read()
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=5)
        time.sleep(3)

    new_edge = sorted(edge_pids() - before_edge)
    if new_edge:
        errors.append("audit_edge_processes_remaining:" + ",".join(map(str, new_edge)))
        for pid in new_edge:
            try:
                psutil.Process(pid).terminate()
            except psutil.Error:
                pass
        psutil.wait_procs(
            [psutil.Process(pid) for pid in new_edge if psutil.pid_exists(pid)],
            timeout=5,
        )
    shutil.rmtree(data_root, ignore_errors=True)
    report = {
        "schema": "baxy.audit.browser-visible-click-chain.v1",
        "core": str(core),
        "core_version": hello.get("coreVersion"),
        "catalog_count": len(hello.get("capabilities") or []),
        "elapsed_seconds": time.perf_counter() - started,
        "cases": cases,
        "read_contains_clicked_text": read_contains_clicked,
        "new_edge_processes_after_cleanup": new_edge,
        "errors": errors,
        "process_exit_code": process.returncode,
        "stderr": stderr[-2048:],
    }
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "total": len(cases),
                "verified": sum(
                    case["response"].get("verified") is True for case in cases
                ),
                "read_contains_clicked_text": read_contains_clicked,
                "new_edge_processes_after_cleanup": new_edge,
                "errors": errors,
            },
            ensure_ascii=False,
        )
    )
    return 0 if len(cases) == 3 and not errors and not stderr else 1


if __name__ == "__main__":
    raise SystemExit(main())
