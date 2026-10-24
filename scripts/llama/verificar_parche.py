"""Whether the patched llama-server (scripts/llama/cache_tools_prefix.patch) answers the BAXY mind exactly as the stock one.

usage: py -3.12 -X utf8 scripts/llama/verificar_parche.py capture SERVER_DIR CAPTURE.json [--catalog F] [--only OPS]
       py -3.12 -X utf8 scripts/llama/verificar_parche.py replay SERVER_DIR CAPTURE.json OUT.json [--env K=V] [--mmproj F]
       py -3.12 -X utf8 scripts/llama/verificar_parche.py identity SERVER_DIR CAPTURE.json OUT.json [--catalog F] [--env K=V]
       py -3.12 -X utf8 scripts/llama/verificar_parche.py compare A.json B.json
       (all but compare also take --gguf FILE, --ngl N and --work DIR)
capture: a short real session of the mind (configure on the catalog, or only the operations OPS of it, warm-up, eight
turns with their tool results, the prefill between turns and one heartbeat) against SERVER_DIR's llama-server,
recording every request it sends.
replay: the recorded requests again, in order, against a fresh server started from the warm-up's saved slot (the
capture keeps it), chats non-streamed with their token log-probabilities, /completion with n_probs.
identity: the capture's chat bodies with the full catalog's tools, rendered, tokenized and refused (8192 context): the
real-size prompts and tokens without generating.
compare: two replays request by request, the same HTTP code, answer (text, tool calls and arguments, parsed message),
token log-probabilities and prompt/cache/predicted token counts (tool-call and completion ids and times left out), and
each side's time outside prompt_ms + predicted_ms; or two identity runs, the same prompt, tokens and refusal.

The server runs like the mind's (LlmServer's arguments) with --gpu-layers from --ngl: 0 by default, with -dev none and
-t 4 and at below-normal priority, so it never touches the GPU (the PC's verification, 2026-10-23); --ngl 99 on a
machine whose GPU is free (the notebook's A/B). Nothing of the product's folders is used: LOCALAPPDATA and the slot
folder are WORK (--work)."""
import argparse
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BELOW_NORMAL, NO_WINDOW = 0x00004000, 0x08000000
VOLATILE = {"id", "created", "system_fingerprint", "timings", "model"}
TURNS = [
    "abre la calculadora",
    "¿cuánto es 37 por 12?",
    "sube un poco el volumen",
    "un diez por ciento",
    "busca en internet el clima de mañana en Ñuñoa",
    "cierra la calculadora",
    "hola, ¿cómo estás?",
    "abre el bloc de notas y escribe hola mundo",
]


def _device_args(ngl: str) -> list[str]:
    return ["-dev", "none", "-t", "4"] if ngl == "0" else []


def _catalog(path: str, only: str) -> dict:
    """The App's catalog message; with ``only`` (operation names, comma-separated) just those capabilities."""
    catalog = json.loads(Path(path).read_text(encoding="utf-8"))
    if only:
        names = {name.strip() for name in only.split(",")}
        catalog["capabilities"] = [c for c in catalog["capabilities"] if c.get("name") in names]
    return catalog


def _mind_tools(catalog: str) -> list[dict]:
    """The tools the mind sends for the catalog (Mind.configure), without a model."""
    sys.path.insert(0, str(ROOT / "src"))
    from baxy_mind.mind import Mind  # noqa: E402

    class NoModel:
        context = 53248

    with tempfile.TemporaryDirectory() as scratch:
        mind = Mind(NoModel(), Path(scratch) / "trace.jsonl")  # type: ignore[arg-type]
        mind.configure(_catalog(catalog, ""))
        return mind.tools


