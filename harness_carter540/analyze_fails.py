"""Lee el merged JSON y agrupa fails por bucket comun para identificar fixes."""
import argparse
import json
import re
from collections import defaultdict
from pathlib import Path


def bucket_reason(reason: str, prompt: str, expected: str, reply: str, tools: list) -> str:
    r = reason.lower()
    if "llm_error" in r or "winerror" in r:
        return "server_dead"
    if "empty reply" in r and not tools:
        return "empty_reply_no_tool"
    if "latency" in r:
        return "latency_only"
    if "tool requerida" in r:
        m = re.search(r"requerida '(\w+)'", r)
        req = m.group(1) if m else "?"
        got = "ninguna" if "ninguna" in r else "wrong_tool"
        return f"missing_tool:{req}/{got}"
    if "tool innecesaria" in r:
        return "extra_tool"
    if "destructiva sin confirm" in r:
        return "destructive_no_confirm"
    if "claim de accion" in r:
        return "fake_success"
    return f"other:{r[:40]}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    args = ap.parse_args()
    d = json.loads(Path(args.input).read_text(encoding="utf-8"))
    fails = [r for r in d["results"] if r.get("status") in ("FAIL", "PARTIAL")]
    buckets = defaultdict(list)
    for r in fails:
        for reason in r.get("reasons", []):
            b = bucket_reason(reason, r.get("prompt", ""), r.get("expected_tools", ""),
                              r.get("reply", ""), r.get("tools", []))
            buckets[b].append(r["cid"])

    # Sort by count
    items = sorted(buckets.items(), key=lambda x: -len(x[1]))
    print(f"Total fails+partial: {len(fails)}\n")
    print("BUCKETS (top 20):")
    for b, cids in items[:20]:
        print(f"  [{len(cids):>3}] {b}")
        if len(cids) <= 5:
            print(f"        {cids}")
        else:
            print(f"        {cids[:5]} ...")

    # Por categoria
    print("\nFAILS POR CATEGORIA:")
    by_cat = defaultdict(int)
    for r in fails:
        by_cat[r.get("category", -1)] += 1
    for cat in sorted(by_cat.keys()):
        print(f"  C{cat:02d}: {by_cat[cat]} fails")


if __name__ == "__main__":
    main()
