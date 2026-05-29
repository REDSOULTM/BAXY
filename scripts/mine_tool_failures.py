"""mine_tool_failures.py — minería de fallos de tools desde traces.jsonl.

Inventario forense:
  - cuántas veces falló cada tool (status='failed', ok=False, error!=None)
  - error messages más comunes por tool
  - tools que fueron INVOCADAS pero nunca emitieron `tool_result`
    (= se colgaron / crash mid-call)
  - llm_proxy zombies, llm_http_error 500, retries forzados
  - "tools" que el LLM eligió pero el handler reportó action inválida

Salida: tabla por tool con conteo, top errores, top mensajes, ejemplos.

Útil cuando algo falla y querés saber QUÉ falla SIN tener que leer 23MB
de jsonl.

Uso:
  python scripts/mine_tool_failures.py
  python scripts/mine_tool_failures.py --since 2026-05-28T09:00
  python scripts/mine_tool_failures.py --tool steam
  python scripts/mine_tool_failures.py --turn 20260528_095338_f2cab9d8
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
DEFAULT_TRACE = REPO / "gemma4_agent" / "data" / "traces.jsonl"


def parse_ts(s: str) -> datetime | None:
    if not s:
        return None
    s = s.replace("Z", "+0000")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        try:
            return datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            return None


def iter_events(path: Path, since: datetime | None = None):
    """Yield events from a jsonl file, optionally filtering by ts >= since."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if since:
                ts = parse_ts(ev.get("ts", ""))
                if ts and ts < since:
                    continue
            yield ev


def short_error(msg: str, maxlen: int = 100) -> str:
    """Truncate + normalize an error msg for grouping."""
    msg = str(msg or "")[:maxlen]
    # Strip volatile parts (timestamps, PIDs, paths) to allow grouping
    msg = re.sub(r"\d{4}-\d{2}-\d{2}T?\d*:?\d*:?\d*[-+]?\d{0,4}", "<ts>", msg)
    msg = re.sub(r"pid[=: ]\d+", "pid=<n>", msg, flags=re.IGNORECASE)
    msg = re.sub(r"port[=: ]\d+", "port=<n>", msg, flags=re.IGNORECASE)
    msg = re.sub(r"\d+\.\d+\.\d+\.\d+", "<ip>", msg)
    return msg


