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


def turn_bounds(events: list, case: dict, replies: list) -> list:
    """The index where each of the case's turns began (its turn.start), as bench_e2e.judge_case noted it."""
    texts = [turn["text"] for turn in case.get("turns") or []]
    starts, position = [], 0
    for text in texts:
        index = next(i for i in range(position, len(events))
                     if events[i].get("type") == "turn.start" and (events[i].get("input") or {}).get("text") == text)
        starts.append(index)
        position = index + 1
    # The run went on with the next case; the case's last turn ends where a turn that is not its own began (the answer
    # to a confirmation is part of the turn).
    own = set(texts) | {r.get("answered") for r in replies if r.get("answered")}
    end = next((i for i in range(position, len(events)) if events[i].get("type") == "turn.start"
                and (events[i].get("input") or {}).get("text") not in own), len(events))
    return starts, end


def rescore(run_dir: Path, case: dict, rerun_world: bool) -> list:
    events = [json.loads(line) for line in (run_dir / "events.jsonl").open(encoding="utf-8", errors="replace")
              if line.strip()]
    case_dir = run_dir / case["id"]
    replies = json.loads((case_dir / "replies.json").read_text(encoding="utf-8"))
    starts, end = turn_bounds(events, case, replies)
    speech = bench_e2e.utterances(events[:end], starts, replies)
    old = next((json.loads(line) for line in (run_dir / "results.jsonl").open(encoding="utf-8")
                if json.loads(line).get("id") == case["id"]), {})
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
        for index, before, after in rescore(args.run_dir, cases[case_id], args.rerun_world):
            print(f"{args.run_dir.name} {case_id} oracle{index}: before {before!r} | now {after}")


if __name__ == "__main__":
    main()
