"""Attested, non-authoritative operation-family shortlist classifier."""

from __future__ import annotations

import gzip
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Iterable

import numpy as np
from scipy.sparse import hstack
from sklearn.feature_extraction.text import TfidfVectorizer

DATA = Path(__file__).resolve().parent / "data"
MANIFEST = DATA / "family_classifier.v1.manifest.json"
EXPECTED_MANIFEST_SHA256 = (
    "4a287113c73e4371012af47c1dd6552ea1afcac7bf040ad547d6c6fd2896ec64"
)
# A closed-set LinearSVC always names a family, even for an open-world request
# that belongs to none of them.  The reviewed current-catalog development
# population has no correct raw decision below this margin; abstention delegates
# to the existing semantic retrieval path and can never add operation authority.
MIN_PREDICTION_MARGIN = 0.05


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class FamilyPrediction:
    family: str
    margin: float


class FamilyClassifier:
    """Load only hash-bound JSON/NumPy data; never deserialize executable code."""

    _shared: tuple[Any, ...] | None = None
    _lock = Lock()

    def __init__(self) -> None:
        self._resources = self._load_shared()

    @classmethod
    def _load_shared(cls) -> tuple[Any, ...]:
        with cls._lock:
            if cls._shared is not None:
                return cls._shared
            if _sha256(MANIFEST) != EXPECTED_MANIFEST_SHA256:
                raise RuntimeError("el manifest del clasificador de familias no coincide")
            manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
            if manifest.get("schema") != "baxy.family-classifier-manifest.v1":
                raise RuntimeError("manifest del clasificador de familias inválido")
            vocabulary_path = DATA / str(manifest["vocabulary"]["file"])
            weights_path = DATA / str(manifest["weights"]["file"])
            for path, identity in (
                (vocabulary_path, manifest["vocabulary"]),
                (weights_path, manifest["weights"]),
            ):
                if (
                    not path.is_file()
                    or path.stat().st_size != identity["bytes"]
                    or _sha256(path) != identity["sha256"]
                ):
                    raise RuntimeError(
                        "un activo del clasificador de familias no coincide"
                    )
            with gzip.open(vocabulary_path, "rt", encoding="utf-8") as handle:
                vocabulary = json.load(handle)
            if vocabulary.get("schema") != "baxy.family-classifier-vocabulary.v1":
                raise RuntimeError("vocabulario del clasificador de familias inválido")
            resources = cls._build_resources(vocabulary, weights_path)
            cls._shared = resources
            return resources

    @staticmethod
    def _build_resources(
        vocabulary: dict[str, Any],
        weights_path: Path,
    ) -> tuple[Any, ...]:
        characters = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=tuple(vocabulary["character_ngram_range"]),
            vocabulary=vocabulary["character_vocabulary"],
            sublinear_tf=True,
            strip_accents="unicode",
        )
        words = TfidfVectorizer(
            analyzer="word",
            ngram_range=tuple(vocabulary["word_ngram_range"]),
            vocabulary=vocabulary["word_vocabulary"],
            sublinear_tf=True,
            strip_accents="unicode",
        )
        characters.fit(["baxy classifier bootstrap"])
        words.fit(["baxy classifier bootstrap"])
        with np.load(weights_path, allow_pickle=False) as arrays:
            character_idf = np.asarray(arrays["character_idf"], dtype=np.float64)
            word_idf = np.asarray(arrays["word_idf"], dtype=np.float64)
            coefficients = np.asarray(arrays["coefficients"], dtype=np.float64)
            intercept = np.asarray(arrays["intercept"], dtype=np.float64)
        classes = tuple(str(value) for value in vocabulary["classes"])
        feature_count = len(character_idf) + len(word_idf)
        if (
            character_idf.shape != (len(characters.vocabulary_),)
            or word_idf.shape != (len(words.vocabulary_),)
            or coefficients.shape
            != (len(classes), feature_count)
            or intercept.shape != (len(classes),)
            or not all(
                np.isfinite(value).all()
                for value in (
                    character_idf,
                    word_idf,
                    coefficients,
                    intercept,
                )
            )
        ):
            raise RuntimeError("pesos del clasificador de familias inválidos")
        characters.idf_ = character_idf
        words.idf_ = word_idf
        return (
            characters,
            words,
            classes,
            coefficients,
            intercept,
        )

    def predict(
        self,
        text: str,
        available_families: Iterable[str],
    ) -> FamilyPrediction | None:
        if not isinstance(text, str) or not text.strip():
            return None
        (
            characters,
            words,
            classes,
            coefficients,
            intercept,
        ) = self._resources
        allowed = set(available_families)
        allowed_indexes = [
            index for index, family in enumerate(classes) if family in allowed
        ]
        if not allowed_indexes:
            return None
        features = hstack(
            (
                characters.transform([text]),
                words.transform([text]) * 1.5,
            ),
            format="csr",
        )
        scores = np.asarray(features @ coefficients.T + intercept).reshape(-1)
        ordered = sorted(allowed_indexes, key=lambda index: float(scores[index]))
        winner = ordered[-1]
        runner_up = ordered[-2] if len(ordered) > 1 else winner
        margin = float(scores[winner] - scores[runner_up])
        if margin < MIN_PREDICTION_MARGIN:
            return None
        return FamilyPrediction(family=classes[winner], margin=margin)
