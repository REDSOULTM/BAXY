"""Compact factual view for root adjudication; never assign a quality verdict."""
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("review", type=Path)
parser.add_argument("--start", type=int, default=0)
parser.add_argument("--count", type=int, default=25)
args = parser.parse_args()
review = json.loads(args.review.read_text(encoding="utf-8-sig"))
assert isinstance(review, list)


def observations(node, depth=0):
    if depth > 8:
        return
    if isinstance(node, str):
        try:
            node = json.loads(node)
        except (ValueError, TypeError):
            return
    if not isinstance(node, dict):
        return
    if (node.get("kind") == "operation" and node.get("operation") == "system.process.list"
            and node.get("polarity") == "success" and node.get("verified") is True
            and node.get("succeeded") is True and isinstance(node.get("observed"), dict)):
        yield node["observed"]
    for step in node.get("steps") or []:
        yield from observations(step, depth + 1)


for case in review[args.start:args.start + args.count]:
    seen = {}
    drafts = {}
    rejections = {}
    for attempt in case.get("compose") or []:
        for observed in observations(attempt.get("situation")):
            key = json.dumps(observed, sort_keys=True, ensure_ascii=False)
            seen.setdefault(key, {"sort": observed.get("sort"),
                                  "observed_count": observed.get("observedProcessCount"),
                                  "returned_count": observed.get("returnedProcessCount"),
                                  "scope": observed.get("observationScope"),
                                  "logical_processors": observed.get("logicalProcessorCount"),
                                  "row_columns": ["pid", "name", "working_set_bytes", "cpu_percent", "sample_seconds"],
                                  "rows": [[row.get("processId"), row.get("name"), row.get("workingSetBytes"),
                                            row.get("cpuUsagePercent"), row.get("sampleDurationSeconds")]
                                           for row in observed.get("processes") or []]})
            if attempt.get("stage") == "first":
                drafts.setdefault(attempt.get("draft"), attempt.get("reason"))
        reason = attempt.get("reason")
        if reason:
            rejections[reason] = rejections.get(reason, 0) + 1
    terminal = case["terminal"]
    print(json.dumps({"case_id": case["case_id"], "turn_id": case["turn_id"],
                      "group": case["group"], "request": case["text"],
                      "criterion": case["criterion"], "terminal_kind": terminal["kind"],
                      "final": terminal["final"], "core_calls": case.get("core_calls"),
                      "verified_observations": list(seen.values()),
                      "first_drafts": [{"text": text, "reason": reason} for text, reason in drafts.items()],
                      "rejection_occurrences": rejections,
                      "quality_adjudicated_by_this_script": False}, ensure_ascii=False))
