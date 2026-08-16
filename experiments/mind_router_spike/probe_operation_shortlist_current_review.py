"""Measure the lightweight operation ranker on the current review corpus.

This is a development-only diagnostic.  It does not promote assets, open any
blind holdout, or grant operation authority.  The product R3 rows are used
only to measure ranking after the real retrieval boundary.
"""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

import numpy as np
from scipy.sparse import hstack
from sklearn.feature_extraction.text import TfidfVectorizer


ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "artifacts" / "research" / "operation_shortlist_v1"
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
NO_ACTION = "__none__"


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _resources(
    assets: Path,
) -> tuple[object, object, tuple[str, ...], np.ndarray, np.ndarray]:
    with gzip.open(
        assets / "operation_shortlist.v1.vocabulary.json.gz",
        "rt",
        encoding="utf-8",
    ) as handle:
        vocabulary = json.load(handle)
    words = TfidfVectorizer(
        analyzer="word",
        ngram_range=tuple(vocabulary["word_ngram_range"]),
        vocabulary=vocabulary["word_vocabulary"],
        sublinear_tf=True,
        strip_accents="unicode",
    )
    characters = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=tuple(vocabulary["character_ngram_range"]),
        vocabulary=vocabulary["character_vocabulary"],
        sublinear_tf=True,
        strip_accents="unicode",
    )
    words.fit(["baxy operation ranker bootstrap"])
    characters.fit(["baxy operation ranker bootstrap"])
    with np.load(
        assets / "operation_shortlist.v1.weights.npz",
        allow_pickle=False,
    ) as arrays:
        words.idf_ = np.asarray(arrays["word_idf"], dtype=np.float64)
        characters.idf_ = np.asarray(arrays["character_idf"], dtype=np.float64)
        coefficients = np.asarray(arrays["coefficients"], dtype=np.float64)
        intercept = np.asarray(arrays["intercept"], dtype=np.float64)
    return (
        words,
        characters,
        tuple(str(value) for value in vocabulary["classes"]),
        coefficients,
        intercept,
    )


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


def probe(args: argparse.Namespace) -> dict[str, object]:
    source_corpus = _read_jsonl(args.corpus)
    product_rows = {
        str(row["case_id"]): row
        for row in json.loads(args.product.read_text(encoding="utf-8"))["rows"]
    }
    corpus = [
        row
        for row in source_corpus
        if str(row["case_id"]) in product_rows
    ]
    if not corpus:
        raise ValueError("the corpus and product report have no matching cases")
    words, characters, classes, coefficients, intercept = _resources(args.assets)
    texts = [str(row["text"]) for row in corpus]
    features = hstack(
        (words.transform(texts), characters.transform(texts)),
        format="csr",
    )
    scores = np.asarray(features @ coefficients.T + intercept)
    class_index = {operation: index for index, operation in enumerate(classes)}

    identity_rows = [
        index
        for index, row in enumerate(corpus)
        if _accepted_sets(row)
    ]
    no_action_rows = [
        index
        for index, row in enumerate(corpus)
        if not _accepted_sets(row)
    ]
    global_rankings = [
        [classes[index] for index in np.argsort(-scores[row_index])]
        for row_index in range(len(corpus))
    ]
    conditional_global_rankings = [
        [operation for operation in ranking if operation != NO_ACTION]
        for ranking in global_rankings
    ]
    candidate_rankings: list[list[str]] = []
    for row_index, row in enumerate(corpus):
        candidates = list(
            dict.fromkeys(
                [NO_ACTION]
                + list(product_rows[str(row["case_id"])]["candidate_operations"])
            )
        )
        candidates = [value for value in candidates if value in class_index]
        candidates.sort(
            key=lambda value: float(scores[row_index, class_index[value]]),
            reverse=True,
        )
        candidate_rankings.append(candidates)
    conditional_candidate_rankings = [
        [operation for operation in ranking if operation != NO_ACTION]
        for ranking in candidate_rankings
    ]
    oracle_family_rankings: list[list[str]] = []
    for index, row in enumerate(corpus):
        accepted = _accepted_sets(row)
        families = {
            operation.split(".", 1)[0]
            for operations in accepted
            for operation in operations
        }
        oracle_family_rankings.append(
            [
                operation
                for operation in conditional_candidate_rankings[index]
                if operation.split(".", 1)[0] in families
            ]
        )

    def identity_metric(rankings: list[list[str]], count: int) -> float:
        return sum(
            _complete_hit(rankings[index], _accepted_sets(corpus[index]), count)
            for index in identity_rows
        ) / len(identity_rows)

    result = {
        "schema": "baxy.operation-shortlist-current-review-probe.v1",
        "scope": "reviewed_development_only_not_blind",
        "cases": len(corpus),
        "source_cases": len(source_corpus),
        "unmatched_source_cases": len(source_corpus) - len(corpus),
        "identity_cases": len(identity_rows),
        "no_action_cases": len(no_action_rows),
        "global": {
            f"complete_identity_top_{count}": round(
                identity_metric(global_rankings, count),
                6,
            )
            for count in (1, 2, 3, 5, 8, 10, 12)
        },
        "conditional_global_known_effect": {
            f"complete_identity_top_{count}": round(
                identity_metric(conditional_global_rankings, count),
                6,
            )
            for count in (1, 2, 3, 5, 8, 10, 12)
        },
        "after_product_retrieval": {
            f"complete_identity_top_{count}": round(
                identity_metric(candidate_rankings, count),
                6,
            )
            for count in (1, 2, 3, 5, 8, 10, 12)
        },
        "conditional_after_product_retrieval": {
            f"complete_identity_top_{count}": round(
                identity_metric(conditional_candidate_rankings, count),
                6,
            )
            for count in (1, 2, 3, 5, 8, 10, 12)
        },
        "oracle_family_after_product_retrieval": {
            f"complete_identity_top_{count}": round(
                identity_metric(oracle_family_rankings, count),
                6,
            )
            for count in (1, 2, 3, 5, 8, 10, 12)
        },
        "no_action_top_1": (
            round(
                sum(
                    global_rankings[index][0] == NO_ACTION
                    for index in no_action_rows
                )
                / len(no_action_rows),
                6,
            )
            if no_action_rows
            else None
        ),
        "rows": [
            {
                "case_id": row["case_id"],
                "outcome": row["outcome"],
                "expected": [sorted(value) for value in _accepted_sets(row)],
                "global_top_5": global_rankings[index][:5],
                "global_top_12": global_rankings[index][:12],
                "global_top_5_scores": [
                    round(float(scores[index, class_index[operation]]), 6)
                    for operation in global_rankings[index][:5]
                ],
                "global_margin": round(
                    float(
                        scores[index, class_index[global_rankings[index][0]]]
                        - scores[index, class_index[global_rankings[index][1]]]
                    ),
                    6,
                ),
                "candidate_top_5": candidate_rankings[index][:5],
                "conditional_candidate_top_5": (
                    conditional_candidate_rankings[index][:5]
                ),
            }
            for index, row in enumerate(corpus)
        ],
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=Path, default=ASSETS)
    parser.add_argument("--corpus", type=Path, default=CORPUS)
    parser.add_argument("--product", type=Path, default=PRODUCT)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    args.assets = args.assets.resolve(strict=True)
    args.corpus = args.corpus.resolve(strict=True)
    args.product = args.product.resolve(strict=True)
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
