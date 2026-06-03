"""Audit: every tool_args.action in train/holdout/curated must exist in the
schema's 'Actions:' list for its tool. Authoritative source for valid actions
is gemma4_agent/tools_pkg/tool_schemas.py (the 'Actions:' enumeration in each
tool description). Read-only; does not modify any data.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gemma4_agent.tools_pkg.tool_schemas import COMPOUND_TOOL_SCHEMAS  # noqa: E402

# ---------------------------------------------------------------------------
# 1. Parse valid actions per tool from the schema descriptions.
#    The contract text is 'Actions: a, b, c.' (sometimes spanning to a newline
#    or to the first sentence end). We grab the comma-separated tokens after
#    'Actions:' up to the first newline or period that ends the list.
# ---------------------------------------------------------------------------
ACTIONS_RE = re.compile(r"Actions?:\s*(.+?)(?:\.\s|\.$|\n)", re.IGNORECASE | re.DOTALL)


def parse_actions(desc: str) -> set[str]:
    m = ACTIONS_RE.search(desc)
    if not m:
        return set()
    blob = m.group(1)
    # Stop at the first newline if the regex captured beyond it.
    blob = blob.split("\n")[0]
    out: set[str] = set()
    for tok in blob.split(","):
        tok = tok.strip()
        # strip trailing parenthetical notes e.g. "wifi_connect (connect ...)"
        tok = re.split(r"[\s(]", tok, 1)[0].strip()
        # drop trailing punctuation
        tok = tok.strip(".:;")
        # Expand the "prefix_a/b" slash shorthand the schema uses for paired
        # actions, e.g. "magnifier_start/stop" -> magnifier_start, magnifier_stop;
        # "ps/ps_all" -> ps, ps_all.
        if "/" in tok:
            parts = tok.split("/")
            base = parts[0]
            prefix = base.rsplit("_", 1)[0] if "_" in base else ""
            for i, p in enumerate(parts):
                p = p.strip()
                if not p:
                    continue
                if i == 0:
                    cand = p
                elif "_" in p or not prefix:
                    cand = p
                else:
                    cand = f"{prefix}_{p}"
                if re.fullmatch(r"[a-z][a-z0-9_]*", cand):
                    out.add(cand)
            continue
        if tok and re.fullmatch(r"[a-z][a-z0-9_]*", tok):
            out.add(tok)
    return out


VALID_ACTIONS: dict[str, set[str]] = {}
for sch in COMPOUND_TOOL_SCHEMAS:
    fn = sch.get("function", {})
    name = fn.get("name")
    desc = fn.get("description", "")
    acts = parse_actions(desc)
    VALID_ACTIONS[name] = acts

# Tools whose schema has no 'Actions:' enumeration (free-form action or none).
NO_ACTION_LIST = {t for t, a in VALID_ACTIONS.items() if not a}

# ---------------------------------------------------------------------------
# 2. Scan dataset files.
# ---------------------------------------------------------------------------
FILES = ["train.jsonl", "holdout.jsonl", "curated.jsonl"]
CUR = ROOT / "dataset_finetune" / "curated"

# Specific watch list from the brief.
WATCH = {
    "developer": ("start_dev", "start_dev_server"),
    "printer_scanner": ("cancel", "cancel_job"),
}

invalid = []          # (file, lineno, tool, action, id)
unknown_tool = []     # action present but tool not resolvable / not in schema
no_schema_action = [] # tool has no Actions: list but record carries an action
rows_with_action = 0
total_rows = 0
watch_hits = {k: {} for k in WATCH}  # tool -> {action: count}


def tools_for(rec) -> list[str]:
    t = rec.get("correct_tools") or []
    if isinstance(t, str):
        t = [t]
    return [x for x in t if isinstance(x, str)]


for fname in FILES:
    fp = CUR / fname
    if not fp.exists():
        print(f"MISSING FILE: {fp}")
        continue
    with open(fp, encoding="utf-8") as fh:
        for ln, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            total_rows += 1
            rec = json.loads(line)
            ta = rec.get("tool_args")
            if not isinstance(ta, dict):
                continue
            action = ta.get("action")
            if not action or not isinstance(action, str):
                continue
            rows_with_action += 1
            rid = rec.get("id", "")
            tools = tools_for(rec)

            # Track watch-list tools regardless of validity.
            for wt in WATCH:
                if wt in tools:
                    watch_hits[wt][action] = watch_hits[wt].get(action, 0) + 1

            # Determine which tool this action belongs to. action lives in a
            # single tool_args dict; pair it with whichever correct_tool's
            # schema recognizes the action. If exactly one tool, use it.
            if not tools:
                unknown_tool.append((fname, ln, None, action, rid))
                continue

            # If any tool in correct_tools validly owns this action -> OK.
            owners = [t for t in tools if action in VALID_ACTIONS.get(t, set())]
            if owners:
                continue
            # No owner. Distinguish causes.
            # Case A: some tool in the list has NO action list (free-form) ->
            #         can't be judged invalid by enum; record separately.
            freeform = [t for t in tools if t in NO_ACTION_LIST]
            schema_tools = [t for t in tools if t not in NO_ACTION_LIST and t in VALID_ACTIONS]
            not_in_schema = [t for t in tools if t not in VALID_ACTIONS]
            if not_in_schema:
                unknown_tool.append((fname, ln, ",".join(not_in_schema), action, rid))
                continue
            if schema_tools:
                # Action not recognized by any schema-bearing tool -> INVALID.
                invalid.append((fname, ln, ",".join(schema_tools), action, rid))
            elif freeform:
                no_schema_action.append((fname, ln, ",".join(freeform), action, rid))


# ---------------------------------------------------------------------------
# 3. Report.
# ---------------------------------------------------------------------------
print("=" * 70)
print(f"Total rows scanned : {total_rows}")
print(f"Rows with tool_args.action : {rows_with_action}")
print(f"Tools with NO 'Actions:' enum in schema: {sorted(NO_ACTION_LIST)}")
print("=" * 70)

print("\n-- WATCH LIST (developer / printer_scanner) --")
for wt, acts in watch_hits.items():
    valid = VALID_ACTIONS.get(wt, set())
    print(f"  {wt}: valid_actions_count={len(valid)}")
    for a, c in sorted(acts.items()):
        ok = "OK" if a in valid else "INVALID"
        print(f"      action={a!r:24} count={c:4d}  -> {ok}")
        if wt in ("developer", "printer_scanner"):
            assert a != "start_dev" or wt != "developer", "start_dev present!"

print(f"\n-- INVALID actions (action not in its tool's schema): {len(invalid)} --")
for row in invalid[:50]:
    print("   ", row)

print(f"\n-- Action present but tool not in schema/unknown: {len(unknown_tool)} --")
for row in unknown_tool[:50]:
    print("   ", row)

print(f"\n-- Action on a tool with free-form action (no enum, NOT counted invalid): {len(no_schema_action)} --")
for row in no_schema_action[:30]:
    print("   ", row)

pass_ = (len(invalid) == 0 and len(unknown_tool) == 0)
print("\n" + "=" * 70)
print(f"RESULT: invalid={len(invalid)}  unknown_tool={len(unknown_tool)}  pass={pass_}")
print("=" * 70)
