"""Runner extendido: 60 tests sobre el modelo cargado en llama-server."""
import json
import sys
import time
from pathlib import Path
from urllib import request as urlrequest

from tools_extended import ALL_SCHEMAS, execute_tool_extended
from tests_extended import ALL_TESTS
from tests import SYSTEM_PROMPT

SERVER_URL = "http://127.0.0.1:8080/v1/chat/completions"
MAX_TURNS = 8
REQUEST_TIMEOUT = 600  # large for big models with offload


def call_server(messages, tools):
    payload = {
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "temperature": 0.7,
        "max_tokens": 1024,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urlrequest.Request(SERVER_URL, data=data, headers={"Content-Type": "application/json"})
    with urlrequest.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        return json.loads(resp.read())


def _parse_args(raw):
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return {"_raw": raw}


def run_test(test):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if test.get("history"):
        messages.extend(test["history"])
    messages.append({"role": "user", "content": test["prompt"]})

    trace = {
        "id": test["id"],
        "block": test["block"],
        "pattern": test["pattern"],
        "kind": test.get("kind"),
        "prompt": test["prompt"],
        "expected": test["expected"],
        "turns": [],
    }
    t0 = time.time()
    try:
        for turn_idx in range(MAX_TURNS):
            t_turn = time.time()
            resp = call_server(messages, ALL_SCHEMAS)
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
                result = execute_tool_extended(name, args)
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


def main():
    if len(sys.argv) < 2:
        print("usage: run_bench_extended.py <model_name>")
        sys.exit(1)
    model_name = sys.argv[1]
    out_dir = Path(__file__).parent.parent / "results"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / f"extended_{model_name}.json"

    results = {"model": model_name, "tests": []}
    total = len(ALL_TESTS)
    for i, test in enumerate(ALL_TESTS, 1):
        print(f"[{model_name}] {i}/{total} {test['id']}: {test['prompt'][:60]}", flush=True)
        trace = run_test(test)
        results["tests"].append(trace)
        flag = "ERR" if trace["error"] else "OK"
        print(f"  -> {flag} {trace['total_latency_s']}s, turns={len(trace['turns'])}", flush=True)

    out_file.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved: {out_file}")


if __name__ == "__main__":
    main()
