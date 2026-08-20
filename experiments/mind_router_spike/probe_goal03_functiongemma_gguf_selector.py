"""Measure a preselected inherited FunctionGemma GGUF as leaf selector.

The model receives the same frozen current-catalog candidate union as the other
Goal 03 selectors.  It can only emit authenticated operation aliases or the
native ``no_tool`` sentinel; providers and dispatch never run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Iterable


REPO = Path(__file__).resolve().parents[2]
for import_root in (REPO, REPO / "src"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from scripts.measure_mind_budget import (  # noqa: E402
    current_core_catalog_snapshot,
    discover_core,
)


CORPUS = REPO / "artifacts/development/goal03_fresh_paraphrase_corpus.v1.jsonl"
DEFAULT_UNION = REPO / "artifacts/development/goal03_frozen_operation_ranker_v1.json"
DEFAULT_OUTPUT = (
    REPO / "artifacts/development/goal03_functiongemma_tools_reduce_iter3_v23.json"
)
EXPECTED_CORPUS_SHA256 = (
    "761c1bc3b3facbf14a3aaafa09f24c0e5e0baaf8cebdd0edc7c2e648cb87413d"
)
TOOL_PREFIX = "baxy_"
NO_TOOL = "no_tool"
DEV_PROMPT = "You are a model that can do function calling with the following functions"
CALL_PATTERN = re.compile(r"call:([A-Za-z0-9_]+)", flags=re.DOTALL)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _tool_name(operation: str) -> str:
    return TOOL_PREFIX + operation.replace(".", "__")


def _operation_name(tool: str | None) -> str | None:
    if not tool or tool == NO_TOOL:
        return None
    if not tool.startswith(TOOL_PREFIX):
        return None
    return tool[len(TOOL_PREFIX) :].replace("__", ".")


def _selection_tools(
    catalog: dict[str, dict[str, Any]], operations: Iterable[str]
) -> list[dict[str, Any]]:
    tools = [
        {
            "type": "function",
            "function": {
                "name": _tool_name(operation),
                "description": str(catalog[operation].get("description") or operation),
                "parameters": {"type": "object", "properties": {}},
            },
        }
        for operation in operations
    ]
    tools.append(
        {
            "type": "function",
            "function": {
                "name": NO_TOOL,
                "description": (
                    "Use when the user is not requesting any concrete action or external "
                    "read supported by another declared function."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
        }
    )
    return tools


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * fraction))]


def _port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
            return True
    except OSError:
        return False


def _wait_health(proc: subprocess.Popen[Any], port: int, timeout_s: float = 90.0) -> None:
    deadline = time.monotonic() + timeout_s
    url = f"http://127.0.0.1:{port}/health"
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"llama-server exited during boot with {proc.returncode}")
        try:
            if urllib.request.urlopen(url, timeout=1).getcode() == 200:
                return
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(0.25)
    raise TimeoutError("llama-server did not become healthy")


def _ask(port: int, text: str, tools: list[dict[str, Any]]) -> tuple[str | None, str]:
    body = json.dumps(
        {
            "messages": [
                {"role": "developer", "content": DEV_PROMPT},
                {"role": "user", "content": text},
            ],
            "tools": tools,
            "temperature": 0.0,
            "max_tokens": 160,
            "stop": ["<end_function_call>"],
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    payload = json.loads(urllib.request.urlopen(request, timeout=30).read())
    message = payload["choices"][0]["message"]
    generated = str(message.get("content") or "")
    tool_calls = message.get("tool_calls") or []
    if tool_calls:
        return str(tool_calls[0]["function"].get("name") or "") or None, generated
    match = CALL_PATTERN.search(generated)
    return (match.group(1) if match else None), generated


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--server", required=True, type=Path)
    parser.add_argument("--union-artifact", type=Path, default=DEFAULT_UNION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--port", type=int, default=18082)
    args = parser.parse_args()
    model = args.model.resolve(strict=True)
    server = args.server.resolve(strict=True)
    union_artifact = args.union_artifact.resolve(strict=True)
    output = args.output.resolve()

    if _sha256(CORPUS) != EXPECTED_CORPUS_SHA256:
        raise RuntimeError("sealed Goal 03 corpus identity changed")
    if _port_open(args.port):
        raise RuntimeError(f"port {args.port} is already in use")

    corpus = {str(row["case_id"]): row for row in _jsonl(CORPUS)}
    union_value = json.loads(union_artifact.read_text(encoding="utf-8"))
    union_rows = {str(row["case_id"]): row for row in union_value["rows"]}
    if set(corpus) != set(union_rows):
        raise RuntimeError("candidate union and sealed corpus populations differ")

    capabilities, _, _ = current_core_catalog_snapshot(discover_core(None))
    catalog = {str(row["name"]): row for row in capabilities}
    candidates: dict[str, list[str]] = {}
    tools_by_case: dict[str, list[dict[str, Any]]] = {}
    for case_id, row in union_rows.items():
        names = list(dict.fromkeys(row["top_28"][:14] + row["e5_top_28"][:14]))
        names = [name for name in names if name in catalog]
        candidates[case_id] = names
        tools_by_case[case_id] = _selection_tools(catalog, names)

    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = "-1"
    command = [
        str(server),
        "-m",
        str(model),
        "--host",
        "127.0.0.1",
        "--port",
        str(args.port),
        "--jinja",
        "-ngl",
        "0",
        "-c",
        "4096",
        "--no-webui",
    ]
    boot_started = time.perf_counter()
    proc = subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    rows: list[dict[str, Any]] = []
    try:
        _wait_health(proc, args.port)
        boot_seconds = time.perf_counter() - boot_started
        first_id = next(iter(corpus))
        _ask(args.port, "open calculator", tools_by_case[first_id])
        for case_id, source in corpus.items():
            started = time.perf_counter()
            selected_tool, generated = _ask(
                args.port, str(source["text"]), tools_by_case[case_id]
            )
            seconds = time.perf_counter() - started
            selected_operation = _operation_name(selected_tool)
            selected = [selected_operation] if selected_operation in candidates[case_id] else []
            native_no_tool = selected_tool == NO_TOOL
            unauthorized_tool = bool(
                selected_tool and not native_no_tool and not selected
            )
            expected = set(source.get("expected_operations") or [])
            rows.append(
                {
                    **source,
                    "candidate_operations": candidates[case_id],
                    "retrieved": bool(expected & set(candidates[case_id])),
                    "selected_tool": selected_tool,
                    "selected_operations": selected,
                    "native_no_tool": native_no_tool,
                    "unauthorized_tool": unauthorized_tool,
                    "selected_expected": bool(expected & set(selected)),
                    "generated": generated,
                    "seconds": seconds,
                }
            )
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)

    inside = [row for row in rows if row["in_catalog"]]
    outside = [row for row in rows if not row["in_catalog"]]
    durations = [float(row["seconds"]) for row in rows]
    result = {
        "schema": "baxy.goal03-functiongemma-gguf-selector.v1",
        "corpus": {"path": str(CORPUS.relative_to(REPO)), "sha256": _sha256(CORPUS)},
        "candidate_union": {
            "path": str(union_artifact.relative_to(REPO)),
            "sha256": _sha256(union_artifact),
            "budget": 28,
            "policy": "symmetric",
        },
        "model": {"path": str(model), "sha256": _sha256(model)},
        "server": {"path": str(server), "sha256": _sha256(server)},
        "contract": {
            "developer_prompt": DEV_PROMPT,
            "temperature": 0.0,
            "max_tokens": 160,
            "stop": ["<end_function_call>"],
            "native_no_tool_always_present": True,
            "gpu_layers": 0,
            "CUDA_VISIBLE_DEVICES": "-1",
        },
        "in_catalog": {
            "rows": len(inside),
            "retrieved": sum(bool(row["retrieved"]) for row in inside),
            "selected_expected": sum(bool(row["selected_expected"]) for row in inside),
        },
        "out_of_catalog": {
            "rows": len(outside),
            "honest_abstentions": sum(row["native_no_tool"] for row in outside),
            "authorized_effect_decisions": sum(
                bool(row["selected_operations"]) for row in outside
            ),
            "kernel_safe_rejections": sum(
                not row["selected_operations"] for row in outside
            ),
            "unauthorized_tool_outputs": sum(
                row["unauthorized_tool"] for row in outside
            ),
            "malformed_or_empty_outputs": sum(
                row["selected_tool"] is None for row in outside
            ),
        },
        "latency_seconds": {
            "rows": len(durations),
            "p50": statistics.median(durations),
            "p90": _percentile(durations, 0.9),
            "max": max(durations),
            "boot": boot_seconds,
            "total_requests": sum(durations),
        },
        "three_zeros": {
            "effects_executed": 0,
            "providers_enabled": False,
            "unsolicited_effects": 0,
            "unverified_successes": 0,
            "fixed_visible_replies": 0,
        },
        "rows": rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                key: result[key]
                for key in ("model", "in_catalog", "out_of_catalog", "latency_seconds")
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
