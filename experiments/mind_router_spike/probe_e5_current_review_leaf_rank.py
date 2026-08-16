"""Measure resident E5 leaf ranking on the reviewed current catalog.

Development diagnostic only: no blind split is opened and the rank cannot
grant authority.  It tests whether the already-resident encoder can reduce the
native model's sibling-operation search space without adding another model.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT, ROOT / "src", ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from baxy_mind.planner import PlannerCatalog  # noqa: E402
from baxy_mind.router import SemanticEncoder  # noqa: E402
from baxy_mind.__main__ import configure_tools  # noqa: E402
from scripts.measure_mind_budget import (  # noqa: E402
    DEFAULT_CORE_CANDIDATES,
    current_core_capabilities,
    discover_core,
)


CORPUS = (
    ROOT
    / "artifacts"
    / "development"
    / "current_catalog_review_development.v1.jsonl"
)
PRODUCT = (
    ROOT
    / "artifacts"
    / "fixes"
    / "current_catalog_review_product_probe_r3.json"
)


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _accepted_sets(row: dict[str, object]) -> tuple[frozenset[str], ...]:
    return tuple(
        frozenset(str(operation) for operation in operations)
        for operations in row["compatible_terminal_operation_sets"]
    )


def _complete_hit(
    ranking: list[str],
    accepted: tuple[frozenset[str], ...],
    count: int,
) -> bool:
    offered = frozenset(ranking[:count])
    return any(expected <= offered for expected in accepted)


def main() -> int:
    corpus = _read_jsonl(CORPUS)
    product_rows = {
        str(row["case_id"]): row
        for row in json.loads(PRODUCT.read_text(encoding="utf-8"))["rows"]
    }
    capabilities = current_core_capabilities(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES))
    )
    encoder = SemanticEncoder(device="cpu")
    catalog = PlannerCatalog(configure_tools(capabilities), encoder=encoder.encode)
    names = list(catalog._tool_names)  # noqa: SLF001 - experiment introspection
    vectors = np.asarray(catalog._tool_vectors)  # noqa: SLF001
    queries = np.asarray(encoder.encode([str(row["text"]) for row in corpus]))
    scores = queries @ vectors.T
    name_index = {name: index for index, name in enumerate(names)}
    global_rankings = [
        [names[index] for index in np.argsort(-scores[row_index])]
        for row_index in range(len(corpus))
    ]
    candidate_rankings: list[list[str]] = []
    for row_index, row in enumerate(corpus):
        candidates = [
            name
            for name in product_rows[str(row["case_id"])]["candidate_operations"]
            if name in name_index
        ]
        candidates.sort(
            key=lambda name: float(scores[row_index, name_index[name]]),
            reverse=True,
        )
        candidate_rankings.append(candidates)

    identity_rows = [
        index for index, row in enumerate(corpus) if _accepted_sets(row)
    ]
    single_rows = [
        index
        for index in identity_rows
        if any(len(expected) == 1 for expected in _accepted_sets(corpus[index]))
    ]

    def metric(rankings: list[list[str]], rows: list[int], count: int) -> float:
        return sum(
            _complete_hit(rankings[index], _accepted_sets(corpus[index]), count)
            for index in rows
        ) / len(rows)

    result = {
        "schema": "baxy.e5-current-review-leaf-rank-probe.v1",
        "scope": "reviewed_development_only_not_blind",
        "cases": len(corpus),
        "identity_cases": len(identity_rows),
        "single_identity_cases": len(single_rows),
        "global": {
            f"complete_identity_top_{count}": round(
                metric(global_rankings, identity_rows, count),
                6,
            )
            for count in (1, 2, 3, 5)
        },
        "after_product_retrieval": {
            f"complete_identity_top_{count}": round(
                metric(candidate_rankings, identity_rows, count),
                6,
            )
            for count in (1, 2, 3, 5)
        },
        "single_after_product_retrieval": {
            f"identity_top_{count}": round(
                metric(candidate_rankings, single_rows, count),
                6,
            )
            for count in (1, 2, 3, 5)
        },
        "rows": [
            {
                "case_id": row["case_id"],
                "outcome": row["outcome"],
                "expected": [sorted(value) for value in _accepted_sets(row)],
                "global_top_5": global_rankings[index][:5],
                "candidate_top_5": candidate_rankings[index][:5],
            }
            for index, row in enumerate(corpus)
        ],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
