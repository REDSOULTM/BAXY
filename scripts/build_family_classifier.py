"""Build the safe, versioned lexical family-classifier product asset."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scripts.measure_mind_budget import (  # noqa: E402
    DEFAULT_CORE_CANDIDATES,
    current_core_capabilities,
    discover_core,
    write_json_atomic,
)

from experiments.mind_router_spike.probe_heldout_family_classifier import (  # noqa: E402
    _catalog_seed_pool,
    _fit_lexical,
    _historical_support_pool,
    _normal_key,
    _qualifying_pool,
    _universal_holdout,
)
from experiments.mind_router_spike.probe_paraphrase_tool_quality import (  # noqa: E402
    _oracle,
)
DATA = SRC / "baxy_mind" / "data"
VOCABULARY = DATA / "family_classifier.v1.vocabulary.json.gz"
WEIGHTS = DATA / "family_classifier.v1.weights.npz"
MANIFEST = DATA / "family_classifier.v1.manifest.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_capabilities(capabilities: list[dict[str, Any]]) -> bytes:
    return (
        json.dumps(
            capabilities,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


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


def build() -> dict[str, Any]:
    capabilities = current_core_capabilities(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES))
    )
    catalog_names = tuple(str(item["name"]) for item in capabilities)
    primary_holdout = _oracle(catalog_names)
    primary_keys = {_normal_key(row["text"]) for row in primary_holdout}
    qualifying = _qualifying_pool(catalog_names)
    qualifying_training = [
        row for row in qualifying if _normal_key(row["text"]) not in primary_keys
    ]
    universal_holdout = _universal_holdout(
        qualifying_training,
        cases=min(
            20,
            len({row["family"] for row in qualifying_training}),
        ),
    )
    universal_keys = {_normal_key(row["text"]) for row in universal_holdout}
    qualifying_training = [
        row
        for row in qualifying_training
        if _normal_key(row["text"]) not in universal_keys
    ]
    support = _historical_support_pool(catalog_names, primary_keys)
    seeds = _catalog_seed_pool(capabilities, primary_keys)
    training_by_key: dict[str, dict[str, Any]] = {}
    for row in qualifying_training + support + seeds:
        key = _normal_key(row["text"])
        if key in universal_keys:
            continue
        training_by_key.setdefault(key, row)
    training = list(training_by_key.values())
    if primary_keys & set(training_by_key) or universal_keys & set(training_by_key):
        raise RuntimeError("family classifier training overlaps a frozen holdout")

    pipeline = _fit_lexical(
        [row["text"] for row in training],
        [row["family"] for row in training],
        0.3,
    )
    features = pipeline.named_steps["features"]
    classifier = pipeline.named_steps["classifier"]
    transformers = dict(features.transformer_list)
    characters = transformers["characters"]
    words = transformers["words"]
    classes = [str(value) for value in classifier.classes_]

    vocabulary_payload = {
        "schema": "baxy.family-classifier-vocabulary.v1",
        "classes": classes,
        "character_vocabulary": {
            key: int(value) for key, value in characters.vocabulary_.items()
        },
        "word_vocabulary": {
            key: int(value) for key, value in words.vocabulary_.items()
        },
        "character_ngram_range": [2, 5],
        "word_ngram_range": [1, 2],
        "character_weight": 1.0,
        "word_weight": 1.5,
        "strip_accents": "unicode",
        "sublinear_tf": True,
    }
    _write_gzip_json_atomic(VOCABULARY, vocabulary_payload)
    _write_npz_atomic(
        WEIGHTS,
        character_idf=np.asarray(characters.idf_, dtype=np.float64),
        word_idf=np.asarray(words.idf_, dtype=np.float64),
        coefficients=np.asarray(classifier.coef_, dtype=np.float64),
        intercept=np.asarray(classifier.intercept_, dtype=np.float64),
    )

    historical = ROOT / "tests" / "data" / "historical_messages.jsonl"
    manifest = {
        "schema": "baxy.family-classifier-manifest.v1",
        "classifier": "word+character TF-IDF / class-balanced LinearSVC",
        "c": 0.3,
        "training_rows": len(training),
        "primary_holdout_rows": len(primary_holdout),
        "universal_holdout_rows": len(universal_holdout),
        "normalised_training_overlap_primary": 0,
        "normalised_training_overlap_universal": 0,
        "historical_messages_sha256": _sha256(historical),
        "capabilities_sha256": hashlib.sha256(
            _canonical_capabilities(capabilities)
        ).hexdigest(),
        "vocabulary": {
            "file": VOCABULARY.name,
            "bytes": VOCABULARY.stat().st_size,
            "sha256": _sha256(VOCABULARY),
        },
        "weights": {
            "file": WEIGHTS.name,
            "bytes": WEIGHTS.stat().st_size,
            "sha256": _sha256(WEIGHTS),
            "arrays": {
                "character_idf": list(characters.idf_.shape),
                "word_idf": list(words.idf_.shape),
                "coefficients": list(classifier.coef_.shape),
                "intercept": list(classifier.intercept_.shape),
            },
        },
    }
    write_json_atomic(MANIFEST, manifest)
    return {
        **manifest,
        "manifest": {
            "file": MANIFEST.name,
            "bytes": MANIFEST.stat().st_size,
            "sha256": _sha256(MANIFEST),
        },
    }


def main() -> int:
    print(json.dumps(build(), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
