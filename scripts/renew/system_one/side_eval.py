"""System One, phase 0 (C2): does the side question (layer 1) tell Qwen's right decisions from its wrong ones?

usage: py -3.12 -X utf8 scripts/renew/system_one/side_eval.py <label> --cases FILE [--gguf PATH]
Per case: Qwen decides as in bench_decision (logprobs on), then one side question on the same slot (probe_side.QUESTION):
«did the person ask for exactly this?» A yes / B something else / C unclear, read from the letter's probabilities.
Writes <banks>/runs/s1sideeval-<label>.jsonl and prints the AUROC of P(A), of Qwen's own confidence and of both.
"""
import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import bench_decision as bench  # noqa: E402
from analyze_signals import auroc  # noqa: E402
from probe_side import QUESTION  # noqa: E402
from qwen_signals import signals  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    parser.add_argument("--cases", required=True)
    parser.add_argument("--gguf", default=r"F:\BAXYeval\models\BAXY-Qwen3.5-4B-ft-c2e1-Q4_K_M.gguf")
    parser.add_argument("--server", default=r"F:\BAXYeval\llama\llama-server.exe")
    parser.add_argument("--catalog", default=str(Path(os.environ["LOCALAPPDATA"]) / "BAXY" / "renew" / "catalog.configure.json"))
    args = parser.parse_args()
    os.environ["BAXY_RENEW_DECIDE_TEMPERATURE"] = "0.2"
    sys.path.insert(0, str(bench.ROOT / "src"))
    from baxy_mind.llm_server import LlmServer  # noqa: E402
    from baxy_mind.mind import Mind  # noqa: E402

    runs = bench.BANKS / "runs"
    server = LlmServer(args.gguf, args.server, context=49152, log_name=f"s1sideeval-{args.label}.log")
    server.start()
    mind = Mind(server, runs / f"s1sideeval-{args.label}.trace.jsonl")
    mind.configure(json.loads(Path(args.catalog).read_text(encoding="utf-8")))
    server.wait_ready(600)
    mind.warm()
    seen = []
    plain_chat = server.chat

    def chat(body, **kw):
        reply = plain_chat({**body, "logprobs": True, "top_logprobs": 10}, **kw)
        seen.append(reply)
        return reply

    server.chat = chat
    rows = []
    out = open(runs / f"s1sideeval-{args.label}.jsonl", "w", encoding="utf-8", newline="\n")
    for case in json.loads(Path(args.cases).read_text(encoding="utf-8")):
        seen.clear()
        mind.new_session(case.get("history") or [])
        result = mind.decide(case["id"], case["text"])
        arguments = result.get("arguments") if result.get("operation") else None
        verdict = bench.judge(case["expect"], result, arguments)
        if verdict is None or not seen:
            continue
        sig = signals((seen[0]["choices"][0].get("logprobs") or {}).get("content") or [])
        if result.get("kind") == "action":
            proposal = f'llamar a {result["operation"]} con {json.dumps(arguments or {}, ensure_ascii=False)}'
        elif result.get("kind") == "clarify":
            proposal = f'preguntarle: «{result.get("question")}»'
        else:
            proposal = f'contestar con palabras, sin hacer nada en el PC: «{(result.get("reply") or "")[:200]}»'
        body = {"messages": [{"role": "system", "content": mind._system()}, *mind.conversation,
                             {"role": "user", "content": QUESTION.format(text=case["text"], proposal=proposal)}],
                "tools": mind.tools, "tool_choice": "none", "max_tokens": 1, "temperature": 0.0,
                "chat_template_kwargs": {"enable_thinking": False}, "logprobs": True, "top_logprobs": 20}
        started = time.monotonic()
        reply = plain_chat(body)
        ms = (time.monotonic() - started) * 1000
        top = ((reply["choices"][0].get("logprobs") or {}).get("content") or [{}])[0].get("top_logprobs") or []
        letters = {}
        for t in top:
            key = t["token"].strip()
            if key in ("A", "B", "C"):
                letters[key] = letters.get(key, 0.0) + math.exp(t["logprob"])
        mass = sum(letters.values()) or 1.0
        p_call = sig.get("p_call", 0.0)
        conf = p_call * (sig.get("p_name") or 0.0) if result.get("kind") in ("action", "clarify") else 1 - p_call
        row = {"id": case["id"], "family": case.get("family"), "ok": bool(verdict), "kind": result.get("kind"),
               "operation": result.get("operation"), "p_yes": letters.get("A", 0.0) / mass,
               "p_other": letters.get("B", 0.0) / mass, "p_unclear": letters.get("C", 0.0) / mass,
               "qwen_conf": conf, "side_ms": round(ms)}
        rows.append(row)
        out.write(json.dumps(row, ensure_ascii=False) + "\n")
        out.flush()
        print(f'{case["id"]} {"ok " if verdict else "BAD"} {result.get("kind")}/{result.get("operation")} '
              f'yes={row["p_yes"]:.2f} q={conf:.2f} {ms:.0f} ms', flush=True)
    server.close()
    ok = [r["ok"] for r in rows]
    print(json.dumps({"cases": len(rows), "wrong": ok.count(False),
                      "auroc_side_yes": round(auroc([r["p_yes"] for r in rows], ok), 3),
                      "auroc_qwen_conf": round(auroc([r["qwen_conf"] for r in rows], ok), 3),
                      "auroc_product": round(auroc([r["p_yes"] * r["qwen_conf"] for r in rows], ok), 3),
                      "auroc_min": round(auroc([min(r["p_yes"], r["qwen_conf"]) for r in rows], ok), 3)}))


if __name__ == "__main__":
    main()
