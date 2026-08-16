"""Build the hash-bound MTOP R4 operation-nomination oracle.

The output is development-only input for a side-effect-free ``turn.decide``
probe.  It names the expected catalog operation but supplies no arguments and
grants no execution authority.  The normal product grounding and veto stages
must still decide whether the turn is actionable, needs clarification, or
must abstain.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"
for path in (REPO, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import measure_turn_policy_v52_mtop_validation as mtop  # noqa: E402
from experiments.mind_router_spike.probe_mtop_product_validation import (  # noqa: E402
    SEED,
    _canonical_sha256,
    expected_turn,
    select_validation_rows,
)
from scripts.measure_mind_budget import write_json_atomic  # noqa: E402


DEFAULT_OUTPUT = (
    REPO
    / "artifacts"
    / "research"
    / "mtop_product_validation_development_r4_operation_oracle.json"
)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def build(*, output: Path, groups_per_stratum: int) -> dict[str, Any]:
    rows, manifest, identity = mtop._load_development(
        mtop.DEVELOPMENT_CORPUS,
        mtop.MANIFEST,
    )
    selected = select_validation_rows(
        rows,
        groups_per_stratum=groups_per_stratum,
    )
    cases = []
    seen_text: dict[str, tuple[str, ...]] = {}
    for index, row in enumerate(selected):
        expected = expected_turn(row)
        operations = tuple(str(value) for value in expected["intent_operations"])
        text = str(row["text"])
        previous = seen_text.setdefault(text, operations)
        if previous != operations:
            raise ValueError(
                "the R4 oracle contains one text with conflicting operations"
            )
        cases.append(
            {
                "request_id": f"mtop-validation-{index}",
                "source_id": str(row["source_id"]),
                "mission_id": str(row["mission_id"]),
                "locale": str(row["locale"]),
                "text": text,
                "disposition": str(row["projection"]["disposition"]),
                "intent_operations": list(operations),
                "expected_kinds": list(expected["kinds"]),
                "expected_effect_operations": list(expected["effect_operations"]),
            }
        )
    if not cases:
        raise ValueError("the R4 operation oracle is empty")
    case_identity = hashlib.sha256(_canonical_bytes(cases)).hexdigest()
    report = {
        "schema": "baxy.mtop-r4-operation-oracle.development.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "development_validation_only_mtop_test_remains_sealed",
        "authority": (
            "operation nomination only; no arguments, effect authority, Core, "
            "or provider access"
        ),
        "side_effect_free": True,
        "source": {
            "corpus_sha256": identity.corpus.sha256,
            "manifest_sha256": identity.manifest.sha256,
            "map_sha256": manifest["source"]["map_sha256"],
            "selection_seed": SEED,
            "groups_per_stratum": groups_per_stratum,
            "selected_rows": len(cases),
            "selected_missions": len({case["mission_id"] for case in cases}),
            "selected_identity_sha256": _canonical_sha256(
                [case["source_id"] for case in cases]
            ),
            "cases_sha256": case_identity,
            "test_content_read": False,
        },
        "cases": cases,
    }
    write_json_atomic(output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--groups-per-stratum", type=int, default=8)
    args = parser.parse_args()
    report = build(
        output=args.output,
        groups_per_stratum=args.groups_per_stratum,
    )
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "cases": len(report["cases"]),
                "cases_sha256": report["source"]["cases_sha256"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
