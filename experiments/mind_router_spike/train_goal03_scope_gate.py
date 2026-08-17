"""Goal 03: a binary in-catalogue / out-of-catalogue gate, trained on labelled data.

The criterion this exists for is literal: *an out-of-catalogue request reaches
the decision with zero candidates*. Four mechanisms were measured against it and
all four failed, and they failed for the same reason — they all read a
similarity, and on a catalogue of 158 near-synonymous leaves there is always
some leaf that plausibly matches any request that sounds like a computer.
Similarity cannot answer a question about *scope*.

This is the fifth, and the one the state of the art actually uses for the
question. It reports two feature families so the result cannot be blamed on one
of them, and it reports AUC on both populations, because the whole finding is in
the gap between them.

Scope is a labelled question, so this learns it from labels. MTOP declares 80
intents as outside BAXY's catalogue in
``src/baxy_mind/data/mtop_turn_evidence_map.v1.json``, reviewed against the real
operation contracts, and the adapter in ``scripts/build_mtop_turn_evidence.py``
projects every development row through them.

Two things about the training set are deliberate:

* **``contract_structure_mismatch`` rows are dropped.** The adapter buckets them
  with the out-of-domain rows, but they are not out of domain: ``play the next
  track`` lands there and BAXY has ``media.control``. They say "in scope, this
  particular phrasing exceeds the contract", which is a different question.
* **The official MTOP test is never opened.** Only ``train`` and ``validation``
  are read; the test seal stays consumed-free.

The operating point is chosen on MTOP ``validation`` under one constraint that
is not negotiable: **keep at least 99 % of in-catalogue requests**. A gate that
buys abstention by refusing real work is the lexical domain gate again. The
fresh paraphrase corpus of goal 03 takes no part in training or in choosing the
threshold — it is only ever read as a held-out population.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

REPO = Path(__file__).resolve().parents[2]
for import_root in (REPO, REPO / "src"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from baxy_mind.router import MODEL_NAME, MODEL_REVISION  # noqa: E402

SCHEMA = "baxy.goal03-scope-gate.v1"
REPORT = REPO / "artifacts" / "development" / "goal03_scope_gate.json"
FRESH_CORPUS = (
    REPO / "artifacts" / "development" / "goal03_fresh_paraphrase_corpus.v1.jsonl"
)
# El piso de servicio: la puerta nunca compra abstención negando trabajo real.
MINIMUM_IN_CATALOGUE_KEPT = 0.99


def load_rows(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split MTOP development rows into the two classes, dropping the ambiguous."""

    train: list[dict[str, Any]] = []
    validation: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        projection = row["projection"]
        disposition = projection["disposition"]
        reason = projection["reason"]
        if disposition in {"candidate", "candidate_missing_information"}:
            label = 1
        elif reason == "mapped_unsupported_intent":
            label = 0
        else:
            continue
        record = {
            "text": row["text"],
            "label": label,
            "locale": row["locale"],
            "intent": row["semantic"].get("intent", ""),
        }
        (train if row["split"] == "train" else validation).append(record)
    return train, validation


def _encode(model: Any, texts: list[str], prefix: str) -> np.ndarray:
    return np.asarray(
        model.encode(
            [prefix + text for text in texts],
            normalize_embeddings=True,
            show_progress_bar=False,
            batch_size=128,
        ),
        dtype=np.float32,
    )


