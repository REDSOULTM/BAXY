"""Baseline: corre los 60 tests del Bloque A+B+C contra qwen3:4b vía Ollama.

Carter hoy corre qwen3:4b-instruct-2507-q4_K_M con Ollama 0.20.4.
Comparación apple-to-apple: mismo modelo, misma forma de servirlo, mismo bench.

Usa el endpoint OpenAI-compatible de Ollama: http://127.0.0.1:11434/v1/chat/completions
"""
import json
import sys
import time
from pathlib import Path
from urllib import request as urlrequest

from tools_extended import ALL_SCHEMAS, execute_tool_extended
from tests_extended import ALL_TESTS
from tests import SYSTEM_PROMPT

OLLAMA_URL = "http://127.0.0.1:11434/v1/chat/completions"
MODEL = "qwen3:4b-instruct-2507-q4_K_M"
MAX_TURNS = 8
REQUEST_TIMEOUT = 300


def call_ollama(messages, tools):
    payload = {
        "model": MODEL,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "temperature": 0.7,
        "max_tokens": 1024,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urlrequest.Request(OLLAMA_URL, data=data, headers={"Content-Type": "application/json"})
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
            resp = call_ollama(messages, ALL_SCHEMAS)
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
                # Ollama may not always return id; synthesize one if missing
                tcid = tc.get("id") or f"call_{turn_idx}_{name}"
                result = execute_tool_extended(name, args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tcid,
                    "content": result,
                })
        trace["total_latency_s"] = round(time.time() - t0, 2)
        trace["error"] = None
    except Exception as e:
        trace["total_latency_s"] = round(time.time() - t0, 2)
        trace["error"] = f"{type(e).__name__}: {e}"
    return trace


def main():
    out_dir = Path(__file__).parent.parent / "results"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / "baseline_qwen3-4b.json"

    results = {"model": MODEL, "tests": []}
    total = len(ALL_TESTS)
    for i, test in enumerate(ALL_TESTS, 1):
        print(f"[qwen3:4b] {i}/{total} {test['id']}: {test['prompt'][:60]}", flush=True)
        trace = run_test(test)
        results["tests"].append(trace)
        flag = "ERR" if trace["error"] else "OK"
        print(f"  -> {flag} {trace['total_latency_s']}s, turns={len(trace['turns'])}", flush=True)

    out_file.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved: {out_file}")


if __name__ == "__main__":
    main()
