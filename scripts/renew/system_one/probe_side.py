"""System One, phase 0 (C): a side question to the loaded Qwen (layer 1) — what it costs, and whether the next decision
still finds the conversation in the cache.

usage: py -3.12 -X utf8 scripts/renew/system_one/probe_side.py <label> --cases FILE [--pairs 12]
Pairs of turns in one session (cases without history, taken in order). Arm `base`: turn 1, turn 2. Arm `side`: turn 1,
then one question on the same slot as the conversation's last user message (tools kept, tool_choice none, one token,
the letter's probabilities), then turn 2. Order base, side, side, base. Writes <banks>/runs/s1side-<label>.jsonl and
prints, per arm, turn 2's re-read prompt tokens and time, and the side question's own time and answer.
"""
import argparse
import json
import math
import os
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import bench_decision as bench  # noqa: E402

QUESTION = ("# Pregunta interna de decisión (no la escribió la persona; no la menciones)\n"
            "# Evidencia\nPedido de la persona: {text}\nLo que propones hacer: {proposal}\n"
            "# Criterio\n¿La persona pidió exactamente esto?\n"
            "# Opciones\nA. Sí, pidió exactamente esto\nB. No, pidió otra cosa\nC. No está claro: hay que preguntarle\n"
            "Responde sólo con la letra.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    parser.add_argument("--cases", required=True)
    parser.add_argument("--pairs", type=int, default=12)
    parser.add_argument("--gguf", default=os.environ.get(
        "BAXY_MIND_LLM_GGUF", r"F:\BAXYeval\models\BAXY-Qwen3.5-4B-ft-c2e1-Q4_K_M.gguf"))
    parser.add_argument("--server", default=r"F:\BAXYeval\llama\llama-server.exe")
    parser.add_argument("--catalog", default=str(Path(os.environ["LOCALAPPDATA"]) / "BAXY" / "renew" / "catalog.configure.json"))
    args = parser.parse_args()
    os.environ["BAXY_RENEW_DECIDE_TEMPERATURE"] = "0.2"
    sys.path.insert(0, str(bench.ROOT / "src"))
    from baxy_mind.llm_server import LlmServer  # noqa: E402
    from baxy_mind.mind import Mind  # noqa: E402

    runs = bench.BANKS / "runs"
    trace = runs / f"s1side-{args.label}.trace.jsonl"
    server = LlmServer(args.gguf, args.server, context=49152, log_name=f"s1side-{args.label}.log")
    server.start()
    mind = Mind(server, trace)
    mind.configure(json.loads(Path(args.catalog).read_text(encoding="utf-8")))
    server.wait_ready(600)
    mind.warm()
    cases = [c for c in json.loads(Path(args.cases).read_text(encoding="utf-8")) if not c.get("history")]
    pairs = [(cases[2 * i], cases[2 * i + 1]) for i in range(min(args.pairs, len(cases) // 2))]

    def last_row():
        rows = trace.read_text(encoding="utf-8").splitlines()
        return json.loads(rows[-1]) if rows else {}

    results = []
    for arm in ("base", "side", "side", "base"):
        for first, second in pairs:
            mind.new_session([])
            r1 = mind.decide(first["id"], first["text"])
            side = None
            if arm == "side":
                proposal = (f'{r1.get("operation")} {json.dumps(r1.get("arguments") or {}, ensure_ascii=False)}'
                            if r1.get("kind") == "action" else f'{r1.get("kind")}: {r1.get("reply") or r1.get("question")}')
                conv = mind._turn["conv"] if getattr(mind, "_turn", None) else []
                body = {"messages": [{"role": "system", "content": mind._system()}, *conv,
                                     {"role": "user", "content": QUESTION.format(text=first["text"], proposal=proposal)}],
                        "tools": mind.tools, "tool_choice": "none", "max_tokens": 1, "temperature": 0.0,
                        "chat_template_kwargs": {"enable_thinking": False}, "logprobs": True, "top_logprobs": 20}
                started = time.monotonic()
                reply = server.chat(body)
                ms = (time.monotonic() - started) * 1000
                top = ((reply["choices"][0].get("logprobs") or {}).get("content") or [{}])[0].get("top_logprobs") or []
                letters = {t["token"].strip(): math.exp(t["logprob"]) for t in top if t["token"].strip() in ("A", "B", "C")}
                timings = reply.get("timings") or {}
                side = {"ms": round(ms), "prompt_n": timings.get("prompt_n"), "letters": letters,
                        "mass": round(sum(letters.values()), 3)}
            started = time.monotonic()
            r2 = mind.decide(second["id"], second["text"])
            ms2 = (time.monotonic() - started) * 1000
            row2 = last_row()
            results.append({"arm": arm, "first": first["id"], "second": second["id"], "r1": r1.get("operation") or r1.get("kind"),
                            "r2": r2.get("operation") or r2.get("kind"), "turn2_ms": round(ms2),
                            "turn2_prompt_n": row2.get("prompt_n"), "side": side})
            print(json.dumps(results[-1], ensure_ascii=False), flush=True)
    server.close()
    with open(runs / f"s1side-{args.label}.jsonl", "w", encoding="utf-8", newline="\n") as out:
        for r in results:
            out.write(json.dumps(r, ensure_ascii=False) + "\n")
    for arm in ("base", "side"):
        rows = [r for r in results if r["arm"] == arm]
        print(arm, "turn2 p50 ms", round(statistics.median(r["turn2_ms"] for r in rows)),
              "turn2 prompt_n p50", statistics.median(r["turn2_prompt_n"] or 0 for r in rows),
              "max", max(r["turn2_prompt_n"] or 0 for r in rows))
    sides = [r["side"] for r in results if r["side"]]
    print("side p50 ms", round(statistics.median(s["ms"] for s in sides)), "p90",
          round(statistics.quantiles([s["ms"] for s in sides], n=10)[8]),
          "prompt_n p50", statistics.median(s["prompt_n"] or 0 for s in sides),
          "letter mass p50", statistics.median(s["mass"] for s in sides))


if __name__ == "__main__":
    main()
