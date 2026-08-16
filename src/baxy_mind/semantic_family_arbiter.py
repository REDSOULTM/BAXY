"""Attested semantic operation-family ranks over the existing E5 embedding."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Iterable

DATA = Path(__file__).resolve().parent / "data"
MANIFEST = DATA / "semantic_family_arbiter.v1.manifest.json"
EXPECTED_MANIFEST_SHA256 = (
    "b0d2701aaa82ced107a2242738b61cf42c7cf667976cfbbab9f385f25bad1e29"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class SemanticFamilyPrediction:
    family: str
    score: float
    margin: float


class SemanticFamilyArbiter:
    """Rank families from one already-attested 384-dimensional E5 row."""

    _shared: tuple[Any, ...] | None = None
    _lock = Lock()

    def __init__(self) -> None:
        self._resources = self._load_shared()

    @classmethod
    def _load_shared(cls) -> tuple[Any, ...]:
        import numpy as np

        with cls._lock:
            if cls._shared is not None:
                return cls._shared
            if _sha256(MANIFEST) != EXPECTED_MANIFEST_SHA256:
                raise RuntimeError("el manifest del árbitro semántico no coincide")
            manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
            if manifest.get("schema") != "baxy.semantic-family-arbiter-manifest.v1":
                raise RuntimeError("manifest del árbitro semántico inválido")
            weights = DATA / str(manifest["weights"]["file"])
            identity = manifest["weights"]
            if (
                not weights.is_file()
                or weights.stat().st_size != identity["bytes"]
                or _sha256(weights) != identity["sha256"]
            ):
                raise RuntimeError("los pesos del árbitro semántico no coinciden")
            with np.load(weights, allow_pickle=False) as arrays:
                coefficients = np.asarray(arrays["coefficients"], dtype=np.float32)
                intercept = np.asarray(arrays["intercept"], dtype=np.float32)
            classes = tuple(str(value) for value in manifest["classes"])
            dimensions = int(manifest["dimensions"])
            if (
                coefficients.shape != (len(classes), dimensions)
                or intercept.shape != (len(classes),)
                or not np.isfinite(coefficients).all()
                or not np.isfinite(intercept).all()
            ):
                raise RuntimeError("pesos del árbitro semántico inválidos")
            cls._shared = classes, coefficients, intercept, dimensions
            return cls._shared

    def rank(
        self,
        embedding: Any,
        available_families: Iterable[str],
        *,
        count: int = 1,
    ) -> tuple[SemanticFamilyPrediction, ...]:
        import numpy as np

        classes, coefficients, intercept, dimensions = self._resources
        row = np.asarray(embedding, dtype=np.float32).reshape(-1)
        if row.shape != (dimensions,) or not np.isfinite(row).all():
            return ()
        allowed = set(available_families)
        indexes = [index for index, family in enumerate(classes) if family in allowed]
        if not indexes or count <= 0:
            return ()
        scores = np.asarray(coefficients @ row + intercept).reshape(-1)
        ordered = sorted(indexes, key=lambda index: float(scores[index]), reverse=True)
        limit = min(int(count), len(ordered))
        predictions: list[SemanticFamilyPrediction] = []
        for position, index in enumerate(ordered[:limit]):
            next_index = ordered[position + 1] if position + 1 < len(ordered) else index
            predictions.append(
                SemanticFamilyPrediction(
                    family=classes[index],
                    score=float(scores[index]),
                    margin=float(scores[index] - scores[next_index]),
                )
            )
        return tuple(predictions)
