"""Compare frozen operation rankers on the open MTOP R4 development slice.

The selected MTOP rows were already opened by the R4 product probe. This
diagnostic does not read the official test split and the ranker remains an
advisory candidate orderer without execution authority.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from scipy.sparse import hstack

from probe_operation_shortlist_current_review import NO_ACTION, _resources


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ASSETS = ROOT / "artifacts/research/operation_shortlist_v1"
DEFAULT_INPUT = (
    ROOT / "artifacts/fixes/mtop_product_validation_development_r4_current.json"
)


def _complete_hit(ranking: list[str], expected: frozenset[str], count: int) -> bool:
    return expected <= frozenset(ranking[:count])


def probe(args: argparse.Namespace) -> dict[str, Any]:
    source = json.loads(args.input.read_text(encoding="utf-8"))
    rows = source["samples"]
    words, characters, classes, coefficients, intercept = _resources(args.assets)
    texts = [str(row["text"]) for row in rows]
    features = hstack(
        (words.transform(texts), characters.transform(texts)),
        format="csr",
    )
    scores = np.asarray(features @ coefficients.T + intercept)
    rankings = [
        [classes[index] for index in np.argsort(-scores[row_index])]
        for row_index in range(len(rows))
    ]
    expected = [
        frozenset(str(value) for value in row["expected"]["intent_operations"])
        or frozenset({NO_ACTION})
        for row in rows
    ]

    def metrics(indices: list[int]) -> dict[str, Any]:
        return {
            "cases": len(indices),
            **{
                f"complete_top_{count}_accuracy": round(
                    sum(
                        _complete_hit(rankings[index], expected[index], count)
                        for index in indices
                    )
                    / len(indices),
                    6,
                )
                for count in (1, 2, 3, 5)
            },
        }

    by_disposition = {
        disposition: metrics(
            [
                index
                for index, row in enumerate(rows)
                if row["projection"]["disposition"] == disposition
            ]
        )
        for disposition in sorted(
            {str(row["projection"]["disposition"]) for row in rows}
        )
    }
    result = {
        "schema": "baxy.operation-shortlist-mtop-r4-probe.v1",
        "scope": "opened_development_slice_only_mtop_test_remains_sealed",
        "source": source["source"],
        "assets": str(args.assets),
        "all": metrics(list(range(len(rows)))),
        "by_disposition": by_disposition,
        "rows": [
            {
                "source_id": row["source_id"],
                "text": row["text"],
                "disposition": row["projection"]["disposition"],
                "expected": sorted(expected[index]),
                "top_5": rankings[index][:5],
            }
            for index, row in enumerate(rows)
        ],
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=Path, default=DEFAULT_ASSETS)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    args.assets = args.assets.resolve(strict=True)
    args.input = args.input.resolve(strict=True)
    result = probe(args)
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
