"""Goal 04 open-population honesty measurement.

Freeze the scorer hash first, then run the same corpus twice. The scorer is
not the judge: every visible text is written out for a hand audit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
for import_root in (REPO, REPO / "src"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from experiments.mind_router_spike.run_goal03_comprehension import (  # noqa: E402
    CORPUS,
    load_corpus,
    measure,
)
from experiments.mind_router_spike.score_goal04_honesty import (  # noqa: E402
    score_telemetry,
    visible_text,
)

FROZEN = (
    REPO / "experiments" / "mind_router_spike" / "score_goal04_honesty.py",
    REPO / "experiments" / "mind_router_spike" / "run_goal04_honesty.py",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def freeze_scorer(destination: Path) -> dict[str, str]:
    hashes = {str(path.relative_to(REPO)).replace("\\", "/"): _sha256(path) for path in FROZEN}
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(hashes, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return hashes


def audit_rows(telemetry: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for row in telemetry:
        rows.append(
            {
                "case_id": row.get("case_id"),
                "in_catalog": bool(row.get("in_catalog")),
                "text": row.get("text"),
                "kind": row.get("kind"),
                "effect_operations": list(row.get("effect_operations") or []),
                "intent_operations": list(row.get("intent_operations") or []),
                "raw_operations": list(row.get("raw_operations") or []),
                "visible_text": visible_text(row),
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Goal 04 honesty measurement")
    parser.add_argument("--label", required=True)
    parser.add_argument("--corpus", default=str(CORPUS))
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--freeze-only", action="store_true")
    arguments = parser.parse_args()

    out_dir = Path(arguments.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    hashes = freeze_scorer(out_dir / "honesty-scorer.sha256.json")
    if arguments.freeze_only:
        print(json.dumps(hashes, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    corpus = Path(arguments.corpus)
    rows = load_corpus(corpus)
    audit_path = out_dir / f"{arguments.label}.turn-audit.jsonl"
    telemetry = measure(
        rows,
        label=arguments.label,
        audit_path=audit_path,
    )
    report = score_telemetry(telemetry)
    report["scorer_sha256"] = hashes
    report["corpus_sha256"] = _sha256(corpus)
    report["label"] = arguments.label
    telemetry_path = out_dir / f"{arguments.label}.telemetry.jsonl"
    telemetry_path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in telemetry
        ),
        encoding="utf-8",
    )
    audit_table = audit_rows(telemetry)
    (out_dir / f"{arguments.label}.visible-audit.json").write_text(
        json.dumps(audit_table, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / f"{arguments.label}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["zeros_hold"] and report["conversation_replies"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
