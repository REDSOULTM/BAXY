"""Price the retrieval lever R124 named, using the encoder already installed.

R124 established that comparative *generative* selection does not carry the
paraphrase signal: over the whole catalogue it stopped 2 of 2 leaks and agreed
with only 2 of 17 legitimate single-effect actions, reproducing R116's inversion
from a second vocabulary. It named two remaining levers -- the decisor model, or
retrieval.

The decisor line has no candidate at the certified size: Qwen3.6 publishes no
dense model below 27B, and Qwen3.5-4B was already measured and rejected locally.
So this prices the other one, with the pinned ``intfloat/multilingual-e5-small``
snapshot BAXY already loads in production. Nothing is downloaded.

The question is narrow: does a bi-encoder rank the wanted operation above its
siblings on the very rows where the generative selector chose the sibling, and
does its score separate an out-of-catalogue request from a legitimate one?

Development diagnostic over already-consumed rows. It executes no operation,
drives no turn and promotes nothing.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from baxy_mind import router  # noqa: E402
from scripts.measure_mind_budget import (  # noqa: E402
    DEFAULT_CORE_CANDIDATES,
    current_core_catalog_snapshot,
    discover_core,
    write_json_atomic,
)


DEFAULT_SOURCE = (
    REPO / "artifacts/development/comparative_selector_agreement_20260812.json"
)
DEFAULT_OUTPUT = REPO / "artifacts/development/e5_operation_ranking_20260812.json"


def run(source: Path, output: Path) -> dict[str, Any]:
    import numpy as np
    from sentence_transformers import SentenceTransformer

    snapshot, identity = router._verified_encoder_snapshot()
    model = SentenceTransformer(str(snapshot), device="cpu")

    capabilities, _, _ = current_core_catalog_snapshot(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES))
    )
    names = [str(item["name"]) for item in capabilities]
    # E5 is asymmetric: the request is a query and each operation a passage.
    # Using the wrong prefix silently degrades the space, so both are explicit.
    passages = [
        f"passage: {item['name']} | {str(item['description']).strip()}"
        for item in capabilities
    ]
    catalogue = model.encode(passages, normalize_embeddings=True, batch_size=32)

    rows = json.loads(source.read_text(encoding="utf-8"))["rows"]
    single = [row for row in rows if not row["compound"]]
    embedded = model.encode(
        [f"query: {row['request_text']}" for row in single],
        normalize_embeddings=True,
        batch_size=32,
    )

    measured: list[dict[str, Any]] = []
    ordered_names = np.array(names)
    for row, vector in zip(single, embedded):
        scores = catalogue @ vector
        order = np.argsort(-scores)
        proposed = row["effect_operations"][0]
        rank = int(np.where(ordered_names[order] == proposed)[0][0]) + 1
        measured.append(
            {
                "case_id": row["case_id"],
                "population": row["population"],
                "is_leak": row["is_leak"],
                "request_text": row["request_text"],
                "proposed": proposed,
                "generative_selected": row["selected"],
                "generative_agrees": row["agrees"],
                "e5_top1": names[order[0]],
                "e5_top1_score": round(float(scores[order[0]]), 4),
                "e5_rank_of_proposed": rank,
                "e5_score_of_proposed": round(float(scores[names.index(proposed)]), 4),
                "e5_top5": [
                    [names[index], round(float(scores[index]), 4)]
                    for index in order[:5]
                ],
            }
        )

    report = {
        "schema": "baxy.e5-operation-ranking.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "authority": (
            "development diagnostic over consumed rows; executes nothing and "
            "promotes nothing. Not production retrieval accuracy: production "
            "combines the family classifier, the semantic arbiter and "
            "literal-schema-grounded families over a shortlist, never the "
            "bi-encoder alone over the whole catalogue."
        ),
        "effects_executed": 0,
        "source": str(source.resolve()),
        "summary": _summarise(measured, identity, len(names)),
        "rows": measured,
    }
    write_json_atomic(output, report)
    return report


def _summarise(
    rows: list[dict[str, Any]],
    identity: Any,
    catalogue_operations: int,
) -> dict[str, Any]:
    legitimate = [row for row in rows if not row["is_leak"]]
    leaks = [row for row in rows if row["is_leak"]]
    return {
        "encoder": identity.public_dict(),
        "catalogue_operations": catalogue_operations,
        "legitimate_single_effect": {
            "total": len(legitimate),
            "e5_top1_correct": sum(
                1 for row in legitimate if row["e5_rank_of_proposed"] == 1
            ),
            "e5_top3_correct": sum(
                1 for row in legitimate if row["e5_rank_of_proposed"] <= 3
            ),
            "e5_top5_correct": sum(
                1 for row in legitimate if row["e5_rank_of_proposed"] <= 5
            ),
            "generative_agreed": sum(
                1 for row in legitimate if row["generative_agrees"]
            ),
            "worst_ranks": sorted(
                (
                    {
                        "case_id": row["case_id"],
                        "request_text": row["request_text"],
                        "proposed": row["proposed"],
                        "rank": row["e5_rank_of_proposed"],
                    }
                    for row in legitimate
                ),
                key=lambda entry: -entry["rank"],
            )[:4],
        },
        # The safety question. If an out-of-catalogue request scores higher than
        # the weakest legitimate one, no cosine threshold can separate them.
        "similarity_threshold": {
            "leaks": [
                {
                    "case_id": row["case_id"],
                    "request_text": row["request_text"],
                    "e5_top1": row["e5_top1"],
                    "e5_top1_score": row["e5_top1_score"],
                }
                for row in leaks
            ],
            "minimum_legitimate_score": min(
                (row["e5_score_of_proposed"] for row in legitimate),
                default=None,
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = run(args.source, args.output)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
