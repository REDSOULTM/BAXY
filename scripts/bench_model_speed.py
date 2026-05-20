"""Benchmark gen speed (tok/s) + tool-call reliability for a GGUF on :8080.

Starts the given model, measures raw decode tok/s and tool-call rate on
"abre steam", prints one line, shuts down. Used to find the best
speed/reliability balance among Gemma4 quants. Run one model per invocation:

    python scripts/bench_model_speed.py <gguf_path> [--mmproj <path>] [--ctx 16384]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

LLAMA = Path("C:/llamacpp-cuda/bin/llama-server.exe")
HOST, PORT = "127.0.0.1", 8080


def _health() -> bool:
    try:
        with urllib.request.urlopen(f"http://{HOST}:{PORT}/health", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def _chat(body: dict, timeout: float = 60) -> dict:
    req = urllib.request.Request(
        f"http://{HOST}:{PORT}/v1/chat/completions",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("--mmproj", default="")
    ap.add_argument("--ctx", type=int, default=16384)
    ap.add_argument("--runs", type=int, default=4)
    args = ap.parse_args()

    cmd = [str(LLAMA), "-m", args.model, "-c", str(args.ctx), "-ngl", "99",
           "--flash-attn", "on", "--jinja", "--host", HOST, "--port", str(PORT),
           "--no-webui"]
    if args.mmproj:
        cmd += ["--mmproj", args.mmproj]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(120):
            if _health():
                break
            time.sleep(1)
        else:
            print(f"{Path(args.model).name}: FAILED to start")
            return 1
        # raw speed
        r = _chat({"model": "g", "stream": False, "temperature": 0.7,
                   "messages": [{"role": "user", "content": "Cuenta del 1 al 60 separados por coma."}],
                   "max_tokens": 200})
        tps = r.get("timings", {}).get("predicted_per_second", 0)
        # tool-call reliability on "abre steam"
        tools = [{"type": "function", "function": {"name": "steam",
                  "description": "Launch or control Steam and Steam games",
                  "parameters": {"type": "object", "properties": {"action": {"type": "string"}}, "required": ["action"]}}}]
        ok = 0
        for _ in range(args.runs):
            rr = _chat({"model": "g", "stream": False, "temperature": 1.0,
                        "messages": [{"role": "system", "content": "You are a model that can do function calling. Use tools to perform PC actions."},
                                     {"role": "user", "content": "abre steam"}],
                        "tools": tools, "tool_choice": "auto",
                        "chat_template_kwargs": {"enable_thinking": True},
                        "thinking_budget_tokens": 384, "max_tokens": 512})
            if rr.get("choices", [{}])[0].get("message", {}).get("tool_calls"):
                ok += 1
        size_mb = Path(args.model).stat().st_size // (1024 * 1024)
        print(f"{Path(args.model).name:34s} {size_mb:5d}MB  {tps:6.1f} tok/s  tool {ok}/{args.runs}")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
    return 0


if __name__ == "__main__":
    sys.exit(main())
