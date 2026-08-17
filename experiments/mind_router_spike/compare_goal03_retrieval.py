"""Goal 03: which operation-level retriever offers the right leaf, and abstains?

Offline. No model server, no provider, no effect. It encodes the authenticated
catalogue once per variant with the pinned E5 snapshot already in production and
scores the fresh paraphrase corpus.

Four variants, each one change from the last:

``A_current``
    what ships today: document = ``name. description. schema hint`` and the
    E5 ``query:`` prefix on **both** sides.
``B_passage``
    the same documents with the ``passage:`` prefix E5 was trained to pair with
    ``query:``. Asymmetric retrieval is the whole point of that model.
``C_intent_document``
    the document becomes what a user would say: the operation's leaf words and
    the head of its description, with the verification clause dropped. Every
    description in this catalogue ends in the same receipt prose, and identical
    tails are what collapse the cosine range.
``D_floor``
    C plus a relative score floor and a top-k cap, so a request that matches
    nothing arrives with zero candidates instead of twenty-eight.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path
from typing import Any, Callable

import numpy as np

REPO = Path(__file__).resolve().parents[2]
for import_root in (REPO, REPO / "src"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from baxy_mind.router import MODEL_NAME, MODEL_REVISION  # noqa: E402

SCHEMA = "baxy.goal03-retrieval-comparison.v1"
CORPUS = REPO / "artifacts" / "development" / "goal03_fresh_paraphrase_corpus.v1.jsonl"
RESULT = REPO / "artifacts" / "development" / "goal03_retrieval_comparison.json"

# Every description in this catalogue closes with how the effect is verified.
# That clause is identical across families and is not something a user says.
_VERIFICATION_TAIL = re.compile(
    r"\s*(?:,\s*)?\b(?:y\s+)?"
    r"(?:verifica|corrobora|comprueba|exige|devuelve|emite|sin\s+exponer"
    r"|sin\s+modificar|y\s+solo\s+devuelve|conserva)\b.*$",
    re.IGNORECASE | re.DOTALL,
)
_EXCLUDED_PREFIXES = ("memory.",)
_EXCLUDED_NAMES = {"app.status"}


def _leaf_words(name: str) -> str:
    return " ".join(part for part in name.split(".") if part)


def _intent_document(name: str, description: str) -> str:
    head = _VERIFICATION_TAIL.sub("", description).strip(" .;,")
    if len(head) < 12:
        head = description
    return f"{_leaf_words(name)}. {head}"


def _compact_schema_hint(schema: dict[str, Any]) -> str:
    properties = schema.get("properties")
    if not isinstance(properties, dict) or not properties:
        return "sin argumentos"
    return ", ".join(sorted(properties))


def load_catalog(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [
        capability
        for capability in payload["capabilities"]
        if capability["name"] not in _EXCLUDED_NAMES
        and not capability["name"].startswith(_EXCLUDED_PREFIXES)
    ]


def load_corpus(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


Variant = tuple[str, Callable[[dict[str, Any]], str], str, dict[str, float]]

VARIANTS: tuple[Variant, ...] = (
    (
        "A_current",
        lambda c: (
            f"{c['name']}. {c['description']}. "
            f"{_compact_schema_hint(c['argumentsSchema'])}"
        ),
        "query: ",
        {},
    ),
    (
        "B_passage",
        lambda c: (
            f"{c['name']}. {c['description']}. "
            f"{_compact_schema_hint(c['argumentsSchema'])}"
        ),
        "passage: ",
        {},
    ),
    (
        "C_intent_document",
        lambda c: _intent_document(c["name"], c["description"]),
        "passage: ",
        {},
    ),
    (
        "D_floor",
        lambda c: _intent_document(c["name"], c["description"]),
        "passage: ",
        {"relative_floor": 0.92, "top_k": 8},
    ),
)


def _encode(model: Any, texts: list[str], prefix: str) -> np.ndarray:
    return np.asarray(
        model.encode(
            [prefix + text for text in texts],
            normalize_embeddings=True,
            show_progress_bar=False,
            batch_size=64,
        ),
        dtype=np.float32,
    )


def _shortlist(
    scores: np.ndarray,
    names: list[str],
    policy: dict[str, float],
) -> list[str]:
    order = np.argsort(-scores)
    if not policy:
        return [names[index] for index in order[:28]]
    top_k = int(policy["top_k"])
    floor = float(policy["relative_floor"]) * float(scores[order[0]])
    return [
        names[index] for index in order[:top_k] if float(scores[index]) >= floor
    ]


def evaluate(
    model: Any,
    catalog: list[dict[str, Any]],
    corpus: list[dict[str, Any]],
) -> dict[str, Any]:
    names = [capability["name"] for capability in catalog]
    queries = [row["text"] for row in corpus]
    query_vectors = _encode(model, queries, "query: ")
    in_catalog = [row for row in corpus if row["in_catalog"]]
    out_catalog = [row for row in corpus if not row["in_catalog"]]

    report: dict[str, Any] = {}
    for label, document_of, prefix, policy in VARIANTS:
        documents = [document_of(capability) for capability in catalog]
        document_vectors = _encode(model, documents, prefix)
        similarity = query_vectors @ document_vectors.T

        ranks: list[int] = []
        recall = {1: 0, 3: 0, 5: 0, 8: 0, 28: 0}
        shortlist_sizes: list[int] = []
        offered = 0
        misses: list[dict[str, Any]] = []
        for index, row in enumerate(corpus):
            if not row["in_catalog"]:
                continue
            scores = similarity[index]
            order = np.argsort(-scores)
            ranked = [names[position] for position in order]
            expected = set(row["expected_operations"])
            best = min(
                (ranked.index(name) for name in expected if name in ranked),
                default=len(ranked),
            )
            ranks.append(best + 1)
            for cut in recall:
                recall[cut] += best < cut
            shortlist = _shortlist(scores, names, policy)
            shortlist_sizes.append(len(shortlist))
            hit = bool(expected & set(shortlist))
            offered += hit
            if not hit:
                misses.append(
                    {
                        "case_id": row["case_id"],
                        "expected": sorted(expected),
                        "rank": best + 1,
                        "offered": shortlist[:6],
                    }
                )

        out_sizes: list[int] = []
        out_margins: list[float] = []
        for index, row in enumerate(corpus):
            if row["in_catalog"]:
                continue
            scores = similarity[index]
            out_sizes.append(len(_shortlist(scores, names, policy)))
            order = np.argsort(-scores)
            out_margins.append(float(scores[order[0]]))

        in_margins = [
            float(similarity[index].max())
            for index, row in enumerate(corpus)
            if row["in_catalog"]
        ]

        report[label] = {
            "prefix": prefix,
            "policy": policy,
            "in_catalog": {
                "rows": len(in_catalog),
                "offered_expected": offered,
                "rate": round(offered / max(len(in_catalog), 1), 4),
                "recall_at": {
                    str(cut): round(value / max(len(in_catalog), 1), 4)
                    for cut, value in recall.items()
                },
                "median_rank": statistics.median(ranks) if ranks else None,
                "mean_shortlist": round(statistics.mean(shortlist_sizes), 2),
            },
            "out_of_catalog": {
                "rows": len(out_catalog),
                "zero_candidate_rows": sum(1 for size in out_sizes if size == 0),
                "mean_shortlist": round(statistics.mean(out_sizes), 2)
                if out_sizes
                else 0.0,
                "max_shortlist": max(out_sizes, default=0),
            },
            "top_score": {
                "in_catalog_median": round(statistics.median(in_margins), 4),
                "out_of_catalog_median": round(statistics.median(out_margins), 4),
                "separation": round(
                    statistics.median(in_margins) - statistics.median(out_margins), 4
                ),
            },
            "misses": misses[:25],
        }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Goal 03 retrieval comparison")
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--corpus", default=str(CORPUS))
    parser.add_argument("--output", default=str(RESULT))
    arguments = parser.parse_args()

    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(
        MODEL_NAME,
        device="cpu",
        revision=MODEL_REVISION,
        local_files_only=True,
    )
    catalog = load_catalog(Path(arguments.catalog))
    corpus = load_corpus(Path(arguments.corpus))
    report = {
        "schema": SCHEMA,
        "encoder": {"model": MODEL_NAME, "revision": MODEL_REVISION},
        "catalog_operations": len(catalog),
        "corpus_rows": len(corpus),
        "variants": evaluate(model, catalog, corpus),
    }
    Path(arguments.output).write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    for label, value in report["variants"].items():
        print(
            f"{label:20s} offered={value['in_catalog']['rate']:.3f} "
            f"r@1={value['in_catalog']['recall_at']['1']:.3f} "
            f"r@5={value['in_catalog']['recall_at']['5']:.3f} "
            f"r@8={value['in_catalog']['recall_at']['8']:.3f} "
            f"medrank={value['in_catalog']['median_rank']} "
            f"ooc_zero={value['out_of_catalog']['zero_candidate_rows']}"
            f"/{value['out_of_catalog']['rows']} "
            f"sep={value['top_score']['separation']:+.4f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
