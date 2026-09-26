"""The product's contextual decider in isolation, self-contained for redpc: llama-server b9980 + Qwen3.5-4B GGUF,
optionally a LoRA adapter; the prompt, full catalog, 4-message window and schema of baxy_mind.semantic.decider
(copied byte for byte). Writes one record per turn (kind/effects/conversation_kind), scored on the notebook.
usage: remote_eval.py --set S.jsonl --out RUN.jsonl --server llama-server.exe --gguf G.gguf [--lora A.gguf]"""
import argparse
import json
import pathlib
import socket
import subprocess
import sys
import time
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from baxy_mind.semantic import decider  # noqa: E402

CAPS = json.load(open(HERE / "catalog_config.json", encoding="utf-8"))["capabilities"]
TOOLS = sorted((c["name"], c["description"]) for c in CAPS)
NAMES = {n for n, _ in TOOLS}


def post(url, payload, timeout=120):
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", required=True, type=pathlib.Path)
    ap.add_argument("--out", required=True, type=pathlib.Path)
    ap.add_argument("--server", required=True)
    ap.add_argument("--gguf", required=True)
    ap.add_argument("--lora")
    args = ap.parse_args()
    rows = [json.loads(line) for line in args.set.read_text(encoding="utf-8").splitlines() if line.strip()]
    system = decider.catalog_prompt(TOOLS)
    fmt = {"type": "json_schema", "json_schema": {"name": "baxy_context_decision", "strict": True,
                                                  "schema": decider.response_schema(sorted(NAMES))}}
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    cmd = [args.server, "-m", args.gguf, "--host", "127.0.0.1", "--port", str(port), "-ngl", "99", "-c", "12288",
           "-b", "2048", "-ub", "512", "-fa", "on", "-ctk", "q8_0", "-ctv", "q8_0", "-np", "1", "--jinja",
           "--reasoning", "off", "--reasoning-budget", "0", "--cache-ram", "0", "--no-mmap"]
    if args.lora:
        cmd[3:3] = ["--lora", args.lora]
    server = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=open(str(args.out) + ".server.log", "w"))
    try:
        for _ in range(300):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as r:
                    if r.status == 200:
                        break
            except Exception:  # noqa: BLE001
                time.sleep(1)
        url = f"http://127.0.0.1:{port}/v1/chat/completions"
        post(url, {"messages": decider.messages(system, "hola", []), "response_format": fmt, "max_tokens": 200})
        done = set()
        if args.out.is_file():
            done = {json.loads(line)["id"] for line in args.out.read_text(encoding="utf-8").splitlines() if line.strip()}
        for row in rows:
            if row["id"] in done:
                continue
            rec = {"id": row["id"]}
            t0 = time.perf_counter()
            try:
                body = post(url, {"messages": decider.messages(system, row["text"], row.get("history") or []),
                                  "response_format": fmt, "temperature": 0.0, "seed": 0, "max_tokens": 200,
                                  "cache_prompt": True, "chat_template_kwargs": {"enable_thinking": False}})
                raw = json.loads(body["choices"][0]["message"]["content"])
                ops = [op for op in raw.get("operations") or [] if op in NAMES]
                d = raw.get("decision")
                if d == "action" and ops:
                    rec.update(kind="plan" if len(ops) > 1 else "action", operation=ops[0], effects=sorted(ops))
                elif d == "clarify":
                    rec.update(kind="clarify")
                elif d == "limit":
                    rec.update(kind="conversation", conversation_kind="unsupported")
                else:
                    rec.update(kind="conversation", conversation_kind="knowledge")
                rec["raw"] = raw
            except Exception as error:  # noqa: BLE001
                rec["error"] = f"{type(error).__name__}: {error}"[:300]
            rec["latency_s"] = round(time.perf_counter() - t0, 3)
            with args.out.open("a", encoding="utf-8", newline="\n") as sink:
                sink.write(json.dumps(rec, ensure_ascii=False) + "\n")
    finally:
        server.kill()
        server.wait(timeout=30)


if __name__ == "__main__":
    main()
