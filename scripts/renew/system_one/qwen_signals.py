"""System One, phase 0 (A): what Qwen's own decision says about its doubt, read from the same call (no extra pass).

usage: py -3.12 -X utf8 scripts/renew/system_one/qwen_signals.py <label> --cases FILE [--gguf PATH] [--rollouts 4]
Runs bench_decision's Mind on each case with `logprobs` on the decision call and writes <banks>/runs/s1-<label>.jsonl:
per case the verdict and the signals (p of acting, p of the chosen tool's name, its weakest name token and the rivals
there, the weakest argument token, low-p digits in a text answer) and, for the rivals, the full tool name the model would
have written after each (greedy continuation of the call's prefix), so a System One model can be asked to choose among
them. Nothing in the product changes: the logprobs ride on the bench's own server.
"""
import argparse
import json
import math
import os
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import bench_decision as bench  # noqa: E402

CALL = "<tool_call>"
NAME_OPEN = "<function="


def p(logprob):
    return math.exp(logprob) if logprob is not None else 0.0


def post(port, path, body, timeout=120):
    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as reply:
        return json.loads(reply.read())


def spans(tokens):
    """Character offset where each token starts in the generated text, and the text."""
    starts, text = [], ""
    for token in tokens:
        starts.append(len(text))
        text += token["token"]
    return starts, text


def signals(content):
    """The doubt read from one decision's logprobs."""
    if not content:
        return {}
    first = content[0]
    alts0 = {a["token"]: p(a["logprob"]) for a in first.get("top_logprobs") or []}
    out = {"p_call": p(first["logprob"]) if first["token"] == CALL else alts0.get(CALL, 0.0),
           "first_alts": sorted(alts0.items(), key=lambda kv: -kv[1])[:5]}
    starts, text = spans(content)
    at = text.find(NAME_OPEN)
    if first["token"] == CALL and at >= 0:
        name_from = at + len(NAME_OPEN)
        name_to = text.find(">", name_from)
        name_to = len(text) if name_to < 0 else name_to
        name_idx = [i for i, s in enumerate(starts) if s + len(content[i]["token"]) > name_from and s < name_to]
        probs = [p(content[i]["logprob"]) for i in name_idx]
        weakest = min(name_idx, key=lambda i: content[i]["logprob"]) if name_idx else None
        out.update(p_name=math.prod(probs) if probs else None, name_min_p=min(probs) if probs else None,
                   name=text[name_from:name_to])
        if weakest is not None:
            # The generated text up to the weakest token: a rival token may carry the «=» of «<function=» with it.
            out["rivals_at"] = text[:starts[weakest]]
            out["rivals"] = [(a["token"], p(a["logprob"])) for a in content[weakest].get("top_logprobs") or []]
        end = text.find("</tool_call>")
        end = len(text) if end < 0 else end
        arg_idx = [i for i, s in enumerate(starts) if name_to < s < end and content[i]["token"].strip()]
        out["arg_min_p"] = min((p(content[i]["logprob"]) for i in arg_idx), default=None)
    else:
        low_digits = [content[i]["token"] for i in range(len(content))
                      if any(ch.isdigit() for ch in content[i]["token"]) and p(content[i]["logprob"]) < 0.5]
        out.update(text_min_p=min(p(t["logprob"]) for t in content), text_low_digits=len(low_digits))
    return out


