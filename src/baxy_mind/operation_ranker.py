"""Frozen leaf ranker used only as one half of the retrieval union.

The weights are the Goal 03B ``operation_shortlist_v3`` LinearSVC, inherited
byte-identical from the previous BAXY tree.  They never authorize an
operation; they only propose names that E5 may have ranked too low.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
from threading import Lock
from typing import Any

import numpy as np
from scipy.sparse import hstack
from sklearn.feature_extraction.text import TfidfVectorizer

DATA = Path(__file__).resolve().parent / "data"
VOCABULARY = DATA / "operation_shortlist.v1.vocabulary.json.gz"
WEIGHTS = DATA / "operation_shortlist.v1.weights.npz"
EXPECTED_VOCABULARY_SHA256 = (
    "cdffce45c4f6b0562ca884c189c405bf88f41a9d4a3089b90b9ee8791165d1b0"
)
EXPECTED_WEIGHTS_SHA256 = (
    "63de7aaeb52cf14e034828315656343b96b5125a33c48e6a5d6d1183bbc14d12"
)
NO_ACTION = "__none__"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class OperationRanker:
    """Hash-bound TF-IDF / LinearSVC ranking of catalog leaves."""

    _shared: tuple[Any, ...] | None = None
    _lock = Lock()

    def __init__(self) -> None:
        self._resources = self._load_shared()

    @classmethod
    def _load_shared(cls) -> tuple[Any, ...]:
        with cls._lock:
            if cls._shared is not None:
                return cls._shared
            if _sha256(VOCABULARY) != EXPECTED_VOCABULARY_SHA256:
                raise RuntimeError("el vocabulario del ranker de operaciones no coincide")
            if _sha256(WEIGHTS) != EXPECTED_WEIGHTS_SHA256:
                raise RuntimeError("los pesos del ranker de operaciones no coinciden")
            with gzip.open(VOCABULARY, "rt", encoding="utf-8") as handle:
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
            with np.load(WEIGHTS, allow_pickle=False) as arrays:
                words.idf_ = np.asarray(arrays["word_idf"], dtype=np.float64)
                characters.idf_ = np.asarray(arrays["character_idf"], dtype=np.float64)
                coefficients = np.asarray(arrays["coefficients"], dtype=np.float64)
                intercept = np.asarray(arrays["intercept"], dtype=np.float64)
            classes = tuple(str(value) for value in vocabulary["classes"])
            cls._shared = (words, characters, classes, coefficients, intercept)
            return cls._shared

    def rank(self, text: str) -> tuple[str, ...]:
        if not isinstance(text, str) or not text.strip():
            return ()
        words, characters, classes, coefficients, intercept = self._resources
        features = hstack(
            (words.transform([text]), characters.transform([text])),
            format="csr",
        )
        scores = np.asarray(features @ coefficients.T + intercept).reshape(-1)
        order = np.argsort(-scores)
        return tuple(
            classes[index]
            for index in order
            if classes[index] != NO_ACTION
        )
