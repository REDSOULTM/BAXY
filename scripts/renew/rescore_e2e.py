"""Re-scores the oracles of saved e2e cases without running BAXY (nb-ayudas, PC 2026-10-19 14:50).

For each case: the speech record is rebuilt from the run's events.jsonl with bench_e2e.utterances (the bench's own
rule) and the case's saved replies.json; then the case's oracles that read only that record or the world as it still
is are run again (speech oracles: Test-Spoken, Test-ConfirmationSpoken, Test-AllSpoken, Test-SpeechCut; and, with
--rerun-world, the rest, for oracles whose world can be rebuilt by hand, such as Steam's). Prints the old and the new
result of each oracle.

Usage: py -3.12 scripts/renew/rescore_e2e.py <run dir> <cases.json> <case id>[,<case id>...] [--rerun-world]
"""
import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bench_e2e  # noqa: E402

SPEECH_ORACLES = re.compile(r"Test-(Spoken|ConfirmationSpoken|AllSpoken|SpeechCut)\b")


class RunMismatch(ValueError):
    """The run's events do not hold the case where its results.jsonl says it ran."""


def case_span(events: list, rows: list, case_id: str) -> tuple[int, int]:
    """Where the case ran: bench_e2e begins each case whose setup passed with a new session (a command.done with
    session «new»), in the order of results.jsonl; the case's events run until the next case's first turn (the end of
    its last utterance may come just after the next new session)."""
    judged = [row["id"] for row in rows
              if "id" in row and row.get("status") not in ("setup_fallido", "sesion_bloqueada")]
    marks = [i for i, e in enumerate(events) if e.get("type") == "command.done" and e.get("session") == "new"]
    if case_id not in judged:
        raise RunMismatch(f"{case_id}: no turns in this run (not in results.jsonl, its setup failed or the session "
                          f"was locked)")
    if len(marks) != len(judged):
        raise RunMismatch(f"{case_id}: events.jsonl has {len(marks)} new sessions for {len(judged)} cases with turns "
                          f"in results.jsonl")
    n = judged.index(case_id)
    if n + 1 == len(marks):
        return marks[n], len(events)
    return marks[n], next((i for i in range(marks[n + 1], len(events)) if events[i].get("type") == "turn.start"),
                          len(events))


def turn_bounds(events: list, case: dict, replies: list, span: tuple[int, int]) -> tuple[list, int]:
    """The index where each of the case's turns began (its turn.start), as bench_e2e.judge_case noted it, searched only
    within the case's span (R12.5: from the run's start, a «sí» or «para» of an earlier case was taken for this one's)."""
    begin, limit = span
    texts = [turn["text"] for turn in case.get("turns") or []]
    starts, position = [], begin
    for number, text in enumerate(texts, start=1):
        index = next((i for i in range(position, limit) if events[i].get("type") == "turn.start"
                      and (events[i].get("input") or {}).get("text") == text), None)
        if index is None:
            raise RunMismatch(f"{case['id']}: turn {number} ({text!r}) has no turn.start in the case's events "
                              f"[{begin}, {limit})")
        starts.append(index)
        position = index + 1
    # The case's last turn ends where a turn that is not its own began (the answer to a confirmation is part of the
    # turn), and never after the next case's first turn.
    own = set(texts) | {r.get("answered") for r in replies if r.get("answered")}
    end = next((i for i in range(position, limit) if events[i].get("type") == "turn.start"
                and (events[i].get("input") or {}).get("text") not in own), limit)
    return starts, end


def rescore(run_dir: Path, case: dict, rerun_world: bool) -> list:
    events = [json.loads(line) for line in (run_dir / "events.jsonl").open(encoding="utf-8", errors="replace")
              if line.strip()]
    case_dir = run_dir / case["id"]
    replies = json.loads((case_dir / "replies.json").read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in (run_dir / "results.jsonl").open(encoding="utf-8") if line.strip()]
    starts, end = turn_bounds(events, case, replies, case_span(events, rows, case["id"]))
    speech = bench_e2e.utterances(events[:end], starts, replies)
    old = next((row for row in rows if row.get("id") == case["id"]), {})
    work = Path(tempfile.mkdtemp(prefix=f"rescore-{case['id']}-"))
    (work / "speech.json").write_text(json.dumps(speech, ensure_ascii=False), encoding="utf-8")
    env = dict(os.environ, BAXY_E2E_REPLIES=str(case_dir / "replies.json"), BAXY_E2E_SPEECH=str(work / "speech.json"))
    rows = []
    for index, oracle in enumerate(case.get("oracle") or []):
        before = (old.get("oracles") or [{}] * (index + 1))[index] if index < len(old.get("oracles") or []) else {}
        if not SPEECH_ORACLES.search(oracle["ps"]) and not rerun_world:
            rows.append((index, before.get("out"), "(not re-run: reads the world of the run)"))
            continue
        script = work / f"oracle{index}.ps1"
        bench_e2e.ps_file(script, [oracle["ps"]])
        code, out = bench_e2e.run_ps(script, env, 240)
        matched = code == 0 and re.search(oracle["expect_regex"], out.strip()) is not None
        rows.append((index, before.get("out"), f"{out.strip()[:200]} -> {'OK' if matched else 'NO'}"))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("cases", type=Path)
    parser.add_argument("ids")
    parser.add_argument("--rerun-world", action="store_true")
    args = parser.parse_args()
    data = json.loads(args.cases.read_text(encoding="utf-8"))
    cases = {c["id"]: c for c in (data if isinstance(data, list) else data["cases"])}
    for case_id in args.ids.split(","):
        try:
            rows = rescore(args.run_dir, cases[case_id], args.rerun_world)
        except RunMismatch as error:
            sys.exit(f"{args.run_dir.name} {error}")
        for index, before, after in rows:
            print(f"{args.run_dir.name} {case_id} oracle{index}: before {before!r} | now {after}")


if __name__ == "__main__":
    main()