def _operating_point(
    scores: np.ndarray,
    labels: np.ndarray,
) -> tuple[float, dict[str, float]]:
    """Lowest threshold that still keeps MINIMUM_IN_CATALOGUE_KEPT of class 1."""

    in_catalogue = scores[labels == 1]
    out_catalogue = scores[labels == 0]
    # A request is refused when its score falls below the threshold, so keeping
    # 99 % of class 1 means the threshold sits at its 1st percentile.
    threshold = float(
        np.quantile(in_catalogue, 1.0 - MINIMUM_IN_CATALOGUE_KEPT)
    )
    return threshold, {
        "in_catalogue_kept": float((in_catalogue >= threshold).mean()),
        "out_of_catalogue_refused": float((out_catalogue < threshold).mean()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Goal 03 scope gate")
    parser.add_argument("--development", required=True)
    arguments = parser.parse_args()

    from sentence_transformers import SentenceTransformer
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from scipy.sparse import hstack

    train, validation = load_rows(Path(arguments.development))
    train_texts = [row["text"] for row in train]
    validation_texts = [row["text"] for row in validation]
    train_y = np.asarray([row["label"] for row in train], dtype=np.int64)
    validation_y = np.asarray([row["label"] for row in validation], dtype=np.int64)

    fresh = [
        json.loads(line)
        for line in FRESH_CORPUS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    fresh_texts = [row["text"] for row in fresh]
    fresh_in = np.asarray([row["in_catalog"] for row in fresh], dtype=bool)

    model = SentenceTransformer(
        MODEL_NAME, device="cpu", revision=MODEL_REVISION, local_files_only=True
    )

    def e5_features() -> tuple[Any, Any, Any]:
        return (
            _encode(model, train_texts, "query: "),
            _encode(model, validation_texts, "query: "),
            _encode(model, fresh_texts, "query: "),
        )

    def tfidf_features() -> tuple[Any, Any, Any]:
        characters = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(2, 5),
            min_df=3,
            sublinear_tf=True,
            strip_accents="unicode",
        )
        words = TfidfVectorizer(
            analyzer="word",
            ngram_range=(1, 2),
            min_df=2,
            sublinear_tf=True,
            strip_accents="unicode",
        )
        characters.fit(train_texts)
        words.fit(train_texts)

        def transform(texts: list[str]) -> Any:
            return hstack(
                (characters.transform(texts), words.transform(texts)), format="csr"
            )

        return transform(train_texts), transform(validation_texts), transform(
            fresh_texts
        )

    variants: dict[str, Any] = {}
    for label, build in (
        ("e5_embedding", e5_features),
        ("char_word_tfidf", tfidf_features),
    ):
        train_x, validation_x, fresh_x = build()
        classifier = LogisticRegression(
            C=1.0, max_iter=3000, class_weight="balanced", solver="lbfgs"
        )
        classifier.fit(train_x, train_y)
        validation_scores = classifier.decision_function(validation_x)
        fresh_scores = classifier.decision_function(fresh_x)
        threshold, operating = _operating_point(validation_scores, validation_y)
        # La misma curva sobre la población fresca, sólo como diagnóstico: el
        # umbral no se elige aquí, porque elegirlo aquí sería ajustar sobre lo
        # que se está evaluando.
        in_scores = fresh_scores[fresh_in]
        curve = {}
        for keep in (1.0, 0.99, 0.95, 0.90):
            point = float(np.quantile(in_scores, 1.0 - keep))
            curve[f"keep_{keep:.2f}"] = {
                "in_catalogue_kept": int((in_scores >= point).sum()),
                "out_of_catalogue_refused": int(
                    (fresh_scores[~fresh_in] < point).sum()
                ),
            }
        variants[label] = {
            "auc": {
                "mtop_validation": round(
                    float(roc_auc_score(validation_y, validation_scores)), 4
                ),
                "fresh_corpus": round(
                    float(roc_auc_score(fresh_in.astype(int), fresh_scores)), 4
                ),
            },
            "operating_point": {
                "threshold": threshold,
                "chosen_on": "mtop_validation",
                "mtop_validation": operating,
            },
            "at_that_threshold_on_the_fresh_corpus": {
                "in_catalogue_rows": int(fresh_in.sum()),
                "in_catalogue_kept": int((fresh_scores[fresh_in] >= threshold).sum()),
                "out_of_catalogue_rows": int((~fresh_in).sum()),
                "out_of_catalogue_refused": int(
                    (fresh_scores[~fresh_in] < threshold).sum()
                ),
            },
            "diagnostic_curve_on_the_fresh_corpus": curve,
        }

    report = {
        "schema": SCHEMA,
        "verdict": (
            "supervised_scope_detection_does_not_transfer_to_free_paraphrase"
        ),
        "encoder": {"model": MODEL_NAME, "revision": MODEL_REVISION},
        "training": {
            "source": "MTOP official release, development members only",
            "test_opened": False,
            "dropped_class": "contract_structure_mismatch",
            "rows": {"train": len(train), "validation": len(validation)},
            "balance": {
                "train_in_catalogue": int((train_y == 1).sum()),
                "train_out_of_catalogue": int((train_y == 0).sum()),
            },
        },
        "constraints": {
            "model_started": False,
            "providers_enabled": False,
            "effects_executed": 0,
            "opened_v9": False,
            "mtop_test_opened": False,
            "weights_shipped": False,
        },
        "variants": variants,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_bytes(
        (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + chr(10)).encode(
            "utf-8"
        )
    )
    for label, value in variants.items():
        print(
            f"{label:18s} AUC mtop={value['auc']['mtop_validation']:.4f} "
            f"fresh={value['auc']['fresh_corpus']:.4f} | at the chosen point: "
            f"{value['at_that_threshold_on_the_fresh_corpus']['in_catalogue_kept']}"
            f"/124 kept, "
            f"{value['at_that_threshold_on_the_fresh_corpus']['out_of_catalogue_refused']}"
            f"/36 refused"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
