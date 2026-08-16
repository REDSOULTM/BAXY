"""Build the safe E5-linear semantic family arbiter product asset."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for value in (ROOT, SRC, ROOT / "experiments" / "functiongemma_selector"):
    if str(value) not in sys.path:
        sys.path.insert(0, str(value))

from benchmark_family_arbiter import DEFAULT_CACHE, _encode  # noqa: E402
from selector_common import read_jsonl, sha256  # noqa: E402
from baxy_mind.router import verified_encoder_snapshot_identity  # noqa: E402

CORPUS = ROOT / "artifacts" / "research" / "functiongemma_training_corpus.v1.jsonl"
DATA = SRC / "baxy_mind" / "data"
WEIGHTS = DATA / "semantic_family_arbiter.v1.weights.npz"
MANIFEST = DATA / "semantic_family_arbiter.v1.manifest.json"


def _write_npz_atomic(path: Path, **arrays: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".npz", dir=path.parent
    )
    os.close(descriptor)
    try:
        import numpy as np

        np.savez_compressed(temporary_name, **arrays)
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def build() -> dict[str, Any]:
    import numpy as np
    from sklearn.svm import LinearSVC

    rows = [
        row
        for row in read_jsonl(CORPUS)
        if str(row.get("operation")) != "__no_action__"
    ]
    texts = [str(row["text"]) for row in rows]
    labels = [str(row["operation"]).split(".", 1)[0] for row in rows]
    embeddings = _encode(texts, CORPUS, DEFAULT_CACHE)
    model = LinearSVC(
        C=3.0,
        class_weight="balanced",
        dual="auto",
        max_iter=20_000,
        random_state=0,
    ).fit(embeddings, labels)
    coefficients = np.asarray(model.coef_, dtype=np.float32)
    intercept = np.asarray(model.intercept_, dtype=np.float32)
    _write_npz_atomic(WEIGHTS, coefficients=coefficients, intercept=intercept)
    manifest = {
        "schema": "baxy.semantic-family-arbiter-manifest.v1",
        "classifier": "class-balanced LinearSVC over attested multilingual-e5-small embeddings",
        "c": 3.0,
        "classes": [str(value) for value in model.classes_],
        "dimensions": int(coefficients.shape[1]),
        "training_rows": len(rows),
        "training_corpus_sha256": sha256(CORPUS),
        "selection_evidence": "artifacts/research/family_arbiter_internal_validation.v1.json",
        "encoder": verified_encoder_snapshot_identity(),
        "weights": {
            "file": WEIGHTS.name,
            "bytes": WEIGHTS.stat().st_size,
            "sha256": sha256(WEIGHTS),
            "arrays": {
                "coefficients": list(coefficients.shape),
                "intercept": list(intercept.shape),
            },
        },
    }
    _write_json_atomic(MANIFEST, manifest)
    result = {
        **manifest,
        "manifest": {
            "file": MANIFEST.name,
            "bytes": MANIFEST.stat().st_size,
            "sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
        },
        "effects_executed": 0,
        "runtime_manifest_changed": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return result


if __name__ == "__main__":
    build()