def _start(args: argparse.Namespace, port: int, ctx: str, log: Path, extra: list[str]) -> subprocess.Popen:
    command = [str(Path(args.server_dir) / "llama-server.exe"), "-m", args.gguf, "--host", "127.0.0.1", "--port",
               str(port), "-ngl", args.ngl, "-c", ctx, "-np", "1", "-fa", "on", "-ctk", "q8_0", "-ctv", "q8_0",
               "--jinja", "--reasoning", "off", "--reasoning-budget", "0", "--load-mode", "none", "-cram", "0",
               "-ctxcp", "10", *_device_args(args.ngl), *extra]
    env = {**os.environ, **dict(item.split("=", 1) for item in args.env)}
    process = subprocess.Popen(command, stdout=open(log, "w", encoding="utf-8"), stderr=subprocess.STDOUT, env=env,
                               creationflags=BELOW_NORMAL | NO_WINDOW)
    for _ in range(1800):
        if process.poll() is not None:
            raise RuntimeError(f"llama-server exited with {process.returncode}")
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as reply:
                if reply.status == 200:
                    return process
        except Exception:  # noqa: BLE001 - still loading
            time.sleep(0.5)
    process.kill()
    raise RuntimeError("llama-server did not become healthy")


def _stop(process: subprocess.Popen) -> None:
    process.terminate()
    try:
        process.wait(15)
    except subprocess.TimeoutExpired:
        process.kill()


def identity(args: argparse.Namespace) -> int:
    """The capture's chat bodies with the full catalog's tools (~44k tokens), with no generation: a server with an
    8192-token context renders, tokenizes and refuses each one. Writes the rendered prompt and its tokens."""
    tools = _mind_tools(args.catalog)
    records = json.loads(Path(args.capture).read_text(encoding="utf-8"))
    bodies = [{**r["body"], "tools": tools} for r in records if r["kind"] == "chat"]
    port = 8094
    process = _start(args, port, "8192", Path(args.out).with_suffix(".server.log"), [])
    results: list[dict] = []
    try:
        for body in bodies:
            template = {k: body[k] for k in ("messages", "tools", "chat_template_kwargs") if k in body}
            prompt = _post(port, "/apply-template", template)[0]["prompt"]
            tokens = _post(port, "/tokenize", {"content": prompt, "parse_special": True})[0]["tokens"]
            chat = {k: v for k, v in body.items() if k != "stream_options"}
            chat.update({"stream": False, "cache_prompt": True, "id_slot": 0, "max_tokens": 1})
            answer, code, _ = _post(port, "/v1/chat/completions", chat)
            results.append({"prompt": prompt, "tokens": tokens, "chat_code": code,
                            "chat_error": (answer.get("error") or {}).get("message", "")})
            print(f"{len(tokens)} tokens, chat {code}", flush=True)
    finally:
        _stop(process)
        Path(args.out).write_text(json.dumps(results, ensure_ascii=False), encoding="utf-8")
    return 0