def mine(trace: Path, since: datetime | None = None,
         tool_filter: str | None = None,
         turn_filter: str | None = None) -> None:
    """Print a forensic summary."""
    # Per-tool counters
    failed_per_tool: Counter[str] = Counter()
    ok_per_tool: Counter[str] = Counter()
    error_msgs_per_tool: dict[str, Counter[str]] = defaultdict(Counter)
    status_per_tool: dict[str, Counter[str]] = defaultdict(Counter)

    # Per-turn aggregation
    turn_tools_invoked: dict[str, list[str]] = defaultdict(list)
    turn_tool_results: dict[str, list[str]] = defaultdict(list)
    turn_errors: dict[str, list[dict]] = defaultdict(list)

    # Global counters
    llm_errors: Counter[str] = Counter()
    forced_retries = 0
    forced_retry_empty = 0

    total_events = 0
    for ev in iter_events(trace, since):
        total_events += 1
        kind = ev.get("kind") or ev.get("event") or ""
        turn_id = ev.get("turn_id", "")
        if turn_filter and turn_id != turn_filter:
            continue

        if kind in {"tool_call", "tool_invoke"}:
            tool_name = ev.get("tool") or ev.get("name") or "?"
            if tool_filter and tool_name != tool_filter:
                continue
            turn_tools_invoked[turn_id].append(tool_name)

        elif kind in {"tool_result", "tool_completed"}:
            tool_name = ev.get("tool") or ev.get("name") or "?"
            if tool_filter and tool_name != tool_filter:
                continue
            result = ev.get("result") or {}
            ok = bool(result.get("ok"))
            status = str(result.get("status") or ("ok" if ok else "failed"))
            err = result.get("error") or ""

            turn_tool_results[turn_id].append(tool_name)
            status_per_tool[tool_name][status] += 1

            if not ok:
                failed_per_tool[tool_name] += 1
                if err:
                    error_msgs_per_tool[tool_name][short_error(err)] += 1
                turn_errors[turn_id].append({
                    "tool": tool_name, "status": status, "error": err[:120],
                })
            else:
                ok_per_tool[tool_name] += 1

        elif kind == "llm_error":
            err = ev.get("error") or ""
            llm_errors[short_error(err)] += 1
            turn_errors[turn_id].append({"kind": "llm_error", "error": err[:200]})

        elif kind == "forced_tool_retry":
            forced_retries += 1
        elif kind == "forced_tool_retry_empty":
            forced_retry_empty += 1

    # ----- Report -----
    print("=" * 72)
    print(f"TOOL FAILURE MINING — {trace.name}")
    if since:
        print(f"  filter: since {since.isoformat()}")
    if tool_filter:
        print(f"  filter: tool={tool_filter}")
    if turn_filter:
        print(f"  filter: turn={turn_filter}")
    print(f"  total events scanned: {total_events:,}")
    print()

    print(f"LLM-LEVEL FAILURES")
    print(f"  forced_tool_retry: {forced_retries}")
    print(f"  forced_tool_retry_empty: {forced_retry_empty}")
    if llm_errors:
        print(f"  llm_error events: {sum(llm_errors.values())}")
        for err, n in llm_errors.most_common(5):
            print(f"    {n:>4}  {err}")
    print()

    print(f"TOOL FAILURES (top by count)")
    if not failed_per_tool:
        print("  (no tool failures in the scan window)")
    else:
        all_tools = sorted(
            set(failed_per_tool) | set(ok_per_tool),
            key=lambda t: -failed_per_tool.get(t, 0),
        )
        print(f"  {'TOOL':<20} {'FAIL':>6} {'OK':>6} {'TOTAL':>6} {'FAIL%':>6}")
        for tool in all_tools[:20]:
            fails = failed_per_tool.get(tool, 0)
            oks = ok_per_tool.get(tool, 0)
            total = fails + oks
            pct = fails * 100 // total if total else 0
            if fails > 0 or tool_filter:
                print(f"  {tool:<20} {fails:>6} {oks:>6} {total:>6} {pct:>5}%")
    print()

    # Per-tool error messages
    if error_msgs_per_tool:
        print(f"TOP ERROR MESSAGES PER TOOL")
        for tool in sorted(error_msgs_per_tool):
            print(f"  {tool}:")
            for msg, n in error_msgs_per_tool[tool].most_common(3):
                print(f"    {n:>3}  {msg}")
        print()

    # Tools invoked but never completed (orphans)
    orphans: list[tuple[str, list[str]]] = []
    for turn_id, invoked in turn_tools_invoked.items():
        results = turn_tool_results.get(turn_id, [])
        # Multiset difference: tool was invoked but no result
        missing = list((Counter(invoked) - Counter(results)).elements())
        if missing:
            orphans.append((turn_id, missing))
    if orphans:
        print(f"TOOLS INVOKED WITHOUT RESULT (potential hang/crash mid-call)")
        for turn_id, missing in orphans[-10:]:  # most recent 10
            print(f"  turn={turn_id}: {missing}")
        print()

    # Recent turn failures (last 5 turns with errors)
    if turn_errors:
        print(f"RECENT TURNS WITH ERRORS (last 5)")
        recent = sorted(turn_errors.keys())[-5:]
        for turn_id in recent:
            print(f"  {turn_id}")
            for e in turn_errors[turn_id][:3]:
                print(f"    {e}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--trace", type=Path, default=DEFAULT_TRACE,
                    help=f"trace jsonl (default: {DEFAULT_TRACE})")
    ap.add_argument("--since", type=str, default=None,
                    help="ISO timestamp; only events from then on")
    ap.add_argument("--tool", type=str, default=None,
                    help="filter to a specific tool")
    ap.add_argument("--turn", type=str, default=None,
                    help="filter to a specific turn_id")
    args = ap.parse_args()

    if not args.trace.exists():
        print(f"ABORT: {args.trace} not found", file=sys.stderr)
        return 1

    since_dt = parse_ts(args.since) if args.since else None
    mine(args.trace, since=since_dt,
         tool_filter=args.tool, turn_filter=args.turn)
    return 0


if __name__ == "__main__":
    sys.exit(main())
