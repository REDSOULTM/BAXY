"""Measure the inherited FunctionGemma mMARCO reranker without tuning it.

The previous patch only invoked this component when the primary router returned
no domain tool and the calibrated abstain probability was below 0.85.  This
probe preserves its model, score floor (-3), top-k (3), max length (128) and CPU
execution.  It scores the typed operation descriptions already present in each
sealed Goal 03 candidate list; no threshold is selected from the sealed cut.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
INHERITED = REPO.parent / "Probando Gemma 4"
RERANKER_SOURCE = INHERITED / "gemma4_agent/routing/reranker.py"
CORPUS = REPO / "artifacts/development/goal03_fresh_paraphrase_corpus.v1.jsonl"
CATALOG = REPO / "artifacts/development/catalog_vocabulary_snapshot.json"
DEFAULT_SELECTION = (
    REPO
    / "artifacts/development/goal03_qwen3_8b_iq2_think128_official_sampling_s0_v16.json"
)
DEFAULT_OUTPUT = REPO / "artifacts/development/goal03_inherited_mmarco_reranker_v19.json"
EXPECTED_CORPUS_SHA256 = (
    "761c1bc3b3facbf14a3aaafa09f24c0e5e0baaf8cebdd0edc7c2e648cb87413d"
)
EXPECTED_MODEL_REVISION = "1427fd652930e4ba29e8149678df786c240d8825"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _latency(values: list[float]) -> dict[str, float | int]:
    ordered = sorted(values)
    p90_index = min(len(ordered) - 1, int(0.9 * len(ordered)))
    return {
        "rows": len(ordered),
        "p50": statistics.median(ordered),
        "p90": ordered[p90_index],
        "max": ordered[-1],
        "total": sum(ordered),
    }


def _score_selection(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    positives = [row for row in rows if row["in_catalog"]]
    negatives = [row for row in rows if not row["in_catalog"]]
    return {
        "field": field,
        "in_catalog": {
            "selected_expected": sum(
                bool(set(row[field]) & set(row["expected_operations"]))
                for row in positives
            ),
            "rows": len(positives),
        },
        "out_of_catalog": {
            "honest_abstentions": sum(not row[field] for row in negatives),
            "rows": len(negatives),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection", type=Path, default=DEFAULT_SELECTION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    if _sha256(CORPUS) != EXPECTED_CORPUS_SHA256:
        raise RuntimeError("sealed Goal 03 corpus identity changed")

    cache = (
        Path.home()
        / ".cache/huggingface/hub"
        / "models--cross-encoder--mmarco-mMiniLMv2-L12-H384-v1"
    )
    revision = (cache / "refs/main").read_text(encoding="utf-8").strip()
    if revision != EXPECTED_MODEL_REVISION:
        raise RuntimeError("cached inherited reranker revision changed")
    snapshot = cache / "snapshots" / revision

    # The inherited component claimed CPU latency.  Make that constraint
    # explicit and forbid a network fallback: this exact snapshot is local.
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["GEMMA4_RERANKER"] = "1"
    sys.path.insert(0, str(INHERITED))

    from gemma4_agent.routing import reranker

    model = reranker._load()
    if model is None:
        raise RuntimeError("the inherited mMARCO reranker did not load")
    if reranker._SCORE_FLOOR != -3.0 or reranker._TOP_K != 3:
        raise RuntimeError("inherited reranker policy changed")

    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    descriptions = {
        str(row["name"]): str(row["description"])
        for row in catalog["capabilities"]
    }
    corpus_by_id = {row["case_id"]: row for row in _jsonl(CORPUS)}
    selection = json.loads(args.selection.read_text(encoding="utf-8"))
    if set(corpus_by_id) != {row["case_id"] for row in selection["rows"]}:
        raise RuntimeError("selection and sealed corpus populations differ")

    # Warm the forward path once.  Timings below are steady-state per request,
    # including tokenization and one batch over that request's candidate list.
    model.predict(
        [("warm up", "a typed operation description")],
        show_progress_bar=False,
    )

    latencies: list[float] = []
    rows: list[dict[str, Any]] = []
    for selected in selection["rows"]:
        source = corpus_by_id[selected["case_id"]]
        candidates = list(selected["candidate_operations"])
        missing = [name for name in candidates if name not in descriptions]
        if missing:
            raise RuntimeError(f"catalog descriptions missing for {missing}")
        pairs = [(source["text"], descriptions[name]) for name in candidates]

        started = time.perf_counter()
        raw_scores = model.predict(pairs, show_progress_bar=False)
        elapsed = time.perf_counter() - started
        latencies.append(elapsed)

        ranked = sorted(
            zip(candidates, raw_scores), key=lambda item: -float(item[1])
        )
        passed = [
            name
            for name, score in ranked
            if float(score) >= reranker._SCORE_FLOOR
        ][: reranker._TOP_K]
        top_one = passed[:1]
        expected = set(source["expected_operations"])

        # Faithful old call-site: invoke only when the primary selector has no
        # operation.  Its <0.85 abstain precondition is non-restrictive on the
        # served head measured in V18 (all 160 are <0.43).
        prior = list(selected["selected_operations"])
        empty_rescue = prior if prior else top_one

        rows.append(
            {
                **source,
                "candidate_operations": candidates,
                "prior_selected_operations": prior,
                "ranked_top_5": [
                    [name, float(score)] for name, score in ranked[:5]
                ],
                "passed_floor": passed,
                "reranker_top_1": top_one,
                "expected_in_top_1": bool(expected & set(top_one)),
                "expected_in_top_3": bool(expected & set(passed)),
                "empty_only_rescue": empty_rescue,
                "seconds": elapsed,
            }
        )

    positives = [row for row in rows if row["in_catalog"]]
    negatives = [row for row in rows if not row["in_catalog"]]
    result = {
        "schema": "baxy.goal03-inherited-mmarco-reranker.v1",
        "source": {
            "checkout": str(INHERITED),
            "source_path": str(RERANKER_SOURCE),
            "source_sha256": _sha256(RERANKER_SOURCE),
            "model": "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
            "model_revision": revision,
            "model_weights_sha256": _sha256(snapshot / "model.safetensors"),
            "catalog_sha256": _sha256(CATALOG),
            "selection_sha256": _sha256(args.selection),
            "corpus_sha256": _sha256(CORPUS),
            "policy": {"score_floor": -3.0, "top_k": 3, "max_length": 128},
            "execution": "CPU; cached snapshot; network disabled",
        },
        "population": {
            "rows": len(rows),
            "in_catalog": len(positives),
            "out_of_catalog": len(negatives),
        },
        "intrinsic": {
            "in_catalog_top_1": sum(row["expected_in_top_1"] for row in positives),
            "in_catalog_top_3": sum(row["expected_in_top_3"] for row in positives),
            "in_catalog_any_above_floor": sum(bool(row["passed_floor"]) for row in positives),
            "out_of_catalog_zero_above_floor": sum(not row["passed_floor"] for row in negatives),
        },
        "selection_before": {
            "in_catalog": selection["in_catalog"],
            "out_of_catalog": selection["out_of_catalog"],
        },
        "selection_overlays": [
            _score_selection(rows, "reranker_top_1"),
            _score_selection(rows, "empty_only_rescue"),
        ],
        "steady_state_seconds": _latency(latencies),
        "rows": rows,
    }
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = {key: result[key] for key in (
        "population", "intrinsic", "selection_before", "selection_overlays",
        "steady_state_seconds",
    )}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