def capture(args: argparse.Namespace) -> int:
    os.environ["LOCALAPPDATA"] = str(Path(args.work) / "localapp")
    os.environ["BAXY_VISION_SLOT_DIR"] = str(Path(args.work) / "slots")
    for name in ("BAXY_MIND_MMPROJ", "BAXY_MIND_LLAMA_PORT"):
        os.environ.pop(name, None)
    Path(os.environ["LOCALAPPDATA"]).mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ROOT / "src"))
    popen = subprocess.Popen

    class LowPopen(popen):  # type: ignore[misc,valid-type]
        def __init__(self, *a, **kw):
            kw["creationflags"] = kw.get("creationflags", 0) | BELOW_NORMAL
            super().__init__(*a, **kw)

    subprocess.Popen = LowPopen  # type: ignore[misc]
    from baxy_mind.llm_server import LlmServer  # noqa: E402
    from baxy_mind.mind import Mind  # noqa: E402

    records: list[dict] = []
    server = LlmServer(args.gguf, str(Path(args.server_dir) / "llama-server.exe"), gpu_layers=args.ngl, context=53248,
                       extra_args=_device_args(args.ngl), log_name="verificar-parche.log")
    chat, post, tokenize = server.chat, server._post, server.tokenize

    def rec_chat(body, **kw):
        kw["timeout"] = 36000.0  # on the CPU the warm-up alone reads ~44k tokens for over an hour
        reply = chat(body, **kw)
        records.append({"kind": "chat", "body": json.loads(json.dumps(body))})
        return reply

    def rec_post(path, body, timeout):
        reply = post(path, body, 36000.0)
        records.append({"kind": "post", "path": path, "body": json.loads(json.dumps(body)), "reply": reply})
        return reply

    def rec_tokenize(text):
        records.append({"kind": "tokenize", "text": text})
        return tokenize(text)

    server.chat, server._post, server.tokenize = rec_chat, rec_post, rec_tokenize  # type: ignore[method-assign]
    server.start()
    try:
        mind = Mind(server, Path(os.environ["LOCALAPPDATA"]) / "trace.jsonl")
        mind.configure(_catalog(args.catalog, args.only))
        server.wait_ready(900)
        mind.warm()
        mind.new_session()
        for i, text in enumerate(TURNS, 1):
            result, steps = mind.decide(i, text), 0
            while result.get("kind") == "action" and steps < 3:
                observed = {"status": "completed", "verification": "readback",
                            "observed": {"operation": result.get("operation")}}
                result = mind.continue_turn(i, json.dumps(observed), final=steps == 2)
                steps += 1
            print(f"turn {i}: {result.get('kind')} {result.get('operation') or ''}", flush=True)
            mind.prefill()
        print(f"beat: {mind.beat(100, {}).get('kind')}", flush=True)
    finally:
        server.close()
        Path(args.capture).write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
        print(f"{len(records)} requests -> {args.capture}")
    return 0


def _post(port: int, path: str, body: dict, timeout: float = 3600) -> tuple[dict, int, float]:
    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as reply:
            answer, code = json.loads(reply.read()), reply.status
    except urllib.error.HTTPError as error:
        answer, code = json.loads(error.read() or b"{}"), error.code
    return answer, code, round((time.perf_counter() - started) * 1000, 1)


def replay(args: argparse.Namespace) -> int:
    records = json.loads(Path(args.capture).read_text(encoding="utf-8"))
    # the warm-up's state, saved by the mind (Mind.warm, LlmServer.save_prefix): every replay starts from it
    saved = next(i for i, r in enumerate(records) if r["kind"] == "post" and "action=save" in r["path"])
    port = 8093
    extra = ["--slot-save-path", str(Path(args.work) / "slots")]
    if args.mmproj:
        extra += ["--mmproj", args.mmproj, "--no-mmproj-offload"]
    process = _start(args, port, "53248", Path(args.out).with_suffix(".server.log"), extra)
    results: list[dict] = []
    try:
        restored, _, _ = _post(port, "/slots/0?action=restore", {"filename": records[saved]["body"]["filename"]})
        print(f"restored {restored.get('n_restored')} tokens", flush=True)
        for index, record in enumerate(records[saved + 1:], saved + 1):
            if record["kind"] == "chat":
                path = "/v1/chat/completions"
                body = {k: v for k, v in record["body"].items() if k != "stream_options"}
                body.update({"id_slot": 0, "cache_prompt": True, "stream": False, "logprobs": True, "top_logprobs": 3})
            elif record["kind"] == "tokenize":
                path, body = "/tokenize", {"content": record["text"], "parse_special": True}
            elif record["kind"] == "post" and "action=" not in record["path"]:
                path, body = record["path"], dict(record["body"])
                if path == "/completion":
                    body["n_probs"] = 3
            else:
                continue
            answer, code, ms = _post(port, path, body)
            results.append({"index": index, "path": path, "code": code, "ms": ms, "reply": answer})
            timings = (answer.get("timings") or {}) if isinstance(answer, dict) else {}
            print(f"{index:3d} {path:<22} {code} {ms:9.1f} ms prompt_n={timings.get('prompt_n')} "
                  f"cache_n={timings.get('cache_n')} predicted_n={timings.get('predicted_n')}", flush=True)
    finally:
        _stop(process)
        Path(args.out).write_text(json.dumps(results, ensure_ascii=False), encoding="utf-8")
    return 0