def rollouts(port, body, sig, wire_names, keep):
    """The full tool name behind each rival token: greedy continuation of the call up to the name's end."""
    if "rivals" not in sig:
        return []
    template = post(port, "/apply-template", {k: body[k] for k in ("messages", "tools", "chat_template_kwargs")})
    head = template["prompt"] + sig["rivals_at"]
    found = []
    for token, prob in sig["rivals"][:keep]:
        if prob < 0.01:
            continue
        written = sig["rivals_at"] + token
        if ">" not in written[written.find(NAME_OPEN):]:
            reply = post(port, "/completion", {"prompt": head + token, "n_predict": 24, "temperature": 0.0,
                                               "stop": [">", "\n"], "cache_prompt": True, "id_slot": 0})
            written += reply.get("content", "")
        at = written.find(NAME_OPEN)
        name = written[at + len(NAME_OPEN):].split(">")[0].strip() if at >= 0 else written.strip()
        found.append({"wire": name, "p": prob, "known": name in wire_names})
    return found


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    parser.add_argument("--cases", required=True)
    parser.add_argument("--gguf", default=os.environ.get(
        "BAXY_MIND_LLM_GGUF", r"F:\BAXYeval\models\BAXY-Qwen3.5-4B-ft-c2e1-Q4_K_M.gguf"))
    parser.add_argument("--server", default=os.environ.get("BAXY_MIND_LLAMA_SERVER", r"F:\BAXYeval\llama\llama-server.exe"))
    parser.add_argument("--catalog", default=str(Path(os.environ["LOCALAPPDATA"]) / "BAXY" / "renew" / "catalog.configure.json"))
    parser.add_argument("--ctx", default="49152")
    parser.add_argument("--rollouts", type=int, default=4)
    args = parser.parse_args()
    os.environ["BAXY_RENEW_DECIDE_TEMPERATURE"] = "0.2"
    sys.path.insert(0, str(bench.ROOT / "src"))
    from baxy_mind.llm_server import LlmServer  # noqa: E402
    from baxy_mind.mind import Mind  # noqa: E402

    runs = bench.BANKS / "runs"
    server = LlmServer(args.gguf, args.server, context=int(args.ctx), log_name=f"s1-{args.label}.log")
    server.start()
    mind = Mind(server, runs / f"s1-{args.label}.trace.jsonl")
    mind.configure(json.loads(Path(args.catalog).read_text(encoding="utf-8")))
    server.wait_ready(600)
    mind.warm()
    wire_names = {t["function"]["name"] for t in mind.tools}

    seen = []
    plain_chat = server.chat

    def chat(body, **kw):
        body = {**body, "logprobs": True, "top_logprobs": 10}
        reply = plain_chat(body, **kw)
        seen.append((body, reply))
        return reply

    server.chat = chat
    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    out_path = runs / f"s1-{args.label}.jsonl"
    with open(out_path, "w", encoding="utf-8", newline="\n") as out:
        for case in cases:
            seen.clear()
            started = time.monotonic()
            try:
                mind.new_session(case.get("history") or [])
                result = mind.decide(case["id"], case["text"])
                error = None
            except Exception as exc:  # noqa: BLE001 - a failed case is a failed case
                result, error = {"kind": "error"}, repr(exc)[:200]
            latency = time.monotonic() - started
            arguments = result.get("arguments") if result.get("operation") else None
            verdict = bench.judge(case["expect"], result, arguments)
            sig, rivals = {}, []
            if seen:
                body, reply = seen[0]
                sig = signals((reply["choices"][0].get("logprobs") or {}).get("content") or [])
                try:
                    rivals = rollouts(server.port, body, sig, wire_names, args.rollouts)
                except Exception as exc:  # noqa: BLE001 - a rival that cannot be read is left out, said in the row
                    sig["rollout_error"] = repr(exc)[:200]
            row = {"id": case["id"], "family": case.get("family"), "text": case["text"],
                   "history": case.get("history") or [], "expect": case["expect"],
                   "ok": error is None and bool(verdict), "excluded": verdict is None, "latency_s": round(latency, 3),
                   "kind": result.get("kind"), "operation": result.get("operation"), "arguments": arguments,
                   "reply": result.get("reply") or result.get("question"), "error": error,
                   "calls_to_model": len(seen), "signals": sig, "rivals": rivals}
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            out.flush()
            print(f"{case['id']} {'-- ' if row['excluded'] else 'ok ' if row['ok'] else 'BAD'} {latency:5.2f}s "
                  f"{result.get('kind')} {result.get('operation')} p_call={sig.get('p_call', 0):.2f} "
                  f"p_name={sig.get('p_name') or 0:.2f} rivals={[r['wire'] for r in rivals]}", flush=True)
    server.close()
    print(out_path)


if __name__ == "__main__":
    main()
