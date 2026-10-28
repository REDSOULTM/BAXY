"""System One, piece A measured: when another layer picks the tool, does Qwen fill its arguments right?

usage: py -3.12 -X utf8 scripts/renew/system_one/forced_fill.py <label> --cases FILE [--gguf PATH] [--server PATH] [--catalog FILE]
Per case whose expectation is one tool: Qwen decides as in bench_decision; then, on the same slot and the same prompt,
LlmServer.fill_call makes it write the arguments of the EXPECTED tool (what happens when Laya picks right). The bank's
judge reads both. Prints argument accuracy of the forced fill — overall, where Qwen had chosen that tool itself, and
where it had chosen another (the override case) — its time, and whether the next decision still found the cache.
"""
import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import bench_decision as bench  # noqa: E402


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
    server = LlmServer(args.gguf, args.server, context=49152, log_name=f"s1fill-{args.label}.log")
    server.start()
    mind = Mind(server, runs / f"s1fill-{args.label}.trace.jsonl")
    mind.configure(json.loads(Path(args.catalog).read_text(encoding="utf-8")))
    server.wait_ready(600)
    mind.warm()
    bodies = []
    plain_chat = server.chat

    def chat(body, **kw):
        bodies.append(json.loads(json.dumps(body)))
        return plain_chat(body, **kw)

    server.chat = chat
    rows = []
    out = open(runs / f"s1fill-{args.label}.jsonl", "w", encoding="utf-8", newline="\n")
    for case in json.loads(Path(args.cases).read_text(encoding="utf-8")):
        if case["expect"]["kind"] != "call":
            continue
        op, want_args, fixed = bench.current(case["expect"]["op"], case["expect"].get("args"))
        if op is None or not (want_args or fixed):
            continue  # nothing to fill-check: the tool alone is the answer
        bodies.clear()
        mind.new_session(case.get("history") or [])
        result = mind.decide(case["id"], case["text"])
        if not bodies:
            continue
        own_ok = bench.judge(case["expect"], result, result.get("arguments") if result.get("operation") else None)
        wire = mind.wires.name(op)
        started = time.monotonic()
        try:
            filled = server.fill_call(bodies[0], wire)
        except Exception as error:  # noqa: BLE001 - a failed fill is a failed fill
            filled = {"error": repr(error)[:200]}
        ms = (time.monotonic() - started) * 1000
        arguments = {**(filled or {}).get("arguments", {}), **mind.constants.get(op, {})} if filled else {}
        forced = {"kind": "action", "operation": op}
        fill_ok = bool(filled and filled.get("name") == wire and bench.judge(case["expect"], forced, arguments))
        row = {"id": case["id"], "qwen_op": result.get("operation"), "qwen_ok": bool(own_ok), "same_tool": result.get("operation") == op,
               "fill_ok": fill_ok, "fill_ms": round(ms), "fill_prompt_n": ((filled or {}).get("timings") or {}).get("prompt_n"),
               "filled": filled}
        rows.append(row)
        out.write(json.dumps(row, ensure_ascii=False) + "\n")
        out.flush()
        print(f'{case["id"]} qwen={"ok " if own_ok else "BAD"} {result.get("operation")} | forced {op}: {"ok " if fill_ok else "BAD"} {ms:.0f} ms', flush=True)
    server.close()
    same = [r for r in rows if r["same_tool"]]
    other = [r for r in rows if not r["same_tool"]]
    print(json.dumps({
        "cases": len(rows),
        "forced_fill_ok": sum(r["fill_ok"] for r in rows),
        "where_qwen_chose_that_tool": {"n": len(same), "qwen_args_ok": sum(r["qwen_ok"] for r in same),
                                       "forced_ok": sum(r["fill_ok"] for r in same)},
        "where_qwen_chose_another": {"n": len(other), "forced_ok": sum(r["fill_ok"] for r in other)},
        "fill_ms_p50": round(statistics.median(r["fill_ms"] for r in rows)) if rows else None,
        "fill_prompt_n_p50": statistics.median(r["fill_prompt_n"] or 0 for r in rows) if rows else None}, ensure_ascii=False))


if __name__ == "__main__":
    main()
