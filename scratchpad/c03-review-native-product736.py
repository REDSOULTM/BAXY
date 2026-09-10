"""Read-only correlation of frozen product736 captures, including partial runs."""
from pathlib import Path
import argparse
import json
import os
import re


parser = argparse.ArgumentParser()
parser.add_argument("model", choices=["k2", "qwen"])
mode = parser.add_mutually_exclusive_group()
mode.add_argument("--partial", action="store_true")
mode.add_argument("--interrupted", action="store_true", help="Seal completed terminals after a recorded RAM guard stop.")
parser.add_argument("--start", type=int, default=0)
parser.add_argument("--count", type=int, default=25)
parser.add_argument("--ids", default="")
parser.add_argument("--summary", action="store_true")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
private = Path(os.environ["LOCALAPPDATA"]) / f"BAXY/C03-native-product736-{args.model}-private"
public = root / f"artifacts/comprobaciones/C03/NATIVE_PRODUCT736/{args.model}"
truncated_tails = []


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(path):
    if not path.exists() and args.partial:
        return []
    lines = path.read_bytes().decode("utf-8-sig").splitlines(keepends=True)
    result = []
    for index, line in enumerate(lines):
        try:
            result.append(json.loads(line))
        except json.JSONDecodeError:
            if not ((args.partial or args.interrupted) and index == len(lines)-1 and not line.endswith("\n")):
                raise
            truncated_tails.append(str(path))
    return result


panel = read(private / "panel.json")
assert len(panel) == 73
if not args.partial:
    outcome = read(public / "EXIT.json")
    assert outcome["exit_code"] == (1 if args.interrupted else 0)
    if args.interrupted:
        assert read(public / "RESOURCES.json")["violations"] == ["free_ram_bound"]
    assert all(outcome[key] for key in (
        "manifest_unchanged", "sources_unchanged", "scripts_unchanged", "app_dll_unchanged"))
events = rows(private / "capture/events.jsonl")
finals = [row for row in events if row.get("type") == "terminal"]
assert len(finals) <= len(panel)
if not args.partial and not args.interrupted:
    assert len(finals) == len(panel)
shell = rows(private / "shell-trace.jsonl")
compose = rows(private / "compose-audit.jsonl")
audit = rows(private / "turn-audit.jsonl")
decisions = {row["request_id"]: row for row in audit if row.get("phase") == "final"}
review = []
for index, (case, final) in enumerate(zip(panel, finals), 1):
    trace = [row for row in shell if row["scope"] == "turn" and row["id"] == f"t{index}"]
    ids = [match[1] for row in trace
           if (match := re.search(r"turn\.decide\.id\.(\d+)\.", row.get("detail") or ""))]
    drafts = [row for row in compose if row.get("trace") == f"t{index}"]
    review.append({**case, "turn_id": f"t{index}", "terminal": final,
        "core_calls": [row["detail"] for row in trace if row["stage"] == "core.call.start"],
        "decisions": [decisions[key] for key in ids if key in decisions], "compose": drafts,
        "trace_duration_ms": trace[-1]["ms"]-trace[0]["ms"] if trace else None})
destination = private / ("live-review.json" if args.partial else "review.json")
destination.write_text(json.dumps(review, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
print(json.dumps({"model": args.model, "completed": len(review), "total": len(panel),
                  "partial": args.partial, "interrupted": args.interrupted,
                  "truncated_tails": truncated_tails, "review": str(destination)}))
if not args.partial:
    (public / "REVIEW_CAPTURE.json").write_text(json.dumps({
        "completed_terminals": len(review), "registered_total": len(panel),
        "interrupted": args.interrupted, "truncated_tails": [Path(p).name for p in truncated_tails],
        "quality_adjudicated": False,
    }, indent=2)+"\n", encoding="utf-8")
selected = ([row for row in review if row["case_id"] in args.ids.split(",")]
            if args.ids else review[args.start:args.start+args.count])
for row in selected:
    first = next((draft for draft in row["compose"] if draft.get("stage") == "first"), {})
    print(json.dumps({"id": row["case_id"], "turn": row["turn_id"], "group": row["group"],
        "text": row["text"], "final": row["terminal"]["final"], "kind": row["terminal"]["kind"],
        "core_calls": row["core_calls"], "milliseconds": row["trace_duration_ms"],
        "facts": None if args.summary else first.get("payload"),
        "rejected": None if args.summary else [
            {key: draft.get(key) for key in ["stage", "draft", "reason"]}
            for draft in row["compose"] if draft.get("reason")]}, ensure_ascii=False))
