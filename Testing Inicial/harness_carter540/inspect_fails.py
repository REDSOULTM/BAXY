"""Imprime fails detallados para una categoria o bucket."""
import argparse
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--cats", nargs="+", type=int, default=None)
    ap.add_argument("--cids", nargs="+", default=None)
    ap.add_argument("--limit", type=int, default=12)
    args = ap.parse_args()
    d = json.loads(Path(args.input).read_text(encoding="utf-8"))
    n = 0
    for r in d["results"]:
        if r.get("status") == "PASS":
            continue
        if args.cats and r.get("category") not in args.cats:
            continue
        if args.cids and r.get("cid") not in args.cids:
            continue
        # skip server_dead
        if any("llm_error" in (x or "").lower() for x in r.get("reasons", [])):
            continue
        n += 1
        if n > args.limit:
            break
        print(f"\n[{r['cid']}] cat=C{r['category']:02d} {r.get('status')}")
        print(f"  prompt:   {r.get('prompt','')}")
        print(f"  expected: {r.get('expected_tools','')}")
        reply = (r.get('reply') or '').replace('\n', ' ')[:240]
        print(f"  reply:    {reply}")
        print(f"  tools:    {r.get('tools', [])}")
        print(f"  reasons:  {r.get('reasons', [])}")
        print(f"  latency:  {r.get('latency_ms')}ms")


if __name__ == "__main__":
    main()
