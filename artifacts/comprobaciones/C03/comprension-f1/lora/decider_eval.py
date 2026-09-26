"""The product's contextual decider in isolation (semantic.decider: prompt, full catalog, 4-message window, schema),
on a llama-server with or without a LoRA adapter. Decision only. usage:
  decider_eval.py --set S.jsonl --out RUN.jsonl [--lora ADAPTER.gguf] [--gguf G] [--limit N]"""
import argparse
import json
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, r"C:/Users/usuario/Desktop/ETC/Programacion/BAXY Definitivo/src")
import free_model as fm  # noqa: E402
from baxy_mind.semantic import decider  # noqa: E402

Q35 = r"D:\BAXYRuntime\experiments\models\qwen35-4b-e87f1764\Qwen3.5-4B-Q4_K_M.gguf"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", required=True, type=pathlib.Path)
    ap.add_argument("--out", required=True, type=pathlib.Path)
    ap.add_argument("--lora")
    ap.add_argument("--gguf", default=Q35)
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()
    rows = [json.loads(line) for line in args.set.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = rows[: args.limit or None]
    tools = sorted((c["name"], c["description"]) for c in fm.CAPS)
    system = decider.catalog_prompt(tools)
    schema = decider.response_schema([n for n, _ in tools])
    fmt = {"type": "json_schema", "json_schema": {"name": "baxy_context_decision", "strict": True, "schema": schema}}
    port = fm.free_port()
    if args.lora:
        original = fm.start_server

        def start_with_lora(gguf, ctx, port):
            import subprocess
            import urllib.request
            command = [fm.MANIFEST["llama_server"], "-m", gguf, "--lora", args.lora, "--host", "127.0.0.1", "--port",
                       str(port), "-ngl", "99", "-c", str(ctx), "-b", "2048", "-ub", "512", "-fa", "on", "-ctk", "q8_0",
                       "-ctv", "q8_0", "-np", "1", "--jinja", "--reasoning", "off", "--reasoning-budget", "0",
                       "--cache-ram", "0", "--no-mmap"]
            process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=open(HERE / "lora-server.log", "w"))
            for _ in range(300):
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as r:
                        if r.status == 200:
                            return process
                except Exception:  # noqa: BLE001
                    time.sleep(1)
            process.kill()
            raise RuntimeError("server with lora did not start")
        fm.start_server = start_with_lora
    server = fm.start_server(args.gguf, 12288, port)
    url = f"http://127.0.0.1:{port}/v1/chat/completions"
    done = set()
    if args.out.is_file():
        done = {json.loads(line)["id"] for line in args.out.read_text(encoding="utf-8").splitlines() if line.strip()}
    try:
        fm.post(url, {"messages": decider.messages(system, "hola", []), "response_format": fmt, "temperature": 0,
                      "max_tokens": 200})
        for row in rows:
            if row["id"] in done:
                continue
            record = {"id": row["id"]}
            t0 = time.perf_counter()
            try:
                body = fm.post(url, {"messages": decider.messages(system, row["text"], row.get("history") or []),
                                     "response_format": fmt, "temperature": 0.0, "seed": 0, "max_tokens": 200,
                                     "cache_prompt": True, "chat_template_kwargs": {"enable_thinking": False}})
                parsed = json.loads(body["choices"][0]["message"]["content"])
                decision = parsed.get("decision")
                ops = [op for op in parsed.get("operations") or [] if op in dict(tools)]
                record.update(fm.to_record({"decision": decision, "operations": ops}))
                record["raw"] = parsed
            except Exception as error:  # noqa: BLE001
                record["error"] = f"{type(error).__name__}: {error}"[:300]
            record["latency_s"] = round(time.perf_counter() - t0, 3)
            with args.out.open("a", encoding="utf-8", newline="\n") as sink:
                sink.write(json.dumps(record, ensure_ascii=False) + "\n")
    finally:
        server.kill()
        server.wait(timeout=30)


if __name__ == "__main__":
    main()
