from __future__ import annotations

import json
from pathlib import Path

from baxy_mind.operation_ranker import NO_ACTION, OperationRanker
from baxy_mind.planner import UNION_PER_SIGNAL


FROZEN = Path("artifacts/development/goal03_frozen_operation_ranker_v1.json")
CORPUS = Path("artifacts/development/goal03_fresh_paraphrase_corpus.v1.jsonl")


def test_ranker_assets_match_the_inherited_v3_sello() -> None:
    ranker = OperationRanker()
    ranking = ranker.rank("open calculator")
    assert ranking
    assert NO_ACTION not in ranking
    assert "app.open" in ranking[:14]


def test_symmetric_union_still_offers_119_expected_leaves() -> None:
    frozen = json.loads(FROZEN.read_text(encoding="utf-8"))
    ranker = OperationRanker()
    texts = {
        json.loads(line)["case_id"]: json.loads(line)["text"]
        for line in CORPUS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    hits = 0
    in_catalog = 0
    for row in frozen["rows"]:
        if not row["in_catalog"]:
            continue
        in_catalog += 1
        live = [
            name
            for name in ranker.rank(texts[row["case_id"]])
            if name != NO_ACTION
        ]
        merged = list(
            dict.fromkeys(live[:UNION_PER_SIGNAL] + list(row["e5_top_28"][:UNION_PER_SIGNAL]))
        )
        if set(row["expected_operations"]) & set(merged):
            hits += 1
    assert in_catalog == 124
    assert hits == 119
