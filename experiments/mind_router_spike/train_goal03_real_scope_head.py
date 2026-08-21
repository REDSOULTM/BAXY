"""Train one preregistered call/no-call head without opening Goal 03 fresh data.

The multilingual E5 encoder is already resident in BAXY.  This experiment only
learns a calibrated linear head over its query embeddings.  Model, revision,
corpora, hashes, classifier and operating-point rule are fixed by V41 before the
program may be run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any, Iterable

import numpy as np


REPO = Path(__file__).resolve().parents[2]
for import_root in (REPO, REPO / "src"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from baxy_mind.router import MODEL_NAME, MODEL_REVISION  # noqa: E402
from experiments.mind_router_spike import (  # noqa: E402
    attest_clinc_oos_development_r251 as clinc,
)


SCHEMA = "baxy.goal03-real-scope-head.v1"
TRAIN = Path(r"D:\BAXYRuntime\experiments\functiongemma-current-union-v1\train.jsonl")
CALIBRATION = Path(
    r"D:\BAXYRuntime\experiments\functiongemma-current-union-v1\validation.jsonl"
)
REAL_TRAIN = Path(
    r"D:\BAXYRuntime\experiments\functiongemma-real-language-v1\mapped_train.jsonl"
)
REAL_VALIDATION = Path(
    r"D:\BAXYRuntime\experiments\functiongemma-real-language-v1\current_union_validation.jsonl"
)
OUTPUT = REPO / "artifacts/development/goal03_real_scope_head_v42.json"
HEAD_OUTPUT = Path(r"D:\BAXYRuntime\experiments\goal03-real-scope-head-v1\scope_head.npz")

EXPECTED_SHA256 = {
    TRAIN: "69e8bcde6760258a6e8d750caa3c648fc85695c0cccd7f6ad6926a92935b8bad",
    CALIBRATION: "a81a50fc80af209d9c6827ac81e300d2ebcc9f493c473b2708e58aa5b52ddab2",
    REAL_TRAIN: "220ad03345aad2a6470be6c5e2353c7bc6c95689a6b5ab1c884212f8eabe853f",
    REAL_VALIDATION: "c42d27e6ccdc03d0ee6dcce20ca26a52b5c1e49e869b8bdfa91db2b88e622300",
    clinc.SOURCE: clinc.SOURCE_SHA256,
}

MINIMUM_CALIBRATION_ACTION_KEEP = 0.99
MINIMUM_REAL_ACTIONS_KEPT = 70
MINIMUM_CALIBRATION_OOS_REFUSED = 246
MINIMUM_CLINC_OOS_REFUSED = 80


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text.casefold())
    plain = "".join(char for char in folded if not unicodedata.combining(char))
    return " ".join(re.findall(r"[a-z0-9]+", plain))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            text = row.get("text")
            operation = row.get("operation")
            if not isinstance(text, str) or not text.strip() or not isinstance(operation, str):
                raise ValueError(f"invalid labelled row at {path}:{line_number}")
            rows.append(row)
    if not rows:
        raise ValueError(f"empty corpus: {path}")
    return rows


def labelled(rows: Iterable[dict[str, Any]], source: str) -> list[dict[str, Any]]:
    return [
        {
            "text": str(row["text"]),
            "label": int(row["operation"] != "__no_action__"),
            "source": source,
        }
        for row in rows
    ]


def deduplicate(rows: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    by_text: dict[str, dict[str, Any]] = {}
    duplicates = 0
    for row in rows:
        key = normalize(str(row["text"]))
        if not key:
            raise ValueError("normalization produced an empty training text")
        previous = by_text.get(key)
        if previous is not None:
            if int(previous["label"]) != int(row["label"]):
                raise ValueError(f"conflicting labels for normalized text SHA {hashlib.sha256(key.encode()).hexdigest()}")
            duplicates += 1
            continue
        by_text[key] = row
    return list(by_text.values()), duplicates


def threshold_for_keep(scores: np.ndarray, minimum_keep: float) -> float:
    if scores.ndim != 1 or not len(scores) or not 0.0 < minimum_keep <= 1.0:
        raise ValueError("invalid threshold inputs")
    maximum_rejected = math.floor((1.0 - minimum_keep) * len(scores))
    ordered = np.sort(scores)
    return float(ordered[maximum_rejected])


def encode(model: Any, texts: list[str]) -> np.ndarray:
    return np.asarray(
        model.encode(
            ["query: " + text for text in texts],
            normalize_embeddings=True,
            show_progress_bar=False,
            batch_size=128,
        ),
        dtype=np.float32,
    )


def summarize(scores: np.ndarray, labels: np.ndarray, threshold: float) -> dict[str, Any]:
    from sklearn.metrics import roc_auc_score

    predicted_action = scores >= threshold
    actions = labels == 1
    oos = ~actions
    result: dict[str, Any] = {
        "rows": int(len(labels)),
        "actions": int(actions.sum()),
        "oos": int(oos.sum()),
        "actions_kept": int((predicted_action & actions).sum()),
        "oos_refused": int((~predicted_action & oos).sum()),
    }
    if actions.any() and oos.any():
        result["roc_auc"] = round(float(roc_auc_score(labels, scores)), 6)
    return result


def run(output: Path, head_output: Path) -> dict[str, Any]:
    from sentence_transformers import SentenceTransformer
    from sklearn.linear_model import LogisticRegression

    if output.exists() or head_output.exists():
        raise FileExistsError("refusing to overwrite scope-head evidence")
    for path, expected in EXPECTED_SHA256.items():
        if not path.is_file() or sha256(path) != expected:
            raise RuntimeError(f"source identity mismatch: {path}")

    train_base = labelled(read_jsonl(TRAIN), "current-union-train")
    train_real = labelled(read_jsonl(REAL_TRAIN), "inherited-real-train")
    calibration = labelled(read_jsonl(CALIBRATION), "current-union-validation")
    real_validation = labelled(
        read_jsonl(REAL_VALIDATION), "inherited-real-validation"
    )
    training, duplicate_rows = deduplicate([*train_base, *train_real])

    training_keys = {normalize(row["text"]) for row in training}
    calibration_keys = {normalize(row["text"]) for row in calibration}
    real_validation_keys = {normalize(row["text"]) for row in real_validation}
    if training_keys & calibration_keys or training_keys & real_validation_keys:
        raise RuntimeError("training overlaps a sealed evaluation population")

    clinc_rows = clinc.development_rows()
    if len(clinc_rows["oos_train"]) != 250 or len(clinc_rows["oos_val"]) != 100:
        raise RuntimeError("unexpected CLINC development identity")
    clinc_validation = [str(row[0]) for row in clinc_rows["oos_val"]]
    if training_keys & {normalize(text) for text in clinc_validation}:
        raise RuntimeError("training overlaps CLINC OOS validation")

    model = SentenceTransformer(
        MODEL_NAME, device="cpu", revision=MODEL_REVISION, local_files_only=True
    )
    started = time.perf_counter()
    train_x = encode(model, [row["text"] for row in training])
    calibration_x = encode(model, [row["text"] for row in calibration])
    real_x = encode(model, [row["text"] for row in real_validation])
    clinc_x = encode(model, clinc_validation)
    embedding_seconds = time.perf_counter() - started

    train_y = np.asarray([row["label"] for row in training], dtype=np.int64)
    calibration_y = np.asarray([row["label"] for row in calibration], dtype=np.int64)
    real_y = np.asarray([row["label"] for row in real_validation], dtype=np.int64)
    if not np.all(real_y == 1):
        raise RuntimeError("real validation is no longer an action-only holdout")

    classifier = LogisticRegression(
        C=1.0,
        class_weight="balanced",
        max_iter=3000,
        random_state=5601,
        solver="lbfgs",
    )
    started = time.perf_counter()
    classifier.fit(train_x, train_y)
    fit_seconds = time.perf_counter() - started
    calibration_scores = classifier.decision_function(calibration_x)
    real_scores = classifier.decision_function(real_x)
    clinc_scores = classifier.decision_function(clinc_x)
    threshold = threshold_for_keep(
        calibration_scores[calibration_y == 1], MINIMUM_CALIBRATION_ACTION_KEEP
    )

    calibration_summary = summarize(calibration_scores, calibration_y, threshold)
    real_summary = summarize(real_scores, real_y, threshold)
    clinc_summary = summarize(
        clinc_scores, np.zeros(len(clinc_scores), dtype=np.int64), threshold
    )
    checks = {
        "calibration_actions_kept": calibration_summary["actions_kept"] >= 473,
        "calibration_oos_refused": calibration_summary["oos_refused"]
        >= MINIMUM_CALIBRATION_OOS_REFUSED,
        "real_actions_kept": real_summary["actions_kept"] >= MINIMUM_REAL_ACTIONS_KEPT,
        "clinc_oos_refused": clinc_summary["oos_refused"]
        >= MINIMUM_CLINC_OOS_REFUSED,
    }

    head_output.parent.mkdir(parents=True, exist_ok=False)
    np.savez_compressed(
        head_output,
        coefficients=np.asarray(classifier.coef_, dtype=np.float32),
        intercept=np.asarray(classifier.intercept_, dtype=np.float32),
        threshold=np.asarray([threshold], dtype=np.float32),
    )
    report = {
        "schema": SCHEMA,
        "encoder": {"model": MODEL_NAME, "revision": MODEL_REVISION, "dimensions": 384},
        "classifier": {
            "kind": "sklearn.LogisticRegression",
            "C": 1.0,
            "class_weight": "balanced",
            "solver": "lbfgs",
            "random_state": 5601,
            "threshold": threshold,
            "threshold_rule": "lowest calibration-action score after allowing at most floor(1%-of-actions) lower scores",
        },
        "sources": {
            str(path): {"sha256": expected, "rows": sum(1 for line in path.open(encoding="utf-8") if line.strip()) if path.suffix == ".jsonl" else None}
            for path, expected in EXPECTED_SHA256.items()
        },
        "training": {
            "rows_after_normalized_deduplication": len(training),
            "actions": int(train_y.sum()),
            "oos": int((train_y == 0).sum()),
            "same_label_duplicates_removed": duplicate_rows,
            "embedding_seconds": round(embedding_seconds, 6),
            "fit_seconds": round(fit_seconds, 6),
        },
        "evaluation": {
            "calibration": calibration_summary,
            "inherited_real_actions": real_summary,
            "clinc_oos_validation": clinc_summary,
        },
        "acceptance": {
            "requirements": {
                "calibration_actions_kept": 473,
                "calibration_oos_refused": MINIMUM_CALIBRATION_OOS_REFUSED,
                "real_actions_kept": MINIMUM_REAL_ACTIONS_KEPT,
                "clinc_oos_refused": MINIMUM_CLINC_OOS_REFUSED,
            },
            "checks": checks,
            "passed": all(checks.values()),
        },
        "head": {"path": str(head_output), "sha256": sha256(head_output)},
        "constraints": {
            "fresh_corpus_opened": False,
            "clinc_test_opened": False,
            "providers_enabled": False,
            "effects_executed": 0,
            "runtime_modified": False,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--head-output", type=Path, default=HEAD_OUTPUT)
    args = parser.parse_args()
    report = run(args.output.resolve(), args.head_output.resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
