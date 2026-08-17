"""Goal 03: specific leaves or parametric tools — which one is found?

The identity fixes the objective and its order: coverage must not drop, and with
coverage intact the smaller number wins. What it leaves to measurement is the
**form**: 157 specific leaves (``audio.volume``, ``audio.volume.adjust``,
``audio.mute``…) against one parametric tool per family
(``audio.control(action, …)``).

This program measures only the half that can be measured without rebuilding the
core: **can retrieval put the right thing in front of the decider?** Coverage is
held constant by construction — the parametric catalogue is the same 157
operations grouped, not a smaller set of capabilities, and every leaf stays
reachable as an ``action`` value.

Offline: one E5 encode per catalogue form, no model server, no effect.
"""

from __future__ import annotations

import argparse
import collections
import json
import statistics
import sys
from pathlib import Path
from typing import Any

import numpy as np

REPO = Path(__file__).resolve().parents[2]
for import_root in (REPO, REPO / "src"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from baxy_mind.router import MODEL_NAME, MODEL_REVISION  # noqa: E402
from experiments.mind_router_spike.compare_goal03_retrieval import (  # noqa: E402
    _compact_schema_hint,
    load_catalog,
    load_corpus,
)

SCHEMA = "baxy.goal03-catalog-form.v1"
CORPUS = REPO / "artifacts" / "development" / "goal03_fresh_paraphrase_corpus.v1.jsonl"
RESULT = REPO / "artifacts" / "development" / "goal03_catalog_form.json"


def _family(name: str) -> str:
    return name.split(".", 1)[0]


def _specific_documents(catalog: list[dict[str, Any]]) -> list[tuple[str, str]]:
    return [
        (
            capability["name"],
            f"{capability['name']}. {capability['description']}. "
            f"{_compact_schema_hint(capability['argumentsSchema'])}",
        )
        for capability in catalog
    ]


def _parametric_documents(catalog: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """One tool per family; every leaf survives as an ``action`` value."""

    grouped: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for capability in catalog:
        grouped[_family(capability["name"])].append(capability)
    documents: list[tuple[str, str]] = []
    for family, members in sorted(grouped.items()):
        actions = ", ".join(
            sorted(member["name"].split(".", 1)[1] for member in members)
        )
        purpose = " ".join(member["description"] for member in members)
        documents.append(
            (family, f"{family}. acciones: {actions}. {purpose}")
        )
    return documents


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


def _measure(
    model: Any,
    documents: list[tuple[str, str]],
    corpus: list[dict[str, Any]],
    *,
    target_of: Any,
    prefix: str,
) -> dict[str, Any]:
    names = [name for name, _ in documents]
    vectors = _encode(model, [text for _, text in documents], prefix)
    queries = [row["text"] for row in corpus]
    similarity = _encode(model, queries, "query: ") @ vectors.T

    in_catalog = [row for row in corpus if row["in_catalog"]]
    recall = {1: 0, 3: 0, 5: 0, 8: 0, 28: 0}
    ranks: list[int] = []
    unreachable: list[str] = []
    for index, row in enumerate(corpus):
        if not row["in_catalog"]:
            continue
        order = np.argsort(-similarity[index])
        ranked = [names[position] for position in order]
        targets = target_of(row)
        best = min(
            (ranked.index(target) for target in targets if target in ranked),
            default=len(ranked),
        )
        ranks.append(best + 1)
        for cut in recall:
            recall[cut] += best < cut
        if best >= len(ranked):
            unreachable.append(row["case_id"])

    out_top = [
        float(similarity[index].max())
        for index, row in enumerate(corpus)
        if not row["in_catalog"]
    ]
    in_top = [
        float(similarity[index].max())
        for index, row in enumerate(corpus)
        if row["in_catalog"]
    ]
    return {
        "entries": len(documents),
        "rows": len(in_catalog),
        "recall_at": {
            str(cut): round(value / max(len(in_catalog), 1), 4)
            for cut, value in recall.items()
        },
        "median_rank": statistics.median(ranks) if ranks else None,
        "mean_rank": round(statistics.mean(ranks), 2) if ranks else None,
        "unreachable_rows": unreachable,
        "top_score": {
            "in_catalog_median": round(statistics.median(in_top), 4),
            "out_of_catalog_median": round(statistics.median(out_top), 4),
            "separation": round(
                statistics.median(in_top) - statistics.median(out_top), 4
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Goal 03 catalogue form comparison")
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
        "coverage_operations": len(catalog),
        "specific": _measure(
            model,
            _specific_documents(catalog),
            corpus,
            target_of=lambda row: set(row["expected_operations"]),
            prefix="passage: ",
        ),
        "parametric": _measure(
            model,
            _parametric_documents(catalog),
            corpus,
            target_of=lambda row: {
                _family(name) for name in row["expected_operations"]
            },
            prefix="passage: ",
        ),
    }
    Path(arguments.output).write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    for form in ("specific", "parametric"):
        value = report[form]
        print(
            f"{form:12s} entries={value['entries']:3d} "
            f"r@1={value['recall_at']['1']:.3f} r@3={value['recall_at']['3']:.3f} "
            f"r@5={value['recall_at']['5']:.3f} r@8={value['recall_at']['8']:.3f} "
            f"medrank={value['median_rank']} meanrank={value['mean_rank']} "
            f"sep={value['top_score']['separation']:+.4f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
