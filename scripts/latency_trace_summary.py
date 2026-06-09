"""Summarize per-turn latency from gemma4_agent/data/traces.jsonl.

Focuses on the gap the user sees before GPU/model activity:
POST/runner queue -> decide phase -> llm_call_start -> llama-server timings.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TRACE = ROOT / "gemma4_agent" / "data" / "traces.jsonl"


def _load(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _fmt_ms(value: Any) -> str:
    if value is None:
        return "   n/a"
    try:
        return f"{float(value):7.1f}"
    except (TypeError, ValueError):
        return "   n/a"


def summarize(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    turns: dict[str, dict[str, Any]] = {}
    runner_events: list[dict[str, Any]] = []
    for row in rows:
        kind = row.get("kind")
        tid = str(row.get("turn_id") or "")
        if kind == "runner_turn_start":
            runner_events.append(row)
            continue
        if not tid:
            continue
        rec = turns.setdefault(tid, {"turn_id": tid, "phases": []})
        if kind == "turn_timing" and row.get("phase") == "decide":
            rec["decide_ms"] = row.get("wall_ms")
            rec["mode"] = row.get("mode")
            rec["tools"] = row.get("tools")
        elif kind == "decide_phase":
            rec["phases"].append(row)
        elif kind == "llm_call_start":
            rec["to_llm_start_ms"] = row.get("since_turn_start_ms")
            rec["tools_sent"] = row.get("tools_sent")
            rec["messages_chars"] = row.get("messages_chars")
            rec["mode"] = row.get("mode") or rec.get("mode")
        elif kind == "llm_response":
            rec["llm_wall_ms"] = row.get("wall_ms")
            rec["prompt_ms"] = row.get("prompt_ms")
            rec["predicted_ms"] = row.get("predicted_ms")
            rec["cache_n"] = row.get("cache_n")
            rec["prompt_n"] = row.get("prompt_n")

    # Best-effort associate runner queue events by order with turns that reached
    # llm_call_start. Trace ids are intentionally separate at the runner layer.
    ordered = [r for r in turns.values() if r.get("to_llm_start_ms") is not None]
    ordered.sort(key=lambda r: r["turn_id"])
    runner_tail = runner_events[-len(ordered):] if ordered else []
    for rec, runner in zip(ordered[-len(runner_tail):], runner_tail):
        rec["queue_wait_ms"] = runner.get("queue_wait_ms")
        rec["text"] = runner.get("text")
        rec["inbox_size"] = runner.get("inbox_size")

    for rec in turns.values():
        phases = rec.get("phases") or []
        if phases:
            worst = max(phases, key=lambda p: float(p.get("delta_ms") or 0.0))
            rec["worst_phase"] = worst.get("phase")
            rec["worst_phase_ms"] = worst.get("delta_ms")
    return ordered[-limit:]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", type=Path, default=DEFAULT_TRACE)
    ap.add_argument("--limit", type=int, default=12)
    args = ap.parse_args()

    rows = _load(args.trace)
    if not rows:
        print(f"no trace rows found: {args.trace}")
        return 1
    data = summarize(rows, args.limit)
    print(
        "queue  decide  to_llm   llm   prompt  pred   tools  mode        worst_phase"
    )
    for rec in data:
        tools = rec.get("tools_sent")
        tools_s = "n/a" if tools is None else str(tools)
        print(
            f"{_fmt_ms(rec.get('queue_wait_ms'))} "
            f"{_fmt_ms(rec.get('decide_ms'))} "
            f"{_fmt_ms(rec.get('to_llm_start_ms'))} "
            f"{_fmt_ms(rec.get('llm_wall_ms'))} "
            f"{_fmt_ms(rec.get('prompt_ms'))} "
            f"{_fmt_ms(rec.get('predicted_ms'))} "
            f"{tools_s:>5}  "
            f"{str(rec.get('mode') or '')[:10]:10s} "
            f"{rec.get('worst_phase') or 'n/a'}:{_fmt_ms(rec.get('worst_phase_ms'))}"
        )
        text = rec.get("text")
        if text:
            print(f"    {text[:100]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
