"""Select a family arbiter without consulting the exact-operation dev gate.

The split is deterministic and stratified by leaf operation.  Normalised text
groups are kept wholly on one side, so repeated punctuation/case variants
cannot leak into validation.  This is research evidence only: it executes no
effect and never changes the registered runtime.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import statistics
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.svm import LinearSVC

from selector_common import REPO, read_jsonl, sha256

SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

DEFAULT_CORPUS = REPO / "artifacts" / "research" / "functiongemma_training_corpus.v1.jsonl"
DEFAULT_OUTPUT = REPO / "artifacts" / "research" / "family_arbiter_internal_validation.v1.json"
DEFAULT_CACHE = REPO / "artifacts" / "research" / "family_arbiter_e5.v1.npz"


def _normal(text: str) -> str:
    value = unicodedata.normalize("NFKC", text).casefold()
    return " ".join("".join(c if c.isalnum() else " " for c in value).split())


def _split(rows: list[dict[str, Any]]) -> tuple[list[int], list[int]]:
    by_operation: dict[str, dict[str, list[int]]] = collections.defaultdict(
        lambda: collections.defaultdict(list)
    )
    for index, row in enumerate(rows):
        by_operation[str(row["operation"])][_normal(str(row["text"]))].append(index)
    validation_keys: set[tuple[str, str]] = set()
    for operation, groups in sorted(by_operation.items()):
        ordered = sorted(
            groups,
            key=lambda text: hashlib.sha256(
                f"baxy-family-arbiter-v1\0{operation}\0{text}".encode("utf-8")
            ).digest(),
        )
        count = max(1, round(len(ordered) * 0.2)) if len(ordered) >= 4 else 0
        validation_keys.update((operation, text) for text in ordered[:count])
    fit: list[int] = []
    validation: list[int] = []
    for index, row in enumerate(rows):
        target = validation if (str(row["operation"]), _normal(str(row["text"]))) in validation_keys else fit
        target.append(index)
    return fit, validation


def _lexical(texts: list[str], labels: list[str], c_value: float) -> Pipeline:
    features = FeatureUnion(
        [
            (
                "characters",
                TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=(2, 5),
                    sublinear_tf=True,
                    strip_accents="unicode",
                    max_features=120_000,
                ),
            ),
            (
                "words",
                TfidfVectorizer(
                    analyzer="word",
                    ngram_range=(1, 2),
                    sublinear_tf=True,
                    strip_accents="unicode",
                    max_features=60_000,
                ),
            ),
        ],
        transformer_weights={"characters": 1.0, "words": 1.5},
    )
    return Pipeline(
        [
            ("features", features),
            (
                "classifier",
                LinearSVC(
                    C=c_value,
                    class_weight="balanced",
                    dual="auto",
                    max_iter=20_000,
                    random_state=0,
                ),
            ),
        ]
    ).fit(texts, labels)


def _encode(texts: list[str], corpus: Path, cache: Path) -> np.ndarray:
    corpus_hash = sha256(corpus)
    if cache.is_file():
        with np.load(cache, allow_pickle=False) as saved:
            if str(saved["corpus_sha256"].item()) == corpus_hash and int(saved["rows"].item()) == len(texts):
                return np.asarray(saved["embeddings"], dtype=np.float32)
    from baxy_mind.router import ProcessIntentRouter

    inherited = os.environ.get("PYTHONPATH", "")
    os.environ["PYTHONPATH"] = str(SRC) + (
        os.pathsep + inherited if inherited else ""
    )
    router = ProcessIntentRouter()
    try:
        if not router.try_ready(180.0):
            raise RuntimeError("the attested E5 worker did not become ready")
        chunks = [
            router.encode(texts[start : start + 512], timeout=180.0)
            for start in range(0, len(texts), 512)
        ]
        matrix = np.vstack(chunks).astype(np.float32, copy=False)
    finally:
        router.close()
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        cache,
        embeddings=matrix,
        corpus_sha256=np.asarray(corpus_hash),
        rows=np.asarray(len(texts), dtype=np.int64),
    )
    return matrix


def _row_z(scores: np.ndarray) -> np.ndarray:
    matrix = np.asarray(scores, dtype=np.float64)
    if matrix.ndim == 1:
        matrix = np.column_stack((-matrix, matrix))
    return (matrix - matrix.mean(axis=1, keepdims=True)) / np.maximum(
        matrix.std(axis=1, keepdims=True), 1e-9
    )


def _aligned(model: Any, values: Any, families: list[str]) -> np.ndarray:
    scores = _row_z(model.decision_function(values))
    aligned = np.full((scores.shape[0], len(families)), -10.0, dtype=np.float64)
    for source, family in enumerate(model.classes_):
        aligned[:, families.index(str(family))] = scores[:, source]
    return aligned


def _metrics(scores: np.ndarray, expected: list[str], families: list[str]) -> dict[str, Any]:
    order = np.argsort(scores, axis=1)[:, ::-1]
    predicted = [families[int(index)] for index in order[:, 0]]
    per_family = {
        family: statistics.fmean(
            float(predicted[index] == family)
            for index, value in enumerate(expected)
            if value == family
        )
        for family in sorted(set(expected))
    }
    return {
        "accuracy": round(statistics.fmean(float(a == b) for a, b in zip(expected, predicted, strict=True)), 6),
        "macro_accuracy": round(statistics.fmean(per_family.values()), 6),
        "top2_recall": round(statistics.fmean(float(expected[i] in {families[int(x)] for x in order[i, :2]}) for i in range(len(expected))), 6),
        "top3_recall": round(statistics.fmean(float(expected[i] in {families[int(x)] for x in order[i, :3]}) for i in range(len(expected))), 6),
        "predictions": predicted,
        "per_family": {key: round(value, 6) for key, value in per_family.items()},
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    rows = [row for row in read_jsonl(args.corpus) if str(row.get("operation")) != "__no_action__"]
    fit_indexes, validation_indexes = _split(rows)
    texts = [str(row["text"]) for row in rows]
    labels = [str(row["operation"]).split(".", 1)[0] for row in rows]
    families = sorted(set(labels))
    fit_texts = [texts[index] for index in fit_indexes]
    fit_labels = [labels[index] for index in fit_indexes]
    validation_texts = [texts[index] for index in validation_indexes]
    validation_labels = [labels[index] for index in validation_indexes]

    started = time.perf_counter()
    embeddings = _encode(texts, args.corpus, args.embedding_cache)
    candidates: list[dict[str, Any]] = []
    lexical_scores: dict[float, np.ndarray] = {}
    semantic_scores: dict[float, np.ndarray] = {}
    for c_value in (0.1, 0.3, 1.0, 3.0):
        model = _lexical(fit_texts, fit_labels, c_value)
        lexical_scores[c_value] = _aligned(
            model.named_steps["classifier"],
            model.named_steps["features"].transform(validation_texts),
            families,
        )
        semantic = LinearSVC(
            C=c_value,
            class_weight="balanced",
            dual="auto",
            max_iter=20_000,
            random_state=0,
        ).fit(embeddings[fit_indexes], fit_labels)
        semantic_scores[c_value] = _aligned(semantic, embeddings[validation_indexes], families)

    for lexical_c, lexical_matrix in lexical_scores.items():
        for semantic_c, semantic_matrix in semantic_scores.items():
            for semantic_weight in (0.0, 0.25, 0.5, 0.75, 1.0):
                scores = (1.0 - semantic_weight) * lexical_matrix + semantic_weight * semantic_matrix
                measured = _metrics(scores, validation_labels, families)
                candidates.append(
                    {
                        "lexical_c": lexical_c,
                        "semantic_c": semantic_c,
                        "semantic_weight": semantic_weight,
                        **{key: value for key, value in measured.items() if key not in {"predictions", "per_family"}},
                    }
                )
    selected = max(
        candidates,
        key=lambda row: (
            float(row["accuracy"]),
            float(row["macro_accuracy"]),
            float(row["top2_recall"]),
            -abs(float(row["semantic_weight"]) - 0.5),
        ),
    )
    selected_scores = (
        (1.0 - float(selected["semantic_weight"])) * lexical_scores[float(selected["lexical_c"])]
        + float(selected["semantic_weight"]) * semantic_scores[float(selected["semantic_c"])]
    )
    selected_metrics = _metrics(selected_scores, validation_labels, families)
    report = {
        "schema": "baxy.family-arbiter-internal-validation.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "candidate selection on operation-stratified internal validation; exact-operation dev gate not loaded",
        "corpus": str(args.corpus),
        "corpus_sha256": sha256(args.corpus),
        "rows": len(rows),
        "fit_rows": len(fit_indexes),
        "validation_rows": len(validation_indexes),
        "normalised_text_overlap": len({_normal(texts[i]) for i in fit_indexes} & {_normal(texts[i]) for i in validation_indexes}),
        "families": families,
        "selected": selected,
        "selected_metrics": selected_metrics,
        "candidate_count": len(candidates),
        "candidates": sorted(candidates, key=lambda row: (row["accuracy"], row["macro_accuracy"]), reverse=True),
        "seconds": round(time.perf_counter() - started, 6),
        "effects_executed": 0,
        "runtime_manifest_changed": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key not in {"candidates", "selected_metrics"}}, ensure_ascii=False, indent=2, sort_keys=True))
    print(json.dumps(report["selected_metrics"] | {"selected": selected}, ensure_ascii=False, indent=2, sort_keys=True))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--embedding-cache", type=Path, default=DEFAULT_CACHE)
    run(parser.parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