def _clean(reply: object) -> object:
    if not isinstance(reply, dict):
        return reply
    out = json.loads(json.dumps({k: v for k, v in reply.items() if k not in VOLATILE}))
    for choice in out.get("choices") or []:
        for call in (choice.get("message") or {}).get("tool_calls") or []:
            call.pop("id", None)
    return out


def _outside(record: dict) -> float:
    timings = (record["reply"].get("timings") or {}) if isinstance(record["reply"], dict) else {}
    return record["ms"] - float(timings.get("prompt_ms") or 0) - float(timings.get("predicted_ms") or 0)


def compare(args: argparse.Namespace) -> int:
    a = json.loads(Path(args.a).read_text(encoding="utf-8"))
    b = json.loads(Path(args.b).read_text(encoding="utf-8"))
    if a and "tokens" in a[0]:  # two identity runs
        same = [x == y for x, y in zip(a, b)]
        print(f"{sum(same)} of {len(a)} bodies with the same prompt, tokens and refusal "
              f"({min(len(x['tokens']) for x in a)}-{max(len(x['tokens']) for x in a)} tokens)")
        return 0 if all(same) and len(a) == len(b) else 1
    identical = len(a) == len(b)
    outside_a, outside_b, logprobs = [], [], 0
    for ra, rb in zip(a, b):
        ta = (ra["reply"].get("timings") or {}) if isinstance(ra["reply"], dict) else {}
        tb = (rb["reply"].get("timings") or {}) if isinstance(rb["reply"], dict) else {}
        counts_a = (ta.get("prompt_n"), ta.get("cache_n"), ta.get("predicted_n"))
        counts_b = (tb.get("prompt_n"), tb.get("cache_n"), tb.get("predicted_n"))
        same = ra["code"] == rb["code"] and _clean(ra["reply"]) == _clean(rb["reply"]) and counts_a == counts_b
        identical &= same
        note = ""
        if ra["path"] in ("/v1/chat/completions", "/completion") and ra["code"] == 200:
            outside_a.append(_outside(ra))
            outside_b.append(_outside(rb))
            note = f"outside prompt+predict {outside_a[-1]:7.1f} | {outside_b[-1]:7.1f} ms"
            choice = (ra["reply"].get("choices") or [{}])[0]
            logprobs += len((choice.get("logprobs") or {}).get("content") or ra["reply"].get("completion_probabilities")
                            or [])
        print(f"{ra['index']:3d} {ra['path']:<22} {'identical' if same else 'DIFFERENT'} {counts_a} {note}")
    if outside_a:
        print(f"p50 outside prompt+predict: A {statistics.median(outside_a):.1f} ms, B {statistics.median(outside_b):.1f}"
              f" ms over {len(outside_a)} generation requests; {logprobs} token log-probabilities compared")
    print(f"{len(a)} vs {len(b)} requests: {'ALL IDENTICAL' if identical else 'DIFFERENCES'}")
    return 0 if identical else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("capture", "replay", "identity"):
        p = sub.add_parser(name)
        p.add_argument("server_dir")
        p.add_argument("capture")
        if name != "capture":
            p.add_argument("out")
            p.add_argument("--env", action="append", default=[])
        if name == "replay":
            p.add_argument("--mmproj", default="")
        else:
            p.add_argument("--catalog", default=r"F:\BAXYeval\renew_v4\catalog-final.json")
        if name == "capture":
            p.add_argument("--only", default="", help="only these operations of the catalog (comma-separated)")
        p.add_argument("--gguf", default=os.environ.get("BAXY_MIND_LLM_GGUF")
                       or r"F:\BAXYeval\models\BAXY-Qwen3.5-4B-ft-c2e1-Q4_K_M.gguf")
        p.add_argument("--ngl", default="0")
        p.add_argument("--work", default=r"D:\BAXYWork")
    p = sub.add_parser("compare")
    p.add_argument("a")
    p.add_argument("b")
    args = parser.parse_args()
    return {"capture": capture, "replay": replay, "identity": identity, "compare": compare}[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
