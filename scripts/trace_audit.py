"""Audit gemma4_agent/data/traces.jsonl over the last N days.

Usage:
    python scripts/trace_audit.py [--days 7]

Outputs a markdown summary to stdout. Does not modify any file.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path


TRACE_PATH = Path("gemma4_agent/data/traces.jsonl")


def parse_ts(s: str) -> datetime | None:
    if not s:
        return None
    # Insert colon into ±HHMM tz suffix: "-0400" -> "-04:00"
    fixed = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", s)
    try:
        return datetime.fromisoformat(fixed)
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--path", default=str(TRACE_PATH))
    args = ap.parse_args()

    events: list[tuple[datetime | None, dict]] = []
    parse_errors = 0
    with open(args.path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except Exception:
                parse_errors += 1
                continue
            events.append((parse_ts(ev.get("ts", "")), ev))

    if not events:
        print("# trace_audit: no events")
        return 0

    timed = [(t, e) for t, e in events if t is not None]
    timed.sort(key=lambda x: x[0])
    max_ts = timed[-1][0]
    cutoff = max_ts - timedelta(days=args.days)
    recent = [(t, e) for t, e in timed if t >= cutoff]

    print("# Trace Audit\n")
    print(f"- Total events: **{len(events)}** (parse_errors={parse_errors})")
    print(f"- Last {args.days} days: **{len(recent)}**")
    print(f"- Range: {cutoff.isoformat()} -> {max_ts.isoformat()}")
    print()

    # 1) Kinds histogram
    kinds = Counter(e.get("kind", "?") for _, e in recent)
    print("## Event kinds (recent)\n")
    for k, c in kinds.most_common():
        print(f"- `{k}`: {c}")
    print()

    # 2) llm_error
    print("## llm_error events (recent)\n")
    llm_errs = [(t, e) for t, e in recent if e.get("kind") == "llm_error"]
    if not llm_errs:
        print("_None_\n")
    else:
        for t, e in llm_errs[-15:]:
            err = (e.get("error") or "")[:300]
            print(f"- `{t.isoformat() if t else '?'}` — {err}")
        print()

    # 3) tool failures
    print("## Tool failures (ok=False or status in {failed,error}) — recent\n")
    fails = Counter()
    fail_examples: dict = {}
    for _, e in recent:
        if e.get("kind") != "tool_result":
            continue
        r = e.get("result") or {}
        if not isinstance(r, dict):
            continue
        ok = r.get("ok")
        status = r.get("status")
        verified = r.get("verified")
        if ok is False or status in ("failed", "error"):
            key = (e.get("name"), status, ok)
            fails[key] += 1
            fail_examples.setdefault(key, r)
    if not fails:
        print("_None_\n")
    else:
        for (name, status, ok), c in fails.most_common(30):
            ex = fail_examples.get((name, status, ok), {})
            short = {k: v for k, v in ex.items() if k in ("error", "reason", "detail", "message")}
            print(f"- `{name}` status={status} ok={ok} → {c}× | example={short}")
        print()

    # 3b) tool_result not verified
    print("## Tools with verified=False — recent\n")
    unver = Counter()
    for _, e in recent:
        if e.get("kind") != "tool_result":
            continue
        r = e.get("result") or {}
        if isinstance(r, dict) and r.get("verified") is False:
            unver[e.get("name")] += 1
    if not unver:
        print("_None_\n")
    else:
        for name, c in unver.most_common(20):
            print(f"- `{name}`: {c}")
        print()

    # 4) Latency p50/p95/p99 by tool (tool_call -> tool_result on same turn_id+name)
    print("## Tool latency (ms) p50 / p95 / p99 — recent\n")
    calls: dict = {}
    durations: dict = defaultdict(list)
    for t, e in recent:
        if t is None:
            continue
        k = e.get("kind")
        name = e.get("name")
        turn = e.get("turn_id")
        if k == "tool_call":
            calls[(turn, name)] = t
        elif k == "tool_result" and (turn, name) in calls:
            dt = (t - calls.pop((turn, name))).total_seconds() * 1000
            durations[name].append(dt)
    rows = []
    for name, vals in durations.items():
        if not vals:
            continue
        vals_sorted = sorted(vals)
        p50 = statistics.median(vals_sorted)

        def pct(p):
            if not vals_sorted:
                return 0
            i = max(0, min(len(vals_sorted) - 1, int(round((p / 100) * len(vals_sorted))) - 1))
            return vals_sorted[i]

        rows.append((name, len(vals), p50, pct(95), pct(99), max(vals_sorted)))
    rows.sort(key=lambda r: r[1], reverse=True)
    print("| tool | n | p50 | p95 | p99 | max |")
    print("|---|---:|---:|---:|---:|---:|")
    for name, n, p50, p95, p99, mx in rows[:25]:
        print(f"| `{name}` | {n} | {p50:.0f} | {p95:.0f} | {p99:.0f} | {mx:.0f} |")
    print()

    # 5) repeated tool_call (loop pattern): same (name, args-hash) > 3 within same turn_id
    print("## Possible loop patterns (same tool+args repeated within a turn) — recent\n")
    by_turn: dict = defaultdict(Counter)
    for _, e in recent:
        if e.get("kind") != "tool_call":
            continue
        try:
            arghash = json.dumps(e.get("args") or {}, sort_keys=True, ensure_ascii=False)[:200]
        except Exception:
            arghash = "<unhashable>"
        by_turn[e.get("turn_id")][(e.get("name"), arghash)] += 1
    loops = []
    for turn, ctr in by_turn.items():
        for (name, arghash), c in ctr.items():
            if c >= 3:
                loops.append((turn, name, c, arghash))
    loops.sort(key=lambda x: x[2], reverse=True)
    if not loops:
        print("_None_\n")
    else:
        for turn, name, c, ah in loops[:20]:
            print(f"- turn=`{turn}` tool=`{name}` repeats={c} args={ah[:120]}")
        print()

    # 6) unverified_intermediate_warning frequencies
    print("## unverified_intermediate_warning — tools cited (recent)\n")
    cited = Counter()
    for _, e in recent:
        if e.get("kind") != "unverified_intermediate_warning":
            continue
        tools = e.get("tools") or []
        for tn in tools:
            cited[tn] += 1
    if not cited:
        print("_None_\n")
    else:
        for name, c in cited.most_common(20):
            print(f"- `{name}`: {c}")
        print()

    # 7) verifier reasons
    print("## verifier events — confirmed=False (recent)\n")
    vcounts = Counter()
    vexamples: dict = {}
    for _, e in recent:
        if e.get("kind") != "verifier":
            continue
        if e.get("confirmed") is False:
            key = (e.get("tool"), e.get("reason"))
            vcounts[key] += 1
            vexamples.setdefault(key, e)
    if not vcounts:
        print("_None_\n")
    else:
        for (tool, reason), c in vcounts.most_common(20):
            print(f"- tool=`{tool}` reason=`{reason}` → {c}")
        print()

    # 8) mission_outcome status
    print("## mission_outcome status distribution (recent)\n")
    statuses = Counter(e.get("status") for _, e in recent if e.get("kind") == "mission_outcome")
    for s, c in statuses.most_common():
        print(f"- `{s}`: {c}")
    print()

    # 9) failure_excluded_from_replan
    print("## failure_excluded_from_replan (recent)\n")
    excl = Counter()
    for _, e in recent:
        if e.get("kind") != "failure_excluded_from_replan":
            continue
        excl[(e.get("tool"), e.get("completion"), e.get("status"))] += 1
    if not excl:
        print("_None_\n")
    else:
        for (tool, comp, status), c in excl.most_common(20):
            print(f"- tool=`{tool}` completion=`{comp}` status=`{status}` → {c}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
