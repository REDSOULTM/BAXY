"""System One, phase 0 (A): does Qwen's own doubt predict its failures? Reads runs/s1-<label>.jsonl from qwen_signals.py.

usage: py -3.12 -X utf8 scripts/renew/system_one/analyze_signals.py <label> [<label> ...]
Per signal: AUROC of «the decision is right» (0.5 = says nothing, 1 = separates perfectly); and, for the combined
confidence (p of the chosen kind × p of the chosen name), how many failures fall below each threshold and how many good
decisions would be questioned with them. Also: when the decision fails, how often the expected operation was among the
rivals (what a second opinion could pick).
"""
import json
import sys
from pathlib import Path

BANKS = Path(r"F:\BAXYeval\renew_v1\runs")


def auroc(scores, labels):
    """Probability that a random right case scores above a random wrong one (ties count half)."""
    pos = [s for s, ok in zip(scores, labels) if ok]
    neg = [s for s, ok in zip(scores, labels) if not ok]
    if not pos or not neg:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def confidence(row):
    sig = row["signals"]
    p_call = sig.get("p_call", 0.0)
    if row["kind"] in ("action", "clarify"):
        return p_call * (sig.get("p_name") or 0.0)
    return 1.0 - p_call


def wire_of(op):
    return (op or "").replace(".", "_")


def main():
    rows = []
    for label in sys.argv[1:]:
        for line in open(BANKS / f"s1-{label}.jsonl", encoding="utf-8"):
            row = json.loads(line)
            if not row["excluded"] and row["signals"]:
                rows.append(row)
    ok = [r["ok"] for r in rows]
    print(f"cases {len(rows)}  right {sum(ok)}  wrong {len(ok) - sum(ok)}")
    called = [r for r in rows if r["kind"] in ("action", "clarify")]
    texts = [r for r in rows if r["kind"] == "conversation"]
    print("\nAUROC (right vs wrong):")
    print(f"  confidence (all)        {auroc([confidence(r) for r in rows], ok):.3f}")
    print(f"  p_call (all)            {auroc([r['signals'].get('p_call', 0) for r in rows], ok):.3f}")
    if called:
        okc = [r["ok"] for r in called]
        for key in ("p_name", "name_min_p", "arg_min_p"):
            vals = [r["signals"].get(key) if r["signals"].get(key) is not None else 1.0 for r in called]
            print(f"  {key:<22}  {auroc(vals, okc) or float('nan'):.3f}   (calls: {len(called)}, wrong {okc.count(False)})")
    if texts:
        okt = [r["ok"] for r in texts]
        print(f"  1-p_call (texts)        {auroc([1 - r['signals'].get('p_call', 0) for r in texts], okt) or float('nan'):.3f}"
              f"   (texts: {len(texts)}, wrong {okt.count(False)})")
    print("\nThreshold on confidence: wrong caught / right questioned")
    for t in (0.5, 0.6, 0.7, 0.8, 0.9, 0.95):
        caught = sum(1 for r in rows if not r["ok"] and confidence(r) < t)
        asked = sum(1 for r in rows if r["ok"] and confidence(r) < t)
        print(f"  < {t:.2f}: {caught:3d}/{ok.count(False)} wrong   {asked:3d}/{sum(ok)} right ({asked / max(1, sum(ok)):.1%})")
    wrong = [r for r in rows if not r["ok"]]
    reach, args_only = 0, 0
    for r in wrong:
        e = r["expect"]
        wants = {wire_of(e.get("op"))} | {wire_of(o) for o in e.get("ops") or []}
        if e["kind"] == "ask":
            wants.add("ask_user")
        chosen = "ask_user" if r["kind"] == "clarify" else wire_of(r["operation"])
        if chosen in wants:
            args_only += 1  # the right operation with a wrong argument: no rival fixes it
            continue
        names = {x["wire"] for x in r["rivals"]} - {chosen}
        alts = {t for t, _ in r["signals"].get("first_alts") or []}
        if wants & names or (e["kind"] == "text" and r["kind"] != "conversation" and any(not a.startswith("<") for a in alts)):
            reach += 1
    print(f"\nWrong with the right operation but a wrong argument: {args_only}/{len(wrong)}")
    print(f"Wrong whose right answer was among Qwen's rivals: {reach}/{len(wrong) - args_only}")
    print("\nWrong cases (id, family, kind/op, expected, confidence, rivals):")
    for r in wrong:
        e = r["expect"]
        print(f"  {r['id']} {r['family']:<12} {r['kind']}/{r['operation']}  want {e['kind']}:{e.get('op') or e.get('ops')}"
              f"  conf={confidence(r):.2f}  rivals={[(x['wire'], round(x['p'], 2)) for x in r['rivals']]}")


if __name__ == "__main__":
    main()
