"""Summarize a run of scripts/measure_app_visible_path.ps1.

The harness writes one raw trace per launched app plus an index describing which
block used which trace and in what order. This script turns that into the
per-stage picture: how long a person waited, and which stage spent it, for the
cold arm and the warm arm separately.

Attribution is by position inside a block, not by wall clock. Within one block
the harness sends the frozen scenario set in a fixed order and waits between
each, and the trace records turns in that same order, so the n-th turn of a
block is the n-th scenario. When a block's turn count does not equal its
scenario count the block is reported as unattributed rather than guessed at,
because a wall-clock correlation across a shared trace file is exactly the kind
of inference that produced a retracted artifact before.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.measure_mind_budget import write_json_atomic  # noqa: E402

SCHEMA = "baxy.app-visible-path.v3"

# Each stage is (name, opening record, closing record), measured on the first
# occurrence of each inside the turn. ``msg`` records are not turn-scoped, so
# they are matched to the turn they fall inside by sequence.
TURN_STAGES: tuple[tuple[str, str, str], ...] = (
    ("keystroke_to_submit_ms", "key.enter", "submit.received"),
    ("bridge_crossing_ms", "submit.received", "bridge.crossed"),
    ("queue_wait_ms", "bridge.crossed", "queue.wait.end"),
    ("decision_ms", "decision.start", "decision.ready"),
    ("arguments_grounding_ms", "arguments.start", "arguments.end"),
    ("core_and_provider_and_verify_ms", "core.call.start", "core.call.end"),
    ("llm_composition_ms", "compose.start", "compose.end"),
    ("first_indication_ms", "key.enter", "visible.indication"),
)

# The stages that must anchor on the answer, not on the echo of what the person
# typed. A turn paints twice: first the user's own message, then the answer. The
# first ``paint.observed`` after ``key.enter`` is the echo, so measuring to it
# reports times shorter than the composition it supposedly contains. These are
# measured from the first ``dom.applied``/``paint.observed`` at or after
# ``visible.text``, which is the record that publishes the answer.
ANSWER_STAGES: tuple[tuple[str, str, str], ...] = (
    ("publish_to_dom_ms", "visible.text", "dom.applied"),
    ("dom_to_paint_ms", "dom.applied", "paint.observed"),
    ("keystroke_to_paint_ms", "key.enter", "paint.observed"),
)


def _read_trace(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict) and "stage" in record and "ms" in record:
            rows.append(record)
    rows.sort(key=lambda record: record.get("seq", 0))
    return rows


def _split_turns(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Cut the trace into turns, one per keystroke that submitted a question."""

    starts = [
        index for index, record in enumerate(rows)
        if record.get("stage") == "key.enter"
    ]
    turns: list[dict[str, Any]] = []
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(rows)
        window = rows[start:end]
        # The turn identifier is whichever non-``msg`` scope appears in the
        # window; ``msg`` records belong to whatever turn encloses them.
        identifiers = {
            record.get("id") for record in window
            if record.get("scope") == "turn" and record.get("id") != "msg"
        }
        first: dict[str, float] = {}
        for record in window:
            stage = str(record.get("stage"))
            if stage not in first:
                first[stage] = float(record["ms"])

        # Everything from the answer's publication onwards, so the paint that is
        # measured is the answer's and not the echo of the typed message.
        answer: dict[str, float] = {}
        publishing = False
        for record in window:
            stage = str(record.get("stage"))
            if stage == "visible.text":
                publishing = True
            if publishing and stage not in answer:
                answer[stage] = float(record["ms"])

        turns.append({
            "turn_id": sorted(identifiers)[0] if identifiers else None,
            "stages": first,
            "answer_stages": answer,
        })
    return turns


def _measure(turn: dict[str, Any]) -> dict[str, float]:
    stages = turn["stages"]
    answer = turn["answer_stages"]
    measured: dict[str, float] = {}
    for name, opening, closing in TURN_STAGES:
        if opening in stages and closing in stages:
            value = stages[closing] - stages[opening]
            if value >= 0:
                measured[name] = round(value, 3)

    for name, opening, closing in ANSWER_STAGES:
        # ``key.enter`` only ever exists in the turn-wide map; the closing
        # record must come from the answer window.
        start = answer.get(opening, stages.get(opening) if opening == "key.enter" else None)
        end = answer.get(closing)
        if start is not None and end is not None:
            value = end - start
            if value >= 0:
                measured[name] = round(value, 3)
    return measured


def _summarize(values: list[float]) -> dict[str, Any]:
    ordered = sorted(values)
    return {
        "n": len(ordered),
        "min_ms": round(ordered[0], 3),
        "p50_ms": round(statistics.median(ordered), 3),
        "max_ms": round(ordered[-1], 3),
        "mean_ms": round(statistics.fmean(ordered), 3),
        "stdev_ms": round(statistics.stdev(ordered), 3) if len(ordered) > 1 else 0.0,
        "values_ms": [round(value, 3) for value in ordered],
    }


