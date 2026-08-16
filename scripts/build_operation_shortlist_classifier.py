"""Build the safe advisory operation-shortlist classifier assets.

The classifier is trained only on MTOP ``train`` plus the reviewed
FunctionGemma corpus.  MTOP ``validation`` is used as a development promotion
check; official MTOP ``test`` is never opened.  The resulting rank cannot grant
operation authority: it only orders authenticated catalog candidates for the
native turn contract.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sys
import tempfile
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for path in (ROOT, SRC, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import numpy as np  # noqa: E402
from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: E402
from sklearn.pipeline import FeatureUnion  # noqa: E402
from sklearn.svm import LinearSVC  # noqa: E402

import measure_turn_policy_v52_mtop_validation as mtop  # noqa: E402
from baxy_mind.planner import required_predecessors  # noqa: E402
from scripts.measure_mind_budget import write_json_atomic  # noqa: E402


DATA = ROOT / "artifacts" / "research" / "operation_shortlist_v1"
VOCABULARY = DATA / "operation_shortlist.v1.vocabulary.json.gz"
WEIGHTS = DATA / "operation_shortlist.v1.weights.npz"
MANIFEST = DATA / "operation_shortlist.v1.manifest.json"
FUNCTIONGEMMA = (
    ROOT / "artifacts" / "research" / "functiongemma_training_corpus.v1.jsonl"
)
EXACT_DEVELOPMENT = (
    ROOT
    / "experiments"
    / "mind_router_spike"
    / "data"
    / "exact_operation_development.v1.jsonl"
)
EXPECTED_FUNCTIONGEMMA_SHA256 = (
    "b27e871a49aacd0f1e527235422547a21ceb0fabcb01505a4f687ad3ed51ba18"
)
NO_ACTION = "__none__"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normal_key(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    folded = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    return " ".join(folded.split())


def _terminal_operations(operations: Iterable[str]) -> tuple[str, ...]:
    ordered = tuple(dict.fromkeys(operations))
    technical = {
        predecessor
        for operation in ordered
        for predecessor in required_predecessors(operation)
        if predecessor in ordered
    }
    return tuple(operation for operation in ordered if operation not in technical)


def _mtop_label(row: dict[str, Any]) -> str | None:
    projection = row["projection"]
    if projection["reason"] == "contract_structure_mismatch":
        return None
    if projection["disposition"] not in {
        "candidate",
        "candidate_missing_information",
    }:
        return NO_ACTION
    terminal = _terminal_operations(projection["candidate_operations"])
    return terminal[0] if len(terminal) == 1 else None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _deduplicate_training(
    records: Iterable[tuple[str, str, str]],
    excluded_keys: set[str],
) -> tuple[list[tuple[str, str]], dict[str, int]]:
    labels_by_key: dict[str, set[str]] = defaultdict(set)
    first_by_key: dict[str, tuple[str, str]] = {}
    excluded_overlap = 0
    for text, label, _source in records:
        key = _normal_key(text)
        if not key or key in excluded_keys:
            excluded_overlap += int(key in excluded_keys)
            continue
        labels_by_key[key].add(label)
        first_by_key.setdefault(key, (text, label))
    conflicts = {key for key, labels in labels_by_key.items() if len(labels) != 1}
    rows = [
        first_by_key[key]
        for key in sorted(first_by_key)
        if key not in conflicts
    ]
    return rows, {
        "normalised_overlap_excluded": excluded_overlap,
        "conflicting_normalised_texts_excluded": len(conflicts),
    }


def _top_k_accuracy(
    classifier: LinearSVC,
    scores: np.ndarray,
    expected: list[str],
    count: int,
) -> float:
    order = np.argsort(-scores, axis=1)[:, :count]
    classes = np.asarray(classifier.classes_, dtype=object)
    return float(
        np.mean(
            [
                label in classes[order[index]]
                for index, label in enumerate(expected)
            ]
        )
    )


def _write_gzip_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=path.parent,
    )
    try:
        with os.fdopen(descriptor, "wb") as raw:
            with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as compressed:
                compressed.write(
                    (
                        json.dumps(
                            payload,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                        + "\n"
                    ).encode("utf-8")
                )
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def _write_npz_atomic(path: Path, **arrays: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".npz",
        dir=path.parent,
    )
    os.close(descriptor)
    try:
        np.savez_compressed(temporary_name, **arrays)
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def build(
    *,
    functiongemma: Path = FUNCTIONGEMMA,
    output_directory: Path = DATA,
    expected_functiongemma_sha256: str = EXPECTED_FUNCTIONGEMMA_SHA256,
    excluded_corpora: Iterable[Path] = (EXACT_DEVELOPMENT,),
) -> dict[str, Any]:
    functiongemma = functiongemma.resolve(strict=True)
    output_directory = output_directory.resolve()
    excluded_corpora = tuple(path.resolve(strict=True) for path in excluded_corpora)
    functiongemma_sha256 = _sha256(functiongemma)
    if functiongemma_sha256 != expected_functiongemma_sha256:
        raise RuntimeError("the reviewed FunctionGemma corpus identity changed")
    mtop_rows, mtop_manifest, identity = mtop._load_development(
        mtop.DEVELOPMENT_CORPUS,
        mtop.MANIFEST,
    )
    excluded_keys = {
        _normal_key(str(row["text"]))
        for path in excluded_corpora
        for row in _read_jsonl(path)
    }
    function_rows = _read_jsonl(functiongemma)

    training_records: list[tuple[str, str, str]] = []
    for row in mtop_rows:
        label = _mtop_label(row)
        if row["split"] == "train" and label is not None:
            training_records.append((str(row["text"]), label, "mtop-train"))
    for row in function_rows:
        operation = str(row["operation"])
        training_records.append(
            (
                str(row["text"]),
                NO_ACTION if operation == "__no_action__" else operation,
                "functiongemma-reviewed",
            )
        )
    training, exclusions = _deduplicate_training(training_records, excluded_keys)
    texts = [text for text, _label in training]
    labels = [label for _text, label in training]
    features = FeatureUnion(
        [
            (
                "words",
                TfidfVectorizer(
                    ngram_range=(1, 2),
                    min_df=2,
                    max_features=150_000,
                    sublinear_tf=True,
                    strip_accents="unicode",
                    dtype=np.float32,
                ),
            ),
            (
                "characters",
                TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=(3, 5),
                    min_df=2,
                    max_features=220_000,
                    sublinear_tf=True,
                    strip_accents="unicode",
                    dtype=np.float32,
                ),
            ),
        ]
    )
    matrix = features.fit_transform(texts)
    classifier = LinearSVC(
        C=0.5,
        dual="auto",
        max_iter=10_000,
        random_state=0,
    ).fit(matrix, labels)

    validation = [
        row
        for row in mtop_rows
        if row["split"] == "validation" and _mtop_label(row) is not None
    ]
    validation_labels = [str(_mtop_label(row)) for row in validation]
    validation_matrix = features.transform(
        [str(row["text"]) for row in validation]
    )
    validation_scores = np.asarray(
        classifier.decision_function(validation_matrix),
        dtype=np.float32,
    )
    validation_metrics = {
        f"top_{count}_accuracy": round(
            _top_k_accuracy(
                classifier,
                validation_scores,
                validation_labels,
                count,
            ),
            6,
        )
        for count in (1, 2, 3, 5)
    }
    if validation_metrics["top_3_accuracy"] < 0.99:
        raise RuntimeError("the operation shortlist failed its MTOP promotion floor")

    transformers = dict(features.transformer_list)
    words = transformers["words"]
    characters = transformers["characters"]
    classes = [str(value) for value in classifier.classes_]
    vocabulary = {
        "schema": "baxy.operation-shortlist-vocabulary.v1",
        "classes": classes,
        "no_action_class": NO_ACTION,
        "word_vocabulary": {
            key: int(value) for key, value in words.vocabulary_.items()
        },
        "character_vocabulary": {
            key: int(value) for key, value in characters.vocabulary_.items()
        },
        "word_ngram_range": [1, 2],
        "character_ngram_range": [3, 5],
        "strip_accents": "unicode",
        "sublinear_tf": True,
    }
    vocabulary_path = output_directory / VOCABULARY.name
    weights_path = output_directory / WEIGHTS.name
    manifest_path = output_directory / MANIFEST.name
    _write_gzip_json_atomic(vocabulary_path, vocabulary)
    _write_npz_atomic(
        weights_path,
        word_idf=np.asarray(words.idf_, dtype=np.float32),
        character_idf=np.asarray(characters.idf_, dtype=np.float32),
        coefficients=np.asarray(classifier.coef_, dtype=np.float32),
        intercept=np.asarray(classifier.intercept_, dtype=np.float32),
    )

    manifest = {
        "schema": "baxy.operation-shortlist-manifest.v1",
        "authority": "authenticated_candidate_order_only",
        "classifier": "word+character TF-IDF / LinearSVC",
        "c": 0.5,
        "training_rows": len(training),
        "training_classes": len(classes),
        "training_class_counts": dict(sorted(Counter(labels).items())),
        "sources": {
            "mtop_development_sha256": identity.corpus.sha256,
            "mtop_manifest_sha256": identity.manifest.sha256,
            "mtop_map_sha256": mtop_manifest["source"]["map_sha256"],
            "functiongemma_sha256": functiongemma_sha256,
            "excluded_corpora": [
                {"path": str(path), "sha256": _sha256(path)}
                for path in excluded_corpora
            ],
            "mtop_test_content_read": False,
        },
        "exclusions": exclusions,
        "validation": {
            "scope": "mtop_validation_development_only",
            "rows": len(validation),
            **validation_metrics,
        },
        "vocabulary": {
            "file": vocabulary_path.name,
            "bytes": vocabulary_path.stat().st_size,
            "sha256": _sha256(vocabulary_path),
        },
        "weights": {
            "file": weights_path.name,
            "bytes": weights_path.stat().st_size,
            "sha256": _sha256(weights_path),
            "arrays": {
                "word_idf": list(words.idf_.shape),
                "character_idf": list(characters.idf_.shape),
                "coefficients": list(classifier.coef_.shape),
                "intercept": list(classifier.intercept_.shape),
            },
        },
    }
    write_json_atomic(manifest_path, manifest)
    return {
        **manifest,
        "manifest": {
            "file": manifest_path.name,
            "bytes": manifest_path.stat().st_size,
            "sha256": _sha256(manifest_path),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--functiongemma", type=Path, default=FUNCTIONGEMMA)
    parser.add_argument("--output-directory", type=Path, default=DATA)
    parser.add_argument(
        "--expected-functiongemma-sha256",
        default=EXPECTED_FUNCTIONGEMMA_SHA256,
    )
    parser.add_argument("--excluded-corpus", type=Path, action="append")
    args = parser.parse_args()
    print(
        json.dumps(
            build(
                functiongemma=args.functiongemma,
                output_directory=args.output_directory,
                expected_functiongemma_sha256=(
                    args.expected_functiongemma_sha256
                ),
                excluded_corpora=(args.excluded_corpus or [EXACT_DEVELOPMENT]),
            ),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
