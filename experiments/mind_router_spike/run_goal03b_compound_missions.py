"""Goal 03B: a regression guard for chained requests, not a target.

The goal 03 corpus has no compound action in it. Its 160 rows are single
attempts, and the 23 that list several operations list them as *acceptable
alternatives* -- the scorer is right if any one of them matches -- not as a
sequence to run. "Conéctate al wifi de casa" is served by ``wifi.connect.named``
or by ``wifi.connect``; no row says "open Steam and go to the library".

That leaves goal 03B blind exactly where goal 01 measured the damage of
consolidating to concentrate: follow-ups, multilingual and chaining. And there is
an identity reason as well as a measurement one -- chaining is what lets the
catalogue shrink without coverage shrinking, so "coverage did not drop" is a
claim about paper until something checks that what stops fitting in one
operation is absorbed by a chain.

Building the compound missions belongs to goal 07 and is not done here. What is
done here is not leaving them broken: fifteen chained requests in the three
languages, with the implicit dependencies people actually speak -- sequencing
heads, elided verbs, bare ordinals, demonstratives pointing at what the previous
clause created, conditionals, and code-switched second clauses -- measured
before and after the change, through the same ``turn.decide`` boundary as the
main corpus. No provider is enabled and no effect is executed.

The score is step coverage, not an alternatives hit: a mission counts as whole
only when every one of its steps is named by the turn.

Usage::

    python -m experiments.mind_router_spike.run_goal03b_compound_missions --label after
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import statistics
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
for import_root in (REPO, REPO / "src"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from experiments.mind_router_spike.run_goal03_comprehension import (  # noqa: E402
    _final_operations,
    load_corpus,
    measure,
)

SCHEMA = "baxy.goal03b-compound-missions.v1"
CORPUS = REPO / "artifacts" / "development" / "goal03b_compound_missions.v1.jsonl"
RESULT_DIR = REPO / "artifacts" / "development"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def score(telemetry: list[dict[str, Any]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    named_steps = 0
    total_steps = 0
    whole_missions = 0
    for row in telemetry:
        proposed = set(_final_operations(row))
        # A step is named when the turn keeps any operation that satisfies it.
        # Repeated steps of the same operation -- two note.create in one mission
        # -- are counted once here on purpose: this boundary decides operations,
        # not cardinality, and goal 07 owns the execution of the sequence.
        covered = [bool(proposed & set(step)) for step in row["steps"]]
        named_steps += sum(covered)
        total_steps += len(covered)
        whole = all(covered)
        whole_missions += whole
        rows.append(
            {
                "case_id": row["case_id"],
                "language": row["language"],
                "dependency": row["dependency"],
                "decision_path": row["decision_path"],
                "kind": row["kind"],
                "steps": row["steps"],
                "step_named": covered,
                "whole": whole,
                "final_operations": sorted(proposed),
                "seconds": row["seconds"],
                "question": row["question"],
                "reply_text": row["reply_text"],
            }
        )
    seconds = sorted(row["seconds"] for row in telemetry)
    return {
        "schema": SCHEMA,
        "missions": {
            "rows": len(rows),
            "whole": whole_missions,
            "rate": round(whole_missions / max(len(rows), 1), 4),
        },
        "steps": {
            "total": total_steps,
            "named": named_steps,
            "rate": round(named_steps / max(total_steps, 1), 4),
        },
        "by_language": {
            language: {
                "rows": sum(1 for row in rows if row["language"] == language),
                "whole": sum(
                    1 for row in rows if row["language"] == language and row["whole"]
                ),
            }
            for language in sorted({row["language"] for row in rows})
        },
        "by_kind": dict(collections.Counter(row["kind"] for row in rows)),
        "latency_seconds": {
            "p50": round(statistics.median(seconds), 3) if seconds else None,
            "p90": round(seconds[min(len(seconds) - 1, int(len(seconds) * 0.9))], 3)
            if seconds
            else None,
            "max": round(seconds[-1], 3) if seconds else None,
        },
        "three_zeros": {
            "providers_enabled": False,
            "effects_executed": 0,
        },
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Goal 03B compound mission guard")
    parser.add_argument("--label", required=True)
    parser.add_argument("--corpus", default=str(CORPUS))
    parser.add_argument("--rescore", action="store_true")
    arguments = parser.parse_args()

    corpus = Path(arguments.corpus)
    rows = load_corpus(corpus)
    audit_path = RESULT_DIR / f"goal03b_compound_{arguments.label}.turn-audit.jsonl"
    telemetry_path = RESULT_DIR / f"goal03b_compound_{arguments.label}.telemetry.jsonl"
    if arguments.rescore:
        telemetry = load_corpus(telemetry_path)
    else:
        telemetry = measure(
            rows,
            label=f"compound-{arguments.label}",
            audit_path=audit_path,
        )
    result = score(telemetry)
    result["corpus"] = {
        "path": str(corpus.relative_to(REPO)),
        "sha256": _sha256(corpus),
        "rows": len(rows),
    }
    telemetry_path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in telemetry
        ),
        encoding="utf-8",
        newline="\n",
    )
    (RESULT_DIR / f"goal03b_compound_{arguments.label}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                key: result[key]
                for key in ("missions", "steps", "by_language", "latency_seconds")
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
