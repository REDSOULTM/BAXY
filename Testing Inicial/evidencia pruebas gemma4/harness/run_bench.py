"""Corre los 10 tests del contrato sobre cada modelo descargado, contra llama-server local.

Uso:
    1. Levantar el server para un modelo:
        llama-server.exe -m models\\E2B\\<file>.gguf --jinja --port 8080 -ngl 99
    2. python harness\\run_bench.py <model_name>

Hace POST /v1/chat/completions con tools=[...] y guarda traza en results/<model>.json.
"""
import json
import sys
import time
from pathlib import Path
from urllib import request as urlrequest

from tools import TOOL_SCHEMAS, execute_tool
from tests import SYSTEM_PROMPT, TESTS

SERVER_URL = "http://127.0.0.1:8080/v1/chat/completions"
MAX_TURNS = 6  # safety: stop tool loop after N turns
REQUEST_TIMEOUT = 300  # warmup of first request can be long


def call_server(messages, tools):
    payload = {
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "temperature": 0.7,
        "max_tokens": 512,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urlrequest.Request(SERVER_URL, data=data, headers={"Content-Type": "application/json"})
    with urlrequest.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        return json.loads(resp.read())


def run_test(test):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": test["prompt"]},
    ]
    trace = {"id": test["id"], "prompt": test["prompt"], "pattern": test["pattern"], "turns": []}
    t0 = time.time()
    try:
        for turn_idx in range(MAX_TURNS):
            t_turn = time.time()
            resp = call_server(messages, TOOL_SCHEMAS)
            turn_latency = time.time() - t_turn
            choice = resp["choices"][0]
            msg = choice["message"]
            tool_calls = msg.get("tool_calls") or []
            content = msg.get("content") or ""
            turn_record = {
                "turn": turn_idx,
                "latency_s": round(turn_latency, 2),
                "content": content,
                "tool_calls": [
                    {"name": tc["function"]["name"], "args": _parse_args(tc["function"]["arguments"])}
                    for tc in tool_calls
                ],
                "finish_reason": choice.get("finish_reason"),
            }
            trace["turns"].append(turn_record)

            if not tool_calls:
                break

            messages.append({
                "role": "assistant",
                "content": content,
                "tool_calls": tool_calls,
            })
            for tc in tool_calls:
                name = tc["function"]["name"]
                args = _parse_args(tc["function"]["arguments"])
                result = execute_tool(name, args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })
        trace["total_latency_s"] = round(time.time() - t0, 2)
        trace["error"] = None
    except Exception as e:
        trace["total_latency_s"] = round(time.time() - t0, 2)
        trace["error"] = f"{type(e).__name__}: {e}"
    return trace


def _parse_args(raw):
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return {"_raw": raw}


def main():
    if len(sys.argv) < 2:
        print("usage: run_bench.py <model_name>")
        sys.exit(1)
    model_name = sys.argv[1]
    out_dir = Path(__file__).parent.parent / "results"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / f"{model_name}.json"

    results = {"model": model_name, "tests": []}
    for test in TESTS:
        print(f"[{model_name}] test {test['id']}: {test['prompt'][:50]}...", flush=True)
        trace = run_test(test)
        results["tests"].append(trace)
        print(f"  -> {trace['total_latency_s']}s, turns={len(trace['turns'])}, err={trace['error']}", flush=True)

    out_file.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved: {out_file}")


if __name__ == "__main__":
    main()