def run(index_path: Path, output: Path) -> dict[str, Any]:
    index = json.loads(index_path.read_text(encoding="utf-8-sig"))
    scenarios = index["scenario_fixture"]["scenarios"]
    expected = len(scenarios)

    traces: dict[str, list[dict[str, Any]]] = {}
    consumed: dict[str, int] = defaultdict(int)
    samples: list[dict[str, Any]] = []
    unattributed: list[dict[str, Any]] = []

    for block in index["blocks"]:
        trace_path = str(block["trace_path"])
        if trace_path not in traces:
            traces[trace_path] = _split_turns(_read_trace(Path(trace_path)))
        turns = traces[trace_path]
        # Warmup turns are real turns in the trace but belong to no scenario, so
        # they are consumed before the block's scenarios are attributed.
        consumed[trace_path] += int(block.get("warmup_turns") or 0)
        start = consumed[trace_path]
        window = turns[start:start + expected]
        if len(window) != expected:
            unattributed.append({
                "block_id": block["block_id"],
                "arm": block["arm"],
                "expected_turns": expected,
                "found_turns": len(window),
                "reason": (
                    "the block's turn count does not match its scenario count, "
                    "so no turn can be attributed to a scenario by position"),
            })
            consumed[trace_path] = start + len(window)
            continue

        consumed[trace_path] = start + expected
        for position, turn in enumerate(window):
            scenario = scenarios[position]
            samples.append({
                "block_id": block["block_id"],
                "round": block["round"],
                "arm": block["arm"],
                "scenario_id": scenario["Id"],
                "route": scenario["Route"],
                "position_in_block": position,
                "turn_id": turn["turn_id"],
                "stages_ms": _measure(turn),
            })

    def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
        collected: dict[str, list[float]] = defaultdict(list)
        for row in rows:
            for name, value in row["stages_ms"].items():
                collected[name].append(value)
        return {
            name: _summarize(values)
            for name, values in sorted(collected.items())
        }

    by_arm = {
        arm: aggregate([row for row in samples if row["arm"] == arm])
        for arm in ("cold", "warm")
    }
    by_route = {
        route: aggregate([row for row in samples if row["route"] == route])
        for route in sorted({row["route"] for row in samples})
    }
    by_scenario = {
        scenario_id: aggregate(
            [row for row in samples if row["scenario_id"] == scenario_id])
        for scenario_id in sorted({row["scenario_id"] for row in samples})
    }

    # A median over a whole cold block hides the one turn that actually costs a
    # cold start, because the model is only unwarmed for the first question.
    # That turn is reported on its own.
    first_turns = {
        arm: aggregate([
            row for row in samples
            if row["arm"] == arm and row["position_in_block"] == 0
        ])
        for arm in ("cold", "warm")
    }
    later_turns = {
        arm: aggregate([
            row for row in samples
            if row["arm"] == arm and row["position_in_block"] > 0
        ])
        for arm in ("cold", "warm")
    }

    cold = by_arm["cold"].get("keystroke_to_paint_ms")
    warm = by_arm["warm"].get("keystroke_to_paint_ms")
    report = {
        "schema": SCHEMA,
        "harness": index["schema"],
        "run_id": index["run_id"],
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "effects_executed": 0,
        "attribution": (
            "by position inside a block: the harness sends the frozen scenario "
            "set in a fixed order and waits between each, so the n-th turn of a "
            "block is the n-th scenario. Blocks whose turn count does not match "
            "are reported as unattributed instead of being correlated by clock."),
        "scenario_fixture_sha256": index["scenario_fixture"]["sha256"],
        "design": index["design"],
        "environment_before": index["environment_before"],
        "environment_after": index["environment_after"],
        "samples_attributed": len(samples),
        "blocks_unattributed": unattributed,
        "cold_vs_warm_keystroke_to_paint": (
            {
                "cold_p50_ms": cold["p50_ms"],
                "warm_p50_ms": warm["p50_ms"],
                "delta_p50_ms": round(cold["p50_ms"] - warm["p50_ms"], 3),
            } if cold and warm else None
        ),
        "by_arm": by_arm,
        "first_turn_of_each_block": first_turns,
        "later_turns_of_each_block": later_turns,
        "by_route": by_route,
        "by_scenario": by_scenario,
        "samples": samples,
    }
    write_json_atomic(output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("index", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO / "artifacts" / "fixes" / "app_visible_path_v3.json")
    args = parser.parse_args()
    report = run(args.index, args.output)
    print(json.dumps({
        "samples_attributed": report["samples_attributed"],
        "blocks_unattributed": len(report["blocks_unattributed"]),
        "cold_vs_warm": report["cold_vs_warm_keystroke_to_paint"],
    }, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
