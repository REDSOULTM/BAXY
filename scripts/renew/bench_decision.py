"""Decision bench: Renew's own Mind on its own llama-server, one model decision per case (no tool runs).

usage: py -3.12 -X utf8 scripts/renew/bench_decision.py <label> --cases FILE [--desc en|es] [--temp 0.2]
       [--gguf PATH] [--server-args "..."] [--catalog FILE] [--ctx 40960]
Cases: list of {id, family, history?, text, expect{kind: call|call_any|ask|text, op?, ops?, args?}} (see README of the
banks). Writes <banks>/runs/<label>.jsonl: a summary line (accuracy, decision p50/p90, VRAM and RAM of llama-server and
of this process acting as the mind) and one row per case.
"""
import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[2]
BANKS = Path(os.environ.get("BAXY_RENEW_BANKS", r"F:\BAXYeval\renew_v1"))
# The catalog changed after the banks were written (operations merged or replaced, 2026-10-15): an expectation that
# names a retired operation is met by the operation that replaced it, with its fixed arguments and its arguments
# renamed; an argument with no counterpart is not checked. Public, versioned, and applied without opening the banks.
EQUIVALENCE_FILE = Path(__file__).with_name("catalog_equivalence.json")
EQUIVALENCE = json.loads(EQUIVALENCE_FILE.read_text(encoding="utf-8")) if EQUIVALENCE_FILE.is_file() else {}


def current(op, args=None):
    """The operation and arguments that meet an expectation written for «op» in today's catalog."""
    entry = EQUIVALENCE.get(op)
    if not entry:
        return op, dict(args or {}), {}
    renamed = {}
    for name, want in (args or {}).items():
        target = (entry.get("args") or {}).get(name, name)
        if target is not None:
            renamed[target] = want
    return entry["op"], renamed, dict(entry.get("fixed") or {})


def norm(value):
    text = unicodedata.normalize("NFKD", str(value).lower())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def arg_ok(want, got):
    if got is None:
        return False
    if isinstance(want, bool):
        return got is want or norm(got) == norm(want)
    if isinstance(want, (int, float)):
        try:
            return float(got) == float(want)
        except (TypeError, ValueError):
            return False
    if isinstance(want, str) and want.startswith("re:"):
        return re.search(want[3:], norm(got)) is not None
    return norm(want) in norm(got)


def judge(expect, result, arguments):
    kind = result.get("kind")
    if expect["kind"] == "call":
        op, args, fixed = current(expect["op"], expect.get("args"))
        return (kind == "action" and result.get("operation") == op
                and all(arg_ok(v, (arguments or {}).get(k)) for k, v in {**args, **fixed}.items()))
    if expect["kind"] == "call_any":
        for candidate in expect["ops"]:
            op, _, fixed = current(candidate)
            if kind == "action" and result.get("operation") == op and all(
                    arg_ok(v, (arguments or {}).get(k)) for k, v in fixed.items()):
                return True
        return False
    if expect["kind"] == "ask":
        return kind == "clarify" or (kind == "conversation" and str(result.get("reply", "")).strip().endswith("?"))
    if expect["kind"] == "text":
        return kind == "conversation" and bool(str(result.get("reply", "")).strip())
    raise ValueError(expect)


def gpu_used_mib():
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True, timeout=20).stdout.strip().splitlines()
    return int(out[0]) if out and out[0].strip().isdigit() else None


