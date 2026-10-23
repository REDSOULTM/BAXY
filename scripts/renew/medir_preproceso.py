"""What llama-server spends on each chat request before it reads a token, split into its parts (GPU measurement).

usage: py -3.12 -X utf8 scripts/renew/medir_preproceso.py [--n 15] [--gguf PATH] [--server PATH] [--catalog FILE]
Starts Qwen's llama-server as the product does (the kept prefix is restored from disk when it is the same), configures
the product's catalog and sends the same decision again and again, cached: each request then reads ~4 tokens and
writes one, so what is left of its wall time is the server's own work around it and the transport. Per request:
- chat: the decision's body to /v1/chat/completions, max_tokens 1, minus the server's prompt_ms and predicted_ms
  (JSON, chat template with the ~180 tools, tokenizing ~44k tokens, the tool-call grammar, the answer);
- template: the same body to /apply-template (JSON and the chat template alone);
- tokenize: the rendered prompt to /tokenize (tokenizing alone);
- completion: the rendered prompt to /completion, n_predict 1, minus its timings (tokenizing and the slot, no template
  and no grammar).
chat − completion − template ≈ the grammar and the chat's own parsing. Writes nothing; prints medians (ms).
Al máximo W5: the trace's turn.decide rows show ~140 ms of every decision outside prompt_ms + predicted_ms (decision2
2026-10-22, p50 136-142 ms; llama-server.log: ~140 ms between one request's release and the next one's slot): this says
which part a change to the server (cached template, tokens or grammar for the same tools) would save.
"""
import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _timed(call) -> tuple[float, object]:
    started = time.perf_counter()
    result = call()
    return (time.perf_counter() - started) * 1000, result


def _inside(reply: dict) -> float:
    timings = reply.get("timings") or {}
    return float(timings.get("prompt_ms") or 0) + float(timings.get("predicted_ms") or 0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=15)
    parser.add_argument("--gguf", default=os.environ.get("BAXY_MIND_LLM_GGUF", ""))
    parser.add_argument("--server", default=os.environ.get("BAXY_MIND_LLAMA_SERVER", ""))
    parser.add_argument("--catalog", default=str(Path(os.environ["LOCALAPPDATA"]) / "BAXY" / "renew"
                                                 / "catalog.configure.json"))
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / "src"))
    from baxy_mind.llm_server import LlmServer  # noqa: E402
    from baxy_mind.mind import Mind  # noqa: E402

    server = LlmServer(args.gguf, args.server, context=int(os.environ.get("BAXY_RENEW_CTX", "53248")),
                       log_name="medir-preproceso.log")
    server.start()
    scratch = Path(os.environ["LOCALAPPDATA"]) / "BAXY" / "renew" / "medir-preproceso"
    scratch.mkdir(parents=True, exist_ok=True)
    try:
        mind = Mind(server, scratch / "trace.jsonl")
        mind.configure(json.loads(Path(args.catalog).read_text(encoding="utf-8")))
        server.wait_ready(600)
        mind.warm()
        bodies: list[dict] = []
        chat = server.chat
        server.chat = lambda body, **kw: bodies.append(json.loads(json.dumps(body))) or chat(body, **kw)  # type: ignore
        mind.new_session()
        mind.decide(1, "abre la calculadora")
        server.chat = chat  # type: ignore[method-assign]
        body = {**bodies[0], "max_tokens": 1}
        prompt = server.template(body)
        parts: dict[str, list[float]] = {"chat": [], "template": [], "tokenize": [], "completion": []}
        for _ in range(args.n):
            server.deadline = None
            wall, reply = _timed(lambda: server.chat(body))
            parts["chat"].append(wall - _inside(reply))  # type: ignore[arg-type]
            wall, _ = _timed(lambda: server.template(body))
            parts["template"].append(wall)
            wall, tokens = _timed(lambda: server.tokenize(prompt))
            parts["tokenize"].append(wall)
            wall, reply = _timed(lambda: server.prefill(prompt))
            parts["completion"].append(wall - _inside(reply))  # type: ignore[arg-type]
        medians = {name: statistics.median(values) for name, values in parts.items()}
        print(f"prompt: {len(prompt)} characters, {len(tokens)} tokens; {args.n} requests each")  # type: ignore[arg-type]
        for name, value in medians.items():
            print(f"{name:<11} {value:7.1f} ms (p50)")
        print(f"grammar and chat parsing ≈ {medians['chat'] - medians['completion'] - medians['template']:.1f} ms")
    finally:
        server.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
