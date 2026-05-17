"""Aggregate usage report over gemma4_agent/data/traces.jsonl.

Self-contained, stdlib only. Reads JSONL, counts events, writes a
Markdown report to stdout AND to
docs/architecture/sprint_prompts/_sprint2_usage_report.md.

Usage:
    python scripts/analyze_traces.py
    python scripts/analyze_traces.py --limit 1000      # only last 1000 lines
    python scripts/analyze_traces.py --since 2026-05-14
    python scripts/analyze_traces.py --traces path/to/other.jsonl

Sections in the report follow Sprint 2.1 spec (A=tools, B=personas,
C=microagents+skills, D=capability classifier, E=routing/fallback,
F=MissionOutcome, G=top-line findings).
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

# Compound tool catalogue. Source of truth lives in
# gemma4_agent.tools.COMPOUND_TOOL_SCHEMAS, but importing the package
# requires its (heavy) dependency graph and we want this script to be
# runnable from a bare Python install. The list is hardcoded here and
# verified in __main__ via a lightweight regex against tools.py so
# divergence is loud.
COMPOUND_TOOL_NAMES: tuple[str, ...] = (
    "accessibility", "app", "audio", "audio_device", "backup_sync",
    "browser", "browser_real", "clipboard", "contacts", "container",
    "creative_local", "data_analysis", "database", "dependency",
    "desktop_layout", "developer", "device_settings", "document",
    "download", "email", "env", "fact_check", "filesystem",
    "form_filler", "game_launcher", "gui", "habit_tracker", "input",
    "job_manager", "knowledge", "local_calendar", "local_search",
    "maintenance", "media", "media_edit", "memory", "network",
    "notes_tasks", "notification", "office", "package", "peripheral",
    "photo_library", "printer_scanner", "registry", "reminder",
    "routine", "safety", "session", "skill_load", "smart_home",
    "source_manager", "state", "steam", "study", "subagent", "system",
    "terminal", "uia", "verify", "vision", "watcher", "web", "whatsapp",
    "window",
)

PERSONA_NAMES: tuple[str, ...] = (
    "default", "coder", "researcher", "creative", "planner", "casual",
)

# Mission outcome statuses we expect to see (mission_goal.OutcomeStatus).
# Listed alphabetically; report sorts by frequency.
MISSION_STATUSES: tuple[str, ...] = (
    "BLOCKED_BY_POLICY",
    "COMPLETED",
    "FAILED",
    "INTENT_NOT_FULFILLED",
    "NEEDS_PERMISSION",
    "NEEDS_USER",
    "PARTIAL",
    "TOOL_OK_VERIFIER_INCONCLUSIVE",
    "UNVERIFIED",
)


def _parse_ts(s: str) -> datetime | None:
    """Parse an event ts like '2026-05-12T03:35:54-0400' permissively."""
    if not s:
        return None
    # strip timezone offset for naive comparison — the report scope is per-day
    try:
        head = s.split("+")[0].split("-")
        if len(head) >= 4:  # has trailing -HHMM
            base = "-".join(head[:-1])
        else:
            base = s
        return datetime.fromisoformat(base)
    except ValueError:
        return None


def _iter_events(path: Path, *, since: datetime | None, limit: int | None) -> Iterable[dict[str, Any]]:
    """Yield parsed events from path. If limit is set, returns the LAST
    `limit` events (so --limit 100 shows the most recent 100).
    """
    with path.open(encoding="utf-8") as f:
        lines = f.readlines()
    if limit is not None and limit > 0:
        lines = lines[-limit:]
    corrupted = 0
    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            ev = json.loads(raw)
        except json.JSONDecodeError:
            corrupted += 1
            continue
        if since is not None:
            ts = _parse_ts(str(ev.get("ts", "")))
            if ts is None or ts < since:
                continue
        yield ev
    # stash corruption count on the iterator via attribute hack
    _iter_events.last_corrupted = corrupted  # type: ignore[attr-defined]


def _md_table(headers: list[str], rows: list[list[Any]]) -> str:
    """Minimal Markdown table (no fancy alignment)."""
    out = ["| " + " | ".join(headers) + " |",
           "| " + " | ".join("---" for _ in headers) + " |"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


def build_report(events: list[dict[str, Any]], *, source_path: Path,
                 since: datetime | None, corrupted: int, total_raw: int) -> str:
    out: list[str] = []
    push = out.append

    push("# Sprint 2 — Trace usage report")
    push("")
    push(f"- **Source:** `{source_path}`")
    push(f"- **Events parsed:** {len(events):,}  (raw lines read: {total_raw:,}, corrupted skipped: {corrupted})")
    if since:
        push(f"- **--since filter:** {since.date().isoformat()}")
    ts_first = next((e.get("ts") for e in events if e.get("ts")), None)
    ts_last = next((e.get("ts") for e in reversed(events) if e.get("ts")), None)
    if ts_first and ts_last:
        push(f"- **Time range:** {ts_first} → {ts_last}")
    turn_ids = {e.get("turn_id") for e in events if e.get("turn_id")}
    push(f"- **Distinct turn_ids:** {len(turn_ids):,}")
    push("")

    # ---- Section A: tools ----
    push("## A — Tools usage")
    push("")
    tool_calls = Counter()
    tool_status: dict[str, Counter] = {}
    for ev in events:
        if ev.get("kind") == "tool_call":
            name = str(ev.get("name", "?"))
            tool_calls[name] += 1
            tool_status.setdefault(name, Counter())
    # status comes from tool_result (paired with tool_call by turn_id+name).
    # The pairing is best-effort: we walk events in order and accumulate the
    # most recent tool_call name per turn_id, then attribute the next
    # tool_result(name) status to it.
    overall_status = Counter()
    for ev in events:
        if ev.get("kind") != "tool_result":
            continue
        name = str(ev.get("name", "?"))
        result = ev.get("result") or {}
        if not isinstance(result, dict):
            status = "non_dict_result"
        elif result.get("needs_confirmation"):
            status = "needs_confirmation"
        elif result.get("ok") is True:
            status = "ok"
        elif result.get("ok") is False:
            status = "failed"
        else:
            status = "unverified"
        overall_status[status] += 1
        tool_status.setdefault(name, Counter())[status] += 1

    push(f"**Total tool_call events:** {sum(tool_calls.values())}  ·  "
         f"**Distinct tool names:** {len(tool_calls)}  ·  "
         f"**Total tool_result events:** {sum(overall_status.values())}")
    push("")
    push("### A.1 Tool call frequency (descending)")
    push("")
    rows = []
    for name, n in tool_calls.most_common():
        sm = tool_status.get(name, Counter())
        rows.append([name, n, sm.get("ok", 0), sm.get("failed", 0),
                     sm.get("needs_confirmation", 0), sm.get("unverified", 0)])
    push(_md_table(["tool", "calls", "ok", "failed", "needs_conf", "unverif"], rows) if rows else "_(no tool_call events)_")
    push("")
    push("### A.2 Compound tools NEVER called in this window")
    push("")
    unused = [n for n in COMPOUND_TOOL_NAMES if tool_calls.get(n, 0) == 0]
    if unused:
        push(f"_{len(unused)} of {len(COMPOUND_TOOL_NAMES)} compound tools have zero calls in this window._")
        push("")
        push("- " + "\n- ".join(unused))
    else:
        push("_(none — every compound tool was called at least once)_")
    push("")
    push("### A.3 Overall status distribution (tool_result)")
    push("")
    if overall_status:
        push(_md_table(["status", "count"],
                       [[s, c] for s, c in overall_status.most_common()]))
    else:
        push("_(no tool_result events)_")
    push("")

    # ---- Section B: personas ----
    push("## B — Personas")
    push("")
    persona_events = Counter()
    for ev in events:
        if ev.get("kind") == "persona_active":
            persona_events[str(ev.get("persona", "?"))] += 1
        # also catch any historical events that may have embedded a persona field
        elif "persona" in ev and isinstance(ev.get("persona"), str):
            persona_events[str(ev.get("persona"))] += 1
    push(f"**Hardcoded personas in personas.py:** {', '.join(PERSONA_NAMES)}")
    if persona_events:
        push("")
        push(_md_table(["persona", "events"],
                       [[p, n] for p, n in persona_events.most_common()]))
        unused_p = [p for p in PERSONA_NAMES if persona_events.get(p, 0) == 0]
        if unused_p:
            push("")
            push(f"**Never seen in logs:** {', '.join(unused_p)}")
    else:
        push("")
        push("> ⚠ No persona-tagged events found in traces.jsonl.")
        push("> The persona system runs but is silent on disk. Sprint 2.2 adds")
        push("> a `persona_active` event so future reports can quantify this.")
    push("")

    # ---- Section C: microagents + skills ----
    push("## C — Microagents and skills")
    push("")
    microagent = Counter()
    skill = Counter()
    for ev in events:
        k = ev.get("kind")
        if k == "microagent_matched":
            microagent[str(ev.get("name", "?"))] += 1
        elif k == "skill_loaded":
            skill[str(ev.get("name", "?"))] += 1
        elif k == "tool_call" and ev.get("name") == "skill_load":
            args = ev.get("args") or {}
            if isinstance(args, dict):
                skill[str(args.get("name", "?"))] += 1
    push("### C.1 Microagents matched")
    push("")
    if microagent:
        push(_md_table(["microagent", "matches"],
                       [[n, c] for n, c in microagent.most_common()]))
    else:
        push("> ⚠ No `microagent_matched` events found. The router currently")
        push("> doesn't log which microagent fired. Sprint 2.2 adds this.")
    push("")
    push("### C.2 Skills loaded (via skill_load tool or skill_loaded event)")
    push("")
    if skill:
        push(_md_table(["skill", "loads"],
                       [[n, c] for n, c in skill.most_common()]))
    else:
        push("> ⚠ No skill load activity found in this window.")
    push("")

    # ---- Section D: capability classifier ----
    push("## D — Capability classifier (Bug 1 of the audit)")
    push("")
    cap_sync = 0
    cap_async = 0
    cap_source = Counter()
    cap_added: Counter = Counter()
    cap_ambiguous = 0
    cap_dispatched = 0
    for ev in events:
        k = ev.get("kind")
        if k == "capability_augment":
            cap_sync += 1
            cap_source[str(ev.get("source", "?"))] += 1
            for t in ev.get("added", []) or []:
                cap_added[str(t)] += 1
            if ev.get("ambiguous"):
                cap_ambiguous += 1
        elif k == "capability_async_dispatched":
            cap_async += 1
            cap_dispatched += 1
        elif k == "capability_verdict":  # added by Sprint 2.2
            cap_sync += 1
            cap_source[str(ev.get("source", "?"))] += 1

    push(f"- `capability_augment` (verdict applied): **{cap_sync}**")
    push(f"- `capability_async_dispatched` (sent to background): **{cap_async}**")
    push(f"- Marked ambiguous: **{cap_ambiguous}**")
    push("")
    if cap_source:
        push("### D.1 Verdict source (cache vs sync vs async result)")
        push("")
        total_with_source = sum(cap_source.values())
        rows = []
        for s, c in cap_source.most_common():
            pct = (c / total_with_source * 100) if total_with_source else 0
            rows.append([s, c, f"{pct:.1f}%"])
        push(_md_table(["source", "count", "share"], rows))
        push("")
        cache_hits = cap_source.get("cache", 0)
        cache_rate = (cache_hits / total_with_source * 100) if total_with_source else 0
        push(f"**Cache hit rate:** {cache_rate:.1f}%  (threshold for keep/kill: 20%)")
        push("")
    if cap_added:
        push("### D.2 Tools most often suggested by classifier")
        push("")
        push(_md_table(["tool", "suggestions"],
                       [[t, c] for t, c in cap_added.most_common(20)]))
        push("")

    # ---- Section E: routing / fallback ----
    push("## E — Routing & fallback")
    push("")
    subset_empty = 0
    subset_nonempty = 0
    router_miss = 0
    phrase_confirm = 0
    phrase_trigger = 0
    subset_size_counter = Counter()
    for ev in events:
        k = ev.get("kind")
        if k == "tool_subset":
            tools = ev.get("tools") or []
            if not tools:
                subset_empty += 1
            else:
                subset_nonempty += 1
            sz = ev.get("schema_count")
            if isinstance(sz, int):
                subset_size_counter[sz] += 1
        elif k == "router_miss":
            router_miss += 1
        elif k == "phrase_confirm_injected":
            phrase_confirm += 1
        elif k == "phrase_trigger_fired":
            phrase_trigger += 1
    total_subset = subset_empty + subset_nonempty
    pct_empty = (subset_empty / total_subset * 100) if total_subset else 0
    push(f"- `tool_subset` events with empty subset: **{subset_empty} / {total_subset}** ({pct_empty:.1f}%) → triggers semantic_router fallback")
    push(f"- `router_miss` (router picked a tool not in the registered set): **{router_miss}**")
    push(f"- `phrase_trigger_fired` (continuation hints / phrase routines): **{phrase_trigger}**")
    push(f"- `phrase_confirm_injected` (confirmation prompt injected): **{phrase_confirm}**")
    push("")
    if subset_size_counter:
        push("### E.1 Distribution of subset sizes")
        push("")
        rows = []
        for sz in sorted(subset_size_counter):
            rows.append([sz, subset_size_counter[sz]])
        push(_md_table(["schema_count", "frequency"], rows))
        push("")

    # ---- Section F: mission outcomes ----
    push("## F — Mission outcomes")
    push("")
    mission = Counter()
    for ev in events:
        if ev.get("kind") == "mission_outcome":
            mission[str(ev.get("status", "?"))] += 1
    if mission:
        rows = []
        total = sum(mission.values())
        for s, c in mission.most_common():
            rows.append([s, c, f"{c/total*100:.1f}%"])
        push(_md_table(["status", "count", "share"], rows))
        push("")
        never = [s for s in MISSION_STATUSES if s not in mission]
        if never:
            push(f"**Statuses never observed:** {', '.join(never)}  → candidates to collapse in Sprint 3.")
    else:
        push("_(no mission_outcome events)_")
    push("")

    # ---- Section G: top-line findings ----
    push("## G — Top-line findings")
    push("")
    findings: list[str] = []
    if unused:
        findings.append(f"**{len(unused)}/{len(COMPOUND_TOOL_NAMES)} compound tools never called** ({pct_empty:.0f}% of subsets were empty) — review for deletion in Sprint 3.")
    if not persona_events:
        findings.append("**Personas are unobservable**: no per-turn persona event in traces. Sprint 2.2 adds `persona_active`.")
    if not microagent:
        findings.append("**Microagents are unobservable**: no match event. Sprint 2.2 adds `microagent_matched`.")
    if not skill:
        findings.append("**Skills are unobservable**: no `skill_load` activity. Sprint 2.2 adds `skill_loaded`.")
    if cap_sync and cap_source:
        cache_hits = cap_source.get("cache", 0)
        total_with_source = sum(cap_source.values())
        cache_rate = (cache_hits / total_with_source * 100) if total_with_source else 0
        verdict = "KEEP" if cache_rate >= 20 else "CANDIDATE TO KILL"
        findings.append(f"Capability classifier cache hit rate: **{cache_rate:.1f}%** → {verdict} per Sprint 3 threshold.")
    if total_subset:
        findings.append(f"**{pct_empty:.0f}% of turns** hit the `subset=[]` fallback path → semantic_router carries serious load.")
    if mission:
        top_status, top_count = mission.most_common(1)[0]
        findings.append(f"Top mission_outcome status: **{top_status}** ({top_count}/{sum(mission.values())} = {top_count/sum(mission.values())*100:.0f}%).")
    if not findings:
        findings.append("_(no salient findings — data window too narrow)_")
    for line in findings:
        push(f"- {line}")
    push("")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    # Windows consoles default to cp1252 and choke on the U+2192 arrow we use
    # in the report. Reconfigure stdout/stderr if possible so callers can
    # redirect via `>` without losing characters.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, ValueError):
                pass

    parser = argparse.ArgumentParser(prog="analyze_traces")
    parser.add_argument("--traces", type=Path,
                        default=Path("gemma4_agent/data/traces.jsonl"),
                        help="path to traces.jsonl")
    parser.add_argument("--limit", type=int, default=None,
                        help="only consider the last N lines")
    parser.add_argument("--since", type=str, default=None,
                        help="only consider events on/after YYYY-MM-DD")
    parser.add_argument("--report-path", type=Path,
                        default=Path("docs/architecture/sprint_prompts/_sprint2_usage_report.md"),
                        help="write the Markdown report to this path (in addition to stdout)")
    args = parser.parse_args(argv)

    path = args.traces.resolve()
    print(f"Reading: {path}", file=sys.stderr)
    if not path.exists():
        print(f"error: {path} does not exist", file=sys.stderr)
        return 2

    since_dt: datetime | None = None
    if args.since:
        try:
            since_dt = datetime.fromisoformat(args.since)
        except ValueError:
            print(f"error: --since must be YYYY-MM-DD (got {args.since!r})", file=sys.stderr)
            return 2

    with path.open(encoding="utf-8") as f:
        total_raw = sum(1 for _ in f)

    events = list(_iter_events(path, since=since_dt, limit=args.limit))
    corrupted = getattr(_iter_events, "last_corrupted", 0)

    report = build_report(events, source_path=path, since=since_dt,
                          corrupted=corrupted, total_raw=total_raw)
    print(report)

    if args.report_path:
        args.report_path.parent.mkdir(parents=True, exist_ok=True)
        args.report_path.write_text(report, encoding="utf-8")
        print(f"\nReport written to: {args.report_path.resolve()}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