def resources(server_pid, gpu_before):
    """VRAM as the GPU's growth since before llama-server started (WDDM reports no per-process VRAM) and RAM (working
    set and private bytes) of llama-server and of this process acting as the mind."""
    def ram(pid):
        # USS is the RAM the process alone holds: llama-server's working set counts the mapped GGUF, and its private
        # bytes count the VRAM WDDM commits (measured on the notebook, 2026-10-15).
        info = psutil.Process(pid).memory_full_info()
        return {"uss_mib": round(info.uss / 2**20), "working_set_mib": round(info.rss / 2**20),
                "private_mib": round(getattr(info, "private", 0) / 2**20)}

    after = gpu_used_mib()
    return {"llama_server": {"vram_mib": after - gpu_before if after is not None and gpu_before is not None else None,
                             **ram(server_pid)},
            "mind": ram(os.getpid()), "gpu_before_mib": gpu_before, "gpu_after_mib": after}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    parser.add_argument("--cases", required=True)
    parser.add_argument("--desc", default="en")
    parser.add_argument("--temp", default="0.2")
    parser.add_argument("--gguf", default=os.environ.get("BAXY_MIND_LLM_GGUF", r"F:\BAXYeval\models\Qwen3.5-4B-Q4_K_M.gguf"))
    parser.add_argument("--server", default=os.environ.get("BAXY_MIND_LLAMA_SERVER", r"F:\BAXYeval\llama\llama-server.exe"))
    parser.add_argument("--server-args", default="")
    parser.add_argument("--catalog", default=str(Path(os.environ["LOCALAPPDATA"]) / "BAXY" / "renew" / "catalog.configure.json"))
    parser.add_argument("--ctx", default="49152")
    parser.add_argument("--src", default=str(ROOT / "src"), help="the mind to measure (a copy for an A/B of the prompt)")
    args = parser.parse_args()
    os.environ["BAXY_RENEW_DESCRIPTIONS"] = args.desc
    os.environ["BAXY_RENEW_DECIDE_TEMPERATURE"] = args.temp
    sys.path.insert(0, args.src)
    from baxy_mind.llm_server import LlmServer  # noqa: E402
    from baxy_mind.mind import Mind  # noqa: E402

    runs = BANKS / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    gpu_before = gpu_used_mib()
    server = LlmServer(args.gguf, args.server, context=int(args.ctx), extra_args=args.server_args.split(),
                       log_name=f"bench-{args.label}.log")
    server.start()
    mind = Mind(server, runs / f"{args.label}.trace.jsonl")
    mind.configure(json.loads(Path(args.catalog).read_text(encoding="utf-8")))
    server.wait_ready(600)
    t0 = time.monotonic()
    mind.warm()
    warm_s = time.monotonic() - t0
    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    rows, by_family = [], {}
    for case in cases:
        started = time.monotonic()
        try:
            mind.new_session(case.get("history") or [])
            result = mind.decide(case["id"], case["text"])
            error = None
        except Exception as exc:  # noqa: BLE001 - a failed case is a failed case
            result, error = {"kind": "error"}, repr(exc)[:200]
        latency = time.monotonic() - started
        arguments = mind._decided.get(result.get("operation")) if result.get("operation") else None
        ok = error is None and judge(case["expect"], result, arguments)
        fam = by_family.setdefault(str(case.get("family", "-")), [0, 0])
        fam[0] += ok
        fam[1] += 1
        rows.append({"id": case["id"], "family": case.get("family"), "ok": ok, "latency_s": round(latency, 3),
                     "kind": result.get("kind"), "operation": result.get("operation"), "arguments": arguments,
                     "reply": result.get("reply") or result.get("question"), "error": error})
        print(f"{case['id']} {'ok ' if ok else 'BAD'} {latency:5.2f}s {result.get('kind')} {result.get('operation')}",
              flush=True)
    measured = resources(server._process.pid, gpu_before)  # type: ignore[union-attr]
    server.close()
    latencies = [r["latency_s"] for r in rows]
    summary = {"label": args.label, "cases": str(args.cases), "desc": args.desc, "temp": args.temp,
               "gguf": Path(args.gguf).name, "server_args": args.server_args, "ok": sum(r["ok"] for r in rows),
               "n": len(rows), "accuracy": round(sum(r["ok"] for r in rows) / max(1, len(rows)), 4),
               "p50": round(statistics.median(latencies), 3),
               "p90": round(statistics.quantiles(latencies, n=10)[8], 3) if len(latencies) > 2 else None,
               "warm_s": round(warm_s, 1), "families": by_family, "resources": measured}
    with open(runs / f"{args.label}.jsonl", "w", encoding="utf-8") as out:
        out.write(json.dumps({"summary": summary}, ensure_ascii=False) + "\n")
        for row in rows:
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
