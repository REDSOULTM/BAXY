"""Evaluate the inherited frozen operation ranker on the fixed Goal 03 cut."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from scipy.sparse import hstack

from experiments.mind_router_spike.probe_operation_shortlist_current_review import (
    NO_ACTION,
    _resources,
)

REPO = Path(__file__).resolve().parents[2]
CORPUS = REPO / "artifacts/development/goal03_fresh_paraphrase_corpus.v1.jsonl"
DEFAULT_ASSETS = REPO / "artifacts/research/operation_shortlist_v3"
DEFAULT_OUTPUT = REPO / "artifacts/development/goal03_frozen_operation_ranker_v1.json"
E5_TELEMETRY = REPO / "artifacts/development/goal03_resume_baseline_20260820.telemetry.jsonl"


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_lf(path: Path, value: dict[str, Any]) -> None:
    serialized = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(serialized)


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=Path, default=DEFAULT_ASSETS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    assets = args.assets.resolve(strict=True)
    corpus = _jsonl(CORPUS)
    e5_rows = {str(row["case_id"]): row for row in _jsonl(E5_TELEMETRY)}
    words, characters, classes, coefficients, intercept = _resources(assets)
    features = hstack(
        (
            words.transform([str(row["text"]) for row in corpus]),
            characters.transform([str(row["text"]) for row in corpus]),
        ),
        format="csr",
    )
    scores = np.asarray(features @ coefficients.T + intercept)
    rankings = [
        [classes[index] for index in np.argsort(-scores[row_index])]
        for row_index in range(len(corpus))
    ]
    rows: list[dict[str, Any]] = []
    for source, ranking in zip(corpus, rankings, strict=True):
        expected = set(str(value) for value in source.get("expected_operations") or [])
        e5_ranking = list(
            e5_rows[str(source["case_id"])].get("candidate_operations") or []
        )
        rows.append(
            {
                "case_id": source["case_id"],
                "in_catalog": bool(source["in_catalog"]),
                "expected_operations": sorted(expected),
                "top_28": ranking[:28],
                "e5_top_28": e5_ranking[:28],
                "expected_rank": min(
                    (ranking.index(value) + 1 for value in expected if value in ranking),
                    default=None,
                ),
                "no_action_rank": ranking.index(NO_ACTION) + 1,
            }
        )
    in_rows = [row for row in rows if row["in_catalog"]]
    out_rows = [row for row in rows if not row["in_catalog"]]
    result = {
        "schema": "baxy.goal03-frozen-operation-ranker.v1",
        "corpus": {"path": str(CORPUS.relative_to(REPO)), "sha256": _sha256(CORPUS)},
        "assets": {
            "path": _display_path(assets),
            "manifest_sha256": _sha256(assets / "operation_shortlist.v1.manifest.json"),
            "vocabulary_sha256": _sha256(assets / "operation_shortlist.v1.vocabulary.json.gz"),
            "weights_sha256": _sha256(assets / "operation_shortlist.v1.weights.npz"),
        },
        "e5_telemetry": {
            "path": str(E5_TELEMETRY.relative_to(REPO)),
            "sha256": _sha256(E5_TELEMETRY),
        },
        "in_catalog": {
            "rows": len(in_rows),
            **{
                f"expected_top_{count}": sum(
                    row["expected_rank"] is not None and row["expected_rank"] <= count
                    for row in in_rows
                )
                for count in (1, 2, 3, 5, 8, 12, 28)
            },
            "symmetric_union": {
                f"expected_in_top_{count * 2}": sum(
                    bool(
                        set(row["expected_operations"])
                        & (
                            set(row["top_28"][:count])
                            | set(row["e5_top_28"][:count])
                        )
                    )
                    for row in in_rows
                )
                for count in (1, 2, 3, 4, 5, 8, 10, 12, 14)
            },
        },
        "out_of_catalog": {
            "rows": len(out_rows),
            "no_action_top_1": sum(row["no_action_rank"] == 1 for row in out_rows),
            "no_action_top_3": sum(row["no_action_rank"] <= 3 for row in out_rows),
        },
        "rows": rows,
    }
    _write_lf(args.output, result)
    print(json.dumps({"in_catalog": result["in_catalog"], "out_of_catalog": result["out_of_catalog"]}, indent=2))
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
