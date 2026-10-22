"""System One, the professor's architecture measured offline: Laya first over the shortlist, Qwen only when Laya is unsure.

usage: <python with sentence-transformers> -X utf8 scripts/renew/system_one/laya_first_eval.py <label> --gguf LAYA.gguf
       --signals s1-<qwen run> [s1-<qwen run> ...] [--fill s1fill-<run> ...] [--train DATADIR] [--k 16]
Step 1 (Laya): for every case of the Qwen runs, the shortlist (piece B) of k tools plus asking and answering in words goes
to Laya (system_one.SystemOne.choose: both option orders, averaged) — its choice, probability and time.
Step 2 (policies, against the bank's expectation, with Qwen's own decision from the same runs and the forced-fill results
of piece A for the arguments): «qwen» as today; «profesor» (Laya decides when p ≥ τ, Qwen otherwise); «hibrido» (Laya
decides when p ≥ τ only on tools a classifier may pick, never risky ones; Qwen otherwise; Qwen's doubt < 0.4 asks).
Reports, per bank and τ: accuracy, wrong actions run, extra questions, share of turns Laya decided alone, and the
decision time those turns would save (Qwen's decision time minus Laya's).
"""
import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import bench_decision as bench  # noqa: E402
from shortlist import ANSWER, ASK, Shortlist, gold_of  # noqa: E402

TAUS = (0.9, 0.95, 0.98)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    parser.add_argument("--gguf", required=True)
    parser.add_argument("--signals", nargs="+", required=True)
    parser.add_argument("--fill", nargs="*", default=[])
    parser.add_argument("--train", default=r"F:\BAXYeval\s1\kevdata-v4")
    parser.add_argument("--k", type=int, default=16)
    parser.add_argument("--server", default=r"F:\BAXYeval\llama\llama-server.exe")
    parser.add_argument("--tools", default=r"F:\BAXYeval\s1\agentes\catalogo_actual.json")
    args = parser.parse_args()
    from sentence_transformers import SentenceTransformer
    sys.path.insert(0, str(bench.ROOT / "src"))
    from baxy_mind.system_one import OPTION_TEXT, SystemOne, short  # noqa: E402

    catalog = json.loads(Path(args.tools).read_text(encoding="utf-8"))
    risk = {t["wire"]: t.get("risk") for t in catalog}
    tools = {t["wire"]: short(t["description"]) for t in catalog if t["wire"] not in (ASK, "confirm_pending")}
    option_text = {w: short(d, 70) for w, d in tools.items()}
    option_text.update(OPTION_TEXT)
    data = Path(args.train)
    examples = [(c["text"][:300], r["questions"]["operacion"]["label"])
                for r, c in zip((json.loads(l) for l in open(data / "train.jsonl", encoding="utf-8")),
                                (json.loads(l) for l in open(data / "train.ids.jsonl", encoding="utf-8")))
                if r["questions"]["operacion"]["label"] in tools]
    sl = Shortlist(tools, examples, SentenceTransformer("intfloat/multilingual-e5-small", device="cpu"))
    laya = SystemOne(args.gguf, args.server, threads=8)
    laya.start()
    deadline = time.monotonic() + 120
    while not laya.ready and time.monotonic() < deadline:
        time.sleep(0.2)
    runs = bench.BANKS / "runs"
    out_path = runs / f"s1first-{args.label}.jsonl"
    rows = []
    with open(out_path, "w", encoding="utf-8", newline="\n") as out:
        for label in args.signals:
            for line in open(runs / f"{label}.jsonl", encoding="utf-8"):
                r = json.loads(line)
                if r["excluded"] or not r.get("signals"):
                    continue
                t0 = time.monotonic()
                ranked = sl.rank(r["text"][:300])[:args.k]
                shortlist_ms = (time.monotonic() - t0) * 1000
                options = {o: option_text[o] for o in ranked + [ASK, ANSWER]}
                judged = laya.choose(r["text"], r["history"], options, timeout=10) or {}
                row = {"id": r["id"], "bank": label, "expect": r["expect"], "qwen_kind": r["kind"],
                       "qwen_op": r["operation"], "qwen_ok": r["ok"], "qwen_ms": round(r["latency_s"] * 1000),
                       "qwen_signals": r["signals"], "laya": judged.get("choice"), "laya_p": judged.get("p", 0.0),
                       "laya_ms": judged.get("ms"), "shortlist_ms": round(shortlist_ms)}
                rows.append(row)
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
    laya.close()
    fill_ok = {}
    for label in args.fill:
        for line in open(runs / f"{label}.jsonl", encoding="utf-8"):
            f = json.loads(line)
            fill_ok[f["id"]] = f["fill_ok"]

    def conf(row):
        s = row["qwen_signals"]
        if row["qwen_kind"] in ("action", "clarify"):
            return s.get("p_call", 0) * (s.get("p_name") or 0)
        return 1 - s.get("p_call", 0)

    def laya_ok(row):
        expect = row["expect"]
        if expect["kind"] == "ask":
            return row["laya"] == ASK
        if expect["kind"] == "text":
            return row["laya"] == ANSWER
        if row["laya"] not in gold_of(expect):
            return False
        has_args = bool(expect.get("args")) or bool(bench.current(expect.get("op") or "", {})[2]) if expect["kind"] == "call" else False
        return fill_ok.get(row["id"], True) if has_args else True  # unmeasured fills count as right (optimistic)

    for bank in args.signals:
        sel = [r for r in rows if r["bank"] == bank]
        n = len(sel)
        base_ok = sum(r["qwen_ok"] for r in sel)
        base_bad = sum(1 for r in sel if not r["qwen_ok"] and r["qwen_kind"] == "action")
        print(f"== {bank}: {n} cases | Qwen alone: right {base_ok} ({base_ok / n:.1%}), wrong actions {base_bad}")
        print(f"   Laya over the shortlist alone: right {sum(laya_ok(r) for r in sel)} ({sum(laya_ok(r) for r in sel) / n:.1%}); "
              f"Laya time p50 {statistics.median([r['laya_ms'] or 0 for r in sel]):.0f} ms")
        for policy in ("profesor", "hibrido"):
            for tau in TAUS:
                ok = bad = asked_extra = alone = 0
                saved = []
                for r in sel:
                    safe = r["laya"] in (ASK, ANSWER) or risk.get(r["laya"]) in ("read_only", "low_reversible")
                    take = r["laya_p"] >= tau and (policy == "profesor" or safe)
                    if take:
                        alone += 1
                        good = laya_ok(r)
                        saved.append(r["qwen_ms"] - (r["laya_ms"] or 0) - r["shortlist_ms"])
                        bad += (not good) and r["laya"] not in (ASK, ANSWER)
                    elif policy == "hibrido" and r["qwen_kind"] == "action" and conf(r) < 0.4:
                        good = r["expect"]["kind"] == "ask"
                        asked_extra += r["qwen_ok"]
                    else:
                        good = r["qwen_ok"]
                        bad += (not good) and r["qwen_kind"] == "action"
                    ok += good
                print(f"   {policy:8} τ={tau}: right {ok} ({ok / n:.1%})  wrong actions {bad}  extra questions {asked_extra}  "
                      f"Laya alone {alone / n:.0%}  time saved on those p50 {statistics.median(saved) if saved else 0:.0f} ms")
    print(out_path)


if __name__ == "__main__":
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    main()
